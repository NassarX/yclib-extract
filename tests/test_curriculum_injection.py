import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cmd(args):
    r = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True)
    print(r.stdout)
    print(r.stderr)
    return r


def test_inject_only_writes_enriched_metadata(tmp_path):
    artifacts_dir = tmp_path / "artifacts"
    metadata_file = tmp_path / "injected_metadata.json"
    config_path = tmp_path / "curriculum.yaml"

    config_path.write_text("""
modules:
  - title: Module 1
    resources:
      - title: Test Resource
        type: video
        author: Example Author
        description: Example summary
        published_at: "2025-01-02"
        tags: ["founder"]
        curriculum_url: "https://www.ycombinator.com/library/test-resource"
        online_url: "https://www.ycombinator.com/library/test-resource"
        video_url: "https://www.youtube.com/watch?v=abc123"
""".strip())

    result = run_cmd(
        [
            sys.executable,
            "scripts/build_curriculum.py",
            "--inject-only",
            "--config",
            str(config_path),
            "--artifacts-dir",
            str(artifacts_dir),
            "--inject-metadata-dir",
            str(metadata_file),
        ]
    )
    assert result.returncode == 0

    assert metadata_file.exists()
    data = json.loads(metadata_file.read_text())
    assert "posts" in data
    payload = data["posts"][0]

    assert payload["title"] == "Test Resource"
    assert payload["summary"] == "Example summary"
    assert payload["published_at"] == "2025-01-02"
    assert payload["file"] == "test-resource.md"
    assert payload["source"] == "startup-school"
    assert "curriculum" in payload["tags"]
    assert "startup-school" in payload["tags"]
    assert "exported_at" in payload
    assert "injected_at" in payload

    generated_curriculum = artifacts_dir / "yc_startup_school" / "startup_school_curriculum.md"
    assert not generated_curriculum.exists()
