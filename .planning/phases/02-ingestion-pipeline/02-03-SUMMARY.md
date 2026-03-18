---
phase: 02-ingestion-pipeline
plan: "03"
subsystem: backend-ingestion
tags: [pageindex, httpx, asyncio, pdf-submission, polling, fallback]

requires:
  - phase: 02-01
    provides: [config.py with pageindex_api_key and pageindex_base_url settings]

provides:
  - build_pageindex_tree async function (submit PDF, poll, return doc_id or None)
  - delete_pageindex_doc sync best-effort function

affects: [02-04-pipeline, 03-retrieval]

tech-stack:
  added: []
  patterns:
    - asyncio-to-thread for sync httpx REST calls inside async context
    - outer-try-except-return-None for graceful degradation
    - best-effort cleanup (delete) that never raises

key-files:
  created: []
  modified:
    - backend/app/ingestion/pageindex_builder.py

key-decisions:
  - "Used httpx REST API directly instead of PageIndexClient class — pageindex v0.1.0 package is an empty stub with no client class; all REST calls use settings.pageindex_base_url and settings.pageindex_api_key"

patterns-established:
  - "Graceful fallback pattern: wrap entire async function in try/except, return None on any failure — never raise"
  - "asyncio.to_thread for sync IO inside async functions"

requirements-completed: [INGEST-04]

duration: 2min
completed: 2026-03-18
---

# Phase 2 Plan 03: PageIndex Builder Summary

**Async PDF submission to PageIndex REST API with 30-attempt polling loop and two-level fallback — invalid key, API errors, or timeout all return None to keep vector-only ingestion unblocked.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-18T16:15:02Z
- **Completed:** 2026-03-18T16:17:10Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- `build_pageindex_tree` async function: submits a PDF via REST, polls `is_retrieval_ready` up to 30 times at 10-second intervals, returns doc_id string on success
- None file_path (URL sources) returns None immediately — no API call made
- Entire function body wrapped in outer `try/except Exception` — invalid API key, network errors, and timeouts all return None, never raise
- Failed document status check inside poll loop returns None explicitly (cleaner than relying on outer except)
- `delete_pageindex_doc` synchronous best-effort cleanup via httpx DELETE — catches all exceptions, never raises

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement pageindex_builder.py with submit, poll, and fallback** - `2d2d578` (feat)

**Plan metadata:** _(see docs commit below)_

## Files Created/Modified

- `backend/app/ingestion/pageindex_builder.py` — build_pageindex_tree and delete_pageindex_doc using httpx REST API against settings.pageindex_base_url

## Decisions Made

- Used `httpx` REST API directly (not `PageIndexClient`) because the installed `pageindex` v0.1.0 Python package is an empty stub with no client class — its `__init__.py` exports nothing. All REST calls mirror the documented API shape (`/documents` POST, `/documents/{id}/ready` GET, `/documents/{id}` GET and DELETE).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] PageIndexClient does not exist in installed pageindex v0.1.0 package**
- **Found during:** Task 1 (initial import test)
- **Issue:** `from pageindex import PageIndexClient` raised `ImportError` — the `pageindex` package v0.1.0 has an empty `__init__.py` with no classes
- **Fix:** Replaced the client-based approach with direct `httpx` REST calls against `settings.pageindex_base_url`. Implemented private sync helpers (`_submit_document`, `_is_retrieval_ready`, `_get_document`) that run in `asyncio.to_thread`, preserving the same async signature and all behavioral requirements from the plan
- **Files modified:** backend/app/ingestion/pageindex_builder.py
- **Verification:** `import ok`, `fallback ok` (None → None), `invalid key fallback ok` (exception → None), `delete fallback ok` (name resolution error → None, no raise)
- **Committed in:** 2d2d578 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug/broken import)
**Impact on plan:** All behavioral requirements met — same function signatures, same fallback guarantees, same polling logic. Only the underlying HTTP transport changed from a non-existent client class to direct httpx REST calls.

## Issues Encountered

None beyond the auto-fixed import deviation above.

## User Setup Required

**External service requires manual configuration.**

To enable live PageIndex document submission, add to `.env`:

```
PAGEINDEX_API_KEY=your_key_here
```

Obtain from: [PageIndex Dashboard -> Settings -> API Keys](https://pageindex.ai)

Without the key, `build_pageindex_tree` gracefully returns None for all PDF submissions — vector-only ingestion continues unaffected.

## Next Phase Readiness

- `pageindex_builder.py` is ready to be imported by `pipeline.py` (02-04)
- Fallback behavior verified — pipeline can call `build_pageindex_tree` safely even without API key configured
- `delete_pageindex_doc` available for cleanup in source deletion flows (Phase 3+)

---
*Phase: 02-ingestion-pipeline*
*Completed: 2026-03-18*
