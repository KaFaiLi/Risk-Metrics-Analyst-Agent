# Implementation Plan: Batch Visualization Enhancements

**Branch**: `001-batch-viz-enhance` | **Date**: January 8, 2026 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-batch-viz-enhance/spec.md`

## Summary

Enhance the Risk Metrics Analyst application with three capabilities:
1. **Batch processing** - Split datasets by `stranaNodeName` column and generate separate visualizations per node, presented via horizontal tabs
2. **Adaptive graph scaling** - Detect scale disparity between metric values and limits, zoom to data range, display limit annotation banners
3. **Missing data interpolation** - Apply linear interpolation to fill systematic gaps while preserving original data for calculations

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Streamlit, Pandas, Plotly, LangChain (Google Gemini)  
**Storage**: File-based (CSV input, PNG/HTML/ZIP output to `Output/`)  
**Testing**: Manual testing (no automated test framework currently in place)  
**Target Platform**: Windows desktop, Streamlit web app  
**Project Type**: Single Streamlit application with modular package structure  
**Performance Goals**: Process 10 nodes × 5,000 rows in under 5 minutes (SC-001)  
**Constraints**: Session-based state; artifacts written to `Output/` directory  
**Scale/Scope**: Typical datasets: 2-10 nodes, 500-5,000 rows per node, 10-50 metrics

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution is template-only (no project-specific principles defined). Proceeding with standard best practices:

| Gate | Status | Notes |
|------|--------|-------|
| Simplicity | ✅ PASS | Extends existing patterns; no new frameworks |
| Modularity | ✅ PASS | New functions in existing modules (metrics.py, visuals.py, app.py) |
| Test Coverage | ⚠️ N/A | No automated tests exist; manual validation approach continues |

## Project Structure

### Documentation (this feature)

```text
specs/001-batch-viz-enhance/
├── spec.md              # Feature specification (completed)
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
risk_metrics_app/
├── app.py           # Main Streamlit UI (batch tab navigation, progress indicators)
├── config.py        # Constants (new: NODE_COLUMN, INTERPOLATION_THRESHOLD)
├── metrics.py       # Data processing (new: split_by_node, detect_gaps, interpolate_series)
├── visuals.py       # Chart creation (new: adaptive_scaling, limit_annotation_banner)
├── reporting.py     # Export functions (new: batch export structure by node)
├── llm.py           # AI insights (unchanged - called per node)
└── prompts.py       # LLM prompts (unchanged)

Output/
├── {NodeA}/         # Batch export structure
│   ├── charts/
│   └── report.html
└── {NodeB}/
    ├── charts/
    └── report.html
```

**Structure Decision**: Single project structure maintained. New functionality integrates into existing modules following established patterns.

## Complexity Tracking

No constitution violations. Feature extends existing architecture without adding new patterns or dependencies.

---

## Phase 0: Research

See [research.md](research.md) for detailed findings.

### Key Decisions

| Topic | Decision | Rationale |
|-------|----------|-----------|
| Batch UI Pattern | Streamlit `st.tabs()` | Native component, supports dynamic tab creation, matches clarified requirement |
| Adaptive Scaling Threshold | 10% of y-axis range | Spec-defined; balances readability with limit visibility |
| Interpolation Method | `pandas.Series.interpolate(method='time')` | Time-aware linear interpolation built into pandas |
| Gap Detection | Compare actual dates to full date range | Simple, reliable approach for systematic gaps |
| Limit Period Grouping | Detect consecutive constant limit values | Groups by value changes to minimize annotation rows |

---

## Phase 1: Design

### Data Model

See [data-model.md](data-model.md) for entity definitions.

**Key Entities:**
- `NodeGroup`: Dataset partition with node name, filtered DataFrame, and per-metric analyses
- `ScaleContext`: Chart y-axis metadata (data range, limit range, scaling applied, limit periods)
- `InterpolatedSeries`: Original series + interpolated series + gap metadata

### API Contracts

No external API changes. Internal function signatures documented in [data-model.md](data-model.md).

### Implementation Approach

#### Feature 1: Batch Processing (P1)

1. **Detection** (`metrics.py`): Add `detect_node_column()` to find `stranaNodeName` (case-insensitive)
2. **Splitting** (`metrics.py`): Add `split_by_node(df, column)` returning `Dict[str, DataFrame]`
3. **UI Toggle** (`app.py`): Show batch mode checkbox when node column detected
4. **Tab Rendering** (`app.py`): Use `st.tabs()` with node names; iterate analysis per tab
5. **Progress** (`app.py`): Show `st.progress()` bar during batch processing
6. **Session State** (`app.py`): Store `batch_results: Dict[str, List[dict]]` keyed by node
7. **Export** (`reporting.py`): Modify `create_export_package()` to create node subfolders

#### Feature 2: Adaptive Graph Scaling (P2)

1. **Detection** (`visuals.py`): Add `calculate_scale_context()` comparing data range to limit range
2. **Scaling** (`visuals.py`): Modify `create_plotly_chart()` to accept `scale_context` and set `yaxis_range`
3. **Limit Periods** (`visuals.py`): Add `group_limit_periods()` to detect limit value changes over time
4. **Annotation** (`visuals.py`): Add `create_limit_annotation()` returning structured HTML/text
5. **Toggle** (`app.py`): Add checkbox per chart to toggle adaptive vs full scale
6. **State** (`app.py`): Store `scale_mode` per metric in session state

#### Feature 3: Missing Data Interpolation (P2)

1. **Gap Detection** (`metrics.py`): Add `detect_systematic_gaps()` analyzing date intervals
2. **Interpolation** (`metrics.py`): Add `interpolate_for_display()` using pandas time interpolation
3. **Chart Data** (`visuals.py`): Pass interpolated series for plotting, original for calculations
4. **Statistics** (`metrics.py`): Ensure `calculate_statistics()` receives original data only

### Quickstart

See [quickstart.md](quickstart.md) for developer onboarding guide.
