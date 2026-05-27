#!/usr/bin/env python3
"""
fetch_altman_essays.py — Fetch Sam Altman's essays from blog.samaltman.com.

This script downloads all essays from Sam Altman's blog (via Atom feed) and
converts them to Markdown files, following the same pattern as PG essays.

Behavior:
- Append-only by default: existing essays are skipped (idempotent)
- Use --force to re-fetch all essays (dev mode)
- Creates altman_essays_audit.json with fetch statistics

Usage:
    python scripts/fetch_altman_essays.py [--force] [--output-dir PATH]

Examples:
    # Append-only mode (default): skip existing essays
    python scripts/fetch_altman_essays.py

    # Force refresh: re-fetch all essays
    python scripts/fetch_altman_essays.py --force

    # Custom output directory
    python scripts/fetch_altman_essays.py --output-dir /custom/path
"""

import argparse
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.yclib_extract.pipeline import PipelineOrchestrator


def main():
    parser = argparse.ArgumentParser(description="Fetch Sam Altman essays from blog.samaltman.com")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force refresh: re-fetch all essays (default: append-only)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Custom output directory for essays (env: SA_ESSAYS_DIR)",
    )

    args = parser.parse_args()

    # Set environment variable if output-dir provided
    if args.output_dir:
        os.environ["SA_ESSAYS_DIR"] = args.output_dir

    # Create orchestrator and fetch essays
    orch = PipelineOrchestrator()

    print(f"🚀 Fetching Sam Altman essays...")
    print(f"   Output directory: {orch.sa_essays_dir}")
    print(f"   Mode: {'force refresh' if args.force else 'append-only'}")
    print()

    try:
        stats = orch.fetch_sa_essays(force=args.force)

        print()
        print("✅ Done!")
        print(f"\n📊 Results:")
        print(f"  Fetched: {stats['fetched']}")
        print(f"  Skipped (existing): {stats['skipped_existing']}")
        print(f"  Failed: {stats['failed']}")

        # Return non-zero if any failed
        return 1 if stats["failed"] > 0 else 0

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
