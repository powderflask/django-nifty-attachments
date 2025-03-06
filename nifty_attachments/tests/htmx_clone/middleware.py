# flake8: noqa: F401
"""
htmx middleware
- Update [response headers](https://htmx.org/reference/#response_headers) for htmx requests
"""

import importlib.util
import json
import sys
from collections.abc import Awaitable, Callable, Iterable, Mapping
from typing import Any, TypeAlias

# from django.contrib.messages.middleware import MessageMiddleware
from django.http import Http404, HttpRequest, HttpResponse
from django.http.response import HttpResponseBase
from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_http_methods
from django_htmx.http import (
    HttpResponseClientRedirect,
    HttpResponseClientRefresh,
    HttpResponseLocation,
    push_url,
    replace_url,
    reswap,
    retarget,
    trigger_client_event,
)
from django_htmx.middleware import HtmxMiddleware

require_PUT = require_http_methods(["PUT"])
require_PUT.__doc__ = "Decorator to require that a view only accepts the PUT method."

require_PATCH = require_http_methods(["PATCH"])
require_PATCH.__doc__ = "Decorator to require that a view only accepts the PATCH method."

require_DELETE = require_http_methods(["DELETE"])
require_DELETE.__doc__ = "Decorator to require that a view only accepts the DELETE method."


class Htmx404Middleware(MiddlewareMixin):
    """
    Exception handler that will attempt to catch `Http404` errors and send a 404
    response with an inline_msg error message.

    Used for returning partial error template for htmx requests that result in 404 due to `get_object_or_404`
    Note: This only works for a real view that raises a 404. It does not work for a url pattern that the url resolver
    can't find. In that case, the 404 will be handled before this middleware is called.
    """

    def process_exception(self, request: HttpRequest, exception: Exception) -> HttpResponse | None:
        if isinstance(exception, Http404) and request.htmx and not request.htmx.boosted:
            # 404 response with inline_msg
            return msg_return(
                request,
                "One or more of the requested resources was not found",
                status=404,
                style="alert-error",
            )
        else:
            # If it's not 404ing from requesting a new page, just return None.
            # This will allow Django to handle it normally.
            return None


# EXPERIMENTAL - DO NOT USE except for A/B testing once existing system (poll.html + hx_messages.html) is trialed
# class HtmxMessageMiddleware(MessageMiddleware):
#     def process_response(self, request, response):
#         response = super().process_response(request, response)
#         if request.htmx and request._messages._queued_messages:
#             # unprocessed messages exist in storage: tell client to poll for them
#             modify_htmx_response(request, {"events": "pollMsg"})
#         return response


class HtmxResponseMiddleware(HtmxMiddleware):
    """
    Middleware subclassing
    (https://django-htmx.readthedocs.io/en/latest/middleware.html)

    to programatically apply modifications
    (https://django-htmx.readthedocs.io/en/latest/http.html#response-modifying-functions)

    to htmx responses
    """

    def __init__(
        self,
        get_response: Callable[[HttpRequest], HttpResponseBase] | Callable[[HttpRequest], Awaitable[HttpResponseBase]],
    ) -> None:
        super().__init__(get_response)
        self.functions_to_process = {}

    def __call__(self, request):
        response = super().__call__(request)
        if request.htmx:
            response["Cache-Control"] = "no-store, max-age=0"  # disable client side cache for hx requests
            # Update htmx response headers from view specific modifications
            if hasattr(request, "functions_to_process") and request.functions_to_process:
                response = process_htmx_response(response, request.functions_to_process)
        return response


def boost(request, location, responseHandler, *responseArgs) -> HttpResponse:
    # request.headers["HX-Boosted"] = "true"  # can't modify WSGIRequest, so we simulate
    modify_htmx_response(request, {"retarget": "body"})
    response = responseHandler(request, *responseArgs)
    return push_url(response, location)


