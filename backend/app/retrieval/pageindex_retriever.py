"""PageIndex retriever — submit a retrieval task and poll until completed.

Implements RETR-03: submit POST /retrieval/, poll GET /retrieval/{id}/ until
status == "completed", then map retrieved_nodes to RetrievedChunk list.

All failures and timeouts return [] — never raise — so the hybrid retriever
can fall back to vector-only without disruption.
"""
import asyncio
import logging

import httpx

from app.config import settings
from app.models.schemas import RetrievedChunk

logger = logging.getLogger(__name__)

# Poll budget: 18 attempts x 5 s = 90 s (PageIndex can take 30-90 s on large docs).
_MAX_POLL_ATTEMPTS = 18
_POLL_INTERVAL_SECS = 5


def _submit_retrieval(doc_id: str, query: str) -> str:
    """Synchronous POST to /retrieval/.  Returns retrieval_id.  Runs in asyncio.to_thread."""
    response = httpx.post(
        f"{settings.pageindex_base_url}/retrieval/",
        json={"doc_id": doc_id, "query": query},
        headers={"Authorization": f"Bearer {settings.pageindex_api_key}"},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()["retrieval_id"]


def _poll_retrieval(retrieval_id: str) -> dict:
    """Synchronous GET /retrieval/{id}/.  Returns the response JSON.  Runs in asyncio.to_thread."""
    response = httpx.get(
        f"{settings.pageindex_base_url}/retrieval/{retrieval_id}/",
        headers={"Authorization": f"Bearer {settings.pageindex_api_key}"},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def _parse_retrieved_nodes(
    nodes: list,
    source_id: str,
    source_title: str,
) -> list:
    """Map a PageIndex retrieved_nodes list to a flat list of RetrievedChunk.

    Args:
        nodes: List of node dicts from the PageIndex response, each containing
               an optional "title" and a "relevant_contents" list.
        source_id: The knowledge source UUID string.
        source_title: The human-readable title of the source.

    Returns:
        Flat list of RetrievedChunk instances; empty list if nodes is empty.
    """
    chunks = []
    for rank, node in enumerate(nodes):
        section_title = node.get("title")
        for item in node.get("relevant_contents", []):
            chunks.append(
                RetrievedChunk(
                    source_id=source_id,
                    source_title=source_title,
                    content=item["relevant_content"],
                    page_number=item.get("page_index"),
                    section_title=section_title,
                    relevance_score=1.0 / (1 + rank),
                    retrieval_method="pageindex",
                )
            )
    return chunks


async def fetch_pageindex_chunks(
    doc_id: str,
    query: str,
    source_id: str,
    source_title: str,
    top_k: int = 5,
) -> list:
    """Submit a retrieval task to PageIndex and return the resulting chunks.

    Implements the submit-poll-parse pattern (RETR-03):
    1. POST /retrieval/ to create a retrieval task.
    2. Poll GET /retrieval/{id}/ every 5 s for up to 90 s.
    3. On completion, parse retrieved_nodes into RetrievedChunk list.
    4. On timeout or any error, log a warning and return [].

    Args:
        doc_id: PageIndex document ID.  If None, returns [] immediately.
        query: The retrieval query string.
        source_id: Knowledge source UUID string (for RetrievedChunk).
        source_title: Human-readable source title (for RetrievedChunk).
        top_k: Not used in the API call directly; kept for interface symmetry.

    Returns:
        List of RetrievedChunk; empty list on timeout or failure.
    """
    # Guard: URL sources have no PageIndex doc — never attempt an HTTP call.
    if doc_id is None:
        return []

    try:
        # Submit retrieval task (synchronous HTTP — run in thread).
        retrieval_id = await asyncio.to_thread(_submit_retrieval, doc_id, query)
        logger.debug(
            "PageIndex: submitted retrieval for doc_id=%s retrieval_id=%s",
            doc_id,
            retrieval_id,
        )

        # Poll until completed or budget exhausted.
        for _ in range(_MAX_POLL_ATTEMPTS):
            await asyncio.sleep(_POLL_INTERVAL_SECS)

            data = await asyncio.to_thread(_poll_retrieval, retrieval_id)
            if data.get("status") == "completed":
                logger.debug(
                    "PageIndex: retrieval_id=%s completed", retrieval_id
                )
                return _parse_retrieved_nodes(
                    data.get("retrieved_nodes", []), source_id, source_title
                )

        # Poll budget exhausted without completion.
        logger.warning(
            "PageIndex retrieval timed out after 90s (retrieval_id=%s, doc_id=%s)",
            retrieval_id,
            doc_id,
        )
        return []

    except Exception as exc:
        logger.error(
            "PageIndex retrieval failed (doc_id=%s): %s",
            doc_id,
            exc,
        )
        return []
