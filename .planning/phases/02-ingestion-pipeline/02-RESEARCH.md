# Phase 2: Ingestion Pipeline - Research

**Researched:** 2026-03-18
**Domain:** File ingestion (PDF + URL) → PageIndex tree + pgvector embeddings + FastAPI polling API
**Confidence:** HIGH (stack + PRD fully prescribed; library APIs verified)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INGEST-01 | User can upload a PDF (up to 50MB) and have it ingested into both PageIndex and pgvector | FastAPI UploadFile + BackgroundTasks pattern; pdfplumber extraction; pgvector upsert; PageIndex submit_document |
| INGEST-02 | User can submit a URL and have its text extracted and ingested into both PageIndex and pgvector | trafilatura.fetch_url + extract; same pipeline as PDF after extraction |
| INGEST-03 | User can poll ingestion status (pending → indexing_pageindex → indexing_vectors → ready → failed) | SQLite status column; GET /knowledge/{id}/status endpoint reads aiosqlite row |
| INGEST-04 | Ingestion completes even when PageIndex fails — falls back to vector-only (pageindex_doc_id = None) | try/except around PageIndex block; status reaches "ready" with pageindex_doc_id = None |
| INGEST-05 | User can list all knowledge sources with their current status | GET /knowledge endpoint; SELECT all from knowledge_sources SQLite table |
| INGEST-06 | User can delete a knowledge source (removes from pgvector + PageIndex + SQLite) | DELETE /knowledge/{id}; pi_client.delete_document(doc_id); pgvector DELETE WHERE source_id; SQLite DELETE |
</phase_requirements>

---

## Summary

Phase 2 builds the complete ingestion pipeline that turns uploaded PDFs and submitted URLs into queryable knowledge. The pipeline has five sequential stages: extract text (pdfplumber for PDF, trafilatura for URL), submit to PageIndex (async, with fallback), chunk and embed into pgvector (OpenAI text-embedding-3-small via raw SQL), update status in SQLite at each stage, and expose a set of REST endpoints for upload, status polling, listing, and deletion.

The most important architectural fact about this phase is that all ingestion work must run as a FastAPI `BackgroundTask` so the upload endpoint can return a `source_id` immediately (HTTP 202) while processing continues in the background. Status is written to the SQLite `knowledge_sources` table at every stage transition, which the polling endpoint reads. The entire pipeline is already scaffolded as stub files; this phase fills them in.

The two highest-risk areas are (1) the PageIndex API client interface — the `pageindex==0.1.0` Python package is a thin wrapper around the cloud API with a small but specific interface (`submit_document`, `get_document`, `is_retrieval_ready`, `get_tree`) — and (2) the pgvector embedding/upsert flow, which requires `register_vector` from `pgvector.psycopg2` to handle vector types in psycopg2 connections. Both are verified from official sources below.

**Primary recommendation:** Run the full ingestion pipeline as a FastAPI `BackgroundTask`, write status to SQLite at each stage, wrap the entire PageIndex block in a try/except so vector-only fallback works automatically, and use raw SQL with `psycopg2-binary` + `pgvector.psycopg2.register_vector` for the embedding upsert — do not use the LangChain PGVector abstraction (it requires psycopg3 and adds unnecessary complexity for this use case).

---

## Standard Stack

### Core (all already in requirements.txt — no new installs needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pdfplumber` | `0.11.0` | Page-by-page PDF text extraction | PRD-prescribed; best for structured text PDFs; handles tables |
| `pypdf` | `4.3.0` | PDF fallback extractor per page | PRD-prescribed; handles pages pdfplumber fails on |
| `trafilatura` | `1.12.0` | Web URL text extraction | PRD-prescribed; outperforms newspaper3k, boilerpipe in benchmarks |
| `pageindex` | `0.1.0` | PageIndex cloud API client | PRD-prescribed; only client for PageIndex service |
| `openai` | `1.58.1` | text-embedding-3-small embeddings | PRD-prescribed; 1536-dim embeddings for pgvector |
| `pgvector` | `0.3.2` | Registers vector type with psycopg2 | Required adapter for pgvector SQL operations |
| `psycopg2-binary` | `2.9.9` | PostgreSQL driver | Already present from Phase 1 |
| `aiosqlite` | `0.20.0` | Async SQLite reads/writes for status | Already present; used in db/database.py |
| `python-multipart` | `0.0.9` | FastAPI multipart file upload parsing | Required by FastAPI for UploadFile |
| `langchain` | `0.3.0` | RecursiveCharacterTextSplitter | PRD specifies 600/100 chunking; don't hand-roll |
| `fastapi` | `0.115.0` | BackgroundTasks, UploadFile, APIRouter | Phase 1 foundation |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `httpx` | `0.27.0` | Async HTTP for PageIndex polling | If needed for direct HTTP calls; PageIndex client may handle internally |
| `python-dotenv` | `1.0.0` | .env loading | Already handled by pydantic-settings |

