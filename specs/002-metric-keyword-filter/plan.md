# Implementation Plan: Metric Keyword Filter

**Branch**: `002-metric-keyword-filter` | **Date**: January 12, 2026 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-metric-keyword-filter/spec.md`

## Summary

Allow users to input keywords to filter out (exclude) risk metrics from analysis. The filter uses comma-separated keywords with case-insensitive substring matching. A live preview shows how many metrics will be excluded before running analysis. The filter persists in session state and works consistently in both single-file and batch processing modes.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Streamlit, Pandas, Plotly, LangChain (Google Gemini)  
**Storage**: File-based (CSV input, PNG/HTML/ZIP output to `Output/`)  
**Testing**: Manual testing (no automated test framework currently in place)  
**Target Platform**: Windows desktop, Streamlit web app  
**Project Type**: Single Streamlit application with modular package structure  
**Performance Goals**: Filter application in under 10 seconds (SC-001); keyword matching is O(n*k) where n=metrics, k=keywords  
**Constraints**: Session-based state; filter resets on browser refresh  
**Scale/Scope**: Typical: 10-50 metrics, 1-20 keywords, instantaneous filtering

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution is template-only (no project-specific principles defined). Proceeding with standard best practices:

| Gate | Status | Notes |
|------|--------|-------|
| Simplicity | ✅ PASS | Single text input, simple string matching, no new dependencies |
| Modularity | ✅ PASS | New filter function in metrics.py, UI integration in app.py sidebar |
| Test Coverage | ⚠️ N/A | No automated tests exist; manual validation approach continues |

## Project Structure

### Documentation (this feature)

```text
specs/002-metric-keyword-filter/
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
├── app.py           # Main Streamlit UI (sidebar filter input, live preview, filter application)
├── config.py        # Constants (new: MAX_EXCLUSION_KEYWORDS = 50)
├── metrics.py       # Data processing (new: parse_exclusion_keywords, filter_metrics_by_keywords)
├── visuals.py       # Chart creation (unchanged)
├── reporting.py     # Export functions (unchanged - receives pre-filtered metrics)
├── llm.py           # AI insights (unchanged - processes filtered metrics)
└── prompts.py       # LLM prompts (unchanged)
```

**Structure Decision**: Single project structure maintained. Filter logic added to metrics.py (data processing layer), UI components in app.py sidebar alongside existing configuration options.

## Complexity Tracking

No constitution violations. Feature is a simple input filter that integrates cleanly with existing metric processing pipeline.

---

## Phase 0: Research

See [research.md](research.md) for detailed findings.

### Key Decisions

| Topic | Decision | Rationale |
|-------|----------|-----------|
| Input Component | Streamlit `st.text_input` in sidebar | Consistent with existing configuration layout |
| Keyword Parsing | Split by comma, strip whitespace, filter empty, deduplicate | Handles user input variations (FR-010) |
| Matching Strategy | Case-insensitive substring (`keyword.lower() in metric.lower()`) | Simple, predictable, no regex complexity (FR-003, FR-009) |
| Live Preview Trigger | `on_change` callback on text input | Updates count without running full analysis |
| Filter Application Point | After `organize_metrics()`, before metric processing loop | Single integration point for both modes |
| Session State Key | `exclusion_keywords_raw` (string), `exclusion_keywords_parsed` (list) | Preserves raw input for display, parsed for logic |

---

## Phase 1: Design

### Data Model

See [data-model.md](data-model.md) for entity definitions.

### Contracts

No external API contracts needed. Filter is internal UI/processing logic.

### Integration Points

1. **Sidebar Input** (app.py `render_sidebar`)
   - Add text input after "Hide metrics without limits" checkbox
   - Add live preview count display

2. **Metric Filtering** (app.py `handle_analysis`, `_handle_single_analysis`, `_handle_batch_analysis`)
   - Call `filter_metrics_by_keywords()` after `organize_metrics()`
   - Display filtered count in UI
   - Block analysis if all metrics filtered (FR-008)

3. **Session State** (app.py `initialize_session_state`)
   - Initialize `exclusion_keywords_raw = ""`
   - Persist across file uploads and setting changes

### Quickstart

See [quickstart.md](quickstart.md) for implementation guide.
