"""Excel / CSV 导入：读取、校验、生成待入库草稿。

表头约定（总表 + `题型` 列）：
题型 / 年级 / 学期 / 难度 / 材料ID或标题 / 材料正文 / 小题序号 / 题干 /
选项A~选项E / 答案 / 解析 / 建议分值 / 知识点标签 / 话题标签 /
图片文件 / 音频文件 / 播放次数 / 选项排版 / 建议词数 / 出题来源 / 录入备注

也兼容"按题型分 sheet"的老文件：若某 sheet 没有 `题型` 列，则用 sheet 名猜测题型。
答案列的统一写法：
  * 选择类   B
  * 填空类   plays|goes       （多空用 | 分隔，同空多解用 / 分隔）
  * 判断类   T,F,T
  * 排序类   3,1,4,2
  * 写作类   要点1 |2;要点2 |3||范文全文
"""

from __future__ import annotations

import csv
import io
from typing import Any

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from apps.catalog.models import QuestionType

HEADERS = [
    "题型", "年级", "学期", "难度",
    "材料ID或标题", "材料正文", "小题序号",
    "题干",
    "选项A", "选项B", "选项C", "选项D", "选项E",
    "答案", "解析", "建议分值",
    "知识点标签", "话题标签",
    "图片文件", "音频文件", "播放次数", "选项排版", "建议词数",
    "出题来源", "录入备注",
]

REQUIRED_COLUMNS = ["题型", "年级", "题干", "答案"]


# =========================================================== 读取


