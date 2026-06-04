from dataclasses import dataclass
from functools import cached_property, wraps
from pathlib import Path

from django import http
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.forms import Form
from django.http import HttpRequest, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import forms, models, utils


@dataclass
class AttachmentViewMixin:
    request: HttpRequest
    related_obj_pk: str | int
    model_type: str | type[models.AbstractAttachment]
    attachment_pk: int = None

    @property
    def next(self):
        next_ = self.request.GET.get("next", self.request.POST.get("next", None))
        try:
            return next_ or self.related_obj.get_absolute_url() or "/"
        except AttributeError:
            return "/"

    @cached_property
    def model(self) -> type[models.AbstractAttachment]:
        # Centralized resolution: handles both class and 'app.Model' strings
        return utils.get_model_class(self.model_type)

    @cached_property
    def attachment(self):
        return (
            get_object_or_404(self.model, pk=self.attachment_pk)
            if self.attachment_pk is not None
            else None
        )

    @cached_property
    def related_obj(self):
        # Always uses the resolved model class to find the parent
        return get_object_or_404(self.model.get_related_model(), pk=self.related_obj_pk)

    def invalid_request(self):
        if self.attachment and str(self.attachment.related_object_id) != str(
            self.related_obj_pk
        ):
            return HttpResponseBadRequest(
                _("Invalid request: Inconsistent attachment related object.")
            )


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
@prefix_template("nifty/attachments/add.html")
def add_attachment(
    request,
    pk,
    model: str | type[models.AbstractAttachment],
    template_name: str,
    form_class: type[Form] = forms.AttachmentUploadForm,
    extra_context=None,
):
    view = AttachmentViewMixin(request, pk, model)
    concrete_model = view.model

    if not concrete_model.can_add_attachments(request.user, view.related_obj):
        raise PermissionDenied()

    form = form_class(request.POST, request.FILES)
    if form.is_valid():
        file = form.cleaned_data["attachment_file"]
        concrete_model.create(request.user, file, related_object=view.related_obj)
        messages.success(request, _("Your attachment was uploaded."))
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
def download_attachment(
    request, pk, model: str | type[models.AbstractAttachment], attachment_pk
):
    view = AttachmentViewMixin(request, pk, model, attachment_pk)

    if not view.model.can_view_attachments(request.user, view.related_obj):
        raise PermissionDenied()

    response = http.FileResponse(
        (view.attachment.data,), as_attachment=True, filename=view.attachment.name
    )
    response["Content-Type"] = view.attachment.content_type
    response["Content-Disposition"] = 'attachment; filename="%s"' % view.attachment.name
    response["Content-Length"] = str(view.attachment.size)

    return response


@require_GET
@login_required
@prefix_template("nifty/attachments/list.html")
def list_attachments(request, pk, model, template_name, extra_context=None):
    view = AttachmentViewMixin(request, pk, model)

    if not view.model.can_view_attachments(request.user, view.related_obj):
        raise PermissionDenied()

    # Dynamically find the relation (e.g., 'attachment_set' vs 'invoices')
    rel_name = (
        view.model._meta.get_field("related_object").remote_field.related_name
        or "attachment_set"
    )
    attachments = getattr(view.related_obj, rel_name).all()

    template_context = {
        "related_object": view.related_obj,
        "attachments": attachments,
    }
    template_context.update(extra_context or {})
    return render(request, template_name, template_context)


@require_http_methods(["GET", "POST", "PUT"])
@login_required
@prefix_template("nifty/attachments/edit.html")
def update_attachment(
    request,
    pk,
    model,
    attachment_pk,
    template_name,
    form_class=None,
    extra_context=None,
):
    view = AttachmentViewMixin(request, pk, model, attachment_pk)

    if not view.attachment.can_change_attachment(request.user):
        raise PermissionDenied()

    if error_resp := view.invalid_request():
        return error_resp

    form_class = form_class or forms.AbstractAttachmentEditForm.get_for(view.model)

    if request.method in ("POST", "PUT"):
        form = form_class(request.POST, request.FILES, instance=view.attachment)
        if form.is_valid():
            form.save()
            messages.success(request, _("Your attachment was updated."))
            return redirect(view.next)
    else:
        form = form_class(instance=view.attachment)

    template_context = {
        "form": form,
        "attachment": view.attachment,
        "action_url": view.attachment.get_update_url(),
        "next": view.next or "",
    }
    template_context.update(extra_context or {})
    return render(request, template_name, template_context)


@require_http_methods(["POST", "DELETE"])
@login_required
def delete_attachment(
    request, pk, model: str | type[models.AbstractAttachment], attachment_pk
):
    view = AttachmentViewMixin(request, pk, model, attachment_pk)

    if not view.attachment.can_delete_attachment(request.user):
        raise PermissionDenied()

    if view.invalid_request():
        return view.invalid_request()

    view.attachment.delete()
    messages.success(request, _("Your attachment was deleted."))
    return redirect(view.next)
