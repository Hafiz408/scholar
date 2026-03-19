# Phase 3: Retrieval Engine - Research

**Researched:** 2026-03-19
**Domain:** RAG retrieval — LLM query routing, pgvector cosine search, PageIndex REST API, hybrid result fusion
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RETR-01 | Router agent classifies each query as pageindex / vector / hybrid with >= 8/10 accuracy on labelled test set | LangChain `with_structured_output` + Pydantic Literal pattern; labelled test set design in Code Examples |
| RETR-02 | Router falls back to "vector" strategy when no pageindex_doc_id is available for any source | SQLite lookup of knowledge_sources.pageindex_doc_id before classification; fallback logic pattern |
| RETR-03 | PageIndex retriever fetches chapter-level chunks from books that have a PageIndex tree | PageIndex REST API: POST /retrieval/ → poll GET /retrieval/{id}/ → parse retrieved_nodes[].relevant_contents[].page_index + relevant_content |
| RETR-04 | Vector retriever performs cosine similarity search filtered by source_id against pgvector | psycopg2 + pgvector: `SELECT … WHERE source_id = ANY(%s) ORDER BY embedding <=> %s LIMIT k` |
| RETR-05 | Hybrid retriever merges PageIndex + vector results with weighted reranking (0.6/0.4), deduplicated by content hash | Weighted score fusion pattern; hashlib.sha256 of content for dedup key |
</phase_requirements>

---

## Summary

Phase 3 builds four components that all live in `backend/app/retrieval/`: a router agent, a PageIndex retriever, a vector retriever, and a hybrid retriever. The stubs exist; all four files contain only `# TODO: implement`. The schemas and data contracts are already fully defined in `app/models/schemas.py` — `RetrievedChunk`, `RetrievalResult`, and `RetrievalStrategy` are ready to use.

The router uses `ChatOpenAI.with_structured_output()` bound to a Pydantic model with `strategy: Literal["pageindex", "vector", "hybrid"]`. It must score >= 8/10 on a labelled test set before Phase 4 begins. RETR-02 is a **pre-classification guard**: the router reads `knowledge_sources.pageindex_doc_id` from SQLite first; if none of the requested sources have a PageIndex doc ID, it short-circuits to `"vector"` without calling the LLM. The PageIndex retriever calls the PageIndex REST API (POST then poll) and maps `retrieved_nodes[].relevant_contents` to `RetrievedChunk`. The vector retriever queries `knowledge_chunks` using the `<=>` cosine distance operator filtered to the correct `source_id` values. The hybrid retriever normalises both result sets, applies 0.6 (PageIndex) / 0.4 (vector) weights, and deduplicates by `hashlib.sha256(content)`.

The hard gate is the labelled test set for the router. Designing 10 representative queries per strategy (30 total) and scoring them programmatically is the critical path for Phase 3.

**Primary recommendation:** Build the router first with a deterministic fallback, validate it against the labelled set, then implement the three retrievers so the hybrid can be tested end-to-end.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| langchain-openai | 0.2.14 (pinned) | `ChatOpenAI.with_structured_output()` for the router | Already in requirements.txt; handles OpenAI tool-call structured output |
| pgvector | 0.3.2 (pinned) | psycopg2 register_vector + `<=>` cosine distance operator | Already used in embedder; Phase 2 established this pattern |
| psycopg2-binary | 2.9.9 (pinned) | Raw SQL cosine similarity query for vector retriever | Consistent with Phase 2 embedder pattern |
| httpx | 0.27.0 (pinned) | PageIndex REST API calls (submit + poll) | Already used in pageindex_builder.py for the same API |
| aiosqlite | 0.20.0 (pinned) | Async SQLite read of knowledge_sources for fallback check | Already used across all routers |
| pydantic | bundled with FastAPI | `RetrievedChunk`, `RetrievalResult` schemas | Already defined in schemas.py |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hashlib | stdlib | SHA-256 content hash for hybrid deduplication | In hybrid retriever only |
| asyncio | stdlib | `asyncio.to_thread` for sync psycopg2 calls in async FastAPI | Same pattern as embedder.py |
| pytest-asyncio | 0.23.0 (pinned) | Async test fixtures for retriever integration tests | Test files already scaffolded |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `with_structured_output` | JSON output parsing with StrOutputParser | Less reliable; schema.py already defines the types; no reason to avoid structured output |
| Weighted score fusion | Reciprocal Rank Fusion (RRF) | RRF ignores raw scores; requirements specify exact 0.6/0.4 weighting — do not change |
| Content-hash dedup | Node ID dedup | PageIndex node IDs differ from pgvector chunk IDs; content hash is the universal key |
| PageIndex legacy REST API | PageIndex Chat API (beta) | Chat API is conversational beta; retrieval API returns `retrieved_nodes` with page numbers needed for RETR-03 |

