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
        content_type=ContentType.objects.get_for_model(model),
        codename=get_permission_codename(action, model._meta),
    )


def get_perm_name_for_model(
    model: models.Model | type[models.Model], action: str
) -> str:
    """
    return a qualified permission name, 'app_label.action_model' for given action,
    e.g., "add", "change", on a given Django model
    """
    code = get_permission_codename(action, model._meta)
    return f"{model._meta.app_label}.{code}"


def get_model_class(
    model: str | models.Model | type[models.Model],
) -> type[models.Model]:
    """Resolve and return a model class from a "app_label.Model"dotted string"""
    if isinstance(model, models.Model):
        return type(model)
    if isinstance(model, str):
        return apps.get_model(*model.split("."))
    return model


def get_attachment_model_from_related_object(
    related_input: str | models.Model,
) -> type[AbstractAttachment]:
    """
    Introspect the related object or a dotted path ("app_label.RelatedModelClass.related_attachment_name") for the Concrete Attachment model.
    """
    # Handle explicit dotted path: "app.Model.relation"
    if isinstance(related_input, str) and related_input.count(".") == 2:
        model_path, relation_name = related_input.rsplit(".", 1)
        parent_model = get_model_class(model_path)
        try:
            # We look for the related_model of the field (ForeignKey/GenericRel)
            return parent_model._meta.get_field(relation_name).related_model
        except Exception as e:
            raise ValueError(
                f"Could not resolve relation '{relation_name}' on {parent_model._meta.label}: {e}"
            )

    # Handle Auto-discovery (Instance or "app.Model")
    from nifty_attachments.models import AbstractAttachment

    target_class = get_model_class(related_input)

    attachment_models = [
        field.related_model
        for field in target_class._meta.get_fields()
        if isinstance(field, (models.ManyToOneRel, models.ManyToManyRel))
        and field.related_model
        and issubclass(field.related_model, AbstractAttachment)
    ]

    if len(attachment_models) == 1:
        return attachment_models[0]

    if len(attachment_models) > 1:
        model_names = ", ".join(m.__name__ for m in attachment_models)
        raise ValueError(
            f"Ambiguity: {target_class.__name__} has multiple attachment relations: {model_names}. "
            f"Pass a dotted path: 'app.Model.relation_name'."
        )

    raise ValueError(f"No attachment model found for {related_input}.")


def get_attachment_model_for_relation_name(
    related_obj: models.Model, relation_name: str = None
):
    """
    Helper to safely retrieve the attachment model for a specific instance.
    """
    try:
        if relation_name:
            # Uses _meta.label (e.g., 'myapp.Gizmo') to ensure get_model_class works perfectly
            parent_path = related_obj._meta.label
            return get_attachment_model_from_related_object(
                f"{parent_path}.{relation_name}"
            )

        return get_attachment_model_from_related_object(related_obj)
    except Exception:
        return None


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
    descriptor = type(
        descriptor_name,
        (ClassServiceDescriptor,),
        dict(service_class=specialized_service),
    )
    return descriptor
