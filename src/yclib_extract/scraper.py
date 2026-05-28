from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from .config import Config

ARTIFACTS_DIR = Path("artifacts")
DEFAULT_METADATA_DIR = str(ARTIFACTS_DIR / "yc_library_metadata.json")
DEFAULT_BLOG_METADATA_DIR = str(ARTIFACTS_DIR / "metadata" / "yc_blog_metadata.json")
DEFAULT_BLOG_TAXONOMY_FILE = str(ARTIFACTS_DIR / "metadata" / "yc_blog_taxonomy.json")
IGNORE_SOURCES_PATH = Path("config/ignore_sources.json")
DEFAULT_YC_BLOG_EXCLUDE_TAGS = [
    "admissions",
    "internal",
    "partners",
    "jobs",
    "hacker news",
    "yc news",
    "yc events",
]
DEFAULT_YC_BLOG_INCLUDE_TAGS = [
    "advice",
    "essay",
    "startup school",
    "fundraising",
    "company building",
]
DEFAULT_YC_BLOG_CONDITIONAL_TAGS = [
    "ai",
    "technical",
    "leadership",
    "growth",
]
DEFAULT_YC_BLOG_CONDITIONAL_MIN_WORDS = 300
DEFAULT_EDUCATIONAL_KEYWORDS = [
    "startup",
    "founder",
    "advice",
    "build",
    "company",
    "product",
    "growth",
    "fundraising",
    "market",
    "customer",
    "engineering",
    "leadership",
    "sales",
    "hiring",
    "strategy",
    "lesson",
]
DEFAULT_LOGISTICS_KEYWORDS = [
    "apply",
    "application",
    "deadline",
    "event",
    "register",
    "schedule",
    "agenda",
    "location",
    "zoom",
    "webinar",
    "office hour",
    "time",
    "date",
]


def normalize_tag(value: str) -> str:
    """Normalize tags for deterministic matching."""
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized.lower())
    return " ".join(normalized.split())


def _flatten_strings(value: Any) -> list[str]:
    """Flatten nested taxonomy values into plain strings."""
    if value is None:
        return []
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    if isinstance(value, dict):
        flattened: list[str] = []
        for nested in value.values():
            flattened.extend(_flatten_strings(nested))
        return flattened
    if isinstance(value, list):
        flattened = []
        for nested in value:
            flattened.extend(_flatten_strings(nested))
        return flattened
    return []


def collect_taxonomy_values(record: Dict[str, Any]) -> list[str]:
    """Collect all known taxonomy labels from a record."""
    values: list[str] = []
    for key in ("tags", "categories", "subcategories"):
        values.extend(_flatten_strings(record.get(key)))
    return values


