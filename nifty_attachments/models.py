from __future__ import annotations

from typing import Protocol

from django.contrib.auth import get_user_model
from django.core.files import File
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from nifty_attachments.utils import class_service, get_model_class, get_perm_name_for_model

User = get_user_model()


class AttachmentPermissions(Protocol):
    """
    Interface for injectable attachment permissions

    Client code can inject custom permissions instance on concreate Attachment model.
    """

    def __init__(self, attachment_model: type[AbstractAttachment]):
        """Initialize permissions for the given concrete attachment_model."""
        ...

    def can_add_attachments(self, user: User, related_to: models.Model) -> bool:
        """Return True iff the user can upload new attachments for the related object"""
        ...

    def can_view_attachments(self, user: User, related_to: models.Model) -> bool:
        """Return True iff the user can view attachments for the related object"""
        ...

    def can_change_attachment(self, user: User, attachment: AbstractAttachment) -> bool:
        """Return True iff the user can edit the existing attachment"""
        ...

    def can_delete_attachment(self, user: User, attachment: AbstractAttachment) -> bool:
        """Return True iff the user can delete the attachment"""
        ...


class DefaultAttachmentPermissions:
    """Default attachment permissions based on standard Model permissions for concrete model"""

    def __init__(self, attachment_model: type[AbstractAttachment]):
        """Base permissions on standard django Model permissions for given concrete attachment_model."""
        self.attachment_model = attachment_model

    def has_perm(self, user: User, action: str) -> bool:
        """shortcut to check permission based on action name"""
        return user.has_perm(get_perm_name_for_model(self.attachment_model, action))

    def can_add_attachments(self, user: User, related_to: models.Model) -> bool:
        """Return True iff the user can upload new attachments to given related object"""
        return self.has_perm(user, "add")

    def can_view_attachments(self, user: User, related_to: models.Model) -> bool:
        """Return True iff the user can view attachments for given related object"""
        return self.has_perm(user, "view")

    def can_change_attachment(self, user: User, attachment: AbstractAttachment) -> bool:
        """Return True iff the user can edit the existing attachment"""
        has_base_perm = self.has_perm(user, "change")
        return has_base_perm if user.pk == attachment.owner_id else has_base_perm and self.has_perm(user, "edit_any")

    def can_delete_attachment(self, user: User, attachment: AbstractAttachment) -> bool:
        """Return True iff the user can delete the attachment"""
        has_base_perm = self.has_perm(user, "delete")
        return has_base_perm if user.pk == attachment.owner_id else has_base_perm and self.has_perm(user, "edit_any")


def create_attachment(
    cls: type[AbstractAttachment],
    user: User,
    file: File,
    related_object: models.Model,
    **kwargs,
):
    """Create a new Attachment object of given class with kwargs and return it"""
    defaults = dict(
        name=getattr(file, "name", "no-name-file"),
        label=getattr(file, "name", ""),
        size=getattr(file, "size", -1),
        content_type=getattr(file, "content_type", "text/plain"),
    )
    attrs = {**defaults, **kwargs}
    attachment = cls(
        related_object=related_object,
        owner=user,
        data=file.read(),
        **attrs,
    )
    attachment.save()
    return attachment


class AbstractAttachment(models.Model):
    """Base Attachment Model - clients extend this model to create a Concrete implementation / DB table.

    Requires a FK to some object the attachment is attached to!
    Use `factory` classmethod to inject the related model and custom permissions dependencies.
    """

    owner = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")
    label = models.CharField(
        max_length=250,
        verbose_name=_("Document Label"),
        help_text=_("Title of this document, displayed as download link text."),
    )
    description = models.TextField(
        blank=True, default="", help_text=_("Optional description of file contents, displayed with download links.")
    )
    timestamp = models.DateTimeField(default=timezone.now, editable=False, verbose_name=_("Uploaded on"))
    name = models.CharField(max_length=255, help_text=_("Original filename of the Uploaded File."))
    size = models.IntegerField(help_text=_("Size, in bytes, of the original Uploaded File."))
    content_type = models.CharField(
        max_length=150, help_text=_("The content-type header uploaded with the original Uploaded File.")
    )
    data = models.BinaryField()

    related_object = None  # a FK injected when concrete attachment model is defined.
    _related_model = None  # shortcut to model class for related_object, injected
    url_namespace = "attachments"  # alternate namespace for concreate attachment urls, injected
    permissions = None  # a AttachmentPermissions instance, injected.

    class Meta:
        abstract = True
        ordering = ["-timestamp"]
        default_permissions = ("add", "change", "delete", "view", "edit_any")

    @classmethod
    def factory(
        cls,
        related_model: str | type[models.Model],
        related_name: str = "attachment_set",
        permissions_class: type[AttachmentPermissions] = DefaultAttachmentPermissions,
        url_namespace: str = "attachments",
        **kwargs,
    ) -> type[AbstractAttachment]:
        """Return an abstract Attachment Model class configured with a FK to related_model."""
        kwargs.setdefault("on_delete", models.CASCADE)
        _url_namespace = url_namespace

        class BaseAttachmentModel(cls):
            _related_model = related_model
            url_namespace = _url_namespace

            related_object = models.ForeignKey(related_model, related_name=related_name, **kwargs)

            permissions = class_service(permissions_class)()

            class Meta(cls.Meta):
                abstract = True

        return BaseAttachmentModel

    def __str__(self):
        return f"{self.label} – {self.description}" if self.description else self.label

    @property
    def info(self):
        return 'File: "{}" [{} kB], was uploaded on {:%Y-%m-%d}, by {}'.format(
            self.name, self.size // 1000, self.timestamp, self.owner
        )

    @classmethod
    def create(cls, user: User, file: File, related_object: models.Model, **kwargs):
        """Create and return an instance from a post request - assumes all data has been cleaned and validated"""
        return create_attachment(cls, user, file, related_object, **kwargs)

    @classmethod
    def get_related_model(cls) -> type[models.Model]:
        return get_model_class(cls._related_model)

    @classmethod
    def get_url_namespace(cls) -> str:
        return cls.url_namespace

    def get_related_absolute_url(self) -> str | None:
        """Return a url for the related_object to this attachment"""
        try:
            return self.related_object.get_absolute_url()
        except AttributeError:
            return None

    @classmethod
    def get_upload_url_for_obj(cls, related_object: models.Model):
        return reverse(f"{cls.get_url_namespace()}:create", args=(related_object.pk,))

    def get_download_url(self):
        return reverse(f"{self.get_url_namespace()}:download", args=(self.related_object_id, self.pk))  # noqa

    def get_delete_url(self):
        return reverse(f"{self.get_url_namespace()}:delete", args=(self.related_object_id, self.pk))  # noqa

    def get_update_url(self):
        return reverse(f"{self.get_url_namespace()}:update", args=(self.related_object_id, self.pk))  # noqa

    # Simple API for permissions logic.  Prefer to override permissions rather than these methods

    @classmethod
    def can_add_attachments(cls, user: User, related_object: models.Model) -> bool:
        """Return True iff the user can upload a new instance of cls"""
        return cls.permissions.can_add_attachments(user, related_object)

    @classmethod
    def can_view_attachments(cls, user: User, related_object: models.Model) -> bool:
        """Return True iff the user can view the attachment"""
        return cls.permissions.can_view_attachments(user, related_object)

    def can_change_attachment(self, user: User) -> bool:
        """Return True iff the user can edit the existing attachment"""
        return self.permissions.can_change_attachment(user, self)

    def can_delete_attachment(self, user: User) -> bool:
        """Return True iff the user can delete the attachment"""
        return self.permissions.can_delete_attachment(user, self)
