# Scholar V1

## What This Is

Scholar is a goal-driven AI study system that turns uploaded textbooks and web documents into a persistent, intelligent knowledge base, then uses that knowledge base to power structured multi-session study plans. Users upload PDFs or URLs, set a study goal with a deadline, and Scholar generates a session-by-session plan — each session delivers AI-grounded notes, conversational Q&A, and a knowledge quiz.

## Core Value

A student can upload their actual textbooks, set a real deadline, and have every note, chat answer, and quiz question grounded in — and only in — those specific books.

## Requirements

### Validated

(None yet — ship to validate)

### Active

**Ingestion Pipeline**
- [ ] User can upload PDF (up to 50MB) and have it ingested into both PageIndex and pgvector
- [ ] User can submit a URL and have its text ingested into both PageIndex and pgvector
- [ ] Ingestion status is queryable (pending → indexing_pageindex → indexing_vectors → ready)
- [ ] Failed PageIndex ingestion falls back to vector-only (never blocks the user)

**Dual Retrieval**
- [ ] Router agent classifies each query as pageindex / vector / hybrid (≥ 8/10 accuracy)
- [ ] PageIndex retriever fetches chapter-level chunks from books with a PageIndex tree
- [ ] Vector retriever performs cosine similarity search across pgvector for cross-book queries
- [ ] Hybrid retriever merges both sources with weighted reranking (PageIndex 0.6, vector 0.4)

**Goal & Study Plan**
- [ ] User can create a study goal with topic, deadline, level, sessions/week, and source selection
- [ ] Planner agent generates a sequenced multi-session study plan (foundational → advanced)
- [ ] Study plan and all sessions are persisted in SQLite

**Study Session — Notes**
- [ ] Note generator produces grounded markdown notes for each session topic via retrieval
- [ ] Notes stream via SSE (notes_chunk events) — never block on a 60-second generation
- [ ] Every factual claim in notes cites the source book and page number

**Study Session — Chat**
- [ ] Session chat agent answers questions grounded only in retrieved context
- [ ] Chat streams via SSE (token + citations events)
- [ ] Full chat history persisted across browser refreshes via LangGraph SqliteSaver

**Study Session — Quiz**
- [ ] Quiz agent generates 5 MCQ questions per session grounded in notes + retrieved context
- [ ] User can submit quiz answers; score is evaluated and stored
- [ ] Session marked complete after quiz submission; progress visible on goal page

**Observability**
- [ ] Every agent call traced in LangSmith (cost and latency visible per node)

**Frontend**
- [ ] Knowledge base page: upload PDF/URL, list sources with status pills
- [ ] Goal creation form: topic, deadline, level, sessions/week, source multi-select
- [ ] Goal detail page: progress bar + session card list with status and quiz score
- [ ] Study session page: three-panel layout (notes, chat, quiz)
- [ ] SSE streaming integrated for chat and notes

**Evaluation**
- [ ] RAGAS benchmark run on 30 Q&A pairs from OpenStax Biology 2e
- [ ] Benchmark results committed to eval/results/ and displayed in README

### Out of Scope

- Vision-based multimodal ingestion (diagrams, equations) — V2
- Adaptive replanning based on quiz scores — V2
- Final cumulative goal completion test — V2
- Super agent (cross-KB chat outside sessions) — V2
- MCP: Notion export — V2
- CI/CD GitHub Actions pipeline — V2
- Production deployment (Fly.io / Vercel) — V2
- ePub format support — V2
- OAuth / social login — not needed for personal study tool

## Context

- Full PRD at `scholar_v1_prd.md` — all data models, API contracts, agent prompts, test plan, eval setup defined in detail
- Tech stack fully prescribed: FastAPI, LangChain 0.3+, LangGraph 0.2+, LangSmith, pgvector, pageindex Python client, Next.js 14, Tailwind
- Implementation order defined in PRD Section 16 (19 steps) — router accuracy is a hard gate at Step 8
- PageIndex API key required before Step 5 (pageindex_builder.py)
- LangGraph SqliteSaver checkpointing is non-negotiable — sessions must survive browser refresh
- Evaluation is non-optional — RAGAS numbers are the portfolio artifact

## Constraints

- **Tech Stack**: All choices prescribed in PRD — FastAPI, LangChain/LangGraph, pgvector, PageIndex, Next.js 14, gpt-4o-mini
- **Gate**: Router must reach ≥ 8/10 accuracy on labelled test set before chat agent is built
- **Security**: `.env` in `.gitignore` from commit 1; no hardcoded secrets ever
- **Chat grounding**: System prompt must enforce "Answer ONLY from provided context" — no training data answers
- **Streaming**: Notes and chat must both stream via SSE; never block on full generation
- **Evaluation**: RAGAS benchmark must be run and results committed — not optional

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Dual retrieval (PageIndex + pgvector) | PageIndex for deep chapter navigation, pgvector for cross-book semantic search | — Pending |
| Router agent as classifier | LLM with structured output classifies query type to pick retrieval strategy | — Pending |
| LangGraph SqliteSaver for session state | Sessions must survive browser refresh; SqliteSaver gives free checkpointing | — Pending |
| gpt-4o-mini as default LLM | Cost-efficient for high-frequency agent calls (notes, chat, quiz) | — Pending |
| RAGAS as evaluation framework | Head-to-head PageIndex vs vector comparison is the central portfolio artifact | — Pending |
| SSE for streaming (not WebSockets) | Notes and chat must stream progressively; SSE is simpler than WS for server-push | — Pending |

---
*Last updated: 2026-03-18 after initialization*
