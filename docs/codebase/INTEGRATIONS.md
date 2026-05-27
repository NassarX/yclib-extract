# Integrations

## Core Sections (Required)

### 1) External APIs & Services

| Service | Purpose | Credentials | Fallback | Evidence |
|---------|---------|-------------|----------|----------|
| Algolia Search | YC Library discovery; queries `Library_bookface_production` index | App ID + API Key (hardcoded public key, no auth needed) | None; failure blocks discovery | `src/yclib_extract/scraper.py:44-50` |
| YouTube / Invidious | Video transcripts; YouTube API + Invidious mirrors | Optional API key; primarily uses Invidious mirrors | Fallback chain: API → yt-dlp → watch page parsing | `src/yclib_extract/lib/youtube_transcripts.py` |
| paulgraham.com | Paul Graham essay fetching via HTML scraping | None (public HTML) | None; HTTP errors logged | `src/yclib_extract/pipeline.py:52-59` |
| blog.samaltman.com | Sam Altman essay fetching via RSS + HTML scraping | None (public RSS + HTML) | None; HTTP errors logged | `src/yclib_extract/pipeline.py:60-67` |

### 2) Database Connections

| Database | Role | Location | Credentials | Evidence |
|----------|------|----------|-------------|----------|
| SQLite 3 | Job tracking & extraction status (local only) | `artifacts/extraction_jobs.db` | None (local file) | `src/yclib_extract/extractor.py:49-95` |

### 3) Credential Management

- **Algolia:** Hardcoded public/read-only keys in `Config.DEFAULT_ALGOLIA_*` constants; can be overridden via env vars or CLI args
- **YouTube transcripts:** No credentials required; uses public API or Invidious mirrors (which are also public)
- **`.env` file:** Simple key=value parser (not `python-dotenv`); no secret masking or encryption
- **Environment variables:** Read directly from `os.environ` via `Config` class
- **No secrets manager:** Credentials passed as plain text in `.env` or environment

### 4) Proxying & Network

- **HTTP/HTTPS proxies:** Configurable via `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` env vars
- **Requests library:** Respects standard proxy environment variables natively
- **SOCKS support:** `PySocks` package allows SOCKS proxy via requests
- **YouTube-specific proxies:** `YOUTUBE_PROXY_URL`, `YOUTUBE_HTTP_PROXY_URL`, `YOUTUBE_HTTPS_PROXY_URL` for YouTube requests
- **Invidious instances:** Comma-separated list (default: `yewtu.cafe,invidio.us`) used as fallback when YouTube is blocked

### 5) Monitoring & Observability

| Component | What is tracked | Storage | Evidence |
|-----------|-----------------|---------|----------|
| Job execution | Status, content length, error message, attempt count | SQLite `extraction_jobs` table | `src/yclib_extract/extractor.py:71-95` |
| Pipeline runs | Stage (discover/extract/audit), counts by status, source type breakdown | JSON files in `scrape_runs/` | `README.md:247-275` |
| Unified audit | Resource status + quality across all sources | `artifacts/resources_audit.csv` | `GEMINI.md:13-14` |
| No APM/logging service | No external observability tooling configured | Stdout + database | — |

### 6) Evidence

- `src/yclib_extract/scraper.py:44-50` — Algolia configuration
- `src/yclib_extract/lib/youtube_transcripts.py` — transcript recovery with fallback chain
- `src/yclib_extract/config.py:45-80` — credential and proxy handling
- `.env.example` — all configuration keys and their defaults
- `README.md:78-125, 368-391` — configuration and proxy setup docs
