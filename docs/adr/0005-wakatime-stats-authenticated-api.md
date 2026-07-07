# ADR-0005: WakaTime stats via the authenticated API, key on the box

- Status: Accepted
- Date: 2026-07-07

## Context

The `/now` page shows the last seven days of coding activity — languages,
projects, total time, daily average — fetched from WakaTime. Two mechanisms
could supply it:

- **Embeddable share URLs.** Keyless: a unique, retractable URL exposing only
  what the share is configured to show. WakaTime's own recommendation for
  public display. But embeds start from _yesterday_, use the default
  15-minute keystroke timeout rather than the account preference, and the
  language embed has historically returned percentages without absolute
  times — so covering all four stats would mean several embeds of differing
  fidelity, or dropping requirements.
- **The authenticated `stats/last_7_days` endpoint.** One call, full
  fidelity, exactly the numbers the dashboard shows — at the price of a
  long-lived credential on the box and a response scoped to the whole
  account, not a curated share.

The data is also ephemeral by nature. It must not flow through git (the
deploy's `verify-commit` gate exists precisely so nothing lands on `main`
unsigned, and a daily stats bot would either defeat that gate or pollute
history), and `content/` is the source of truth for prose, not telemetry.

A spike against the real endpoint surfaced two facts that shaped the design:
the response carries roughly two dozen keys per project, including AI-spend
telemetry (token counts, per-model dollar costs, human-vs-AI line counts)
that must never reach the database or a template; and the account's
visibility settings do not filter what the owner's own key sees.

## Decision

**Fetch with the personal API key; treat the response as hostile; keep the
data out of git.**

1. A daily user-scope timer (`blog-wakatime.timer`) runs a one-shot container
   executing `sync_wakatime`, decoupled from the deploy timer — stats refresh
   whether or not `main` moves. The key is the `wakatime_api_key` podman
   secret (sops-encrypted at rest, per ADR-0004), exposed only to the
   one-shot, never to the long-running app, never in argv or logs.
2. The response is parsed at the boundary by a pure-domain module
   (`blog/wakatime.py`, fully ty-checked): a tolerant wire layer keeps only
   `name`/`percent`/`total_seconds` per item — discarding the AI-spend
   telemetry by construction — and a strict frozen domain layer bounds every
   field. The stored row is the re-serialised validated model, never the raw
   response, and is re-validated on the way back out, so neither a poisoned
   payload nor a hand-tampered row reaches a template. Rendering uses
   Django's default auto-escaping only.
3. Because visibility settings do not filter the authenticated response,
   project curation is code-side: `parse_stats` filters a `hidden_projects`
   deny-list _before_ the domain models are built, so a hidden name never
   touches the database.
4. Failure degrades to staleness, not breakage: a failed sync leaves the
   previous snapshot serving under an honest "as of" date. Freshness is
   surfaced by a `wakatime_last_success_timestamp_seconds` gauge written to
   the node_exporter textfile collector on success only; the `WakaTimeStale`
   rule fires past 48 hours (tolerating one missed daily run).

## Consequences

- Full-fidelity stats with no new dependency (stdlib `urllib`, injected fetch
  as in `blog/snapshots.py`) and no new scrape target.
- The box gains one outbound HTTPS endpoint, `api.wakatime.com`. The box has
  no egress policy; adding one is a possible future hardening, out of scope
  here.
- The key's blast radius on leak is read access to the full WakaTime account
  plus the ability to submit fake heartbeats. Mitigations: podman secret,
  tailnet-only box, runbook rotation (no app restart — the one-shot reads the
  secret fresh each run). Residual: a root-level box compromise reads the
  secret; that adversary already owns the site. Accepted.
- Publishing weekly aggregates (no timestamps, no per-day series) is a
  deliberate dampener on work-pattern inference; the deny-list is the control
  for project-name exposure and needs curating as employment changes.
- Reversible: switching to embed URLs later deletes the secret from the box
  and swaps the fetch, leaving the domain, storage, template, and alerting
  untouched — at which point this ADR is superseded.
