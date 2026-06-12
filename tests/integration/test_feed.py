"""Integration specs for the Atom feed and its aliases.

Feed validity is asserted with feedparser (bozo == 0, atom10) rather than the
W3C online feed validator named in N3.3's original DoD: the W3C service is
network-fragile and rate-limited in CI, and the feedparser checks cover the same
well-formedness intent. This is the recorded resolution of N3.3's DoD loose end.
"""

import feedparser
import pytest
from django.test import Client

from blog.sync import sync_content

pytestmark = pytest.mark.django_db

VOCAB = ["python"]


def _doc(
    slug: str, *, title: str = "A Title", status: str = "published", body: str = "Body."
) -> str:
    return (
        "---\n"
        f"title: {title}\n"
        f"slug: {slug}\n"
        "date: 2026-06-10\n"
        "kind: note\n"
        "tags: [python]\n"
        f"status: {status}\n"
        "---\n"
        f"{body}"
    )


def _sync(docs: dict[str, str]) -> None:
    assert sync_content(docs, VOCAB, write=True).wrote


class DescribeFeed:
    def it_serves_atom_at_feed_xml(self, client: Client) -> None:
        response = client.get("/feed.xml")
        assert response.status_code == 200
        assert "atom+xml" in response["Content-Type"]

    def it_is_well_formed_atom(self, client: Client) -> None:
        _sync({"a.md": _doc("a", title="A Post")})
        parsed = feedparser.parse(client.get("/feed.xml").content)
        assert parsed.bozo == 0
        assert parsed.version == "atom10"
        assert parsed.feed.title
        assert parsed.feed.author

    def it_includes_full_post_content(self, client: Client) -> None:
        _sync({"a.md": _doc("a", body="Hello **world**.")})
        parsed = feedparser.parse(client.get("/feed.xml").content)
        assert "<strong>world</strong>" in parsed.entries[0].content[0].value

    def it_lists_only_published_active_posts(self, client: Client) -> None:
        _sync({"a.md": _doc("a"), "b.md": _doc("b-draft", status="draft")})
        parsed = feedparser.parse(client.get("/feed.xml").content)
        links = [entry.link for entry in parsed.entries]
        assert any(link.endswith("/posts/a") for link in links)
        assert not any("b-draft" in link for link in links)


class DescribeAliases:
    def it_redirects_rss_to_the_feed(self, client: Client) -> None:
        response = client.get("/rss")
        assert response.status_code == 301
        assert response["Location"].endswith("/feed.xml")

    def it_redirects_atom_xml_to_the_feed(self, client: Client) -> None:
        response = client.get("/atom.xml")
        assert response.status_code == 301
        assert response["Location"].endswith("/feed.xml")