def reselect(response: HttpResponse, select: str) -> HttpResponse:
    """
    Apply the HX-Reselect attribute to the HttpResponse object.

    This function adds the HX-Reselect attribute to the HttpResponse object,
    allowing you to specify a CSS selector to choose which part of the response
    will be swapped in. This attribute overrides an existing hx-select attribute
    on the triggering element.

    Args:
    - response: HttpResponse object to be modified.
    - select: A CSS selector indicating which part of the response to use for swapping.

    Returns:
    - Modified HttpResponse object with the HX-Reselect attribute set.

    Reference:
    - HX-Reselect: A CSS selector that allows you to choose which part of the response
      is used to be swapped in. Overrides an existing hx-select on the triggering element.
    """
    response["HX-Reselect"] = select
    return response


# A merge input can be any JSON string format or a python iterable or mapping
MergeInput: TypeAlias = str | Mapping[str, Any] | Iterable[str] | None


def events_to_dict(ev: MergeInput) -> dict[str, Any]:
    """Convert the MergeInput object to a dict, with empty values as needed"""

    def to_dict(itr: Iterable, values="") -> dict[str, Any]:
        """return a dict with keys == itr and all(values==values)"""
        return {k: "" for k in (str(s).strip() for s in itr) if k not in ("", None)}

    # If ev is a json string, load it and then convert result.
    if isinstance(ev, str):
        try:
            ev = json.loads(ev)
        except json.JSONDecodeError:
            pass
    # convert ev to a dict where keys are the event names, with empty values as needed.
    match ev:
        case str():
            # is str input was not valid JSON, it must be a comma-sep list of tokens
            return to_dict(ev.split(","))
        case _ if isinstance(ev, Mapping):
            return dict(ev)
        case _ if isinstance(ev, Iterable):
            return to_dict(ev)
        case None:
            return {}
        case _:
            raise ValueError(f"Unexpected event type: {type(ev)} ({ev})")


def merge_events(events: MergeInput, new_events: MergeInput) -> str:
    """
    Merge events and new events into a single JSON string
    Events with the same name / key will have their event detail updated

    Args:
    - events (MergeInput) : Typically existing events found in response.headers['HX-Trigger'].
    - new_events (MergeInput): Typically new events added by modify_htmx_response.
    Returns:
    - str: Merged events as a JSON string, typically to be set in response.headers['HX-Trigger'].
    """
    merged = {**events_to_dict(events), **events_to_dict(new_events)}
    if any(merged.values()):  # at least one event has a detail
        return json.dumps(merged)
    else:
        return ",".join(merged.keys())


def retrigger(
    response: HttpResponse, after: str | None = None, events: str | list | dict | None = None
) -> HttpResponse:
    """
    Apply the HX-Trigger attribute to the HttpResponse object.

    https://htmx.org/headers/hx-trigger/

    This response headers can be used to trigger client side actions on the target element within a response to htmx.
    You can trigger a single event or as many uniquely named events as you would like.

    Args:
    - after: ('settle', 'swap', None). Defaults to None. Specify when the event should be triggered.
    - events: (str, list, dict, None). Defaults to None. The value to add to the response header.
                Can be a single event, a list of events,
                or a dictionary containing the event name and any key-values accessed by event.detail.key
    """
    header = f"HX-Trigger{f'-After-{after.capitalize()}' if after else ''}"
    existing_value = response.get(header)

    response[header] = merge_events(existing_value, events)
    return response


def htmx_redirect(to, *args, **kwargs) -> HttpResponse:
    return HttpResponseClientRedirect(to, *args, **kwargs)


def htmx_refresh() -> HttpResponse:
    return HttpResponseClientRefresh()


queue_poll_messages = lambda request: modify_htmx_response(request, {"retrigger": {"events": "pollMsg"}})


