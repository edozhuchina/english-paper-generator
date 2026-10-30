"""全局枚举与选项常量。集中放置，避免各 app 重复定义。"""

from django.db import models

# ------------------------------------------------------------------ 学段

GRADE_CHOICES = [
    (3, "三年级"),
    (4, "四年级"),
    (5, "五年级"),
    (6, "六年级"),
]

TERM_CHOICES = [
    ("上", "上册"),
    ("下", "下册"),
    ("全", "全册"),
]

DIFFICULTY_CHOICES = [
    (1, "容易"),
    (2, "较易"),
    (3, "中等"),
    (4, "较难"),
    (5, "难"),
]

# ------------------------------------------------------------------ 题型

QUESTION_GROUP_CHOICES = [
    ("listening", "听力题"),
    ("vocab_grammar", "词汇语法题"),
    ("reading", "阅读与完形"),
    ("subjective", "主观题"),
    ("writing", "作文题"),
]

OPTIONS_LAYOUT_CHOICES = [
    ("vertical", "竖排（每行一个）"),
    ("horizontal", "横排（一行排完）"),
    ("grid2", "两列网格"),
    ("grid4", "四宫格（2×2）"),
]

# ------------------------------------------------------------------ 题目

SOURCE_TYPE_CHOICES = [
    ("sample", "内置样例"),
    ("excel", "Excel/CSV 导入"),
    ("docx", "Word 解析导入"),
    ("ai_ocr", "图片识别导入"),
    ("manual", "手动录入"),
]

REVIEW_STATUS_CHOICES = [
    ("draft", "草稿"),
    ("pending", "待审核"),
    ("approved", "已通过"),
    ("rejected", "已驳回"),
]

# ------------------------------------------------------------------ 材料

PASSAGE_KIND_CHOICES = [
    ("reading", "阅读短文"),
    ("cloze_text", "完形正文"),
    ("listening_script", "听力原文"),
    ("dialogue", "对话上下文"),
    ("picture_prompt", "看图提示"),
]

# ------------------------------------------------------------------ 媒体

MEDIA_KIND_CHOICES = [
    ("image", "图片"),
    ("audio", "音频"),
    ("attachment", "附件"),
]

# ------------------------------------------------------------------ 标签

TAG_CATEGORY_CHOICES = [
    ("grammar_point", "语法点"),
    ("topic", "话题"),
    ("skill", "技能"),
    ("exam_point", "考点"),
]

# ------------------------------------------------------------------ 试卷

PAPER_STATUS_CHOICES = [
    ("draft", "草稿"),
    ("finalized", "已定稿"),
    ("archived", "已归档"),
]

EXAM_TYPE_CHOICES = [
    ("unit", "单元测验"),
    ("midterm", "期中测试"),
    ("final", "期末测试"),
    ("mock", "模拟卷"),
    ("homework", "作业练习"),
]

SECTION_TYPE_CHOICES = [
    ("listening", "听力部分"),
    ("vocab_grammar", "词汇语法"),
    ("reading", "阅读理解"),
    ("writing", "写作部分"),
    ("custom", "自定义"),
]

NUMBER_STYLE_CHOICES = [
    ("arabic", "阿拉伯数字 1."),
    ("chinese", "中文数字 一、"),
    ("none", "不编号"),
]

POINTS_MODE_CHOICES = [
    ("uniform", "本板块统一分值"),
    ("per_question", "逐题单独设分"),
]

# ------------------------------------------------------------------ 导入

IMPORT_KIND_CHOICES = [
    ("excel", "Excel/CSV"),
    ("docx", "Word 文档"),
    ("ai_ocr", "图片识别"),
    ("sample", "内置样例"),
    ("manual", "手动录入"),
]

IMPORT_STATUS_CHOICES = [
    ("pending", "待处理"),
    ("validating", "校验中"),
    ("awaiting_confirm", "待确认"),
    ("importing", "入库中"),
    ("done", "已完成"),
    ("failed", "失败"),
    ("cancelled", "已取消"),
]

DRAFT_STATUS_CHOICES = [
    ("pending", "待校对"),
    ("edited", "已编辑"),
    ("confirmed", "已确认"),
    ("discarded", "已丢弃"),
]


class GradeField(models.PositiveSmallIntegerField):
    """年级字段，复用统一选项。"""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("choices", GRADE_CHOICES)
        kwargs.setdefault("verbose_name", "年级")
        super().__init__(*args, **kwargs)


class DifficultyField(models.PositiveSmallIntegerField):
    """难度字段，1~5。"""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("choices", DIFFICULTY_CHOICES)
        kwargs.setdefault("verbose_name", "难度")
        kwargs.setdefault("default", 3)
        super().__init__(*args, **kwargs)
