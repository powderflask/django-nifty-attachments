# django-nifty-attachments


[![PyPI Version](https://img.shields.io/pypi/v/django-nifty-attachments.svg)](https://pypi.python.org/pypi/django-nifty-attachments) [![Test with pytest](https://github.com/actions/workflows/pytest.yaml/badge.svg)](https://github.com/powderflask/django-nifty-attachments/tree/main/.github/workflows/pytest.yaml/badge.svg) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/powderflask/django-nifty-attachments)


Version: 0.1.0

*"Private" file attachments for a Django Model, with permissions-based access control and without Generic FK.*

> django-nifty-attachments is free software distributed under the MIT License.



## Adaptations:

Re-wrote app top-to-bottom to accommodate HN use-cases.

1. Removed support for python2 & django<3, delete migrations, delete locale, delete admin, delete management command
2. Remove Generic FK to "related object" , replace with "Model Factory" pattern,
   using Abstract Model and dependency inversion instead.
3. Provide injectable permissions
4. Implement "app settings" pattern


Installation:
=============

1. Put `attachments` to your `INSTALLED_APPS` in your `settings.py`
   within your django project (to auto-detect templates and tags):
    ```
    INSTALLED_APPS = (
        ...
        'attachments',
    )
    ```

   2. Define a concrete Attachment model with relation to your related object:
       ```
       class GizmoAttachment(AbstractAttachment.factory("myapp.Gizmo")):
           """ A concrete implementation of AbstractAttachment,
                with a required FK named `related` to Gizmo with revers relation "attachment_set"
           """
       ```

3. Add the attachments urlpattern to your `urls.py`, injecting your concrete attachment model:
    ```
    path(r'^gizmo/attachments/',
         include('attachments.urls', namespace='gizmo-attachments', kwargs=dict(model='myapp.GizmoAttachment')),
    ```

4. Migrate your database:
    ```
    ./manage.py migrate
    ```

5. Grant the user some permissions:

   * For **viewing / downloading attachments** grant the user (or group) the permission
     `gizmo.view_attachment`.

   * For **adding attachments** grant the user (or group) the permission
     `gizmo.add_attachment`.

   * For **updating attachments** grant the user (or group) the permission
     `gizmo.change_attachment`.

   * For **deleting own attachments** grant the user (or group) the permission
     `gizmo.delete_attachment`. This allows the user to delete their own
     attachments only.

   * For **updating or deleting any attachments** (including attachments by other users) grant
     the user the permission `gizmo.edit_any_attachment`.


Settings
========

* `ATTACHMENTS_FILE_UPLOAD_MAX_SIZE` The maximum upload file size in Mb.
   Default: `10 Mb`.   Set to `None` for no restriction on file size.

* `ATTACHMENTS_CONTENT_TYPE_WHITELIST` A tuple of http content type strings to allow for upload.
  Default: `()`.   Set to `()` for no restriction on content type.


Configuration
=============

* configure file upload validators:
  * define an iterable of `Callable[[File], ]`;
    Validators execute against uploaded `File`. Raise a `ValidationError` to deny the upload.
  * configure setting `ATTACHMENTS_FILE_UPLOAD_VALIDATORS` equal to the iterable or a dotted path to it.
    E.g.  `ATTACHMENTS_FILE_UPLOAD_VALIDATORS = "attachments.validators.default_validators"`
  * For custom validators on different Concrete Attachment types, inject custom `form_class` to add view.

* configure permissions: implement the interface defined by `AttachmentPermissionsApi`
  and set `permissions = MyAttachmentsPermissions()` on your concrete Attachment Model.


Tests
=====

Run the testsuite in your local environment using `pipenv`:

    $ cd django-attachments/
    $ pipenv install --dev
    $ pipenv run pytest attachments/


Usage:
======

In your models:
---------------

You must explicitly define a Concrete Attachments model for each related model.
1. use the `factory` method on `AbstractAttachment` to create a base model with a FK to your `related_model`
2. extend this abstract base class, you can add or override any behaviours you like.
3. if you provide a custom `Meta` options, it is highly recommended you extend the base Meta.

    ```
    class GizmoAttachment(AbstractAttachment.factory("myapp.Gizmo"):
        ...
        class Meta(base_model.Meta)
            ...
    ```

You can also inject custom permissions logic with any class that implements `AttachmentPermissions` Protocol.

    ```
    class GizmoPermissions(DefaultAttachmentPermissions):

        def can_add_attachments(self, user: User, related_to: "Gizmo") -> bool:
            """ Return True iff the user can upload new attachments to the given Gizmo """
            return gizmo.permissions.can_change(user, related_to) and super().can_add_attachments(user, related_to)

    base_model = AbstractAttachment.factory(
        related_model = "myapp.Gizmo",
        permissions_class = GizmoPermissions
    )
    class GizmoAttachment(base_model):
        ...

    ```

In your urls:
-------------

You need to run one namespaced instance of the attachments app for each concrete Model.
* Include the `attachments.urls`, supplying an explicit namespace *if your app urls are not namespaced*.
* Inject your concrete Attachment Model, either the Model class or an `app_label.ModelName` string.

    ```
    path('gizmo/attachments/',
         include('attachments.urls', namespace='gizmo-attachments'),
                 kwargs=dict(model='myapp.GizmoAttachment')),
    ```

To use distinct templates for a specific concrete Attachment type, either
* copy in a url from `attachments.urls`, adding a `template_name` kwarg, to customize an individual view; or
* add at `template_prefix` kwarg to the path include with a template path prefix.

    ```
    path('gizmo/attachments/',
         include('attachments.urls', namespace='gizmo-attachments'),
                 kwargs=dict(model='myapp.GizmoAttachment', template_prefix='gizmo/')),
    ```

Also, inject `form_class` to `create` and `update` views,
e.g., to customize validation logic for each Concrete Attachment type


In your templates:
------------------

Load the `attachments_tags`:

    {% load attachments_tags %}

django-attachments comes with some templatetags to add or delete attachments
for your model objects in your frontend.

1. `get_attachments_for [object]`: Fetches the attachments for the given
   model instance. You can optionally define a variable name in which the attachment
   list is stored in the template context (this is required in Django 1.8). If
   you do not define a variable name, the result is printed instead.

    {% get_attachments_for entry as attachments_list %}

2. `attachments_count [object]`: Counts the attachments for the given
   model instance and returns an int:

    {% attachments_count entry %}

3. `attachment_form`: Renders a upload form to add attachments for the given
   model instance. Example:

    {% attachment_form [object] %}

   It returns an empty string if the current user is not logged in.

4. `attachment_delete_link`: Renders a link to the delete view for the given
   *attachment*. Example:

    {% for att in attachments_list %}
        {{ att }} {% attachment_delete_link att %}
    {% endfor %}

   This tag automatically checks for permission. It returns only a html link if the
   give n attachment's creator is the current logged in user or the user has the
   `delete_foreign_attachments` permission.

Quick Example:
==============

    {% load attachments_tags %}
    {% get_attachments_for entry as my_entry_attachments %}

    <span>Object has {% attachments_count entry %} attachments</span>
    {% if my_entry_attachments %}
    <ul>
    {% for attachment in my_entry_attachments %}
        <li>
            <a href="{{ attachment.attachment_file.url }}">{{ attachment.filename }}</a>
            {% attachment_delete_link attachment %}
        </li>
    {% endfor %}
    </ul>
    {% endif %}

    {% attachment_form entry %}

    {% if messages %}
    <ul class="messages">
    {% for message in messages %}
        <li{% if message.tags %} class="{{ message.tags }}"{% endif %}>
            {{ message }}
        </li>
    {% endfor %}
    </ul>
    {% endif %}

Settings
========

- `DELETE_ATTACHMENTS_FROM_DISK` will delete attachment files when the
  attachment model is deleted. **Default False**!
- `FILE_UPLOAD_MAX_SIZE` in bytes. Deny file uploads exceeding this value.
  **Undefined by default**.
- `AppConfig.attachment_validators` - a list of custom form validator functions
  which will be executed against uploaded files. If any of them raises
  `ValidationError` the upload will be denied. **Empty by default**. See
  `attachments/tests/testapp/apps.py` for an example.


---
### Acknowledgments
This project would be impossible to maintain without the help of our generous [contributors](https://github.com//graphs/contributors)

#### Technology Colophon

Without django and the django dev team, the universe would have fewer rainbows and ponies.

This package was originally created with [`cookiecutter`](https://www.cookiecutter.io/) 
and the [`cookiecutter-powder-pypackage`](https://github.com/JacobTumak/CookiePowder) project template.

---

## Developing?
Check out the [Dev Guide](https://github.com/powderflask/django-nifty-attachments/tree/main/dev-guide.md).

 * [GitHub Actions](https://docs.github.com/en/actions) (see [.github/workflows](https://github.com/powderflask/django-nifty-attachments/tree/main/.github/workflows))