**Installation:** No new packages needed. All dependencies are pinned in `requirements.txt`.

---

## Architecture Patterns

### Recommended Project Structure

```
backend/app/retrieval/
├── __init__.py          # already exists
├── router.py            # RETR-01, RETR-02 — LLM router + fallback logic
├── vector_retriever.py  # RETR-04 — psycopg2 cosine search
├── pageindex_retriever.py  # RETR-03 — PageIndex REST API + poll
└── hybrid_retriever.py  # RETR-05 — merge, weight, dedup

backend/tests/
├── conftest.py          # shared fixtures (mock pgvector conn, mock httpx)
├── test_router.py       # labelled test set + accuracy gate assertion
└── test_vector_retriever.py  # integration or mock-based
```

### Pattern 1: Router with Structured Output + Pre-Classification Fallback

**What:** Before calling the LLM, check whether any of the requested source IDs have a `pageindex_doc_id`. If none do, return `"vector"` immediately. Otherwise, call the LLM with `with_structured_output`.

**When to use:** Every retrieval call goes through this function.

```python
# Source: LangChain docs (docs.langchain.com) + schemas.py
from pydantic import BaseModel, Field
from typing import Literal
from langchain_openai import ChatOpenAI
from app.models.schemas import RetrievalStrategy

class RouterDecision(BaseModel):
    strategy: Literal["pageindex", "vector", "hybrid"] = Field(
        description=(
            "pageindex — query asks for structured chapter/section navigation in a book; "
            "vector — broad semantic or cross-book search; "
            "hybrid — query benefits from both structured navigation and semantic search"
        )
    )

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
_router_chain = _llm.with_structured_output(RouterDecision)

async def classify_query(
    query: str,
    source_ids: list[str],
) -> RetrievalStrategy:
    """RETR-01 + RETR-02: classify and apply fallback."""
    # RETR-02: pre-check — if no PageIndex docs, skip LLM entirely
    pageindex_doc_ids = await _get_pageindex_doc_ids(source_ids)  # SQLite read
    if not pageindex_doc_ids:
        return "vector"

    decision: RouterDecision = await asyncio.to_thread(
        _router_chain.invoke,
        [{"role": "user", "content": f"Query: {query}"}]
    )
    return decision.strategy
```

### Pattern 2: Vector Retriever — Cosine Distance with Source Filter

**What:** Embed the query then execute a single SQL statement using `<=>` (cosine distance) filtered to `source_ids`.

**When to use:** Strategy is `"vector"` or when called from the hybrid retriever.

```python
# Source: pgvector-python README (github.com/pgvector/pgvector-python)
# + embedder.py pattern from Phase 2
import numpy as np
import psycopg2
from pgvector.psycopg2 import register_vector

def _vector_search_sync(
    query_embedding: list[float],
    source_ids: list[str],
    top_k: int,
) -> list[dict]:
    conn = psycopg2.connect(settings.database_url)
    register_vector(conn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_id, source_title, content, page_number,
                       1 - (embedding <=> %s) AS cosine_similarity
                FROM knowledge_chunks
                WHERE source_id = ANY(%s)
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                (np.array(query_embedding), source_ids,
                 np.array(query_embedding), top_k),
            )
            return cur.fetchall()
    finally:
        conn.close()
```

**Note:** `1 - (embedding <=> %s)` converts cosine distance to cosine similarity. Pass the same embedding twice: once for scoring, once in ORDER BY. Use `ANY(%s)` with a Python list for multi-source filtering.

### Pattern 3: PageIndex Retriever — Submit + Poll

