"""把 RenderPlan 写成 Word 试卷。

产出物包含：卷头 / 各大题 / 题目正文 / 参考答案与解析 / 答题卡（可选）/ 听力音频清单。
已知限制：python-docx 无法把 mp3 嵌进 docx，因此音频只能以网页播放 + 清单交付。
"""

from __future__ import annotations

from decimal import Decimal

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Cm, Pt

from apps.exporter.docx_helpers import (
    add_answer_lines,
    add_footer_page_number,
    add_scaled_picture,
    add_styled_paragraph,
    make_borderless_table,
    set_run_font,
    setup_a4,
    _set_tbl_borders,
)
from apps.exporter.plan import RenderItem, RenderPlan
from apps.exporter.renderers import get_renderer


def write_paper_docx(
    plan: RenderPlan,
    output_path: str,
    *,
    with_answers: bool | None = None,
    with_answer_sheet: bool = False,
    with_audio_manifest: bool = True,
) -> str:
    """生成试卷 docx，返回文件路径。"""
    with_answers = plan.include_answers if with_answers is None else with_answers

    doc = Document()
    section = setup_a4(doc)
    add_footer_page_number(section)

    _render_header(doc, plan)

    for render_section in plan.sections:
        _render_section_title(doc, render_section.display_title, render_section.directions)
        for item in render_section.items:
            _render_passage_if_any(doc, item)
            renderer = get_renderer(item.renderer_key)
            renderer(doc, item)

    if with_answer_sheet and plan.answer_sheet:
        doc.add_page_break()
        _render_answer_sheet(doc, plan)

    if with_answers:
        doc.add_page_break()
        _render_answers(doc, plan)

    if with_audio_manifest and plan.media_manifest:
        doc.add_page_break()
        _render_audio_manifest(doc, plan)

    doc.save(output_path)
    return output_path


# --------------------------------------------------------------------------- 卷头


def _render_header(doc, plan: RenderPlan):
    header = plan.header or {}

    school_label = header.get("school_label") or "学校：____________"
    top = make_borderless_table(doc, rows=1, cols=2)
    top.alignment = WD_TABLE_ALIGNMENT.CENTER
    left_cell, right_cell = top.rows[0].cells
    left_cell.width = Cm(11)
    right_cell.width = Cm(6.2)
    lp = left_cell.paragraphs[0]
    set_run_font(lp.add_run(school_label), size=Pt(10.5))
    rp = right_cell.paragraphs[0]
    rp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_run_font(rp.add_run("座号：____________"), size=Pt(10.5))

    title = add_styled_paragraph(
        doc, plan.title, size=Pt(16), bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
        space_before=4, space_after=2,
    )
    title.paragraph_format.left_indent = Cm(0)
    title.paragraph_format.first_line_indent = Cm(0)

    if plan.subtitle:
        sub = add_styled_paragraph(
            doc, plan.subtitle, size=Pt(12), align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2
        )
        sub.paragraph_format.first_line_indent = Cm(0)

    meta_bits = []
    if plan.duration_min:
        meta_bits.append(f"考试时间：{plan.duration_min} 分钟")
    if plan.total_score:
        meta_bits.append(f"满分：{_fmt_score(plan.total_score)} 分")
    if meta_bits:
        para = add_styled_paragraph(
            doc, "    ".join(meta_bits), size=Pt(10.5), align=WD_ALIGN_PARAGRAPH.CENTER,
            space_after=4
        )
        para.paragraph_format.first_line_indent = Cm(0)

    if header.get("show_class_name", True):
        info = make_borderless_table(doc, rows=1, cols=3)
        labels = ["学校：________________", "班级：________________", "姓名：________________"]
        widths = [Cm(5.8), Cm(5.8), Cm(5.8)]
        for index, label in enumerate(labels):
            cell = info.rows[0].cells[index]
            cell.width = widths[index]
            set_run_font(cell.paragraphs[0].add_run(label), size=Pt(10.5))

    if header.get("show_score_table", True):
        _render_score_table(doc, plan)

    motto = header.get("motto")
    if motto:
        add_styled_paragraph(doc, motto, size=Pt(9), italic=True,
                             align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)

    note = header.get("note")
    if note:
        add_styled_paragraph(doc, note, size=Pt(9), space_after=2)


