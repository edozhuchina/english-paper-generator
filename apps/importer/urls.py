from django.urls import path

from apps.importer import views

app_name = "import"

urlpatterns = [
    path("", views.ImportHomeView.as_view(), name="home"),
    path("template/", views.TemplateDownloadView.as_view(), name="template"),
    path("upload/", views.UploadView.as_view(), name="upload"),
    path("<int:job_id>/commit/", views.CommitView.as_view(), name="commit"),
    path("<int:job_id>/cancel/", views.CancelView.as_view(), name="cancel"),
]
