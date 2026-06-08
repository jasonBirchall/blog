# ADR-0001: HSTS without preload

- Status: Accepted
- Date: 2026-06-08

## Context

The blog runs behind Caddy, which terminates TLS and serves the site over HTTPS
only. We want HTTP Strict Transport Security (HSTS) so that, after a first
visit, browsers refuse to talk to the site over plain HTTP.

HSTS has an optional `preload` flag. Setting it — and submitting the domain to
hstspreload.org — bakes "HTTPS-only for this domain and all its subdomains"
into the preload lists shipped inside browsers. Removal from those lists is slow
(months) and outside our control. The domain and its subdomains are still
settling: a preview environment exists and future services may need their own
hostnames. A permanent, hard-to-reverse, all-subdomains commitment is therefore
premature.

## Decision

Enable HSTS in production with a one-year `max-age` and `includeSubDomains`, but
leave `preload` off:

    SECURE_HSTS_SECONDS = 31_536_000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False

Silence Django's `security.W021` deploy check, which exists only to nudge toward
preload, so that a genuinely new deploy warning stands out instead of being lost
in expected noise.

## Consequences

- Strong transport security: after one visit, browsers enforce HTTPS for the
  domain and its subdomains for a year, refreshed on every response.
- Reversible: we can shorten `max-age` or drop the header without waiting on the
  browser preload list.
- The residual gap — a first-ever visit over plain HTTP, before any HSTS header
  is seen — is covered by Caddy's HTTP→HTTPS redirect and Django's
  `SECURE_SSL_REDIRECT`.
- If we later decide preload is worth the commitment, it is a one-line change
  plus a submission, and this ADR is superseded by a follow-up.
