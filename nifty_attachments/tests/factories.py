import mimetypes

import factory
from django.contrib.auth import get_user_model
from factory import Faker, SubFactory
from factory.django import DjangoModelFactory

from .testapp import models

User = get_user_model()


class UserFactory(DjangoModelFactory):
    username = Faker("user_name")
    email = Faker("email")
    password = Faker("password")

    class Meta:
        model = User


class GizmoFactory(DjangoModelFactory):
    title = Faker("word")

    class Meta:
        model = models.GizmoModel


class AbstractAttachmentFactory(DjangoModelFactory):
    owner = SubFactory(UserFactory)
    label = (Faker("word"),)
    description = (Faker("paragraph"),)
    name = Faker("file_name", category="image")
    content_type = factory.LazyAttribute(lambda obj: mimetypes.guess_type(obj.name)[0] or "text/plain")
    data = b"Binary file content"
    size = factory.LazyAttribute(lambda obj: len(obj.data))


class GizmoAttachmentFactory(AbstractAttachmentFactory):
    related_object = SubFactory(GizmoFactory)

    class Meta:
        model = models.GizmoAttachment


class ModelWithUuidPkFactory(DjangoModelFactory):
    title = Faker("word")

    class Meta:
        model = models.ModelWithUuidPk


class UuidAttachmentFactory(AbstractAttachmentFactory):
    related_object = SubFactory(ModelWithUuidPkFactory)

    class Meta:
        model = models.UuidAttachment
