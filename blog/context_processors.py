"""Template context processors."""

from django.conf import settings
from django.http import HttpRequest


def site(request: HttpRequest) -> dict[str, str]:
    """Expose site metadata to every template."""
    return {"site_name": settings.SITE_NAME, "site_description": settings.SITE_DESCRIPTION}
