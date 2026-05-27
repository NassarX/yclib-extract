# yclib-extract

A reproducible, installable toolkit to discover and extract content from the Y Combinator Library (articles, videos, podcasts). This is a skeleton project—it provides discovery, extraction, and auditing tooling without including downloaded or copyrighted content.

## What It Does

- **Discover** YC Library posts via Algolia (public data, no account needed)
- **Extract** rendered HTML and convert to clean Markdown with preserved formatting
- **Recover** video transcripts via a resilient fallback chain
- **Track** extraction status and resumable runs with SQLite + JSON audits
- **Configure** via simple env vars and an interactive setup command

## Installation

### Requirements
- Python 3.9+
- Any OS (Windows, Mac, Linux)

### Quick Install
```bash
pip install yclib-extract
yclib-extract init          # Interactive first-run setup
```

The `init` command will:
1. Create a `.env` file with defaults
2. Offer setup options for Algolia credentials (hardcoded fallback, manual, or AI agent)
3. Ask if you want transcript support (optional extra)

### Install with Optional Features
```bash
# Core only (no video transcripts)
pip install yclib-extract

# Core + transcript support
pip install "yclib-extract[transcripts]"

# Core + full transcript support (youtube-transcript-api + yt-dlp)
pip install "yclib-extract[transcripts-full]"
```

## Quick Start

### 1. Initialize (One Time)
```bash
yclib-extract init
```

Follow the prompts to set up credentials and preferences. A `.env` file will be created in your current directory.

### 2. Discover Metadata
```bash
yclib-extract discover
```

This fetches metadata for all YC Library posts and saves them to `artifacts/yc_library_metadata.json`. Output:
- Consolidated metadata for all posts in a single JSON file
- minimal metadata: title, URL, author, type (Article/Video/Podcast/External)
- `file` field points to the final Markdown filename

### 3. Extract Content
```bash
yclib-extract extract
```

Processes each post from metadata and produces:
- `artifacts/yc_library/<slug>.md` — Markdown with rich frontmatter (title, url, type, author, summary, timestamps, media URLs, word count)
- Progress printed to console
- Status tracked in `artifacts/extraction_jobs.db`

### 4. Check Results
```bash
ls artifacts/yc_library/              # Extracted Markdown files
cat artifacts/yc_library_metadata.json # Metadata JSON
cat scrape_runs/yc_content_runs_*.json # Daily audit manifests
```

## Configuration

All configuration is via environment variables (set in `.env` or system env):

### Algolia Credentials
By default, **yclib-extract uses hardcoded Algolia credentials** that are already public and read-only. You do **not** need to do anything for discovery to work.

If credentials change, you can override:
```bash
ALGOLIA_APP_ID=your_app_id
ALGOLIA_API_KEY=your_api_key
```

#### Getting Credentials Manually
1. Open https://www.ycombinator.com/library/search in your browser
2. Open DevTools (F12) → Network tab → filter by "algolia"
3. Click any search request → Headers tab
4. Copy:
   - `X-Algolia-Application-Id` → set as `ALGOLIA_APP_ID`
   - `X-Algolia-API-Key` → set as `ALGOLIA_API_KEY`
5. Restart yclib-extract

#### Using AI Agent to Auto-Capture
If you prefer, use this prompt with Claude / GitHub Copilot CLI:

```
I need you to use Playwright to open https://www.ycombinator.com/library/search,
capture the Algolia credentials from the Network tab, and save them to my .env file.

Steps:
1. Open the page with Playwright
2. Intercept network requests and find the Algolia request
3. Extract the X-Algolia-Application-Id and X-Algolia-API-Key headers
4. Write to .env in the current directory:
   ALGOLIA_APP_ID=<value>
   ALGOLIA_API_KEY=<value>

The .env file should be created in /path/to/yclib-extract/ (or current working directory).
```

### Content & Extraction
```bash
# Minimum characters for successful extraction (default: 700)
YCLIB_EXTRACT_MIN_CONTENT_LENGTH=700

# Fallback Invidious instances for YouTube transcript blocks
INVIDIOUS_INSTANCES=yewtu.cafe,invidio.us
```

### Transcript Fallback Chain
If you installed `[transcripts]` or `[transcripts-full]`, transcripts are recovered via:
1. **On-page transcript** (fastest)
2. **YouTube API** (if `youtube-transcript-api` installed)
3. **yt-dlp captions** (if `yt-dlp` installed; requires ffmpeg)
4. **YouTube watch page** (always available, lowest coverage)

