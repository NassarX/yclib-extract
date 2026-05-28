"""Metadata file utilities for loading, saving, and processing metadata."""

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None


def load_json(filepath: Path) -> Any:
    """Load JSON file."""
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def save_json(filepath: Path, data: Any, indent: int = 2) -> None:
    """Save data to JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent)
        f.write("\n")


def load_yaml(filepath: Path) -> Any:
    """Load YAML file."""
    if yaml is None:
        raise ImportError("PyYAML is required: pip install PyYAML")
    with open(filepath, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_csv(filepath: Path) -> List[Dict[str, str]]:
    """Load CSV file into list of dicts."""
    rows = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows


def save_csv(filepath: Path, rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
    """Save list of dicts to CSV file."""
    if not rows:
        return

    if fieldnames is None:
        fieldnames = list(rows[0].keys())

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def infer_source_type(filename: str) -> str:
    """Infer source type from metadata filename.
    
    Returns:
        Source type slug (e.g., 'yc-library', 'pg-essay', 'yc-blog')
    """
    mapping = {
        "yc_library_metadata.json": "yc-library",
        "yc_blog_metadata.json": "yc-blog",
        "pg_essays_metadata.json": "pg-essay",
        "altman_essays_metadata.json": "altman-essay",
        "yc_startup_school_metadata.json": "startup-school",
    }
    return mapping.get(filename, "article")


def extract_tag_slugs(item: Dict[str, Any]) -> List[str]:
    """Extract tag slugs from resource, handling different formats.
    
    Formats supported:
    - List of tag dicts: [{"name": "...", "slug": "...", "url": "..."}]
    - List of strings: ["tag1", "tag2"]
    - Existing tags_yaml field
    
    Args:
        item: Resource dict with potential 'tags', 'tags_yaml', or similar fields
    
    Returns:
        List of tag slugs
    """
    # Check for existing tags_yaml field (priority)
    if "tags_yaml" in item and isinstance(item["tags_yaml"], list):
        return item["tags_yaml"]

    # Extract from tags field (various formats)
    tags = item.get("tags", []) or []

    if not tags:
        return []

    result = []

    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, dict) and "slug" in tag:
                # Tag object with slug (YC Library/Blog format)
                result.append(tag["slug"])
            elif isinstance(tag, str):
                # String tag (essays/startup school format)
                result.append(tag)

    return result


def iterate_metadata_items(data: Any) -> Any:
    """Iterate over metadata items, handling different structures.
    
    Yields:
        Individual resource items from metadata structure
    """
    if isinstance(data, list) and data:
        # Bundle format: [{"posts": [...], "tags": {...}, ...}]
        bundle = data[0]
        if "posts" in bundle and isinstance(bundle["posts"], list):
            yield from bundle["posts"]
        else:
            yield from data
    elif isinstance(data, dict):
        if "resources" in data and isinstance(data["resources"], list):
            yield from data["resources"]
        else:
            # Single resource or resources at top level
            yield data
