"""WakaTime coding-activity stats as framework-free domain types.

Pure domain (no Django), so it stays in ty's strict zone alongside
`frontmatter.py`. The WakaTime response is treated as hostile regardless of
trust in the service, because the cost is near zero: it is validated at the
boundary into frozen, bounded models, and only three fields per item (`name`,
`percent`, `total_seconds`) are kept. WakaTime also returns per-project
AI-spend telemetry — token counts, per-model dollar costs, human-vs-AI line
counts — that must never reach the database or a template, so the wire models
use `extra="ignore"` to drop it by construction (see PLAN.md N.0).

`fetch_stats` performs one authenticated HTTPS GET via stdlib `urllib` with an
injected callable (as in `snapshots.py`) so no spec touches the network;
`parse_stats` validates a raw response string into a `WakaStats`. Duration
formatting lives here too, so templates stay logic-free.
"""

import base64
import urllib.request
from collections.abc import Callable, Iterable
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

_STATS_URL = "https://api.wakatime.com/api/v1/users/current/stats/last_7_days"
_TIMEOUT_SECONDS = 30.0
_MAX_NAME_LEN = 100
_MAX_PAYLOAD_BYTES = 512 * 1024
_TOP_N = 10

Fetch = Callable[[str, str], str]

_Name = Annotated[str, StringConstraints(max_length=_MAX_NAME_LEN)]
_Percent = Annotated[float, Field(ge=0, le=100)]
_Seconds = Annotated[float, Field(ge=0)]


class WakaStatsError(Exception):
    """Raised when a WakaTime response is missing or invalid. Message is quotable."""


# --- Domain: strict, frozen, stored verbatim -------------------------------


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class LanguageStat(_Strict):
    name: _Name
    percent: _Percent
    total_seconds: _Seconds

    @property
    def text(self) -> str:
        return format_duration(self.total_seconds)


class ProjectStat(_Strict):
    name: _Name
    percent: _Percent
    total_seconds: _Seconds

    @property
    def text(self) -> str:
        return format_duration(self.total_seconds)


class WakaStats(_Strict):
    languages: tuple[LanguageStat, ...]
    projects: tuple[ProjectStat, ...]
    total_seconds: _Seconds
    daily_average_seconds: _Seconds
    range_start: date
    range_end: date

    @property
    def total_text(self) -> str:
        return format_duration(self.total_seconds)

    @property
    def daily_average_text(self) -> str:
        return format_duration(self.daily_average_seconds)


# --- Wire: tolerant boundary parse of WakaTime's own shape ------------------


class _Wire(BaseModel):
    # extra="ignore" on purpose (not "forbid"): WakaTime sends ~24 keys per
    # project — including AI-spend telemetry — that we deliberately discard,
    # keeping only the declared fields below.
    model_config = ConfigDict(extra="ignore")


class _WireItem(_Wire):
    name: _Name
    percent: _Percent
    total_seconds: _Seconds


class _WireData(_Wire):
    languages: list[_WireItem]
    projects: list[_WireItem]
    total_seconds: _Seconds
    daily_average: _Seconds
    start: datetime
    end: datetime


class _WireResponse(_Wire):
    data: _WireData


def format_duration(seconds: float) -> str:
    """Render a duration as WakaTime does: '8 hrs 27 mins', '52 mins', '1 hr'."""
    total_minutes = int(seconds // 60)
    hours, minutes = divmod(total_minutes, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} hr{'s' if hours != 1 else ''}")
    if minutes or not hours:
        parts.append(f"{minutes} min{'s' if minutes != 1 else ''}")
    return " ".join(parts)


def _top(items: Iterable[_WireItem]) -> tuple[_WireItem, ...]:
    ranked = sorted(items, key=lambda item: item.total_seconds, reverse=True)
    return tuple(ranked[:_TOP_N])


def parse_stats(raw: str, *, hidden_projects: frozenset[str] = frozenset()) -> WakaStats:
    """Validate a raw stats response into a WakaStats, or raise WakaStatsError.

    Hidden projects are filtered before the domain models are built, so a name
    on the deny-list never reaches the database or a template.
    """
    if len(raw.encode("utf-8")) > _MAX_PAYLOAD_BYTES:
        raise WakaStatsError("WakaTime response exceeds the maximum accepted size")
    try:
        data = _WireResponse.model_validate_json(raw).data
        languages = _top(data.languages)
        projects = _top(item for item in data.projects if item.name not in hidden_projects)
        return WakaStats(
            languages=tuple(
                LanguageStat(name=i.name, percent=i.percent, total_seconds=i.total_seconds)
                for i in languages
            ),
            projects=tuple(
                ProjectStat(name=i.name, percent=i.percent, total_seconds=i.total_seconds)
                for i in projects
            ),
            total_seconds=data.total_seconds,
            daily_average_seconds=data.daily_average,
            range_start=data.start.date(),
            range_end=data.end.date(),
        )
    except ValidationError as exc:
        raise WakaStatsError(f"Invalid WakaTime stats response: {exc}") from exc


def _default_fetch(url: str, api_key: str) -> str:
    token = base64.b64encode(api_key.encode("utf-8")).decode("ascii")
    request = urllib.request.Request(url, headers={"Authorization": f"Basic {token}"})
    with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")


def fetch_stats(api_key: str, *, fetch: Fetch = _default_fetch) -> str:
    """Fetch the raw last-7-days stats response. Network is injected for specs."""
    return fetch(_STATS_URL, api_key)
