---
phase: 13-notion-mcp-export
plan: 02
subsystem: api
tags: [notion, httpx, aiosqlite, background-tasks, exponential-backoff, fastapi]

# Dependency graph
requires:
  - phase: 13-01
    provides: settings.notion_api_key, settings.notion_parent_page_id, study_goals.notion_page_url column
provides:
  - backend/app/agents/notion_mcp.py: async Notion export agent with _post_with_backoff and run_notion_export
  - POST /goals/{goal_id}/export/notion: non-blocking endpoint using FastAPI BackgroundTasks
affects:
  - 13-03 (frontend or test coverage for the export endpoint)

# Tech tracking
tech-stack:
  added:
    - httpx (async HTTP client for Notion API calls)
  patterns:
    - "BackgroundTasks pattern: endpoint returns immediately, export runs async in background"
    - "Own-connection pattern: run_notion_export opens its own aiosqlite connections (not accepting one from caller)"
    - "Backoff loop: for attempt in range(MAX_RETRIES) with asyncio.sleep(2 ** attempt) on 429"
    - "Guard-before-task: settings validation runs before background_tasks.add_task() so 400 is synchronous"

key-files:
  created:
    - backend/app/agents/notion_mcp.py
  modified:
    - backend/app/routers/goals.py

key-decisions:
  - "run_notion_export opens its own aiosqlite connection — avoids lifetime mismatch between request-scoped and background-task-scoped resources"
  - "Sequential session child page creation (loop, not gather) — goal_page_id from step 1 is required as parent before step 2 begins"
  - "Backoff formula asyncio.sleep(2 ** attempt) gives 1s/2s/4s for attempts 0/1/2 — final attempt after loop exhaustion surfaces error via raise_for_status"
  - "try/except Exception wraps entire export body so background failures are logged, not silently swallowed"

patterns-established:
  - "BackgroundTasks export pattern: validate config synchronously → add_task() → return immediately"
  - "Notion backoff wrapper: _post_with_backoff isolates retry logic so export orchestration stays readable"

requirements-completed: [NTN-01, NTN-03, NTN-05]

# Metrics
duration: 3min
completed: 2026-03-22
---

# Phase 13 Plan 02: Notion Export Agent Summary

**httpx-based Notion export agent with 3-retry exponential backoff wired into POST /goals/{id}/export/notion via FastAPI BackgroundTasks — returns {status: export_started} immediately and writes notion_page_url back to SQLite on completion.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-21T21:39:03Z
- **Completed:** 2026-03-21T21:42:05Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created `notion_mcp.py` with `_post_with_backoff` (exponential backoff on HTTP 429) and `run_notion_export` (full goal+sessions export orchestration)
- Added `POST /goals/{goal_id}/export/notion` endpoint — validates config synchronously, schedules background task, returns immediately
- Sequential session child page creation — goal page ID obtained in Step 1 before any Step 2 calls begin
- `notion_page_url` written back to `study_goals` row after export succeeds; failures logged via `logger.error`, not swallowed

## Task Commits

Each task was committed atomically:

1. **Task 1: Create notion_mcp.py Notion export agent** - `e8d68bd` (feat)
2. **Task 2: Add POST /goals/{id}/export/notion endpoint** - `0d1cc3e` (feat)

## Files Created/Modified
- `backend/app/agents/notion_mcp.py` - Notion API wrapper with `_make_headers`, `_post_with_backoff`, `run_notion_export`
- `backend/app/routers/goals.py` - Added `BackgroundTasks` import, `run_notion_export` import, and `export_to_notion` endpoint

## Decisions Made
- `run_notion_export` opens its own `aiosqlite` connection — prevents lifetime mismatch between request lifecycle and background task lifecycle
- Sequential session child page creation (not concurrent) — goal page ID from step 1 is the required parent for all session child pages in step 2
- Backoff uses `asyncio.sleep(2 ** attempt)`: attempt 0 = 1s, attempt 1 = 2s, attempt 2 = 4s; final attempt after loop exhaustion calls `raise_for_status()` to surface persistent rate-limit failures
- Guard checks (`if not settings.notion_api_key`) placed before `background_tasks.add_task()` to ensure HTTP 400 is returned synchronously — never swallowed by background worker

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None - both tasks applied cleanly with no import errors or test regressions.

## User Setup Required
To use the Notion export feature, set these environment variables before starting the backend:
```
NOTION_API_KEY=secret_...          # Notion integration token
NOTION_PARENT_PAGE_ID=...          # Notion page ID to create goal pages under
```
Both must be set; if either is empty the endpoint returns HTTP 400.

## Next Phase Readiness
- `POST /goals/{goal_id}/export/notion` is live and returns `{status: export_started}` when both keys are configured
- `run_notion_export` + `_post_with_backoff` importable and tested
- `notion_page_url` written to DB after successful export, ready for frontend display in Plan 03

## Self-Check: PASSED

- FOUND: backend/app/agents/notion_mcp.py
- FOUND: backend/app/routers/goals.py
- FOUND: .planning/phases/13-notion-mcp-export/13-02-SUMMARY.md
- FOUND: commit e8d68bd (Task 1)
- FOUND: commit 0d1cc3e (Task 2)

---
*Phase: 13-notion-mcp-export*
*Completed: 2026-03-22*
