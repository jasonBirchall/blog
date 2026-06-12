"""Regenerate the golden files; review the result with `git diff tests/golden`.

Run via `make golden`. Markdown goldens (tests/golden/markdown/*.html) are
re-rendered through render_markdown verbatim. Post goldens
(tests/golden/posts/*.html) are rendered through the post-detail view in a
throwaway test database; the <article> is extracted with trailing whitespace
stripped per line, matching the committed, .editorconfig-normalised files so the
diff is meaningful.
"""

from pathlib import Path

_MARKDOWN = Path("tests/golden/markdown")
_POSTS = Path("tests/golden/posts")


def _regenerate_markdown() -> None:
    from blog.rendering import render_markdown

    for source in sorted(_MARKDOWN.glob("*.md")):
        rendered = render_markdown(source.read_text(encoding="utf-8"))
        source.with_suffix(".html").write_text(rendered, encoding="utf-8")


def _regenerate_posts() -> None:
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")

    import django

    django.setup()

    from django.conf import settings
    from django.test import Client
    from django.test.runner import DiscoverRunner
    from django.test.utils import setup_test_environment

    from blog.models import Post
    from blog.sync import sync_content

    settings.ALLOWED_HOSTS = ["testserver"]
    setup_test_environment()
    runner = DiscoverRunner(verbosity=0)
    databases = runner.setup_databases()
    client = Client()
    for source in sorted(_POSTS.glob("*.md")):
        Post.objects.all().delete()
        sync_content({source.name: source.read_text(encoding="utf-8")}, ["python"], write=True)
        slug = Post.objects.values_list("slug", flat=True).get()
        html = client.get(f"/posts/{slug}").content.decode()
        start = html.index("<article")
        end = html.index("</article>") + len("</article>")
        article = "\n".join(line.rstrip() for line in html[start:end].splitlines())
        source.with_suffix(".html").write_text(article + "\n", encoding="utf-8")
    runner.teardown_databases(databases)


if __name__ == "__main__":
    _regenerate_markdown()
    _regenerate_posts()
    print("Regenerated goldens. Review with: git diff tests/golden")
