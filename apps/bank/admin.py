from django.contrib import admin
from django.utils.html import format_html

from apps.bank.models import MediaAsset, Passage, Question


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "kind", "size_display", "checksum_short", "created_at")
    list_filter = ("kind",)
    search_fields = ("original_filename", "file")
    readonly_fields = ("size_bytes", "checksum", "width", "height")

    @admin.display(description="体积")
    def size_display(self, obj):
        if obj.size_bytes >= 1024 * 1024:
            return f"{obj.size_bytes / 1024 / 1024:.1f} MB"
        return f"{obj.size_bytes / 1024:.0f} KB"

    @admin.display(description="指纹")
    def checksum_short(self, obj):
        return (obj.checksum or "")[:12]


@admin.register(Passage)
class PassageAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "grade", "word_count", "question_count")
    list_filter = ("kind", "grade", "term")
    search_fields = ("title", "body")
    filter_horizontal = ("tags",)

    @admin.display(description="小题数")
    def question_count(self, obj):
        return obj.questions.count()


class DifficultyFilter(admin.SimpleListFilter):
    title = "难度"
    parameter_name = "difficulty"

    def lookups(self, request, model_admin):
        return [(1, "容易"), (3, "中等"), (5, "难")]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(difficulty=self.value())
        return queryset


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "question_type",
        "grade",
        "difficulty",
        "stem_short",
        "answer_preview",
        "review_status",
        "source_type",
        "usage_count",
        "is_active",
    )
    list_filter = (
        "question_type",
        "grade",
        "review_status",
        "source_type",
        "is_active",
        DifficultyFilter,
    )
    search_fields = ("stem", "answer_text", "code", "explanation")
    filter_horizontal = ("tags",)
    raw_id_fields = ("passage", "stem_image", "audio", "import_job")
    readonly_fields = ("duplicate_key", "answer_text", "usage_count", "last_used_at")
    list_per_page = 30
    fieldsets = (
        (
            "基本信息",
            {"fields": ("question_type", "grade", "term", "difficulty", "code", "tags")},
        ),
        ("题干与素材", {"fields": ("stem", "stem_image", "passage", "sequence", "content")}),
        ("音频（听力题）", {"fields": ("audio", "audio_play_count"), "classes": ("collapse",)}),
        ("答案与解析", {"fields": ("answer", "answer_text", "explanation")}),
        (
            "计分与归档",
            {
                "fields": (
                    "suggested_score",
                    "options_layout",
                    "expected_word_count",
                    "review_status",
                    "is_active",
                    "source_type",
                    "import_job",
                )
            },
        ),
        (
            "系统信息",
            {"fields": ("duplicate_key", "duplicate_of", "usage_count", "last_used_at"),
             "classes": ("collapse",)},
        ),
    )

    @admin.display(description="题干")
    def stem_short(self, obj):
        text = obj.stem or (obj.passage.body[:40] if obj.passage_id else "")
        return text[:40] + ("…" if len(text) > 40 else "")

    @admin.display(description="答案")
    def answer_preview(self, obj):
        return format_html("<code>{}</code>", (obj.answer_text or "")[:60])
