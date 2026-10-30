"""试卷相关的页面与 AJAX 接口。

组卷工作台采用「左选题 / 右组卷」的双栏布局，所有操作走 AJAX，
避免每次拖动都整页刷新。
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView

from apps.bank.models import Question
from apps.catalog.models import QuestionType, Tag
from apps.exporter.plan import build_render_plan
from apps.exporter.writer_docx import write_paper_docx
from apps.paper.models import Paper, PaperQuestion, PaperSection

ILLEGAL_FILENAME_RE = re.compile(r'[\\/:*?"<>|]+')


def _safe_filename(name: str) -> str:
    cleaned = ILLEGAL_FILENAME_RE.sub("_", (name or "").strip())
    return cleaned[:80] or "exam"


# =========================================================== 列表 / 新建


class PaperListView(ListView):
    model = Paper
    template_name = "paper/paper_list.html"
    context_object_name = "papers"
    paginate_by = 20
    ordering = ["-id"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_papers"] = Paper.objects.count()
        return context


class PaperCreateView(CreateView):
    model = Paper
    template_name = "paper/paper_form.html"
    fields = [
        "title",
        "subtitle",
        "grade",
        "term",
        "exam_type",
        "duration_min",
        "target_score",
        "answer_included",
        "answer_sheet_enabled",
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["types"] = QuestionType.objects.filter(is_active=True).order_by("group", "sort_order")
        return context

    def form_valid(self, form):
        if self.request.user.is_authenticated:
            form.instance.creator = self.request.user
        with transaction.atomic():
            response = super().form_valid(form)
            paper = self.object
            # 建卷时给一套默认板块，省得手工从零搭
            PaperSection.objects.get_or_create(
                paper=paper, order=1,
                defaults={"title": "听力部分", "section_type": "listening",
                          "directions": "听录音，选出你所听到的内容。每小题读两遍。",
                          "number_style": "arabic", "points_each": Decimal("1")},
            )
            PaperSection.objects.get_or_create(
                paper=paper, order=2,
                defaults={"title": "笔试部分", "section_type": "vocab_grammar",
                          "directions": "从 A、B、C 三个选项中选出最佳答案。",
                          "number_style": "arabic", "points_each": Decimal("1")},
            )
        messages.success(self.request, f"试卷「{paper.title}」已创建，开始挑题吧")
        return response


class PaperDeleteView(View):
    def post(self, request, pk, *args, **kwargs):
        paper = get_object_or_404(Paper, pk=pk)
        paper.delete()
        messages.success(request, f"试卷「{paper.title}」已移到回收站（可在后台恢复）")
        return redirect("paper:list")


# =========================================================== 组卷工作台


class PaperBuilderView(View):
    """双栏组卷台：左边题库挑题，右边试卷拼装。"""

    template_name = "paper/paper_builder.html"

    def get(self, request, pk, *args, **kwargs):
        from django.shortcuts import render

        from apps.paper.services import serialize_question

        paper = get_object_or_404(Paper, pk=pk)
        params = request.GET

        queryset = Question.objects.select_related("question_type", "passage").prefetch_related("tags")
        queryset = queryset.filter(review_status="approved")

        type_code = params.get("type")
        if type_code:
            queryset = queryset.filter(question_type__code=type_code)
        group = params.get("group")
        if group:
            queryset = queryset.filter(question_type__group=group)
        grade = params.get("grade") or str(paper.grade)
        if grade:
            queryset = queryset.filter(grade=grade)
        difficulty = params.get("difficulty")
        if difficulty:
            queryset = queryset.filter(difficulty=difficulty)
        keyword = params.get("q")
        if keyword:
            queryset = queryset.filter(
                Q(stem__icontains=keyword)
                | Q(answer_text__icontains=keyword)
                | Q(passage__body__icontains=keyword)
            )

        selected_ids = set(paper.items.values_list("question_id", flat=True))

        context = {
            "paper": paper,
            "types": QuestionType.objects.filter(is_active=True).order_by("group", "sort_order"),
            "tags": Tag.objects.all().order_by("category", "sort_order"),
            "candidates": queryset[:40],
            "selected_ids": selected_ids,
            "request_params": params,
            "current_type": params.get("type", ""),
            "current_group": params.get("group", ""),
            "current_grade": grade,
            "current_difficulty": params.get("difficulty", ""),
            "keyword": params.get("q", ""),
            "type_count": dict(
                Question.objects.filter(review_status="approved")
                .values_list("question_type__code")
                .annotate(count=Count("id"))
            ),
            "candidate_json": json.dumps(
                [serialize_question(q) for q in queryset[:40]], ensure_ascii=False
            ),
        }
        return render(request, self.template_name, context)


# =========================================================== AJAX：题目进出卷


@require_POST
def add_questions(request, pk):
    """把勾选的题目加入试卷（默认进最后一个板块）。"""
    paper = get_object_or_404(Paper, pk=pk)
    payload = _json_body(request)
    question_ids = payload.get("question_ids") or []
    section_id = payload.get("section_id")

    if not question_ids:
        return JsonResponse({"ok": False, "error": "没有选中任何题目"}, status=400)

    section = None
    if section_id:
        section = PaperSection.objects.filter(paper=paper, pk=section_id).first()
    if section is None:
        # 前端没指定板块时续到最后一个板块，不要每次加题都新开一个板块
        section = paper.sections.order_by("-order").first()
    if section is None:
        # 一个板块都没有时才兜底新建
        section = PaperSection.objects.create(
            paper=paper, order=1, title="笔试部分",
            section_type="vocab_grammar", points_each=Decimal("1"),
        )

    added, skipped = 0, []
    with transaction.atomic():
        for qid in question_ids:
            question = Question.objects.filter(pk=qid).first()
            if question is None:
                continue
            exists = PaperQuestion.objects.filter(paper=paper, question=question).exists()
            if exists:
                skipped.append(question.id)
                continue
            max_order = section.items.aggregate(m=Max("order_in_section"))["m"] or 0
            PaperQuestion.objects.create(
                paper=paper,
                section=section,
                question=question,
                order_in_section=max_order + 1,
                points=question.suggested_score,
                answer_blank_lines=question.question_type.default_answer_lines,
            )
            added += 1

    paper.recompute_total()
    return JsonResponse({"ok": True, "added": added, "skipped": skipped})


@require_POST
def remove_question(request, pk, item_id):
    paper = get_object_or_404(Paper, pk=pk)
    item = get_object_or_404(PaperQuestion, pk=item_id, paper=paper)
    question_id = item.question_id
    item.delete()
    _resequence(paper)
    paper.recompute_total()
    return JsonResponse({"ok": True, "removed": question_id})


@require_POST
def update_item(request, pk, item_id):
    """改分值 / 答题行数 / 题号覆盖 / 本卷题干微调。"""
    paper = get_object_or_404(Paper, pk=pk)
    item = get_object_or_404(PaperQuestion, pk=item_id, paper=paper)
    payload = _json_body(request)

    if "points" in payload:
        try:
            item.points = Decimal(str(payload["points"]))
            item.points_locked = True
        except (InvalidOperation, ValueError):
            return JsonResponse({"ok": False, "error": "分值不是合法数字"}, status=400)
    if "answer_blank_lines" in payload:
        item.answer_blank_lines = int(payload["answer_blank_lines"] or 0)
    if "display_no_override" in payload:
        item.display_no_override = str(payload["display_no_override"] or "")[:16]
    if "custom_stem" in payload:
        item.custom_stem = payload["custom_stem"] or ""
    if "points_locked" in payload:
        item.points_locked = bool(payload["points_locked"])

    item.save()
    paper.recompute_total()
    return JsonResponse({"ok": True, "points": str(item.points)})


@require_POST
def reorder_items(request, pk):
    """拖拽后保存顺序；同时支持跨板块移动。"""
    paper = get_object_or_404(Paper, pk=pk)
    payload = _json_body(request)
    orders = payload.get("orders") or []
    if not orders:
        return JsonResponse({"ok": False, "error": "缺少排序数据"}, status=400)

    with transaction.atomic():
        for entry in orders:
            item_id = entry.get("item_id")
            section_id = entry.get("section_id")
            order = int(entry.get("order", 0))
            item = PaperQuestion.objects.filter(pk=item_id, paper=paper).first()
            if item is None:
                continue
            if section_id:
                section = PaperSection.objects.filter(paper=paper, pk=section_id).first()
                if section is not None:
                    item.section = section
            item.order_in_section = order
            item.save()

    _resequence(paper)
    return JsonResponse({"ok": True})


# =========================================================== AJAX：板块


@require_POST
def create_section(request, pk):
    paper = get_object_or_404(Paper, pk=pk)
    payload = _json_body(request)
    title = (payload.get("title") or "新板块").strip()[:64]
    last_order = paper.sections.aggregate(m=Max("order"))["m"] or 0
    section = PaperSection.objects.create(
        paper=paper,
        order=last_order + 1,
        title=title,
        section_type=payload.get("section_type") or "custom",
        directions=payload.get("directions") or "",
        points_each=Decimal(str(payload.get("points_each") or 1)),
    )
    return JsonResponse({"ok": True, "section": _section_json(section)})


@require_POST
def update_section(request, pk, section_id):
    paper = get_object_or_404(Paper, pk=pk)
    section = get_object_or_404(PaperSection, pk=section_id, paper=paper)
    payload = _json_body(request)

    if "title" in payload:
        section.title = (payload["title"] or "").strip()[:64]
    if "directions" in payload:
        section.directions = payload["directions"] or ""
    if "number_style" in payload:
        section.number_style = payload["number_style"] or "arabic"
    if "points_each" in payload:
        try:
            section.points_each = Decimal(str(payload["points_each"]))
            # 统一分值模式下把板块内所有题刷新
            if section.points_mode == "uniform":
                locked = PaperQuestion.objects.filter(section=section, points_locked=True)
                PaperQuestion.objects.filter(section=section).exclude(
                    pk__in=locked.values_list("pk", flat=True)
                ).update(points=section.points_each)
        except (InvalidOperation, ValueError):
            return JsonResponse({"ok": False, "error": "分值不是合法数字"}, status=400)
    if "order" in payload:
        section.order = int(payload["order"])
    section.save()

    paper.recompute_total()
    return JsonResponse({"ok": True, "section": _section_json(section)})


@require_POST
def delete_section(request, pk, section_id):
    paper = get_object_or_404(Paper, pk=pk)
    section = get_object_or_404(PaperSection, pk=section_id, paper=paper)
    if section.items.exists():
        return JsonResponse(
            {"ok": False, "error": "该板块下还有题目，请先移除题目"}, status=400
        )
    section.delete()
    paper.recompute_total()
    return JsonResponse({"ok": True})


# =========================================================== 导出


def export_docx(request, pk):
    """导出可编辑 Word 试卷。"""
    paper = get_object_or_404(Paper, pk=pk)
    paper.recompute_total()

    plan = build_render_plan(paper)
    export_dir = Path(settings.MEDIA_ROOT) / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    # 文件名带试卷 ID 与导出时刻：同名试卷反复导出（或覆盖改名后）不会互相顶掉
    stamp = timezone.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{_safe_filename(paper.title)}_{paper.pk}_{stamp}.docx"
    target = export_dir / filename

    write_paper_docx(
        plan,
        str(target),
        with_answers=paper.answer_included,
        with_answer_sheet=paper.answer_sheet_enabled,
        with_audio_manifest=bool(plan.media_manifest),
    )

    paper.last_exported_at = paper.updated_at
    paper.save(update_fields=["last_exported_at"])

    response = FileResponse(open(target, "rb"), as_attachment=True, filename=filename)
    return response


# =========================================================== 内部工具


def _json_body(request) -> dict:
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


def _resequence(paper: Paper):
    """让每个板块内的 order_in_section 重新变成连续的 1,2,3…"""
    for section in paper.sections.all():
        for index, item in enumerate(section.items.order_by("order_in_section", "id"), start=1):
            if item.order_in_section != index:
                item.order_in_section = index
                item.save(update_fields=["order_in_section"])


def _section_json(section: PaperSection) -> dict:
    return {
        "id": section.id,
        "order": section.order,
        "title": section.title,
        "directions": section.directions,
        "number_style": section.number_style,
        "points_each": str(section.points_each),
        "count": section.items.count(),
        "subtotal": str(section.subtotal()),
    }
