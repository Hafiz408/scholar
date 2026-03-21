"""Tests for pageindex_builder — local PageIndex tree building and cleanup."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ingestion.pageindex_builder import (
    _tree_path,
    build_pageindex_tree,
    delete_pageindex_doc,
)
from app.config import settings


# ---------------------------------------------------------------------------
# _tree_path
# ---------------------------------------------------------------------------


def test_tree_path_format():
    """_tree_path should return upload_dir/<source_id>_tree.json."""
    path = _tree_path("abc-123")
    assert path == Path(settings.upload_dir) / "abc-123_tree.json"


# ---------------------------------------------------------------------------
# build_pageindex_tree
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_skips_url_source():
    """build_pageindex_tree returns None immediately for URL sources (file_path=None)."""
    result = await build_pageindex_tree(None, "Some URL Doc", source_id="sid-1")
    assert result is None


@pytest.mark.asyncio
async def test_build_saves_tree_and_returns_source_id(tmp_path):
    """build_pageindex_tree saves tree JSON and returns source_id on success."""
    fake_tree = {"doc_name": "test", "structure": []}

    with (
        patch("app.ingestion.pageindex_builder._build_tree_sync", return_value=fake_tree),
        patch(
            "app.ingestion.pageindex_builder._tree_path",
            return_value=tmp_path / "sid-2_tree.json",
        ),
        patch("asyncio.to_thread", new=AsyncMock(return_value=fake_tree)),
    ):
        result = await build_pageindex_tree("/fake/file.pdf", "Test Doc", source_id="sid-2")

    assert result == "sid-2"
    saved = tmp_path / "sid-2_tree.json"
    assert saved.exists()
    data = json.loads(saved.read_text())
    assert data == fake_tree


@pytest.mark.asyncio
async def test_build_returns_none_on_exception():
    """build_pageindex_tree returns None (not raises) when _build_tree_sync fails."""
    with patch(
        "asyncio.to_thread", new=AsyncMock(side_effect=RuntimeError("model error"))
    ):
        result = await build_pageindex_tree("/any.pdf", "Doc", source_id="sid-3")

    assert result is None


# ---------------------------------------------------------------------------
# delete_pageindex_doc
# ---------------------------------------------------------------------------


def test_delete_removes_existing_file(tmp_path):
    """delete_pageindex_doc removes the tree file when it exists."""
    tree_file = tmp_path / "sid-4_tree.json"
    tree_file.write_text("{}")

    with patch(
        "app.ingestion.pageindex_builder._tree_path",
        return_value=tree_file,
    ):
        delete_pageindex_doc("sid-4")

    assert not tree_file.exists()


def test_delete_silent_when_file_missing(tmp_path):
    """delete_pageindex_doc does not raise when the tree file is absent."""
    missing = tmp_path / "ghost_tree.json"
    with patch(
        "app.ingestion.pageindex_builder._tree_path",
        return_value=missing,
    ):
        delete_pageindex_doc("ghost")  # must not raise


def test_delete_silent_on_os_error(tmp_path):
    """delete_pageindex_doc swallows OS errors gracefully."""
    tree_file = tmp_path / "sid-5_tree.json"
    tree_file.write_text("{}")

    broken_path = MagicMock()
    broken_path.exists.return_value = True
    broken_path.unlink.side_effect = PermissionError("no permission")

    with patch(
        "app.ingestion.pageindex_builder._tree_path",
        return_value=broken_path,
    ):
        delete_pageindex_doc("sid-5")  # must not raise
