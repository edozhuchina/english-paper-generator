"""题型渲染器：把 RenderItem 画到 python-docx 文档里。

每个渲染器对应 QuestionType.renderer_key，签名统一为 render_xxx(doc, item)。
题干里的空位用 `___`（两个以上下划线）或 `[n]` 标记，会被渲染成带下划线的空格。
"""

from __future__ import annotations

import re
from typing import Callable

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

from apps.exporter.docx_helpers import (
    add_answer_lines,
    add_scaled_picture,
    add_styled_paragraph,
    make_borderless_table,
    set_run_font,
)
from apps.exporter.plan import RenderItem, _opt_image

BLANK_RE = re.compile(r"_{2,}|\[\d+\]")

# 题干空位在 Word 里占据的字符宽度
BLANK_WIDTH = 14


def render_generic(doc, item: RenderItem):
    """兜底渲染器：题干 + 题内已有的结构。"""
    _render_stem(doc, item)
    for line in (item.content or {}).get("prompts", []) or []:
        add_styled_paragraph(doc, line, size=Pt(10.5), indent_cm=0.5, space_after=1)
    for line in (item.content or {}).get("statements", []) or []:
        text = line.get("text", "") if isinstance(line, dict) else str(line)
        add_styled_paragraph(doc, text, size=Pt(10.5), indent_cm=0.5, space_after=1)
    _render_answer_lines(doc, item)


# --------------------------------------------------------------------------- 选择题

def render_choice(doc, item: RenderItem):
    _render_stem(doc, item)
    _render_options(doc, item)


def _render_options(doc, item: RenderItem):
    options = item.options
    if not options:
        return
    layout = item.layout or "vertical"

    has_image = any(opt.image_path for opt in options)

    if layout == "horizontal":
        para = doc.add_paragraph()
        para.paragraph_format.left_indent = Cm(0.74)
        for index, opt in enumerate(options):
            prefix = f"{opt.key}. " if opt.key else ""
            run = para.add_run()
            set_run_font(run, size=Pt(10.5))
            run.text = "" if index == 0 else "    "
            if opt.image_path:
                _render_option_image(para, opt, inline=True)
                continue
            text_run = para.add_run(f"{prefix}{opt.text}" if opt.text else prefix)
            set_run_font(text_run, size=Pt(10.5))
            if index < len(options) - 1:
                sep = para.add_run("        ")
                set_run_font(sep, size=Pt(10.5))
        return

    if layout in {"grid2", "grid4"} or has_image:
        cols = 2 if layout != "grid2" else 2
        rows = (len(options) + cols - 1) // cols
        table = make_borderless_table(doc, rows=rows, cols=cols)
        for index, opt in enumerate(options):
            row, col = divmod(index, cols)
            cell = table.cell(row, col)
            para = cell.paragraphs[0]
            para.paragraph_format.space_after = Pt(2)
            if opt.key:
                key_run = para.add_run(f"{opt.key}. ")
                set_run_font(key_run, size=Pt(10.5))
            if opt.image_path:
                add_scaled_picture(para, opt.image_path, max_w=4.6, max_h=3.2)
            if opt.text:
                set_run_font(para.add_run(opt.text), size=Pt(10.5))
        return

    # vertical
    for opt in options:
        para = doc.add_paragraph()
        para.paragraph_format.left_indent = Cm(0.9)
        para.paragraph_format.first_line_indent = Cm(-0.9)
        para.paragraph_format.space_after = Pt(1)
        key_text = f"{opt.key}. " if opt.key else ""
        set_run_font(para.add_run(key_text), size=Pt(10.5))
        if opt.text:
            set_run_font(para.add_run(opt.text), size=Pt(10.5))
        if opt.image_path:
            add_scaled_picture(para, opt.image_path, max_w=4.6, max_h=3.2)


def _render_option_image(paragraph, opt, inline=False):
    if not opt.image_path:
        return
    add_scaled_picture(paragraph, opt.image_path, max_w=3.0, max_h=2.4)
    if opt.text:
        set_run_font(paragraph.add_run(f" {opt.text}"), size=Pt(10.5))


# --------------------------------------------------------------------------- 排序 / 判断

def render_order(doc, item: RenderItem):
    """听句排序：列出打乱的句子，句前留空括号供填写序号。"""
    _render_stem(doc, item)
    for index, entry in enumerate((item.content or {}).get("items", []) or [], start=1):
        text = entry.get("text", "") if isinstance(entry, dict) else str(entry)
        para = doc.add_paragraph()
        para.paragraph_format.left_indent = Cm(0.74)
        para.paragraph_format.space_after = Pt(1)
        set_run_font(para.add_run(f"（    ）"), size=Pt(10.5))
        set_run_font(para.add_run(text), size=Pt(10.5))