def _render_score_table(doc, plan: RenderPlan):
    columns = [s.display_title for s in plan.sections]
    if not columns:
        return
    columns.append("总分")
    table = doc.add_table(rows=2, cols=len(columns))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    header_cells = table.rows[0].cells
    for index, title in enumerate(columns):
        para = header_cells[index].paragraphs[0]
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_run_font(para.add_run(title), size=Pt(9), bold=True)

    value_cells = table.rows[1].cells
    for index in range(len(columns)):
        para = value_cells[index].paragraphs[0]
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_run_font(para.add_run(""), size=Pt(9))


# --------------------------------------------------------------------------- 大题与材料


def _render_section_title(doc, title: str, directions: str = ""):
    para = add_styled_paragraph(
        doc, title, size=Pt(12), bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
        space_before=10, space_after=3,
    )
    para.paragraph_format.first_line_indent = Cm(0)
    if directions:
        dp = add_styled_paragraph(doc, directions, size=Pt(10.5), italic=True, space_after=3)
        dp.paragraph_format.first_line_indent = Cm(0)


def _render_passage_if_any(doc, item: RenderItem):
    passage = item.passage
    if not passage:
        return
    title = passage.get("title")
    if title:
        para = add_styled_paragraph(doc, title, size=Pt(11), bold=True,
                                    align=WD_ALIGN_PARAGRAPH.CENTER, space_before=4, space_after=2)
        para.paragraph_format.first_line_indent = Cm(0)

    image = passage.get("image")
    if image and image.get("path"):
        ip = add_styled_paragraph(doc)
        ip.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_scaled_picture(ip, image["path"], max_w=7.0, max_h=5.0)

    body = (passage.get("body") or "").strip()
    if body:
        for line in body.split("\n"):
            line = line.strip()
            if not line:
                continue
            para = add_styled_paragraph(doc, line, size=Pt(10.5), space_after=1)
            para.paragraph_format.first_line_indent = Cm(0.74)

    audio = passage.get("audio")
    if audio and audio.get("filename"):
        para = add_styled_paragraph(doc, f"（听力材料：{audio['filename']}）",
                                    size=Pt(9), italic=True, space_after=2)
        para.paragraph_format.first_line_indent = Cm(0)


# --------------------------------------------------------------------------- 答案、答题卡、清单


def _render_answers(doc, plan: RenderPlan):
    add_styled_paragraph(doc, "参考答案与解析", size=Pt(14), bold=True,
                         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6)

    for render_section in plan.sections:
        if not render_section.items:
            continue
        add_styled_paragraph(doc, render_section.display_title, size=Pt(12), bold=True,
                             space_before=6, space_after=2)
        for item in render_section.items:
            para = doc.add_paragraph()
            para.paragraph_format.left_indent = Cm(0.74)
            para.paragraph_format.first_line_indent = Cm(-0.74)
            para.paragraph_format.space_after = Pt(1)
            no_run = para.add_run(f"{item.no} ")
            set_run_font(no_run, size=Pt(10.5), bold=True)
            answer_text = _answer_display(item)
            set_run_font(para.add_run(answer_text), size=Pt(10.5))
            if item.explanation:
                exp = doc.add_paragraph()
                exp.paragraph_format.left_indent = Cm(0.74)
                exp.paragraph_format.space_after = Pt(3)
                set_run_font(exp.add_run(f"解析：{item.explanation}"), size=Pt(9), italic=True)


