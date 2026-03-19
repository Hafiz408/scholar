---
phase: 04-agents-orchestrator
plan: "01"
subsystem: api
tags: [langgraph, langgraph-checkpoint-sqlite, sse-starlette, fastapi, sqlite, langchain-openai, asyncsqlitesaver]

# Dependency graph
requires:
  - phase: 03-retrieval-engine
    provides: hybrid retriever and knowledge_sources table in SQLite
  - phase: 02-ingestion-pipeline
    provides: knowledge_sources + knowledge_chunks tables, asyncio.to_thread pattern
provides:
  - AsyncSqliteSaver wired into FastAPI lifespan as app.state.checkpointer
  - LangGraph compiled graph stored as app.state.graph
  - prompts.py with all four agent system prompts centralized
  - generate_plan function with ceil(deadline_days/7*sessions_per_week) session count
  - create_goal_with_plan and get_goal_plan orchestrator functions
  - POST /goals (201) and GET /goals/{goal_id} (200/404) HTTP endpoints
  - All four agent routers (goals, sessions, chat, quiz) registered in main.py
affects: [04-02-sessions, 04-03-chat, 04-04-quiz]

# Tech tracking
tech-stack:
  added: [langgraph-checkpoint-sqlite, sse-starlette]
  patterns:
    - "asyncio.to_thread bridges sync LangChain chain (with_structured_output) into async FastAPI handlers"
    - "AsyncSqliteSaver initialized inside async with block in lifespan, never at module level"
    - "Agent system prompts centralized in prompts.py — all four agents import from one location"
    - "Minimal passthrough LangGraph node — graph exists solely for AsyncSqliteSaver checkpointing"

key-files:
  created:
    - backend/app/agents/prompts.py
    - backend/app/agents/planner.py
    - backend/app/agents/orchestrator.py
    - backend/app/routers/goals.py
  modified:
    - backend/requirements.txt
    - backend/app/main.py
    - backend/app/routers/sessions.py
    - backend/app/routers/chat.py
    - backend/app/routers/quiz.py

key-decisions:
  - "AsyncSqliteSaver imported inside lifespan function (not module-level) to avoid circular import risk"
  - "study_goals table uses knowledge_source_ids column (not source_ids) — matched existing SQLite schema"
  - "Stub routers (sessions/chat/quiz) given minimal router objects so all four can be registered in main.py now — plans 04-02/03/04 will fill in endpoints"
  - "build_graph uses minimal passthrough node — checkpointer is the purpose, not graph routing"

patterns-established:
  - "Lifespan pattern: init_db + init_pgvector_schema → AsyncSqliteSaver context → build_graph → yield"
  - "All agent prompts imported from app.agents.prompts — no inline prompt strings in agent files"

requirements-completed: [GOAL-01, GOAL-02, GOAL-03, GOAL-04, OBS-01]

# Metrics
duration: 15min
completed: 2026-03-19
---

# Phase 4 Plan 01: Agents Orchestrator Foundation Summary

**LangGraph AsyncSqliteSaver wired into FastAPI lifespan, Planner agent with structured output, goal CRUD over POST /goals + GET /goals/{goal_id}, and all four agent routers registered in main.py**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-19T08:53:00Z
- **Completed:** 2026-03-19T09:08:46Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- langgraph-checkpoint-sqlite and sse-starlette installed, Docker image rebuilt successfully
- AsyncSqliteSaver initialized in lifespan, stored as app.state.checkpointer; compiled LangGraph graph as app.state.graph
- prompts.py centralizes all four agent system prompts; planner.py generates plans via structured output with correct session count formula; orchestrator.py persists goals + sessions to SQLite
- POST /goals and GET /goals/{goal_id} exposed with proper 201/404 responses; all four agent routers registered in main.py

## Task Commits

Each task was committed atomically:

1. **Task 1: Install dependencies and wire AsyncSqliteSaver into FastAPI lifespan** - `24ebf73` (feat)
2. **Task 2: Create prompts.py and implement planner agent with goal CRUD** - `a92e0dd` (feat)
3. **Task 3: Create goals HTTP router and register all four agent routers in main.py** - `eaa83e7` (feat)

**Plan metadata:** (docs: committed below)

## Files Created/Modified

- `backend/requirements.txt` - Added langgraph-checkpoint-sqlite and sse-starlette
- `backend/app/main.py` - AsyncSqliteSaver lifespan + all four router registrations
- `backend/app/agents/prompts.py` - PLANNER, NOTE, CHAT, QUIZ system prompts
- `backend/app/agents/planner.py` - generate_plan using ceil(deadline_days/7*sessions_per_week) with asyncio.to_thread
- `backend/app/agents/orchestrator.py` - build_graph, create_goal_with_plan, get_goal_plan
- `backend/app/routers/goals.py` - POST /goals (201), GET /goals/{goal_id} (200/404)
- `backend/app/routers/sessions.py` - Minimal router stub (populated in 04-02)
- `backend/app/routers/chat.py` - Minimal router stub (populated in 04-03)
- `backend/app/routers/quiz.py` - Minimal router stub (populated in 04-04)

## Decisions Made

- `AsyncSqliteSaver` imported inside lifespan function body, not at module level, to avoid potential circular imports at startup
- The `study_goals` table uses `knowledge_source_ids` column per existing SQLite schema in `db/database.py` — orchestrator updated accordingly
- Sessions/chat/quiz router stubs given minimal `router = APIRouter(...)` objects so main.py can import and register all four routers now, avoiding concurrent write conflicts in later plans
- `build_graph` uses a minimal passthrough node — the graph's purpose is to hold the AsyncSqliteSaver checkpointer, not to route agent logic

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added minimal router objects to stub files**
- **Found during:** Task 1 (wiring routers in main.py)
- **Issue:** sessions.py, chat.py, quiz.py were stubs with only a comment; importing `router` from them would fail at startup, breaking the backend
- **Fix:** Added `router = APIRouter(prefix=..., tags=[...])` to each stub file so all four routers are importable
- **Files modified:** backend/app/routers/sessions.py, chat.py, quiz.py
- **Verification:** Backend starts without import errors; health endpoint returns 200
- **Committed in:** 24ebf73 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (missing critical — stub routers)
**Impact on plan:** Necessary for backend to start with all four routers registered. Plans 04-02/03/04 will replace stubs with full implementations.

## Issues Encountered

- Frontend container port conflict (3000 already allocated) on `docker compose up -d` — pre-existing issue unrelated to this plan; backend started cleanly.

## User Setup Required

None - no external service configuration required for this plan. LANGCHAIN_TRACING_V2 is present in the container environment (currently set to false; set to true + add LANGSMITH_API_KEY in .env to enable LangSmith tracing).

## Next Phase Readiness

- Plans 04-02, 04-03, 04-04 can now implement sessions/chat/quiz endpoints — stubs with router objects are in place, main.py registrations already committed
- app.state.checkpointer and app.state.graph available to all route handlers via `request.app.state`
- goals endpoints ready for end-to-end test once an OpenAI API key is configured

---
*Phase: 04-agents-orchestrator*
*Completed: 2026-03-19*

## Self-Check: PASSED

- backend/app/agents/prompts.py: FOUND
- backend/app/agents/planner.py: FOUND
- backend/app/agents/orchestrator.py: FOUND
- backend/app/routers/goals.py: FOUND
- Commit 24ebf73: FOUND
- Commit a92e0dd: FOUND
- Commit eaa83e7: FOUND
