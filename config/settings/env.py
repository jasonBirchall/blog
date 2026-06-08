import os

from django.core.exceptions import ImproperlyConfigured


def require_env(key: str) -> str:
    try:
        return os.environ[key]
    except KeyError:
        raise ImproperlyConfigured(f"Missing required environment variable: {key}") from None
