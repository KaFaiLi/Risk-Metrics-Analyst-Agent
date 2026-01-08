# Feature Specification: Batch Visualization Enhancements

**Feature Branch**: `001-batch-viz-enhance`  
**Created**: January 8, 2026  
**Status**: Draft  
**Input**: User description: "Batch processing with stranaNodeName column separation, graph scaling improvements for small values with large limits, and handling systematically missing data patterns"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Batch Analysis by Node Grouping (Priority: P1)

As a risk analyst, I want to automatically split my dataset by the `stranaNodeName` column and generate separate visualization reports for each node, so that I can analyze risk metrics for individual portfolios or business units without manually filtering the data.

**Why this priority**: This is the core batch processing capability. Analysts currently have to manually filter data and run the analysis multiple times, which is time-consuming and error-prone for large datasets with multiple nodes.

**Independent Test**: Can be fully tested by uploading a CSV file containing multiple distinct values in the `stranaNodeName` column and verifying that separate analysis outputs are generated for each unique node value.

**Acceptance Scenarios**:

1. **Given** a CSV file with a `stranaNodeName` column containing values "a", "b", and "c", **When** the user enables batch processing mode and runs the analysis, **Then** the system generates three separate sets of visualizations and reports, one for each node.

2. **Given** a CSV file with a `stranaNodeName` column, **When** the user chooses batch processing, **Then** each generated report clearly identifies which node it belongs to in the title and filename.

3. **Given** a CSV file without a `stranaNodeName` column, **When** the user attempts batch processing, **Then** the system displays a clear message explaining the column is required and falls back to single-analysis mode.

4. **Given** a large dataset with 10+ unique node values, **When** batch processing completes, **Then** the user can browse, download, or export reports for each node individually or as a combined package.

---

### User Story 2 - Adaptive Graph Scaling (Priority: P2)

As a risk analyst viewing charts, I want the system to intelligently handle cases where metric values are small but limit boundaries are very large, so that I can still visually discern patterns and trends in the actual data without the chart appearing as a compressed flat line.

**Why this priority**: Visualization readability is critical for risk analysis. Charts that appear as flat lines due to extreme limit ranges render the tool ineffective for its primary purpose.

**Independent Test**: Can be tested by uploading a CSV where a metric has values ranging from 0.01 to 0.05 but limits set at ±100,000, and verifying the chart displays the metric data in a readable, expanded view.

**Acceptance Scenarios**:

1. **Given** a metric with values between 0-100 but max/min limits of ±100,000, **When** the chart is rendered, **Then** the user can clearly see the data trend without it appearing as a flat line pressed against the x-axis.

2. **Given** a chart with detected scale disparity, **When** the chart is displayed, **Then** the user receives a visual indicator or note explaining that adaptive scaling has been applied.

3. **Given** adaptive scaling is applied, **When** the user views the chart, **Then** limit breach information remains clearly communicated (even if limit lines are not fully visible on the zoomed view).

4. **Given** a metric where values naturally span close to the limit range, **When** the chart is rendered, **Then** no adaptive scaling is applied and the full limit lines are shown as normal.

---

### User Story 3 - Missing Data Pattern Handling (Priority: P2)

As a risk analyst, I want line charts to display correctly on a continuous time scale even when there are systematic gaps in the data (such as weekends or holidays), so that I can see unbroken trend lines while preserving accurate date context.

**Why this priority**: Data integrity visualization is essential. When charts fail to render due to missing data patterns, analysts lose critical visibility into risk trends.

**Independent Test**: Can be tested by uploading a CSV where data exists only on business days (or every other day), and verifying the chart renders a visible, continuous line on a proper time-scaled x-axis.

**Acceptance Scenarios**:

1. **Given** a dataset where values are recorded only on business days (weekdays), **When** the chart is rendered, **Then** a continuous line is displayed using linear interpolation for weekend gaps, with the x-axis showing the full date range.

2. **Given** a dataset with alternating day gaps (data every 2nd day), **When** the chart is rendered, **Then** the line chart displays correctly with interpolated values filling the gaps.

3. **Given** interpolated data is used for display, **When** statistics are calculated, **Then** only original (non-interpolated) data points are used for mean, median, std, outlier detection, and breach calculations.

---

### Edge Cases

- What happens when all nodes in batch processing have zero data points for a metric? → Display empty state with message "No data available for this metric"
- How does the system handle a node with only 1-2 data points (insufficient for meaningful statistics)? → Generate partial report with available data and display warning about limited statistics reliability
- What happens when adaptive scaling is needed but the user has explicitly set chart axis ranges?
- What happens if `stranaNodeName` values contain special characters or very long strings?

## Requirements *(mandatory)*

