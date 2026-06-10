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
