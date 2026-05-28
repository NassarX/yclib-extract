"""Resource registry and configuration.

This module defines all resources (YC Library, PG Essays, Altman Essays, YC Blog, Startup School)
in a single, centralized location. Adding or removing resources requires changes ONLY here.

This is the single source of truth for:
- Resource metadata (names, directories, environment variables)
- Metadata file locations
- Default tags for each resource
- Directory paths
- Orchestrator methods to use

Usage:
    from scripts.shared.resource_registry import RESOURCES, get_resource
    
    # Get a specific resource
    pg_essays = get_resource("pg-essay")
    print(pg_essays.output_dir)
    
    # Iterate all resources
    for resource in RESOURCES:
        print(f"{resource.name}: {resource.metadata_file}")
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .path_utils import get_artifacts_dir, get_metadata_dir


@dataclass
class Resource:
    """Represents a content resource type."""

    # Identifier for this resource (used internally)
    slug: str

    # Human-readable name
    name: str

    # Output directory (where extracted markdown is stored)
    output_dir: str

    # Environment variable name for overriding output directory
    env_var: str

    # Metadata JSON filename (in artifacts/metadata/)
    metadata_file: str

    # Default tags for this resource (used in tag defaults)
    default_tags: List[str]

    # Pipeline orchestrator method to call (e.g., "fetch_pg_essays")
    orchestrator_method: Optional[str] = None

    # Whether this resource supports force refresh
    supports_force_refresh: bool = True

    # Brief description
    description: str = ""

    def get_output_path(self) -> Path:
        """Get the full output directory path."""
        return get_artifacts_dir() / self.output_dir

    def get_metadata_path(self) -> Path:
        """Get the full metadata file path."""
        return get_metadata_dir() / self.metadata_file

    def get_orchestrator_method_name(self) -> str:
        """Get the orchestrator method name (with fallback)."""
        if self.orchestrator_method:
            return self.orchestrator_method
        # Auto-generate from slug: "pg-essay" -> "fetch_pg_essays"
        parts = self.slug.split("-")
        return f"fetch_{'_'.join(parts)}s"


# ============================================================================
# ALL RESOURCES DEFINED HERE - Single source of truth
# ============================================================================

RESOURCES = [
    Resource(
        slug="yc-library",
        name="YC Library",
        output_dir="yc_library",
        env_var="YC_LIBRARY_DIR",
        metadata_file="yc_library_metadata.json",
        default_tags=["YC", "yc-library"],
        description="Y Combinator's curated library of business resources",
    ),
    Resource(
        slug="yc-blog",
        name="YC Blog",
        output_dir="yc_blog",
        env_var="YC_BLOG_DIR",
        metadata_file="yc_blog_metadata.json",
        default_tags=["YC", "yc-blog"],
        description="Official Y Combinator blog posts",
    ),
    Resource(
        slug="pg-essay",
        name="Paul Graham Essays",
        output_dir="pg_essays",
        env_var="PG_ESSAYS_DIR",
        metadata_file="pg_essays_metadata.json",
        default_tags=["essay", "pg"],
        orchestrator_method="fetch_pg_essays",
        description="Essays from Paul Graham (paulgraham.com)",
    ),
    Resource(
        slug="altman-essay",
        name="Sam Altman Essays",
        output_dir="altman_essays",
        env_var="SA_ESSAYS_DIR",
        metadata_file="altman_essays_metadata.json",
        default_tags=["essay", "altman"],
        orchestrator_method="fetch_sa_essays",
        description="Essays from Sam Altman (blog.samaltman.com)",
    ),
    Resource(
        slug="startup-school",
        name="Startup School",
        output_dir="yc_startup_school",
        env_var="YC_STARTUP_SCHOOL_DIR",
        metadata_file="yc_startup_school_metadata.json",
        default_tags=["YC", "startup-school"],
        supports_force_refresh=False,
        description="Y Combinator's Startup School curriculum",
    ),
]


def get_resource(slug: str) -> Optional[Resource]:
    """Get a resource by slug.
    
    Args:
        slug: Resource slug (e.g., "pg-essay", "yc-library")
    
    Returns:
        Resource object or None if not found
    """
    for resource in RESOURCES:
        if resource.slug == slug:
            return resource
    return None


def get_resource_by_name(name: str) -> Optional[Resource]:
    """Get a resource by human-readable name.
    
    Args:
        name: Resource name (e.g., "Paul Graham Essays")
    
    Returns:
        Resource object or None if not found
    """
    for resource in RESOURCES:
        if resource.name.lower() == name.lower():
            return resource
    return None


def get_resource_by_env_var(env_var: str) -> Optional[Resource]:
    """Get a resource by environment variable name.
    
    Args:
        env_var: Environment variable name (e.g., "PG_ESSAYS_DIR")
    
    Returns:
        Resource object or None if not found
    """
    for resource in RESOURCES:
        if resource.env_var == env_var:
            return resource
    return None


def get_resource_by_metadata_file(filename: str) -> Optional[Resource]:
    """Get a resource by metadata filename.
    
    Args:
        filename: Metadata filename (e.g., "pg_essays_metadata.json")
    
    Returns:
        Resource object or None if not found
    """
    for resource in RESOURCES:
        if resource.metadata_file == filename:
            return resource
    return None


def list_all_resources() -> List[Resource]:
    """Get all registered resources.
    
    Returns:
        List of all Resource objects
    """
    return RESOURCES.copy()


def list_resource_slugs() -> List[str]:
    """Get all resource slugs.
    
    Returns:
        List of all resource slugs
    """
    return [r.slug for r in RESOURCES]


def list_resource_names() -> List[str]:
    """Get all resource names.
    
    Returns:
        List of all human-readable resource names
    """
    return [r.name for r in RESOURCES]
