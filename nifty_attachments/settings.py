"""
Default settings for the attachments app.

Provides defaults for all attachments settings.
"""

from django.conf import settings

# Upload file settings - constrain the file content_types and max. filesize for document file uploads.
# None to allow any file type.  Future State add dependency on python-magic and libmagic for whitelist processing.
#   e.g.  ATTACHMENTS_CONTENT_TYPE_WHITELIST = ('application/pdf', 'image/png', 'image/jpg')
ATTACHMENTS_CONTENT_TYPE_WHITELIST = getattr(settings, "ATTACHMENTS_CONTENT_TYPE_WHITELIST", None) or getattr(
    settings, "FILE_UPLOAD_CONTENT_TYPES", ()
)

# max. size in Mb, None for no limit
ATTACHMENTS_FILE_UPLOAD_MAX_SIZE = getattr(settings, "ATTACHMENTS_FILE_UPLOAD_MAX_SIZE", None) or getattr(
    settings, "FILE_UPLOAD_MAX_SIZE", 10
)

# an iterable of uploaded file validators or a dotted path to import such an iterable.
ATTACHMENTS_FILE_UPLOAD_VALIDATORS = getattr(settings, "ATTACHMENTS_FILE_UPLOAD_VALIDATORS", None) or getattr(
    settings, "FILE_UPLOAD_VALIDATORS", "nifty_attachments.validators.default_validators"
)