def read_upload(uploaded) -> list[dict]:
    """把上传文件读成 [{列名: 值}]，自动识别 xlsx / csv。"""
    name = (uploaded.name or "").lower()
    if name.endswith(".csv"):
        raw = uploaded.read().decode("utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(raw))
        rows = list(reader)
        if not rows:
            return []
        header = [str(cell).strip() for cell in rows[0]]
        return [_zip_row(header, row, sheet_name="CSV") for row in rows[1:] if any(str(c).strip() for c in row)]

    workbook = load_workbook(uploaded, data_only=True)
    result: list[dict] = []
    for sheet in workbook.worksheets:
        rows = list(sheet.values)
        if not rows:
            continue
        header = [str(cell).strip() if cell is not None else "" for cell in rows[0]]
        if not [h for h in header if h]:
            continue
        for index, row in enumerate(rows[1:], start=2):
            if not any(cell is not None and str(cell).strip() for cell in row):
                continue
            record = _zip_row(header, row, sheet_name=sheet.title)
            record["__row__"] = index
            record["__sheet__"] = sheet.title
            result.append(record)
    return result


def _zip_row(header: list[str], row, sheet_name: str) -> dict:
    record: dict[str, Any] = {}
    for index, key in enumerate(header):
        value = row[index] if index < len(row) else None
        if isinstance(value, str):
            value = value.strip()
        if key:
            record[key] = value
    record.setdefault("__row__", 0)
    record["__sheet__"] = sheet_name
    # 没有题型列时，用 sheet 名兜底
    if "题型" not in record or not record.get("题型"):
        record["题型"] = sheet_name
    return record


# =========================================================== 校验与草稿


def _type_map() -> dict:
    """code / 中文名 -> QuestionType"""
    mapping: dict[str, QuestionType] = {}
    for question_type in QuestionType.objects.all():
        mapping[question_type.code] = question_type
        mapping[question_type.name] = question_type
    return mapping


def parse_rows(rows: list[dict], target_grade=None, default_difficulty=None):
    """把原始行解析成 ImportDraft + 行级错误报告。"""
    from apps.importer.models import ImportDraft

    type_map = _type_map()
    drafts: list[ImportDraft] = []
    report: list[dict] = []
    valid = 0
    error = 0

    for index, row in enumerate(rows, start=1):
        errors: list[dict] = []
        row_no = row.get("__row__") or index

        # --- 必填
        missing = [name for name in REQUIRED_COLUMNS if not row.get(name) and not target_grade and name == "年级"]
        for name in REQUIRED_COLUMNS:
            if not row.get(name) and not (name == "年级" and target_grade):
                missing.append(name)
        missing = sorted(set(missing))
        if missing:
            errors.append(_issue("error", "E001_MISSING_REQUIRED",
                                 f"缺少必填列：{'、'.join(missing)}",
                                 column=",".join(missing)))
            report.append(_report_row(row_no, row, errors))
            error += 1
            continue

        # --- 题型
        question_type = type_map.get(str(row.get("题型", "")).strip())
        if question_type is None:
            errors.append(_issue("error", "E002_UNKNOWN_TYPE",
                                 f"未知题型「{row.get('题型')}」，请填题型代码或标准中文名",
                                 column="题型"))
            report.append(_report_row(row_no, row, errors))
            error += 1
            continue

        grade = row.get("年级") or target_grade
        try:
            grade = int(str(grade).strip())
            if grade not in (3, 4, 5, 6):
                raise ValueError
        except (TypeError, ValueError):
            errors.append(_issue("error", "E002_BAD_GRADE", f"年级必须是 3~6，当前为「{grade}」", column="年级"))

        # --- 选项
        options = []
        for letter in "ABCDE":
            text = row.get(f"选项{letter}")
            if text:
                options.append({"key": letter, "text": str(text).strip(), "image_id": None})
        if question_type.has_options and len(options) < 2:
            errors.append(_issue("error", "E003_BAD_OPTION",
                                 "选择题至少需要两个选项", column="选项A"))

        # --- 答案
        answer, answer_error = parse_answer(question_type, str(row.get("答案", "")), options)
        if answer_error:
            errors.append(_issue("error", answer_error[0], answer_error[1], column="答案"))

        # --- 难度、学期
        difficulty = row.get("难度") or default_difficulty or 3
        try:
            difficulty = int(str(difficulty).strip())
            difficulty = max(1, min(5, difficulty))
        except (TypeError, ValueError):
            difficulty = 3
            errors.append(_issue("warn", "W101_DEFAULT_APPLIED", "难度未填写或非法，已按 3 处理", column="难度"))

        term = str(row.get("学期") or "").strip() or "全"

        # --- 分值
        suggested_score = row.get("建议分值") or question_type.default_score
        try:
            suggested_score = float(str(suggested_score).strip())
        except (TypeError, ValueError):
            suggested_score = float(question_type.default_score)

        content = build_content(question_type, row, options)

        payload = {
            "question_type_code": question_type.code,
            "grade": grade,
            "term": term,
            "difficulty": difficulty,
            "stem": str(row.get("题干") or "").strip(),
            "content": content,
            "answer": answer,
            "explanation": str(row.get("解析") or "").strip(),
            "suggested_score": suggested_score,
            "options_layout": str(row.get("选项排版") or question_type.default_option_layout).strip(),
            "expected_word_count": row.get("建议词数"),
            "tags_grammar": [t for t in str(row.get("知识点标签") or "").replace("，", "、").split("、") if t],
            "tags_topic": [t for t in str(row.get("话题标签") or "").replace("，", "、").split("、") if t],
            "passage_ref": str(row.get("材料ID或标题") or "").strip(),
            "passage_body": str(row.get("材料正文") or "").strip(),
            "sequence": row.get("小题序号"),
            "source": str(row.get("出题来源") or "").strip(),
            "image_file": str(row.get("图片文件") or "").strip(),
            "audio_file": str(row.get("音频文件") or "").strip(),
            "audio_play_count": row.get("播放次数") or 1,
        }

        level = "error" if any(e["level"] == "error" for e in errors) else "warn"
        if level == "error":
            error += 1
        else:
            valid += 1

        if errors:
            report.append(_report_row(row_no, row, errors))

        drafts.append(
            ImportDraft(
                row_index=row_no,
                sheet_name=row.get("__sheet__", ""),
                raw_text=str(row.get("题干") or ""),
                detected_type=question_type,
                payload=payload,
                errors=errors,
            )
        )

    summary = {"total": len(rows), "valid": valid, "error": error, "report": report}
    return drafts, summary


def _issue(level: str, code: str, message: str, column: str = "") -> dict:
    return {"level": level, "code": code, "message": message, "column": column}


def _report_row(row_no, row, errors) -> dict:
    return {
        "row": row_no,
        "sheet": row.get("__sheet__", ""),
        "stem_preview": str(row.get("题干") or "")[:40],
        "errors": errors,
    }


# =========================================================== 答案解析


def parse_answer(question_type: QuestionType, raw: str, options: list[dict]):
    """把答案单元格翻译成统一 answer JSON。返回 (answer, None | (code, message))"""
    answer_type = (question_type.answer_schema or {}).get("type", "single_choice")
    raw = (raw or "").strip()
    letters = [opt["key"] for opt in options]

    if answer_type == "single_choice":
        value = [v.strip().upper() for v in raw.replace("，", ",").split(",") if v.strip()]
        if not value:
            return {}, ("E003_BAD_OPTION", "答案不能为空")
        if letters and value[0] not in letters:
            return {}, ("E003_BAD_OPTION", f"答案「{value[0]}」不在选项 {''.join(letters)} 范围内")
        return {"v": 1, "type": "single_choice", "value": value}, None

    if answer_type == "tf":
        mapper = {"T": True, "F": False, "TRUE": True, "FALSE": False,
                  "正确": True, "错误": False, "√": True, "×": False, "对": True, "错": False}
        values = []
        for part in [p.strip().upper() for p in raw.replace("，", ",").split(",") if p.strip()]:
            if part not in mapper:
                return {}, ("E005_BAD_TF", f"判断题答案只接受 T/F、正确/错误、√/×，收到「{part}」")
            values.append(mapper[part])
        return {"v": 1, "type": "tf", "value": values}, None

    if answer_type == "order":
        try:
            values = [int(v.strip()) for v in raw.replace("，", ",").split(",") if v.strip()]
        except ValueError:
            return {}, ("E005_BAD_ORDER", "排序题答案必须是逗号分隔的数字，例如 3,1,4,2")
        return {"v": 1, "type": "order", "value": values}, None

    if answer_type == "rubric":
        if "||" in raw:
            rubric_part, sample_part = raw.split("||", 1)
        else:
            rubric_part, sample_part = raw, ""
        rubrics = []
        for item in [i.strip() for i in rubric_part.replace("，", ";").split(";") if i.strip()]:
            if "|" in item:
                point, score = item.split("|", 1)
            else:
                point, score = item, "0"
            try:
                score_value = float(score.strip()) if score.strip() else 0
            except ValueError:
                score_value = 0
            rubrics.append({"point": point.strip(), "score": score_value})
        return {
            "v": 1, "type": "rubric",
            "rubric": rubrics,
            "sample": [sample_part.strip()] if sample_part.strip() else [],
        }, None

    # blanks
    blanks = []
    for index, group in enumerate([g.strip() for g in raw.split("|") if g.strip()], start=1):
        blanks.append({
            "no": index,
            "value": [v.strip() for v in group.split("/") if v.strip()],
        })
    return {"v": 1, "type": "blanks", "value": blanks}, None


def build_content(question_type: QuestionType, row: dict, options: list[dict]) -> dict:
    """按题型把行数据组装成 content JSON。"""
    content: dict[str, Any] = {"v": 1}
    code = question_type.code

    if options:
        content["options"] = options
        content["layout"] = {"options": str(row.get("选项排版") or question_type.default_option_layout).strip()}

    if code == "listening_choice":
        content["mode"] = "image" if str(row.get("图片文件")) else "word"
    if code in {"banked_fill"}:
        words = str(row.get("选项A") or "")
        content["word_bank"] = [w.strip() for w in words.replace("，", "、").split("、") if w.strip()]
    if code == "word_form_fill":
        content["blanks"] = [{"no": 1, "given": ""}]
    if code == "translation":
        content["direction"] = "c2e" if _has_chinese(str(row.get("题干") or "")) else "e2c"
    if code == "sentence_unscramble":
        content["words"] = [w for w in str(row.get("题干") or "").replace("|", " ").split() if w]
    if code in {"writing", "picture_writing"}:
        content["topic"] = str(row.get("题干") or "").strip()
        prompts = str(row.get("解析") or "")
        content["prompts"] = [p.strip() for p in prompts.split("\n") if p.strip()]

    return content


def _has_chinese(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


# =========================================================== 模板生成


def build_import_template():
    """生成带下拉校验的 Excel 模板。"""
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "题目"

    header_fill = PatternFill("solid", fgColor="DDEBF7")
    for column_index, header in enumerate(HEADERS, start=1):
        cell = sheet.cell(row=1, column=column_index, value=header)
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        width = 14 if header not in {"题干", "材料正文", "解析", "录入备注"} else 40
        sheet.column_dimensions[get_column_letter(column_index)].width = width
    sheet.freeze_panes = "A2"

    type_names = list(QuestionType.objects.filter(is_active=True).values_list("name", flat=True))
    type_codes = list(QuestionType.objects.filter(is_active=True).values_list("code", flat=True))
    type_list = ",".join(type_names + type_codes)[:250]

    validations = {
        "题型": type_list,
        "年级": "3,4,5,6",
        "学期": "上,下,全",
        "难度": "1,2,3,4,5",
        "选项排版": "vertical,horizontal,grid2,grid4",
    }
    for column_name, source in validations.items():
        if column_name not in HEADERS:
            continue
        column_index = HEADERS.index(column_name) + 1
        letter = get_column_letter(column_index)
        validation = DataValidation(type="list", formula1=f'"{source}"', allow_blank=True)
        validation.error = "请从下拉列表中选择"
        validation.promptTitle = "填写提示"
        validation.prompt = f"请选择：{source}"
        sheet.add_data_validation(validation)
        validation.add(f"{letter}2:{letter}500")

    # 示例行
    sample = {
        "题型": "single_choice",
        "年级": 5,
        "学期": "下",
        "难度": 3,
        "题干": "My father ______ to work by car every day.",
        "选项A": "go",
        "选项B": "goes",
        "选项C": "going",
        "答案": "B",
        "解析": "主语 My father 是第三人称单数，一般现在时动词加 -es。",
        "建议分值": 1,
        "知识点标签": "一般现在时、第三人称单数",
        "话题标签": "日程作息",
        "选项排版": "vertical",
    }
    for column_index, header in enumerate(HEADERS, start=1):
        if header in sample:
            sheet.cell(row=2, column=column_index, value=sample[header])

    # 填写说明 sheet
    guide = workbook.create_sheet("填写说明")
    guide.column_dimensions["A"].width = 100
    guide_lines = [
        "小学英语题库导入模板 · 填写说明",
        "",
        "1. 所有题填在同一个「题目」页，用「题型」列区分；也支持按题型分 sheet（sheet 名需为题型名）。",
        "2. 标红的 4 列为必填：题型、年级、题干、答案；年级可在导入页面统一指定。",
        "3. 选项只写内容，不要写 A. 前缀，系统自动生成 A/B/C/D。",
        "4. 答案写法：",
        "     选择类      B",
        "     填空类      plays|goes        （多个空用 | 分隔；同一空多个可接受答案用 / 分隔）",
        "     判断类      T,F,T             （也支持 正确/错误、√/×）",
        "     排序类      3,1,4,2",
        "     连词/改写/翻译   完整句子，多解用 / 分隔",
        "     写作类      要点1 |2;要点2 |3||参考范文",
        "5. 阅读/完形/听力短文属「一材多题」：同一材料的多个小题，材料ID或标题 填同一个标题，材料正文只在第一行填一次。",
        "6. 导入是两步：先上传做预校验，页面确认无误后再点确认入库。重复题会自动跳过。",
    ]
    for index, line in enumerate(guide_lines, start=1):
        cell = guide.cell(row=index, column=1, value=line)
        if index == 1:
            cell.font = Font(bold=True, size=13)
    return workbook
