import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .config import Config
from .scraper import (
    DEFAULT_BLOG_METADATA_DIR,
    DEFAULT_BLOG_TAXONOMY_FILE,
    DEFAULT_YC_BLOG_CONDITIONAL_MIN_WORDS,
    DEFAULT_YC_BLOG_CONDITIONAL_TAGS,
    DEFAULT_YC_BLOG_EXCLUDE_TAGS,
    DEFAULT_YC_BLOG_INCLUDE_TAGS,
    YCBlogScraper,
    build_clean_taxonomy_from_posts,
    clean_metadata_record,
)

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

    # Scrape blog command (PoC + filtered metadata)
    scrape_blog_parser = subparsers.add_parser(
        "scrape-blog", help="Discover YC Blog posts via Algolia"
    )
    scrape_blog_parser.add_argument("--output-dir", default=DEFAULT_BLOG_METADATA_DIR)
    scrape_blog_parser.add_argument("--taxonomy-output", default=DEFAULT_BLOG_TAXONOMY_FILE)
    scrape_blog_parser.add_argument("--algolia-app-id", help="Algolia app ID")
    scrape_blog_parser.add_argument("--algolia-api-key", help="Algolia API key")
    scrape_blog_parser.add_argument("--algolia-index", help="Algolia index name")
    scrape_blog_parser.add_argument(
        "--include-tags",
        nargs="*",
        default=DEFAULT_YC_BLOG_INCLUDE_TAGS,
        help="Allowlist tags (defaults to Essay/Advice/Founder Stories/Startup School)",
    )
    scrape_blog_parser.add_argument(
        "--exclude-tags",
        nargs="*",
        default=DEFAULT_YC_BLOG_EXCLUDE_TAGS,
        help="Denylist tags (defaults to YC News/YC Events)",
    )
    scrape_blog_parser.add_argument(
        "--conditional-tags",
        nargs="*",
        default=DEFAULT_YC_BLOG_CONDITIONAL_TAGS,
        help="Conditional tags that require content-level checks",
    )
    scrape_blog_parser.add_argument(
        "--conditional-min-words",
        type=int,
        default=DEFAULT_YC_BLOG_CONDITIONAL_MIN_WORDS,
        help="Minimum words for conditional-tag posts",
    )
    scrape_blog_parser.add_argument(
        "--taxonomy-only",
        action="store_true",
        help="Only fetch and write taxonomy/category counts; do not persist filtered metadata",
    )
    scrape_blog_parser.add_argument(
        "--autodiscover-config",
        action="store_true",
        help="Attempt to auto-detect blog Algolia config from ycombinator.com/blog",
    )

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
        choices=["startup_school", "full", "yc_blog"],
        help="Run a specialised workflow: 'startup_school', 'yc_blog', or 'full' (all sources)",
    )
    pipeline_parser.add_argument("--algolia-index", default="library_posts")
    pipeline_parser.add_argument("--algolia-blog-index", default="ycdc_blog_production")
    pipeline_parser.add_argument(
        "--blog-include-tags",
        nargs="*",
        default=DEFAULT_YC_BLOG_INCLUDE_TAGS,
        help="YC Blog allowlist tags",
    )
    pipeline_parser.add_argument(
        "--blog-exclude-tags",
        nargs="*",
        default=DEFAULT_YC_BLOG_EXCLUDE_TAGS,
        help="YC Blog denylist tags (takes precedence)",
    )
    pipeline_parser.add_argument(
        "--blog-conditional-tags",
        nargs="*",
        default=DEFAULT_YC_BLOG_CONDITIONAL_TAGS,
        help="YC Blog tags requiring content-level checks",
    )
    pipeline_parser.add_argument(
        "--blog-conditional-min-words",
        type=int,
        default=DEFAULT_YC_BLOG_CONDITIONAL_MIN_WORDS,
        help="Minimum words for conditional YC Blog posts",
    )

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

    elif args.command == "scrape-blog":
        config = Config()
        scraper_kwargs = {
            "app_id": args.algolia_app_id or config.algolia_app_id,
            "api_key": args.algolia_api_key or config.algolia_blog_api_key,
            "index_name": args.algolia_index or config.algolia_blog_index,
        }
        if args.autodiscover_config:
            try:
                discovered = YCBlogScraper.discover_algolia_config()
                scraper_kwargs = {
                    "app_id": discovered["app_id"],
                    "api_key": discovered["api_key"],
                    "index_name": discovered["index_name"],
                }
            except Exception:
                pass

        scraper = YCBlogScraper(**scraper_kwargs)
        print(f"Discovering YC Blog posts from Algolia ({scraper.index_name})...")

        try:
            posts = scraper.browse_all()
        except Exception as e:
            print(f"⚠ Algolia failed ({e}), falling back to RSS feed + scraping...")
            posts = scraper.browse_all_from_rss()

        print(f"Found {len(posts)} blog posts")

        taxonomy_payload = build_clean_taxonomy_from_posts(posts)
        taxonomy_path = Path(args.taxonomy_output)
        taxonomy_path.parent.mkdir(parents=True, exist_ok=True)
        taxonomy_path.write_text(json.dumps(taxonomy_payload, indent=2))
        print(f"Wrote clean taxonomy to {args.taxonomy_output}")

        if not args.taxonomy_only:
            # Clean metadata before saving
            clean_posts = [clean_metadata_record(post) for post in posts]
            saved = scraper.save_posts(
                clean_posts,
                args.output_dir,
                include_tags=args.include_tags,
                exclude_tags=args.exclude_tags,
                conditional_tags=args.conditional_tags,
                conditional_min_words=args.conditional_min_words,
            )
            print(f"Saved {saved} filtered blog posts to {args.output_dir}")

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

        config = Config()
        orchestrator = PipelineOrchestrator(
            metadata_dir=args.metadata_dir,
            content_dir=args.output_dir,
            workers=args.workers,
            algolia_app_id=args.algolia_app_id or config.algolia_app_id,
            algolia_api_key=args.algolia_api_key or config.algolia_api_key,
            algolia_index=args.algolia_index or config.algolia_index,
            algolia_blog_index=args.algolia_blog_index or config.algolia_blog_index,
            algolia_blog_api_key=config.algolia_blog_api_key,
        )
        # handle specialised workflows
        workflow = getattr(args, "workflow", None)
        if workflow == "startup_school":
            orchestrator.run_startup_school(
                replay=args.replay, force=(args.mode == "dev" or args.replay)
            )
        elif workflow == "yc_blog":
            orchestrator.run_yc_blog(
                replay=args.replay,
                force=(args.mode == "dev" or args.replay),
                include_tags=args.blog_include_tags,
                exclude_tags=args.blog_exclude_tags,
                conditional_tags=args.blog_conditional_tags,
                conditional_min_words=args.blog_conditional_min_words,
            )
        elif workflow == "full":
            orchestrator.run_full(
                force=args.force,
                replay=args.replay,
                blog_include_tags=args.blog_include_tags,
                blog_exclude_tags=args.blog_exclude_tags,
                blog_conditional_tags=args.blog_conditional_tags,
                blog_conditional_min_words=args.blog_conditional_min_words,
            )
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
