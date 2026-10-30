"""试卷、大题板块与试卷-题目关联。

题目一旦入卷，`PaperQuestion` 上会记录本卷的分值与顺序；题库里的题可以被任意多份卷引用，
不会因为出过一次就被占用。
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum

from apps.core.choices import (
    EXAM_TYPE_CHOICES,
    GRADE_CHOICES,
    NUMBER_STYLE_CHOICES,
    PAPER_STATUS_CHOICES,
    POINTS_MODE_CHOICES,
    SECTION_TYPE_CHOICES,
    TERM_CHOICES,
)
from apps.core.models import SoftDeleteModel, TimeStampedModel

CN_NUM = "一二三四五六七八九十"


def cn_number(n: int) -> str:
    """把 1,2,3… 变成中文数字，供大题编号使用。"""
    if n <= 10:
        return CN_NUM[n - 1]
    if n < 20:
        return "十" + CN_NUM[n - 11]
    tens, ones = divmod(n, 10)
    return CN_NUM[tens - 1] + "十" + (CN_NUM[ones - 1] if ones else "")


DEFAULT_HEADER_CONFIG = {
    "school_label": "学校：____________",
    "show_class_name": True,
    "show_score_table": True,
    "score_table": [
        {"caption": "题号", "rows": 1},
        {"caption": "得分", "rows": 1},
    ],
    "note": "",
    "motto": "",
}


class Paper(TimeStampedModel, SoftDeleteModel):
    """一份试卷。"""

    title = models.CharField("试卷标题", max_length=200)
    subtitle = models.CharField("副标题", max_length=200, blank=True)
    grade = models.PositiveSmallIntegerField("年级", choices=GRADE_CHOICES)
    term = models.CharField("学期", max_length=4, choices=TERM_CHOICES, blank=True)
    exam_type = models.CharField(
        "考试类型", max_length=16, choices=EXAM_TYPE_CHOICES, default="unit"
    )
    duration_min = models.PositiveIntegerField("考试时长(分钟)", default=60)

    target_score = models.DecimalField("目标总分", max_digits=6, decimal_places=2, default=100)
    computed_total_score = models.DecimalField(
        "实际总分", max_digits=6, decimal_places=2, default=0
    )
    status = models.CharField(
        "状态", max_length=16, choices=PAPER_STATUS_CHOICES, default="draft"
    )

    header_config = models.JSONField("卷头配置", default=dict, blank=True)
    listening_audio = models.ForeignKey(
        "bank.MediaAsset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="paper_audio",
        verbose_name="整卷听力音频",
    )
    answer_sheet_enabled = models.BooleanField("生成答题卡", default=False)
    answer_included = models.BooleanField("卷后附答案", default=True)

    version = models.PositiveIntegerField("版本", default=1)
    auto_seed = models.BigIntegerField("自动组卷随机种子", null=True, blank=True)
    composition_report = models.JSONField("组卷报告", default=list, blank=True)

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="papers",
        verbose_name="创建人",
    )
    last_exported_at = models.DateTimeField("最近导出时间", null=True, blank=True)

    class Meta:
        verbose_name = "试卷"
        verbose_name_plural = "试卷"
        ordering = ["-id"]

    def __str__(self) -> str:
        return self.title

    @property
    def header(self) -> dict:
        merged = dict(DEFAULT_HEADER_CONFIG)
        merged.update(self.header_config or {})
        return merged

    def question_count(self) -> int:
        return self.items.count()

    def recompute_total(self, save: bool = True) -> Decimal:
        total = self.items.aggregate(total=Sum("points"))["total"] or Decimal("0")
        self.computed_total_score = total
        if save:
            self.save(update_fields=["computed_total_score"])
        return total

    @property
    def score_gap(self) -> Decimal:
        return Decimal(self.target_score or 0) - Decimal(self.computed_total_score or 0)


class PaperSection(models.Model):
    """大题 / 板块，例如「一、听力部分」。"""

    paper = models.ForeignKey(
        Paper, on_delete=models.CASCADE, related_name="sections", verbose_name="所属试卷"
    )
    order = models.PositiveSmallIntegerField("板块序号")
    title = models.CharField("板块标题", max_length=64)
    directions = models.TextField("答题说明", blank=True)
    section_type = models.CharField(
        "板块类型", max_length=24, choices=SECTION_TYPE_CHOICES, default="custom"
    )
    points_mode = models.CharField(
        "赋分方式", max_length=16, choices=POINTS_MODE_CHOICES, default="uniform"
    )
    points_each = models.DecimalField("每题分值", max_digits=5, decimal_places=2, default=1)
    number_style = models.CharField(
        "编号样式", max_length=16, choices=NUMBER_STYLE_CHOICES, default="arabic"
    )
    listening_audio = models.ForeignKey(
        "bank.MediaAsset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="section_audio",
        verbose_name="板块听力音频",
    )

    class Meta:
        verbose_name = "大题板块"
        verbose_name_plural = "大题板块"
        ordering = ["order"]
        unique_together = [("paper", "order")]

    @property
    def display_title(self) -> str:
        """卷面上显示的大题编号，例如「三、阅读理解」。"""
        return f"{cn_number(self.order)}、{self.title}"

    def __str__(self) -> str:
        return f"{self.order}. {self.title}"

    def items_ordered(self):
        return self.items.all()

    def subtotal(self) -> Decimal:
        return self.items.aggregate(total=Sum("points"))["total"] or Decimal("0")


class PaperQuestion(models.Model):
    """试卷与题目的关联：本卷的顺序、分值、覆盖性定制与快照。"""

    paper = models.ForeignKey(
        Paper, on_delete=models.CASCADE, related_name="items", verbose_name="所属试卷"
    )
    section = models.ForeignKey(
        PaperSection,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="items",
        verbose_name="所属板块",
    )
    question = models.ForeignKey(
        "bank.Question",
        on_delete=models.PROTECT,
        related_name="paper_items",
        verbose_name="题目",
    )
    order_in_section = models.PositiveSmallIntegerField("板块内序号", default=0)

    points = models.DecimalField("本卷分值", max_digits=5, decimal_places=2, default=1)
    points_locked = models.BooleanField("分值已锁定", default=False)
    required = models.BooleanField("必答", default=True)
    answer_blank_lines = models.PositiveSmallIntegerField("答题空行", default=0)

    custom_stem = models.TextField("本卷题干微调", blank=True)
    display_no_override = models.CharField("题号覆盖", max_length=16, blank=True)
    note = models.TextField("备注", blank=True)

    snapshot_stem = models.TextField("快照·题干", blank=True)
    snapshot_content = models.JSONField("快照·结构", default=dict, blank=True)
    snapshot_answer = models.JSONField("快照·答案", default=dict, blank=True)

    class Meta:
        verbose_name = "试卷题目"
        verbose_name_plural = "试卷题目"
        ordering = ["order_in_section", "id"]
        unique_together = [("paper", "question")]
        indexes = [models.Index(fields=["section", "order_in_section"], name="pq_order_idx")]

    def __str__(self) -> str:
        return f"{self.paper_id}-{self.order_in_section}-{self.question_id}"

    def save(self, *args, **kwargs):
        creating = self._state.adding
        if creating and not self.points:
            self.points = self.question.suggested_score
        super().save(*args, **kwargs)
        if creating:
            self.question.usage_count = (self.question.usage_count or 0) + 1
            self.question.save(update_fields=["usage_count"])

    def delete(self, *args, **kwargs):
        question = self.question
        result = super().delete(*args, **kwargs)
        question.usage_count = max((question.usage_count or 1) - 1, 0)
        question.save(update_fields=["usage_count"])
        return result

    # ------------------------------------------------------------------ 取值

    def stem(self) -> str:
        """优先用快照，其次用本卷微调，最后用题库原文。"""
        if self.snapshot_stem:
            return self.snapshot_stem
        return self.custom_stem or self.question.stem

    def content(self) -> dict:
        if self.snapshot_content:
            return self.snapshot_content
        return self.question.content or {}

    def answer(self) -> dict:
        if self.snapshot_answer:
            return self.snapshot_answer
        return self.question.answer or {}

    def take_snapshot(self, source=None) -> None:
        q = source or self.question
        self.snapshot_stem = self.custom_stem or q.stem
        self.snapshot_content = q.content or {}
        self.snapshot_answer = q.answer or {}
        self.save(update_fields=["snapshot_stem", "snapshot_content", "snapshot_answer"])
