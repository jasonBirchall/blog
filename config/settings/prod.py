"""Production settings: hardened for HTTPS behind Caddy.

DEBUG and ALLOWED_HOSTS come strictly from the environment via base.
"""

from .base import *

# Caddy terminates TLS and proxies over HTTP; trust its forwarded-proto header
# so Django knows the original request was secure.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True

# Cookies only over HTTPS, never readable by JS, conservative on cross-site.
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

# HSTS: one year, include subdomains, no preload (reversible — see ADR/decision).
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False

# Preload is a deliberate, reversible no (decision: don't get stuck in the
# browser preload list). Silence the matching deploy warning so a genuinely new
# one stands out instead of being lost in expected noise.
SILENCED_SYSTEM_CHECKS = ["security.W021"]

# Defensive response headers.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
