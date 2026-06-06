# Reporting Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a long-format dataset that feeds a new Power BI deliverable (small-multiples, built once from a guide) and a redesigned lazy-loading HTML report, both auto-absorbing new metrics.

**Architecture:** A new pure module `dataset.py` transforms the existing wide per-node DataFrames into one tidy long table (`node, valuedate, metric, value, limit_max, limit_min, is_breach_max, is_breach_min, is_outlier, sort_order`). The CSV is the single source of truth: Power BI loads it (facet by `metric`), and the HTML report is reworked to render charts lazily on scroll with an overview-first, status-driven UX.

**Tech Stack:** Python 3, pandas, Plotly, Streamlit, pytest (introduced here for the pure transform), Power BI Desktop (user side).

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `risk_metrics_app/dataset.py` | Pure wide→long transform + CSV writer | Create |
| `tests/test_dataset.py` | Unit tests for the transform | Create |
| `tests/test_reporting_helpers.py` | Unit tests for status/KPI helpers | Create |
| `risk_metrics_app/reporting.py` | Add status/KPI helpers; lazy-load charts; new UX | Modify |
| `risk_metrics_app/app.py` | Wire dataset generation + download into export flow | Modify |
| `docs/powerbi-setup.md` | Build-once Power BI guide | Create |
| `.gitignore` | Ignore `.superpowers/` and generated dataset | Modify |
| `requirements.txt` | Add `pytest` | Modify |

Each task is self-contained. Tasks 1–3 (data layer) are independent of Tasks 5–7 (HTML) and can be built/merged separately. Task 4 (Power BI guide) depends only on the column contract from Task 2.

---

## Task 0: Test scaffold

**Files:**
- Modify: `requirements.txt`
- Create: `tests/__init__.py`

- [ ] **Step 1: Add pytest to requirements**

Append to `requirements.txt`:

```
pytest>=8.0
```

- [ ] **Step 2: Install it**

Run: `pip install pytest>=8.0`
Expected: pytest installs (or "already satisfied").

- [ ] **Step 3: Create the tests package**

Create `tests/__init__.py` (empty file).

- [ ] **Step 4: Verify pytest discovers nothing yet**

Run: `python -m pytest -q`
Expected: "no tests ran".

- [ ] **Step 5: Commit**

```bash
git add requirements.txt tests/__init__.py
git commit -m "chore: add pytest test scaffold"
```

---

## Task 1: Long-format transform for a single node

**Files:**
- Create: `risk_metrics_app/dataset.py`
- Test: `tests/test_dataset.py`

This task builds `build_node_long_df`: turn one node's wide DataFrame into long rows for a given metric list. Reuses `calculate_statistics` (for the ±2SD outlier threshold) and the existing limit suffix constants — no new ranking logic.

- [ ] **Step 1: Write the failing test**

Create `tests/test_dataset.py`:

```python
import numpy as np
import pandas as pd

from risk_metrics_app.dataset import build_node_long_df


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
    df = _sample_df()
    out = build_node_long_df(df, ordered_metrics=["var"], node_name="NodeA", sort_order_map={"var": 0})

    # value 100 > limit_max 50 -> max breach on the third row only
    assert out["is_breach_max"].tolist() == [False, False, True]
    assert out["is_breach_min"].tolist() == [False, False, False]
    # 100 is the only point > mean + 2*std
    assert out["is_outlier"].tolist() == [False, False, True]


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dataset.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'risk_metrics_app.dataset'`.

- [ ] **Step 3: Write the implementation**

Create `risk_metrics_app/dataset.py`:

```python
"""Wide -> long transform that feeds the Power BI dataset and the HTML report.

The long table has one row per (node, valuedate, metric). New metrics arrive as
new rows, never new columns, so downstream consumers absorb them automatically.
"""
from typing import Dict, List

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
            else pd.Series([pd.NA] * len(df))
        )
        limit_min = (
            df[min_col].ffill().reset_index(drop=True)
            if min_col in df.columns
            else pd.Series([pd.NA] * len(df))
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dataset.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add risk_metrics_app/dataset.py tests/test_dataset.py
git commit -m "feat: add single-node wide-to-long transform"
```

---

## Task 2: Combine nodes and write the dataset CSV

