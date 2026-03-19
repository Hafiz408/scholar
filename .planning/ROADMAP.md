# Roadmap: Scholar V1

## Overview

Scholar V1 is built in seven phases that mirror the PRD's 19 implementation steps. Infrastructure is laid first (Docker, PostgreSQL, pgvector, project scaffold), then ingestion, retrieval, agents, API, frontend, and finally a mandatory RAGAS evaluation that produces the portfolio artifact. Every phase delivers a coherent, independently verifiable capability before the next begins. The router accuracy gate (≥ 8/10) at Phase 3 is a hard checkpoint — Phase 4 agents do not begin until it is met.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Infrastructure** - Docker, PostgreSQL, pgvector, and project scaffold ready for development
- [x] **Phase 2: Ingestion Pipeline** - PDF and URL ingestion into PageIndex and pgvector with status tracking
- [x] **Phase 3: Retrieval Engine** - Router, PageIndex retriever, vector retriever, and hybrid retriever passing accuracy gate (completed 2026-03-19)
- [x] **Phase 4: Agents & Orchestrator** - Planner, note generator, session chat, and quiz agents with LangGraph + LangSmith (completed 2026-03-19)
- [x] **Phase 5: API Layer** - quiz_questions schema gap + end-to-end integration tests covering the full API surface (completed 2026-03-19)
- [x] **Phase 6: Frontend** - Next.js UI: knowledge page, goal form, goal detail, study session with SSE streaming (completed 2026-03-19)
- [ ] **Phase 7: Evaluation** - RAGAS benchmark on 30 Q&A pairs; results committed and README updated

## Phase Details

### Phase 1: Infrastructure
**Goal**: A fully containerised development environment exists — FastAPI, PostgreSQL with pgvector, and Next.js scaffold all run locally with a single `docker compose up`
**Depends on**: Nothing (first phase)
**Requirements**: None (foundational scaffold — no v1 user-facing requirements; enables all downstream phases)
**Success Criteria** (what must be TRUE):
  1. `docker compose up` starts all services (FastAPI, PostgreSQL, Next.js) without errors
  2. FastAPI health endpoint returns 200 and pgvector extension is confirmed active
  3. `.env` is gitignored from the first commit and no secrets appear in version history
  4. Project directory structure matches PRD layout (backend/, frontend/, eval/, .planning/)
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Docker Compose + PostgreSQL/pgvector setup + FastAPI scaffold with /health endpoint
- [x] 01-02-PLAN.md — Next.js 14 scaffold with Tailwind, App Router, and frontend Dockerfile
- [x] 01-03-PLAN.md — Integration boot: `docker compose up` verification + human approval gate

### Phase 2: Ingestion Pipeline
**Goal**: Users can upload PDFs and URLs and have them fully ingested into both PageIndex and pgvector, with live status polling and graceful fallback when PageIndex fails
**Depends on**: Phase 1
**Requirements**: INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05, INGEST-06
**Success Criteria** (what must be TRUE):
  1. User uploads a PDF (up to 50 MB) and the API returns a source ID; polling shows status progressing to "ready"
  2. User submits a URL and its extracted text appears in both PageIndex and pgvector
  3. If PageIndex ingestion fails, status reaches "ready" with pageindex_doc_id = None — the upload is never blocked
  4. User can list all knowledge sources and see their current status pill (pending / indexing / ready / failed)
  5. User can delete a source and it is removed from pgvector, PageIndex, and SQLite
**Plans**: 4 plans

Plans:
- [x] 02-01-PLAN.md — Config + pgvector schema init + FastAPI lifespan + PDF extractor + URL extractor
- [x] 02-02-PLAN.md — Embedder: chunking (600/100) + batch OpenAI embeddings + pgvector upsert
- [x] 02-03-PLAN.md — PageIndex builder with submit, poll, and graceful fallback to None
- [x] 02-04-PLAN.md — Pipeline orchestrator + /knowledge API (upload, status, list, delete)

### Phase 3: Retrieval Engine
**Goal**: The retrieval layer accurately classifies queries and returns grounded context chunks; router meets the ≥ 8/10 accuracy hard gate before any chat agent is built
**Depends on**: Phase 2
**Requirements**: RETR-01, RETR-02, RETR-03, RETR-04, RETR-05
**Success Criteria** (what must be TRUE):
  1. Router agent scores ≥ 8/10 on the labelled test set of pageindex / vector / hybrid queries
  2. Router falls back to "vector" strategy when no PageIndex doc IDs are available for the selected sources
  3. PageIndex retriever returns chapter-level chunks with book title and page number for sources that have a PageIndex tree
  4. Vector retriever returns cosine-similarity results filtered to the correct source IDs
  5. Hybrid retriever merges both result sets with 0.6/0.4 weighting and deduplicates by content hash
**Plans**: 3 plans

Plans:
- [ ] 03-01-PLAN.md — Router agent (RETR-01 + RETR-02): classify_query with RETR-02 fallback guard + 10-query labelled test set with ≥ 8/10 accuracy gate
- [ ] 03-02-PLAN.md — PageIndex retriever (RETR-03) + vector retriever (RETR-04): submit/poll/parse + cosine SQL with source_id filter
- [ ] 03-03-PLAN.md — Hybrid retriever (RETR-05): 0.6/0.4 weighted merge + content hash dedup + retrieve() orchestrator + integration tests