### Alternatives Considered (but NOT used — PRD locks these choices)

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `psycopg2-binary` + raw SQL | LangChain PGVector abstraction | LangChain PGVector now requires psycopg3; project uses psycopg2; adds abstraction debt |
| `pdfplumber` primary | `pymupdf` | pymupdf faster but not in PRD stack; pdfplumber better for structured academic texts |
| `trafilatura` | `newspaper3k`, `beautifulsoup4` | trafilatura benchmarked superior for main-text extraction |
| FastAPI `BackgroundTasks` | Celery + Redis | BackgroundTasks sufficient for dev-scale; no broker infrastructure needed |

**No new installs required.** All libraries already in `backend/requirements.txt`.

---

## Architecture Patterns

### Recommended Module Structure (already scaffolded — fill in the TODOs)

```
backend/app/
├── ingestion/
│   ├── pdf_extractor.py      # pdfplumber primary, pypdf fallback
│   ├── url_extractor.py      # trafilatura fetch + extract
│   ├── pageindex_builder.py  # PageIndex submit + polling loop
│   ├── embedder.py           # chunk → embed → pgvector upsert
│   └── pipeline.py           # orchestrates all 5 stages + status writes
├── routers/
│   └── knowledge.py          # POST /upload, GET /status, GET /, DELETE /
├── db/
│   └── database.py           # init_db(), get_db() — already complete
└── config.py                 # needs sqlite_path, pageindex_api_key, upload_dir added
```

### Pattern 1: FastAPI Upload → Background Task → Status Polling

**What:** Return `source_id` immediately (HTTP 202), run ingestion as a background task, client polls status endpoint.

**When to use:** Any long-running operation (ingestion can take 2-5 min for large PDFs via PageIndex).

```python
# Source: https://fastapi.tiangolo.com/tutorial/background-tasks/
from fastapi import APIRouter, BackgroundTasks, UploadFile, File

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

@router.post("/upload", status_code=202)
async def upload_knowledge(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    db: aiosqlite.Connection = Depends(get_db)
):
    source_id = str(uuid.uuid4())
    # Write "pending" record to SQLite immediately
    await db.execute(
        "INSERT INTO knowledge_sources (id, status, ...) VALUES (?, 'pending', ...)",
        (source_id, ...)
    )
    await db.commit()
    # Save uploaded file to disk BEFORE returning (UploadFile stream closes after response)
    if file:
        save_path = os.path.join(settings.upload_dir, f"{source_id}.pdf")
        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    background_tasks.add_task(run_ingestion, source_id, save_path, url, source_type, title)
    return {"source_id": source_id, "status": "pending"}
```

**CRITICAL:** Read the file bytes and save to disk BEFORE returning from the endpoint. `UploadFile.file` is a stream that closes when the response is sent — the background task will see an empty file if you pass the `UploadFile` object directly.

### Pattern 2: Ingestion Pipeline with Status Transitions

**What:** Sequential pipeline that writes status to SQLite at each stage, with PageIndex in a try/except for graceful fallback.

