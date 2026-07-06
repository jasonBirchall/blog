"""sync_wakatime management command (a thin adapter over blog.wakatime).

Run daily by a user-scope systemd timer on the box (N.7), decoupled from the
deploy timer so stats refresh even when `main` has not moved:

    uv run python manage.py sync_wakatime

Reads WAKATIME_API_KEY from the environment (never argv, never logged). Any
failure exits non-zero via CommandError and leaves the existing snapshot
untouched — stale data beats broken data.
"""

import os
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from blog.models import WakaSnapshot
from blog.wakatime import WakaStatsError, fetch_stats, parse_stats


class Command(BaseCommand):
    help = "Fetch the last 7 days of WakaTime stats and upsert the snapshot."

    def handle(self, *args: Any, **options: Any) -> None:
        api_key = os.environ.get("WAKATIME_API_KEY")
        if not api_key:
            raise CommandError("WAKATIME_API_KEY is not set")
        try:
            stats = parse_stats(fetch_stats(api_key))
        except (WakaStatsError, OSError) as exc:
            # OSError covers urllib's URLError/timeout; the row is left as-is.
            raise CommandError(f"WakaTime sync failed: {exc}") from exc
        WakaSnapshot.store(stats, timezone.now())
        self.stdout.write(
            self.style.SUCCESS(
                f"Stored WakaTime snapshot: {stats.total_text} across "
                f"{len(stats.projects)} projects, {len(stats.languages)} languages."
            )
        )
