import uuid

from django.contrib.auth import get_permission_codename
from django.db import models
from django.urls import reverse

from nifty_attachments.models import AbstractAttachment, DefaultAttachmentPermissions


class GizmoModel(models.Model):
    title = models.CharField(max_length=100)

    class Meta:
        db_table = "testapp_gizmo"

    def get_absolute_url(self):
        return reverse("gizmo:detail", args=(self.pk,))


class GizmoAttachment(AbstractAttachment.factory(GizmoModel, url_namespace="gizmo:attachments")):
    pass


class ModelWithUuidPk(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=100)

    class Meta:
        db_table = "testapp_uuid4_model"

    def get_absolute_url(self):
        return "/"


class UuidPermissions(DefaultAttachmentPermissions):

    def can_add_attachments(self, user, related_to) -> bool:
        """Return True iff the user can upload new attachments to the given related object"""
        code = get_permission_codename("change", ModelWithUuidPk._meta)
        return user.has_perm(f"attachments_testapp.{code}") and super().can_add_attachments(user, related_to)


base_attachment_model = AbstractAttachment.factory(
    related_model=ModelWithUuidPk,
    related_name="uuid_attachments",
    permissions_class=UuidPermissions,
)


class UuidAttachment(base_attachment_model):
    pass
