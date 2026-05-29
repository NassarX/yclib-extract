import json

from yclib_extract import pipeline as pipeline_module
from yclib_extract.companies import CompaniesByTagScraper, DEFAULT_COMPANY_TAGS
from yclib_extract.pipeline import PipelineOrchestrator


class DummySession:
    def __init__(self, payload):
        self.payload = payload

    def get(self, url, timeout=15):
        class Resp:
            def __init__(self, payload):
                self._payload = payload
                self.status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        return Resp(self.payload)


COMPANY_PAYLOAD = [
    {
        "id": 21,
        "name": "Tap to Learn",
        "slug": "tap-to-learn",
        "former_names": [],
        "small_logo_thumb_url": "/company/thumb/missing.png",
        "website": "http://taptolearn.com",
        "all_locations": "Menlo Park, CA, USA",
        "long_description": "When we began our first experiments with using Mobile devices a few years ago we were very excited by the possibility of learning in nontraditional manner.",
        "one_liner": "Games For Education",
        "team_size": 11,
        "industry": "Consumer",
        "subindustry": "Consumer -> Gaming",
        "launched_at": 1322045690,
        "tags": ["Education", "Gaming"],
        "tags_highlighted": [],
        "top_company": False,
        "isHiring": False,
        "nonprofit": False,
        "batch": "Winter 2012",
        "status": "Inactive",
        "industries": ["Consumer", "Gaming"],
        "regions": ["United States of America", "America / Canada"],
        "stage": "Early",
        "app_video_public": False,
        "demo_day_video_public": False,
        "app_answers": None,
        "question_answers": False,
        "url": "https://www.ycombinator.com/companies/tap-to-learn",
        "api": "https://yc-oss.github.io/api/batches/winter-2012/tap-to-learn.json",
    }
]


def test_build_tag_record_humanizes_slug():
    scraper = CompaniesByTagScraper(session=DummySession([]))
    record = scraper.build_tag_record("space-exploration", count=3)

    assert record == {
        "name": "Space Exploration",
        "slug": "space-exploration",
        "url": "https://raw.githubusercontent.com/yc-oss/api/main/tags/space-exploration.json",
        "count": 3,
    }


def test_discover_tag_slugs(monkeypatch):
    scraper = CompaniesByTagScraper(session=DummySession([]))

    def fake_fetch_json(url, retries=3, backoff=0.4):
        if "git/trees" not in url:
            raise AssertionError("unexpected url")
        return {
            "tree": [
                {"path": "tags/ai.json", "type": "blob"},
                {"path": "tags/weather.json", "type": "blob"},
                {"path": "docs/readme.md", "type": "blob"},
            ]
        }

    monkeypatch.setattr(scraper, "_fetch_json", fake_fetch_json)

    assert scraper.discover_tag_slugs() == ["ai", "weather"]


def test_save_metadata_writes_taxonomy_records(tmp_path):
    scraper = CompaniesByTagScraper(session=DummySession(COMPANY_PAYLOAD))
    out_dir = tmp_path / "metadata"

    total = scraper.save_metadata(["weather"], str(out_dir), force=True, concurrency=2)

    assert total == 1
    total2, summary = scraper.save_metadata(
        ["weather"], str(out_dir), force=True, concurrency=2, return_summary=True
    )
    assert total2 == 1
    assert summary[0]["name"] == "Weather"
    assert summary[0]["slug"] == "weather"
    assert summary[0]["url"].endswith("/weather.json")
    assert summary[0]["count"] == 1
    assert summary[0]["file"].endswith("weather.json")
    # companies list should be present and reference the canonical api/url unifier
    assert "companies" in summary[0]
    assert summary[0]["companies"][0] == COMPANY_PAYLOAD[0]["url"]


