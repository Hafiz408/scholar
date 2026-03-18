---
phase: 02-ingestion-pipeline
plan: "02"
subsystem: backend-ingestion
tags: [embedder, pgvector, openai, langchain, chunking, psycopg2]

requires:
  - phase: 02-01-foundation
    provides: pgvector-schema, config-phase2, psycopg2 connection pattern
provides:
  - embed_and_store async function (chunking + batch embedding + pgvector upsert)
  - delete_chunks_for_source synchronous helper
affects: [02-03-pageindex-builder, 02-04-pipeline, 02-05-knowledge-router, 03-retrieval]

tech-stack:
  added: [langchain-text-splitters, numpy (pre-installed), pgvector.psycopg2.register_vector]
  patterns: [asyncio-to-thread for sync psycopg2 in async context, register_vector before vector SQL, batch-50 OpenAI embeddings]

key-files:
  created: []
  modified:
    - backend/app/ingestion/embedder.py

key-decisions:
  - "Used asyncio.to_thread to wrap entire psycopg2 block so async FastAPI routes are not blocked by synchronous DB and OpenAI calls"
  - "register_vector(conn) called immediately after psycopg2.connect() — required before any vector SQL or psycopg2 raises type adaptation error"
  - "Module-level openai_client = OpenAI(api_key=settings.openai_api_key) instantiated once at import time for connection reuse"

patterns-established:
  - "asyncio.to_thread pattern: wrap entire sync I/O block (not individual calls) for correct event loop safety"
  - "register_vector pattern: always call register_vector(conn) right after psycopg2.connect() when working with pgvector"
  - "Batch embedding: collect content strings, send one embeddings.create() call per batch of 50, zip results with chunks"

requirements-completed: [INGEST-01, INGEST-02]

duration: 2min
completed: 2026-03-18
---

# Phase 2 Plan 02: Embedder — Chunking, Batch Embedding, and pgvector Upsert Summary

**Async embedder with RecursiveCharacterTextSplitter (600/100), OpenAI text-embedding-3-small in batches of 50, and psycopg2+register_vector upsert into knowledge_chunks pgvector table**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-18T00:00:00Z
- **Completed:** 2026-03-18
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- `embed_and_store` async function: accepts pages list, source_id, source_title; chunks with RecursiveCharacterTextSplitter(600/100); embeds in batches of 50 via OpenAI; upserts into knowledge_chunks with ON CONFLICT update; returns total chunk count
- `delete_chunks_for_source` synchronous helper: deletes all knowledge_chunks rows for a source_id; used by delete endpoint on knowledge source removal
- Proper async safety: all synchronous psycopg2 and OpenAI calls wrapped in `asyncio.to_thread` to avoid blocking FastAPI event loop

## Task Commits

1. **Task 1: Implement embedder.py** - `1a2e534` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `backend/app/ingestion/embedder.py` - Full embedder module with embed_and_store, delete_chunks_for_source, and _chunk_pages helper

## Decisions Made

- Used `asyncio.to_thread` wrapping the entire `_embed_and_store_sync` function — this is cleaner than wrapping individual calls and ensures the DB connection lifecycle stays within a single thread.
- `register_vector(conn)` is called immediately after `psycopg2.connect()` before any SQL execution — this is required by pgvector.psycopg2 to register the vector type adapter.
- Module-level `openai_client` singleton instantiated once at import time rather than per-call to avoid repeated client construction overhead.

## Deviations from Plan

None — plan executed exactly as written. All imports, function signatures, SQL, and batch logic matched the plan specification.

## Issues Encountered

None — `langchain-text-splitters` and `numpy` were already installed in the container as transitive dependencies of `langchain==0.3.0` and other packages.

## User Setup Required

None — no external service configuration required for this plan. (OpenAI API key is already in .env from prior phase setup.)

## Next Phase Readiness

- `embed_and_store` and `delete_chunks_for_source` are ready for use by the ingestion pipeline (02-04) and knowledge router (02-05)
- Plan 02-03 (PageIndex builder) can proceed independently as it does not depend on this module
- The knowledge_chunks table and pgvector index are confirmed functional via register_vector verification

---
*Phase: 02-ingestion-pipeline*
*Completed: 2026-03-18*
