"""Shared utilities for yclib-extract scripts."""

from .cli_base import ResourceFetcherCLI
from .metadata_utils import (
    extract_tag_slugs,
    infer_source_type,
    load_csv,
    load_json,
    load_yaml,
    save_json,
)
from .output_formatters import OutputFormatter
from .path_utils import get_artifacts_dir, get_metadata_dir, get_project_root, setup_imports
from .resource_registry import (
    Resource,
    get_resource,
    get_resource_by_env_var,
    get_resource_by_metadata_file,
    get_resource_by_name,
    list_all_resources,
    list_resource_names,
    list_resource_slugs,
)

__all__ = [
    "ResourceFetcherCLI",
    "OutputFormatter",
    "setup_imports",
    "get_project_root",
    "get_artifacts_dir",
    "get_metadata_dir",
    "load_json",
    "save_json",
    "load_yaml",
    "load_csv",
    "infer_source_type",
    "extract_tag_slugs",
    "Resource",
    "get_resource",
    "get_resource_by_name",
    "get_resource_by_env_var",
    "get_resource_by_metadata_file",
    "list_all_resources",
    "list_resource_slugs",
    "list_resource_names",
]

