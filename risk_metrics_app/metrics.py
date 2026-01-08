import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd

from risk_metrics_app.config import NODE_COLUMN

PRIORITY_METRICS = ["VaR", "SVaR", "STTHH"]

VALUE_DATE_COLUMN = "valuedate"
LIMIT_MAX_SUFFIX = "_limmaxvalue"
LIMIT_MIN_SUFFIX = "_limminvalue"


@dataclass
class InterpolatedSeries:
    """Container for interpolated time series data.
    
    Attributes:
        display: Interpolated series for chart rendering (fills gaps).
        original: Original series with NaN preserved for accurate statistics.
    """
    display: pd.Series
    original: pd.Series


def detect_node_column(df: pd.DataFrame) -> Optional[str]:
    """Detect the stranaNodeName column in a case-insensitive manner.
    
    Args:
        df: DataFrame to search for node column.
        
    Returns:
        The actual column name if found, None otherwise.
    """
    for col in df.columns:
        if col.lower() == NODE_COLUMN:
            return col
    return None


def split_by_node(df: pd.DataFrame, node_column: str) -> Dict[str, pd.DataFrame]:
    """Split DataFrame into separate DataFrames by unique node values.
    
    Args:
        df: DataFrame containing the node column.
        node_column: The name of the column to split by.
        
    Returns:
        Dictionary mapping node names to filtered DataFrames.
    """
    result: Dict[str, pd.DataFrame] = {}
    unique_nodes = df[node_column].dropna().unique()
    
    for node in sorted(unique_nodes):
        node_df = df[df[node_column] == node].copy()
        # Drop the node column as it's no longer needed after splitting
        node_df = node_df.drop(columns=[node_column])
        result[str(node)] = node_df
    
    return result


def interpolate_for_display(series: pd.Series, date_index: pd.DatetimeIndex) -> InterpolatedSeries:
    """Interpolate time series to fill systematic gaps for chart display.
    
    Uses time-based linear interpolation to fill NaN values while preserving
    the original series for accurate statistical calculations.
    
    Args:
        series: Original data series with potential NaN gaps.
        date_index: DatetimeIndex to use for time-based interpolation.
        
    Returns:
        InterpolatedSeries with both display (interpolated) and original data.
    """
    # Create a series with datetime index for time-based interpolation
    indexed_series = pd.Series(series.values, index=date_index)
    
    # Apply time-based linear interpolation
    interpolated = indexed_series.interpolate(method='time')
    
    # Convert back to regular index matching original
    display_series = pd.Series(interpolated.values, index=series.index, name=series.name)
    
    return InterpolatedSeries(
        display=display_series,
        original=series.copy()
    )


def _strip_limit_suffix(column_name: str) -> str:
    """Remove known limit suffixes from a column name in a case-insensitive way."""
    stripped = re.sub(r"(?i)_limmaxvalue$", "", column_name)
    stripped = re.sub(r"(?i)_limminvalue$", "", stripped)
    return stripped


def parse_metric_name(column_name: str) -> Tuple[str, Optional[str]]:
    """Parse metric name to extract base name and optional maturity code."""
    base_name = _strip_limit_suffix(column_name)

    basis_match = re.match(r"(?i)BasisSensiByCurrencyByPillar\[(\w+)\]\[(\w+)\]", base_name)
    if basis_match:
        currency = basis_match.group(1)
        maturity = basis_match.group(2)
        return f"BasisSensi_{currency}", maturity

    maturity_match = re.search(r"(?i)(\d+)([DWMY])", base_name)
    if maturity_match:
        value_part = maturity_match.group(1)
        unit_part = maturity_match.group(2).upper()
        maturity = f"{value_part}{unit_part}"
        base_without_maturity = base_name[:maturity_match.start()] + base_name[maturity_match.end():]
        base_without_maturity = base_without_maturity.strip("_") or base_name
        return base_without_maturity, maturity

    return base_name, None


