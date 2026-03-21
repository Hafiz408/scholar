# Requirements: Scholar V2

**Defined:** 2026-03-21
**Core Value:** A student can upload their actual textbooks, set a real deadline, and have every note, chat answer, and quiz question grounded in — and only in — those specific books.

## v2 Requirements

### Observability (OBS)

- [x] **OBS-01**: LangSmith traces visible for all agent calls (planner, chat, quiz, all V2 agents)
- [x] **OBS-02**: `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT` injected into env at startup when key is set

### Vision Ingestion (VIS)

- [x] **VIS-01**: `get_vision_llm()` added to `llm_factory.py` using `vision_model` setting — raises `ValueError` if vision_model is empty
- [x] **VIS-02**: `vision_extractor.py` extracts diagram/chart/table/equation descriptions from image-heavy PDF pages via vision LLM
- [x] **VIS-03**: Vision extraction is opt-in — `vision_model=""` means no LLM call, ingestion continues unchanged
- [x] **VIS-04**: Vision extraction never blocks ingestion — exceptions are logged, pipeline continues
- [x] **VIS-05**: `pipeline.py` calls vision extractor after text extraction; appends visual descriptions to page text
- [x] **VIS-06**: `vision_max_pages` config setting caps pages processed per document (cost guard)

### Adaptive Learning (ADP)

- [x] **ADP-01**: `adaptive_planner.py` generates a follow-up session when quiz score < 65%
- [x] **ADP-02**: Follow-up session inserted immediately after the completed session (other session numbers incremented)
- [x] **ADP-03**: Quiz submission response includes `followup_session_added` and `followup_session` fields
- [x] **ADP-04**: Adaptive planner wrapped in try/except — quiz submission succeeds even if planner errors
- [x] **ADP-05**: `POST /goals/{id}/adapt` endpoint for manual adaptive replanning

### Final Test (TST)

- [x] **TST-01**: `test_agent.py` generates cross-session MCQ test (1-2 questions per completed session, max 15 total)
- [x] **TST-02**: Test questions grounded in retrieved context (not training data)
- [x] **TST-03**: `cumulative_tests` SQLite table created via migration
- [x] **TST-04**: `POST /goals/{id}/test/generate` returns test only when all sessions complete (400 otherwise)
- [x] **TST-05**: `POST /goals/{id}/test/submit` scores answers; score ≥ 70% → goal status = `complete`
- [x] **TST-06**: Submit response includes `weak_session_numbers` (sessions with < 50% correct)

### Super Agent (SUP)

- [x] **SUP-01**: `super_agent.py` retrieves context from ALL ready knowledge sources (not session-scoped)
- [x] **SUP-02**: Empty knowledge base returns SSE error event "No books indexed yet" (no crash)
- [x] **SUP-03**: `thread_id` comes from frontend (localStorage UUID) — never generated server-side
- [x] **SUP-04**: `POST /super/chat/stream` SSE endpoint with same event format as `/chat/stream`

### Notion Export (NTN)

- [ ] **NTN-01**: `notion_mcp.py` creates goal page and session child pages via Notion API
- [x] **NTN-02**: Empty `notion_api_key` → error returned immediately, no HTTP call
- [ ] **NTN-03**: HTTP 429 retried with exponential backoff (1s, 2s, 4s — max 3 retries)
- [x] **NTN-04**: `notion_page_url` column added to `study_goals` SQLite table
- [ ] **NTN-05**: `POST /goals/{id}/export/notion` is a `BackgroundTask` — returns `{"status": "export_started"}` immediately

### Orchestrator (ORC)

- [x] **ORC-01**: `ScholarState` expanded with V2 fields (`sessions_complete`, `weak_session_ids`, `followup_sessions_added`, `final_test_id`, `goal_complete`)
- [x] **ORC-02**: `update_goal_progress()` function added to orchestrator

### Frontend (FE)

