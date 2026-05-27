"""Tests for footnote processing in essay extraction."""

import pytest

from yclib_extract.lib.html_cleaning import process_footnotes


def test_footnote_reference_conversion():
    """Test conversion of [n] and linked markers to [^n] format."""
    content = """This is text[1] with references[2]. 
[[3](#f3n)] is a linked marker.

**Notes**
[1] First note
[2] Second note
[3] Third note
"""
    result = process_footnotes(content)

    assert "[^1]" in result
    assert "[^2]" in result
    assert "[^3]" in result
    assert "[1]" not in result
    assert "[2]" not in result
    assert "[3](#f3n)" not in result

    assert "[^1]: First note" in result
    assert "[^2]: Second note" in result
    assert "[^3]: Third note" in result


def test_footnote_multiline():
    """Test footnotes that span multiple lines."""
    content = """Text[^1].

**Notes**
[1] First line
    Second line of same note
[2] Another note
"""
    result = process_footnotes(content)

    assert "[^1]: First line Second line of same note" in result
    assert "[^2]: Another note" in result


def test_no_notes_section():
    """Test that text is preserved if no notes section is found."""
    content = "Just some text [1] that isn't a footnote."
    result = process_footnotes(content)
    assert result == content.strip()
