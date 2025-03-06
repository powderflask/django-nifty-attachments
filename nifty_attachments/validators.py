"""
File upload validation logic
"""

from __future__ import annotations

from django import forms
from django.core.files import File
from django.template.defaultfilters import filesizeformat
from django.utils.translation import gettext_lazy as _

from nifty_attachments import settings


def validate_file_size(file: File, max_size_mb: int = None):
    """raise ValidationError if file size exceeds max_size_mb or max file size setting."""
    max_size_mb = max_size_mb or settings.ATTACHMENTS_FILE_UPLOAD_MAX_SIZE
    if not max_size_mb:
        return
    max_file_size = max_size_mb * 1024 * 1024
    if max_file_size and file.size > max_file_size:
        raise forms.ValidationError(
            _("File size, {size}, exceeds maximum size of {max}.").format(
                size=filesizeformat(file.size), max=filesizeformat(max_file_size)
            )
        )


def validate_file_content_type(file: File, whitelist=()):
    """raise ValidationError if content type not in whitelist or whitelist setting."""
    content_types = whitelist or settings.ATTACHMENTS_CONTENT_TYPE_WHITELIST
    if not content_types:
        return
    try:
        ct = file.content_type
    except AttributeError:
        return
    if ct not in content_types:
        raise forms.ValidationError(
            _("File type {ct} not supported. Supported types: {supported}.").format(ct=ct, supported=content_types)
        )


default_validators = (
    validate_file_size,
    validate_file_content_type,
)
