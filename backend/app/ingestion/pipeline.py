import asyncio
import logging
from typing import Optional

import aiosqlite

from app.config import settings
from app.ingestion.pdf_extractor import extract_pdf
from app.ingestion.url_extractor import extract_url
from app.ingestion.pageindex_builder import build_pageindex_tree
from app.ingestion.embedder import embed_and_store

logger = logging.getLogger(__name__)


async def _update_status(db: aiosqlite.Connection, source_id: str, status: str) -> None:
    """Write a new status value to the knowledge_sources row for source_id."""
    await db.execute(
        "UPDATE knowledge_sources SET status = ? WHERE id = ?", (status, source_id)
    )
    await db.commit()


async def run_ingestion(
    source_id: str,
    file_path: Optional[str],
    url: Optional[str],
    source_type: str,
    title: str,
) -> None:
    """Orchestrate the full 5-stage ingestion pipeline as a FastAPI BackgroundTask.

    Stages:
      1. Text extraction (PDF via pdfplumber/pypdf, URL via trafilatura)
      2. PageIndex tree submission and polling (PDF only; URL returns None immediately)
      3. pgvector embedding and chunk upsert
      4. Mark source as ready in SQLite

    Never propagates exceptions — any unhandled failure sets status to 'failed'.

    Args:
        source_id: UUID string for this knowledge source row.
        file_path: Local path to the saved PDF, or None for URL sources.
        url: Source URL string, or None for PDF sources.
        source_type: Either "pdf" or "url".
        title: Human-readable title (updated from trafilatura metadata for URLs).
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            # Stage 1: Extract text
            if source_type == "pdf":
                pages, meta = await asyncio.to_thread(extract_pdf, file_path)
                page_count = meta["total_pages"]
            else:
                # URL source
                extracted = await extract_url(url)
                pages = [
                    {
                        "page_number": 1,
                        "text": extracted["text"],
                        "has_images": False,
                        "word_count": extracted["word_count"],
                    }
                ]
                page_count = extracted["page_count"]
                title = extracted["title"]  # update title from trafilatura metadata

            # Update page_count in SQLite
            await db.execute(
                "UPDATE knowledge_sources SET page_count = ? WHERE id = ?",
                (page_count, source_id),
            )
            await db.commit()

            # Stage 2: PageIndex (PDF only; URL returns None immediately)
            await _update_status(db, source_id, "indexing_pageindex")
            pageindex_doc_id = await build_pageindex_tree(file_path, title, source_id=source_id)
            # build_pageindex_tree never raises — returns None on any failure

            # Stage 3: pgvector embeddings
            await _update_status(db, source_id, "indexing_vectors")
            chunk_count = await embed_and_store(pages, source_id, title)
            logger.info("Stored %d chunks for %s", chunk_count, source_id)

            # Stage 4: Ready
            await db.execute(
                "UPDATE knowledge_sources SET status = 'ready', pageindex_doc_id = ? WHERE id = ?",
                (pageindex_doc_id, source_id),
            )
            await db.commit()

        except Exception as e:
            logger.error("Ingestion failed for %s: %s", source_id, e)
            await _update_status(db, source_id, "failed")
