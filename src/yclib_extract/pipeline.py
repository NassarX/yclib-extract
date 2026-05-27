"""Pipeline orchestration for YC Library discovery, extraction, and audits."""

import argparse
import csv
import json
import os
import re
import sqlite3
import contextlib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET
import unicodedata

import requests
from bs4 import BeautifulSoup

from .extractor import (
    DEFAULT_CONTENT_DIR,
    DEFAULT_DB_PATH,
    REMOVED_WORD_THRESHOLD,
    ContentExtractor,
    YCLibraryExtractionEnhancer,
)
from .lib.html_cleaning import (
    extract_main_content,
    html_to_markdown,
    process_footnotes,
    process_internal_links,
)
from .lib.youtube_transcripts import extract_podcast_url, extract_youtube_url
from .scraper import AlgoliaScraper, RSSScraper, is_ignored, load_ignore_sources

ARTIFACTS_DIR = Path("artifacts").resolve()
METADATA_DIR = ARTIFACTS_DIR / "metadata"
DEFAULT_METADATA_DIR = str(METADATA_DIR / "yc_library_metadata.json")
DEFAULT_PG_METADATA = METADATA_DIR / "pg_essays_metadata.json"
DEFAULT_SA_METADATA = METADATA_DIR / "altman_essays_metadata.json"
DEFAULT_SS_METADATA = METADATA_DIR / "yc_startup_school_metadata.json"
DEFAULT_PG_ESSAYS_DIR = str(ARTIFACTS_DIR / "pg_essays")
DEFAULT_SA_ESSAYS_DIR = str(ARTIFACTS_DIR / "altman_essays")
SA_STARTUP_DIR = ARTIFACTS_DIR / "yc_startup_school"
UNIFIED_AUDIT_CSV = ARTIFACTS_DIR / "resources_audit.csv"
SCRAPE_RUNS_DIR = Path("scrape_runs").resolve()
RETRYABLE_STATUSES = {"failed", "error", "short"}
COMPLETED_STATUSES = {"done", "short", "removed"}
STAGE_ORDER = {"discover": 0, "extract": 1, "audit": 2}
PG_ARTICLES_INDEX_URL = "https://paulgraham.com/articles.html"
PG_RSS_URL = "https://paulgraham.com/rss.xml"
PG_INDEX_DENYLIST = {
    "articles.html",
    "index.html",
    "rss.html",
    "avg.html",
    "gb.html",
}
SA_ARTICLES_FEED_URL = "https://blog.samaltman.com/posts.atom"
SA_ARCHIVE_URL = "https://blog.samaltman.com/archive"
SA_INDEX_DENYLIST = {
    "archive",
    "archive.html",
    "index.html",
    "rss.xml",
}


def _count_words(text: str) -> int:
    return len([token for token in text.split() if token.strip()])


def _estimate_reading_time(word_count: int) -> str:
    """Estimate reading time in minutes (assuming 200 wpm)."""
    minutes = max(1, round(word_count / 200))
    return f"{minutes} min"


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open() as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _load_metadata_posts(metadata_path: str) -> List[Dict[str, Any]]:
    """Load posts from consolidated metadata JSON file.

    Args:
        metadata_path: Path to yc_library_metadata.json file

    Returns:
        List of post metadata dictionaries
    """
    path = Path(metadata_path)
    if not path.exists():
        return []

    try:
        data = _load_json(path)
        # Check if it has a "posts" key (new format with consolidated structure)
        if isinstance(data, dict) and "posts" in data:
            return data.get("posts", [])
        # Otherwise return the data as-is if it's a list
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def _safe_filename(value: str) -> str:
    parsed = urlparse(value)
    slug = (parsed.path or value).strip("/").replace("/", "-")
    return slug or "item"


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


def _parse_frontmatter(path: Path) -> Tuple[Dict[str, Any], str]:
    if not path.exists():
        return {}, ""

    lines = path.read_text().splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, path.read_text()

    frontmatter: Dict[str, Any] = {}
    body_start = 1
    for index in range(1, len(lines)):
        line = lines[index].strip()
        if line == "---":
            body_start = index + 1
            break
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        value = raw_value.strip()
        if value:
            try:
                frontmatter[key.strip()] = json.loads(value)
            except json.JSONDecodeError:
                frontmatter[key.strip()] = value.strip('"')

    body = "\n".join(lines[body_start:]).strip()
    return frontmatter, body


