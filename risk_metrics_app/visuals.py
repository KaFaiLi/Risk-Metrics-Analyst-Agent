import base64
import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from .config import ADAPTIVE_SCALE_THRESHOLD, OUTPUT_DIR, logger
from .metrics import VALUE_DATE_COLUMN, InterpolatedSeries


@dataclass
class LimitPeriod:
    """Represents limit values for a specific time period.
    
    Attributes:
        start_date: Beginning of the period.
        end_date: End of the period.
        max_limit: Maximum limit value (None if not applicable).
        min_limit: Minimum limit value (None if not applicable).
    """
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    max_limit: Optional[float] = None
    min_limit: Optional[float] = None


@dataclass
class ScaleContext:
    """Context for adaptive chart scaling when data range is much smaller than limits.
    
    Attributes:
        needs_adaptive_scaling: True if adaptive scaling should be applied.
        data_range: Tuple of (min, max) for the actual data values.
        limit_range: Tuple of (min, max) including limit lines.
        limit_periods: List of LimitPeriod objects for annotation display.
        scale_ratio: Ratio of data range to limit range (triggers if < threshold).
    """
    needs_adaptive_scaling: bool = False
    data_range: Tuple[float, float] = (0.0, 0.0)
    limit_range: Tuple[float, float] = (0.0, 0.0)
    limit_periods: List[LimitPeriod] = field(default_factory=list)
    scale_ratio: float = 1.0


def calculate_scale_context(
    data: pd.Series,
    dates: pd.Series,
    max_limit: Optional[pd.Series] = None,
    min_limit: Optional[pd.Series] = None,
) -> ScaleContext:
    """Calculate whether adaptive scaling is needed and gather limit period info.
    
    Adaptive scaling is triggered when the data range occupies less than
    ADAPTIVE_SCALE_THRESHOLD (10%) of the total y-axis range including limits.
    
    Args:
        data: The metric data series.
        dates: The date series for grouping limit periods.
        max_limit: Optional series of maximum limit values.
        min_limit: Optional series of minimum limit values.
        
    Returns:
        ScaleContext with scaling decision and limit period information.
    """
    data_clean = data.dropna()
    if data_clean.empty:
        return ScaleContext()
    
    data_min = float(data_clean.min())
    data_max = float(data_clean.max())
    data_range = data_max - data_min
    
    # Calculate limit range
    limit_min = data_min
    limit_max = data_max
    
    has_limits = False
    if max_limit is not None and not max_limit.isna().all():
        limit_max = max(limit_max, float(max_limit.max()))
        has_limits = True
    if min_limit is not None and not min_limit.isna().all():
        limit_min = min(limit_min, float(min_limit.min()))
        has_limits = True
    
    limit_range = limit_max - limit_min
    
    # Calculate scale ratio
    if limit_range > 0:
        scale_ratio = data_range / limit_range
    else:
        scale_ratio = 1.0
    
    needs_scaling = has_limits and scale_ratio < ADAPTIVE_SCALE_THRESHOLD
    
    # Build limit periods for annotation
    limit_periods = _build_limit_periods(dates, max_limit, min_limit)
    
    return ScaleContext(
        needs_adaptive_scaling=needs_scaling,
        data_range=(data_min, data_max),
        limit_range=(limit_min, limit_max),
        limit_periods=limit_periods,
        scale_ratio=scale_ratio,
    )


def _build_limit_periods(
    dates: pd.Series,
    max_limit: Optional[pd.Series],
    min_limit: Optional[pd.Series],
) -> List[LimitPeriod]:
    """Build a list of LimitPeriod objects grouped by changing limit values.
    
    Groups consecutive dates with the same limit values into periods.
    """
    if dates.empty:
        return []
    
    periods: List[LimitPeriod] = []
    
    # Get limit values aligned with dates
    max_vals = max_limit.values if max_limit is not None else [None] * len(dates)
    min_vals = min_limit.values if min_limit is not None else [None] * len(dates)
    date_vals = pd.to_datetime(dates).values
    
    current_start = date_vals[0]
    current_max = max_vals[0] if max_vals[0] is not None and not pd.isna(max_vals[0]) else None
    current_min = min_vals[0] if min_vals[0] is not None and not pd.isna(min_vals[0]) else None
    
    for i in range(1, len(dates)):
        this_max = max_vals[i] if max_vals[i] is not None and not pd.isna(max_vals[i]) else None
        this_min = min_vals[i] if min_vals[i] is not None and not pd.isna(min_vals[i]) else None
        
        # Check if limit values changed
        if this_max != current_max or this_min != current_min:
            # Save current period
            if current_max is not None or current_min is not None:
                periods.append(LimitPeriod(
                    start_date=pd.Timestamp(current_start),
                    end_date=pd.Timestamp(date_vals[i - 1]),
                    max_limit=current_max,
                    min_limit=current_min,
                ))
            # Start new period
            current_start = date_vals[i]
            current_max = this_max
            current_min = this_min
    
    # Don't forget the last period
    if current_max is not None or current_min is not None:
        periods.append(LimitPeriod(
            start_date=pd.Timestamp(current_start),
            end_date=pd.Timestamp(date_vals[-1]),
            max_limit=current_max,
            min_limit=current_min,
        ))
    
    return periods


