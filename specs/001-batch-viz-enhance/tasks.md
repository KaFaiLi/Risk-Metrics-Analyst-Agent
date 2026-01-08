# Tasks: Batch Visualization Enhancements

**Input**: Design documents from `/specs/001-batch-viz-enhance/`  
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, quickstart.md ✓

**Tests**: No automated tests exist in this project; manual validation via `streamlit run app_main.py`

**Organization**: Tasks grouped by user story to enable independent implementation and testing

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths relative to repository root

---

## Phase 1: Setup

**Purpose**: Add new constants and extend session state for all features

- [x] T001 Add NODE_COLUMN constant to risk_metrics_app/config.py
- [x] T002 [P] Extend initialize_session_state() with batch and scaling keys in risk_metrics_app/app.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data structures and utilities that all user stories depend on

**⚠️ CRITICAL**: Complete before starting any user story implementation

- [x] T003 [P] Create InterpolatedSeries dataclass in risk_metrics_app/metrics.py
- [x] T004 [P] Create ScaleContext and LimitPeriod dataclasses in risk_metrics_app/visuals.py
- [x] T005 Add helper function sanitize_node_name() for filesystem-safe names in risk_metrics_app/reporting.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Batch Analysis by Node Grouping (Priority: P1) 🎯 MVP

**Goal**: Split datasets by `stranaNodeName` column and generate separate visualizations per node with tab navigation

**Independent Test**: Upload `Examples/Fake Pivot Metrics.csv`, enable batch mode, verify tabs "a" and "b" appear with separate analyses

### Implementation for User Story 1

- [x] T006 [P] [US1] Implement detect_node_column() function in risk_metrics_app/metrics.py
- [x] T007 [P] [US1] Implement split_by_node() function in risk_metrics_app/metrics.py
- [x] T008 [US1] Add batch mode detection and checkbox to render_sidebar() in risk_metrics_app/app.py
- [x] T009 [US1] Create handle_batch_analysis() function to process all nodes in risk_metrics_app/app.py
- [x] T010 [US1] Add progress bar display during batch processing in risk_metrics_app/app.py
- [x] T011 [US1] Implement tab-based results display using st.tabs() in risk_metrics_app/app.py
- [x] T012 [US1] Create render_node_results() helper to display single node analysis in risk_metrics_app/app.py
- [x] T013 [US1] Handle edge case: node with insufficient data (1-2 points) warning in risk_metrics_app/app.py
- [x] T014 [P] [US1] Implement create_batch_export_package() with node folder structure in risk_metrics_app/reporting.py
- [x] T015 [US1] Add batch export buttons (individual + combined) to render_export_options() in risk_metrics_app/app.py
- [x] T016 [US1] Update run_app() to route between single and batch analysis modes in risk_metrics_app/app.py

**Checkpoint**: Batch processing fully functional - can upload multi-node CSV, see tabs, export per-node packages

---

## Phase 4: User Story 2 - Adaptive Graph Scaling (Priority: P2)

**Goal**: Detect scale disparity and zoom charts to data range with limit annotation banners

**Independent Test**: Upload CSV with metric values 0-100 and limits ±100,000, verify chart zooms to data with limit banner visible

### Implementation for User Story 2

- [x] T017 [P] [US2] Implement calculate_scale_context() function in risk_metrics_app/visuals.py
- [x] T018 [P] [US2] Implement group_limit_periods() function in risk_metrics_app/visuals.py
- [x] T019 [US2] Implement create_limit_annotation_html() function in risk_metrics_app/visuals.py
- [x] T020 [US2] Modify create_plotly_chart() to accept scale_context parameter in risk_metrics_app/visuals.py
- [x] T021 [US2] Apply yaxis.range when adaptive_applied is True in create_plotly_chart() in risk_metrics_app/visuals.py
- [x] T022 [US2] Integrate scale context calculation into analysis loop in risk_metrics_app/app.py
- [x] T023 [US2] Display limit annotation banner above chart when adaptive scaling applied in risk_metrics_app/app.py
- [x] T024 [US2] Add toggle checkbox for adaptive vs full-scale view per metric in risk_metrics_app/app.py
- [x] T025 [US2] Store and restore adaptive_scale_toggles in session state in risk_metrics_app/app.py

**Checkpoint**: Adaptive scaling works - small-value metrics with large limits show readable charts with limit banners

---

## Phase 5: User Story 3 - Missing Data Interpolation (Priority: P2)

**Goal**: Apply linear interpolation to fill systematic gaps while preserving original data for calculations

**Independent Test**: Create CSV with business-day-only data, verify continuous line chart on time-scaled x-axis

### Implementation for User Story 3

