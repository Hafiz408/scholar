---
phase: 02-ingestion-pipeline
plan: "01"
subsystem: backend-ingestion
tags: [config, pgvector, lifespan, pdf-extraction, url-extraction]
dependency_graph:
  requires: [01-infrastructure]
  provides: [config-phase2, pgvector-schema, pdf-extractor, url-extractor]
  affects: [02-02-embedder, 02-03-pageindex-builder, 02-04-pipeline]
tech_stack:
  added: [pdfplumber, pypdf, trafilatura, psycopg2-binary]
  patterns: [asynccontextmanager-lifespan, asyncio-to-thread, pdfplumber-pypdf-fallback]
key_files:
  created: []
  modified:
    - backend/app/config.py
    - backend/app/main.py
    - backend/app/db/database.py
    - backend/app/ingestion/pdf_extractor.py
    - backend/app/ingestion/url_extractor.py
    - .env.example
decisions:
  - "Used autocommit=True on psycopg2 connection for init_pgvector_schema to avoid transaction issues with CREATE EXTENSION"
  - "Kept app.database (SQLAlchemy) for health check; db/database.py handles SQLite and pgvector init separately"
metrics:
  duration: "2 min"
  completed_date: "2026-03-18"
  tasks_completed: 3
  files_modified: 6
---

# Phase 2 Plan 01: Foundation — Config, pgvector Schema, and Extraction Modules Summary

**One-liner:** Phase 2 foundation established with pydantic-settings config extension, psycopg2-based pgvector schema init via FastAPI lifespan, pdfplumber+pypdf PDF extractor, and async trafilatura URL extractor.

## What Was Built

Three foundational components that all downstream ingestion plans depend on:

1. **config.py extended** — Added 8 new Phase 2 settings fields (`sqlite_path`, `upload_dir`, `max_upload_size_mb`, `llm_model`, `embedding_model`, `embedding_dimensions`, `pageindex_api_key`, `pageindex_base_url`) and a module-level `settings` singleton for direct import.

2. **pgvector schema init** — `init_pgvector_schema()` in `backend/app/db/database.py` creates the `knowledge_chunks` table (with `vector(1536)` column), an ivfflat index on embeddings, and a source_id index.

3. **FastAPI lifespan** — `main.py` replaced with `@asynccontextmanager` lifespan calling `init_db()` (SQLite) and `init_pgvector_schema()` (PostgreSQL) on startup.

4. **pdf_extractor.py** — `extract_pdf(file_path)` returns `(pages, metadata)` using pdfplumber primary extraction with per-page pypdf fallback; skips pages under 20 words.

5. **url_extractor.py** — `extract_url(url)` async function wraps blocking trafilatura calls in `asyncio.to_thread` to avoid event loop blocking; returns title, text, url, word_count, page_count.

## Verification Results

All five verification checks passed:
- `config ok` — settings.sqlite_path, settings.upload_dir accessible
- `schema ok` — init_pgvector_schema() ran without error; knowledge_chunks table exists
- `extractors ok` — both modules import cleanly
- `/health` returned `{"status":"ok","pgvector":"active"}`

## Commits

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Extend config, pgvector schema init, lifespan startup | 908ea8e |
| 2 | Implement pdf_extractor (pdfplumber + pypdf fallback) | c11cc48 |
| 3 | Implement url_extractor (async trafilatura wrapper) | 9c5531d |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] main.py imported from app.database instead of app.db.database**
- **Found during:** Task 1
- **Issue:** The existing main.py imported `get_engine` from `app.database` (the Phase 1 SQLAlchemy helper). After adding lifespan, `init_db` and `init_pgvector_schema` needed to come from `app.db.database`. The health check still correctly uses `app.database.get_engine()` for pgvector status check.
- **Fix:** Imported both modules — `app.database` for get_engine (health check), `app.db.database` for init_db and init_pgvector_schema (lifespan).
- **Files modified:** backend/app/main.py
- **Commit:** 908ea8e

**2. [Rule 2 - Missing] psycopg2 connection needed autocommit=True for CREATE EXTENSION**
- **Found during:** Task 1
- **Issue:** CREATE EXTENSION IF NOT EXISTS cannot run inside a transaction block in PostgreSQL. Without autocommit=True, psycopg2 wraps statements in a transaction by default.
- **Fix:** Set `conn.autocommit = True` before executing the pgvector schema DDL.
- **Files modified:** backend/app/db/database.py
- **Commit:** 908ea8e

## Self-Check: PASSED

All files verified present. All three task commits verified in git log:
- 908ea8e (Task 1)
- c11cc48 (Task 2)
- 9c5531d (Task 3)
