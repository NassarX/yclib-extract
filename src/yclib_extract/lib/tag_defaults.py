"""Default and source-specific tags for all resources.

Ensures all resources have mandatory tags based on their source, plus any
metadata tags. Handles:
- YC Library: YC, yc-library + metadata tags
- YC Blog: YC, yc-blog + metadata tags
- Essays: essay + metadata tags (PG, Altman)
- Startup School: YC, startup-school + metadata tags
"""

from typing import Dict, List, Set

# Default tags by source type
SOURCE_DEFAULT_TAGS: Dict[str, List[str]] = {
    "yc-library": ["YC", "yc-library"],
    "yc-blog": ["YC", "yc-blog"],
    "essay": ["essay"],
    "pg-essay": ["essay", "pg"],
    "altman-essay": ["essay", "altman"],
    "startup-school": ["YC", "startup-school"],
}


def get_default_tags_for_source(source_type: str) -> List[str]:
    """Get default tags for a given source type.

    Args:
        source_type: One of 'yc-library', 'yc-blog', 'essay', 'startup-school'

    Returns:
        List of default tags for this source

    Examples:
        get_default_tags_for_source("yc-library") → ["YC", "yc-library"]
        get_default_tags_for_source("essay") → ["essay"]
    """
    # Normalize source type
    normalized = source_type.lower().strip()
    return SOURCE_DEFAULT_TAGS.get(normalized, [])


def merge_tags(
    metadata_tags: List[str],
    source_type: str,
    deduplicate: bool = True,
) -> List[str]:
    """Merge metadata tags with source-specific default tags.

    Default tags are prepended to maintain consistent ordering.

    Args:
        metadata_tags: Tags from post metadata (may be empty)
        source_type: Type of source (yc-library, yc-blog, essay, startup-school)
        deduplicate: Whether to remove duplicates (case-insensitive)

    Returns:
        List of merged tags with defaults first

    Examples:
        merge_tags(["advice", "essay"], "yc-blog")
        → ["YC", "yc-blog", "advice", "essay"]

        merge_tags([], "essay")
        → ["essay"]

        merge_tags(["Essay"], "essay", deduplicate=True)
        → ["essay"]  # Deduplicated (case-insensitive)
    """
    default_tags = get_default_tags_for_source(source_type)

    # Combine defaults + metadata tags
    all_tags = default_tags + metadata_tags

    if not deduplicate:
        return all_tags

    # Deduplicate while preserving order (case-insensitive)
    seen: Set[str] = set()
    result: List[str] = []

    for tag in all_tags:
        normalized = tag.lower().strip()
        if normalized not in seen:
            seen.add(normalized)
            result.append(tag)

    return result


def build_tags_for_resource(
    resource_type: str,
    source_type: str,
    metadata_tags: List[str] | None = None,
) -> List[str]:
    """Build final tags list for a resource.

    This is the main entry point for adding tags to any resource.

    Args:
        resource_type: Type of resource being tagged
        source_type: Source (yc-library, yc-blog, essay, startup-school)
        metadata_tags: Tags extracted from metadata (optional)

    Returns:
        Complete list of tags for the resource
    """
    if metadata_tags is None:
        metadata_tags = []

    # Normalize and clean metadata tags
    clean_metadata_tags = [
        tag.strip().lower() for tag in metadata_tags if tag and isinstance(tag, str)
    ]

    return merge_tags(clean_metadata_tags, source_type)


if __name__ == "__main__":
    print("Tag Defaults Test:\n")

    # Test 1: YC Library with metadata tags
    result = build_tags_for_resource("article", "yc-library", ["advice", "fundraising"])
    print(f"YC Library + advice/fundraising: {result}")
    assert "YC" in result and "yc-library" in result and "advice" in result

    # Test 2: Essay with no metadata tags
    result = build_tags_for_resource("article", "essay", [])
    print(f"Essay (no metadata): {result}")
    assert result == ["essay"]

    # Test 3: YC Blog with metadata tags
    result = build_tags_for_resource("article", "yc-blog", ["startup-school", "video"])
    print(f"YC Blog + startup-school/video: {result}")
    assert "YC" in result and "yc-blog" in result

    # Test 4: Startup School with deduplication
    result = build_tags_for_resource("article", "startup-school", ["yc", "YC"])
    print(f"Startup School with duplicate YC: {result}")
    assert result.count("yc") + result.count("YC") == 1  # Only one variant

    # Test 5: PG Essay
    result = build_tags_for_resource("article", "pg-essay", [])
    print(f"PG Essay: {result}")
    assert "essay" in result and "pg" in result

    print("\n✅ All tests passed!")