class PipelineDB:
    """SQLite tracking for pipeline stages keyed by canonical URL."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self.init_db()

    @contextlib.contextmanager
    def _connect(self):
        """Internal helper to ensure connections are always closed and use a timeout for robustness."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            yield conn
        finally:
            conn.close()

    def init_db(self):
        db_parent = Path(self.db_path).parent
        if str(db_parent) not in ("", "."):
            db_parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_items (
                    canonical_url TEXT PRIMARY KEY,
                    title TEXT,
                    source_type TEXT,
                    metadata_path TEXT,
                    content_path TEXT,
                    job_id TEXT,
                    stage TEXT DEFAULT 'discover',
                    status TEXT DEFAULT 'pending',
                    media_url TEXT,
                    word_count INTEGER,
                    content_words INTEGER,
                    last_error TEXT,
                    last_seen_at TEXT,
                    updated_at TEXT
                )
                """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    run_id TEXT PRIMARY KEY,
                    start_stage TEXT,
                    mode TEXT,
                    replay INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running',
                    started_at TEXT,
                    ended_at TEXT,
                    metadata_dir TEXT,
                    content_dir TEXT
                )
                """)
            conn.commit()

    def upsert_item(self, canonical_url: str, **fields: Any):
        if not canonical_url:
            return

        now = datetime.now().isoformat()
        existing = self.get_item(canonical_url)
        payload = {
            "title": fields.get("title") or (existing or {}).get("title"),
            "source_type": fields.get("source_type") or (existing or {}).get("source_type"),
            "metadata_path": fields.get("metadata_path") or (existing or {}).get("metadata_path"),
            "content_path": fields.get("content_path") or (existing or {}).get("content_path"),
            "job_id": fields.get("job_id") or (existing or {}).get("job_id"),
            "stage": fields.get("stage") or (existing or {}).get("stage") or "discover",
            "status": fields.get("status") or (existing or {}).get("status") or "pending",
            "media_url": fields.get("media_url") or (existing or {}).get("media_url"),
            "word_count": (
                fields.get("word_count")
                if fields.get("word_count") is not None
                else (existing or {}).get("word_count")
            ),
            "content_words": (
                fields.get("content_words")
                if fields.get("content_words") is not None
                else (existing or {}).get("content_words")
            ),
            "last_error": fields.get("last_error") or (existing or {}).get("last_error"),
            "last_seen_at": now,
            "updated_at": now,
        }

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO pipeline_items (
                    canonical_url, title, source_type, metadata_path, content_path, job_id,
                    stage, status, media_url, word_count, content_words, last_error,
                    last_seen_at, updated_at
                ) VALUES (
                    :canonical_url, :title, :source_type, :metadata_path, :content_path, :job_id,
                    :stage, :status, :media_url, :word_count, :content_words, :last_error,
                    :last_seen_at, :updated_at
                )
                ON CONFLICT(canonical_url) DO UPDATE SET
                    title=excluded.title,
                    source_type=excluded.source_type,
                    metadata_path=excluded.metadata_path,
                    content_path=excluded.content_path,
                    job_id=excluded.job_id,
                    stage=excluded.stage,
                    status=excluded.status,
                    media_url=excluded.media_url,
                    word_count=excluded.word_count,
                    content_words=excluded.content_words,
                    last_error=excluded.last_error,
                    last_seen_at=excluded.last_seen_at,
                    updated_at=excluded.updated_at
                """,
                {"canonical_url": canonical_url, **payload},
            )
            conn.commit()

    def get_item(self, canonical_url: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM pipeline_items WHERE canonical_url = ?",
                (canonical_url,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return dict(zip([column[0] for column in cursor.description], row))

    def iter_items(self) -> Iterable[Dict[str, Any]]:
        with self._connect() as conn:
            cursor = conn.execute("SELECT * FROM pipeline_items ORDER BY updated_at, canonical_url")
            columns = [column[0] for column in cursor.description]
            for row in cursor.fetchall():
                yield dict(zip(columns, row))

    def begin_run(
        self,
        run_id: str,
        start_stage: str,
        mode: str,
        replay: bool,
        metadata_dir: str,
        content_dir: str,
    ):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO pipeline_runs (
                    run_id, start_stage, mode, replay, status, started_at, metadata_dir, content_dir
                ) VALUES (?, ?, ?, ?, 'running', ?, ?, ?)
                """,
                (
                    run_id,
                    start_stage,
                    mode,
                    int(replay),
                    datetime.now().isoformat(),
                    metadata_dir,
                    content_dir,
                ),
            )
            conn.commit()

    def end_run(self, run_id: str, status: str):
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE pipeline_runs
                SET status = ?, ended_at = ?
                WHERE run_id = ?
                """,
                (status, datetime.now().isoformat(), run_id),
            )
            conn.commit()

    def get_last_run(self) -> Optional[Dict[str, Any]]:
        """Get the most recent pipeline run."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if not row:
                return None
            return dict(zip([column[0] for column in cursor.description], row))


