"""Settings for the Dopamine Detox challenge tracker."""

import datetime as dt
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEV_SECRET_KEY = "dev-only-insecure-key-change-me-in-production"


def load_dotenv(path: Path) -> None:
    """Read KEY=VALUE lines from .env into the environment.

    Real environment variables win, so a shell export overrides the file.
    Written by hand to keep the project dependency-free — hosts like
    PythonAnywhere have no easy way to set env vars for a web app otherwise.
    """
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_date(name: str, default: dt.date) -> dt.date:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        return default


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", DEV_SECRET_KEY)
DEBUG = env_bool("DJANGO_DEBUG", True)

if not DEBUG and SECRET_KEY == DEV_SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY is still the development default while DEBUG is off. "
        "Set a real one in .env — generate it with:\n"
        '  python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"'
    )

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")
    if h.strip()
]
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "tracker",
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

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "tracker.context_processors.challenge",
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
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# People sign in with the email they registered, not a username.
AUTHENTICATION_BACKENDS = [
    "tracker.backends.EmailBackend",
    "django.contrib.auth.backends.ModelBackend",
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "Asia/Dhaka")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "today"
LOGOUT_REDIRECT_URL = "login"

# ---------------------------------------------------------------------------
# The challenge
# ---------------------------------------------------------------------------
CHALLENGE_NAME = os.environ.get("CHALLENGE_NAME", "Dopamine Detox")
CHALLENGE_START = env_date("CHALLENGE_START", dt.date(2026, 9, 11))
CHALLENGE_END = env_date("CHALLENGE_END", dt.date(2027, 1, 11))
CHALLENGE_PRIZE = os.environ.get("CHALLENGE_PRIZE", "10,000")
# A trial run before the real thing: everything works for real, and a banner on
# every page says the data will be wiped. Turn off before the real start date.
CHALLENGE_TEST_MODE = env_bool("CHALLENGE_TEST_MODE", False)
CHALLENGE_REAL_START = env_date("CHALLENGE_REAL_START", dt.date(2026, 9, 11))
CHALLENGE_CURRENCY = os.environ.get("CHALLENGE_CURRENCY", "৳")

# ---------------------------------------------------------------------------
# Security — only applies once DEBUG is off, so local work is unaffected
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "0"))
