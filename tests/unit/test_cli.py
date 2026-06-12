"""Specs for the authoring CLI (blog.cli): new and promote."""

import datetime
from pathlib import Path

import pytest

from blog.cli import create_post, main, promote_note
from blog.enums import Kind, Status
from blog.frontmatter import LinkFrontmatter, QuoteFrontmatter, parse_document
from blog.linting import lint_content

TODAY = datetime.date(2026, 6, 12)


class DescribeNew:
    def it_creates_a_lint_clean_draft_stub(self, tmp_path: Path) -> None:
        path = create_post(tmp_path, "til", "my-slug", today=TODAY)
        assert path == tmp_path / "my-slug.md"
        text = path.read_text(encoding="utf-8")
        frontmatter = parse_document(text).frontmatter
        assert frontmatter.kind == Kind.TIL
        assert frontmatter.status == Status.DRAFT
        assert frontmatter.date == TODAY
        assert lint_content({path.name: text}, []) == []

    def it_stubs_a_link_block_for_a_link(self, tmp_path: Path) -> None:
        path = create_post(tmp_path, "link", "a-link", today=TODAY)
        assert isinstance(parse_document(path.read_text()).frontmatter, LinkFrontmatter)

    def it_stubs_a_quote_block_for_a_quote(self, tmp_path: Path) -> None:
        path = create_post(tmp_path, "quote", "a-quote", today=TODAY)
        assert isinstance(parse_document(path.read_text()).frontmatter, QuoteFrontmatter)

    def it_slugifies_the_given_slug(self, tmp_path: Path) -> None:
        assert create_post(tmp_path, "note", "My Post!", today=TODAY).name == "my-post.md"

    def it_refuses_to_overwrite(self, tmp_path: Path) -> None:
        create_post(tmp_path, "note", "dup", today=TODAY)
        with pytest.raises(FileExistsError):
            create_post(tmp_path, "note", "dup", today=TODAY)

    def it_rejects_an_unknown_kind(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="rant"):
            create_post(tmp_path, "rant", "x", today=TODAY)


class DescribePromote:
    def _tags(self, tmp_path: Path) -> Path:
        path = tmp_path / "tags.yml"
        path.write_text("tags:\n  - python\n", encoding="utf-8")
        return path

    def it_copies_a_note_into_content(self, tmp_path: Path) -> None:
        content = tmp_path / "content"
        note = tmp_path / "my-zettel.md"
        note.write_text("Some collected thoughts.", encoding="utf-8")
        path, errors = promote_note(content, self._tags(tmp_path), note, today=TODAY)
        assert path == content / "my-zettel.md"
        assert "Some collected thoughts." in path.read_text(encoding="utf-8")
        assert errors == []

    def it_surfaces_lint_problems(self, tmp_path: Path) -> None:
        content = tmp_path / "content"
        note = tmp_path / "bad.md"
        note.write_text("A line with trailing space.   ", encoding="utf-8")
        _path, errors = promote_note(content, self._tags(tmp_path), note, today=TODAY)
        assert any("railing whitespace" in error.message for error in errors)


class DescribeCli:
    def it_runs_new_via_main(self, tmp_path: Path) -> None:
        assert main(["new", "til", "hello", "--content", str(tmp_path)]) == 0
        assert (tmp_path / "hello.md").exists()
