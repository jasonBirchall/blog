"""Local development settings."""

from .base import *

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# Plain (un-hashed) static storage in dev so {% static %} resolves without a
# collected manifest; the compressed-manifest storage is prod-only.
STORAGES = {
    **STORAGES,
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
