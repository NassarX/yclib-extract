#!/usr/bin/env python3
"""Generate quality report for the extracted library."""

import sys
from collections import Counter
from pathlib import Path

# Add project root to sys.path before imports
_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / "src"))

from scripts.shared import load_csv, OutputFormatter


def generate_quality_report(audit_csv: str = "artifacts/resources_audit.csv"):
    """Print a summary of extraction quality across all sources."""
    formatter = OutputFormatter()
    
    audit_path = Path(audit_csv)
    if not audit_path.exists():
        formatter.error(f"Audit file {audit_csv} not found.")
        return 1

    rows = load_csv(audit_path)
    
    formatter.header(f"Quality Report ({len(rows)} resources)")
    print()

    # 1. Quality Levels
    quality_counts = Counter(r["quality_level"] for r in rows)
    print("Quality Levels:")
    for level, count in quality_counts.most_common():
        pct = (count / len(rows)) * 100
        print(f"  - {level:10}: {count:4} ({pct:4.1f}%)")

    # 2. Source Breakdown
    source_counts = Counter(r["source"] for r in rows)
    print("\nSource Breakdown:")
    for source, count in source_counts.most_common():
        print(f"  - {source:15}: {count:4}")

    # 3. Status
    status_counts = Counter(r["status"] for r in rows)
    print("\nExtraction Status:")
    for status, count in status_counts.most_common():
        print(f"  - {status:15}: {count:4}")

    # 4. Warnings
    all_warnings = []
    for r in rows:
        if r.get("warnings"):
            all_warnings.extend(w.strip() for w in r["warnings"].split(","))

    if all_warnings:
        warning_counts = Counter(all_warnings)
        print("\nCommon Warnings:")
        for warn, count in warning_counts.most_common(5):
            print(f"  - {warn:20}: {count:4}")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(generate_quality_report())
