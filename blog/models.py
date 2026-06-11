"""Persistence adapter for content.

The Markdown files under content/ are the source of truth; these rows are a
derived projection synced from them. `kind`/`status` reuse the framework-free
enums so the DB and the parser share one vocabulary.
"""

from django.db import models

from blog.enums import Kind, Status

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
    tags = models.ManyToManyField(Tag, related_name="posts", blank=True)

    class Meta:
        ordering = ("-date", "-id")

    def __str__(self) -> str:
        return f"{self.kind}: {self.title}"
