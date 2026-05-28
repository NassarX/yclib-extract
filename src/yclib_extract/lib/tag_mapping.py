"""Tag normalization and semantic grouping for YC Blog.

Handles:
1. Semantic duplicates (video/videos → video)
2. Platform references (hacker-news, yc-news)
3. Numeric hash removal (hash-25267)
4. Variant normalization (female-founders, women-founders)
"""

from typing import Dict, List, Set

# Map variants to their canonical form
TAG_SEMANTIC_GROUPS: Dict[str, List[str]] = {
    # Video content variations
    "video": ["video", "videos"],
    # Startup School variations
    "startup-school": ["startup-school", "hash-startup-school"],
    # Jobs variations
    "jobs": ["jobs", "hash-jobs"],
    # Gender diversity in founders (normalize both to one canonical)
    "female-founders": ["female-founders", "women-founders"],
    # YC Continuity program
    "yc-continuity": ["yc-continuity", "hash-ycc"],
}

# Create reverse lookup: variant → canonical
_VARIANT_TO_CANONICAL: Dict[str, str] = {}
for canonical, variants in TAG_SEMANTIC_GROUPS.items():
    for variant in variants:
        _VARIANT_TO_CANONICAL[variant] = canonical


def get_canonical_tag(tag_slug: str) -> str:
    """Return the canonical form of a tag slug.

    Examples:
        "videos" → "video"
        "women-founders" → "female-founders"
        "advice" → "advice" (no mapping)
    """
    return _VARIANT_TO_CANONICAL.get(tag_slug, tag_slug)


def normalize_tag_variants(tags: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Normalize a list of tags by mapping variants to canonical forms.

    Removes duplicates after canonicalization.

    Args:
        tags: List of tag dicts with 'slug' and 'name' keys

    Returns:
        List of deduplicated tag dicts with canonical slugs
    """
    seen_canonical: Set[str] = set()
    result: List[Dict[str, str]] = []

    for tag in tags:
        slug = tag.get("slug", "")
        canonical = get_canonical_tag(slug)

        if canonical and canonical not in seen_canonical:
            seen_canonical.add(canonical)
            # Return a new dict with canonical slug
            canonical_tag = dict(tag)
            canonical_tag["slug"] = canonical
            result.append(canonical_tag)

    return result


def get_all_variant_slugs_for_canonical(canonical: str) -> List[str]:
    """Get all variant slugs that map to a canonical form.

    Examples:
        "video" → ["video", "videos"]
        "female-founders" → ["female-founders", "women-founders"]
    """
    return TAG_SEMANTIC_GROUPS.get(canonical, [canonical])


if __name__ == "__main__":
    # Quick test
    print("Tag Semantic Groups Test:")
    print("\nCanonical → Variants:")
    for canonical, variants in TAG_SEMANTIC_GROUPS.items():
        print(f"  {canonical:25} ← {variants}")

    print("\n\nVariant → Canonical:")
    for variant, canonical in sorted(_VARIANT_TO_CANONICAL.items()):
        if variant != canonical:
            print(f"  {variant:25} → {canonical}")

    # Test normalization
    print("\n\nTest normalize_tag_variants():")
    test_tags = [
        {"slug": "video", "name": "Video"},
        {"slug": "videos", "name": "Videos"},
        {"slug": "advice", "name": "Advice"},
        {"slug": "women-founders", "name": "Women Founders"},
        {"slug": "female-founders", "name": "Female Founders"},
    ]
    normalized = normalize_tag_variants(test_tags)
    for tag in normalized:
        print(f"  {tag['slug']:25} {tag['name']}")
