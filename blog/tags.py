"""Tag controlled-vocabulary loader.

`tags.yml` is a flat list of slugs — the only tags a post may use. This module
parses and validates it at the boundary (parse, don't validate) and is pure
Python so the content linter and sync command can reuse it without Django.
"""

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class TagVocabularyError(Exception):
    """Raised when tags.yml is malformed. The message is meant to be quotable."""


class _TagFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tags: list[str]


def load_tag_vocabulary(path: Path) -> tuple[str, ...]:
    """Parse tags.yml and return the ordered, unique, validated slugs."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    try:
        parsed = _TagFile.model_validate(raw)
    except ValidationError as exc:
        raise TagVocabularyError(f"tags.yml is not a flat list under 'tags': {exc}") from exc

    seen: set[str] = set()
    for slug in parsed.tags:
        if not SLUG_PATTERN.match(slug):
            raise TagVocabularyError(f"Tag slug must be lowercase and hyphenated: {slug!r}")
        if slug in seen:
            raise TagVocabularyError(f"Duplicate tag slug: {slug!r}")
        seen.add(slug)
    return tuple(parsed.tags)


def derive_tag_name(slug: str) -> str:
    """Human-readable display name for a slug (no name is stored in tags.yml)."""
    return slug.replace("-", " ").title()