Videos without publicly available transcripts are marked as `status: missing` in the database.

## Command Reference

### Main Commands

**`yclib-extract init`** — Interactive first-run setup
```bash
yclib-extract init
```

**`yclib-extract discover`** — Fetch all YC Library metadata
```bash
yclib-extract discover
yclib-extract discover --limit 50      # Process only first 50
```

**`yclib-extract extract`** — Extract metadata into Markdown
```bash
yclib-extract extract                            # All pending posts
yclib-extract extract --force                    # Re-extract done posts
yclib-extract extract --retry-failed-only        # Only retry failed/error/short
yclib-extract extract --workers 8                # Use 8 threads
yclib-extract extract --limit 100                # Process max 100
```

**`yclib-extract pipeline`** — Full orchestrated pipeline
```bash
# Run all three stages (discover → extract → audit)
yclib-extract pipeline --start-stage discover

# Start from extraction (skip discovery)
yclib-extract pipeline --start-stage extract --mode dev

# Modes: 'weekly' (incremental, normal), 'dev' (replay-friendly, force-like)

# Startup School workflow:
# pg essays fetch -> yc discover -> curriculum inject -> extract -> curriculum build
yclib-extract pipeline --workflow startup_school --mode weekly
```

### Advanced / Internal Commands
```bash
# Inspect job database
yclib-extract audit --report-by-status          # Summary by status
yclib-extract audit --list-errors               # Show all errors

# Manual transcript testing
yclib-get-transcript https://www.youtube.com/watch?v=VIDEO_ID
```

## Outputs

### Metadata JSON (`artifacts/yc_library_metadata.json`)
```json
{
  "posts": [
    {
      "id": "startup_library_123",
      "url": "https://www.ycombinator.com/library/abc-post",
      "media_url": "https://youtu.be/ABC123",
      "title": "Post Title",
      "author": "Author Name",
      "type": "Video",
      "source_type": "Video",
      "description": "Post summary",
      "date": "2024-01-15",
      "file": "post-title.md"
    }
  ]
}
```

### Markdown File (`artifacts/yc_library/<slug>.md`)
```markdown
---
title: "Post Title"
url: "https://www.ycombinator.com/library/abc-post"
type: "Video"
author: "Author Name"
summary: "Post summary"
published_at: "2024-01-15"
exported_at: "2024-05-25T15:00:00"
source_url: "https://youtu.be/ABC123"
video_url: "https://youtu.be/ABC123"
file: "post-title.md"
word_count: 1250
---

# Post Title

[Body content in clean Markdown...]

## Transcript

[Video transcript if available...]
```

### Extraction Database (`artifacts/extraction_jobs.db`)
SQLite table tracks every post:
- `id` — post slug
- `status` — `pending`, `done`, `short`, `failed`, `error`, `missing`, `removed`
- `attempt_count` — number of attempts
- `content_length` — bytes extracted
- `error_msg` — last error (if any)
- `extracted_at` — timestamp of successful extraction

Query examples:
```bash
sqlite3 artifacts/extraction_jobs.db "SELECT status, COUNT(*) FROM extraction_jobs GROUP BY status;"
sqlite3 artifacts/extraction_jobs.db "SELECT id, error_msg FROM extraction_jobs WHERE status = 'error';"
```

### Daily Audit Manifest (`scrape_runs/yc_content_runs_YYYYMMDD.json`)
```json
{
  "runs": [
    {
      "stage": "discover",
      "generated_at": "2024-05-25T15:00:00",
      "total_discovered": 423,
      "total_files": 423
    },
    {
      "stage": "extract",
      "generated_at": "2024-05-25T15:10:00",
      "total_files": 423,
      "done": 350,
      "short": 30,
      "missing": 40,
      "error": 3,
      "by_source_type": {
        "Article": {"done": 150, "short": 5, "error": 0},
        "Video": {"done": 150, "short": 20, "error": 3},
        "Podcast": {"done": 50, "short": 5, "error": 0}
      },
      "workers": 4,
      "force": false,
      "limit": null
    }
  ]
}
```

### PG Essays Fetch Audit (`artifacts/pg_essays_audit.json`)

- Generated by `yclib-extract pipeline --workflow startup_school`
- Tracks fetch status for each URL from `https://paulgraham.com/articles.html`
- Status values: `fetched`, `skipped_existing`, `failed`
- In weekly mode, existing files are append-only (skipped by default)

### Sam Altman Essays Fetch Audit (`artifacts/altman_essays_audit.json`)

