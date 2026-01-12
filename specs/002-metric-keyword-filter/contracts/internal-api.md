# Contracts: Metric Keyword Filter

**Feature**: `002-metric-keyword-filter`  
**Date**: January 12, 2026

## Overview

This feature is entirely internal to the Streamlit application and does not expose external APIs. The "contracts" here define the internal function signatures and data structures that other modules depend on.

## Internal Function Contracts

### parse_exclusion_keywords

**Module**: `risk_metrics_app.metrics`

```python
def parse_exclusion_keywords(
    raw_input: str, 
    max_keywords: int = 50
) -> Tuple[List[str], bool]:
    """
    Parse comma-separated keywords from user input.
    
    Parameters:
        raw_input: Raw string from text input field (may contain whitespace, 
                   empty entries, duplicates)
        max_keywords: Maximum allowed keywords (default 50)
        
    Returns:
        Tuple containing:
        - List[str]: Parsed, trimmed, deduplicated keywords (max `max_keywords` items)
        - bool: True if original input exceeded max_keywords limit
        
    Guarantees:
        - Returns empty list for empty/whitespace-only input
        - All returned keywords are stripped of whitespace
        - No empty strings in returned list
        - No duplicates in returned list
        - Order preserved (first occurrence wins for duplicates)
        - List length <= max_keywords
        
    Examples:
        parse_exclusion_keywords("") -> ([], False)
        parse_exclusion_keywords("  ") -> ([], False)
        parse_exclusion_keywords("Basis") -> (["Basis"], False)
        parse_exclusion_keywords("Basis, Credit") -> (["Basis", "Credit"], False)
        parse_exclusion_keywords("Basis,,Credit") -> (["Basis", "Credit"], False)
        parse_exclusion_keywords("Basis, Basis") -> (["Basis"], False)
        parse_exclusion_keywords(" Basis , Credit ") -> (["Basis", "Credit"], False)
    """
```

---

### filter_metrics_by_keywords

**Module**: `risk_metrics_app.metrics`

```python
def filter_metrics_by_keywords(
    metrics: List[str],
    keywords: List[str]
) -> Tuple[List[str], List[str]]:
    """
    Filter out metrics matching any exclusion keyword.
    
    Parameters:
        metrics: List of metric column names to filter
        keywords: List of exclusion keywords (should be pre-parsed)
        
    Returns:
        Tuple containing:
        - List[str]: Metrics that do NOT match any keyword (remaining)
        - List[str]: Metrics that DO match at least one keyword (excluded)
        
    Matching Rules:
        - Case-insensitive substring matching
        - A metric is excluded if ANY keyword appears within its name
        - Keywords are treated as literal strings (not regex)
        
    Guarantees:
        - len(remaining) + len(excluded) == len(metrics)
        - Order of metrics is preserved in both lists
        - If keywords is empty, returns (metrics, [])
        - If metrics is empty, returns ([], [])
        
    Examples:
        filter_metrics_by_keywords(["VaR", "SVaR", "BasisSensi"], []) 
            -> (["VaR", "SVaR", "BasisSensi"], [])
            
        filter_metrics_by_keywords(["VaR", "SVaR", "BasisSensi"], ["Basis"]) 
            -> (["VaR", "SVaR"], ["BasisSensi"])
            
        filter_metrics_by_keywords(["VaR", "SVaR", "BasisSensi"], ["basis"]) 
            -> (["VaR", "SVaR"], ["BasisSensi"])  # Case insensitive
            
        filter_metrics_by_keywords(["VaR", "SVaR", "BasisSensi"], ["Basis", "VaR"]) 
            -> (["SVaR"], ["VaR", "BasisSensi"])
    """
```

---

### get_metric_columns

**Module**: `risk_metrics_app.metrics`

```python
def get_metric_columns(df: pd.DataFrame) -> List[str]:
    """
    Extract metric column names from DataFrame.
    
    Parameters:
        df: DataFrame with lowercase column names
        
    Returns:
        List of column names that are actual metrics (not metadata or limits)
        
    Exclusion Rules:
        - Excludes 'valuedate' column
        - Excludes columns ending with '_limmaxvalue' 
        - Excludes columns ending with '_limminvalue'
        - Excludes 'strananodename' column (batch mode node identifier)
        
    Guarantees:
        - All returned names exist in df.columns
        - Order matches df.columns order (filtered)
        
    Notes:
        - Assumes df.columns are already lowercased
        - Used for live preview caching, not for analysis ordering
          (use organize_metrics for ordered processing)
    """
```

---

## Session State Contract

### Keys

| Key | Type | Default | Mutated By |
|-----|------|---------|------------|
| `exclusion_keywords_raw` | `str` | `""` | Sidebar text input |
| `uploaded_file_columns` | `Optional[List[str]]` | `None` | `handle_analysis()` after file load |

### Invariants

1. `exclusion_keywords_raw` is always a valid string (never None)
2. `uploaded_file_columns` is None until a file is uploaded and parsed
3. `uploaded_file_columns` is reset to None by `reset_analysis_state()`
4. `exclusion_keywords_raw` persists across `reset_analysis_state()` calls

---

## UI Contract

### Filter Input Behavior

| User Action | System Response |
|-------------|-----------------|
| Type in filter input | Value stored in session state, preview updates |
| Upload file | Column names cached, preview becomes active |
| Clear filter input | No filtering applied, preview shows "No exclusion filter applied" |
| Enter >50 keywords | Truncate, show warning |
| Keywords match all metrics | Show error, preview says "All metrics would be excluded" |
| Click Analyze with all excluded | Show error, block analysis |

### Preview Text Variants

| Condition | Preview Text |
|-----------|--------------|
| No input | "ℹ️ No exclusion filter applied" |
| Input but no file columns cached | No preview shown |
| Input, file cached, no matches | "ℹ️ No metrics match these keywords" |
| Input, file cached, some matches | "📊 X metric(s) will be excluded" |
| Input, file cached, all match | "⚠️ All metrics would be excluded!" |
