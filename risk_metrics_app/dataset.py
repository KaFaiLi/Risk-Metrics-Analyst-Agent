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
