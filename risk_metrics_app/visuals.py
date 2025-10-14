import base64
import os
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from .config import OUTPUT_DIR, logger
from .metrics import VALUE_DATE_COLUMN


def create_plotly_chart(
    df: pd.DataFrame,
    metric_name: str,
    stats: dict,
    outliers: pd.Series,
    max_limit: Optional[pd.Series] = None,
    min_limit: Optional[pd.Series] = None,
) -> go.Figure:
    """Create an interactive Plotly chart with statistics, limits, and outliers."""
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df[VALUE_DATE_COLUMN],
            y=df[metric_name],
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

    fig.update_layout(
        title=f"{metric_name} Analysis",
        xaxis_title="Date",
        yaxis_title="Value",
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


__all__ = ["create_plotly_chart", "save_and_encode_image"]
