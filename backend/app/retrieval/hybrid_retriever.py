"""Hybrid retriever — merge PageIndex and vector results with weighted fusion.

Implements RETR-05:
- merge_results: 0.6/0.4 weighted fusion with SHA-256 content hash deduplication.
- retrieve: single public orchestrator that dispatches to the correct retriever
  based on classify_query output, running both concurrently in hybrid mode.
"""
import asyncio
import hashlib
import time
from app.core.logging import get_logger

from app.core import pg
from app.models.schemas import RetrievedChunk, RetrievalResult
from app.retrieval.router import classify_query, _get_pageindex_doc_ids
from app.retrieval.pageindex_retriever import fetch_pageindex_chunks
from app.retrieval.vector_retriever import vector_search

logger = get_logger(__name__)


def merge_results(
    pageindex_chunks: list[RetrievedChunk],
    vector_chunks: list[RetrievedChunk],
    pi_weight: float = 0.6,
    vec_weight: float = 0.4,
) -> list[RetrievedChunk]:
    """Merge PageIndex and vector chunks with weighted fusion and content deduplication.

    Deduplicates by SHA-256 hash of chunk content. When the same content appears
    in both lists, the scores are combined (pi_weight * pi_score + vec_weight * vec_score).
    Input chunk objects are never mutated — model_copy() is used for all output chunks.

    Args:
        pageindex_chunks: Chunks from the PageIndex retriever.
        vector_chunks: Chunks from the vector retriever.
        pi_weight: Weight applied to PageIndex scores (default 0.6).
        vec_weight: Weight applied to vector scores (default 0.4).

    Returns:
        Merged, deduplicated list of RetrievedChunk sorted by combined score descending.
    """
    if not pageindex_chunks and not vector_chunks:
        return []

    # keyed by sha256(content) → (chunk, combined_score)
    scored: dict[str, tuple[RetrievedChunk, float]] = {}

    # PageIndex pass
    for chunk in pageindex_chunks:
        key = hashlib.sha256(chunk.content.encode()).hexdigest()
        scored[key] = (chunk, chunk.relevance_score * pi_weight)

    # Vector pass — merge duplicates, insert new
    for chunk in vector_chunks:
        key = hashlib.sha256(chunk.content.encode()).hexdigest()
        if key in scored:
            existing_chunk, existing_score = scored[key]
            scored[key] = (existing_chunk, existing_score + chunk.relevance_score * vec_weight)
        else:
            scored[key] = (chunk, chunk.relevance_score * vec_weight)

    # Sort by combined score descending
    sorted_entries = sorted(scored.values(), key=lambda t: t[1], reverse=True)

    # Build result list without mutating input objects
    return [
        chunk.model_copy(update={"relevance_score": score})
        for chunk, score in sorted_entries
    ]


async def _get_sources_with_pageindex(
    source_ids: list[str],
) -> list[tuple[str, str, str]]:
    """Query Postgres for (pageindex_doc_id, source_id, source_title) triples.

    Returns only sources that have a non-null pageindex_doc_id.

    Args:
        source_ids: List of knowledge source UUID strings.

    Returns:
        List of (doc_id, source_id, source_title) tuples.
    """
    if not source_ids:
        return []

    placeholders = ",".join(["%s"] * len(source_ids))
    query = (
        f"SELECT pageindex_doc_id, id, title FROM knowledge_sources "
        f"WHERE id IN ({placeholders}) AND pageindex_doc_id IS NOT NULL"
    )

    async with pg.connect() as db:
        async with db.execute(query, source_ids) as cursor:
            rows = await cursor.fetchall()

    return [(row["pageindex_doc_id"], row["id"], row["title"]) for row in rows]


async def retrieve(
    query: str,
    source_ids: list[str],
    top_k: int = 5,
) -> RetrievalResult:
    """Orchestrate retrieval across the full stack (RETR-05).

    1. classify_query determines the routing strategy.
    2. Dispatch to the correct retriever(s):
       - 'pageindex': fetch_pageindex_chunks for each source with a pageindex_doc_id.
       - 'vector': vector_search across all source_ids.
       - 'hybrid': both concurrently via asyncio.gather, then merge_results.
    3. Return RetrievalResult with the top_k chunks.

    Args:
        query: Natural language query string.
        source_ids: List of knowledge source UUID strings.
        top_k: Maximum number of chunks to return.

    Returns:
        RetrievalResult with strategy_used, chunks, and latency_ms.
    """
    start_ms = time.monotonic()

    # RETRIEVAL_STRATEGY pins the strategy; "auto" (default) defers to the router.
    configured = (settings.retrieval_strategy or "auto").lower().strip()
    if configured in ("hybrid", "pageindex", "vector"):
        strategy = configured
    else:
        strategy = await classify_query(query, source_ids)

    chunks: list[RetrievedChunk] = []
    strategy_used = strategy

    if strategy == "pageindex":
        pi_sources = await _get_sources_with_pageindex(source_ids)
        if pi_sources:
            tasks = [
                fetch_pageindex_chunks(doc_id, query, sid, stitle)
                for doc_id, sid, stitle in pi_sources
            ]
            results = await asyncio.gather(*tasks)
            chunks = [c for result in results for c in result]
        strategy_used = "pageindex"

    elif strategy == "vector":
        chunks = await vector_search(query, source_ids, top_k)
        strategy_used = "vector"

    else:  # hybrid
        pi_sources = await _get_sources_with_pageindex(source_ids)
        pi_tasks = [
            fetch_pageindex_chunks(doc_id, query, sid, stitle)
            for doc_id, sid, stitle in pi_sources
        ]
        vec_task = vector_search(query, source_ids, top_k)

        all_results = await asyncio.gather(*pi_tasks, vec_task)
        pi_chunks = [c for result in all_results[:-1] for c in result]
        vec_chunks = all_results[-1]
        chunks = merge_results(pi_chunks, vec_chunks)
        strategy_used = "hybrid"

    latency_ms = int((time.monotonic() - start_ms) * 1000)

    return RetrievalResult(
        strategy_used=strategy_used,
        chunks=chunks[:top_k],
        latency_ms=latency_ms,
    )
