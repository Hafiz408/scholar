"""Vector retriever — cosine similarity search against knowledge_chunks in pgvector.

Implements RETR-04: embed the query via OpenAI-compatible client, then run a
cosine similarity SQL query filtered to the provided source_ids.

Returns a list of RetrievedChunk sorted by similarity (highest first).
Returns [] on empty source_ids or any failure.
"""
import asyncio
from app.core.logging import get_logger

import numpy as np
import psycopg2
from pgvector.psycopg2 import register_vector
from openai import OpenAI

from app.config import settings
from app.models.schemas import RetrievedChunk

logger = get_logger(__name__)

# SQL for cosine similarity search with source_id filter.
# The query embedding is passed TWICE:
#   - once for the 1 - (embedding <=> %s) score expression
#   - once for the ORDER BY embedding <=> %s clause
# Passing a plain list raises ProgrammingError — pgvector adapter requires numpy.ndarray.
_VECTOR_SEARCH_SQL = """
    SELECT source_id, source_title, content, page_number,
           1 - (embedding <=> %s) AS cosine_similarity
    FROM knowledge_chunks
    WHERE source_id = ANY(%s)
    ORDER BY embedding <=> %s
    LIMIT %s
"""


def _get_embedding_client() -> OpenAI:
    """Build an OpenAI-compatible client for embeddings from settings."""
    return OpenAI(
        api_key=settings.embedding_api_key or settings.openai_api_key or "none",
        base_url=settings.embedding_base_url or None,
    )


def embed_query(query: str) -> list:
    """Embed a single query string using the configured embedding model.

    Args:
        query: The natural language query to embed.

    Returns:
        List of floats representing the embedding vector.
    """
    client = _get_embedding_client()
    resp = client.embeddings.create(
        input=[query],
        model=settings.embedding_model,
    )
    return resp.data[0].embedding


def _vector_search_sync(
    query_embedding: list,
    source_ids: list,
    top_k: int,
) -> list:
    """Synchronous pgvector cosine similarity search.  Runs in asyncio.to_thread.

    Args:
        query_embedding: List of floats from embed_query.
        source_ids: List of source UUID strings to filter results.
        top_k: Maximum number of results to return.

    Returns:
        List of tuples: (source_id, source_title, content, page_number, cosine_similarity).
    """
    embedding_array = np.array(query_embedding)
    conn = psycopg2.connect(settings.database_url)
    register_vector(conn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                _VECTOR_SEARCH_SQL,
                (
                    embedding_array,   # for 1 - (embedding <=> %s) score
                    source_ids,        # for ANY(%s) filter
                    embedding_array,   # for ORDER BY embedding <=> %s
                    top_k,
                ),
            )
            return cur.fetchall()
    finally:
        conn.close()


async def vector_search(
    query: str,
    source_ids: list,
    top_k: int = 5,
) -> list:
    """Embed query and run cosine similarity search against knowledge_chunks.

    Implements RETR-04:
    1. Embed query string.
    2. Run SQL cosine similarity search filtered to source_ids.
    3. Map result rows to RetrievedChunk list.

    Args:
        query: Natural language query.
        source_ids: List of knowledge source UUID strings to search within.
        top_k: Maximum number of chunks to return.

    Returns:
        List of RetrievedChunk sorted by cosine similarity (highest first).
        Returns [] if source_ids is empty or on any error.
    """
    if not source_ids:
        return []

    try:
        query_embedding = await asyncio.to_thread(embed_query, query)
        rows = await asyncio.to_thread(_vector_search_sync, query_embedding, source_ids, top_k)
        return [
            RetrievedChunk(
                source_id=row[0],
                source_title=row[1],
                content=row[2],
                page_number=row[3],
                relevance_score=float(row[4]),
                retrieval_method="vector",
            )
            for row in rows
        ]
    except Exception:
        logger.exception("vector_search failed for source_ids=%s", source_ids)
        return []
