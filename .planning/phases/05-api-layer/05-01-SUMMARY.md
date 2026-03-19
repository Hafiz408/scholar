---
phase: 05-api-layer
plan: "01"
subsystem: testing
tags: [pytest, fastapi, testclient, sqlite, aiosqlite, mocking, integration-tests]

# Dependency graph
requires:
  - phase: 04-agents-orchestrator
    provides: quiz router with generate/submit endpoints; orchestrator create_goal_with_plan; study_sessions.quiz_questions TEXT column
provides:
  - quiz_questions normalized table DDL in SQLITE_SCHEMA (created by init_db on startup)
  - pytest integration tests covering full API surface (goals, sessions, quiz, health)
affects: [06-frontend, any phase adding new API endpoints]

# Tech tracking
tech-stack:
  added: []
  patterns: [FastAPI TestClient for sync integration tests, unittest.mock.patch AsyncMock for LLM mocking, pythonpath=. in pytest.ini for import resolution without __init__.py]

key-files:
  created:
    - backend/tests/test_api_integration.py
  modified:
    - backend/app/db/database.py
    - backend/pytest.ini

key-decisions:
  - "pythonpath = . added to pytest.ini — pytest-asyncio 0.23.0 crashes with __init__.py + asyncio_mode=auto (Package collector bug); pythonpath solves import without making tests/ a package"
  - "quiz_questions normalized table is additive — existing study_sessions.quiz_questions TEXT column and ALTER TABLE guard retained for live DB compatibility; quiz.py storage behavior unchanged"
  - "GET /goals/{goal_id} response shape is {goal: {...}, sessions: [...]} — test asserts data['goal']['id'] not data['goal_id'] to match actual orchestrator return shape"

patterns-established:
  - "Integration tests: insert test fixtures directly via aiosqlite asyncio.run() in test body — no shared test DB teardown needed (unique UUIDs per test)"
  - "LLM mocking: patch app.agents.orchestrator.generate_plan with AsyncMock; patch app.agents.quiz_agent._quiz_chain with MagicMock"
  - "TestClient scope=module — single lifespan for all tests in file"

requirements-completed: [API-INT-01]

# Metrics
duration: 12min
completed: 2026-03-19
---

# Phase 5 Plan 01: API Layer Integration Tests Summary

**quiz_questions table added to SQLITE_SCHEMA and 10 pytest integration tests covering full goal/session/quiz/health API surface with mocked LLM calls, all passing in Docker container**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-19T09:30:00Z
- **Completed:** 2026-03-19T09:42:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added `quiz_questions` normalized table DDL to `SQLITE_SCHEMA` in `database.py` — replaces ALTER TABLE-only approach; table confirmed present after backend restart
- Created `backend/tests/test_api_integration.py` with 10 tests: POST /goals (201 + 422 validation), GET /goals/{id} (200 with sessions list + 404), POST /sessions/{id}/start (404), POST /sessions/{id}/quiz/generate (404 + 422 no-notes), POST /sessions/{id}/quiz/submit (score=1.0 + session status=complete + 404), GET /health (200)
- All 10 tests pass in Docker container with no real OpenAI API calls made

## Task Commits

Each task was committed atomically:

1. **Task 1: Add quiz_questions table to SQLITE_SCHEMA** - `7c24005` (feat)
2. **Task 2: Write pytest integration tests** - `9379d31` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `backend/app/db/database.py` - Added quiz_questions CREATE TABLE IF NOT EXISTS DDL to SQLITE_SCHEMA
- `backend/tests/test_api_integration.py` - 10 integration tests for full API surface with mocked LLM
- `backend/pytest.ini` - Added `pythonpath = .` for test import resolution

## Decisions Made
- `pythonpath = .` added to `pytest.ini` to resolve `ModuleNotFoundError: No module named 'app'` without needing `__init__.py` (which triggers pytest-asyncio 0.23.0 Package collector bug under asyncio_mode=auto)
- `quiz_questions` table is additive — the `study_sessions.quiz_questions TEXT` column and its ALTER TABLE guard are retained for backward compatibility; quiz.py continues using the TEXT column for storage
- Test fixture for `test_quiz_generate_returns_422_when_notes_absent` uses `knowledge_source_ids` column name (matches actual SQLite schema) not `source_ids` as the plan template suggested

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added pythonpath = . to pytest.ini**
- **Found during:** Task 2 (integration test file creation)
- **Issue:** Without `__init__.py` in `tests/`, pytest cannot resolve `from app.main import app`; with `__init__.py`, pytest-asyncio 0.23.0 crashes (`AttributeError: 'Package' object has no attribute 'obj'` in asyncio_mode=auto)
- **Fix:** Added `pythonpath = .` to `pytest.ini` — allows pytest to add `/app` to sys.path so `app.*` imports resolve without making `tests/` a package
- **Files modified:** `backend/pytest.ini`
- **Verification:** All 10 tests pass in Docker container
- **Committed in:** `9379d31` (Task 2 commit)

**2. [Rule 1 - Bug] Adjusted GET /goals response shape assertion**
- **Found during:** Task 2 (writing test_get_goal_returns_plan)
- **Issue:** Plan template asserts `data["goal_id"]` but `get_goal_plan()` returns `{"goal": {...}, "sessions": [...]}` — `goal_id` is nested at `data["goal"]["id"]`
- **Fix:** Test asserts `data["goal"]["id"] == goal_id` and `len(data["sessions"]) >= 1` to match actual API contract
- **Files modified:** `backend/tests/test_api_integration.py`
- **Verification:** Test passes with correct assertion
- **Committed in:** `9379d31` (Task 2 commit)

**3. [Rule 1 - Bug] Used knowledge_source_ids column in test fixture inserts**
- **Found during:** Task 2 (test_quiz_generate_returns_422_when_notes_absent fixture setup)
- **Issue:** Plan template used `source_ids` column name in INSERT but actual `study_goals` schema uses `knowledge_source_ids`
- **Fix:** Used correct column name `knowledge_source_ids` in all test fixture INSERT statements
- **Files modified:** `backend/tests/test_api_integration.py`
- **Verification:** Tests pass without SQLite constraint errors
- **Committed in:** `9379d31` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (1 blocking, 2 bugs)
**Impact on plan:** All auto-fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond deviations documented above.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- `quiz_questions` normalized table DDL available for future migration from denormalized TEXT storage
- Integration test suite provides regression coverage for all major API endpoints
- Phase 5 plan 01 complete; ready for remaining Phase 5 plans

---
*Phase: 05-api-layer*
*Completed: 2026-03-19*
