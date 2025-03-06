import json
from http import HTTPStatus

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from nifty_attachments.utils import get_perm_name_for_model

from .factories import GizmoAttachmentFactory, UuidAttachmentFactory
from .fixtures import add_perm, remove_perm
from .testapp.models import UuidAttachment


def upload_file(client, attachment_model, obj, file_obj=None, file_content=b"file content", **extra):
    """Uploads a sample file for the given user."""
    add_url = attachment_model.get_upload_url_for_obj(obj)

    if not file_obj:
        file_obj = SimpleUploadedFile(
            "Ünicode Filename 🙂.jpg",
            file_content,
            content_type="image/jpeg",
        )
    return client.post(add_url, {"attachment_file": file_obj}, follow=True, **extra)


def get_related_set(attachment_model, obj):
    """Uuid model overrides the default reverse related_name"""
    return obj.uuid_attachments.all() if attachment_model is UuidAttachment else obj.attachment_set.all()


@pytest.fixture
def logged_in_client_user(client, get_user_factory):
    user = get_user_factory(perms=("view", "add", "change", "delete"))
    client.force_login(user)
    return client, user


@pytest.mark.django_db
def test_empty_post_to_form_wont_create_attachment(attachment_model, related_object, logged_in_client_user):
    client, _ = logged_in_client_user
    add_url = attachment_model.get_upload_url_for_obj(related_object)
    response = client.post(add_url)
    # uuid model requires extra permissions to add, so yields Permission Denied
    assert response.status_code == 403 if attachment_model is UuidAttachment else 200
    assert attachment_model.objects.count() == 0
    assert get_related_set(attachment_model, related_object).count() == 0


@pytest.mark.parametrize("attachment_factory", [GizmoAttachmentFactory], indirect=True)
@pytest.mark.django_db
def test_invalid_model_yields_404(attachment_model, logged_in_client_user):
    # Can't "get" Uuid PK object with a user object int id.
    client, user = logged_in_client_user
    add_url = attachment_model.get_upload_url_for_obj(user)
    response = client.post(add_url)
    assert response.status_code == 404
    assert attachment_model.objects.count() == 0


@pytest.mark.django_db
def test_invalid_attachment_wont_fail(attachment_model, related_object, logged_in_client_user):
    client, user = logged_in_client_user
    response = upload_file(client, attachment_model, related_object, file_obj="Not a UploadedFile object")
    # uuid model requires extra permissions to add, so yields Permission Denied
    assert response.status_code == 403 if attachment_model is UuidAttachment else 200
    assert attachment_model.objects.count() == 0


@pytest.mark.parametrize("attachment_factory", [GizmoAttachmentFactory], indirect=True)
@pytest.mark.django_db
def test_upload_size_less_than_limit(attachment_settings, attachment_model, related_object, logged_in_client_user):
    attachment_settings.ATTACHMENTS_FILE_UPLOAD_MAX_SIZE = 1  # Mb
    client, user = logged_in_client_user
    response = upload_file(client, attachment_model, related_object)
    assert response.status_code == 200
    assert attachment_model.objects.count() == 1
    assert get_related_set(attachment_model, related_object).count() == 1


@pytest.mark.parametrize("attachment_factory", [GizmoAttachmentFactory], indirect=True)
@pytest.mark.django_db
def test_upload_size_more_than_limit(attachment_settings, attachment_model, related_object, logged_in_client_user):
    attachment_settings.ATTACHMENTS_FILE_UPLOAD_MAX_SIZE = 1 / (1024 * 1024)  # 1 byte
    client, user = logged_in_client_user
    response = upload_file(client, attachment_model, related_object)
    assert response.status_code == 200
    assert attachment_model.objects.count() == 0
    assert "File size, 12" in str(response.content)
    assert "exceeds maximum size of 1" in str(response.content)


@pytest.mark.django_db
def test_upload_without_permission(attachment_model, related_object, logged_in_client_user):
    client, user = logged_in_client_user
    remove_perm(user, attachment_model, "add")
    response = upload_file(client, attachment_model, related_object)
    assert response.status_code == 403
    assert attachment_model.objects.count() == 0


