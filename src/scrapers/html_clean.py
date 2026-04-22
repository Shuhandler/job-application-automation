"""HTML → plaintext normalization using selectolax.

Keeps structural whitespace (paragraph / list breaks) without leaking
markup. Intentionally conservative: we don't attempt main-content
detection here — that's a Phase 2 concern.
"""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

_BLOCK_TAGS = frozenset(
    {
        "p",
        "div",
        "br",
        "li",
        "ul",
        "ol",
        "tr",
        "td",
        "th",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "section",
        "article",
        "header",
        "footer",
        "blockquote",
        "pre",
    }
)
_DROP_TAGS = ("script", "style", "noscript", "iframe", "svg", "template")

_WS_RUN = re.compile(r"[ \t\f\v]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def clean_html(html: str) -> str:
    """Return a plaintext rendering of ``html`` suitable for DB storage.

    - Drops script/style/etc.
    - Inserts a newline after every block-level tag boundary.
    - Collapses runs of horizontal whitespace.
    - Collapses 3+ consecutive newlines to exactly 2.
    """

    if not html:
        return ""

    tree = HTMLParser(html)
    for tag in _DROP_TAGS:
        for node in tree.css(tag):
            node.decompose()

    body = tree.body if tree.body is not None else tree.root
    if body is None:
        return ""

    parts: list[str] = []
    for node in body.traverse(include_text=True):
        if node.tag == "-text":
            text = node.text(deep=False)
            if text:
                parts.append(text)
        elif node.tag in _BLOCK_TAGS:
            parts.append("\n")

    out = "".join(parts)
    lines = [_WS_RUN.sub(" ", ln).strip() for ln in out.splitlines()]
    collapsed = "\n".join(lines)
    collapsed = _BLANK_LINES.sub("\n\n", collapsed)
    return collapsed.strip()