- Generated by `python scripts/fetch_altman_essays.py`
- Tracks fetch status for each essay from `https://blog.samaltman.com`
- Status values: `fetched`, `skipped_existing`, `failed`
- In append-only mode, existing files are skipped by default

### Excluded Items Audit (`artifacts/yc_library_audit.csv`)

- Generated after extraction completes
- Consolidates items marked as `short` (below minimum content length) and `removed` (missing media and content)
- Columns: id, source_type, title, url, media_url, final_words, body_words, status, warning/reason

## Troubleshooting

### "No content found" or "Content too short"
**Status:** `short` or `failed`
**Reason:** Page HTML doesn't contain enough extractable text (< 2000 chars by default)
**Solution:**
- Increase `YCLIB_EXTRACT_MIN_CONTENT_LENGTH` in `.env`
- Manually review the post at the `url` field to confirm content exists
- Some posts may be link aggregators or short intros (expected)

### Video transcripts not extracted
**Status:** `missing` or transcript section empty
**Reason:** Video has no public captions, or YouTube is blocking requests
**Solutions:**
1. Install transcript support: `pip install "yclib-extract[transcripts]"`
2. Set up proxy via `INVIDIOUS_INSTANCES` env var
3. Manually add transcript to the Markdown file

### "RequestBlocked" errors
**Reason:** YouTube rate-limiting or geo-blocking
**Solutions:**
- Wait a few hours and retry: `yclib-extract extract --retry-failed-only`
- Use Invidious fallback: set `INVIDIOUS_INSTANCES` and reinstall with `[transcripts-full]`
- Reduce `--workers` to slow down requests

### "Algolia request failed"
**Reason:** Credentials are invalid or network is down
**Solutions:**
1. Check your `.env` file for typos
2. Manually grab new credentials from DevTools (see Configuration section)
3. Use the AI agent prompt to auto-capture

### Database locked errors
**Reason:** Multiple processes writing to `extraction_jobs.db` simultaneously
**Solution:** Run extraction with only one process (`--workers 1`) or ensure no other instance is running

## Advanced Usage

### Resume Failed Jobs
```bash
# Retry only jobs marked failed/error/short
yclib-extract extract --retry-failed-only

# Force re-extract everything (slow, overwrites done jobs)
yclib-extract extract --force
```

### Skip Specific Sources
Create or edit `config/ignore_sources.json`:
```json
[
  "example.com",
  "https://example.com/specific-page",
  "author-name"
]
```

The extractor skips any job whose URL, ID, title, or author matches a substring in this list.

### Customize Min Content Length
```bash
# In .env
YCLIB_EXTRACT_MIN_CONTENT_LENGTH=1000

# Or via env var
export YCLIB_EXTRACT_MIN_CONTENT_LENGTH=1000
yclib-extract extract
```

### Proxy Configuration
The package supports two types of proxy settings:

1. **YouTube Transcript Settings** — For handling YouTube rate-limiting and transcripts
   - `INVIDIOUS_INSTANCES` — Free YouTube mirrors (fallback when rate-limited)
   - `YOUTUBE_PROXY_URL` — Route YouTube requests through a corporate proxy

2. **General Proxy Settings** — For all HTTP/HTTPS traffic (behind firewall)
   - `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` — Route all traffic through corporate gateway

**For quick setup behind a firewall:**
```bash
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080
export ALL_PROXY=http://proxy.company.com:8080
yclib-extract extract
```

**For YouTube transcript rate-limiting:**
```bash
export INVIDIOUS_INSTANCES=yewtu.cafe,invidio.us,inv.riverside.rocks
yclib-extract extract --retry-failed-only
```

**See [docs/PROXY_SETTINGS.md](docs/PROXY_SETTINGS.md) for detailed explanations, real-world scenarios, and troubleshooting.**

### From-Scratch Rebuild
If you need a clean slate:
```bash
rm -rf artifacts/yc_library artifacts/yc_library_metadata.json artifacts/extraction_jobs.db
rm scrape_runs/yc_content_runs_*.json

# Then re-run discovery and extraction
yclib-extract discover
yclib-extract extract
```

## Contributing

1. Fork the repository
2. Create a branch: `git checkout -b my-feature`
3. Make changes and test: `pytest tests/`
4. Commit with conventional message: `git commit -m "feat: add X"`
5. Push and open a PR

### Local Development
```bash
git clone <repo>
cd yclib-extract
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,yaml,transcripts-full]"

# Run tests
pytest tests/ -v

# Lint
black src/ tests/
isort src/ tests/
flake8 src/ tests/ --max-line-length=100

# Type check
mypy src/ --ignore-missing-imports
```

