""" Unit tests for attachments.utils """

import pytest
from django.contrib.auth.models import Permission

from nifty_attachments.utils import (
    get_attachment_model_from_related_object,
    get_model_class,
    get_perm_name_for_model,
    get_permission_for_model,
)

from .testapp.models import (
    BlueprintAttachment,
    GizmoAttachment,
    InvoiceAttachment,
    MultiAttachmentGizmo,
)


@pytest.mark.django_db
def test_get_permission_for_model():
    perm = get_permission_for_model(GizmoAttachment, "add")
    assert type(perm) is Permission
    assert perm.codename == "add_gizmoattachment"


@pytest.mark.django_db
def test_get_perm_name_for_model():
    # Test with Class
    name = get_perm_name_for_model(GizmoAttachment, "add")
    assert name == "attachments_testapp.add_gizmoattachment"

    # Test with Instance (if your helper supports it)
    instance = GizmoAttachment()
    name = get_perm_name_for_model(instance, "add")
    assert name == "attachments_testapp.add_gizmoattachment"


@pytest.mark.django_db
def test_get_model_class():
    model = get_model_class("attachments_testapp.GizmoAttachment")
    assert model is GizmoAttachment
    model = get_model_class(GizmoAttachment)
    assert model is GizmoAttachment


@pytest.mark.django_db
def test_get_attachment_model_from_related_object_by_instance(attachment_model, attachment):
    """Scenario 1: Standard resolution using a model instance."""
    related_object = attachment.related_object
    model = get_attachment_model_from_related_object(related_object)
    assert model is attachment_model


@pytest.mark.django_db
def test_get_attachment_model_from_related_object_by_class_string(attachment_model):
    """Scenario 2: Resolution using an 'app.Model' string."""
    path = "attachments_testapp.Gizmo"
    model = get_attachment_model_from_related_object(path)
    assert model is GizmoAttachment


@pytest.mark.django_db
def test_get_attachment_model_from_related_object_by_relation_path(attachment_model, attachment):
    parent_model = attachment_model.get_related_model()
    # Again, find the name dynamically
    relation_name = attachment_model._meta.get_field("related_object").remote_field.related_name

    path = f"{parent_model._meta.app_label}.{parent_model._meta.model_name}.{relation_name}"

    model = get_attachment_model_from_related_object(path)
    # Ensure it matches the specific factory-generated model for this test run
    assert model is attachment_model


@pytest.mark.django_db
def test_get_attachment_model_ambiguity_error(attachment_model):
    """
    If a model has multiple AbstractAttachment relations, it should
    raise ValueError unless an explicit path is provided.
    """

    # This assumes MultiAttachmentGizmo is set up with two different
    # concrete attachment models in your test app.
    with pytest.raises(ValueError) as excinfo:
        get_attachment_model_from_related_object("attachments_testapp.MultiAttachmentGizmo")

    assert "multiple attachment relations" in str(excinfo.value)


@pytest.mark.django_db
def test_get_attachment_model_invalid_path():
    """Verify error handling for invalid relation strings."""
    with pytest.raises(ValueError):
        # Correct app.Model but non-existent relation
        get_attachment_model_from_related_object("attachments_testapp.Gizmo.wrong_relation")


@pytest.mark.django_db
def test_get_attachment_model_ambiguity_logic():
    """
    Verify that a model with multiple attachment relations raises a ValueError
    when auto-discovery is attempted, but succeeds with an explicit path.
    """

    gizmo = MultiAttachmentGizmo.objects.create(name="Multi-Tasker")

    # 1. Test Auto-discovery failure (The Ambiguity)
    with pytest.raises(ValueError) as excinfo:
        get_attachment_model_from_related_object(gizmo)
    assert "multiple attachment relations" in str(excinfo.value)

    # 2. Test Explicit Resolution for Relation A
    path_a = "attachments_testapp.MultiAttachmentGizmo.invoices"
    model_a = get_attachment_model_from_related_object(path_a)
    assert model_a is InvoiceAttachment

    # 3. Test Explicit Resolution for Relation B
    path_b = "attachments_testapp.MultiAttachmentGizmo.blueprints"
    model_b = get_attachment_model_from_related_object(path_b)
    assert model_b is BlueprintAttachment


def test_get_attachment_model_lookup_error():
    # apps.get_model will fail to find 'fake_app'
    path = "fake_app.NonExistentModel"

    with pytest.raises(LookupError):
        get_attachment_model_from_related_object(path)


def test_get_attachment_model_value_error():
    from django.contrib.auth.models import User  # "load" the model # noqa

    path = "auth.User"
    # invalid model (no attachments)
    with pytest.raises(ValueError):
        get_attachment_model_from_related_object(path)
