# Testing

## Core Sections (Required)

### 1) Test Framework & Setup

| Component | Details | Evidence |
|-----------|---------|----------|
| Test runner | pytest >= 7.0 | `pyproject.toml:33` |
| Test location | `tests/` (11 test modules) | Scan output; `.github/workflows/ci.yml:26` |
| Python versions tested | 3.9, 3.11 (in matrix) | `.github/workflows/ci.yml:14` |
| Assertion style | `assert` statements (pytest default) | `tests/test_smoke.py:1-2` |
| Fixtures | In `tests/fixtures/` (HTML files, etc.) | Scan output lists `tests/fixtures/live_office_hours.html` |
| Mocking | Avoid external calls; mock `requests` or use fixtures | [TODO: verify in test code] |

### 2) Test File Organization

| File | Purpose | Coverage |
|------|---------|----------|
| `test_smoke.py` | Minimal placeholder test | Sanity check |
| `test_cli.py` | CLI argument parsing and command routing | `src/yclib_extract/cli.py` |
| `test_config.py` | Configuration loading and priority resolution | `src/yclib_extract/config.py` |
| `test_scraper.py` | Algolia discovery and metadata persistence | `src/yclib_extract/scraper.py` |
| `test_extractor.py` | Content extraction and job tracking | `src/yclib_extract/extractor.py` |
| `test_html_cleaning.py` | HTML parsing, footnote processing, Markdown generation | `src/yclib_extract/lib/html_cleaning.py` |
| `test_transcripts.py` | Transcript recovery fallback chain | `src/yclib_extract/lib/youtube_transcripts.py` |
| `test_curriculum_injection.py` | Curriculum metadata injection logic | `scripts/build_curriculum.py` |
| `test_regressions.py` | Regression tests for known issues | [TODO: verify specific regressions] |
| `test_optional_deps.py` | Optional dependency handling (transcripts-full, yaml, playwright) | Feature gating |

### 3) Coverage & Quality Gates

- **Coverage threshold:** [TODO] (no coverage enforcement visible in CI)
- **Coverage tool:** [TODO] (not explicitly configured in `pyproject.toml`)
- **CI/CD quality gates:** Tests must pass on Python 3.9, 3.11; `pytest -q` in CI
- **Lint enforcement:** [TODO] (black/isort/flake8 not run in CI, only tests)

### 4) Testing Best Practices

- **No external API calls:** Tests should mock Algolia, YouTube, paulgraham.com
- **Fixtures for large HTML:** Use `tests/fixtures/live_office_hours.html` (133.6KB) for extraction tests
- **Database testing:** Create temporary `.db` files or use in-memory SQLite (`:memory:`)
- **Deterministic tests:** Avoid time-dependent assertions or randomness
- **Isolation:** Each test should clean up its artifacts directory or use temp directories

### 5) Known Test Issues [TODO]

- No explicit test for retry logic (`--retry-failed-only` flag)
- No explicit test for thread pool parallelization edge cases
- Limited integration testing with real Algolia/YouTube (should mock)
- Transcript fallback chain testing may require Invidious mock

### 6) Evidence

- `.github/workflows/ci.yml:20-27` — CI test setup
- `tests/` directory listing from scan output
- `pyproject.toml:33` — pytest dependency
- `README.md:412-425` — local development test commands
