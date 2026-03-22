# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-22)

**Core value:** A student can upload their actual textbooks, set a real deadline, and have every note, chat answer, and quiz question grounded in — and only in — those specific books.
**Current focus:** v2.0 shipped — awaiting v3.0 milestone start

## Current Position

Milestone: v2.0 Adaptive Learning + Multimodal + Super Agent — SHIPPED 2026-03-22
Phase: 16 of 16 (Real RAGAS Benchmark) — COMPLETE
Status: All v2.0 phases complete; milestone archived; git tag v2.0 created

Progress: [████████████████████] 100% (v2.0 shipped)

## Performance Metrics

**Velocity (v1.0 baseline):**
- Total plans completed: 23
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
| 10-adaptive-planner | 3/3 | 7 min | 2.3 min |
| 11-final-test-agent-orchestrator | 4/4 | 13 min | 3.25 min |
| 12-super-agent | 2/2 | 4 min | 2.0 min |

*Updated after each plan completion*
| 13-notion-mcp-export | 3/3 | 10 min | 3.3 min |
| 14-frontend-v2-components | 3/4 | 10 min | 3.3 min |
| 15-github-actions-ci | 1/1 | 2 min | 2.0 min |
| 16-real-ragas-benchmark | 1/1 | 3 min | 3.0 min |
| Phase 16-real-ragas-benchmark P02 | 14 | 2 tasks | 4 files |

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
- Phase 10 Plan 01: PASS_THRESHOLD strict less-than (< 0.65); insert_followup_session() accepts caller-owned db connection for atomic UPDATE+INSERT; handle_quiz_failure() always fetches session_number fresh by UUID to avoid stale data in multi-session adapt
- Phase 10 Plan 02: submit_session_quiz return type changed to dict to allow **followup_result spread; handle_quiz_failure imported lazily inside try block; manual_adapt processes sessions in session_number ASC order with per-session error isolation
- Phase 10 Plan 03: Tests went GREEN immediately (implementation pre-existed from plans 01/02); patch settings at module level to redirect aiosqlite.connect to tmp_path DB
- Phase 11 Plan 01: ScholarState extended additively (new V2 fields appended) so build_graph() needs no changes; cumulative_tests placed inside SQLITE_SCHEMA constant (not a separate migration) so init_db() handles it automatically; update_goal_progress() returns empty dict for unknown goal_id
- Phase 11 Plan 02: Per-session LLM calls chosen over batch call to avoid context limits; q.session_number enforced post-LLM-call (loop variable always authoritative); retrieval failure per session is non-fatal (warn + skip)
- Phase 11 Plan 03: FINAL_TEST_PASS_THRESHOLD=0.70 and WEAK_SESSION_THRESHOLD=0.50 named as separate constants; TestQuestion cast to QuizQuestion to reuse evaluate_quiz(); _compute_weak_sessions reads server-side stored data to prevent client manipulation of session_number
- Phase 11 Plan 04: side_effect factory required for mock_test_output (not shared return_value) — Pydantic model objects are mutable; shared instance across 2 session loop iterations results in all session_numbers being overwritten to the last session's value
- Phase 12 Plan 01: top_k=8 for super agent (larger cross-source pool); checkpoint channel_values excludes goal_id; broader try/except Exception yields SSE error event before re-raising to prevent silent broken streams
- Phase 12 Plan 02: Tests went GREEN immediately (implementation pre-existed from Plan 01); LLM mock uses real async generator function (not AsyncMock) to satisfy async for protocol in astream(); aiosqlite mock requires nested async context managers for connect→execute→fetchall chain
- [Phase 13-01]: notion_api_key/notion_parent_page_id use empty-string defaults (falsy pattern) matching vision_model; notion_page_url column added via idempotent ALTER TABLE guard in init_db()
- [Phase 13-02]: run_notion_export opens its own aiosqlite connection (background task lifetime mismatch); sequential session child pages (goal_page_id required from step 1); asyncio.sleep(2**attempt) backoff; try/except wraps full export body to prevent silent failures
- [Phase 14-01]: layout.tsx stays Server Component using next/link Link (no 'use client' needed); h-screen replaced with h-full in study page to avoid double-scroll in nested flex layout; streamSuperChat follows identical parseSSE pattern as streamChat
- [Phase 14-02]: useState function initializer used for thread_id to avoid SSR localStorage access pitfall in 'use client' component; cancelRef pattern for SSE cleanup on unmount
- [Phase 14-03]: AdaptiveAlert uses undefined sentinel (not boolean) to distinguish "not triggered" from "triggered with no session data" (null); NotionExportButton initializes directly to 'done' state when initialNotionUrl provided on mount
- [Phase 15-01]: pgvector/pgvector:pg16 image (not postgres:16) — pgvector compiled in; init_pgvector_schema() runs CREATE EXTENSION so no separate psql step needed; -m "not integration" (not --ignore) preserves 2 mocked tests in test_router.py while excluding accuracy gate; PYTHONPATH=/opt/pageindex via PageIndex git clone; SQLITE_PATH=/tmp/scholar_ci.db for CI
- [Phase 16-01]: --output-dir defaults to None in argparse (not RESULTS_DIR) so resolution happens in one ternary after parse_args(); output_dir.mkdir(parents=True, exist_ok=True) called before timestamp setup; Step 5 RESULTS_DIR.mkdir() removed; ASCII table uses f-strings only — zero new pip dependencies
- [Phase 16-real-ragas-benchmark]: Phase 16-02: Ran RAGAS benchmark against test_book.pdf (no Biology 2e present); answer_relevancy=NaN (RAGAS needs OPENAI_API_KEY for embeddings, separate from LLM_API_KEY); README shows N/A† with explanatory footnote

### Pending Todos

None yet.

### Blockers/Concerns

- EVAL-02/EVAL-03: Completed. Real scores generated but with caveats: Biology 2e PDF not present (test_book.pdf used instead); OPENAI_API_KEY not configured so AnswerRelevancy=NaN; pgvector store empty so context_precision=0.00. For representative scores: upload Biology 2e + configure OPENAI_API_KEY + re-run benchmark.

## Session Continuity

Last session: 2026-03-22
Stopped at: Completed 16-02-PLAN.md (final plan)
Resume file: None
