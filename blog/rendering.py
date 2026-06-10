"""Render Markdown post bodies to sanitised, semantic HTML.

Pure domain (no Django). markdown-it-py (CommonMark + tables + footnotes) with
Pygments-highlighted fenced code and no smart-quote typography. The output is
then sanitised with nh3: only Markdown-generated structure, Pygments/footnote
markup, and a small hand-written inline allow-list survive — everything else
(scripts, styles, event handlers, javascript: URLs) is stripped.
"""

import nh3
from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin
from pygments import highlight as pygments_highlight

# Import from the concrete submodule: pygments.formatters loads names
# dynamically, which a static type checker can't resolve.
from pygments.formatters.html import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

_FORMATTER = HtmlFormatter(nowrap=True)


def _highlight(code: str, lang: str, _attrs: str) -> str:
    """Highlight a fenced block with Pygments, or fall back to default escaping.

    Returning a string that starts with ``<pre`` makes markdown-it use it as-is;
    returning "" lets markdown-it render a plain escaped ``<pre><code>`` block.
    """
    if not lang:
        return ""
    try:
        lexer = get_lexer_by_name(lang)
    except ClassNotFound:
        return ""
    inner = pygments_highlight(code, lexer, _FORMATTER)
    return f'<pre class="highlight"><code class="language-{lang}">{inner}</code></pre>'


_MARKDOWN = MarkdownIt(
    "commonmark",
    {"html": True, "typographer": False, "highlight": _highlight},
)
_MARKDOWN.enable("table")
_MARKDOWN.use(footnote_plugin)

# nh3 replaces (not extends) its defaults, so this set must be exhaustive:
# Markdown structure + Pygments/footnote markup + the hand-written inline tags.
_ALLOWED_TAGS = {
    "p",
    "a",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "ul",
    "ol",
    "li",
    "hr",
    "br",
    "em",
    "strong",
    "code",
    "pre",
    "img",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "span",
    "div",
    "section",
    "sup",
    "sub",
    # Hand-written inline allow-list:
    "abbr",
    "kbd",
    "mark",
    "cite",
    "del",
    "ins",
}

_ALLOWED_ATTRIBUTES = {
    "a": {"href", "id", "class", "title"},
    "img": {"src", "alt", "title"},
    "ol": {"class", "start"},
    "ul": {"class"},
    "li": {"id", "class"},
    "section": {"class"},
    "hr": {"class"},
    "sup": {"class", "id"},
    "span": {"class"},
    "code": {"class"},
    "pre": {"class"},
    "abbr": {"title"},
}


def render_markdown(text: str) -> str:
    """Render a Markdown body to sanitised, semantic HTML."""
    raw_html = _MARKDOWN.render(text)
    return nh3.clean(raw_html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRIBUTES)
