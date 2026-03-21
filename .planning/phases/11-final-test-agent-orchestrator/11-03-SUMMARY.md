---
phase: 11-final-test-agent-orchestrator
plan: 03
subsystem: api

tags: [fastapi, aiosqlite, cumulative_tests, test-router, mcq, scoring]

requires:
  - phase: 11-02
    provides: generate_test(), TestQuestion, TestOutput from test_agent.py
  - phase: 10-adaptive-planner
    provides: evaluate_quiz(), QuizQuestion from quiz_agent.py (reused for scoring)
  - phase: 11-01
    provides: cumulative_tests table in SQLITE_SCHEMA

provides:
  - POST /goals/{goal_id}/test/generate endpoint with 3-guard precondition checking
  - POST /goals/{goal_id}/test/submit endpoint with scoring, goal completion marking, and weak_session_numbers
  - test router registered in FastAPI app

affects:
  - frontend (consumes /goals/{id}/test/generate and /goals/{id}/test/submit)
  - phase 12+ (goal status='complete' set by submit endpoint)

tech-stack:
  added: []
  patterns:
    - "Public DTO pattern: TestQuestionPublic strips correct_index before sending to frontend"
    - "Server-side session tagging: _compute_weak_sessions uses stored question data not client data"
    - "Router prefix sharing: /goals prefix shared by goals_router and test_router — FastAPI merges by distinct path patterns"

key-files:
  created:
    - backend/app/routers/test.py
  modified:
    - backend/app/main.py

key-decisions:
  - "FINAL_TEST_PASS_THRESHOLD=0.70 (distinct from adaptive planner's 0.65 quiz pass threshold)"
  - "WEAK_SESSION_THRESHOLD=0.50 (per TST-06 spec — different from both pass thresholds)"
  - "TestQuestion cast to QuizQuestion for evaluate_quiz() reuse — avoids duplicating evaluation logic"
  - "Most recent cumulative_tests row loaded by ORDER BY created_at DESC LIMIT 1 — allows test retakes"
  - "_compute_weak_sessions reads session_number from stored server-side question data, not submitted answers — prevents client manipulation"

patterns-established:
  - "Guard ordering: existence (404) → has-sessions (400) → all-complete (400) — most specific guard last"
  - "Two-connection pattern: read guards in one aiosqlite connection, write results in separate connection"

requirements-completed: [TST-04, TST-05, TST-06]

duration: 3min
completed: 2026-03-22
---

# Phase 11 Plan 03: Test Router Summary

**FastAPI test router with guarded generate + scored submit endpoints — stores full questions to cumulative_tests, marks goal complete at 70%, and returns weak_session_numbers per TST-04/TST-05/TST-06**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-21T20:31:16Z
- **Completed:** 2026-03-21T20:34:30Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created `backend/app/routers/test.py` with generate and submit endpoints, all three precondition guards, and threshold constants
- Registered test router in `backend/app/main.py` alongside existing routers
- All 8 existing adaptive planner tests still pass (no regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create routers/test.py with generate and submit endpoints** - `36b4fa5` (feat)
2. **Task 2: Register test router in main.py** - `1e369a5` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `backend/app/routers/test.py` — Test router with generate/submit endpoints, TestQuestionPublic, TestSubmitRequest, _compute_weak_sessions helper
- `backend/app/main.py` — Added test_router import and app.include_router(test_router)

## Decisions Made
- FINAL_TEST_PASS_THRESHOLD=0.70 and WEAK_SESSION_THRESHOLD=0.50 named as separate constants to prevent threshold confusion (three different thresholds exist in the codebase)
- `TestQuestion` cast to `QuizQuestion` at submit time to reuse `evaluate_quiz()` — avoids duplicating pure-Python scoring logic
- `_compute_weak_sessions` uses `questions: list[TestQuestion]` from stored DB data (not submitted answers) so session_number cannot be client-manipulated

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 11 complete: ScholarState V2, test_agent.py, and test router all implemented
- Phase 12+ can rely on `goal.status='complete'` being set by POST /goals/{id}/test/submit when score >= 70%
- Frontend needs to call /generate before /submit, and handle the goal_complete boolean in submit response

---
*Phase: 11-final-test-agent-orchestrator*
*Completed: 2026-03-22*
