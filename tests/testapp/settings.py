"""
These settings are NOT actually used!!
They are here in anticipation that one day attachments may be an independent 3rd party app.
"""

import os

DEBUG = True

TESTAPP_DIR = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = "testsecretkey"

if os.environ.get("DJANGO_DATABASE_ENGINE") == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "USER": "postgres",
            "NAME": "attachments",
            "HOST": "localhost",
            "PORT": 5432,
        }
    }
elif os.environ.get("DJANGO_DATABASE_ENGINE") == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "USER": "root",
            "NAME": "attachments",
            "HOST": "127.0.0.1",
            "PORT": 3306,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": "tests_db.sqlite3",
            "TEST": {
                "NAME": None,  # use in-memory test DB
                "MIGRATE": False,  # Django 3.1+ -- disable migrations, create test DB schema directly from models.
            },
        },
    }

DATABASES["default"].update(
    {
        "PASSWORD": os.environ.get("DATABASE_PASSWORD", "testing"),
    }
)

ROOT_URLCONF = "tests.testapp.urls"

INSTALLED_APPS = [
    "nifty_attachments.apps.AttachmentsConfig",
    "tests.testapp.apps.AttachmentsTestappConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
]

MIDDLEWARE = (
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
)

MIDDLEWARE_CLASSES = (
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
)

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(TESTAPP_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

# Configure testapp Attachment settings
ATTACHMENTS_FILE_UPLOAD_VALIDATORS = "tests.testapp.validators.testapp_validators"
