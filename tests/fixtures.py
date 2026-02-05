"""
    Test fixtures
"""

import importlib

import pytest
import pytest_django.fixtures
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.views import View

import nifty_attachments.settings
from nifty_attachments.utils import get_model_class, get_permission_for_model

from .factories import GizmoAttachmentFactory, UserFactory, UuidAttachmentFactory


class NoView(View):
    def get(self, request, *args, **kwargs):
        raise NotImplementedError(request.path)


def add_perm(user, model, action):

    # If it's a string, resolve it to a class first
    if isinstance(model, str):
        model = get_model_class(model)

    ct = ContentType.objects.get_for_model(model)
    codename = f"{action}_{model._meta.model_name.lower()}"
    perm, _ = Permission.objects.get_or_create(content_type=ct, codename=codename)
    user.user_permissions.add(perm)

    if hasattr(user, "_perm_cache"):
        del user._perm_cache


def remove_perm(user, attachment_model, action: str):
    perm = get_permission_for_model(attachment_model, action)
    user.user_permissions.remove(perm)


@pytest.fixture(params=[GizmoAttachmentFactory, UuidAttachmentFactory])
def attachment_factory(request):
    return request.param


@pytest.fixture
def attachment_model(attachment_factory):
    return attachment_factory._meta.model


@pytest.fixture
def get_user_factory(attachment_model) -> callable:
    """Return a user factory function that initializes user with given perms. for given model"""

    def user_factory(
        perms=(
            "view",
            "add",
        ),
        **kwargs,
    ):
        u = UserFactory(**kwargs)
        for perm in perms:
            add_perm(u, attachment_model, perm)
        return u

    return user_factory


@pytest.fixture
def related_object(attachment_model):
    related_model = attachment_model.related_object.field.related_model
    return related_model.objects.create(title=f"A test {related_model.__name__}")


@pytest.fixture
def attachment(attachment_factory, related_object, get_user_factory):
    """Test fixture with a related object for the given attachment model"""
    jon = get_user_factory(
        username="jon",
        password="password",
        email="jon@example.com",
    )
    attach = attachment_factory(owner=jon, related_object=related_object)
    return attach


class SettingsWrapper(pytest_django.fixtures.SettingsWrapper):
    """Reload Attachments settings after any change to settings."""

    def __delattr__(self, attr: str) -> None:
        super().__delattr__(attr)
        importlib.reload(nifty_attachments.settings)

    def __setattr__(self, attr: str, value) -> None:
        super().__setattr__(attr, value)
        importlib.reload(nifty_attachments.settings)

    def finalize(self) -> None:
        super().finalize()
        importlib.reload(nifty_attachments.settings)


@pytest.fixture()
def attachment_settings():
    """An Attachment settings object which restores changes after the testrun"""
    wrapper = SettingsWrapper()
    yield wrapper
    wrapper.finalize()