### Phase 4: Agents & Orchestrator
**Goal**: The full study session machinery works end-to-end — planner generates session plans, note generator streams grounded notes, chat agent streams context-only answers, quiz agent generates and scores MCQs, all traced in LangSmith, all state persisted via LangGraph SqliteSaver
**Depends on**: Phase 3
**Requirements**: GOAL-01, GOAL-02, GOAL-03, GOAL-04, SESS-01, SESS-02, SESS-03, SESS-04, CHAT-01, CHAT-02, CHAT-03, CHAT-04, QUIZ-01, QUIZ-02, QUIZ-03, QUIZ-04, OBS-01
**Success Criteria** (what must be TRUE):
  1. User creates a goal and receives a sequenced study plan where session count matches ceil(deadline_days / 7 * sessions_per_week)
  2. Starting a session triggers SSE-streamed notes that include page-level citations and complete without blocking
  3. Sending a chat message returns an SSE-streamed response that cites sources and refuses to answer from training data
  4. Chat history survives a full browser refresh (LangGraph SqliteSaver checkpoint)
  5. Every agent call (Planner, Note Generator, Chat, Quiz) appears in LangSmith with cost and latency per node
  6. User can generate a 5-question MCQ quiz for a session and submit answers to receive a scored result; session is marked complete
**Plans**: 4 plans

Plans:
- [x] 04-01-PLAN.md — Dependencies + AsyncSqliteSaver lifespan + prompts.py + Planner agent + Goal CRUD (GOAL-01, GOAL-02, GOAL-03, GOAL-04, OBS-01)
- [ ] 04-02-PLAN.md — Note Generator SSE streaming + POST /sessions/{session_id}/start endpoint (SESS-01, SESS-02, SESS-03, SESS-04)
- [ ] 04-03-PLAN.md — Session Chat agent SSE streaming + AsyncSqliteSaver history + POST /sessions/{session_id}/chat endpoint (CHAT-01, CHAT-02, CHAT-03, CHAT-04)
- [ ] 04-04-PLAN.md — Quiz Agent (generate + evaluate) + POST /quiz/generate and /quiz/submit endpoints (QUIZ-01, QUIZ-02, QUIZ-03, QUIZ-04)

### Phase 5: API Layer
**Goal**: quiz_questions table is properly defined in SQLITE_SCHEMA, and end-to-end integration tests verify the full API surface (goals → sessions → notes → quiz) passes without errors
**Depends on**: Phase 4
**Requirements**: API-INT-01
**Success Criteria** (what must be TRUE):
  1. quiz_questions table DDL exists in SQLITE_SCHEMA in database.py — no ALTER TABLE workaround needed at runtime
  2. pytest integration tests pass end-to-end: POST /goals → GET /goals/{id} → POST /sessions/{id}/start → POST /sessions/{id}/quiz/generate → POST /sessions/{id}/quiz/submit
  3. All integration tests run in the Docker backend container without LLM calls (mocked with pytest-mock or httpx test client)
**Plans**: 1 plan

Plans:
- [ ] 05-01-PLAN.md — quiz_questions SQLITE_SCHEMA DDL fix + pytest end-to-end integration tests for full API surface

### Phase 6: Frontend
**Goal**: The complete Next.js UI is functional — users can upload sources, create goals, run study sessions with streaming notes and chat, and complete quizzes, all from the browser
**Depends on**: Phase 5
**Requirements**: FE-01, FE-02, FE-03, FE-04, FE-05
**Success Criteria** (what must be TRUE):
  1. User can drag-and-drop a PDF or submit a URL on the knowledge page and watch the status pill update without refreshing
  2. User can fill the goal creation form and see a generated session card list on the goal detail page
  3. Goal detail page shows a live progress bar and session cards with correct locked/available/complete states and quiz score badges
  4. Study session page shows three panels — notes stream in as they generate, chat responds with citation chips, quiz flows to results and Complete Session
  5. Chat and notes both stream via SSE with no full-page block
**Plans**: 4 plans

Plans:
- [x] 06-01-PLAN.md — API client (lib/api.ts + lib/sse.ts) + knowledge base page (upload, URL, status pills, polling)
- [ ] 06-02-PLAN.md — Goal creation form + goal detail page (progress bar, session cards with states)
- [ ] 06-03-PLAN.md — Study session three-panel layout + SessionNotes (SSE) + ChatPanel (SSE + citations)
- [ ] 06-04-PLAN.md — Quiz panel (MCQ state machine, results, Complete Session flow)

### Phase 7: Evaluation
**Goal**: RAGAS benchmark is run against 30 labelled Q&A pairs, results are committed, and the README displays a comparison table — the portfolio artifact is complete
**Depends on**: Phase 6
**Requirements**: EVAL-01, EVAL-02, EVAL-03
**Success Criteria** (what must be TRUE):
  1. 30 Q&A pairs (10 deep / 10 broad / 10 intermediate) from OpenStax Biology 2e are answered using both PageIndex and vector strategies
  2. RAGAS scores (faithfulness, answer_relevancy, context_precision, avg_latency_ms) are committed as JSON to eval/results/
  3. README contains a comparison table showing PageIndex vs vector results for all four metrics
**Plans**: 2 plans

Plans:
- [ ] 07-01-PLAN.md — golden_qa.json (30 Q&A pairs) + run_ragas.py RAGAS 0.2 benchmark script implementation
- [ ] 07-02-PLAN.md — Run benchmark inside Docker, commit JSON results, update README comparison table

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure | 3/3 | Complete | 2026-03-18 |
| 2. Ingestion Pipeline | 4/4 | Complete | 2026-03-19 |
| 3. Retrieval Engine | 3/3 | Complete   | 2026-03-19 |
| 4. Agents & Orchestrator | 4/4 | Complete   | 2026-03-19 |
| 5. API Layer | 1/1 | Complete   | 2026-03-19 |
| 6. Frontend | 4/4 | Complete   | 2026-03-19 |
| 7. Evaluation | 1/2 | In Progress|  |
