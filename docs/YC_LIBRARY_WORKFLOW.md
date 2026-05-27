# YC Library Extraction Workflow

## Overview
The YC Library extraction pipeline handles discovery, enrichment, extraction, and auditing of YC Library content from Algolia.

## Pipeline Stages

### 1. Discovery (Algolia)
- **Input**: Algolia API credentials
- **Process**: Paginate through Algolia index using `AlgoliaPageinator`
- **Output**: Raw metadata list
- **Key Features**:
  - Efficient pagination for large result sets
  - Batch processing with configurable page size
  - Error handling and timeout protection

### 2. Enrichment & Filtering
- **Input**: Raw metadata
- **Process**: 
  - Detect and remove duplicates by URL
  - Enrich metadata with content type and quality scores
  - Filter by criteria (status, date range, etc.)
- **Output**: Cleaned metadata
- **Key Features**:
  - Preserve order during deduplication
  - Content type detection (video, document, article)
  - Quality scoring based on field completeness (0-100)

### 3. Extraction
- **Input**: Cleaned metadata + HTML content
- **Process**:
  - Convert HTML to Markdown
  - Sanitize and clean content
  - Apply YC Library-specific formatting
  - Track extraction quality metrics
- **Output**: Markdown files + quality metrics
- **Key Features**:
  - Quality level determination (short/minimal/good/excellent)
  - Content length analysis
  - Warning generation for incomplete content
  - Completeness checking (title, author, content)

### 4. Configuration & Decision
- **Input**: Metadata + YCLibraryConfig
- **Process**:
  - Decide whether to extract or skip
  - Apply extraction thresholds
  - Handle retry logic for failed resources
- **Output**: Extraction decision + config

### 5. Auditing
- **Input**: All extractions + metrics
- **Process**:
  - Generate unified audit CSV
  - Track by status, quality, source
  - Calculate aggregate statistics
  - Store extraction timestamps
- **Output**: `artifacts/resources_audit.csv`
- **Key Columns**:
  - resource_id, source, title, url
  - status (done/error/short), quality_level
  - content_length, word_count, warnings
  - extracted_at, file_path

## Quality Thresholds

- **Minimum content length**: 100 characters
- **Target content length**: 500+ characters
- **Quality Levels**:
  - `short`: < 100 chars
  - `minimal`: 100-500 chars
  - `good`: 500-5000 chars
  - `excellent`: 5000+ chars

## Configuration

```python
yc_config = YCLibraryConfig()
yc_config.quality_thresholds = {
    'min_content_length': 100,
    'target_content_length': 500,
    'allow_short_content': False,  # Skip short content
}
yc_config.extraction_tracking = {
    'track_quality': True,
    'store_metrics': True,
}
```

## Error Handling

- **Extraction errors** are logged with resource ID and stored in audit
- **Network errors** trigger retry logic
- **Invalid metadata** is filtered during enrichment
- **Duplicate content** is deduplicated by URL (canonical key)

## Files Modified

- `src/yclib_extract/scraper.py` — AlgoliaPageinator, MetadataFilter
- `src/yclib_extract/extractor.py` — YCLibraryExtractionEnhancer
- `src/yclib_extract/config.py` — YCLibraryConfig
- `src/yclib_extract/lib/audit.py` — UnifiedAudit
- `tests/test_yc_library_pipeline.py` — Comprehensive test coverage

## Integration with Main Pipeline

The YC Library pipeline integrates into the unified orchestration system:
- Trigger: `yclib-extract pipeline --workflow full --mode weekly`
- Discovery: Algolia → metadata.json
- Extraction: metadata → markdown files
- Auditing: Append to resources_audit.csv

