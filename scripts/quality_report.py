"""Generate quality report for the extracted library."""

import csv
from collections import Counter
from pathlib import Path


def generate_quality_report(audit_csv: str = "artifacts/resources_audit.csv"):
    """Print a summary of extraction quality across all sources."""
    if not Path(audit_csv).exists():
        print(f"Error: Audit file {audit_csv} not found.")
        return

    rows = []
    with open(audit_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"--- Quality Report ({len(rows)} resources) ---\n")

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
        if r["warnings"]:
            all_warnings.extend(w.strip() for w in r["warnings"].split(","))

    if all_warnings:
        warning_counts = Counter(all_warnings)
        print("\nCommon Warnings:")
        for warn, count in warning_counts.most_common(5):
            print(f"  - {warn:20}: {count:4}")


if __name__ == "__main__":
    generate_quality_report()
