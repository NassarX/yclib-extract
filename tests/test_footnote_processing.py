"""Tests for footnote processing in essay extraction."""

import pytest
from yclib_extract.lib.html_cleaning import process_footnotes, extract_footnotes_from_html

def test_footnote_reference_conversion():
    """Test conversion of [n] to [^n] format."""
    content = "This is text[1] with references[2] to footnotes[3]."
    result = process_footnotes(content)
    
    assert "[^1]" in result
    assert "[^2]" in result
    assert "[^3]" in result
    assert "[1]" not in result

def test_footnote_appending():
    """Test appending footnote definitions."""
    content = "Text with footnote[^1]."
    footnotes = {'1': 'This is the first footnote', '2': 'Second note'}
    
    result = process_footnotes(content, footnotes)
    
    assert "[^1]: This is the first footnote." in result
    assert "[^2]: Second note." in result

def test_extract_footnotes_from_html():
    """Test extracting footnotes from HTML structure."""
    html = '''
    <div class="footnotes">
        <li id="fn1">First footnote content</li>
        <li id="fn2">Second footnote content</li>
    </div>
    '''
    
    cleaned, footnotes = extract_footnotes_from_html(html)
    
    assert '1' in footnotes
    assert '2' in footnotes
    assert 'First footnote content' in footnotes['1']
