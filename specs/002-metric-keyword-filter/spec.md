# Feature Specification: Metric Keyword Filter

**Feature Branch**: `002-metric-keyword-filter`  
**Created**: January 12, 2026  
**Status**: Draft  
**Input**: User description: "Allow users to input keywords to filter out multiple risk metrics they want to exclude from analysis"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Exclude Single Keyword Match (Priority: P1)

As a risk analyst, I want to exclude metrics containing a specific keyword (e.g., "Basis") so that I can focus my analysis on the metrics that are most relevant to my current task without being overwhelmed by unrelated data.

**Why this priority**: This is the core functionality - being able to filter out metrics by a single keyword is the minimum viable feature that delivers immediate value to users who deal with large numbers of metrics.

**Independent Test**: Can be fully tested by entering a single keyword in the filter input, running analysis, and verifying that metrics containing that keyword are excluded from results, charts, and reports.

**Acceptance Scenarios**:

1. **Given** a CSV with metrics including "BasisSensiByCurrencyByPillar[EUR][1W]", "VaR", "SVaR", **When** user enters "Basis" as exclusion keyword and runs analysis, **Then** only "VaR" and "SVaR" metrics are processed and displayed
2. **Given** the exclusion filter is empty, **When** user runs analysis, **Then** all metrics from the CSV are processed (no filtering applied)
3. **Given** user enters a keyword that matches no metrics, **When** user runs analysis, **Then** all metrics are processed and a subtle indicator shows no metrics were filtered

---

### User Story 2 - Exclude Multiple Keywords (Priority: P1)

As a risk analyst, I want to exclude metrics matching multiple different keywords at once so that I can quickly narrow down to the specific metrics I need without repeatedly running the analysis.

**Why this priority**: Users often need to exclude several categories of metrics simultaneously. This is essential for efficient workflow when dealing with datasets containing many metric types.

**Independent Test**: Can be fully tested by entering multiple comma-separated keywords, running analysis, and verifying all matching metrics are excluded.

**Acceptance Scenarios**:

1. **Given** a CSV with metrics "VaR", "SVaR", "BasisSensi_EUR", "CreditDelta", "CreditVega", **When** user enters "Basis, Credit" as exclusion keywords, **Then** only "VaR" and "SVaR" are processed
2. **Given** user enters multiple keywords with inconsistent spacing (e.g., "Basis,Credit, Vega"), **When** analysis runs, **Then** system trims whitespace and correctly excludes all matching metrics
3. **Given** user enters duplicate keywords (e.g., "Basis, Basis, Credit"), **When** analysis runs, **Then** system treats them as unique keywords without errors

---

### User Story 3 - Case-Insensitive Matching (Priority: P2)

As a risk analyst, I want keyword matching to be case-insensitive so that I don't have to worry about the exact capitalization of metric names when filtering.

**Why this priority**: Case sensitivity would create friction and confusion. Users shouldn't need to remember exact casing of metric names.

**Independent Test**: Can be tested by entering keywords in various cases and verifying matches regardless of case.

**Acceptance Scenarios**:

1. **Given** a metric named "BasisSensiByCurrencyByPillar", **When** user enters "basis" (lowercase), **Then** the metric is excluded
2. **Given** a metric named "VaR", **When** user enters "VAR" or "var" or "Var", **Then** the metric is excluded

---

### User Story 4 - Persist Filter Across Session (Priority: P3)

As a risk analyst, I want my exclusion keywords to persist during my session so that I don't have to re-enter them if I upload a new file or adjust other settings.

**Why this priority**: Improves user experience but is not critical for core functionality. Users can still accomplish their goals without persistence.

**Independent Test**: Can be tested by entering keywords, uploading a new file, and verifying keywords are still present.

**Acceptance Scenarios**:

1. **Given** user has entered exclusion keywords, **When** user uploads a new CSV file, **Then** the exclusion keywords remain in the input field
2. **Given** user has entered exclusion keywords, **When** user changes other analysis settings, **Then** the exclusion keywords are preserved

---

### User Story 5 - Visual Feedback on Filtered Metrics (Priority: P2)

As a risk analyst, I want to see how many metrics were filtered out so that I have confidence the filter is working as expected.

**Why this priority**: Provides transparency and helps users verify their filters are working correctly without being core functionality.

**Independent Test**: Can be tested by applying filters and checking for displayed count of excluded metrics.

**Acceptance Scenarios**:

1. **Given** user enters keywords that match 5 out of 20 metrics, **When** analysis completes, **Then** UI displays "15 metrics analyzed (5 excluded by filter)"
2. **Given** user enters keywords that match all metrics, **When** user attempts analysis, **Then** system shows a warning that no metrics remain for analysis

---

### Edge Cases

- What happens when all metrics are filtered out? → Display clear error message, prevent analysis from running
- What happens when filter keywords contain special regex characters (e.g., brackets, asterisks)? → Treat keywords as literal strings, not regex patterns
- How does the system handle very long keyword lists? → Accept up to 50 keywords; show warning if exceeded
- What happens with empty keywords in a list (e.g., "Basis,,Credit")? → Skip empty entries, process valid keywords only

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a text input field in the sidebar for entering metric exclusion keywords
- **FR-002**: System MUST support comma-separated keywords for excluding multiple metric patterns
- **FR-003**: System MUST perform case-insensitive substring matching when filtering metrics
- **FR-004**: System MUST exclude any metric whose name contains any of the specified keywords
- **FR-005**: System MUST apply the filter before metric processing, chart generation, and report creation
- **FR-006**: System MUST preserve exclusion keywords in session state across file uploads and setting changes
- **FR-007**: System MUST display the count of excluded metrics after filtering is applied
- **FR-008**: System MUST show a warning when all metrics would be filtered out and prevent analysis
- **FR-009**: System MUST treat keywords as literal strings (not regex patterns) for predictable behavior
- **FR-010**: System MUST trim whitespace from individual keywords in the comma-separated list
- **FR-011**: System MUST apply the filter consistently in both single-file and batch processing modes
- **FR-012**: System MUST show a live count preview (e.g., "5 metrics will be excluded") as user types keywords, before running analysis

### Key Entities

- **Exclusion Keywords**: User-provided comma-separated string of keywords to match against metric names
- **Filtered Metrics**: Subset of metrics remaining after exclusion filter is applied
- **Filter Summary**: Count of total metrics, analyzed metrics, and excluded metrics

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can exclude metrics by keyword in under 10 seconds (enter keywords, run analysis)
- **SC-002**: Filter correctly excludes all metrics containing any specified keyword with 100% accuracy
- **SC-003**: Filter works identically in single-file and batch processing modes
- **SC-004**: Users can clearly see how many metrics were filtered vs. analyzed
- **SC-005**: No user confusion about case sensitivity (case-insensitive matching works consistently)

## Assumptions

- Users primarily want to exclude metrics by partial name matching (substring), not exact matching
- Comma is an acceptable delimiter for multiple keywords (metric names don't contain commas)
- The filter input should be in the sidebar alongside other analysis configuration options
- Session persistence means Streamlit session state; browser refresh will reset the filter
- The filter applies to metric column names, not to metric values or dates

## Clarifications

### Session 2026-01-12

- Q: When should the exclusion filter be applied—live preview or only on "Run Analysis"? → A: Live preview shows count only (e.g., "5 metrics will be excluded") as user types
- Q: Should the filter support inclusion keywords in addition to exclusion? → A: Exclusion-only (simpler UI, can add inclusion later if needed)
