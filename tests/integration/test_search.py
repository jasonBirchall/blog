"""Integration specs for FTS5 full-text search over published posts."""

import time

import pytest

from blog.search import search_posts
from blog.sync import sync_content

pytestmark = pytest.mark.django_db

VOCAB = ["python", "django"]


def _doc(
    slug: str,
    *,
    title: str = "A Title",
    status: str = "published",
    body: str = "Body.",
) -> str:
    return (
        "---\n"
        f"title: {title}\n"
        f"slug: {slug}\n"
        "date: 2026-06-10\n"
        "kind: note\n"
        "tags: [python]\n"
        f"status: {status}\n"
        "---\n"
        f"{body}"
    )


def _sync(docs: dict[str, str]) -> None:
    assert sync_content(docs, VOCAB, write=True).wrote


class DescribeSearch:
    def it_finds_a_post_by_a_title_word(self) -> None:
        _sync({"a.md": _doc("a", title="Django Patterns")})
        assert [r.slug for r in search_posts("patterns")] == ["a"]

    def it_finds_a_post_by_a_body_word(self) -> None:
        _sync({"a.md": _doc("a", body="A note about asynchronous code.")})
        assert [r.slug for r in search_posts("asynchronous")] == ["a"]

    def it_ranks_more_relevant_posts_first(self) -> None:
        _sync(
            {
                "a.md": _doc("strong", title="Python Python", body="Python everywhere python."),
                "b.md": _doc("weak", title="Cooking", body="I mention python once."),
            }
        )
        results = search_posts("python")
        assert results[0].slug == "strong"
        assert {r.slug for r in results} == {"strong", "weak"}

    def it_excludes_drafts(self) -> None:
        _sync({"a.md": _doc("draft-post", title="Secret Python", status="draft")})
        assert search_posts("python") == []

    def it_excludes_deactivated_posts(self) -> None:
        _sync({"a.md": _doc("a", title="Findable"), "b.md": _doc("b", title="Findable too")})
        _sync({"a.md": _doc("a", title="Findable")})  # b's file removed -> deactivated
        assert {r.slug for r in search_posts("findable")} == {"a"}


class DescribeTokenisation:
    def it_returns_empty_for_a_blank_query(self) -> None:
        _sync({"a.md": _doc("a", title="Python")})
        assert search_posts("   ") == []

    def it_ignores_punctuation(self) -> None:
        _sync({"a.md": _doc("a", title="Python")})
        assert [r.slug for r in search_posts("python!?,")] == ["a"]

    def it_does_not_crash_on_fts_operators(self) -> None:
        _sync({"a.md": _doc("a", title="Python")})
        assert search_posts("python AND OR NOT *") == []  # literal words; no match, no error

    def it_requires_all_terms(self) -> None:
        _sync(
            {
                "a.md": _doc("both", title="Python and Django"),
                "b.md": _doc("one", title="Python only"),
            }
        )
        assert [r.slug for r in search_posts("python django")] == ["both"]


class DescribeBenchmark:
    def it_searches_a_large_corpus_quickly(self) -> None:
        docs = {
            f"p{i}.md": _doc(f"post-{i}", title=f"Title {i}", body=f"Body {i} common-term.")
            for i in range(500)
        }
        _sync(docs)
        start = time.perf_counter()
        results = search_posts("common-term", limit=20)
        elapsed = time.perf_counter() - start
        assert len(results) == 20
        assert elapsed < 0.5  # generous; FTS5 over 500 docs is sub-millisecond