### Functional Requirements

**Batch Processing**

- **FR-001**: System MUST detect the presence of a `stranaNodeName` column (case-insensitive) in uploaded CSV files.
- **FR-002**: System MUST provide a batch processing toggle when the `stranaNodeName` column is detected.
- **FR-003**: System MUST split the dataset by unique values in the `stranaNodeName` column when batch processing is enabled.
- **FR-004**: System MUST generate separate visualization outputs (charts, statistics, AI insights) for each unique node value.
- **FR-005**: System MUST clearly label each output with its corresponding node identifier in titles, filenames, and reports.
- **FR-006**: System MUST allow users to export batch results either as individual node packages or as a combined archive.
- **FR-007**: System MUST display progress indication showing which node is currently being processed during batch analysis.
- **FR-008**: System MUST present batch results using horizontal tabs, one per node, allowing users to click and switch between node views.
- **FR-009**: System MUST organize combined batch export archives by node folder structure (e.g., `/NodeA/charts/`, `/NodeA/report.html`).

**Adaptive Graph Scaling**

- **FR-010**: System MUST detect when metric values occupy less than 10% of the chart's y-axis range due to large limit boundaries.
- **FR-011**: System MUST automatically apply adaptive scaling to zoom the chart view to the actual data range when scale disparity is detected.
- **FR-012**: System MUST indicate to users when adaptive scaling has been applied to a chart.
- **FR-013**: System MUST preserve limit breach information in statistics and text even when limit lines are outside the zoomed view.
- **FR-014**: System MUST allow users to toggle between adaptive (zoomed) and full-scale views.
- **FR-015**: When adaptive scaling hides limit lines, system MUST display a structured annotation banner showing limit values grouped by time period (date range, min limit, max limit) to communicate limit changes over time.

**Missing Data Pattern Handling**

- **FR-016**: System MUST maintain a continuous time scale x-axis for charts (not categorical).
- **FR-017**: System MUST detect systematic missing data patterns (e.g., weekends, every-N-day gaps) in the time series.
- **FR-018**: System MUST apply linear interpolation to fill systematic gaps, ensuring the line chart renders continuously without visual breaks.
- **FR-019**: Interpolated values MUST be used for display purposes only; original data (without interpolation) MUST be used for all statistical calculations and breach detection.

### Key Entities *(include if feature involves data)*

- **Node Group**: A logical partition of the dataset identified by a unique `stranaNodeName` value. Contains its own subset of date-metric observations.
- **Scale Context**: Metadata about a chart's y-axis range including data min/max, limit min/max, and whether adaptive scaling is applied.
- **Gap Pattern**: A detected regularity in missing time series data, characterized by frequency (e.g., every 2 days) and coverage percentage.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can process a multi-node dataset and receive all node-specific reports in under 5 minutes for datasets with up to 10 nodes and 5,000 rows per node.
- **SC-002**: Charts with small-value metrics and large limits are visually interpretable—data trends must be discernible without external tools or manual axis adjustment.
- **SC-003**: Time series with systematic missing data (weekends, holidays, regular intervals) render as continuous lines using linear interpolation, while preserving original data for all calculations.
- **SC-004**: 95% of users successfully identify the node associated with a report within 3 seconds of viewing it.
- **SC-005**: Users can toggle between adaptive and full-scale chart views within 1 click/tap.
- **SC-006**: Batch processing completes without manual intervention—no user prompts required during execution for a standard 10-node dataset.

## Assumptions

- The `stranaNodeName` column, when present, contains categorical string values suitable for grouping (not numeric IDs requiring interpretation).
- Systematic missing data patterns are regular (every N days, weekdays-only) rather than random or irregular.
- Adaptive scaling should prioritize data readability over limit visualization when there is a significant scale mismatch.
- Batch processing results should be stored temporarily for session duration to allow users to navigate between node reports without re-processing.

## Clarifications

### Session 2026-01-08

- Q: How should users navigate between node reports after batch processing? → A: Horizontal tabs showing all node names, click to switch views
- Q: What should the system do when a node has insufficient data (1-2 points)? → A: Generate partial report with available data and display warning about limited statistics reliability
- Q: How should adaptive scaling communicate off-screen limits? → A: Text annotation banner above chart showing limit values grouped by time periods (e.g., "2025-01-01 to 2025-01-30: Min -10,000 / Max 40,000") in a visually structured format
- Q: How should missing data be handled in charts? → A: Keep continuous time scale x-axis; use linear interpolation to fill systematic gaps (weekends, regular intervals) so line displays correctly
- Q: How should batch export archives be organized? → A: By node folder structure (`/NodeA/charts/`, `/NodeA/report.html`, `/NodeB/charts/`, etc.)
