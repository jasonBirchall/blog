"""Integration specs for the reserved-slug convention.

A published reserved doc (now, about, …) is synced through the normal pipeline
but must appear in none of the home stream, feed, archive, search index, tag
counts, or the post sitemap; `/posts/<slug>` redirects to `/<slug>`; and each
reserved slug is listed in the sitemap as a static page.

The specs are parametrised over RESERVED_SLUGS, so adding the next reserved slug
to that frozenset is the only change needed here.
"""

import xml.etree.ElementTree as ET

import pytest
from django.test import Client

from blog.enums import RESERVED_SLUGS
from blog.feeds import PostFeed
from blog.search import search_posts
from blog.sync import sync_content
from blog.views import _published_posts

pytestmark = pytest.mark.django_db

VOCAB = ["python"]
RESERVED = sorted(RESERVED_SLUGS)
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


def _both(reserved: str) -> dict[str, str]:
    """A reserved doc alongside an ordinary post `a`, so each spec proves the
    ordinary post survives while the reserved slug is filtered out. The reserved
    doc carries a unique title and body word so exclusion is checkable."""
    return {
        f"{reserved}.md": _doc(
            reserved, title=f"{reserved.title()} Uniquetitle", body=f"{reserved}bodyword."
        ),
        "a.md": _doc("a"),
    }


def _sync(docs: dict[str, str]) -> None:
    assert sync_content(docs, VOCAB, write=True).wrote


def _locations(content: bytes) -> list[str]:
    root = ET.fromstring(content)
    return [el.text or "" for el in root.findall(".//sm:loc", _NS)]


@pytest.mark.parametrize("reserved", RESERVED)
class DescribeExclusionFromListings:
    def it_is_absent_from_the_published_stream(self, reserved: str) -> None:
        _sync(_both(reserved))
        assert {post.slug for post in _published_posts()} == {"a"}

    def it_is_absent_from_the_feed(self, reserved: str) -> None:
        _sync(_both(reserved))
        assert {item.slug for item in PostFeed().items()} == {"a"}

    def it_is_absent_from_the_search_index(self, reserved: str) -> None:
        _sync(_both(reserved))
        assert search_posts(f"{reserved}bodyword") == []
        assert [r.slug for r in search_posts("Body")] == ["a"]

    def it_is_absent_from_the_post_sitemap(self, reserved: str, client: Client) -> None:
        _sync(_both(reserved))
        locations = _locations(client.get("/sitemap.xml").content)
        assert not any(loc.endswith(f"/posts/{reserved}") for loc in locations)
        assert any(loc.endswith("/posts/a") for loc in locations)


@pytest.mark.parametrize("reserved", RESERVED)
class DescribeTagCounts:
    def it_does_not_count_a_reserved_post_toward_a_tag(self, reserved: str, client: Client) -> None:
        # reserved and a share the 'python' tag; the tag index must count only a.
        _sync(_both(reserved))
        body = client.get("/tags/").content.decode()
        # The tag appears (a uses it) but its count reflects one post, not two.
        assert "/tags/python" in body
        tag_page = client.get("/tags/python").content.decode()
        assert f"{reserved.title()} Uniquetitle" not in tag_page
        assert "A Title" in tag_page


@pytest.mark.parametrize("reserved", RESERVED)
class DescribeRouting:
    def it_redirects_the_post_route_to_the_reserved_page(
        self, reserved: str, client: Client
    ) -> None:
        _sync(_both(reserved))
        response = client.get(f"/posts/{reserved}")
        assert response.status_code == 301
        assert response["Location"] == f"/{reserved}"

    def it_lists_the_reserved_slug_in_the_sitemap_as_a_static_page(
        self, reserved: str, client: Client
    ) -> None:
        _sync(_both(reserved))
        locations = _locations(client.get("/sitemap.xml").content)
        assert any(
            loc.endswith(f"/{reserved}") and not loc.endswith(f"/posts/{reserved}")
            for loc in locations
        )