@pytest.mark.parametrize("attachment_factory", [GizmoAttachmentFactory], indirect=True)
@pytest.mark.django_db
def test_upload_with_permission(attachment_model, related_object, logged_in_client_user):
    client, user = logged_in_client_user
    response = upload_file(client, attachment_model, related_object)
    assert response.status_code == 200
    assert attachment_model.objects.count() == 1


@pytest.mark.parametrize("attachment_factory", [UuidAttachmentFactory], indirect=True)
@pytest.mark.django_db
def test_upload_with_custom_permission(attachment_model, related_object, logged_in_client_user):
    client, user = logged_in_client_user
    response = upload_file(client, attachment_model, related_object)
    assert user.has_perm(get_perm_name_for_model(attachment_model, "add"))  # has basic perm
    assert response.status_code == 403  # but custom perm adds additional restriction
    assert attachment_model.objects.count() == 0


@pytest.mark.django_db
def test_anonymous_user_cant_delete_attachment(client, attachment_model, attachment):
    del_url = attachment.get_delete_url()
    response = client.delete(del_url, follow=False)
    assert response.status_code == 302
    assert attachment_model.objects.count() == 1


@pytest.mark.django_db
def test_owner_can_delete_attachment(client, attachment_model, attachment):
    user = attachment.owner
    add_perm(user, attachment_model, "delete")
    u = type(user).objects.get(pk=user.pk)  # bust django permissions cache
    client.force_login(attachment.owner)
    del_url = attachment.get_delete_url()
    response = client.delete(del_url, follow=True)
    assert response.status_code == 200
    assert attachment_model.objects.count() == 0


@pytest.mark.django_db
def test_owner_cant_delete_attachment_without_permission(client, attachment_model, attachment):
    user = attachment.owner
    assert not user.has_perm(get_perm_name_for_model(attachment_model, "delete"))
    client.force_login(user)
    del_url = attachment.get_delete_url()
    response = client.delete(del_url, follow=True)
    assert response.status_code == 403
    assert attachment_model.objects.count() == 1


@pytest.mark.django_db
def test_cant_delete_others_attachment_without_permission(attachment_model, attachment, logged_in_client_user):
    client, user = logged_in_client_user
    assert user.has_perm(get_perm_name_for_model(attachment_model, "delete"))
    del_url = attachment.get_delete_url()
    response = client.delete(del_url, follow=True)
    assert response.status_code == 403
    assert attachment_model.objects.count() == 1


@pytest.mark.django_db
def test_can_delete_others_attachment_with_permission(client, attachment_model, attachment, get_user_factory):
    user = get_user_factory(perms=("view", "delete", "edit_any"))
    assert attachment.owner != user
    client.force_login(user)
    del_url = attachment.get_delete_url()
    response = client.delete(del_url, follow=True)
    assert response.status_code == 200
    assert attachment_model.objects.count() == 0


@pytest.mark.parametrize("attachment_factory", [GizmoAttachmentFactory], indirect=True)
class TestCustomValidators:

    @pytest.mark.django_db
    def test_deny_specific_content(self, attachment_model, related_object, logged_in_client_user):
        client, user = logged_in_client_user

        response = upload_file(
            client, attachment_model, related_object, file_content=b"<xml>this is not allowed</xml>"
        )

        assert "XML is forbidden" in str(response.content)
        assert attachment_model.objects.count() == 0

    @pytest.mark.django_db
    def test_form_errors_are_returned_as_json(self, attachment_model, related_object, logged_in_client_user):
        client, user = logged_in_client_user

        response = upload_file(
            client,
            attachment_model,
            related_object,
            file_content=b"<xml>this is not allowed</xml>",
            HTTP_X_RETURN_FORM_ERRORS=True,
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.headers.get("Content-Type") == "application/json"

        errors = json.loads(response.content)
        # note: field errors are a list of string messages
        assert errors["attachment_file"] == ["XML is forbidden"]

        assert attachment_model.objects.count() == 0
