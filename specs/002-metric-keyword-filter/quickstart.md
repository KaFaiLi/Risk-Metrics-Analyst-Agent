# Quickstart: Metric Keyword Filter

**Feature**: `002-metric-keyword-filter`  
**Date**: January 12, 2026

## Overview

This guide provides step-by-step implementation instructions for the metric keyword filter feature. Follow these steps in order to implement the feature with minimal risk.

---

## Step 1: Add Configuration Constant

**File**: `risk_metrics_app/config.py`

Add the maximum keywords constant:

```python
# Exclusion filter settings
MAX_EXCLUSION_KEYWORDS = 50
```

---

## Step 2: Add Filter Functions to metrics.py

**File**: `risk_metrics_app/metrics.py`

Add these functions after the existing imports and before `detect_node_column`:

```python
def parse_exclusion_keywords(raw_input: str, max_keywords: int = 50) -> Tuple[List[str], bool]:
    """Parse comma-separated keywords from user input.
    
    Args:
        raw_input: Raw string from text input field
        max_keywords: Maximum allowed keywords (default 50)
        
    Returns:
        Tuple of (parsed_keywords, exceeded_limit)
    """
    if not raw_input or not raw_input.strip():
        return [], False
    
    # Split by comma, strip whitespace, remove empty entries
    keywords = [kw.strip() for kw in raw_input.split(',') if kw.strip()]
    
    # Deduplicate while preserving order
    keywords = list(dict.fromkeys(keywords))
    
    # Check limit
    exceeded = len(keywords) > max_keywords
    if exceeded:
        keywords = keywords[:max_keywords]
    
    return keywords, exceeded


def filter_metrics_by_keywords(
    metrics: List[str],
    keywords: List[str]
) -> Tuple[List[str], List[str]]:
    """Filter out metrics matching any exclusion keyword.
    
    Args:
        metrics: List of metric column names
        keywords: List of exclusion keywords (already parsed)
        
    Returns:
        Tuple of (remaining_metrics, excluded_metrics)
    """
    if not keywords:
        return metrics, []
    
    def matches_any_keyword(metric: str) -> bool:
        metric_lower = metric.lower()
        return any(kw.lower() in metric_lower for kw in keywords)
    
    remaining = []
    excluded = []
    
    for metric in metrics:
        if matches_any_keyword(metric):
            excluded.append(metric)
        else:
            remaining.append(metric)
    
    return remaining, excluded


def get_metric_columns(df: pd.DataFrame) -> List[str]:
    """Extract metric column names from DataFrame.
    
    Excludes valuedate, limit columns, and node column.
    
    Args:
        df: DataFrame with lowercase column names
        
    Returns:
        List of metric column names
    """
    from .config import NODE_COLUMN
    
    metric_columns = [
        col for col in df.columns
        if col.lower() != VALUE_DATE_COLUMN
        and not col.lower().endswith(LIMIT_MAX_SUFFIX)
        and not col.lower().endswith(LIMIT_MIN_SUFFIX)
        and col.lower() != NODE_COLUMN
    ]
    return metric_columns
```

Update `__all__` to include new functions:

```python
__all__ = [
    # ... existing exports ...
    "parse_exclusion_keywords",
    "filter_metrics_by_keywords",
    "get_metric_columns",
]
```

---

## Step 3: Update Session State Initialization

**File**: `risk_metrics_app/app.py`

In `initialize_session_state()`, add:

```python
# Metric exclusion filter state
st.session_state.setdefault("exclusion_keywords_raw", "")
st.session_state.setdefault("uploaded_file_columns", None)
```

In `reset_analysis_state()`, add:

```python
# Reset file columns cache (but preserve keywords for next analysis)
st.session_state.uploaded_file_columns = None
```

---

## Step 4: Add Sidebar Filter UI

**File**: `risk_metrics_app/app.py`

In `render_sidebar()`, after the adaptive scaling checkbox and before the divider/Upload Data section, add:

```python
st.divider()

st.subheader("🔍 Exclude Metrics by Keyword")
exclusion_input = st.text_input(
    "Keywords to exclude",
    value=st.session_state.get("exclusion_keywords_raw", ""),
    placeholder="e.g., Basis, Credit, Vega",
    help="Comma-separated keywords. Metrics containing any keyword will be excluded from analysis.",
    key="exclusion_keywords_input",
)
st.session_state.exclusion_keywords_raw = exclusion_input

# Live preview
if exclusion_input.strip():
    from .metrics import parse_exclusion_keywords, filter_metrics_by_keywords
    from .config import MAX_EXCLUSION_KEYWORDS
    
    keywords, exceeded = parse_exclusion_keywords(exclusion_input, MAX_EXCLUSION_KEYWORDS)
    
    if exceeded:
        st.warning(f"⚠️ Maximum {MAX_EXCLUSION_KEYWORDS} keywords allowed. Extra keywords ignored.")
    
    # Preview count if file columns are cached
    cached_columns = st.session_state.get("uploaded_file_columns")
    if cached_columns and keywords:
        _, excluded = filter_metrics_by_keywords(cached_columns, keywords)
        if len(excluded) == len(cached_columns):
            st.error("⚠️ All metrics would be excluded!")
        elif len(excluded) > 0:
            st.caption(f"📊 {len(excluded)} metric(s) will be excluded")
        else:
            st.caption("ℹ️ No metrics match these keywords")
else:
    st.caption("ℹ️ No exclusion filter applied")
```

