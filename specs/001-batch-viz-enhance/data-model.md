# Data Model: Batch Visualization Enhancements

**Feature**: `001-batch-viz-enhance`  
**Date**: January 8, 2026

## Entities

### NodeGroup

A logical partition of the uploaded dataset identified by a unique `stranaNodeName` value.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | The unique node identifier from `stranaNodeName` column |
| `data` | `pd.DataFrame` | Filtered DataFrame containing only rows for this node |
| `row_count` | `int` | Number of data points in this node |
| `metrics_analyses` | `List[dict]` | Per-metric analysis results (same structure as existing `metrics_analyses`) |
| `portfolio_summary` | `Optional[str]` | AI-generated portfolio summary for this node (if LLM enabled) |

**Relationships**:
- One NodeGroup contains many MetricAnalysis records
- NodeGroups are derived from a single uploaded DataFrame

---

### ScaleContext

Metadata about a chart's y-axis scaling state and limit information.

| Field | Type | Description |
|-------|------|-------------|
| `data_min` | `float` | Minimum value in the metric data series |
| `data_max` | `float` | Maximum value in the metric data series |
| `limit_min` | `Optional[float]` | Minimum value across all min limit values (if present) |
| `limit_max` | `Optional[float]` | Maximum value across all max limit values (if present) |
| `full_range` | `float` | Total range from min(data, limits) to max(data, limits) |
| `data_range` | `float` | Range of actual data values (data_max - data_min) |
| `scale_ratio` | `float` | Ratio of data_range to full_range (0.0 to 1.0) |
| `adaptive_applied` | `bool` | Whether adaptive scaling is currently active |
| `limit_periods` | `List[LimitPeriod]` | Grouped limit values by time period |

**Validation Rules**:
- `adaptive_applied` is `True` when `scale_ratio < 0.10` (10% threshold)
- `limit_periods` is populated only when `adaptive_applied` is `True`

---

### LimitPeriod

A time period with constant limit values, used for annotation display.

| Field | Type | Description |
|-------|------|-------------|
| `start_date` | `datetime` | First date in this period |
| `end_date` | `datetime` | Last date in this period |
| `max_limit` | `Optional[float]` | Max limit value for this period (None if not set) |
| `min_limit` | `Optional[float]` | Min limit value for this period (None if not set) |

**Validation Rules**:
- `start_date <= end_date`
- At least one of `max_limit` or `min_limit` must be non-None

---

### InterpolatedSeries

Container for original and display-ready interpolated time series data.

| Field | Type | Description |
|-------|------|-------------|
| `original` | `pd.Series` | Original metric values (used for statistics) |
| `display` | `pd.Series` | Interpolated values on full date range (used for charting) |
| `original_dates` | `pd.DatetimeIndex` | Dates present in original data |
| `full_dates` | `pd.DatetimeIndex` | Complete date range (daily) |
| `gap_count` | `int` | Number of interpolated (filled) dates |
| `coverage_pct` | `float` | Percentage of dates with original data |

**Validation Rules**:
- `len(display) >= len(original)`
- Statistics (mean, std, outliers) calculated from `original` only

---

## Function Signatures

### metrics.py - New Functions

```python
NODE_COLUMN = "strananodename"  # Case-insensitive detection target

def detect_node_column(df: pd.DataFrame) -> Optional[str]:
    """
    Detect presence of stranaNodeName column (case-insensitive).
    
    Returns the actual column name if found, None otherwise.
    """
    pass

def split_by_node(df: pd.DataFrame, node_column: str) -> Dict[str, pd.DataFrame]:
    """
    Split DataFrame by unique values in node column.
    
    Returns dict mapping node name -> filtered DataFrame.
    Preserves all columns; each DataFrame is independent copy.
    """
    pass

def detect_systematic_gaps(dates: pd.DatetimeIndex) -> Dict[str, Any]:
    """
    Analyze date series for systematic missing patterns.
    
    Returns:
        {
            'has_gaps': bool,
            'gap_count': int,
            'coverage_pct': float,
            'pattern': Optional[str]  # e.g., 'weekends', 'every_2_days', None
        }
    """
    pass

def interpolate_for_display(
    df: pd.DataFrame, 
    metric_column: str,
    date_column: str = VALUE_DATE_COLUMN
) -> InterpolatedSeries:
    """
    Create interpolated series for chart display.
    
    Uses pandas time-based linear interpolation.
    Original series preserved for statistics.
    """
    pass
```

