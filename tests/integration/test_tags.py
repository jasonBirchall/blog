"""Specs for the tag index (/tags/) and tag detail (/tags/<slug>)."""

from datetime import date

import pytest
from django.test import Client

from blog.models import Post, Tag

pytestmark = pytest.mark.django_db


def _post(
    slug: str, *, tags: list[str], status: str = "published", on: date = date(2026, 6, 10)
) -> Post:
    post = Post.objects.create(
        slug=slug,
        title=slug.title(),
        date=on,
        kind="note",
        body_markdown="Body.",
        excerpt="An excerpt.",
        status=status,
        is_active=True,
    )
    for name in tags:
        tag, _ = Tag.objects.get_or_create(slug=name, defaults={"name": name.title()})
        post.tags.add(tag)
    return post


class DescribeTagIndex:
    def it_renders_empty_when_there_are_no_tags(self, client: Client) -> None:
        response = client.get("/tags/")
        assert response.status_code == 200
        assert "No tags" in response.content.decode()

    def it_shows_post_counts(self, client: Client) -> None:
        _post("a", tags=["python"])
        _post("b", tags=["python"])
        assert 'class="tag-count">2' in client.get("/tags/").content.decode()

    def it_orders_by_count_then_slug(self, client: Client) -> None:
        _post("a", tags=["python"])
        _post("b", tags=["python"])
        _post("c", tags=["django"])
        _post("d", tags=["zig"])
        html = client.get("/tags/").content.decode()
        assert html.index(">python<") < html.index(">django<") < html.index(">zig<")

    def it_excludes_tags_with_no_published_posts(self, client: Client) -> None:
        _post("a", tags=["ghost"], status="draft")
        assert "ghost" not in client.get("/tags/").content.decode()


class DescribeTagDetail:
    def it_lists_posts_for_the_tag(self, client: Client) -> None:
        _post("kept", tags=["python"])
        _post("other", tags=["django"])
        html = client.get("/tags/python").content.decode()
        assert "/posts/kept" in html
        assert "/posts/other" not in html

    def it_excludes_drafts(self, client: Client) -> None:
        _post("draft-post", tags=["python"], status="draft")
        assert "/posts/draft-post" not in client.get("/tags/python").content.decode()

    def it_404s_for_an_unknown_tag(self, client: Client) -> None:
        assert client.get("/tags/nope").status_code == 404

    def it_paginates(self, client: Client) -> None:
        for i in range(25):
            _post(f"p{i}", tags=["python"])
        page1 = client.get("/tags/python").content.decode()
        assert page1.count('class="entry"') == 20
        assert "?page=2" in page1
        assert client.get("/tags/python?page=2").content.decode().count('class="entry"') == 5
