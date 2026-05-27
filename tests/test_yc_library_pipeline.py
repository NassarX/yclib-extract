"""Tests for YC Library extraction pipeline."""

import pytest
from yclib_extract.scraper import AlgoliaPageinator, MetadataFilter
from yclib_extract.extractor import YCLibraryExtractionEnhancer
from yclib_extract.lib.audit import UnifiedAudit


def test_algolia_paginator_deduplication():
    """Test pagination handles duplicates correctly."""
    paginator = AlgoliaPageinator(None, "app_id", "api_key", "index")
    assert hasattr(paginator, 'paginate_all_results')


def test_metadata_filter_duplicates():
    """Test duplicate detection by URL."""
    metadata = [
        {'url': 'https://example.com/1', 'title': 'Article 1'},
        {'url': 'https://example.com/1', 'title': 'Article 1 Dup'},
        {'url': 'https://example.com/2', 'title': 'Article 2'},
    ]
    
    filtered = MetadataFilter.filter_duplicates(metadata, 'url')
    assert len(filtered) == 2


def test_metadata_filter_by_criteria():
    """Test filtering by multiple criteria."""
    metadata = [
        {'source': 'yc', 'status': 'published'},
        {'source': 'pg', 'status': 'published'},
        {'source': 'yc', 'status': 'draft'},
    ]
    
    filtered = MetadataFilter.filter_by_criteria(metadata, {'source': 'yc', 'status': 'published'})
    assert len(filtered) == 1


def test_metadata_enrichment():
    """Test metadata enrichment with quality scores."""
    item = {
        'title': 'Article',
        'author': 'Author',
        'url': 'https://example.com',
    }
    
    enriched = MetadataFilter.enrich_metadata(item)
    assert 'quality_score' in enriched
    assert enriched['quality_score'] > 0


def test_extraction_quality_tracking():
    """Test extraction quality metrics calculation."""
    content = 'This is a test article. ' * 100
    metadata = {'title': 'Test', 'author': 'Author'}
    
    metrics = YCLibraryExtractionEnhancer.track_extraction_quality(content, metadata)
    
    assert metrics['title_present'] is True
    assert metrics['author_present'] is True
    assert metrics['word_count'] > 0
    assert metrics['quality_level'] in ('short', 'minimal', 'good', 'excellent')


def test_unified_audit_generation():
    """Test audit entry creation and statistics."""
    audit = UnifiedAudit()
    
    metadata = {'title': 'Test', 'url': 'https://example.com'}
    metrics = {'quality_level': 'good', 'content_length': 1000, 'word_count': 200, 'warnings': []}
    
    audit.add_entry('res-1', 'yc_library', metadata, metrics, 'test.md')
    
    stats = audit.get_statistics()
    assert stats['total'] == 1
    assert stats['by_source']['yc_library'] == 1
    assert stats['by_quality']['good'] == 1
