"""Model-invariant specs for Post and Tag (the persistence adapter)."""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from blog.enums import Kind, Status
from blog.models import Post, Tag

pytestmark = pytest.mark.django_db


def _make_post(**overrides: object) -> Post:
    fields: dict[str, object] = {
        "title": "Hello",
        "slug": "hello",
        "date": datetime.date(2026, 6, 10),
        "kind": Kind.NOTE.value,
        "body_markdown": "hi",
        "status": Status.PUBLISHED.value,
    }
    fields.update(overrides)
    return Post.objects.create(**fields)


class DescribePost:
    def it_persists_with_valid_fields(self) -> None:
        assert _make_post().pk is not None

    def it_enforces_globally_unique_slugs_across_kinds(self) -> None:
        _make_post(slug="dup", kind=Kind.NOTE.value)
        with pytest.raises(IntegrityError):
            _make_post(slug="dup", kind=Kind.ESSAY.value)

    def it_rejects_an_unknown_kind_on_validation(self) -> None:
        post = Post(
            title="x",
            slug="x",
            date=datetime.date(2026, 6, 10),
            kind="bogus",
            body_markdown="x",
            status=Status.DRAFT.value,
        )
        with pytest.raises(ValidationError):
            post.full_clean()

    def it_orders_newest_first(self) -> None:
        old = _make_post(slug="old", date=datetime.date(2020, 1, 1))
        new = _make_post(slug="new", date=datetime.date(2026, 1, 1))
        assert list(Post.objects.all()) == [new, old]

    def it_links_tags(self) -> None:
        post = _make_post()
        tag = Tag.objects.create(slug="python", name="Python")
        post.tags.add(tag)
        assert list(post.tags.all()) == [tag]

    def it_stringifies_as_kind_and_title(self) -> None:
        assert str(_make_post(kind=Kind.LINK.value, title="A Link")) == "link: A Link"


class DescribeTag:
    def it_enforces_unique_slugs(self) -> None:
        Tag.objects.create(slug="python", name="Python")
        with pytest.raises(IntegrityError):
            Tag.objects.create(slug="python", name="Python again")

    def it_stringifies_as_its_slug(self) -> None:
        assert str(Tag.objects.create(slug="django", name="Django")) == "django"
