# Roadmap: Scholar V1

## Overview

Scholar V1 is built in seven phases that mirror the PRD's 19 implementation steps. Infrastructure is laid first (Docker, PostgreSQL, pgvector, project scaffold), then ingestion, retrieval, agents, API, frontend, and finally a mandatory RAGAS evaluation that produces the portfolio artifact. Every phase delivers a coherent, independently verifiable capability before the next begins. The router accuracy gate (≥ 8/10) at Phase 3 is a hard checkpoint — Phase 4 agents do not begin until it is met.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Infrastructure** - Docker, PostgreSQL, pgvector, and project scaffold ready for development
- [ ] **Phase 2: Ingestion Pipeline** - PDF and URL ingestion into PageIndex and pgvector with status tracking
- [ ] **Phase 3: Retrieval Engine** - Router, PageIndex retriever, vector retriever, and hybrid retriever passing accuracy gate
- [ ] **Phase 4: Agents & Orchestrator** - Planner, note generator, session chat, and quiz agents with LangGraph + LangSmith
- [ ] **Phase 5: API Layer** - All remaining API endpoints (goals, sessions, chat, quiz) wired and testable
- [ ] **Phase 6: Frontend** - Next.js UI: knowledge page, goal form, goal detail, study session with SSE streaming
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
**Plans**: TBD

Plans:
- [ ] 01-01: Docker Compose + PostgreSQL + pgvector setup
- [ ] 01-02: FastAPI scaffold with health endpoint, SQLite init, and env config
- [ ] 01-03: Next.js 14 scaffold with Tailwind and project structure

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
**Plans**: TBD

Plans:
- [ ] 02-01: PDF extractor and URL extractor modules
- [ ] 02-02: Embedder and pgvector ingestion
- [ ] 02-03: PageIndex builder with fallback logic
- [ ] 02-04: Ingestion pipeline orchestrator and /knowledge endpoints (upload, status, list, delete)

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
**Plans**: TBD

Plans:
- [ ] 03-01: Router agent with structured output + labelled test set
- [ ] 03-02: PageIndex retriever and vector retriever
- [ ] 03-03: Hybrid retriever with weighted reranking + retrieval integration tests

### Phase 4: Agents & Orchestrator
**Goal**: The full study session machinery works end-to-end — planner generates session plans, note generator streams grounded notes, chat agent streams context-only answers, quiz agent generates and scores MCQs, all traced in LangSmith, all state persisted via LangGraph SqliteSaver
**Depends on**: Phase 3
**Requirements**: GOAL-01, GOAL-02, GOAL-03, GOAL-04, SESS-01, SESS-02, SESS-03, SESS-04, CHAT-01, CHAT-02, CHAT-03, CHAT-04, OBS-01
**Success Criteria** (what must be TRUE):
  1. User creates a goal and receives a sequenced study plan where session count matches ceil(deadline_days / 7 * sessions_per_week)
  2. Starting a session triggers SSE-streamed notes that include page-level citations and complete without blocking
  3. Sending a chat message returns an SSE-streamed response that cites sources and refuses to answer from training data
  4. Chat history survives a full browser refresh (LangGraph SqliteSaver checkpoint)
  5. Every agent call (Planner, Note Generator, Chat, Quiz) appears in LangSmith with cost and latency per node
**Plans**: TBD

Plans:
- [ ] 04-01: Planner agent and LangGraph orchestrator with SqliteSaver
- [ ] 04-02: Note generator with SSE streaming and citation grounding
- [ ] 04-03: Session chat agent with SSE streaming, grounding enforcement, and history persistence
- [ ] 04-04: Quiz agent (generation, submission, scoring) and LangSmith tracing

### Phase 5: API Layer
**Goal**: All API endpoints for goals, sessions, chat, and quiz are implemented, wired to agents, and manually testable end-to-end via the FastAPI docs UI
**Depends on**: Phase 4
**Requirements**: QUIZ-01, QUIZ-02, QUIZ-03, QUIZ-04
**Success Criteria** (what must be TRUE):
  1. User can request a quiz for a completed session and receive 5 MCQ questions each with 4 options
  2. Each quiz question has one unambiguously correct answer and a plausible distractor set
  3. User can submit answers and receive a score (0.0–1.0) with per-question explanation
  4. After submission, the session is marked complete with the quiz score stored, and the goal progress updates
**Plans**: TBD

Plans:
- [ ] 05-01: Quiz endpoints (generate, submit, score) wired to quiz agent
- [ ] 05-02: Goal and session endpoints (create goal, get plan, session status) — remaining API surface

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
**Plans**: TBD

Plans:
- [ ] 06-01: Knowledge base page (upload, URL, status pills, polling)
- [ ] 06-02: Goal creation form and goal detail page (progress bar, session cards)
- [ ] 06-03: Study session page with three-panel layout and SSE integration (notes + chat)
- [ ] 06-04: Quiz panel UI (MCQ render, answer submit, results, Complete Session)

### Phase 7: Evaluation
**Goal**: RAGAS benchmark is run against 30 labelled Q&A pairs, results are committed, and the README displays a comparison table — the portfolio artifact is complete
**Depends on**: Phase 6
**Requirements**: EVAL-01, EVAL-02, EVAL-03
**Success Criteria** (what must be TRUE):
  1. 30 Q&A pairs (10 deep / 10 broad / 10 intermediate) from OpenStax Biology 2e are answered using both PageIndex and vector strategies
  2. RAGAS scores (faithfulness, answer_relevancy, context_precision, avg_latency_ms) are committed as JSON to eval/results/
  3. README contains a comparison table showing PageIndex vs vector results for all four metrics
**Plans**: TBD

Plans:
- [ ] 07-01: RAGAS eval script, 30 Q&A pair dataset, and benchmark run
- [ ] 07-02: Commit results JSON and update README comparison table

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure | 0/3 | Not started | - |
| 2. Ingestion Pipeline | 0/4 | Not started | - |
| 3. Retrieval Engine | 0/3 | Not started | - |
| 4. Agents & Orchestrator | 0/4 | Not started | - |
| 5. API Layer | 0/2 | Not started | - |
| 6. Frontend | 0/4 | Not started | - |
| 7. Evaluation | 0/2 | Not started | - |
