# Technical Concerns & Known Issues

## Core Sections (Required)

### 1) Code Quality Risks

| Risk | Severity | Location | Details | Evidence |
|------|----------|----------|---------|----------|
| Code formatting drift | Low | `src/yclib_extract/` | Black check fails on multiple files (cli.py, config.py, scraper.py, etc.) | Scan: `black --check` output shows reformatting needed |
| [TODO] Documentation | Low | Throughout | Core business logic lacks inline docstrings; only high-level docs exist | [Verify: sample functions] |
| [TODO] Type hints | Medium | `src/yclib_extract/` | Limited type hints; mypy not enforced in CI | `README.md:427` mentions `--ignore-missing-imports` |
| Hardcoded paths | Low | Module constants | Artifact paths hardcoded to `artifacts/` directory | `src/yclib_extract/config.py:46-47` |

### 2) Performance Concerns

| Concern | Impact | Notes | Mitigation |
|---------|--------|-------|-----------|
| Sequential metadata loading | Medium | JSON metadata files loaded entirely into memory before extraction | No pagination or streaming; works for current ~400-700 resources |
| Thread pool overhead | Low | Default 4 workers; parallelization via ThreadPoolExecutor | SQLite write contention possible at scale; uses 30s timeout |
| Redundant HTML fetches | Low | No HTTP caching layer (requests library default); fetches same URL multiple times if job retried | Consider adding requests-cache |
| Trafilatura extraction latency | Low | No parallelization within extraction; CPU-bound for large HTML files | Current acceptable for production runs |

### 3) Security Considerations

| Issue | Severity | Details | Evidence |
|-------|----------|---------|----------|
| Plain-text credentials | Low | `.env` file contains Algolia keys in plain text; no encryption | Standard for local tools; not suitable for shared/CI environments |
| Public hardcoded API key | Low | Algolia API key is read-only and public (no risk); intentional design | `src/yclib_extract/scraper.py:44-50` |
| No input validation | Medium | User-provided URLs, slugs, content not explicitly validated before insertion into Markdown/CSV | `[TODO]` verify injection risks in Markdown frontmatter |
| YAML deserialization | Low | `config/startup_school_curriculum.yaml` parsed without explicit schema validation | `[TODO]` verify YAML safety (no code execution) |
| No authentication on essay fetch | Low | Public sites (paulgraham.com, samaltman.com) require no auth; exposure limited | Intended design |

### 4) Operational Concerns

| Concern | Severity | Notes | Mitigation |
|---------|----------|-------|-----------|
| Single SQLite file | Medium | `artifacts/extraction_jobs.db` is single point of failure; no replication | Regular backups recommended; 30s timeout prevents most deadlocks |
| Network reliability | Medium | Algolia, YouTube, essay sites availability affects pipeline completeness | Retry logic for failed/error status; ignore-list allows skipping unreliable sources |
| Append-only mode assumptions | Low | Weekly mode assumes file paths never collide; title-based slugs may produce duplicates across sources | `[ASK USER]` how to handle slug collisions in `yc_startup_school/` directory |
| Large artifact directory | Low | `artifacts/` contains extracted Markdown (potentially gigabytes) + metadata JSON + SQLite DB | Gitignored but takes local disk space |

### 5) Known Bugs & TODOs

**Production code TODOs/FIXMEs:** None found in scan (see Evidence below).

**Identified gaps:**

- `[TODO]` Test coverage for retry logic (`--retry-failed-only` edge cases)
- `[TODO]` Thread pool error handling (what happens when worker crashes?)
- `[TODO]` Transcript fallback chain exhaustion (all methods fail → mark missing?)
- `[TODO]` Slug collision resolution for cross-source items in `yc_startup_school/`

### 6) File Churn & Complexity

| File | Commits (90d) | Size | Fragility Signals |
|------|---------------|------|-------------------|
| `.github/copilot-instructions.md` | 1 | High | Emerging best practices; not yet stable |
| `.gitignore` | 1 | Low | Unlikely to change |
| README.md | 1 | Very High (572 lines) | Central documentation; may become stale |
| CONTEXT.md | 1 | Medium | Domain language reference; critical accuracy |
| GEMINI.md | 1 | Medium | Project overview; may drift from code |

**Observation:** Project is fresh (few commits); expect rapid iteration in early phases. Watch for documentation drift as features are added.

### 7) Scalability Limits

- **Max resources per run:** Current ~700 items (YC Library + PG essays + Altman essays); threading handles ~4-8 items in parallel
- **Metadata file size:** 337.6 KB for YC metadata; manageable but could grow
- **SQLite concurrent writes:** 30s timeout adequate for current threading model; would need connection pooling for >100 parallel workers
- **Artifact disk usage:** Extracted Markdown files (largest: 146 KB); total potentially gigabytes for full library

### 8) Evidence

- Scan output: `pyproject.toml`, `.env.example`, CI/CD configuration
- `.github/workflows/ci.yml` — no linting enforcement (only tests)
- `src/yclib_extract/extractor.py:56-63` — SQLite connection pooling with timeout
- `src/yclib_extract/pipeline.py:49-50` — retryable statuses list
- Scan output: High-churn files (minimal; project is young)
- `README.md:298-333` — troubleshooting section reveals operational concerns
