import os
import uuid
from app.core.logging import get_logger
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, UploadFile, File, Form, HTTPException, Response

from pydantic import ValidationError

from sqlalchemy import select, delete

from app.config import settings
from app.core.database import get_session
from app.models.db_models import KnowledgeSource as KnowledgeSourceORM, to_dict
from app.models.schemas import KnowledgeSource, IngestionStatus
from app.ingestion.pipeline import run_ingestion
from app.ingestion.embedder import delete_chunks_for_source
from app.ingestion.pageindex_builder import delete_pageindex_doc

logger = get_logger(__name__)

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/upload", status_code=202)
async def upload_knowledge(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
):
    """Upload a PDF file or a URL for ingestion into the knowledge base.

    Returns HTTP 202 immediately with source_id and status=pending.
    The actual ingestion (text extraction, embedding, PageIndex) runs as a background task.
    """
    if file is None and url is None:
        raise HTTPException(status_code=400, detail="Must provide file or url")

    source_id = str(uuid.uuid4())
    save_path: Optional[str] = None

    if file is not None:
        # Read all bytes before any background work — UploadFile stream must not be passed
        # to a background task (stream is closed by the time the task runs).
        content = await file.read()
        size_mb = len(content) / (1024 * 1024)
        if size_mb > settings.max_upload_size_mb:
            raise HTTPException(
                status_code=413,
                detail=f"File size {size_mb:.1f} MB exceeds limit of {settings.max_upload_size_mb} MB",
            )
        os.makedirs(settings.upload_dir, exist_ok=True)
        save_path = os.path.join(settings.upload_dir, f"{source_id}.pdf")
        with open(save_path, "wb") as fh:
            fh.write(content)
        source_type = "pdf"
        title = file.filename or source_id
    else:
        source_type = "url"
        title = url

    async with get_session() as session:
        session.add(
            KnowledgeSourceORM(
                id=source_id,
                title=title,
                source_type=source_type,
                file_path=save_path,
                url=url,
                page_count=0,
                status="pending",
                created_at=_now(),
            )
        )
        await session.commit()

    background_tasks.add_task(run_ingestion, source_id, save_path, url, source_type, title)

    return {"source_id": source_id, "status": "pending"}


@router.get("/{source_id}/status", response_model=IngestionStatus)
async def get_status(source_id: str):
    """Return the current ingestion status for a knowledge source."""
    async with get_session() as session:
        obj = (
            await session.execute(
                select(KnowledgeSourceORM).where(KnowledgeSourceORM.id == source_id)
            )
        ).scalar_one_or_none()

    if obj is None:
        raise HTTPException(status_code=404, detail="Knowledge source not found")

    row = to_dict(obj)
    status = row["status"]
    page_count = row["page_count"] or 0
    return IngestionStatus(
        source_id=row["id"],
        status=status,
        pages_processed=page_count if status == "ready" else 0,
        total_pages=page_count,
    )


@router.get("", response_model=list[KnowledgeSource])
async def list_knowledge_sources():
    """Return all knowledge sources ordered by creation date descending."""
    async with get_session() as session:
        orm_rows = (
            await session.execute(
                select(KnowledgeSourceORM).order_by(KnowledgeSourceORM.created_at.desc())
            )
        ).scalars().all()

    sources = []
    for obj in orm_rows:
        row = to_dict(obj)
        try:
            sources.append(
                KnowledgeSource(
                    id=row["id"],
                    title=row["title"],
                    source_type=row["source_type"],
                    file_path=row["file_path"],
                    url=row["url"],
                    page_count=row["page_count"] or 0,
                    pageindex_doc_id=row["pageindex_doc_id"],
                    status=row["status"],
                    # Tolerate a missing/non-string created_at so one bad row never 500s the whole list.
                    created_at=(
                        datetime.fromisoformat(row["created_at"])
                        if isinstance(row["created_at"], str)
                        else datetime.now(timezone.utc)
                    ),
                )
            )
        except ValidationError as exc:
            # Skip malformed/legacy rows (e.g. missing source_type) so one bad
            # row never 500s the whole list.
            logger.warning("Skipping malformed knowledge_sources row id=%s: %s", row["id"], exc)
    return sources


@router.delete("/{source_id}", status_code=204)
async def delete_knowledge_source(source_id: str):
    """Delete a knowledge source with cascade across pgvector, PageIndex, and Postgres.

    Returns 204 on success, 404 if source not found.
    PageIndex deletion is best-effort — failure there will not prevent the overall delete.
    """
    # Step 1: Fetch pageindex_doc_id from Postgres (also validates source exists)
    async with get_session() as session:
        obj = (
            await session.execute(
                select(KnowledgeSourceORM).where(KnowledgeSourceORM.id == source_id)
            )
        ).scalar_one_or_none()

        if obj is None:
            raise HTTPException(status_code=404, detail="Knowledge source not found")

        pageindex_doc_id = obj.pageindex_doc_id

        # Step 2: Delete from pgvector (synchronous — fast operation)
        try:
            delete_chunks_for_source(source_id)
        except Exception as e:
            logger.warning("pgvector delete failed for %s: %s", source_id, e)

        # Step 3: Delete from PageIndex (best-effort — delete_pageindex_doc never raises)
        if pageindex_doc_id is not None:
            delete_pageindex_doc(pageindex_doc_id)

        # Step 4: Delete from Postgres
        await session.execute(
            delete(KnowledgeSourceORM).where(KnowledgeSourceORM.id == source_id)
        )
        await session.commit()

    return Response(status_code=204)
