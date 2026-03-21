# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-21)

**Core value:** A student can upload their actual textbooks, set a real deadline, and have every note, chat answer, and quiz question grounded in — and only in — those specific books.
**Current focus:** Phase 9 — Vision Ingestion

## Current Position

Phase: 9 of 16 (Vision Ingestion)
Plan: 3 of 3 in current phase (phase complete)
Status: In progress
Last activity: 2026-03-22 — Phase 9 Plan 03 complete: full pytest test suite for VIS-01 through VIS-06, 8 tests all passing

Progress: [█████████░░░░░░] ~58% (Phase 9 Plan 03 complete)

## Performance Metrics

**Velocity (v1.0 baseline):**
- Total plans completed: 22
- Average duration: 3.6 min
- Total execution time: ~1.3 hours

**By Phase (v1.0):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-infrastructure | 3/3 | 11 min | 3.7 min |
| 02-ingestion-pipeline | 4/4 | 8 min | 2.0 min |
| 03-retrieval-engine | 3/3 | 14 min | 4.7 min |
| 04-agents-orchestrator | 4/4 | 32 min | 8.0 min |
| 05-api-layer | 1/1 | — | — |
| 06-frontend | 4/4 | 9 min | 2.3 min |
| 07-evaluation | 1/1 | 3 min | 3.0 min |
| 08-langsmith-activation | 1/1 | 2 min | 2.0 min |
| 09-vision-ingestion | 3/3 | 13 min | 4.3 min |

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting v2.0 work:

- Mistral free tier via model factory: vision LLM will need separate `get_vision_llm()` factory entry
- LangGraph SqliteSaver: already in use; super agent thread_id must come from frontend localStorage UUID
- SSE POST pattern: established in v1.0 — `/super/chat/stream` must follow same POST+SSE convention
- RAGAS 0.2 column names: `user_input/retrieved_contexts/response/reference` — benchmark script update must preserve these
- Phase 8: Inject LangSmith vars into os.environ in lifespan (not .env) so LangChain picks them up at call time — no per-agent code changes needed
- Phase 8: Guard injection with `if settings.langsmith_api_key` to silently disable tracing when key absent
- Phase 9: get_vision_llm() uses falsy check (`if not settings.vision_model`) not `is not None` to catch empty string Pydantic default; no streaming param as vision calls are single-invoke
- Phase 9 Plan 02: Stage 1.5 import scoped inside source_type == 'pdf' block; 150 DPI render balances clarity vs token cost; processed counter increments only on actual LLM calls
- Phase 9 Plan 03: Patch augment_pages_with_vision on ve_mod (not pipeline_mod) to intercept local imports inside pipeline function body; async def coroutine mocks required for awaited pipeline stage functions

### Pending Todos

None yet.

### Blockers/Concerns

- EVAL-02/EVAL-03: Real RAGAS run requires an ingested PDF with a PageIndex tree (~150 LLM calls). Deferred to Phase 16 intentionally — ensure a suitable PDF is available before starting that phase.

## Session Continuity

Last session: 2026-03-22
Stopped at: Completed 09-03-PLAN.md
Resume file: None
