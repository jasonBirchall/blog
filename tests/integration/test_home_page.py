"""Specs for the chronological home stream and its pagination."""

from datetime import date, timedelta

import pytest
from django.test import Client

from blog.models import Post

pytestmark = pytest.mark.django_db


def _post(
    slug: str, *, on: date, kind: str = "note", status: str = "published", title: str = "T"
) -> Post:
    return Post.objects.create(
        slug=slug,
        title=title,
        date=on,
        kind=kind,
        body_markdown="Body.",
        excerpt="An excerpt.",
        status=status,
        is_active=True,
    )


class DescribeHomeStream:
    def it_renders_an_empty_corpus(self, client: Client) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert "No posts" in response.content.decode()

    def it_lists_a_single_post(self, client: Client) -> None:
        _post("only", on=date(2026, 6, 10), title="Only Post")
        html = client.get("/").content.decode()
        assert "Only Post" in html
        assert "/posts/only" in html

    def it_orders_newest_first(self, client: Client) -> None:
        _post("old", on=date(2020, 1, 1), title="Older One")
        _post("new", on=date(2026, 1, 1), title="Newer One")
        html = client.get("/").content.decode()
        assert html.index("Newer One") < html.index("Older One")

    def it_shows_a_kind_indicator(self, client: Client) -> None:
        _post("a", on=date(2026, 6, 10), kind="link", title="A Link")
        assert 'class="kind">link' in client.get("/").content.decode()

    def it_excludes_drafts(self, client: Client) -> None:
        _post("d", on=date(2026, 6, 10), status="draft", title="Draft Post")
        assert "Draft Post" not in client.get("/").content.decode()


class DescribePagination:
    def it_paginates_over_a_large_corpus(self, client: Client) -> None:
        Post.objects.bulk_create(
            Post(
                slug=f"p{i}",
                title=f"Post {i}",
                date=date(2026, 1, 1) + timedelta(days=i),
                kind="note",
                body_markdown="Body.",
                status="published",
                is_active=True,
            )
            for i in range(100)
        )
        page1 = client.get("/").content.decode()
        assert page1.count('class="entry"') == 20
        assert "?page=2" in page1
        assert 'class="entry"' in client.get("/?page=2").content.decode()

    def it_clamps_an_out_of_range_page(self, client: Client) -> None:
        _post("a", on=date(2026, 6, 10))
        assert client.get("/?page=999").status_code == 200
