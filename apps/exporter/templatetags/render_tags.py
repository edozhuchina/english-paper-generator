from django import template
from django.utils.safestring import mark_safe

from apps.exporter.plan import RenderItem

register = template.Library()


@register.filter
def blanks_to_lines(text):
    """把题干里的 ___ / [n] 渲染成下划线空格，换行用 || 表示。"""
    if not text:
        return ""
    import html
    import re

    escaped = html.escape(str(text))
    escaped = re.sub(r"_{2,}|\[\d+\]", '<span class="blank-space"></span>', escaped)
    escaped = escaped.replace("||", "<br>")
    return mark_safe(escaped)


@register.filter
def times(count):
    """模板里做 n 次循环：`{% for i in n|times %}`"""
    try:
        return range(int(count))
    except (TypeError, ValueError):
        return range(0)


@register.simple_tag
def option_layout_class(layout: str) -> str:
    return {
        "vertical": "opts-vertical",
        "horizontal": "opts-horizontal",
        "grid2": "opts-grid2",
        "grid4": "opts-grid4",
    }.get(layout, "opts-vertical")


@register.simple_tag
def answer_display(item: RenderItem) -> str:
    """答案页里把统一的 answer JSON 渲染成可读文字。"""
    from apps.exporter.writer_docx import _answer_display

    return _answer_display(item)
