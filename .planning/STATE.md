# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-18)

**Core value:** A student can upload their actual textbooks, set a real deadline, and have every note, chat answer, and quiz question grounded in — and only in — those specific books.
**Current focus:** Phase 6 — Frontend (complete — all 4 plans done)

## Current Position

Phase: 6 of 7 (Frontend)
Plan: 4 of 4 in current phase
Status: Phase 06 complete — QuizPanel MCQ flow, study session all three panels functional
Last activity: 2026-03-19 — Completed 06-04 QuizPanel (FE-04)

Progress: [█████████████] 86%

## Performance Metrics

**Velocity:**
- Total plans completed: 8
- Average duration: 3.6 min
- Total execution time: 0.5 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-infrastructure | 3/3 | 11 min | 3.7 min |
| 02-ingestion-pipeline | 4/5 | 8 min | 2 min |
| 03-retrieval-engine | 3/3 | 14 min | 4.7 min |
| 04-agents-orchestrator | 4/4 | 32 min | 8 min |
| 06-frontend | 4/4 | 9 min | 2.3 min |

**Recent Trend:**
- Last 5 plans: 5 min
- Trend: —

*Updated after each plan completion*
| Phase 03-retrieval-engine P03 | 8 | 2 tasks | 2 files |
| Phase 04-agents-orchestrator P01 | 15 | 3 tasks | 9 files |
| Phase 04-agents-orchestrator P02 | 8 | 2 tasks | 2 files |
| Phase 04-agents-orchestrator P03 | 2 | 2 tasks | 2 files |
| Phase 04-agents-orchestrator P04 | 7 | 2 tasks | 3 files |
| Phase 06-frontend P01 | 4 | 2 tasks | 6 files |
| Phase 06-frontend P02 | 2 | 2 tasks | 5 files |
| Phase 06-frontend P03 | 1 | 2 tasks | 3 files |
| Phase 06-frontend P04 | 2 | 2 tasks | 2 files |

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
- [Phase 04-agents-orchestrator-01]: AsyncSqliteSaver imported inside lifespan body (not module-level); study_goals uses knowledge_source_ids column; stub routers given minimal router objects so all four can be registered in main.py now
- [Phase 04-agents-orchestrator]: knowledge_source_ids column used in sessions JOIN query — plan template used source_ids but actual SQLite schema uses knowledge_source_ids
- [Phase 04-agents-orchestrator]: streaming=True in ChatOpenAI constructor required alongside .astream() — prevents full-response buffering in note_generator
- [Phase 04-agents-orchestrator-03]: chat router uses prefix=/sessions — coexists with sessions router under same prefix; goal_id used as LangGraph thread_id for per-goal history isolation
- [Phase 04-agents-orchestrator-03]: Defensive import fallback for Checkpoint/CheckpointMetadata: base -> types -> plain dict handles langgraph version differences
- [Phase 04-agents-orchestrator-04]: QuizQuestionPublic model strips correct_index at HTTP layer — security boundary explicit in router, not agent; router prefix=/sessions (not /quiz) to match /sessions/{id}/quiz/* paths; ALTER TABLE guard pattern for idempotent SQLite column additions
- [Phase 05-api-layer-01]: pythonpath = . in pytest.ini resolves app.* imports without __init__.py — pytest-asyncio 0.23.0 + asyncio_mode=auto crashes on Package collector when __init__.py present
- [Phase 05-api-layer-01]: quiz_questions normalized table additive; study_sessions.quiz_questions TEXT column + ALTER TABLE guard retained for live DB backward compat
- [Phase 05-api-layer-01]: GET /goals/{goal_id} response shape is {goal: {...}, sessions: [...]} — goal_id nested at data["goal"]["id"], not data["goal_id"]
- [Phase 06-frontend-01]: @microsoft/fetch-event-source required — both /sessions/{id}/start and /sessions/{id}/chat are POST endpoints; native EventSource (GET-only) cannot be used
- [Phase 06-frontend-01]: Quiz endpoints are /sessions/{session_id}/quiz/generate and /sessions/{session_id}/quiz/submit (prefix /sessions, not /quiz) — matches Phase 4 router decisions
- [Phase 06-frontend-01]: CreateGoalRequest and QuizSubmissionRequest defined in api.ts (not types/index.ts) — they mirror backend Pydantic models, not frontend domain types
- [Phase 06-frontend-02]: createGoal called with source_ids (not knowledge_source_ids) — backend goals.py CreateGoalRequest uses source_ids as field name
- [Phase 06-frontend-02]: Redirect after goal creation uses studyPlan.goal.id — getGoalPlan returns {goal: StudyGoal, sessions: [...]} so goal ID is nested at .goal.id
- [Phase 06-frontend-02]: goals/[id]/page.tsx is 'use client' with useEffect data fetch — params.id accessed synchronously per Next.js 14 pattern
- [Phase 06-frontend]: source_title used in citation chips — RetrievedChunk has source_title not title per types/index.ts
- [Phase 06-frontend]: selectedAnswers stores option index (number) — QuizSubmissionRequest is Record<string, number> (question_id -> index)
- [Phase 06-frontend]: per_question used for quiz results — QuizResult uses per_question with correct/question_id, not question_results/is_correct as plan spec assumed

### Pending Todos

None yet.

### Blockers/Concerns

None — Phase 6 complete. All four plans done. Ready for Phase 7 if applicable.

## Session Continuity

Last session: 2026-03-19
Stopped at: Completed 06-frontend-04-PLAN.md
Resume file: None