**What:** POST to `/retrieval/` then poll GET `/retrieval/{id}/` until `status == "completed"`. Map `retrieved_nodes` to `RetrievedChunk`.

**When to use:** Strategy is `"pageindex"` or when called from the hybrid retriever.

```python
# Source: docs.pageindex.ai/sdk/retrieval + pageindex_builder.py pattern
import httpx
import asyncio

async def fetch_pageindex_chunks(
    doc_id: str,
    query: str,
    source_id: str,
    source_title: str,
) -> list[RetrievedChunk]:
    headers = {"Authorization": f"Bearer {settings.pageindex_api_key}"}

    # Submit retrieval task
    resp = await asyncio.to_thread(
        lambda: httpx.post(
            f"{settings.pageindex_base_url}/retrieval/",
            json={"doc_id": doc_id, "query": query},
            headers=headers,
            timeout=30.0,
        )
    )
    resp.raise_for_status()
    retrieval_id = resp.json()["retrieval_id"]

    # Poll for completion (max 12 attempts × 5 s = 60 s)
    for _ in range(12):
        await asyncio.sleep(5)
        result_resp = await asyncio.to_thread(
            lambda: httpx.get(
                f"{settings.pageindex_base_url}/retrieval/{retrieval_id}/",
                headers=headers,
                timeout=15.0,
            )
        )
        result_resp.raise_for_status()
        data = result_resp.json()
        if data.get("status") == "completed":
            return _parse_retrieved_nodes(
                data["retrieved_nodes"], source_id, source_title
            )

    return []  # timeout — return empty, don't raise

def _parse_retrieved_nodes(
    nodes: list[dict],
    source_id: str,
    source_title: str,
) -> list[RetrievedChunk]:
    chunks = []
    for rank, node in enumerate(nodes):
        for item in node.get("relevant_contents", []):
            chunks.append(RetrievedChunk(
                source_id=source_id,
                source_title=source_title,
                content=item["relevant_content"],
                page_number=item.get("page_index"),
                section_title=node.get("title"),
                relevance_score=1.0 / (1 + rank),  # rank-based score
                retrieval_method="pageindex",
            ))
    return chunks
```

### Pattern 4: Hybrid Retriever — Weighted Fusion + Content Hash Dedup

**What:** Run both retrievers, normalise scores, apply 0.6/0.4 weights, deduplicate by content hash.

**When to use:** Strategy is `"hybrid"`.

```python
# Source: project requirements (RETR-05) + standard weighted fusion pattern
import hashlib

def merge_results(
    pageindex_chunks: list[RetrievedChunk],
    vector_chunks: list[RetrievedChunk],
    pi_weight: float = 0.6,
    vec_weight: float = 0.4,
) -> list[RetrievedChunk]:
    scored: dict[str, tuple[RetrievedChunk, float]] = {}

    for chunk in pageindex_chunks:
        key = hashlib.sha256(chunk.content.encode()).hexdigest()
        scored[key] = (chunk, chunk.relevance_score * pi_weight)

    for chunk in vector_chunks:
        key = hashlib.sha256(chunk.content.encode()).hexdigest()
        if key in scored:
            # Merge: add weighted vector score to existing entry
            existing_chunk, existing_score = scored[key]
            scored[key] = (existing_chunk, existing_score + chunk.relevance_score * vec_weight)
        else:
            scored[key] = (chunk, chunk.relevance_score * vec_weight)

    # Sort by merged score descending
    merged = sorted(scored.values(), key=lambda x: x[1], reverse=True)
    result = []
    for chunk, score in merged:
        chunk.relevance_score = score
        result.append(chunk)
    return result
```

### Pattern 5: Router Labelled Test Set Structure

**What:** A list of dicts with `query`, `expected_strategy`, and `has_pageindex_docs` flag. Test runs classify_query and checks accuracy.

