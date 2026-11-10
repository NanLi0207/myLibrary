"""Names, repeats, replacing and archiving: different documents never share a name, a name
alone never makes two documents "the same", and nothing of the user's is replaced or lost.

Temporary libraries and invented documents only.
"""

import io
import threading
import time
from pathlib import Path

import add_book
import catalog
import library_jobs
import ocr_pdf
import pytest
from book_meta import Meta
from book_toc import Chapter
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Highlight
from pypdf.generic import ArrayObject, FloatObject
from reportlab.pdfgen import canvas
from testlib import entry, id_of, put  # noqa: F401

CHINESE_TITLES = "甲乙丙丁戊己庚辛壬癸子丑"  # 12 different titles, none with a Latin letter


@pytest.fixture
def library(tmp_path, monkeypatch):
    """An empty temporary library; no network, no page building, no search index."""
    for name in ("BOOKS", "PAPERS", "THESES", "EXAMPLES", "NOTES"):
        monkeypatch.setattr(add_book, name, tmp_path / name.lower())
    monkeypatch.setattr(add_book, "CATALOG", tmp_path / "catalog.csv")
    monkeypatch.setattr(add_book, "ARCHIVE", tmp_path / "archive")
    monkeypatch.setattr(add_book, "LIBRARY", tmp_path)
    monkeypatch.setattr(add_book, "PAGE_CACHE", tmp_path / ".cache" / "chapter_pages.json")
    monkeypatch.setattr(library_jobs.library_page, "build", lambda: None)
    monkeypatch.setattr(library_jobs.book_search, "update", lambda: 0)
    monkeypatch.setattr(library_jobs, "_jobs", {})
    return tmp_path


def text_pdf(label: str = "") -> bytes:
    """A searchable one-page PDF; different bytes on every call (ReportLab's random ID)."""
    out = io.BytesIO()
    c = canvas.Canvas(out)
    for line in range(20):
        c.drawString(72, 720 - 20 * line, f"Invented text {label} line {line}.")
    c.showPage()
    c.save()
    return out.getvalue()


def scan_pdf() -> bytes:
    """A page without text, like a scan: any searchable copy is "richer"."""
    out = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(200, 200)
    writer.write(out)
    return out.getvalue()


def marked(data: bytes) -> bytes:
    """The same PDF with a highlight in it (as the reading view or any PDF program saves)."""
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(data)))
    rect = (10, 10, 100, 30)
    quad = ArrayObject([FloatObject(v) for v in (10, 30, 100, 30, 10, 10, 100, 10)])
    writer.add_annotation(page_number=0, annotation=Highlight(rect=rect, quad_points=quad))
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def add(library, meta: Meta, data: bytes, name: str = "upload.pdf") -> dict:
    return wait(library_jobs.start_add(library_jobs.save_upload(name, data)))


def names(library) -> list[str]:
    return sorted(r["slug"] for r in catalog.load(library / "catalog.csv").values())


def wait(job: dict, seconds: float = 30) -> dict:
    end = time.time() + seconds
    while time.time() < end:
        (current,) = [j for j in library_jobs.list_jobs() if j["id"] == job["id"]]
        if current["status"] != "working":
            if current.get("doc_id"):
                rows = catalog.load(library_jobs.add_book.CATALOG)
                current["slug"] = rows[current["doc_id"]]["slug"]  # its name, to read tests
            return current
        time.sleep(0.02)
    raise AssertionError("job didn't finish")


def identify_by_upload(monkeypatch, metas: dict[str, Meta]):
    """identify() answers by the upload's file name (save_upload keeps it)."""

    def identify(path, online, **kw):
        time.sleep(0.02)  # a lookup takes a moment: concurrent jobs really overlap
        return metas[path.stem]

    monkeypatch.setattr(library_jobs, "identify", identify)


def registered(library, slug, data, folder="books", **row) -> Path:
    pdf = library / folder / f"{slug}.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(data)
    notes = library / "notes" / slug
    notes.mkdir(parents=True, exist_ok=True)
    (notes / "README.md").write_text("# x\n\n- [x] Chapter 1\n\nLast read: page 7\n", "utf-8")
    put(library / "catalog.csv", {"slug": slug, "title": slug, "added": "2026-01-01",
                                             "file": f"{folder}/{slug}.pdf"} | row)  # fmt: skip
    return pdf


