# Tests — Scholar Backend

pytest suite covering ingestion, retrieval, all agents, and API routing. All tests run without live LLM or database connections — every external call is mocked.

---

## Running Tests

```bash
# Standard run (CI-equivalent — excludes live-LLM gate)
pytest tests/ -m "not integration" -v

# Full run (requires LLM_API_KEY set)
pytest tests/ -v

# Single file
pytest tests/test_adaptive_planner.py -v
```

**Result: 93 pass, 1 deselected (integration gate).**

---

## Test Architecture

```
tests/
├── conftest.py                   # shared markers only
├── fixtures/
│   └── sample.pdf                # 5-page test PDF committed to repo
│
├── # ── V1 core ──────────────────────────────────────────────
├── test_pdf_extractor.py         # pdfplumber extraction, word count, has_images
├── test_pageindex_builder.py     # tree build, polling, failure/None fallback
├── test_router.py                # query classification; accuracy gate (integration)
├── test_vector_retriever.py      # pgvector search with mock connection
├── test_retrieval.py             # hybrid merge, dedup, weighted fusion
├── test_planner.py               # session count formula, deterministic output
├── test_quiz_agent.py            # scoring 0.0/1.0/partial, per-question correctness
│
├── # ── V2 agents ────────────────────────────────────────────
├── test_adaptive_planner.py      # followup insertion, session renumbering
├── test_final_test_agent.py      # test generation, scoring, goal completion
├── test_super_agent.py           # cross-source retrieval, empty KB, SSE shape
├── test_vision_ingestion.py      # opt-in vision, max_pages cap, exception safety
├── test_notion_mcp.py            # auth errors, backoff, session_page_count
├── test_langsmith_activation.py  # env injection, key-absent guard
│
└── # ── Integration ──────────────────────────────────────────
    test_api_integration.py       # HTTP-level endpoint tests (requires live DB)
```

---

## Test Coverage by Area

### Ingestion

| Test | What it verifies |
|------|-----------------|
| `test_pdf_extractor.py` | 5-page fixture → 5 page dicts; pages < 20 words skipped; `has_images` flag; word count |
| `test_pageindex_builder.py` | Poll stops on `status=ready`; `TimeoutError` after 30 polls; `None` on API unavailable |
| `test_vision_ingestion.py` | `vision_model=""` → no-op; `has_images=False` → skipped; mock LLM response parsed; `vision_max_pages` cap; exception logged, ingestion not blocked; pipeline calls augmentor |

### Retrieval

| Test | What it verifies |
|------|-----------------|
| `test_router.py` | Mock LLM structured output → correct strategy; fallback to `vector` when no pageindex_doc_id |
| `test_router.py::test_router_accuracy_gate` | ≥ 8/10 accuracy on 10 labelled queries **[integration — live LLM]** |
| `test_vector_retriever.py` | Rows sorted by score desc; source_id filter applied; `retrieval_method="vector"` |
| `test_retrieval.py` | `merge_results` weighted fusion; SHA-256 dedup; hybrid dispatch via `asyncio.gather` |

### Agents

| Test | What it verifies |
|------|-----------------|
| `test_planner.py` | 14-day/3-per-week → 6 sessions; sequential numbering; source titles in prompt |
| `test_quiz_agent.py` | All correct → 1.0; all wrong → 0.0; per-question `correct`+`explanation` |
| `test_adaptive_planner.py` | score ≥ 0.65 → `None` (no write); score < 0.65 → followup inserted; downstream sessions renumbered; completed sessions keep their number; LLM exception → `None` |
| `test_final_test_agent.py` | 6 sessions → 6–12 questions; cap at 15; session_numbers tagged correctly; score ≥ 0.70 → goal `complete`; score < 0.70 → unchanged; weak_session_numbers; 400 if sessions pending |
| `test_super_agent.py` | Only `status=ready` sources; empty KB → SSE error event; hybrid_retriever called with all source_ids; different thread_ids → independent history; citation source_title present |
| `test_notion_mcp.py` | Empty API key → 400 no HTTP call; HTTP 401 → error message; HTTP 429 → 3 retries with backoff; sessions without notes skipped; session_page_count accurate; goal_page_url returned on success |
| `test_langsmith_activation.py` | Env vars injected when key set; not injected when key absent; Settings fields exist |

---

## Mocking Conventions

### LLM calls
```python
from unittest.mock import patch, MagicMock

# Structured output (planner, router, adaptive planner)
mock_chain = MagicMock()
mock_chain.invoke.return_value = StudyPlanOutput(sessions=[...], rationale="...")
with patch("app.agents.planner._plan_chain", mock_chain):
    ...

# Streaming (note generator, session chat)
async def fake_astream(messages):
    for chunk in ["Hello ", "world"]:
        yield AIMessageChunk(content=chunk)

with patch.object(llm, "astream", fake_astream):
    ...
```

### SQLite (aiosqlite)
Tests that need database writes use `tmp_path` fixtures to create isolated SQLite files — never touch `settings.sqlite_path`:
```python
@pytest_asyncio.fixture
async def tmp_db(tmp_path):
    db_path = str(tmp_path / "test.sqlite")
    async with aiosqlite.connect(db_path) as db:
        await db.execute("CREATE TABLE ...")
        await db.commit()
    return db_path
```

### HTTP (httpx / Notion)
```python
with patch("app.agents.notion_mcp.httpx.AsyncClient") as mock_client:
    mock_client.return_value.__aenter__.return_value.post.return_value.status_code = 200
    ...
```

---

## Markers

| Marker | Meaning | CI behaviour |
|--------|---------|-------------|
| `@pytest.mark.integration` | Requires live LLM API key | Excluded by `-m "not integration"` |
| *(none)* | Fully mocked, no external deps | Always runs |

Define custom markers in `conftest.py`:
```python
def pytest_configure(config):
    config.addinivalue_line("markers", "integration: requires live APIs")
```

---

## pytest Configuration (`pytest.ini`)

```ini
[pytest]
asyncio_mode = auto    # all async tests auto-detected; no @pytest.mark.asyncio needed
pythonpath = .         # imports from app/ work without install
```

> Async fixtures must still use `@pytest_asyncio.fixture` even with `asyncio_mode = auto`.
> Requires `pytest-asyncio >= 0.23.8` for compatibility with `pytest >= 8.3.0`.

---

## Adding New Tests

1. Place test file in `tests/`
2. Name test functions `test_<what>_<condition>` (e.g., `test_adaptive_planner_score_below_threshold`)
3. Use `@pytest_asyncio.fixture` for async fixtures (not `@pytest.fixture`)
4. Add `@pytest.mark.integration` for any test making real network/LLM calls
5. Always mock `settings.sqlite_path` with `tmp_path` — never use the real DB file
