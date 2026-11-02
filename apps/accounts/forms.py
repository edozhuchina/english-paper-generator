"""自助注册与登录表单。"""

from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class SignUpForm(UserCreationForm):
    """只开放用户名、邮箱与密码。

    注册出来的账号是**待启用**状态：没有 is_staff（进不了后台），
    也没有 is_active（登录直接被拒），必须由管理员在后台勾上"有效"才能使用。
    """

    email = forms.EmailField(label="邮箱（选填）", required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self) -> str:
        email = (self.cleaned_data.get("email") or "").strip()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("这个邮箱已经注册过账号")
        return email

    def save(self, commit: bool = True):
        user = super().save(commit=False)
        user.is_active = False
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    """区分"密码对但账号还没启用"，否则用户只会看到一句"用户名或密码不正确"。"""

    error_messages = {
        **AuthenticationForm.error_messages,
        "inactive": "账号已注册，但还需要管理员启用后才能登录",
    }

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if username and password:
            user = User.objects.filter(username=username).first()
            # ModelBackend 对未启用账号一律返回 None，这里提前给出可读的原因
            if user is not None and not user.is_active and user.check_password(password):
                raise ValidationError(self.error_messages["inactive"], code="inactive")
        return super().clean()
