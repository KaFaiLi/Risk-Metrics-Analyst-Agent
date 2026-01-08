# Quickstart: Batch Visualization Enhancements

**Feature**: `001-batch-viz-enhance`  
**Date**: January 8, 2026

## Overview

This feature adds three enhancements to the Risk Metrics Analyst application:

1. **Batch Processing** - Analyze multiple portfolios/nodes in a single upload
2. **Adaptive Graph Scaling** - Readable charts when data is small relative to limits
3. **Missing Data Interpolation** - Continuous line charts for business-day data

## Prerequisites

- Python 3.11+
- Existing development environment set up per main README
- Sample data: `Examples/Fake Pivot Metrics.csv` (contains `stranaNodeName` column)

## Quick Setup

```powershell
# Activate virtual environment
cd P:\Alan\Github\Risk-Metrics-Analyst-Agent
.\.venv\Scripts\Activate.ps1

# Install dependencies (if not already done)
pip install -r requirements.txt

# Run the application
streamlit run app_main.py
```

## Feature Testing

### 1. Batch Processing

**Test Data**: Use `Examples/Fake Pivot Metrics.csv` which contains `stranaNodeName` with values "a" and "b"

**Steps**:
1. Upload the CSV file
2. Observe "Batch Mode" checkbox appears (node column detected)
3. Enable batch mode
4. Click "Analyze Risk Metrics"
5. Verify tabs appear for each node ("a", "b")
6. Switch between tabs to view node-specific analyses
7. Export and verify ZIP structure has `/a/` and `/b/` folders

### 2. Adaptive Graph Scaling

**Test Data**: Create/modify CSV where metric values are 0-100 but limits are ±100,000

**Steps**:
1. Upload CSV with scale disparity
2. Run analysis
3. Observe chart zooms to data range
4. Verify annotation banner shows limit values with date periods
5. Toggle "Show Full Scale" to see limits on chart
6. Toggle back to adaptive view

### 3. Missing Data Interpolation

**Test Data**: Create CSV with business-day-only data (skip weekends)

**Steps**:
1. Upload CSV with systematic gaps
2. Run analysis
3. Observe continuous line chart on time-scaled x-axis
4. Verify statistics use original data only (check mean/median values)
5. Verify outlier markers appear on actual data points only

## Key Files to Modify

| File | Changes |
|------|---------|
| `risk_metrics_app/config.py` | Add `NODE_COLUMN` constant |
| `risk_metrics_app/metrics.py` | Add `detect_node_column()`, `split_by_node()`, `interpolate_for_display()` |
| `risk_metrics_app/visuals.py` | Add `calculate_scale_context()`, `group_limit_periods()`, modify `create_plotly_chart()` |
| `risk_metrics_app/app.py` | Add batch UI flow, adaptive toggle, session state extensions |
| `risk_metrics_app/reporting.py` | Add `create_batch_export_package()` |

## Architecture Notes

### Session State Structure

```python
st.session_state = {
    # Existing keys (unchanged)
    "metrics_analyses": [...],
    "portfolio_summary": "...",
    "analysis_completed": True,
    
    # New batch processing keys
    "batch_mode": False,
    "batch_results": {
        "NodeA": [...],  # List of metric analyses
        "NodeB": [...]
    },
    "batch_node_names": ["NodeA", "NodeB"],
    "batch_portfolio_summaries": {
        "NodeA": "...",
        "NodeB": "..."
    },
    
    # New scaling keys
    "scale_contexts": {
        "VaR": ScaleContext(...),
        "SVaR": ScaleContext(...)
    },
    "adaptive_scale_toggles": {
        "VaR": True,  # True = adaptive, False = full scale
        "SVaR": True
    }
}
```

### Data Flow

```
CSV Upload
    ↓
detect_node_column() → batch_mode available?
    ↓
split_by_node() → Dict[node_name, DataFrame]
    ↓
For each node:
    ↓
    interpolate_for_display() → InterpolatedSeries
    ↓
    calculate_statistics(original) → stats, outliers
    ↓
    calculate_scale_context() → ScaleContext
    ↓
    create_plotly_chart(display_series, scale_context)
    ↓
    Store in batch_results[node_name]
    ↓
Display via st.tabs()
```

## Common Issues

### Chart Line Disappears
- **Cause**: Gaps in time series data
- **Fix**: Ensure `interpolate_for_display()` is called and `display_series` passed to chart

### Tabs Don't Appear
- **Cause**: `stranaNodeName` column not detected (case mismatch)
- **Fix**: Check `detect_node_column()` uses case-insensitive matching

### Statistics Seem Wrong
- **Cause**: Interpolated data used for statistics
- **Fix**: Verify `calculate_statistics()` receives `InterpolatedSeries.original`

### Export Missing Node Folders
- **Cause**: Using single-mode export function
- **Fix**: Call `create_batch_export_package()` when `batch_mode` is True

## Next Steps

See [tasks.md](tasks.md) (generated via `/speckit.tasks`) for implementation checklist.
