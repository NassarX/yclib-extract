# Conventions

## Core Sections (Required)

### 1) Naming Conventions

| Category | Pattern | Examples | Evidence |
|----------|---------|----------|----------|
| Module names | `snake_case.py` | `scraper.py`, `html_cleaning.py` | `src/yclib_extract/` |
| Class names | `PascalCase` | `Config`, `ContentExtractor`, `ExtractionDB` | `src/yclib_extract/extractor.py:41-47` |
| Functions | `snake_case` | `extract_content()`, `load_ignore_sources()` | `src/yclib_extract/scraper.py` |
| Private functions | `_snake_case` | `_slugify()`, `_load_json()` | `src/yclib_extract/scraper.py:53-70` |
| Constants | `SCREAMING_SNAKE_CASE` | `DEFAULT_METADATA_DIR`, `ARTIFACTS_DIR` | `src/yclib_extract/config.py:45-59` |
| Variables | `snake_case` | `metadata_path`, `job_count` | Throughout |
| File naming (extracted output) | `kebab-case.md` | `do-things-that-dont-scale.md` (slugified from title) | `README.md:188-199` |

### 2) Code Organization & Imports

- **Import order:** Standard library → third-party → local (with blank lines between groups)
- **Local imports:** Use relative imports (`from . import module`, `from .lib import something`)
- **Path conventions:** Paths managed as `Path` objects (pathlib), not strings; centralized defaults (e.g., `ARTIFACTS_DIR = Path("artifacts").resolve()`)
- **Artifact paths:** Hardcoded as module-level constants (not passed through config layers)

### 3) Error Handling

- **Approach:** Return error information in dataclass or database field; raise exceptions only for unrecoverable errors
- **Job status:** Database `status` field captures outcome: `pending`, `done`, `short`, `failed`, `error`, `missing`, `removed`
- **Error messages:** Stored in database `error_msg` field for audit trail; printed to stdout
- **Transcript fallback:** Graceful degradation: no public transcript → mark `quality: missing-transcript` (not fatal)
- **No raising on extraction failure:** Failed extraction marked with status; caller decides retry policy

### 4) Logging & Output

- **Logging approach:** Print-based (no logging library); progress to stdout, warnings to stderr
- **Log format:** Simple text messages; no structured logging
- **Audit trail:** SQLite job table + CSV audit file record all extraction attempts
- **Verbosity:** CLI has `--audit-only` flag to skip extraction and show current status

### 5) Database & Persistence

- **Database:** SQLite 3 standard library (no ORM)
- **Schema:** Single table `extraction_jobs` with job tracking fields (id, status, content_length, error_msg, etc.)
- **Safety:** Context manager `_connect()` with 30s timeout; no explicit transactions
- **Configuration:** Path to `.db` file hardcoded or passed explicitly; no dynamic schema creation

### 6) Testing Conventions

- **Test location:** `tests/` directory (alongside package, not inside `src/`)
- **Test naming:** `test_*.py` modules, `test_*()` functions
- **Fixtures:** In `tests/fixtures/` (HTML files, etc.)
- **Mocking:** Avoid external API calls; mock `requests.get()` or use local fixtures
- **Assertion style:** Plain `assert` statements (pytest default)
- **No skip decorators:** Tests are expected to pass on all supported Python versions

### 7) Evidence

- `src/yclib_extract/` — all modules follow conventions
- `pyproject.toml:45-50` — black and isort configuration
- `.github/copilot-instructions.md` — project conventions guide
- `CONTEXT.md` — canonical domain language and naming
