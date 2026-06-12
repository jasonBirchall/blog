"""snapshot_posts management command (a thin adapter over blog.snapshots).

Intended as a post-deploy step (wired into the deploy workflow in N6.3):

    uv run python manage.py snapshot_posts
"""

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from blog.snapshots import snapshot_new_posts


class Command(BaseCommand):
    help = "Snapshot newly-published posts to the Wayback Machine (failures non-fatal)."

    def handle(self, *args: Any, **options: Any) -> None:
        report = snapshot_new_posts(settings.SITE_URL)
        self.stdout.write(
            self.style.SUCCESS(
                f"Snapshotted {report.snapshotted}; {report.failed} failed (will retry)."
            )
        )
