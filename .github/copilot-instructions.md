# Copilot Instructions for yclib-extract

Use this guide when changing `yclib-extract` so your edits match the current project shape, naming, and pipeline behavior.

## Before changing code
- Read `README.md` for the user-facing flow.
- Read `CONTEXT.md` for canonical domain language.
- Read `src/yclib_extract/pipeline.py` and `src/yclib_extract/cli.py` before touching orchestration.

## Quick start
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
pytest tests/ -v
black src/ tests/
isort src/ tests/
flake8 src/ tests/ --max-line-length=100
mypy src/ --ignore-missing-imports
```

## Current package shape
```
src/yclib_extract/
├── cli.py              # argparse entry point and subcommand wiring
├── pipeline.py         # orchestration for discovery, extraction, audits, workflows
├── scraper.py          # Algolia discovery and metadata persistence
├── extractor.py        # HTML -> Markdown extraction and SQLite job tracking
├── config.py           # env/default handling and .env persistence
├── commands/init.py    # interactive first-run setup
└── lib/
    ├── html_cleaning.py
    └── youtube_transcripts.py
```

`scripts/` contains the higher-level curriculum and essay fetch flows, including `build_curriculum.py`, `fetch_pg_essays.py`, and `fetch_sam_altman_essays.py`.

## User-facing commands
- `yclib-extract init`
- `yclib-extract scrape`
- `yclib-extract extract`
- `yclib-extract pipeline`

`scrape` discovers YC Library posts via Algolia. `extract` converts metadata into Markdown. `pipeline` orchestrates discovery, extraction, and audits with `--mode weekly|dev`, `--start-stage discover|extract|audit`, `--replay`, `--workflow startup_school|full`, and the usual force/retry flags.

## Core conventions
- Treat `artifacts/metadata/yc_library_metadata.json` as the discovery source of truth.
- Write extracted Markdown to `artifacts/yc_library/`.
- Keep Startup School curriculum output in `artifacts/yc_startup_school/`.
- Keep essay fetch outputs in `artifacts/pg_essays/` and `artifacts/sam_altman_essays/`.
- Keep extraction state in `artifacts/extraction_jobs.db`.
- Keep generated outputs out of source control.
- Preserve append-only behavior in weekly flows; force/replay should remain explicit.
- Keep transcript recovery resilient and optional; `missing` and `error` mean different things.
- Keep comments minimal and code paths explicit.

## Configuration
- Algolia: `ALGOLIA_APP_ID`, `ALGOLIA_API_KEY`, `ALGOLIA_INDEX`
- Paths: `METADATA_DIR`, `CONTENT_DIR`
- Extraction: `YCLIB_EXTRACT_MIN_CONTENT_LENGTH`
- Transcript fallback: `INVIDIOUS_INSTANCES`
- General proxying: `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`

## When updating docs or behavior
- Keep `README.md`, `.github/copilot-instructions.md`, and `CONTEXT.md` consistent.
- Prefer the current code over legacy command names or old output paths.
- Use conventional commits: `feat`, `fix`, `docs`, `chore`, `ci`, `test`, `refactor`.

## Helpful implementation reminders
- `cli.py` should stay thin and delegate work.
- `scraper.py` should handle discovery and metadata writing, not orchestration.
- `extractor.py` should own extraction and status updates.
- `pipeline.py` should coordinate multi-stage behavior, not duplicate extraction logic.
- `config.py` is the single place for defaults and `.env` handling.
