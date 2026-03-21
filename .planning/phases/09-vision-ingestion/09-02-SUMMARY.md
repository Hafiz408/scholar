---
phase: 09-vision-ingestion
plan: "02"
subsystem: ingestion
tags: [pymupdf, langchain, vision, pdf, pipeline]

# Dependency graph
requires:
  - phase: 09-vision-ingestion/09-01
    provides: vision_model/vision_max_pages settings and get_vision_llm() factory
  - phase: 02-ingestion-pipeline
    provides: pipeline.py structure, extract_pdf, page dict schema
provides:
  - vision_extractor.py with augment_pages_with_vision async function
  - Stage 1.5 vision augmentation wired into pipeline.py (PDF-only)
  - Per-page PyMuPDF rendering at 150 DPI to base64 PNG
  - Per-page exception isolation — pipeline never fails due to vision errors
affects: [10-quiz-generation, 11-chat-api, 16-evaluation]

# Tech tracking
tech-stack:
  added: [pymupdf>=1.26.0 (fitz), langchain_core.messages.HumanMessage with image_url]
  patterns: [asyncio.to_thread wrapping synchronous PyMuPDF+LLM call, falsy opt-in guard for empty string settings]

key-files:
  created: [backend/app/ingestion/vision_extractor.py]
  modified: [backend/app/ingestion/pipeline.py]

key-decisions:
  - "Stage 1.5 import placed inside source_type == 'pdf' block (not top-level) to keep it co-located and enforce VIS-05 (URL sources untouched)"
  - "150 DPI render chosen: 72 DPI loses small text, 300 DPI triples token cost"
  - "processed counter increments only on successful LLM call (not on has_images=False skip), ensuring vision_max_pages cap counts actual API calls"
  - "Per-page try/except inside augment_pages_with_vision loop (not outer pipeline try/except) is the critical VIS-04 isolation boundary"

patterns-established:
  - "Vision opt-in: `if not settings.vision_model: return pages` — falsy check catches empty string Pydantic default"
  - "asyncio.to_thread wraps synchronous PyMuPDF + LLM call, consistent with existing extract_pdf pattern in pipeline.py"

requirements-completed: [VIS-02, VIS-03, VIS-04, VIS-05]

# Metrics
duration: 3min
completed: 2026-03-22
---

# Phase 9 Plan 02: Vision Extractor Summary

**PDF pages rendered to 150 DPI PNG via PyMuPDF, described by vision LLM, and appended to page text as Stage 1.5 in the ingestion pipeline**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-21T19:08:45Z
- **Completed:** 2026-03-21T19:11:44Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created vision_extractor.py with `augment_pages_with_vision` — async function that appends visual descriptions to page text for has_images=True pages
- Per-page exception isolation: vision failures are logged as warnings, pipeline continues, processed counter not incremented (VIS-04)
- vision_max_pages cost cap enforced (VIS-06): 0 = unlimited, otherwise stop after N LLM calls
- Wired Stage 1.5 into pipeline.py inside the `source_type == "pdf"` block, after text extraction, before PageIndex build — URL paths untouched (VIS-05)
- All 13 existing tests (test_pdf_extractor, test_pageindex_builder) pass after pipeline modification

## Task Commits

Each task was committed atomically:

1. **Task 1: Create vision_extractor.py** - `461687d` (feat)
2. **Task 2: Wire Stage 1.5 into pipeline.py** - `2931aa8` (feat)

## Files Created/Modified
- `backend/app/ingestion/vision_extractor.py` - Vision augmentation module: _render_page_to_base64, _describe_page_sync, augment_pages_with_vision
- `backend/app/ingestion/pipeline.py` - Stage 1.5 inserted after PDF text extraction (4 lines added)

## Decisions Made
- Import of `augment_pages_with_vision` placed inside the `if source_type == "pdf":` block rather than top-level — keeps it co-located with the code that uses it and explicitly enforces that URL sources never trigger vision (VIS-05)
- 150 DPI chosen for page rendering: balances OCR/diagram clarity vs. base64 token cost; 72 DPI loses fine text, 300 DPI triples size
- `processed` counter only increments after a successful (non-excepted) LLM call on a has_images=True page — ensures vision_max_pages accurately counts API calls, not pages skipped

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

PyMuPDF (`fitz`) was not installed in the local Python environment (it is present in backend/requirements.txt for Docker). Installed locally with `pip install pymupdf` to enable import verification. This is a local dev environment gap, not a production issue.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Vision pipeline is complete and opt-in: set `VISION_MODEL=gpt-4o-mini` (or any vision-capable model) in `.env` to activate
- Enriched page text flows into both PageIndex (Stage 2) and pgvector embeddings (Stage 3) automatically
- Phase 9 Plan 03 (if any) or next phase can proceed immediately

---
*Phase: 09-vision-ingestion*
*Completed: 2026-03-22*
