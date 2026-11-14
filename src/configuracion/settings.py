import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


def _parse_csv_env(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip() and item.strip() != "*"]


BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY or SECRET_KEY == "generar-localmente":
    raise ImproperlyConfigured("Falta una DJANGO_SECRET_KEY local válida.")
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = _parse_csv_env("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1", "[::1]"])
CSRF_TRUSTED_ORIGINS = _parse_csv_env("DJANGO_CSRF_TRUSTED_ORIGINS", [])
SECURE_SSL_COOKIES = os.environ.get("DJANGO_SECURE_SSL", "false").lower() == "true"

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "cuentas", "inicio", "residuos",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "configuracion.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "configuracion.wsgi.application"
_POSTGRES_OPTIONS = {"connect_timeout": 5}
_POSTGRES_SSLMODE = os.environ.get("POSTGRES_SSLMODE", "").strip()
if _POSTGRES_SSLMODE:
    _POSTGRES_OPTIONS["sslmode"] = _POSTGRES_SSLMODE

DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": os.environ.get("POSTGRES_DB", "ecometrics"),
    "USER": os.environ.get("POSTGRES_USER", "ecometrics"),
    "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
    "HOST": os.environ.get("POSTGRES_HOST", "db"),
    "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    "OPTIONS": _POSTGRES_OPTIONS,
}}
AUTH_USER_MODEL = "cuentas.Usuario"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "es-pe"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT", "/var/lib/ecometrics/staticfiles"))
WHITENOISE_USE_FINDERS = DEBUG
MEDIA_ROOT = Path(os.environ.get("ECOMETRICS_MEDIA_ROOT", str(BASE_DIR / ".private" / "evidencias")))

_AZURE_STORAGE_CONN = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "").strip()
if _AZURE_STORAGE_CONN:
    _DEFAULT_STORAGE = {
        "BACKEND": "storages.backends.azure_storage.AzureStorage",
        "OPTIONS": {
            "connection_string": _AZURE_STORAGE_CONN,
            "azure_container": os.environ.get("AZURE_STORAGE_CONTAINER", "evidencias"),
            "azure_ssl": True,
            "expiration_secs": 3600,
            "overwrite_files": False,
        },
    }
else:
    _DEFAULT_STORAGE = {"BACKEND": "django.core.files.storage.FileSystemStorage"}

STORAGES = {
    "default": _DEFAULT_STORAGE,
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedStaticFilesStorage"
        ),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = SECURE_SSL_COOKIES
CSRF_COOKIE_SECURE = SECURE_SSL_COOKIES
X_FRAME_OPTIONS = "DENY"
LOGIN_URL = "login"
LOGOUT_REDIRECT_URL = "login"
