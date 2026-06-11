"""Integration specs for sync_content: parse -> render -> upsert, transactionally."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from blog import sync as sync_module
from blog.models import Post
from blog.sync import sync_content

pytestmark = pytest.mark.django_db

VOCAB = ["python", "django"]


def _doc(
    *,
    slug: str = "a-post",
    tags: str = "[python]",
    status: str = "published",
    body: str = "Body.",
) -> str:
    return (
        "---\n"
        "title: A Title\n"
        f"slug: {slug}\n"
        "date: 2026-06-10\n"
        "kind: note\n"
        f"tags: {tags}\n"
        f"status: {status}\n"
        "---\n"
        f"{body}"
    )


class DescribeWriting:
    def it_creates_posts(self) -> None:
        report = sync_content({"a.md": _doc(slug="a")}, VOCAB, write=True)
        assert report.created == 1
        assert Post.objects.filter(slug="a", is_active=True).exists()

    def it_regenerates_html_and_excerpt(self) -> None:
        body = "A summary sentence.\n\nMore detail here."
        sync_content({"a.md": _doc(slug="a", body=body)}, VOCAB, write=True)
        post = Post.objects.get(slug="a")
        assert "<p>A summary sentence.</p>" in post.body_html
        assert post.excerpt == "A summary sentence."

    def it_updates_an_existing_post(self) -> None:
        sync_content({"a.md": _doc(slug="a", body="One")}, VOCAB, write=True)
        report = sync_content({"a.md": _doc(slug="a", body="Two")}, VOCAB, write=True)
        assert report.updated == 1
        assert "Two" in Post.objects.get(slug="a").body_html

    def it_associates_tags_from_the_vocabulary(self) -> None:
        sync_content({"a.md": _doc(slug="a", tags="[python, django]")}, VOCAB, write=True)
        assert set(Post.objects.get(slug="a").tags.values_list("slug", flat=True)) == {
            "python",
            "django",
        }

    def it_resolves_wikilinks_between_posts(self) -> None:
        docs = {
            "a.md": _doc(slug="target", body="Hi"),
            "b.md": _doc(slug="src", body="See [[target]]."),
        }
        sync_content(docs, VOCAB, write=True)
        assert '/posts/target"' in Post.objects.get(slug="src").body_html

    def it_marks_deleted_files_inactive(self) -> None:
        sync_content({"a.md": _doc(slug="a"), "b.md": _doc(slug="b")}, VOCAB, write=True)
        report = sync_content({"a.md": _doc(slug="a")}, VOCAB, write=True)
        assert report.deactivated == 1
        assert Post.objects.get(slug="b").is_active is False
        assert Post.objects.get(slug="a").is_active is True


class DescribeCheckMode:
    def it_does_not_touch_the_database(self) -> None:
        report = sync_content({"a.md": _doc(slug="a")}, VOCAB, write=False)
        assert report.wrote is False
        assert Post.objects.count() == 0

    def it_reports_errors_for_bad_content(self) -> None:
        report = sync_content({"a.md": _doc(slug="a", tags="[rust]")}, VOCAB, write=False)
        assert report.errors
        assert Post.objects.count() == 0


class DescribeValidationAbort:
    def it_does_not_write_when_content_is_invalid(self) -> None:
        report = sync_content({"a.md": _doc(slug="a", tags="[rust]")}, VOCAB, write=True)
        assert report.errors
        assert report.wrote is False
        assert Post.objects.count() == 0


class DescribeTransactionalRollback:
    def it_rolls_back_a_partial_write_on_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = {"n": 0}

        def boom(body: str, index: dict[str, str]) -> str:
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("injected failure mid-sync")
            return "<p>ok</p>"

        monkeypatch.setattr(sync_module, "_render_html", boom)
        docs = {"a.md": _doc(slug="a"), "b.md": _doc(slug="b")}
        with pytest.raises(RuntimeError, match="injected"):
            sync_content(docs, VOCAB, write=True)
        assert Post.objects.count() == 0


class DescribeManagementCommand:
    def it_writes_in_default_mode_over_a_content_directory(self, tmp_path) -> None:
        (tmp_path / "a.md").write_text(_doc(slug="a"), encoding="utf-8")
        tags = tmp_path / "tags.yml"
        tags.write_text("tags:\n  - python\n", encoding="utf-8")
        call_command("sync_content", "--content", str(tmp_path), "--tags", str(tags))
        assert Post.objects.filter(slug="a").exists()

    def it_exits_nonzero_on_bad_content_in_check_mode(self, tmp_path) -> None:
        (tmp_path / "a.md").write_text(_doc(slug="a", tags="[rust]"), encoding="utf-8")
        tags = tmp_path / "tags.yml"
        tags.write_text("tags:\n  - python\n", encoding="utf-8")
        with pytest.raises(CommandError):
            call_command("sync_content", "--check", "--content", str(tmp_path), "--tags", str(tags))
        assert Post.objects.count() == 0
