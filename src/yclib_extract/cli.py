import argparse
import sys
from pathlib import Path

from . import __version__

ARTIFACTS_DIR = Path("artifacts")
METADATA_DIR = ARTIFACTS_DIR / "metadata"
DEFAULT_METADATA_DIR = str(METADATA_DIR / "yc_library_metadata.json")
DEFAULT_CONTENT_DIR = str(ARTIFACTS_DIR / "yc_library")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="yclib-extract: Discover and extract YC Library content",
        prog="yclib-extract",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Discover posts via Algolia")
    scrape_parser.add_argument("--output-dir", default=DEFAULT_METADATA_DIR)
    scrape_parser.add_argument("--algolia-app-id", help="Algolia app ID")
    scrape_parser.add_argument("--algolia-api-key", help="Algolia API key")
    scrape_parser.add_argument("--algolia-index", default="library_posts")

    # Extract command
    extract_parser = subparsers.add_parser("extract", help="Extract content from posts")
    extract_parser.add_argument("--input-dir", default=DEFAULT_METADATA_DIR)
    extract_parser.add_argument("--output-dir", default=DEFAULT_CONTENT_DIR)
    extract_parser.add_argument("--workers", type=int, default=4)
    extract_parser.add_argument("--force", action="store_true")
    extract_parser.add_argument("--retry-failed-only", action="store_true")
    extract_parser.add_argument("--audit-only", action="store_true")

    # Pipeline command
    pipeline_parser = subparsers.add_parser(
        "pipeline", help="Run discovery, extraction, and audits as one pipeline"
    )
    pipeline_parser.add_argument("--metadata-dir", default=DEFAULT_METADATA_DIR)
    pipeline_parser.add_argument("--output-dir", default=DEFAULT_CONTENT_DIR)
    pipeline_parser.add_argument("--workers", type=int, default=4)
    pipeline_parser.add_argument("--mode", choices=["weekly", "dev"], default="weekly")
    pipeline_parser.add_argument(
        "--start-stage", choices=["discover", "extract", "audit"], default="discover"
    )
    pipeline_parser.add_argument("--replay", action="store_true")
    pipeline_parser.add_argument("--force", action="store_true")
    pipeline_parser.add_argument("--retry-failed-only", action="store_true")
    pipeline_parser.add_argument("--algolia-app-id", help="Algolia app ID")
    pipeline_parser.add_argument("--algolia-api-key", help="Algolia API key")
    pipeline_parser.add_argument(
        "--workflow",
        choices=["startup_school", "full"],
        help="Run a specialised workflow: 'startup_school' or 'full' (all sources)",
    )
    pipeline_parser.add_argument("--algolia-index", default="library_posts")

    # Init command
    init_parser = subparsers.add_parser("init", help="Interactive first-run setup")
    init_parser.add_argument(
        "--output", default=".env", help="Where to save .env file (default: .env)"
    )

    # Fetch command
    fetch_parser = subparsers.add_parser("fetch", help="Fetch specific content modules directly")
    fetch_subparsers = fetch_parser.add_subparsers(dest="target", help="Content target")

    pg_parser = fetch_subparsers.add_parser("pg", help="Fetch Paul Graham essays")
    pg_parser.add_argument("--force", action="store_true", help="Force re-fetch")

    sa_parser = fetch_subparsers.add_parser("altman", help="Fetch Sam Altman essays")
    sa_parser.add_argument("--force", action="store_true", help="Force re-fetch")

    # Build command
    build_parser = subparsers.add_parser("build", help="Build curated outputs")
    build_subparsers = build_parser.add_subparsers(dest="target", help="Build target")

    school_parser = build_subparsers.add_parser(
        "startup-school", help="Build standalone curriculum"
    )
    school_parser.add_argument("--ensure-local", action="store_true", help="Download missing files")
    school_parser.add_argument("--cleanup-orphans", action="store_true", help="Remove unused files")
    school_parser.add_argument("--collect", action="store_true", help="Copy all files to output")
    school_parser.add_argument("--force", action="store_true", help="Force overwrite")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "scrape":
        from .scraper import AlgoliaScraper

        scraper = AlgoliaScraper(
            app_id=args.algolia_app_id,
            api_key=args.algolia_api_key,
            index_name=args.algolia_index,
        )
        print(f"Discovering posts from Algolia ({args.algolia_index})...")
        posts = scraper.browse_all()
        print(f"Found {len(posts)} posts")
        scraper.save_posts(posts, args.output_dir)
        print(f"Saved to {args.output_dir}/")

    elif args.command == "extract":
        from .extractor import ContentExtractor

        extractor = ContentExtractor(output_dir=args.output_dir)
        if args.audit_only:
            print("Audit mode: no changes")
            return 0
        extractor.process_posts(
            args.input_dir,
            workers=args.workers,
            force=args.force,
            retry_failed_only=args.retry_failed_only,
        )

    elif args.command == "pipeline":
        from .pipeline import PipelineOrchestrator

        orchestrator = PipelineOrchestrator(
            metadata_dir=args.metadata_dir,
            content_dir=args.output_dir,
            workers=args.workers,
            algolia_app_id=args.algolia_app_id,
            algolia_api_key=args.algolia_api_key,
            algolia_index=args.algolia_index,
        )
        # handle specialised workflows
        workflow = getattr(args, "workflow", None)
        if workflow == "startup_school":
            orchestrator.run_startup_school(
                replay=args.replay, force=(args.mode == "dev" or args.replay)
            )
        elif workflow == "full":
            orchestrator.run_full(force=args.force, replay=args.replay)
        else:
            orchestrator.run(
                start_stage=args.start_stage,
                mode=args.mode,
                replay=args.replay,
                retry_failed_only=args.retry_failed_only,
            )

    elif args.command == "fetch":
        from .pipeline import PipelineOrchestrator

        orchestrator = PipelineOrchestrator()
        if args.target == "pg":
            print("🚀 Fetching Paul Graham essays...")
            orchestrator.fetch_pg_essays(force=args.force)
        elif args.target == "altman":
            print("🚀 Fetching Sam Altman essays...")
            orchestrator.fetch_sa_essays(force=args.force)
        else:
            fetch_parser.print_help()
            return 1

    elif args.command == "build":
        if args.target == "startup-school":
            # Delegate to the standalone curriculum builder script
            import subprocess
            import sys

            script_path = Path(__file__).parent.parent.parent / "scripts" / "build_curriculum.py"
            cmd = [sys.executable, str(script_path)]
            if args.ensure_local:
                cmd.append("--ensure-local")
            if args.cleanup_orphans:
                cmd.append("--cleanup-orphans")
            if args.collect:
                cmd.append("--collect")
            if args.force:
                cmd.append("--force")

            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as e:
                return e.returncode
        else:
            build_parser.print_help()
            return 1

    elif args.command == "init":
        from .commands.init import run_init

        return run_init(output_path=args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
