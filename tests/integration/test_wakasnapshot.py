"""Specs for the WakaSnapshot persistence adapter (single-row, self-validating).

The row is a derived artefact: exactly one snapshot (pk=1), and `latest_stats`
re-validates the stored payload through the domain, so an empty or hand-tampered
row degrades to None rather than raising or serving unvalidated data.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from blog.models import WakaSnapshot
from blog.wakatime import parse_stats

pytestmark = pytest.mark.django_db

RAW = (Path(__file__).parent.parent / "fixtures" / "wakatime" / "last_7_days.json").read_text()
_WHEN = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)


class DescribeStore:
    def it_keeps_exactly_one_row_on_repeated_upserts(self) -> None:
        stats = parse_stats(RAW)
        WakaSnapshot.store(stats, _WHEN)
        row = WakaSnapshot.store(stats, datetime(2026, 7, 7, 9, 0, tzinfo=UTC))
        assert WakaSnapshot.objects.count() == 1
        assert row.pk == 1
        assert row.fetched_at == datetime(2026, 7, 7, 9, 0, tzinfo=UTC)

    def it_stores_the_reserialised_model_not_the_raw_response(self) -> None:
        WakaSnapshot.store(parse_stats(RAW), _WHEN)
        payload = WakaSnapshot.objects.get(pk=1).payload
        # The AI-spend telemetry in the raw fixture must not survive to storage.
        assert "ai_input_tokens" not in payload
        assert "daily_average_seconds" in payload


class DescribeLatestStats:
    def it_returns_none_when_empty(self) -> None:
        assert WakaSnapshot.latest_stats() is None

    def it_round_trips_stored_stats(self) -> None:
        stored = parse_stats(RAW)
        WakaSnapshot.store(stored, _WHEN)
        result = WakaSnapshot.latest_stats()
        assert result is not None
        stats, fetched_at = result
        assert stats == stored
        assert fetched_at == _WHEN

    def it_returns_none_on_a_corrupt_payload(self) -> None:
        WakaSnapshot.objects.create(pk=1, payload="{ not valid json", fetched_at=_WHEN)
        assert WakaSnapshot.latest_stats() is None
