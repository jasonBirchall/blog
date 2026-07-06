"""Integration specs for the sync_wakatime command (network injected via patch).

The command is a thin adapter: read the key from the environment, fetch, parse,
and upsert the one snapshot. Any failure must exit non-zero (CommandError) and
leave the previous row intact — stale beats broken. The key must never surface
in output.
"""

import io
from datetime import UTC, datetime
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from blog.models import WakaSnapshot
from blog.wakatime import parse_stats

pytestmark = pytest.mark.django_db

RAW = (Path(__file__).parent.parent / "fixtures" / "wakatime" / "last_7_days.json").read_text()
_FETCH = "blog.management.commands.sync_wakatime.fetch_stats"


@pytest.fixture(autouse=True)
def _api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WAKATIME_API_KEY", "secret-key")


def _seed_previous_row() -> WakaSnapshot:
    WakaSnapshot.store(parse_stats(RAW), datetime(2026, 1, 1, tzinfo=UTC))
    return WakaSnapshot.objects.get(pk=1)


class DescribeSuccess:
    def it_writes_the_snapshot(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_FETCH, lambda api_key: RAW)
        call_command("sync_wakatime")
        result = WakaSnapshot.latest_stats()
        assert result is not None
        stats, _ = result
        assert stats.projects[0].name == "alpha"

    def it_does_not_leak_the_key_to_stdout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_FETCH, lambda api_key: RAW)
        out = io.StringIO()
        call_command("sync_wakatime", stdout=out)
        assert "secret-key" not in out.getvalue()


class DescribeMissingKey:
    def it_errors_when_the_key_is_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("WAKATIME_API_KEY", raising=False)
        with pytest.raises(CommandError, match="WAKATIME_API_KEY"):
            call_command("sync_wakatime")


class DescribeFailureLeavesPreviousRowIntact:
    def it_keeps_the_row_on_fetch_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        before = _seed_previous_row()

        def boom(api_key: str) -> str:
            raise OSError("network down")

        monkeypatch.setattr(_FETCH, boom)
        with pytest.raises(CommandError):
            call_command("sync_wakatime")
        after = WakaSnapshot.objects.get(pk=1)
        assert after.payload == before.payload
        assert after.fetched_at == before.fetched_at

    def it_keeps_the_row_on_parse_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        before = _seed_previous_row()
        monkeypatch.setattr(_FETCH, lambda api_key: "not valid json")
        with pytest.raises(CommandError):
            call_command("sync_wakatime")
        after = WakaSnapshot.objects.get(pk=1)
        assert after.payload == before.payload
