# Research: Metric Keyword Filter

**Feature**: `002-metric-keyword-filter`  
**Date**: January 12, 2026

## Research Tasks

### 1. Streamlit Text Input with Live Updates

**Question**: How to implement live preview of filtered metrics count as user types keywords?

**Findings**:
- Streamlit `st.text_input` supports `on_change` callback that fires when value changes
- However, `on_change` triggers a rerun, which resets the page state
- Alternative: Use the current input value on each rerun (Streamlit's reactive model)
- For live preview without analysis rerun, store keywords in session state and compute preview count during sidebar render

**Decision**: Use session state to store keywords. On each Streamlit rerun, compute preview count from uploaded file's column names. No special callback needed - Streamlit's reactive model handles updates naturally.

**Alternatives Rejected**:
- `st_aggrid` or custom JS components: Overkill for simple text input
- Debouncing: Streamlit handles reruns efficiently; no need for artificial delays

---

### 2. Keyword Parsing Best Practices

**Question**: How to handle edge cases in comma-separated keyword input?

**Findings**:
- Standard approach: `[kw.strip() for kw in input.split(',') if kw.strip()]`
- Handles: leading/trailing whitespace, multiple spaces, empty entries from double commas
- Deduplication: `list(dict.fromkeys(keywords))` preserves order while removing duplicates
- Special characters: Treat as literal strings per FR-009 (no regex)

**Decision**: 
```python
def parse_exclusion_keywords(raw_input: str) -> List[str]:
    """Parse comma-separated keywords, strip whitespace, remove duplicates."""
    keywords = [kw.strip() for kw in raw_input.split(',') if kw.strip()]
    return list(dict.fromkeys(keywords))  # Deduplicate preserving order
```

**Alternatives Rejected**:
- Regex split: Unnecessary complexity for comma delimiter
- Semicolon alternative: Comma is more intuitive; metric names don't contain commas

---

### 3. Case-Insensitive Substring Matching

**Question**: Best approach for case-insensitive substring matching in Python?

**Findings**:
- Standard: `keyword.lower() in metric_name.lower()`
- Performance: O(n) per check, efficient for typical dataset sizes (10-50 metrics)
- Alternative: Pre-compile lowercase versions if performance becomes an issue

**Decision**: Simple string `in` operator with `.lower()` on both sides.

```python
def metric_matches_keyword(metric_name: str, keyword: str) -> bool:
    """Check if keyword appears in metric name (case-insensitive)."""
    return keyword.lower() in metric_name.lower()
```

---

### 4. Filter Integration Point

**Question**: Where in the processing pipeline should the exclusion filter be applied?

**Findings**:
- Current flow: `handle_analysis` → `organize_metrics(df)` → metric loop
- `organize_metrics` returns ordered list of metric column names
- Filter should apply to this list before the metric processing loop
- Same pattern needed in `_handle_single_analysis` and `_handle_batch_analysis`

**Decision**: Create `filter_metrics_by_keywords(ordered_metrics, keywords)` function. Call immediately after `organize_metrics()` in all three analysis functions. Return tuple of `(filtered_metrics, excluded_count)`.

```python
def filter_metrics_by_keywords(
    metrics: List[str], 
    keywords: List[str]
) -> Tuple[List[str], int]:
    """Filter out metrics matching any keyword."""
    if not keywords:
        return metrics, 0
    
    def matches_any_keyword(metric: str) -> bool:
        return any(kw.lower() in metric.lower() for kw in keywords)
    
    filtered = [m for m in metrics if not matches_any_keyword(m)]
    excluded_count = len(metrics) - len(filtered)
    return filtered, excluded_count
```

---

### 5. Live Preview Without Full Analysis

**Question**: How to show "X metrics will be excluded" before running analysis?

**Findings**:
- Need access to metric column names from uploaded file
- Cannot fully parse file on every keystroke (too expensive)
- Solution: Read only column headers when file is uploaded, cache in session state
- Preview computation: Apply same filter logic to cached column names

**Decision**: 
1. When file is uploaded, extract and cache column names in session state
2. In sidebar, if file columns cached, compute preview from keywords
3. Display: "X metrics will be excluded" or "No metrics match these keywords"

**Implementation Notes**:
- Cache key: `uploaded_file_columns`
- Column detection reuses existing logic: exclude valuedate and limit suffix columns
- Preview updates on every rerun (Streamlit handles efficiently)

---

### 6. Session State Persistence

**Question**: How to ensure keywords persist across file uploads and setting changes?

**Findings**:
- Streamlit session state persists within a session until browser refresh
- Existing pattern in app: `st.session_state.setdefault("key", default_value)`
- Text input with `value=st.session_state.get("key", "")` syncs state

**Decision**: 
- Add `exclusion_keywords_raw` to `initialize_session_state()` with default `""`
- Use as `value` parameter in `st.text_input`
- Store updated value back to session state on each rerun

---

### 7. Maximum Keywords Limit

**Question**: Should we enforce a limit on number of keywords (edge case from spec)?

**Findings**:
- Spec suggests 50 keywords max with warning
- Low priority, but prevents potential performance/UI issues
- Simple check after parsing

**Decision**: Add `MAX_EXCLUSION_KEYWORDS = 50` to config.py. If exceeded, truncate list and show warning in sidebar.

---

## Summary of Decisions

| Topic | Decision | Rationale |
|-------|----------|-----------|
| Input Component | `st.text_input` in sidebar | Consistent with existing layout |
| Keyword Parsing | Split, strip, deduplicate | Handles all edge cases |
| Matching | Case-insensitive substring | Simple, predictable, per FR-003/FR-009 |
| Live Preview | Read cached columns, apply filter | No expensive file parsing |
| Filter Point | After `organize_metrics()` | Single integration point |
| Session State | `exclusion_keywords_raw` | Persists across interactions |
| Max Keywords | 50 with warning | Prevents edge case issues |