```python
# Source: PRD Section 6.5 — pipeline.py specification
async def run_ingestion(source_id: str, file_path: Optional[str],
                        url: Optional[str], source_type: str, title: str):
    async with aiosqlite.connect(settings.sqlite_path) as db:
        try:
            # Stage 1: Extract
            if source_type == "pdf":
                pages, metadata = extract_pdf(file_path)
            else:
                extracted = await extract_url(url)
                pages = [{"page_number": 1, "text": extracted["text"], ...}]
                title = extracted["title"]

            # Stage 2: PageIndex (with fallback)
            await _update_status(db, source_id, "indexing_pageindex")
            pageindex_doc_id = None
            try:
                pageindex_doc_id = await build_pageindex_tree(file_path or title, title)
            except Exception as e:
                logging.warning(f"PageIndex failed for {source_id}: {e}")
                # pageindex_doc_id stays None — vector-only fallback

            # Stage 3: Vectors
            await _update_status(db, source_id, "indexing_vectors")
            chunk_count = await embed_and_store(pages, source_id, title)

            # Stage 4: Ready
            await _update_status(db, source_id, "ready", pageindex_doc_id=pageindex_doc_id)

        except Exception as e:
            await _update_status(db, source_id, "failed", error=str(e))
```

### Pattern 3: PDF Extraction with pdfplumber + pypdf Fallback

**What:** Use pdfplumber as primary extractor, fall back to pypdf per page on failure. Skip pages with < 20 words.

```python
# Source: https://github.com/jsvine/pdfplumber (official README)
import pdfplumber
import pypdf

def extract_pdf(file_path: str) -> tuple[list[dict], dict]:
    pages = []
    with pdfplumber.open(file_path) as pdf:
        total = len(pdf.pages)
        metadata = {}
        for i, page in enumerate(pdf.pages):
            try:
                text = page.extract_text() or ""
            except Exception:
                # Fallback to pypdf for this page
                reader = pypdf.PdfReader(file_path)
                text = reader.pages[i].extract_text() or ""
            words = text.split()
            if len(words) < 20:
                continue  # skip blank/diagram-only pages
            pages.append({
                "page_number": i + 1,  # 1-indexed per PRD
                "text": text,
                "has_images": len(page.images) > 0,
                "word_count": len(words)
            })
    return pages, {"total_pages": total}
```

### Pattern 4: URL Extraction with trafilatura

**What:** Fetch URL content with trafilatura and extract main body text. Estimate page_count from word count.

```python
# Source: https://trafilatura.readthedocs.io/en/latest/usage-python.html
import trafilatura

async def extract_url(url: str) -> dict:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise ValueError(f"Could not fetch URL: {url}")
    text = trafilatura.extract(downloaded, include_tables=True)
    if not text:
        raise ValueError(f"Could not extract text from URL: {url}")
    # Use trafilatura metadata for title
    meta = trafilatura.extract_metadata(downloaded)
    title = (meta.title if meta and meta.title else url)
    word_count = len(text.split())
    return {
        "title": title,
        "text": text,
        "url": url,
        "word_count": word_count,
        "page_count": max(1, word_count // 300)  # PRD spec
    }
```

**Note:** `trafilatura.fetch_url()` is synchronous. Wrap in `asyncio.to_thread()` if calling from an async context to avoid blocking the event loop.

### Pattern 5: PageIndex Client Usage

**What:** Submit PDF to PageIndex cloud API, poll for completion, return doc_id.

**Verified methods (from official PageIndex docs and cookbook):**
- `PageIndexClient(api_key=str)` — initialize
- `submit_document(file_path: str) -> dict` — returns `{"doc_id": "pi-xxx..."}`
- `get_document(doc_id: str) -> dict` — returns `{"status": "completed"|"processing"|"failed", ...}`
- `is_retrieval_ready(doc_id: str) -> bool` — convenience method
- `get_tree(doc_id: str, node_summary: bool = False) -> dict` — returns tree structure
- `chat_completions(messages: list, doc_id: str|list) -> dict` — Phase 3 usage

```python
# Source: https://github.com/VectifyAI/PageIndex/blob/main/cookbook/pageindex_RAG_simple.ipynb
# Source: https://docs.pageindex.ai/sdk
import asyncio
from pageindex import PageIndexClient

async def build_pageindex_tree(file_path: str, doc_title: str) -> Optional[str]:
    """Submit PDF to PageIndex. Poll until ready. Return doc_id or None on failure."""
    client = PageIndexClient(api_key=settings.pageindex_api_key)

    try:
        result = client.submit_document(file_path)
        doc_id = result["doc_id"]
    except Exception as e:
        logging.warning(f"PageIndex submit failed: {e}")
        return None  # vector-only fallback

    # Poll every 10s, max 30 attempts (5 minutes)
    for attempt in range(30):
        await asyncio.sleep(10)
        try:
            if client.is_retrieval_ready(doc_id):
                return doc_id
            doc_status = client.get_document(doc_id).get("status", "")
            if doc_status == "failed":
                raise ValueError(f"PageIndex processing failed for {doc_id}")
        except Exception as e:
            logging.warning(f"PageIndex poll error (attempt {attempt}): {e}")

    raise TimeoutError(f"PageIndex timed out after 30 polls for {doc_id}")
```

