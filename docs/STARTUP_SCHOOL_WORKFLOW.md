# Startup School & YouTube Extraction Workflow

## Overview
The Startup School pipeline is a specialized workflow that builds a standalone, portable learning library from the official YC Startup School curriculum. It coordinates YouTube transcript recovery, cross-source resource resolution, and directory organization.

## Pipeline Stages

### 1. Curriculum Definition
- **Input**: `config/startup_school_curriculum.yaml`
- **Process**: Defines the learning modules, resources, authors, and conditions.

### 2. Resource Resolution & Mapping
- **Process**: 
  - Each resource in the YAML is mapped to a canonical ID (slugified title).
  - Naming collisions across sources (e.g., an essay and a video with the same title) are resolved by adding source-specific suffixes (`-pg`, `-sa`, `-yc`).
- **Output**: `artifacts/metadata/yc_startup_school_metadata.json`

### 3. Transcript Recovery (YouTube)
- **Input**: YouTube URLs from curriculum.
- **Fallback Chain**:
  1. `YouTubeTranscriptApi` (Official)
  2. `yt-dlp` (Captions extraction)
  3. Watch Page Scraping (Metadata extraction)
  4. **Invidious API** (Mirror fallback)
- **Cleanup**: Normalizes whitespace, replaces smart quotes, and adds heuristic speaker labels.

### 4. Standalone Library Assembly
- **Process**:
  - Existing Markdown files from other pipelines (PG, SA, YC Library) are copied into `artifacts/yc_startup_school/`.
  - Missing resources (mostly YouTube videos) are extracted directly into the directory.
  - Orphaned files (those no longer in the curriculum) are optionally removed.
- **Output**: A self-contained directory of Markdown files + `startup_school_curriculum.md` guide.

## Key Commands
- **Full Build**: `yclib-extract pipeline --workflow startup_school`
- **Manual Build**: `python scripts/build_curriculum.py --ensure-local --cleanup-orphans`

## Integrity & Quality
- **Standalone Integrity**: The `yc_startup_school` directory is designed to be moved or shared without requiring the rest of the `artifacts/` folder.
- **Transcript Quality**: Verified by presence of `transcript` markers and heuristic speaker detection.
- **Collision Resolution**: Ensured by the `resolved_id` logic in `build_curriculum.py`.
