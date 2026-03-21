---
phase: 13-notion-mcp-export
plan: 01
subsystem: database
tags: [notion, pydantic-settings, sqlite, schema-migration, alter-table]

# Dependency graph
requires: []
provides:
  - settings.notion_api_key and settings.notion_parent_page_id in backend/app/config.py
  - study_goals.notion_page_url TEXT column via idempotent ALTER TABLE guard in init_db()
affects:
  - 13-02 (Notion MCP export background task uses settings and column)
  - 13-03 (export router checks settings.notion_api_key falsy)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Empty-string default (falsy) for optional integration credentials in pydantic Settings"
    - "try/except ALTER TABLE guard pattern for idempotent SQLite schema migrations"

key-files:
  created: []
  modified:
    - backend/app/config.py
    - backend/app/db/database.py

key-decisions:
  - "Empty string default for notion_api_key and notion_parent_page_id follows existing vision_model pattern — falsy check means feature is disabled unless both are set"
  - "notion_page_url ALTER TABLE guard placed after quiz_questions guard in init_db(), before conn.close() — same idempotent try/except/pass pattern as prior column additions"

patterns-established:
  - "ALTER TABLE guard: wrap ADD COLUMN in try/except Exception: pass so init_db() is safe to call on existing DB"

requirements-completed: [NTN-02, NTN-04]

# Metrics
duration: 3min
completed: 2026-03-22
---

# Phase 13 Plan 01: Notion Infrastructure (Settings + Schema) Summary

**Two Notion infrastructure primitives added: empty-string credential fields in pydantic Settings and an idempotent ALTER TABLE guard adding notion_page_url TEXT to study_goals.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-21T21:31:00Z
- **Completed:** 2026-03-21T21:34:53Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `notion_api_key` and `notion_parent_page_id` to `Settings` class, both defaulting to `""` (feature disabled when absent)
- Added `notion_page_url TEXT` ALTER TABLE guard to `init_db()` — column created on first call, silently skipped on subsequent calls
- Confirmed `init_db()` idempotency: two consecutive calls produce no error
- All 81 relevant tests pass; pre-existing Docker/API-key-dependent test failures are unrelated

## Task Commits

Each task was committed atomically:

1. **Task 1: Add notion_api_key and notion_parent_page_id to Settings** - `d2e7799` (feat)
2. **Task 2: Add notion_page_url column guard to init_db()** - `75b3f47` (feat)

## Files Created/Modified
- `backend/app/config.py` - Added `notion_api_key: str = ""` and `notion_parent_page_id: str = ""` after `vision_max_pages`
- `backend/app/db/database.py` - Added idempotent ALTER TABLE guard for `study_goals.notion_page_url TEXT`

## Decisions Made
- Empty string defaults follow existing `vision_model: str = ""` pattern — falsy check allows downstream code to gate on `if settings.notion_api_key` with no special handling needed
- notion_page_url guard placed immediately after the existing quiz_questions guard to maintain consistent grouping of migration guards in init_db()

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None - both tasks applied cleanly with no import errors or migration conflicts.

## User Setup Required
None - no external service configuration required at this plan step. Notion credentials (`NOTION_API_KEY`, `NOTION_PARENT_PAGE_ID`) will be documented when the export feature is fully wired (13-02/13-03).

## Next Phase Readiness
- `settings.notion_api_key` and `settings.notion_parent_page_id` ready for use in Phase 13 Plan 02 (export background task)
- `study_goals.notion_page_url` column ready to receive URLs written back by the export worker
- No blockers

---
*Phase: 13-notion-mcp-export*
*Completed: 2026-03-22*
