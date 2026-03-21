---
phase: 13-notion-mcp-export
plan: 03
subsystem: tests
tags: [notion, pytest, asyncio, httpx, aiosqlite, tdd, mocking]

# Dependency graph
requires:
  - phase: 13-02
    provides: run_notion_export, _post_with_backoff, POST /goals/{id}/export/notion
  - phase: 13-01
    provides: settings.notion_api_key, settings.notion_parent_page_id, notion_page_url column
provides:
  - backend/tests/test_notion_mcp.py: 10-test pytest suite covering NTN-01 through NTN-05
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "AsyncClient mock: patch httpx.AsyncClient with __aenter__/__aexit__ AsyncMock stubs"
    - "Backoff test: mock asyncio.sleep via monkeypatch to capture sleep call arguments"
    - "DB isolation: _make_db() helper creates tmp_path SQLite with full Phase 13 schema"
    - "Router test: construct minimal FastAPI app + TestClient to test endpoint guards synchronously"

key-files:
  created:
    - backend/tests/test_notion_mcp.py
  modified: []

key-decisions:
  - "Split NTN-03 into two tests (retries_before_success + backoff_timing) to reach 10-test count and separate concerns"
  - "test_api_integration.py failures are pre-existing PostgreSQL dependency — out of scope for this plan"
  - "_make_db() helper DRY-ifies SQLite seeding across 5 async fixtures"

patterns-established:
  - "httpx.AsyncClient patching: mock at app.agents.notion_mcp.httpx.AsyncClient level with __aenter__ AsyncMock"
  - "asyncio.sleep patching: monkeypatch nm_mod.asyncio.sleep for side-effect-free backoff tests"

requirements-completed: [NTN-01, NTN-02, NTN-03, NTN-04, NTN-05]

# Metrics
duration: 4min
completed: 2026-03-22
---

# Phase 13 Plan 03: Notion MCP Export Tests Summary

**10-test pytest suite covering all five NTN requirements with mocked httpx and asyncio.sleep — verifies endpoint guards, backoff timing, DB column existence, and URL writeback without live Notion API calls.**

## Performance

- **Duration:** ~4 min
- **Completed:** 2026-03-22
- **Tasks:** 1 (TDD — tests written, implementation pre-existed from Plan 02)
- **Files created:** 1

## Accomplishments

- Created `backend/tests/test_notion_mcp.py` with 10 tests, all GREEN
- NTN-01: Verified 3 httpx.AsyncClient.post calls (1 goal + 2 sessions), notion_page_url writeback, NULL notes_markdown fallback
- NTN-02: Verified HTTP 400 returned synchronously for empty notion_api_key and notion_parent_page_id before any background task enqueues
- NTN-03: Verified exponential backoff sleep sequence (1s, 2s for attempts 0, 1), successful retry after 429s, and HTTPStatusError raised when all retries exhausted
- NTN-04: Verified notion_page_url column exists in study_goals via PRAGMA table_info on a fresh tmp_path SQLite DB
- NTN-05: Verified POST /goals/{id}/export/notion returns HTTP 200 `{"status": "export_started"}` immediately

## Task Commits

1. **Task 1: Write NTN-01 through NTN-05 pytest suite** - `6b46fbe` (test)

## Files Created/Modified

- `backend/tests/test_notion_mcp.py` — 10 tests, 425 lines

## Decisions Made

- Split NTN-03 into `test_backoff_retries_before_success` + `test_backoff_retry_timing` to reach 10 tests and separate behavioral concern (success after retries) from timing concern (sleep arguments)
- `test_api_integration.py` failures are pre-existing PostgreSQL Docker dependency — not caused by this plan and out of scope
- `_make_db()` helper DRY-ifies async SQLite fixture setup across multiple test functions

## Deviations from Plan

None — plan executed exactly as written. All 10 tests went GREEN directly (implementation pre-existed from Plan 02).

## Self-Check: PASSED

- FOUND: backend/tests/test_notion_mcp.py
- FOUND: .planning/phases/13-notion-mcp-export/13-03-SUMMARY.md
- FOUND: commit 6b46fbe (Task 1)
- 10 tests collected and passed

---
*Phase: 13-notion-mcp-export*
*Completed: 2026-03-22*
