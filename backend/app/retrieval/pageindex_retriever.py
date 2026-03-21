"""PageIndex retriever — navigate a locally stored document tree using LLM reasoning.

Loads the JSON tree saved by pageindex_builder, flattens it to a section
skeleton (id + title + summary), asks the LLM to pick the most relevant
section IDs for the query, then returns the full text of those sections as
RetrievedChunk objects.

All failures return [] — never raise — so the hybrid retriever falls back
to vector-only without disruption.
"""
import json
import logging
import re
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI

from app.agents.prompts import PAGEINDEX_TREE_SEARCH_PROMPT
from app.config import settings
from app.models.schemas import RetrievedChunk

logger = logging.getLogger(__name__)

# Module-level LLM client singleton (connection-pooled).
_llm_client: Optional[AsyncOpenAI] = None


def _get_llm_client() -> AsyncOpenAI:
    global _llm_client
    if _llm_client is None:
        _llm_client = AsyncOpenAI(
            api_key=settings.llm_api_key or settings.openai_api_key or None,
            base_url=settings.llm_base_url or None,
        )
    return _llm_client


def _tree_path(doc_id: str) -> Path:
    return Path(settings.upload_dir) / f"{doc_id}_tree.json"


def _load_tree(doc_id: str) -> Optional[dict]:
    """Load the saved JSON tree for doc_id. Returns None if not found."""
    path = _tree_path(doc_id)
    if not path.exists():
        logger.warning("PageIndex: tree file not found for doc_id=%s", doc_id)
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _flatten_skeleton(nodes: list, depth: int = 0) -> str:
    """Recursively flatten tree nodes to a compact id→title→summary outline."""
    lines = []
    indent = "  " * depth
    for node in nodes:
        node_id = node.get("id", "?")
        title = node.get("title", "")
        summary = (node.get("summary") or "")[:200]
        lines.append(f"{indent}[{node_id}] {title}: {summary}")
        children = node.get("nodes") or []
        if children:
            lines.append(_flatten_skeleton(children, depth + 1))
    return "\n".join(lines)


def _collect_nodes_by_ids(nodes: list, target_ids: set) -> list:
    """Walk the tree depth-first and return nodes whose id is in target_ids."""
    result = []
    for node in nodes:
        if node.get("id") in target_ids:
            result.append(node)
        children = node.get("nodes") or []
        if children:
            result.extend(_collect_nodes_by_ids(children, target_ids))
    return result


async def _ask_llm_for_node_ids(skeleton: str, query: str, top_k: int) -> list[str]:
    """Call the LLM to select relevant section IDs from the document outline."""
    prompt = PAGEINDEX_TREE_SEARCH_PROMPT.format(
        tree_skeleton=skeleton,
        query=query,
        top_k=top_k,
    )
    client = _get_llm_client()
    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    content = response.choices[0].message.content.strip()

    # Extract a JSON array from the response (guard against prose wrapping).
    match = re.search(r"\[.*?\]", content, re.DOTALL)
    if not match:
        logger.warning("PageIndex: LLM returned no JSON array: %r", content[:200])
        return []
    return json.loads(match.group())


async def fetch_pageindex_chunks(
    doc_id: str,
    query: str,
    source_id: str,
    source_title: str,
    top_k: int = 5,
) -> list:
    """Retrieve relevant chunks from a locally stored PageIndex tree.

    1. Load the JSON tree from disk.
    2. Flatten the tree to a skeleton outline.
    3. Ask the LLM to pick the top_k most relevant section IDs.
    4. Extract the full text from those sections.
    5. Return as RetrievedChunk list ordered by LLM rank.

    Args:
        doc_id: The source_id used as the tree filename stem.
        query: The user's search query.
        source_id: Knowledge source UUID (for RetrievedChunk metadata).
        source_title: Human-readable source title (for RetrievedChunk metadata).
        top_k: Maximum number of sections to return.

    Returns:
        List of RetrievedChunk; empty list on any failure.
    """
    if doc_id is None:
        return []

    try:
        tree = _load_tree(doc_id)
        if tree is None:
            return []

        nodes = tree.get("structure") or []
        if not nodes:
            logger.warning("PageIndex: empty structure in tree for doc_id=%s", doc_id)
            return []

        skeleton = _flatten_skeleton(nodes)
        node_ids = await _ask_llm_for_node_ids(skeleton, query, top_k)
        if not node_ids:
            return []

        logger.debug(
            "PageIndex: LLM selected node_ids=%s for doc_id=%s", node_ids, doc_id
        )

        # Preserve LLM-ranked order: id → rank position.
        id_rank = {nid: rank for rank, nid in enumerate(node_ids)}
        target_ids = set(node_ids)
        matched = _collect_nodes_by_ids(nodes, target_ids)

        chunks = []
        for node in matched:
            text = node.get("text") or node.get("summary") or ""
            if not text:
                continue
            rank = id_rank.get(node.get("id", ""), len(matched))
            chunks.append(
                RetrievedChunk(
                    source_id=source_id,
                    source_title=source_title,
                    content=text,
                    page_number=node.get("start_index"),
                    section_title=node.get("title"),
                    relevance_score=1.0 / (1 + rank),
                    retrieval_method="pageindex",
                )
            )

        # Sort by relevance (higher score = lower rank index).
        chunks.sort(key=lambda c: c.relevance_score, reverse=True)
        return chunks[:top_k]

    except Exception as exc:
        logger.error("PageIndex retrieval failed (doc_id=%s): %s", doc_id, exc)
        return []