def modify_htmx_response(request, htmx_funcs) -> HttpRequest:
    # Check if "functions_to_process" attribute already exists
    if hasattr(request, "functions_to_process"):
        # Update the existing attribute
        ftp = getattr(request, "functions_to_process")
        ftp.update(htmx_funcs)
        htmx_funcs = ftp
    # Set the attribute
    setattr(request, "functions_to_process", htmx_funcs)
    return request


def _request_configures_response(request):
    """Request provides configuration to modify the HTMX response.
    :param request: The request object
    :param config: dict: configuration of functions to modify HX response headers passed by request.GET

    Example:
    <tag
        id="requesting-element"
        hx-get="/api/endpoint">
        hx-vals="{'config': {"retrigger": {"events": {"reloadChoices": {"target": "#target-element"}}}}}"
    >
    </tag>
    # The requesting element specifies that the reloadChoices event should be fired
    # on the target element after returning its own response.
    This enables cascading updates and decouples response customization from the core view logic,
    improving reusability and flexibility by moving it to the form field instance.
    """
    config = request.GET.get("config")
    try:
        config = json.loads(config)
    except (json.JSONDecodeError, TypeError):
        config = None
    return modify_htmx_response(request, config) if config else request


def process_htmx_response(response: HttpResponse, functions_to_process: dict) -> HttpResponse:
    """
    Process the response with a dictionary of functions.

    Args:
    - response: HttpResponse object to process.
    - functions_to_process: A dictionary where keys are function names and values are their arguments.
                            default is [django-htmx.http]
                                (https://github.com/adamchainz/django-htmx/blob/main/src/django_htmx/http.py) functions

    Returns:
    - Modified HttpResponse object after applying all specified functions.

    Usage:
    response = HttpResponse()
    functions_to_process = {
        # Assumes function is in default module 'django_htmx', example passes argument positionally
        'reselect': 'some_value',
        # Custom module and function, example passes argument list positionally
        'another_module.another_function': ['existing'],
        # Pass arguments as kwargs
        'yet_another_module.yet_another_function': {'arg1': 'existing'},
        # Add more function names and their arguments here
    }
    response = process_htmx_response(response, functions_to_process)
    """
    for func_name, args in functions_to_process.items():
        if "." in func_name:
            module_name, func_name = func_name.rsplit(".", 1)
        else:
            module_name = __name__

        # Try to find the function in the specified module
        spec = importlib.util.find_spec(module_name)
        if spec:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        else:
            module = sys.modules[__name__]
        if hasattr(module, func_name):
            func = getattr(module, func_name)
            if isinstance(args, dict):
                # Pass arguments as kwargs
                response = func(response, **args)
            elif isinstance(args, list):
                # Pass arguments positionally
                response = func(response, *args)
            else:
                # Pass single argument positionally
                response = func(response, args)
            continue  # Move to the next function

        # If the function is not found in the current file, raise an error
        raise AttributeError(f"Function '{func_name}' not found in module '{module_name}' or current file")
    return response


def msg_return(
    request, msg: str, status: int = 200, style: str = None, target: str = None, processors: dict = None
) -> HttpResponse:
    """
    Return a rendered inline message template with the given message, style, target, and processors.

    Args:
        request (HttpRequest): The current request.
        msg (str): The message to display in the inline message template.
        status (int, optional): The HTTP status code for the response. Defaults to 200.
        style (str, optional): Additional CSS classes to apply to the inline message template. Defaults to None.
        target (str, optional): The target element to swap the inline message template into. Defaults to None.
        processors (dict, optional): Additional processors to apply to the response. Defaults to {}.

    Returns:
        HttpResponse: The rendered inline message template.
    """
    processors = processors or {}
    context_vars = {}
    if msg:
        context_vars["msg"] = mark_safe(msg)
    if style:
        context_vars["class"] = style
    if target:
        context_vars["swap_target_container"] = target

    modified_processors = {"reswap": "afterbegin"}
    modified_processors.update(processors)

    return render(
        modify_htmx_response(request, modified_processors),
        template_name="include/components/inline_msg.html",
        context=context_vars,
        status=status,
    )