class PipelineOrchestrator:
    """Run discovery, extraction, and auditing as a single pipeline."""

    def __init__(
        self,
        metadata_dir: str = DEFAULT_METADATA_DIR,
        content_dir: str = DEFAULT_CONTENT_DIR,
        db_path: str = DEFAULT_DB_PATH,
        workers: int = 4,
        min_content_length: int = 700,
        algolia_app_id: Optional[str] = None,
        algolia_api_key: Optional[str] = None,
        algolia_index: str = "library_posts",
    ):
        self.metadata_dir = Path(metadata_dir)
        self.content_dir = Path(content_dir)
        self.pg_essays_dir = Path(os.environ.get("PG_ESSAYS_DIR", DEFAULT_PG_ESSAYS_DIR))
        self.sa_essays_dir = Path(os.environ.get("SA_ESSAYS_DIR", DEFAULT_SA_ESSAYS_DIR))
        self.workers = workers
        self.db = PipelineDB(db_path)
        self.extractor = ContentExtractor(
            output_dir=content_dir, min_content_length=min_content_length
        )
        self.pg_extractor = ContentExtractor(
            output_dir=str(self.pg_essays_dir), min_content_length=1
        )
        self.sa_extractor = ContentExtractor(
            output_dir=str(self.sa_essays_dir), min_content_length=1
        )
        self.pg_metadata_path = Path(os.environ.get("PG_METADATA", str(DEFAULT_PG_METADATA)))
        self.sa_metadata_path = Path(os.environ.get("SA_METADATA", str(DEFAULT_SA_METADATA)))
        self.ss_metadata_path = Path(os.environ.get("SS_METADATA", str(DEFAULT_SS_METADATA)))
        self.scraper = AlgoliaScraper(
            app_id=algolia_app_id,
            api_key=algolia_api_key,
            index_name=algolia_index,
        )
        # Create parent directories
        METADATA_DIR.mkdir(parents=True, exist_ok=True)
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.pg_essays_dir.mkdir(parents=True, exist_ok=True)
        self.sa_essays_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _log(message: str):
        print(f"[pipeline] {message}")

    def run(
        self,
        start_stage: str = "discover",
        mode: str = "weekly",
        replay: bool = False,
        force: bool = False,
        limit: Optional[int] = None,
        retry_failed_only: bool = False,
    ) -> Dict[str, int]:
        start_stage = start_stage.lower().strip()
        if start_stage not in STAGE_ORDER:
            raise ValueError(f"Unknown start stage: {start_stage}")

        if mode not in {"weekly", "dev"}:
            raise ValueError(f"Unknown mode: {mode}")

        last_run = self.db.get_last_run()
        if last_run and last_run["status"] == "error" and not replay and not force:
            self._log(
                f"Warning: Last run {last_run['run_id']} failed. "
                "Consider using --replay to resume or --force to restart."
            )

        force = force or replay or mode == "dev"
        run_id = datetime.now().strftime("%Y%m%d%H%M%S")
        self.db.begin_run(
            run_id, start_stage, mode, force, str(self.metadata_dir), str(self.content_dir)
        )
        self._log(
            f"run {run_id} started at stage '{start_stage}' ({mode}{', force' if force else ''})"
        )

        try:
            # Adjust extractor min_content_length based on env or dev mode
            env_min = os.environ.get("YCLIB_EXTRACT_MIN_CONTENT_LENGTH")
            if env_min:
                try:
                    self.extractor.min_content_length = int(env_min)
                    msg = (
                        f"extractor.min_content_length set from env: "
                        f"{self.extractor.min_content_length}"
                    )
                    self._log(msg)
                except ValueError:
                    min_len = self.extractor.min_content_length
                    msg = (
                        f"Invalid YCLIB_EXTRACT_MIN_CONTENT_LENGTH='{env_min}'; "
                        f"using default {min_len}"
                    )
                    self._log(msg)
            elif mode == "dev":
                # lower threshold for dev runs
                self.extractor.min_content_length = 700
                self._log("dev mode: extractor.min_content_length set to 700")

            stages = ["discover", "extract", "audit"]
            results = {"discovered": 0, "extracted": 0}
            
            # Filter stages based on start_stage
            active_stages = stages[stages.index(start_stage):]
            
            for stage in active_stages:
                self._log(f"executing stage: {stage}")
                
                if stage == "discover":
                    results["discovered"] = self.discover(run_id=run_id)
                elif stage == "extract":
                    results["extracted"] = self.extract(
                        force=force, limit=limit, retry_failed_only=retry_failed_only
                    )
                elif stage == "audit":
                    self.write_unified_audit()
                    
            self._write_scrape_run(
                run_id, active_stages[-1], results["discovered"], results["extracted"], 
                force=force, limit=limit
            )
            self.db.end_run(run_id, "done")
            self._log("run complete")
            return results
        except Exception:
            self.db.end_run(run_id, "error")
            self._log("run failed")
            raise

    def run_full(self, force: bool = False, replay: bool = False) -> Dict[str, Any]:
        """Run full extraction: PG Essays, Sam Altman Essays, YC Library, and Startup School."""
        self._log("starting full extraction pipeline")

        pg_stats = self.fetch_pg_essays(force=force or replay)
        sa_stats = self.fetch_sa_essays(force=force or replay)

        # YC Library
        yc_stats = self.run(mode="dev" if force or replay else "weekly", force=force, replay=replay)

        # Startup School
        ss_stats = self.run_startup_school(force=force, replay=replay)

        self._log("full extraction pipeline complete")
        return {"pg": pg_stats, "sa": sa_stats, "yc": yc_stats, "ss": ss_stats}

    def run_startup_school(self, replay: bool = False, force: bool = False) -> Dict[str, Any]:
        """Run standalone startup-school workflow using standard metadata-driven extraction."""
        run_id = datetime.now().strftime("%Y%m%d%H%M%S")
        mode = "dev" if force else "weekly"
        self.db.begin_run(
            run_id, "curriculum", mode, replay, str(self.ss_metadata_path), str(SA_STARTUP_DIR)
        )
        force_str = ", force" if force else ""
        self._log(f"startup_school run {run_id} started ({mode}{force_str})")

        try:
            # 1. Generate standard metadata from YAML config
            self._log(f"generating curriculum metadata: {self.ss_metadata_path}")
            cmd_meta = [
                sys.executable,
                "scripts/build_curriculum.py",
                "--artifacts-dir",
                str(ARTIFACTS_DIR),
                "--inject-only",
                "--inject-metadata-dir",
                str(self.ss_metadata_path),
            ]
            subprocess.run(cmd_meta, check=True)

            # 2. Run standalone curriculum build with prioritized copying and extraction
            self._log(
                f"running curriculum resource population (copy + extract) into {SA_STARTUP_DIR}"
            )
            cmd_populate = [
                sys.executable,
                "scripts/build_curriculum.py",
                "--artifacts-dir",
                str(ARTIFACTS_DIR),
                "--ensure-local",
            ]
            if force or replay or mode == "dev":
                cmd_populate.append("--force")
            subprocess.run(cmd_populate, check=True)

            self.write_unified_audit()
            self.db.end_run(run_id, "done")
            self._log("startup_school run complete")
            return {
                "status": "success",
                "run_id": run_id,
                "metadata": str(self.ss_metadata_path),
                "output": str(SA_STARTUP_DIR),
            }
        except Exception:
            self.db.end_run(run_id, "error")
            self._log("startup_school run failed")
            raise

    def _run_curriculum_build(self, inject_only: bool) -> None:
        cmd = [
            sys.executable,
            "scripts/build_curriculum.py",
            "--artifacts-dir",
            str(ARTIFACTS_DIR),
        ]
        if inject_only:
            cmd.extend(["--inject-only", "--inject-metadata-dir", str(self.metadata_dir)])
            phase = "inject-only"
        else:
            cmd.append("--collect")
            phase = "build"
        self._log(f"running curriculum {phase}: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=False)
        if result.returncode != 0:
            raise RuntimeError(f"curriculum {phase} failed with exit code {result.returncode}")

    @staticmethod
    def _pg_slug(url: str) -> str:
        name = Path(urlparse(url).path).name
        stem = name[:-5] if name.lower().endswith(".html") else name
        return _slugify(stem)

    def _fetch_pg_index_urls(self) -> List[str]:
        """Fetch all Paul Graham essay URLs from both HTML index and RSS feed."""
        urls = set()

        # 1. Fetch from HTML index (archive)
        try:
            response = requests.get(PG_ARTICLES_INDEX_URL, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for link in soup.find_all("a", href=True):
                absolute = urljoin(PG_ARTICLES_INDEX_URL, link["href"])
                parsed = urlparse(absolute)
                if parsed.netloc.lower() not in {"paulgraham.com", "www.paulgraham.com"}:
                    continue
                name = Path(parsed.path).name.lower()
                if not name.endswith(".html"):
                    continue
                if name in PG_INDEX_DENYLIST:
                    continue
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                urls.add(clean_url)
        except Exception as e:
            self._log(f"Warning: Failed to fetch PG HTML index: {e}")

        # 2. Fetch from RSS feed (recent)
        try:
            rss = RSSScraper(PG_RSS_URL)
            for item in rss.fetch_items():
                if item.get("url"):
                    urls.add(item["url"])
        except Exception as e:
            self._log(f"Warning: Failed to fetch PG RSS feed: {e}")

        return sorted(list(urls))

    def fetch_pg_essays(self, force: bool = False) -> Dict[str, int]:
        """Fetch all Paul Graham essays from the authoritative index into PG_ESSAYS_DIR."""
        self._log(f"fetching PG essays from {PG_ARTICLES_INDEX_URL}")
        urls = self._fetch_pg_index_urls()
        self._log(f"discovered {len(urls)} PG essay URLs")

        # Build URL-to-slug map for internal link processing
        url_to_slug: Dict[str, str] = {url: self._pg_slug(url) for url in urls}

        audit_rows: List[Dict[str, str]] = []
        fetched = 0
        skipped_existing = 0
        failed = 0

        for url in urls:
            url_slug = url_to_slug[url]  # Short slug from URL
            status = "failed"
            reason = ""
            title = url_slug.replace("-", " ").title()

            # Temporary title-based slug for initial check
            title_slug = _slugify(title)
            filename = f"{title_slug}.md"
            output_path = self.pg_essays_dir / filename

            try:
                if output_path.exists() and not force:
                    skipped_existing += 1
                    status = "skipped_existing"
                else:
                    page = requests.get(url, timeout=20)
                    page.raise_for_status()
                    soup = BeautifulSoup(page.content, "html.parser")
                    content_html = extract_main_content(soup)
                    if not content_html:
                        raise ValueError("No extractable content")
                    markdown = html_to_markdown(content_html, base_url=url)

                    # Process footnotes (e.g., [1] text -> [^1]: text)
                    markdown = process_footnotes(markdown)

                    # Extract real title
                    title_node = soup.find("h1") or soup.find("title")
                    if title_node:
                        title = title_node.get_text(" ", strip=True)

                    # Use title-based slug for filename and ID
                    title_slug = _slugify(title)
                    url_to_slug[url] = title_slug  # Update map for internal links
                    filename = f"{title_slug}.md"
                    output_path = self.pg_essays_dir / filename

                    # Process internal PG links (convert to file references)
                    markdown = process_internal_links(
                        markdown, blog_domain="paulgraham.com", url_to_slug_map=url_to_slug
                    )

                    word_count = _count_words(markdown)
                    reading_time = _estimate_reading_time(word_count)

                    metadata = {
                        "id": title_slug,
                        "url": url,
                        "title": title,
                        "author": "Paul Graham",
                        "description": "",
                        "summary": "",
                        "type": "essay",
                        "source_type": "essay",
                        "file": filename,
                        "source_url": url,
                        "word_count": word_count,
                        "reading_time": reading_time,
                    }
                    self.pg_extractor.save_markdown(
                        title_slug, markdown, metadata, source_type="essay"
                    )
                    fetched += 1
                    status = "fetched"
            except Exception as exc:
                failed += 1
                status = "failed"
                reason = str(exc)

            audit_rows.append(
                {
                    "id": title_slug,
                    "url": url,
                    "title": title,
                    "author": "Paul Graham",
                    "type": "essay",
                    "status": status,
                    "reason": reason,
                    "local_path": str(output_path),
                    "quality": metadata.get("quality") if status == "fetched" else None,
                }
            )

        self._log(f"writing PG essays metadata to {self.pg_metadata_path}")
        self.pg_metadata_path.write_text(json.dumps({"posts": audit_rows}, indent=2))
        self.write_unified_audit()
        return {"fetched": fetched, "skipped_existing": skipped_existing, "failed": failed}

    @staticmethod
    def _sa_slug(url: str) -> str:
        """Derive canonical slug from Sam Altman blog URL.

        Examples:
            https://blog.samaltman.com/essay-title → essay-title
            https://blog.samaltman.com/2279512 → 2279512
        """
        parsed = urlparse(url)
        slug = parsed.path.strip("/").split("/")[-1]
        return slug or "essay"

    def _fetch_sa_index_urls(self) -> List[Tuple[str, Optional[str]]]:
        """Fetch Sam Altman essay URLs from Atom feed with publication dates.

        Falls back to archive HTML parsing if feed is unavailable.
        Returns list of (url, published_date) tuples sorted by date (oldest first).
        """
        urls_with_dates = []

        try:
            rss = RSSScraper(SA_ARTICLES_FEED_URL)
            items = rss.fetch_items()
            for item in items:
                if item.get("url"):
                    urls_with_dates.append((item["url"], item.get("date")))

            if urls_with_dates:
                self._log(f"fetched {len(urls_with_dates)} URLs from Atom feed")
                # Sort by date (oldest first), None dates go to end
                urls_with_dates.sort(key=lambda x: (x[1] is None, x[1]))
                return urls_with_dates
        except Exception as exc:
            self._log(f"Atom feed fetch failed: {exc}; falling back to archive parsing")

        # Fallback: Parse archive page with Playwright
        try:
            # Import Playwright locally (optional dependency)
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(SA_ARCHIVE_URL, wait_until="networkidle", timeout=30000)
                content = page.content()
                browser.close()

            soup = BeautifulSoup(content, "html.parser")
            for link in soup.find_all("a", href=True):
                absolute = urljoin(SA_ARCHIVE_URL, link["href"])
                parsed = urlparse(absolute)
                if parsed.netloc.lower() not in {"blog.samaltman.com", "www.blog.samaltman.com"}:
                    continue
                path_lower = parsed.path.lower()
                if any(x in path_lower for x in list(SA_INDEX_DENYLIST)):
                    continue
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                urls_with_dates.append((clean_url, None))

            if urls_with_dates:
                self._log(f"fetched {len(urls_with_dates)} URLs from archive page")
                return sorted(urls_with_dates)
        except Exception as exc:
            self._log(f"Archive page parsing failed: {exc}")

        self._log("warning: could not fetch any Sam Altman essay URLs")
        return []

    def fetch_sa_essays(self, force: bool = False) -> Dict[str, int]:
        """Fetch all Sam Altman essays from blog feed into SA_ESSAYS_DIR.

        Processes essays oldest-to-newest for correct internal link resolution.
        Applies footnote and internal link processing to markdown.
        """
        self._log(f"fetching Sam Altman essays from {SA_ARTICLES_FEED_URL}")
        urls_with_dates = self._fetch_sa_index_urls()
        self._log(f"discovered {len(urls_with_dates)} Sam Altman essay URLs")

        # Build URL-to-slug map for internal link processing
        url_to_slug: Dict[str, str] = {}

        audit_rows: List[Dict[str, str]] = []
        fetched = 0
        skipped_existing = 0
        failed = 0

        for url, published_date in urls_with_dates:
            url_slug = self._sa_slug(url)
            status = "failed"
            reason = ""
            title = url_slug.replace("-", " ").title()

            # Temporary title-based slug for initial check
            title_slug = _slugify(title)
            filename = f"{title_slug}.md"
            output_path = self.sa_essays_dir / filename

            try:
                if output_path.exists() and not force:
                    skipped_existing += 1
                    status = "skipped_existing"
                else:
                    page = requests.get(url, timeout=20)
                    page.raise_for_status()
                    soup = BeautifulSoup(page.content, "html.parser")
                    content_html = extract_main_content(soup)
                    if not content_html:
                        raise ValueError("No extractable content")
                    markdown = html_to_markdown(content_html, base_url=url)

                    # Process footnotes (e.g., [1] text -> [^1]: text)
                    markdown = process_footnotes(markdown)

                    # Extract real title
                    title = ""
                    og_title = soup.find("meta", property="og:title")
                    if og_title and og_title.get("content"):
                        title = og_title["content"]

                    if not title:
                        # Fallback to post-title h2 common on Posthaven
                        post_title_node = soup.find("div", class_="post-title")
                        if post_title_node:
                            h2 = post_title_node.find("h2")
                            if h2:
                                title = h2.get_text(strip=True)

                    if not title:
                        # General fallback: check h1/title but skip if it's just the blog name
                        title_node = soup.find("h1") or soup.find("title")
                        if title_node:
                            potential_title = title_node.get_text(" ", strip=True)
                            if potential_title.lower() not in {
                                "sam altman",
                                "sam altman - sam altman",
                            }:
                                title = potential_title

                    if not title:
                        title = url_slug.replace("-", " ").title()

                    # Use title-based slug for filename and ID
                    title_slug = _slugify(title)
                    url_to_slug[url] = title_slug
                    filename = f"{title_slug}.md"
                    output_path = self.sa_essays_dir / filename

                    # Process internal blog links (convert to file references)
                    markdown = process_internal_links(
                        markdown, blog_domain="blog.samaltman.com", url_to_slug_map=url_to_slug
                    )

                    word_count = _count_words(markdown)
                    reading_time = _estimate_reading_time(word_count)

                    metrics = YCLibraryExtractionEnhancer.track_extraction_quality(
                        markdown, {"title": title, "author": "Sam Altman"}
                    )
                    markdown = YCLibraryExtractionEnhancer.enrich_with_quality_markers(
                        markdown, metrics
                    )

                    metadata = {
                        "id": title_slug,
                        "url": url,
                        "title": title,
                        "author": "Sam Altman",
                        "description": "",
                        "summary": "",
                        "type": "essay",
                        "source_type": "essay",
                        "file": filename,
                        "source_url": url,
                        "published": published_date or "",
                        "word_count": word_count,
                        "reading_time": reading_time,
                        "quality": metrics.get("quality_level"),
                    }
                    self.sa_extractor.save_markdown(
                        title_slug, markdown, metadata, source_type="essay"
                    )
                    fetched += 1
                    status = "fetched"
            except Exception as exc:
                failed += 1
                status = "failed"
                reason = str(exc)

            audit_rows.append(
                {
                    "id": title_slug,
                    "url": url,
                    "title": title,
                    "author": "Sam Altman",
                    "type": "essay",
                    "status": status,
                    "reason": reason,
                    "local_path": str(output_path),
                    "published": published_date or "",
                    "quality": metadata.get("quality") if status == "fetched" else None,
                }
            )

        self._log(f"writing Sam Altman essays metadata to {self.sa_metadata_path}")
        self.sa_metadata_path.write_text(json.dumps({"posts": audit_rows}, indent=2))
        self.write_unified_audit()
        return {"fetched": fetched, "skipped_existing": skipped_existing, "failed": failed}

    def discover(self, run_id: Optional[str] = None) -> int:
        self._log("discovering metadata from Algolia")
        posts = self.scraper.browse_all()
        self._log(f"discovered {len(posts)} posts")
        saved = self.scraper.save_posts(posts, str(self.metadata_dir))
        self._log(f"wrote {saved} metadata files to {self.metadata_dir}")

        metadata_path = Path(self.metadata_dir)
        for post in _load_metadata_posts(str(metadata_path)):
            url = post.get("url") or ""
            if not url:
                continue
            self.db.upsert_item(
                url,
                title=post.get("title", ""),
                source_type=post.get("type") or post.get("source_type") or "article",
                metadata_path=str(metadata_path),
                stage="discover",
                status="pending",
                job_id=post.get("id") or _slugify(post.get("title") or "post"),
            )

        return saved

    def _write_scrape_run(
        self,
        run_id: str,
        run_type: str,
        saved: int,
        extracted: int,
        force: bool = False,
        limit: Optional[int] = None,
    ):
        """Write scrape run summary to audit manifest."""
        SCRAPE_RUNS_DIR.mkdir(parents=True, exist_ok=True)

        # Load posts from consolidated metadata file
        posts = _load_metadata_posts(str(self.metadata_dir))
        items = list(self.db.iter_items())
        summary = self._build_run_summary(items, posts)
        generated_at = datetime.now().isoformat()
        input_dir = _slugify(self.metadata_dir.name.replace("_", "-"))
        date_key = datetime.now().strftime("%Y%m%d")
        filename = f"yc_content_runs_{date_key}.json"
        run_summary = {
            "type": run_type,
            "state": "done",
            "input_dir": input_dir,
            "generated_at": generated_at,
            "total_files": len(posts),
            "done": summary["done"],
            "missing": summary["missing"],
            "by_source_type": summary["by_source_type"],
            "issues": summary["issues"],
            "workers": self.workers,
            "force": bool(force),
            "limit": limit,
            "run_id": run_id,
        }
        output_path = SCRAPE_RUNS_DIR / filename
        payload = {"date": date_key, "runs": []}
        if output_path.exists():
            try:
                existing = json.loads(output_path.read_text())
                if isinstance(existing, dict) and isinstance(existing.get("runs"), list):
                    payload = existing
            except json.JSONDecodeError:
                payload = {"date": date_key, "runs": []}

        payload["date"] = date_key
        payload.setdefault("runs", [])
        payload["runs"] = [run for run in payload["runs"] if run.get("run_id") != run_id]
        payload["runs"].append(run_summary)
        output_path.write_text(json.dumps(payload, indent=2))
        self._log(f"wrote scrape snapshot to {output_path}")

    def _build_run_summary(
        self, items: List[Dict[str, Any]], posts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        summary = {
            "done": 0,
            "missing": 0,
            "by_source_type": {},
            "issues": [],
        }

        def bucket_for(source_type: str) -> str:
            normalized = (source_type or "").strip().lower()
            if normalized in {"article", "blog"}:
                return "blog"
            if normalized in {"video", "podcast"}:
                return "video"
            if normalized == "external":
                return "external"
            return normalized or "other"

        for item in items:
            bucket = bucket_for(item.get("source_type", ""))
            summary["by_source_type"].setdefault(bucket, {"done": 0, "missing": 0})
            status = (item.get("status") or "").lower()
            if status == "done":
                summary["done"] += 1
                summary["by_source_type"][bucket]["done"] += 1
            else:
                summary["missing"] += 1
                summary["by_source_type"][bucket]["missing"] += 1
                summary["issues"].append(
                    {
                        "id": item.get("job_id") or _safe_filename(item.get("canonical_url", "")),
                        "source_type": item.get("source_type", ""),
                        "url": item.get("canonical_url", ""),
                        "status": item.get("status", ""),
                        "media_url": item.get("media_url", ""),
                        "title": item.get("title", ""),
                    }
                )

        if not items and posts:
            summary["missing"] = len(posts)

        return summary

    def extract(
        self,
        force: bool = False,
        limit: Optional[int] = None,
        retry_failed_only: bool = False,
    ) -> int:
        self._log(f"loading metadata from {self.metadata_dir}")
        posts = []
        seen_urls = set()
        ignore_sources = load_ignore_sources()

        for post in _load_metadata_posts(str(self.metadata_dir)):
            url = post.get("url") or ""
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            post_id = post.get("id", _slugify(post.get("title", "post")))
            post_title = post.get("title", "")
            post_type = post.get("type") or post.get("source_type") or "article"
            post_source = f"{url} {post_id} {post_title} {post_type}"
            if is_ignored(post_source, ignore_sources):
                continue

            item = self.db.get_item(url)
            status = (item or {}).get("status")
            if not force and status in COMPLETED_STATUSES:
                continue
            if retry_failed_only and status not in RETRYABLE_STATUSES:
                continue

            posts.append(post)
            if limit is not None and len(posts) >= limit:
                break

        if not posts:
            self._log("no extractable posts found")
            return 0

        self._log(f"extracting {len(posts)} posts with {self.workers} workers")
        completed = 0
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {executor.submit(self._extract_one, post): post.get("id") for post in posts}

            for future in as_completed(futures):
                result = future.result()
                if result:
                    completed += 1
                self._log(f"extracted {completed}/{len(posts)}")

        self._log(f"finished extraction: {completed}/{len(posts)} done")
        self.write_unified_audit()
        return completed

    def _extract_one(self, post: Dict[str, Any]) -> bool:
        url = post.get("url") or ""
        job_id = post.get("id") or _slugify(post.get("title", "post")) or _safe_filename(url)
        source_type = post.get("type") or post.get("source_type") or "article"

        result = self.extractor.extract_content(
            url, job_id, source_type, media_url_hint=post.get("media_url")
        )
        job_status = self.extractor.db.get_job_status(job_id) or {}
        status = job_status.get("status") or "error"
        canonical_source_type = job_status.get("source_type") or source_type

        content_path = ""
        media_url = ""
        word_count = None
        content_words = None

        if result and status == "done":
            content_path = self.extractor.save_markdown(
                job_id,
                result.content,
                post,
                result.video_url or "",
                result.podcast_url or "",
                result.source_type or canonical_source_type,
            )
            media_url = result.video_url or result.podcast_url or ""
            frontmatter, body = _parse_frontmatter(Path(content_path))
            content_words = _count_words(body)
            word_count = frontmatter.get("word_count") or _count_words(body)
        elif status in {"short", "removed", "error", "failed"}:
            media_url = self._recover_media_url(url, canonical_source_type)

        self.db.upsert_item(
            url,
            title=post.get("title", ""),
            source_type=canonical_source_type,
            metadata_path=str(self.metadata_dir),
            content_path=content_path,
            stage="extract",
            status=status,
            job_id=job_id,
            media_url=media_url,
            word_count=word_count,
            content_words=content_words,
            last_error=job_status.get("error_msg", ""),
        )
        return status == "done"

    def _recover_media_url(self, url: str, source_type: str) -> str:
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
        except Exception:
            return ""

        html = response.text
        normalized = (source_type or "").strip().lower()
        if normalized == "podcast":
            return extract_podcast_url(html) or ""

        return extract_youtube_url(html) or extract_podcast_url(html) or ""

    def write_unified_audit(self) -> str:
        """Unify all audits from 4 parts into a single CSV file."""
        self._log(f"generating unified audit: {UNIFIED_AUDIT_CSV}")
        rows = []
        seen_urls = set()

        from .extractor import ExtractionDB

        ex_db = ExtractionDB()
        # Key by URL for robust cross-run matching (IDs may have changed from Algolia -> Title)
        job_stats_by_url = {j.get("url"): j for j in ex_db.get_all_jobs() if j.get("url")}

        # 1. Process Startup School Metadata (Primary for Curriculum items)
        ss_meta_posts = _load_metadata_posts(str(self.ss_metadata_path))
        for item in ss_meta_posts:
            if not item:
                continue
            url = item.get("url")
            if not url or url in seen_urls:
                continue

            job_id = item.get("id")
            filename = item.get("file") or f"{job_id}.md"
            local_path = SA_STARTUP_DIR / filename
            is_done = local_path.exists()

            job_info = job_stats_by_url.get(url) or {}
            quality = job_info.get("quality") or ""

            seen_urls.add(url)
            rows.append(
                {
                    "source": "Startup School",
                    "id": job_id,
                    "title": item.get("title"),
                    "url": url,
                    "source_url": item.get("media_url") or item.get("source_url") or url,
                    "type": (item.get("type") or item.get("source_type") or "Article").title(),
                    "status": "done" if is_done else "missing",
                    "quality": quality,
                    "local_path": str(local_path) if is_done else "",
                    "reason": "" if is_done else "Not yet extracted or copied",
                }
            )

        # 2. Process PG Essays
        pg_meta_posts = _load_metadata_posts(str(self.pg_metadata_path))
        for item in pg_meta_posts:
            if not item:
                continue
            url = item.get("url")
            if not url or url in seen_urls:
                continue

            job_info = job_stats_by_url.get(url) or {}
            quality = job_info.get("quality") or ""

            seen_urls.add(url)
            rows.append(
                {
                    "source": "PG Essays",
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "url": url,
                    "source_url": item.get("source_url") or url,
                    "type": item.get("type", "Essay").title(),
                    "status": "done" if item.get("status") == "fetched" else item.get("status"),
                    "quality": quality,
                    "local_path": item.get("local_path"),
                    "reason": item.get("reason"),
                }
            )

        # 3. Process Sam Altman Essays
        sa_meta_posts = _load_metadata_posts(str(self.sa_metadata_path))
        for item in sa_meta_posts:
            if not item:
                continue
            url = item.get("url")
            if not url or url in seen_urls:
                continue

            job_info = job_stats_by_url.get(url) or {}
            quality = job_info.get("quality") or ""

            seen_urls.add(url)
            rows.append(
                {
                    "source": "SA Essays",
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "url": url,
                    "source_url": item.get("source_url") or url,
                    "type": item.get("type", "Essay").title(),
                    "status": "done" if item.get("status") == "fetched" else item.get("status"),
                    "quality": quality,
                    "local_path": item.get("local_path"),
                    "reason": item.get("reason"),
                }
            )

        # 4. Process Extraction DB (YC Library)
        lib_meta_posts = _load_metadata_posts(str(self.metadata_dir))
        lib_meta_map = {p.get("url"): p for p in lib_meta_posts if p and p.get("url")}

        try:
            for job in ex_db.get_all_jobs():
                if not job:
                    continue
                url = job.get("url")
                if not url or url in seen_urls:
                    continue

                # Default source is YC Library unless it's a Startup School domain
                source = "YC Library"
                if "startupschool.org" in url:
                    source = "Startup School"

                job_id = job.get("id") or job.get("job_id")
                status = job.get("status")
                quality = job.get("quality") or ""
                meta = lib_meta_map.get(url)

                # Find local path
                local_path = ""
                if status == "done":
                    # Use filename from metadata if available, otherwise job_id
                    filename = (meta.get("file") or f"{job_id}.md") if meta else f"{job_id}.md"
                    p = self.content_dir / filename
                    if p.exists():
                        local_path = str(p)

                seen_urls.add(url)
                rows.append(
                    {
                        "source": source,
                        "id": job_id,
                        "title": meta.get("title") if meta else job_id,
                        "url": url,
                        "source_url": (
                            (meta.get("media_url") or meta.get("source_url") or url)
                            if meta
                            else url
                        ),
                        "type": (
                            meta.get("type")
                            if meta
                            else (
                                None or meta.get("source_type")
                                if meta
                                else None or job.get("source_type", "article") or "article"
                            )
                        ).title(),
                        "status": status,
                        "quality": quality,
                        "local_path": local_path,
                        "reason": job.get("error_msg", ""),
                    }
                )
        except Exception as e:
            self._log(f"Warning: failed to parse Extraction DB: {e}")
        # 5. Write Unified CSV
        self._write_csv(
            UNIFIED_AUDIT_CSV,
            rows,
            [
                "source",
                "id",
                "title",
                "url",
                "source_url",
                "type",
                "status",
                "quality",
                "local_path",
                "reason",
            ],
        )
        self._log(f"wrote unified audit to {UNIFIED_AUDIT_CSV}")
        return str(UNIFIED_AUDIT_CSV)

    def _write_csv(self, path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in fieldnames})


def main():
    """Run the pipeline CLI."""
    import sys

    parser = argparse.ArgumentParser(description="Run YC Library pipeline stages")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Common arguments
    def add_common_args(p):
        p.add_argument("--metadata-dir", default=DEFAULT_METADATA_DIR)
        p.add_argument("--output-dir", default=DEFAULT_CONTENT_DIR)
        p.add_argument("--workers", type=int, default=4)
        p.add_argument("--algolia-app-id")
        p.add_argument("--algolia-api-key")
        p.add_argument("--algolia-index", default="library_posts")

    # 'run' command (default)
    run_parser = subparsers.add_parser("run", help="Run pipeline discovery and extraction")
    add_common_args(run_parser)
    run_parser.add_argument("--mode", choices=["weekly", "dev"], default="weekly")
    run_parser.add_argument("--start-stage", choices=list(STAGE_ORDER), default="discover")
    run_parser.add_argument(
        "--replay", action="store_true", help="Reprocess all items regardless of pipeline state"
    )
    run_parser.add_argument("--force", action="store_true", help="Force reprocessing")
    run_parser.add_argument("--limit", type=int, help="Limit number of metadata files processed")
    run_parser.add_argument("--retry-failed-only", action="store_true")

    # 'full' command (extract all sources)
    full_parser = subparsers.add_parser(
        "full", help="Extract all sources (PG essays, SA essays, YC Library)"
    )
    add_common_args(full_parser)
    full_parser.add_argument("--force", action="store_true", help="Force reprocessing")
    full_parser.add_argument(
        "--replay", action="store_true", help="Reprocess all items regardless of pipeline state"
    )

    # For backward compatibility: if first arg looks like a flag (starts with --),
    # inject 'run' as the implicit command
    args_to_parse = sys.argv[1:]
    if args_to_parse and args_to_parse[0].startswith("--"):
        args_to_parse = ["run"] + args_to_parse
    elif not args_to_parse:
        # If no args provided, default to 'run'
        args_to_parse = ["run"]

    args = parser.parse_args(args_to_parse)

    # Set defaults for common args if missing
    if not hasattr(args, "metadata_dir"):
        args.metadata_dir = DEFAULT_METADATA_DIR
    if not hasattr(args, "output_dir"):
        args.output_dir = DEFAULT_CONTENT_DIR
    if not hasattr(args, "workers"):
        args.workers = 4

    # Default to 'run' if no command specified
    if not args.command:
        args.command = "run"
        # Set defaults for 'run' command
        if not hasattr(args, "mode"):
            args.mode = "weekly"
        if not hasattr(args, "start_stage"):
            args.start_stage = "discover"
        if not hasattr(args, "replay"):
            args.replay = False
        if not hasattr(args, "force"):
            args.force = False
        if not hasattr(args, "limit"):
            args.limit = None
        if not hasattr(args, "retry_failed_only"):
            args.retry_failed_only = False

    orchestrator = PipelineOrchestrator(
        metadata_dir=args.metadata_dir,
        content_dir=args.output_dir,
        workers=args.workers,
        algolia_app_id=args.algolia_app_id,
        algolia_api_key=args.algolia_api_key,
        algolia_index=args.algolia_index,
    )

    if args.command == "run":
        result = orchestrator.run(
            start_stage=args.start_stage,
            mode=args.mode,
            replay=args.replay,
            force=args.force,
            limit=args.limit,
            retry_failed_only=args.retry_failed_only,
        )
        print(
            "Pipeline complete: "
            f"{result.get('discovered', 0)} discovered, "
            f"{result.get('extracted', 0)} extracted, "
            f"{result.get('excluded_audit', 0)} excluded items"
        )
    elif args.command == "full":
        result = orchestrator.run_startup_school(
            replay=args.replay,
            force=args.force,
        )
        print(
            "Full extraction complete: "
            f"PG essays: {result.get('pg_fetched', 0)} fetched, {result.get('pg_failed', 0)} failed | "
            f"SA essays: {result.get('sa_fetched', 0)} fetched, {result.get('sa_failed', 0)} failed | "
            f"YC: {result.get('discovered', 0)} discovered, {result.get('extracted', 0)} extracted"
        )


if __name__ == "__main__":
    main()
