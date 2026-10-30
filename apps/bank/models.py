"""题库核心：媒体资产、材料、题目。

设计要点
--------
* **一行 = 一道可判分的题**。阅读/完形/听力短文的多个小题是多条 Question 行，
  通过 `passage` 外键 + `sequence` 组织，可单独检索、单独赋分、单独渲染。
* 公共检索字段全部落在列上（题型/年级/难度/审核态…），保证规则组卷能用索引 SQL。
* 题型特有的结构（选项、填空位、评分要点）放在 `content` / `answer` 两个 JSON 字段，
  由 QuestionType.code 决定解释方式 —— 新增题型不需要迁移。
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.choices import (
    DIFFICULTY_CHOICES,
    GRADE_CHOICES,
    MEDIA_KIND_CHOICES,
    OPTIONS_LAYOUT_CHOICES,
    PASSAGE_KIND_CHOICES,
    REVIEW_STATUS_CHOICES,
    SOURCE_TYPE_CHOICES,
    TERM_CHOICES,
)
from apps.core.models import SoftDeleteModel, TimeStampedModel

_PUNCT_RE = re.compile(
    r"[\s　，。！？、；：…·—\-_()（）\[\]【】<>《》\"'“”‘’`,.!?;:/\\|]+"
)


def normalize_text(text) -> str:
    """文本归一化：全角转半角、去标点空白、转小写。用于去重指纹计算。"""
    if text is None:
        return ""
    value = unicodedata.normalize("NFKC", str(text))
    value = _PUNCT_RE.sub("", value)
    return value.lower()


class AuditableModel(TimeStampedModel, SoftDeleteModel):
    """带创建人 + 时间戳 + 软删除的组合基类。"""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_created_by",
        verbose_name="创建人",
    )

    class Meta:
        abstract = True


class MediaAsset(AuditableModel):
    """图片 / 音频 / 附件统一资产表。"""

    file = models.FileField("文件", upload_to="assets/%Y/%m/")
    kind = models.CharField("类型", max_length=16, choices=MEDIA_KIND_CHOICES, default="image")
    mime = models.CharField("MIME", max_length=64, blank=True)
    size_bytes = models.BigIntegerField("字节数", default=0)
    width = models.PositiveIntegerField("宽(px)", null=True, blank=True)
    height = models.PositiveIntegerField("高(px)", null=True, blank=True)
    duration_sec = models.DecimalField(
        "时长(秒)", max_digits=8, decimal_places=2, null=True, blank=True
    )
    original_filename = models.CharField("原始文件名", max_length=255, blank=True)
    checksum = models.CharField("文件指纹", max_length=64, blank=True, db_index=True)
    alt_text = models.CharField("替代文字", max_length=200, blank=True)

    class Meta:
        verbose_name = "媒体资产"
        verbose_name_plural = "媒体资产"
        ordering = ["-id"]

    def __str__(self) -> str:
        return self.original_filename or self.file.name

    @property
    def url(self) -> str:
        return self.file.url if self.file else ""

    def compute_checksum(self, save: bool = True) -> str:
        """读取文件内容算 sha256，同时回填体积等元信息。"""
        if not self.file:
            return ""
        digest = hashlib.sha256()
        total = 0
        try:
            self.file.open("rb")
            for chunk in self.file.chunks(chunk_size=65536):
                digest.update(chunk)
                total += len(chunk)
        finally:
            try:
                self.file.close()
            except Exception:  # noqa: BLE001 - 读失败时不阻断
                pass
        self.checksum = digest.hexdigest()
        self.size_bytes = total
        if save:
            self.save(update_fields=["checksum", "size_bytes"])
        return self.checksum


class Passage(AuditableModel):
    """材料：阅读短文 / 完形正文 / 听力原文 / 对话上下文 / 看图提示。"""

    kind = models.CharField(
        "材料类型", max_length=24, choices=PASSAGE_KIND_CHOICES, default="reading"
    )
    title = models.CharField("标题", max_length=128, blank=True)
    grade = models.PositiveSmallIntegerField("适用年级", choices=GRADE_CHOICES, null=True, blank=True)
    term = models.CharField("适用学期", max_length=4, choices=TERM_CHOICES, blank=True)
    body = models.TextField("正文", blank=True)
    body_rich = models.JSONField("正文富结构", default=dict, blank=True)
    translation = models.TextField("参考译文", blank=True)
    audio = models.ForeignKey(
        MediaAsset,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="passage_audio",
        verbose_name="音频",
    )
    image = models.ForeignKey(
        MediaAsset,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="passage_image",
        verbose_name="配图",
    )
    source = models.CharField("出处", max_length=200, blank=True)
    word_count = models.PositiveIntegerField("词数", default=0)
    tags = models.ManyToManyField("catalog.Tag", blank=True, verbose_name="标签")

    class Meta:
        verbose_name = "材料"
        verbose_name_plural = "材料库"
        ordering = ["-id"]

    def __str__(self) -> str:
        label = self.title or (self.body[:24] + "…" if len(self.body) > 24 else self.body)
        return label or f"材料#{self.pk}"

    def save(self, *args, **kwargs):
        if self.body:
            self.word_count = len(re.findall(r"[A-Za-z']+", self.body))
        super().save(*args, **kwargs)


class QuestionManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

    def approved(self):
        """可被自动组卷抽取的题池。"""
        return self.get_queryset().filter(is_active=True, review_status="approved")


class Question(AuditableModel):
    """题目主表。一行 = 一道可独立计分的题。"""

    uuid = models.UUIDField("UUID", null=True, blank=True, editable=False)
    code = models.CharField("人工题号", max_length=64, blank=True, db_index=True)
    question_type = models.ForeignKey(
        "catalog.QuestionType",
        on_delete=models.PROTECT,
        related_name="questions",
        verbose_name="题型",
    )
    grade = models.PositiveSmallIntegerField("年级", choices=GRADE_CHOICES, db_index=True)
    term = models.CharField("学期", max_length=4, choices=TERM_CHOICES, blank=True)
    difficulty = models.PositiveSmallIntegerField(
        "难度", choices=DIFFICULTY_CHOICES, default=3, db_index=True
    )

    stem = models.TextField("题干", blank=True)
    stem_image = models.ForeignKey(
        MediaAsset,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="question_stem_image",
        verbose_name="题干配图",
    )
    audio = models.ForeignKey(
        MediaAsset,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="question_audio",
        verbose_name="音频",
    )
    audio_play_count = models.PositiveSmallIntegerField("播放次数", default=1)

    passage = models.ForeignKey(
        Passage,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="questions",
        verbose_name="所属材料",
    )
    sequence = models.PositiveSmallIntegerField("材料内序号", default=0)

    content = models.JSONField("题干结构", default=dict, blank=True)
    answer = models.JSONField("标准答案", default=dict, blank=True)
    answer_text = models.TextField("答案纯文本", blank=True, help_text="冗余存储，供检索与去重")
    explanation = models.TextField("解析", blank=True)
    options_layout = models.CharField(
        "选项排版",
        max_length=16,
        choices=OPTIONS_LAYOUT_CHOICES,
        default="vertical",
    )
    suggested_score = models.DecimalField("建议分值", max_digits=5, decimal_places=2, default=1)
    expected_word_count = models.PositiveSmallIntegerField("建议词数", null=True, blank=True)

    tags = models.ManyToManyField("catalog.Tag", blank=True, verbose_name="标签")

    review_status = models.CharField(
        "审核状态",
        max_length=16,
        choices=REVIEW_STATUS_CHOICES,
        default="approved",
        db_index=True,
    )
    source_type = models.CharField(
        "来源方式", max_length=16, choices=SOURCE_TYPE_CHOICES, default="manual"
    )
    import_job = models.ForeignKey(
        "importer.ImportJob",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="questions",
        verbose_name="所属导入批次",
    )

    usage_count = models.PositiveIntegerField("被组卷次数", default=0)
    last_used_at = models.DateTimeField("最近使用时间", null=True, blank=True)

    duplicate_key = models.CharField(
        "去重指纹", max_length=64, null=True, blank=True, unique=True, db_index=True
    )
    duplicate_of = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="duplicates",
        verbose_name="重复于",
    )
    is_active = models.BooleanField("启用（参与组卷）", default=True)

    objects = QuestionManager()

    class Meta:
        verbose_name = "题目"
        verbose_name_plural = "题库"
        ordering = ["-id"]
        indexes = [
            models.Index(
                fields=["is_deleted", "review_status", "question_type", "grade", "difficulty"],
                name="q_pick_idx",
            ),
            models.Index(fields=["is_deleted", "duplicate_key"], name="q_dup_idx"),
            models.Index(fields=["passage", "sequence"], name="q_passage_idx"),
        ]

    def __str__(self) -> str:
        prefix = f"[{self.question_type.code}]" if self.question_type_id else ""
        text = self.stem or (self.passage.title if self.passage_id else "")
        if len(text) > 40:
            text = text[:40] + "…"
        return f"{prefix}{text or f'题目#{self.pk}'}"

    # ------------------------------------------------------------------ 存储钩子

    def flat_answer(self) -> str:
        """把 answer JSON 摊平成可读纯文本，用于列表展示、检索与去重。"""
        return flatten_answer_payload(self.answer)

    def build_duplicate_key(self) -> str:
        type_code = self.question_type.code if self.question_type_id else ""
        raw = "\x1f".join(
            [
                type_code,
                normalize_text(self.stem),
                normalize_text(self.flat_answer()),
                json.dumps(self.content or {}, sort_keys=True, ensure_ascii=False),
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def find_duplicate(self):
        """返回与本题内容重复的第一道题（不含自身）。"""
        key = self.build_duplicate_key()
        qs = Question.objects.filter(duplicate_key=key)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        return qs.first()

    def save(self, *args, **kwargs):
        if not self.uuid:
            import uuid as _uuid

            self.uuid = _uuid.uuid4()
        self.answer_text = self.flat_answer()
        self.duplicate_key = self.build_duplicate_key()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------ 读取辅助

    @property
    def options(self) -> list:
        return (self.content or {}).get("options", []) or []

    @property
    def option_layout(self) -> str:
        layout = (self.content or {}).get("layout", {}) or {}
        return self.options_layout or layout.get("options") or "vertical"

    @property
    def points(self) -> Decimal:
        return self.suggested_score or Decimal("0")


def flatten_answer_payload(answer: dict) -> str:
    """把统一结构的答案 JSON 转成一行可读文本。"""
    if not isinstance(answer, dict):
        return ""
    kind = answer.get("type", "")
    if kind == "single_choice":
        return "、".join(str(v) for v in answer.get("value", []) if v)
    if kind == "tf":
        mapper = {True: "T", False: "F"}
        return "、".join(mapper.get(bool(v), str(v)) for v in answer.get("value", []))
    if kind == "order":
        return "、".join(str(v) for v in answer.get("value", []))
    if kind == "blanks":
        parts = []
        for blank in answer.get("value", []):
            values = blank.get("value", []) if isinstance(blank, dict) else [blank]
            values = [v for v in values if v]
            if values:
                parts.append(" / ".join(str(v) for v in values))
        return " | ".join(parts)
    if kind == "rubric":
        sample = answer.get("sample", []) or []
        rubric = answer.get("rubric", []) or []
        bits = [str(s) for s in sample if s]
        bits += [
            f"{r.get('point', '')}{r.get('score', '')}分"
            for r in rubric
            if isinstance(r, dict)
        ]
        return "；".join(bits)
    return json.dumps(answer, ensure_ascii=False)
