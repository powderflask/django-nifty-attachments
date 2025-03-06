"""
Abstract Forms for attachments operations.

Concrete ModelForms are constructed at runtime using modelform_factory to inject the concrete model class
"""

from __future__ import annotations

from typing import TypeVar

from django import forms
from django.utils.translation import gettext_lazy as _

from nifty_attachments import settings
from nifty_attachments.models import AbstractAttachment
from nifty_attachments.utils import resolve_import

validators = list(resolve_import(settings.ATTACHMENTS_FILE_UPLOAD_VALIDATORS))

ModelFormType = TypeVar("ModelFormType", bound=type[forms.ModelForm])


class AttachmentUploadForm(forms.Form):
    attachment_file = forms.FileField(label=_("Upload attachment"), validators=validators)


class AbstractModelForm(forms.ModelForm):
    """Base class for a ModelForm where the Model is injected at runtime."""

    @classmethod
    def get_for(cls, model: type[AbstractAttachment]):
        """Return a concrete version of this form for the given Attachment model."""
        return forms.modelform_factory(model, cls)


class AbstractAttachmentEditForm(AbstractModelForm):
    """ModelForm without a model (can't be used as-is!). Inject concrete Model using modelform_factory"""

    class Meta:
        model = None  # expecting concrete subclass of AbstractAttachment
        fields = (
            "label",
            "description",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fld_name in ("label", "description"):
            fld = self.fields[fld_name]
            fld.widget.attrs["title"] = self.instance.info
            fld.widget.attrs["placeholder"] = fld.help_text
