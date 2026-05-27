"""Interactive init command for first-run setup.

Guides users through:
1. Algolia credential strategy selection
2. Transcript support preference
3. Validation and .env file generation
"""

import sys
from pathlib import Path

from ..config import Config


def prompt_yes_no(question: str, default: bool = True) -> bool:
    """Prompt user for yes/no answer.

    Args:
        question: Question to ask
        default: Default answer if user just presses Enter

    Returns:
        True for yes, False for no
    """
    default_str = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input(f"{question} {default_str}: ").strip().lower()
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please enter 'y' or 'n'")


def prompt_choice(question: str, choices: list[str]) -> str:
    """Prompt user to select from choices.

    Args:
        question: Question to ask
        choices: List of valid choices

    Returns:
        Selected choice
    """
    print(f"\n{question}")
    for i, choice in enumerate(choices, 1):
        print(f"  {i}) {choice}")

    while True:
        answer = input("Select option (number): ").strip()
        try:
            idx = int(answer) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass
        print(f"Please enter a number between 1 and {len(choices)}")


def run_init(output_path: str = ".env") -> int:
    """Run interactive setup for new users.

    Args:
        output_path: Where to save .env file (default: .env)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    print("\n" + "=" * 60)
    print("yclib-extract first-run setup")
    print("=" * 60)

    print("\nThis will create a .env file with your configuration.")
    print("You can always edit it manually later.\n")

    # Step 1: Algolia credentials
    print("\nStep 1: Algolia Credentials")
    print("-" * 40)
    print("""The YC Library uses Algolia for search. You have three options:

1. Use hardcoded defaults (recommended)
   - Uses public credentials baked into the app
   - Works immediately, no setup needed

2. Manual copy from DevTools
   - Open https://www.ycombinator.com/library/search in browser
   - DevTools → Network → filter by "algolia"
   - Copy headers: X-Algolia-Application-Id and X-Algolia-API-Key
   - Paste them when prompted

3. AI agent (using Copilot/Claude)
   - Provide a prompt to your AI agent to use Playwright
   - Agent will extract credentials from browser automatically
   - More complex but fully automated""")

    algolia_choice = prompt_choice(
        "Which Algolia credential method?",
        [
            "Use hardcoded defaults",
            "Manually copy from DevTools",
            "Use AI agent with Playwright",
        ],
    )

    algolia_app_id = None
    algolia_api_key = None

    if algolia_choice == "Manually copy from DevTools":
        algolia_app_id = input("\nEnter Algolia App ID (X-Algolia-Application-Id): ").strip()
        if not algolia_app_id:
            print("ERROR: App ID is required")
            return 1

        algolia_api_key = input("Enter Algolia API Key (X-Algolia-API-Key): ").strip()
        if not algolia_api_key:
            print("ERROR: API Key is required")
            return 1
    elif algolia_choice == "Use AI agent with Playwright":
        print("""
When using an AI agent (like Copilot), provide this prompt:

---
I need to extract Algolia credentials from the YC Library search page.

Use Playwright to:
1. Navigate to https://www.ycombinator.com/library/search
2. Wait for the page to load
3. Open DevTools Network tab (via Playwright's context)
4. Make a search request (type something in the search box)
5. Capture the "algolia" network request headers
6. Extract X-Algolia-Application-Id and X-Algolia-API-Key

Store the credentials and update .env file with:
  ALGOLIA_APP_ID=<value>
  ALGOLIA_API_KEY=<value>
---
""")
        input("Press Enter once you've saved the .env with AI agent...")

    # Step 2: Transcript support
    print("\nStep 2: Transcript Support")
    print("-" * 40)
    print("""Transcript extraction is optional. If enabled, the tool will:
- Extract transcripts from YouTube videos in posts
- Append them to the generated Markdown
- Fall back gracefully if transcripts aren't available

This requires youtube-transcript-api and optionally yt-dlp.""")

    enable_transcripts = prompt_yes_no("Enable transcript extraction?", default=True)

    # Create config with collected answers
    print("\nStep 3: Verification")
    print("-" * 40)

    config = Config(
        algolia_app_id=algolia_app_id,
        algolia_api_key=algolia_api_key,
        load_env=False,
    )

    print("\nConfiguration summary:")
    for key, value in config.to_dict().items():
        if value is not None:
            print(f"  {key}: {value}")

    if not prompt_yes_no("\nDoes this look correct?", default=True):
        print("Setup cancelled. No changes made.")
        return 1

    # Save to .env
    config.save_to_env_file(output_path)
    print(f"\n✓ Configuration saved to {output_path}")

    # Print next steps
    print("\nNext steps:")
    print("-" * 40)
    if enable_transcripts:
        print("1. Install with transcript support:")
        print("   pip install -e .[transcripts]")
    else:
        print("1. Install without transcript support:")
        print("   pip install -e .")

    print("\n2. Start the extraction pipeline:")
    print("   yclib-extract pipeline")
    print("\n3. Check artifacts/ directory for results:")
    print("   - artifacts/yc_library_metadata.json (post metadata)")
    print("   - artifacts/yc_library/ (extracted content as Markdown)")

    print("\n" + "=" * 60)
    print("Setup complete! 🎉")
    print("=" * 60 + "\n")

    return 0
