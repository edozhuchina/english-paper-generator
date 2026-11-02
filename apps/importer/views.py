"""题库导入：Excel/CSV 批量导入 + 模板下载。

流程统一两级：**预校验（dry-run）→ 页面确认 → 真正入库**，
避免一行脏数据把整张表污染。
"""

from __future__ import annotations

import io
from datetime import datetime

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views import View

from apps.catalog.models import QuestionType
from apps.importer.models import ImportDraft, ImportJob
from apps.importer.services.excel import (
    build_import_template,
    parse_rows,
    read_upload,
)
from apps.importer.services.commit import commit_drafts


class ImportHomeView(View):
    template_name = "importer/import_home.html"

    def get(self, request):
        recent_jobs = ImportJob.objects.order_by("-id")[:8]
        return render(
            request,
            self.template_name,
            {
                "types": QuestionType.objects.filter(is_active=True).order_by("group", "sort_order"),
                "recent_jobs": recent_jobs,
            },
        )


class TemplateDownloadView(View):
    """下载带下拉校验的 Excel 模板。"""

    def get(self, request):
        workbook = build_import_template()
        stream = io.BytesIO()
        workbook.save(stream)
        stream.seek(0)
        stamp = datetime.now().strftime("%Y%m%d")
        response = HttpResponse(
            stream.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="import_template_{stamp}.xlsx"'
        return response


class UploadView(View):
    """上传 Excel/CSV，做一次 dry-run 校验并生成草稿。"""

    template_name = "importer/import_review.html"

    def post(self, request):
        uploaded = request.FILES.get("file")
        if not uploaded:
            messages.error(request, "请先选择要上传的文件")
            return redirect("import:home")

        if uploaded.size > 20 * 1024 * 1024:
            messages.error(request, "文件过大，请控制在 20MB 以内")
            return redirect("import:home")

        target_grade = request.POST.get("target_grade") or None
        default_difficulty = request.POST.get("default_difficulty") or None

        job = ImportJob.objects.create(
            kind="excel",
            original_filename=uploaded.name,
            status="validating",
            operator=request.user if request.user.is_authenticated else None,
        )
        if target_grade:
            job.target_grade = int(target_grade)
        if default_difficulty:
            job.default_difficulty = int(default_difficulty)

        rows = read_upload(uploaded)
        drafts, summary = parse_rows(rows, job.target_grade, job.default_difficulty)

        job.total_rows = summary["total"]
        job.valid_rows = summary["valid"]
        job.error_rows = summary["error"]
        job.report = summary["report"]
        job.status = "awaiting_confirm"
        job.save()

        with transaction.atomic():
            for draft in drafts:
                draft.job = job
            ImportDraft.objects.bulk_create(drafts)

        return render(
            request,
            self.template_name,
            {
                "job": job,
                "report": summary["report"],
                "valid_count": summary["valid"],
                "error_count": summary["error"],
            },
        )


class CommitView(View):
    """确认无误后正式入库。"""

    def post(self, request, job_id):
        job, error = _load_job(request, job_id)
        if job is None:
            messages.error(request, error)
            return redirect("import:home")

        skip_errors = request.POST.get("skip_errors") == "1"
        result = commit_drafts(job, skip_errors=skip_errors)

        if result["imported"]:
            messages.success(request, f"已入库 {result['imported']} 道题")
        if result["duplicate"]:
            messages.warning(request, f"跳过重复题目 {result['duplicate']} 道")
        if result["failed"]:
            messages.error(request, f"{result['failed']} 行未能入库，请查看报告")

        return redirect("import:home")


class CancelView(View):
    def post(self, request, job_id):
        job, error = _load_job(request, job_id)
        if job is None:
            messages.error(request, error)
            return redirect("import:home")
        job.status = "cancelled"
        job.save(update_fields=["status"])
        ImportDraft.objects.filter(job=job, status="pending").update(status="discarded")
        messages.info(request, "已取消该批次")
        return redirect("import:home")


def _load_job(request, job_id: int):
    """取批次并校验归属：只有创建人本人或管理员能动，否则就是越权。"""
    job = ImportJob.objects.filter(pk=job_id).first()
    if job is None:
        return None, "导入批次不存在"
    if job.operator_id and job.operator_id != request.user.pk and not request.user.is_staff:
        return None, "无权操作他人的导入批次"
    return job, ""
