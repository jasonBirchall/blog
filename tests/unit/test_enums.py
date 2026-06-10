"""Specs for the content vocabulary enums (framework-free domain types)."""

from blog.enums import Kind, Status


class DescribeKind:
    def it_is_the_closed_set_of_post_kinds(self) -> None:
        assert {k.value for k in Kind} == {"essay", "link", "quote", "til", "note"}

    def it_is_a_string_enum(self) -> None:
        assert Kind.ESSAY == "essay"


class DescribeStatus:
    def it_is_draft_or_published(self) -> None:
        assert {s.value for s in Status} == {"draft", "published"}

    def it_is_a_string_enum(self) -> None:
        assert Status.PUBLISHED == "published"
