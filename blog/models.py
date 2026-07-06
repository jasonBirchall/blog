"""Persistence adapter for content.

The Markdown files under content/ are the source of truth; these rows are a
derived projection synced from them. `kind`/`status` reuse the framework-free
enums so the DB and the parser share one vocabulary.
"""

from datetime import datetime

from django.db import models
from pydantic import ValidationError

from blog.enums import Kind, Status
from blog.wakatime import WakaStats

KIND_CHOICES = [(kind.value, kind.value) for kind in Kind]
STATUS_CHOICES = [(status.value, status.value) for status in Status]


class Tag(models.Model):
    slug = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=50)

    class Meta:
        ordering = ("slug",)

    def __str__(self) -> str:
        return str(self.slug)


class Post(models.Model):
    title = models.CharField(max_length=200)
    # Slugs are globally unique across kinds; URLs are flat (/posts/<slug>).
    slug = models.SlugField(max_length=200, unique=True)
    date = models.DateField()
    updated = models.DateField(null=True, blank=True)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    body_markdown = models.TextField()
    # Per-kind blocks (populated by sync from frontmatter; blank for other kinds).
    link_url = models.URLField(blank=True)
    link_source = models.CharField(max_length=200, blank=True)
    quote_text = models.TextField(blank=True)
    quote_source = models.CharField(max_length=200, blank=True)
    quote_url = models.URLField(blank=True)
    # Derived from body_markdown on sync; left blank until then.
    body_html = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=Status.DRAFT.value)
    # Derived from body_markdown on sync (first paragraph, collapsed).
    excerpt = models.TextField(blank=True)
    # Soft-delete flag: a post whose source file is gone is deactivated, not deleted.
    is_active = models.BooleanField(default=True)
    # Set once the post has been snapshotted to the Wayback Machine.
    archived = models.BooleanField(default=False)
    tags = models.ManyToManyField(Tag, related_name="posts", blank=True)

    class Meta:
        ordering = ("-date", "-id")

    def __str__(self) -> str:
        return f"{self.kind}: {self.title}"


class WakaSnapshot(models.Model):
    """The single latest WakaTime stats snapshot (a derived artefact, pk=1).

    Like the SQLite DB itself, this is derived and ephemeral, never in git. The
    payload is the *re-serialised, validated* WakaStats (never WakaTime's raw
    response), so a poisoned upstream payload cannot lie dormant here; and
    `latest_stats` re-validates through the domain, so even a hand-tampered row
    cannot bypass validation on the way to a template.
    """

    payload = models.TextField()
    fetched_at = models.DateTimeField()

    def __str__(self) -> str:
        return f"WakaSnapshot(fetched_at={self.fetched_at:%Y-%m-%d})"

    @classmethod
    def store(cls, stats: WakaStats, fetched_at: datetime) -> "WakaSnapshot":
        """Upsert the one snapshot row (pk=1), storing the re-serialised model."""
        row, _ = cls.objects.update_or_create(
            pk=1, defaults={"payload": stats.model_dump_json(), "fetched_at": fetched_at}
        )
        return row

    @classmethod
    def latest_stats(cls) -> "tuple[WakaStats, datetime] | None":
        """Return the latest (stats, fetched_at), or None if absent or corrupt."""
        row = cls.objects.filter(pk=1).first()
        if row is None:
            return None
        try:
            return WakaStats.model_validate_json(row.payload), row.fetched_at
        except ValidationError:
            return None
