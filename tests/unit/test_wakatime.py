"""Specs for the WakaTime stats domain (pure domain, a trust boundary).

The response is untrusted: these cover the happy path from the sanitised
fixture, the deny-list, duration formatting, storage round-trip, and hostile
payloads (oversized, negative, out-of-range, non-JSON, empty, missing fields).
The response also carries per-project AI-spend telemetry we must drop; a spec
asserts it never survives parsing. Escaping of hostile names is a rendering
concern, asserted in the N.5 integration specs, not here.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from blog.wakatime import (
    WakaStats,
    WakaStatsError,
    fetch_stats,
    format_duration,
    parse_stats,
)

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "wakatime" / "last_7_days.json"
RAW = _FIXTURE.read_text(encoding="utf-8")


def _tampered(mutate) -> str:
    """Return the fixture as raw JSON after applying `mutate` to its `data` dict."""
    payload = json.loads(RAW)
    mutate(payload["data"])
    return json.dumps(payload)


class DescribeParsingTheFixture:
    def it_parses_the_sanitised_fixture(self) -> None:
        stats = parse_stats(RAW)
        assert isinstance(stats, WakaStats)
        assert stats.range_start == date(2026, 6, 28)
        assert stats.range_end == date(2026, 7, 5)
        assert stats.total_seconds == 47847.000001
        assert stats.daily_average_seconds == 7975.0

    def it_keeps_languages_sorted_by_time_desc(self) -> None:
        names = [lang.name for lang in parse_stats(RAW).languages]
        assert names == ["Markdown", "Python", "Bash", "Other"]

    def it_keeps_projects_sorted_by_time_desc(self) -> None:
        names = [proj.name for proj in parse_stats(RAW).projects]
        assert names == ["alpha", "beta", "gamma", "delta"]

    def it_caps_each_list_to_the_top_ten(self) -> None:
        many = _tampered(
            lambda data: data.__setitem__(
                "languages",
                [{"name": f"L{n}", "percent": 1.0, "total_seconds": float(n)} for n in range(25)],
            )
        )
        assert len(parse_stats(many).languages) == 10

    def it_drops_ai_spend_telemetry(self) -> None:
        # The fixture's first two projects carry ai_input_tokens / ai_agent_costs.
        top = parse_stats(RAW).projects[0]
        assert set(top.model_dump()) == {"name", "percent", "total_seconds"}
        assert "ai_input_tokens" not in top.model_dump()


class DescribeTheDenyList:
    def it_filters_hidden_projects_before_building(self) -> None:
        stats = parse_stats(RAW, hidden_projects=frozenset({"beta", "delta"}))
        assert [p.name for p in stats.projects] == ["alpha", "gamma"]

    def it_ignores_names_not_present(self) -> None:
        assert len(parse_stats(RAW, hidden_projects=frozenset({"absent"})).projects) == 4


class DescribeDurationFormatting:
    def it_formats_hours_and_minutes(self) -> None:
        assert format_duration(30422) == "8 hrs 27 mins"

    def it_singularises_one_hour_one_minute(self) -> None:
        assert format_duration(3660) == "1 hr 1 min"

    def it_omits_hours_when_zero(self) -> None:
        assert format_duration(3120) == "52 mins"

    def it_renders_zero_as_zero_mins(self) -> None:
        assert format_duration(0) == "0 mins"


class DescribeStorageRoundTrip:
    def it_round_trips_through_json(self) -> None:
        stats = parse_stats(RAW)
        # The N.2 storage contract: dump to JSON, re-validate through the domain.
        assert WakaStats.model_validate_json(stats.model_dump_json()) == stats


class DescribeRejectingHostilePayloads:
    def it_rejects_non_json(self) -> None:
        with pytest.raises(WakaStatsError):
            parse_stats("not json at all")

    def it_rejects_an_empty_body(self) -> None:
        with pytest.raises(WakaStatsError):
            parse_stats("")

    def it_rejects_an_oversized_body(self) -> None:
        with pytest.raises(WakaStatsError, match="size"):
            parse_stats("x" * (600 * 1024))

    def it_rejects_negative_seconds(self) -> None:
        raw = _tampered(lambda data: data["languages"][0].__setitem__("total_seconds", -1))
        with pytest.raises(WakaStatsError):
            parse_stats(raw)

    def it_rejects_a_percent_over_one_hundred(self) -> None:
        raw = _tampered(lambda data: data["projects"][0].__setitem__("percent", 150))
        with pytest.raises(WakaStatsError):
            parse_stats(raw)

    def it_rejects_an_overlong_name(self) -> None:
        raw = _tampered(lambda data: data["languages"][0].__setitem__("name", "x" * 200))
        with pytest.raises(WakaStatsError):
            parse_stats(raw)

    def it_rejects_a_missing_summary_field(self) -> None:
        raw = _tampered(lambda data: data.pop("total_seconds"))
        with pytest.raises(WakaStatsError):
            parse_stats(raw)


class DescribeHostileNames:
    def it_preserves_a_script_tag_name_for_the_template_to_escape(self) -> None:
        # Under the length cap, a hostile name is preserved verbatim; escaping is
        # the template's job (asserted end-to-end in the N.5 specs).
        payload = "<script>alert(1)</script>"
        raw = _tampered(lambda data: data["projects"][0].__setitem__("name", payload))
        assert parse_stats(raw).projects[0].name == payload


class DescribeFetch:
    def it_hits_the_stats_endpoint_with_the_key(self) -> None:
        calls: list[tuple[str, str]] = []
        body = fetch_stats("secret-key", fetch=lambda url, key: calls.append((url, key)) or RAW)
        assert len(calls) == 1
        assert calls[0][0].endswith("/stats/last_7_days")
        assert calls[0][1] == "secret-key"
        assert body == RAW

    def it_round_trips_fetch_into_parse(self) -> None:
        stats = parse_stats(fetch_stats("k", fetch=lambda url, key: RAW))
        assert stats.projects[0].name == "alpha"
