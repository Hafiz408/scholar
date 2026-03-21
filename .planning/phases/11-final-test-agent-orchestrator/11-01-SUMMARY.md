---
phase: 11-final-test-agent-orchestrator
plan: "01"
subsystem: agents/orchestrator + db
tags: [orchestrator, state, sqlite, schema]
dependency_graph:
  requires: []
  provides: [ScholarState-V2, update_goal_progress, cumulative_tests-table]
  affects: [backend/app/agents/orchestrator.py, backend/app/db/database.py]
tech_stack:
  added: []
  patterns: [TypedDict-extension, aiosqlite-context-manager, CREATE-TABLE-IF-NOT-EXISTS]
key_files:
  created: []
  modified:
    - backend/app/agents/orchestrator.py
    - backend/app/db/database.py
decisions:
  - ScholarState extended additively (new V2 fields appended) so build_graph() needs no changes
  - cumulative_tests placed inside SQLITE_SCHEMA constant (not a separate migration) so init_db() handles it automatically
  - update_goal_progress() returns empty dict for unknown goal_id rather than raising
metrics:
  duration: "2 min"
  completed: "2026-03-22"
  tasks_completed: 2
  files_modified: 2
---

# Phase 11 Plan 01: ScholarState V2 + cumulative_tests Schema Summary

**One-liner:** Added V2 TypedDict fields and update_goal_progress() to orchestrator.py, and cumulative_tests SQLite table to database.py SQLITE_SCHEMA.

## What Was Built

### Task 1: ScholarState V2 + update_goal_progress()

Extended `ScholarState` TypedDict in `backend/app/agents/orchestrator.py` with five new fields:
- `sessions_complete: bool`
- `weak_session_ids: list[str]`
- `followup_sessions_added: int`
- `final_test_id: str | None`
- `goal_complete: bool`

Added `update_goal_progress(goal_id: str) -> dict` async function that queries study_goals and study_sessions via aiosqlite and returns computed progress state. Returns empty dict for unknown goal_id.

### Task 2: cumulative_tests Table

Appended `cumulative_tests` table definition to the `SQLITE_SCHEMA` constant in `backend/app/db/database.py`. The table stores:
- `id TEXT PRIMARY KEY`
- `goal_id TEXT NOT NULL` (FK to study_goals)
- `questions TEXT NOT NULL` (JSON list of TestQuestion dicts)
- `score REAL` (NULL until submitted, 0.0-1.0 after)
- `weak_session_numbers TEXT` (JSON list[int], NULL until submitted)
- `created_at TEXT`

`init_db()` picks up the new table automatically via `executescript(SQLITE_SCHEMA)` — no function changes required.

## Verification Results

All existing 8 pytest tests still pass:

```
tests/test_adaptive_planner.py::test_score_below_threshold_inserts_followup PASSED
tests/test_adaptive_planner.py::test_score_at_threshold_no_insertion PASSED
tests/test_adaptive_planner.py::test_null_score_no_insertion PASSED
tests/test_adaptive_planner.py::test_downstream_session_renumbered PASSED
tests/test_adaptive_planner.py::test_completed_session_keeps_number PASSED
tests/test_adaptive_planner.py::test_exception_propagates_from_planner PASSED
tests/test_adaptive_planner.py::test_manual_adapt_returns_shape PASSED
tests/test_adaptive_planner.py::test_manual_adapt_no_failed_sessions PASSED
8 passed, 5 warnings in 0.64s
```

Import verification:
- `from app.agents.orchestrator import ScholarState, update_goal_progress` — OK
- V2 fields confirmed in ScholarState.__annotations__
- `cumulative_tests` in SQLITE_SCHEMA — OK
- `init_db()` twice on fresh DB — OK (idempotent)

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | d1baf4e | feat(11-01): extend ScholarState V2 fields and add update_goal_progress() |
| Task 2 | c24e7ce | feat(11-01): add cumulative_tests table to SQLITE_SCHEMA in database.py |

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED
