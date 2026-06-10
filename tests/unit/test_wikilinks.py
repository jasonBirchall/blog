"""Specs for [[slug]] wikilink resolution (pure domain).

Only slug-shaped targets are wikilinks: a known slug becomes an anchor, an
unknown slug-shaped target raises (the sync command surfaces it), and a
non-slug target like [[Donella Meadows]] stays literal. Code spans and fenced
blocks are never touched.
"""

import pytest

from blog.rendering import render_markdown
from blog.wikilinks import UnresolvedWikilinkError

INDEX = {"on-systems": "On Systems", "ports-and-adapters": "Ports & Adapters"}


class DescribeResolvedWikilinks:
    def it_rewrites_a_known_slug_to_an_anchor(self) -> None:
        html = render_markdown("See [[on-systems]] for more.", slug_index=INDEX)
        assert '<a href="/posts/on-systems"' in html
        assert ">On Systems</a>" in html

    def it_resolves_several_in_one_document(self) -> None:
        html = render_markdown("[[on-systems]] and [[ports-and-adapters]].", slug_index=INDEX)
        assert "/posts/on-systems" in html
        assert "/posts/ports-and-adapters" in html


class DescribeUnresolvedWikilinks:
    def it_raises_for_a_slug_shaped_target_not_in_the_index(self) -> None:
        with pytest.raises(UnresolvedWikilinkError, match="missing-post"):
            render_markdown("A [[missing-post]] link.", slug_index=INDEX)


class DescribeNonSlugWikilinks:
    def it_leaves_a_non_slug_target_as_literal_text(self) -> None:
        html = render_markdown("Quoting [[Donella Meadows]] here.", slug_index=INDEX)
        assert "Donella Meadows" in html
        assert "<a " not in html

    def it_does_not_raise_for_a_non_slug_target(self) -> None:
        render_markdown("[[Some Title With Spaces]]", slug_index=INDEX)


class DescribeCodeSafety:
    def it_ignores_a_wikilink_in_an_inline_code_span(self) -> None:
        html = render_markdown("Literal `[[on-systems]]` token.", slug_index=INDEX)
        assert "<code>[[on-systems]]</code>" in html
        assert "<a " not in html

    def it_does_not_raise_for_an_unresolved_wikilink_in_a_code_block(self) -> None:
        html = render_markdown("```\n[[ghost-post]]\n```\n", slug_index=INDEX)
        assert "[[ghost-post]]" in html
