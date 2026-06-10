"""Specs for the content linter's pure checks (no filesystem, no Django).

Each check is exercised with in-memory documents. Line-numbered checks
(trailing whitespace, smart quotes) assert the exact line.
"""

from blog.linting import lint_content

VOCAB = ["python", "django"]


def _doc(
    *,
    slug: str = "a-post",
    kind: str = "note",
    tags: str = "[]",
    status: str = "published",
    body: str = "Body.",
) -> str:
    return (
        "---\n"
        "title: A Title\n"
        f"slug: {slug}\n"
        "date: 2026-06-10\n"
        f"kind: {kind}\n"
        f"tags: {tags}\n"
        f"status: {status}\n"
        "---\n"
        f"{body}"
    )


class DescribeCleanContent:
    def it_reports_nothing_for_a_valid_document(self) -> None:
        assert lint_content({"ok.md": _doc(tags="[python]")}, VOCAB) == []


class DescribeFrontmatter:
    def it_flags_invalid_frontmatter(self) -> None:
        errors = lint_content({"bad.md": "---\nnot a mapping\n---\nbody"}, VOCAB)
        assert any("mapping" in e.message.lower() for e in errors)
        assert all(e.path == "bad.md" for e in errors)


class DescribeSlugUniqueness:
    def it_flags_a_duplicate_slug_across_files(self) -> None:
        docs = {
            "a.md": _doc(slug="dup", tags="[python]"),
            "b.md": _doc(slug="dup", tags="[python]"),
        }
        errors = lint_content(docs, VOCAB)
        assert any("Duplicate slug" in e.message and "dup" in e.message for e in errors)


class DescribeTagVocabulary:
    def it_flags_a_tag_not_in_the_vocabulary(self) -> None:
        errors = lint_content({"a.md": _doc(tags="[rust]")}, VOCAB)
        assert any("Unknown tag" in e.message and "rust" in e.message for e in errors)


class DescribeWikilinks:
    def it_flags_an_unresolved_wikilink(self) -> None:
        errors = lint_content({"a.md": _doc(tags="[python]", body="See [[ghost-post]].")}, VOCAB)
        assert any("ghost-post" in e.message for e in errors)

    def it_allows_a_wikilink_to_a_published_post(self) -> None:
        docs = {
            "target.md": _doc(slug="target", tags="[python]", body="Hi"),
            "src.md": _doc(slug="src", tags="[python]", body="See [[target]]."),
        }
        assert lint_content(docs, VOCAB) == []


class DescribeWhitespaceAndQuotes:
    def it_flags_trailing_whitespace_on_the_right_line(self) -> None:
        text = _doc(tags="[python]", body="A trailing line.   ")
        errors = [
            e for e in lint_content({"a.md": text}, VOCAB) if "railing whitespace" in e.message
        ]
        assert errors
        assert errors[0].line == len(text.splitlines())

    def it_flags_a_smart_quote(self) -> None:
        text = _doc(tags="[python]", body="He said “hello”.")
        assert any("Smart quote" in e.message for e in lint_content({"a.md": text}, VOCAB))
