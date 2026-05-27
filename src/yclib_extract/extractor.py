import json
import sqlite3
import contextlib
import re
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from bs4 import BeautifulSoup

from .lib.html_cleaning import extract_main_content, html_to_markdown
from .lib.youtube_transcripts import extract_podcast_url, extract_youtube_url, get_transcript
from .scraper import is_ignored, load_ignore_sources

ARTIFACTS_DIR = Path("artifacts").resolve()
DEFAULT_DB_PATH = str(ARTIFACTS_DIR / "extraction_jobs.db")
DEFAULT_CONTENT_DIR = str(ARTIFACTS_DIR / "yc_library")
DEFAULT_METADATA_DIR = str(ARTIFACTS_DIR / "yc_library_metadata.json")
RETRYABLE_STATUSES = {"failed", "error", "short"}
REMOVED_WORD_THRESHOLD = 200

FRONTMATTER_FIELDS = (
    "title",
    "url",
    "type",
    "author",
    "summary",
    "published_at",
    "exported_at",
    "source_url",
    "file",
    "video_url",
    "podcast_url",
    "word_count",
)


@dataclass
class ExtractionResult:
    content: str
    video_url: Optional[str] = None
    podcast_url: Optional[str] = None
    source_type: Optional[str] = None


class ExtractionDB:
    """SQLite tracking for extraction jobs."""

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
        """Initialize tracking table."""
        db_parent = Path(self.db_path).parent
        if str(db_parent) not in ("", "."):
            db_parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS extraction_jobs (
                    id TEXT PRIMARY KEY,
                    file_path TEXT,
                    url TEXT,
                    source_type TEXT,
                    status TEXT DEFAULT 'pending',
                    quality TEXT,
                    attempt_count INTEGER DEFAULT 0,
                    last_attempt TEXT,
                    error_msg TEXT,
                    content_length INTEGER,
                    extracted_at TEXT
                )
                """)
            conn.commit()

    def register_job(self, job_id: str, file_path: str, url: str, source_type: str):
        """Register a new extraction job."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO extraction_jobs
                (id, file_path, url, source_type, status, attempt_count)
                VALUES (?, ?, ?, ?, 'pending', 0)
                """,
                (job_id, file_path, url, source_type),
            )
            conn.execute(
                """
                UPDATE extraction_jobs
                SET file_path = ?, url = ?, source_type = ?
                WHERE id = ?
                """,
                (file_path, url, source_type, job_id),
            )
            conn.commit()

    def update_job_status(
        self,
        job_id: str,
        status: str,
        content_length: Optional[int] = None,
        error_msg: str = "",
        source_type: Optional[str] = None,
        quality: Optional[str] = None,
    ):
        """Update job status and metadata."""
        with self._connect() as conn:
            if source_type is not None:
                conn.execute(
                    """
                    UPDATE extraction_jobs
                    SET source_type = ?
                    WHERE id = ?
                    """,
                    (source_type, job_id),
                )

            if quality is not None:
                conn.execute(
                    """
                    UPDATE extraction_jobs
                    SET quality = ?
                    WHERE id = ?
                    """,
                    (quality, job_id),
                )

            conn.execute(
                """
                UPDATE extraction_jobs
                SET status = ?, attempt_count = attempt_count + 1,
                    last_attempt = ?, error_msg = ?,
                    content_length = ?, extracted_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    datetime.now().isoformat(),
                    error_msg,
                    content_length,
                    datetime.now().isoformat() if status == "done" else None,
                    job_id,
                ),
            )
            conn.commit()

    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get job status."""
        with self._connect() as conn:
            cursor = conn.execute("SELECT * FROM extraction_jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if row:
                cols = [description[0] for description in cursor.description]
                return dict(zip(cols, row))
        return None

    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """Retrieve all extraction jobs."""
        with self._connect() as conn:
            cursor = conn.execute("SELECT * FROM extraction_jobs ORDER BY last_attempt DESC")
            rows = cursor.fetchall()
            cols = [description[0] for description in cursor.description]
            return [dict(zip(cols, r)) for r in rows]


class ContentExtractor:
    """Extract and convert YC Library content to Markdown."""

    def __init__(self, output_dir: str = DEFAULT_CONTENT_DIR, min_content_length: int = 700):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.min_content_length = min_content_length
        self.db = ExtractionDB()

    @staticmethod
    def _canonical_source_type(source_type: str) -> str:
        normalized = (source_type or "article").strip().lower()
        mapping = {
            "video": "Video",
            "podcast": "Podcast",
            "external": "External",
            "article": "Article",
        }
        return mapping.get(normalized, source_type.strip() if source_type else "Article")

    def extract_content(
        self,
        url: str,
        job_id: str,
        source_type: str = "article",
        media_url_hint: Optional[str] = None,
    ) -> Optional[ExtractionResult]:
        """Fetch and extract page content."""
        try:
            # Register job
            self.db.register_job(job_id, "", url, source_type)

            # Fetch page
            response = requests.get(url, timeout=15)
            response.raise_for_status()

            html = response.text
            soup = BeautifulSoup(response.content, "html.parser")

            # Extract main content
            content_html = extract_main_content(soup)
            if not content_html:
                # If we have a media hint, we might still be able to save it
                if media_url_hint:
                    content_html = f"<p>External media resource.</p>"
                else:
                    self.db.update_job_status(job_id, "failed", error_msg="No content found")
                    return None

            # Convert to Markdown
            markdown = html_to_markdown(content_html, base_url=url)
            normalized_source_type = (source_type or "article").strip().lower()
            is_video = normalized_source_type == "video"

            video_url = extract_youtube_url(html)
            if not video_url and is_video:
                if media_url_hint and (
                    "youtube.com" in media_url_hint or "youtu.be" in media_url_hint
                ):
                    video_url = media_url_hint

            podcast_url = extract_podcast_url(html)
            if not podcast_url and not is_video:
                if media_url_hint and "spotify.com" in media_url_hint:
                    podcast_url = media_url_hint

            if podcast_url and not is_video:
                normalized_source_type = "podcast"
            canonical_source_type = self._canonical_source_type(normalized_source_type)

            quality = None
            if is_video and (len(markdown) < self.min_content_length or not content_html):
                if video_url:
                    transcript = get_transcript(video_url)
                    if transcript:
                        markdown = f"{markdown}\n\n## Transcript\n\n{transcript}"
                    else:
                        quality = "missing-transcript"

            title = soup.find("h1")
            title_text = title.get_text(" ", strip=True) if title else ""
            final_word_count = self._count_words(f"{title_text}\n{markdown}")

            # Check minimum length
            if normalized_source_type in {"external"}:
                status = "done"
            elif is_video and video_url:
                # If it's a video and we have the URL, we keep it even if short (metadata is valuable)
                status = "done"
            elif normalized_source_type == "podcast" and podcast_url:
                status = "done"
            elif is_video and not video_url and final_word_count < REMOVED_WORD_THRESHOLD:
                status = "removed"
            elif (
                normalized_source_type == "podcast"
                and not podcast_url
                and final_word_count < REMOVED_WORD_THRESHOLD
            ):
                status = "removed"
            elif len(markdown) < self.min_content_length:
                status = "short"
            else:
                status = "done"

            if status == "removed":
                self.db.update_job_status(
                    job_id,
                    status,
                    len(markdown),
                    "Extracted body appears removed or unavailable",
                    canonical_source_type,
                    quality=quality,
                )
                return None

            if status == "short":
                self.db.update_job_status(
                    job_id,
                    "short",
                    len(markdown),
                    "Content too short",
                    canonical_source_type,
                    quality=quality,
                )
                return None

            self.db.update_job_status(
                job_id, "done", len(markdown), source_type=canonical_source_type, quality=quality
            )
            return ExtractionResult(
                content=markdown,
                video_url=video_url,
                podcast_url=podcast_url,
                source_type=canonical_source_type,
            )

        except Exception as e:
            self.db.update_job_status(job_id, "error", error_msg=str(e))
            return None

    def _format_frontmatter(self, metadata: Dict[str, Any]) -> str:
        lines = ["---"]
        for field in FRONTMATTER_FIELDS:
            value = metadata.get(field)
            if value in (None, "", [], {}):
                continue
            lines.append(f"{field}: {json.dumps(value)}")
        lines.append("---")
        return "\n".join(lines)

    @staticmethod
    def _count_words(text: str) -> int:
        return len(re.findall(r"\b\w+\b", text))

    def save_markdown(
        self,
        job_id: str,
        content: str,
        metadata: Dict[str, Any],
        video_url: str = "",
        podcast_url: str = "",
        source_type: str = "",
    ):
        """Save extracted content as Markdown."""
        filename = metadata.get("file") or f"{job_id}.md"
        filepath = self.output_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w") as f:
            frontmatter = dict(metadata)
            frontmatter["type"] = self._canonical_source_type(
                source_type or frontmatter.get("source_type") or frontmatter.get("type", "")
            )
            if video_url:
                frontmatter["video_url"] = video_url
            if podcast_url:
                frontmatter["podcast_url"] = podcast_url
            frontmatter["source_url"] = (
                video_url
                or podcast_url
                or frontmatter.get("media_url")
                or frontmatter.get("url")
                or ""
            )
            if "description" in frontmatter and not frontmatter.get("summary"):
                frontmatter["summary"] = frontmatter["description"]
            if "date" in frontmatter and not frontmatter.get("published_at"):
                frontmatter["published_at"] = frontmatter["date"]
            frontmatter["exported_at"] = datetime.now().isoformat()
            frontmatter["file"] = frontmatter.get("file") or filename

            body = content.strip()
            title = metadata.get("title")
            title_heading = f"# {title}" if title else ""
            if title_heading and body.startswith(title_heading):
                body = body[len(title_heading) :].lstrip()

            frontmatter["word_count"] = self._count_words(f"{title or ''}\n{body}")

            f.write(self._format_frontmatter(frontmatter))
            f.write("\n\n")

            f.write(body)

        return str(filepath)

    def process_posts(
        self,
        input_dir: str,
        workers: int = 4,
        force: bool = False,
        retry_failed_only: bool = False,
    ):
        """Process all posts in input directory or consolidated JSON file."""
        if force and retry_failed_only:
            raise ValueError("--force and --retry-failed-only cannot be used together")

        input_path = Path(input_dir)
        posts_data = []

        if input_path.is_file() and input_path.suffix == ".json":
            # Support consolidated JSON file
            try:
                with open(input_path, "r") as f:
                    data = json.load(f)
                    posts = data.get("posts", data) if isinstance(data, dict) else data
                    for p in posts:
                        posts_data.append((p.get("id") or _slugify(p.get("title", "post")), p))
            except Exception as e:
                print(f"Error loading consolidated metadata: {e}")
                return
        else:
            # Traditional directory of JSON files
            files = sorted(input_path.glob("*.json"))
            for post_file in files:
                try:
                    with open(post_file) as f:
                        posts_data.append((post_file.stem, json.load(f)))
                except Exception as e:
                    print(f"Error loading {post_file}: {e}")

        ignore_sources = load_ignore_sources()
        mode = "retry failed only" if retry_failed_only else "all eligible"
        print(f"Processing {len(posts_data)} posts with {workers} workers ({mode})...")

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {}

            for job_id, post in posts_data:
                url = post.get("url")
                title = post.get("title", "")
                source_type = self._canonical_source_type(
                    post.get("source_type") or post.get("type") or "article"
                )
                post_source = f"{url} {post.get('media_url', '')} {job_id} {title} {source_type}"

                if not url:
                    continue

                if is_ignored(post_source, ignore_sources):
                    continue

                # Check if already done
                status = self.db.get_job_status(job_id)
                status_value = status["status"] if status else None
                if retry_failed_only and status_value not in RETRYABLE_STATUSES:
                    continue
                if status_value == "done" and not force:
                    continue

                future = executor.submit(
                    self.extract_content,
                    url,
                    job_id,
                    source_type,
                    media_url_hint=post.get("media_url"),
                )
                futures[future] = (job_id, title, url, post)

            for future in as_completed(futures):
                job_id, title, url, post = futures[future]
                try:
                    result = future.result()
                    if result:
                        self.save_markdown(
                            job_id,
                            result.content,
                            post,
                            result.video_url or "",
                            result.podcast_url or "",
                            result.source_type or "",
                        )
                        print(f"✓ {job_id}")
                    else:
                        print(f"✗ {job_id} (no content or too short)")
                except Exception as e:
                    print(f"✗ {job_id}: {e}")


def main():
    """CLI entry point for extraction."""
    import argparse

    parser = argparse.ArgumentParser(description="Extract YC Library content")
    parser.add_argument("--input-dir", default=DEFAULT_METADATA_DIR, help="Input directory")
    parser.add_argument("--output-dir", default=DEFAULT_CONTENT_DIR, help="Output directory")
    parser.add_argument("--workers", type=int, default=4, help="Number of workers")
    parser.add_argument("--force", action="store_true", help="Re-extract everything")
    parser.add_argument(
        "--retry-failed-only",
        action="store_true",
        help="Retry only DB jobs currently marked failed/error/short",
    )
    parser.add_argument("--audit-only", action="store_true", help="Dry-run, report status")

    args = parser.parse_args()

    extractor = ContentExtractor(output_dir=args.output_dir)

    if args.audit_only:
        print("Audit mode: no changes")
        return

    extractor.process_posts(
        args.input_dir,
        workers=args.workers,
        force=args.force,
        retry_failed_only=args.retry_failed_only,
    )


if __name__ == "__main__":
    main()
