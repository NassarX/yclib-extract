import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlencode

import requests

from .config import Config

ARTIFACTS_DIR = Path("artifacts")
DEFAULT_METADATA_DIR = str(ARTIFACTS_DIR / "yc_library_metadata.json")
IGNORE_SOURCES_PATH = Path("config/ignore_sources.json")


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

    def fetch_items(self) -> list[Dict[str, str]]:
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

    def _make_request(self, params: Dict) -> Dict:
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
        return response.json()

    def browse_all(self, per_page: int = 1000) -> list[Dict]:
        """Browse all posts via Algolia."""
        posts = []
        page = 0

        while True:
            params = {
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

            result = self._make_request(params)
            query_result = result.get("results", [{}])[0]
            posts.extend(query_result.get("hits", []))

            nb_pages = query_result.get("nbPages", 0) or 0
            if page >= nb_pages - 1:
                break
            page += 1

        return posts

    def _normalize_hit(self, hit: Dict) -> Dict:
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

    def save_posts(self, posts: list[Dict], output_file: str):
        """Save discovered posts as consolidated JSON metadata file."""
        ignore_sources = load_ignore_sources()
        saved = 0
        consolidated = []

        for post in posts:
            normalized = self._normalize_hit(post)
            if normalized["url"] and not any(
                is_ignored(normalized.get(field, ""), ignore_sources)
                for field in ("url", "id", "title", "author")
            ):
                normalized["file"] = f"{normalized['id']}.md"
                if not normalized.get("source_url"):
                    normalized["source_url"] = normalized.get("media_url") or normalized["url"]
                consolidated.append(normalized)
                saved += 1

        # Save consolidated metadata file
        if consolidated:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                json.dump({"posts": consolidated}, f, indent=2)

        return saved


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
