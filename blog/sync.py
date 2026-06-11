"""Sync content/ Markdown into the database.

Where the pure domain meets Django: validate first (reusing the content linter),
then upsert every post inside one transaction, so a bad post can never leave the
database half-written. Files that have vanished mark their posts inactive (a soft
delete, never destructive). Derived fields (body_html, excerpt) are regenerated.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from django.db import transaction

from blog.enums import Status
from blog.frontmatter import parse_document
from blog.linting import LintError, lint_content
from blog.models import Post, Tag
from blog.rendering import render_markdown
from blog.tags import derive_tag_name
from blog.wikilinks import SlugIndex

_EXCERPT_LIMIT = 280


@dataclass(frozen=True)
class SyncReport:
    errors: list[LintError] = field(default_factory=list)
    created: int = 0
    updated: int = 0
    deactivated: int = 0
    wrote: bool = False


def read_documents(content_dir: Path) -> dict[str, str]:
    return {
        str(path.relative_to(content_dir)): path.read_text(encoding="utf-8")
        for path in sorted(content_dir.rglob("*.md"))
    }


def _excerpt(body: str) -> str:
    collapsed = " ".join(body.strip().split("\n\n", 1)[0].split())
    if len(collapsed) <= _EXCERPT_LIMIT:
        return collapsed
    return collapsed[:_EXCERPT_LIMIT].rstrip() + "..."


def _render_html(body: str, index: SlugIndex) -> str:
    return render_markdown(body, slug_index=index)


def _ensure_tags(slugs: Iterable[str]) -> list[Tag]:
    return [
        Tag.objects.get_or_create(slug=slug, defaults={"name": derive_tag_name(slug)})[0]
        for slug in slugs
    ]


def sync_content(
    documents: Mapping[str, str], vocabulary: Iterable[str], *, write: bool
) -> SyncReport:
    """Validate content and, when write=True and clean, upsert it transactionally."""
    errors = lint_content(documents, vocabulary)
    if errors or not write:
        return SyncReport(errors=errors)

    parsed = {path: parse_document(text) for path, text in documents.items()}
    index = {
        doc.frontmatter.slug: doc.frontmatter.title
        for doc in parsed.values()
        if doc.frontmatter.status == Status.PUBLISHED
    }

    created = updated = 0
    seen: set[str] = set()
    with transaction.atomic():
        for doc in parsed.values():
            frontmatter = doc.frontmatter
            post, was_created = Post.objects.update_or_create(
                slug=frontmatter.slug,
                defaults={
                    "title": frontmatter.title,
                    "date": frontmatter.date,
                    "kind": frontmatter.kind.value,
                    "body_markdown": doc.body,
                    "body_html": _render_html(doc.body, index),
                    "excerpt": _excerpt(doc.body),
                    "status": frontmatter.status.value,
                    "is_active": True,
                },
            )
            post.tags.set(_ensure_tags(frontmatter.tags))
            seen.add(frontmatter.slug)
            created += int(was_created)
            updated += int(not was_created)
        deactivated = (
            Post.objects.filter(is_active=True).exclude(slug__in=seen).update(is_active=False)
        )

    return SyncReport(
        errors=[], created=created, updated=updated, deactivated=deactivated, wrote=True
    )
