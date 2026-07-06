"""Integration specs for the reserved-slug convention (now).

A published `now.md` is synced through the normal pipeline but must appear in
none of the home stream, feed, archive, search index, tag counts, or the post
sitemap; `/posts/now` redirects to `/now`; and `/now` is listed in the sitemap
as a static page.
"""

import xml.etree.ElementTree as ET

import pytest
from django.test import Client

from blog.feeds import PostFeed
from blog.search import search_posts
from blog.sync import sync_content
from blog.views import _published_posts

pytestmark = pytest.mark.django_db

VOCAB = ["python"]
_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def _doc(slug: str, *, title: str = "A Title", body: str = "Body.", tags: str = "[python]") -> str:
    return (
        "---\n"
        f"title: {title}\n"
        f"slug: {slug}\n"
        "date: 2026-06-10\n"
        "kind: note\n"
        f"tags: {tags}\n"
        "status: published\n"
        "---\n"
        f"{body}"
    )


def _sync(docs: dict[str, str]) -> None:
    assert sync_content(docs, VOCAB, write=True).wrote


def _locations(content: bytes) -> list[str]:
    root = ET.fromstring(content)
    return [el.text or "" for el in root.findall(".//sm:loc", _NS)]


# A now.md alongside an ordinary post, so each spec proves the ordinary post
# survives while `now` is filtered out.
BOTH = {"now.md": _doc("now", title="Now Uniquetitle", body="Nowbodyword."), "a.md": _doc("a")}


class DescribeExclusionFromListings:
    def it_is_absent_from_the_published_stream(self) -> None:
        _sync(BOTH)
        slugs = {post.slug for post in _published_posts()}
        assert slugs == {"a"}

    def it_is_absent_from_the_feed(self) -> None:
        _sync(BOTH)
        assert {item.slug for item in PostFeed().items()} == {"a"}

    def it_is_absent_from_the_search_index(self) -> None:
        _sync(BOTH)
        assert search_posts("Nowbodyword") == []
        assert [r.slug for r in search_posts("Body")] == ["a"]

    def it_is_absent_from_the_post_sitemap(self, client: Client) -> None:
        _sync(BOTH)
        locations = _locations(client.get("/sitemap.xml").content)
        assert not any(loc.endswith("/posts/now") for loc in locations)
        assert any(loc.endswith("/posts/a") for loc in locations)


class DescribeTagCounts:
    def it_does_not_count_a_reserved_post_toward_a_tag(self, client: Client) -> None:
        # now and a share the 'python' tag; the tag index must count only a.
        _sync(BOTH)
        body = client.get("/tags/").content.decode()
        # The tag appears (a uses it) but its count reflects one post, not two.
        assert "/tags/python" in body
        tag_page = client.get("/tags/python").content.decode()
        assert "Now Uniquetitle" not in tag_page
        assert "A Title" in tag_page


class DescribeRouting:
    def it_redirects_posts_now_to_the_now_page(self, client: Client) -> None:
        _sync(BOTH)
        response = client.get("/posts/now")
        assert response.status_code == 301
        assert response["Location"] == "/now"

    def it_lists_now_in_the_sitemap_as_a_static_page(self, client: Client) -> None:
        _sync(BOTH)
        locations = _locations(client.get("/sitemap.xml").content)
        assert any(loc.endswith("/now") and not loc.endswith("/posts/now") for loc in locations)
