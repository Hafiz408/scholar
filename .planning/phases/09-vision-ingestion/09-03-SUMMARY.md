---
phase: 09-vision-ingestion
plan: "03"
subsystem: testing
tags: [pytest, monkeypatch, vision, asyncio, pytest-asyncio]

# Dependency graph
requires:
  - phase: 09-01
    provides: get_vision_llm() factory function in llm_factory.py
  - phase: 09-02
    provides: vision_extractor.py with augment_pages_with_vision and pipeline.py Stage 1.5 wiring
provides:
  - Full pytest test suite covering VIS-01 through VIS-06 requirements
  - 8 test functions in backend/tests/test_vision_ingestion.py, all passing without a live LLM
affects: [future phases that modify llm_factory, vision_extractor, or pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "monkeypatch module-level settings attributes (ve.settings.vision_model) for Pydantic settings mutation"
    - "monkeypatch module attribute (ve_mod.augment_pages_with_vision) to intercept local imports inside pipeline functions"
    - "async coroutine mocks (async def fake_augment) for awaited pipeline dependencies"
    - "FakeConn async context manager pattern for aiosqlite mocking without real DB"

key-files:
  created:
    - backend/tests/test_vision_ingestion.py
  modified: []

key-decisions:
  - "Patch augment_pages_with_vision on ve_mod (vision_extractor module) rather than pipeline_mod, because pipeline uses a local import inside the function body — patching the module attribute before run_ingestion is called ensures the local import picks up the mock"
  - "Use async def coroutine mocks for build_pageindex_tree and embed_and_store (both are async functions in pipeline); plan template had non-async lambdas which would have failed"
  - "asyncio_mode=AUTO detected from pytest-asyncio plugin at runtime (not conftest.py); @pytest.mark.asyncio decorators are valid in both auto and non-auto modes"

patterns-established:
  - "VIS test pattern: monkeypatch.setattr(ve.settings, 'field', value) for settings isolation per test"
  - "VIS test pattern: monkeypatch.setattr(ve, '_describe_page_sync', fake_fn) to intercept LLM calls"
  - "Pipeline test pattern: patch on vision_extractor module before calling run_ingestion to intercept local imports"

requirements-completed: [VIS-01, VIS-02, VIS-03, VIS-04, VIS-05, VIS-06]

# Metrics
duration: 5min
completed: 2026-03-22
---

# Phase 9 Plan 03: Vision Ingestion Test Suite Summary

**8-test pytest suite covering VIS-01 through VIS-06 using monkeypatching — no live LLM, no PDF file, all pass**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-22T19:14:00Z
- **Completed:** 2026-03-22T19:18:59Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Wrote 8 fully monkeypatched tests covering every VIS requirement without any live API key or real PDF
- Corrected plan template bugs: async coroutine mocks for `build_pageindex_tree`/`embed_and_store`, and pipeline local-import patch strategy
- Full regression check passed: 48 tests pass across all non-integration test files, zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: RED/GREEN — Write tests for VIS-01 through VIS-06** - `f623d1b` (test)

**Plan metadata:** (docs commit — created after this summary)

_Note: Task 2 (regression check) required no file changes — all tests passed on first run._

## Files Created/Modified

- `backend/tests/test_vision_ingestion.py` - 8-test pytest suite covering VIS-01 through VIS-06 with full monkeypatching

## Decisions Made

- Patching `ve_mod.augment_pages_with_vision` (the `vision_extractor` module attribute) rather than `pipeline_mod`'s name, because `pipeline.py` uses a local `from app.ingestion.vision_extractor import augment_pages_with_vision` inside the `source_type == 'pdf'` branch. Since the module is already in `sys.modules`, patching the module attribute before `run_ingestion` executes ensures the local import binds to our mock.
- Replaced plan template's non-async lambda mocks for `build_pageindex_tree` and `embed_and_store` with proper `async def` coroutines, since both are awaited by `run_ingestion`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed async mock signatures for pipeline stage functions**
- **Found during:** Task 1 (writing test_pipeline_calls_vision_augmentation_for_pdf)
- **Issue:** Plan template provided `lambda *a, **kw: None` for `build_pageindex_tree` and `embed_and_store`, but both are `async def` coroutines awaited inside `run_ingestion`. Non-async lambdas would cause TypeError when awaited.
- **Fix:** Replaced lambdas with `async def fake_build_pageindex(*a, **kw): return None` and `async def fake_embed_and_store(*a, **kw): return 0`
- **Files modified:** backend/tests/test_vision_ingestion.py
- **Verification:** `test_pipeline_calls_vision_augmentation_for_pdf` passed
- **Committed in:** f623d1b (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — incorrect mock type)
**Impact on plan:** Auto-fix necessary for correctness. No scope creep.

## Issues Encountered

None beyond the auto-fixed mock type issue above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 9 is complete: all three plans (09-01, 09-02, 09-03) committed and passing
- VIS-01 through VIS-06 requirements fully tested and verified
- Vision ingestion is ready as an opt-in feature (set `VISION_MODEL` in `.env` to enable)

## Self-Check: PASSED

- FOUND: backend/tests/test_vision_ingestion.py
- FOUND: .planning/phases/09-vision-ingestion/09-03-SUMMARY.md
- FOUND commit: f623d1b (test(09-03): add failing tests for VIS-01 through VIS-06)

---
*Phase: 09-vision-ingestion*
*Completed: 2026-03-22*
