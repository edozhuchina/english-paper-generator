"""试卷模块的辅助服务：题目序列化、分值协调等。"""

from __future__ import annotations

from decimal import Decimal

from apps.bank.models import Question


def serialize_question(question: Question) -> dict:
    """给前端组卷台用的轻量结构（不含大块富文本，避免负载过大）。"""
    options = [
        {"key": opt.get("key", ""), "text": opt.get("text", "")}
        for opt in (question.content or {}).get("options", []) or []
    ]
    passage_title = ""
    if question.passage_id and question.passage.title:
        passage_title = question.passage.title
    return {
        "id": question.id,
        "type_code": question.question_type.code,
        "type_name": question.question_type.name,
        "group": question.question_type.group,
        "stem": question.stem,
        "passage_title": passage_title,
        "sequence": question.sequence,
        "options": options,
        "answer_text": question.answer_text,
        "grade": question.grade,
        "difficulty": question.difficulty,
        "suggested_score": str(question.suggested_score),
        "usage_count": question.usage_count,
        "tags": [t.name for t in question.tags.all()],
        "has_audio": question.audio_id is not None or bool(
            question.passage_id and question.passage.audio_id
        ),
    }


def reconcile_points(paper, step=Decimal("0.5"), min_point=Decimal("0.5")):
    """把试卷总分调整到目标总分。

    按 step 步长在**未锁定**的题目上轮转微调，返回实际总分与未能消化的余量。
    """
    from apps.paper.models import PaperQuestion

    items = list(PaperQuestion.objects.filter(paper=paper).order_by("section__order", "order_in_section"))
    actual = sum((item.points for item in items), Decimal("0"))
    diff = Decimal(paper.target_score) - actual
    if diff == 0:
        return actual, Decimal("0")

    adjustable = [item for item in items if not item.points_locked] or items
    sign = 1 if diff > 0 else -1
    step_size = Decimal(step)
    cursor = 0
    guard = 0

    while abs(diff) >= step_size and guard < 10000:
        item = adjustable[cursor % len(adjustable)]
        new_points = item.points + sign * step_size
        if new_points >= min_point:
            item.points = new_points
            diff -= sign * step_size
            cursor += 1
        else:
            cursor += 1
        guard += 1

    for item in items:
        item.save(update_fields=["points"])

    total = sum((item.points for item in items), Decimal("0"))
    paper.computed_total_score = total
    paper.save(update_fields=["computed_total_score"])
    return total, diff
