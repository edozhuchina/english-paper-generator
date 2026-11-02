"""导入批次归属校验测试：不能替别人提交 / 取消批次。"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase

from apps.importer.models import ImportJob


class ImportJobOwnershipTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="Zx9-luomiao-2026")
        self.stranger = User.objects.create_user("stranger", password="Zx9-luomiao-2026")
        self.staff = User.objects.create_user(
            "boss", password="Zx9-luomiao-2026", is_staff=True
        )
        self.job = ImportJob.objects.create(
            kind="excel", original_filename="owner.xlsx", status="awaiting_confirm", operator=self.owner
        )

    def _commit(self, user):
        self.client.force_login(user)
        return self.client.post(f"/import/{self.job.pk}/commit/", {"skip_errors": "1"})

    def test_stranger_cannot_commit_someone_elses_job(self):
        self._commit(self.stranger)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "awaiting_confirm")

    def test_stranger_cannot_cancel_someone_elses_job(self):
        self.client.force_login(self.stranger)
        self.client.post(f"/import/{self.job.pk}/cancel/")
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "awaiting_confirm")

    def test_owner_can_commit(self):
        self._commit(self.owner)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "done")

    def test_staff_can_commit_for_others(self):
        self._commit(self.staff)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "done")

    def test_missing_job_reports_error(self):
        self.client.force_login(self.owner)
        response = self.client.post("/import/999999/commit/", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "导入批次不存在")
