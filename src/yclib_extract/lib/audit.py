"""Unified audit generation for YC Library and all extraction pipelines."""

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class UnifiedAudit:
    """Generate unified audit CSV for all extracted resources."""

    AUDIT_COLUMNS = [
        "resource_id",
        "source",
        "title",
        "url",
        "status",
        "quality_level",
        "content_length",
        "word_count",
        "reading_time",
        "published_at",
        "warnings",
        "extracted_at",
        "file_path",
    ]

    def __init__(self, audit_path: str = "artifacts/resources_audit.csv"):
        self.audit_path = Path(audit_path)
        self.entries: List[Dict] = []

    def add_entry(
        self,
        resource_id: str,
        source: str,
        metadata: dict,
        quality_metrics: dict,
        file_path: Optional[str] = None,
    ):
        """Add audit entry for extracted resource.

        Args:
            resource_id: Unique resource identifier
            source: Source type (yc_library, pg_essays, altman_essays, youtube)
            metadata: Resource metadata
            quality_metrics: Quality tracking metrics
            file_path: Path to extracted file
        """
        entry = {
            "resource_id": resource_id,
            "source": source,
            "title": metadata.get("title", ""),
            "url": metadata.get("url", ""),
            "status": metadata.get("status", "done"),
            "quality_level": quality_metrics.get("quality_level", "unknown"),
            "content_length": quality_metrics.get("content_length", 0),
            "word_count": quality_metrics.get("word_count", 0),
            "reading_time": metadata.get("reading_time", ""),
            "published_at": metadata.get("published_at") or metadata.get("published", ""),
            "warnings": ", ".join(quality_metrics.get("warnings", [])),
            "extracted_at": datetime.now().isoformat(),
            "file_path": file_path or "",
        }
        self.entries.append(entry)

    def write_audit(self):
        """Write audit CSV to disk."""
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.audit_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.AUDIT_COLUMNS)
            writer.writeheader()
            writer.writerows(self.entries)

    def get_statistics(self) -> dict:
        """Get audit statistics.

        Returns:
            Dict with counts by status, quality level, source
        """
        stats = {
            "total": len(self.entries),
            "by_status": {},
            "by_quality": {},
            "by_source": {},
            "total_content_length": 0,
            "total_word_count": 0,
        }

        for entry in self.entries:
            # Count by status
            status = entry["status"]
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

            # Count by quality
            quality = entry["quality_level"]
            stats["by_quality"][quality] = stats["by_quality"].get(quality, 0) + 1

            # Count by source
            source = entry["source"]
            stats["by_source"][source] = stats["by_source"].get(source, 0) + 1

            # Aggregate metrics
            stats["total_content_length"] += entry["content_length"]
            stats["total_word_count"] += entry["word_count"]

        return stats
