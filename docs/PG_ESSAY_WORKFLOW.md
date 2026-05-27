# Paul Graham Essay Extraction Workflow

## Overview
The PG essay extraction pipeline handles discovery of essays from paulgraham.com, advanced footnote processing, and metadata-rich Markdown generation.

## Pipeline Stages

### 1. Discovery (HTML + RSS)
- **Inputs**: `PG_ARTICLES_INDEX_URL`, `PG_RSS_URL`
- **Process**: 
  - Scrape the HTML article index for the complete archive.
  - Parse the RSS feed for the most recent essays.
  - Merge and deduplicate URLs.
- **Output**: `artifacts/metadata/pg_essays_metadata.json`

### 2. Extraction & Cleaning
- **Input**: Essay URL
- **Process**:
  - Fetch HTML content.
  - Extract main content using `BeautifulSoup` and `trafilatura`.
  - **Advanced Footnote Processing**:
    - Detect "Notes" section.
    - Extract definitions (multi-line supported).
    - Convert inline markers `[1]` and linked markers `[[1](#f1n)]` to GFM `[^1]` format.
  - **Internal Link Resolution**:
    - Convert relative and absolute `paulgraham.com` links to local `./slug.md` references.
- **Output**: Cleaned Markdown string.

### 3. Metadata Enrichment
- **Input**: Markdown content
- **Process**:
  - Calculate word counts.
  - Estimate reading time (assuming 200 wpm).
  - Generate slug from title or URL stem.
- **Output**: Enriched frontmatter in Markdown files.

### 4. Auditing
- **Process**: Results are appended to the unified `artifacts/resources_audit.csv`.

## Key Commands
- **Full Run**: `yclib-extract pipeline --workflow full` (includes PG essays)
- **Targeted Run**: `python scripts/fetch_pg_essays.py`
- **Force Refresh**: `python scripts/fetch_pg_essays.py --force`

## Quality Metrics
- **Footnote Integrity**: Verified by converting definitions to standard Markdown footnotes.
- **Link Integrity**: Internal links are mapped to local files to enable offline navigation.
- **Metadata**: Every essay includes `word_count` and `reading_time`.

## Configuration
Constants in `src/yclib_extract/pipeline.py` define the source URLs and index denylist (skipping administrative pages like `index.html` or `rss.html`).
