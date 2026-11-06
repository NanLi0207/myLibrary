"""Your marks in the reading view are written into the library's PDF (reader.save_marks)."""

import io

import pytest
import reader
from pypdf import PdfWriter


def pdf_bytes(pages: int, note: str = "") -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(200, 200)
    if note:
        writer.add_metadata({"/Subject": note})
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(reader, "LIBRARY", tmp_path)
    (tmp_path / "books").mkdir()
    (tmp_path / "books" / "a-book.pdf").write_bytes(pdf_bytes(3))
    return tmp_path


def test_the_marked_pdf_replaces_the_book_and_the_original_is_kept(library):
    original = (library / "books" / "a-book.pdf").read_bytes()
    marked = pdf_bytes(3, "with my highlights")
    assert reader.save_marks("books/a-book.pdf", marked)["saved"]
    assert (library / "books" / "a-book.pdf").read_bytes() == marked
    kept = library / "archive" / "before-marks" / "books" / "a-book.pdf"
    assert kept.read_bytes() == original
    reader.save_marks("books/a-book.pdf", pdf_bytes(3, "more marks"))
    assert kept.read_bytes() == original  # the first original, not the last save


def test_anything_but_the_same_whole_pdf_is_refused(library):
    before = (library / "books" / "a-book.pdf").read_bytes()
    with pytest.raises(ValueError, match="whole PDF"):
        reader.save_marks("books/a-book.pdf", b"<html>not a pdf</html>")
    with pytest.raises(ValueError, match="whole PDF"):
        reader.save_marks("books/a-book.pdf", pdf_bytes(3)[:-200])  # cut short
    with pytest.raises(ValueError, match="2 pages, the book 3"):
        reader.save_marks("books/a-book.pdf", pdf_bytes(2))
    with pytest.raises(ValueError, match="isn't in the library"):
        reader.save_marks("books/gone.pdf", pdf_bytes(3))
    assert (library / "books" / "a-book.pdf").read_bytes() == before
    assert not (library / "archive").exists()
