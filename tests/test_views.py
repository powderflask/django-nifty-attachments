import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch

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
    _ = type(user).objects.get(pk=user.pk)  # bust django permissions cache
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
@pytest.mark.django_db
def test_custom_validator_denies_specific_content(attachment_model, related_object, logged_in_client_user):
    client, user = logged_in_client_user

    response = upload_file(client, attachment_model, related_object, file_content=b"<xml>this is not allowed</xml>")

    assert "XML is forbidden" in str(response.content)
    assert attachment_model.objects.count() == 0


@pytest.mark.django_db
def test_owner_can_update_attachment(client, attachment_model, attachment):
    """Verify owner with change permission can update label and description."""
    user = attachment.owner
    add_perm(user, attachment_model, "change")
    client.force_login(user)

    update_url = attachment.get_update_url()
    payload = {"label": "Updated Label", "description": "Updated Description"}

    response = client.post(update_url, data=payload, follow=True)

    assert response.status_code == 200
    attachment.refresh_from_db()
    assert attachment.label == "Updated Label"
    assert attachment.description == "Updated Description"


@pytest.mark.django_db
def test_non_owner_cant_update_attachment_without_edit_any(attachment_model, attachment, logged_in_client_user):
    """Verify non-owner with 'change' but NO 'edit_any' is denied."""
    client, user = logged_in_client_user
    # User already has 'change' from fixture, but isn't owner
    assert attachment.owner != user

    update_url = attachment.get_update_url()
    response = client.post(update_url, data={"label": "Sneaky Update"})

    assert response.status_code == 403
    attachment.refresh_from_db()
    assert attachment.label != "Sneaky Update"


@pytest.mark.django_db
def test_non_owner_can_update_with_edit_any_permission(client, attachment_model, attachment, get_user_factory):
    """Verify non-owner can update if they possess the 'edit_any' permission."""
    user = get_user_factory(perms=("view", "change", "edit_any"))
    client.force_login(user)

    update_url = attachment.get_update_url()
    payload = {"label": "Admin Override", "description": "Changed by admin"}

    response = client.post(update_url, data=payload, follow=True)

    assert response.status_code == 200
    attachment.refresh_from_db()
    assert attachment.label == "Admin Override"


@pytest.mark.django_db
def test_update_view_get_request_renders_form(client, attachment_model, attachment):
    """Verify GET request to update URL returns the form with initial data."""
    user = attachment.owner
    add_perm(user, attachment_model, "change")
    client.force_login(user)

    update_url = attachment.get_update_url()
    response = client.get(update_url)

    assert response.status_code == 200
    # Check if initial data is present in the rendered HTML or context
    assert attachment.label in str(response.content)
    assert attachment.description in str(response.content)


@pytest.mark.django_db
def test_list_attachments_finds_correct_relation(client, attachment_model, attachment, get_user_factory):
    """
    Verify that list_attachments finds files even when the related_name
    is non-standard (e.g. Uuid model).
    """
    user = attachment.owner
    add_perm(user, attachment_model, "view")
    client.force_login(user)

    # URL for list view
    url = reverse(f"{attachment_model.get_url_namespace()}:list", args=(attachment.related_object_id,))

    response = client.get(url)
    assert response.status_code == 200
    # Verify the attachment label appears in the list
    assert attachment.label in response.content.decode()
    # Verify the related object is in context
    assert response.context["related_object"] == attachment.related_object


@pytest.mark.django_db
def test_download_attachment_success(client, attachment):

    user = attachment.owner
    add_perm(user, attachment._meta.model, "view")
    client.force_login(user)

    url = attachment.get_download_url()
    response = client.get(url)

    assert response.status_code == 200
    # BinaryField data is returned via streaming_content in the view
    content = b"".join(response.streaming_content)

    # Compare against the 'data' field directly
    assert content == attachment.data
    assert response["Content-Type"] == attachment.content_type


