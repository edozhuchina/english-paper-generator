from django import template

register = template.Library()


@register.filter
def dict_get(mapping, key):
    """模板里取字典值：{{ mydict|dict_get:key }}"""
    if not isinstance(mapping, dict):
        return ""
    return mapping.get(key, "")
