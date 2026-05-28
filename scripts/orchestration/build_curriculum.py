#!/usr/bin/env python3
"""
build_curriculum.py — Generate the Startup School Curriculum guide.

Refactored logic:
- Uses consolidated metadata JSON files (PG, SA, YC Library) for source mapping.
- Copies existing files to artifacts/yc_startup_school for a standalone directory.
- Falls back to extraction for missing items or YouTube/External sources.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

# Add project root to sys.path before imports
_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / "src"))

from scripts.shared import load_yaml, OutputFormatter

try:
    import yaml
except ImportError:
    print("PyYAML is required: pip install PyYAML", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TYPE_ICON = {
    "video": "📺",
    "article": "📄",
    "essay": "📝",
}

TYPE_LABEL = {
    "video": "Video",
    "article": "Article",
    "essay": "Essay",
}

CONDITION_VERB = {
    "video": "Watch this if:",
    "article": "Read this if:",
    "essay": "Read this if:",
}


def load_config(config_path: Path) -> dict:
    return load_yaml(config_path)


def slugify(text: str) -> str:
    t = (text or "").lower()
    allowed = []
    for ch in t:
        if ch.isalnum() or ch in ("-", "_"):
            allowed.append(ch)
        elif ch.isspace():
            allowed.append("-")
    s = "".join(allowed)
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-")


def get_source_type(res: dict) -> str:
    """Identify the source type of a resource based on its URL."""
    url = (res.get("online_url") or res.get("curriculum_url") or res.get("url") or "").lower()
    if "paulgraham.com" in url:
        return "pg_essay"
    if "blog.samaltman.com" in url:
        return "sa_essay"
    if "ycombinator.com/library" in url:
        return "yc_library"
    return "startup_school"


def get_res_id(res: dict) -> str:
    """Derive unique ID for a resource based on resolved ID (with conflict resolution), title slug, or URL."""
    # 0. Prioritize already resolved ID (handles collisions)
    if "resolved_id" in res:
        return res["resolved_id"]

    # 1. Prioritize slugified title for descriptive filenames
    title = res.get("title")
    if title:
        # Standardize "Why to Not Not Start a Startup" -> "why-to-not-not-start-a-startup"
        # and "Do Things That Don't Scale" -> "do-things-that-dont-scale"
        return slugify(title)

    # 2. Fallback to curriculum URL slug
    curr_url = res.get("curriculum_url") or res.get("url") or ""
    if curr_url:
        parsed = urlparse(curr_url)
        url_slug = parsed.path.strip("/").split("/")[-1]
        if url_slug:
            return url_slug

    # 3. Fallback to online_url slug (e.g. PG short names)
    online_url = res.get("online_url") or ""
    if online_url:
        parsed = urlparse(online_url)
        slug = parsed.path.strip("/").replace(".html", "")
        if slug:
            return slug

    return "resource"


def get_all_urls(res: dict) -> list:
    urls = []
    for key in ["curriculum_url", "online_url", "url", "video_url"]:
        u = res.get(key)
        if u and isinstance(u, str):
            urls.append(u)
    return urls


def load_metadata_maps(artifacts_dir: Path):
    """Load URL -> local_path maps from consolidated metadata files."""
    metadata_dir = artifacts_dir / "metadata"
    combined_map = {}

    # Files to scan
    meta_files = [
        ("pg_essays_metadata.json", "pg_essay"),
        ("altman_essays_metadata.json", "sa_essay"),
        ("yc_library_metadata.json", "yc_library"),
        ("yc_startup_school_metadata.json", "startup_school"),
    ]

    for filename, source_type in meta_files:
        path = metadata_dir / filename
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            posts = data.get("posts", [])
            for p in posts:
                # Collect all potential URLs that identify this resource
                item_urls = set()
                for key in ("url", "media_url", "source_url"):
                    val = p.get(key)
                    if val and isinstance(val, str):
                        item_urls.add(val)

                if not item_urls:
                    continue

                local_path = p.get("local_path") or p.get("file")
                status = p.get("status") or "done"

                if status not in ("done", "fetched", "skipped_existing"):
                    continue

                # Resolve full path to the .md file
                if local_path:
                    p_obj = Path(local_path)
                    if not p_obj.is_absolute():
                        # Determine directory based on source_type
                        if source_type == "pg_essay":
                            p_obj = artifacts_dir / "pg_essays" / p_obj.name
                        elif source_type == "sa_essay":
                            p_obj = artifacts_dir / "altman_essays" / p_obj.name
                        elif source_type == "yc_library":
                            p_obj = artifacts_dir / "yc_library" / p_obj.name
                        elif source_type == "startup_school":
                            p_obj = artifacts_dir / "yc_startup_school" / p_obj.name

                    if p_obj.exists():
                        for url in item_urls:
                            combined_map[url] = p_obj
        except Exception as e:
            print(f"Warning: failed to load metadata {filename}: {e}")

    return combined_map


def local_exists_for(res: dict, yc_startup_dir: Path) -> bool:
    """Return True if resource has a local file in the startup school dir."""
    res_id = get_res_id(res)
    p = yc_startup_dir / f"{res_id}.md"
    if p.exists():
        res["local_file"] = p.name
        return True
    return False


def to_metadata_json(res: dict, res_id: str) -> dict:
    """Convert YAML resource to extractor metadata format."""
    tags = res.get("tags") or []
    tags.extend(["curriculum", "startup-school"])

    meta = {
        "id": res_id,
        "url": res.get("curriculum_url") or res.get("online_url") or res.get("url") or "",
        "media_url": res.get("video_url") or res.get("online_url"),
        "title": res.get("title"),
        "author": res.get("author"),
        "description": res.get("description") or res.get("summary") or "",
        "summary": res.get("description") or res.get("summary") or "",
        "tags": tags,
        "type": res.get("type") or "video",
        "source_type": res.get("type") or "Video",
        "file": f"{res_id}.md",
        "source_url": res.get("video_url") or res.get("online_url"),
        "source": "startup-school",
        "published_at": res.get("published_at") or res.get("date"),
        "exported_at": datetime.now().isoformat(),
        "injected_at": datetime.now().isoformat(),
    }
    return meta


def run_extractor_on(
    metadata_dir: Path, output_dir: Path, workers: int = 1, force: bool = False
) -> int:
    """Invoke the project's extractor CLI."""
    cmd = [
        sys.executable,
        "scripts/yclib-extract",
        "extract",
        "--input-dir",
        str(metadata_dir),
        "--output-dir",
        str(output_dir),
        "--workers",
        str(workers),
    ]
    if force:
        cmd.append("--force")
    print(f"Running extractor: {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=False)
    return r.returncode


def render_resource(res: dict, yc_startup_dir: Path) -> str:
    """Render a single curriculum resource as Markdown."""
    lines = []
    title = res["title"]
    rtype = res.get("type", "video")
    icon = TYPE_ICON.get(rtype, "📄")
    label = TYPE_LABEL.get(rtype, "Video")
    duration = res.get("duration")
    author = res.get("author", "")
    description = (res.get("description") or "").strip()
    conditions = res.get("conditions") or []
    local_file = res.get("local_file")
    online_url = res.get("online_url") or res.get("curriculum_url") or ""
    video_url = res.get("video_url")

    meta_parts = []
    if author:
        meta_parts.append(f"**Author:** {author}")
    if duration:
        meta_parts.append(f"**Duration:** {duration}")
    meta_parts.append(f"**Type:** {label}")

    lines.append(f"### {icon} {title}")
    lines.append("")
    if meta_parts:
        lines.append("  ".join(meta_parts))
        lines.append("")

    if description:
        lines.append(description)
        lines.append("")

    if conditions:
        verb = CONDITION_VERB.get(rtype, "Read this if:")
        lines.append(f"**{verb}**")
        for cond in conditions:
            lines.append(f"- {cond}")
        lines.append("")

    lines.append("| | Reference |")
    lines.append("|---|-----------|")

    if local_file:
        lines.append(f"| 📁 | **Local copy** → [`{local_file}`]({local_file}) |")
    else:
        lines.append("| ⚠️ | **Local copy** → *Not yet scraped — online only* |")

    if online_url:
        display = online_url.replace("https://", "").replace("http://", "")
        lines.append(f"| 🔗 | **Online** → [{display}]({online_url}) |")

    if video_url:
        vid_display = video_url.replace("https://", "")
        lines.append(f"| ▶️ | **YouTube** → [{vid_display}]({video_url}) |")

    lines.append("")
    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def build_markdown(config: dict, yc_startup_dir: Path) -> str:
    """Build the full curriculum Markdown document."""
    modules = config.get("modules", [])
    total_resources = sum(len(m.get("resources", [])) for m in modules)

    local_count = sum(
        1 for m in modules for r in m.get("resources", []) if local_exists_for(r, yc_startup_dir)
    )
    missing_count = total_resources - local_count

    lines = []
    lines.append("# Startup School Curriculum")
    lines.append("")
    lines.append(f"> **{len(modules)} modules · {total_resources} resources**  ")
    lines.append(
        f"> {local_count}/{total_resources} resources available locally · "
        f"{missing_count} online-only  "
    )
    lines.append(
        f"> Source: [startupschool.org/curriculum](https://www.startupschool.org/curriculum)  "
    )
    lines.append(f"> Generated: {date.today()}")
    lines.append("")
    lines.append(
        "This guide mirrors the official Startup School curriculum. Each resource "
        "includes a local reference to the extracted Markdown file in this directory."
    )
    lines.append("")

    lines.append("## Table of Contents")
    lines.append("")
    for mod in modules:
        mod_title = mod["title"]
        anchor = mod_title.lower()
        for ch in " :&'\".,/()":
            anchor = anchor.replace(ch, "-")
        anchor = anchor.strip("-")
        while "--" in anchor:
            anchor = anchor.replace("--", "-")
        lines.append(f"- [{mod_title}](#{anchor})")
        for res in mod.get("resources", []):
            has_local = "✅" if local_exists_for(res, yc_startup_dir) else "⚠️"
            lines.append(f"  - {has_local} {res['title']}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for i, mod in enumerate(modules, 1):
        lines.append(f"## {mod['title']}\n")
        for res in mod.get("resources", []):
            lines.append(render_resource(res, yc_startup_dir))

    lines.append("---")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append(f"- ✅ = local Markdown file available")
    lines.append(f"- ⚠️ = not yet scraped; {missing_count} resource(s) need extraction")
    lines.append("")
    lines.append("_This file is auto-generated by `scripts/build_curriculum.py`._")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Build Startup School curriculum")
    parser.add_argument("--artifacts-dir", default="artifacts")
    parser.add_argument("--config", default="config/startup_school_curriculum.yaml")
    parser.add_argument("--ensure-local", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--inject-only", action="store_true")
    parser.add_argument("--inject-metadata-dir", default=None)
    parser.add_argument("--cleanup-orphans", action="store_true")

    args = parser.parse_args()
    artifacts_dir = Path(args.artifacts_dir)
    yc_startup_dir = artifacts_dir / "yc_startup_school"
    yc_startup_dir.mkdir(parents=True, exist_ok=True)

    config = load_config(Path(args.config))
    modules = config.get("modules", [])

    if args.inject_only:
        target_path = (
            Path(args.inject_metadata_dir)
            if args.inject_metadata_dir
            else artifacts_dir / "metadata" / "yc_startup_school_metadata.json"
        )
        posts = []
        for mod in modules:
            for res in mod.get("resources", []):
                res_id = get_res_id(res)
                posts.append(to_metadata_json(res, res_id))

        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump({"posts": posts}, f, indent=2)
        print(f"✅ Injected {len(posts)} resources into {target_path}")
        return 0

    # Resolve all IDs and handle naming collisions consistently
    standalone_files = {}
    for mod in modules:
        for res in mod.get("resources", []):
            res_id = get_res_id(res)
            url = res.get("online_url") or res.get("curriculum_url") or res.get("url") or ""
            filename = f"{res_id}.md"
            if filename in standalone_files and standalone_files[filename] != url:
                stype = get_source_type(res)
                suffix = "ss"
                if stype == "pg_essay":
                    suffix = "pg"
                elif stype == "sa_essay":
                    suffix = "sa"
                elif stype == "yc_library":
                    suffix = "yc"
                res_id = f"{res_id}-{suffix}"
                filename = f"{res_id}.md"
                if filename in standalone_files and standalone_files[filename] != url:
                    res_id = f"{res_id}-{slugify(url[-10:])}"
                    filename = f"{res_id}.md"
            standalone_files[filename] = url
            res["resolved_id"] = res_id

    if args.ensure_local:
        meta_map = load_metadata_maps(artifacts_dir)
        to_extract = []

        # Track which files are "current" in the curriculum
        current_files = {"startup_school_curriculum.md"}

        for mod in modules:
            for res in mod.get("resources", []):
                res_id = res["resolved_id"]
                filename = f"{res_id}.md"
                current_files.add(filename)

                if local_exists_for(res, yc_startup_dir) and not args.force:
                    continue

                urls = get_all_urls(res)
                found_src = None

                # Try to find in metadata map using all possible URLs
                for u in urls:
                    if u in meta_map:
                        found_src = meta_map[u]
                        break

                if found_src and found_src.exists():
                    dest_path = yc_startup_dir / filename
                    if found_src.resolve() != dest_path.resolve():
                        shutil.copy2(found_src, dest_path)
                        print(f"📄 Copied local source: {res_id} (from {found_src.parent.name})")
                    else:
                        print(f"📄 Source already in place: {res_id}")
                    continue

                # Otherwise add to extraction queue
                to_extract.append(res)

        if to_extract:
            print(f"🔁 ensure-local: {len(to_extract)} resources to extract")
            tmpdir = Path(tempfile.mkdtemp(prefix="yc_curric_meta_"))
            try:
                for res in to_extract:
                    res_id = get_res_id(res)
                    meta = to_metadata_json(res, res_id)
                    with open(tmpdir / f"{res_id}.json", "w", encoding="utf-8") as f:
                        json.dump(meta, f, indent=2)

                workers = int(os.environ.get("YCLIB_EXTRACTOR_WORKERS", "4"))
                run_extractor_on(tmpdir, yc_startup_dir, workers=workers, force=args.force)
            finally:
                shutil.rmtree(tmpdir)

        if args.cleanup_orphans:
            print(f"🧹 cleaning orphans in {yc_startup_dir}...")
            for p in yc_startup_dir.glob("*.md"):
                if p.name not in current_files:
                    print(f"  - removing orphan: {p.name}")
                    p.unlink()

    print(f"🔨 Building curriculum Markdown...")
    markdown = build_markdown(config, yc_startup_dir)

    out_path = yc_startup_dir / "startup_school_curriculum.md"
    out_path.write_text(markdown, encoding="utf-8")
    print(f"✅ Written: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
