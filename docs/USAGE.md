# Advanced Usage & Output Formats

This document covers detailed output structures, advanced CLI options, proxy configuration, and troubleshooting for `yclib-extract`.

## Outputs

### Metadata JSON (`artifacts/yc_library_metadata.json`)
```json
{
  "posts": [
    {
      "id": "startup_library_123",
      "url": "https://www.ycombinator.com/library/abc-post",
      "media_url": "https://youtu.be/ABC123",
      "title": "Post Title",
      "author": "Author Name",
      "type": "Video",
      "source_type": "Video",
      "description": "Post summary",
      "date": "2024-01-15",
      "file": "post-title.md"
    }
  ]
}
```

### Markdown File (`artifacts/yc_library/<slug>.md`)
```markdown
---
title: "Post Title"
url: "https://www.ycombinator.com/library/abc-post"
type: "Video"
author: "Author Name"
summary: "Post summary"
published_at: "2024-01-15"
exported_at: "2024-05-25T15:00:00"
source_url: "https://youtu.be/ABC123"
video_url: "https://youtu.be/ABC123"
file: "post-title.md"
word_count: 1250
---

# Post Title

[Body content in clean Markdown...]

## Transcript

[Video transcript if available...]
```

### Extraction Database (`artifacts/extraction_jobs.db`)
SQLite table tracks every post:
- `id` — post slug
- `status` — `pending`, `done`, `short`, `failed`, `error`, `missing`, `removed`
- `attempt_count` — number of attempts
- `content_length` — bytes extracted
- `error_msg` — last error (if any)
- `extracted_at` — timestamp of successful extraction

Query examples:
```bash
sqlite3 artifacts/extraction_jobs.db "SELECT status, COUNT(*) FROM extraction_jobs GROUP BY status;"
sqlite3 artifacts/extraction_jobs.db "SELECT id, error_msg FROM extraction_jobs WHERE status = 'error';"
```

### Daily Audit Manifest (`scrape_runs/yc_content_runs_YYYYMMDD.json`)
```json
{
  "runs": [
    {
      "stage": "extract",
      "generated_at": "2024-05-25T15:10:00",
      "total_files": 423,
      "done": 350,
      "short": 30,
      "missing": 40,
      "error": 3,
      "by_source_type": {
        "Article": {"done": 150, "short": 5, "error": 0},
        "Video": {"done": 150, "short": 20, "error": 3},
        "Podcast": {"done": 50, "short": 5, "error": 0}
      }
    }
  ]
}
```

## Advanced CLI Commands

### Pipeline Execution Modes
```bash
# Start from extraction (skip discovery)
yclib-extract pipeline --start-stage extract --mode dev

# Modes: 
# 'weekly' (default, incremental, skips existing)
# 'dev' (replay-friendly, overwrites existing)
```

### Resume Failed Jobs
```bash
# Retry only jobs marked failed/error/short
yclib-extract extract --retry-failed-only

# Force re-extract everything (slow, overwrites done jobs)
yclib-extract extract --force
```

### Skip Specific Sources
Create or edit `config/ignore_sources.json`:
```json
[
  "example.com",
  "https://example.com/specific-page",
  "author-name"
]
```

## Troubleshooting

### "No content found" or "Content too short"
**Status:** `short` or `failed`
**Reason:** Page HTML doesn't contain enough extractable text (< 2000 chars by default)
**Solution:**
- Increase `YCLIB_EXTRACT_MIN_CONTENT_LENGTH` in `.env`
- Some posts may be link aggregators or short intros (expected behavior).

### Video transcripts not extracted
**Status:** `missing` or transcript section empty
**Reason:** Video has no public captions, or YouTube is blocking requests
**Solutions:**
1. Install transcript support: `pip install "yclib-extract[transcripts]"`
2. Set up proxy via `INVIDIOUS_INSTANCES` env var
3. Manually add transcript to the Markdown file

### "RequestBlocked" errors
**Reason:** YouTube rate-limiting or geo-blocking
**Solutions:**
- Wait a few hours and retry: `yclib-extract extract --retry-failed-only`
- Use Invidious fallback: set `INVIDIOUS_INSTANCES` and reinstall with `[transcripts-full]`
- Reduce `--workers` to slow down requests

## Proxy Configuration
The package supports two types of proxy settings:

1. **YouTube Transcript Settings** — For handling YouTube rate-limiting and transcripts
   - `INVIDIOUS_INSTANCES` — Free YouTube mirrors (fallback when rate-limited)
   - `YOUTUBE_PROXY_URL` — Route YouTube requests through a corporate proxy

2. **General Proxy Settings** — For all HTTP/HTTPS traffic (behind firewall)
   - `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` — Route all traffic through corporate gateway

**For quick setup behind a firewall:**
```bash
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080
export ALL_PROXY=http://proxy.company.com:8080
yclib-extract extract
```
