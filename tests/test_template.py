import pytest
from django.urls import reverse

from .factories import GizmoAttachmentFactory, UuidAttachmentFactory
from .fixtures import add_perm
from .testapp.models import GizmoModel


def get_detail_url(obj):
    url_name = "gizmo:detail" if isinstance(obj, GizmoModel) else "uuid4-detail"
    return reverse(url_name, kwargs={"pk": obj.pk})


@pytest.mark.django_db
def test_uploaded_attachment_urls_are_listed(client, attachment_model, attachment):
    client.force_login(attachment.owner)
    obj = attachment.related_object
    response = client.get(get_detail_url(obj))
    attachment = attachment_model.objects.filter(related_object=obj).first()
    assert "Object has 1 attachments" in str(response.content)
    assert attachment.get_download_url() in str(response.content)


@pytest.mark.django_db
def test_attachment_count_is_listed(client, attachment_model, attachment):
    client.force_login(attachment.owner)
    obj = attachment.related_object
    response = client.get(get_detail_url(obj))
    assert "Object has 1 attachments" in str(response.content)


@pytest.mark.parametrize("attachment_factory", [GizmoAttachmentFactory], indirect=True)
@pytest.mark.django_db
def test_upload_form_is_listed_with_add_permission(client, attachment_model, attachment):
    client.force_login(attachment.owner)
    obj = attachment.related_object
    response = client.get(get_detail_url(obj))
    assert "<form" in str(response.content)
    assert f'action="{attachment.get_upload_url_for_obj(obj)}"' in str(response.content)


@pytest.mark.parametrize("attachment_factory", [UuidAttachmentFactory], indirect=True)
@pytest.mark.django_db
def test_upload_form_is_not_listed_without_add_permission(client, attachment_model, attachment):
    client.force_login(attachment.owner)
    obj = attachment.related_object
    response = client.get(get_detail_url(obj))
    assert "<form" not in str(response.content)
    assert f'action="{attachment.get_upload_url_for_obj(obj)}"' not in str(response.content)


@pytest.mark.django_db
def test_delete_link_is_listed_with_delete_permission(client, attachment_model, attachment):
    add_perm(attachment.owner, attachment_model, "delete")
    client.force_login(attachment.owner)
    obj = attachment.related_object
    response = client.get(get_detail_url(obj))
    assert "delete-attachment" in str(response.content)


@pytest.mark.django_db
def test_delete_link_is_not_listed_without_delete_permission(client, attachment_model, attachment):
    client.force_login(attachment.owner)
    obj = attachment.related_object
    response = client.get(get_detail_url(obj))
    assert "delete-attachment" not in str(response.content)


@pytest.mark.django_db
def test_delete_link_is_listed_with_edit_all_permission(client, attachment_model, attachment, get_user_factory):
    other_user = get_user_factory(perms=("view", "delete", "edit_any"))
    client.force_login(other_user)
    obj = attachment.related_object
    response = client.get(get_detail_url(obj))
    assert "delete-attachment" in str(response.content)


@pytest.mark.django_db
def test_delete_link_is_not_listed_for_others_attachments(client, attachment_model, attachment, get_user_factory):
    other_user = get_user_factory(perms=("view", "delete"))
    client.force_login(other_user)
    obj = attachment.related_object
    response = client.get(get_detail_url(obj))
    assert "delete-attachment" not in str(response.content)