**IMPORTANT:** The `pageindex` Python client methods (`submit_document`, `get_document`, `is_retrieval_ready`) are SYNCHRONOUS — wrap in `asyncio.to_thread()` if calling from async context, or call them directly (they are fast HTTP calls; polling sleep is the bottleneck).

**Delete method status:** The docs reference a `deleteDocument` method in the JS SDK. For Python, check `pi_client.delete_document(doc_id)` at runtime. If not available, use the REST API directly: `DELETE https://api.pageindex.ai/documents/{doc_id}` with `Authorization: Bearer {api_key}` header.

### Pattern 6: pgvector Embedding Upsert

**What:** Chunk text with RecursiveCharacterTextSplitter (600/100), batch embed 50 chunks at a time with OpenAI text-embedding-3-small, upsert into pgvector using raw psycopg2 SQL.

```python
# Source: https://github.com/pgvector/pgvector-python (official README — psycopg2 section)
# Source: PRD Section 6.4
import uuid
import numpy as np
import psycopg2
from pgvector.psycopg2 import register_vector
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI

CHUNK_SIZE = 600
CHUNK_OVERLAP = 100
BATCH_SIZE = 50

async def embed_and_store(pages: list[dict], source_id: str, source_title: str) -> int:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )

    # Build all chunks with metadata
    all_chunks = []
    for page in pages:
        splits = splitter.split_text(page["text"])
        for i, chunk_text in enumerate(splits):
            all_chunks.append({
                "id": str(uuid.uuid4()),
                "source_id": source_id,
                "source_title": source_title,
                "page_number": page["page_number"],
                "chunk_index": i,
                "content": chunk_text,
            })

    # Batch embed
    openai_client = OpenAI(api_key=settings.openai_api_key)
    conn = psycopg2.connect(settings.database_url)
    register_vector(conn)  # REQUIRED — registers vector type adapter

    try:
        for batch_start in range(0, len(all_chunks), BATCH_SIZE):
            batch = all_chunks[batch_start:batch_start + BATCH_SIZE]
            texts = [c["content"] for c in batch]
            resp = openai_client.embeddings.create(
                input=texts, model="text-embedding-3-small"
            )
            embeddings = [e.embedding for e in resp.data]

            with conn.cursor() as cur:
                for chunk, embedding in zip(batch, embeddings):
                    cur.execute("""
                        INSERT INTO knowledge_chunks
                            (id, source_id, source_title, page_number, chunk_index, content, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding
                    """, (
                        chunk["id"], chunk["source_id"], chunk["source_title"],
                        chunk["page_number"], chunk["chunk_index"],
                        chunk["content"], np.array(embedding)
                    ))
            conn.commit()
    finally:
        conn.close()

    return len(all_chunks)
```

**Note on RecursiveCharacterTextSplitter import:** In langchain 0.3.x it moved to `langchain_text_splitters` package. If not installed separately, import from `langchain.text_splitter` (deprecated but still works in 0.3.0). The `langchain` 0.3.0 package installs `langchain-text-splitters` as a dependency.

### Pattern 7: pgvector Table Schema (create on startup)

The PRD specifies this schema — create it in `app/db/database.py`'s `init_db()` alongside the existing SQLite schema:

```sql
-- Run against PostgreSQL on backend startup
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_title TEXT NOT NULL,
    page_number INTEGER,
    chunk_index INTEGER,
    content TEXT NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_chunks_source
    ON knowledge_chunks (source_id);
```

**Where to create this:** Add a `init_pgvector_schema()` function called from FastAPI's `lifespan` event or startup, using the existing synchronous `get_engine()` SQLAlchemy engine.

### Pattern 8: Config.py additions required

The current `config.py` is missing fields needed by Phase 2. These must be added:

