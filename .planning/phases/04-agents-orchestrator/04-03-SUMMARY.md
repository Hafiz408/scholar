---
phase: 04-agents-orchestrator
plan: "03"
subsystem: api
tags: [langgraph, asyncsqlitesaver, sse-starlette, langchain-openai, fastapi, sqlite, sse]

# Dependency graph
requires:
  - phase: 04-agents-orchestrator
    plan: "01"
    provides: AsyncSqliteSaver wired as app.state.checkpointer, CHAT_SYSTEM_PROMPT in prompts.py, chat router stub in main.py
  - phase: 03-retrieval-engine
    provides: hybrid retrieve() function returning RetrievalResult with chunks/strategy_used/latency_ms
provides:
  - stream_chat async generator yielding SSE token/citations/done events grounded in retrieved context
  - POST /sessions/{session_id}/chat endpoint returning EventSourceResponse
  - LangGraph AsyncSqliteSaver chat history persistence per goal_id thread
affects: [04-04-quiz, frontend-chat-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "stream_chat loads history via checkpointer.aget_tuple(config) where config thread_id = goal_id"
    - "Checkpoint saved via checkpointer.aput after streaming completes — history survives refresh"
    - "SSE event sequence: token* → citations → done"
    - "Defensive import fallback for Checkpoint/CheckpointMetadata across langgraph versions"

key-files:
  created:
    - backend/app/agents/session_chat.py
  modified:
    - backend/app/routers/chat.py

key-decisions:
  - "chat.py SQL query uses sg.knowledge_source_ids (not sg.source_ids) per actual SQLite schema"
  - "chat router uses prefix=/sessions so endpoint is /sessions/{session_id}/chat — coexists with sessions router which also uses prefix=/sessions"
  - "Defensive import fallback for Checkpoint/CheckpointMetadata: base -> types -> plain dict"

patterns-established:
  - "SSE agent pattern: retrieve -> load history -> astream -> save history -> citations -> done"
  - "goal_id used as LangGraph thread_id for per-goal chat history isolation"

requirements-completed: [CHAT-01, CHAT-02, CHAT-03, CHAT-04]

# Metrics
duration: 2min
completed: 2026-03-19
---

# Phase 4 Plan 03: Session Chat Agent Summary

**SSE-streaming chat agent with context-only grounding, citation events, and LangGraph AsyncSqliteSaver history persistence per goal thread**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-19T09:16:24Z
- **Completed:** 2026-03-19T09:18:01Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- session_chat.py implements stream_chat async generator: retrieves context, loads history from AsyncSqliteSaver, streams via ChatOpenAI.astream(), saves updated history, yields citations then done SSE events
- CHAT_SYSTEM_PROMPT grounding enforced — answers only from context, never training data
- POST /sessions/{session_id}/chat router returns EventSourceResponse, passes app.state.checkpointer, returns 404 for unknown sessions

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement session_chat.py — streaming chat with AsyncSqliteSaver history** - `7d39541` (feat)
2. **Task 2: Create chat router with POST /sessions/{session_id}/chat endpoint** - `9acda1f` (feat)

**Plan metadata:** (docs: committed below)

## Files Created/Modified

- `backend/app/agents/session_chat.py` - stream_chat async generator: retrieve -> history load -> astream -> history save -> citations -> done
- `backend/app/routers/chat.py` - POST /sessions/{session_id}/chat returning EventSourceResponse with checkpointer

## Decisions Made

- The chat router uses `prefix="/sessions"` so the endpoint resolves to `/sessions/{session_id}/chat`, coexisting with the sessions router (also `prefix="/sessions"`) which handles `/{session_id}/start`
- `goal_id` is used as the LangGraph `thread_id` so chat history is scoped per goal (not per session), allowing multi-session continuity within a study goal
- Defensive import chain for `Checkpoint`/`CheckpointMetadata`: tries `langgraph.checkpoint.base`, then `langgraph.checkpoint.types`, then falls back to plain `dict` — handles version differences without breaking

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed wrong column name in SQL JOIN query**
- **Found during:** Task 2 (chat router implementation)
- **Issue:** Plan template used `sg.source_ids` in the SQL query, but actual SQLite schema column is `sg.knowledge_source_ids` (same issue previously documented in STATE.md from 04-02)
- **Fix:** Used `sg.knowledge_source_ids` in the SELECT and JSON decode
- **Files modified:** backend/app/routers/chat.py
- **Verification:** 404 response confirmed for unknown session; query compiles without error
- **Committed in:** 9acda1f (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (plan template column name mismatch)
**Impact on plan:** Required fix for correct SQLite query. No scope creep.

## Issues Encountered

None — both tasks completed cleanly. All three verification checks passed.

## User Setup Required

None - no external service configuration required for this plan. OPENAI_API_KEY must be set in .env to exercise streaming (pre-existing requirement from Phase 4 agents).

## Next Phase Readiness

- stream_chat and POST /sessions/{session_id}/chat are complete and ready for frontend SSE consumption
- Plan 04-04 (quiz agent) can now be implemented — same pattern as chat/notes agents
- Chat history persistence confirmed: history loads from checkpointer on each message, updated checkpoint saved after response

---
*Phase: 04-agents-orchestrator*
*Completed: 2026-03-19*

## Self-Check: PASSED

- backend/app/agents/session_chat.py: FOUND
- backend/app/routers/chat.py: FOUND
- Commit 7d39541: FOUND
- Commit 9acda1f: FOUND
