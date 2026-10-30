"""python-docx 排版辅助函数。

封装了本项目反复用到的几件"python-docx 没有原生 API、必须手写 XML"的事：
中文字体、无边框/单边边框表格、页码域、答题空格线、等比例插图。

注意：python-docx 1.0 起 OxmlElement / parse_xml 从 docx.oxml.xmlchemy 迁到了
docx.oxml.parser，务必用新路径。
"""

from __future__ import annotations

from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml.parser import OxmlElement
from docx.shared import Cm, Pt
from PIL import Image

# ------------------------------------------------------------------ 字体

ASCII_FONT = "Times New Roman"
EAST_FONT = "宋体"
BODY_SIZE = Pt(10.5)


def set_run_font(
    run,
    size=BODY_SIZE,
    bold=False,
    italic=False,
    ascii_font: str = ASCII_FONT,
    east_font: str = EAST_FONT,
    underline=False,
    color=None,
):
    """设置 run 字体。**必须同时设 eastAsia**，否则中文会掉到默认字体。"""
    run.font.name = ascii_font
    run.font.size = size
    run.bold = bold
    run.italic = italic
    run.underline = underline
    if color is not None:
        run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:ascii"), ascii_font)
    rfonts.set(qn("w:hAnsi"), ascii_font)
    rfonts.set(qn("w:eastAsia"), east_font)
    return run


def add_styled_paragraph(doc, text="", *, size=BODY_SIZE, bold=False, italic=False,
                         align=None, space_before=0, space_after=0, indent_cm=None,
                         hanging_cm=None, ascii_font=ASCII_FONT, east_font=EAST_FONT):
    """新建一个可控样式的段落。**不用 add_heading()**，那会带上蓝色主题字体。"""
    para = doc.add_paragraph()
    fmt = para.paragraph_format
    fmt.space_before = Pt(space_before)
    fmt.space_after = Pt(space_after)
    if align is not None:
        para.alignment = align
    if indent_cm is not None:
        fmt.left_indent = Cm(indent_cm)
    if hanging_cm is not None:
        fmt.first_line_indent = Cm(hanging_cm)
    if text:
        set_run_font(para.add_run(text), size=size, bold=bold, italic=italic,
                     ascii_font=ascii_font, east_font=east_font)
    return para


# ------------------------------------------------------------------ 页面

def setup_a4(doc, *, top=2.0, bottom=2.0, left=1.8, right=1.8):
    """A4 纵向 + 页边距（单位 cm）。"""
    from docx.shared import Cm as _Cm, Mm as _Mm  # noqa: F401  (局部导入避免循环)

    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(top)
    section.bottom_margin = Cm(bottom)
    section.left_margin = Cm(left)
    section.right_margin = Cm(right)
    return section


# ------------------------------------------------------------------ 表格

def _set_tbl_borders(table, **edges):
    """逐边设置表格边框。edges: top/bottom/left/right/inside_h/inside_v -> dict(val, sz)"""
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge, spec in edges.items():
        tag = {
            "top": "w:top",
            "bottom": "w:bottom",
            "left": "w:left",
            "right": "w:right",
            "inside_h": "w:insideH",
            "inside_v": "w:insideV",
        }[edge]
        el = OxmlElement(tag)
        el.set(qn("w:val"), spec.get("val", "single"))
        el.set(qn("w:sz"), str(spec.get("sz", 4)))
        el.set(qn("w:space"), "0")
        if spec.get("color"):
            el.set(qn("w:color"), spec["color"])
        borders.append(el)
    tbl_pr.append(borders)


def make_borderless_table(doc, rows: int, cols: int, width: float | None = None):
    """创建完全无边框的表格——本项目所有对齐布局都靠它完成。"""
    table = doc.add_table(rows=rows, cols=cols)
    _set_tbl_borders(
        table,
        top={"val": "none"},
        bottom={"val": "none"},
        left={"val": "none"},
        right={"val": "none"},
        inside_h={"val": "none"},
        inside_v={"val": "none"},
    )
    return table


def set_cell_bottom_border(cell, sz=6):
    """只给单元格留下边框——用于做答题横线。"""
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for tag in ("w:top", "w:left", "w:right"):
        el = OxmlElement(tag)
        el.set(qn("w:val"), "none")
        borders.append(el)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(sz))
    bottom.set(qn("w:space"), "0")
    bottom.set(qn("w:color"), "808080")
    borders.append(bottom)
    tc_pr.append(borders)


def add_answer_lines(doc, lines: int, height_cm: float = 0.75, *, border=True):
    """作文/写话的答题横线。用表格+单元格下边框，印刷效果最稳。"""
    if lines <= 0:
        return None
    table = doc.add_table(rows=lines, cols=1)
    _set_tbl_borders(
        table,
        top={"val": "none"},
        bottom={"val": "none"},
        left={"val": "none"},
        right={"val": "none"},
        inside_h={"val": "none"},
        inside_v={"val": "none"},
    )
    for row in table.rows:
        row.height = Cm(height_cm)
        cell = row.cells[0]
        cell.vertical_alignment = WD_ALIGN_VERTICAL.BOTTOM
        if border:
            set_cell_bottom_border(cell)
    return table


def add_inline_blank(run, width_chars: int = 10):
    """填空题的行内空格下划线。"""
    run.text = " " * width_chars
    run.underline = True
    return run


def add_underline_paragraph(doc, width_cm: float = 6.0):
    """整行下划线（主观题答题位）。"""
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(2)
    para.paragraph_format.space_after = Pt(6)
    run = para.add_run(" " * 8)
    run.underline = True
    return para


# ------------------------------------------------------------------ 图片

MAX_IMAGE_W_CM = 10.5
MAX_IMAGE_H_CM = 7.0


def add_scaled_picture(paragraph_or_cell, path: str, *, max_w=MAX_IMAGE_W_CM, max_h=MAX_IMAGE_H_CM):
    """按原始 dpi 与像素等比缩放插图，避免图片被拉伸变形。"""
    try:
        image = Image.open(path)
        px_w, px_h = image.size
        dpi = (image.info.get("dpi") or (96, 96))[0] or 96
        width_cm = px_w / dpi * 2.54
        height_cm = px_h / dpi * 2.54
    except Exception:  # noqa: BLE001 - 读不到图就退回默认尺寸
        width_cm, height_cm = max_w, max_h

    scale = min(max_w / width_cm, max_h / height_cm, 1.0)
    target_w = Cm(width_cm * scale)
    try:
        return paragraph_or_cell.add_run().add_picture(path, width=target_w)
    except Exception:  # noqa: BLE001
        return paragraph_or_cell.add_run("[图片缺失]")


# ------------------------------------------------------------------ 页码

def add_page_field(paragraph, instr="PAGE", align=WD_ALIGN_PARAGRAPH.CENTER):
    """手写页码域（Total pages 用 NUMPAGES）。python-docx 无原生 API。"""
    paragraph.alignment = align
    run = paragraph.add_run()
    set_run_font(run, size=Pt(9))
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), instr)
    fld.append(run._r)
    paragraph._p.append(fld)
    return paragraph


def add_footer_page_number(section):
    """给节添加「第 X 页 / 共 Y 页」页脚。"""
    footer = section.footer
    para = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.add_run("第 ")
    set_run_font(run, size=Pt(9))
    add_page_field(para, "PAGE", align=None)
    tail = para.add_run(" 页，共 ")
    set_run_font(tail, size=Pt(9))
    add_page_field(para, "NUMPAGES", align=None)
    tail2 = para.add_run(" 页")
    set_run_font(tail2, size=Pt(9))
    return para
