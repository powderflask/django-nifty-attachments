""" Unit tests for attachments.utils """

import pytest
from django.contrib.auth.models import Permission

from nifty_attachments.utils import (
    get_attachment_model_from_related_object,
    get_model_class,
    get_perm_name_for_model,
    get_permission_for_model,
)

from .testapp.models import GizmoAttachment


@pytest.mark.django_db
def test_get_permission_for_model():
    perm = get_permission_for_model(GizmoAttachment, "add")
    assert type(perm) is Permission
    assert perm.codename == "add_gizmoattachment"


@pytest.mark.django_db
def test_get_perm_name_for_model():
    name = get_perm_name_for_model(GizmoAttachment, "add")
    assert name == "attachments_testapp.add_gizmoattachment"


@pytest.mark.django_db
def test_get_model_class():
    model = get_model_class("attachments_testapp.GizmoAttachment")
    assert model is GizmoAttachment
    model = get_model_class(GizmoAttachment)
    assert model is GizmoAttachment


@pytest.mark.django_db
def test_get_attachment_model_from_related_object(attachment_model, attachment):
    related_object = attachment.related_object
    model = get_attachment_model_from_related_object(related_object)
    assert model is attachment_model


# ClassServiceDescriptor and class_service are well-tested in their native package,
# just didn't want to introduce dependency here.
