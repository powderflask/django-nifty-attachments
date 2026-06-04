from unittest.mock import MagicMock

import pytest

from nifty_attachments.utils import get_attachment_model_from_related_object

from .factories import GizmoAttachmentFactory, UuidAttachmentFactory
from .fixtures import add_perm


@pytest.mark.django_db
def test_attachment_resolution_by_string(attachment_model, attachment):
    instance = attachment.related_object
    # Dynamically find the related_name from the FK field we injected in factory
    relation_name = attachment_model._meta.get_field(
        "related_object"
    ).remote_field.related_name

    app_label = instance._meta.app_label
    model_name = instance._meta.model_name
    path = f"{app_label}.{model_name}.{relation_name}"

    resolved_model = get_attachment_model_from_related_object(path)
    assert resolved_model == attachment_model


@pytest.mark.django_db
def test_attachment_model(attachment_model, attachment):
    instances = attachment_model.objects.all()
    assert instances.count() == 1
    assert isinstance(
        instances.first().related_object, attachment_model.get_related_model()
    )


@pytest.mark.django_db
def test_attachment_owner_permissions(attachment_model, attachment):
    instance = attachment_model.objects.first()

    assert (
        attachment_model.can_view_attachments(instance.owner, instance.related_object)
        is True
    )
    assert attachment_model.can_view_attachments(instance.owner, None) is True

    assert instance.can_change_attachment(instance.owner) is False
    assert instance.can_delete_attachment(instance.owner) is False

    add_perm(instance.owner, attachment_model, "change")
    add_perm(instance.owner, attachment_model, "delete")

    u = type(instance.owner).objects.get(pk=instance.owner.pk)
    assert instance.can_change_attachment(u) is True
    assert instance.can_delete_attachment(u) is True


@pytest.mark.parametrize("attachment_factory", [GizmoAttachmentFactory], indirect=True)
@pytest.mark.django_db
def test_attachment_default_permissions(attachment_model, attachment):
    instance = attachment_model.objects.first()
    user = instance.owner

    # NEW: Verify add works with both instance and None
    assert attachment_model.can_add_attachments(user, instance.related_object) is True
    assert attachment_model.can_add_attachments(user, None) is True


@pytest.mark.parametrize("attachment_factory", [UuidAttachmentFactory], indirect=True)
@pytest.mark.django_db
def test_attachment_custom_permissions(attachment_model, attachment):
    """
    UuidPermissions requires:
    1. 'add' permission on the parent (ModelWithUuidPk)
    2. 'add' permission on the attachment itself (via DefaultAttachmentPermissions)
    """
    instance = attachment_model.objects.first()
    user = instance.owner
    parent_model = attachment_model.get_related_model()  # This is ModelWithUuidPk

    # Initially should be False
    assert attachment_model.can_add_attachments(user, None) is False

    # Add Parent Permission (add_modelwithuuidpk)
    add_perm(user, parent_model, "add")

    # Add Attachment Permission (add_uuidattachment)
    add_perm(user, attachment_model, "add")

    # Refresh user to bust the permission cache
    u = type(user).objects.get(pk=user.pk)

    assert attachment_model.can_add_attachments(u, None) is True


@pytest.mark.django_db
def test_attachment_other_permissions(attachment_model, attachment, get_user_factory):
    instance = attachment_model.objects.first()
    # Ensure they have basic CRUD perms for the model
    other_user = get_user_factory(perms=("view", "add", "change", "delete"))

    # Class-level view/add should pass
    assert attachment_model.can_view_attachments(other_user, None) is True

    # Change/Delete on a specific instance should fail for non-owners without edit_any
    assert instance.can_change_attachment(other_user) is False
    assert instance.can_delete_attachment(other_user) is False

    add_perm(other_user, attachment_model, "edit_any")
    u = type(other_user).objects.get(pk=other_user.pk)
    assert instance.can_change_attachment(u) is True
    assert instance.can_delete_attachment(u) is True


@pytest.mark.django_db
def test_get_related_absolute_url_fallback(attachment):
    attachment.related_object.get_absolute_url = MagicMock(
        side_effect=AttributeError("Simulated missing method")
    )
    assert attachment.get_related_absolute_url() is None
