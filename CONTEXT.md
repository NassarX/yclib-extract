# YC Content Extraction

This context defines the canonical language for generating and maintaining extracted YC Library and Paul Graham content artifacts.

## Language

**Metadata Manifest**:
JSON files in `artifacts/metadata/` that define the intended state and instructions for extraction. This is the source of truth for what resources should exist and where they come from.
_Avoid_: audit file, db

**Taxonomy Snapshot**:
A JSON snapshot (for example `artifacts/metadata/yc_blog_taxonomy.json`) that reports discovered category/tag values and counts. It informs filtering policy but does not itself define extraction intent.
_Avoid_: final metadata manifest, extraction state

**Unified Audit**:
A single CSV file (`artifacts/resources_audit.csv`) acting as a historical record of the last pipeline execution across all sources. It reports on extraction success but does not dictate intended state.
_Avoid_: metadata, database

**Curriculum Resource**:
A single learning item defined in `config/startup_school_curriculum.yaml` that must resolve to an online source and optionally a local artifact.
_Avoid_: lesson file, entry

**Resource Matching**:
The process of identifying duplicate content across different metadata manifests (for example YC Library vs Startup School). The **Source URL** is the primary canonical identifier for matching, as titles and IDs may vary between sources.
_Avoid_: title matching, ID matching

**Local Artifact**:
A Markdown file generated under configured artifact directories (for example `YC_LIBRARY_DIR`, `PG_ESSAYS_DIR`, `YC_STARTUP_DIR`) and referenced by curriculum output.
_Avoid_: cache file, temp file

**Standalone Naming**:
The policy for naming files in the `yc_startup_school` directory. Files use Title-Based Slugs; if a collision occurs, a source-specific suffix is appended (e.g., `-pg`, `-yc`). This resolution applies *only* to the standalone school directory to preserve the integrity of the original source folders.
_Avoid_: global renaming, hash-based naming

**Standalone Integrity**:
The principle that the `yc_startup_school` directory must be self-contained. In the rare event that a Local Artifact references internal binary assets (for example images or PDFs), those assets must be copied into the standalone directory to prevent cross-component dependency.
_Avoid_: cross-component links, relative path traversal

**PG Essay Slug**:
The canonical filename stem for a Paul Graham essay derived from URL/title without numeric suffixes.
_Avoid_: numbered filename, legacy `-1`/`-2` suffix

**Refresh Existing**:
An explicit opt-in behavior that allows re-fetch/rewrite of already existing local artifacts; default pipeline behavior is to skip existing files.
_Avoid_: automatic overwrite, implicit update

**Extraction Quality**:
A secondary status field in the **Unified Audit** used to distinguish between full and partial extraction success. A resource is marked **`done`** if the Local Artifact is created, but may include a **Quality Warning** (for example "missing-transcript") to facilitate targeted retries or specialized auditing without blocking the overall pipeline completion.
_Avoid_: failed-status-for-partial-success, hidden-short-content

**Weekly Mode**:
Production-oriented pipeline behavior that is append-only: existing local artifacts are preserved and only missing resources are backfilled.
_Avoid_: refresh mode, overwrite mode

**Tag Filter Precedence**:
When both allowlist and denylist tags apply to the same resource, denylist wins and the resource is excluded.
_Avoid_: include-wins conflict handling

**Dev Replay**:
Testing-oriented pipeline behavior (`--mode dev --replay`) that can force reprocessing to validate workflow behavior without changing weekly production policy.
_Avoid_: production refresh

## Example dialogue

Dev: "This Curriculum Resource is missing locally; should I fetch it?"

Domain expert: "Yes, create a Local Artifact, but keep the PG Essay Slug canonical and unnumbered."

Dev: "The artifact already exists. Should I rewrite it?"

Domain expert: "Not by default. Only rewrite when Refresh Existing is explicitly requested."
