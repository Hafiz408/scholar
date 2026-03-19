---
phase: 02-ingestion-pipeline
plan: "04"
subsystem: ingestion-api
tags: [pipeline, fastapi, background-tasks, sqlite, pgvector, pageindex]
one_liner: "5-stage ingestion orchestrator (pipeline.py) wired to /knowledge REST API (upload, status, list, delete)"

dependency_graph:
  requires:
    - 02-01  # SQLite schema + pgvector init
    - 02-02  # embed_and_store, delete_chunks_for_source
    - 02-03  # build_pageindex_tree, delete_pageindex_doc
  provides:
    - run_ingestion (BackgroundTask entrypoint)
    - POST /knowledge/upload (202)
    - GET /knowledge/{id}/status (200)
    - GET /knowledge/ (200 list)
    - DELETE /knowledge/{id} (204 cascade)
  affects:
    - backend/app/main.py (router wired in)

tech_stack:
  added:
    - aiosqlite (async SQLite in pipeline + router)
  patterns:
    - FastAPI BackgroundTasks for async ingestion without blocking HTTP response
    - File bytes read synchronously in endpoint; save_path passed to background task
    - asyncio.to_thread for all synchronous calls (extract_pdf, psycopg2 operations)
    - Outer try/except in pipeline.py ensures status always transitions (ready or failed)

key_files:
  created:
    - backend/app/ingestion/pipeline.py
    - backend/app/routers/knowledge.py
  modified:
    - backend/app/main.py

decisions:
  - "UploadFile bytes read in endpoint body before background task starts — stream is closed by task time"
  - "GET /knowledge route defined as '/' on the router; FastAPI redirects /knowledge → /knowledge/ (standard behavior)"
  - "delete_chunks_for_source wrapped in try/except in DELETE endpoint — pgvector failure logs but does not block SQLite cleanup"

metrics:
  duration_minutes: 2
  completed_date: "2026-03-19"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
---

# Phase 2 Plan 4: Ingestion Pipeline Wiring Summary

## What Was Built

5-stage ingestion pipeline orchestrator (`pipeline.py`) and the `/knowledge` REST API router, completing the full end-to-end ingestion path from HTTP upload to pgvector + SQLite storage.

## Tasks Completed

| # | Task | Commit | Key Files |
|---|------|--------|-----------|
| 1 | Implement pipeline.py 5-stage orchestrator | 556c71f | backend/app/ingestion/pipeline.py |
| 2 | Implement knowledge router + wire into main.py | d6cd4ac | backend/app/routers/knowledge.py, backend/app/main.py |

## Pipeline Stages

`run_ingestion(source_id, file_path, url, source_type, title)` — called as FastAPI BackgroundTask:

1. **Extract text**: PDF via `asyncio.to_thread(extract_pdf)` or URL via `await extract_url(url)`. Updates `page_count` in SQLite.
2. **PageIndex** (status: `indexing_pageindex`): `await build_pageindex_tree(file_path, title)` — returns `None` for URLs or on any failure; never raises.
3. **pgvector embedding** (status: `indexing_vectors`): `await embed_and_store(pages, source_id, title)`.
4. **Ready** (status: `ready`): writes `pageindex_doc_id` (may be `None`) and `status=ready`.
5. **Failure path**: outer `except` catches any unhandled error and sets `status=failed`.

## API Endpoints

| Method | Path | Status | Behavior |
|--------|------|--------|----------|
| POST | /knowledge/upload | 202 | Accept PDF or URL; start background ingestion |
| GET | /knowledge/{id}/status | 200/404 | Poll ingestion status |
| GET | /knowledge/ | 200 | List all sources DESC by created_at |
| DELETE | /knowledge/{id} | 204/404 | Cascade delete: pgvector → PageIndex (best-effort) → SQLite |

## Verification Results

- `POST /knowledge/upload -F "url=https://en.wikipedia.org/wiki/Photosynthesis"` → HTTP 202, source_id returned
- Background task ran: `page_count=38` was set (Stage 1 completed), status=`failed` due to missing OpenAI key at Stage 3 — expected behavior without API key configured
- `GET /knowledge/{id}/status` → 200 with correct status
- `GET /knowledge/` → 200 with source list
- `POST /knowledge/upload` (no args) → 400
- `DELETE /knowledge/{id}` (existing) → 204
- `DELETE /knowledge/{id}` (non-existent) → 404
- `GET /health` → `{"status":"ok","pgvector":"active"}` (no regression)
- `from app.ingestion.pipeline import run_ingestion; from app.routers.knowledge import router` → `all imports ok`

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

All files found: pipeline.py, knowledge.py, main.py, SUMMARY.md
All commits found: 556c71f (pipeline.py), d6cd4ac (knowledge router + main.py)