def get_maturity_order(maturity: Optional[str]) -> int:
    """Convert maturity string to a sortable integer representing days."""
    if not maturity:
        return 0

    match = re.match(r"(?i)(\d+)([DWMY])", maturity)
    if not match:
        return 0

    value = int(match.group(1))
    unit = match.group(2).upper()
    multipliers = {"D": 1, "W": 7, "M": 30, "Y": 365}
    return value * multipliers.get(unit, 0)


def organize_metrics(df: pd.DataFrame) -> List[str]:
    """Organize metric columns by priority and maturity."""
    metric_columns = [
        col
        for col in df.columns
        if col.lower() != VALUE_DATE_COLUMN
        and not col.lower().endswith(LIMIT_MAX_SUFFIX)
        and not col.lower().endswith(LIMIT_MIN_SUFFIX)
    ]

    priority_cols = []
    for metric in PRIORITY_METRICS:
        metric_lower = metric.lower()
        for col in metric_columns:
            if col.lower() == metric_lower:
                priority_cols.append(col)

    other_cols = [col for col in metric_columns if col not in priority_cols]

    parsed_metrics = []
    for col in other_cols:
        base_name, maturity = parse_metric_name(col)
        maturity_order = get_maturity_order(maturity)
        parsed_metrics.append((col, base_name, maturity, maturity_order))

    def sort_key(item: Tuple[str, str, Optional[str], int]) -> Tuple[str, int, int, str]:
        column, base_name, maturity, maturity_order = item
        maturity_flag = 0 if maturity is None else 1
        return (base_name.lower(), maturity_flag, maturity_order, column)

    parsed_metrics.sort(key=sort_key)
    sorted_other_cols = [m[0] for m in parsed_metrics]

    return priority_cols + sorted_other_cols


def calculate_statistics(data: pd.Series) -> Tuple[dict, pd.Series]:
    """Calculate summary statistics and identify ±2σ outliers."""
    stats = {
        "mean": data.mean(),
        "median": data.median(),
        "std": data.std(),
        "min": data.min(),
        "max": data.max(),
        "count": len(data),
    }

    if stats["std"] > 0:
        upper_threshold = stats["mean"] + 2 * stats["std"]
        lower_threshold = stats["mean"] - 2 * stats["std"]
        outliers = data[(data > upper_threshold) | (data < lower_threshold)]
    else:
        outliers = pd.Series(dtype=float)

    return stats, outliers


def check_limit_breaches(
    df: pd.DataFrame,
    metric_name: str,
    max_limit=None,
    min_limit=None,
) -> List[dict]:
    """Check for limit breaches for a given metric."""
    breaches: List[dict] = []
    if max_limit is not None:
        max_breaches = df[df[metric_name] > max_limit]
        if not max_breaches.empty:
            breach_dates = max_breaches[VALUE_DATE_COLUMN].dt.strftime("%Y-%m-%d").tolist()
            breaches.append(
                {
                    "type": "max",
                    "count": len(max_breaches),
                    "dates": breach_dates,
                }
            )
    if min_limit is not None:
        min_breaches = df[df[metric_name] < min_limit]
        if not min_breaches.empty:
            breach_dates = min_breaches[VALUE_DATE_COLUMN].dt.strftime("%Y-%m-%d").tolist()
            breaches.append(
                {
                    "type": "min",
                    "count": len(min_breaches),
                    "dates": breach_dates,
                }
            )

    return breaches


__all__ = [
    "PRIORITY_METRICS",
    "LIMIT_MAX_SUFFIX",
    "LIMIT_MIN_SUFFIX",
    "VALUE_DATE_COLUMN",
    "InterpolatedSeries",
    "calculate_statistics",
    "check_limit_breaches",
    "detect_node_column",
    "get_maturity_order",
    "interpolate_for_display",
    "organize_metrics",
    "parse_metric_name",
    "split_by_node",
]
