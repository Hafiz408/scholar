import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from app.retrieval.hybrid_retriever import merge_results, retrieve
from app.models.schemas import RetrievedChunk, RetrievalResult


def make_chunk(content, score, method):
    return RetrievedChunk(
        source_id="src-1",
        source_title="Test Book",
        content=content,
        relevance_score=score,
        retrieval_method=method,
    )


class TestMergeResults:
    def test_empty_both_lists_returns_empty(self):
        assert merge_results([], []) == []

    def test_only_pageindex_chunks(self):
        chunks = [make_chunk("alpha", 0.9, "pageindex"), make_chunk("beta", 0.5, "pageindex")]
        result = merge_results(chunks, [])
        assert len(result) == 2
        assert result[0].relevance_score == pytest.approx(0.9 * 0.6)

    def test_only_vector_chunks(self):
        chunks = [make_chunk("gamma", 0.8, "vector")]
        result = merge_results([], chunks)
        assert result[0].relevance_score == pytest.approx(0.8 * 0.4)

    def test_dedup_by_content_hash(self):
        pi_chunk = make_chunk("shared content", 1.0, "pageindex")
        vec_chunk = make_chunk("shared content", 0.9, "vector")
        unique = make_chunk("unique content", 0.5, "vector")
        result = merge_results([pi_chunk], [vec_chunk, unique])
        assert len(result) == 2  # dedup collapses shared content to one entry
        # Merged score: 1.0*0.6 + 0.9*0.4 = 0.96
        merged = next(r for r in result if r.content == "shared content")
        assert merged.relevance_score == pytest.approx(0.96)

    def test_does_not_mutate_input_chunks(self):
        chunk = make_chunk("test", 0.8, "pageindex")
        original_score = chunk.relevance_score
        merge_results([chunk], [])
        assert chunk.relevance_score == original_score  # input not mutated

    def test_sorted_by_score_descending(self):
        chunks = [make_chunk(f"content {i}", float(i) / 10, "pageindex") for i in range(1, 4)]
        result = merge_results(chunks, [])
        scores = [r.relevance_score for r in result]
        assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_retrieve_routes_to_vector_strategy():
    """retrieve() dispatches to vector_search when strategy is 'vector'."""
    expected_chunks = [make_chunk("vector result", 0.9, "vector")]

    with patch("app.retrieval.hybrid_retriever.classify_query", return_value="vector"):
        with patch("app.retrieval.hybrid_retriever.vector_search", return_value=expected_chunks):
            result = await retrieve("What is DNA?", ["src-1"], top_k=5)

    assert isinstance(result, RetrievalResult)
    assert result.strategy_used == "vector"
    assert result.chunks == expected_chunks


@pytest.mark.asyncio
async def test_retrieve_hybrid_calls_both_retrievers_concurrently():
    """retrieve() with hybrid strategy calls both retrievers and merges results."""
    pi_chunks = [make_chunk("pageindex result", 0.8, "pageindex")]
    vec_chunks = [make_chunk("vector result", 0.7, "vector")]

    async def mock_pageindex(*args, **kwargs):
        return pi_chunks

    with patch("app.retrieval.hybrid_retriever.classify_query", return_value="hybrid"):
        with patch("app.retrieval.hybrid_retriever.vector_search", return_value=vec_chunks):
            with patch("app.retrieval.hybrid_retriever.fetch_pageindex_chunks", side_effect=mock_pageindex):
                with patch(
                    "app.retrieval.hybrid_retriever._get_sources_with_pageindex",
                    return_value=[("doc-1", "src-1", "Book")]
                ):
                    result = await retrieve("hybrid query", ["src-1"], top_k=5)

    assert result.strategy_used == "hybrid"
    assert len(result.chunks) >= 1  # merged results returned
