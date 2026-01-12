# Tasks: Metric Keyword Filter

**Feature Branch**: `002-metric-keyword-filter`  
**Date**: January 12, 2026  
**Input**: Design documents from `/specs/002-metric-keyword-filter/`

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Tasks include exact file paths

---

## Phase 1: Setup

**Purpose**: Add configuration constants and core filter functions

- [X] T001 [P] Add `MAX_EXCLUSION_KEYWORDS = 50` constant to `risk_metrics_app/config.py`
- [X] T002 Add `parse_exclusion_keywords()` function to `risk_metrics_app/metrics.py`
- [X] T003 Add `filter_metrics_by_keywords()` function to `risk_metrics_app/metrics.py`
- [X] T004 Add `get_metric_columns()` helper function to `risk_metrics_app/metrics.py`

**Checkpoint**: Core filter logic available for integration

---

## Phase 2: Foundational (Session State)

**Purpose**: Initialize session state keys for filter persistence

- [X] T005 Add `exclusion_keywords_raw` and `uploaded_file_columns` to `initialize_session_state()` in `risk_metrics_app/app.py`

**Checkpoint**: Session state ready for UI and analysis integration

---

## Phase 3: User Story 1 & 2 - Single/Multiple Keyword Exclusion (Priority: P1) 🎯 MVP

**Goal**: Enable users to exclude metrics by one or more comma-separated keywords

**Independent Test**: Enter keyword(s) in sidebar, run analysis, verify matching metrics are excluded from results

- [X] T006 [US1/2] Add exclusion keyword text input to sidebar in `render_sidebar()` in `risk_metrics_app/app.py`
- [X] T007 [US1/2] Cache metric columns on file upload in `handle_analysis()` in `risk_metrics_app/app.py`
- [X] T008 [US1/2] Apply keyword filter in `_handle_single_analysis()` after `organize_metrics()` in `risk_metrics_app/app.py`
- [X] T009 [US1/2] Display excluded metric count and block analysis if all metrics excluded in `risk_metrics_app/app.py`

**Checkpoint**: Core exclusion functionality working in single-file mode

---

## Phase 4: User Story 3 - Case-Insensitive Matching (Priority: P2)

**Goal**: Ensure keyword matching works regardless of case

**Independent Test**: Enter lowercase keyword for uppercase metric name, verify match

**Note**: Case-insensitivity is built into `filter_metrics_by_keywords()` implementation (T003). This phase validates the behavior.

- [X] T010 [US3] Verify case-insensitive matching works in `filter_metrics_by_keywords()` by testing with "basis" for "BasisSensi" metric

**Checkpoint**: Case-insensitive matching confirmed

---

## Phase 5: User Story 5 - Visual Feedback / Live Preview (Priority: P2)

**Goal**: Show live count of metrics that will be excluded as user types

**Independent Test**: Type keywords in sidebar, see count update before running analysis

- [X] T011 [US5] Add live preview count display below keyword input in sidebar in `risk_metrics_app/app.py`
- [X] T012 [US5] Show warning if >50 keywords entered in `risk_metrics_app/app.py`
- [X] T013 [US5] Show error message if all metrics would be excluded (preview) in `risk_metrics_app/app.py`

**Checkpoint**: Live preview provides immediate feedback to users

---

## Phase 6: User Story 4 - Session Persistence (Priority: P3)

**Goal**: Keywords persist when uploading new files or changing settings

**Independent Test**: Enter keywords, upload new file, verify keywords remain

**Note**: Session persistence is implemented via `st.session_state` in T005/T006. This phase validates the behavior.

- [X] T014 [US4] Verify keywords persist after uploading new file
- [X] T015 [US4] Reset `uploaded_file_columns` cache in `reset_analysis_state()` while preserving keywords in `risk_metrics_app/app.py`

**Checkpoint**: Session persistence working as expected

---

## Phase 7: Batch Mode Support

**Goal**: Ensure filter works consistently in batch processing mode

**Independent Test**: Upload multi-node CSV, apply filter, verify all nodes are filtered

- [X] T016 Apply keyword filter in `_process_node_analysis()` for batch mode in `risk_metrics_app/app.py`
- [X] T017 Handle edge case where all metrics in a single node are excluded in batch mode

**Checkpoint**: Filter works identically in single-file and batch modes (SC-003)

---

## Phase 8: Polish & Validation

**Purpose**: Final cleanup and manual testing

- [X] T018 [P] Add imports for new functions at top of `risk_metrics_app/app.py`
- [ ] T019 Manual test: Single keyword exclusion with sample CSV
- [ ] T020 Manual test: Multiple keywords with inconsistent spacing
- [ ] T021 Manual test: Case-insensitive matching
- [ ] T022 Manual test: All metrics excluded error handling
- [ ] T023 Manual test: Batch mode with keyword filter
- [ ] T024 Manual test: Session persistence across file uploads

---

## Dependencies

```
T001 ─┐
T002 ─┼─► T005 ─► T006 ─► T007 ─► T008 ─► T009 ─► T011 ─► T016
T003 ─┤                                      │
T004 ─┘                                      ▼
                                         T018 ─► T019-T024
```

### Parallel Opportunities

| Group | Tasks | Reason |
|-------|-------|--------|
| Config & Functions | T001, T002-T004 | Different files, no dependencies |
| Final Polish | T018, T019-T024 | Independent validation tasks |

---

## Implementation Strategy

### MVP Scope (Phase 1-3)

Deliver User Stories 1 & 2 first. This provides:
- Core keyword exclusion functionality
- Single and multiple keyword support
- Working single-file mode

**Estimated effort**: ~2 hours

### Full Feature (Phase 4-8)

Add remaining stories incrementally:
- Phase 4: Validation only (built-in)
- Phase 5: Live preview UI (~30 min)
- Phase 6: Validation only (built-in)
- Phase 7: Batch mode support (~30 min)
- Phase 8: Testing (~1 hour)

**Total estimated effort**: ~4 hours

---

## Validation Summary

| Success Criteria | Validation Task |
|------------------|-----------------|
| SC-001: Exclude in <10 seconds | T019 |
| SC-002: 100% accuracy | T019, T020, T021 |
| SC-003: Single/batch parity | T023 |
| SC-004: Clear filtered count | T011, T019 |
| SC-005: Case-insensitive | T021 |
