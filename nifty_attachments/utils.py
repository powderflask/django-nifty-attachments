"""
Utility functions
"""

from typing import ForwardRef, TypeVar

from django.apps import apps
from django.contrib.auth import get_permission_codename, get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.module_loading import import_string

User = get_user_model()
AbstractAttachment = ForwardRef("attachments.AbstractAttachment")


def get_permission_for_model(model: type[models.Model], action: str) -> Permission:
    """
    return a permission object for given action, e.g., "add", "change", on a given Django model
    """
    return Permission.objects.get(
        content_type=ContentType.objects.get_for_model(model), codename=get_permission_codename(action, model._meta)
    )


def get_perm_name_for_model(model: models.Model | type[models.Model], action: str) -> str:
    """
    return a qualified permission name, 'app_label.action_model' for given action,
    e.g., "add", "change", on a given Django model
    """
    code = get_permission_codename(action, model._meta)
    return f"{model._meta.app_label}.{code}"


def get_model_class(model: str | type[models.Model]) -> type[models.Model]:
    """Resolve and return a model class from a "app_label.Model"dotted string"""
    match model:
        case str():
            return apps.get_model(*model.split("."))  # type: ignore
        case _:
            assert issubclass(model, models.Model)
            return model


def get_attachment_model_from_related_object(related_object: models.Model) -> type[AbstractAttachment]:
    """Introspect the related object for the Concrete Attachment model"""
    from nifty_attachments.models import AbstractAttachment

    if hasattr(related_object, "attachment_set"):
        # Short-cut - if the default related_name is being uses, this is trivial.
        return related_object.attachment_set.none().model

    related_model = type(related_object)

    # Find the model classes for the fields which are subclass of A
    attachment_models = [
        field.related_model
        for field in related_model._meta.get_fields()
        if isinstance(field, models.ManyToOneRel) and issubclass(field.related_model, AbstractAttachment)
    ]
    if len(attachment_models) == 0:
        raise ValueError(f"Related object {related_object} has no related attachments.")
    elif len(attachment_models) > 1:
        attachment_model_names = ", ".join(model.__name__ for model in attachment_models)
        raise ValueError(
            f"Related object {related_object} has multiple related attachments: {attachment_model_names}."
        )

    return attachment_models[0]


T = TypeVar("T")


def resolve_import(value: str | T) -> T:
    """value can be a concrete object or a string with a dotted path to the object."""
    try:
        return import_string(value)
    except ImportError:
        return value


class ClassServiceDescriptor:
    """
    A descriptor used to "inject" instances of a "service" class onto its owner class.
    First positional parameter of service_class class must be an owner class (type not instance!)
    """

    service_class = None

    def __init__(self, service_class=None, **kwargs):
        """
        Inject service_class instances, initialized with owner class, into the descriptor's owner class
        first positional arg for service_class constructor must be an owner class type
        kwargs are passed through to the service_class constructor
        """
        self.service_class = service_class or self.service_class
        self.service_class_kwargs = kwargs
        self.attr_name = ""  # set by __set_name__

    def __set_name__(self, owner, name):
        self.attr_name = name

    def __get__(self, instance, owner):
        owner = owner or type(instance)
        service_obj = self.service_class(owner, **self.service_class_kwargs)
        setattr(owner, self.attr_name, service_obj)
        return service_obj


def class_service(service_class, **kwargs):
    """
    Factory to return specialized class service descriptors.
    Return a ClassServiceDescriptor for a specialized subclass of service_class, that has kwargs as class attributes
    """
    specialized_service = type(service_class.__name__, (service_class,), kwargs)

    descriptor_name = f"{service_class.__name__}ClassService"
    descriptor = type(descriptor_name, (ClassServiceDescriptor,), dict(service_class=specialized_service))
    return descriptor
