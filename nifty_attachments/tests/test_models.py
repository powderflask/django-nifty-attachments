import pytest

from ..utils import get_permission_for_model
from .factories import GizmoAttachmentFactory, UuidAttachmentFactory
from .fixtures import add_perm


@pytest.mark.django_db
def test_attachment_model(attachment_model, attachment):
    instances = attachment_model.objects.all()
    assert instances.count() == 1
    assert isinstance(instances.first().related_object, attachment_model.get_related_model())


@pytest.mark.django_db
def test_attachment_owner_permissions(attachment_model, attachment):
    instance = attachment_model.objects.first()
    assert attachment_model.can_view_attachments(instance.owner, instance.related_object) is True
    assert instance.can_change_attachment(instance.owner) is False
    assert instance.can_delete_attachment(instance.owner) is False
    add_perm(instance.owner, attachment_model, "change")
    add_perm(instance.owner, attachment_model, "delete")
    u = type(instance.owner).objects.get(pk=instance.owner.pk)  # bust django permissions cache
    assert instance.can_change_attachment(u) is True
    assert instance.can_delete_attachment(u) is True


@pytest.mark.parametrize("attachment_factory", [GizmoAttachmentFactory], indirect=True)
@pytest.mark.django_db
def test_attachment_default_permissions(attachment_model, attachment):
    """Custom permission requires change perm on the related object."""
    instance = attachment_model.objects.first()
    user = instance.owner
    assert attachment_model.can_add_attachments(user, instance.related_object) is True


@pytest.mark.parametrize("attachment_factory", [UuidAttachmentFactory], indirect=True)
@pytest.mark.django_db
def test_attachment_custom_permissions(attachment_model, attachment):
    """Custom permission requires change perm on the related object."""
    instance = attachment_model.objects.first()
    user = instance.owner
    assert attachment_model.can_add_attachments(user, instance.related_object) is False
    perm = get_permission_for_model(attachment_model, "change")
    user.user_permissions.add(perm)


@pytest.mark.django_db
def test_attachment_other_permissions(attachment_model, attachment, get_user_factory):
    instance = attachment_model.objects.first()
    other_user = get_user_factory(perms=("view", "add", "change", "delete"))
    assert attachment_model.can_view_attachments(other_user, instance.related_object) is True
    assert instance.can_change_attachment(other_user) is False
    assert instance.can_delete_attachment(other_user) is False
    add_perm(other_user, attachment_model, "edit_any")
    u = type(other_user).objects.get(pk=other_user.pk)  # bust django permissions cache
    assert instance.can_change_attachment(u) is True
    assert instance.can_delete_attachment(u) is True
