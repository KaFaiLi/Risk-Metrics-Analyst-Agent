# Research: Batch Visualization Enhancements

**Feature**: `001-batch-viz-enhance`  
**Date**: January 8, 2026

## Research Tasks

### 1. Streamlit Tab Navigation for Batch Results

**Question**: What is the best pattern for displaying batch results with horizontal tabs in Streamlit?

**Finding**: Streamlit provides native `st.tabs()` component that supports dynamic tab creation.

```python
# Pattern for dynamic tabs
node_names = list(batch_results.keys())
tabs = st.tabs(node_names)
for tab, node_name in zip(tabs, node_names):
    with tab:
        # Render node-specific content
        render_node_analysis(batch_results[node_name])
```

**Decision**: Use `st.tabs()` with node names as labels
**Rationale**: Native Streamlit component, clean API, supports dynamic number of tabs
**Alternatives Rejected**: 
- `st.selectbox` dropdown - Requires extra click, less visual
- `st.expander` accordion - Cluttered with many nodes
- Custom HTML tabs - Unnecessary complexity

---

### 2. Pandas Time-Based Interpolation

**Question**: How to perform linear interpolation on time series with systematic gaps?

**Finding**: Pandas `Series.interpolate(method='time')` performs time-weighted linear interpolation.

```python
# Create date range for full period
full_range = pd.date_range(start=df['valuedate'].min(), end=df['valuedate'].max(), freq='D')

# Reindex to full range (introduces NaN for missing dates)
df_full = df.set_index('valuedate').reindex(full_range)

# Interpolate metric columns (time-weighted linear)
for col in metric_columns:
    df_full[col] = df_full[col].interpolate(method='time')
```

**Decision**: Use `pandas.Series.interpolate(method='time')` after reindexing to full date range
**Rationale**: Time-aware interpolation handles irregular gaps correctly; built-in pandas function
**Alternatives Rejected**:
- `method='linear'` - Index-based, not time-aware
- `scipy.interpolate` - Over-engineered for this use case
- Forward-fill - Misrepresents trends

---

### 3. Plotly Y-Axis Range Control

**Question**: How to programmatically control Plotly chart y-axis range for adaptive scaling?

**Finding**: Plotly `fig.update_layout(yaxis=dict(range=[min, max]))` sets explicit axis range.

```python
# Calculate adaptive range with padding
data_min, data_max = metric_series.min(), metric_series.max()
padding = (data_max - data_min) * 0.1
adaptive_range = [data_min - padding, data_max + padding]

fig.update_layout(yaxis=dict(range=adaptive_range))
```

**Decision**: Use `update_layout(yaxis=dict(range=[...]))` with 10% padding
**Rationale**: Direct Plotly API, maintains interactivity (zoom/pan still works)
**Alternatives Rejected**:
- `yaxis_autorange=False` alone - Requires explicit range anyway
- Chart annotations for limits - Clutters the visualization

---

### 4. Scale Disparity Detection Algorithm

**Question**: How to detect when adaptive scaling should be applied?

**Finding**: Compare data range to combined data+limit range. If data occupies <10% of total range, apply scaling.

```python
def should_apply_adaptive_scaling(data_series, max_limit, min_limit, threshold=0.10):
    data_min, data_max = data_series.min(), data_series.max()
    data_range = data_max - data_min
    
    # Determine full range including limits
    full_min = min(data_min, min_limit.min() if min_limit is not None else data_min)
    full_max = max(data_max, max_limit.max() if max_limit is not None else data_max)
    full_range = full_max - full_min
    
    if full_range == 0:
        return False
    
    return (data_range / full_range) < threshold
```

**Decision**: Apply adaptive scaling when data range < 10% of full range (including limits)
**Rationale**: Spec-defined threshold; simple, predictable behavior
**Alternatives Rejected**:
- Dynamic thresholds - Unpredictable user experience
- User-configurable - Adds complexity without clear benefit

---

### 5. Limit Period Grouping for Annotation Banner

**Question**: How to group time-varying limits into display-friendly periods?

**Finding**: Detect value changes in limit series and group consecutive dates with same values.

```python
def group_limit_periods(dates, max_limits, min_limits):
    """Group consecutive dates with identical limit values."""
    periods = []
    current_period = None
    
    for i, date in enumerate(dates):
        max_val = max_limits.iloc[i] if max_limits is not None else None
        min_val = min_limits.iloc[i] if min_limits is not None else None
        
        if current_period is None:
            current_period = {'start': date, 'end': date, 'max': max_val, 'min': min_val}
        elif max_val == current_period['max'] and min_val == current_period['min']:
            current_period['end'] = date
        else:
            periods.append(current_period)
            current_period = {'start': date, 'end': date, 'max': max_val, 'min': min_val}
    
    if current_period:
        periods.append(current_period)
    
    return periods
```

**Decision**: Group by consecutive identical (max, min) pairs
**Rationale**: Minimizes annotation rows; captures actual limit changes
**Alternatives Rejected**:
- Fixed time buckets (monthly) - Misses actual change points
- Show all dates - Too verbose

---

### 6. Batch Export Folder Structure

**Question**: How to organize ZIP export for batch processing results?

**Finding**: Python `zipfile` supports nested folder paths in archive.

```python
with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    for node_name, analyses in batch_results.items():
        # Sanitize node name for filesystem
        safe_name = sanitize_filename(node_name)
        
        # Add HTML report
        html_content = create_html_report(analyses, ...)
        zf.writestr(f"{safe_name}/report.html", html_content)
        
        # Add chart images
        for analysis in analyses:
            img_data = pio.to_image(analysis['fig'], format='png')
            metric_safe = sanitize_filename(analysis['metric'])
            zf.writestr(f"{safe_name}/charts/{metric_safe}.png", img_data)
```

**Decision**: Structure as `/{NodeName}/report.html` and `/{NodeName}/charts/*.png`
**Rationale**: Matches clarified requirement; intuitive for users sharing node-specific results
**Alternatives Rejected**:
- Flat structure - Hard to navigate with many nodes
- By type first - Splits related artifacts

---

### 7. Session State Design for Batch Results

**Question**: How to store batch processing results for tab navigation without re-processing?

**Finding**: Extend existing `st.session_state` pattern with node-keyed dictionary.

```python
# In initialize_session_state()
st.session_state.setdefault("batch_mode", False)
st.session_state.setdefault("batch_results", {})  # Dict[node_name, List[metric_analysis]]
st.session_state.setdefault("batch_node_names", [])
st.session_state.setdefault("current_portfolio_summaries", {})  # Dict[node_name, str]
```

**Decision**: Store `batch_results` as `Dict[str, List[dict]]` keyed by node name
**Rationale**: Matches existing `metrics_analyses` structure per node; enables tab switching without recomputation
**Alternatives Rejected**:
- Flat list with node attribute - Harder to filter by node
- Separate session keys per node - Unbounded key creation

---

## Summary

All research questions resolved. Key technology choices:
- **Streamlit `st.tabs()`** for batch result navigation
- **Pandas `interpolate(method='time')`** for gap filling
- **Plotly `yaxis.range`** for adaptive scaling
- **10% threshold** for scale disparity detection
- **Consecutive value grouping** for limit period annotation
- **Node-folder ZIP structure** for batch exports
