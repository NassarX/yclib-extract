import argparse
import html as html_lib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from typing import Iterable, Optional
from urllib.parse import parse_qs, urlparse

import requests


def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def extract_youtube_url(html: str) -> Optional[str]:
    """Extract a YouTube watch URL from a YC page HTML payload."""
    patterns = [
        r"https://www\.youtube\.com/embed/([a-zA-Z0-9_-]{11})",
        r"https://img\.youtube\.com/vi/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r'data-video-id=["\']([a-zA-Z0-9_-]{11})["\']',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if not match:
            continue

        candidate = match.group(1)
        if extract_video_id(candidate):
            return f"https://www.youtube.com/watch?v={extract_video_id(candidate)}"
        return f"https://www.youtube.com/watch?v={candidate}"

    return None


def extract_podcast_url(html: str) -> Optional[str]:
    """Extract a podcast episode URL from YC page HTML payload."""
    match = re.search(r'data-page=(["\'])(.*?)\1', html, flags=re.IGNORECASE | re.DOTALL)
    if match:
        try:
            payload = json.loads(html_lib.unescape(match.group(2)))
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = {}
        article = payload.get("props", {}).get("article", {}) or {}
        link = article.get("link")
        if isinstance(link, str) and "open.spotify.com/episode/" in link:
            return link
        spotify_id = article.get("spotify_id")
        if isinstance(spotify_id, str) and spotify_id:
            return f"https://open.spotify.com/episode/{spotify_id}"

    patterns = [
        r'<iframe[^>]+title=["\'][^"\']*Spotify embed[^"\']*["\'][^>]+src=["\']([^"\']+)["\']',
        (
            r'<iframe[^>]+src=["\'](https://open\.spotify\.com/'
            r'(?:embed/)?episode/[A-Za-z0-9]+(?:\?[^\s"\'>]*)?)["\']'
        ),
        r"https://open\.spotify\.com/(?:embed/)?episode/[A-Za-z0-9]+(?:\?[^\s\"\'>]*)?",
    ]

    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if not match:
            continue

        candidate = match.group(1) if match.lastindex else match.group(0)
        candidate = html_lib.unescape(candidate)
        if candidate.startswith("//"):
            candidate = f"https:{candidate}"
        embed_match = re.match(
            r"https://open\.spotify\.com/embed/episode/([A-Za-z0-9]+)(\?[^\s\"'>]*)?",
            candidate,
            flags=re.IGNORECASE,
        )
        if embed_match:
            query = embed_match.group(2) or ""
            return f"https://open.spotify.com/episode/{embed_match.group(1)}{query}"
        return candidate

    return None


def format_timestamp(seconds: float) -> str:
    """Convert seconds to MM:SS or HH:MM:SS."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _normalize_transcript_entries(entries: Iterable, with_timestamps: bool = False) -> list[str]:
    lines = []
    for entry in entries:
        if isinstance(entry, dict):
            text = entry.get("text")
            start = entry.get("start")
        else:
            text = getattr(entry, "text", None)
            start = getattr(entry, "start", None)

        if not text:
            continue

        if with_timestamps and start is not None:
            lines.append(f"[{format_timestamp(float(start))}] {text}")
        else:
            lines.append(text)

    return lines


def _is_english_language(lang: str) -> bool:
    lang = (lang or "").strip().lower()
    return lang == "en" or lang.startswith("en-")


def _preferred_caption_langs(captions: dict) -> list[str]:
    langs = list(captions.keys())
    english = [lang for lang in langs if _is_english_language(lang)]
    return english + [lang for lang in langs if lang not in english]


def _caption_url_lang(caption_url: str) -> str:
    parsed = urlparse(caption_url)
    query = parse_qs(parsed.query)
    return (query.get("lang") or query.get("tlang") or [""])[0]


def _get_proxy_urls() -> tuple[Optional[str], Optional[str]]:
    """Resolve proxy URLs from env vars for transcript fetching."""
    common = os.getenv("YOUTUBE_PROXY_URL") or os.getenv("ALL_PROXY")
    http_url = os.getenv("YOUTUBE_HTTP_PROXY_URL") or os.getenv("HTTP_PROXY") or common
    https_url = os.getenv("YOUTUBE_HTTPS_PROXY_URL") or os.getenv("HTTPS_PROXY") or common
    return http_url, https_url


def _get_requests_proxies() -> Optional[dict]:
    http_url, https_url = _get_proxy_urls()
    proxies = {}
    if http_url:
        proxies["http"] = http_url
    if https_url:
        proxies["https"] = https_url
    return proxies or None


def get_transcript_from_youtube_api(video_id: str) -> Optional[str]:
    """Fetch transcript using YouTubeTranscriptApi.

    Requires: pip install yclib-extract[transcripts]
    """
    try:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError:
            print("YouTube API transcript requires: pip install yclib-extract[transcripts]")
            return None

        http_url, https_url = _get_proxy_urls()
        api_kwargs = {}
        if http_url or https_url:
            try:
                from youtube_transcript_api.proxies import GenericProxyConfig

                api_kwargs["proxy_config"] = GenericProxyConfig(
                    http_url=http_url,
                    https_url=https_url,
                )
            except Exception as proxy_error:
                print(f"Could not configure transcript proxy for {video_id}: {proxy_error}")

        transcript = YouTubeTranscriptApi(**api_kwargs).fetch(video_id)

        if not transcript:
            return None

        if hasattr(transcript, "snippets"):
            entries = transcript.snippets
        elif hasattr(transcript, "to_raw_data"):
            entries = transcript.to_raw_data()
        else:
            entries = transcript

        lines = _normalize_transcript_entries(entries)

        return "\n".join(lines) if lines else None
    except Exception as e:
        print(f"YouTube API transcript failed for {video_id}: {e}")
        return None


def get_transcript_from_yt_dlp(video_id: str) -> Optional[str]:
    """Fetch transcript using yt-dlp captions download.

    Requires: pip install yclib-extract[transcripts-full]
    """
    try:
        try:
            import yt_dlp
        except ImportError:
            print("yt-dlp transcript requires: pip install yclib-extract[transcripts-full]")
            return None

        url = f"https://www.youtube.com/watch?v={video_id}"
        http_url, https_url = _get_proxy_urls()
        proxy_url = https_url or http_url
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
        }
        if proxy_url:
            ydl_opts["proxy"] = proxy_url

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # Try to get captions
        if info.get("subtitles"):
            for lang in _preferred_caption_langs(info["subtitles"]):
                captions = info["subtitles"].get(lang, [])
                for cap in captions:
                    if cap.get("data"):
                        return cap["data"]

        # Fallback to auto-generated
        if info.get("automatic_captions"):
            for lang in _preferred_caption_langs(info["automatic_captions"]):
                captions = info["automatic_captions"].get(lang, [])
                for cap in captions:
                    if cap.get("data"):
                        return cap["data"]

        return None
    except Exception as e:
        print(f"yt-dlp transcript failed for {video_id}: {e}")
        return None


def _parse_caption_payload(text: str, with_timestamps: bool = False) -> str:
    """Parse caption payload (VTT/SBV/XML) into plain text."""
    text = text.strip()

    if not text:
        return ""

    if text.startswith("<"):
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            pass
        else:
            lines = []
            for node in root.iter():
                if node.tag.endswith("text") and (node.text or "").strip():
                    start = node.attrib.get("start")
                    value = html_lib.unescape((node.text or "").strip())
                    if start:
                        if with_timestamps:
                            lines.append(f"[{format_timestamp(float(start))}] {value}")
                        else:
                            lines.append(value)
                    else:
                        lines.append(value)
            return "\n".join(lines) if with_timestamps else " ".join(lines)

    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("WEBVTT") or "-->" in line or line.startswith("Kind:"):
            continue
        lines.append(html_lib.unescape(line))

    return "\n".join(lines) if with_timestamps else " ".join(lines)


def _extract_caption_urls_from_html(html: str) -> list[str]:
    urls = []
    for raw in re.findall(r'"baseUrl":"([^"]+)"', html):
        try:
            urls.append(json.loads(f'"{raw}"'))
        except json.JSONDecodeError:
            continue
    return urls


def get_transcript_from_youtube_page(video_id: str, with_timestamps: bool = False) -> Optional[str]:
    """Fetch transcript by scraping the YouTube watch page captions metadata."""
    try:
        proxies = _get_requests_proxies()
        response = requests.get(
            f"https://www.youtube.com/watch?v={video_id}",
            timeout=15,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                )
            },
            proxies=proxies,
        )
        response.raise_for_status()

        caption_urls = _extract_caption_urls_from_html(response.text)
        caption_urls = sorted(
            caption_urls, key=lambda u: (0 if _is_english_language(_caption_url_lang(u)) else 1, u)
        )

        for caption_url in caption_urls:
            caption_response = requests.get(caption_url, timeout=15, proxies=proxies)
            caption_response.raise_for_status()
            transcript = _parse_caption_payload(
                caption_response.text, with_timestamps=with_timestamps
            )
            if transcript:
                return transcript
    except Exception as e:
        print(f"YouTube page transcript failed for {video_id}: {e}")

    return None


def format_transcript(text: str, max_length: Optional[int] = None) -> str:
    """Clean and format transcript text."""
    if not text:
        return ""

    # Basic cleanup
    text = re.sub(r"\s+", " ", text)  # Normalize whitespace
    text = re.sub(r"[“”]", '"', text)  # Normalize quotes

    # [Placeholder] Simple speaker detection (heuristic)
    # Match names like "Garry Tan:" or ">> Speaker:" at the beginning of phrases
    text = re.sub(r"(>>\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*:)", r"\n\n\1", text)

    # Handle common case where speaker is just a capitalized name followed by colon
    # but avoid matching common words at start of sentences
    # This is a placeholder for real diarization
    text = re.sub(r"(?<= )([A-Z][a-z]+ [A-Z][a-z]+:)", r"\n\n\1", text)

    if max_length:
        text = text[:max_length]

    return text.strip()


def get_transcript(url: str, with_timestamps: bool = False) -> Optional[str]:
    """
    Get YouTube transcript with fallback chain:
    1. YouTubeTranscriptApi
    2. yt-dlp captions
    3. YouTube watch page captions metadata
    4. Invidious API fallback
    """
    video_id = extract_video_id(url)
    if not video_id:
        return None

    # Try YouTube API first
    transcript = get_transcript_from_youtube_api(video_id)
    if transcript:
        return transcript if with_timestamps else format_transcript(transcript)

    # Fallback to yt-dlp
    transcript = get_transcript_from_yt_dlp(video_id)
    if transcript:
        transcript = _parse_caption_payload(transcript, with_timestamps=with_timestamps)
        return transcript if with_timestamps else format_transcript(transcript)

    # Fallback to watch page scraping
    transcript = get_transcript_from_youtube_page(video_id, with_timestamps=with_timestamps)
    if transcript:
        return transcript if with_timestamps else format_transcript(transcript)

    # Fallback to Invidious
    transcript = TranscriptRecoveryEnhancer.try_invidious_transcript(video_id)
    if transcript:
        return format_transcript(transcript)

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Get YouTube video transcript")
    parser.add_argument("video", help="YouTube video URL or video ID")
    parser.add_argument(
        "--timestamps",
        "-t",
        action="store_true",
        help="Include timestamps in output",
    )
    args = parser.parse_args()

    try:
        transcript = get_transcript(args.video, with_timestamps=args.timestamps)
        if not transcript:
            raise ValueError("No transcript found")
        print(transcript)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


class TranscriptRecoveryEnhancer:
    """Enhanced transcript recovery with improved fallback chain."""

    # Invidious instances for fallback
    DEFAULT_INVIDIOUS_INSTANCES = [
        "yewtu.cafe",
        "inv.riverside.rocks",
        "yt.artemislena.eu",
        "invidio.us",
    ]

    @staticmethod
    def try_invidious_transcript(video_id: str, instances: list = None) -> Optional[str]:
        """Try to fetch transcript from Invidious mirror.

        Args:
            video_id: YouTube video ID
            instances: List of Invidious instances to try

        Returns:
            Transcript text or None if unavailable
        """
        if instances is None:
            instances = TranscriptRecoveryEnhancer.DEFAULT_INVIDIOUS_INSTANCES

        for instance in instances:
            try:
                url = f"https://{instance}/api/v1/captions/{video_id}"
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    captions = data.get("captions", [])
                    if captions:
                        # Get English or first available caption
                        for cap in captions:
                            if cap.get("label", "").startswith("English"):
                                return TranscriptRecoveryEnhancer._download_invidious_captions(
                                    instance, video_id, cap.get("label")
                                )
                        # Fallback to first available
                        if captions:
                            return TranscriptRecoveryEnhancer._download_invidious_captions(
                                instance, video_id, captions[0].get("label")
                            )
            except Exception:
                continue

        return None

    @staticmethod
    def _download_invidious_captions(instance: str, video_id: str, label: str) -> Optional[str]:
        """Download actual captions from Invidious."""
        try:
            url = f"https://{instance}/api/v1/captions/{video_id}"
            params = {"label": label}
            resp = requests.get(url, params=params, timeout=5)
            if resp.status_code == 200:
                lines = [line.strip() for line in resp.text.split("\n") if line.strip()]
                return "\n".join(lines)
        except Exception:
            pass
        return None
