"""Isolated settings for the local backend test suite."""

import os
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

from django.core.exceptions import ImproperlyConfigured

if os.environ.get("DJANGO_SETTINGS_MODULE") != "config.settings.test":
    raise ImproperlyConfigured("Select config.settings.test explicitly.")

# Replace inherited credentials before base settings or provider SDKs read them.
os.environ.update(
    {
        "DJANGO_SECRET_KEY": "erbauer-backend-tests-only-not-a-production-key",
        "DJANGO_DEBUG": "False",
        "CLIENT_IP_SOURCE": "remote_addr",
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_DB_PORT": "55432",
        "POSTGRES_DB": "erbauer_test_control",
        "POSTGRES_USER": "erbauer_test",
        "POSTGRES_PASSWORD": "erbauer_test_only",
        "PGHOST": "127.0.0.1",
        "PGHOSTADDR": "127.0.0.1",
        "PGPORT": "55432",
        "PGDATABASE": "erbauer_test_control",
        "PGUSER": "erbauer_test",
        "PGPASSWORD": "erbauer_test_only",
        "PGSSLMODE": "disable",
        "PGSERVICE": "",
        "PGSERVICEFILE": os.devnull,
        "PGPASSFILE": os.devnull,
        "PGOPTIONS": "",
        "REDIS_URL": "",
        "CELERY_BROKER_URL": "memory://",
        "CELERY_BROKER_READ_URL": "memory://",
        "CELERY_BROKER_WRITE_URL": "memory://",
        "CELERY_RESULT_BACKEND": "",
        "CLOUDINARY_URL": "cloudinary://test-key:test-secret@erbauer-tests",
        "CLOUDINARY_CLOUD_NAME": "erbauer-tests",
        "CLOUDINARY_API_KEY": "test-key",
        "CLOUDINARY_API_SECRET": "test-secret",
        "BREVO_API_KEY": "",
        "DEFAULT_FROM_EMAIL": "sender@example.invalid",
        "COMPANY_CONTACT_EMAIL": "contact@example.invalid",
        "SIMPLE_INVOICE_RECIPIENT_EMAIL": "invoices@example.invalid",
        "CF_TURNSTILE_SITE_KEY": "",
        "CF_TURNSTILE_SECRET_KEY": "",
        "LIBREOFFICE_PATH": "erbauer-tests-must-mock-libreoffice",
        "CACHE_DEFAULT_TIMEOUT": "900",
        **{
            f"{scope}_{option}": value
            for scope in (
                "CONTACT_FORM",
                "VERIFICATION",
                "PASSWORD_RESET",
                "REGISTRATION",
                "LOGIN",
            )
            for option, value in (
                ("ATTEMPTS", "10"),
                ("WINDOW", "120"),
                ("COOLDOWN", "300"),
            )
        },
    }
)

from config.settings.base import *  # noqa: E402,F403

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
SECRET_KEY = "erbauer-backend-tests-only-not-a-production-key"
CLIENT_IP_SOURCE = "remote_addr"
TEST_RUNNER = "config.testing.IsolatedDiscoverRunner"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": "127.0.0.1",
        "PORT": "55432",
        "NAME": "erbauer_test_control",
        "USER": "erbauer_test",
        "PASSWORD": "erbauer_test_only",
        "CONN_MAX_AGE": 0,
        "OPTIONS": {
            "hostaddr": "127.0.0.1",
            "sslmode": "disable",
            "connect_timeout": 5,
        },
        "TEST": {"NAME": "test_erbauer_backend"},
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": f"erbauer-tests-{uuid4().hex}",
    }
}

_redis_mode = os.environ.get("TEST_REDIS_INTEGRATION", "0")
if _redis_mode not in {"0", "1"}:
    raise ImproperlyConfigured("TEST_REDIS_INTEGRATION must be 0 or 1.")
TEST_REDIS_INTEGRATION = _redis_mode == "1"
# Tests opt in with override_settings; the default cache always stays local.
TEST_REDIS_CACHE = {
    "BACKEND": "django.core.cache.backends.redis.RedisCache",
    "LOCATION": "redis://127.0.0.1:56379/0",
    "KEY_PREFIX": f"erbauer:tests:{uuid4().hex}",
    "OPTIONS": {"socket_connect_timeout": 2, "socket_timeout": 2},
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = "sender@example.invalid"
SERVER_EMAIL = DEFAULT_FROM_EMAIL
COMPANY_CONTACT_EMAIL = "contact@example.invalid"
SIMPLE_INVOICE_RECIPIENT_EMAIL = "invoices@example.invalid"
ANYMAIL = {}
ADMINS = []
MANAGERS = []

# The runner replaces this fallback with a unique, managed temporary directory.
MEDIA_ROOT = Path(gettempdir()) / "erbauer-backend-tests"
MEDIA_URL = "/test-media/"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
STATICFILES_STORAGE = STORAGES["staticfiles"]["BACKEND"]
CLOUDINARY = {
    "cloud_name": "erbauer-tests",
    "api_key": "test-key",
    "api_secret": "test-secret",
}
CLOUDINARY_STORAGE = {
    "CLOUD_NAME": "erbauer-tests",
    "API_KEY": "test-key",
    "API_SECRET": "test-secret",
}

CF_TURNSTILE_SITE_KEY = ""
CF_TURNSTILE_SECRET_KEY = ""
CELERY_BROKER_URL = "memory://"
CELERY_BROKER_READ_URL = "memory://"
CELERY_BROKER_WRITE_URL = "memory://"
CELERY_RESULT_BACKEND = None
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_IGNORE_RESULT = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = False
CELERY_BROKER_TRANSPORT_OPTIONS = {}
CELERY_BEAT_SCHEDULE = {}
CELERY_BEAT_SCHEDULER = "celery.beat.PersistentScheduler"
CELERY_REDBEAT_REDIS_URL = None
CELERY_REDBEAT_REDIS_OPTIONS = {}

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
