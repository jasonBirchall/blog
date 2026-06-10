"""Golden-file specs for the Markdown renderer.

Each input under tests/golden/markdown/ is rendered and compared byte-for-byte
to its committed .html. Regenerate intentionally and review the diff when the
renderer or its pinned dependencies change.
"""

from pathlib import Path

import pytest

from blog.rendering import render_markdown

_GOLDEN_DIR = Path(__file__).parent.parent / "golden" / "markdown"
_INPUTS = sorted(_GOLDEN_DIR.glob("*.md"))


class DescribeGoldenRendering:
    @pytest.mark.parametrize("source", _INPUTS, ids=lambda path: path.stem)
    def it_matches_the_committed_html(self, source: Path) -> None:
        expected = source.with_suffix(".html").read_text(encoding="utf-8")
        assert render_markdown(source.read_text(encoding="utf-8")) == expected
