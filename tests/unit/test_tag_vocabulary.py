"""Specs for the tag controlled-vocabulary loader (a config trust boundary).

Untrusted YAML enters here, so the specs focus on the edges: duplicates, bad
casing, hierarchy, and wrong shape must all fail with a precise, quotable error.
"""

from pathlib import Path

import pytest
from django.conf import settings

from blog.tags import TagVocabularyError, derive_tag_name, load_tag_vocabulary


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "tags.yml"
    path.write_text(body, encoding="utf-8")
    return path


class DescribeLoadTagVocabulary:
    def it_loads_a_flat_list_of_slugs(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "tags:\n  - python\n  - django\n")
        assert load_tag_vocabulary(path) == ("python", "django")

    def it_accepts_an_empty_vocabulary(self, tmp_path: Path) -> None:
        assert load_tag_vocabulary(_write(tmp_path, "tags: []\n")) == ()

    def it_rejects_duplicate_slugs(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "tags:\n  - python\n  - python\n")
        with pytest.raises(TagVocabularyError, match=r"[Dd]uplicate"):
            load_tag_vocabulary(path)

    def it_rejects_non_lowercase_hyphenated_slugs(self, tmp_path: Path) -> None:
        with pytest.raises(TagVocabularyError):
            load_tag_vocabulary(_write(tmp_path, "tags:\n  - Python\n"))

    def it_rejects_hierarchical_slugs(self, tmp_path: Path) -> None:
        with pytest.raises(TagVocabularyError):
            load_tag_vocabulary(_write(tmp_path, "tags:\n  - tech/python\n"))

    def it_rejects_a_file_without_a_tags_key(self, tmp_path: Path) -> None:
        with pytest.raises(TagVocabularyError):
            load_tag_vocabulary(_write(tmp_path, "categories:\n  - python\n"))


class DescribeDeriveTagName:
    def it_titlecases_a_single_word(self) -> None:
        assert derive_tag_name("python") == "Python"

    def it_titlecases_a_hyphenated_slug(self) -> None:
        assert derive_tag_name("ports-and-adapters") == "Ports And Adapters"


class DescribeCommittedVocabulary:
    def it_parses_the_repository_tags_file(self) -> None:
        slugs = load_tag_vocabulary(settings.TAG_VOCABULARY_PATH)
        assert isinstance(slugs, tuple)