```python
# Fields to add to Settings in backend/app/config.py
pageindex_api_key: str = ""
pageindex_base_url: str = "https://api.pageindex.ai"
sqlite_path: str = "./data/scholar.db"
upload_dir: str = "./data/uploads"
max_upload_size_mb: int = 50
llm_model: str = "gpt-4o-mini"
embedding_model: str = "text-embedding-3-small"
embedding_dimensions: int = 1536
```

Also update `.env.example` to document `PAGEINDEX_API_KEY`.

**Also:** The existing `config.py` exports `get_settings()` as a cached function but `db/database.py` imports `settings` directly. Ensure the `db/database.py` uses `from app.config import get_settings; settings = get_settings()` at module load OR imports the `settings` object exported from config (the PRD uses `settings = Settings()` as a module-level singleton — this is the pattern to follow).

### Pattern 9: Knowledge Router API Contracts

```python
# POST /knowledge/upload → 202 {"source_id": str, "status": "pending"}
# GET  /knowledge/{id}/status → 200 IngestionStatus
# GET  /knowledge → 200 list[KnowledgeSource]
# DELETE /knowledge/{id} → 204 No Content
```

Delete must cascade: pgvector DELETE WHERE source_id = ?, PageIndex delete (if doc_id not None), SQLite DELETE.

### Anti-Patterns to Avoid

- **Passing UploadFile to background task:** The file stream closes with the response. Always read bytes / save to disk BEFORE starting the background task.
- **Calling trafilatura synchronously in async context:** Use `await asyncio.to_thread(trafilatura.fetch_url, url)` to avoid blocking uvicorn's event loop.
- **Missing `register_vector(conn)` before psycopg2 vector operations:** Without this call, psycopg2 cannot serialize/deserialize the `vector` type and will raise a type error.
- **Using LangChain's PGVector class:** It now requires `psycopg3` (not `psycopg2-binary`). The project uses psycopg2 — use raw SQL with `pgvector.psycopg2.register_vector`.
- **Blocking the status on PageIndex failure:** The PageIndex try/except must catch ALL exceptions (TimeoutError, ValueError, httpx errors) and set `pageindex_doc_id = None`, never propagating to the outer try/except.
- **Not creating pgvector schema before first embed:** The `knowledge_chunks` table and ivfflat index must be created at startup, not lazily.
- **50MB size validation only in frontend:** Also validate server-side. Check `file.size` or stream size before writing to disk — reject with HTTP 413 if > 50MB.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Text chunking with overlap | Custom string split | `RecursiveCharacterTextSplitter(600, 100)` | Handles sentence/paragraph boundaries correctly; edge cases with newlines, whitespace |
| PDF text extraction | Custom pdfminer wrapper | `pdfplumber` + `pypdf` fallback | pdfplumber handles table detection, layout awareness; pypdf handles edge cases |
| URL boilerplate removal | Custom HTML parser | `trafilatura` | Benchmarked best for main-text extraction across 100s of site types |
| OpenAI batching | Manual loop per chunk | `client.embeddings.create(input=[list])` | OpenAI accepts batches; reduces API calls by 50x |
| PageIndex polling loop | Custom sleep/retry | `client.is_retrieval_ready()` built-in | Already handles the status check; write a loop around it |
| Vector type registration | Custom psycopg2 adapter | `pgvector.psycopg2.register_vector(conn)` | Vector serialization has subtle endianness/format issues |

**Key insight:** Every sub-problem in this pipeline has a dedicated, production-tested library. The implementation work is wiring them together with correct error handling — not reimplementing extraction, chunking, or vector serialization.

---

## Common Pitfalls

### Pitfall 1: UploadFile Stream Closed Before Background Task Reads It

**What goes wrong:** Background task receives an `UploadFile` object but the file stream has already been closed when the HTTP response was sent. Reading the file in the background task returns empty bytes.

**Why it happens:** FastAPI closes the upload stream when it sends the response. Background tasks run after the response, so the stream is gone.

**How to avoid:** Save the file to disk (or read bytes into memory) synchronously inside the endpoint handler, BEFORE calling `background_tasks.add_task()`. Pass the file path (string) to the background task, not the UploadFile object.

**Warning signs:** Background task logs show empty content or zero-page PDFs; no exception raised.

---

