"""Process an extraction CSV into the long-format dataset and save it as Parquet.

This is a thin, headless wrapper around ``risk_metrics_app`` that performs only
the data-shaping half of the pipeline: it loads a wide "pivot metrics"
extraction file, transforms it into the one-row-per-(node, valuedate, metric)
long table used by the report/Power BI exports, and writes the result to a
Parquet file. No statistics narration, charts, or LLM calls are involved.

Usage examples
--------------
Process the bundled sample into ``Output/long_dataset.parquet``::

    python process_extraction.py

Process a specific extraction file to a chosen destination::

    python process_extraction.py path/to/api_extract.csv -o path/to/out.parquet
"""

from __future__ import annotations

import argparse
import os
from typing import Dict

import pandas as pd

from risk_metrics_app.config import OUTPUT_DIR, logger
from risk_metrics_app.dataset import build_long_dataset, write_long_dataset_parquet
from risk_metrics_app.metrics import (
    VALUE_DATE_COLUMN,
    detect_node_column,
    organize_metrics,
    split_by_node,
)

DEFAULT_INPUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "Examples", "Fake Pivot Metrics.csv"
)
DEFAULT_OUTPUT = os.path.join(OUTPUT_DIR, "long_dataset.parquet")


def load_extraction_file(input_path: str) -> pd.DataFrame:
    """Read an extraction CSV and apply the canonical preprocessing.

    Mirrors the loading performed by the Streamlit app: lowercase column names
    and parse the ``ValueDate`` column into datetimes.
    """
    df = pd.read_csv(input_path)
    df.columns = [col.lower() for col in df.columns]

    if VALUE_DATE_COLUMN not in df.columns:
        raise ValueError(
            f"The extraction file is missing the required 'ValueDate' column: {input_path}"
        )

    df[VALUE_DATE_COLUMN] = pd.to_datetime(df[VALUE_DATE_COLUMN])
    logger.info("Loaded extraction file %s with shape %s", input_path, df.shape)
    return df


def build_node_frames(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Split into per-node wide frames, or a single ``__single__`` frame."""
    node_column = detect_node_column(df)
    if node_column:
        node_frames = split_by_node(df, node_column)
        logger.info("Detected node column '%s' - %d node(s)", node_column, len(node_frames))
        return node_frames

    logger.info("No node column detected - single mode")
    return {"__single__": df}


def build_canonical_ordered_metrics(node_frames: Dict[str, pd.DataFrame]) -> list[str]:
    """Union per-node metric orderings, preserving priority/maturity order.

    A metric present only in an earlier node is kept even when a later node has
    a different set, matching the app's Power BI dataset behaviour.
    """
    ordered_metrics: list[str] = []
    for df in node_frames.values():
        ordered_metrics = list(dict.fromkeys(ordered_metrics + organize_metrics(df)))
    return ordered_metrics


def process_extraction_to_parquet(input_path: str, output_path: str) -> pd.DataFrame:
    """Run the full extraction -> long -> Parquet pipeline.

    Returns the long-format DataFrame that was written.
    """
    df = load_extraction_file(input_path)
    node_frames = build_node_frames(df)
    ordered_metrics = build_canonical_ordered_metrics(node_frames)

    long_df = build_long_dataset(node_frames, ordered_metrics)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    write_long_dataset_parquet(long_df, output_path)
    logger.info("Wrote %d long-format rows to %s", len(long_df), output_path)
    return long_df


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "input",
        nargs="?",
        default=DEFAULT_INPUT,
        help=f"Path to the extraction CSV (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Destination Parquet path (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    long_df = process_extraction_to_parquet(args.input, args.output)
    print(
        f"Processed '{args.input}' -> '{args.output}' "
        f"({len(long_df)} rows, {long_df['metric'].nunique()} metrics, "
        f"{long_df['node'].nunique()} node(s))."
    )


if __name__ == "__main__":
    main()
