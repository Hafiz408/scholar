"""Tests for the vector retriever — DB and embedding calls are mocked."""
import pytest
from unittest.mock import patch, MagicMock
from app.retrieval.vector_retriever import embed_query, vector_search
from app.models.schemas import RetrievedChunk


# ---------------------------------------------------------------------------
# embed_query
# ---------------------------------------------------------------------------


def test_embed_query_returns_float_list():
    """embed_query returns a non-empty list of floats from the OpenAI client."""
    mock_embedding = [0.1] * 1536
    mock_resp = MagicMock()
    mock_resp.data = [MagicMock(embedding=mock_embedding)]

    with patch("app.retrieval.vector_retriever._get_embedding_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_resp
        mock_client_fn.return_value = mock_client

        result = embed_query("What is DNA?")

    assert isinstance(result, list)
    assert len(result) == 1536
    assert all(isinstance(v, float) for v in result)


# ---------------------------------------------------------------------------
# vector_search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vector_search_returns_empty_for_no_source_ids():
    """vector_search returns [] immediately when source_ids is empty."""
    result = await vector_search("any query", source_ids=[], top_k=5)
    assert result == []


@pytest.mark.asyncio
async def test_vector_search_maps_rows_to_retrieved_chunks():
    """vector_search maps DB rows to RetrievedChunk with correct fields."""
    fake_rows = [
        ("src-uuid-1", "Test Book", "Photosynthesis is the process...", 42, 0.87),
        ("src-uuid-1", "Test Book", "Chlorophyll absorbs light...", 43, 0.73),
    ]
    mock_embedding = [0.0] * 1536

    with patch("app.retrieval.vector_retriever.embed_query", return_value=mock_embedding):
        with patch("app.retrieval.vector_retriever._vector_search_sync", return_value=fake_rows):
            results = await vector_search("What is photosynthesis?", ["src-uuid-1"], top_k=5)

    assert len(results) == 2
    first = results[0]
    assert isinstance(first, RetrievedChunk)
    assert first.source_id == "src-uuid-1"
    assert first.source_title == "Test Book"
    assert first.content == "Photosynthesis is the process..."
    assert first.page_number == 42
    assert first.relevance_score == pytest.approx(0.87)
    assert first.retrieval_method == "vector"


@pytest.mark.asyncio
async def test_vector_search_returns_empty_on_exception():
    """vector_search catches exceptions and returns [] rather than raising."""
    with patch("app.retrieval.vector_retriever.embed_query", side_effect=ConnectionError("db down")):
        result = await vector_search("query", ["src-1"], top_k=5)
    assert result == []


@pytest.mark.asyncio
async def test_vector_search_respects_top_k():
    """top_k value must be forwarded to the sync search function."""
    captured_top_k = []

    def capture_sync(embedding, source_ids, top_k):
        captured_top_k.append(top_k)
        return []

    with patch("app.retrieval.vector_retriever.embed_query", return_value=[0.0] * 1536):
        with patch("app.retrieval.vector_retriever._vector_search_sync", side_effect=capture_sync):
            await vector_search("query", ["src-1"], top_k=10)

    assert captured_top_k == [10]