def render_judge(doc, item: RenderItem):
    """判断正误：每条陈述后跟 ( T / F )。"""
    _render_stem(doc, item)
    for entry in (item.content or {}).get("statements", []) or []:
        no = entry.get("no") if isinstance(entry, dict) else None
        text = entry.get("text", "") if isinstance(entry, dict) else str(entry)
        para = doc.add_paragraph()
        para.paragraph_format.left_indent = Cm(0.74)
        para.paragraph_format.space_after = Pt(1)
        prefix = f"{no}. " if no else ""
        set_run_font(para.add_run(prefix), size=Pt(10.5))
        set_run_font(para.add_run(text), size=Pt(10.5))
        set_run_font(para.add_run("  （ T / F ）"), size=Pt(9))


# --------------------------------------------------------------------------- 填空类

def render_blanks(doc, item: RenderItem):
    """选词填空 / 适当形式填空 / 英汉互译共用。"""
    content = item.content or {}

    word_bank = content.get("word_bank") or []
    if word_bank:
        para = doc.add_paragraph()
        para.paragraph_format.space_after = Pt(2)
        label = para.add_run("备选词：")
        set_run_font(label, size=Pt(10.5), bold=True)
        for index, word in enumerate(word_bank):
            run = para.add_run(word if index == 0 else f"    {word}")
            set_run_font(run, size=Pt(10.5))

    _render_stem_with_blanks(doc, item)

    items = content.get("items") or []
    if items and not item.stem:
        for index, entry in enumerate(items, start=1):
            if isinstance(entry, dict):
                text = entry.get("src", "") or entry.get("text", "")
            else:
                text = str(entry)
            para = doc.add_paragraph()
            para.paragraph_format.left_indent = Cm(0.74)
            para.paragraph_format.space_after = Pt(2)
            set_run_font(para.add_run(f"{index}. "), size=Pt(10.5))
            set_run_font(para.add_run(text), size=Pt(10.5))
            blank = para.add_run(" " * BLANK_WIDTH)
            blank.underline = True

    given = [b.get("given") for b in (content.get("blanks") or []) if isinstance(b, dict) and b.get("given")]
    if given and not content.get("hide_given"):
        para = doc.add_paragraph()
        para.paragraph_format.left_indent = Cm(0.74)
        para.paragraph_format.space_after = Pt(2)
        hint = para.add_run("（给出的提示词：" + "，".join(str(g) for g in given) + "）")
        set_run_font(hint, size=Pt(9), italic=True)


# --------------------------------------------------------------------------- 情景对话

def render_dialogue(doc, item: RenderItem):
    content = item.content or {}
    _render_stem(doc, item)

    for line in content.get("lines") or []:
        if not isinstance(line, dict):
            continue
        role = line.get("role", "")
        text = line.get("text", "") or ""
        para = doc.add_paragraph()
        para.paragraph_format.left_indent = Cm(0.74)
        para.paragraph_format.space_after = Pt(1)
        role_run = para.add_run(f"{role}: ")
        set_run_font(role_run, size=Pt(10.5), bold=True)
        _render_text_with_blanks(para, text)

    pool = content.get("pool") or []
    if pool:
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(3)
        para.paragraph_format.space_after = Pt(2)
        set_run_font(para.add_run("备选句子："), size=Pt(10.5), bold=True)
        for entry in pool:
            if not isinstance(entry, dict):
                continue
            key = entry.get("key", "")
            text = entry.get("text", "")
            sub = doc.add_paragraph()
            sub.paragraph_format.left_indent = Cm(0.74)
            sub.paragraph_format.space_after = Pt(0)
            set_run_font(sub.add_run(f"{key}. {text}"), size=Pt(10.5))


# --------------------------------------------------------------------------- 主观题

def render_unscramble(doc, item: RenderItem):
    """连词成句：把打乱的词列出来（含干扰词）。"""
    content = item.content or {}
    words = content.get("words") or []
    distractors = content.get("distractors") or []
    _render_stem(doc, item)

    para = doc.add_paragraph()
    para.paragraph_format.left_indent = Cm(0.74)
    para.paragraph_format.space_after = Pt(2)
    label = para.add_run("所给词语：")
    set_run_font(label, size=Pt(10.5), bold=True)
    set_run_font(para.add_run("    ".join(str(w) for w in words)), size=Pt(10.5))
    if distractors:
        dd = doc.add_paragraph()
        dd.paragraph_format.left_indent = Cm(0.74)
        dd.paragraph_format.space_after = Pt(2)
        set_run_font(dd.add_run("（干扰词：" + "，".join(str(d) for d in distractors) + "）"),
                     size=Pt(9), italic=True)

    line = doc.add_paragraph()
    line.paragraph_format.left_indent = Cm(0.74)
    line.paragraph_format.space_after = Pt(4)
    blank = line.add_run(" " * 60)
    blank.underline = True