def test_companies_by_tag_pipeline_smoke(tmp_path, monkeypatch):
    metadata_dir = tmp_path / "metadata"
    content_dir = tmp_path / "content"
    db_path = tmp_path / "extraction.db"
    artifacts_dir = tmp_path / "artifacts"

    monkeypatch.setenv("YC_BLOG_DIR", str(tmp_path / "yc_blog"))
    monkeypatch.setenv("PG_ESSAYS_DIR", str(tmp_path / "pg_essays"))
    monkeypatch.setenv("SA_ESSAYS_DIR", str(tmp_path / "sa_essays"))
    monkeypatch.setattr(pipeline_module, "ARTIFACTS_DIR", artifacts_dir)

    scraper = CompaniesByTagScraper(session=DummySession(COMPANY_PAYLOAD))
    monkeypatch.setattr(pipeline_module, "CompaniesByTagScraper", lambda: scraper)

    orchestrator = PipelineOrchestrator(
        metadata_dir=str(metadata_dir),
        content_dir=str(content_dir),
        db_path=str(db_path),
    )

    result = orchestrator.run_companies_by_tag(
        ["weather"], force=True, output_dir=str(metadata_dir)
    )

    assert result["discovered_tags"] == 1
    assert result["companies_saved"] == 1
    assert result["markdown_saved"] == 1

    taxonomy = json.loads((metadata_dir / "yc_companies_by_tag_taxonomy.json").read_text())
    assert taxonomy[0]["name"] == "Weather"
    assert taxonomy[0]["slug"] == "weather"
    assert taxonomy[0]["url"].endswith("/weather.json")
    assert taxonomy[0]["count"] == 1

    # markdown is written once as a canonical artifact under /companies/
    markdown_path = artifacts_dir / "yc_companies_by_tag" / "companies" / "tap-to-learn.md"
    text = markdown_path.read_text()
    assert text.startswith("---")
    assert 'title: "Tap to Learn"' in text
    assert 'summary: "Games For Education"' in text
    assert (
        'source_url: "https://yc-oss.github.io/api/batches/winter-2012/tap-to-learn.json"' in text
    )
    assert "When we began our first experiments with using Mobile devices" in text
    assert '- **batch**: "Winter 2012"' in text
    assert '- **website**: "http://taptolearn.com"' in text
    assert text.rstrip().endswith("- **question_answers**: false")


def test_companies_by_tag_pipeline_discovers_all_tags(tmp_path, monkeypatch):
    metadata_dir = tmp_path / "metadata"
    content_dir = tmp_path / "content"
    db_path = tmp_path / "extraction.db"
    artifacts_dir = tmp_path / "artifacts"

    monkeypatch.setenv("YC_BLOG_DIR", str(tmp_path / "yc_blog"))
    monkeypatch.setenv("PG_ESSAYS_DIR", str(tmp_path / "pg_essays"))
    monkeypatch.setenv("SA_ESSAYS_DIR", str(tmp_path / "sa_essays"))
    monkeypatch.setattr(pipeline_module, "ARTIFACTS_DIR", artifacts_dir)

    scraper = CompaniesByTagScraper(session=DummySession(COMPANY_PAYLOAD))
    monkeypatch.setattr(scraper, "discover_tag_slugs", lambda: ["weather"])
    monkeypatch.setattr(pipeline_module, "CompaniesByTagScraper", lambda: scraper)

    orchestrator = PipelineOrchestrator(
        metadata_dir=str(metadata_dir),
        content_dir=str(content_dir),
        db_path=str(db_path),
    )

    result = orchestrator.run_companies_by_tag(
        None, force=True, output_dir=str(metadata_dir), discover_all_tags=True
    )

    assert result["discovered_tags"] == 1
    taxonomy = json.loads((metadata_dir / "yc_companies_by_tag_taxonomy.json").read_text())
    assert taxonomy[0]["slug"] == "weather"


def test_companies_by_tag_pipeline_uses_default_seed_tags(tmp_path, monkeypatch):
    metadata_dir = tmp_path / "metadata"
    content_dir = tmp_path / "content"
    db_path = tmp_path / "extraction.db"
    artifacts_dir = tmp_path / "artifacts"

    monkeypatch.setattr(pipeline_module, "ARTIFACTS_DIR", artifacts_dir)

    captured = {}

    class StubScraper:
        def save_metadata(self, tags, output_dir, force=False, concurrency=4, write_manifests=True, return_summary=False):
            captured["tags"] = list(tags)
            if return_summary:
                return 0, []
            return 0

        def get_tag_counts(self, tags):
            return {tag: 0 for tag in tags}

        def build_tag_record(self, tag, count=None):
            return {
                "name": tag.replace("-", " ").title(),
                "slug": tag,
                "url": f"https://example.com/{tag}.json",
                "count": count,
            }

        def fetch_tag(self, tag):
            return []

    monkeypatch.setattr(pipeline_module, "CompaniesByTagScraper", lambda: StubScraper())

    orchestrator = PipelineOrchestrator(
        metadata_dir=str(metadata_dir),
        content_dir=str(content_dir),
        db_path=str(db_path),
    )

    orchestrator.run_companies_by_tag(None, force=True, output_dir=str(metadata_dir))

    assert captured["tags"] == DEFAULT_COMPANY_TAGS
