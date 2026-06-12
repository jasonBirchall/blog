"""Snapshot newly-published posts to the Wayback Machine.

Pings web.archive.org's Save Page Now for each published post not yet archived,
marking it archived on success. Failures are non-fatal and logged, and the post
is left unarchived so the next deploy retries it. The HTTP call is injected so
it can be exercised without the network.
"""

import logging
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from blog.enums import Status
from blog.models import Post

logger = logging.getLogger(__name__)

Fetch = Callable[[str], bool]


def _save_page_now(url: str, *, timeout: float = 30.0) -> bool:
    save_url = f"https://web.archive.org/save/{url}"
    try:
        with urllib.request.urlopen(save_url, timeout=timeout) as response:
            return 200 <= response.status < 400
    except (urllib.error.URLError, TimeoutError) as exc:
        logger.warning("Wayback snapshot failed for %s: %s", url, exc)
        return False


@dataclass(frozen=True)
class SnapshotReport:
    snapshotted: int
    failed: int


def snapshot_new_posts(base_url: str, *, fetch: Fetch = _save_page_now) -> SnapshotReport:
    base = base_url.rstrip("/")
    snapshotted = failed = 0
    posts = Post.objects.filter(is_active=True, status=Status.PUBLISHED.value, archived=False)
    for post in posts:
        if fetch(f"{base}/posts/{post.slug}"):
            post.archived = True
            post.save(update_fields=["archived"])
            snapshotted += 1
        else:
            failed += 1
    return SnapshotReport(snapshotted=snapshotted, failed=failed)
