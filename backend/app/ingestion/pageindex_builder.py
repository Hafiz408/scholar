"""PageIndex builder — submit PDFs to the PageIndex cloud API and poll for readiness.

The pageindex Python package v0.1.0 is an empty stub with no client class.
We call the REST API directly via httpx, mirroring the patterns documented
in the plan (submit_document, is_retrieval_ready, get_document, delete_document).

All failures (missing key, network errors, timeouts, API errors) are caught
and return None so the vector-only ingestion pipeline continues unblocked.
"""
import asyncio
import logging
from typing import Any, Dict, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Polling parameters matching the plan specification.
_MAX_POLL_ATTEMPTS = 30
_POLL_INTERVAL_SECS = 10


def _headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {settings.pageindex_api_key}"}


def _submit_document(file_path: str) -> Dict[str, Any]:
    """Synchronous REST call to submit a PDF.  Runs in asyncio.to_thread."""
    with open(file_path, "rb") as fh:
        response = httpx.post(
            f"{settings.pageindex_base_url}/documents",
            headers=_headers(),
            files={"file": fh},
            timeout=60.0,
        )
    response.raise_for_status()
    return response.json()


def _is_retrieval_ready(doc_id: str) -> bool:
    """Synchronous check whether a document is ready for retrieval.  Runs in asyncio.to_thread."""
    response = httpx.get(
        f"{settings.pageindex_base_url}/documents/{doc_id}/ready",
        headers=_headers(),
        timeout=30.0,
    )
    response.raise_for_status()
    data = response.json()
    return bool(data.get("ready", False))


def _get_document(doc_id: str) -> Dict[str, Any]:
    """Synchronous fetch of document metadata.  Runs in asyncio.to_thread."""
    response = httpx.get(
        f"{settings.pageindex_base_url}/documents/{doc_id}",
        headers=_headers(),
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


async def build_pageindex_tree(file_path: Optional[str], doc_title: str) -> Optional[str]:
    """Submit a PDF to PageIndex and poll until retrieval is ready.

    Returns the doc_id string on success, or None on any failure (URL sources,
    missing/invalid API key, timeout, API errors). Never raises — all failures
    are caught so vector-only ingestion can continue unblocked.

    Args:
        file_path: Local path to the PDF file. None means a URL source, which
                   PageIndex does not support — returns None immediately.
        doc_title: Human-readable title for the document (used for logging).

    Returns:
        doc_id string if PageIndex successfully indexed the document, else None.
    """
    # URL sources are not supported by PageIndex — skip immediately.
    if file_path is None:
        logger.info("PageIndex: skipping URL source (file_path is None) for '%s'", doc_title)
        return None

    try:
        # submit_document is synchronous — run in thread to avoid blocking the event loop.
        result = await asyncio.to_thread(_submit_document, file_path)
        doc_id: str = result["doc_id"]
        logger.info("PageIndex: submitted '%s' → doc_id=%s", doc_title, doc_id)

        # Poll until retrieval is ready (max 30 attempts × 10 s = 5 minutes).
        for attempt in range(_MAX_POLL_ATTEMPTS):
            await asyncio.sleep(_POLL_INTERVAL_SECS)

            # is_retrieval_ready is synchronous — run in thread.
            ready = await asyncio.to_thread(_is_retrieval_ready, doc_id)
            if ready:
                logger.info(
                    "PageIndex: '%s' ready after %d attempt(s)", doc_title, attempt + 1
                )
                return doc_id

            # Also check whether the document entered a failed state.
            doc = await asyncio.to_thread(_get_document, doc_id)
            if doc.get("status") == "failed":
                logger.warning(
                    "PageIndex: document '%s' (doc_id=%s) entered failed state — "
                    "falling back to vector-only",
                    doc_title,
                    doc_id,
                )
                return None

        # 30 attempts exhausted without becoming ready.
        logger.warning(
            "PageIndex timed out for '%s' (doc_id=%s) after %d attempts — "
            "falling back to vector-only",
            doc_title,
            doc_id,
            _MAX_POLL_ATTEMPTS,
        )
        return None

    except Exception as e:
        logger.warning(
            "PageIndex failed for '%s': %s — falling back to vector-only",
            doc_title,
            e,
        )
        return None


def delete_pageindex_doc(doc_id: str) -> None:
    """Best-effort deletion of a PageIndex document.

    Catches all exceptions and never raises — deletion failure must not affect
    any caller.

    Args:
        doc_id: The PageIndex document ID to delete.
    """
    try:
        httpx.delete(
            f"{settings.pageindex_base_url}/documents/{doc_id}",
            headers=_headers(),
            timeout=10.0,
        )
        logger.info("PageIndex: deleted doc_id=%s", doc_id)
    except Exception as e:
        logger.warning("PageIndex delete failed for %s: %s", doc_id, e)
        # Best-effort — never raise.
