# Sam Altman Essay Extraction Workflow

## Overview
The Sam Altman essay extraction pipeline handles discovery of posts from blog.samaltman.com, content extraction from Tumblr-based layouts, and metadata enrichment.

## Pipeline Stages

### 1. Discovery (Atom Feed + Archive)
- **Inputs**: `SA_ARTICLES_FEED_URL` (Atom), `SA_ARCHIVE_URL` (HTML)
- **Process**: 
  - Parse the Atom feed using `RSSScraper` for recent posts and metadata (including publication dates).
  - Fallback to Playwright-based archive scraping if the feed is unavailable or incomplete.
  - Sort essays oldest-to-newest to ensure internal link resolution maps correctly.
- **Output**: `artifacts/metadata/altman_essays_metadata.json`

### 2. Extraction & Cleaning
- **Input**: Essay URL
- **Process**:
  - Fetch HTML content.
  - Extract main content using targeted selectors for blog layouts (e.g., `article`, `div.post`, `div.entry`).
  - Convert to Markdown using standard cleaning rules.
  - **Internal Link Resolution**:
    - Convert `blog.samaltman.com` links to local `./slug.md` references.
- **Output**: Cleaned Markdown string.

### 3. Metadata Enrichment
- **Input**: Markdown content
- **Process**:
  - Calculate word counts and reading time.
  - **Extraction Quality**:
    - Verify content length and presence of core metadata.
    - Tag with quality levels (`excellent`, `good`, `minimal`, `short`).
- **Output**: Enriched frontmatter with quality markers.

### 4. Auditing
- **Process**: Results are appended to the unified `artifacts/resources_audit.csv`.

## Key Commands
- **Full Run**: `yclib-extract pipeline --workflow full`
- **Targeted Run**: `python scripts/fetch_altman_essays.py`

## Configuration
Constants in `src/yclib_extract/pipeline.py` define the Atom feed URL and archive fallback URL.
