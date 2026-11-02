"""自助注册（待审批）与登录流程测试。"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

VALID = {
    "username": "teacher01",
    "email": "teacher01@example.com",
    "password1": "Zx9-luomiao-2026",
    "password2": "Zx9-luomiao-2026",
}


class RegisterTests(TestCase):
    def test_anonymous_can_open_page(self):
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "注册账号")

    def test_register_creates_inactive_account(self):
        response = self.client.post(reverse("register"), VALID)
        self.assertRedirects(response, reverse("login"))

        user = User.objects.get(username="teacher01")
        self.assertEqual(user.email, "teacher01@example.com")
        # 自助注册只提交申请：既没启用、也没后台权限
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_staff)
        # 注册完不会自动登录
        self.assertEqual(self.client.get(reverse("paper:list")).status_code, 302)

    def test_inactive_account_is_told_to_wait_for_approval(self):
        self.client.post(reverse("register"), VALID)
        response = self.client.post(
            reverse("login"),
            {"username": "teacher01", "password": VALID["password1"]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "管理员启用")
        self.assertEqual(self.client.get(reverse("paper:list")).status_code, 302)

    def test_activated_account_can_login(self):
        self.client.post(reverse("register"), VALID)
        User.objects.filter(username="teacher01").update(is_active=True)

        response = self.client.post(
            reverse("login"),
            {"username": "teacher01", "password": VALID["password1"]},
        )
        self.assertRedirects(response, reverse("paper:list"))
        self.assertEqual(self.client.get(reverse("paper:list")).status_code, 200)

    def test_staff_activation_keeps_self_registered_out_of_admin(self):
        self.client.post(reverse("register"), VALID)
        User.objects.filter(username="teacher01").update(is_active=True)
        self.client.login(username="teacher01", password=VALID["password1"])

        self.assertEqual(self.client.get("/admin/").status_code, 302)

    def test_password_mismatch_rejected(self):
        response = self.client.post(reverse("register"), {**VALID, "password2": "other-pass-2026"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="teacher01").exists())

    def test_duplicate_username_rejected(self):
        User.objects.create_user("teacher01", password="Zx9-luomiao-2026")
        response = self.client.post(reverse("register"), VALID)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(username="teacher01").count(), 1)

    def test_duplicate_email_rejected(self):
        User.objects.create_user("other", email="teacher01@example.com", password="Zx9-luomiao-2026")
        response = self.client.post(reverse("register"), VALID)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="teacher01").exists())

    def test_cannot_grant_self_staff_by_post(self):
        data = {**VALID, "is_staff": "1", "is_superuser": "1", "is_active": "1"}
        self.assertRedirects(self.client.post(reverse("register"), data), reverse("login"))
        user = User.objects.get(username="teacher01")
        self.assertFalse(user.is_staff or user.is_superuser or user.is_active)

    def test_logged_in_user_is_redirected_away(self):
        User.objects.create_user("someone", password="Zx9-luomiao-2026")
        self.client.login(username="someone", password="Zx9-luomiao-2026")
        self.assertRedirects(self.client.get(reverse("register")), reverse("paper:list"))

    @override_settings(ALLOW_SELF_REGISTRATION=False)
    def test_can_be_closed_by_setting(self):
        response = self.client.post(reverse("register"), VALID, follow=True)
        self.assertRedirects(response, reverse("login"))
        self.assertFalse(User.objects.filter(username="teacher01").exists())


class AdminActivationTests(TestCase):
    """管理员在后台启用注册申请（批量动作）。"""

    PASSWORD = "Zx9-luomiao-2026"

    def setUp(self):
        self.staff = User.objects.create_superuser("root01", "root01@example.com", self.PASSWORD)
        self.pending = User.objects.create_user(
            "pending01", "pending01@example.com", self.PASSWORD, is_active=False
        )
        self.client.force_login(self.staff)

    def _run_action(self, action, *users):
        return self.client.post(
            reverse("admin:auth_user_changelist"),
            {
                "action": action,
                "_selected_action": [str(user.pk) for user in users],
                "index": "0",
                "select_across": "0",
            },
            follow=True,
        )

    def test_changelist_shows_is_active_and_actions(self):
        response = self.client.get(reverse("admin:auth_user_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "启用所选用户")
        # 未启用的排在前面，注册申请一眼就能看到
        self.assertEqual(response.context["cl"].result_list[0].username, "pending01")

    def test_activate_action_enables_selected_user(self):
        response = self._run_action("activate_users", self.pending)
        self.pending.refresh_from_db()
        self.assertTrue(self.pending.is_active)
        # 动作成功后 messages 会被这次 follow 的响应消费掉，所以断言在这一步
        self.assertContains(response, "已启用 1 个账号")

    def test_activate_action_does_not_touch_staff_flags(self):
        self._run_action("activate_users", self.pending)
        self.pending.refresh_from_db()
        self.assertFalse(self.pending.is_staff or self.pending.is_superuser)

    def test_cannot_deactivate_yourself(self):
        self._run_action("deactivate_users", self.staff, self.pending)
        self.staff.refresh_from_db()
        self.pending.refresh_from_db()
        # 自己没被停用，其他人照常停用
        self.assertTrue(self.staff.is_active)
        self.assertFalse(self.pending.is_active)

    def test_activated_user_can_login(self):
        self._run_action("activate_users", self.pending)
        self.client.logout()
        response = self.client.post(
            reverse("login"), {"username": "pending01", "password": self.PASSWORD}
        )
        self.assertRedirects(response, reverse("paper:list"))
