# Pipeline Orchestration & State Management

## Overview
The `PipelineOrchestrator` is the central brain of the project, coordinating discovery, extraction, and auditing across multiple content sources. It uses a metadata-driven approach and maintains persistent state in SQLite to ensure reliability and idempotency.

## State Management (SQLite)

### Pipeline Items (`pipeline_items` table)
- **Canonical Key**: `canonical_url`
- **Fields**: Tracks `stage`, `status`, `word_count`, `last_error`, and timestamps for every resource.
- **Purpose**: Prevents redundant work and enables resume capabilities.

### Pipeline Runs (`pipeline_runs` table)
- **Fields**: `run_id`, `start_stage`, `mode`, `status`, `started_at`, `ended_at`.
- **Purpose**: Audits historical performance and provides a "Resume" context for failed runs.

## Multi-Stage Workflow
The pipeline executes in sequential stages:
1. **Discover**: Scrapes sources (Algolia, RSS, HTML) to build/update metadata JSON manifests.
2. **Extract**: Fetches content, converts to Markdown, recovers transcripts, and applies cleaning rules.
3. **Audit**: Aggregates all results into a unified CSV index.

## Execution Modes

### Weekly Mode (`--mode weekly`)
- **Default behavior**.
- **Append-only**: Skips resources that are already marked as `done` in the database.
- **Safe for production**: Minimizes network usage and risk of overwriting validated content.

### Dev Mode (`--mode dev`)
- **Forces re-extraction**: Overwrites existing files.
- **Lower thresholds**: Often used with lower `min_content_length` for testing.
- **Replay**: Equivalent to using `--force` or `--replay`.

## Error Handling & Retries
- **Retryable Statuses**: `failed`, `error`, `short` (content too small).
- **Manual Retry**: `yclib-extract extract --retry-failed-only` allows targeting problematic resources without re-running discovery.
- **Timeout Protection**: Network requests use a 15-20s timeout to prevent hanging.

## Run Resumption
If a run fails, the orchestrator detects the previous `error` status and warns the user. Using `--replay` will resume the last attempted stage.

## Monitoring
Every run generates a **Run Summary** at the end, reporting counts of successes, failures, and skipped items by status.
