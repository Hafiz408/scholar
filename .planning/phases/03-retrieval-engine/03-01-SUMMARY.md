---
phase: 03-retrieval-engine
plan: "01"
subsystem: api
tags: [langchain, openai, gpt-4o-mini, pydantic, aiosqlite, pytest-asyncio]

# Dependency graph
requires:
  - phase: 02-ingestion-pipeline
    provides: knowledge_sources table with pageindex_doc_id column in SQLite
provides:
  - classify_query async function in backend/app/retrieval/router.py
  - RETR-02 fallback guard (no LLM call when no pageindex_doc_ids exist)
  - RouterDecision Pydantic model with Literal strategy field and descriptive Field examples
  - 10-query LABELLED_TEST_SET with accuracy gate assertion
affects:
  - 03-retrieval-engine (all subsequent plans — router is the critical path gate)
  - 04-chat-agents (cannot begin without >= 8/10 accuracy gate passing)

# Tech tracking
tech-stack:
  added: [pytest.ini with asyncio_mode=auto]
  patterns: [ChatOpenAI.with_structured_output for type-safe LLM output, asyncio.to_thread for sync LangChain calls in async context, aiosqlite SELECT with IN clause placeholder pattern]

key-files:
  created:
    - backend/app/retrieval/router.py
    - backend/tests/test_router.py
    - backend/tests/conftest.py
    - backend/pytest.ini
  modified: []

key-decisions:
  - "asyncio_mode=auto in pytest.ini — required to fix pytest-asyncio 0.23.0 collection bug with __init__.py in tests package"
  - "RouterDecision Field description carries the system prompt examples inline — avoids needing a separate system message in the chain invoke call"
  - "asyncio.to_thread wraps _router_chain.invoke — maintains sync LangChain compatibility inside async FastAPI context"

patterns-established:
  - "RETR-02 guard pattern: always check DB before LLM call, return cheapest strategy on empty result"
  - "with_structured_output(RouterDecision): bind Pydantic model to LLM for type-safe strategy classification"
  - "pytest.mark.integration: marks tests requiring live API keys, separating them from unit tests"

requirements-completed: [RETR-01, RETR-02]

# Metrics
duration: 8min
completed: 2026-03-19
---

# Phase 3 Plan 01: Query Router Agent Summary

**gpt-4o-mini query router with Pydantic structured output classifies pageindex/vector/hybrid strategies, with RETR-02 DB guard short-circuiting to 'vector' before any LLM call when no pageindex docs exist**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-19T00:00:00Z
- **Completed:** 2026-03-19T00:08:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- RouterDecision Pydantic model with Literal["pageindex", "vector", "hybrid"] and inline Field description that acts as the classifier prompt
- classify_query function with RETR-02 DB-first guard: queries SQLite for pageindex_doc_id before making any LLM call; returns "vector" immediately on empty result
- 10-query LABELLED_TEST_SET with per-category coverage (3 pageindex, 3 vector, 2 hybrid, 2 RETR-02 fallback)
- 2 fully-mocked RETR-02 unit tests pass without API key; integration accuracy gate test wired and ready for OPENAI_API_KEY

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement router.py — RETR-02 fallback guard + RETR-01 LLM classifier** - `6cf6d6a` (feat)
2. **Task 2: Implement test_router.py — labelled test set + accuracy gate** - `a0241cc` (feat)

## Files Created/Modified
- `backend/app/retrieval/router.py` - RouterDecision model, _router_chain, _get_pageindex_doc_ids, classify_query
- `backend/tests/test_router.py` - LABELLED_TEST_SET, accuracy gate test, 2 RETR-02 unit tests
- `backend/tests/conftest.py` - integration marker registration (replaces TODO stub)
- `backend/pytest.ini` - asyncio_mode=auto configuration

## Decisions Made
- asyncio_mode=auto in pytest.ini: required to fix pytest-asyncio 0.23.0 crash on __init__.py inside tests package
- RouterDecision Field description carries per-strategy examples inline rather than a separate system message — keeps chain invocation simple and the prompt colocated with the type definition
- asyncio.to_thread wraps _router_chain.invoke to bridge sync LangChain into async FastAPI handlers

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added pytest.ini with asyncio_mode=auto**
- **Found during:** Task 2 (test_router.py verification)
- **Issue:** pytest-asyncio 0.23.0 crashes with `AttributeError: 'Package' object has no attribute 'obj'` when tests directory has an `__init__.py` in STRICT mode; async tests were being skipped without config
- **Fix:** Created `backend/pytest.ini` with `asyncio_mode = auto`, which resolves both the collection crash and the need to mark every async test explicitly
- **Files modified:** backend/pytest.ini
- **Verification:** `python -m pytest tests/test_router.py -k "not integration" -v` — 2 passed
- **Committed in:** a0241cc (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Required for tests to run at all. No scope creep.

## Issues Encountered
- OPENAI_API_KEY not set in .env — integration accuracy gate test (test_router_accuracy_gate) requires a live key and cannot be verified locally. The test structure is correct and the RETR-02 guard path is fully verified via mocks. Set OPENAI_API_KEY in backend/.env to run the accuracy gate.

## User Setup Required

To run the integration accuracy gate:

1. Add your OpenAI API key to `backend/.env`:
   ```
   OPENAI_API_KEY=sk-...
   ```
2. Restart the backend container: `docker compose restart backend`
3. Run: `docker compose exec backend python -m pytest tests/test_router.py -v -m integration -s`
4. Expected: `Router accuracy: 8/10` or higher

## Next Phase Readiness
- router.py fully implemented: exports classify_query ready for use by retrieval orchestrator
- RETR-02 unit tests verified: no LLM call when pageindex_doc_ids is empty
- Integration accuracy gate blocked on OPENAI_API_KEY — set key to clear the Phase 3 hard gate before Phase 4 begins
- All other Phase 3 plans (vector/pageindex/hybrid retrievers) may proceed in parallel — they do not depend on this gate passing

---
*Phase: 03-retrieval-engine*
*Completed: 2026-03-19*
