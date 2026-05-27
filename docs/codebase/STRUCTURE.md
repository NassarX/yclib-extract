# Codebase Structure

## Core Sections (Required)

### 1) Top-Level Map

| Path | Purpose | Evidence |
|------|---------|----------|
| `src/yclib_extract/` | Main Python package with discovery, extraction, orchestration | `README.md:432-442` |
| `src/yclib_extract/cli.py` | argparse entry point and command routing | `pyproject.toml:37-40` |
| `src/yclib_extract/scraper.py` | Algolia discovery and metadata persistence | `GEMINI.md:10` |
| `src/yclib_extract/extractor.py` | HTML-to-Markdown content extraction engine | `GEMINI.md:12` |
| `src/yclib_extract/pipeline.py` | Orchestration: discovery → extraction → audit across all sources | `GEMINI.md:13-14` |
| `src/yclib_extract/config.py` | Centralized env/default config management | `README.md:78-125` |
| `src/yclib_extract/commands/init.py` | Interactive first-run setup | `README.md:44-50` |
| `src/yclib_extract/lib/html_cleaning.py` | HTML parsing, footnote processing, internal links | `CONTEXT.md:51-52` |
| `src/yclib_extract/lib/youtube_transcripts.py` | Transcript recovery fallback chain | `README.md:128-134` |
| `tests/` | Pytest test suite (11 test modules) | `.github/workflows/ci.yml:26` |
| `config/` | Configuration files (ignore list, curriculum YAML) | `README.md:451` |
| `scripts/` | Utility scripts: curriculum build, essay fetchers | `README.md:476-510` |
| `artifacts/` | Generated output directory (gitignored): metadata, extracted Markdown, audit CSV, SQLite DB | `README.md:446-449` |
| `scrape_runs/` | Daily audit manifests (gitignored) | `README.md:247-275` |
| `.env.example` | Environment variable template with defaults | `README.md:78-125` |
| `pyproject.toml` | Package manifest and tooling config | `README.md:457-460` |

### 2) Entry Points

- **Main runtime entry:** `src/yclib_extract/cli.py:main()` (registered as `yclib-extract` console script)
- **Secondary entry points:**
  - `yclib-scrape` → `yclib_extract.scraper:main()` (manual Algolia discovery)
  - `yclib-get` → `yclib_extract.extractor:main()` (manual content extraction)
- **How entry is selected:**
  - CLI argument selects subcommand (`scrape`, `extract`, `pipeline`, `init`)
  - Each subcommand delegates to appropriate module
  - Config is loaded from `.env` file or environment variables (not command-line config files)

### 3) Module Boundaries

| Boundary | What belongs here | What must not be here |
|----------|-------------------|------------------------|
| `scraper.py` | Algolia API calls, metadata JSON persistence, ignore-list handling | Extraction, HTML parsing, pipeline orchestration |
| `extractor.py` | HTML fetching, trafilatura extraction, Markdown generation, SQLite job tracking, frontmatter formatting | Algolia discovery, pipeline orchestration, transcript logic |
| `pipeline.py` | Multi-stage orchestration (discover, extract, audit), unified audit CSV generation, essay fetching, curriculum injection | Individual extraction or scraping work |
| `config.py` | Env var loading, .env file parsing, default values, CLI override merging | Business logic, external API calls |
| `lib/html_cleaning.py` | HTML DOM manipulation, footnote processing, link rewriting, Markdown generation | Network calls, job tracking, file I/O (except final write) |
| `lib/youtube_transcripts.py` | Transcript recovery fallback chain (on-page → API → yt-dlp → watch page), proxy handling | Job tracking, Markdown formatting |
| `commands/init.py` | Interactive first-run setup, .env file generation | Real discovery/extraction work |
| `tests/` | Unit and integration tests, fixtures | Production code, business logic |

### 4) Naming and Organization Rules

- **File naming pattern:** `snake_case.py` for all Python modules (e.g., `config.py`, `scraper.py`, `html_cleaning.py`)
- **Directory organization pattern:** Layer-based (cli → commands/scraper/extractor/pipeline → lib; not feature-based)
- **Function/variable naming:** `snake_case` throughout (no camelCase or PascalCase)
- **Class naming:** `PascalCase` for classes (e.g., `Config`, `ExtractionDB`, `AlgoliaScraper`, `ContentExtractor`)
- **Private members:** Prefix with `_` for internal functions/methods (e.g., `_slugify()`, `_load_json()`)
- **Constants:** `SCREAMING_SNAKE_CASE` (e.g., `DEFAULT_METADATA_DIR`, `ARTIFACTS_DIR`)
- **Artifacts and output paths:** Centralized as `Path` objects in module root (e.g., `ARTIFACTS_DIR = Path("artifacts").resolve()`)
- **Database paths:** Hardcoded defaults (e.g., `DEFAULT_DB_PATH = str(ARTIFACTS_DIR / "extraction_jobs.db")`)
- **Import organization:** Grouped by category with blank lines: stdlib → third-party → local imports; uses `from . import module` for same-package

### 5) Evidence

- `README.md:431-456` — project structure diagram
- `src/yclib_extract/cli.py` — entry point and command routing
- `src/yclib_extract/__init__.py` — package initialization and version
- `GEMINI.md:57-62` — key files reference
- `pyproject.toml:37-40` — console script entry points

## Extended Sections (Optional)

Add only when repository complexity requires it:

- Subdirectory deep maps by feature/layer
- Middleware/boot order details
- Generated-vs-source layout boundaries
- Monorepo workspace-level structure maps
