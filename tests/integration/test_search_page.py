"""Specs for the /search surface (server-rendered, JS-disabled friendly)."""

import pytest
from django.test import Client

from blog.sync import sync_content

pytestmark = pytest.mark.django_db

VOCAB = ["python"]


def _doc(slug: str, *, title: str, status: str = "published", body: str = "Body.") -> str:
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


class DescribeSearchPage:
    def it_renders_a_get_form(self, client: Client) -> None:
        response = client.get("/search")
        assert response.status_code == 200
        html = response.content.decode()
        assert "<form" in html
        assert 'name="q"' in html
        assert 'method="get"' in html

    def it_works_without_javascript(self, client: Client) -> None:
        assert "<script" not in client.get("/search?q=django").content.decode()

    def it_finds_matching_posts(self, client: Client) -> None:
        _sync({"a.md": _doc("a", title="Django Patterns"), "b.md": _doc("b", title="Cooking")})
        html = client.get("/search?q=django").content.decode()
        assert "/posts/a" in html
        assert "/posts/b" not in html

    def it_shows_a_no_results_message(self, client: Client) -> None:
        _sync({"a.md": _doc("a", title="Django")})
        assert "No results" in client.get("/search?q=nonexistentterm").content.decode()

    def it_shows_no_results_section_without_a_query(self, client: Client) -> None:
        html = client.get("/search").content.decode()
        assert "<form" in html
        assert "No results" not in html

    def it_preserves_the_query_in_pagination(self, client: Client) -> None:
        _sync({f"p{i}.md": _doc(f"p{i}", title=f"Common Term {i}") for i in range(25)})
        html = client.get("/search?q=common").content.decode()
        assert "q=common" in html
        assert "page=2" in html
