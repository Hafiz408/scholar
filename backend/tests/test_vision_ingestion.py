"""
Tests for Phase 9: Vision Ingestion (VIS-01 through VIS-06).

All tests use monkeypatching — no live LLM API key or real PDF required.
"""
import pytest
import pytest_asyncio


# ── VIS-01 ─────────────────────────────────────────────────────────────────
# get_vision_llm() raises ValueError with "vision_model" in message when empty

def test_get_vision_llm_raises_when_model_empty(monkeypatch):
    """VIS-01: ValueError raised with descriptive message when vision_model is ''."""
    from app.config import Settings
    import app.core.llm_factory as factory

    monkeypatch.setattr(factory, "settings", Settings(vision_model="", _env_file=None))
    with pytest.raises(ValueError, match="vision_model"):
        factory.get_vision_llm()


def test_get_vision_llm_returns_chat_model_when_configured(monkeypatch):
    """VIS-01: Returns a BaseChatModel when vision_model is set (openai provider)."""
    from app.config import Settings
    from langchain_core.language_models.chat_models import BaseChatModel
    import app.core.llm_factory as factory

    monkeypatch.setattr(
        factory,
        "settings",
        Settings(
            vision_model="gpt-4o-mini",
            llm_provider="openai",
            openai_api_key="sk-test",
            _env_file=None,
        ),
    )
    llm = factory.get_vision_llm()
    assert isinstance(llm, BaseChatModel)


# ── VIS-03: Opt-in guard ────────────────────────────────────────────────────
# augment_pages_with_vision is a no-op when vision_model is ""

@pytest.mark.asyncio
async def test_augment_no_op_when_vision_disabled(monkeypatch):
    """VIS-03: Pages returned unchanged when vision_model is empty."""
    import app.ingestion.vision_extractor as ve

    monkeypatch.setattr(ve.settings, "vision_model", "")
    pages = [
        {"page_number": 1, "text": "original text", "has_images": True, "word_count": 2}
    ]
    result = await ve.augment_pages_with_vision(pages, "fake.pdf")
    assert result[0]["text"] == "original text"


# ── VIS-02: Vision description appended to page text ───────────────────────

@pytest.mark.asyncio
async def test_augment_appends_description_to_image_page(monkeypatch):
    """VIS-02: Vision description appended to text for has_images=True pages."""
    import app.ingestion.vision_extractor as ve

    monkeypatch.setattr(ve.settings, "vision_model", "gpt-4o-mini")
    monkeypatch.setattr(ve.settings, "vision_max_pages", 0)  # unlimited
    monkeypatch.setattr(
        ve,
        "_describe_page_sync",
        lambda file_path, page_number: "A bar chart showing quarterly sales.",
    )
    pages = [
        {"page_number": 1, "text": "Chapter text.", "has_images": True, "word_count": 2}
    ]
    result = await ve.augment_pages_with_vision(pages, "fake.pdf")
    assert "[Visual content: A bar chart showing quarterly sales.]" in result[0]["text"]
    assert result[0]["text"].startswith("Chapter text.")


@pytest.mark.asyncio
async def test_augment_skips_text_only_pages(monkeypatch):
    """VIS-02: Pages with has_images=False are not processed (no LLM call)."""
    import app.ingestion.vision_extractor as ve

    monkeypatch.setattr(ve.settings, "vision_model", "gpt-4o-mini")
    monkeypatch.setattr(ve.settings, "vision_max_pages", 0)
    call_count = {"n": 0}

    def fake_describe(file_path, page_number):
        call_count["n"] += 1
        return "some description"

    monkeypatch.setattr(ve, "_describe_page_sync", fake_describe)
    pages = [
        {"page_number": 1, "text": "only text", "has_images": False, "word_count": 2}
    ]
    await ve.augment_pages_with_vision(pages, "fake.pdf")
    assert call_count["n"] == 0


# ── VIS-04: Exception isolation ─────────────────────────────────────────────
# Per-page exception must not propagate; page text remains unchanged

