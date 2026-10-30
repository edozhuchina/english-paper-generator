"""题型字典与标签。新增题型只需要往 QuestionType 插一行，不需要改模型。"""

from __future__ import annotations

from django.db import models

from django.utils import timezone

from apps.core.choices import (
    OPTIONS_LAYOUT_CHOICES,
    QUESTION_GROUP_CHOICES,
    TAG_CATEGORY_CHOICES,
)


class QuestionType(models.Model):
    """题型字典。

    code 是所有分派逻辑的唯一依据；renderer_key 决定 Word/网页如何渲染；
    content_schema / answer_schema 供导入器做 Python 层校验。
    """

    code = models.SlugField("题型代码", max_length=48, unique=True)
    name = models.CharField("题型名称", max_length=32)
    group = models.CharField(
        "所属板块", max_length=24, choices=QUESTION_GROUP_CHOICES, default="vocab_grammar"
    )

    has_options = models.BooleanField("含选项", default=False)
    has_blanks = models.BooleanField("含填空位", default=False)
    has_passage = models.BooleanField("需要材料", default=False)
    has_audio = models.BooleanField("含音频", default=False)
    has_image = models.BooleanField("含图片", default=False)
    can_have_subquestions = models.BooleanField("可带小题", default=False)
    is_objective = models.BooleanField("客观题（机器可判）", default=True)

    content_schema = models.JSONField("题干结构校验规则", default=dict, blank=True)
    answer_schema = models.JSONField("答案结构校验规则", default=dict, blank=True)
    renderer_key = models.CharField("渲染器标识", max_length=64, default="generic")

    default_score = models.DecimalField("默认分值", max_digits=5, decimal_places=2, default=1)
    default_option_layout = models.CharField(
        "默认选项排版",
        max_length=16,
        choices=OPTIONS_LAYOUT_CHOICES,
        default="vertical",
    )
    default_answer_lines = models.PositiveSmallIntegerField("默认答题行数", default=0)

    sort_order = models.PositiveSmallIntegerField("排序号", default=0)
    is_active = models.BooleanField("启用", default=True)
    remark = models.CharField("备注", max_length=200, blank=True)

    class Meta:
        verbose_name = "题型"
        verbose_name_plural = "题型字典"
        ordering = ["group", "sort_order", "id"]

    def __str__(self) -> str:
        return f"{self.name}（{self.code}）"


class Tag(models.Model):
    """知识点 / 话题 / 技能 / 考点标签，支持两级。"""

    name = models.CharField("标签名", max_length=64)
    category = models.CharField(
        "分类", max_length=24, choices=TAG_CATEGORY_CHOICES, default="grammar_point"
    )
    code = models.SlugField("代码", max_length=64, blank=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
        verbose_name="上级标签",
    )
    sort_order = models.PositiveSmallIntegerField("排序号", default=0)
    is_system = models.BooleanField("系统内置", default=False)
    # 用 default 而非 auto_now_add：loaddata 走 raw 保存，auto_now_add 不会触发，会导致 NOT NULL 失败
    created_at = models.DateTimeField("创建时间", default=timezone.now)

    class Meta:
        verbose_name = "标签"
        verbose_name_plural = "标签字典"
        ordering = ["category", "sort_order", "id"]
        unique_together = [("name", "category")]

    def __str__(self) -> str:
        return self.name