---

## Step 5: Cache File Columns on Upload

**File**: `risk_metrics_app/app.py`

In `handle_analysis()`, after loading and lowercasing the DataFrame columns, add:

```python
# Cache metric columns for live preview
from .metrics import get_metric_columns
st.session_state.uploaded_file_columns = get_metric_columns(df)
```

---

## Step 6: Apply Filter in Single Mode

**File**: `risk_metrics_app/app.py`

In `_handle_single_analysis()`, after `organize_metrics(df)` and before the limit filter:

```python
# Apply keyword exclusion filter
from .metrics import parse_exclusion_keywords, filter_metrics_by_keywords
from .config import MAX_EXCLUSION_KEYWORDS

keywords, _ = parse_exclusion_keywords(
    st.session_state.get("exclusion_keywords_raw", ""),
    MAX_EXCLUSION_KEYWORDS
)

if keywords:
    ordered_metrics, excluded_metrics = filter_metrics_by_keywords(ordered_metrics, keywords)
    if excluded_metrics:
        st.info(f"🔍 Excluded {len(excluded_metrics)} metric(s) by keyword filter: {', '.join(excluded_metrics[:5])}{'...' if len(excluded_metrics) > 5 else ''}")
        logger.info("Excluded %s metric(s) by keyword filter", len(excluded_metrics))
    
    if not ordered_metrics:
        st.error("⚠️ All metrics were excluded by the keyword filter. Please adjust your filter settings.")
        logger.warning("All metrics excluded by keyword filter")
        return
```

---

## Step 7: Apply Filter in Batch Mode

**File**: `risk_metrics_app/app.py`

In `_process_node_analysis()`, after `organize_metrics(df)` and before the limit filter, add the same filter logic as Step 6 (adjusted for node context):

```python
# Apply keyword exclusion filter
from .metrics import parse_exclusion_keywords, filter_metrics_by_keywords
from .config import MAX_EXCLUSION_KEYWORDS

keywords, _ = parse_exclusion_keywords(
    st.session_state.get("exclusion_keywords_raw", ""),
    MAX_EXCLUSION_KEYWORDS
)

if keywords:
    ordered_metrics, excluded_metrics = filter_metrics_by_keywords(ordered_metrics, keywords)
    if excluded_metrics:
        st.info(f"🔍 Excluded {len(excluded_metrics)} metric(s) by keyword filter")
        logger.info("Node %s: Excluded %s metric(s) by keyword filter", node_name, len(excluded_metrics))
    
    if not ordered_metrics:
        st.warning(f"⚠️ All metrics in node {node_name} were excluded by the keyword filter.")
        logger.warning("Node %s: All metrics excluded by keyword filter", node_name)
        return [], ""
```

---

## Step 8: Update Imports

**File**: `risk_metrics_app/app.py`

Add to the imports from `.metrics`:

```python
from .metrics import (
    # ... existing imports ...
    parse_exclusion_keywords,
    filter_metrics_by_keywords,
    get_metric_columns,
)
```

Add to the imports from `.config`:

```python
from .config import logger, MAX_EXCLUSION_KEYWORDS
```

---

## Testing Checklist

### Manual Tests

1. **Single keyword exclusion**
   - Upload CSV with metrics including "BasisSensi_EUR_1W", "VaR", "SVaR"
   - Enter "Basis" in exclusion field
   - Verify preview shows "1 metric(s) will be excluded"
   - Run analysis, verify only "VaR" and "SVaR" appear

2. **Multiple keywords**
   - Enter "Basis, Credit" in exclusion field
   - Verify both metric types excluded

3. **Case insensitivity**
   - Enter "basis" (lowercase) for "BasisSensi_EUR" metric
   - Verify match works

4. **Session persistence**
   - Enter keywords, upload new file
   - Verify keywords persist in input field

5. **All metrics excluded**
   - Enter keywords matching all metrics
   - Verify error message and analysis blocked

6. **Batch mode**
   - Upload multi-node CSV
   - Apply keyword filter
   - Verify filter applies to all nodes

7. **Empty/whitespace handling**
   - Enter "  , Basis, , Credit,  "
   - Verify parsing handles gracefully

---

## Rollback

If issues occur:
1. Remove filter UI section from `render_sidebar()`
2. Remove filter logic from `_handle_single_analysis()` and `_process_node_analysis()`
3. Remove session state keys from `initialize_session_state()`
4. Remove new functions from `metrics.py`
5. Remove `MAX_EXCLUSION_KEYWORDS` from `config.py`

The existing analysis flow will continue to work without the filter feature.