**Files:**
- Modify: `risk_metrics_app/dataset.py`
- Test: `tests/test_dataset.py`

Adds `build_long_dataset` (multi-node concat with a shared `sort_order` map derived from the canonical ordered metric list) and `write_long_dataset_csv`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_dataset.py`:

```python
from risk_metrics_app.dataset import build_long_dataset, write_long_dataset_csv


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dataset.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_long_dataset'`.

- [ ] **Step 3: Write the implementation**

Append to `risk_metrics_app/dataset.py`:

```python
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
```

- [ ] **Step 4: Update the module exports**

Add to the bottom of `risk_metrics_app/dataset.py`:

```python
__all__ = [
    "LONG_COLUMNS",
    "build_node_long_df",
    "build_long_dataset",
    "write_long_dataset_csv",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_dataset.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add risk_metrics_app/dataset.py tests/test_dataset.py
git commit -m "feat: combine nodes and write long-format dataset CSV"
```

---

## Task 3: Wire dataset generation into the app + export ZIP

**Files:**
- Modify: `risk_metrics_app/app.py` (export section near lines 280–390)
- Modify: `risk_metrics_app/reporting.py` (`create_export_package`, `create_batch_export_package`)

The app already keeps the per-node DataFrames during analysis. We add a session-state stash of the wide frames + ordered metrics, then expose the CSV as a download and embed it in the ZIPs.

- [ ] **Step 1: Stash wide frames + ordered metrics in session state**

In `risk_metrics_app/app.py`, find where `metrics_analyses` is returned from the node analysis (single mode `_handle_single_analysis` and the batch path). After analysis completes for a node, record its wide DataFrame and ordered metric list. Add near the existing `st.session_state.setdefault(...)` block (around line 43):

```python
    st.session_state.setdefault("dataset_node_frames", {})
    st.session_state.setdefault("dataset_ordered_metrics", [])
```

In the single-mode handler, after `ordered_metrics` is finalized and before the metric loop, add:

```python
    st.session_state.dataset_node_frames = {"__single__": df}
    st.session_state.dataset_ordered_metrics = ordered_metrics
```

