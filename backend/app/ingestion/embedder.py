import asyncio
import uuid
import logging
import numpy as np
import psycopg2
from pgvector.psycopg2 import register_vector
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from app.config import settings

logger = logging.getLogger(__name__)

BATCH_SIZE = 50


def _get_embedding_client() -> OpenAI:
    """Build an OpenAI-compatible client for embeddings from settings.

    Works with any provider that speaks the OpenAI embeddings API:
    - OpenAI:  EMBEDDING_BASE_URL unset, EMBEDDING_API_KEY (or OPENAI_API_KEY)
    - Ollama:  EMBEDDING_BASE_URL=http://localhost:11434/v1, EMBEDDING_API_KEY=ollama
    - Groq, Together, LM Studio, etc.: set their base URL and API key accordingly
    """
    return OpenAI(
        api_key=settings.embedding_api_key or settings.openai_api_key or "none",
        base_url=settings.embedding_base_url or None,
    )


def _chunk_pages(pages: list[dict], source_id: str, source_title: str) -> list[dict]:
    """Split pages into chunks using RecursiveCharacterTextSplitter."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)
    chunks = []
    for page in pages:
        page_number = page.get("page_number")
        text = page.get("text", "")
        if not text.strip():
            continue
        split_texts = splitter.split_text(text)
        for chunk_index, content in enumerate(split_texts):
            chunks.append({
                "id": str(uuid.uuid4()),
                "source_id": source_id,
                "source_title": source_title,
                "page_number": page_number,
                "chunk_index": chunk_index,
                "content": content,
            })
    return chunks


def _embed_and_store_sync(pages: list[dict], source_id: str, source_title: str) -> int:
    """Synchronous implementation of chunking, embedding, and pgvector upsert."""
    chunks = _chunk_pages(pages, source_id, source_title)
    if not chunks:
        logger.warning("No chunks produced for source_id=%s", source_id)
        return 0

    conn = psycopg2.connect(settings.database_url)
    register_vector(conn)
    try:
        total_stored = 0
        for batch_start in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[batch_start: batch_start + BATCH_SIZE]

            # Generate embeddings for the batch
            resp = _get_embedding_client().embeddings.create(
                input=[c["content"] for c in batch],
                model=settings.embedding_model,
            )
            embeddings = [np.array(e.embedding) for e in resp.data]

            # Upsert each chunk with its embedding
            with conn.cursor() as cur:
                for chunk, embedding in zip(batch, embeddings):
                    cur.execute(
                        """
                        INSERT INTO knowledge_chunks
                            (id, source_id, source_title, page_number, chunk_index, content, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding
                        """,
                        (
                            chunk["id"],
                            chunk["source_id"],
                            chunk["source_title"],
                            chunk["page_number"],
                            chunk["chunk_index"],
                            chunk["content"],
                            embedding,
                        ),
                    )
            conn.commit()
            total_stored += len(batch)
            logger.info("Upserted batch of %d chunks (total so far: %d)", len(batch), total_stored)

        return total_stored
    finally:
        conn.close()


async def embed_and_store(pages: list[dict], source_id: str, source_title: str) -> int:
    """
    Chunk pages, generate embeddings via OpenAI, and upsert into pgvector.

    Args:
        pages: List of dicts with 'page_number' and 'text' keys.
        source_id: UUID string identifying the knowledge source.
        source_title: Human-readable title for the source.

    Returns:
        Total number of chunks stored.
    """
    return await asyncio.to_thread(_embed_and_store_sync, pages, source_id, source_title)


def delete_chunks_for_source(source_id: str) -> None:
    """
    Delete all knowledge_chunks rows for a given source_id.

    Args:
        source_id: UUID string identifying the knowledge source to delete.
    """
    conn = psycopg2.connect(settings.database_url)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM knowledge_chunks WHERE source_id = %s", (source_id,))
        conn.commit()
    finally:
        conn.close()
