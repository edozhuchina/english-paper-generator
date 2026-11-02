"""题库页面测试：删除后的 next 跳转必须限制在本站。"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase

from apps.bank.models import Question
from apps.catalog.models import QuestionType


class QuestionDeleteRedirectTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("tester", password="Zx9-luomiao-2026")
        self.client.force_login(self.user)
        # 测试库不带 fixtures，题型字典得自己造一行
        self.qtype, _ = QuestionType.objects.get_or_create(
            code="single_choice",
            defaults={"name": "单项选择", "group": "vocab_grammar", "has_options": True},
        )

    def _make_question(self, stem: str) -> Question:
        return Question.objects.create(
            question_type=self.qtype,
            grade=5,
            stem=stem,
            answer={"v": 1},
            review_status="approved",
        )

    def test_external_next_falls_back_to_bank(self):
        question = self._make_question("外站跳转测试")
        response = self.client.post(
            f"/bank/{question.pk}/delete/", {"next": "https://evil.example/phish"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/bank/")

    def test_protocol_relative_next_falls_back(self):
        question = self._make_question("协议相对跳转测试")
        response = self.client.post(f"/bank/{question.pk}/delete/", {"next": "//evil.example"})
        self.assertEqual(response.headers["Location"], "/bank/")

    def test_internal_next_is_kept(self):
        question = self._make_question("站内跳转测试")
        response = self.client.post(
            f"/bank/{question.pk}/delete/", {"next": "/bank/?type=single_choice"}
        )
        self.assertEqual(response.headers["Location"], "/bank/?type=single_choice")

    def test_missing_next_defaults_to_bank(self):
        question = self._make_question("缺省跳转测试")
        response = self.client.post(f"/bank/{question.pk}/delete/")
        self.assertEqual(response.headers["Location"], "/bank/")

    def test_soft_deleted_question_disappears(self):
        question = self._make_question("软删除测试")
        self.client.post(f"/bank/{question.pk}/delete/")
        self.assertFalse(Question.objects.filter(pk=question.pk).exists())
        self.assertTrue(Question._base_manager.filter(pk=question.pk).first().is_deleted)
