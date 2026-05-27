# GEMINI.md - YC Content Extraction Instructions

This project, `yclib-extract`, is a Python-based toolkit designed to discover, extract, and audit content from the Y Combinator Library, Paul Graham's essays, and Sam Altman's blog. It follows a metadata-driven architecture focused on "Efficiency First" content reuse and stable, reproducible extraction.

## Project Overview

- **Purpose**: Automates the creation of a local, searchable Markdown library of YC-related content.
- **Main Technologies**: Python 3.9+, Requests, BeautifulSoup4, Trafilatura (HTML extraction), SQLite (job tracking), YouTube Transcript API (video transcripts).
- **Architecture**:
    1. **Discovery**: Scrapers fetch metadata from sources (Algolia for YC Library, RSS/HTML for essays).
    2. **Metadata**: Centralized JSON manifests in `artifacts/metadata/` act as the source of truth.
    3. **Extraction**: Targeted extraction of HTML content, conversion to Markdown with rich frontmatter.
    4. **Tracking**: SQLite database (`extraction_jobs.db`) manages job status and prevents redundant work.
    5. **Auditing**: Unified CSV audit (`artifacts/resources_audit.csv`) reports on the success and quality of 700+ resources.

## Key Commands

### Installation & Setup
- **Initialize**: `yclib-extract init` (sets up `.env` and credentials)
- **Install (Core)**: `pip install -e .`
- **Install (Full)**: `pip install -e ".[transcripts-full,yaml,playwright]"`

### Running the Pipeline
- **Full Workflow**: `yclib-extract pipeline --workflow full` (Runs discovery, extraction, and audits for all sources)
- **Startup School**: `yclib-extract pipeline --workflow startup_school` (Specialized curriculum-focused run)
- **Targeted Extraction**: `yclib-extract extract --retry-failed-only` (Retries jobs with `failed`, `error`, or `short` status)

### Utility Scripts
- **Build Curriculum**: `python scripts/build_curriculum.py --collect` (Generates the Startup School guide)
- **Fetch PG Essays**: `python scripts/fetch_pg_essays.py`
- **Fetch Altman Essays**: `python scripts/fetch_altman_essays.py`

### Testing & Validation
- **Run All Tests**: `pytest tests/`
- **Check Database**: `sqlite3 artifacts/extraction_jobs.db "SELECT status, COUNT(*) FROM extraction_jobs GROUP BY status;"`

## Development Conventions

### 1. Metadata-Driven Workflow
Always prioritize the **Metadata Manifest** (`artifacts/metadata/*.json`) as the source of truth. The pipeline should be capable of resuming from metadata even if the local content or database is partially lost.

### 2. File Naming (Title-Based Slugs)
All local artifacts use **Title-Based Slugs** (e.g., `do-things-that-dont-scale.md`). For Startup School resources, use the specific slug resolution logic to handle potential cross-source collisions (e.g., adding `-pg` or `-yc` suffixes).

### 3. Extraction Quality
Distinguish between **Status** (behavioral success) and **Quality** (content completeness).
- `status=done` means the file was created.
- `quality=missing-transcript` indicates a video was extracted without its transcript section.
Always check both fields in `resources_audit.csv`.

### 4. Footnote & Reference Handling
Essays (especially PG's) require specialized footnote processing. Use `process_footnotes` in `src/yclib_extract/lib/html_cleaning.py` to handle multi-line notes and anchor replacements.

### 5. Standalone Integrity
The `yc_startup_school` directory must be self-contained. When building the curriculum, local artifacts should be copied into this directory to ensure it can be moved or distributed without external dependencies.

## Key Files
- `src/yclib_extract/pipeline.py`: Main orchestration logic and unified audit generation.
- `src/yclib_extract/extractor.py`: Content extraction engine and SQLite job management.
- `config/startup_school_curriculum.yaml`: Definition of the Startup School learning paths.
- `CONTEXT.md`: Canonical domain language and naming conventions.
- `artifacts/resources_audit.csv`: Master index of all project resources.
