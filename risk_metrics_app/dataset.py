"""Wide -> long transform that feeds the Power BI dataset and the HTML report.

The long table has one row per (node, valuedate, metric). New metrics arrive as
new rows, never new columns, so downstream consumers absorb them automatically.
"""
from typing import Dict, List

import numpy as np
import pandas as pd

from .metrics import (
    LIMIT_MAX_SUFFIX,
    LIMIT_MIN_SUFFIX,
    VALUE_DATE_COLUMN,
    calculate_statistics,
)

LONG_COLUMNS = [
    "node",
    "valuedate",
    "metric",
    "value",
    "limit_max",
    "limit_min",
    "is_breach_max",
    "is_breach_min",
    "is_outlier",
    "sort_order",
]


def build_node_long_df(
    df: pd.DataFrame,
    ordered_metrics: List[str],
    node_name: str,
    sort_order_map: Dict[str, int],
) -> pd.DataFrame:
    """Build the long-format rows for one node.

    Args:
        df: One node's wide DataFrame (lowercase columns, parsed valuedate).
        ordered_metrics: Metric columns to emit, already priority/maturity ordered.
        node_name: Value for the ``node`` column.
        sort_order_map: Maps metric -> integer facet order.

    Returns:
        DataFrame with the columns listed in ``LONG_COLUMNS``.
    """
    frames: List[pd.DataFrame] = []

    for metric in ordered_metrics:
        if metric not in df.columns:
            continue

        value = df[metric].reset_index(drop=True)
        dates = df[VALUE_DATE_COLUMN].reset_index(drop=True)

        max_col = f"{metric}{LIMIT_MAX_SUFFIX}"
        min_col = f"{metric}{LIMIT_MIN_SUFFIX}"
        limit_max = (
            df[max_col].ffill().reset_index(drop=True)
            if max_col in df.columns
            else pd.Series([np.nan] * len(df))
        )
        limit_min = (
            df[min_col].ffill().reset_index(drop=True)
            if min_col in df.columns
            else pd.Series([np.nan] * len(df))
        )

        is_breach_max = (value > limit_max).fillna(False)
        is_breach_min = (value < limit_min).fillna(False)

        stats, _ = calculate_statistics(df[metric])
        if stats["std"] and stats["std"] > 0:
            is_outlier = ((value - stats["mean"]).abs() > 2 * stats["std"]).fillna(False)
        else:
            is_outlier = pd.Series([False] * len(df))

        frames.append(
            pd.DataFrame(
                {
                    "node": node_name,
                    "valuedate": dates,
                    "metric": metric,
                    "value": value,
                    "limit_max": limit_max,
                    "limit_min": limit_min,
                    "is_breach_max": is_breach_max.astype(bool),
                    "is_breach_min": is_breach_min.astype(bool),
                    "is_outlier": is_outlier.astype(bool),
                    "sort_order": sort_order_map.get(metric, len(sort_order_map)),
                }
            )
        )

    if not frames:
        return pd.DataFrame(columns=LONG_COLUMNS)

    return pd.concat(frames, ignore_index=True)[LONG_COLUMNS]


def build_long_dataset(
    node_frames: Dict[str, pd.DataFrame],
    ordered_metrics: List[str],
) -> pd.DataFrame:
    """Concatenate per-node long frames into one dataset.

    Args:
        node_frames: Maps node name -> that node's wide DataFrame. Use
            ``{"__single__": df}`` in single (non-batch) mode.
        ordered_metrics: Canonical priority/maturity-ordered metric list shared
            across nodes; its index becomes each metric's ``sort_order``.

    Returns:
        Combined long-format DataFrame (columns = ``LONG_COLUMNS``).
    """
    sort_order_map = {metric: idx for idx, metric in enumerate(ordered_metrics)}

    frames = [
        build_node_long_df(df, ordered_metrics, node_name, sort_order_map)
        for node_name, df in node_frames.items()
    ]
    frames = [f for f in frames if not f.empty]

    if not frames:
        return pd.DataFrame(columns=LONG_COLUMNS)

    return pd.concat(frames, ignore_index=True)


def write_long_dataset_csv(long_df: pd.DataFrame, path: str) -> str:
    """Write the long dataset to CSV. Returns the path written."""
    long_df.to_csv(path, index=False, date_format="%Y-%m-%d")
    return path


def write_long_dataset_parquet(long_df: pd.DataFrame, path: str) -> str:
    """Write the long dataset to Parquet. Returns the path written.

    Requires a Parquet engine (``pyarrow`` or ``fastparquet``). The
    ``valuedate`` column keeps its native datetime dtype so downstream
    consumers get proper timestamps rather than strings.
    """
    long_df.to_parquet(path, index=False)
    return path


__all__ = [
    "LONG_COLUMNS",
    "build_node_long_df",
    "build_long_dataset",
    "write_long_dataset_csv",
    "write_long_dataset_parquet",
]
