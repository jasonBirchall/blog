"""Atom 1.0 feed of the most recent published posts, with full content."""

from datetime import UTC, datetime, time
from typing import Any

from django.conf import settings
from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed

from blog.enums import Status
from blog.models import Post

_FEED_LIMIT = 20


class _FullContentAtomFeed(Atom1Feed):
    """Atom feed that also emits the full post HTML as <content type="html">."""

    def add_item_elements(self, handler: Any, item: dict[str, Any]) -> None:
        super().add_item_elements(handler, item)
        content = item.get("content")
        if content:
            handler.addQuickElement("content", content, {"type": "html"})


class PostFeed(Feed):
    feed_type = _FullContentAtomFeed
    link = "/"

    def title(self) -> str:
        return settings.SITE_NAME

    def subtitle(self) -> str:
        return settings.SITE_DESCRIPTION

    def author_name(self) -> str:
        return settings.SITE_AUTHOR

    def feed_url(self) -> str:
        return "/feed.xml"

    def items(self) -> list[Post]:
        return list(
            Post.objects.filter(is_active=True, status=Status.PUBLISHED.value).order_by(
                "-date", "-id"
            )[:_FEED_LIMIT]
        )

    def item_title(self, item) -> str:
        return item.title

    def item_description(self, item) -> str:
        return item.excerpt

    def item_link(self, item) -> str:
        return f"/posts/{item.slug}"

    def item_pubdate(self, item) -> datetime:
        return datetime.combine(item.date, time.min, tzinfo=UTC)

    def item_updateddate(self, item) -> datetime:
        return datetime.combine(item.date, time.min, tzinfo=UTC)

    def item_extra_kwargs(self, item) -> dict[str, str]:
        return {"content": item.body_html}