def collect_tag_slugs(record: Dict[str, Any]) -> list[str]:
    """Extract tag/category slugs from a record (prefer slug over name).

    Handles both dict format (with slug/name fields) and string format (backward compat).
    """
    slugs = []
    for key in ("tags", "categories", "subcategories"):
        items = record.get(key, [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    # Prefer slug, fallback to name
                    slug = item.get("slug") or item.get("name", "")
                    if slug:
                        slugs.append(slug)
                elif isinstance(item, str):
                    if item:
                        slugs.append(item)
        elif isinstance(items, str):
            if items:
                slugs.append(items)
    return slugs


def clean_metadata_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Remove null/empty fields from tags and categories only.

    For tags/categories: keep only {name, slug, url}
    - Convert hash-{non-numeric} to {non-numeric} (e.g., hash-jobs → jobs)
    - Exclude hash-{numeric} tags (e.g., hash-25267)
    For other fields: preserve as-is (don't remove empty strings).
    """
    cleaned = {}
    for key, value in record.items():
        if key in ("tags", "categories"):
            # For tags/categories, keep only clean dict entries with name/slug/url
            if isinstance(value, list):
                clean_items: list[dict[Any, Any] | str] = []
                for item in value:
                    if isinstance(item, dict):
                        slug = item.get("slug", "")

                        # Handle hash tags
                        if slug and slug.startswith("hash-"):
                            hash_content = slug[5:]  # Remove "hash-" prefix
                            # Skip purely numeric hashes (e.g., hash-25267)
                            if hash_content.isdigit():
                                continue
                            # Convert hash-{content} to {content} (e.g., hash-jobs → jobs)
                            slug = hash_content

                        clean_item = {
                            k: v
                            for k, v in item.items()
                            if v is not None and k in ("name", "slug", "url")
                        }
                        # Update slug in clean_item
                        if clean_item and slug:
                            clean_item["slug"] = slug

                        if clean_item:
                            clean_items.append(clean_item)
                    elif isinstance(item, str) and item:
                        clean_items.append(item)
                if clean_items:
                    cleaned[key] = clean_items
            elif value:
                cleaned[key] = value
        else:
            # For all other fields, preserve as-is (including empty strings)
            cleaned[key] = value
    return cleaned


def build_clean_taxonomy_from_posts(posts: list[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a clean taxonomy of tags and categories with slug focus."""
    tags_map: Dict[str, Dict[str, str]] = {}
    categories_map: Dict[str, Dict[str, str]] = {}

    for post in posts:
        # Extract tags
        tags = post.get("tags", [])
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, dict):
                    slug = tag.get("slug", "")
                    name = tag.get("name", "")
                    if slug and name:
                        if slug not in tags_map:
                            tags_map[slug] = {"slug": slug, "name": name}

        # Extract categories
        categories = post.get("categories", [])
        if isinstance(categories, list):
            for cat in categories:
                if isinstance(cat, dict):
                    slug = cat.get("slug", "")
                    name = cat.get("name", "")
                    if slug and name:
                        if slug not in categories_map:
                            categories_map[slug] = {"slug": slug, "name": name}

    return {
        "tags": dict(sorted(tags_map.items())),
        "categories": dict(sorted(categories_map.items())),
        "total_posts": len(posts),
    }


def should_include_by_tags(
    record: Dict[str, Any], include_tags: Iterable[str], exclude_tags: Iterable[str]
) -> bool:
    """Return True when record satisfies include/exclude tag rules using normalized slug matching.

    Exclusion has precedence: if any denylist tag matches, record is excluded.
    Normalizes both filter tags and post slugs before comparison.
    """
    include_set = {normalize_tag(tag) for tag in include_tags if tag}
    exclude_set = {normalize_tag(tag) for tag in exclude_tags if tag}

    # Extract slugs from record (prefer slug over name)
    record_slugs = {normalize_tag(slug) for slug in collect_tag_slugs(record) if slug}

    if record_slugs & exclude_set:
        return False
    if not include_set:
        return True
    return bool(record_slugs & include_set)


def classify_by_tag_cascade(
    record: Dict[str, Any],
    include_tags: Iterable[str],
    exclude_tags: Iterable[str],
    conditional_tags: Iterable[str],
) -> str:
    """Classify a post by exclude/include/conditional tag cascade using normalized slug matching.

    Normalizes both filter tags and post slugs before comparison to handle:
    - Filter: "hacker news" (spaces) → Normalized: "hacker news"
    - Post slug: "hacker-news" (dashes) → Normalized: "hacker news"
    - Match: Both normalize to same value ✓
    """
    # Normalize filter tags: convert dashes to spaces, lowercase
    include_set = {normalize_tag(tag) for tag in include_tags if tag}
    exclude_set = {normalize_tag(tag) for tag in exclude_tags if tag}
    conditional_set = {normalize_tag(tag) for tag in conditional_tags if tag}

    # Extract and normalize slugs from record (prefer slug over name)
    record_slugs = {normalize_tag(slug) for slug in collect_tag_slugs(record) if slug}

    if record_slugs & exclude_set:
        return "exclude"
    if record_slugs & include_set:
        return "include"
    if record_slugs and record_slugs.issubset(conditional_set):
        return "conditional"
    return "skip"


def _extract_text_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for selector in ("article", "main"):
        node = soup.select_one(selector)
        if node:
            text = node.get_text(" ", strip=True)
            return str(text) if text is not None else ""
    text = soup.get_text(" ", strip=True)
    return str(text) if text is not None else ""


def passes_conditional_content_filter(
    url: str,
    min_words: int = DEFAULT_YC_BLOG_CONDITIONAL_MIN_WORDS,
    educational_keywords: Optional[Iterable[str]] = None,
    logistics_keywords: Optional[Iterable[str]] = None,
) -> bool:
    """Evaluate conditional-tag posts by content quality signals."""
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    text = _extract_text_content(response.text).lower()
    words = re.findall(r"\b\w+\b", text)
    if len(words) < min_words:
        return False

    positive = [k for k in (educational_keywords or DEFAULT_EDUCATIONAL_KEYWORDS) if k in text]
    negative = [k for k in (logistics_keywords or DEFAULT_LOGISTICS_KEYWORDS) if k in text]
    return len(positive) >= 2 and len(positive) >= len(negative)


def classify_by_content(
    post: Dict[str, Any],
    include_keywords: Optional[dict[str, list[str]]] = None,
    exclude_keywords: Optional[list[str]] = None,
) -> str:
    """Classify a post by analyzing its content when tag metadata is unavailable.

    Returns: "include", "exclude", or "skip"
    """
    if include_keywords is None:
        include_keywords = {
            "advice": ["advice", "tips", "how to", "best practices", "lessons"],
            "essay": ["essay", "thoughts on", "reflection", "perspective", "lessons learned"],
            "startup school": ["startup school", "education", "course", "curriculum"],
            "fundraising": ["fundraising", "funding", "investors", "capital", "pitch"],
            "company building": ["company", "building", "founders", "teams", "culture"],
        }
    if exclude_keywords is None:
        exclude_keywords = ["yc news", "announcement", "press release", "event", "hiring"]

    content = (post.get("content") or "").lower()
    title = (post.get("post_title") or "").lower()
    full_text = f"{title} {content}"

    # Check exclude first
    for kw in exclude_keywords:
        if kw.lower() in full_text:
            return "exclude"

    # Check include
    for category, keywords in include_keywords.items():
        matches = sum(1 for kw in keywords if kw.lower() in full_text)
        if matches >= 2:
            return "include"

    # If has some educational content, include
    edu_keywords = ["startup", "founder", "build", "growth", "product"]
    if sum(1 for kw in edu_keywords if kw in full_text) >= 3:
        return "include"

    return "skip"


def build_taxonomy_from_posts(posts: list[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a count map of taxonomy values from Algolia hits."""
    fields = ("tags", "categories", "subcategories")
    counts: Dict[str, Dict[str, int]] = {field: {} for field in fields}

    for post in posts:
        for field in fields:
            for value in _flatten_strings(post.get(field)):
                normalized = normalize_tag(value)
                if not normalized:
                    continue
                counts[field][normalized] = counts[field].get(normalized, 0) + 1

    return {
        "counts": {field: dict(sorted(values.items())) for field, values in counts.items()},
        "total_posts": len(posts),
    }


def load_ignore_sources() -> set[str]:
    """Load persisted source identifiers that should be skipped."""
    try:
        raw = json.loads(IGNORE_SOURCES_PATH.read_text())
    except FileNotFoundError:
        return set()
    except json.JSONDecodeError:
        return set()

    if not isinstance(raw, list):
        return set()

    return {str(item).strip().lower() for item in raw if str(item).strip()}


def is_ignored(value: str, ignore_sources: Optional[set[str]] = None) -> bool:
    """Return True when a value matches a persisted ignore entry."""
    if not value:
        return False

    if ignore_sources is None:
        ignore_sources = load_ignore_sources()
    needle = value.strip().lower()
    return any(entry == needle or entry in needle or needle in entry for entry in ignore_sources)


def _get_known_yc_algolia_config() -> Dict[str, str]:
    """Return the known YC Algolia configuration used by the legacy scraper."""
    return {
        "appId": "45BWZJ1SGC",
        "apiKey": (
            "MDlkNDAyNzM1YjA2YTQwYjBkMGIwNjk2Mzg4NDQ3ZGRkMTdhZWJmODM0MDdiNDVhMTNlNDRiZ"
            "iM5MmFuYWx5dGljc1RhZ3M9eWNkYyUyQ2xpYnJhcnkmcmVzdHJpY3RJbmRpY2VzPUxpYnJhcnlf"
            "Ym9va2ZhY2VfcHJvZHVjdGlvbiZ0YWdGaWx0ZXJzPSU1QiUyMnljZGNfcHVibGljJTIyJTJDJTV"
            "CJTIya2Jfcm9vdF8xNzYlMjIlMkMlMjJrYl9yb290XzkxMiUyMiU1RCU1RA=="
        ),
        "indexName": "Library_bookface_production",
    }


def _slugify(value: str, fallback: str = "file") -> str:
    if not value:
        return fallback

    # 1. Convert accented characters to ASCII (e.g., "café" -> "cafe")
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")

    # 2. Lowercase and strip out apostrophes entirely
    value = value.lower().replace("'", "")

    # 3. Replace all other non-alphanumeric characters with a single hyphen
    slug = re.sub(r"[^a-z0-9]+", "-", value)

    # 4. Remove leading/trailing hyphens
    slug = slug.strip("-")

    return slug or fallback


def _canonical_source_type(value: str) -> str:
    normalized = (value or "").strip().lower()
    mapping = {
        "article": "Article",
        "blog": "Article",
        "video": "Video",
        "podcast": "Podcast",
        "external": "External",
    }
    return mapping.get(normalized, (value or "Article").strip() or "Article")


def _is_media_url(value: str) -> bool:
    value = (value or "").strip().lower()
    return "youtu.be/" in value or "youtube.com/" in value or "open.spotify.com/" in value


class RSSScraper:
    """Discover essays via RSS or Atom feeds."""

    def __init__(self, feed_url: str):
        self.feed_url = feed_url

    def fetch_items(self) -> list[Dict[str, str | None]]:
        """Fetch and parse feed items.

        Returns:
            List of dicts with 'url', 'title', and 'date'
        """
        try:
            response = requests.get(self.feed_url, timeout=20)
            response.raise_for_status()

            # Simple XML parsing for RSS/Atom
            import xml.etree.ElementTree as ET

            root = ET.fromstring(response.content)

            items = []
            # Try Atom format (Altman)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns):
                title = entry.find("atom:title", ns)
                link = entry.find("atom:link", ns)
                published = entry.find("atom:published", ns)
                updated = entry.find("atom:updated", ns)
                date_node = published if published is not None else updated

                if link is not None:
                    items.append(
                        {
                            "url": link.get("href"),
                            "title": title.text if title is not None else "",
                            "date": date_node.text if date_node is not None else "",
                        }
                    )

            if items:
                return items

            # Try RSS 2.0 format (PG)
            for item in root.findall(".//item"):
                title = item.find("title")
                link = item.find("link")
                pub_date = item.find("pubDate")
                if link is not None:
                    items.append(
                        {
                            "url": link.text,
                            "title": title.text if title is not None else "",
                            "date": pub_date.text if pub_date is not None else "",
                        }
                    )

            return items
        except Exception as e:
            print(f"Error fetching RSS feed {self.feed_url}: {e}")
            return []


class AlgoliaScraper:
    """Discover YC Library posts via Algolia search."""

    def __init__(
        self,
        app_id: Optional[str] = None,
        api_key: Optional[str] = None,
        index_name: str = "library_posts",
        config: Optional[Config] = None,
    ):
        """Initialize scraper with Algolia credentials.

        Args:
            app_id: Algolia app ID (overrides config if provided)
            api_key: Algolia API key (overrides config if provided)
            index_name: Algolia index name (default: library_posts)
            config: Config object (used if app_id/api_key not provided)
        """
        if config is None:
            config = Config()

        fallback = _get_known_yc_algolia_config()
        self.app_id = app_id or config.algolia_app_id or fallback["appId"]
        self.api_key = api_key or config.algolia_api_key or fallback["apiKey"]

        # Handle index name: use config if default, otherwise use provided
        if index_name == "library_posts":
            self.index_name = config.algolia_index or fallback["indexName"]
        else:
            self.index_name = index_name

        self.base_url = f"https://{self.app_id}-dsn.algolia.net/1/indexes/{self.index_name}"
        self.queries_url = f"https://{self.app_id}-dsn.algolia.net/1/indexes/*/queries"

    def _make_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make Algolia API request."""
        headers = {
            "X-Algolia-Application-Id": self.app_id,
            "X-Algolia-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Referer": "https://www.ycombinator.com/",
            "User-Agent": "Mozilla/5.0",
        }

        query_params = urlencode(
            [
                (key, value if isinstance(value, str) else json.dumps(value))
                for key, value in params.items()
            ]
        )
        payload = {
            "requests": [
                {
                    "indexName": self.index_name,
                    "params": query_params,
                }
            ]
        }

        response = requests.post(
            self.queries_url,
            json=payload,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        result: Dict[str, Any] = response.json()
        return result

    def _default_query_params(self, per_page: int, page: int) -> Dict[str, Any]:
        return {
            "query": "",
            "hitsPerPage": per_page,
            "page": page,
            "attributesToRetrieve": ["*"],
            "attributesToHighlight": [],
            "analytics": False,
            "facets": ["id", "sus_curriculum", "media_type", "categories", "subcategories"],
            "sortFacetValuesBy": "alpha",
            "maxValuesPerFacet": 1000,
            "analyticsTags": ["ycdc", "library"],
            "restrictIndices": self.index_name,
            "tagFilters": [["ycdc_public", "kb_root_176", "kb_root_912"]],
        }

    def browse_all(self, per_page: int = 1000) -> list[Dict[str, str | None]]:
        """Browse all posts via Algolia."""
        posts: list[Dict[str, str | None]] = []
        page = 0

        while True:
            params = self._default_query_params(per_page=per_page, page=page)

            result = self._make_request(params)
            query_result: Dict[str, Any] = result.get("results", [{}])[0]
            hits: list[Dict[str, str | None]] = query_result.get("hits", [])
            posts.extend(hits)

            nb_pages = query_result.get("nbPages", 0) or 0
            if page >= nb_pages - 1:
                break
            page += 1

        return posts

    def browse_facets(self) -> Dict[str, Dict[str, int]]:
        """Fetch available facet values and counts from Algolia."""
        params = self._default_query_params(per_page=0, page=0)
        params["facets"] = ["*"]
        params["maxValuesPerFacet"] = 1000
        result = self._make_request(params)
        query_result: Dict[str, Any] = result.get("results", [{}])[0]
        facets = query_result.get("facets", {})
        return facets if isinstance(facets, dict) else {}

    def _normalize_hit(self, hit: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Algolia hit to post metadata."""
        page_url = hit.get("shared_search_path") or hit.get("slug") or hit.get("url")
        media_url = hit.get("link") or hit.get("url")

        if page_url and not page_url.startswith("http"):
            page_url = f"https://www.ycombinator.com{page_url}"

        if media_url:
            if not _is_media_url(media_url):
                media_url = ""
            elif not media_url.startswith("http"):
                media_url = f"https://{media_url.lstrip('/')}"
        if not media_url:
            media_url = ""

        source_type = _canonical_source_type(hit.get("media_type") or hit.get("type") or "Article")
        title = hit.get("title", hit.get("name", ""))
        title_id = _slugify(title) or hit.get("objectID", "")

        return {
            "id": title_id,
            "algolia_id": hit.get("objectID", ""),
            "url": page_url,
            "media_url": media_url,
            "title": title,
            "company": hit.get("company_name", ""),
            "author": hit.get("author", ""),
            "date": hit.get("published_at", hit.get("date", "")),
            "description": hit.get("description", hit.get("content", "")),
            "tags": hit.get("tags", []),
            "type": source_type,
            "source_type": source_type,
        }

    def save_posts(
        self,
        posts: list[Dict[str, Any]],
        output_file: str,
        include_tags: Optional[Iterable[str]] = None,
        exclude_tags: Optional[Iterable[str]] = None,
        conditional_tags: Optional[Iterable[str]] = None,
        conditional_min_words: int = DEFAULT_YC_BLOG_CONDITIONAL_MIN_WORDS,
    ) -> int:
        """Save discovered posts as consolidated JSON metadata file."""
        ignore_sources = load_ignore_sources()
        saved = 0
        consolidated: list[Dict[str, Any]] = []
        include_values = list(include_tags or [])
        exclude_values = list(exclude_tags or [])
        conditional_values = list(conditional_tags or [])

        for post in posts:
            normalized = self._normalize_hit(post)
            normalized["categories"] = _flatten_strings(post.get("categories"))
            normalized["subcategories"] = _flatten_strings(post.get("subcategories"))
            if normalized["url"] and not any(
                is_ignored(normalized.get(field, ""), ignore_sources)
                for field in ("url", "id", "title", "author")
            ):
                if include_values or exclude_values or conditional_values:
                    decision = classify_by_tag_cascade(
                        normalized,
                        include_tags=include_values,
                        exclude_tags=exclude_values,
                        conditional_tags=conditional_values,
                    )

                    # If tag cascade returns "skip" (no tags matched),
                    # try content-based classification
                    if decision == "skip" and post.get("content"):
                        decision = classify_by_content(post)

                    if decision == "exclude" or decision == "skip":
                        continue
                    if decision == "conditional":
                        if not passes_conditional_content_filter(
                            normalized["url"], min_words=conditional_min_words
                        ):
                            continue
                normalized["file"] = f"{normalized['id']}.md"
                if not normalized.get("source_url"):
                    normalized["source_url"] = normalized.get("media_url") or normalized["url"]
                # Clean metadata before saving (remove null fields and keep only
                # id/name/slug for tags)
                cleaned = clean_metadata_record(normalized)
                consolidated.append(cleaned)
                saved += 1

        # Save consolidated metadata file
        if consolidated:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                json.dump({"posts": consolidated}, f, indent=2)

        return saved


class YCBlogScraper(AlgoliaScraper):
    """Discover YC Blog posts and derive taxonomy for tag-based filtering."""

    BLOG_URL = "https://www.ycombinator.com/blog/"
    BLOG_CONFIG_PATTERNS = [
        re.compile(
            (
                r'"algolia"\s*:\s*\{[^}]*"appId"\s*:\s*"(?P<app>[^"]+)"[^}]*'
                r'"apiKey"\s*:\s*"(?P<key>[^"]+)"[^}]*'
                r'"indexName"\s*:\s*"(?P<index>[^"]+)"'
            ),
            re.IGNORECASE,
        ),
        re.compile(
            (
                r'"appId"\s*:\s*"(?P<app>[^"]+)"[^}]+?'
                r'"apiKey"\s*:\s*"(?P<key>[^"]+)"[^}]+?'
                r'"indexName"\s*:\s*"(?P<index>[^"]+)"'
            ),
            re.IGNORECASE,
        ),
    ]

    def __init__(
        self,
        app_id: Optional[str] = None,
        api_key: Optional[str] = None,
        index_name: Optional[str] = None,
        config: Optional[Config] = None,
    ):
        """Initialize YC Blog scraper with blog-specific Algolia credentials."""
        if config is None:
            config = Config()

        # Use blog-specific defaults if not provided
        app_id = app_id or config.algolia_app_id
        api_key = api_key or config.algolia_blog_api_key
        index_name = index_name or config.algolia_blog_index

        # Initialize parent with blog credentials
        super().__init__(app_id=app_id, api_key=api_key, index_name=index_name, config=config)

    def _make_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Override to send credentials as URL query parameters for blog API."""
        # The blog API requires credentials in URL query params, not headers
        query_params = urlencode(
            [
                (key, value if isinstance(value, str) else json.dumps(value))
                for key, value in params.items()
            ]
        )
        payload = {
            "requests": [
                {
                    "indexName": self.index_name,
                    "params": query_params,
                }
            ]
        }

        # Send credentials as URL query parameters for the blog API
        url_params = {
            "x-algolia-application-id": self.app_id,
            "x-algolia-api-key": self.api_key,
        }

        headers = {
            "Content-Type": "application/json",
            "Referer": "https://www.ycombinator.com/",
            "User-Agent": "Mozilla/5.0",
        }

        response = requests.post(
            self.queries_url,
            params=url_params,
            json=payload,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        result: Dict[str, Any] = response.json()
        return result

    @classmethod
    def discover_algolia_config(cls) -> Dict[str, str]:
        """Best-effort discovery of blog Algolia credentials from YC blog HTML."""
        response = requests.get(cls.BLOG_URL, timeout=20)
        response.raise_for_status()
        html = response.text
        for pattern in cls.BLOG_CONFIG_PATTERNS:
            match = pattern.search(html)
            if match:
                return {
                    "app_id": match.group("app"),
                    "api_key": match.group("key"),
                    "index_name": match.group("index"),
                }
        raise RuntimeError("Unable to auto-discover YC Blog Algolia config")

    def _normalize_hit(self, hit: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Algolia hit to post metadata for blog posts."""
        # For blog posts, construct URL with /blog/ path
        page_url = hit.get("shared_search_path") or hit.get("slug") or hit.get("url")

        if page_url:
            # Ensure it starts with a slash
            if not page_url.startswith("/"):
                page_url = "/" + page_url
            # Ensure it includes /blog/ path
            if not page_url.startswith("/blog/"):
                page_url = "/blog" + page_url
            # Convert to full URL
            page_url = f"https://www.ycombinator.com{page_url}"

        media_url = hit.get("link") or hit.get("url")
        if media_url:
            if not _is_media_url(media_url):
                media_url = ""
            elif not media_url.startswith("http"):
                media_url = f"https://{media_url.lstrip('/')}"
        if not media_url:
            media_url = ""

        source_type = _canonical_source_type(hit.get("media_type") or hit.get("type") or "Article")
        title = hit.get("title", hit.get("name", ""))
        title_id = _slugify(title) or hit.get("objectID", "")

        return {
            "id": title_id,
            "algolia_id": hit.get("objectID", ""),
            "url": page_url,
            "media_url": media_url,
            "title": title,
            "company": hit.get("company_name", ""),
            "author": hit.get("author", ""),
            "date": hit.get("published_at", hit.get("date", "")),
            "description": hit.get("description", hit.get("content", "")),
            "tags": hit.get("tags", []),
            "type": source_type,
            "source_type": source_type,
        }

    def browse_all_from_rss(self) -> list[Dict[str, str | None]]:
        """Fallback: Fetch YC Blog posts from RSS feed + individual post scraping."""
        import xml.etree.ElementTree as ET

        posts: list[Dict[str, str | None]] = []
        try:
            rss_resp = requests.get(f"{self.BLOG_URL}feed", timeout=20)
            rss_resp.raise_for_status()
            root = ET.fromstring(rss_resp.content)

            items = root.findall(".//item")
            for item in items:
                title_elem = item.find("title")
                link_elem = item.find("link")
                category_elem = item.find("category")

                title = (title_elem.text or "").strip() if title_elem is not None else ""
                link = (link_elem.text or "").strip() if link_elem is not None else ""
                category = (category_elem.text or "").strip() if category_elem is not None else ""

                if not link:
                    continue

                objectid = link.split("/")[-1].rstrip("/") or "unknown"
                post_data: Dict[str, Any] = {
                    "objectID": objectid,
                    "post_title": title,
                    "url": link,
                    "tags": [category] if category else [],
                }

                try:
                    post_resp = requests.get(link, timeout=10)
                    post_resp.raise_for_status()
                    post_soup = BeautifulSoup(post_resp.content, "html.parser")

                    all_tags: set[str] = set(post_data.get("tags", []) or [])

                    meta_tags = post_soup.find_all("meta", {"property": "article:tag"})
                    for tag in meta_tags:
                        content = tag.get("content")
                        if isinstance(content, str):
                            content_str = content.strip()
                            if content_str:
                                all_tags.add(content_str)

                    meta_keywords = post_soup.find("meta", {"name": "keywords"})
                    if meta_keywords:
                        content = meta_keywords.get("content")
                        if isinstance(content, str):
                            keywords = [t.strip() for t in content.split(",") if t.strip()]
                            all_tags.update(keywords)

                    json_ld = post_soup.find("script", {"type": "application/ld+json"})
                    if json_ld and json_ld.string:
                        try:
                            ld_data = json.loads(json_ld.string)
                            if isinstance(ld_data, dict):
                                if "keywords" in ld_data:
                                    kw = ld_data["keywords"]
                                    if isinstance(kw, str):
                                        all_tags.update(
                                            [t.strip() for t in kw.split(",") if t.strip()]
                                        )
                                    elif isinstance(kw, list):
                                        all_tags.update(kw)
                        except Exception:
                            pass

                    article_content = ""
                    article = post_soup.find("article") or post_soup.find("main")
                    if article:
                        article_content = article.get_text()
                    post_data["content"] = article_content[:10000]
                    post_data["tags"] = list(all_tags)

                except Exception:
                    pass

                posts.append(post_data)

            return posts

        except Exception:
            return []


def main():
    """CLI entry point for discovery."""
    import argparse

    parser = argparse.ArgumentParser(description="Discover YC Library posts")
    parser.add_argument("--output-dir", default=DEFAULT_METADATA_DIR, help="Output directory")
    parser.add_argument("--algolia-app-id", help="Algolia app ID")
    parser.add_argument("--algolia-api-key", help="Algolia API key")
    parser.add_argument("--algolia-index", default="library_posts", help="Algolia index name")

    args = parser.parse_args()

    scraper = AlgoliaScraper(
        app_id=args.algolia_app_id,
        api_key=args.algolia_api_key,
        index_name=args.algolia_index,
    )

    print(f"Discovering posts from Algolia ({args.algolia_index})...")
    posts = scraper.browse_all()
    print(f"Found {len(posts)} posts")

    saved = scraper.save_posts(posts, args.output_dir)
    print(f"Saved {saved} posts to {args.output_dir}/")


if __name__ == "__main__":
    main()


class AlgoliaPageinator:
    """Enhanced pagination for large Algolia result sets."""

    def __init__(self, client, app_id, api_key, index_name):
        self.client = client
        self.app_id = app_id
        self.api_key = api_key
        self.index_name = index_name

    def paginate_all_results(self, query="", filters="", batch_size=1000, max_results=None):
        """Paginate through all Algolia results efficiently.

        Args:
            query: Search query
            filters: Algolia filter expression
            batch_size: Results per page
            max_results: Stop after this many results (None = all)

        Yields:
            Result batches
        """
        import requests

        params = {
            "query": query,
            "hitsPerPage": batch_size,
            "page": 0,
        }

        if filters:
            params["filters"] = filters

        total_fetched = 0

        while True:
            try:
                # Make paginated request to Algolia API
                url = f"https://{self.app_id}-dsn.algolia.net/1/indexes/{self.index_name}"
                headers = {
                    "X-Algolia-API-Key": self.api_key,
                    "X-Algolia-Application-Id": self.app_id,
                }

                response = requests.get(url, params=params, headers=headers, timeout=10)
                response.raise_for_status()

                data = response.json()
                hits = data.get("hits", [])

                if not hits:
                    break

                yield hits
                total_fetched += len(hits)

                if max_results and total_fetched >= max_results:
                    break

                if len(hits) < batch_size:
                    break

                params["page"] += 1

            except Exception as e:
                print(f"Pagination error: {e}")
                break


class MetadataFilter:
    """Filtering and deduplication for YC Library metadata."""

    @staticmethod
    def filter_duplicates(metadata_list: list, key_field="url") -> list:
        """Remove duplicate entries by canonical key.

        Args:
            metadata_list: List of metadata dicts
            key_field: Field to use as deduplication key

        Returns:
            Deduplicated list preserving order
        """
        seen = set()
        result = []
        for item in metadata_list:
            key = item.get(key_field)
            if key and key not in seen:
                seen.add(key)
                result.append(item)
        return result

    @staticmethod
    def filter_by_criteria(metadata_list: list, criteria: dict) -> list:
        """Filter metadata by multiple criteria.

        Args:
            metadata_list: List of metadata dicts
            criteria: Dict of {field: value_or_list}

        Returns:
            Filtered list
        """
        result = []
        for item in metadata_list:
            match = True
            for field, expected in criteria.items():
                actual = item.get(field)
                if isinstance(expected, list):
                    if actual not in expected:
                        match = False
                        break
                elif actual != expected:
                    match = False
                    break
            if match:
                result.append(item)
        return result

    @staticmethod
    def enrich_metadata(item: dict) -> dict:
        """Add computed fields to metadata.

        Args:
            item: Metadata dict

        Returns:
            Enriched metadata
        """
        enriched = item.copy()

        # Add content type detection
        if "media_url" in enriched and enriched["media_url"]:
            if "youtube.com" in enriched["media_url"] or "youtu.be" in enriched["media_url"]:
                enriched["content_type"] = "video"
            elif enriched["media_url"].endswith((".pdf", ".epub")):
                enriched["content_type"] = "document"

        # Add quality markers
        enriched["quality_score"] = 0
        if enriched.get("title"):
            enriched["quality_score"] += 20
        if enriched.get("description"):
            enriched["quality_score"] += 20
        if enriched.get("author"):
            enriched["quality_score"] += 20
        if enriched.get("published_at"):
            enriched["quality_score"] += 20
        if enriched.get("url"):
            enriched["quality_score"] += 20

        return enriched