## Project Structure

```
yclib-extract/
├── src/yclib_extract/
│   ├── cli.py                 # CLI entry point
│   ├── scraper.py             # Algolia discovery
│   ├── extractor.py           # HTML → Markdown conversion
│   ├── pipeline.py            # Orchestrated pipeline
│   └── lib/
│       ├── html_cleaning.py   # HTML parsing + cleanup
│       └── youtube_transcripts.py  # Transcript fallback chain
├── tests/                      # Unit tests
├── docs/                       # Detailed guides (legacy, see README)
├── artifacts/                  # Output (gitignored)
│   ├── yc_library/            # Extracted Markdown
│   ├── yc_library_metadata.json   # Metadata JSON (single file)
│   ├── yc_library_audit.csv   # Audit report (short + removed items)
│   └── extraction_jobs.db     # Status database
├── config/
│   └── ignore_sources.json    # Skip list
├── scrape_runs/               # Daily audit manifests (gitignored)
├── .env.example               # Template
├── pyproject.toml             # Package config
└── README.md                  # This file
```

## License

MIT. See LICENSE file.

## Maintainer

Mahmoud Nassar

## Feedback

Found a bug? Have a feature request? Open an issue or PR on GitHub.

---

**Ready to get started?** Run `pip install yclib-extract && yclib-extract init` now.

## Curriculum Guide

This repository includes a script to build the Startup School curriculum guide from the YAML config at config/startup_school_curriculum.yaml.

Usage:
  - Update config/startup_school_curriculum.yaml to point local files (if available).
  - Run: python3 scripts/build_curriculum.py to generate artifacts/yc_startup_school/startup_school_curriculum.md.
  - Use --collect (and optionally --yc-dir) to collect curriculum markdown into artifacts/yc_startup_school/.

Contact
-------
For follow-up or changes, update this document or the curriculum YAML in config/startup_school_curriculum.yaml.

## Startup School curriculum: build changes

The `scripts/build_curriculum.py` script was simplified. Notable changes:

- Extractor worker and force options removed from the CLI. Control via environment variables instead:
  - `YCLIB_EXTRACTOR_WORKERS` (default: 2)
  - `YCLIB_ENSURE_FORCE` (set to `1`/`true` to pass --force to the extractor)
- New flags: `--ensure-local` (generate missing metadata + run extractor), `--inject-only` (write metadata JSONs only and exit), `--inject-metadata-dir` (override metadata dir for injection), `--collect` (copy referenced markdown into artifacts/<yc-dir>).
- Collection now always copies and overwrites files to reduce flags and keep the CLI minimal.

Usage examples:

- Ensure local and run extractor (env-driven):

  YCLIB_EXTRACTOR_WORKERS=4 YCLIB_ENSURE_FORCE=1 python scripts/build_curriculum.py --ensure-local

- Inject metadata only (no extractor):

  python scripts/build_curriculum.py --inject-only

- Build and collect into artifacts:

  python scripts/build_curriculum.py --collect

---

## Essays & Resources

### Paul Graham Essays

Fetch essays from https://paulgraham.com/articles.html:

```bash
# Append-only (default): skip existing essays
python scripts/fetch_pg_essays.py

# Force refresh: re-fetch all essays
python scripts/fetch_pg_essays.py --force

# Custom output directory
python scripts/fetch_pg_essays.py --output-dir /custom/path
```

**Output**: `artifacts/pg_essays/` (Markdown files + audit JSON)

### Sam Altman Essays

Fetch essays from https://blog.samaltman.com/archive:

```bash
# Append-only (default): skip existing essays
python scripts/fetch_sam_altman_essays.py

# Force refresh: re-fetch all essays
python scripts/fetch_sam_altman_essays.py --force

# Custom output directory
python scripts/fetch_sam_altman_essays.py --output-dir /custom/path
```

**Output**: `artifacts/sam_altman_essays/` (Markdown files + audit JSON)

**Current Status**: ✅ 30 essays fetched and available

### Integrated Workflow

Both essay collections are part of the startup school workflow:

```bash
yclib-extract pipeline --startup-school
```

This runs:
1. Fetch Paul Graham essays (append-only)
2. Fetch Sam Altman essays (append-only)
3. Discover YC Library posts
4. Build Startup School curriculum
5. Extract and convert all resources
6. Generate final markdown guides

---

## Feature Planning & Roadmap

Future features are documented in `/docs/features/`. See `/docs/features/README.md` for the planning index and design decisions for implemented features.
