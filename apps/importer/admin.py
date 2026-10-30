from django.contrib import admin

from apps.importer.models import ImportDraft, ImportJob


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "kind",
        "original_filename",
        "status",
        "total_rows",
        "valid_rows",
        "error_rows",
        "imported_rows",
        "skipped_duplicate",
        "created_at",
    )
    list_filter = ("kind", "status")
    search_fields = ("original_filename", "note")
    readonly_fields = ("created_at", "started_at", "finished_at")


@admin.register(ImportDraft)
class ImportDraftAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "job",
        "row_index",
        "detected_type",
        "status",
        "ai_confidence",
        "resolved_question",
    )
    list_filter = ("status", "detected_type")
    search_fields = ("raw_text",)
    raw_id_fields = ("job", "source_image", "resolved_question")