```python
# Source: Phase 3 requirements (RETR-01 — >= 8/10 accuracy gate)
LABELLED_TEST_SET = [
    # pageindex queries — chapter navigation, "in chapter X", "on page Y"
    {"query": "What does chapter 3 cover?", "expected": "pageindex", "has_pageindex": True},
    {"query": "Summarise the introduction section", "expected": "pageindex", "has_pageindex": True},
    {"query": "What is defined in the first chapter?", "expected": "pageindex", "has_pageindex": True},
    # vector queries — broad semantic, cross-book
    {"query": "What are the main causes of climate change?", "expected": "vector", "has_pageindex": True},
    {"query": "Compare photosynthesis and cellular respiration", "expected": "vector", "has_pageindex": True},
    {"query": "Explain Newton's second law", "expected": "vector", "has_pageindex": True},
    # hybrid queries — specific topic + cross-section
    {"query": "What does chapter 2 say about mitosis and how does it relate to meiosis?", "expected": "hybrid", "has_pageindex": True},
    {"query": "Find all sections discussing protein synthesis and compare them", "expected": "hybrid", "has_pageindex": True},
    # fallback: no PageIndex docs → always "vector"
    {"query": "What is DNA replication?", "expected": "vector", "has_pageindex": False},
    {"query": "What chapter covers evolution?", "expected": "vector", "has_pageindex": False},
]
# Accuracy gate: >= 8/10 correct before proceeding
```

### Anti-Patterns to Avoid

- **Passing `embedding` directly as a Python list to psycopg2 without `np.array`:** pgvector's psycopg2 adapter requires `numpy.ndarray`, not a plain list. The embedder already does this correctly — copy the pattern.
- **Calling PageIndex retrieval without checking `pageindex_doc_id` first:** Never call the PageIndex API if `doc_id` is `None` — it will 404. The RETR-02 guard lives in the router, but each retriever should also guard against a None doc_id.
- **Running both retrievers sequentially in hybrid mode:** Use `asyncio.gather()` to fire them concurrently and cut latency roughly in half.
- **Normalising scores across retrievers without checking for empty lists:** If one retriever returns zero results, division-by-zero in normalisation. Guard with `if not chunks: return []` before score fusion.
- **Deduplicating by source_id + page_number instead of content hash:** Two chunks can share a page number but have different content. The requirement specifies content hash.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LLM output parsing for strategy classification | Custom regex or JSON parser | `ChatOpenAI.with_structured_output(RouterDecision)` | Handles tool-call protocol, retries malformed output, returns typed Pydantic object |
| Cosine similarity computation in Python | numpy dot product on fetched embeddings | `<=>` operator in SQL ORDER BY | pgvector computes distance in-database using the ivfflat index — Python-side is O(n×d), SQL index is O(log n) |
| PageIndex HTTP client | Custom requests wrapper | `httpx` (already used in `pageindex_builder.py`) | Consistent with existing pattern, sync calls wrapped in `asyncio.to_thread` |
| Merge/sort logic for hybrid | Custom priority queue | Plain Python dict + `sorted()` | The merge is simple enough; no need for a heap given expected result counts (< 50) |

**Key insight:** The hardest part of this phase is the router's prompt engineering and test set design. The retrieval mechanics themselves are straightforward SQL + REST.

---

## Common Pitfalls

### Pitfall 1: Embedding the query twice in the vector retriever

**What goes wrong:** The SQL `ORDER BY embedding <=> %s` needs the query vector as a parameter. Developers pass it only once then get a psycopg2 parameter count error.

**Why it happens:** The SQL pattern uses `%s` in both SELECT (for similarity score) and ORDER BY. Both positions require the vector value.

**How to avoid:** Always pass the `query_embedding` as a parameter twice in the tuple: `(np.array(q_emb), source_ids, np.array(q_emb), top_k)`.

**Warning signs:** `psycopg2.ProgrammingError: not all arguments converted during string formatting`.

### Pitfall 2: PageIndex retrieval task still "processing" after timeout

**What goes wrong:** The poll loop exhausts all attempts but the task is still processing. Caller blocks for 60 seconds then gets empty results silently.

**Why it happens:** PageIndex reasoning can take 30–90 seconds on large documents. Default poll budgets may be too tight.

**How to avoid:** Set poll budget to at least 18 attempts × 5 s = 90 s. Log a warning (not an exception) on timeout. Return empty `[]` — the hybrid can still return vector results.

**Warning signs:** Retrieval results always empty for PageIndex strategy during testing.

### Pitfall 3: Router prompt under-specifies strategy boundaries

