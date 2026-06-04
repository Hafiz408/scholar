import asyncio

import aiosqlite
from pydantic import BaseModel, Field
from typing import Literal

from app.config import settings
from app.llm_factory import get_llm


class RouterDecision(BaseModel):
    strategy: Literal["pageindex", "vector", "hybrid"] = Field(
        description=(
            "Classification of the query into one of three retrieval strategies:\n"
            "- 'pageindex': query explicitly asks for chapter/section navigation, page numbers, "
            "or structured book outline — e.g. 'What does chapter 3 cover?' or "
            "'Summarise the introduction'\n"
            "- 'vector': query is a broad semantic or factual question not tied to a specific "
            "book structure — e.g. 'Explain photosynthesis' or 'Compare DNA replication methods'\n"
            "- 'hybrid': query combines structural navigation with semantic depth — "
            "e.g. 'What does chapter 2 say about mitosis and how does it relate to meiosis?'"
        )
    )


_router_chain = get_llm(temperature=0).with_structured_output(RouterDecision)


async def _get_pageindex_doc_ids(source_ids: list[str]) -> list[str]:
    """Query SQLite for non-null pageindex_doc_id values for the given source IDs."""
    if not source_ids:
        return []

    placeholders = ",".join("?" * len(source_ids))
    query = (
        f"SELECT pageindex_doc_id FROM knowledge_sources "
        f"WHERE id IN ({placeholders}) AND pageindex_doc_id IS NOT NULL"
    )

    async with aiosqlite.connect(settings.sqlite_path) as db:
        async with db.execute(query, source_ids) as cursor:
            rows = await cursor.fetchall()

    return [row[0] for row in rows]


async def classify_query(query: str, source_ids: list[str]) -> str:
    """Classify a query into a retrieval strategy.

    RETR-02: If no sources have a pageindex_doc_id, returns 'vector' immediately
    without making any LLM call. Otherwise calls the configured LLM with structured
    output to classify into pageindex / vector / hybrid.

    Args:
        query: The user's natural-language query.
        source_ids: List of knowledge source IDs to consider.

    Returns:
        One of 'pageindex', 'vector', or 'hybrid'.
    """
    pageindex_doc_ids = await _get_pageindex_doc_ids(source_ids)

    if not pageindex_doc_ids:
        return "vector"

    decision = await asyncio.to_thread(
        _router_chain.invoke,
        [{"role": "user", "content": f"Classify this query: {query}"}],
    )
    return decision.strategy
