"""Render AI narrative markdown to safe HTML."""

from __future__ import annotations

import bleach
import markdown

_ALLOWED_TAGS = [
    "h1",
    "h2",
    "h3",
    "h4",
    "p",
    "ul",
    "ol",
    "li",
    "strong",
    "em",
    "code",
    "pre",
    "blockquote",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "a",
    "hr",
    "br",
]
_ALLOWED_ATTRS: dict[str, list[str]] = {
    "a": ["href", "title", "rel", "target"],
    "th": ["colspan", "rowspan"],
    "td": ["colspan", "rowspan"],
}


def render_ai_markdown(text: str) -> str:
    """Convert markdown to sanitized HTML for AI insights display."""
    if not text.strip():
        return ""
    html = markdown.markdown(
        text,
        extensions=["fenced_code", "tables", "nl2br", "sane_lists"],
    )
    cleaned = bleach.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)
    return str(cleaned)
