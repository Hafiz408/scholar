"""
Vision extractor — augments PDF page text with diagram/chart/table descriptions
from a vision-capable LLM.

Opt-in: only runs when settings.vision_model is non-empty.
Never raises: per-page exceptions are logged; pipeline continues (VIS-04).
"""
import asyncio
import base64
from app.core.logging import get_logger

import fitz  # PyMuPDF — already in requirements.txt (pymupdf>=1.26.0)
from langchain_core.messages import HumanMessage

from app.config import settings
from app.core.llm_factory import get_vision_llm

logger = get_logger(__name__)

# Render at 150 DPI — balances image clarity for diagrams/equations with token cost.
# 72 DPI loses small text; 300 DPI triples image size and token cost.
_RENDER_DPI = 150

VISION_PROMPT = (
    "You are analyzing a page from an academic textbook or scientific document. "
    "Describe any diagrams, charts, tables, equations, or figures visible on this page. "
    "Be concise and factual. If the page contains only text with no visual elements, "
    "respond with an empty string."
)


def _render_page_to_base64(file_path: str, page_number: int) -> str:
    """Render a single PDF page (1-indexed) to a base64-encoded PNG string.

    Uses context manager to ensure doc.close() is always called (VIS-04 / file handle hygiene).
    """
    with fitz.open(file_path) as doc:
        pix = doc[page_number - 1].get_pixmap(dpi=_RENDER_DPI)
        return base64.b64encode(pix.tobytes("png")).decode("utf-8")


def _describe_page_sync(file_path: str, page_number: int) -> str:
    """Render page, invoke vision LLM, return description string (synchronous).

    Instantiates the LLM once per call. Runs inside asyncio.to_thread — do not
    call directly from async context without to_thread.
    """
    b64 = _render_page_to_base64(file_path, page_number)
    llm = get_vision_llm()
    message = HumanMessage(
        content=[
            {"type": "text", "text": VISION_PROMPT},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            },
        ]
    )
    response = llm.invoke([message])
    return response.content.strip()


async def augment_pages_with_vision(
    pages: list[dict],
    file_path: str,
) -> list[dict]:
    """Append vision descriptions to page text for image-bearing pages.

    Respects:
      - VIS-03: opt-in guard (returns pages unchanged when vision_model is empty)
      - VIS-06: vision_max_pages cost cap (0 = unlimited)
      - VIS-04: per-page exception isolation (logs warning, continues)

    Args:
        pages: List of page dicts with keys: page_number, text, has_images, word_count.
               Mutates text field in-place for augmented pages.
        file_path: Absolute path to the PDF file on disk.

    Returns:
        The same pages list (text fields potentially augmented).
    """
    if not settings.vision_model:
        return pages  # VIS-03: opt-in guard — empty string is falsy

    max_pages = settings.vision_max_pages  # 0 = unlimited
    processed = 0

    for page in pages:
        if max_pages and processed >= max_pages:
            logger.info(
                "vision_max_pages=%d reached; skipping remaining pages for %s",
                max_pages,
                file_path,
            )
            break

        if not page.get("has_images"):
            continue  # skip text-only pages; do NOT increment processed

        try:
            description = await asyncio.to_thread(
                _describe_page_sync, file_path, page["page_number"]
            )
            if description:
                page["text"] = (
                    page["text"] + "\n\n[Visual content: " + description + "]"
                )
            processed += 1  # VIS-06: count only pages where a call was made
        except Exception as exc:
            logger.warning(
                "Vision extraction failed for page %d of %s: %s",
                page["page_number"],
                file_path,
                exc,
            )
            # VIS-04: exception logged, pipeline continues; processed NOT incremented

    return pages