@pytest.mark.asyncio
async def test_vision_exception_logged_not_raised(monkeypatch):
    """VIS-04: RuntimeError in _describe_page_sync logged; pages returned normally."""
    import app.ingestion.vision_extractor as ve

    monkeypatch.setattr(ve.settings, "vision_model", "gpt-4o-mini")
    monkeypatch.setattr(ve.settings, "vision_max_pages", 0)

    def boom(file_path, page_number):
        raise RuntimeError("mock LLM error")

    monkeypatch.setattr(ve, "_describe_page_sync", boom)
    pages = [
        {"page_number": 1, "text": "original text", "has_images": True, "word_count": 2}
    ]
    # Must NOT raise
    result = await ve.augment_pages_with_vision(pages, "fake.pdf")
    assert result[0]["text"] == "original text"


# ── VIS-06: vision_max_pages cost cap ──────────────────────────────────────

@pytest.mark.asyncio
async def test_vision_max_pages_caps_llm_calls(monkeypatch):
    """VIS-06: Only vision_max_pages LLM calls made even when more image pages exist."""
    import app.ingestion.vision_extractor as ve

    monkeypatch.setattr(ve.settings, "vision_model", "gpt-4o-mini")
    monkeypatch.setattr(ve.settings, "vision_max_pages", 2)
    call_count = {"n": 0}

    def fake_describe(file_path, page_number):
        call_count["n"] += 1
        return "description"

    monkeypatch.setattr(ve, "_describe_page_sync", fake_describe)
    pages = [
        {"page_number": i, "text": f"text {i}", "has_images": True, "word_count": 2}
        for i in range(1, 6)  # 5 image-bearing pages
    ]
    await ve.augment_pages_with_vision(pages, "fake.pdf")
    assert call_count["n"] == 2  # capped at vision_max_pages=2


# ── VIS-05: pipeline.py Stage 1.5 wiring ───────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_calls_vision_augmentation_for_pdf(monkeypatch):
    """VIS-05: run_ingestion calls augment_pages_with_vision for pdf source_type.

    Note: pipeline.py imports augment_pages_with_vision via a local import inside
    the pdf branch. We patch app.ingestion.vision_extractor.augment_pages_with_vision
    before run_ingestion executes so the local `from ... import` picks up our mock.
    """
    import app.ingestion.pipeline as pipeline_mod
    import app.ingestion.vision_extractor as ve_mod

    call_log = {"called": False, "file_path": None}

    async def fake_augment(pages, file_path):
        call_log["called"] = True
        call_log["file_path"] = file_path
        return pages

    # Patch augment_pages_with_vision on the vision_extractor module.
    # Pipeline does: from app.ingestion.vision_extractor import augment_pages_with_vision
    # inside the function body — the local import will resolve to the patched attribute
    # because sys.modules["app.ingestion.vision_extractor"] is already loaded.
    monkeypatch.setattr(ve_mod, "augment_pages_with_vision", fake_augment)

    # Patch extract_pdf — called via asyncio.to_thread (sync callable)
    monkeypatch.setattr(
        pipeline_mod,
        "extract_pdf",
        lambda fp: (
            [{"page_number": 1, "text": "t", "has_images": False, "word_count": 1}],
            {"total_pages": 1},
        ),
    )

    # Patch async pipeline stages
    async def fake_build_pageindex(*a, **kw):
        return None

    async def fake_embed_and_store(*a, **kw):
        return 0

    monkeypatch.setattr(pipeline_mod, "build_pageindex_tree", fake_build_pageindex)
    monkeypatch.setattr(pipeline_mod, "embed_and_store", fake_embed_and_store)

    # Patch get_session (ORM) to avoid real DB connection.
    # pipeline.py calls get_session() twice: once to update page_count,
    # once to mark status=ready. Both are fire-and-forget within the test.
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock, MagicMock

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())
    mock_session.commit = AsyncMock()

    @asynccontextmanager
    async def fake_get_session():
        yield mock_session

    monkeypatch.setattr(pipeline_mod, "get_session", fake_get_session)

    await pipeline_mod.run_ingestion(
        source_id="test-uuid",
        file_path="/fake/path/book.pdf",
        url=None,
        source_type="pdf",
        title="Test Book",
    )
    assert call_log["called"] is True
    assert call_log["file_path"] == "/fake/path/book.pdf"
