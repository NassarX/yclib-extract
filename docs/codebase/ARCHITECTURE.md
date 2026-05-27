# Architecture

## Core Sections (Required)

### 1) Layering & Decomposition

| Layer | Modules | Responsibilities |
|-------|---------|------------------|
| CLI Entry | `cli.py`, `commands/init.py` | Argument parsing, command routing, user interaction |
| Discovery | `scraper.py` | Algolia API queries, metadata JSON persistence, source filtering |
| Extraction | `extractor.py` | HTML fetching, content extraction, job tracking, Markdown generation |
| Orchestration | `pipeline.py` | Multi-source coordination, metadata injection, audit CSV generation |
| Content Processing | `lib/html_cleaning.py`, `lib/youtube_transcripts.py` | DOM manipulation, text cleaning, transcript recovery |
| Configuration | `config.py` | Environment loading, .env parsing, default resolution |

### 2) Data Flow & Patterns

**Typical request flow:**

1. **User invokes:** `yclib-extract pipeline --workflow full`
2. **CLI router** (`cli.py:main()`) → parses args, loads Config
3. **Pipeline orchestrator** (`pipeline.py`) coordinates:
   - **Discover phase:** `AlgoliaScraper` fetches from Algolia, persists to `yc_library_metadata.json`
   - **Extract phase:** `ContentExtractor` reads metadata, fetches HTML, extracts via trafilatura, writes Markdown, updates `extraction_jobs.db`
   - **Audit phase:** Aggregates job status into `resources_audit.csv`
4. **Output:** Markdown files in `artifacts/yc_library/`, audit data in SQLite + CSV

**Key patterns:**

- **Metadata-driven:** JSON files (`artifacts/metadata/*.json`) are the source of truth; extraction resumes from metadata
- **Job tracking:** SQLite table prevents redundant work; status field (`pending`, `done`, `short`, `failed`, `error`, `missing`, `removed`)
- **Quality distinction:** Separate `status` (behavioral result) from `quality` (content completeness) for targeted retries
- **Fallback chain:** Transcript recovery tries: on-page → YouTube API → yt-dlp → watch page
- **Append-only weekly mode:** Existing files are skipped by default; `--force` or `--mode dev` allows replay

### 3) Concurrency & Async Patterns

- **Thread pool:** `concurrent.futures.ThreadPoolExecutor` for parallel extraction (configurable `--workers`, default 4)
- **No async/await:** All I/O is blocking with explicit thread management
- **SQLite safety:** Database connection pooling with 30s timeout; writes protected by SQLite's internal locking
- **No background workers:** All operations run synchronously in main thread or worker thread pool

### 4) Key Abstractions & Classes

| Class | Role | Key Methods |
|-------|------|-------------|
| `Config` | Configuration container with priority resolution | `__init__()`, property accessors |
| `AlgoliaScraper` | Algolia API client and metadata persistence | `discover()`, `fetch_page()` |
| `ContentExtractor` | HTML extraction and Markdown generation | `extract_all()`, `extract_one()`, `extract_content()` |
| `ExtractionDB` | SQLite job tracking | `init_db()`, `get_job()`, `update_job()`, `mark_done()` |
| `ExtractionResult` | Dataclass: extracted content + metadata | `content`, `video_url`, `podcast_url`, `source_type` |

### 5) Resilience & Error Handling

- **Retryable statuses:** `failed`, `error`, `short` can be retried via `--retry-failed-only`
- **Transcript fallback:** Missing transcripts mark as `quality: missing-transcript`, not fatal
- **Ignore list:** `config/ignore_sources.json` allows skipping specific URLs, authors, or domains
- **Logging:** Print-based progress tracking to stdout; errors logged to database `error_msg` field
- **Proxy support:** HTTP/HTTPS proxies configurable via env vars; Invidious instances for YouTube fallback

### 6) Evidence

- `src/yclib_extract/pipeline.py:74-189` — pipeline state and discovery flow
- `src/yclib_extract/extractor.py:200-350` (approx) — extraction orchestration
- `src/yclib_extract/lib/youtube_transcripts.py` — transcript recovery chain
- `README.md:10-11, 128-134` — design overview
- `GEMINI.md:9-14` — architecture overview