# --- different documents never share a name ---------------------------------------------------


def test_two_chinese_titled_documents_of_one_year_are_both_kept(library, monkeypatch):
    a = Meta(title="光学设计", author="张三", year="2020")
    b = Meta(title="激光技术", author="李四", year="2020")
    assert add_book.Book(a.title, a.author, a.year).base_slug == "unknown-2020-untitled"
    assert add_book.Book(b.title, b.author, b.year).base_slug == "unknown-2020-untitled"
    data_a, data_b = text_pdf("a"), text_pdf("b")
    identify_by_upload(monkeypatch, {"a": a, "b": b})

    first, second = add(library, a, data_a, "a.pdf"), add(library, b, data_b, "b.pdf")
    assert first["status"] == second["status"] == "done"
    assert (first["slug"], second["slug"]) == ("unknown-2020-untitled", "unknown-2020-untitled-2")
    assert "unknown-2020-untitled is another document's name" in second["message"]
    path = library / "catalog.csv"
    assert entry(path, "unknown-2020-untitled")["title"] == "光学设计"
    assert entry(path, "unknown-2020-untitled-2")["title"] == "激光技术"
    assert first["doc_id"] != second["doc_id"] and all(
        map(catalog.is_id, (first["doc_id"], second["doc_id"]))
    )
    rows = {r["slug"]: r for r in catalog.load(path).values()}
    assert (library / "books" / "unknown-2020-untitled.pdf").read_bytes() == data_a
    assert (library / "books" / "unknown-2020-untitled-2.pdf").read_bytes() == data_b
    for slug in rows:
        assert (library / "notes" / slug / "README.md").exists()
    assert not (library / "archive").exists()  # nothing was taken for a repeat


def test_many_documents_with_one_candidate_name_get_numbered_names(library, monkeypatch):
    titles = ["Optical Design", "Optical Design: A Primer", "Optical design (2nd ed.)"]
    metas = {f"d{n}": Meta(title=t, author="Ann Lee", year="2015") for n, t in enumerate(titles)}
    identify_by_upload(monkeypatch, metas)
    slugs = [add(library, metas[k], text_pdf(k), f"{k}.pdf")["slug"] for k in metas]
    assert slugs == ["lee-2015-optical-design", "lee-2015-optical-design-2",
                     "lee-2015-optical-design-3"]  # fmt: skip
    assert len(catalog.load(library / "catalog.csv")) == 3


def test_a_name_left_by_notes_without_a_book_is_not_reused(library, monkeypatch):
    """Notes whose book was moved away by hand still belong to that book: a new document with
    the same name must not take them over."""
    (library / "notes" / "lee-2015-optics").mkdir(parents=True)
    (library / "notes" / "lee-2015-optics" / "ch01-basics.md").write_text("mine", "utf-8")
    identify_by_upload(monkeypatch, {"x": Meta(title="Optics", author="Ann Lee", year="2015")})
    job = add(library, None, text_pdf(), "x.pdf")
    assert job["slug"] == "lee-2015-optics-2"
    assert (library / "notes" / "lee-2015-optics" / "ch01-basics.md").read_text("utf-8") == "mine"


def test_concurrent_imports_with_the_same_candidate_name(library, monkeypatch):
    metas = {f"c{n}": Meta(title=f"光学{ch}", author="王五", year="2021")
             for n, ch in enumerate(CHINESE_TITLES)}  # fmt: skip
    identify_by_upload(monkeypatch, metas)
    data = {k: text_pdf(k) for k in metas}
    uploads = [library_jobs.save_upload(f"{k}.pdf", data[k]) for k in metas]
    jobs = [wait(j) for j in [library_jobs.start_add(p) for p in uploads]]

    assert [j["message"] for j in jobs if j["status"] != "done"] == []
    rows = catalog.load(library / "catalog.csv")
    assert len(rows) == len(metas) == len({j["slug"] for j in jobs})
    by_title = {m.title: k for k, m in metas.items()}
    for row in rows.values():  # every name holds its own document, whole
        assert (library / row["file"]).read_bytes() == data[by_title[row["title"]]]
        assert (library / row["notes"] / "README.md").exists()


# --- repeats need proof ---------------------------------------------------------------------------


