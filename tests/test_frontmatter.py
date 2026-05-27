"""Tests for enhanced frontmatter generation."""

import pytest
from yclib_extract.lib.html_cleaning import generate_enriched_frontmatter

def test_frontmatter_generation():
    """Test basic frontmatter generation."""
    metadata = {
        'title': 'Test Article',
        'author': 'John Doe',
        'url': 'https://example.com',
        'tags': ['test', 'sample']
    }
    content = ' '.join(['word'] * 300)
    fm = generate_enriched_frontmatter(metadata, content)
    
    assert 'title: Test Article' in fm
    assert 'author: John Doe' in fm
    assert 'word_count: 300' in fm
    assert 'reading_time_minutes' in fm

def test_frontmatter_with_missing_fields():
    """Test frontmatter handles missing metadata gracefully."""
    metadata = {}
    content = 'Some content'
    fm = generate_enriched_frontmatter(metadata, content)
    
    assert 'title: Untitled' in fm
    assert 'author: Unknown' in fm
    assert '---' in fm
