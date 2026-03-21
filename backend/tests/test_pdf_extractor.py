"""Tests for the PDF extractor — runs against the real "Test book.pdf"."""
import pytest
from pathlib import Path
from app.ingestion.pdf_extractor import extract_pdf

TEST_PDF = Path(__file__).parent.parent.parent / "Test book.pdf"

_skip_if_no_pdf = pytest.mark.skipif(
    not TEST_PDF.exists(),
    reason=f"Test PDF not found at {TEST_PDF}",
)


@_skip_if_no_pdf
def test_returns_nonempty_pages():
    """PDF with real content should yield at least one page."""
    pages, metadata = extract_pdf(str(TEST_PDF))
    assert len(pages) > 0, "Expected at least one extractable page"
    assert metadata["total_pages"] > 0


@_skip_if_no_pdf
def test_page_schema():
    """Every returned page must have the required keys and valid values."""
    pages, _ = extract_pdf(str(TEST_PDF))
    for page in pages:
        assert "page_number" in page
        assert "text" in page
        assert "has_images" in page
        assert "word_count" in page
        assert isinstance(page["page_number"], int) and page["page_number"] >= 1
        assert isinstance(page["text"], str) and len(page["text"]) > 0
        assert isinstance(page["has_images"], bool)
        assert isinstance(page["word_count"], int) and page["word_count"] >= 20


@_skip_if_no_pdf
def test_skips_low_word_count_pages():
    """Pages with fewer than 20 words must not appear in output."""
    pages, _ = extract_pdf(str(TEST_PDF))
    for page in pages:
        assert page["word_count"] >= 20, (
            f"Page {page['page_number']} has {page['word_count']} words — should be filtered"
        )


@_skip_if_no_pdf
def test_word_count_matches_text():
    """word_count field must match actual split count of text."""
    pages, _ = extract_pdf(str(TEST_PDF))
    for page in pages[:5]:  # spot-check first 5
        assert page["word_count"] == len(page["text"].split())


@_skip_if_no_pdf
def test_page_numbers_are_ascending():
    """Page numbers in output should be in ascending order."""
    pages, _ = extract_pdf(str(TEST_PDF))
    numbers = [p["page_number"] for p in pages]
    assert numbers == sorted(numbers)


def test_nonexistent_file_raises():
    """extract_pdf must raise for a missing path."""
    with pytest.raises(Exception):
        extract_pdf("/tmp/nonexistent_scholar_test_9999.pdf")
