from django.contrib import admin

from apps.catalog.models import QuestionType, Tag


@admin.register(QuestionType)
class QuestionTypeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "group",
        "default_score",
        "default_option_layout",
        "renderer_key",
        "sort_order",
        "is_active",
    )
    list_filter = ("group", "is_active", "is_objective")
    search_fields = ("code", "name")
    list_editable = ("sort_order", "is_active")
    ordering = ("group", "sort_order")
    fieldsets = (
        ("基本信息", {"fields": ("code", "name", "group", "sort_order", "is_active", "remark")}),
        (
            "结构特征",
            {
                "fields": (
                    "has_options",
                    "has_blanks",
                    "has_passage",
                    "has_audio",
                    "has_image",
                    "can_have_subquestions",
                    "is_objective",
                )
            },
        ),
        ("渲染与默认分值", {"fields": ("renderer_key", "default_score", "default_option_layout", "default_answer_lines")}),
        ("校验规则", {"fields": ("content_schema", "answer_schema"), "classes": ("collapse",)}),
    )


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "parent", "sort_order", "is_system")
    list_filter = ("category", "is_system")
    search_fields = ("name", "code")
    list_editable = ("sort_order",)
