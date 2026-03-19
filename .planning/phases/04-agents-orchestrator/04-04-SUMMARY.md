---
phase: 04-agents-orchestrator
plan: "04"
subsystem: api
tags: [langchain-openai, pydantic, structured-output, asyncio-to-thread, aiosqlite, fastapi, quiz, mcq]

# Dependency graph
requires:
  - phase: 04-agents-orchestrator
    plan: "01"
    provides: prompts.py with QUIZ_SYSTEM_PROMPT; quiz router stub registered in main.py; study_sessions SQLite table
  - phase: 04-agents-orchestrator
    plan: "02"
    provides: notes_markdown stored in study_sessions after session start
provides:
  - generate_quiz async function using asyncio.to_thread + with_structured_output(QuizOutput)
  - evaluate_quiz pure Python scoring function returning score (0.0-1.0) + per-question explanations
  - QuizQuestion, QuizOutput, PerQuestionResult, QuizResult Pydantic models
  - POST /sessions/{session_id}/quiz/generate — returns QuizQuestionPublic (no correct_index)
  - POST /sessions/{session_id}/quiz/submit — evaluates answers, persists quiz_score, sets status='complete'
  - quiz_questions TEXT column in study_sessions via ALTER TABLE guard in init_db()
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "asyncio.to_thread bridges sync LangChain chain (with_structured_output) into async FastAPI handlers — same pattern as planner.py and note_generator.py"
    - "correct_index security boundary: stored internally in SQLite, never returned in generate response (QuizQuestionPublic), only revealed in submit response (PerQuestionResult)"
    - "evaluate_quiz is pure Python with no LLM call — fast, deterministic, testable"
    - "ALTER TABLE guard in init_db(): try/except pass to safely add quiz_questions column on existing DBs"

key-files:
  created:
    - backend/app/agents/quiz_agent.py
  modified:
    - backend/app/routers/quiz.py
    - backend/app/db/database.py

key-decisions:
  - "QuizQuestionPublic model strips correct_index at the router level — not in quiz_agent — keeping security boundary explicit in the HTTP layer"
  - "quiz_questions column added via ALTER TABLE guard in init_db() — safe for existing databases, no migration tool needed"
  - "Router prefix=/sessions (not /quiz) to match /sessions/{id}/quiz/* path pattern per API design"
  - "evaluate_quiz is synchronous pure Python — no LLM, no asyncio.to_thread needed"

patterns-established:
  - "Security boundary at HTTP layer: internal models have correct_index, public response models do not"
  - "ALTER TABLE guard pattern: try/except pass for idempotent column additions in SQLite"

requirements-completed: [QUIZ-01, QUIZ-02, QUIZ-03, QUIZ-04]

# Metrics
duration: 7min
completed: 2026-03-19
---

# Phase 4 Plan 04: Quiz Agent Summary

**Quiz agent with structured MCQ generation (5 questions, correct_index security boundary) and pure Python evaluation (score + explanations), wired to /sessions/{id}/quiz/generate and /sessions/{id}/quiz/submit endpoints that store correct answers in SQLite and mark sessions complete**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-03-19T09:20:28Z
- **Completed:** 2026-03-19T09:27:30Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- quiz_agent.py: generate_quiz uses asyncio.to_thread + with_structured_output(QuizOutput); evaluate_quiz is pure Python; correct_index in QuizQuestion for internal storage only
- quiz router: /generate stores full questions (with correct_index) in SQLite and returns QuizQuestionPublic (no correct_index); /submit reconstructs questions from SQLite, scores answers, persists quiz_score, sets status='complete'
- quiz_questions TEXT column added to study_sessions via ALTER TABLE guard in init_db() — safe for existing databases

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement quiz_agent.py** - `251b829` (feat)
2. **Task 2: Create quiz router with generate and submit endpoints** - `26f5d8a` (feat)

**Plan metadata:** (docs: committed below)

## Files Created/Modified

- `backend/app/agents/quiz_agent.py` - QuizQuestion/QuizOutput/QuizResult models; generate_quiz async (asyncio.to_thread); evaluate_quiz pure Python scoring
- `backend/app/routers/quiz.py` - POST /sessions/{id}/quiz/generate (QuizQuestionPublic, no correct_index) and POST /sessions/{id}/quiz/submit (QuizResult with score + explanations)
- `backend/app/db/database.py` - ALTER TABLE guard to add quiz_questions TEXT column to study_sessions

## Decisions Made

- `QuizQuestionPublic` model at the HTTP layer strips `correct_index` — the security boundary is explicit in the router, not buried in the agent
- `quiz_questions` column added via `ALTER TABLE` guard (try/except pass) in `init_db()` — idempotent, no migration tooling needed
- Router prefix set to `/sessions` (matching `/sessions/{id}/quiz/*`) per the API design — not `/quiz`
- `evaluate_quiz` is synchronous pure Python — fast, deterministic, no LLM cost for scoring

## Deviations from Plan

None - plan executed exactly as written.

Note: The plan's OpenAPI verification command (`assert 'correct_index' not in str(schemas.get('QuizQuestionPublic', {}))`) produced a false positive because the schema description text contains the word "correct_index". The actual QuizQuestionPublic schema has only `id`, `question`, and `options` fields — verified by inspecting the OpenAPI response directly.

## Issues Encountered

- OpenAPI verification assertion matched on `correct_index` in the schema's description string ("Quiz question without correct_index") — not in the field properties. Verified schema directly; field `correct_index` is not present in `QuizQuestionPublic` properties. Not a real issue.

## User Setup Required

None - no external service configuration required for this plan.

## Next Phase Readiness

- Phase 4 is complete — all four agent routers (goals, sessions, chat, quiz) are fully implemented
- Study session lifecycle is complete: create goal → generate plan → start session (notes) → quiz → complete
- Phase 5 can proceed with full agent API available

---
*Phase: 04-agents-orchestrator*
*Completed: 2026-03-19*

## Self-Check: PASSED

- backend/app/agents/quiz_agent.py: FOUND
- backend/app/routers/quiz.py: FOUND
- backend/app/db/database.py: FOUND
- Commit 251b829: FOUND
- Commit 26f5d8a: FOUND