**What goes wrong:** The LLM returns `"vector"` for chapter-specific queries because "vector search is good for everything."

**Why it happens:** Without explicit examples in the system prompt, gpt-4o-mini defaults to vector for most queries.

**How to avoid:** Include one-sentence definitions and 1–2 examples per strategy in the system/instructions message. Use `temperature=0` to reduce variance.

**Warning signs:** Router accuracy below 6/10 on labelled set; all failures are `"pageindex"` or `"hybrid"` misclassified as `"vector"`.

### Pitfall 4: RETR-02 fallback checked after LLM call

**What goes wrong:** The LLM classifies as `"pageindex"` but all sources are vector-only. PageIndex retriever gets called with `doc_id=None` and 404s.

**Why it happens:** Fallback guard placed after the LLM call instead of before.

**How to avoid:** Check `pageindex_doc_ids` as the very first operation in `classify_query`. If the list is empty, return `"vector"` immediately without calling the LLM.

**Warning signs:** `httpx.HTTPStatusError: 404` in PageIndex retriever logs.

### Pitfall 5: Hybrid dedup mutates RetrievedChunk objects in the input lists

**What goes wrong:** Score normalisation modifies `chunk.relevance_score` in-place on the original list objects, causing issues if callers inspect the original results.

**Why it happens:** Pydantic models are mutable by default.

**How to avoid:** Create new `RetrievedChunk` instances (or use `.model_copy(update={"relevance_score": score})`) when writing merged results. Do not mutate inputs.

---

## Code Examples

Verified patterns from official sources and existing project code:

### Embedding a query (reuse embedder pattern from Phase 2)

```python
# Source: backend/app/ingestion/embedder.py pattern
from app.ingestion.embedder import _get_embedding_client
from app.config import settings

def embed_query(query: str) -> list[float]:
    client = _get_embedding_client()
    resp = client.embeddings.create(
        input=[query],
        model=settings.embedding_model,
    )
    return resp.data[0].embedding
```

### SQLite lookup of pageindex_doc_ids for source list

```python
# Source: backend/app/routers/knowledge.py aiosqlite pattern
import aiosqlite
from app.config import settings

async def _get_pageindex_doc_ids(source_ids: list[str]) -> list[str]:
    placeholders = ",".join("?" * len(source_ids))
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT pageindex_doc_id FROM knowledge_sources "
            f"WHERE id IN ({placeholders}) AND pageindex_doc_id IS NOT NULL",
            source_ids,
        ) as cursor:
            rows = await cursor.fetchall()
    return [row["pageindex_doc_id"] for row in rows]
```

### pgvector cosine distance query with source filter

```python
# Source: pgvector-python README + Phase 2 embedder pattern
cur.execute(
    """
    SELECT source_id, source_title, content, page_number,
           1 - (embedding <=> %s) AS cosine_similarity
    FROM knowledge_chunks
    WHERE source_id = ANY(%s)
    ORDER BY embedding <=> %s
    LIMIT %s
    """,
    (np.array(query_embedding), source_ids,
     np.array(query_embedding), top_k),
)
```

### Running both retrievers concurrently in hybrid mode

