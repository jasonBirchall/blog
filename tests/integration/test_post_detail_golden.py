"""Golden-HTML specs for the post-detail <article>, one per kind.

Each input under tests/golden/posts/ is synced, rendered at /posts/<slug>, and
its <article> block is compared to the committed .html. Regenerate
intentionally and review the diff when the templates change.
"""

from pathlib import Path

import pytest
from django.test import Client

from blog.models import Post
from blog.sync import sync_content

pytestmark = pytest.mark.django_db

_POSTS = Path(__file__).parent.parent / "golden" / "posts"
_INPUTS = sorted(_POSTS.glob("*.md"))


def _article(html: str) -> str:
    start = html.index("<article")
    end = html.index("</article>") + len("</article>")
    return html[start:end]


def _normalize(text: str) -> str:
    # Trailing whitespace per line (and a trailing newline) are insignificant in
    # HTML and are stripped from the committed goldens by .editorconfig.
    return "\n".join(line.rstrip() for line in text.splitlines())


class DescribeGoldenPostDetail:
    @pytest.mark.parametrize("source", _INPUTS, ids=lambda path: path.stem)
    def it_matches_the_committed_article(self, client: Client, source: Path) -> None:
        assert sync_content(
            {source.name: source.read_text(encoding="utf-8")}, ["python"], write=True
        ).wrote
        slug = Post.objects.values_list("slug", flat=True).get()
        article = _article(client.get(f"/posts/{slug}").content.decode())
        golden = source.with_suffix(".html").read_text(encoding="utf-8")
        assert _normalize(article) == _normalize(golden)