### Pitfall 2: Missing `register_vector` on psycopg2 Connection

**What goes wrong:** `psycopg2.ProgrammingError: can't adapt type 'numpy.ndarray'` when trying to INSERT an embedding vector.

**Why it happens:** psycopg2 doesn't know how to serialize a numpy array to PostgreSQL's `vector` type without the adapter registration.

**How to avoid:** Call `from pgvector.psycopg2 import register_vector; register_vector(conn)` immediately after creating the psycopg2 connection, before any vector SQL.

**Warning signs:** Immediate crash on first `embed_and_store` call with a type adaptation error.

---

### Pitfall 3: PageIndex Exception Propagates and Blocks Upload

**What goes wrong:** PageIndex API throws a connection error or timeout, which propagates up the pipeline and marks the source as "failed" — even though vector ingestion would have succeeded.

**Why it happens:** The PageIndex try/except is too narrow and doesn't catch all exception types (e.g., httpx.ConnectError, TimeoutError, ValueError).

**How to avoid:** Catch the broadest exception class (`except Exception as e:`) around the PageIndex block. Log the warning. Set `pageindex_doc_id = None`. Continue to the vector stage. INGEST-04 requires this fallback always works.

**Warning signs:** Source status becomes "failed" after PageIndex errors even though pgvector ingestion would succeed. Test by setting an invalid `PAGEINDEX_API_KEY`.

---

### Pitfall 4: SQLite Write Conflicts in Background Task

**What goes wrong:** Multiple concurrent ingestions both write status updates to SQLite, causing `database is locked` errors.

**Why it happens:** SQLite has file-level locking. Multiple concurrent writes contend for the lock.

**How to avoid:** Use `aiosqlite` with individual connection per background task (`async with aiosqlite.connect(settings.sqlite_path) as db:`). The project's `db/database.py` already provides this pattern — use it. Do not share a single connection across background tasks.

**Warning signs:** "sqlite3.OperationalError: database is locked" in backend logs during concurrent uploads.

---

### Pitfall 5: ivfflat Index Requires Minimum Row Count

**What goes wrong:** `ERROR: ivfflat index requires at least 1 row` — the index creation fails or queries fail when the `knowledge_chunks` table is empty.

**Why it happens:** The ivfflat index in pgvector requires data to exist for training the cluster centroids. Creating the index on an empty table or querying immediately after creation before any data exists can cause errors.

**How to avoid:** Create the index WITH the table creation `IF NOT EXISTS` — the `CREATE INDEX IF NOT EXISTS ... USING ivfflat` syntax is safe to run on an empty table at startup (it creates the empty index). The error occurs only if you try to do similarity queries when 0 rows exist — guard vector retrieval queries against empty tables.

**Warning signs:** Vector retrieval queries error on fresh installs before any documents are ingested.

---

### Pitfall 6: trafilatura.fetch_url Blocks Event Loop

**What goes wrong:** Uvicorn becomes unresponsive during URL extraction because trafilatura's `fetch_url` does synchronous I/O.

**Why it happens:** trafilatura uses the `requests` library internally (synchronous HTTP). Calling it directly in an async FastAPI handler blocks the event loop for all other requests.

**How to avoid:** Run in a thread pool: `await asyncio.to_thread(trafilatura.fetch_url, url)`. Same applies to the extraction step if it's CPU-intensive.

**Warning signs:** Server hangs during URL ingestion; other API endpoints stop responding.

---

### Pitfall 7: Config Missing Fields

**What goes wrong:** `AttributeError: Settings has no attribute 'sqlite_path'` (or `pageindex_api_key`, `upload_dir`) at runtime when ingestion code tries to access settings.

**Why it happens:** The existing `config.py` from Phase 1 only has the minimum fields needed for infrastructure. Phase 2 requires additional settings.

**How to avoid:** Add all required fields to `Settings` BEFORE implementing any ingestion module. See Pattern 8 above for the complete list.

**Warning signs:** Import-time or first-call AttributeError on any ingestion module.

---

## Code Examples

### Upload Endpoint with File Size Guard

