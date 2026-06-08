import pandas as pd
import pytest

from process_extraction import (
    build_canonical_ordered_metrics,
    build_node_frames,
    load_extraction_file,
    process_extraction_to_parquet,
)


def _write_extraction_csv(path, with_node=True):
    rows = {
        "ValueDate": ["2026-01-01", "2026-01-02", "2026-01-03"],
        "VaR": [10.0, 12.0, 100.0],
        "VaR_limMaxValue": [50.0, 50.0, 50.0],
        "SVaR": [5.0, 6.0, 7.0],
    }
    if with_node:
        rows["stranaNodeName"] = ["NodeA", "NodeA", "NodeA"]
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_load_extraction_file_lowercases_and_parses_dates(tmp_path):
    csv_path = _write_extraction_csv(tmp_path / "extract.csv")
    df = load_extraction_file(str(csv_path))

    assert "valuedate" in df.columns
    assert "var" in df.columns
    assert pd.api.types.is_datetime64_any_dtype(df["valuedate"])


def test_load_extraction_file_requires_valuedate(tmp_path):
    bad = tmp_path / "bad.csv"
    pd.DataFrame({"VaR": [1.0]}).to_csv(bad, index=False)

    with pytest.raises(ValueError, match="ValueDate"):
        load_extraction_file(str(bad))


def test_build_node_frames_single_mode(tmp_path):
    csv_path = _write_extraction_csv(tmp_path / "extract.csv", with_node=False)
    df = load_extraction_file(str(csv_path))
    frames = build_node_frames(df)

    assert list(frames.keys()) == ["__single__"]


def test_build_node_frames_batch_mode(tmp_path):
    csv_path = _write_extraction_csv(tmp_path / "extract.csv", with_node=True)
    df = load_extraction_file(str(csv_path))
    frames = build_node_frames(df)

    assert list(frames.keys()) == ["NodeA"]
    # Node column is dropped from the per-node wide frame.
    assert "strananodename" not in frames["NodeA"].columns


def test_canonical_ordered_metrics_priority_first(tmp_path):
    csv_path = _write_extraction_csv(tmp_path / "extract.csv", with_node=False)
    df = load_extraction_file(str(csv_path))
    frames = build_node_frames(df)

    ordered = build_canonical_ordered_metrics(frames)
    # PRIORITY_METRICS puts var/svar ahead of other metrics, limit columns excluded.
    assert ordered[:2] == ["var", "svar"]
    assert "var_limmaxvalue" not in ordered


def test_process_extraction_to_parquet_roundtrips(tmp_path):
    pytest.importorskip("pyarrow")

    csv_path = _write_extraction_csv(tmp_path / "extract.csv", with_node=True)
    out_path = tmp_path / "out" / "long_dataset.parquet"

    long_df = process_extraction_to_parquet(str(csv_path), str(out_path))

    assert out_path.exists()
    reloaded = pd.read_parquet(out_path)
    assert list(reloaded.columns) == [
        "node", "valuedate", "metric", "value",
        "limit_max", "limit_min",
        "is_breach_max", "is_breach_min", "is_outlier", "sort_order",
    ]
    assert set(reloaded["metric"]) == {"var", "svar"}
    assert (reloaded["node"] == "NodeA").all()
    assert len(reloaded) == len(long_df)
