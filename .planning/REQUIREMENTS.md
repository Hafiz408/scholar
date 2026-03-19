# Requirements: Scholar V1

**Defined:** 2026-03-18
**Core Value:** A student can upload their actual textbooks, set a real deadline, and have every note, chat answer, and quiz question grounded in — and only in — those specific books.

## v1 Requirements

### Ingestion

- [x] **INGEST-01**: User can upload a PDF (up to 50MB) and have it ingested into both PageIndex and pgvector
- [x] **INGEST-02**: User can submit a URL and have its text extracted and ingested into both PageIndex and pgvector
- [x] **INGEST-03**: User can poll ingestion status (pending → indexing_pageindex → indexing_vectors → ready → failed)
- [x] **INGEST-04**: Ingestion completes even when PageIndex fails — falls back to vector-only (pageindex_doc_id = None)
- [x] **INGEST-05**: User can list all knowledge sources with their current status
- [x] **INGEST-06**: User can delete a knowledge source (removes from pgvector + PageIndex + SQLite)

### Retrieval

- [x] **RETR-01**: Router agent classifies each query as pageindex / vector / hybrid with ≥ 8/10 accuracy on labelled test set
- [x] **RETR-02**: Router falls back to "vector" strategy when no pageindex_doc_id is available for any source
- [x] **RETR-03**: PageIndex retriever fetches chapter-level chunks from books that have a PageIndex tree
- [x] **RETR-04**: Vector retriever performs cosine similarity search filtered by source_id against pgvector
- [x] **RETR-05**: Hybrid retriever merges PageIndex + vector results with weighted reranking (0.6 / 0.4), deduplicated by content hash

### Goals & Planning

- [x] **GOAL-01**: User can create a study goal with title, topic, deadline (days), level, sessions/week, and knowledge source selection
- [x] **GOAL-02**: Planner agent generates a sequenced multi-session study plan (session count = ceil(deadline_days / 7 * sessions_per_week))
- [x] **GOAL-03**: Each session in the plan has a title, topic, estimated_minutes, and sequential session_number
- [x] **GOAL-04**: User can retrieve a goal's full study plan including session statuses

### Session — Notes

- [x] **SESS-01**: User can start a session, triggering SSE-streamed note generation grounded in retrieved context
- [x] **SESS-02**: Notes stream via SSE notes_chunk events — never blocks waiting for full generation
- [x] **SESS-03**: Every factual claim in notes cites source book title and page number
- [x] **SESS-04**: Notes are persisted in SQLite after generation completes

### Session — Chat

- [x] **CHAT-01**: User can send a chat message and receive an SSE-streamed response grounded in retrieved context
- [x] **CHAT-02**: Chat agent answers ONLY from provided context — refuses to answer from training data
- [x] **CHAT-03**: Each chat response includes citation chunks referencing source book and page
- [x] **CHAT-04**: Full chat history is persisted in LangGraph state (SqliteSaver) — survives browser refresh

### Session — Quiz

- [x] **QUIZ-01**: User can generate a 5-question MCQ quiz for a session, grounded in session notes and retrieved context
- [x] **QUIZ-02**: Each question has 4 options with one unambiguously correct answer and a plausible distractor set
- [x] **QUIZ-03**: User can submit quiz answers and receive a score (0.0–1.0) with per-question explanation
- [x] **QUIZ-04**: Quiz score is stored in study_sessions.quiz_score; session is marked complete after submission

### Observability

- [x] **OBS-01**: Every agent call (Planner, Note Generator, Session Chat, Quiz Agent) is traced in LangSmith with cost and latency

### API Integration

- [ ] **API-INT-01**: End-to-end integration tests verify the full API surface (POST /goals → GET /goals/{id} → POST /sessions/{id}/start → POST /sessions/{id}/quiz/generate → POST /sessions/{id}/quiz/submit) passes without errors; quiz_questions table DDL is in SQLITE_SCHEMA (not via ALTER TABLE workaround)

### Frontend

- [ ] **FE-01**: Knowledge base page: drag-and-drop PDF upload + URL field, source list with status pills, polling during ingestion
- [ ] **FE-02**: Goal creation form: title, topic, source multi-select, deadline dropdown, level radio, sessions/week selector
- [ ] **FE-03**: Goal detail page: progress bar, session card list with locked/available/in-progress/complete states and quiz score badges
- [ ] **FE-04**: Study session page: three-panel layout — Notes (react-markdown with citations), Chat (SSE streaming + citation chips), Quiz (MCQ → results → Complete Session)
- [ ] **FE-05**: SSE streaming integrated for both chat (token events) and notes (notes_chunk events)

