"""导入链路自检：造一份含"正确行 + 故意错误行"的 xlsx，跑上传校验与确认入库。

用法：
    DJANGO_SETTINGS_MODULE=config.settings_sqlite .venv\\Scripts\\python scripts/selfcheck_import.py
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_sqlite")

import django  # noqa: E402

django.setup()

from django.contrib.auth.models import User  # noqa: E402
from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from django.test import Client  # noqa: E402

from apps.bank.models import Question  # noqa: E402
from apps.importer.models import ImportDraft, ImportJob  # noqa: E402

HEADERS = [
    "题型", "年级", "学期", "难度", "题干",
    "选项A", "选项B", "选项C", "选项D", "答案", "解析", "建议分值",
    "知识点标签", "话题标签", "选项排版",
]

ROWS = [
    # --- 正确行
    ["single_choice", 5, "下", 3, "He ______ football every afternoon.",
     "play", "plays", "playing", "played", "B", "主语三单，一般现在时", 1, "一般现在时", "体育运动", "vertical"],
    ["single_choice", 5, "下", 3, "There ______ some water in the bottle.",
     "is", "are", "am", "", "A", "water 不可数", 1, "不可数名词", "", "vertical"],
    ["writing", 6, "下", 4, "My Favourite Season",
     "", "", "", "", "内容完整|6;书写工整|4||My favourite season is spring. It is warm and beautiful.",
     "", 10, "", "天气季节", "vertical"],
    ["sentence_unscramble", 4, "上", 2, "连词成句",
     "", "", "", "", "Where is the cat?", "", 2, "特殊疑问句", "动物朋友", "vertical"],
    # --- 故意的错误行
    ["unknown_type", 5, "下", 3, "未知题型测试", "a", "b", "c", "", "A", "", 1, "", "", ""],
    ["single_choice", 5, "下", 3, "选项不足测试", "onlyone", "", "", "", "A", "", 1, "", "", ""],
    ["single_choice", 5, "下", 3, "答案越界测试", "a", "b", "c", "", "Z", "", 1, "", "", ""],
]


def build_xlsx() -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "题目"
    sheet.append(HEADERS)
    for row in ROWS:
        sheet.append(row)
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def main():
    data = build_xlsx()
    # ALLOWED_HOSTS 只放行本机后，测试客户端的默认 host（testserver）会被拦，所以显式指定
    client = Client(SERVER_NAME="127.0.0.1")

    # 全站登录保护后，上传 / 入库接口都需要登录态
    user, _ = User.objects.get_or_create(username="selfcheck")
    user.set_password("selfcheck-2026")
    user.is_active = True
    user.save()
    client.force_login(user)

    before = Question.objects.count()

    response = client.post(
        "/import/upload/",
        {"file": SimpleUploadedFile("selftest.xlsx", data)},
    )
    print(f"上传校验：HTTP {response.status_code}")

    job = ImportJob.objects.order_by("-id").first()
    print(f"批次 #{job.id} 状态={job.get_status_display()} "
          f"总行={job.total_rows} 可入库={job.valid_rows} 错误={job.error_rows}")
    print(f"草稿数：{ImportDraft.objects.filter(job=job).count()}")

    print("-" * 60)
    for item in job.report:
        row_no = item["row"]
        for err in item["errors"]:
            level = "错误" if err["level"] == "error" else "提醒"
            print(f"  行{row_no} [{level}] {err['code']}: {err['message']}")

    print("-" * 60)
    response = client.post(f"/import/{job.id}/commit/", {"skip_errors": "1"})
    job.refresh_from_db()
    after = Question.objects.count()
    print(f"入库：HTTP {response.status_code}；题目 {before} -> {after}（新增 {after - before}）")
    print(f"批次统计：入库={job.imported_rows} 重复={job.skipped_duplicate} 失败={job.error_rows}")

    # 再传一次同一文件，验证去重
    client.post("/import/upload/", {"file": SimpleUploadedFile("selftest.xlsx", data)})
    job2 = ImportJob.objects.order_by("-id").first()
    client.post(f"/import/{job2.id}/commit/", {"skip_errors": "1"})
    job2.refresh_from_db()
    final = Question.objects.count()
    print(f"重复上传：新增 {final - after} 道题（应为 0），跳过重复 {job2.skipped_duplicate} 道")

    print("=" * 60)
    ok = (job.imported_rows == 4) and (final - after == 0)
    print("导入链路自检：" + ("通过" if ok else "存在问题，请检查上面输出"))


if __name__ == "__main__":
    main()