```python
# Source: Python asyncio stdlib
pi_task = asyncio.create_task(fetch_pageindex_chunks(doc_id, query, ...))
vec_task = asyncio.create_task(vector_search(query, source_ids, ...))
pi_chunks, vec_chunks = await asyncio.gather(pi_task, vec_task)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual JSON parsing of LLM output for routing | `with_structured_output()` on ChatOpenAI | LangChain 0.2+ | Eliminates malformed output failures; no retry logic needed |
| Rank-based fusion (RRF) | Weighted score fusion (project-specified 0.6/0.4) | Design decision | Honour the requirement exactly; RRF would require different normalisation |
| PageIndex SDK (empty stub v0.1.0) | Direct httpx REST calls | Phase 2 discovery | The `pageindex` package is an empty stub — continue using httpx directly |

**Deprecated/outdated:**
- `pageindex` Python package v0.1.0: empty stub, useless. All PageIndex calls go through httpx REST directly (pattern established in `pageindex_builder.py`).
- PageIndex Chat API (beta): Do not use for this phase. The legacy retrieval API returns `retrieved_nodes` with `page_index` fields which map directly to `RetrievedChunk.page_number`. The Chat API returns conversational text without structured node data.

---

## Open Questions

1. **PageIndex retrieval endpoint request body format**
   - What we know: The SDK docs show `pi_client.submit_query(doc_id, query)` — the REST body likely is `{"doc_id": "...", "query": "..."}` based on the SDK parameter names
   - What's unclear: Whether the POST body is JSON or form-encoded; whether the `thinking=True` flag improves accuracy enough to justify the extra latency
   - Recommendation: Default to JSON body. Test with `thinking=False` first (faster). Only enable `thinking=True` if the retriever returns poor results in integration tests.

2. **Router accuracy gate testing against live LLM**
   - What we know: The test set must score >= 8/10. Tests with `pytest-asyncio` will call the real OpenAI API.
   - What's unclear: Whether the test should be marked as an integration test (requires `OPENAI_API_KEY`) or mocked.
   - Recommendation: Mark with `@pytest.mark.integration` and a `.env` guard. Keep the labelled set deterministic (same 10 queries, fixed temperature=0). Do not mock — the gate must verify real LLM behaviour.

3. **Cosine similarity score normalisation for hybrid fusion**
   - What we know: pgvector returns `1 - (embedding <=> query)` which is in [−1, 1] but practically [0, 1] for normalised embeddings. PageIndex returns rank-based scores we assign as `1/(1+rank)`.
   - What's unclear: Whether the scales are comparable enough for direct 0.6/0.4 weighting.
   - Recommendation: Both approaches produce [0, 1] values. Apply weights as-is. If hybrid results are noticeably worse than single-strategy in integration tests, normalise each list to [0, 1] by dividing by the max score in that list before applying weights.

---

## Sources

### Primary (HIGH confidence)

- `backend/app/ingestion/embedder.py` — psycopg2 + pgvector pattern with `register_vector`, batch upsert, `asyncio.to_thread`
- `backend/app/ingestion/pageindex_builder.py` — httpx REST pattern for PageIndex API; confirmed `pageindex` package is empty stub
- `backend/app/models/schemas.py` — `RetrievedChunk`, `RetrievalResult`, `RetrievalStrategy` already defined; no new schema work needed
- `backend/app/db/database.py` — `knowledge_chunks` table schema: `id, source_id, source_title, page_number, chunk_index, content, embedding`; `knowledge_sources` has `pageindex_doc_id` column
- `backend/requirements.txt` — pinned versions confirmed: langchain-openai==0.2.14, pgvector==0.3.2, httpx==0.27.0, aiosqlite==0.20.0
- https://docs.pageindex.ai/sdk/retrieval — retrieval task API: POST `/retrieval/`, poll GET `/retrieval/{id}/`, response shape with `retrieved_nodes[].title`, `retrieved_nodes[].node_id`, `retrieved_nodes[].relevant_contents[].page_index`, `retrieved_nodes[].relevant_contents[].relevant_content`
- https://docs.pageindex.ai/endpoints — confirms legacy retrieval endpoints remain available

### Secondary (MEDIUM confidence)

- https://docs.langchain.com/oss/python/langchain/structured-output — `with_structured_output()` with Pydantic `Literal` fields pattern; multiple community sources corroborate this as the standard approach
- https://github.com/pgvector/pgvector-python — `<=>` cosine distance operator; `register_vector(conn)` required; `ANY(%s)` for list filtering

### Tertiary (LOW confidence)

- WebSearch: PageIndex retrieval POST body format (JSON vs form-encoded) — not definitively confirmed from official docs; inferred from SDK parameter names

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already pinned in requirements.txt; patterns directly from existing Phase 2 code
- Architecture: HIGH — schemas already defined; retrievers are straightforward implementations of documented APIs
- Router accuracy: MEDIUM — prompt engineering quality will determine whether 8/10 gate is met; no guarantee without testing
- PageIndex API exact request format: MEDIUM — confirmed endpoint and response shape; POST body format inferred but not shown in official REST docs

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (PageIndex API is stable legacy; pgvector operators do not change; LangChain structured output API is stable in 0.2.x)
