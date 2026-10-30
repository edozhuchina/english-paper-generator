from django.urls import path

from apps.prints import views

app_name = "print"

urlpatterns = [
    path("paper/<int:pk>/", views.paper_print, name="paper"),
    path("paper/<int:pk>/answers/", views.answer_print, name="answers"),
]
