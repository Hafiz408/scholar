# Roadmap: Scholar V1

## Milestones

- ✅ **v1.0 MVP** — Phases 1–7 (shipped 2026-03-21)
- [ ] **v2.0 Adaptive Learning + Multimodal + Super Agent** — Phases 8–16

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–7) — SHIPPED 2026-03-21</summary>

- [x] Phase 1: Infrastructure (3/3 plans) — completed 2026-03-18
- [x] Phase 2: Ingestion Pipeline (4/4 plans) — completed 2026-03-19
- [x] Phase 3: Retrieval Engine (3/3 plans) — completed 2026-03-19
- [x] Phase 4: Agents & Orchestrator (4/4 plans) — completed 2026-03-19
- [x] Phase 5: API Layer (1/1 plan) — completed 2026-03-19
- [x] Phase 6: Frontend (4/4 plans) — completed 2026-03-19
- [x] Phase 7: Evaluation (2/2 plans) — completed 2026-03-21

</details>

**v2.0 Adaptive Learning + Multimodal + Super Agent**

- [x] **Phase 8: LangSmith Activation** — Wire tracing env vars so every agent call appears in LangSmith dashboard (completed 2026-03-21)
- [x] **Phase 9: Vision Ingestion** — Extend ingestion pipeline to extract diagram/chart descriptions from image-heavy PDF pages via vision LLM (completed 2026-03-21)
- [x] **Phase 10: Adaptive Planner** — Auto-insert follow-up study session when quiz score falls below 65% (completed 2026-03-22)
- [x] **Phase 11: Final Test Agent + Orchestrator** — Cross-session cumulative MCQ test that marks goal complete at ≥ 70%; expand ScholarState for V2 fields (completed 2026-03-21)
- [x] **Phase 12: Super Agent** — Cross-KB persistent chat across all uploaded sources (completed 2026-03-21)
- [x] **Phase 13: Notion MCP Export** — Export study plan and session notes to Notion via background task (completed 2026-03-22)
- [x] **Phase 14: Frontend V2 Components** — Super page, AdaptiveAlert, TestPanel, NotionExportButton wired into existing UI (completed 2026-03-21)
- [ ] **Phase 15: GitHub Actions CI** — Automated pytest + ruff on every PR to feature/v2 and main
- [ ] **Phase 16: Real RAGAS Benchmark** — Replace placeholder scores with real faithfulness/relevancy/precision metrics from OpenStax Biology 2e run

## Phase Details

