"""Specs for the production security posture (config/settings/prod.py).

These assert the hardening that only applies in production (TLS behind Caddy),
so they read the module directly rather than going through the test settings.
"""

from config.settings import prod


class DescribeProductionSecurity:
    def it_trusts_caddys_forwarded_proto_and_forces_https(self) -> None:
        assert prod.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
        assert prod.SECURE_SSL_REDIRECT is True

    def it_locks_down_session_and_csrf_cookies(self) -> None:
        assert prod.SESSION_COOKIE_SECURE is True
        assert prod.SESSION_COOKIE_HTTPONLY is True
        assert prod.CSRF_COOKIE_SECURE is True

    def it_enables_hsts_for_a_year_with_subdomains_but_no_preload(self) -> None:
        assert prod.SECURE_HSTS_SECONDS == 31_536_000
        assert prod.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
        assert prod.SECURE_HSTS_PRELOAD is False
        # The deliberate no-preload choice silences exactly its own deploy warning.
        assert prod.SILENCED_SYSTEM_CHECKS == ["security.W021"]

    def it_sets_defensive_response_headers(self) -> None:
        assert prod.SECURE_CONTENT_TYPE_NOSNIFF is True
        assert prod.X_FRAME_OPTIONS == "DENY"
