"""Resolve [[slug]] wikilinks to anchors against the published-post index.

Implemented as a markdown-it inline rule so wikilinks inside code spans and
fenced blocks are left untouched. Only slug-shaped targets are treated as
wikilinks: a slug-shaped target that is not a published post raises
UnresolvedWikilinkError (surfaced by the sync command); a non-slug target such as
[[Donella Meadows]] is left as literal text.
"""

from collections.abc import Callable, Mapping

from markdown_it import MarkdownIt
from markdown_it.rules_inline import StateInline

from blog.tags import SLUG_PATTERN

SlugIndex = Mapping[str, str]  # published slug -> title

_OPEN = "[["
_CLOSE = "]]"


class UnresolvedWikilinkError(Exception):
    """A slug-shaped wikilink pointing at no published post. The message is quotable."""


def _make_rule(index: SlugIndex) -> Callable[[StateInline, bool], bool]:
    def _wikilink(state: StateInline, silent: bool) -> bool:
        start = state.pos
        if not state.src.startswith(_OPEN, start):
            return False
        close = state.src.find(_CLOSE, start + len(_OPEN))
        if close == -1:
            return False
        target = state.src[start + len(_OPEN) : close]
        if not SLUG_PATTERN.match(target):
            return False  # not slug-shaped -> leave [[...]] as literal text
        title = index.get(target)
        if title is None:
            raise UnresolvedWikilinkError(f"Unresolved wikilink: {_OPEN}{target}{_CLOSE}")
        if not silent:
            opening = state.push("link_open", "a", 1)
            opening.attrSet("href", f"/posts/{target}")
            text = state.push("text", "", 0)
            text.content = title
            state.push("link_close", "a", -1)
        state.pos = close + len(_CLOSE)
        return True

    return _wikilink


def wikilink_plugin(md: MarkdownIt, index: SlugIndex) -> None:
    """Register the wikilink inline rule on a MarkdownIt instance."""
    md.inline.ruler.before("link", "wikilink", _make_rule(index))
