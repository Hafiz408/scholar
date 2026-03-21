---
phase: 11-final-test-agent-orchestrator
plan: "04"
subsystem: testing
tags: [pytest, tdd, final-test-agent, orchestrator, monkeypatch]
dependency_graph:
  requires: [11-01, 11-02, 11-03]
  provides: [test-coverage-TST-01, test-coverage-TST-02, test-coverage-TST-03, test-coverage-TST-04, test-coverage-TST-05, test-coverage-TST-06, test-coverage-ORC-01, test-coverage-ORC-02]
  affects: [CI]
tech_stack:
  added: []
  patterns: [monkeypatch-module-level, tmp_path-sqlite-isolation, side_effect-factory-for-mutable-mocks]
key_files:
  created:
    - backend/tests/test_final_test_agent.py
  modified: []
decisions:
  - "Used side_effect factory (not a single shared MagicMock return_value) for mock_test_output in TST-01/TST-02 test — shared mutable Pydantic objects are mutated by both session loop iterations, causing false session_number values; factory creates fresh objects per call"
  - "test_api_integration.py errors are pre-existing (require live DB lifespan); out-of-scope for this plan and not introduced by our changes"
metrics:
  duration: "5 min"
  completed: "2026-03-22"
  tasks_completed: 1
  files_created: 1
  files_modified: 0
requirements: [TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, ORC-01, ORC-02]
---

# Phase 11 Plan 04: Final Test Agent + Orchestrator V2 Tests Summary

**One-liner:** 15-test pytest suite covering TST-01 through TST-06 and ORC-01/ORC-02 with monkeypatched LLM and tmp_path SQLite isolation.

## What Was Built

`backend/tests/test_final_test_agent.py` — a complete CI-safe test suite for Phase 11, following the established `test_adaptive_planner.py` patterns:

- `tmp_db` fixture: async aiosqlite setup with minimal schema (study_goals, study_sessions, cumulative_tests) + seeded goal and 2 complete sessions
- `mock_retrieve` fixture: patches `app.agents.test_agent.retrieve` with async coroutine returning mock chunks
- All router tests call async handler functions directly (no TestClient overhead)
- Settings redirected via `monkeypatch.setattr(mod, "settings", mock_settings)` pattern

**Test coverage (15 tests):**

| Test | Requirement |
|------|-------------|
| test_generate_test_tags_session_numbers | TST-01/TST-02 |
| test_generate_test_caps_at_15_questions | TST-01 |
| test_init_db_creates_cumulative_tests_table | TST-03 |
| test_init_db_idempotent | TST-03 |
| test_generate_endpoint_400_when_sessions_incomplete | TST-04 |
| test_generate_endpoint_400_when_no_sessions | TST-04 |
| test_submit_marks_goal_complete_on_passing_score | TST-05 |
| test_submit_does_not_mark_complete_on_fail | TST-05 |
| test_submit_exactly_70_percent_marks_complete | TST-05 |
| test_submit_returns_weak_session_numbers | TST-06 |
| test_submit_mixed_weak_sessions | TST-06 |
| test_scholar_state_has_v2_annotations | ORC-01 |
| test_update_goal_progress_returns_correct_shape | ORC-02 |
| test_update_goal_progress_identifies_weak_sessions | ORC-02 |
| test_update_goal_progress_nonexistent_goal | ORC-02 |

## Verification

```
cd backend
python -m pytest tests/test_final_test_agent.py -v
# 15 passed in 0.72s

python -m pytest tests/ --ignore=tests/test_api_integration.py -v
# 73 passed, 1 pre-existing failure (test_router_accuracy_gate requires live OpenAI key)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mutable mock object reuse in TST-01 test**
- **Found during:** RED run — `test_generate_test_tags_session_numbers` failed with `assert 2 == 1`
- **Issue:** The initial `mock_test_output` fixture returned a single `TestOutput` instance with 2 `TestQuestion` objects. The `generate_test()` loop mutates `q.session_number` in-place. When both session calls reuse the same object, the second loop (session_number=2) overwrites session_number on all 4 questions before the test assertion runs.
- **Fix:** Replaced shared fixture with a `side_effect` factory that creates fresh `TestQuestion` objects per LLM call. Also added `session_number=99` (deliberately wrong) in the mock to prove the post-LLM enforcement overwrites it correctly.
- **Files modified:** `backend/tests/test_final_test_agent.py`
- **Commit:** 5e43d61

## Commits

| Hash | Message |
|------|---------|
| 5e43d61 | test(11-04): add pytest suite for TST-01–TST-06 and ORC-01/ORC-02 |

## Self-Check: PASSED

- FOUND: backend/tests/test_final_test_agent.py
- FOUND: commit 5e43d61
