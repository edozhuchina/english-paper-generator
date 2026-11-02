"""组卷接口回归测试。

重点守护「加入试卷」这条链路：它曾经因为用了未定义的变量而整条 500，
而页面冒烟测试只发 GET，拦不住这类错误。
"""

from __future__ import annotations

import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from apps.bank.models import Question
from apps.catalog.models import QuestionType
from apps.paper.models import Paper, PaperQuestion, PaperSection


class PaperTestMixin:
    """一份带板块与三道题的干净环境。"""

    def setUp(self):
        self.user = User.objects.create_user("tester", password="pw-selftest-2026")
        self.client.force_login(self.user)
        self.question_type = QuestionType.objects.create(
            code="single_choice", name="单项选择", default_score=Decimal("2")
        )
        self.paper = Paper.objects.create(title="测试卷", grade=5, target_score=Decimal("100"))
        self.section = PaperSection.objects.create(
            paper=self.paper, order=1, title="笔试部分", points_each=Decimal("2")
        )
        self.questions = [self.make_question(f"He ______ football. #{index}") for index in range(3)]

    def make_question(self, stem: str) -> Question:
        return Question.objects.create(
            question_type=self.question_type,
            grade=5,
            stem=stem,
            suggested_score=Decimal("2"),
            review_status="approved",
        )

    def post_add(self, ids, section_id=None):
        payload = {"question_ids": ids}
        if section_id is not None:
            payload["section_id"] = section_id
        return self.client.post(
            f"/papers/{self.paper.pk}/items/add/",
            data=json.dumps(payload),
            content_type="application/json",
        )


class AddQuestionsTests(PaperTestMixin, TestCase):
    def test_numbers_items_continuously_across_calls(self):
        first = self.post_add([self.questions[0].pk], section_id=self.section.pk)
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(first.json()["added"], 1)

        second = self.post_add(
            [self.questions[1].pk, self.questions[2].pk], section_id=self.section.pk
        )
        self.assertEqual(second.json()["added"], 2)

        orders = list(
            PaperQuestion.objects.filter(paper=self.paper)
            .order_by("order_in_section")
            .values_list("order_in_section", flat=True)
        )
        self.assertEqual(orders, [1, 2, 3])

    def test_recomputes_total_score(self):
        self.post_add([question.pk for question in self.questions], section_id=self.section.pk)
        self.paper.refresh_from_db()
        self.assertEqual(self.paper.computed_total_score, Decimal("6"))

    def test_skips_duplicates(self):
        self.post_add([self.questions[0].pk], section_id=self.section.pk)
        again = self.post_add([self.questions[0].pk], section_id=self.section.pk)
        self.assertEqual(again.json()["added"], 0)
        self.assertEqual(again.json()["skipped"], [self.questions[0].pk])
        self.assertEqual(PaperQuestion.objects.filter(paper=self.paper).count(), 1)

    def test_omitting_section_id_appends_to_last_section(self):
        """组卷台不传 section_id，题目应该续到最后一个板块，而不是每次新开板块。"""
        self.post_add([self.questions[0].pk])
        self.post_add([self.questions[1].pk])

        self.assertEqual(PaperSection.objects.filter(paper=self.paper).count(), 1)
        self.assertEqual(
            list(
                PaperQuestion.objects.filter(paper=self.paper)
                .order_by("order_in_section")
                .values_list("order_in_section", flat=True)
            ),
            [1, 2],
        )

    def test_creates_section_when_paper_has_none(self):
        PaperSection.objects.filter(paper=self.paper).delete()
        response = self.post_add([self.questions[0].pk])
        self.assertEqual(response.status_code, 200, response.content)
        section = PaperSection.objects.get(paper=self.paper)
        self.assertEqual(section.order, 1)
        self.assertEqual(self.paper.items.count(), 1)


class LoginFlowTests(TestCase):
    def setUp(self):
        User.objects.create_user("teacher", password="pw-selftest-2026")

    def test_valid_credentials_redirect_to_paper_list(self):
        response = self.client.post(
            "/login/", {"username": "teacher", "password": "pw-selftest-2026"}
        )
        self.assertRedirects(response, "/papers/", fetch_redirect_response=False)
        self.assertIn("sessionid", self.client.cookies)

    def test_wrong_password_stays_on_login_form(self):
        response = self.client.post("/login/", {"username": "teacher", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        # 具体文案由 Django 的认证表单给出（中文翻译会变），这里只断言表单确实报错
        self.assertTrue(response.context["form"].non_field_errors())

    def test_logout_ends_the_session(self):
        self.client.login(username="teacher", password="pw-selftest-2026")
        self.client.post("/logout/")
        response = self.client.get("/papers/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.headers["Location"])


class BuilderAccessTests(TestCase):
    def test_anonymous_visitor_is_redirected_to_login(self):
        paper = Paper.objects.create(title="匿名不可见", grade=5)
        response = self.client.get(f"/papers/{paper.pk}/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.headers["Location"])

    def test_logged_in_visitor_sees_builder(self):
        user = User.objects.create_user("viewer", password="pw-selftest-2026")
        self.client.force_login(user)
        paper = Paper.objects.create(title="登录可见", grade=5)
        response = self.client.get(f"/papers/{paper.pk}/")
        self.assertEqual(response.status_code, 200)
