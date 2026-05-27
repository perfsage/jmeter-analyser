"""Unit tests for AI markdown rendering."""

from perfsage.core.ai.markdown_render import render_ai_markdown


def test_render_ai_markdown_headings() -> None:
    html = render_ai_markdown("## Summary\n\nSome text.")
    assert "<h2>" in html
    assert "Summary" in html


def test_render_ai_markdown_code_block() -> None:
    html = render_ai_markdown("```python\nprint('hi')\n```")
    assert "<code>" in html or "<pre>" in html


def test_render_ai_markdown_strips_script_tags() -> None:
    html = render_ai_markdown("<script>alert(1)</script>\n\nSafe text.")
    assert "<script>" not in html
    assert "Safe text" in html
