"""用户后台：把「有效」摆到列表上，并提供批量启用 / 停用。

自助注册只提交申请（`is_active=False`），管理员在这里勾选一行点个动作就能放行，
不用逐个点进详情页改表单。
"""

from __future__ import annotations

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

# django.contrib.auth 已经把 User 注册过一次，这里先撤掉再换成自己的
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:  # pragma: no cover - 正常加载顺序下不会走到
    pass


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "is_active", "is_staff", "is_superuser", "last_login")
    # is_active=False 排在前面：待启用的注册申请不会沉到列表底部
    ordering = ("is_active", "username")
    actions = ("activate_users", "deactivate_users")

    @admin.action(description="启用所选用户（允许登录）")
    def activate_users(self, request, queryset):
        updated = queryset.filter(is_active=False).update(is_active=True)
        self.message_user(request, f"已启用 {updated} 个账号，现在可以登录了", messages.SUCCESS)

    @admin.action(description="停用所选用户（禁止登录）")
    def deactivate_users(self, request, queryset):
        # 排除自己：否则一不小心就把当前管理员锁在门外
        updated = (
            queryset.exclude(pk=request.user.pk).filter(is_active=True).update(is_active=False)
        )
        self.message_user(request, f"已停用 {updated} 个账号", messages.WARNING)
