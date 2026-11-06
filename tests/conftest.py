import book_ocr
import library_page
import library_server
import pytest
import subjects


@pytest.fixture(autouse=True)
def no_writes_to_real_project(tmp_path, monkeypatch):
    """Redirect every file the scripts write, so tests never touch the real library."""
    monkeypatch.setattr(library_page, "PAGE", tmp_path / "library.html")
    monkeypatch.setattr(library_server, "CACHE", tmp_path / ".cache" / "chapter_pages.json")
    monkeypatch.setattr(book_ocr, "CACHE_DIR", tmp_path / ".cache" / "ocr")
    # No subject lookups online in tests (a test that needs one gives its own answer)
    monkeypatch.setattr(subjects, "lookup", lambda row: {})
