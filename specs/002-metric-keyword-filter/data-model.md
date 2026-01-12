# Data Model: Metric Keyword Filter

**Feature**: `002-metric-keyword-filter`  
**Date**: January 12, 2026

## Entities

### ExclusionKeywords

User-provided keywords for filtering out metrics from analysis.

| Field | Type | Description |
|-------|------|-------------|
| `raw_input` | `str` | Original comma-separated string entered by user |
| `parsed_keywords` | `List[str]` | Cleaned, deduplicated list of keywords |
| `keyword_count` | `int` | Number of valid keywords (after parsing) |

**Validation Rules**:
- Empty strings and whitespace-only entries are ignored
- Keywords are trimmed of leading/trailing whitespace
- Duplicate keywords are removed (first occurrence kept)
- Maximum 50 keywords allowed (warn if exceeded, truncate)

**Session State Key**: `exclusion_keywords_raw`

---

### FilterResult

Result of applying exclusion filter to a list of metrics.

| Field | Type | Description |
|-------|------|-------------|
| `original_metrics` | `List[str]` | Full list of metric names before filtering |
| `filtered_metrics` | `List[str]` | Metrics remaining after exclusion |
| `excluded_metrics` | `List[str]` | Metrics that were excluded |
| `excluded_count` | `int` | Number of metrics excluded |
| `original_count` | `int` | Total metrics before filtering |

**Computed Properties**:
- `remaining_count`: `len(filtered_metrics)`
- `all_excluded`: `len(filtered_metrics) == 0`

---

### FilterPreview

Live preview state shown in sidebar before analysis runs.

| Field | Type | Description |
|-------|------|-------------|
| `available_metrics` | `List[str]` | Metric columns detected in uploaded file |
| `preview_count` | `int` | How many metrics would be excluded |
| `keywords_applied` | `List[str]` | Keywords being previewed |
| `preview_text` | `str` | Human-readable preview message |

**Display Logic**:
- If no keywords: `"No exclusion filter applied"`
- If keywords but no matches: `"No metrics match these keywords"`
- If keywords with matches: `"5 metrics will be excluded"`
- If all metrics would be excluded: `"⚠️ All metrics would be excluded"`

---

## State Flow

### Session State Keys

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `exclusion_keywords_raw` | `str` | `""` | Raw input from text field |
| `uploaded_file_columns` | `Optional[List[str]]` | `None` | Cached metric column names for preview |

### State Transitions

```
[File Upload]
     │
     ▼
┌──────────────────────────┐
│ Cache column names in    │
│ uploaded_file_columns    │
└──────────────────────────┘
     │
     ▼
[User types keywords in sidebar]
     │
     ▼
┌──────────────────────────┐
│ Update exclusion_keywords│
│ Compute preview count    │
│ Display preview text     │
└──────────────────────────┘
     │
     ▼
[User clicks Analyze]
     │
     ▼
┌──────────────────────────┐
│ Parse keywords           │
│ Apply filter to metrics  │
│ Check all_excluded       │
│ Continue or show error   │
└──────────────────────────┘
```

---

## Functions

### parse_exclusion_keywords

**Location**: `metrics.py`

**Signature**:
```python
def parse_exclusion_keywords(raw_input: str, max_keywords: int = 50) -> Tuple[List[str], bool]:
    """
    Parse comma-separated keywords from user input.
    
    Args:
        raw_input: Raw string from text input field
        max_keywords: Maximum allowed keywords (default 50)
        
    Returns:
        Tuple of (parsed_keywords, exceeded_limit)
    """
```

**Logic**:
1. Split by comma
2. Strip whitespace from each keyword
3. Remove empty strings
4. Deduplicate (preserve order)
5. Truncate if exceeds max, return exceeded flag

---

### filter_metrics_by_keywords

**Location**: `metrics.py`

**Signature**:
```python
def filter_metrics_by_keywords(
    metrics: List[str],
    keywords: List[str]
) -> Tuple[List[str], List[str]]:
    """
    Filter out metrics matching any exclusion keyword.
    
    Args:
        metrics: List of metric column names
        keywords: List of exclusion keywords (already parsed)
        
    Returns:
        Tuple of (remaining_metrics, excluded_metrics)
    """
```

**Logic**:
1. If no keywords, return (metrics, [])
2. For each metric, check if any keyword is a substring (case-insensitive)
3. Partition into remaining and excluded lists
4. Return both lists

---

### get_metric_columns

**Location**: `metrics.py`

**Signature**:
```python
def get_metric_columns(df: pd.DataFrame) -> List[str]:
    """
    Extract metric column names from DataFrame (excludes valuedate and limit columns).
    
    Args:
        df: DataFrame with lowercase column names
        
    Returns:
        List of metric column names (unordered)
    """
```

**Logic**:
1. Exclude `valuedate` column
2. Exclude columns ending with `_limmaxvalue` or `_limminvalue`
3. Exclude node column if present
4. Return remaining column names

---

## UI Components

### Sidebar Filter Section

**Location**: `app.py` `render_sidebar()`

**Position**: After "Enable adaptive graph scaling" checkbox, before "Upload Data" section

**Components**:
1. `st.text_input` for keywords
2. `st.caption` for live preview count
3. `st.warning` if limit exceeded or all metrics would be excluded

**Mockup**:
```
⚙️ Configuration
├── [x] Enable AI-generated insights
│   └── [API Key input]
├── [ ] Hide metrics without limits
├── [x] Enable adaptive graph scaling
├── ────────────────────────────
├── 🔍 Exclude Metrics by Keyword
│   └── [Comma-separated keywords...]
│   └── "5 metrics will be excluded"  ← live preview
├── ────────────────────────────
├── 📁 Upload Data
│   └── [File uploader]
└── [🚀 Analyze Risk Metrics]
```

---

## Integration with Existing Flow

### handle_analysis Changes

1. After parsing CSV and lowercasing columns
2. Before calling `_handle_single_analysis` or `_handle_batch_analysis`
3. Parse keywords from session state
4. Pass keywords to analysis functions

### _handle_single_analysis Changes

1. After `organize_metrics(df)`
2. Call `filter_metrics_by_keywords(ordered_metrics, keywords)`
3. Display excluded count
4. If all excluded, show error and return early
5. Continue with filtered metric list

### _handle_batch_analysis Changes

Same as single analysis, applied within `_process_node_analysis` for each node.

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Empty keyword input | No filtering applied |
| Keywords with only whitespace | Treated as empty, no filtering |
| Duplicate keywords | Deduplicated silently |
| Double commas (e.g., "Basis,,Credit") | Empty entries ignored |
| Special regex chars (e.g., "[EUR]") | Matched literally |
| All metrics excluded | Show error, block analysis |
| >50 keywords | Truncate, show warning |
| Keyword longer than any metric name | No matches (harmless) |
