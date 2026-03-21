---
phase: 09-vision-ingestion
plan: "01"
subsystem: api
tags: [pydantic-settings, langchain, llm-factory, vision, config]

# Dependency graph
requires:
  - phase: 03-retrieval-engine
    provides: llm_factory.py with get_llm() pattern this mirrors
provides:
  - vision_model and vision_max_pages Pydantic settings fields in config.py
  - get_vision_llm() factory function in llm_factory.py with ValueError guard on empty vision_model
affects:
  - 09-vision-ingestion (plans 02+): vision extractor and tests depend on these building blocks

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "get_vision_llm() mirrors get_llm() structure but with mandatory vision_model guard (falsy check, not `is not None`)"
    - "Vision settings are opt-in: empty string default means vision disabled without env var configuration"

key-files:
  created: []
  modified:
    - backend/app/config.py
    - backend/app/llm_factory.py

key-decisions:
  - "Vision factory uses falsy check (`if not settings.vision_model`) rather than `is not None` to correctly catch empty string Pydantic default"
  - "No streaming parameter on get_vision_llm() — vision calls are single-invoke, not streaming"
  - "get_vision_llm() uses settings.llm_provider for provider dispatch (shared with get_llm()), only the model name differs"

patterns-established:
  - "Vision is opt-in via VISION_MODEL env var — empty string default cleanly disables the feature"
  - "ValueError guard before provider dispatch enforces configuration requirement at call time"

requirements-completed: [VIS-01, VIS-06]

# Metrics
duration: 5min
completed: 2026-03-22
---

# Phase 9 Plan 01: Vision Config and LLM Factory Summary

**Pydantic vision_model/vision_max_pages settings fields and get_vision_llm() factory with ValueError guard on unconfigured vision model**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-22T00:00:00Z
- **Completed:** 2026-03-22T00:05:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `vision_model: str = ""` and `vision_max_pages: int = 20` to Settings class after embedding settings block
- Added `get_vision_llm()` to llm_factory.py mirroring get_llm() structure with all four providers (openai, openai-compat, anthropic, google)
- Implemented mandatory ValueError guard when vision_model is empty, containing "vision_model" in error message per VIS-01 requirement
- All 40 non-integration tests pass; test_router_accuracy_gate failure is pre-existing (requires live OpenAI API key)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add vision settings to config.py** - `243ae60` (feat)
2. **Task 2: Add get_vision_llm() to llm_factory.py** - `d141197` (feat)

## Files Created/Modified

- `backend/app/config.py` - Added vision_model (default "") and vision_max_pages (default 20) fields to Settings class
- `backend/app/llm_factory.py` - Added get_vision_llm() function with ValueError guard and full provider support

## Decisions Made

- Used falsy check `if not settings.vision_model` rather than `is not None` to correctly catch empty string Pydantic default
- No `streaming` parameter in get_vision_llm() since vision calls use single invoke pattern
- Provider dispatch reuses `settings.llm_provider` — vision model name differs but provider selection is shared

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The pre-existing `test_router_accuracy_gate` failure requires a live OpenAI API key and is unrelated to this plan's changes.

## User Setup Required

None - no external service configuration required. Users who want vision enabled must add `VISION_MODEL=gpt-4o-mini` (or equivalent) to their `.env` file when the feature is configured in later plans.

## Next Phase Readiness

- `get_vision_llm()` is importable and raises correctly — downstream vision extractor (09-02+) can import and use it
- Settings fields are live — environment can configure vision via VISION_MODEL and VISION_MAX_PAGES env vars
- No blockers for subsequent vision ingestion plans

---
*Phase: 09-vision-ingestion*
*Completed: 2026-03-22*
