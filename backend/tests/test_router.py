import pytest
from unittest.mock import patch
from app.retrieval.router import classify_query

LABELLED_TEST_SET = [
    # pageindex — chapter/section navigation queries
    {"query": "What does chapter 3 cover?", "expected": "pageindex", "has_pageindex": True},
    {"query": "Summarise the introduction section of the book", "expected": "pageindex", "has_pageindex": True},
    {"query": "What topics are covered in section 2.1?", "expected": "pageindex", "has_pageindex": True},
    # vector — broad semantic queries
    {"query": "What are the main causes of climate change?", "expected": "vector", "has_pageindex": True},
    {"query": "Compare photosynthesis and cellular respiration", "expected": "vector", "has_pageindex": True},
    {"query": "Explain Newton's second law of motion", "expected": "vector", "has_pageindex": True},
    # hybrid — structural + semantic
    {"query": "What does chapter 2 say about mitosis and how does it relate to meiosis?", "expected": "hybrid", "has_pageindex": True},
    {"query": "Find all sections discussing protein synthesis and compare their key claims", "expected": "hybrid", "has_pageindex": True},
    # RETR-02 fallback — no pageindex docs → always "vector" regardless of query type
    {"query": "What is DNA replication?", "expected": "vector", "has_pageindex": False},
    {"query": "What chapter covers evolution?", "expected": "vector", "has_pageindex": False},
]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_router_accuracy_gate():
    """RETR-01: router must score >= 8/10 on labelled test set."""
    correct = 0
    results = []

    for case in LABELLED_TEST_SET:
        if case["has_pageindex"]:
            source_ids = ["test-source-with-pageindex"]
            mock_doc_ids = ["mock-pageindex-doc-id"]
        else:
            source_ids = ["test-source-no-pageindex"]
            mock_doc_ids = []

        with patch("app.retrieval.router._get_pageindex_doc_ids", return_value=mock_doc_ids):
            result = await classify_query(case["query"], source_ids)

        passed = result == case["expected"]
        correct += int(passed)
        results.append({
            "query": case["query"],
            "expected": case["expected"],
            "got": result,
            "passed": passed,
        })

    print(f"\nRouter accuracy: {correct}/10")
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status}] {r['query'][:50]} → expected={r['expected']}, got={r['got']}")

    assert correct >= 8, (
        f"Router accuracy gate FAILED: {correct}/10 correct. "
        f"Need >= 8/10 before Phase 4 begins. See output above for failures."
    )


@pytest.mark.asyncio
async def test_retr02_fallback_no_pageindex_docs():
    """RETR-02: when no sources have pageindex_doc_id, classify_query returns 'vector' without LLM call."""
    with patch("app.retrieval.router._get_pageindex_doc_ids", return_value=[]):
        with patch("app.retrieval.router._router_chain") as mock_chain:
            result = await classify_query("What chapter covers DNA?", ["source-1"])
            mock_chain.invoke.assert_not_called()
    assert result == "vector"


@pytest.mark.asyncio
async def test_retr02_fallback_empty_source_ids():
    """RETR-02: empty source list also returns 'vector' without LLM call."""
    with patch("app.retrieval.router._get_pageindex_doc_ids", return_value=[]):
        result = await classify_query("Any query", [])
    assert result == "vector"
