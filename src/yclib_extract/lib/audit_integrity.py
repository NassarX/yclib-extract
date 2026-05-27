"""Integrity and quality checks for the extracted library."""

import csv
import json
from pathlib import Path
from typing import Dict, List


def check_file_integrity(audit_csv: str = "artifacts/resources_audit.csv") -> Dict[str, int]:
    """Verify that all files listed in the audit CSV actually exist on disk."""
    stats = {"total": 0, "missing": 0, "exists": 0}

    if not Path(audit_csv).exists():
        print(f"Error: Audit file {audit_csv} not found.")
        return stats

    with open(audit_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats["total"] += 1
            file_path = row.get("file_path")
            if file_path and Path(file_path).exists():
                stats["exists"] += 1
            else:
                stats["missing"] += 1
                print(f"Missing file: {row.get('resource_id')} ({file_path})")

    return stats


def find_duplicate_slugs(metadata_dir: str = "artifacts/metadata") -> List[str]:
    """Identify duplicate IDs/slugs across different metadata sources."""
    slug_map = {}
    duplicates = []

    for meta_file in Path(metadata_dir).glob("*.json"):
        with open(meta_file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                posts = data.get("posts", [])
                for p in posts:
                    slug = p.get("id")
                    if slug:
                        if slug in slug_map and slug_map[slug] != meta_file.name:
                            duplicates.append(f"{slug} (in {slug_map[slug]} and {meta_file.name})")
                        else:
                            slug_map[slug] = meta_file.name
            except Exception:
                continue

    return duplicates


if __name__ == "__main__":
    print("Running integrity check...")
    stats = check_file_integrity()
    print(f"Results: {stats}")

    print("\nChecking for slug collisions...")
    dupes = find_duplicate_slugs()
    if dupes:
        print(f"Found {len(dupes)} collisions:")
        for d in dupes:
            print(f"  - {d}")
    else:
        print("No collisions found.")
