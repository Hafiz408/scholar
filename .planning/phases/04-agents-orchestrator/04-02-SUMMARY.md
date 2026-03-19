---
phase: 04-agents-orchestrator
plan: "02"
subsystem: api
tags: [sse-starlette, langchain-openai, aiosqlite, fastapi, streaming, sse]

# Dependency graph
requires:
  - phase: 04-agents-orchestrator
    plan: "01"
    provides: AsyncSqliteSaver lifespan, sessions router stub registered in main.py, prompts.py with NOTE_SYSTEM_PROMPT
  - phase: 03-retrieval-engine
    provides: hybrid_retriever.retrieve() returning RetrievedChunk list with source_title and page_number fields

provides:
  - stream_notes async generator in note_generator.py yielding SSE event strings (notes_chunk, notes_done)
  - POST /sessions/{session_id}/start endpoint returning EventSourceResponse with token-by-token SSE streaming
  - notes_markdown persisted to study_sessions SQLite table after stream completes
affects: [04-03-chat, 04-04-quiz, frontend-session-view]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Async generator as SSE source: stream_notes yields raw SSE-formatted strings consumed by EventSourceResponse"
    - "CancelledError caught inside async generator for clean client disconnect — no re-raise"
    - "JOIN query across study_sessions and study_goals to gather all SSE context in one DB call"
    - "knowledge_source_ids column name used (not source_ids) — confirmed from db/database.py schema"

key-files:
  created:
    - backend/app/agents/note_generator.py
  modified:
    - backend/app/routers/sessions.py

key-decisions:
  - "study_goals JOIN uses knowledge_source_ids column — plan template used 'source_ids' but actual SQLite schema uses 'knowledge_source_ids' (confirmed in db/database.py)"
  - "streaming=True in ChatOpenAI constructor is required alongside .astream() — prevents full-response buffering"
  - "sessions.py does not touch main.py — router already registered by 04-01 Task 3"

patterns-established:
  - "SSE streaming pattern: async generator yields f'event: {event_type}\ndata: {json_payload}\n\n' strings"
  - "Post-stream SQLite persist pattern: collect tokens into list, join, UPDATE after stream exhausted"

requirements-completed: [SESS-01, SESS-02, SESS-03, SESS-04]

# Metrics
duration: 8min
completed: 2026-03-19
---

# Phase 4 Plan 02: Note Generator Agent Summary

**SSE-streaming note generator using ChatOpenAI.astream() with hybrid retrieval context and SQLite persistence via POST /sessions/{session_id}/start**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-19T09:10:00Z
- **Completed:** 2026-03-19T09:18:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- note_generator.py implements stream_notes async generator: retrieves top-8 context chunks, formats with source_title and page_number citations, streams token-by-token via ChatOpenAI.astream() with streaming=True, yields notes_chunk SSE events, persists notes_markdown to SQLite, yields notes_done event
- sessions.py upgraded from stub to full implementation: POST /sessions/{session_id}/start returns EventSourceResponse; 404 for unknown sessions; 409 for sessions not in pending/in_progress status
- JOIN query correctly uses knowledge_source_ids column (actual schema) rather than source_ids (plan template)

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement note_generator.py async SSE streaming agent** - `eb99783` (feat)
2. **Task 2: Create sessions router with POST /sessions/{session_id}/start SSE endpoint** - `8d77e42` (feat)

**Plan metadata:** (docs: committed below)

## Files Created/Modified

- `backend/app/agents/note_generator.py` - stream_notes async generator; _format_context helper with citation formatting
- `backend/app/routers/sessions.py` - POST /sessions/{session_id}/start returning EventSourceResponse; 404/409 guards

## Decisions Made

- Used `knowledge_source_ids` in the JOIN query (not `source_ids`) — confirmed from the actual CREATE TABLE in `db/database.py`. The plan's template query used `source_ids` but that column does not exist in the schema.
- `streaming=True` set in ChatOpenAI constructor alongside `.astream()` call — the plan explicitly requires this to prevent full-response buffering.
- Router does not modify `main.py` — the sessions router was already registered by plan 04-01 Task 3.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected JOIN column from source_ids to knowledge_source_ids**
- **Found during:** Task 2 (sessions router implementation)
- **Issue:** Plan's template SELECT query referenced `sg.source_ids` but the actual `study_goals` CREATE TABLE uses `knowledge_source_ids` — the query would fail at runtime with a SQL error
- **Fix:** Changed `sg.source_ids` to `sg.knowledge_source_ids` in the SELECT and the local variable assignment
- **Files modified:** backend/app/routers/sessions.py
- **Verification:** Confirmed column name in backend/app/db/database.py SQLITE_SCHEMA; matches 04-01-SUMMARY.md decision note
- **Committed in:** 8d77e42 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (column name bug)
**Impact on plan:** Required for the JOIN query to succeed at runtime. No scope creep.

## Issues Encountered

None — both tasks executed cleanly.

## User Setup Required

None - no external service configuration required for this plan. OPENAI_API_KEY must be set in .env for actual streaming to work (same requirement as 04-01).

## Next Phase Readiness

- POST /sessions/{session_id}/start is ready for end-to-end test once OpenAI API key is configured
- Plans 04-03 (chat) and 04-04 (quiz) can now implement their SSE endpoints using the same streaming pattern established here
- notes_markdown is persisted to SQLite and available for 04-04 quiz generation

---
*Phase: 04-agents-orchestrator*
*Completed: 2026-03-19*

## Self-Check: PASSED

- backend/app/agents/note_generator.py: FOUND
- backend/app/routers/sessions.py: FOUND
- Commit eb99783: FOUND
- Commit 8d77e42: FOUND
