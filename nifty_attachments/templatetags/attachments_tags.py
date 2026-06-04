from typing import Any

from django.contrib.auth import get_user_model
from django.db import models
from django.template import Library

from nifty_attachments.forms import AttachmentUploadForm
from nifty_attachments.models import AbstractAttachment
from nifty_attachments.utils import (
    get_attachment_model_for_relation_name,
    get_attachment_model_from_related_object,
)

User = get_user_model()
register = Library()


@register.inclusion_tag("nifty/attachments/add.html", takes_context=True)
def attachment_form(
    context: dict[str, Any],
    related_obj: models.Model,
    relation_name: str = None,
    **kwargs,
):
    """
    Renders "upload attachment" form for a specific model instance iff user has permission.
    Usage:

        {% attachment_form obj %}
    """
    if not isinstance(related_obj, models.Model):
        return {"form": None}

    attachment_model = get_attachment_model_for_relation_name(
        related_obj, relation_name
    )
    if not attachment_model:
        return {"form": None}

    user = context.get("user")

    if (
        user
        and user.is_authenticated
        and attachment_model.can_add_attachments(user, related_obj)
    ):
        return {
            "form": AttachmentUploadForm(),
            "action_url": attachment_model.get_upload_url_for_obj(related_obj),
            "next": kwargs.get("next", context.request.build_absolute_uri()),
        }
    return {"form": None}


@register.inclusion_tag(
    "nifty/attachments/include/delete_link.html", takes_context=True
)
def attachment_delete_link(context, attachment: AbstractAttachment, **kwargs):
    """Renders delete link for a specific attachment instance."""
    if not isinstance(attachment, models.Model) or not attachment.can_delete_attachment(
        context.get("user")
    ):
        return {"delete_url": None}

    return {
        "next": kwargs.get("next", context.request.build_absolute_uri()),
        "delete_url": attachment.get_delete_url(),
    }


@register.simple_tag
def attachments_count(related_obj: models.Model, relation_name: str = None):
    """Returns count for an instance's attachments. Default relation: 'attachment_set' unless otherwise specified"""
    if related_obj is None:
        return 0
    queryset = attachment_set(related_obj, relation_name)
    return queryset.count() if hasattr(queryset, "count") else len(queryset)


@register.simple_tag
def get_attachments_for(related_obj: models.Model, relation_name: str = None):
    """Usage: {% get_attachments_for obj "uuid_attachments" as var %}"""
    return attachment_set(related_obj, relation_name)


@register.filter
def attachment_set(related_obj: models.Model, relation_name: str = None):
    """
    Returns a QuerySet of attachments.
    Default relation_name: 'attachment_set'
    Usage:
        {% for attachment in obj|attachment_set %}
        {% for attachment in obj|attachment_set:'attached_notes' %}
    """
    if related_obj is None:
        return []

    attachment_model = get_attachment_model_for_relation_name(
        related_obj, relation_name
    )
    if attachment_model:
        return attachment_model.objects.filter(related_object=related_obj)
    else:
        return []


@register.filter
def attachment_upload_url(related_obj: models.Model, relation_name=None):
    """
    Returns the "create" attachment endpoint url for the given related object.

    Usage:

        href="{{ obj|attachment_upload_url }}"
    """
    attachment_model = get_attachment_model_for_relation_name(
        related_obj, relation_name
    )
    if not attachment_model:
        return "/400"
    return attachment_model.get_upload_url_for_obj(related_obj)


@register.filter
def can_add_attachment(user: User, related_obj: str | models.Model) -> bool:
    """
    Return True iff the user can create an attachment for the related_obj
    Usage:
    # uses default attachment relation: attachment_set
    {% if request.user|can_add_attachment:object %}
    # specifies attachment relation to model from class using dotted-path
    {% if request.user|can_add_attachment:'app_label.MyModel.related_name' %}
    """
    if not user or not user.is_authenticated or related_obj is None:
        return False

    attachment_model = get_attachment_model_from_related_object(related_obj)
    if (
        not attachment_model
    ):  # if this statement were truthy, an error would have already been raised
        return False
    instance = related_obj if isinstance(related_obj, models.Model) else None
    return attachment_model.can_add_attachments(user, instance)


@register.filter
def can_change_attachment(user: User, attachment: AbstractAttachment):
    """Return True iff the user can edit the existing attachment"""
    if not user or not attachment or isinstance(attachment, str):
        return False
    return attachment.can_change_attachment(user)


@register.filter
def can_delete_attachment(user: User, attachment: AbstractAttachment):
    """Return True iff the user can delete the attachment"""
    if not user or not attachment or isinstance(attachment, str):
        return False
    return attachment.can_delete_attachment(user)