def test_the_exact_same_pdf_uploaded_again_and_again_is_added_once(library, monkeypatch):
    meta = Meta(title="Practical Lens Design", author="Jane Doe", year="2015")
    monkeypatch.setattr(library_jobs, "identify", lambda path, online, **kw: meta)
    data = text_pdf()
    first = add(library, meta, data, "same.pdf")
    later = [add(library, meta, data, "same.pdf") for _ in range(2)]
    together = [wait(j) for j in [library_jobs.start_add(library_jobs.save_upload("same.pdf", data))
                                  for _ in range(3)]]  # fmt: skip

    assert first["status"] == "done"
    assert [j["status"] for j in later + together] == ["duplicate"] * 5
    assert all("identical file" in j["message"] for j in later + together)
    assert names(library) == [first["slug"]]
    assert (library / "books" / f"{first['slug']}.pdf").read_bytes() == data
    archived = sorted((library / "archive" / "books").iterdir())
    assert len(archived) == 5 and all(p.read_bytes() == data for p in archived)


def test_different_pdfs_with_the_same_file_name_are_different_documents(library, monkeypatch):
    calls = iter([Meta(title="Ray Optics", author="Ann Lee", year="2018"),
                  Meta(title="Wave Optics", author="Bo Chen", year="2019")])  # fmt: skip
    monkeypatch.setattr(library_jobs, "identify", lambda path, online, **kw: next(calls))
    a, b = text_pdf("ray"), text_pdf("wave")
    ja, jb = add(library, None, a, "paper.pdf"), add(library, None, b, "paper.pdf")
    assert (ja["status"], jb["status"]) == ("done", "done")
    assert (library / "books" / f"{ja['slug']}.pdf").read_bytes() == a
    assert (library / "books" / f"{jb['slug']}.pdf").read_bytes() == b


def test_a_same_titled_different_file_never_replaces_the_library_pdf(library, monkeypatch):
    """The old rule: the same name meant the same work, and a "richer" file replaced the
    library's PDF, even though it might be a different document."""
    old = registered(library, "doe-2015-practical-lens-design", scan_pdf(),
                     title="Practical Lens Design", authors="Jane Doe", year="2015")  # fmt: skip
    before = old.read_bytes()
    meta = Meta(title="Practical Lens Design", author="Jane Doe", year="2015")
    monkeypatch.setattr(library_jobs, "identify", lambda path, online, **kw: meta)
    job = add(library, meta, text_pdf())  # searchable: "richer" than the scan
    assert job["status"] == "done" and job["slug"] == "doe-2015-practical-lens-design-2"
    assert "possibly the same work" in job["message"]
    assert old.read_bytes() == before
    readme = library / "notes" / "doe-2015-practical-lens-design" / "README.md"
    assert "Last read: page 7" in readme.read_text("utf-8")
    doc = id_of(library / "catalog.csv", "doe-2015-practical-lens-design")
    with pytest.raises(ValueError, match="not a proven repeat"):
        add_book.handle_repeat(old, meta, doc, reason="same author, year and title")


def test_a_pdf_with_your_marks_and_notes_is_never_replaced(library, monkeypatch):
    # Same DOI, and searchable: this used to replace an unmarked PDF. No DOI (B29) or ISBN
    # (L21) proves the same PDF now: the copy is a document of its own, nothing replaced
    old = registered(library, "doe-2019-freeform", marked(scan_pdf()), doi="10.1/freeform",
                     type="book", title="Freeform", authors="Jane Doe", year="2019")  # fmt: skip
    before = old.read_bytes()
    assert add_book.has_marks(old)
    meta = Meta(title="Freeform", author="Jane Doe", year="2019", doi="10.1/freeform",
                publisher="Example Press")  # fmt: skip
    monkeypatch.setattr(library_jobs, "identify", lambda path, online, **kw: meta)
    job = add(library, meta, text_pdf())
    assert job["status"] == "done" and "shares its DOI with doe-2019-freeform" in job["message"]
    assert old.read_bytes() == before and add_book.has_marks(old)  # your marks, in place
    readme = library / "notes" / "doe-2019-freeform" / "README.md"
    assert "Last read: page 7" in readme.read_text("utf-8")
    assert not (library / "archive").exists()  # nothing moved to the archive
    row = entry(library / "catalog.csv", "doe-2019-freeform")
    assert row["publisher"] == ""  # the other document's details are not put into this entry


