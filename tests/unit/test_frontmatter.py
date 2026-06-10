"""Specs for the Markdown frontmatter parser (pure domain, a trust boundary).

Untrusted document text enters here, so the specs cover each kind's happy path
plus the edges: missing/!unterminated fences, bad YAML, wrong enum values, bad
slugs, and per-kind block rules (a link must carry its block; an essay must not).
"""

import datetime

import pytest

from blog.enums import Kind, Status
from blog.frontmatter import (
    FrontmatterError,
    LinkFrontmatter,
    QuoteFrontmatter,
    parse_document,
)

ESSAY = (
    "title: On Simplicity\n"
    "slug: on-simplicity\n"
    "date: 2026-06-10\n"
    "kind: essay\n"
    "tags: [software-engineering]\n"
    "status: published\n"
)

LINK = (
    "title: A Good Read\n"
    "slug: a-good-read\n"
    "date: 2026-06-10\n"
    "kind: link\n"
    "tags: []\n"
    "status: published\n"
    "link:\n"
    "  url: https://example.com/post\n"
    "  source: Example\n"
)

QUOTE = (
    "title: On Systems\n"
    "slug: on-systems\n"
    "date: 2026-06-10\n"
    "kind: quote\n"
    "tags: []\n"
    "status: draft\n"
    "quote:\n"
    "  text: A system is never finished.\n"
    "  source: Donella Meadows\n"
)


def _doc(frontmatter: str, body: str = "Body text.") -> str:
    return f"---\n{frontmatter}---\n{body}"


class DescribeParsingEachKind:
    def it_parses_an_essay_with_the_full_spine(self) -> None:
        doc = parse_document(_doc(ESSAY))
        fm = doc.frontmatter
        assert fm.kind == Kind.ESSAY
        assert fm.title == "On Simplicity"
        assert fm.slug == "on-simplicity"
        assert fm.date == datetime.date(2026, 6, 10)
        assert fm.status == Status.PUBLISHED
        assert fm.tags == ["software-engineering"]
        assert doc.body == "Body text."

    def it_parses_a_til(self) -> None:
        doc = parse_document(_doc(ESSAY.replace("kind: essay", "kind: til")))
        assert doc.frontmatter.kind == Kind.TIL

    def it_parses_a_note(self) -> None:
        doc = parse_document(_doc(ESSAY.replace("kind: essay", "kind: note")))
        assert doc.frontmatter.kind == Kind.NOTE

    def it_parses_a_link_with_its_block(self) -> None:
        fm = parse_document(_doc(LINK)).frontmatter
        assert isinstance(fm, LinkFrontmatter)
        assert str(fm.link.url).startswith("https://example.com/post")
        assert fm.link.source == "Example"

    def it_parses_a_quote_with_an_optional_url(self) -> None:
        fm = parse_document(_doc(QUOTE)).frontmatter
        assert isinstance(fm, QuoteFrontmatter)
        assert fm.quote.text.startswith("A system")
        assert fm.quote.url is None


class DescribeRejectingStructure:
    def it_rejects_a_document_without_an_opening_fence(self) -> None:
        with pytest.raises(FrontmatterError, match="fence"):
            parse_document("title: x\n")

    def it_rejects_an_unterminated_fence(self) -> None:
        with pytest.raises(FrontmatterError, match="closed"):
            parse_document("---\ntitle: x\nno closing fence")

    def it_rejects_invalid_yaml(self) -> None:
        with pytest.raises(FrontmatterError):
            parse_document("---\n:\n  - : :\n---\nbody")

    def it_rejects_non_mapping_frontmatter(self) -> None:
        with pytest.raises(FrontmatterError, match="mapping"):
            parse_document("---\n- a\n- b\n---\nbody")


class DescribeRejectingSemantics:
    def it_rejects_a_missing_spine_field(self) -> None:
        with pytest.raises(FrontmatterError):
            parse_document(_doc(ESSAY.replace("title: On Simplicity\n", "")))

    def it_rejects_an_unknown_kind(self) -> None:
        with pytest.raises(FrontmatterError):
            parse_document(_doc(ESSAY.replace("kind: essay", "kind: rant")))

    def it_rejects_an_unknown_status(self) -> None:
        with pytest.raises(FrontmatterError):
            parse_document(_doc(ESSAY.replace("status: published", "status: live")))

    def it_rejects_a_non_slug_slug(self) -> None:
        with pytest.raises(FrontmatterError):
            parse_document(_doc(ESSAY.replace("slug: on-simplicity", "slug: On_Simplicity")))

    def it_rejects_a_link_missing_its_block(self) -> None:
        with pytest.raises(FrontmatterError):
            parse_document(_doc(ESSAY.replace("kind: essay", "kind: link")))

    def it_rejects_a_quote_missing_its_block(self) -> None:
        with pytest.raises(FrontmatterError):
            parse_document(_doc(ESSAY.replace("kind: essay", "kind: quote")))

    def it_rejects_an_essay_carrying_a_link_block(self) -> None:
        polluted = ESSAY + "link:\n  url: https://example.com\n  source: x\n"
        with pytest.raises(FrontmatterError):
            parse_document(_doc(polluted))

    def it_rejects_a_malformed_link_url(self) -> None:
        with pytest.raises(FrontmatterError):
            parse_document(_doc(LINK.replace("https://example.com/post", "not-a-url")))


class DescribeRoundTrip:
    def it_preserves_the_body_verbatim(self) -> None:
        body = "# Heading\n\nA paragraph with a [link](https://example.com).\n\nMore."
        assert parse_document(_doc(ESSAY, body=body)).body == body
