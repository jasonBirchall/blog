"""Content linter: the checks, as pure functions over in-memory documents.

No filesystem or Django here (the CLI adapter in blog.lint_content does the I/O).
Each problem is a LintError carrying a 1-based line number where one can be
located, so the output is precise and quotable.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from blog.enums import Status
from blog.frontmatter import FrontmatterError, ParsedDocument, parse_document
from blog.rendering import render_markdown
from blog.wikilinks import UnresolvedWikilinkError

# Built from code points, not glyphs: literal smart quotes would themselves trip
# ruff's ambiguous-character rule.
_SMART_QUOTES = {chr(0x201C), chr(0x201D), chr(0x2018), chr(0x2019)}


@dataclass(frozen=True, order=True)
class LintError:
    path: str
    line: int
    message: str


def _line_of(text: str, needle: str) -> int:
    index = text.find(needle)
    return text.count("\n", 0, index) + 1 if index != -1 else 1


def _line_checks(path: str, text: str) -> list[LintError]:
    errors: list[LintError] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if line != line.rstrip():
            errors.append(LintError(path, number, "Trailing whitespace"))
        for quote in _SMART_QUOTES:
            if quote in line:
                errors.append(
                    LintError(path, number, f"Smart quote {quote!r}; use a straight quote")
                )
    return errors


def lint_content(documents: Mapping[str, str], vocabulary: Iterable[str]) -> list[LintError]:
    """Run every content check across a set of {path: text} documents."""
    vocab = set(vocabulary)
    errors: list[LintError] = []
    parsed: dict[str, tuple[str, ParsedDocument]] = {}

    for path, text in documents.items():
        errors.extend(_line_checks(path, text))
        try:
            doc = parse_document(text)
        except FrontmatterError as exc:
            errors.append(LintError(path, 1, str(exc)))
            continue
        parsed[path] = (text, doc)
        for tag in doc.frontmatter.tags:
            if tag not in vocab:
                errors.append(LintError(path, _line_of(text, tag), f"Unknown tag: {tag!r}"))

    seen: dict[str, str] = {}
    for path, (text, doc) in parsed.items():
        slug = doc.frontmatter.slug
        if slug in seen:
            errors.append(
                LintError(
                    path, _line_of(text, slug), f"Duplicate slug {slug!r} (also in {seen[slug]})"
                )
            )
        else:
            seen[slug] = path

    index = {
        doc.frontmatter.slug: doc.frontmatter.title
        for _, doc in parsed.values()
        if doc.frontmatter.status == Status.PUBLISHED
    }
    for path, (text, doc) in parsed.items():
        try:
            render_markdown(doc.body, slug_index=index)
        except UnresolvedWikilinkError as exc:
            marker = str(exc).split(": ", 1)[-1]
            errors.append(LintError(path, _line_of(text, marker), str(exc)))

    return sorted(errors)
