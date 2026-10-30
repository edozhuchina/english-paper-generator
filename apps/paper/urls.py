from django.urls import path

from apps.paper import views

app_name = "paper"

urlpatterns = [
    path("", views.PaperListView.as_view(), name="list"),
    path("create/", views.PaperCreateView.as_view(), name="create"),
    path("<int:pk>/", views.PaperBuilderView.as_view(), name="builder"),
    path("<int:pk>/delete/", views.PaperDeleteView.as_view(), name="delete"),
    path("<int:pk>/export/docx/", views.export_docx, name="export-docx"),

    path("<int:pk>/items/add/", views.add_questions, name="item-add"),
    path("<int:pk>/items/<int:item_id>/remove/", views.remove_question, name="item-remove"),
    path("<int:pk>/items/<int:item_id>/update/", views.update_item, name="item-update"),
    path("<int:pk>/items/reorder/", views.reorder_items, name="item-reorder"),

    path("<int:pk>/sections/create/", views.create_section, name="section-create"),
    path("<int:pk>/sections/<int:section_id>/update/", views.update_section, name="section-update"),
    path("<int:pk>/sections/<int:section_id>/delete/", views.delete_section, name="section-delete"),
]
