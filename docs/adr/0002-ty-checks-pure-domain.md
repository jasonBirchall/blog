# ADR-0002: ty type-checks the pure domain; Django ORM access is suppressed via scoped overrides

- Status: Accepted
- Date: 2026-06-10

## Context

The constitution mandates two things that are currently in tension:

- **`ty`** (Astral's type checker) must pass in CI.
- **Django 5** is the web framework, and SQLite-backed models are the
  persistence layer.

`ty` has no Django ORM support. Django injects managers (`Model.objects`),
related managers (`post.tags.add/.all`), and field descriptors dynamically via
its model metaclass, and exposes queryset methods through `from_queryset`. None
of this is statically visible, so `ty` reports false positives wherever the ORM
is touched:

- `Post.objects` → *unresolved-attribute*
- `post.tags.add(...)` → *unresolved-attribute*
- `self.slug` inside a method → typed as `SlugField`, not `str`

This appears in models, the ORM-exercising tests, and (soon) every view and
service that runs a query. A naive response — globally downgrading
`unresolved-attribute` — would hide genuine typos in the pure domain too.

## Decision

Keep `ty` mandatory and lean into the ports-&-adapters split:

1. **The pure domain is fully type-checked.** Framework-free modules
   (`blog/enums.py`, `blog/tags.py`, and the coming frontmatter parser, markdown
   renderer, and wikilink resolver) import no Django and get `ty`'s full
   scrutiny. This is where types carry the most value.
2. **Prefer a runtime-safe fix over suppression when it's cheap** — e.g.
   `return str(self.slug)` in a model `__str__`, which satisfies `ty` and is a
   no-op at runtime.
3. **Otherwise, suppress narrowly.** Use `[[tool.ty.overrides]]` to set the
   specific rule (`unresolved-attribute`) to `ignore` for the specific
   Django-coupled paths — currently `tests/integration/**`. Expand the `include`
   globs as ORM access reaches views/services. Never suppress globally, and
   never suppress a rule other than the one Django actually breaks.

## Consequences

- The domain/adapter boundary is reinforced by the tooling: the domain is
  strictly typed; the thin Django adapter is where we accept `ty`'s blind spots.
- Static attribute checking is lost on the suppressed paths. This is acceptable
  because those paths are exercised by tests that run for real — `pytest` (and
  Django's own `check`) catch the typos `ty` no longer can.
- The override `include` list will grow over time. Each addition is a small,
  reviewable change, and this ADR is its rationale.
- The risk is over-scoping a suppression and silently losing safety, so scopes
  stay narrow and per-rule.
- Reversible: when `ty` gains Django support (a plugin or stubs), delete the
  overrides and the `str()` shims and this ADR is superseded.