def render_rewrite(doc, item: RenderItem):
    """改写句子：给原句 + 改写要求 + 答题线。"""
    content = item.content or {}
    _render_stem(doc, item)
    source = content.get("source")
    if source:
        para = doc.add_paragraph()
        para.paragraph_format.left_indent = Cm(0.74)
        para.paragraph_format.space_after = Pt(1)
        set_run_font(para.add_run("原句："), size=Pt(10.5), bold=True)
        set_run_font(para.add_run(str(source)), size=Pt(10.5))
    requirement = content.get("requirement")
    if requirement:
        para = doc.add_paragraph()
        para.paragraph_format.left_indent = Cm(0.74)
        para.paragraph_format.space_after = Pt(2)
        set_run_font(para.add_run("要求："), size=Pt(10.5), bold=True)
        set_run_font(para.add_run(str(requirement)), size=Pt(10.5))
    line = doc.add_paragraph()
    line.paragraph_format.left_indent = Cm(0.74)
    line.paragraph_format.space_after = Pt(4)
    blank = line.add_run(" " * 60)
    blank.underline = True


def render_writing(doc, item: RenderItem):
    """看图写话 / 书面表达：提示要点 + 配图 + 作答横线。"""
    content = item.content or {}
    _render_stem(doc, item)

    if item.stem_image_path:
        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_scaled_picture(para, item.stem_image_path, max_w=8.0, max_h=6.0)

    topic_image = item.content.get("image_id")
    if topic_image and not item.stem_image_path:
        path = _opt_image(topic_image).get("path")
        if path:
            para = doc.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_scaled_picture(para, path, max_w=8.0, max_h=6.0)

    prompts = content.get("prompts") or []
    if prompts:
        for line in prompts:
            para = doc.add_paragraph()
            para.paragraph_format.left_indent = Cm(0.74)
            para.paragraph_format.space_after = Pt(1)
            set_run_font(para.add_run(str(line)), size=Pt(10.5))

    topic = content.get("topic")
    if topic:
        para = doc.add_paragraph()
        para.paragraph_format.left_indent = Cm(0.74)
        para.paragraph_format.space_after = Pt(2)
        set_run_font(para.add_run(f"题目：{topic}"), size=Pt(11), bold=True)

    meta = []
    if content.get("min_words"):
        meta.append(f"不少于 {content['min_words']} 词")
    if content.get("min_sentences"):
        meta.append(f"不少于 {content['min_sentences']} 句话")
    if item.explanation:
        pass
    if meta:
        para = doc.add_paragraph()
        para.paragraph_format.left_indent = Cm(0.74)
        para.paragraph_format.space_after = Pt(3)
        set_run_font(para.add_run("（" + "，".join(meta) + "）"), size=Pt(9), italic=True)

    add_answer_lines(doc, max(item.answer_lines, 4) if item.answer_lines else 6)


# --------------------------------------------------------------------------- 辅助


def _render_stem(doc, item: RenderItem, *, first_indent=0.0):
    """题号 + 题干（含行内空位）。"""
    para = doc.add_paragraph()
    fmt = para.paragraph_format
    fmt.left_indent = Cm(0.74 + first_indent)
    fmt.first_line_indent = Cm(-0.74)
    fmt.space_before = Pt(3)
    fmt.space_after = Pt(2)

    if item.no:
        no_run = para.add_run(f"{item.no} ")
        set_run_font(no_run, size=Pt(10.5), bold=True)

    if item.stem:
        _render_text_with_blanks(para, item.stem)

    if item.stem_image_path and item.type_code not in {"picture_writing", "writing"}:
        add_scaled_picture(para, item.stem_image_path, max_w=4.0, max_h=3.0)
    return para


def _render_stem_with_blanks(doc, item: RenderItem):
    _render_stem(doc, item)


def _render_text_with_blanks(paragraph, text: str):
    """把 `___` / `[n]` 渲染成下划线空格。"""
    if not text:
        return
    parts = BLANK_RE.split(text)
    matches = BLANK_RE.findall(text)
    for index, chunk in enumerate(parts):
        if chunk:
            set_run_font(paragraph.add_run(chunk), size=Pt(10.5))
        if index < len(matches):
            blank_run = paragraph.add_run(" " * BLANK_WIDTH)
            blank_run.underline = True


def _render_answer_lines(doc, item: RenderItem):
    if item.answer_lines and item.answer_lines > 0:
        add_answer_lines(doc, item.answer_lines)
    elif not item.options:
        line = doc.add_paragraph()
        line.paragraph_format.left_indent = Cm(0.74)
        line.paragraph_format.space_after = Pt(4)
        blank = line.add_run(" " * 40)
        blank.underline = True


RENDERERS: dict[str, Callable] = {
    "choice": render_choice,
    "order": render_order,
    "judge": render_judge,
    "blanks": render_blanks,
    "dialogue": render_dialogue,
    "unscramble": render_unscramble,
    "rewrite": render_rewrite,
    "writing": render_writing,
    "generic": render_generic,
}


def get_renderer(key: str) -> Callable:
    return RENDERERS.get(key, render_generic)
