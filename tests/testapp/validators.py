"""
Attachment validators for testapp
"""

from django.core.exceptions import ValidationError

from nifty_attachments.validators import default_validators


def deny_xml_uploads(uploaded_file):
    if uploaded_file.read().find(b"<xml>") > -1:
        raise ValidationError("XML is forbidden")


testapp_validators = default_validators + (deny_xml_uploads,)
