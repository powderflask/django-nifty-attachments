"""
    Test fixtures
"""
import importlib
from django.views.generic import View
import pytest
import pytest_django.fixtures
import nifty_attachments.settings
from nifty_attachments.utils import get_permission_for_model
from tests.factories import GizmoAttachmentFactory, UserFactory, UuidAttachmentFactory


class NoView(View):
    def get(self, request, *args, **kwargs):
        raise NotImplementedError(request.path)


@pytest.fixture(autouse=True)
def url_conf(settings):
    # settings.ROOT_URLCONF = "nifty_attachments.tests.testapp.urls"
    # Hack - add minimal DVM urls to allow the test suite to run in context of DVM project.  Remove when factored out.
    from django.urls import include, path

    from tests.testapp.urls import urlpatterns

    urlconf = lambda: None
    urlconf.urlpatterns = urlpatterns + [
        # path("dvm/", include("dvm.urls")),
        path("messages/", NoView.as_view(), name="messages"),  # messages route exists in 'base.html', so its faked
    ]
    settings.ROOT_URLCONF = urlconf


def add_perm(user, attachment_model, action: str):
    perm = get_permission_for_model(attachment_model, action)
    user.user_permissions.add(perm)


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
