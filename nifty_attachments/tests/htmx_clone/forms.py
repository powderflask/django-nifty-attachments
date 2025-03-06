import logging
from typing import Any

from django import forms
from django.forms.widgets import Select

logger = logging.getLogger(__name__)

# DEFAULTS
# any of these attrs can be overriden or appended to in the form field init
DYNAMIC_HX_CHOICE_FIELD_ATTRS = {
    # the url to load choices from
    # set via init parameter
    "hx-get": None,
    # the element to swap in the new choices
    # use outerHTML if 'selector' context var is used in form_choices.html
    "hx-swap": "innerHTML",
    # all inputs with this class will be included in the request for choices
    # overriden by dependent fields
    "hx-include": ".dynamic-choice",
    # dependent fields will override this to subscribe the change of choices from that input
    "hx-trigger": "change from:previous select.dynamic-choice",
    "hx-indicator": "previous label",
    "data-hn-tooltip": "Click to load available options. When a selection is changed, dependent choices will be \
                        reloaded with the correct options.",
    "script": "on htmx:afterRequest from me add [@selected] to <option:nth-child(0) /> in me end",
    "class": "dynamic-choice",
}


def union_tokens(*tokens: str, sep: str = None) -> str:
    """return a string with unique tokens from all sep-separated input strings"""
    tokens = {t for s in tokens for t in s.split(sep)}
    sep = sep or " "
    return sep.join(tokens)


class DynamicHXSelectWidget(Select):
    option_inherits_attrs = False

    def __init__(self, css_class="dynamic-choice", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs["class"] = union_tokens(self.attrs.get("class", ""), css_class)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        # Add custom attributes to the option element
        option_attrs = attrs.copy() if attrs else {}
        # disables default hx-trigger behavior "click/change" as the trigger is from another elements change
        option_attrs["hx-disable"] = "true"

        return super().create_option(name, value, label, selected, index, subindex, option_attrs)


def is_not_none(value: Any) -> bool:
    """Return True iff value is not None without evaluating value in case it is a Promise or other lazy eval obj."""
    return not (isinstance(value, str) and value == "") and not isinstance(value, type(None))


def get_hx_select_widget(
    choice_url: str, dependency_fields: list[str] = None, widget_attrs: dict[str, str] = None, **kwargs
) -> DynamicHXSelectWidget:
    default_field_attrs = DYNAMIC_HX_CHOICE_FIELD_ATTRS.copy()
    default_field_attrs["hx-get"] = choice_url  # required for widget to work
    if dependency_fields:
        default_field_attrs["hx-trigger"] = ", ".join(
            [f"change from:{dependency}" for dependency in dependency_fields]
        )
        default_field_attrs["hx-include"] = ", ".join([f"{dependency}" for dependency in dependency_fields])
        # cascade dependent fields so correct values are in hx-include
        default_field_attrs["hx-sync"] = "closest form:queue"
    if not kwargs.get("choices"):
        # get initial choices via trigger if none given
        default_field_attrs["hx-trigger"] = default_field_attrs["hx-trigger"] + ", click once"

    return DynamicHXSelectWidget(attrs=dict(default_field_attrs or {}, **widget_attrs))


class DynamicHXChoiceField(forms.ChoiceField):
    """
    ChoiceField that uses htmx to populate the choices dynamically upon selection of adjacent form inputs.
    The widget is a Select widget with custom attributes to load the choices on the given field.
    The field validates choices against the current choices, and adds new choices if the 'allow_new_choices' is True.
    Allowing new choices is required, otherwise,
    the field will raise a ValidationError if the full list of choices isn't initially provided
    :param allow_new_choices: Allow dynamic choices to be added as a valid choice for form.clean, or raise an error
    :param choice_url: The URL to load the choices from. Should be a Django URL that accepts a GET request,
                        and returns an htmx response to swap in a new <select> or <ul>.
    :param: widget: Default is DynamicHXSelectWidget. Can be overridden to use a different widget
    :param dependency_fields: A list of fields, given as query selectors,
                              that should be watched for changes and include in API requests.
    :param widget_attrs: Additional attributes to pass to the widget. This can include any of the htmx attributes,
                            as well as any other HTML attributes that the widget may accept.
    """

    def __init__(
        self, *args, allow_new_choices=True, choice_url=None, dependency_fields=None, widget_attrs=None, **kwargs
    ):
        if is_not_none(choice_url):
            self.allow_new_choices = allow_new_choices
            kwargs.setdefault(
                "widget", get_hx_select_widget(choice_url, dependency_fields or [], widget_attrs or {}, **kwargs)
            )
        else:
            logger.debug("No URL provided for HXChoiceField")  # Dev choice to instantiate fields as regular Select

        super().__init__(*args, **kwargs)

    def validate(self, value):
        """
        Validate that the input is in self.choices, or add it dynamically if allowed.
        """
        if self.allow_new_choices and value not in dict(self.choices):
            # Dynamically add the new choice
            self.choices = list(self.choices) + [(value, value)]
        super().validate(value)
