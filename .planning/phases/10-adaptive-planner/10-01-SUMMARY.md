---
phase: 10-adaptive-planner
plan: 01
subsystem: agents
tags: [adaptive-planner, aiosqlite, sqlite, langchain, structured-output, llm]

# Dependency graph
requires:
  - phase: 04-agents-orchestrator
    provides: planner.py SessionPlan model and asyncio.to_thread LLM invoke pattern
  - phase: 01-infrastructure
    provides: SQLite study_sessions and knowledge_sources schema
provides:
  - adaptive_planner.py with handle_quiz_failure(), generate_followup_session(), insert_followup_session()
  - ADAPTIVE_PLANNER_SYSTEM_PROMPT in prompts.py
  - PASS_THRESHOLD = 0.65 constant
affects:
  - 10-adaptive-planner plan 02 (quiz.py integration)
  - 10-adaptive-planner plan 03 (goals.py /adapt endpoint)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Sentinel session_number=0 from LLM; insertion function overrides with computed value to avoid LLM arithmetic errors"
    - "Two-step atomic SQLite pattern: UPDATE session_number > N first, then INSERT, single db.commit()"
    - "Private _fetch_source_titles() opens own connection; insert_followup_session() accepts caller-owned connection for transaction control"

key-files:
  created:
    - backend/app/agents/adaptive_planner.py
  modified:
    - backend/app/agents/prompts.py

key-decisions:
  - "PASS_THRESHOLD strict less-than: score < 0.65 triggers follow-up; score == 0.65 does NOT (per requirements ADP-01)"
  - "insert_followup_session() accepts open db connection — caller opens and commits — keeps UPDATE+INSERT in one atomic transaction"
  - "handle_quiz_failure() always fetches fresh session_number from DB by UUID; never accepts session_number as parameter to avoid stale data in multi-session adapt scenarios"
  - "No new packages added — all dependencies (aiosqlite, langchain, pydantic) already in requirements.txt"

patterns-established:
  - "Pattern: adaptive LLM chain mirrors planner.py — get_llm(temperature=0).with_structured_output(SessionPlan) at module level"
  - "Pattern: session renumber uses UPDATE ... WHERE session_number > ? (strictly greater than, not >=) to preserve the completed session's number"

requirements-completed: [ADP-01, ADP-02, ADP-04]

# Metrics
duration: 2min
completed: 2026-03-22
---

# Phase 10 Plan 01: Adaptive Planner Core Summary

**LLM-driven adaptive_planner.py that generates and atomically inserts a follow-up study session when quiz score < 65%, using SessionPlan structured output and a two-step SQLite UPDATE+INSERT transaction**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-22T08:39:52Z
- **Completed:** 2026-03-22T08:41:52Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created adaptive_planner.py with three public functions (handle_quiz_failure, generate_followup_session, insert_followup_session) and PASS_THRESHOLD constant
- Added ADAPTIVE_PLANNER_SYSTEM_PROMPT to prompts.py with sentinel session_number=0 pattern
- Atomic SQLite renumber+insert: UPDATE strictly-greater-than downstream sessions, INSERT follow-up, single db.commit()

## Task Commits

Each task was committed atomically:

1. **Task 1: Add ADAPTIVE_PLANNER_SYSTEM_PROMPT to prompts.py** - `4d5b9ad` (feat)
2. **Task 2: Create adaptive_planner.py with full handle_quiz_failure logic** - `38cbad0` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `backend/app/agents/adaptive_planner.py` - Core adaptive planner module with LLM session generation and atomic DB insertion
- `backend/app/agents/prompts.py` - Added ADAPTIVE_PLANNER_SYSTEM_PROMPT (remediation session designer prompt)

## Decisions Made

- PASS_THRESHOLD strict less-than (< 0.65): score exactly at 0.65 does not trigger follow-up, per ADP-01 requirements
- insert_followup_session() accepts caller-owned open aiosqlite connection — caller commits — ensures UPDATE+INSERT land in one transaction (Pitfall 2 avoidance)
- handle_quiz_failure() fetches session_number fresh from DB using UUID on every call — never passed as a parameter — avoids stale data in cascading adapt scenarios (Pitfall 4 avoidance)
- LLM outputs session_number=0 sentinel; insertion function assigns computed value — avoids LLM arithmetic errors (Pitfall 5 avoidance)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. All three verification checks passed on first run:
- Import check: all public symbols importable without error
- Assertion: 'Follow-up' present in ADAPTIVE_PLANNER_SYSTEM_PROMPT
- Syntax: ast.parse confirms no syntax errors in adaptive_planner.py

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- adaptive_planner.py is importable and ready for integration into quiz.py submit handler (ADP-03, ADP-04)
- handle_quiz_failure(session_id) interface is stable — quiz router calls this with a UUID string
- insert_followup_session() and generate_followup_session() are separately callable for testing
- No new packages needed for next plans in this phase

## Self-Check: PASSED

- FOUND: backend/app/agents/adaptive_planner.py
- FOUND: backend/app/agents/prompts.py
- FOUND: .planning/phases/10-adaptive-planner/10-01-SUMMARY.md
- FOUND: commit 4d5b9ad (feat: add ADAPTIVE_PLANNER_SYSTEM_PROMPT)
- FOUND: commit 38cbad0 (feat: create adaptive_planner.py)

---
*Phase: 10-adaptive-planner*
*Completed: 2026-03-22*
