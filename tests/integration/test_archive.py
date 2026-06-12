"""Specs for the /archive/ page: all published posts grouped by year."""

from datetime import date

import pytest
from django.test import Client

from blog.models import Post

pytestmark = pytest.mark.django_db


def _post(slug: str, *, on: date, status: str = "published", title: str = "T") -> Post:
    return Post.objects.create(
        slug=slug,
        title=title,
        date=on,
        kind="note",
        body_markdown="Body.",
        status=status,
        is_active=True,
    )


class DescribeArchive:
    def it_renders_an_empty_corpus(self, client: Client) -> None:
        response = client.get("/archive/")
        assert response.status_code == 200
        assert "No posts" in response.content.decode()

    def it_groups_posts_by_year_newest_first(self, client: Client) -> None:
        _post("older", on=date(2025, 3, 1))
        _post("newer", on=date(2026, 3, 1))
        html = client.get("/archive/").content.decode()
        assert "<h2>2026</h2>" in html
        assert "<h2>2025</h2>" in html
        assert html.index("2026") < html.index("2025")

    def it_lists_a_post_under_its_year(self, client: Client) -> None:
        _post("a-post", on=date(2026, 3, 1), title="A Post")
        html = client.get("/archive/").content.decode()
        assert "/posts/a-post" in html

    def it_excludes_drafts(self, client: Client) -> None:
        _post("draft-post", on=date(2026, 3, 1), status="draft", title="Draft")
        assert "/posts/draft-post" not in client.get("/archive/").content.decode()

    def it_renders_the_whole_corpus_in_a_single_query(
        self, client: Client, django_assert_num_queries
    ) -> None:
        for i in range(30):
            _post(f"p{i}", on=date(2020 + i % 6, 1, 1))
        with django_assert_num_queries(1):
            client.get("/archive/")
