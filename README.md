# yclib-extract

A reproducible, installable toolkit to discover and extract content from the Y Combinator ecosystem. It converts articles, essays, videos, and podcasts into a clean, searchable, and locally-navigable Markdown library.

## Core Components

The toolkit orchestrates extraction across four primary sources:

1. **Paul Graham Essays**: Extracts the complete archive from paulgraham.com. Includes advanced footnote processing and internal link resolution.
2. **Sam Altman Essays**: Extracts blog posts from blog.samaltman.com. Includes Atom feed discovery and layout-specific content extraction.
3. **YC Library**: Discovers and extracts hundreds of public articles, videos, and podcasts via the Algolia-backed Y Combinator Library.
4. **Startup School**: Assembles a curated, standalone curriculum directory by matching curriculum requirements against extracted assets, complete with fallback YouTube transcript recovery.
5. **YC Blog (tag-filtered)**: Supports Algolia-backed YC Blog discovery with taxonomy snapshots and allowlist/denylist filtering (denylist precedence). *Note: The public YC Blog Algolia API has ACL restrictions. If API access fails, the tool automatically falls back to RSS feed (limited to 15 recent announcements). For full blog content access, consider providing custom Algolia credentials.*
6. **YC Companies by Tag**: Fetches tag-scoped YC company lists from the `yc-oss/api` tag JSON files, writes per-tag metadata/taxonomy, and exports each company as Markdown with YAML frontmatter plus supporting fields.

## Installation

Requires Python 3.9+.

```bash
# Core install (no video transcripts)
pip install yclib-extract

# Install with full YouTube transcript recovery support
pip install "yclib-extract[transcripts-full]"

# Interactive first-run setup
yclib-extract init
```

## Quick Start

`yclib-extract` is designed to be run as a unified pipeline or as modular, targeted fetches. 

### The Unified Pipeline
To discover, extract, and audit the entire YC Library and the Startup School curriculum:

```bash
yclib-extract pipeline --workflow full
```
*This command runs the discovery phase (Algolia, RSS), the extraction phase (HTML to Markdown, transcript recovery), and generates a unified audit CSV.*

### Targeted Extraction
You can fetch specific components independently:

```bash
# Fetch Paul Graham essays
yclib-extract fetch pg

# Fetch Sam Altman essays
yclib-extract fetch altman

# Build the standalone Startup School curriculum directory
yclib-extract build startup-school --ensure-local --cleanup-orphans

# YC Blog PoC: discover taxonomy + save filtered metadata
yclib-extract scrape-blog --taxonomy-output artifacts/metadata/yc_blog_taxonomy.json

# YC Companies by Tag: require one or more tag slugs
yclib-extract scrape-companies --tags ai weather --taxonomy-output artifacts/metadata/yc_companies_by_tag_taxonomy.json
```

*Note: The pipeline uses an append-only mode by default. Append `--force` to any command to overwrite existing files and force a fresh extraction.*

## Outputs

All extracted content is saved to the `artifacts/` directory:

- `artifacts/pg_essays/` — Paul Graham essays.
- `artifacts/sam_altman_essays/` — Sam Altman essays.
- `artifacts/yc_library/` — YC Library resources.
- `artifacts/yc_blog/` — YC Blog resources.
- `artifacts/yc_companies_by_tag/` — YC Companies-by-tag resources, grouped by tag slug.
- `artifacts/yc_startup_school/` — Standalone Startup School curriculum.
- `artifacts/resources_audit.csv` — A unified audit detailing the success and quality metrics of every extracted file.

Each Markdown file contains rich YAML frontmatter (title, author, publication date, word count, reading time) designed to be highly compatible with tools like Obsidian.

## Advanced Usage & Documentation

For detailed information on database tracking, output formats, proxy configuration, and troubleshooting, please refer to the detailed documentation:

- **[Advanced Usage & Formats](docs/USAGE.md)**
- **[Codebase Architecture & Design](docs/codebase/ARCHITECTURE.md)**

## License

MIT. See LICENSE file.
