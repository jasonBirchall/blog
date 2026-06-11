"""Integration specs for sitemap.xml and robots.txt."""

import xml.etree.ElementTree as ET

import pytest
from django.test import Client, override_settings

from blog.sync import sync_content

pytestmark = pytest.mark.django_db

VOCAB = ["python", "django"]
_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def _doc(slug: str, *, status: str = "published", tags: str = "[python]") -> str:
    return (
        "---\n"
        "title: A Title\n"
        f"slug: {slug}\n"
        "date: 2026-06-10\n"
        "kind: note\n"
        f"tags: {tags}\n"
        f"status: {status}\n"
        "---\n"
        "Body."
    )


def _sync(docs: dict[str, str]) -> None:
    assert sync_content(docs, VOCAB, write=True).wrote


def _locations(content: bytes) -> list[str]:
    root = ET.fromstring(content)
    return [el.text or "" for el in root.findall(".//sm:loc", _NS)]


class DescribeSitemap:
    def it_is_well_formed_with_a_urlset(self, client: Client) -> None:
        _sync({"a.md": _doc("a")})
        root = ET.fromstring(client.get("/sitemap.xml").content)
        assert root.tag.endswith("urlset")

    def it_lists_published_posts_only(self, client: Client) -> None:
        _sync({"a.md": _doc("a"), "b.md": _doc("b-draft", status="draft")})
        locations = _locations(client.get("/sitemap.xml").content)
        assert any(loc.endswith("/posts/a") for loc in locations)
        assert not any("b-draft" in loc for loc in locations)

    def it_lists_tag_pages_for_tags_in_use(self, client: Client) -> None:
        _sync({"a.md": _doc("a", tags="[python]")})
        locations = _locations(client.get("/sitemap.xml").content)
        assert any(loc.endswith("/tags/python") for loc in locations)


class DescribeRobots:
    def it_serves_plain_text(self, client: Client) -> None:
        response = client.get("/robots.txt")
        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/plain")

    def it_allows_crawlers_and_links_the_sitemap(self, client: Client) -> None:
        body = client.get("/robots.txt").content.decode()
        assert "User-agent: *" in body
        assert "Sitemap:" in body
        assert "/sitemap.xml" in body

    def it_blocks_the_ai_crawlers(self, client: Client) -> None:
        body = client.get("/robots.txt").content.decode()
        assert "User-agent: GPTBot" in body
        assert "User-agent: ClaudeBot" in body
        assert "Disallow: /" in body

    @override_settings(IS_PREVIEW=True)
    def it_disallows_everything_in_preview(self, client: Client) -> None:
        body = client.get("/robots.txt").content.decode()
        assert "User-agent: *" in body
        assert "Disallow: /" in body
        assert "Sitemap:" not in body
