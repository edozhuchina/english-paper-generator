from django.contrib import admin

from apps.paper.models import Paper, PaperQuestion, PaperSection


class PaperQuestionInline(admin.TabularInline):
    model = PaperQuestion
    extra = 0
    fields = ("order_in_section", "question", "points", "points_locked", "answer_blank_lines")
    raw_id_fields = ("question",)
    ordering = ("order_in_section",)


class PaperSectionInline(admin.TabularInline):
    model = PaperSection
    extra = 0
    fields = ("order", "title", "section_type", "points_mode", "points_each", "directions")


@admin.register(Paper)
class PaperAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "grade",
        "term",
        "exam_type",
        "computed_total_score",
        "target_score",
        "status",
        "created_at",
    )
    list_filter = ("grade", "term", "exam_type", "status")
    search_fields = ("title", "subtitle")
    inlines = (PaperSectionInline,)
    readonly_fields = ("computed_total_score", "created_at", "updated_at", "last_exported_at")


@admin.register(PaperSection)
class PaperSectionAdmin(admin.ModelAdmin):
    list_display = ("paper", "order", "title", "section_type", "points_mode", "points_each")
    list_filter = ("section_type",)
    inlines = (PaperQuestionInline,)


@admin.register(PaperQuestion)
class PaperQuestionAdmin(admin.ModelAdmin):
    list_display = ("paper", "section", "order_in_section", "question", "points", "points_locked")
    list_filter = ("paper",)
    raw_id_fields = ("paper", "section", "question")