- [x] T026 [P] [US3] Implement detect_systematic_gaps() function in risk_metrics_app/metrics.py
- [x] T027 [US3] Implement interpolate_for_display() function returning InterpolatedSeries in risk_metrics_app/metrics.py
- [x] T028 [US3] Modify create_plotly_chart() to accept display_series parameter in risk_metrics_app/visuals.py
- [x] T029 [US3] Use display_series for line trace, original data for outlier markers in risk_metrics_app/visuals.py
- [x] T030 [US3] Integrate interpolation into analysis loop in risk_metrics_app/app.py
- [x] T031 [US3] Ensure calculate_statistics() receives original (non-interpolated) data in risk_metrics_app/app.py

**Checkpoint**: Interpolation works - business-day data shows continuous lines, statistics use original data only

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Integration, edge cases, and documentation

- [x] T032 [P] Add logging for batch processing operations in risk_metrics_app/app.py
- [x] T033 [P] Add logging for adaptive scaling decisions in risk_metrics_app/visuals.py
- [x] T034 Handle edge case: stranaNodeName with special characters in risk_metrics_app/metrics.py
- [x] T035 Update HTML report template for batch mode (node titles, navigation) in risk_metrics_app/reporting.py
- [x] T036 Run manual validation per quickstart.md test scenarios
- [x] T037 Update __all__ exports in modified modules

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) ─────────────────────────────────┐
                                                 │
Phase 2 (Foundational) ──────────────────────────┼─► BLOCKS all user stories
                                                 │
                        ┌────────────────────────┘
                        │
                        ▼
              ┌─────────────────────┐
              │  User Stories Can   │
              │  Start in Parallel  │
              └─────────────────────┘
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
     Phase 3        Phase 4        Phase 5
    (US1 - P1)     (US2 - P2)     (US3 - P2)
     Batch         Adaptive      Interpolation
         │              │              │
         └──────────────┼──────────────┘
                        │
                        ▼
                   Phase 6
                   (Polish)
```

### User Story Dependencies

- **User Story 1 (P1)**: No dependencies on other stories - can deliver as MVP
- **User Story 2 (P2)**: No dependencies on US1 - can be implemented independently
- **User Story 3 (P2)**: No dependencies on US1 or US2 - can be implemented independently

### Within Each User Story

1. Data processing functions (metrics.py) before visualization (visuals.py)
2. Core functions before UI integration (app.py)
3. UI before exports (reporting.py)

### Parallel Opportunities

**Phase 1**: T001, T002 can run in parallel (different files)

**Phase 2**: T003, T004, T005 can run in parallel (different files)

**Phase 3 (US1)**: 
- T006, T007 can run in parallel (both in metrics.py but independent functions)
- T014 can start after T007 (needs sanitize from T005)

**Phase 4 (US2)**:
- T017, T018 can run in parallel (independent functions in visuals.py)

**Phase 5 (US3)**:
- T026 can start immediately after Phase 2
- T027 depends on T026

**Phase 6**:
- T032, T033 can run in parallel (different files)

---

## Parallel Example: User Story 1

```bash
# After Phase 2 complete, launch these in parallel:
T006: "Implement detect_node_column() in metrics.py"
T007: "Implement split_by_node() in metrics.py"
T014: "Implement create_batch_export_package() in reporting.py"

# Then sequentially in app.py:
T008 → T009 → T010 → T011 → T012 → T013 → T015 → T016
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T005)
3. Complete Phase 3: User Story 1 (T006-T016)
4. **STOP and VALIDATE**: 
   - Upload `Examples/Fake Pivot Metrics.csv`
   - Enable batch mode
   - Verify tabs "a" and "b" appear
   - Verify export creates node folders
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add User Story 1 → Test → **MVP Complete!** (batch processing works)
3. Add User Story 2 → Test → Charts readable with large limits
4. Add User Story 3 → Test → Business-day data renders correctly
5. Polish phase → Production ready

### Sequential Implementation (Single Developer)

Recommended order for solo development:
```
T001 → T002 → T003 → T004 → T005 (Foundation)
→ T006 → T007 → T008 → T009 → T010 → T011 → T012 → T013 → T014 → T015 → T016 (US1 complete)
→ T017 → T018 → T019 → T020 → T021 → T022 → T023 → T024 → T025 (US2 complete)
→ T026 → T027 → T028 → T029 → T030 → T031 (US3 complete)
→ T032 → T033 → T034 → T035 → T036 → T037 (Polish)
```

---

## Notes

- All file paths are relative to `risk_metrics_app/` package
- No automated tests - validate manually per quickstart.md
- Session state keys must be initialized before use
- Commit after each task or logical group (e.g., after completing each user story)
- Use `Examples/Fake Pivot Metrics.csv` for testing (contains nodes "a" and "b")