### visuals.py - New/Modified Functions

```python
def calculate_scale_context(
    data_series: pd.Series,
    max_limit: Optional[pd.Series],
    min_limit: Optional[pd.Series],
    dates: pd.Series,
    threshold: float = 0.10
) -> ScaleContext:
    """
    Calculate scaling metadata for adaptive chart rendering.
    
    Sets adaptive_applied=True if data occupies < threshold of full range.
    Populates limit_periods when adaptive scaling is needed.
    """
    pass

def group_limit_periods(
    dates: pd.Series,
    max_limits: Optional[pd.Series],
    min_limits: Optional[pd.Series]
) -> List[LimitPeriod]:
    """
    Group consecutive dates with identical limit values.
    
    Used to create annotation banner showing limit changes over time.
    """
    pass

def create_limit_annotation_html(limit_periods: List[LimitPeriod]) -> str:
    """
    Generate HTML for limit annotation banner.
    
    Format:
    <div class="limit-annotation">
        <p>📊 Adaptive scaling applied - limits outside view:</p>
        <table>
            <tr><td>2025-01-01 to 2025-01-30</td><td>Min: -10,000</td><td>Max: 40,000</td></tr>
            ...
        </table>
    </div>
    """
    pass

def create_plotly_chart(
    df: pd.DataFrame,
    metric_name: str,
    stats: dict,
    outliers: pd.Series,
    max_limit: Optional[pd.Series] = None,
    min_limit: Optional[pd.Series] = None,
    scale_context: Optional[ScaleContext] = None,  # NEW PARAMETER
    display_series: Optional[pd.Series] = None,    # NEW PARAMETER (interpolated)
) -> go.Figure:
    """
    Create interactive Plotly chart with optional adaptive scaling.
    
    If scale_context.adaptive_applied is True:
    - Sets yaxis.range to data range with 10% padding
    - Limit lines may be outside visible area
    
    If display_series provided:
    - Uses display_series for line plotting (interpolated)
    - Uses original df[metric_name] for outlier markers
    """
    pass
```

### reporting.py - Modified Functions

```python
def create_batch_export_package(
    batch_results: Dict[str, List[dict]],  # node_name -> metrics_analyses
    portfolio_summaries: Dict[str, Optional[str]],
    file_name: str,
    use_llm: bool
) -> BytesIO:
    """
    Create ZIP archive with node-organized folder structure.
    
    Structure:
    /{NodeA}/
        report.html
        charts/
            VaR.png
            SVaR.png
            ...
    /{NodeB}/
        ...
    summary.txt (combined summary)
    """
    pass
```

### app.py - Session State Extensions

```python
# Additional session state keys
st.session_state.setdefault("batch_mode", False)
st.session_state.setdefault("batch_results", {})  # Dict[str, List[dict]]
st.session_state.setdefault("batch_node_names", [])
st.session_state.setdefault("batch_portfolio_summaries", {})  # Dict[str, str]
st.session_state.setdefault("scale_contexts", {})  # Dict[metric, ScaleContext]
st.session_state.setdefault("adaptive_scale_toggles", {})  # Dict[metric, bool]
```

---

## State Transitions

### Batch Processing Flow

```
[Upload CSV] 
    → detect_node_column()
    → If found: show batch toggle
    
[Enable Batch Mode]
    → split_by_node()
    → Store node_names in session
    
[Run Analysis]
    → For each node:
        → Filter df by node
        → Run existing analysis pipeline
        → Store in batch_results[node_name]
    → Update progress bar
    
[Display Results]
    → Create tabs from node_names
    → Each tab renders from batch_results[node_name]
    
[Export]
    → create_batch_export_package() with node folder structure
```

### Adaptive Scaling Flow

```
[Per Metric]
    → calculate_scale_context(data, limits)
    → If adaptive_applied:
        → create_plotly_chart() with constrained yaxis
        → create_limit_annotation_html()
        → Display annotation above chart
    → Else:
        → Standard chart with full range
    
[Toggle Clicked]
    → Flip scale_contexts[metric].adaptive_applied
    → Re-render chart with updated range
```

### Interpolation Flow

```
[Per Metric]
    → interpolate_for_display(df, metric)
    → Pass InterpolatedSeries.display to chart
    → Pass InterpolatedSeries.original to calculate_statistics()
    → Outliers marked on original data points only
```
