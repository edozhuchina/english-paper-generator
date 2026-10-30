"""全流程自检：自动组一份覆盖所有题型的卷子，导出 Word，验证渲染器不报错。

用法：
    DJANGO_SETTINGS_MODULE=config.settings_sqlite .venv\\Scripts\\python scripts/selfcheck_flow.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_sqlite")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402

from apps.bank.models import Question  # noqa: E402
from apps.exporter.plan import build_render_plan  # noqa: E402
from apps.exporter.writer_docx import write_paper_docx  # noqa: E402
from apps.paper.models import Paper, PaperQuestion, PaperSection  # noqa: E402

SECTION_PLAN = [
    ("听力部分", "听录音，选出你听到的内容。每小题读两遍。",
     ["listening_choice", "listening_order", "listening_judge"]),
    ("词汇语法", "从 A、B、C 三个选项中选出最佳答案。",
     ["single_choice", "banked_fill", "word_form_fill", "translation"]),
    ("阅读理解", "阅读短文，完成下列各题。",
     ["reading_choice", "reading_judge", "cloze", "dialogue_completion"]),
    ("语言运用", "按要求完成句子。",
     ["sentence_unscramble", "sentence_rewrite"]),
    ("书面表达", "根据提示完成写作。",
     ["picture_writing", "writing"]),
]


def main():
    grade = 5
    paper = Paper.objects.filter(title="自检样卷（五年级）").first()
    if paper:
        paper.hard_delete()
    paper = Paper.objects.create(
        title="自检样卷（五年级）",
        subtitle="2026 学年第二学期期末测试",
        grade=grade,
        term="下",
        exam_type="final",
        duration_min=60,
        target_score=100,
        answer_included=True,
        answer_sheet_enabled=True,
    )

    total_added = 0
    for order, (title, directions, codes) in enumerate(SECTION_PLAN, start=1):
        section = PaperSection.objects.create(
            paper=paper, order=order, title=title, directions=directions,
            points_each="2",
        )
        for code in codes:
            questions = list(
                Question.objects.filter(question_type__code=code, grade=grade).order_by("id")[:2]
            )
            # 五年级没有就往其它年级借，保证每种题型都被覆盖到
            if not questions:
                questions = list(
                    Question.objects.filter(question_type__code=code).order_by("id")[:2]
                )
            for question in questions:
                order_index = section.items.count() + 1
                PaperQuestion.objects.create(
                    paper=paper, section=section, question=question,
                    order_in_section=order_index, points=question.suggested_score,
                    answer_blank_lines=question.question_type.default_answer_lines,
                )
                total_added += 1

    paper.recompute_total()

    plan = build_render_plan(paper)
    export_dir = Path(settings.MEDIA_ROOT) / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    target = export_dir / "selfcheck.docx"
    write_paper_docx(
        plan, str(target),
        with_answers=True,
        with_answer_sheet=True,
        with_audio_manifest=bool(plan.media_manifest),
    )

    kinds: dict[str, int] = {}
    for item in plan.all_items():
        kinds[item.type_code] = kinds.get(item.type_code, 0) + 1

    print("=" * 60)
    print(f"试卷：{paper.title}")
    print(f"板块数：{len(plan.sections)}    题目数：{len(plan.all_items())}")
    print(f"实际总分：{paper.computed_total_score}    目标：{paper.target_score}")
    print(f"听力清单条目：{len(plan.media_manifest)}")
    print("-" * 60)
    covered = sorted(kinds.keys())
    all_types = list(
        Question.objects.values_list("question_type__code", flat=True).distinct()
    )
    missing = sorted(set(all_types) - set(covered))
    for code in covered:
        print(f"  ✓ {code:<22} {kinds[code]} 题")
    if missing:
        print("-" * 60)
        print("未覆盖题型：", ", ".join(missing))
    print("=" * 60)
    print(f"导出文件：{target}")
    print(f"文件大小：{target.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
