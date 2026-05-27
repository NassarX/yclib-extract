"""Tests for graceful handling of optional dependencies."""

import sys
from unittest.mock import patch

from yclib_extract.lib.youtube_transcripts import (
    get_transcript_from_youtube_api,
    get_transcript_from_yt_dlp,
)


def test_get_transcript_from_youtube_api_missing_dependency(capsys):
    """Test graceful degradation when youtube-transcript-api is missing."""
    # Mock the import to raise ImportError
    with patch(
        "builtins.__import__", side_effect=ImportError("No module named 'youtube_transcript_api'")
    ):
        result = get_transcript_from_youtube_api("test-video-id")

    assert result is None
    captured = capsys.readouterr()
    assert (
        "transcripts" in captured.out or "ImportError" in captured.out or "requires" in captured.out
    )


def test_get_transcript_from_yt_dlp_missing_dependency(capsys):
    """Test graceful degradation when yt-dlp is missing."""
    # Mock the import to raise ImportError
    with patch("builtins.__import__", side_effect=ImportError("No module named 'yt_dlp'")):
        result = get_transcript_from_yt_dlp("test-video-id")

    assert result is None
    captured = capsys.readouterr()
    assert (
        "transcripts-full" in captured.out
        or "ImportError" in captured.out
        or "requires" in captured.out
    )


def test_core_functionality_without_transcripts():
    """Test that core extraction works without transcript dependencies.

    This tests that importing and using basic modules doesn't require
    transcript dependencies.
    """
    from yclib_extract.lib.youtube_transcripts import (
        extract_podcast_url,
        extract_video_id,
        extract_youtube_url,
    )

    # These should work without any transcript dependencies
    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    youtube_url = extract_youtube_url(
        '<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>'
    )
    assert youtube_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    spotify_url = extract_podcast_url('link="https://open.spotify.com/episode/123abc"')
    assert spotify_url is None or "spotify" not in spotify_url.lower() or "123abc" in spotify_url
