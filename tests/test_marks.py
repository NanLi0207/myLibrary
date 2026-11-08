"""Your marks in the reading view are written into the library's PDF (reader.save_marks).

D5: every save names the version of the PDF its marks were made on (the SHA-256 of the bytes
the tab loaded, then of what it last saved). The library's PDF is written only if it is still
exactly that version; otherwise nothing is written to it and the tab's PDF is kept, verified,
in archive/marks-conflicts/ (MarksConflict). A copy that can't be kept, or a write that can't
be verified, is an error, never a success."""

import hashlib
import io
import re

import library_jobs
import pytest
import reader
from pypdf import PdfReader, PdfWriter

FILE = "books/a-book.pdf"


def pdf_bytes(pages: int, note: str = "") -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(200, 200)
    if note:
        writer.add_metadata({"/Subject": note})
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def version(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(reader, "LIBRARY", tmp_path)
    (tmp_path / "books").mkdir()
    (tmp_path / FILE).write_bytes(pdf_bytes(3))
    return tmp_path


def conflict_copies(library) -> list:
    folder = library / "archive" / "marks-conflicts"
    return sorted(p for p in folder.rglob("*") if p.is_file()) if folder.exists() else []


def test_the_marked_pdf_replaces_the_book_and_the_original_is_kept(library):
    original = (library / FILE).read_bytes()
    marked = pdf_bytes(3, "with my highlights")
    saved = reader.save_marks(FILE, marked, base=version(original))
    assert saved["saved"] and saved["version"] == version(marked)
    assert (library / FILE).read_bytes() == marked
    kept = library / "archive" / "before-marks" / FILE
    assert kept.read_bytes() == original
    reader.save_marks(FILE, pdf_bytes(3, "more marks"), base=saved["version"])
    assert kept.read_bytes() == original  # the first original, not the last save


def test_anything_but_the_same_whole_pdf_is_refused(library):
    before = (library / FILE).read_bytes()
    base = version(before)
    with pytest.raises(ValueError, match="whole PDF"):
        reader.save_marks(FILE, b"<html>not a pdf</html>", base=base)
    with pytest.raises(ValueError, match="whole PDF"):
        reader.save_marks(FILE, pdf_bytes(3)[:-200], base=base)  # cut short
    with pytest.raises(ValueError, match="2 pages, the book 3"):
        reader.save_marks(FILE, pdf_bytes(2), base=base)
    with pytest.raises(ValueError, match="isn't in the library"):
        reader.save_marks("books/gone.pdf", pdf_bytes(3), base=base)
    assert (library / FILE).read_bytes() == before
    assert not (library / "archive").exists()


@pytest.mark.parametrize("base", ["", "abc", "G" * 64, version(b"x").upper(), None])
def test_a_save_without_a_proper_version_is_refused(library, base):
    before = (library / FILE).read_bytes()
    with pytest.raises(ValueError, match="version"):
        reader.save_marks(FILE, pdf_bytes(3, "marks"), base=base)
    assert (library / FILE).read_bytes() == before and conflict_copies(library) == []


def test_saves_in_a_row_each_build_on_the_last(library):
    base = version((library / FILE).read_bytes())
    for n in range(3):
        data = pdf_bytes(3, f"marks {n}")
        answer = reader.save_marks(FILE, data, base=base)
        assert answer["version"] == version(data) == version((library / FILE).read_bytes())
        base = answer["version"]
    assert conflict_copies(library) == []


def test_a_stale_version_writes_nothing_and_keeps_the_tabs_pdf(library):
    """Two tabs (D5): the first saves; the second, on the version both loaded, gets a conflict.
    Its PDF is kept in archive/marks-conflicts/, byte for byte and readable."""
    loaded = version((library / FILE).read_bytes())
    first = pdf_bytes(3, "first tab's marks")
    reader.save_marks(FILE, first, base=loaded)
    second = pdf_bytes(3, "second tab's marks")
    with pytest.raises(reader.MarksConflict) as conflict:
        reader.save_marks(FILE, second, base=loaded)
    assert (library / FILE).read_bytes() == first  # the first tab's marks stay
    assert conflict.value.current == version(first)
    [copy] = conflict_copies(library)
    assert copy.read_bytes() == second and len(PdfReader(copy).pages) == 3
    assert conflict.value.kept == copy.relative_to(library).as_posix()
    name = r"archive/marks-conflicts/books/a-book\.\d{8}-\d{6}-\d{6}\.[0-9a-f]{8}\.pdf"
    assert re.fullmatch(name, conflict.value.kept)


def test_a_replaced_pdf_with_other_pages_still_keeps_the_tabs_marks(library):
    """The PDF was replaced (OCR, a better copy) by one with other pages: the tab's PDF can't
    go there, but it is kept all the same."""
    loaded = version((library / FILE).read_bytes())
    (library / FILE).write_bytes(pdf_bytes(5, "replaced"))
    mine = pdf_bytes(3, "my marks")
    with pytest.raises(reader.MarksConflict):
        reader.save_marks(FILE, mine, base=loaded)
    [copy] = conflict_copies(library)
    assert copy.read_bytes() == mine


def test_conflict_copies_never_overwrite_each_other(library):
    loaded = version((library / FILE).read_bytes())
    reader.save_marks(FILE, pdf_bytes(3, "first"), base=loaded)
    kept = set()
    for n in range(5):  # several in the same second
        with pytest.raises(reader.MarksConflict) as conflict:
            reader.save_marks(FILE, pdf_bytes(3, f"stale {n}"), base=loaded)
        kept.add(conflict.value.kept)
    assert len(kept) == 5 and len(conflict_copies(library)) == 5


def test_keeping_another_copy_never_touches_the_pdf(library):
    before = (library / FILE).read_bytes()
    mine = pdf_bytes(3, "more marks after the conflict")
    answer = reader.keep_marks_copy(FILE, mine)
    [copy] = conflict_copies(library)
    assert answer["kept"] == copy.relative_to(library).as_posix() and copy.read_bytes() == mine
    assert (library / FILE).read_bytes() == before
    with pytest.raises(ValueError, match="whole PDF"):
        reader.keep_marks_copy(FILE, b"not a pdf")


def test_a_copy_that_cant_be_written_is_an_error(library, monkeypatch):
    loaded = version((library / FILE).read_bytes())
    first = pdf_bytes(3, "first")
    reader.save_marks(FILE, first, base=loaded)
    write_bytes = reader.safe_io.write_bytes

    def disk_full(path, data, **kw):
        if "marks-conflicts" in str(path):
            raise OSError(28, "No space left on device")
        return write_bytes(path, data, **kw)

    monkeypatch.setattr(reader.safe_io, "write_bytes", disk_full)
    with pytest.raises(reader.MarksNotKept, match="only in the tab"):
        reader.save_marks(FILE, pdf_bytes(3, "second"), base=loaded)
    assert (library / FILE).read_bytes() == first and conflict_copies(library) == []


def test_a_copy_that_doesnt_read_back_the_same_is_an_error(library, monkeypatch):
    loaded = version((library / FILE).read_bytes())
    reader.save_marks(FILE, pdf_bytes(3, "first"), base=loaded)
    read_bytes = reader.safe_io.read_bytes
    monkeypatch.setattr(
        reader.safe_io, "read_bytes",
        lambda path: b"damaged" if "marks-conflicts" in str(path) else read_bytes(path),
    )  # fmt: skip
    with pytest.raises(reader.MarksNotKept):
        reader.save_marks(FILE, pdf_bytes(3, "second"), base=loaded)


def test_a_save_that_doesnt_read_back_the_same_is_never_a_success(library, monkeypatch):
    loaded = version((library / FILE).read_bytes())
    read_bytes = reader.safe_io.read_bytes
    monkeypatch.setattr(
        reader.safe_io, "read_bytes",
        lambda path: b"damaged" if str(path).endswith("a-book.pdf") else read_bytes(path),
    )  # fmt: skip
    with pytest.raises(reader.MarksNotKept, match="couldn't be checked"):
        reader.save_marks(FILE, pdf_bytes(3, "mine"), base=loaded)


def test_clear_archive_keeps_every_conflict_copy(library, monkeypatch):
    monkeypatch.setattr(library_jobs.add_book, "ARCHIVE", library / "archive")
    loaded = version((library / FILE).read_bytes())
    reader.save_marks(FILE, pdf_bytes(3, "first"), base=loaded)
    with pytest.raises(reader.MarksConflict):
        reader.save_marks(FILE, pdf_bytes(3, "second"), base=loaded)
    copies = conflict_copies(library)
    library_jobs.clear_archive()
    assert conflict_copies(library) == copies and all(p.exists() for p in copies)
