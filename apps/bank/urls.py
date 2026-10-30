from django.urls import path

from apps.bank import views

app_name = "bank"

urlpatterns = [
    path("", views.QuestionListView.as_view(), name="question-list"),
    path("create/", views.QuestionCreateView.as_view(), name="question-create"),
    path("<int:pk>/", views.QuestionDetailView.as_view(), name="question-detail"),
    path("<int:pk>/edit/", views.QuestionUpdateView.as_view(), name="question-update"),
    path("<int:pk>/delete/", views.QuestionDeleteView.as_view(), name="question-delete"),
]
