import asyncio
from app.core.logging import get_logger
import trafilatura

logger = get_logger(__name__)


async def extract_url(url: str) -> dict:
    """Fetch and extract main text from a URL. Async-safe via asyncio.to_thread.

    Returns:
        dict with keys: title, text, url, word_count, page_count
        page_count = max(1, word_count // 300) — estimated pages from word count
    """
    downloaded = await asyncio.to_thread(trafilatura.fetch_url, url)
    if not downloaded:
        raise ValueError(f"Could not fetch URL: {url}")

    text = await asyncio.to_thread(trafilatura.extract, downloaded, include_tables=True)
    if not text:
        raise ValueError(f"Could not extract text from URL: {url}")

    meta = await asyncio.to_thread(trafilatura.extract_metadata, downloaded)
    title = (meta.title if meta and meta.title else url)

    word_count = len(text.split())
    return {
        "title": title,
        "text": text,
        "url": url,
        "word_count": word_count,
        "page_count": max(1, word_count // 300),
    }