### Evaluation

- [ ] **EVAL-01**: RAGAS benchmark run on 30 Q&A pairs from OpenStax Biology 2e (10 deep / 10 broad / 10 intermediate)
- [ ] **EVAL-02**: Benchmark results committed to eval/results/ as JSON files
- [ ] **EVAL-03**: README displays RAGAS comparison table (PageIndex vs vector: faithfulness, answer_relevancy, context_precision, avg_latency_ms)

## v2 Requirements

### Multimodal Ingestion
- **MM-01**: System can ingest diagrams and charts from PDFs using vision models
- **MM-02**: System can ingest equations from PDFs

### Adaptive Learning
- **ADAPT-01**: System adjusts study plan based on quiz scores
- **ADAPT-02**: System generates cumulative final test on goal completion

### Platform
- **PLAT-01**: ePub format support for ingestion
- **PLAT-02**: Production deployment on Fly.io / Vercel
- **PLAT-03**: CI/CD GitHub Actions pipeline
- **PLAT-04**: MCP: Notion export for notes

### Extended Features
- **EXT-01**: Super agent — cross-KB chat outside of study sessions
- **EXT-02**: OAuth / social login

## Out of Scope

| Feature | Reason |
|---------|--------|
| Vision-based multimodal ingestion | High complexity, requires separate pipeline — V2 |
| Adaptive replanning from quiz scores | Requires evaluation data to exist first — V2 |
| Final cumulative goal test | Needs completion signal design — V2 |
| Super agent (cross-KB chat) | Out of session scope — V2 |
| MCP Notion export | Adds external dependency — V2 |
| CI/CD pipeline | Deployment-layer concern — V2 |
| Production deployment | Local dev first — V2 |
| ePub support | PDF/URL covers core use case — V2 |
| OAuth / social login | Personal study tool, email not needed in V1 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INGEST-01 | Phase 2 | Complete |
| INGEST-02 | Phase 2 | Complete |
| INGEST-03 | Phase 2 | Complete |
| INGEST-04 | Phase 2 | Complete |
| INGEST-05 | Phase 2 | Complete |
| INGEST-06 | Phase 2 | Complete |
| RETR-01 | Phase 3 | Complete |
| RETR-02 | Phase 3 | Complete |
| RETR-03 | Phase 3 | Complete |
| RETR-04 | Phase 3 | Complete |
| RETR-05 | Phase 3 | Complete |
| GOAL-01 | Phase 4 | Complete |
| GOAL-02 | Phase 4 | Complete |
| GOAL-03 | Phase 4 | Complete |
| GOAL-04 | Phase 4 | Complete |
| SESS-01 | Phase 4 | Complete |
| SESS-02 | Phase 4 | Complete |
| SESS-03 | Phase 4 | Complete |
| SESS-04 | Phase 4 | Complete |
| CHAT-01 | Phase 4 | Complete |
| CHAT-02 | Phase 4 | Complete |
| CHAT-03 | Phase 4 | Complete |
| CHAT-04 | Phase 4 | Complete |
| QUIZ-01 | Phase 4 | Complete |
| QUIZ-02 | Phase 4 | Complete |
| QUIZ-03 | Phase 4 | Complete |
| QUIZ-04 | Phase 4 | Complete |
| OBS-01 | Phase 4 | Complete |
| API-INT-01 | Phase 5 | Pending |
| FE-01 | Phase 6 | Pending |
| FE-02 | Phase 6 | Pending |
| FE-03 | Phase 6 | Pending |
| FE-04 | Phase 6 | Pending |
| FE-05 | Phase 6 | Pending |
| EVAL-01 | Phase 7 | Pending |
| EVAL-02 | Phase 7 | Pending |
| EVAL-03 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 37 total
- Mapped to phases: 37
- Phase 1 (Infrastructure): 0 requirements (foundational scaffold — no direct user-facing requirements)
- Phase 2 (Ingestion Pipeline): 6 requirements
- Phase 3 (Retrieval Engine): 5 requirements
- Phase 4 (Agents & Orchestrator): 17 requirements (GOAL-01–04, SESS-01–04, CHAT-01–04, QUIZ-01–04, OBS-01)
- Phase 5 (API Layer): 1 requirement (API-INT-01)
- Phase 6 (Frontend): 5 requirements
- Phase 7 (Evaluation): 3 requirements
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-18*
*Last updated: 2026-03-19 — QUIZ-01 through QUIZ-04 moved from Phase 5 to Phase 4 (implemented in 04-04-PLAN.md); API-INT-01 added as Phase 5 requirement*
