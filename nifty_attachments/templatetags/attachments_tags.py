from django.db import models
from django.template import Library

from ..forms import AttachmentUploadForm
from ..models import AbstractAttachment, User
from ..utils import get_attachment_model_from_related_object

register = Library()


@register.inclusion_tag("nifty/attachments/add.html", takes_context=True)
def attachment_form(context, related_obj: models.Model, **kwargs):
    """
    Renders "upload attachment" form for the related_object iff the user has permission.

    Usage:

        {% attachment_form obj %}
    """
    attachment_model = get_attachment_model_from_related_object(related_obj)
    if attachment_model.can_add_attachments(context["user"], related_obj):
        return {
            "form": AttachmentUploadForm(),
            "action_url": attachment_model.get_upload_url_for_obj(related_obj),
            "next": kwargs.get("next", context.request.build_absolute_uri()),
        }
    else:
        return {"form": None}


def get_delete_link_context(context, attachment: AbstractAttachment, **kwargs):
    """Return context to render a delete link."""
    if attachment.can_delete_attachment(context["user"]):
        return {
            "next": kwargs.get("next", context.request.build_absolute_uri()),
            "delete_url": attachment.get_delete_url(),
        }
    return {"delete_url": None}


@register.inclusion_tag("nifty/attachments/include/delete_link.html", takes_context=True)
def attachment_delete_link(context, attachment: AbstractAttachment, **kwargs):
    """
    Renders a html link to the delete view of the given attachment iff the user has permission.

    Usage:

            {% attachment_delete_link attachment %}
    """
    return get_delete_link_context(context, attachment, **kwargs)


@register.inclusion_tag("nifty/attachments/htmx/delete_link.html", takes_context=True)
def attachment_hx_delete_link(context, attachment: AbstractAttachment, **kwargs):
    """
    Renders a html link to the delete view of the given attachment iff the user has permission.

    Usage:

            {% attachment_delete_link attachment %}
    """
    return get_delete_link_context(context, attachment, **kwargs)


@register.simple_tag
def attachments_count(related_obj: models.Model):
    """
    Resolves to the number of attachments that are attached to a related object.

    Usage:

        {% attachments_count obj %}
    """
    attachment_model = get_attachment_model_from_related_object(related_obj)
    return attachment_model.objects.filter(related_object=related_obj).count()


@register.simple_tag
def get_attachments_for(related_obj: models.Model):
    """
    Resolves to an iterable of attachments that are attached to a related object.

    You can specify the variable name in the context the attachments are stored using the `as` argument.

    Usage:

        {% get_attachments_for obj as "my_attachments" %}
    """
    attachment_model = get_attachment_model_from_related_object(related_obj)
    return attachment_model.objects.filter(related_object=related_obj)


@register.filter
def attachment_set(related_obj: models.Model):
    """
    Returns an iterable of attachments that are attached to a related object.

    Usage:

        {% for attachment in obj|attachment_set %}
    """
    return get_attachments_for(related_obj)


@register.filter
def attachment_upload_url(related_obj: models.Model):
    """
    Returns the "create" attachment endpoint url for the given related object.

    Usage:

        href="{{ obj|attachment_upload_url }}"
    """
    attachment_model = get_attachment_model_from_related_object(related_obj)
    return attachment_model.get_upload_url_for_obj(related_obj)


# Permission filters


@register.filter
def can_add_attachment(user: User, related_obj: models.Model) -> bool:
    """Return True iff the user can edit the existing attachment"""
    attachment_model = get_attachment_model_from_related_object(related_obj)
    return attachment_model.can_add_attachments(user, related_obj)


@register.filter
def can_change_attachment(user: User, attachment: AbstractAttachment) -> bool:
    """Return True iff the user can edit the existing attachment"""
    return attachment.can_change_attachment(user)


@register.filter
def can_delete_attachment(user: User, attachment: AbstractAttachment) -> bool:
    """Return True iff the user can delete the attachment"""
    return attachment.can_delete_attachment(user)
