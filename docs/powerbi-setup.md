# Power BI Setup Guide (Build Once)

This guide builds a Power BI report that shows **every risk metric at once** as a
small-multiples grid — no slicer, no per-metric manual work. You build the `.pbix`
**once** (~10 minutes). After that, new metrics appear automatically on **Refresh**,
because each metric is a *row value* (a chart facet), not a separate column.

The report reads the long-format dataset the app generates:
`Output/powerbi_dataset.csv` (also available via the "Download Power BI dataset (CSV)"
button and inside the export ZIP).

## 1. Overview — why new metrics are automatic

The dataset is **long format**: one row per `(node, valuedate, metric)`.

| column | meaning |
|---|---|
| `node` | portfolio node (`__single__` in single mode) |
| `valuedate` | date |
| `metric` | metric name — this becomes the small-multiples facet |
| `value` | the metric value |
| `limit_max` / `limit_min` | limits (blank if the metric has none) |
| `is_breach_max` / `is_breach_min` | breach flags |
| `is_outlier` | ±2SD outlier flag |
| `sort_order` | integer giving the facet order (VaR, SVaR, STTHH first, then by name/maturity) |

A new metric such as `custom_VaR` arrives as **new rows**, never new columns. The visual
facets by `metric`, so a new metric value simply produces a new tile. Nothing in the
`.pbix` needs to change.

## 2. Load the data

1. Open **Power BI Desktop**.
2. **Home → Get Data → Text/CSV**.
3. Select `Output/powerbi_dataset.csv`.
4. Click **Load**.

## 3. Make the file path a parameter (so you can move the file later)

This lets you re-point the report at the dataset wherever you keep it — no query editing.

1. **Home → Transform data** (opens Power Query Editor).
2. **Home → Manage Parameters → New Parameter**:
   - Name: `DatasetPath`
   - Type: `Text`
   - Current Value: the full path to `powerbi_dataset.csv` (e.g. `C:\Reports\powerbi_dataset.csv`).
3. Select the dataset query in the left pane. Click the gear icon on the **Source** step.
4. Change the file path so it uses the parameter. In the formula bar the Source step
   should read like:
   `= Csv.Document(File.Contents(DatasetPath), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv])`
   (use `DatasetPath` in place of the hard-coded path string).
5. **Home → Close & Apply.**

**To relocate the dataset later:** Transform data → **Manage Parameters** → edit
`DatasetPath` → **Close & Apply**. Done.

## 4. Confirm column types

Still useful to verify once (these never change, because long format never adds columns):

| column | type |
|---|---|
| `valuedate` | Date |
| `value`, `limit_max`, `limit_min` | Decimal Number |
| `is_breach_max`, `is_breach_min`, `is_outlier` | True/False |
| `sort_order` | Whole Number |
| `node`, `metric` | Text |

Set types in Power Query (click the column type icon in each header), then **Close & Apply**.

## 5. Sort metrics by `sort_order`

So the facets appear in priority order (VaR, SVaR, STTHH first) rather than alphabetically:

1. **Data view** (left rail) → select the `metric` column.
2. **Column tools → Sort by column → `sort_order`**.

## 6. Build the small-multiples visual

1. **Report view** → add a **Line chart**.
2. Field wells:
   - **X-axis:** `valuedate`
   - **Y-axis:** `value`, then also add `limit_max` and `limit_min` (three lines per facet)
   - **Small multiples:** `metric`
3. Add `is_breach_max`, `is_breach_min`, `is_outlier` to the **Tooltips** well so hovering a
   point shows whether it breached or is an outlier.

## 7. Format

- **Visual → Format → Small multiples → Grid layout:** set Rows and Columns (e.g. 3 × 3)
  so tiles are readable; the grid scrolls when there are more metrics than fit.
- **Lines:** give `limit_max`/`limit_min` a distinct (e.g. dashed) style so limits read
  differently from the value line.
- Resize the visual to fill the page.

## 8. Refresh workflow (when data updates)

1. Regenerate the dataset from the app (it overwrites `powerbi_dataset.csv`).
2. In Power BI Desktop: **Home → Refresh**.

That's it — existing tiles update and any brand-new metrics appear as new tiles.

## 9. Acceptance walkthrough — adding `custom_VaR`

Use this to confirm the auto-handling works:

1. Add a new metric `custom_VaR` (and optionally `custom_VaR_limmaxvalue` /
   `custom_VaR_limminvalue`) to the source data.
2. Run the analysis in the app and regenerate the dataset.
3. In Power BI: **Home → Refresh**.
4. **Expected:** a new `custom_VaR` tile appears in the grid, in its sorted position, with
   no edits to the `.pbix`.

## 10. Known limitations

- **Shared Y-axis:** Power BI small multiples share one Y-axis across all tiles. A metric
  ranging 0–0.001 shown next to one ranging 0–5000 will look flat. The per-metric *adaptive
  scaling* available in the HTML report is **not** available in this view.
- **Per-metric axes / richer per-metric layout:** if you need each metric on its own axis
  (plus stats and breach callouts per metric), build a **paginated report** in **Power BI
  Report Builder** — a chart that repeats once per `metric`, exporting cleanly to multi-page
  PDF. That is a separate, heavier build; this guide covers the interactive small-multiples
  report only.
