from pathlib import Path

from dateutil.relativedelta import relativedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
BASE_URL = "http://testserver"

SECRET_KEY = "thissecretkeyisonlyfortests"

DEBUG = False

ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "jasmin_services",
    "jasmin_metadata",
    "jasmin_notifications",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "oauth2_provider",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "tests.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "jasmin_services.wsgi.application"

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


LANGUAGE_CODE = "en-gb"

TIME_ZONE = "Europe/London"

USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = "/static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

JASMIN_SERVICES = {
    "DEFAULT_EXPIRY_DELTA": relativedelta(years=3),
    "NOTIFY_EXPIRE_DELTAS": [
        relativedelta(months=2),
        relativedelta(weeks=2),
        relativedelta(days=2),
    ],
    "JISCMAIL_TO_ADDRS": ["alexander.manning@stfc.ac.uk"],
    "DEFAULT_METADATA_FORM": 1,
    "LDAP_GROUPS": [],
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "oauth2_provider.contrib.rest_framework.OAuth2Authentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "jasmin_django_utils.api.permissions.IsAdminUserOrTokenHasResourceScope"
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "JASMIN Account API",
    "DESCRIPTION": "Account and service data for the jasmin-account portal.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_DIST": "SIDECAR",
    "REDOC_DIST": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
    "OAUTH2_FLOWS": ["clientCredentials"],
    "OAUTH2_AUTHORIZATION_URL": BASE_URL + "/oauth/authorize/",
    "OAUTH2_TOKEN_URL": BASE_URL + "/oauth/token/",
    "AUTHENTICATION_WHITELIST": [
        "oauth2_provider.contrib.rest_framework.OAuth2Authentication",
    ],
    "PREPROCESSING_HOOKS": [
        "jasmin_django_utils.api.hooks.spectacular_hide_admin_auth"
    ],
}
