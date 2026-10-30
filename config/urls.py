from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

admin.site.site_header = "小学英语出卷系统"
admin.site.site_title = "小学英语出卷系统"
admin.site.index_title = "后台管理"

urlpatterns = [
    path("admin/", admin.site.urls),
    # 全站登录由 LoginRequiredMiddleware 负责，这里只提供登录 / 退出两个入口
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", RedirectView.as_view(pattern_name="paper:list"), name="home"),
    path("bank/", include("apps.bank.urls", namespace="bank")),
    path("papers/", include("apps.paper.urls", namespace="paper")),
    path("import/", include("apps.importer.urls", namespace="import")),
    path("print/", include("apps.prints.urls", namespace="print")),
]
