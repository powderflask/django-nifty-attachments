from functools import cached_property, wraps
from dataclasses import dataclass
from pathlib import Path

from django import http
from django.contrib import messages
from django.forms import Form, ModelForm
from django.utils.translation import gettext as _
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpRequest, HttpResponseBadRequest
from django.views.decorators.http import require_GET, require_POST, require_http_methods


from . import forms, models, utils


require_PUT = require_http_methods(["PUT"])
require_PUT.__doc__ = "Decorator to require that a view only accepts the PUT method."

require_DELETE = require_http_methods(["DELETE"])
require_DELETE.__doc__ = "Decorator to require that a view only accepts the DELETE method."


@dataclass
class AttachmentViewMixin:
    request: HttpRequest
    related_obj_pk: str | int
    model_type: str | type[models.AbstractAttachment]
    attachment_pk: int = None

    @property
    def next(self):
        next_ = self.request.GET.get("next", self.request.POST.get("next", None))  # noqa
        try:
            return next_ or self.related_obj.get_absolute_url() or "/"
        except AttributeError:
            return "/"

    @cached_property
    def model(self):
        return utils.get_model_class(self.model_type)

    @cached_property
    def attachment(self):
        return get_object_or_404(self.model, pk=self.attachment_pk) if self.attachment_pk is not None else None

    @cached_property
    def related_obj(self):
        return get_object_or_404(self.model.get_related_model(), pk=self.related_obj_pk)

    def invalid_request(self):
        if str(self.attachment.related_object_id) != str(self.related_obj_pk):
            return HttpResponseBadRequest(_("Invalid request: Inconsistent attachment related object."))


def prefix_template(default_template_name):
    """A view decorator that prepends an optional `template_prefix` to the `template_name`"""

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, template_prefix="", **kwargs):
            template_name = kwargs.get("template_name", default_template_name)
            kwargs["template_name"] = str(Path(template_prefix, template_name))
            return view_func(*args, **kwargs)

        return wrapper

    return decorator


@require_POST
@login_required
@prefix_template("attachments/add.html")
def add_attachment(
    request,
    pk,
    model: str | type[models.AbstractAttachment],
    template_name: str,
    form_class: type[Form] = forms.AttachmentUploadForm,
    extra_context=None,
):
    view = AttachmentViewMixin(request, pk, model)

    if not view.model.can_add_attachments(request.user, view.related_obj):
        raise PermissionDenied()

    form = form_class(request.POST, request.FILES)
    if form.is_valid():
        file = form.cleaned_data["attachment_file"]
        view.model.create(request.user, file, related_object=view.related_obj)
        messages.success(request, _(f"Your attachment was uploaded and attached to {view.related_obj}."))
        return redirect(view.next)

    template_context = {
        "form": form,
        "action_url": view.model.get_upload_url_for_obj(view.related_obj),
        "next": view.next or "",
    }
    template_context.update(extra_context or {})

    return render(request, template_name, template_context)


@require_GET
@login_required
def download_attachment(request, pk, model: str | type[models.AbstractAttachment], attachment_pk):
    view = AttachmentViewMixin(request, pk, model, attachment_pk)

    if not view.model.can_view_attachments(request.user, view.related_obj):
        raise PermissionDenied()

    response = http.FileResponse((view.attachment.data,), as_attachment=True, filename=view.attachment.name)
    response["Content-Type"] = view.attachment.content_type
    response["Content-Disposition"] = 'attachment; filename="%s"' % view.attachment.name
    response["Content-Length"] = str(view.attachment.size)

    return response


@require_GET
@login_required
@prefix_template("attachments/list.html")
def list_attachments(
    request,
    pk,
    model: str | type[models.AbstractAttachment],
    template_name: str,
    extra_context=None,
):
    view = AttachmentViewMixin(request, pk, model)

    if not view.model.can_view_attachments(request.user, view.related_obj):
        raise PermissionDenied()

    template_context = {
        "related_object": view.related_obj,
        "attachments": view.related_obj.attachments,
    }
    template_context.update(extra_context or {})

    return render(request, template_name, template_context)


@require_PUT
@login_required
@prefix_template("attachments/upload.html")
def update_attachment(
    request,
    pk,
    model: str | type[models.AbstractAttachment],
    attachment_pk,
    template_name: str,
    form_class: type[ModelForm] = None,  # default: concrete forms.AbstractAttachmentEditForm.get_for(model)
    extra_context=None,
):
    view = AttachmentViewMixin(request, pk, model, attachment_pk)

    if not view.attachment.can_change_attachment(request.user):
        raise PermissionDenied()

    if view.invalid_request():
        return view.invalid_request()

    form_class = form_class or forms.AbstractAttachmentEditForm.get_for(model)
    form = form_class(request.POST, request.FILES)
    if form.is_valid():
        form.save()
        messages.success(request, _("Your attachment was updated."))
        return redirect(view.next)

    template_context = {
        "form": form,
        "action_url": view.attachment.get_update_url(),
        "next": view.next or "",
    }
    template_context.update(extra_context or {})

    return render(request, template_name, template_context)


@require_DELETE
@login_required
def delete_attachment(request, pk, model: str | type[models.AbstractAttachment], attachment_pk):
    view = AttachmentViewMixin(request, pk, model, attachment_pk)

    if not view.attachment.can_delete_attachment(request.user):
        raise PermissionDenied()

    if view.invalid_request():
        return view.invalid_request()

    view.attachment.delete()
    messages.success(request, _("Your attachment was deleted."))
    return redirect(view.next)
