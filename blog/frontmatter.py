"""Parse and validate Markdown frontmatter into typed, immutable objects.

Pure domain (no Django). A document is `---`-fenced YAML frontmatter followed by
a Markdown body. The frontmatter is validated against a per-kind schema as a
discriminated union, so invalid states are unrepresentable: a link post must
carry a link block, a quote post a quote block, and an essay neither. Errors are
raised as FrontmatterError with a precise, quotable message.
"""

import datetime
from dataclasses import dataclass
from typing import Annotated, Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    TypeAdapter,
    ValidationError,
)

from blog.enums import Kind, Status
from blog.tags import SLUG_PATTERN

_FENCE = "---"

Slug = Annotated[str, StringConstraints(pattern=SLUG_PATTERN.pattern)]


class FrontmatterError(Exception):
    """Raised when frontmatter is missing or invalid. The message is quotable."""


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class LinkBlock(_Strict):
    url: HttpUrl
    source: str


class QuoteBlock(_Strict):
    text: str
    source: str
    url: HttpUrl | None = None


class _Spine(_Strict):
    title: str
    slug: Slug
    date: datetime.date
    updated: datetime.date | None = None
    tags: list[Slug]
    status: Status


class EssayFrontmatter(_Spine):
    kind: Literal[Kind.ESSAY]


class TilFrontmatter(_Spine):
    kind: Literal[Kind.TIL]


class NoteFrontmatter(_Spine):
    kind: Literal[Kind.NOTE]


class LinkFrontmatter(_Spine):
    kind: Literal[Kind.LINK]
    link: LinkBlock


class QuoteFrontmatter(_Spine):
    kind: Literal[Kind.QUOTE]
    quote: QuoteBlock


Frontmatter = Annotated[
    EssayFrontmatter | TilFrontmatter | NoteFrontmatter | LinkFrontmatter | QuoteFrontmatter,
    Field(discriminator="kind"),
]

_FRONTMATTER = TypeAdapter(Frontmatter)


@dataclass(frozen=True)
class ParsedDocument:
    frontmatter: (
        EssayFrontmatter | TilFrontmatter | NoteFrontmatter | LinkFrontmatter | QuoteFrontmatter
    )
    body: str


def split_frontmatter(text: str) -> tuple[str, str]:
    """Return (yaml_text, body), raising if the `---` fences are missing."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FENCE:
        raise FrontmatterError("Document does not start with a '---' frontmatter fence")
    for index in range(1, len(lines)):
        if lines[index].strip() == _FENCE:
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :])
    raise FrontmatterError("Frontmatter is not closed by a matching '---' fence")


def parse_document(text: str) -> ParsedDocument:
    """Parse a full document into validated frontmatter plus its Markdown body."""
    yaml_text, body = split_frontmatter(text)
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"Frontmatter is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise FrontmatterError("Frontmatter must be a YAML mapping")
    try:
        frontmatter = _FRONTMATTER.validate_python(data)
    except ValidationError as exc:
        raise FrontmatterError(f"Invalid frontmatter: {exc}") from exc
    return ParsedDocument(frontmatter=frontmatter, body=body)
