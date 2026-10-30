"""RenderPlan：排版中间表示。

题库 → RenderPlan（纯数据结构）→ 两个消费者：
  * exporter.writer_docx  生成 .docx
  * prints 视图            生成 A4 打印 HTML

好处是编号规则、答题说明、选项样式、图片位置、答案页这些排版逻辑**只写一遍**，
不会出现「导出的 Word 和网页上看到的不一样」。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from apps.paper.models import Paper

CN_NUM = "一二三四五六七八九十"


def cn_number(n: int) -> str:
    if n <= 10:
        return CN_NUM[n - 1]
    if n < 20:
        return "十" + CN_NUM[n - 11]
    tens, ones = divmod(n, 10)
    return CN_NUM[tens - 1] + "十" + (CN_NUM[ones - 1] if ones else "")


@dataclass
class RenderOption:
    key: str
    text: str
    image_path: str | None = None
    image_url: str | None = None


@dataclass
class RenderItem:
    """卷面上独立的一道题。"""

    no: str = ""
    type_code: str = ""
    renderer_key: str = "generic"
    stem: str = ""
    options: list[RenderOption] = field(default_factory=list)
    layout: str = "vertical"
    content: dict[str, Any] = field(default_factory=dict)
    answer: dict[str, Any] = field(default_factory=dict)
    answer_text: str = ""
    explanation: str = ""
    points: Decimal = Decimal("0")
    answer_lines: int = 0
    stem_image_path: str | None = None
    stem_image_url: str | None = None
    audio: dict[str, Any] | None = None
    audio_play_count: int = 1
    passage: dict[str, Any] | None = None  # 仅在该组小题的首题携带
    paper_item_id: int | None = None
    question_id: int | None = None


@dataclass
class RenderSection:
    order: int = 0
    title: str = ""
    directions: str = ""
    number_style: str = "arabic"
    items: list[RenderItem] = field(default_factory=list)
    audio: dict[str, Any] | None = None

    @property
    def display_title(self) -> str:
        prefix = cn_number(self.order) + "、" if self.order else ""
        return f"{prefix}{self.title}"

    def subtotal(self) -> Decimal:
        return sum((item.points for item in self.items), Decimal("0"))


@dataclass
class RenderPlan:
    """整份试卷的可渲染结构。"""

    paper_id: int = 0
    title: str = ""
    subtitle: str = ""
    grade: int = 0
    term: str = ""
    duration_min: int = 0
    total_score: Decimal = Decimal("0")
    header: dict[str, Any] = field(default_factory=dict)
    sections: list[RenderSection] = field(default_factory=list)
    media_manifest: list[dict[str, Any]] = field(default_factory=list)
    answer_sheet: list[RenderItem] = field(default_factory=list)
    include_answers: bool = False

    def all_items(self) -> list[RenderItem]:
        return [item for section in self.sections for item in section.items]


# --------------------------------------------------------------------------- 构建


def _media_info(asset) -> dict[str, Any] | None:
    if not asset:
        return None
    try:
        path = asset.file.path
    except Exception:  # noqa: BLE001 - 文件缺失时不影响出题流程
        path = ""
    return {
        "path": path,
        "url": asset.url,
        "filename": asset.original_filename or (asset.file.name if asset.file else ""),
        "duration": float(asset.duration_sec) if asset.duration_sec else None,
        "kind": asset.kind,
    }


def build_render_plan(paper: Paper, include_answers: bool | None = None) -> RenderPlan:
    """把 Paper 翻译成 RenderPlan。"""
    if include_answers is None:
        include_answers = paper.answer_included

    plan = RenderPlan(
        paper_id=paper.id,
        title=paper.title,
        subtitle=paper.subtitle,
        grade=paper.grade,
        term=paper.term,
        duration_min=paper.duration_min,
        total_score=paper.computed_total_score,
        header=paper.header,
        include_answers=include_answers,
    )

    seen_passage_ids: set[int] = set()
    audio_seen: set[str] = set()

    for section in paper.sections.prefetch_related("items__question__question_type", "items__question__passage"):
        render_section = RenderSection(
            order=section.order,
            title=section.title,
            directions=section.directions,
            number_style=section.number_style,
            audio=_media_info(section.listening_audio) or _media_info(paper.listening_audio),
        )

        ordered = list(section.items.all().select_related(
            "question", "question__question_type", "question__passage",
            "question__stem_image", "question__audio",
        ))

        for index, pq in enumerate(ordered, start=1):
            question = pq.question
            content = pq.content()
            answer = pq.answer()
            qtype = question.question_type

            item = RenderItem(
                type_code=qtype.code,
                renderer_key=qtype.renderer_key or "generic",
                stem=pq.stem(),
                layout=question.option_layout,
                content=content,
                answer=answer,
                answer_text=question.answer_text,
                explanation=pq.question.explanation,
                points=pq.points,
                answer_lines=pq.answer_blank_lines or qtype.default_answer_lines,
                audio=_media_info(question.audio),
                audio_play_count=question.audio_play_count or 1,
                paper_item_id=pq.id,
                question_id=question.id,
            )
            if question.stem_image_id:
                stem_image_info = _media_info(question.stem_image)
                item.stem_image_path = stem_image_info["path"]
                item.stem_image_url = stem_image_info["url"]

            for opt in (content or {}).get("options", []) or []:
                image_info = _opt_image(opt.get("image_id"))
                item.options.append(
                    RenderOption(
                        key=opt.get("key", ""),
                        text=opt.get("text", ""),
                        image_path=image_info.get("path"),
                        image_url=image_info.get("url"),
                    )
                )

            # 材料（阅读/完形/情景对话）：同组小题只在首题前渲染一次
            passage = question.passage
            if passage is not None and passage.id not in seen_passage_ids:
                seen_passage_ids.add(passage.id)
                item.passage = {
                    "id": passage.id,
                    "kind": passage.kind,
                    "title": passage.title,
                    "body": passage.body,
                    "translation": passage.translation,
                    "image": _media_info(passage.image),
                    "audio": _media_info(passage.audio) or _media_info(question.audio),
                    "word_count": passage.word_count,
                }
            elif passage is None:
                seen_passage_ids.discard(-1)

            # 编号
            if section.number_style == "none":
                item.no = pq.display_no_override or ""
            elif pq.display_no_override:
                item.no = pq.display_no_override
            else:
                item.no = f"{index}."

            # 听力音频清单
            audio = item.audio or (item.passage or {}).get("audio") or render_section.audio
            if audio and audio.get("filename") and audio["filename"] not in audio_seen:
                audio_seen.add(audio["filename"])
                plan.media_manifest.append(
                    {
                        "no": f"{render_section.display_title} 第{index}题",
                        "filename": audio["filename"],
                        "duration": audio.get("duration"),
                        "play_count": item.audio_play_count,
                        "url": audio.get("url"),
                    }
                )

            render_section.items.append(item)
            if item.type_code in {"single_choice", "listening_choice", "reading_choice", "cloze"}:
                plan.answer_sheet.append(item)

        plan.sections.append(render_section)

    return plan


def _opt_image(image_id) -> dict[str, Any]:
    """把选项/配图的 MediaAsset id 转成 {path, url}，缺胳膊少腿时返回空字典。"""
    if not image_id:
        return {}
    from apps.bank.models import MediaAsset

    asset = MediaAsset.objects.filter(pk=image_id).first()
    if not asset:
        return {}
    info = _media_info(asset) or {}
    if not info.get("url") and asset.file:
        try:
            info["url"] = asset.file.url
        except Exception:  # noqa: BLE001
            info["url"] = ""
    return info
