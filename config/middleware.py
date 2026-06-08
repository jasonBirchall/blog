"""Project-level middleware."""

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse


class XRobotsTagMiddleware:
    """Mark every response noindex/nofollow when running as the preview env.

    The flag is read per-request so `override_settings(IS_PREVIEW=True)` works in
    tests; the cost is a single attribute lookup.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self._get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self._get_response(request)
        if settings.IS_PREVIEW:
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response
