# Reporting Redesign — Design

**Date:** 2026-06-06
**Status:** Approved (brainstorm), pending spec review

## Problem

The current HTML report (`reporting.py:create_html_report`) renders one **interactive Plotly figure per metric** via `fig.to_html(include_plotlyjs="cdn")`. At hundreds of metrics:

- **Load is slow** — every figure runs `Plotly.newPlot` at page load; the DOM is huge and the inline figure JSON balloons file size.
- **Search lags** — the page is heavy even though the search itself only filters nav items.
- **UX is bland** — the report is a flat wall of charts that "only shows information"; no signal-first overview, no status filtering.

There is also a data constraint: the upstream dataset's **columns change over time** — new risk metrics (e.g. `custom_VaR`) appear as new wide columns. Any solution must absorb new metrics with minimal manual work.

## Goals

1. A **Power BI** deliverable that shows *every* metric at once (no slicer) and auto-absorbs new metrics on refresh.
2. A **redesigned HTML report** that loads fast at hundreds of metrics and surfaces signal first.
3. A single **data layer** feeding both, so new metrics flow to both outputs without per-metric manual work.

## Non-goals

- Live/scheduled Power BI refresh infrastructure. The user re-points the dataset file path themselves (accepted compromise).
- Programmatic generation of a binary `.pbix`. Delivered as a build-once guide instead.
- Paginated Power BI report (Report Builder). Documented as a future option only.

## Architecture

```
extraction / metrics  →  long-format dataset (CSV)  →  ┬→  Power BI (.pbix, built once from guide)
                                                       └→  HTML report (redesigned, lazy-load)
```

The long-format dataset is the single source of truth. New metric → pipeline regenerates the dataset → both outputs update (Power BI on Refresh, HTML on regeneration).

---

## Component 1 — Data layer (long-format export)

New module `risk_metrics_app/dataset.py`.

### `build_long_dataset(...) -> pandas.DataFrame`

Consumes the same per-metric analyses the report already builds (so breach/outlier flags are computed once, consistently). Emits one tidy DataFrame, **one row per `(node, valuedate, metric)`**:

| column | source | notes |
|---|---|---|
| `node` | `strananodename` lower, or `"__single__"` in single mode | distinguishes batch nodes within one file |
| `valuedate` | existing `valuedate` | Date |
| `metric` | base display name | the Power BI small-multiples facet key |
| `value` | the metric's value column | Decimal |
| `limit_max` | `<metric>_limmaxvalue`, ffill | null if metric has no max limit |
| `limit_min` | `<metric>_limminvalue`, ffill | null if metric has no min limit |
| `is_breach_max` | breach logic | bool per row |
| `is_breach_min` | breach logic | bool per row |
| `is_outlier` | ±2SD outlier logic | bool per row |
| `sort_order` | priority + maturity rank | integer; orders facets VaR/SVaR/STTHH → others (fixes the small-multiples alphabetical-ordering edge) |

### Why long format

- New metric = **new rows, never new columns**. This is what makes both outputs auto-absorb new metrics.
- Limits and flags live alongside the value, so each Power BI facet shows its own limit lines and each HTML card its own status with no joins.

### Output and wiring

- `write_long_dataset_csv(df, path)` → writes `Output/powerbi_dataset.csv`. CSV chosen for transparency (doubles as a data backup); Parquet noted as a future option.
- Batch mode: a single combined CSV across all nodes, distinguished by the `node` column.
- Wire into `app.py` export flow and include the CSV in the export ZIP packages (`create_export_package`, `create_batch_export_package`).

### Edge cases

- Metric with no limit columns → `limit_max`/`limit_min` null; downstream draws value line only.
- Excluded metrics (keyword / missing-limit filters) → **not** emitted to the dataset (consistent with them being excluded from analysis).
- Single mode (no `strananodename`) → `node = "__single__"`.

---

## Component 2 — Power BI build-once guide

