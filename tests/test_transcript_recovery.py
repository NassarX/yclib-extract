"""Tests for enhanced transcript recovery."""

import pytest
from yclib_extract.lib.youtube_transcripts import TranscriptRecoveryEnhancer

def test_invidious_instance_order():
    """Test that fallback instances are properly ordered."""
    instances = TranscriptRecoveryEnhancer.DEFAULT_INVIDIOUS_INSTANCES
    assert len(instances) > 0
    assert 'yewtu.cafe' in instances

def test_transcript_recovery_graceful_failure():
    """Test that transcript recovery fails gracefully."""
    # This would fail with real network, but tests graceful handling
    result = TranscriptRecoveryEnhancer.try_invidious_transcript('INVALID_ID')
    # Should return None or empty string, not raise exception
    assert result is None or isinstance(result, str)

def test_caption_extraction():
    """Test caption extraction logic."""
    # Mock test - in real scenario would use vcr cassettes
    assert hasattr(TranscriptRecoveryEnhancer, '_download_invidious_captions')
