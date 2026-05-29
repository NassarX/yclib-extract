Companies-by-tag workflow

This feature fetches YC companies grouped by tag from the yc-oss/api tags directory and writes both a metadata manifest and per-company Markdown artifacts.

Quick example

# Fetch metadata for specific tags (required)
yclib-extract scrape-companies --tags weather health --output-dir artifacts/metadata/yc_companies_by_tag

# Fetch metadata and write Markdown artifacts
yclib-extract scrape-companies --tags weather health --output-dir artifacts/metadata/yc_companies_by_tag

Output
- Metadata manifests: artifacts/metadata/yc_companies_by_tag/{tag}.json
- Taxonomy summary: artifacts/metadata/yc_companies_by_tag/yc_companies_by_tag_taxonomy.json
- Markdown artifacts: artifacts/yc_companies_by_tag/{tag}/{company-slug}.md

Notes
- The CLI requires at least one tag slug to be provided via --tags to avoid unbounded scraping.
- Use --force to overwrite existing manifests and Markdown files.