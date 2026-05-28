#!/usr/bin/env python3
"""Enrich all metadata files with mandatory tags_yaml field.

This script ensures all resources have a 'tags_yaml' field with proper defaults:
- YC Library: ["YC", "yc-library"] + any slug-based tags from metadata
- YC Blog: ["YC", "yc-blog"] + any slug-based tags from metadata
- PG Essays: ["essay", "pg"] + any metadata tags
- Altman Essays: ["essay", "altman"] + any metadata tags
- Startup School: ["YC", "startup-school"] + any metadata tags
"""

import sys
from pathlib import Path
from typing import Any, Dict

# Add project root to sys.path before imports
_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / "src"))

from scripts.shared import (
    extract_tag_slugs,
    infer_source_type,
    load_json,
    save_json,
    get_metadata_dir,
    OutputFormatter,
)
from yclib_extract.lib.tag_defaults import build_tags_for_resource


def enrich_metadata_file(filepath: Path, formatter: OutputFormatter) -> int:
    """Add tags_yaml to all resources in metadata file.
    
    Returns number of resources updated.
    """
    if not filepath.exists():
        formatter.warning(f"File not found: {filepath}")
        return 0

    data = load_json(filepath)
    source_type = infer_source_type(filepath.name)
    updated_count = 0

    # Handle different metadata structures
    if isinstance(data, list) and data:
        # Bundle format: [{"posts": [...], "tags": {...}, ...}]
        bundle = data[0]
        if "posts" in bundle:
            items = bundle["posts"]
            for item in items:
                if not isinstance(item, dict):
                    continue

                # Extract existing tags (slug-based)
                existing_tags = extract_tag_slugs(item)

                # Build new tags with defaults
                new_tags = build_tags_for_resource(
                    resource_type="article",
                    source_type=source_type,
                    metadata_tags=existing_tags,
                )

                # Add tags_yaml field
                item["tags_yaml"] = new_tags
                updated_count += 1
    elif isinstance(data, dict):
        # Single resource or dict with resources
        if "resources" in data:
            items = data["resources"]
        else:
            items = [data]

        for item in items:
            if not isinstance(item, dict):
                continue

            existing_tags = extract_tag_slugs(item)
            new_tags = build_tags_for_resource(
                resource_type="article",
                source_type=source_type,
                metadata_tags=existing_tags,
            )

            item["tags_yaml"] = new_tags
            updated_count += 1

    # Write back
    save_json(filepath, data)

    return updated_count


def main():
    """Enrich all metadata files with tags."""
    formatter = OutputFormatter()
    metadata_dir = get_metadata_dir()

    if not metadata_dir.exists():
        formatter.error(f"Metadata directory not found: {metadata_dir}")
        return 1

    formatter.header("Enriching metadata with tags")
    print()

    metadata_files = [
        "yc_library_metadata.json",
        "yc_blog_metadata.json",
        "pg_essays_metadata.json",
        "altman_essays_metadata.json",
        "yc_startup_school_metadata.json",
    ]

    total_updated = 0
    for filename in metadata_files:
        filepath = metadata_dir / filename
        if filepath.exists():
            formatter.subheader(f"Processing {filename}")
            updated = enrich_metadata_file(filepath, formatter)
            formatter.info(f"Added tags_yaml to {updated} resources")
            total_updated += updated
        else:
            formatter.warning(f"Skipping {filename} (not yet created)")

    print()
    formatter.stats("Results", {"Total resources updated": total_updated})
    formatter.done()
    return 0


if __name__ == "__main__":
    sys.exit(main())
