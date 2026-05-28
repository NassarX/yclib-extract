"""Base class for resource-specific CLI scripts."""

import argparse
import sys
from pathlib import Path
from typing import Callable, Dict, Optional

from .output_formatters import OutputFormatter
from .path_utils import setup_imports


class ResourceFetcherCLI:
    """Base class for resource fetching scripts (PG essays, Altman essays, etc.).
    
    Subclasses should override:
    - get_description() -> str
    - get_default_output_dir_env() -> str
    - run_fetch(force: bool) -> Dict[str, int]
    """

    def __init__(self, resource_name: str):
        """Initialize the CLI.
        
        Args:
            resource_name: Human-readable name (e.g., "Paul Graham essays")
        """
        self.resource_name = resource_name
        self.formatter = OutputFormatter()

    def get_description(self) -> str:
        """Get the script description for argparse."""
        return f"Fetch {self.resource_name}"

    def get_default_output_dir_env(self) -> str:
        """Get the environment variable name for output directory."""
        # Default: convert "Paul Graham essays" to PG_ESSAYS_DIR
        raise NotImplementedError("Subclass must implement get_default_output_dir_env()")

    def run_fetch(self, force: bool = False) -> Dict[str, int]:
        """Run the fetch operation.
        
        Args:
            force: Whether to force refresh (re-fetch all)
        
        Returns:
            Dict with stats: {'fetched': N, 'skipped_existing': N, 'failed': N}
        """
        raise NotImplementedError("Subclass must implement run_fetch()")

    def setup_parser(self) -> argparse.ArgumentParser:
        """Create argument parser."""
        parser = argparse.ArgumentParser(description=self.get_description())
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force refresh: re-fetch all (default: append-only)",
        )
        parser.add_argument(
            "--output-dir",
            type=str,
            default=None,
            help=f"Custom output directory (env: {self.get_default_output_dir_env()})",
        )
        return parser

    def main(self) -> int:
        """Main entry point."""
        setup_imports()

        parser = self.setup_parser()
        args = parser.parse_args()

        self.formatter.header(f"Fetching {self.resource_name}")
        self.formatter.info(f"Mode: {'force refresh' if args.force else 'append-only'}")
        print()

        try:
            stats = self.run_fetch(force=args.force)

            self.formatter.stats("Results", stats)
            self.formatter.done()

            return 1 if stats.get("failed", 0) > 0 else 0

        except Exception as e:
            self.formatter.error(str(e))
            import traceback
            traceback.print_exc()
            return 1
