import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import quote

import requests

RAW_TAG_URL = "https://raw.githubusercontent.com/yc-oss/api/main/tags/{tag}.json"
DEFAULT_TIMEOUT = 15


class CompaniesByTagScraper:
    def __init__(self, session: Optional[requests.Session] = None, base_url: str = RAW_TAG_URL):
        self.session = session or requests.Session()
        self.base_url = base_url

    @staticmethod
    def _humanize_tag_slug(tag: str) -> str:
        return tag.replace("-", " ").strip().title()

    def _fetch_json(self, url: str, retries: int = 3, backoff: float = 0.4) -> Optional[Any]:
        for attempt in range(1, retries + 1):
            try:
                resp = self.session.get(url, timeout=DEFAULT_TIMEOUT)
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:
                if attempt == retries:
                    raise
                time.sleep(backoff * attempt)
        return None

    def fetch_url(self, url: str) -> List[Dict[str, Any]]:
        data = self._fetch_json(url)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for value in data.values():
                if isinstance(value, list):
                    return value
        return []

    def fetch_tag(self, tag: str) -> List[Dict[str, Any]]:
        """Fetch the JSON array for a single tag slug."""
        url = self.base_url.format(tag=tag)
        return self.fetch_url(url)

    def get_tag_counts(self, tags: List[str]) -> Dict[str, int]:
        """Return a mapping of tag -> count of companies for the provided tags."""
        counts: Dict[str, int] = {}
        for tag in tags:
            try:
                items = self.fetch_tag(tag)
                counts[tag] = len(items)
            except Exception:
                counts[tag] = 0
        return counts

    def build_tag_record(self, tag: str, count: Optional[int] = None) -> Dict[str, Any]:
        slug = tag.strip()
        url = self.base_url.format(tag=quote(slug, safe=""))
        return {
            "name": self._humanize_tag_slug(slug),
            "slug": slug,
            "url": url,
            "count": count,
        }

    def save_metadata(self, tags: List[str], output_dir: str, force: bool = False, concurrency: int = 4) -> int:
        """Fetch per-tag company lists and save them as JSON files under output_dir.

        Uses a thread pool to fetch tags in parallel. Returns the total number
        of company entries saved across tags.
        """
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        total = 0
        summary: List[Dict[str, Any]] = []

        def _process_tag(tag: str):
            try:
                items = self.fetch_tag(tag)
            except Exception:
                items = []
            tag_file = out_path / f"{tag}.json"
            if tag_file.exists() and not force:
                # read existing to count
                try:
                    existing = json.loads(tag_file.read_text())
                    count = len(existing) if isinstance(existing, list) else 0
                except Exception:
                    count = 0
            else:
                try:
                    tag_file.write_text(json.dumps(items, indent=2))
                    count = len(items)
                except Exception:
                    count = 0
            record = self.build_tag_record(tag, count=count)
            record["file"] = str(tag_file)
            return record, count

        # Run fetches in parallel
        with ThreadPoolExecutor(max_workers=max(1, int(concurrency))) as exe:
            futures = {exe.submit(_process_tag, tag): tag for tag in tags}
            for fut in as_completed(futures):
                try:
                    record, count = fut.result()
                except Exception:
                    continue
                summary.append(record)
                total += count

        # write consolidated taxonomy/summary
        summary_file = out_path.parent / "yc_companies_by_tag_metadata.json"
        try:
            summary_file.write_text(json.dumps({"tags": summary}, indent=2))
        except Exception:
            pass
        return total
