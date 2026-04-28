import os
from pathlib import Path
from dotenv import load_dotenv
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
DEBUG = os.getenv("DJANGO_DEBUG", "") != "False"
ALLOWED_HOSTS = ["127.0.0.1"]

INSTALLED_APPS = [
    "core",
    "main.apps.MainConfig",
    "user",
    "account",
    "anymail",
    "crispy_forms",
    "crispy_bootstrap5",
    "cloudinary",
    "cloudinary_storage",
    "debug_toolbar",
    "modeltranslation",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_cleanup.apps.CleanupConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "main.context_processors.company_base",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "en"
LANGUAGES = [
    ("uk", _("Ukrainian")),
    ("en", _("English")),
]
TIME_ZONE = "UTC"

LOCALE_PATHS = [
    BASE_DIR / "locale",
]

USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


AUTH_USER_MODEL = "user.User"
LOGIN_REDIRECT_URL = "/"

# Debug-toolbar
INTERNAL_IPS = [
    "127.0.0.1",
]

# Crispy-forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Email
EMAIL_BACKEND = "anymail.backends.brevo.EmailBackend"
ANYMAIL = {
    "BREVO_API_KEY": os.getenv("BREVO_API_KEY"),
}
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL")

COMPANY_CONTACT_EMAIL = os.getenv("COMPANY_CONTACT_EMAIL")

# Contact form rate limit
CONTACT_FORM_ATTEMPTS = int(os.getenv("CONTACT_FORM_ATTEMPTS", 10))
CONTACT_FORM_WINDOW = int(os.getenv("CONTACT_FORM_WINDOW", 120))
CONTACT_FORM_COOLDOWN = int(os.getenv("CONTACT_FORM_COOLDOWN", 300))

# services/rate_limits/resend_verification
VERIFICATION_ATTEMPTS = int(os.getenv("VERIFICATION_ATTEMPTS", 10))
VERIFICATION_WINDOW = int(os.getenv("VERIFICATION_WINDOW", 120))
VERIFICATION_COOLDOWN = int(os.getenv("VERIFICATION_COOLDOWN", 300))

# services/rate_limits/password_reset
PASSWORD_RESET_ATTEMPTS = int(os.getenv("PASSWORD_RESET_ATTEMPTS", 10))
PASSWORD_RESET_WINDOW = int(os.getenv("PASSWORD_RESET_WINDOW", 120))
PASSWORD_RESET_COOLDOWN = int(os.getenv("PASSWORD_RESET_COOLDOWN", 300))

# services/rate_limits/registration
REGISTRATION_ATTEMPTS = int(os.getenv("REGISTRATION_ATTEMPTS", 10))
REGISTRATION_WINDOW = int(os.getenv("REGISTRATION_WINDOW", 120))
REGISTRATION_COOLDOWN = int(os.getenv("REGISTRATION_COOLDOWN", 300))

# services/rate_limits/login
LOGIN_ATTEMPTS = int(os.getenv("LOGIN_ATTEMPTS", 10))
LOGIN_WINDOW = int(os.getenv("LOGIN_WINDOW", 120))
LOGIN_COOLDOWN = int(os.getenv("LOGIN_COOLDOWN", 300))

# Cloudflare Turnstile captcha services/turnstile
CF_TURNSTILE_SITE_KEY = os.getenv("CF_TURNSTILE_SITE_KEY", "")
CF_TURNSTILE_SECRET_KEY = os.getenv("CF_TURNSTILE_SECRET_KEY", "")

# Cache
CACHE_DEFAULT_TIMEOUT = int(os.getenv("CACHE_DEFAULT_TIMEOUT", 900))
