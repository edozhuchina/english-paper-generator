"""草稿入库：把 ImportDraft.payload 落成真正 Question / Passage / Tag。

四种录入来源（Excel、CSV、Word、AI 识别）共用这一套 commit 逻辑，
保证去重、标签挂载、材料关联的行为完全一致。
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from apps.bank.models import Passage, Question
from apps.catalog.models import QuestionType, Tag
from apps.importer.models import ImportDraft, ImportJob


def commit_drafts(job: ImportJob, skip_errors: bool = True) -> dict:
    """返回 {'imported', 'duplicate', 'failed'}。"""
    result = {"imported": 0, "duplicate": 0, "failed": 0}

    drafts = list(job.drafts.filter(status__in=["pending", "edited"]).order_by("row_index"))
    type_map = {qt.code: qt for qt in QuestionType.objects.all()}

    with transaction.atomic():
        for draft in drafts:
            errors = draft.errors or []
            has_error = any(e.get("level") == "error" for e in errors)
            # skip_errors=True → 跳过有错的行；False → 仍然尝试入库（便于"我知道它是小问题"的场景）
            if has_error and skip_errors:
                draft.status = "discarded"
                draft.save(update_fields=["status"])
                result["failed"] += 1
                continue

            payload = draft.payload or {}
            question_type = type_map.get(payload.get("question_type_code"))
            if question_type is None:
                _mark_failed(draft, "题型不存在")
                result["failed"] += 1
                continue

            passage = _resolve_passage(payload, job)

            question = Question(
                question_type=question_type,
                grade=payload.get("grade") or job.target_grade or 3,
                term=payload.get("term") or "全",
                difficulty=payload.get("difficulty") or 3,
                stem=payload.get("stem") or "",
                content=payload.get("content") or {},
                answer=payload.get("answer") or {},
                explanation=payload.get("explanation") or "",
                suggested_score=Decimal(str(payload.get("suggested_score") or question_type.default_score)),
                options_layout=payload.get("options_layout") or question_type.default_option_layout,
                expected_word_count=payload.get("expected_word_count") or None,
                review_status="approved",
                source_type=job.kind,
                import_job=job,
                passage=passage,
                sequence=int(payload.get("sequence") or 0),
                created_by=job.operator,
            )

            duplicate = question.find_duplicate()
            if duplicate is not None:
                question.duplicate_of = duplicate
                draft.status = "discarded"
                draft.resolved_question = duplicate
                draft.save(update_fields=["status", "resolved_question"])
                result["duplicate"] += 1
                continue

            try:
                question.save()
            except Exception as error:  # noqa: BLE001 - 单行失败不阻断整批
                _mark_failed(draft, str(error))
                result["failed"] += 1
                continue

            _attach_tags(question, payload)
            draft.status = "confirmed"
            draft.resolved_question = question
            draft.save(update_fields=["status", "resolved_question"])
            result["imported"] += 1

        job.imported_rows = result["imported"]
        job.skipped_duplicate = result["duplicate"]
        job.error_rows = result["failed"]
        job.status = "done"
        job.save(update_fields=["imported_rows", "skipped_duplicate", "error_rows", "status"])

    return result


def _resolve_passage(payload: dict, job: ImportJob):
    """按「材料ID或标题」查找已有材料，或用「材料正文」新建。"""
    ref = payload.get("passage_ref")
    body = payload.get("passage_body")

    if ref:
        if str(ref).isdigit():
            return Passage.objects.filter(pk=int(ref)).first()
        existed = Passage.objects.filter(title=ref).first()
        if existed:
            return existed
    if ref or body:
        return Passage.objects.create(
            title=ref or (body[:20] if body else "未命名材料"),
            body=body or "",
            grade=payload.get("grade") or job.target_grade,
            source=payload.get("source") or "",
            created_by=job.operator,
        )
    return None


def _attach_tags(question: Question, payload: dict):
    names = []
    names += [(n, "grammar_point") for n in payload.get("tags_grammar") or []]
    names += [(n, "topic") for n in payload.get("tags_topic") or []]
    for name, category in names:
        tag, _ = Tag.objects.get_or_create(name=name, category=category)
        question.tags.add(tag)


def _mark_failed(draft: ImportDraft, reason: str):
    errors = list(draft.errors or [])
    errors.append({"level": "error", "code": "E999_COMMIT_FAILED", "message": reason, "column": ""})
    draft.errors = errors
    draft.save(update_fields=["errors"])
