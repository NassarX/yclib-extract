import json

from yclib_extract.scraper import (
    AlgoliaScraper,
    build_taxonomy_from_posts,
    classify_by_tag_cascade,
    passes_conditional_content_filter,
    should_include_by_tags,
)


def test_normalize_hit_supports_multiple_url_fields():
    scraper = AlgoliaScraper(app_id="app", api_key="key")

    normalized = scraper._normalize_hit(
        {
            "objectID": "123",
            "shared_search_path": "/library/posts/abc",
            "link": "https://youtu.be/abc123",
            "name": "Post title",
            "company_name": "Company",
            "author": "Author",
            "date": "2024-01-01",
            "content": "Description",
            "tags": ["yc"],
            "media_type": "video",
        }
    )

    assert normalized["id"] == "post-title"
    assert normalized["algolia_id"] == "123"
    assert normalized["url"] == "https://www.ycombinator.com/library/posts/abc"
    assert normalized["media_url"] == "https://youtu.be/abc123"
    assert normalized["title"] == "Post title"
    assert normalized["description"] == "Description"
    assert normalized["type"] == "Video"
    assert normalized["source_type"] == "Video"


def test_browse_all_collects_all_pages(monkeypatch):
    scraper = AlgoliaScraper(app_id="app", api_key="key")
    calls = []

    def fake_make_request(params):
        calls.append(params)
        if params["page"] == 0:
            return {"results": [{"hits": [{"objectID": "1"}], "nbPages": 2}]}
        return {"results": [{"hits": [{"objectID": "2"}], "nbPages": 2}]}

    monkeypatch.setattr(scraper, "_make_request", fake_make_request)

    assert scraper.browse_all(per_page=2) == [{"objectID": "1"}, {"objectID": "2"}]
    assert calls == [
        {
            "query": "",
            "hitsPerPage": 2,
            "page": 0,
            "attributesToRetrieve": ["*"],
            "attributesToHighlight": [],
            "analytics": False,
            "facets": ["id", "sus_curriculum", "media_type", "categories", "subcategories"],
            "sortFacetValuesBy": "alpha",
            "maxValuesPerFacet": 1000,
            "analyticsTags": ["ycdc", "library"],
            "restrictIndices": "Library_bookface_production",
            "tagFilters": [["ycdc_public", "kb_root_176", "kb_root_912"]],
        },
        {
            "query": "",
            "hitsPerPage": 2,
            "page": 1,
            "attributesToRetrieve": ["*"],
            "attributesToHighlight": [],
            "analytics": False,
            "facets": ["id", "sus_curriculum", "media_type", "categories", "subcategories"],
            "sortFacetValuesBy": "alpha",
            "maxValuesPerFacet": 1000,
            "analyticsTags": ["ycdc", "library"],
            "restrictIndices": "Library_bookface_production",
            "tagFilters": [["ycdc_public", "kb_root_176", "kb_root_912"]],
        },
    ]


def test_save_posts_writes_normalized_json(tmp_path):
    scraper = AlgoliaScraper(app_id="app", api_key="key")
    # Keep this unit test isolated from the repo's persisted ignore list.
    from yclib_extract import scraper as scraper_module

    scraper_module.load_ignore_sources = lambda: set()
    metadata_file = tmp_path / "metadata.json"
    scraper.save_posts(
        [
            {
                "objectID": "1",
                "url": "/library/posts/abc",
                "title": "Title",
            }
        ],
        str(metadata_file),
    )

    # Check consolidated JSON file format
    data = json.loads(metadata_file.read_text())
    assert "posts" in data
    assert len(data["posts"]) == 1
    saved = data["posts"][0]
    assert saved["url"] == "https://www.ycombinator.com/library/posts/abc"
    assert saved["media_url"] == ""
    assert saved["title"] == "Title"
    assert saved["file"] == "title.md"
    assert saved["type"] == "Article"
    assert saved["source_type"] == "Article"


def test_save_posts_keeps_video_media_url_separate(monkeypatch, tmp_path):
    scraper = AlgoliaScraper(app_id="app", api_key="key")
    monkeypatch.setattr("yclib_extract.scraper.load_ignore_sources", lambda: set())

    metadata_file = tmp_path / "metadata.json"
    scraper.save_posts(
        [
            {
                "objectID": "1",
                "shared_search_path": "/library/posts/abc",
                "link": "https://youtu.be/abc123",
                "title": "Video Title",
                "media_type": "video",
            }
        ],
        str(metadata_file),
    )

    # Check consolidated JSON file format
    data = json.loads(metadata_file.read_text())
    assert "posts" in data
    assert len(data["posts"]) == 1
    saved = data["posts"][0]
    assert saved["url"] == "https://www.ycombinator.com/library/posts/abc"
    assert saved["media_url"] == "https://youtu.be/abc123"
    assert saved["file"] == "video-title.md"