def create_limit_annotation_html(scale_context: ScaleContext) -> str:
    """Generate HTML banner showing off-screen limit values grouped by period.
    
    Args:
        scale_context: ScaleContext with limit_periods populated.
        
    Returns:
        HTML string for the annotation banner.
    """
    if not scale_context.limit_periods:
        return ""
    
    lines = ['<div style="background-color: #fff3cd; border: 1px solid #ffc107; '
             'border-radius: 4px; padding: 10px; margin: 10px 0;">']
    lines.append('<strong>📊 Limit Values (not shown on chart - adaptive scaling applied):</strong>')
    lines.append('<ul style="margin: 5px 0; padding-left: 20px;">')
    
    for period in scale_context.limit_periods:
        date_range = f"{period.start_date.strftime('%Y-%m-%d')} to {period.end_date.strftime('%Y-%m-%d')}"
        limits_text = []
        if period.max_limit is not None:
            limits_text.append(f"Max: {period.max_limit:,.2f}")
        if period.min_limit is not None:
            limits_text.append(f"Min: {period.min_limit:,.2f}")
        
        if limits_text:
            lines.append(f'<li><strong>{date_range}:</strong> {" | ".join(limits_text)}</li>')
    
    lines.append('</ul></div>')
    
    return '\n'.join(lines)


def create_plotly_chart(
    df: pd.DataFrame,
    metric_name: str,
    stats: dict,
    outliers: pd.Series,
    max_limit: Optional[pd.Series] = None,
    min_limit: Optional[pd.Series] = None,
    scale_context: Optional[ScaleContext] = None,
    display_series: Optional[InterpolatedSeries] = None,
) -> go.Figure:
    """Create an interactive Plotly chart with statistics, limits, and outliers.
    
    Args:
        df: DataFrame containing the data.
        metric_name: Name of the metric column.
        stats: Dictionary of calculated statistics.
        outliers: Series of outlier values.
        max_limit: Optional series of maximum limit values.
        min_limit: Optional series of minimum limit values.
        scale_context: Optional ScaleContext for adaptive scaling.
        display_series: Optional InterpolatedSeries for gap-filled display.
    """
    fig = go.Figure()

    # Use interpolated display series if provided, otherwise use original data
    if display_series is not None:
        y_data = display_series.display
    else:
        y_data = df[metric_name]

    fig.add_trace(
        go.Scatter(
            x=df[VALUE_DATE_COLUMN],
            y=y_data,
            mode="lines",
            name=f"{metric_name}",
            line=dict(color="#1f77b4", width=2),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df[VALUE_DATE_COLUMN],
            y=[stats["mean"]] * len(df),
            mode="lines",
            name=f"Mean ({stats['mean']:.4f})",
            line=dict(color="green", width=2, dash="dash"),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df[VALUE_DATE_COLUMN],
            y=[stats["median"]] * len(df),
            mode="lines",
            name=f"Median ({stats['median']:.4f})",
            line=dict(color="orange", width=2, dash="dot"),
        )
    )

    # Determine if we should show limit lines
    show_limits = True
    if scale_context is not None and scale_context.needs_adaptive_scaling:
        show_limits = False  # Hide limits when adaptive scaling is active

    if show_limits:
        if max_limit is not None and not max_limit.isna().all():
            fig.add_trace(
                go.Scatter(
                    x=df[VALUE_DATE_COLUMN],
                    y=max_limit,
                    mode="lines",
                    name="Max Limit",
                    line=dict(color="red", width=2, dash="dashdot"),
                )
            )

        if min_limit is not None and not min_limit.isna().all():
            fig.add_trace(
                go.Scatter(
                    x=df[VALUE_DATE_COLUMN],
                    y=min_limit,
                    mode="lines",
                    name="Min Limit",
                    line=dict(color="purple", width=2, dash="dashdot"),
                )
            )

    if len(outliers) > 0:
        outlier_dates = df.loc[outliers.index, VALUE_DATE_COLUMN]
        fig.add_trace(
            go.Scatter(
                x=outlier_dates,
                y=outliers,
                mode="markers",
                name="Outliers (±2 SD)",
                marker=dict(color="red", size=10, symbol="circle-open", line=dict(width=2)),
            )
        )

    # Apply adaptive scaling if needed
    y_axis_config = dict(title="Value")
    if scale_context is not None and scale_context.needs_adaptive_scaling:
        # Add padding to data range (10% on each side)
        data_min, data_max = scale_context.data_range
        padding = (data_max - data_min) * 0.1 if data_max != data_min else abs(data_min) * 0.1
        y_axis_config["range"] = [data_min - padding, data_max + padding]

    fig.update_layout(
        title=f"{metric_name} Analysis",
        xaxis_title="Date",
        yaxis=y_axis_config,
        hovermode="x unified",
        template="plotly_white",
        height=500,
        showlegend=False,
    )

    return fig


def save_and_encode_image(fig: go.Figure, metric_name: str) -> str:
    """Persist a Plotly figure to PNG and return a base64-encoded string."""
    filename = f"{metric_name.replace('/', '_')}_chart.png"
    file_path = os.path.join(OUTPUT_DIR, filename)
    pio.write_image(fig, file=file_path, format="png", width=1200, height=600, scale=2)
    logger.info("Saved chart to %s", file_path)

    with open(file_path, "rb") as img_file:
        img_base64 = base64.b64encode(img_file.read()).decode()

    return img_base64


__all__ = [
    "LimitPeriod",
    "ScaleContext",
    "calculate_scale_context",
    "create_limit_annotation_html",
    "create_plotly_chart",
    "save_and_encode_image",
]
