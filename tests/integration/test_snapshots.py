"""Specs for the Wayback Machine snapshot mechanism (network injected)."""

from datetime import date

import pytest

from blog.models import Post
from blog.snapshots import snapshot_new_posts

pytestmark = pytest.mark.django_db


def _post(slug: str, *, status: str = "published", archived: bool = False) -> Post:
    return Post.objects.create(
        slug=slug,
        title=slug,
        date=date(2026, 6, 10),
        kind="note",
        body_markdown="Body.",
        status=status,
        is_active=True,
        archived=archived,
    )


class DescribeSnapshot:
    def it_snapshots_published_unarchived_posts(self) -> None:
        _post("a")
        calls: list[str] = []
        report = snapshot_new_posts(
            "https://blog.test/", fetch=lambda url: calls.append(url) or True
        )
        assert report.snapshotted == 1
        assert report.failed == 0
        assert calls == ["https://blog.test/posts/a"]
        assert Post.objects.get(slug="a").archived is True

    def it_skips_already_archived_posts(self) -> None:
        _post("a", archived=True)
        report = snapshot_new_posts("https://blog.test", fetch=lambda url: True)
        assert report.snapshotted == 0

    def it_skips_drafts(self) -> None:
        _post("d", status="draft")
        calls: list[str] = []
        snapshot_new_posts("https://blog.test", fetch=lambda url: calls.append(url) or True)
        assert calls == []

    def it_leaves_failed_posts_unarchived_to_retry(self) -> None:
        _post("a")
        report = snapshot_new_posts("https://blog.test", fetch=lambda url: False)
        assert report.snapshotted == 0
        assert report.failed == 1
        assert Post.objects.get(slug="a").archived is False