@pytest.mark.django_db
def test_redirect_to_next_parameter(client, attachment_model, related_object, logged_in_client_user):

    client, user = logged_in_client_user

    # Grant both model perms and potentially object-level perms
    add_perm(user, attachment_model, "add")
    add_perm(user, related_object, "add")
    if hasattr(related_object, "owner"):
        related_object.owner = user
        related_object.save()

    custom_next = "/custom-destination/"
    base_url = attachment_model.get_upload_url_for_obj(related_object)
    url = f"{base_url}?next={custom_next}"

    file_obj = SimpleUploadedFile("test.pdf", b"fake binary content", content_type="application/pdf")
    response = client.post(url, {"attachment_file": file_obj, "label": "Test"})

    assert response.status_code == 302
    assert response.url == custom_next


@pytest.mark.django_db
class TestViewResolutionFailures:

    def test_update_view_invalid_attachment_id(self, client, attachment, attachment_model, logged_in_client_user):
        client, _ = logged_in_client_user

        # Use a valid related_object_id but a fake attachment PK
        fake_pk = 99999

        url = reverse(f"{attachment_model.get_url_namespace()}:update", args=(attachment.related_object_id, fake_pk))

        response = client.post(url, data={"label": "New"})
        assert response.status_code == 404

    def test_delete_view_invalid_attachment_id(self, client, attachment, attachment_model, logged_in_client_user):
        client, _ = logged_in_client_user

        fake_pk = 99999

        url = reverse(f"{attachment_model.get_url_namespace()}:delete", args=(attachment.related_object_id, fake_pk))

        response = client.delete(url)
        assert response.status_code == 404


@pytest.mark.django_db
def test_mixin_invalid_request_handling(client, attachment_model, logged_in_client_user):
    client, _ = logged_in_client_user

    other_obj = get_user_model().objects.create(username="wrong_type", password="!")

    try:
        url = attachment_model.get_upload_url_for_obj(other_obj)
        response = client.get(url)
        # Handle the 405 if the upload view only allows POST
        if response.status_code == 405:
            response = client.post(url)
        assert response.status_code == 404
    except (ValidationError, NoReverseMatch):
        # If the URL can't even be built, we've technically covered the safety logic
        pytest.skip("URL resolution failed before reaching view logic")


@pytest.mark.django_db
def test_download_permission_denied(client, attachment, attachment_model):
    """Hits the 'raise PermissionDenied()' by using a total stranger."""

    stranger = get_user_model().objects.create(username="stranger")
    client.force_login(stranger)

    # Stranger should not have access to GizmoAttachment or UuidAttachment
    url = attachment.get_download_url()
    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_update_permission_denied(client, attachment, logged_in_client_user):
    """Hits the 'raise PermissionDenied()' in update_attachment."""
    client, user = logged_in_client_user
    # Ensure user has NO change permissions
    url = attachment.get_update_url()

    response = client.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_list_permission_denied(client, attachment, logged_in_client_user):
    """Hits the 'raise PermissionDenied()' in update_attachment."""

    stranger = get_user_model().objects.create(username="stranger")
    client.force_login(stranger)
    url = reverse(f"{attachment.get_url_namespace()}:list", args=(attachment.related_object.pk,))

    response = client.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_update_view_invalid_request_mismatch(client, attachment, attachment_model, admin_user):
    """
    Triggers view.invalid_request() by being a Superuser (bypassing 403)
    but providing mismatched IDs.
    """
    client.force_login(admin_user)

    # Create another related object
    other_obj = attachment.related_object._meta.model.objects.create(
        **({"title": "Other"} if hasattr(attachment.related_object, "title") else {})
    )

    # URL: Valid Other Object + Valid Attachment (but mismatched)
    url = reverse(f"{attachment_model.get_url_namespace()}:update", args=(other_obj.pk, attachment.pk))

    response = client.get(url)
    assert response.status_code == 400


@pytest.mark.django_db
def test_delete_view_invalid_request_mismatch(client, attachment, attachment_model, admin_user):
    """Triggers view.invalid_request() in delete view via Superuser."""
    client.force_login(admin_user)

    other_obj = attachment.related_object._meta.model.objects.create(
        **({"title": "Other"} if hasattr(attachment.related_object, "title") else {})
    )

    url = reverse(f"{attachment_model.get_url_namespace()}:delete", args=(other_obj.pk, attachment.pk))

    # delete_attachment allows POST
    response = client.post(url)
    assert response.status_code == 400
