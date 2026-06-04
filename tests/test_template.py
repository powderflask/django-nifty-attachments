import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.urls import reverse

from nifty_attachments.templatetags.attachments_tags import (
    attachment_form,
    attachment_set,
    attachment_upload_url,
    attachments_count,
    can_add_attachment,
    can_change_attachment,
    can_delete_attachment,
)
from nifty_attachments.utils import get_attachment_model_from_related_object

from .fixtures import add_perm
from .testapp.models import Gizmo, InvoiceAttachment

# --- Helpers ---


def get_detail_url(obj):
    url_name = "gizmo:detail" if isinstance(obj, Gizmo) else "uuid4-detail"
    return reverse(url_name, kwargs={"pk": obj.pk})


def get_rel_name(model):
    """Refactored helper to resolve relation name based on model type."""
    return "uuid_attachments" if "Uuid" in model.__name__ else "attachment_set"


# --- Integration / UI Tests ---
@pytest.mark.django_db
def test_detail_view_attachment_integration(client, attachment_model, attachment):
    # Grant delete permission so the 'delete-attachment' string appears
    add_perm(attachment.owner, attachment_model, "delete")

    client.force_login(attachment.owner)
    obj = attachment.related_object
    response = client.get(get_detail_url(obj))
    content = response.content.decode()

    assert "Object has 1 attachments" in content
    assert attachment.get_download_url() in content
    assert "delete-attachment" in content


@pytest.mark.django_db
@pytest.mark.parametrize("has_perm_logic", [True, False])
def test_upload_form_visibility_logic(
    client, attachment_model, attachment, has_perm_logic
):
    user = attachment.owner
    obj = attachment.related_object

    if has_perm_logic:
        add_perm(user, attachment_model, "add")
        add_perm(user, obj, "add")  # Required for UUID/Object-level perms
    else:
        user.user_permissions.clear()

    # Refresh user to pick up the new perms
    user = get_user_model().objects.get(pk=user.pk)

    client.force_login(user)
    response = client.get(get_detail_url(obj))
    content = response.content.decode()

    if has_perm_logic:
        assert "<form" in content
    else:
        assert "<form" not in content


# --- Filter & Logic Tests ---


@pytest.mark.django_db
def test_can_add_attachment_comprehensive(
    get_user_factory, attachment_model, attachment
):
    """Covers instance path, dotted path, and relation names in one flow."""
    user = get_user_factory(perms=(), is_superuser=False)
    obj = attachment.related_object
    rel_name = get_rel_name(attachment_model)

    # 1. Initially False
    assert can_add_attachment(user, obj) is False

    # 2. Grant perms
    add_perm(user, attachment_model, "add")
    add_perm(user, obj, "add")  # for UUID models
    user = type(user).objects.get(pk=user.pk)

    # Test Instance & Dotted Path (Scenario A & B)
    assert can_add_attachment(user, obj) is True
    assert can_add_attachment(user, f"{obj._meta.label}.{rel_name}") is True


@pytest.mark.django_db
def test_attachment_upload_url_logic(attachment_model, attachment):
    """Tests basic filter and relation_name branch."""
    obj = attachment.related_object
    rel_name = get_rel_name(attachment_model)

    assert attachment_upload_url(obj) == attachment.get_upload_url_for_obj(obj)
    assert "add-for" in attachment_upload_url(obj, relation_name=rel_name)


# --- Fail-Fast & Error Path Parametrization ---


@pytest.mark.django_db
@pytest.mark.parametrize(
    "filter_func, expected",
    [
        (can_add_attachment, False),
        (can_change_attachment, False),
        (can_delete_attachment, False),
    ],
)
def test_filter_fail_fast_paths(filter_func, expected, get_user_factory, attachment):
    user = get_user_factory()
    # Pass both user and None/object to satisfy the (user, attachment) signature
    assert filter_func(user, None) == expected
    assert filter_func(None, attachment) == expected


# --- Utility & Tag Specifics ---


@pytest.mark.django_db
def test_attachment_form_tag_context(get_user_factory, attachment):
    """Tests inclusion tag with mocked request context."""
    request = RequestFactory().get("/upload-page/")
    user = get_user_factory()
    add_perm(user, attachment.related_object, "add")

    # Custom context mock to support .request
    class MockContext(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.request = kwargs.get("request")

    context = MockContext(user=user, request=request)
    result = attachment_form(context, attachment.related_object)

    assert result["form"] is not None
    assert result["next"] == "http://testserver/upload-page/"


@pytest.mark.django_db
def test_utility_dotted_path_resolution(get_user_factory):
    """Verify string path to model class flow."""
    user = get_user_factory()
    add_perm(user, InvoiceAttachment, "add")
    path = "attachments_testapp.MultiAttachmentGizmo.invoices"

    assert get_attachment_model_from_related_object(path) == InvoiceAttachment


@pytest.mark.django_db
class TestTagFailPaths:
    """Targeted tests for the 'return null' / fail-fast branches of tags."""

    def test_attachment_form_fail_fast(self, attachment):

        # 1. related_obj is not a Model (hits isinstance check)
        assert attachment_form({}, "not-a-model") == {"form": None}

        # 2. Invalid relation name (get_attachment_model_for_relation_name returns None)
        assert attachment_form(
            {}, attachment.related_object, relation_name="fake_rel"
        ) == {"form": None}

    def test_attachments_count_fail_fast(self):

        # hits if related_obj is None
        assert attachments_count(None) == 0

    def test_attachment_set_fail_fast(self, attachment):

        # 1. related_obj is None
        assert attachment_set(None) == []

        # 2. Invalid relation name
        assert (
            attachment_set(attachment.related_object, relation_name="invalid_rel") == []
        )

    def test_attachment_upload_url_fail_fast(self, attachment):

        # Invalid relation/model results in /400
        assert (
            attachment_upload_url(attachment.related_object, relation_name="bad_rel")
            == "/400"
        )
        assert attachment_upload_url(None) == "/400"


@pytest.mark.django_db
def test_can_add_attachment_resolution_failures(get_user_factory, attachment):

    user = get_user_factory()

    # 1. Invalid dotted path (e.g. only 1 dot where 2 are expected for explicit)
    # This falls through to auto-discovery and fails if model not found
    with pytest.raises(LookupError):
        can_add_attachment(user, "invalid.path") is False

    # 2. Non-existent app/model in string
    with pytest.raises(LookupError):
        assert can_add_attachment(user, "fakeapp.FakeModel.rel") is False

    # 3. Valid user, but None related_obj
    assert can_add_attachment(user, None) is False

    # 4 Real model, no attachments
    from django.contrib.auth.models import User  # noqa

    with pytest.raises(ValueError):
        can_add_attachment(user, "auth.User")
