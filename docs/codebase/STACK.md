# Technology Stack

## Core Sections (Required)

### 1) Runtime Summary

| Area | Value | Evidence |
|------|-------|----------|
| Primary language | Python | `pyproject.toml:6` |
| Runtime + version | Python 3.9+ (targets 3.9, 3.10, 3.11, 3.12) | `pyproject.toml:10, .github/workflows/ci.yml:14` |
| Package manager | pip with setuptools | `pyproject.toml:1-3` |
| Module/build system | setuptools with `setuptools.build_meta` | `pyproject.toml:1-3` |

### 2) Production Frameworks and Dependencies

| Dependency | Version | Role in system | Evidence |
|------------|---------|----------------|----------|
| requests | >=2.31.0 | HTTP client for Algolia discovery and content fetching | `pyproject.toml:24` |
| beautifulsoup4 | >=4.12.0 | HTML parsing and DOM traversal | `pyproject.toml:25` |
| trafilatura | >=1.6.0 | Primary HTML-to-Markdown content extraction engine | `pyproject.toml:26` |
| PySocks | >=1.7.1 | SOCKS proxy support for HTTP/HTTPS requests | `pyproject.toml:27` |
| sqlite3 | std lib | Local job tracking and extraction status database | `src/yclib_extract/extractor.py:8` |
| youtube-transcript-api | >=0.6.0 | YouTube transcript recovery (optional, `[transcripts]`) | `pyproject.toml:31` |
| yt-dlp | >=2023.12.0 | Fallback caption extraction via ffmpeg (optional, `[transcripts-full]`) | `pyproject.toml:32` |

### 3) Development Toolchain

| Tool | Purpose | Evidence |
|------|---------|----------|
| pytest | Test runner | `pyproject.toml:33, .github/workflows/ci.yml:26` |
| black | Code formatter (line-length: 100) | `pyproject.toml:33, 45-46` |
| isort | Import sorter (profile: black) | `pyproject.toml:33, 49-50` |
| flake8 | Linter | `pyproject.toml:33` |
| PyYAML | YAML parsing (optional, `[yaml]`) | `pyproject.toml:33, 239` |
| playwright | Browser automation for credential capture (optional, `[playwright]`) | `pyproject.toml:34, 240` |
| mypy | Type checker (available but not enforced) | Listed in development notes |

### 4) Key Commands

```bash
# Install
pip install -e .                           # Core only
pip install -e ".[dev,yaml,transcripts-full]"  # Full dev setup

# Test
pytest tests/ -v                           # Run all tests
pytest -q                                  # Quick test (CI mode)

# Lint & Format
black src/ tests/                          # Format code
isort src/ tests/                          # Sort imports
flake8 src/ tests/ --max-line-length=100   # Lint
mypy src/ --ignore-missing-imports         # Type check

# CLI
yclib-extract init                         # Interactive setup
yclib-extract scrape                       # Discover via Algolia
yclib-extract extract                      # Extract metadata to Markdown
yclib-extract pipeline                     # Orchestrated discovery + extract + audit
```

### 5) Environment and Config

- **Config sources:**
  - `.env` file (simple key=value parser in `src/yclib_extract/config.py`)
  - `config/ignore_sources.json` (source denylist)
  - `config/startup_school_curriculum.yaml` (curriculum definition)
  - CLI arguments (highest priority)

- **Required env vars:**
  - `ALGOLIA_APP_ID` (default: `45BWZJ1SGC`, public/read-only)
  - `ALGOLIA_API_KEY` (default: hardcoded public key, no manual setup needed)
  - `ALGOLIA_INDEX` (default: `Library_bookface_production`)
  - `CONTENT_DIR` (default: `artifacts/yc_library`)
  - `YCLIB_EXTRACT_MIN_CONTENT_LENGTH` (default: 700)
  - `INVIDIOUS_INSTANCES` (default: `yewtu.cafe,invidio.us`)

- **Deployment/runtime constraints:**
  - CLI-only application; no web server or daemon mode
  - SQLite database path hardcoded to `artifacts/extraction_jobs.db` (single-threaded with 30s timeout)
  - All outputs written to `artifacts/` directory (gitignored)
  - Proxy support via `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` env vars

### 6) Evidence

- `pyproject.toml` — build configuration, dependencies, entry points, linting config
- `.env.example` — environment variable template with defaults
- `.github/workflows/ci.yml` — GitHub Actions CI pipeline
- `src/yclib_extract/config.py` — configuration management and env loading
- `src/yclib_extract/extractor.py:49-80` — SQLite database initialization

## Extended Sections (Optional)

Add only when needed for complex repos:

- Full dependency taxonomy by category
- Detailed compiler/runtime flags
- Environment matrix (dev/stage/prod)
- Process manager and container runtime details
