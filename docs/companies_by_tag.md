Companies-by-tag workflow

This feature fetches YC companies grouped by tag from the yc-oss/api tags directory and writes both a metadata manifest and per-company Markdown artifacts.

Quick example

# Fetch metadata for specific tags
yclib-extract scrape-companies --tags weather health --output-dir artifacts/metadata/yc_companies_by_tag

# Discover all YC tags and build a taxonomy first
yclib-extract scrape-companies --discover-all-tags --taxonomy-only --taxonomy-output artifacts/metadata/yc_companies_by_tag_taxonomy.json

# Fetch metadata and write Markdown artifacts
yclib-extract scrape-companies --tags weather health --output-dir artifacts/metadata/yc_companies_by_tag

# Fetch the built-in default seed tags
yclib-extract scrape-companies --taxonomy-output artifacts/metadata/yc_companies_by_tag_taxonomy.json

Output
- Metadata manifests: artifacts/metadata/yc_companies_by_tag/{tag}.json
- Taxonomy summary: artifacts/metadata/yc_companies_by_tag/yc_companies_by_tag_taxonomy.json
- Markdown artifacts: artifacts/yc_companies_by_tag/companies/{company-slug}.md

Notes
- Use --discover-all-tags to fetch the full YC tag taxonomy before choosing a subset to run.
- If no tags are provided, the CLI uses the built-in seed set: generative-ai, aiops, crypto-web3, developer-tools, design-tools, open-source, web-development.
- Use --force to overwrite existing manifests and Markdown files.