In the batch path, accumulate per node (replace the analogous spot where each node's `df`/`ordered_metrics` are known):

```python
    st.session_state.dataset_node_frames[node_name] = df
    st.session_state.dataset_ordered_metrics = ordered_metrics
```

- [ ] **Step 2: Add a dataset download button**

In `app.py`, in the export UI block (near line 288 where `create_html_report` download is built), add after the existing HTML download button:

```python
        from .dataset import build_long_dataset, write_long_dataset_csv
        from .config import OUTPUT_DIR
        import os

        node_frames = st.session_state.get("dataset_node_frames", {})
        ordered_metrics = st.session_state.get("dataset_ordered_metrics", [])
        if node_frames and ordered_metrics:
            long_df = build_long_dataset(node_frames, ordered_metrics)
            dataset_path = os.path.join(OUTPUT_DIR, "powerbi_dataset.csv")
            write_long_dataset_csv(long_df, dataset_path)
            csv_bytes = long_df.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8")
            st.download_button(
                label="⬇️ Download Power BI dataset (CSV)",
                data=csv_bytes,
                file_name="powerbi_dataset.csv",
                mime="text/csv",
                key="download_powerbi_dataset",
            )
```

- [ ] **Step 3: Embed the dataset in the export ZIPs**

In `risk_metrics_app/reporting.py`, change `create_export_package` to accept the long dataset and write it into the ZIP. Update the signature:

```python
def create_export_package(
    metrics_analyses: List[dict],
    portfolio_summary: str,
    file_name: str,
    use_llm: bool,
    excluded_by_keyword: Optional[List[str]] = None,
    excluded_by_limit: Optional[List[str]] = None,
    long_dataset_csv: Optional[str] = None,
) -> BytesIO:
```

Inside the `with zipfile.ZipFile(...)` block, after `zip_file.writestr("risk_analysis_report.html", html_content)` add:

```python
        if long_dataset_csv:
            zip_file.writestr("powerbi_dataset.csv", long_dataset_csv)
```

- [ ] **Step 4: Pass the CSV from the app into the ZIP call**

In `app.py` where `create_export_package(...)` is called (around line 306), pass the CSV string:

```python
        long_dataset_csv = None
        if node_frames and ordered_metrics:
            long_dataset_csv = build_long_dataset(node_frames, ordered_metrics).to_csv(
                index=False, date_format="%Y-%m-%d"
            )
        zip_buffer = create_export_package(
            st.session_state.metrics_analyses,
            st.session_state.portfolio_summary,
            file_name,
            use_llm,
            excluded_by_keyword=st.session_state.get("excluded_by_keyword"),
            excluded_by_limit=st.session_state.get("excluded_by_limit"),
            long_dataset_csv=long_dataset_csv,
        )
```

- [ ] **Step 5: Mirror for batch export**

In `reporting.py`, add a top-level `powerbi_dataset.csv` to `create_batch_export_package` by adding the same `long_dataset_csv: Optional[str] = None` parameter and, inside its `with zipfile.ZipFile(...)` block before the per-node loop:

```python
        if long_dataset_csv:
            zip_file.writestr("powerbi_dataset.csv", long_dataset_csv)
```

Then pass it from the batch export call site in `app.py` (around line 376), building it from `st.session_state.dataset_node_frames` + `dataset_ordered_metrics` the same way as Step 4.

- [ ] **Step 6: Manual verification**

Run: `streamlit run app_main.py`
Steps: upload a sample CSV → run analysis → in the export section confirm a "Download Power BI dataset (CSV)" button appears, downloads, and the CSV has the 10 `LONG_COLUMNS`. Download the ZIP and confirm `powerbi_dataset.csv` is inside.
Expected: dataset present and well-formed; `Output/powerbi_dataset.csv` written.

- [ ] **Step 7: Commit**

```bash
git add risk_metrics_app/app.py risk_metrics_app/reporting.py
git commit -m "feat: generate and export Power BI long-format dataset"
```

---

## Task 4: Power BI build-once guide

**Files:**
- Create: `docs/powerbi-setup.md`

- [ ] **Step 1: Write the guide**

Create `docs/powerbi-setup.md` with these sections (write full prose, not headers only):

1. **Overview** — the `.pbix` is built once; new metrics appear on Refresh because `metric` is a row value (facet), not a column.
2. **Load the data** — Get Data → Text/CSV → select `powerbi_dataset.csv` → Load.
3. **Make the path a parameter** — Transform data → Manage Parameters → New `DatasetPath` (Text) = full path to the CSV. Click the source query → gear on the `Source` step → set the file path to `DatasetPath`. To relocate later: Transform data → edit `DatasetPath` → Close & Apply. (This is the user-changes-path workflow.)
4. **Confirm column types** — `valuedate`=Date; `value`,`limit_max`,`limit_min`=Decimal Number; `is_breach_max`,`is_breach_min`,`is_outlier`=True/False; `sort_order`=Whole Number; `node`,`metric`=Text. Close & Apply.
5. **Sort metric by sort_order** — select the `metric` column in Data view → Column tools → Sort by column → `sort_order`.
6. **Build the visual** — Line chart: X-axis=`valuedate`; Y-axis=`value`, `limit_max`, `limit_min`; **Small multiples=`metric`**. Add `is_breach_max`/`is_breach_min`/`is_outlier` to the tooltip.
7. **Format** — set small-multiples grid rows/columns (e.g. 3×3) so all tiles scroll; distinct dashed style for limit lines.
8. **Refresh workflow** — regenerate the dataset from the app (overwrites the CSV) → Home → Refresh.
9. **Acceptance walkthrough** — add a new metric `custom_VaR` to the source, regenerate the dataset, Refresh, confirm a new tile appears with no PBIX edits.
10. **Known limitations** — small multiples share a Y-axis (per-metric adaptive scaling not available here); to get per-metric axes, build a paginated report in Power BI Report Builder (note as future option).

- [ ] **Step 2: Verify it renders**

Run: open `docs/powerbi-setup.md` in a Markdown previewer; confirm all 10 sections present and no placeholders.
Expected: complete guide, every step actionable.

- [ ] **Step 3: Commit**

```bash
git add docs/powerbi-setup.md
git commit -m "docs: add Power BI build-once setup guide"
```

---

## Task 5: HTML status + KPI helpers (pure, tested)

**Files:**
- Modify: `risk_metrics_app/reporting.py`
- Test: `tests/test_reporting_helpers.py`

Pure functions the redesigned report uses: per-metric status with precedence breach > outlier > ok, and aggregate KPI counts.

- [ ] **Step 1: Write the failing test**

Create `tests/test_reporting_helpers.py`:

```python
from risk_metrics_app.reporting import metric_status, kpi_counts


def _analysis(metric, breaches, n_outliers):
    return {
        "metric": metric,
        "breaches": breaches,
        "outliers": list(range(n_outliers)),
    }


def test_metric_status_precedence():
    assert metric_status(_analysis("a", [{"type": "max"}], 5)) == "breach"
    assert metric_status(_analysis("b", [], 3)) == "outlier"
    assert metric_status(_analysis("c", [], 0)) == "ok"


def test_kpi_counts_aggregate():
    analyses = [
        _analysis("a", [{"type": "max"}], 5),
        _analysis("b", [], 3),
        _analysis("c", [], 0),
        _analysis("d", [], 0),
    ]
    counts = kpi_counts(analyses)
    assert counts == {"total": 4, "breach": 1, "outlier": 1, "ok": 2}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_reporting_helpers.py -v`
Expected: FAIL — `ImportError: cannot import name 'metric_status'`.

- [ ] **Step 3: Write the implementation**

Add to `risk_metrics_app/reporting.py` (near the top, after imports):

```python
def metric_status(analysis: dict) -> str:
    """Return 'breach', 'outlier', or 'ok' for a metric analysis.

    Precedence: a breaching metric is 'breach' even if it also has outliers.
    """
    if analysis.get("breaches"):
        return "breach"
    if len(analysis.get("outliers", [])) > 0:
        return "outlier"
    return "ok"


def kpi_counts(metrics_analyses: List[dict]) -> dict:
    """Aggregate status counts for the KPI summary strip."""
    counts = {"total": len(metrics_analyses), "breach": 0, "outlier": 0, "ok": 0}
    for analysis in metrics_analyses:
        counts[metric_status(analysis)] += 1
    return counts
```

Add `"metric_status"` and `"kpi_counts"` to the `__all__` list in `reporting.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_reporting_helpers.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add risk_metrics_app/reporting.py tests/test_reporting_helpers.py
git commit -m "feat: add HTML report status and KPI helpers"
```

---

## Task 6: Lazy-load charts in the HTML report

**Files:**
- Modify: `risk_metrics_app/reporting.py` (`create_html_report`, lines ~261 and the `<script>` block ~577)

Replace per-figure `fig.to_html(include_plotlyjs="cdn")` with: Plotly loaded once globally, each figure embedded as inert JSON, rendered on scroll via `IntersectionObserver`.

- [ ] **Step 1: Load Plotly once in `<head>`**

In the `<head>` of the HTML template string (near line 456 where Tailwind is loaded), add the Plotly CDN script:

```html
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
```

- [ ] **Step 2: Embed each figure as inert JSON instead of full HTML**

Replace the per-metric figure rendering (line ~261):

```python
        fig_html = fig.to_html(include_plotlyjs="cdn", div_id=f"plot-{metric.replace('/', '_')}")
```

with:

```python
        plot_div_id = f"plot-{make_anchor_id(metric)}"
        fig_json = fig.to_json()
        fig_html = (
            f'<div id="{plot_div_id}" class="lazy-plot" '
            f'style="min-height:420px"></div>'
            f'<script type="application/json" class="plot-spec" '
            f'data-target="{plot_div_id}">{fig_json}</script>'
        )
```

- [ ] **Step 3: Add the IntersectionObserver renderer**

Inside the existing `<script> (function() { ... })()` block (before its closing `})();` near line 679), add:

```javascript
            // Lazy-render Plotly charts only when scrolled into view
            const renderPlot = (specEl) => {
                if (specEl.dataset.rendered) return;
                const target = document.getElementById(specEl.dataset.target);
                if (!target) return;
                const spec = JSON.parse(specEl.textContent);
                Plotly.newPlot(target, spec.data, spec.layout,
                    {responsive: true, displayModeBar: false});
                specEl.dataset.rendered = "1";
            };
            const plotObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        renderPlot(entry.target);
                        plotObserver.unobserve(entry.target);
                    }
                });
            }, {rootMargin: "200px"});
            document.querySelectorAll('.plot-spec').forEach(el => plotObserver.observe(el));
```

- [ ] **Step 4: Manual verification (performance)**

Run: `streamlit run app_main.py`
Steps: analyze a CSV with many metrics → download the HTML → open it → confirm it opens quickly and charts appear as you scroll (not all at once). Open DevTools Network: only one Plotly script load.
Expected: fast initial load; charts render progressively.

- [ ] **Step 5: Commit**

```bash
git add risk_metrics_app/reporting.py
git commit -m "perf: lazy-render HTML report charts via IntersectionObserver"
```

---

## Task 7: Overview-first, status-driven HTML UX

**Files:**
- Modify: `risk_metrics_app/reporting.py` (`create_html_report` body + JS)

Add the KPI strip, "needs attention" table, status filter chips, and per-card status border. Reuses `metric_status`/`kpi_counts` from Task 5.

- [ ] **Step 1: Tag each metric section with its status**

In the metric-section loop, compute status and put it on the `<article>` as a data attribute and a colored left border. Where `metric_section = f'''<article id="{anchor_id}" class="mb-10 ...">` is built (line ~351), change the opening tag to:

```python
        status = metric_status(analysis)
        border = {"breach": "border-l-4 border-l-red-500",
                  "outlier": "border-l-4 border-l-amber-400",
                  "ok": "border-l-4 border-l-emerald-400"}[status]
```

and replace the `<article ...>` opening with:

```python
        metric_section = f'''
        <article id="{anchor_id}" data-status="{status}" data-metric="{metric.lower()}"
                 class="metric-card mb-10 bg-white border border-gray-200 {border} rounded-2xl shadow-lg overflow-hidden scroll-mt-32">
```

(Adjust the closing of the existing f-string accordingly — keep the rest of the article body unchanged.)

- [ ] **Step 2: Build the KPI strip + attention table**

Before the `<main>` block (after the header, near line 509), insert computed HTML. First compute in Python (before the template string, near line 231 where `metric_count` is set):

```python
    counts = kpi_counts(metrics_analyses_sorted)
    attention = [a for a in metrics_analyses_sorted if metric_status(a) != "ok"]
    attention_rows = []
    for a in attention:
        st_ = metric_status(a)
        icon = "⛔" if st_ == "breach" else "⚠️"
        n_breach = sum(b["count"] for b in a.get("breaches", []))
        detail = f"{n_breach} breaches" if st_ == "breach" else f"{len(a.get('outliers', []))} outliers"
        anchor = make_anchor_id(a["metric"])
        attention_rows.append(
            f'<tr class="border-b border-gray-100 hover:bg-gray-50">'
            f'<td class="py-2 px-3">{icon}</td>'
            f'<td class="py-2 px-3 font-medium">{a["metric"]}</td>'
            f'<td class="py-2 px-3 text-gray-600">{detail}</td>'
            f'<td class="py-2 px-3"><a href="#{anchor}" class="text-blue-600 hover:underline">jump →</a></td>'
            f'</tr>'
        )
    attention_table = (
        f'<div class="overflow-x-auto"><table class="w-full text-sm">'
        f'<thead><tr class="text-left text-gray-500"><th class="py-2 px-3"></th>'
        f'<th class="py-2 px-3">Metric</th><th class="py-2 px-3">Issue</th>'
        f'<th class="py-2 px-3"></th></tr></thead><tbody>{"".join(attention_rows)}</tbody></table></div>'
        if attention_rows else
        '<p class="text-emerald-600 font-medium">No breaches or outliers detected.</p>'
    )
```

Then insert this template fragment after the header `</header>` (line ~509):

```python
        <!-- KPI strip -->
        <section class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
            <div class="bg-white border border-gray-200 rounded-xl p-4 text-center shadow-sm">
                <div class="text-3xl font-bold text-gray-900">{counts['total']}</div>
                <div class="text-xs uppercase tracking-wide text-gray-500">Metrics</div>
            </div>
            <div class="bg-red-50 border border-red-200 rounded-xl p-4 text-center shadow-sm">
                <div class="text-3xl font-bold text-red-600">{counts['breach']}</div>
                <div class="text-xs uppercase tracking-wide text-red-500">Breaching</div>
            </div>
            <div class="bg-amber-50 border border-amber-200 rounded-xl p-4 text-center shadow-sm">
                <div class="text-3xl font-bold text-amber-600">{counts['outlier']}</div>
                <div class="text-xs uppercase tracking-wide text-amber-500">Outliers</div>
            </div>
            <div class="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center shadow-sm">
                <div class="text-3xl font-bold text-emerald-600">{counts['ok']}</div>
                <div class="text-xs uppercase tracking-wide text-emerald-500">OK</div>
            </div>
        </section>
        <!-- Needs attention -->
        <section class="mb-8 bg-white border border-gray-200 rounded-2xl shadow-sm p-5">
            <h2 class="text-lg font-bold text-gray-800 mb-3">Needs attention</h2>
            {attention_table}
        </section>
```

- [ ] **Step 3: Add status filter chips to the sticky nav**

In the sticky nav search row (near line 515, inside the `flex items-center gap-3` div), add before the search input:

```html
                    <div class="flex gap-2" id="statusChips">
                        <button data-status="all" class="status-chip px-3 py-1.5 rounded-lg text-sm font-medium bg-blue-600 text-white">All</button>
                        <button data-status="breach" class="status-chip px-3 py-1.5 rounded-lg text-sm font-medium bg-red-100 text-red-700">Breaches</button>
                        <button data-status="outlier" class="status-chip px-3 py-1.5 rounded-lg text-sm font-medium bg-amber-100 text-amber-700">Outliers</button>
                        <button data-status="ok" class="status-chip px-3 py-1.5 rounded-lg text-sm font-medium bg-emerald-100 text-emerald-700">OK</button>
                    </div>
```

- [ ] **Step 4: Wire chip + search filtering of the metric cards**

In the `<script>` block, add (after the lazy-render code from Task 6):

```javascript
            // Filter metric cards by status chip + search text
            const cards = document.querySelectorAll('.metric-card');
            let activeStatus = "all";
            function applyCardFilter() {
                const term = (searchInput.value || "").toLowerCase().trim();
                cards.forEach(card => {
                    const matchStatus = activeStatus === "all" || card.dataset.status === activeStatus;
                    const matchText = !term || card.dataset.metric.includes(term);
                    card.style.display = (matchStatus && matchText) ? "" : "none";
                });
            }
            document.querySelectorAll('.status-chip').forEach(chip => {
                chip.addEventListener('click', () => {
                    activeStatus = chip.dataset.status;
                    document.querySelectorAll('.status-chip').forEach(c => {
                        c.classList.toggle('ring-2', c === chip);
                        c.classList.toggle('ring-offset-1', c === chip);
                    });
                    applyCardFilter();
                });
            });
            searchInput.addEventListener('input', applyCardFilter);
```

- [ ] **Step 5: Manual verification (UX)**

Run: `streamlit run app_main.py`
Steps: download the HTML for a multi-metric CSV that has at least one breach and one outlier. Confirm: KPI counts match the data; "Needs attention" lists the right metrics with working jump links; clicking "Breaches" hides non-breaching cards; typing in search narrows cards; each card shows the correct colored left border.
Expected: overview-first layout works; filters correct.

- [ ] **Step 6: Commit**

```bash
git add risk_metrics_app/reporting.py
git commit -m "feat: overview-first status-driven HTML report UX"
```

---

## Task 8: Ignore generated artifacts

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add ignores**

Append to `.gitignore`:

```
.superpowers/
Output/powerbi_dataset.csv
```

- [ ] **Step 2: Verify**

Run: `git status --porcelain`
Expected: `.superpowers/` and `Output/powerbi_dataset.csv` not listed as untracked.

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: ignore brainstorm dir and generated dataset"
```

---

## Final verification

- [ ] Run full test suite: `python -m pytest -v` → all pass.
- [ ] Run app, exercise single mode and batch mode, download HTML + ZIP + CSV.
- [ ] Confirm the CSV opens in Power BI per `docs/powerbi-setup.md` and the `custom_VaR` acceptance walkthrough passes.
```
