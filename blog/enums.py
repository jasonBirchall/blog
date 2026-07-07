"""Content vocabulary as framework-free domain types.

These are pure Python (no Django import) so the markdown frontmatter parser can
share the exact same vocabulary as the ORM without depending on the framework.
"""

from enum import StrEnum


class Kind(StrEnum):
    ESSAY = "essay"
    LINK = "link"
    QUOTE = "quote"
    TIL = "til"
    NOTE = "note"


class Status(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


# Slugs that render at their own top-level route (e.g. /now), not /posts/<slug>.
# A reserved slug is synced through the normal content pipeline but excluded from
# the home stream, feed, archive, tag counts, search index, and the post sitemap.
RESERVED_SLUGS = frozenset({"now", "about"})
