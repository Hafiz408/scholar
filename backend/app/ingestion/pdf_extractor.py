import pdfplumber
import pypdf
import logging

logger = logging.getLogger(__name__)


def extract_pdf(file_path: str) -> tuple[list[dict], dict]:
    """Extract text from a PDF file page by page.

    Uses pdfplumber as primary extractor with pypdf as per-page fallback.
    Pages with fewer than 20 words (blank/diagram-only) are skipped.

    Returns:
        (pages, metadata) where pages is a list of page dicts and
        metadata is {"total_pages": int}.
        Each page dict: {"page_number": int, "text": str, "has_images": bool, "word_count": int}
    """
    pages = []
    with pdfplumber.open(file_path) as pdf:
        total = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            try:
                text = page.extract_text() or ""
                has_images = len(page.images) > 0
            except Exception as e:
                logger.warning(f"pdfplumber failed on page {i+1}: {e}, falling back to pypdf")
                try:
                    reader = pypdf.PdfReader(file_path)
                    text = reader.pages[i].extract_text() or ""
                    has_images = False
                except Exception as e2:
                    logger.warning(f"pypdf also failed on page {i+1}: {e2}, skipping")
                    continue
            words = text.split()
            if len(words) < 20:
                continue
            pages.append({
                "page_number": i + 1,
                "text": text,
                "has_images": has_images,
                "word_count": len(words),
            })
    return pages, {"total_pages": total}
