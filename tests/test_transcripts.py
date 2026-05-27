import sys
from types import ModuleType
from types import SimpleNamespace

from yclib_extract.lib.youtube_transcripts import (
    _parse_caption_payload,
    extract_video_id,
    format_transcript,
    get_transcript,
    get_transcript_from_youtube_api,
)


def test_extract_video_id_handles_common_youtube_urls():
    assert extract_video_id("https://www.youtube.com/watch?v=abcdefghijk") == "abcdefghijk"
    assert extract_video_id("https://youtu.be/abcdefghijk") == "abcdefghijk"
    assert extract_video_id("https://www.youtube.com/embed/abcdefghijk") == "abcdefghijk"


def test_parse_caption_payload_strips_timestamps():
    payload = """WEBVTT

    00:00:01.000 --> 00:00:02.000
    Hello

    00:00:02.000 --> 00:00:03.000
    world
    """

    assert _parse_caption_payload(payload) == "Hello world"


def test_format_transcript_normalizes_whitespace_and_quotes():
    assert format_transcript("Hello\n  world “quote”") == 'Hello world "quote"'


def test_get_transcript_uses_fallback_chain(monkeypatch):
    monkeypatch.setattr(
        "yclib_extract.lib.youtube_transcripts.get_transcript_from_youtube_api",
        lambda video_id: None,
    )
    monkeypatch.setattr(
        "yclib_extract.lib.youtube_transcripts.get_transcript_from_yt_dlp",
        lambda video_id: "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello",
    )

    assert get_transcript("https://www.youtube.com/watch?v=abcdefghijk") == "Hello"


def test_get_transcript_from_youtube_api_uses_proxy_env(monkeypatch):
    seen = {}

    class FakeProxyConfig:
        def __init__(self, http_url=None, https_url=None):
            seen["http_url"] = http_url
            seen["https_url"] = https_url

    class FakeApi:
        def __init__(self, proxy_config=None):
            seen["proxy_config"] = proxy_config

        def fetch(self, video_id):
            assert video_id == "abcdefghijk"
            return [SimpleNamespace(text="Hello")]

    monkeypatch.setenv("YOUTUBE_PROXY_URL", "socks5://127.0.0.1:9050")
    fake_root = ModuleType("youtube_transcript_api")
    fake_root.YouTubeTranscriptApi = FakeApi
    fake_proxies = ModuleType("youtube_transcript_api.proxies")
    fake_proxies.GenericProxyConfig = FakeProxyConfig

    monkeypatch.setitem(sys.modules, "youtube_transcript_api", fake_root)
    monkeypatch.setitem(sys.modules, "youtube_transcript_api.proxies", fake_proxies)

    assert get_transcript_from_youtube_api("abcdefghijk") == "Hello"
    assert seen["http_url"] == "socks5://127.0.0.1:9050"
    assert seen["https_url"] == "socks5://127.0.0.1:9050"
    assert seen["proxy_config"] is not None
