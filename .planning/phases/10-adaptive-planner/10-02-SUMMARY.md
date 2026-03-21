---
phase: 10-adaptive-planner
plan: 02
subsystem: api
tags: [fastapi, adaptive-planner, quiz, goals, aiosqlite]

# Dependency graph
requires:
  - phase: 10-adaptive-planner plan 01
    provides: handle_quiz_failure, generate_followup_session, insert_followup_session in adaptive_planner.py

provides:
  - "quiz submit endpoint returns enriched dict with followup_session_added and followup_session fields"
  - "POST /goals/{goal_id}/adapt endpoint for manual replanning of all failed sessions"

affects:
  - 10-adaptive-planner plan 03
  - any frontend or integration layer consuming quiz submit or goals adapt

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Planner call placed after db.commit() to guarantee score is persisted before reading (ADP-04)"
    - "Planner exceptions wrapped in try/except at router level — never surface as non-200"
    - "Lazy import of handle_quiz_failure inside try block to isolate dependency errors"

key-files:
  created: []
  modified:
    - backend/app/routers/quiz.py
    - backend/app/routers/goals.py

key-decisions:
  - "Return type of submit_session_quiz changed from QuizResult to dict to allow **followup_result spread"
  - "handle_quiz_failure imported inside try block to prevent import errors from breaking quiz submit"
  - "manual_adapt iterates sessions in session_number ASC order; each call fetches fresh data by UUID so prior insertions in the loop do not corrupt results"

patterns-established:
  - "Adaptive planner integration pattern: call after DB commit, wrap in try/except, merge result into response dict"

requirements-completed: [ADP-03, ADP-04, ADP-05]

# Metrics
duration: 3min
completed: 2026-03-22
---

# Phase 10 Plan 02: Router Wiring for Adaptive Planner Summary

**quiz submit returns followup_session_added/followup_session after post-commit planner call; POST /goals/{goal_id}/adapt triggers bulk replanning for all failed sessions**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-21T19:46:49Z
- **Completed:** 2026-03-21T19:49:50Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Enriched `submit_session_quiz` to call `handle_quiz_failure` after the DB commit and return adaptive planner fields in the response
- Guaranteed ADP-04 ordering: planner reads `quiz_score` from SQLite only after it is committed
- Added `POST /goals/{goal_id}/adapt` endpoint that iterates all failed sessions for a goal and returns aggregate followup counts

## Task Commits

Each task was committed atomically:

1. **Task 1: Enrich quiz submit handler with adaptive planner response** - `0f01660` (feat)
2. **Task 2: Add POST /goals/{goal_id}/adapt endpoint** - `1d19217` (feat)

**Plan metadata:** (this docs commit)

## Files Created/Modified

- `backend/app/routers/quiz.py` - Added logging, changed return type to dict, added post-commit planner call with try/except, enriched return value
- `backend/app/routers/goals.py` - Added logging/aiosqlite/settings imports, added manual_adapt endpoint

## Decisions Made

- Return type of `submit_session_quiz` changed from `QuizResult` to `dict` — necessary to spread `followup_result` fields alongside `QuizResult` fields without creating a new Pydantic model.
- `handle_quiz_failure` imported lazily inside the `try` block — isolates any import-time errors in the adaptive planner module from breaking the quiz submit path.
- `manual_adapt` processes sessions in `session_number ASC` order; `handle_quiz_failure` always fetches fresh data by UUID so prior insertions within the same loop do not affect subsequent calls.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Both router surfaces are wired and verified: quiz submit enrichment (ADP-03/ADP-04) and manual adapt endpoint (ADP-05).
- Plan 03 can proceed to add any remaining adaptive planner requirements (tests, frontend integration, or further enrichment).

---
*Phase: 10-adaptive-planner*
*Completed: 2026-03-22*
