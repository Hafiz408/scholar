"""PageIndex builder — build a hierarchical document tree using the open-source PageIndex library.

Calls page_index_main() locally (no cloud service required). The resulting tree
is saved as JSON to data/uploads/<source_id>_tree.json and the source_id is
returned as the doc_id for later retrieval.

All failures return None so the vector-only pipeline continues unblocked.
"""
import asyncio
import json
from app.core.logging import get_logger
import os
from pathlib import Path
from typing import Optional

from app.config import settings

logger = get_logger(__name__)

# Configure litellm env vars at module load so PageIndex picks them up on import.
# PageIndex uses litellm internally; OPENAI_API_KEY is the key it reads.
_api_key = settings.llm_api_key or settings.openai_api_key
if _api_key:
    os.environ.setdefault("OPENAI_API_KEY", _api_key)

# For OpenAI-compatible providers (e.g. Mistral), prefix the model with "openai/"
# so litellm routes through the custom base URL set via litellm.api_base.
_PAGEINDEX_MODEL = (
    f"openai/{settings.llm_model}" if settings.llm_base_url else settings.llm_model
)


def _tree_path(source_id: str) -> Path:
    return Path(settings.upload_dir) / f"{source_id}_tree.json"


def _build_tree_sync(file_path: str) -> dict:
    """Synchronous PageIndex call. Runs in asyncio.to_thread to avoid blocking."""
    import litellm
    from pageindex import ConfigLoader, page_index_main

    if settings.llm_base_url:
        litellm.api_base = settings.llm_base_url

    opt = ConfigLoader().load()
    opt.model = _PAGEINDEX_MODEL
    # PageIndex checks these against the STRING 'yes' (not truthiness); passing
    # Python True silently disables them, producing a tree with no node_id/summary/text
    # — which makes tree navigation impossible. Must be the string 'yes'.
    opt.if_add_node_id = "yes"
    opt.if_add_node_text = "yes"
    opt.if_add_node_summary = "yes"

    return page_index_main(file_path, opt)


async def build_pageindex_tree(
    file_path: Optional[str],
    doc_title: str,
    source_id: str = "",
) -> Optional[str]:
    """Build a PageIndex tree from a PDF and save it to disk.

    Args:
        file_path: Local path to the PDF. None means a URL source — skipped immediately.
        doc_title: Human-readable title used for logging.
        source_id: The knowledge source UUID; used to name the tree file.

    Returns:
        source_id on success (used as pageindex_doc_id in the DB), None on any failure.
    """
    if file_path is None:
        logger.info("PageIndex: skipping URL source for '%s'", doc_title)
        return None

    try:
        logger.info("PageIndex: building tree for '%s'", doc_title)
        tree = await asyncio.to_thread(_build_tree_sync, file_path)

        out = _tree_path(source_id)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(tree, ensure_ascii=False), encoding="utf-8")
        logger.info("PageIndex: saved tree → %s", out)
        return source_id

    except Exception as exc:
        logger.warning(
            "PageIndex failed for '%s': %s — falling back to vector-only",
            doc_title,
            exc,
        )
        return None


def delete_pageindex_doc(doc_id: str) -> None:
    """Delete the locally stored tree file. Never raises."""
    try:
        path = _tree_path(doc_id)
        if path.exists():
            path.unlink()
            logger.info("PageIndex: deleted tree %s", path)
    except Exception as exc:
        logger.warning("PageIndex: delete failed for doc_id=%s: %s", doc_id, exc)