def test_marks_saved_from_the_reading_view_count_too(library):
    pdf = registered(library, "doe-2019-freeform", scan_pdf())
    assert not add_book.has_marks(pdf)
    original = library / "archive" / "before-marks" / "books" / pdf.name
    original.parent.mkdir(parents=True)
    original.write_bytes(scan_pdf())
    assert add_book.has_marks(pdf)


def test_refresh_never_archives_the_copy_with_your_marks(library):
    """Two entries sharing a DOI, one of them with your marks: a shared DOI is no proof of the
    same PDF (B29), and a marked PDF is never byte-identical to an unmarked one, so Refresh
    never pairs them: both stay, with their files."""
    plain = registered(library, "doe-2019-freeform", text_pdf(), doi="10.1/x", type="book",
                       added="2026-01-01")  # fmt: skip
    (library / "notes" / "doe-2019-freeform" / "README.md").write_text("# x\n", "utf-8")
    mine = registered(library, "doe-2019-freeform-optics", marked(scan_pdf()), doi="10.1/x",
                      type="book", added="2026-02-01")  # fmt: skip
    (library / "notes" / "doe-2019-freeform-optics" / "README.md").write_text("# x\n", "utf-8")
    assert add_book.catalog_repeats() == []
    assert plain.exists() and mine.exists() and add_book.has_marks(mine)


# --- archive names --------------------------------------------------------------------------------


def test_archive_names_never_collide(library):
    for n in range(4):
        pdf = library / "books" / "doe-2015-x.pdf"
        pdf.parent.mkdir(exist_ok=True)
        pdf.write_bytes(f"version {n}".encode())
        add_book.move_to_archive(pdf)
    archived = sorted((library / "archive" / "books").iterdir())
    assert len(archived) == 4
    assert sorted(p.read_bytes() for p in archived) == [f"version {n}".encode() for n in range(4)]
    for n in range(3):  # folders too
        notes = library / "notes" / "doe-2015-x"
        notes.mkdir(parents=True)
        (notes / "README.md").write_text(f"notes {n}", "utf-8")
        add_book.move_to_archive(notes)
    assert len(list((library / "archive" / "notes").iterdir())) == 3


def test_concurrent_archiving_of_one_name(library):
    files = []
    for folder in ("books", "papers", "theses"):
        pdf = library / folder / "same.pdf"
        pdf.parent.mkdir()
        pdf.write_bytes(folder.encode())
        files.append(pdf)
    threads = [threading.Thread(target=add_book.move_to_archive, args=(f, "books")) for f in files]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    archived = sorted(p.read_bytes() for p in (library / "archive" / "books").iterdir())
    assert archived == [b"books", b"papers", b"theses"]


def test_removing_twice_on_one_day_keeps_every_archived_copy(library):
    for n in range(3):
        registered(library, "doe-2015-x", f"pdf {n}".encode())
        add_book.remove_book(id_of(library / "catalog.csv", "doe-2015-x"), dry_run=False, yes=True)
    assert len(list((library / "archive" / "books").iterdir())) == 3
    assert len(list((library / "archive" / "notes").iterdir())) == 3


# --- interrupted operations -----------------------------------------------------------------------


def test_an_interrupted_replacement_puts_the_library_pdf_back(library, monkeypatch):
    old = registered(library, "doe-2019-freeform", scan_pdf(), isbn="9780070591783")
    before = old.read_bytes()
    new = library / "books" / "upload.pdf"
    new.write_bytes(text_pdf())
    real_rename = Path.rename

    def failing_rename(self, target):
        if self == new:  # the second step: the new copy into the library's place
            raise PermissionError("the file is open in another program")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", failing_rename)
    with pytest.raises(PermissionError):
        add_book.replace_pdf(id_of(library / "catalog.csv", "doe-2019-freeform"), new,
                             Meta(isbn="9780070591783"))  # fmt: skip
    assert old.read_bytes() == before  # back in its place
    assert new.exists()
    assert not list((library / "archive" / "books").glob("*"))


def test_an_interrupted_removal_moves_everything_back(library, monkeypatch):
    pdf = registered(library, "doe-2015-x", text_pdf())
    doc = id_of(library / "catalog.csv", "doe-2015-x")

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(catalog, "remove", fail)
    with pytest.raises(OSError):
        add_book.remove_book(doc, dry_run=False, yes=True)
    assert pdf.exists() and (library / "notes" / "doe-2015-x" / "README.md").exists()
    assert doc in catalog.load(library / "catalog.csv")
    # and its tombstone was taken back: the document is in the library, not retired
    assert catalog.resolve(library / "catalog.csv", doc)["status"] == "live"
    assert catalog.check(library / "catalog.csv") == []


