"""Environment-variable helpers. No silent fallbacks for secrets."""

import os

from django.core.exceptions import ImproperlyConfigured


def require_env(key: str) -> str:
    try:
        return os.environ[key]
    except KeyError:
        raise ImproperlyConfigured(f"Missing required environment variable: {key}") from None


def env_bool(key: str, *, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(key: str, *, default: list[str] | None = None) -> list[str]:
    raw = os.environ.get(key)
    if not raw:
        return default or []
    return [item.strip() for item in raw.split(",") if item.strip()]
