---
phase: 11-final-test-agent-orchestrator
plan: 02
subsystem: agents
tags: [pydantic, structured-output, langchain, retrieval, mcq, test-generation]

# Dependency graph
requires:
  - phase: 11-01
    provides: ScholarState V2 with cumulative_tests table
  - phase: 03-retrieval-engine
    provides: hybrid_retriever.retrieve() for per-session context
  - phase: 04-agents-orchestrator
    provides: quiz_agent.py pattern (structured-output MCQ generation)

provides:
  - TestQuestion Pydantic model with session_number field
  - TestOutput structured-output wrapper
  - generate_test() async function with per-session retrieval and cap at 15
  - _test_chain module-level monkeypatchable LLM chain

affects:
  - 11-03-final-test-router (consumes generate_test, TestQuestion.session_number for weak_session_numbers)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Per-session LLM calls with retrieved context to avoid single large prompt
    - Module-level _test_chain for monkeypatching in tests (matching quiz_agent.py pattern)
    - Post-LLM session_number enforcement to guard against incorrect LLM output

key-files:
  created:
    - backend/app/agents/test_agent.py
  modified: []

key-decisions:
  - "Per-session LLM calls (not one batch call) to avoid context limit issues for multi-session tests"
  - "session_number always re-enforced after LLM call — LLM output cannot be trusted for this field"
  - "_test_chain initialized at module level with temperature=0.3 (same pattern as quiz_agent/_adaptive_chain)"
  - "Retrieval failure per session is non-fatal — log warning and skip that session rather than aborting all"

patterns-established:
  - "Per-session retrieval + generation loop with MAX cap guard before each iteration"
  - "Enforce domain-critical fields (session_number) after structured output — never rely on LLM to set them correctly"

requirements-completed: [TST-01, TST-02]

# Metrics
duration: 3min
completed: 2026-03-22
---

# Phase 11 Plan 02: Test Agent Summary

**Async MCQ generator grounding each session's questions in retrieved context via per-session hybrid_retriever calls, with session_number enforced post-LLM for accurate weak_session_numbers computation**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-22T00:05:45Z
- **Completed:** 2026-03-22T00:08:30Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Created `test_agent.py` with `TestQuestion` (including critical `session_number` field), `TestOutput`, and `generate_test()`
- Per-session retrieval strategy: each session topic passed to `hybrid_retriever.retrieve()` with `top_k=3`, keeping prompts small regardless of session count
- Hard cap of `MAX_TEST_QUESTIONS=15` checked before each session iteration; `_test_chain` module-level for monkeypatching

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test_agent.py with TestQuestion, generate_test(), and per-session retrieval** - `275287c` (feat)

**Plan metadata:** (docs commit — pending)

## Files Created/Modified
- `backend/app/agents/test_agent.py` - TestQuestion/TestOutput Pydantic models, _test_chain, generate_test() async orchestrator

## Decisions Made
- Per-session LLM calls chosen over a single batch call (RESEARCH recommendation) to avoid exceeding context limits when many sessions exist
- `q.session_number = session_number` enforced in loop after LLM call — the LLM cannot be trusted to set this field correctly; it must come from the loop variable
- Retrieval failure for a given session is handled as a warning + skip, not a hard abort, since other sessions can still generate valid questions

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `test_agent.py` is complete and importable; all four exports (`TestQuestion`, `TestOutput`, `generate_test`, `_test_chain`) verified
- Ready for Phase 11 Plan 03: final test router that calls `generate_test()`, stores questions, and computes `weak_session_numbers` at submit time

---
*Phase: 11-final-test-agent-orchestrator*
*Completed: 2026-03-22*
