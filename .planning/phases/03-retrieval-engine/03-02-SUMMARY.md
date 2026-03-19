---
phase: 03-retrieval-engine
plan: "02"
subsystem: retrieval
tags: [pageindex, pgvector, cosine-similarity, async, httpx, embeddings]
dependency_graph:
  requires:
    - backend/app/config.py (settings.pageindex_base_url, pageindex_api_key, embedding_model, database_url)
    - backend/app/models/schemas.py (RetrievedChunk)
    - backend/app/ingestion/embedder.py (pattern reference for _get_embedding_client)
  provides:
    - backend/app/retrieval/pageindex_retriever.py (fetch_pageindex_chunks, _parse_retrieved_nodes)
    - backend/app/retrieval/vector_retriever.py (vector_search, embed_query, _vector_search_sync)
  affects:
    - backend/app/retrieval/hybrid_retriever.py (03-03 — will call both leaf retrievers)
tech_stack:
  added: []
  patterns:
    - asyncio.to_thread wrapping all synchronous HTTP and DB calls
    - Module-level _get_embedding_client pattern reused from embedder.py
    - numpy.ndarray required by pgvector psycopg2 adapter (not plain list)
    - embedding passed twice in SQL param tuple (score + ORDER BY)
key_files:
  created: []
  modified:
    - backend/app/retrieval/pageindex_retriever.py
    - backend/app/retrieval/vector_retriever.py
decisions:
  - "Poll budget 18x5s=90s chosen to match research finding that PageIndex takes 30-90s on large docs"
  - "query_embedding passed as np.array twice in SQL tuple — pgvector adapter requires ndarray; ORDER BY needs bound parameter"
  - "Both retrievers return [] (not raise) on all failure paths — hybrid retriever relies on this contract"
metrics:
  duration: "3 min"
  completed_date: "2026-03-19"
  tasks_completed: 2
  files_modified: 2
---

# Phase 03 Plan 02: Leaf Retrievers (PageIndex + Vector) Summary

**One-liner:** PageIndex submit-poll-parse retriever and pgvector cosine similarity retriever, both returning RetrievedChunk lists with graceful empty-list fallbacks.

## What Was Built

Two independent leaf retrievers that serve as the data-fetching primitives for the hybrid retriever (03-03):

**pageindex_retriever.py** (`fetch_pageindex_chunks` — RETR-03):
- None doc_id guard returns [] immediately (URL sources have no PageIndex doc)
- POST /retrieval/ to submit task, extract retrieval_id
- Poll GET /retrieval/{retrieval_id}/ every 5 s for up to 18 attempts (90 s budget)
- On completion: _parse_retrieved_nodes maps retrieved_nodes flat structure to RetrievedChunk list
- page_index field maps to page_number; outer node index (rank) drives relevance_score = 1/(1+rank)
- All exceptions caught at the outer try/except — always returns []

**vector_retriever.py** (`vector_search` — RETR-04):
- embed_query: builds OpenAI-compatible client from settings (same _get_embedding_client pattern as embedder.py)
- _vector_search_sync: psycopg2 connect + register_vector, executes cosine SQL with 4-param tuple
- SQL: `1 - (embedding <=> %s)` for score, `ANY(%s)` for source_id filter, `embedding <=> %s` for ORDER BY, LIMIT %s
- embedding passed as np.array (pgvector adapter requirement); passed twice in param tuple
- empty source_ids guard returns [] without DB call
- rows mapped to RetrievedChunk with retrieval_method="vector"

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | pageindex_retriever.py — submit+poll+parse (RETR-03) | 060c575 | backend/app/retrieval/pageindex_retriever.py |
| 2 | vector_retriever.py — cosine similarity SQL (RETR-04) | 8e169e6 | backend/app/retrieval/vector_retriever.py |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

## Self-Check: PASSED

- backend/app/retrieval/pageindex_retriever.py: FOUND
- backend/app/retrieval/vector_retriever.py: FOUND
- .planning/phases/03-retrieval-engine/03-02-SUMMARY.md: FOUND
- commit 060c575: FOUND
- commit 8e169e6: FOUND