- [ ] **FE-01**: `/super` page with full-height chat, `thread_id` from localStorage, source count in header
- [ ] **FE-02**: Super agent page linked in main navigation sidebar
- [ ] **FE-03**: `AdaptiveAlert.tsx` — dismissible banner shown when follow-up session added
- [ ] **FE-04**: `TestPanel.tsx` — "Take Final Test" shown when all sessions complete; confetti on pass
- [ ] **FE-05**: `NotionExportButton.tsx` — polls for `notion_page_url` after export starts

### CI/CD (CI)

- [ ] **CI-01**: `.github/workflows/ci.yml` runs pytest + ruff on PRs to `feature/v2` and `main`
- [ ] **CI-02**: `test_router_accuracy_gate.py` excluded from CI (requires live LLM)
- [ ] **CI-03**: CI uses PostgreSQL service container for integration tests

### Evaluation (EVAL)

- [ ] **EVAL-01**: `eval/run_ragas.py` updated with `--output-dir` argument and summary table output
- [ ] **EVAL-02**: Real RAGAS benchmark run with OpenStax Biology 2e; JSON results committed to `eval/results/`
- [ ] **EVAL-03**: README comparison table updated with real faithfulness, answer relevancy, context precision, and avg latency scores

## Out of Scope (V3)

| Feature | Reason |
|---------|--------|
| Production deployment (Fly.io / Vercel) | V3 — infrastructure not needed for V2 validation |
| ePub format support | V3 — PDF + URL sufficient for V2 |
| Spaced repetition scheduling | V3 — complex scheduling out of V2 scope |
| Progress analytics dashboard | V3 — deferred |
| Multi-user / auth | V3 — personal tool for now |
| OAuth / social login | Not needed for personal study tool |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| OBS-01 | Phase 8 | Complete |
| OBS-02 | Phase 8 | Complete |
| VIS-01 | Phase 9 | Complete |
| VIS-02 | Phase 9 | Complete |
| VIS-03 | Phase 9 | Complete |
| VIS-04 | Phase 9 | Complete |
| VIS-05 | Phase 9 | Complete |
| VIS-06 | Phase 9 | Complete |
| ADP-01 | Phase 10 | Complete |
| ADP-02 | Phase 10 | Complete |
| ADP-03 | Phase 10 | Complete |
| ADP-04 | Phase 10 | Complete |
| ADP-05 | Phase 10 | Complete |
| TST-01 | Phase 11 | Complete |
| TST-02 | Phase 11 | Complete |
| TST-03 | Phase 11 | Complete |
| TST-04 | Phase 11 | Complete |
| TST-05 | Phase 11 | Complete |
| TST-06 | Phase 11 | Complete |
| ORC-01 | Phase 11 | Complete |
| ORC-02 | Phase 11 | Complete |
| SUP-01 | Phase 12 | Complete |
| SUP-02 | Phase 12 | Complete |
| SUP-03 | Phase 12 | Complete |
| SUP-04 | Phase 12 | Complete |
| NTN-01 | Phase 13 | Pending |
| NTN-02 | Phase 13 | Complete |
| NTN-03 | Phase 13 | Pending |
| NTN-04 | Phase 13 | Complete |
| NTN-05 | Phase 13 | Pending |
| FE-01 | Phase 14 | Pending |
| FE-02 | Phase 14 | Pending |
| FE-03 | Phase 14 | Pending |
| FE-04 | Phase 14 | Pending |
| FE-05 | Phase 14 | Pending |
| CI-01 | Phase 15 | Pending |
| CI-02 | Phase 15 | Pending |
| CI-03 | Phase 15 | Pending |
| EVAL-01 | Phase 16 | Pending |
| EVAL-02 | Phase 16 | Pending |
| EVAL-03 | Phase 16 | Pending |

**Coverage:**
- v2 requirements: 39 total
- Mapped to phases: 39
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-21*
*Last updated: 2026-03-21 — traceability confirmed against ROADMAP.md Phase 8–16*
