"""用户自助注册。

登录保护由 LoginRequiredMiddleware 全站接管，因此注册页必须显式标注
login_not_required，否则未登录用户会被拦回登录页、永远注册不了。

注册只负责"提交申请"：新账号是停用状态，管理员在后台勾上「有效」后才能登录。
"""

from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.shortcuts import redirect, render

from apps.accounts.forms import SignUpForm


@login_not_required
def register(request):
    """注册成功后不自动登录，退回登录页并提示等待启用。"""
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    if not settings.ALLOW_SELF_REGISTRATION:
        messages.error(request, "自助注册已关闭，请联系管理员开通账号")
        return redirect("login")

    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.info(
            request,
            f"账号「{user.username}」已提交，管理员启用后即可登录（后台 → 用户 → 勾选「有效」）",
        )
        return redirect("login")

    return render(request, "registration/register.html", {"form": form})