```python
# Source: https://fastapi.tiangolo.com/tutorial/request-files/ (verified)
@router.post("/upload", status_code=202)
async def upload_knowledge(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None)
):
    if not file and not url:
        raise HTTPException(400, "Must provide file or url")

    source_id = str(uuid.uuid4())

    if file:
        # Validate size BEFORE saving
        content = await file.read()
        size_mb = len(content) / (1024 * 1024)
        if size_mb > settings.max_upload_size_mb:
            raise HTTPException(413, f"File exceeds {settings.max_upload_size_mb}MB limit")

        os.makedirs(settings.upload_dir, exist_ok=True)
        save_path = os.path.join(settings.upload_dir, f"{source_id}.pdf")
        with open(save_path, "wb") as f:
            f.write(content)  # file saved to disk before returning
        source_type = "pdf"
        title = file.filename or source_id
    else:
        save_path = None
        source_type = "url"
        title = url

    # Write pending record to SQLite
    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.execute(
            "INSERT INTO knowledge_sources (id, title, source_type, file_path, url, page_count, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, 0, 'pending', ?)",
            (source_id, title, source_type, save_path, url, datetime.utcnow().isoformat())
        )
        await db.commit()

    background_tasks.add_task(run_ingestion, source_id, save_path, url, source_type, title)
    return {"source_id": source_id, "status": "pending"}
```

### Delete Endpoint (cascade across all stores)

```python
@router.delete("/{source_id}", status_code=204)
async def delete_knowledge_source(source_id: str):
    async with aiosqlite.connect(settings.sqlite_path) as db:
        row = await db.execute(
            "SELECT pageindex_doc_id FROM knowledge_sources WHERE id = ?", (source_id,)
        )
        source = await row.fetchone()
        if not source:
            raise HTTPException(404, "Source not found")

        pageindex_doc_id = source["pageindex_doc_id"]

    # 1. Delete from pgvector
    conn = psycopg2.connect(settings.database_url)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM knowledge_chunks WHERE source_id = %s", (source_id,))
        conn.commit()
    finally:
        conn.close()

    # 2. Delete from PageIndex (best-effort)
    if pageindex_doc_id:
        try:
            client = PageIndexClient(api_key=settings.pageindex_api_key)
            client.delete_document(pageindex_doc_id)  # verify method name at runtime
        except Exception as e:
            logging.warning(f"PageIndex delete failed for {pageindex_doc_id}: {e}")

    # 3. Delete from SQLite
    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.execute("DELETE FROM knowledge_sources WHERE id = ?", (source_id,))
        await db.commit()
```

### Status Polling Endpoint

