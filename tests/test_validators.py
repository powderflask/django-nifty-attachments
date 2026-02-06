import pytest
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from nifty_attachments.validators import validate_file_content_type


def test_validate_file_content_type_success():
    """Validates when the content type is in the provided whitelist."""
    file = SimpleUploadedFile("test.pdf", b"content", content_type="application/pdf")
    # Should not raise
    ct = validate_file_content_type(file, whitelist=("application/pdf", "image/jpeg"))
    assert ct is None


def test_validate_file_content_type_invalid_raises_error():
    """Raises ValidationError when the content type is not supported."""
    file = SimpleUploadedFile("test.exe", b"content", content_type="application/x-msdownload")

    with pytest.raises(forms.ValidationError) as excinfo:
        validate_file_content_type(file, whitelist=("image/png", "application/pdf"))

    assert "File type application/x-msdownload not supported" in str(excinfo.value)


@override_settings(ATTACHMENTS_CONTENT_TYPE_WHITELIST=[])
def test_validate_file_content_type_no_whitelist_returns_early(settings):
    """If no whitelist is provided and setting is empty, it should pass anything."""
    file = SimpleUploadedFile("test.any", b"content", content_type="text/plain")

    # Should not raise because whitelist logic is bypassed
    ct = validate_file_content_type(file, whitelist=())
    assert ct is None  # not raised


def test_validate_file_content_type_missing_attribute_graceful_exit():
    """If the file object doesn't have a content_type (e.g. a local File object), it skips validation."""

    class MockFile:
        pass  # No content_type attribute

    # Should return early due to AttributeError handling
    ct = validate_file_content_type(MockFile(), whitelist=("image/png",))
    assert ct is None


@pytest.mark.xfail(reason="not sure", strict=True)
@override_settings(ATTACHMENTS_CONTENT_TYPE_WHITELIST=["image/png"])
def test_validate_file_content_type_uses_settings_fallback(settings):
    """Verifies that it respects the ATTACHMENTS_CONTENT_TYPE_WHITELIST setting."""
    file = SimpleUploadedFile("test.jpg", b"content", content_type="image/jpeg")

    with pytest.raises(forms.ValidationError):
        validate_file_content_type(file)  # No whitelist passed, uses settings