def _answer_display(item: RenderItem) -> str:
    answer = item.answer or {}
    kind = answer.get("type", "")

    if kind == "single_choice":
        value = answer.get("value") or []
        if len(value) == 1 and len(item.options) == 1:
            return str(value[0])
        # 多选场景直接给 key 序列
        keys = [str(v) for v in value]
        if len(keys) == 1 and item.options:
            mapping = {opt.key: opt.text for opt in item.options}
            chosen = mapping.get(keys[0], "")
            return f"{keys[0]}（{chosen}）" if chosen else keys[0]
        return "、".join(keys)
    if kind == "tf":
        mapper = {True: "T", False: "F"}
        return "、".join(mapper.get(bool(v), str(v)) for v in answer.get("value", []))
    if kind == "order":
        return " → ".join(str(v) for v in answer.get("value", []))
    if kind == "blanks":
        parts = []
        for blank in answer.get("value", []):
            values = blank.get("value", []) if isinstance(blank, dict) else [blank]
            values = [str(v) for v in values if v]
            if values:
                parts.append(" / ".join(values))
        return " | ".join(parts) or "（参考答案见解析）"
    if kind == "rubric":
        bits = []
        rubric = answer.get("rubric") or []
        for rule in rubric:
            if isinstance(rule, dict):
                bits.append(f"{rule.get('point', '')}（{rule.get('score', '')}分）")
        sample = answer.get("sample") or []
        if sample:
            bits.append("参考范文：" + " ".join(str(s) for s in sample))
        return "；".join(bits)
    return item.answer_text or "（略）"


def _render_answer_sheet(doc, plan: RenderPlan):
    add_styled_paragraph(doc, "答题卡", size=Pt(14), bold=True,
                         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
    add_styled_paragraph(doc, "请用 2B 铅笔在对应选项上填涂。", size=Pt(9), italic=True, space_after=4)

    per_row = 5
    items = plan.answer_sheet
    rows = (len(items) + per_row - 1) // per_row
    table = doc.add_table(rows=rows * 2, cols=per_row)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    for index, item in enumerate(items):
        block = index // per_row
        row_in_block = index % per_row
        no_row = block * 2
        opt_row = block * 2 + 1

        cell_no = table.cell(no_row, row_in_block)
        p = cell_no.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_run_font(p.add_run(item.no.replace(".", "")), size=Pt(9))

        cell_opt = table.cell(opt_row, row_in_block)
        p2 = cell_opt.paragraphs[0]
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        letters = "".join(opt.key for opt in item.options) or "ABCD"
        set_run_font(p2.add_run("○ " + "  ○ ".join(letters[:5])), size=Pt(8))


def _render_audio_manifest(doc, plan: RenderPlan):
    add_styled_paragraph(doc, "听力音频清单", size=Pt(14), bold=True,
                         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
    add_styled_paragraph(
        doc,
        "说明：python-docx 无法将音频嵌入 Word 文档，请按此清单单独准备播放文件。",
        size=Pt(9), italic=True, space_after=4,
    )
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    headers = ["题目位置", "文件名", "时长(秒)", "播放次数"]
    for index, text in enumerate(headers):
        para = table.rows[0].cells[index].paragraphs[0]
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_run_font(para.add_run(text), size=Pt(9.5), bold=True)

    for entry in plan.media_manifest:
        cells = table.add_row().cells
        values = [
            entry.get("no", ""),
            entry.get("filename", ""),
            f"{entry['duration']:.1f}" if entry.get("duration") else "—",
            str(entry.get("play_count", 1)),
        ]
        for index, value in enumerate(values):
            set_run_font(cells[index].paragraphs[0].add_run(value), size=Pt(9.5))


def _fmt_score(value) -> str:
    try:
        value = Decimal(str(value))
    except Exception:  # noqa: BLE001
        return str(value)
    return f"{value.normalize():f}".rstrip("0").rstrip(".") if value == value.to_integral_value() else f"{value}"
