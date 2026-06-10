"""Behaviour specs for the Markdown renderer (pure domain).

The golden files lock exact output; these assert the guarantees that matter and
would be easy to miss in a diff: no smart quotes, Pygments highlighting,
footnotes, and the inline-HTML allow-list / sanitisation.
"""

from blog.rendering import render_markdown


class DescribeTypography:
    def it_keeps_straight_quotes(self) -> None:
        html = render_markdown('He said "hello".')
        assert '"hello"' in html
        assert "“" not in html and "”" not in html

    def it_keeps_double_hyphens(self) -> None:
        assert "—" not in render_markdown("a -- b")


class DescribeStructure:
    def it_renders_tables(self) -> None:
        html = render_markdown("| a | b |\n| - | - |\n| 1 | 2 |\n")
        assert "<table>" in html
        assert "<td>1</td>" in html

    def it_renders_footnotes_in_a_section(self) -> None:
        html = render_markdown("A claim.[^1]\n\n[^1]: The evidence.\n")
        assert "<sup" in html
        assert 'class="footnotes"' in html

    def it_highlights_fenced_code_with_pygments(self) -> None:
        html = render_markdown("```python\ndef f():\n    return 1\n```\n")
        assert 'class="language-python"' in html
        assert 'class="k"' in html  # Pygments keyword token for `def`

    def it_falls_back_cleanly_for_an_unknown_language(self) -> None:
        html = render_markdown("```nope\nplain text\n```\n")
        assert "<pre" in html
        assert "plain text" in html


class DescribeInlineHtmlAllowList:
    def it_keeps_an_allowed_inline_tag(self) -> None:
        assert "<kbd>Esc</kbd>" in render_markdown("Press <kbd>Esc</kbd>.")

    def it_strips_a_disallowed_tag_and_its_script(self) -> None:
        html = render_markdown("Hi <script>alert(1)</script> there")
        assert "<script" not in html
        assert "alert(1)" not in html

    def it_refuses_to_linkify_a_javascript_url(self) -> None:
        # markdown-it leaves a dangerous link destination as inert text.
        assert "<a " not in render_markdown("[x](javascript:alert(1))")

    def it_strips_javascript_scheme_from_raw_html_links(self) -> None:
        assert "javascript:" not in render_markdown('<a href="javascript:alert(1)">x</a>')