def test_an_interrupted_ocr_swap_keeps_the_book(library, monkeypatch):
    pdf = library / "books" / "doe-2015-scan.pdf"
    pdf.parent.mkdir()
    pdf.write_bytes(b"%PDF original")
    new = library / "ocr-output.pdf"
    new.write_bytes(b"%PDF with text")
    keep = library / "archive" / "books" / pdf.name
    real_replace = Path.replace

    def failing_replace(self, target):
        if self == new:
            raise PermissionError("locked")
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", failing_replace)
    with pytest.raises(SystemExit):  # ocr_pdf's message for a locked file
        ocr_pdf.replace_pdf(pdf, new, keep, source=ocr_pdf.fingerprint(pdf))  # (unchanged PDF)
    assert pdf.read_bytes() == b"%PDF original" and not keep.exists()


# --- never the library itself ---------------------------------------------------------------------


@pytest.mark.parametrize("file", ["", "books", "books/", "../outside.pdf", "notes/x.pdf"])
def test_an_entry_without_a_proper_pdf_is_never_replaced(library, file):
    put(library / "catalog.csv", {"slug": "doe-2015-x", "file": file})
    upload = library / "books" / "upload.pdf"
    upload.parent.mkdir()
    upload.write_bytes(text_pdf())
    meta = Meta(isbn="9780070591783")
    with pytest.raises(ValueError):
        add_book.replace_pdf(id_of(library / "catalog.csv", "doe-2015-x"), upload, meta)
    assert (
        add_book.richer_than_library(upload, meta, id_of(library / "catalog.csv", "doe-2015-x"))
        == ""
    )
    assert upload.exists() and (library / "catalog.csv").exists()


def test_a_folder_is_never_taken_for_the_library_pdf(library):
    (library / "books" / "doe-2015-x.pdf").mkdir(parents=True)  # a folder with a PDF's name
    put(library / "catalog.csv", {"slug": "doe-2015-x", "file": "books/doe-2015-x.pdf"})
    upload = library / "books" / "upload.pdf"
    upload.write_bytes(text_pdf())
    with pytest.raises(ValueError, match="isn't a file"):
        add_book.replace_pdf(id_of(library / "catalog.csv", "doe-2015-x"), upload, Meta())
    assert (library / "books" / "doe-2015-x.pdf").is_dir() and upload.exists()


def test_the_library_and_its_folders_are_never_moved(library, tmp_path_factory):
    (library / "books").mkdir()
    (library / "archive" / "books").mkdir(parents=True)
    (library / "archive" / "books" / "old.pdf").write_bytes(b"x")
    outside = tmp_path_factory.mktemp("elsewhere") / "mine.pdf"
    outside.write_bytes(b"x")
    for path in (library, library / "books", library / "archive" / "books" / "old.pdf",
                 library / "catalog.csv", outside):  # fmt: skip
        with pytest.raises(ValueError):
            add_book.move_to_archive(path)
    assert (library / "books").is_dir() and outside.exists()


def test_a_book_is_never_placed_over_an_existing_file(library):
    book = add_book.Book("Optics", "Ann Lee", "2015", name="lee-2015-optics")
    (library / "books").mkdir()
    (library / "books" / "lee-2015-optics.pdf").write_bytes(b"theirs")
    upload = library / "books" / "upload.pdf"
    upload.write_bytes(b"mine")
    with pytest.raises(FileExistsError):
        add_book.place_book(upload, book, Meta())
    assert (library / "books" / "lee-2015-optics.pdf").read_bytes() == b"theirs"


# --- chapter notes --------------------------------------------------------------------------------


