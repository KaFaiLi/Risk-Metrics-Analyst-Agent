import numpy as np
import pandas as pd
import pytest

from risk_metrics_app.dataset import (
    build_node_long_df,
    build_long_dataset,
    write_long_dataset_csv,
    write_long_dataset_parquet,
)


def _sample_df():
    return pd.DataFrame(
        {
            "valuedate": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]),
            "var": [10.0, 12.0, 100.0],
            "var_limmaxvalue": [50.0, 50.0, 50.0],
            "var_limminvalue": [0.0, 0.0, 0.0],
        }
    )


def test_build_node_long_df_basic_shape_and_values():
    df = _sample_df()
    out = build_node_long_df(df, ordered_metrics=["var"], node_name="NodeA", sort_order_map={"var": 0})

    assert list(out.columns) == [
        "node", "valuedate", "metric", "value",
        "limit_max", "limit_min",
        "is_breach_max", "is_breach_min", "is_outlier", "sort_order",
    ]
    assert len(out) == 3
    assert (out["node"] == "NodeA").all()
    assert (out["metric"] == "var").all()
    assert out["value"].tolist() == [10.0, 12.0, 100.0]
    assert out["limit_max"].tolist() == [50.0, 50.0, 50.0]
    assert out["sort_order"].tolist() == [0, 0, 0]


def test_build_node_long_df_flags_breach_and_outlier():
    # Five inliers at 10 plus one spike at 100: mean=25, std~36.7,
    # so mean + 2*std ~ 98.5 and the spike is a genuine +-2SD outlier
    # while a single spike among only three points would inflate std too much.
    df = pd.DataFrame(
        {
            "valuedate": pd.to_datetime(
                ["2026-01-01", "2026-01-02", "2026-01-03",
                 "2026-01-04", "2026-01-05", "2026-01-06"]
            ),
            "var": [10.0, 10.0, 10.0, 10.0, 10.0, 100.0],
            "var_limmaxvalue": [50.0] * 6,
            "var_limminvalue": [0.0] * 6,
        }
    )
    out = build_node_long_df(df, ordered_metrics=["var"], node_name="NodeA", sort_order_map={"var": 0})

    # value 100 > limit_max 50 -> max breach on the last row only
    assert out["is_breach_max"].tolist() == [False, False, False, False, False, True]
    assert out["is_breach_min"].tolist() == [False] * 6
    # 100 is the only point > mean + 2*std
    assert out["is_outlier"].tolist() == [False, False, False, False, False, True]


def test_build_node_long_df_missing_limits_are_null():
    df = pd.DataFrame(
        {
            "valuedate": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            "custom_var": [1.0, 2.0],
        }
    )
    out = build_node_long_df(df, ordered_metrics=["custom_var"], node_name="N", sort_order_map={"custom_var": 0})

    assert out["limit_max"].isna().all()
    assert out["limit_min"].isna().all()
    assert out["is_breach_max"].tolist() == [False, False]
    assert out["is_breach_min"].tolist() == [False, False]


def test_build_long_dataset_combines_nodes_and_assigns_sort_order():
    df_a = pd.DataFrame(
        {"valuedate": pd.to_datetime(["2026-01-01"]), "svar": [3.0], "var": [1.0]}
    )
    df_b = pd.DataFrame(
        {"valuedate": pd.to_datetime(["2026-01-01"]), "svar": [4.0], "var": [2.0]}
    )
    # canonical order: var first, then svar
    out = build_long_dataset({"A": df_a, "B": df_b}, ordered_metrics=["var", "svar"])

    assert set(out["node"]) == {"A", "B"}
    assert len(out) == 4  # 2 nodes * 2 metrics * 1 date
    order = dict(zip(out["metric"], out["sort_order"]))
    assert order["var"] == 0
    assert order["svar"] == 1


def test_write_long_dataset_csv_roundtrips(tmp_path):
    df = pd.DataFrame(
        {"valuedate": pd.to_datetime(["2026-01-01"]), "var": [1.0]}
    )
    long_df = build_long_dataset({"__single__": df}, ordered_metrics=["var"])
    path = tmp_path / "powerbi_dataset.csv"

    write_long_dataset_csv(long_df, str(path))

    reloaded = pd.read_csv(path)
    assert list(reloaded.columns) == [
        "node", "valuedate", "metric", "value",
        "limit_max", "limit_min",
        "is_breach_max", "is_breach_min", "is_outlier", "sort_order",
    ]
    assert reloaded["node"].iloc[0] == "__single__"


def test_write_long_dataset_parquet_roundtrips(tmp_path):
    pytest.importorskip("pyarrow")

    df = pd.DataFrame(
        {"valuedate": pd.to_datetime(["2026-01-01", "2026-01-02"]), "var": [1.0, 2.0]}
    )
    long_df = build_long_dataset({"__single__": df}, ordered_metrics=["var"])
    path = tmp_path / "long_dataset.parquet"

    write_long_dataset_parquet(long_df, str(path))

    reloaded = pd.read_parquet(path)
    assert list(reloaded.columns) == [
        "node", "valuedate", "metric", "value",
        "limit_max", "limit_min",
        "is_breach_max", "is_breach_min", "is_outlier", "sort_order",
    ]
    assert reloaded["node"].iloc[0] == "__single__"
    # valuedate keeps a native datetime dtype rather than being stringified.
    assert pd.api.types.is_datetime64_any_dtype(reloaded["valuedate"])
    assert reloaded["value"].tolist() == [1.0, 2.0]
