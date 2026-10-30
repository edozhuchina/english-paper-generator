"""打印视图。与 Word 导出共用同一份 RenderPlan，保证两处排版一致。"""

from __future__ import annotations

from django.shortcuts import get_object_or_404, render

from apps.exporter.plan import RenderPlan, build_render_plan
from apps.paper.models import Paper


def _build_context(paper: Paper, include_answers: bool) -> dict:
    paper.recompute_total()
    plan: RenderPlan = build_render_plan(paper, include_answers=include_answers)
    return {
        "paper": paper,
        "plan": plan,
        "mode": "answer" if include_answers else "student",
    }


def paper_print(request, pk):
    """试卷打印页（A4，浏览器 Ctrl+P 另存 PDF）。"""
    paper = get_object_or_404(Paper, pk=pk)
    include = request.GET.get("mode") == "answer"
    return render(request, "prints/paper.html", _build_context(paper, include))


def answer_print(request, pk):
    """仅答案与解析页。"""
    paper = get_object_or_404(Paper, pk=pk)
    return render(request, "prints/answers.html", _build_context(paper, True))
