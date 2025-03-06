"""
Attachments URL Configuration.

Each view MUST be passed kwarg: model=ConcreteAttachmentModel
either as a model class or an "app_label.ModelName" string

To configure urls for concrete attachments:

path('my-model/attachments/',
     include('attachments.urls', namespace='my-attachments'),
     dict(model='myapp.ConcreteAttachmentModel'))

namespace is optional if the including urls config is already namespaced and defines one attachments app.
"""

from django.urls import path

from . import views

app_name = "attachments"

urlpatterns = [
    path("add-for/<slug:pk>/", views.add_attachment, name="create"),
    path("download-for/<slug:pk>/<int:attachment_pk>/", views.download_attachment, name="download"),
    path("update-for/<slug:pk>/<int:attachment_pk>/", views.update_attachment, name="update"),
    path("delete-for/<slug:pk>/<int:attachment_pk>/", views.delete_attachment, name="delete"),
    path("list-for/<slug:pk>/", views.list_attachments, name="list"),
]
