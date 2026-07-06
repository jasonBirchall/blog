"""Integration specs for the /now page (prose + WakaTime stats).

Covers the authored-existence contract (404 on absent/draft), graceful
rendering with and without a snapshot, and the security invariants: hostile
stats names arrive HTML-escaped, no JavaScript, no cookies, valid HTML5.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import html5lib
import pytest
from django.test import Client

from blog.models import WakaSnapshot
from blog.sync import sync_content
from blog.wakatime import parse_stats

pytestmark = pytest.mark.django_db

VOCAB = ["python"]
RAW = (Path(__file__).parent.parent / "fixtures" / "wakatime" / "last_7_days.json").read_text()
_WHEN = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)


def _now_doc(*, status: str = "published", body: str = "Working on things.") -> str:
    return (
        "---\n"
        "title: Now\n"
        "slug: now\n"
        "date: 2026-06-10\n"
        "kind: note\n"
        "tags: []\n"
        f"status: {status}\n"
        "---\n"
        f"{body}"
    )


def _sync_now(*, status: str = "published", body: str = "Working on things.") -> None:
    assert sync_content({"now.md": _now_doc(status=status, body=body)}, VOCAB, write=True).wrote


def _store_snapshot(raw: str = RAW) -> None:
    WakaSnapshot.store(parse_stats(raw), _WHEN)


class DescribeAuthoredExistence:
    def it_404s_when_now_is_absent(self, client: Client) -> None:
        assert client.get("/now").status_code == 404

    def it_404s_when_now_is_a_draft(self, client: Client) -> None:
        _sync_now(status="draft")
        assert client.get("/now").status_code == 404

    def it_renders_the_prose_when_published(self, client: Client) -> None:
        _sync_now(body="Currently between employers.")
        response = client.get("/now")
        assert response.status_code == 200
        assert "Currently between employers." in response.content.decode()


class DescribeStatsRendering:
    def it_omits_the_stats_section_without_a_snapshot(self, client: Client) -> None:
        _sync_now()
        assert "Coding activity" not in client.get("/now").content.decode()

    def it_renders_the_stats_section_with_a_snapshot(self, client: Client) -> None:
        _sync_now()
        _store_snapshot()
        html = client.get("/now").content.decode()
        assert "Coding activity" in html
        assert "Markdown" in html  # a language name from the fixture
        assert "alpha" in html  # a project name from the fixture
        assert "As of" in html
        assert 'datetime="2026-07-06"' in html


class DescribeSecurityInvariants:
    def it_escapes_hostile_stats_names(self, client: Client) -> None:
        payload = json.loads(RAW)
        payload["data"]["projects"][0]["name"] = "<script>alert(1)</script>"
        payload["data"]["languages"][0]["name"] = "<img src=x onerror=alert(1)>"
        _sync_now()
        _store_snapshot(json.dumps(payload))
        html = client.get("/now").content.decode()
        # No live tag may survive; the escaped (inert) forms must be present. The
        # string "onerror=alert(1)" survives as inert TEXT inside &lt;img...&gt;,
        # so the meaningful check is that the angle brackets are escaped.
        assert "<script>alert(1)</script>" not in html
        assert "<img src=x onerror" not in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
        assert "&lt;img src=x onerror=alert(1)&gt;" in html

    def it_ships_no_javascript(self, client: Client) -> None:
        _sync_now()
        _store_snapshot()
        assert "<script" not in client.get("/now").content.decode()

    def it_sets_no_cookies(self, client: Client) -> None:
        _sync_now()
        _store_snapshot()
        assert client.get("/now").cookies == {}

    def it_is_valid_html5(self, client: Client) -> None:
        _sync_now()
        _store_snapshot()
        parser = html5lib.HTMLParser()
        parser.parse(client.get("/now").content)
        assert parser.errors == []
