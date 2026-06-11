"""Sitemaps for published posts and the tags actually in use.

URLs are plain strings, so the sitemap is valid before the post/tag views exist
(N4.2/N4.4); the entries resolve once those views land.
"""

import datetime

from django.contrib.sitemaps import Sitemap

from blog.enums import Status
from blog.models import Post, Tag


class PostSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self) -> list[Post]:
        return list(
            Post.objects.filter(is_active=True, status=Status.PUBLISHED.value).order_by(
                "-date", "-id"
            )
        )

    def location(self, item) -> str:
        return f"/posts/{item.slug}"

    def lastmod(self, item) -> datetime.date:
        return item.date


class TagSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.4

    def items(self) -> list[Tag]:
        return list(
            Tag.objects.filter(posts__is_active=True, posts__status=Status.PUBLISHED.value)
            .distinct()
            .order_by("slug")
        )

    def location(self, item) -> str:
        return f"/tags/{item.slug}"
