import asyncio
from app.core.logging import get_logger
from typing import Optional

from sqlalchemy import update

from app.core.database import get_session
from app.models.db_models import KnowledgeSource
from app.ingestion.pdf_extractor import extract_pdf
from app.ingestion.url_extractor import extract_url
from app.ingestion.pageindex_builder import build_pageindex_tree
from app.ingestion.embedder import embed_and_store

logger = get_logger(__name__)


async def _update_status(source_id: str, status: str) -> None:
    """Write a new status value to the knowledge_sources row for source_id."""
    async with get_session() as session:
        await session.execute(
            update(KnowledgeSource)
            .where(KnowledgeSource.id == source_id)
            .values(status=status)
        )
        await session.commit()


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
      4. Mark source as ready in Postgres

    Never propagates exceptions — any unhandled failure sets status to 'failed'.

    Args:
        source_id: UUID string for this knowledge source row.
        file_path: Local path to the saved PDF, or None for URL sources.
        url: Source URL string, or None for PDF sources.
        source_type: Either "pdf" or "url".
        title: Human-readable title (updated from trafilatura metadata for URLs).
    """
    try:
        # Stage 1: Extract text
        if source_type == "pdf":
            pages, meta = await asyncio.to_thread(extract_pdf, file_path)
            page_count = meta["total_pages"]

            # Stage 1.5: Vision augmentation (opt-in, PDF only — VIS-05)
            from app.ingestion.vision_extractor import augment_pages_with_vision
            pages = await augment_pages_with_vision(pages, file_path)
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

        # Update page_count in Postgres
        async with get_session() as session:
            await session.execute(
                update(KnowledgeSource)
                .where(KnowledgeSource.id == source_id)
                .values(page_count=page_count)
            )
            await session.commit()

        # Stage 2: PageIndex (PDF only; URL returns None immediately)
        await _update_status(source_id, "indexing_pageindex")
        pageindex_doc_id = await build_pageindex_tree(file_path, title, source_id=source_id)
        # build_pageindex_tree never raises — returns None on any failure

        # Stage 3: pgvector embeddings
        await _update_status(source_id, "indexing_vectors")
        chunk_count = await embed_and_store(pages, source_id, title)
        logger.info("Stored %d chunks for %s", chunk_count, source_id)

        # Stage 4: Ready
        async with get_session() as session:
            await session.execute(
                update(KnowledgeSource)
                .where(KnowledgeSource.id == source_id)
                .values(status="ready", pageindex_doc_id=pageindex_doc_id)
            )
            await session.commit()

    except Exception as e:
        logger.error("Ingestion failed for %s: %s", source_id, e)
        await _update_status(source_id, "failed")
