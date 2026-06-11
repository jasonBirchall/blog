"""Specs for the /posts/<slug> detail view and its per-kind rendering."""

import pytest
from django.test import Client

from blog.sync import sync_content

pytestmark = pytest.mark.django_db

VOCAB = ["python"]

ESSAY = """---
title: An Essay
slug: an-essay
date: 2026-06-10
kind: essay
tags: [python]
status: published
---
First paragraph of the essay."""

LINK = """---
title: A Link Post
slug: a-link
date: 2026-06-10
kind: link
tags: [python]
status: published
link:
  url: https://example.com/article
  source: Example
---
Commentary on the link."""

QUOTE = """---
title: A Quote Post
slug: a-quote
date: 2026-06-10
kind: quote
tags: [python]
status: published
quote:
  text: A system is never finished.
  source: Donella Meadows
---
Context for the quote."""


def _sync(docs: dict[str, str]) -> None:
    assert sync_content(docs, VOCAB, write=True).wrote


class DescribePostDetail:
    def it_renders_a_published_post(self, client: Client) -> None:
        _sync({"a.md": ESSAY})
        response = client.get("/posts/an-essay")
        assert response.status_code == 200
        assert "<h1>An Essay</h1>" in response.content.decode()

    def it_renders_the_body_inside_the_reading_column(self, client: Client) -> None:
        _sync({"a.md": ESSAY})
        html = client.get("/posts/an-essay").content.decode()
        # Body lives in <main>; kind/date metadata lives in the article header (edge).
        assert '<main id="main">' in html
        assert "<p>First paragraph of the essay.</p>" in html
        assert 'class="post-header"' in html

    def it_shows_the_date_in_a_time_element(self, client: Client) -> None:
        _sync({"a.md": ESSAY})
        assert '<time datetime="2026-06-10">' in client.get("/posts/an-essay").content.decode()

    def it_lists_tags_at_the_edge(self, client: Client) -> None:
        _sync({"a.md": ESSAY})
        html = client.get("/posts/an-essay").content.decode()
        assert "/tags/python" in html

    def it_404s_for_a_draft(self, client: Client) -> None:
        _sync({"a.md": ESSAY.replace("status: published", "status: draft")})
        assert client.get("/posts/an-essay").status_code == 404

    def it_404s_for_an_unknown_slug(self, client: Client) -> None:
        assert client.get("/posts/nope").status_code == 404

    def it_404s_for_a_deactivated_post(self, client: Client) -> None:
        _sync({"a.md": ESSAY, "b.md": ESSAY.replace("an-essay", "b-essay")})
        _sync({"b.md": ESSAY.replace("an-essay", "b-essay")})  # a removed -> deactivated
        assert client.get("/posts/an-essay").status_code == 404


class DescribeLinkPost:
    def it_renders_the_link_header(self, client: Client) -> None:
        _sync({"a.md": LINK})
        html = client.get("/posts/a-link").content.decode()
        assert 'href="https://example.com/article"' in html
        assert "Example" in html


class DescribeQuotePost:
    def it_renders_the_quote_header(self, client: Client) -> None:
        _sync({"a.md": QUOTE})
        html = client.get("/posts/a-quote").content.decode()
        assert "A system is never finished." in html
        assert "Donella Meadows" in html


class DescribeEditDate:
    def it_shows_the_updated_date_when_present(self, client: Client) -> None:
        _sync(
            {"a.md": ESSAY.replace("date: 2026-06-10\n", "date: 2026-06-10\nupdated: 2026-06-15\n")}
        )
        assert '<time datetime="2026-06-15">' in client.get("/posts/an-essay").content.decode()

    def it_omits_the_updated_date_when_absent(self, client: Client) -> None:
        _sync({"a.md": ESSAY})
        assert "2026-06-15" not in client.get("/posts/an-essay").content.decode()
