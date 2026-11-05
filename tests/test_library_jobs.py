import time

import add_book
import catalog
import library_jobs
import pytest
from book_meta import Meta
from reportlab.pdfgen import canvas


@pytest.fixture
def library(tmp_path, monkeypatch):
    """An empty library in a temporary folder; no network, no real search index."""
    for name in ("BOOKS", "EXAMPLES", "NOTES"):
        monkeypatch.setattr(add_book, name, tmp_path / name.lower())
    monkeypatch.setattr(add_book, "CATALOG", tmp_path / "catalog.csv")
    monkeypatch.setattr(add_book, "PAGE_CACHE", tmp_path / ".cache" / "chapter_pages.json")
    monkeypatch.setattr(library_jobs.library_page, "build", lambda: None)
    monkeypatch.setattr(library_jobs.book_search, "update", lambda: 0)
    monkeypatch.setattr(library_jobs, "_jobs", {})
    return tmp_path


def text_pdf() -> bytes:
    path = __import__("io").BytesIO()
    c = canvas.Canvas(path)
    for line in range(30):
        c.drawString(72, 720 - 20 * line, f"Line {line} of an invented book about lenses.")
    c.showPage()
    c.save()
    return path.getvalue()


def wait(job: dict) -> dict:
    for _ in range(200):
        current = next(j for j in library_jobs.list_jobs() if j["id"] == job["id"])
        if current["status"] != "working":
            return current
        time.sleep(0.05)
    raise AssertionError("job didn't finish")


def test_upload_is_identified_named_and_registered(library, monkeypatch):
    meta = Meta(title="Practical Lens Design", author="Jane Doe", year="2015")
    monkeypatch.setattr(library_jobs, "identify", lambda path, online: meta)

    path = library_jobs.save_upload("my download (z).pdf", text_pdf())
    assert path.parent == library / "books" and path.name == "my download (z).pdf"
    done = wait(library_jobs.start_add(path))
    assert done["status"] == "done" and done["scan"] is False
    assert done["slug"] == "doe-2015-practical-lens-design"
    assert (library / "books" / "doe-2015-practical-lens-design.pdf").exists()
    assert "doe-2015-practical-lens-design" in catalog.load(library / "catalog.csv")
    assert (library / "notes" / "doe-2015-practical-lens-design" / "README.md").exists()

    # The same book again: recognised, and the second copy is removed
    again = wait(library_jobs.start_add(library_jobs.save_upload("copy.pdf", text_pdf())))
    assert again["status"] == "duplicate" and not (library / "books" / "copy.pdf").exists()


def test_missing_details_are_asked_for(library, monkeypatch):
    monkeypatch.setattr(library_jobs, "identify", lambda path, online: Meta(title="Optics"))
    job = wait(library_jobs.start_add(library_jobs.save_upload("scan001.pdf", text_pdf())))
    assert job["status"] == "needs_details" and job["missing"] == ["author", "year"]
    assert job["guess"]["title"] == "Optics"

    library_jobs.continue_add(job["id"], {"title": "", "author": "Ann Lee", "year": "2001"})
    done = wait(job)
    assert done["status"] == "done" and done["slug"] == "lee-2001-optics"
    with pytest.raises(ValueError):
        library_jobs.continue_add(job["id"], {})  # nothing waiting any more


def test_only_pdfs_are_accepted(library):
    with pytest.raises(ValueError, match="not a PDF"):
        library_jobs.save_upload("notes.txt", b"hello")
    first = library_jobs.save_upload("../../evil?.pdf", text_pdf())
    second = library_jobs.save_upload("../../evil?.pdf", text_pdf())
    assert first.parent == second.parent == library / "books"  # never outside books/
    assert first != second  # an existing file is never overwritten


def test_ocr_reports_progress_one_book_at_a_time(library, monkeypatch):
    pdf = library / "books" / "doe-2015-scan.pdf"
    pdf.parent.mkdir()
    pdf.write_bytes(text_pdf())
    started = []

    def fake_ocr(path, progress):
        started.append(path)
        for page in range(1, 4):
            progress(page, 3)
            time.sleep(0.05)

    monkeypatch.setattr(library_jobs.ocr_pdf, "make_searchable", fake_ocr)
    monkeypatch.setattr(library_jobs.add_book, "refresh_chapters", lambda pdf, dry_run: None)
    job = library_jobs.start_ocr("doe-2015-scan")
    with pytest.raises(ValueError, match="another book"):
        library_jobs.start_ocr("doe-2015-scan")
    done = wait(job)
    assert done["status"] == "done" and (done["done"], done["total"]) == (3, 3)
    assert started == [pdf]
    with pytest.raises(ValueError):
        library_jobs.start_ocr("no-such-book")
