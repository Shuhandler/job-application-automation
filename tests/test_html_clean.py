from __future__ import annotations

from src.scrapers.html_clean import clean_html


def test_empty_input() -> None:
    assert clean_html("") == ""


def test_drops_scripts_and_styles() -> None:
    html = "<div>Hi<script>alert(1)</script><style>a{}</style></div>"
    assert "alert" not in clean_html(html)
    assert "a{}" not in clean_html(html)


def test_preserves_paragraph_breaks() -> None:
    html = "<p>Line one</p><p>Line two</p>"
    out = clean_html(html)
    assert "Line one" in out
    assert "Line two" in out
    assert "\n" in out  # not all on one line


def test_collapses_excess_whitespace() -> None:
    html = "<p>   lots   of   space   </p>"
    out = clean_html(html)
    assert "lots of space" in out
    assert "   " not in out


def test_handles_nested_lists() -> None:
    html = "<ul><li>A</li><li>B</li><li>C</li></ul>"
    out = clean_html(html)
    assert "A" in out and "B" in out and "C" in out
