"""导入批次与待校对草稿。

设计要点：Excel/CSV、Word 解析、AI 图片识别、手动录入四种来源，**共用一张草稿表
ImportDraft + 一个校对页 + 一套 commit 逻辑**，只是 payload 的来源不同。
这样只需维护一个 Web 界面，行为也能保证一致。
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.choices import (
    DRAFT_STATUS_CHOICES,
    DIFFICULTY_CHOICES,
    GRADE_CHOICES,
    IMPORT_KIND_CHOICES,
    IMPORT_STATUS_CHOICES,
)


class ImportJob(models.Model):
    """一次导入批次，负责记录来源、进度与校验报告。"""

    kind = models.CharField("来源类型", max_length=16, choices=IMPORT_KIND_CHOICES, default="excel")
    source_file = models.ForeignKey(
        "bank.MediaAsset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="import_jobs",
        verbose_name="源文件",
    )
    original_filename = models.CharField("原始文件名", max_length=255, blank=True)

    target_grade = models.PositiveSmallIntegerField(
        "默认年级", choices=GRADE_CHOICES, null=True, blank=True
    )
    default_difficulty = models.PositiveSmallIntegerField(
        "默认难度", choices=DIFFICULTY_CHOICES, null=True, blank=True
    )
    default_tags = models.ManyToManyField(
        "catalog.Tag", blank=True, verbose_name="默认标签"
    )

    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="import_jobs",
        verbose_name="操作人",
    )
    status = models.CharField(
        "状态", max_length=20, choices=IMPORT_STATUS_CHOICES, default="pending"
    )

    total_rows = models.PositiveIntegerField("总行数", default=0)
    valid_rows = models.PositiveIntegerField("有效行数", default=0)
    error_rows = models.PositiveIntegerField("错误行数", default=0)
    imported_rows = models.PositiveIntegerField("已入库", default=0)
    skipped_duplicate = models.PositiveIntegerField("重复跳过", default=0)

    report = models.JSONField("校验明细", default=list, blank=True)
    report_file = models.FileField("报告文件", upload_to="imports/reports/", blank=True)

    started_at = models.DateTimeField("开始时间", null=True, blank=True)
    finished_at = models.DateTimeField("结束时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    note = models.TextField("备注", blank=True)

    class Meta:
        verbose_name = "导入批次"
        verbose_name_plural = "导入批次"
        ordering = ["-id"]

    def __str__(self) -> str:
        return f"#{self.pk} {self.get_kind_display()} {self.original_filename}".strip()

    @property
    def error_items(self) -> list:
        return [r for r in (self.report or []) if r.get("level") == "error"]

    @property
    def warn_items(self) -> list:
        return [r for r in (self.report or []) if r.get("level") == "warn"]


class ImportDraft(models.Model):
    """单条待入库草稿。payload 结构由 QuestionType.code 决定。"""

    job = models.ForeignKey(
        ImportJob, on_delete=models.CASCADE, related_name="drafts", verbose_name="所属批次"
    )
    row_index = models.PositiveIntegerField("行号", default=0)
    sheet_name = models.CharField("工作表名", max_length=64, blank=True)

    source_image = models.ForeignKey(
        "bank.MediaAsset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="drafts_as_image",
        verbose_name="原始图片",
    )
    raw_text = models.TextField("原文", blank=True)

    detected_type = models.ForeignKey(
        "catalog.QuestionType",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="drafts",
        verbose_name="识别题型",
    )
    ai_confidence = models.DecimalField(
        "识别置信度", max_digits=4, decimal_places=3, null=True, blank=True
    )
    payload = models.JSONField("结构化内容", default=dict, blank=True)
    errors = models.JSONField("错误明细", default=list, blank=True)

    status = models.CharField(
        "状态", max_length=16, choices=DRAFT_STATUS_CHOICES, default="pending"
    )
    resolved_question = models.ForeignKey(
        "bank.Question",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="from_drafts",
        verbose_name="入库题目",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_drafts",
        verbose_name="校对者",
    )
    reviewed_at = models.DateTimeField("校对时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "待校对草稿"
        verbose_name_plural = "待校对草稿"
        ordering = ["row_index", "id"]

    def __str__(self) -> str:
        return f"草稿#{self.pk}（批次{self.job_id} 第{self.row_index}行）"

    @property
    def has_error(self) -> bool:
        return any(e.get("level") == "error" for e in (self.errors or []))

    @property
    def low_confidence(self) -> bool:
        return self.ai_confidence is not None and self.ai_confidence < 0.7
