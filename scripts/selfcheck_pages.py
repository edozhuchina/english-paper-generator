"""页面冒烟测试：逐个访问主要 URL，确保模板能正常渲染。

用法：
    DJANGO_SETTINGS_MODULE=config.settings_sqlite .venv\\Scripts\\python scripts/selfcheck_pages.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_sqlite")

import django  # noqa: E402

django.setup()

from django.contrib.auth.models import User  # noqa: E402
from django.test import Client  # noqa: E402

from apps.bank.models import Question  # noqa: E402
from apps.paper.models import Paper  # noqa: E402

URLS = [
    ("GET", "/login/", "登录页"),
    ("GET", "/admin/login/", "后台登录"),
    ("GET", "/", "首页重定向"),
    ("GET", "/bank/", "题库列表"),
    ("GET", "/bank/create/", "手动录题"),
    ("GET", "/papers/", "试卷列表"),
    ("GET", "/papers/create/", "新建试卷"),
    ("GET", "/import/", "导入首页"),
    ("GET", "/import/template/", "模板下载"),
]


def login(client: Client) -> None:
    """全站登录保护后，所有业务页面都需要先登录。"""
    user, _ = User.objects.get_or_create(username="selfcheck")
    user.set_password("selfcheck-2026")
    user.save()
    client.force_login(user)


def main():
    client = Client()
    failures = 0

    # 登录保护：未登录访问业务页面必须被拦到 /login/
    guard = Client().get("/bank/")
    if guard.status_code == 302 and "/login/" in guard.headers.get("Location", ""):
        print("[OK ] 302 登录保护      /bank/（未登录被拦截）")
    else:
        failures += 1
        print(f"[FAIL] {guard.status_code} 登录保护      /bank/ 未拦截")

    login(client)

    paper = Paper.objects.order_by("-id").first()
    question = Question.objects.order_by("-id").first()

    dynamic = []
    if paper:
        dynamic += [
            ("GET", f"/papers/{paper.pk}/", "组卷工作台"),
            ("GET", f"/papers/{paper.pk}/export/docx/", "导出 Word"),
            ("GET", f"/print/paper/{paper.pk}/", "打印预览"),
            ("GET", f"/print/paper/{paper.pk}/?mode=answer", "含答案打印"),
            ("GET", f"/print/paper/{paper.pk}/answers/", "答案页"),
        ]
    if question:
        dynamic += [
            ("GET", f"/bank/{question.pk}/", "题目详情"),
            ("GET", f"/bank/{question.pk}/edit/", "题目编辑"),
        ]

    for method, url, label in URLS + dynamic:
        try:
            response = client.get(url, follow=False)
            status = response.status_code
            ok = status in (200, 302, 303)
            if not ok:
                failures += 1
            mark = "OK " if ok else "FAIL"
            extra = ""
            if status in (302, 303):
                extra = f" -> {response.headers.get('Location', '')}"
            print(f"[{mark}] {status} {label:<12} {url}{extra}")
        except Exception as error:  # noqa: BLE001
            failures += 1
            print(f"[FAIL] EXC {label:<12} {url}")
            print(f"       {type(error).__name__}: {error}")

    print("=" * 60)
    if failures:
        print(f"存在 {failures} 个失败项")
        sys.exit(1)
    print("全部页面通过冒烟测试")


if __name__ == "__main__":
    main()
