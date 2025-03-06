from django.contrib import admin
from django.urls import include, path
from django.views.generic import DetailView, TemplateView

from .models import GizmoModel, ModelWithUuidPk

admin.autodiscover()


gizmo_patters = [
    path("attachments/", include("nifty_attachments.urls"), kwargs=dict(model="attachments_testapp.GizmoAttachment")),
    path(
        "<int:pk>/",
        DetailView.as_view(
            template_name="testapp_detail.html",
            queryset=GizmoModel.objects.all(),
        ),
        name="detail",
    ),
]


urlpatterns = [
    path("", TemplateView.as_view(template_name="testapp_home.html"), name="home"),  # placeholder
    path("auth/", include("django.contrib.auth.urls")),  # for redirect - not needed.
    path("admin/", admin.site.urls),
    # use nested namespacing (pass namespace, gizmo:attachments, to Attachment model factory)
    path("gizmo/", include((gizmo_patters, "gizmo"))),
    # or supply an instance namespace (and use django url namespace handler)
    path(
        "uuid4/attachments/",
        include("nifty_attachments.urls", namespace="uuid4"),
        kwargs=dict(model="attachments_testapp.UuidAttachment"),
    ),
    path(
        "testapp/uuid/<uuid:pk>/",
        DetailView.as_view(
            template_name="testapp_detail.html",
            queryset=ModelWithUuidPk.objects.all(),
        ),
        name="uuid4-detail",
    ),
]