def test_refreshing_chapters_keeps_your_notes_and_archives_old_templates(library, monkeypatch):
    pdf = registered(library, "doe-2015-x", text_pdf())
    notes = library / "notes" / "doe-2015-x"
    mine = notes / "ch01-basics.md"
    mine.write_text("# Chapter 1: Basics\n\nMy own summary of the basics.\n", "utf-8")
    template = notes / "ch02-chapter-2.md"
    template.write_text("# Chapter 2: Chapter 2\n\n## Key ideas\n\n-\n", "utf-8")
    new = [Chapter(1, "Basics"), Chapter(2, "Lenses"), Chapter(3, "Mirrors")]
    monkeypatch.setattr(add_book, "book_chapters", lambda path: new)

    for _ in range(2):  # twice: the second archived template doesn't overwrite the first
        add_book.refresh_chapters(pdf, dry_run=False)
        template.write_text("# Chapter 2: Chapter 2\n\n## Key ideas\n\n-\n", "utf-8")

    assert mine.read_text("utf-8").endswith("My own summary of the basics.\n")
    assert (notes / "ch02-lenses.md").exists() and (notes / "ch03-mirrors.md").exists()
    archived = list((library / "archive" / "notes" / "doe-2015-x").iterdir())
    assert len(archived) == 2 and all(p.name.startswith("ch02-chapter-2") for p in archived)


# --- the command line (add_book.py) --------------------------------------------------------------


def cli_args(**over):
    import argparse

    return argparse.Namespace(**({"offline": True, "ocr": False, "no_ocr": True, "dry_run": False,
                                  "title": None, "author": None, "year": None,
                                  "publisher": ""} | over))  # fmt: skip


def test_the_command_line_names_and_repeats_the_same_way(library, monkeypatch):
    metas = iter([Meta(title="光学设计", author="张三", year="2020"),
                  Meta(title="激光技术", author="李四", year="2020")])  # fmt: skip
    monkeypatch.setattr(add_book, "identify", lambda path, **kw: next(metas))
    (library / "books").mkdir()
    a, b = library / "books" / "a.pdf", library / "books" / "b.pdf"
    a.write_bytes(text_pdf("a"))
    b.write_bytes(text_pdf("b"))
    data_a = a.read_bytes()
    add_book.process(a, cli_args())
    add_book.process(b, cli_args())
    assert names(library) == ["unknown-2020-untitled", "unknown-2020-untitled-2"]

    # A file already named like an entry (copied in by hand), identical to a book: archived
    copy = library / "books" / "zhang-2020-copy.pdf"
    copy.write_bytes(data_a)
    monkeypatch.setattr(add_book, "identify", lambda path, **kw: Meta(title="x", year="2020"))
    add_book.process(copy, cli_args(), rename=False)
    assert not copy.exists() and (library / "archive" / "books" / copy.name).exists()
    assert (library / "books" / "unknown-2020-untitled.pdf").read_bytes() == data_a


def test_a_shared_isbn_with_a_different_title_never_replaces_the_pdf(library, monkeypatch):
    """An ISBN read from the wrong page (e.g. a series advert) must not swap in another book:
    a shared ISBN is no proof at all now (L21), so the other book is a document of its own."""
    old = registered(library, "doe-2019-freeform", scan_pdf(), isbn="9780070591783",
                     type="book", title="Freeform Optics", authors="Jane Doe")  # fmt: skip
    before = old.read_bytes()
    other = Meta(title="Thin Film Coatings", author="Bo Chen", year="2021", isbn="9780070591783")
    monkeypatch.setattr(library_jobs, "identify", lambda path, online, **kw: other)
    job = add(library, other, text_pdf())
    assert job["status"] == "done" and "shares its ISBN with doe-2019-freeform" in job["message"]
    assert old.read_bytes() == before
    # A DOI read from the wrong page, with another title: no proof either (B29), kept apart
    doi = registered(library, "doe-2020-coatings", scan_pdf(), doi="10.1/coatings",
                     type="book", title="Coatings", authors="Jane Doe")  # fmt: skip
    kept = doi.read_bytes()
    stranger = Meta(title="Freeform Lenses", author="Bo Chen", year="2021", doi="10.1/coatings")
    monkeypatch.setattr(library_jobs, "identify", lambda path, online, **kw: stranger)
    job = add(library, stranger, text_pdf("x"))
    assert job["status"] == "done" and "shares its DOI with doe-2020-coatings" in job["message"]
    assert doi.read_bytes() == kept
    # The same work with its subtitle or edition note: titles agree, so a better copy may
    assert add_book.titles_agree("Freeform Optics", "Freeform optics: design and practice")
    assert add_book.titles_agree("光学设计", "光学 设计")
    assert not add_book.titles_agree("光学设计", "激光技术")
