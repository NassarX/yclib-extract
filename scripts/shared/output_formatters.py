"""Output formatting utilities for consistent script output."""

from typing import Any, Dict


class OutputFormatter:
    """Standardized output formatting for scripts."""

    @staticmethod
    def header(title: str, emoji: str = "🚀") -> None:
        """Print a formatted header."""
        print(f"\n{emoji} {title}")

    @staticmethod
    def subheader(title: str, indent: int = 3) -> None:
        """Print a formatted subheader."""
        print(" " * indent + f"• {title}")

    @staticmethod
    def success(message: str, emoji: str = "✅") -> None:
        """Print a success message."""
        print(f"{emoji} {message}")

    @staticmethod
    def error(message: str, emoji: str = "❌") -> None:
        """Print an error message."""
        print(f"{emoji} {message}")

    @staticmethod
    def warning(message: str, emoji: str = "⚠️") -> None:
        """Print a warning message."""
        print(f"{emoji} {message}")

    @staticmethod
    def stats(title: str, stats_dict: Dict[str, Any], emoji: str = "📊") -> None:
        """Print a formatted stats section."""
        print(f"\n{emoji} {title}:")
        for key, value in stats_dict.items():
            # Convert snake_case to Title Case
            label = key.replace("_", " ").title()
            print(f"  {label}: {value}")

    @staticmethod
    def table(title: str, rows: list, columns: list = None, emoji: str = "📋") -> None:
        """Print a formatted table.
        
        Args:
            title: Table title
            rows: List of dicts with row data
            columns: List of column names to display (if None, use all keys from first row)
            emoji: Emoji prefix for title
        """
        if not rows:
            print(f"{emoji} {title}: (empty)")
            return

        if columns is None:
            columns = list(rows[0].keys())

        print(f"\n{emoji} {title}:")
        # Print header
        header_line = " | ".join(str(col).ljust(15) for col in columns)
        print("  " + header_line)
        print("  " + "-" * len(header_line))

        # Print rows
        for row in rows:
            row_line = " | ".join(str(row.get(col, "")).ljust(15) for col in columns)
            print("  " + row_line)

    @staticmethod
    def info(message: str, emoji: str = "ℹ️") -> None:
        """Print an info message."""
        print(f"{emoji} {message}")

    @staticmethod
    def done(message: str = "Done!", emoji: str = "✅") -> None:
        """Print a completion message."""
        print(f"\n{emoji} {message}\n")