Deliverable: `docs/powerbi-setup.md`. The user builds the `.pbix` once (~10 min) following the guide, then never edits it; new metrics flow via Refresh.

Guide contents:

1. **Get Data → Text/CSV** → select `powerbi_dataset.csv` → Load.
2. **Path as parameter** — create a `DatasetPath` parameter and point the query Source step at it. Relocating the file later = Transform data → edit `DatasetPath`. (Implements the user-changes-path compromise.)
3. **Type safety** — confirm `value`/`limit_max`/`limit_min` = Decimal, `valuedate` = Date, `is_*` = True/False. One-time on fixed columns; long format never adds columns, so this stays stable.
4. **Build the visual** — Line chart:
   - X = `valuedate`
   - Y = `value`, `limit_max`, `limit_min` (three lines per facet)
   - **Small multiples = `metric`**
   - Sort facets by `sort_order`.
5. **Format** — small-multiples grid rows/columns, tooltip fields (`is_breach_max`/`is_breach_min`/`is_outlier`), conditional formatting for limit lines.
6. **Refresh workflow** — pipeline overwrites the CSV → Home → Refresh → new tiles appear.

Acceptance walkthrough documented in the guide: add `custom_VaR`, regenerate dataset, Refresh, confirm a new tile appears with zero PBIX edits.

Documented caveats: small-multiples **shared Y-axis** limitation (per-metric adaptive scaling not available in this view); how to switch to a paginated report later if per-metric axes are needed.

---

## Component 3 — HTML report redesign

Rework `reporting.py:create_html_report` (and its JS). Output remains a single self-contained file with **interactive** charts.

### Performance mechanism

- Include `plotly.js` **once** globally; per-figure `include_plotlyjs=False`.
- For each metric, embed the figure spec as an inert `<script type="application/json">` payload — **no `Plotly.newPlot` at load**.
- An `IntersectionObserver` renders a chart (`Plotly.newPlot` from the embedded JSON) only when its card scrolls into view; `Plotly.purge` charts that scroll far off-screen to cap memory.
- Net: page load renders ~0 charts (instant); search/filter act on lightweight cards (fast at hundreds of metrics).

### UX

1. **KPI summary strip** (top): total metrics, # breaching, # outliers, # OK.
2. **"Needs attention" table** (top, sortable): metrics with breaches/outliers first, each linking (jump) to its card.
3. **Sticky filter bar**: status chips — All / Breaches / Outliers / OK — that filter the whole report, plus the existing text search. Filtering hides non-matching cards (and skips their lazy render).
4. **Metric cards**: color-coded left border by status (breach = red, outlier = amber, ok = green); chart lazy-renders on scroll.

### Kept from current report

- Priority + maturity metric ordering.
- Breach / outlier / limit-annotation detail blocks.
- AI insights inline + portfolio summary.
- Self-contained single file; print styles.

### Status derivation

Per metric, status precedence: **breach > outlier > ok** (a breaching metric is tagged breach even if it also has outliers). Counts in the KPI strip and chips derive from these per-metric statuses.

---

## Testing / verification

No test suite exists in the repo. Verification is manual:

- **Data layer**: generate dataset from a sample CSV; assert row count = Σ(non-excluded metrics × dates × nodes); spot-check `limit_max`/`limit_min` ffill, breach/outlier flags vs the HTML report, `sort_order` matches priority/maturity ordering.
- **Power BI**: follow the guide once; run the `custom_VaR` acceptance walkthrough (new tile on Refresh, no PBIX edits).
- **HTML**: generate a report with a few hundred metrics; confirm fast initial load, charts render on scroll, status chips/search filter correctly, KPI + attention table match the data.

## Components are independent

- `dataset.py` is standalone (pure transform; testable without UI).
- The Power BI guide depends only on the dataset's column contract.
- The HTML redesign is isolated to `reporting.py` + its embedded JS.

The dataset's column schema is the shared contract between all three.
