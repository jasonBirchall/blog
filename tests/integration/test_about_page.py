"""Integration specs for the /about page (prose + contact h-card).

Covers the authored-existence contract (404 on absent/draft), the h-card
microformat structure, and the site-wide invariants: no JavaScript, no cookies,
valid HTML5. Cribbed from test_now_page.py minus the WakaTime stats.
"""

import html5lib
import pytest
from django.test import Client

from blog.sync import sync_content

pytestmark = pytest.mark.django_db

VOCAB = ["python"]


def _about_doc(*, status: str = "published", body: str = "Hello, I build things.") -> str:
    return (
        "---\n"
        "title: About\n"
        "slug: about\n"
        "date: 2026-07-07\n"
        "kind: note\n"
        "tags: []\n"
        f"status: {status}\n"
        "---\n"
        f"{body}"
    )


def _sync_about(*, status: str = "published", body: str = "Hello, I build things.") -> None:
    assert sync_content({"about.md": _about_doc(status=status, body=body)}, VOCAB, write=True).wrote


class DescribeAuthoredExistence:
    def it_404s_when_about_is_absent(self, client: Client) -> None:
        assert client.get("/about").status_code == 404

    def it_404s_when_about_is_a_draft(self, client: Client) -> None:
        _sync_about(status="draft")
        assert client.get("/about").status_code == 404

    def it_renders_the_prose_when_published(self, client: Client) -> None:
        _sync_about(body="I lead platform engineering.")
        response = client.get("/about")
        assert response.status_code == 200
        assert "I lead platform engineering." in response.content.decode()


class DescribeContactCard:
    def it_marks_up_an_h_card(self, client: Client) -> None:
        _sync_about()
        html = client.get("/about").content.decode()
        for microformat in ("h-card", "p-name", "u-url"):
            assert microformat in html

    def it_links_the_contact_channels_with_rel_me(self, client: Client) -> None:
        _sync_about()
        html = client.get("/about").content.decode()
        assert 'rel="me" href="https://fosstodon.org/@jasonbirchall"' in html
        assert 'rel="me" href="https://codeberg.org/jasonbirchall"' in html


class DescribeSecurityInvariants:
    def it_ships_no_javascript(self, client: Client) -> None:
        _sync_about()
        assert "<script" not in client.get("/about").content.decode()

    def it_sets_no_cookies(self, client: Client) -> None:
        _sync_about()
        assert client.get("/about").cookies == {}

    def it_is_valid_html5(self, client: Client) -> None:
        _sync_about()
        parser = html5lib.HTMLParser()
        parser.parse(client.get("/about").content)
        assert parser.errors == []

    def it_leaks_no_unrendered_template_syntax(self, client: Client) -> None:
        # A multi-line {# #} comment renders literally in Django; this guards
        # against that (and any other stray {% %}/{{ }}) reaching the browser.
        _sync_about()
        html = client.get("/about").content.decode()
        for token in ("{#", "#}", "{%", "%}", "{{", "}}"):
            assert token not in html
