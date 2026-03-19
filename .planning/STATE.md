# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-18)

**Core value:** A student can upload their actual textbooks, set a real deadline, and have every note, chat answer, and quiz question grounded in — and only in — those specific books.
**Current focus:** Phase 3 — Retrieval Engine COMPLETE — Next: Phase 4 Study Agents

## Current Position

Phase: 3 of 7 (Retrieval Engine)
Plan: 3 of 3 in current phase
Status: Complete — all 3 plans done (03-01 Query Router, 03-02 Leaf Retrievers, 03-03 Hybrid Retriever)
Last activity: 2026-03-19 — Completed 03-03 Hybrid Retriever (RETR-05)

Progress: [████████░░] 43%

## Performance Metrics

**Velocity:**
- Total plans completed: 7
- Average duration: 3.4 min
- Total execution time: 0.4 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-infrastructure | 3/3 | 11 min | 3.7 min |
| 02-ingestion-pipeline | 4/5 | 8 min | 2 min |
| 03-retrieval-engine | 3/3 | 14 min | 4.7 min |

**Recent Trend:**
- Last 5 plans: 3.2 min
- Trend: —

*Updated after each plan completion*
| Phase 03-retrieval-engine P03 | 8 | 2 tasks | 2 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Dual retrieval (PageIndex + pgvector): PageIndex for chapter nav, pgvector for cross-book semantic search
- Router agent as classifier: LLM with structured output; ≥ 8/10 accuracy is a hard gate before chat agents
- LangGraph SqliteSaver: non-negotiable for session chat history survival across refreshes
- gpt-4o-mini: default LLM for cost efficiency across high-frequency agent calls
- SSE over WebSockets: simpler server-push for notes and chat streaming
- [Phase 01-infrastructure]: Used pgvector/pgvector:0.8.0-pg16 pinned version; DATABASE_URL uses service name db for container networking; synchronous SQLAlchemy engine in Phase 1 only
- [Phase 01-infrastructure]: node:20-alpine base image for minimal Dockerfile footprint in frontend service
- [Phase 01-infrastructure]: CMD npm run dev in frontend Dockerfile; docker-compose handles WATCHPACK_POLLING and anonymous volumes
- [Phase 01-infrastructure-03]: Phase 1 go/no-go gate passed — all three services healthy, pgvector active, git history clean
- [Phase 02-ingestion-pipeline-01]: Used autocommit=True on psycopg2 for CREATE EXTENSION in init_pgvector_schema; kept app.database get_engine for health check alongside db/database init functions
- [Phase 02-ingestion-pipeline-02]: asyncio.to_thread wraps entire sync psycopg2+OpenAI block; register_vector(conn) called immediately after connect(); module-level OpenAI client singleton
- [Phase 02-ingestion-pipeline-03]: Used httpx REST API directly — pageindex v0.1.0 package is empty stub; build_pageindex_tree outer try/except returns None on all failures
- [Phase 02-ingestion-pipeline-04]: UploadFile bytes read in endpoint before background task; GET /knowledge/ redirects from /knowledge (standard FastAPI behavior); pgvector delete in router wrapped in try/except
- [Phase 03-retrieval-engine-02]: Poll budget 18x5s=90s for PageIndex (30-90s on large docs); np.array required by pgvector adapter; embedding passed twice in SQL tuple for score + ORDER BY
- [Phase 03-retrieval-engine-01]: asyncio_mode=auto in pytest.ini fixes pytest-asyncio 0.23.0 crash on __init__.py; RouterDecision Field description carries per-strategy examples inline as classifier prompt; asyncio.to_thread bridges sync LangChain into async handlers
- [Phase 03-retrieval-engine]: model_copy(update={'relevance_score': score}) avoids mutating input RetrievedChunk objects in merge_results
- [Phase 03-retrieval-engine]: _get_sources_with_pageindex helper returns (doc_id, source_id, title) triples; separate from router's _get_pageindex_doc_ids which returns only doc_ids

### Pending Todos

None yet.

### Blockers/Concerns

- Router accuracy gate (≥ 8/10) must be passed at end of Phase 3 before Phase 4 agents begin

## Session Continuity

Last session: 2026-03-19
Stopped at: Completed 03-retrieval-engine-03-PLAN.md
Resume file: None