def test_save_posts_skips_ignored_sources(monkeypatch, tmp_path):
    scraper = AlgoliaScraper(app_id="app", api_key="key")
    monkeypatch.setattr(
        "yclib_extract.scraper.load_ignore_sources",
        lambda: {"https://www.ycombinator.com/library/posts/abc"},
    )

    saved_count = scraper.save_posts(
        [
            {
                "objectID": "1",
                "url": "/library/posts/abc",
                "title": "Ignored",
            }
        ],
        str(tmp_path),
    )

    assert saved_count == 0
    assert list(tmp_path.iterdir()) == []


def test_scraper_accepts_config():
    """Test AlgoliaScraper accepts Config object."""
    from yclib_extract.config import Config

    config = Config(
        algolia_app_id="custom-app",
        algolia_api_key="custom-key",
        algolia_index="custom-index",
        load_env=False,
    )

    scraper = AlgoliaScraper(config=config)
    assert scraper.app_id == "custom-app"
    assert scraper.api_key == "custom-key"
    assert scraper.index_name == "custom-index"


def test_scraper_cli_args_override_config():
    """Test CLI args override Config."""
    from yclib_extract.config import Config

    config = Config(
        algolia_app_id="config-app",
        algolia_api_key="config-key",
        load_env=False,
    )

    scraper = AlgoliaScraper(app_id="cli-app", config=config)
    assert scraper.app_id == "cli-app"
    assert scraper.api_key == "config-key"


def test_should_include_by_tags_exclusion_precedence():
    record = {
        "tags": ["Essay"],
        "categories": ["Startup School"],
        "subcategories": ["YC News"],
    }
    assert (
        should_include_by_tags(
            record,
            include_tags=["Essay", "Startup School"],
            exclude_tags=["YC News"],
        )
        is False
    )


def test_build_taxonomy_from_posts_counts_normalized_values():
    taxonomy = build_taxonomy_from_posts(
        [
            {"tags": ["Founder Stories", "Essay"]},
            {"tags": ["founder stories"], "categories": ["Startup School"]},
            {"subcategories": ["YC Events"]},
        ]
    )
    assert taxonomy["counts"]["tags"]["founder stories"] == 2
    assert taxonomy["counts"]["categories"]["startup school"] == 1
    assert taxonomy["counts"]["subcategories"]["yc events"] == 1


def test_classify_by_tag_cascade_respects_exclude_include_conditional():
    excluded = {"tags": ["essay", "yc news"]}
    included = {"tags": ["advice"]}
    conditional = {"tags": ["office hours", "founder stories"]}
    skipped = {"tags": ["unknown-tag"]}

    assert (
        classify_by_tag_cascade(
            excluded,
            include_tags=["advice", "essay"],
            exclude_tags=["yc news"],
            conditional_tags=["office hours", "founder stories"],
        )
        == "exclude"
    )
    assert (
        classify_by_tag_cascade(
            included,
            include_tags=["advice", "essay"],
            exclude_tags=["yc news"],
            conditional_tags=["office hours", "founder stories"],
        )
        == "include"
    )
    assert (
        classify_by_tag_cascade(
            conditional,
            include_tags=["advice", "essay"],
            exclude_tags=["yc news"],
            conditional_tags=["office hours", "founder stories"],
        )
        == "conditional"
    )
    assert (
        classify_by_tag_cascade(
            skipped,
            include_tags=["advice", "essay"],
            exclude_tags=["yc news"],
            conditional_tags=["office hours", "founder stories"],
        )
        == "skip"
    )


def test_passes_conditional_content_filter(monkeypatch):
    class FakeResp:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    positive_text = "<main>" + ("startup growth leadership product advice " * 80) + "</main>"
    negative_text = "<main>" + ("apply deadline event schedule date " * 80) + "</main>"

    monkeypatch.setattr("yclib_extract.scraper.requests.get", lambda *_args, **_kwargs: FakeResp(positive_text))
    assert passes_conditional_content_filter("https://example.com/a", min_words=300) is True

    monkeypatch.setattr("yclib_extract.scraper.requests.get", lambda *_args, **_kwargs: FakeResp(negative_text))
    assert passes_conditional_content_filter("https://example.com/b", min_words=300) is False