```python
@router.get("/{source_id}/status", response_model=IngestionStatus)
async def get_ingestion_status(source_id: str):
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, status, page_count FROM knowledge_sources WHERE id = ?",
            (source_id,)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(404, "Source not found")
        return IngestionStatus(
            source_id=row["id"],
            status=row["status"],
            pages_processed=row["page_count"] if row["status"] == "ready" else 0,
            total_pages=row["page_count"]
        )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LangChain PGVector abstraction | Raw SQL + pgvector.psycopg2.register_vector | langchain 0.3.x moved to psycopg3 | Must use psycopg2 path directly since project uses psycopg2-binary |
| `from pydantic import BaseSettings` | `from pydantic_settings import BaseSettings` | pydantic v2 | Already done in config.py — note for any new settings files |
| `from langchain.text_splitter import RecursiveCharacterTextSplitter` | `from langchain_text_splitters import RecursiveCharacterTextSplitter` | langchain 0.3.x | Old import is deprecated but still works; prefer new import |
| Polling with `time.sleep()` | `await asyncio.sleep()` | Always | Sync sleep blocks the event loop; must use async sleep in background tasks |
| `@app.on_event("startup")` FastAPI | `@asynccontextmanager lifespan` | FastAPI 0.93+ | Old pattern deprecated; use lifespan for pgvector schema init |

**Deprecated/outdated in this context:**
- `RecursiveCharacterTextSplitter` from `langchain.text_splitter`: deprecated import path in 0.3.x — use `langchain_text_splitters`
- LangChain `PGVector` integration class: requires psycopg3 — not compatible with this project's psycopg2 setup

---

## Open Questions

1. **PageIndex `delete_document` Python method name**
   - What we know: The JS SDK has `deleteDocument(docId)`. The Python docs reference delete via API endpoint.
   - What's unclear: Whether `pi_client.delete_document(doc_id)` is the correct method name in the Python client `pageindex==0.1.0`
   - Recommendation: At implementation time, inspect the installed package: `python -c "from pageindex import PageIndexClient; print([m for m in dir(PageIndexClient) if 'del' in m.lower()])"`. If not available, use `httpx.delete(f"{settings.pageindex_base_url}/documents/{doc_id}", headers={"Authorization": f"Bearer {settings.pageindex_api_key}"})`.

2. **PageIndex API key required for plan 3**
   - What we know: STATE.md already flags this: "PageIndex API key must be obtained before Phase 2 plan 3 (pageindex_builder.py)"
   - What's unclear: Whether a free tier/trial key is available immediately
   - Recommendation: Plans 1-2 (config, schema, PDF/URL extraction, embedder) can proceed without the key. Plan 3 (pageindex_builder + pipeline integration) requires the key. Structure plans accordingly.

3. **Where to initialize pgvector schema**
   - What we know: Currently `main.py` uses `app.on_event` pattern (deprecated). PRD shows schema must exist before first embed.
   - What's unclear: Whether to use lifespan or keep simple startup call
   - Recommendation: Use `@asynccontextmanager lifespan` in `main.py` to call both `init_db()` (SQLite) and `init_pgvector_schema()` (PostgreSQL). This is the current FastAPI best practice.

4. **URL ingestion and PageIndex (text-only, no PDF)**
   - What we know: PageIndex `submit_document` takes a file path. URLs produce text, not a PDF file.
   - What's unclear: Whether PageIndex can ingest plain text or only PDF files
   - Recommendation: For URL sources, skip PageIndex entirely (`pageindex_doc_id = None` from the start). The PRD pipeline spec shows `build_pageindex_tree(file_path or title, title)` — if `file_path` is None (URL source), the function should return None immediately. Only PDFs get PageIndex indexing.

---

## Sources

### Primary (HIGH confidence)
- PageIndex official docs — https://docs.pageindex.ai/sdk — SDK methods: `PageIndexClient`, `submit_document`, `get_document`, `is_retrieval_ready`, `get_tree`, `chat_completions`
- PageIndex cookbook notebook — https://github.com/VectifyAI/PageIndex/blob/main/cookbook/pageindex_RAG_simple.ipynb — verified `submit_document` → polling pattern
- pgvector-python official README — https://github.com/pgvector/pgvector-python — `register_vector`, psycopg2 usage, SQLAlchemy integration
- trafilatura official docs — https://trafilatura.readthedocs.io/en/latest/usage-python.html — `fetch_url`, `extract`, `extract_metadata`
- FastAPI official docs — https://fastapi.tiangolo.com/tutorial/background-tasks/ — `BackgroundTasks`, `add_task`
- FastAPI official docs — https://fastapi.tiangolo.com/tutorial/request-files/ — `UploadFile`, `File`, `Form`, `python-multipart`
- pdfplumber official GitHub — https://github.com/jsvine/pdfplumber — `pdfplumber.open`, `page.extract_text()`, `page.images`
- PRD Section 6 (ingestion pipeline spec) — scholar_v1_prd.md — all function signatures, pipeline stages, SQL schema

### Secondary (MEDIUM confidence)
- pgvector-python OpenAI example — https://github.com/pgvector/pgvector-python/blob/master/examples/openai/example.py — verified embedding + insert pattern (uses psycopg3 in example but psycopg2 adapter confirmed in README)
- pgvector PyPI — https://pypi.org/project/pgvector/ — confirms `pgvector.psycopg2` module exists

### Tertiary (LOW confidence — verify at implementation)
- PageIndex Python `delete_document` method: Referenced in JS SDK and inferred from REST API docs. Python method name not confirmed in source. Verify at runtime.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries in requirements.txt, versions pinned, APIs verified
- Architecture: HIGH — PRD specifies exact function signatures, SQL schemas, and pipeline stages
- PageIndex client API: MEDIUM-HIGH — `submit_document`, `get_document`, `is_retrieval_ready` confirmed from cookbook and docs; `delete_document` Python method name LOW confidence
- Pitfalls: HIGH — UploadFile stream, register_vector, PageIndex fallback are well-documented gotchas

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable — pageindex Python client is pinned at 0.1.0 in requirements.txt)
