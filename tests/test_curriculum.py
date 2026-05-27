"""Tests for the Startup School curriculum builder."""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from scripts.build_curriculum import get_res_id, get_source_type, slugify

def test_slugify():
    """Test slugification of titles."""
    assert slugify("Do Things That Don't Scale") == "do-things-that-dont-scale"
    assert slugify("Why to Not Not Start a Startup") == "why-to-not-not-start-a-startup"
    assert slugify("Hello   World") == "hello-world"

def test_get_source_type():
    """Test source type detection from URLs."""
    assert get_source_type({"url": "https://paulgraham.com/foo.html"}) == "pg_essay"
    assert get_source_type({"url": "https://blog.samaltman.com/bar"}) == "sa_essay"
    assert get_source_type({"url": "https://www.ycombinator.com/library/123"}) == "yc_library"
    assert get_source_type({"url": "https://youtube.com/watch?v=123"}) == "startup_school"

def test_get_res_id_priority():
    """Test ID resolution priority."""
    # Priority 0: resolved_id
    res = {"title": "Title", "resolved_id": "fixed-id"}
    assert get_res_id(res) == "fixed-id"
    
    # Priority 1: slugified title
    res = {"title": "A Great Title"}
    assert get_res_id(res) == "a-great-title"
    
    # Priority 2: curriculum_url slug
    res = {"curriculum_url": "https://startupschool.org/curriculum/slug-from-url"}
    assert get_res_id(res) == "slug-from-url"

def test_curriculum_metadata_injection(tmp_path):
    """Test generating metadata JSON from curriculum items."""
    from scripts.build_curriculum import to_metadata_json
    
    res = {
        "title": "Test Resource",
        "author": "Test Author",
        "url": "https://example.com/test",
        "type": "video"
    }
    
    meta = to_metadata_json(res, "test-resource")
    
    assert meta["id"] == "test-resource"
    assert meta["title"] == "Test Resource"
    assert meta["author"] == "Test Author"
    assert "curriculum" in meta["tags"]
    assert meta["file"] == "test-resource.md"