### Phase 8: LangSmith Activation
**Goal**: Every agent call in the system is traced in LangSmith with cost and latency visible
**Depends on**: Nothing (v1.0 codebase baseline)
**Requirements**: OBS-01, OBS-02
**Success Criteria** (what must be TRUE):
  1. After setting `LANGCHAIN_API_KEY` in `.env`, developer can open LangSmith dashboard and see traces for planner, chat, quiz, and all V2 agents without any code changes
  2. When `LANGCHAIN_API_KEY` is absent or empty, the app starts normally and agents run without error (tracing gracefully disabled)
  3. `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, and `LANGCHAIN_PROJECT` are read from environment at startup and injected into the LangChain runtime
**Plans**: 1 plan

Plans:
- [ ] 08-01-PLAN.md — Inject LangSmith env vars at startup + add pytest tests for injection logic

### Phase 9: Vision Ingestion
**Goal**: Users can opt in to vision-enhanced PDF ingestion that appends diagram/chart/table descriptions to page text
**Depends on**: Phase 8
**Requirements**: VIS-01, VIS-02, VIS-03, VIS-04, VIS-05, VIS-06
**Success Criteria** (what must be TRUE):
  1. When `vision_model` is set in config, uploading a diagram-heavy PDF page results in a natural-language description of that diagram appended to the extracted text in the knowledge base
  2. When `vision_model` is empty, ingestion runs identically to v1.0 — no vision LLM call is made, no extra latency
  3. A vision extraction exception on any single page is logged but does not halt or fail the overall ingestion pipeline
  4. `vision_max_pages` config setting prevents processing more than N pages per document (verified by test with a document exceeding the limit)
  5. `get_vision_llm()` raises `ValueError` with a clear message when called with an empty `vision_model` setting
**Plans**: 3 plans

Plans:
- [ ] 09-01-PLAN.md — Add vision_model/vision_max_pages config + get_vision_llm() factory
- [ ] 09-02-PLAN.md — Create vision_extractor.py + wire Stage 1.5 into pipeline.py
- [ ] 09-03-PLAN.md — TDD: pytest suite covering VIS-01 through VIS-06

### Phase 10: Adaptive Planner
**Goal**: Quiz failure automatically triggers a targeted follow-up session inserted into the study plan so students revisit weak material without manual intervention
**Depends on**: Phase 9
**Requirements**: ADP-01, ADP-02, ADP-03, ADP-04, ADP-05
**Success Criteria** (what must be TRUE):
  1. Submitting a quiz with score < 65% results in a new follow-up session appearing immediately after the completed session in the study plan (verified via `GET /goals/{id}`)
  2. Session numbers for all sessions after the insertion point are incremented by 1 — no gaps, no duplicates
  3. The quiz submission response body includes `followup_session_added: true` and a populated `followup_session` object when a follow-up is inserted
  4. Submitting a quiz with score ≥ 65% returns `followup_session_added: false` and does not alter the plan
  5. `POST /goals/{id}/adapt` triggers adaptive replanning manually and returns the updated session list
**Plans**: 3 plans

Plans:
- [x] 10-01-PLAN.md — Create adaptive_planner.py agent + add ADAPTIVE_PLANNER_SYSTEM_PROMPT to prompts.py
- [x] 10-02-PLAN.md — Wire adaptive planner into quiz submit response + add POST /goals/{id}/adapt endpoint
- [x] 10-03-PLAN.md — TDD: pytest suite covering ADP-01 through ADP-05

### Phase 11: Final Test Agent + Orchestrator
**Goal**: Students can take a cumulative cross-session MCQ test after completing all sessions; passing (≥ 70%) marks the goal complete
**Depends on**: Phase 10
**Requirements**: TST-01, TST-02, TST-03, TST-04, TST-05, TST-06, ORC-01, ORC-02
**Success Criteria** (what must be TRUE):
  1. `POST /goals/{id}/test/generate` with all sessions complete returns a test of 1-2 questions per session (capped at 15 total), each grounded in retrieved context
  2. `POST /goals/{id}/test/generate` when sessions are not all complete returns HTTP 400 with an explanatory message
  3. `POST /goals/{id}/test/submit` with score ≥ 70% changes goal status to `complete` (confirmed by subsequent `GET /goals/{id}`)
  4. Submit response includes `weak_session_numbers` listing sessions where the student answered < 50% correctly
  5. `cumulative_tests` SQLite table exists after migration and stores test records correctly
  6. `ScholarState` includes V2 fields (`sessions_complete`, `weak_session_ids`, `followup_sessions_added`, `final_test_id`, `goal_complete`) and `update_goal_progress()` function is importable from the orchestrator module
**Plans**: 4 plans

Plans:
- [ ] 11-01-PLAN.md — Extend ScholarState V2 + add update_goal_progress() + cumulative_tests DB table
- [x] 11-02-PLAN.md — Create test_agent.py with per-session retrieval and session_number-tagged TestQuestion
- [x] 11-03-PLAN.md — Create test router (generate + submit endpoints) and register in main.py
- [ ] 11-04-PLAN.md — TDD: pytest suite covering TST-01 through TST-06 and ORC-01/ORC-02

### Phase 12: Super Agent
**Goal**: Students can chat across their entire knowledge base — all uploaded sources — in a single persistent conversation
**Depends on**: Phase 11
**Requirements**: SUP-01, SUP-02, SUP-03, SUP-04
**Success Criteria** (what must be TRUE):
  1. `POST /super/chat/stream` returns SSE token events grounded in context retrieved from ALL ready knowledge sources, not scoped to a single session
  2. Sending a chat message when no sources are indexed returns an SSE `error` event with the text "No books indexed yet" — the server does not crash or return HTTP 5xx
  3. The frontend `thread_id` (a localStorage UUID) controls conversation continuity — the same `thread_id` from a previous request continues the same conversation thread server-side
  4. The SSE event format from `/super/chat/stream` is identical to the existing `/chat/stream` format (same event names and field structure)
**Plans**: 2 plans

Plans:
- [ ] 12-01-PLAN.md — Create super_agent.py + routers/super.py + register in main.py
- [ ] 12-02-PLAN.md — TDD: pytest suite covering SUP-01 through SUP-04

### Phase 13: Notion MCP Export
**Goal**: Students can export their study plan and session notes to Notion with one click; the export runs in the background without blocking the UI
**Depends on**: Phase 12
**Requirements**: NTN-01, NTN-02, NTN-03, NTN-04, NTN-05
**Success Criteria** (what must be TRUE):
  1. `POST /goals/{id}/export/notion` returns `{"status": "export_started"}` immediately (no blocking wait for Notion API)
  2. After the background task completes, `GET /goals/{id}` returns a populated `notion_page_url` field pointing to the created Notion page
  3. Calling the export endpoint with `notion_api_key` absent or empty returns an error immediately — no HTTP call to Notion is attempted
  4. When Notion API returns HTTP 429, the client retries with exponential backoff (1s, 2s, 4s) up to 3 times before surfacing the error
  5. The created Notion page has one parent page for the goal and child pages for each session's notes
**Plans**: 3 plans

Plans:
- [x] 13-01-PLAN.md — Add notion_api_key/notion_parent_page_id to config + notion_page_url column to SQLite
- [x] 13-02-PLAN.md — Create notion_mcp.py agent + wire POST /goals/{id}/export/notion endpoint
- [x] 13-03-PLAN.md — TDD: pytest suite covering NTN-01 through NTN-05

### Phase 14: Frontend V2 Components
**Goal**: All V2 backend capabilities are accessible from the frontend — super chat, adaptive alerts, final test, and Notion export are visible and functional in the UI
**Depends on**: Phase 13
**Requirements**: FE-01, FE-02, FE-03, FE-04, FE-05
**Success Criteria** (what must be TRUE):
  1. Navigating to `/super` renders a full-height chat interface; the page header shows the count of indexed sources; conversation persists across page refreshes via localStorage `thread_id`
  2. The main navigation sidebar contains a link to the Super Agent page that navigates correctly
  3. After a quiz score < 65% is submitted, a dismissible `AdaptiveAlert` banner appears on the goal detail page indicating a follow-up session was added
  4. When all sessions on a goal are complete, a "Take Final Test" button appears; submitting a passing score triggers a confetti animation
  5. The Notion export button on the goal detail page becomes a link showing "View in Notion" once `notion_page_url` is populated (polled after export starts)
**Plans**: 4 plans

Plans:
- [x] 14-01-PLAN.md — Foundation: extend types/api/sse, add nav sidebar to layout, fix h-screen in study page
- [x] 14-02-PLAN.md — Super Agent page at /super with localStorage thread_id and SSE streaming
- [x] 14-03-PLAN.md — AdaptiveAlert, TestPanel, NotionExportButton components wired into goal and study pages
- [ ] 14-04-PLAN.md — (remaining)

### Phase 15: GitHub Actions CI
**Goal**: Every pull request to feature/v2 and main automatically runs the test suite and linter so regressions are caught before merge
**Depends on**: Phase 14
**Requirements**: CI-01, CI-02, CI-03
**Success Criteria** (what must be TRUE):
  1. Opening a test PR to `feature/v2` triggers the CI workflow; pytest and ruff both run and the check appears in the GitHub PR status
  2. The CI workflow completes without requiring any live LLM API calls — `test_router_accuracy_gate.py` is excluded
  3. Integration tests that require PostgreSQL pass in CI via the PostgreSQL service container (no local DB needed)
**Plans**: 1 plan

Plans:
- [ ] 15-01-PLAN.md — Create .github/workflows/ci.yml with ruff, pytest, and pgvector service container

### Phase 16: Real RAGAS Benchmark
**Goal**: The README benchmark table shows real faithfulness, answer relevancy, context precision, and latency scores from an actual run against OpenStax Biology 2e — replacing all placeholder dashes
**Depends on**: Phase 15
**Requirements**: EVAL-01, EVAL-02, EVAL-03
**Success Criteria** (what must be TRUE):
  1. `eval/run_ragas.py --output-dir eval/results/` executes without error and prints a summary table of all four metrics to stdout
  2. JSON result files for the benchmark run are committed to `eval/results/` with real numeric values (no `—` placeholders)
  3. The README comparison table shows real scores for faithfulness, answer relevancy, context precision, and avg latency for both PageIndex and vector strategies
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Infrastructure | v1.0 | 3/3 | Complete | 2026-03-18 |
| 2. Ingestion Pipeline | v1.0 | 4/4 | Complete | 2026-03-19 |
| 3. Retrieval Engine | v1.0 | 3/3 | Complete | 2026-03-19 |
| 4. Agents & Orchestrator | v1.0 | 4/4 | Complete | 2026-03-19 |
| 5. API Layer | v1.0 | 1/1 | Complete | 2026-03-19 |
| 6. Frontend | v1.0 | 4/4 | Complete | 2026-03-19 |
| 7. Evaluation | v1.0 | 2/2 | Complete | 2026-03-21 |
| 8. LangSmith Activation | 1/1 | Complete   | 2026-03-21 | - |
| 9. Vision Ingestion | 3/3 | Complete   | 2026-03-21 | - |
| 10. Adaptive Planner | 2/3 | Complete    | 2026-03-21 | - |
| 11. Final Test Agent + Orchestrator | 4/4 | Complete    | 2026-03-21 | - |
| 12. Super Agent | 2/2 | Complete    | 2026-03-21 | - |
| 13. Notion MCP Export | 3/3 | Complete    | 2026-03-21 | - |
| 14. Frontend V2 Components | 3/4 | Complete    | 2026-03-21 | - |
| 15. GitHub Actions CI | v2.0 | 0/? | Not started | - |
| 16. Real RAGAS Benchmark | v2.0 | 0/? | Not started | - |

Full v1.0 phase details archived at: `.planning/milestones/v1.0-ROADMAP.md`
