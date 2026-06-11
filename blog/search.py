"""Full-text search over published posts via SQLite FTS5.

The FTS5 virtual table (post_fts) is created by a migration and populated by
sync_content. User input is reduced to quoted word terms before it reaches
MATCH, so it can never trigger FTS5 operator-syntax errors.
"""

import re
from dataclasses import dataclass

from django.db import connection

_WORD = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class SearchResult:
    slug: str
    title: str


def _to_match_query(raw: str) -> str:
    # Quote each word as an FTS5 phrase; space-separated phrases are implicit AND.
    return " ".join(f'"{term}"' for term in _WORD.findall(raw))


def search_posts(query: str, *, limit: int = 20) -> list[SearchResult]:
    """Return published posts matching every word in the query, best-ranked first."""
    match_query = _to_match_query(query)
    if not match_query:
        return []
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT slug, title FROM post_fts WHERE post_fts MATCH %s ORDER BY rank LIMIT %s",
            [match_query, limit],
        )
        return [SearchResult(slug=slug, title=title) for slug, title in cursor.fetchall()]
