import os
import time

import add_book
import catalog
import library_jobs
import pytest
from book_meta import Meta
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from testlib import entry, id_of, put  # noqa: F401


@pytest.fixture
def library(tmp_path, monkeypatch):
    """An empty library in a temporary folder; no network, no real search index."""
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


def names(library) -> list[str]:
    """The names of the documents in the catalog, sorted."""
    return sorted(r["slug"] for r in catalog.load(library / "catalog.csv").values())


def name_of(library, doc_id: str) -> str:
    return catalog.load(library / "catalog.csv")[doc_id]["slug"]


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
    monkeypatch.setattr(library_jobs, "identify", lambda path, online, **kw: meta)

    path = library_jobs.save_upload("my download (z).pdf", text_pdf())
    assert path.parent == library / "books" and path.name == "my download (z).pdf"
    done = wait(library_jobs.start_add(path))
    assert done["status"] == "done" and done["scan"] is False
    assert catalog.is_id(done["doc_id"])
    assert name_of(library, done["doc_id"]) == "doe-2015-practical-lens-design"
    assert (library / "books" / "doe-2015-practical-lens-design.pdf").exists()
    assert names(library) == ["doe-2015-practical-lens-design"]
    assert (library / "notes" / "doe-2015-practical-lens-design" / "README.md").exists()

    # The very same file again: recognised, and the second copy is moved to the archive
    first = library / "books" / "doe-2015-practical-lens-design.pdf"
    again = wait(library_jobs.start_add(library_jobs.save_upload("copy.pdf", first.read_bytes())))
    assert again["status"] == "duplicate" and not (library / "books" / "copy.pdf").exists()
    assert (library / "archive" / "books" / "copy.pdf").exists()

    # A different file with the same title, author and year: no proof it's the same work (no
    # shared DOI or ISBN), so it's kept under a name of its own and reported, never thrown away
    other = wait(library_jobs.start_add(library_jobs.save_upload("other.pdf", text_pdf())))
    assert other["status"] == "done"
    assert name_of(library, other["doc_id"]) == "doe-2015-practical-lens-design-2"
    assert other["doc_id"] != done["doc_id"]  # a different document, its own id
    assert "possibly the same work as doe-2015-practical-lens-design" in other["message"]
    assert len(catalog.load(library / "catalog.csv")) == 2


def test_nothing_is_ever_asked(library, monkeypatch):
    """Details nobody could find are filled in anyway (here: no author, no year), as
    identify() does with fill_gaps."""
    import book_meta

    def identify(path, online, **kw):
        meta = Meta(title="Optics")  # all a lookup found
        book_meta.fill_gaps(meta, path, {})
        return meta

    monkeypatch.setattr(library_jobs, "identify", identify)
    job = wait(library_jobs.start_add(library_jobs.save_upload("scan001.pdf", text_pdf())))
    year = str(__import__("datetime").date.today().year)  # the file's own date, at worst
    assert job["status"] == "done" and name_of(library, job["doc_id"]) == f"unknown-{year}-optics"


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
    doc = put(library / "catalog.csv", {"slug": "doe-2015-scan", "file": "books/doe-2015-scan.pdf"})
    job = library_jobs.start_ocr(doc)
    with pytest.raises(ValueError, match="another book"):
        library_jobs.start_ocr(doc)
    done = wait(job)
    assert done["status"] == "done" and (done["done"], done["total"]) == (3, 3)
    assert started == [pdf]
    with pytest.raises(ValueError):
        library_jobs.start_ocr("no-such-book")


def test_refresh_adds_pdfs_put_into_the_folders_by_hand(library, monkeypatch):
    """⟳ Refresh: like add_book.py, for files copied into books/, papers/ or theses/."""
    seen = []

    def identify(path, online, paper=False, thesis=False):
        seen.append((path.name, paper, thesis))
        if thesis:
            return Meta(title="Freeform Mirrors", author="Jane Doe", year="2019", kind="thesis")
        return Meta(title="Practical Optics", author="Ann Lee", year="2015")

    monkeypatch.setattr(library_jobs, "identify", identify)
    for folder, name in (("books", "Some Download (1).pdf"), ("theses", "final_version.pdf"),
                         ("books", "lee-2015-practical-optics-handmade.pdf")):  # fmt: skip
        (library / folder).mkdir(exist_ok=True)
        (library / folder / name).write_bytes(text_pdf())

    result = library_jobs.refresh()
    assert result["started"] == 3
    assert library_jobs.refresh()["started"] == 0  # clicked again: nothing twice
    for job in list(library_jobs.list_jobs()):
        wait(job)
    assert ("final_version.pdf", False, True) in seen  # a file in theses/ is a thesis
    assert entry(library / "catalog.csv", "doe-2019-freeform-mirrors")["type"] == "thesis"
    assert (library / "theses" / "doe-2019-freeform-mirrors.pdf").exists()
    assert (library / "books" / "lee-2015-practical-optics.pdf").exists()
    # The one already named by hand keeps its name
    assert "lee-2015-practical-optics-handmade" in names(library)
    assert (library / "notes" / "lee-2015-practical-optics-handmade" / "README.md").exists()

    # The same book copied in again (the very same file): reported, and moved to the archive
    copy = library / "books" / "practical optics copy.pdf"
    copy.write_bytes((library / "books" / "lee-2015-practical-optics.pdf").read_bytes())
    library_jobs.refresh()
    [job] = [j for j in library_jobs.list_jobs() if j["file"] == copy.name]
    job = wait(job)
    assert job["status"] == "duplicate" and "moved to archive/books/" in job["message"]
    assert not copy.exists() and (library / "archive" / "books" / copy.name).exists()
    assert library_jobs.refresh()["started"] == 0  # not reported again


def test_a_damaged_pdf_is_not_added(library):
    """An incomplete download: an error line, no card, and the file stays where it was."""
    broken = library / "books" / "broken.pdf"
    broken.parent.mkdir(exist_ok=True)
    broken.write_bytes(b"%PDF-1.4 cut off halfway")
    library_jobs.refresh()
    [job] = library_jobs.list_jobs()
    job = wait(job)
    assert job["status"] == "error" and "isn't a readable PDF" in job["message"]
    assert broken.exists() and not (library / "catalog.csv").exists()


def test_history_keeps_finished_jobs_until_cleared(library, monkeypatch):
    monkeypatch.setattr(library_jobs, "HISTORY", 2)
    for n in range(3):
        library_jobs._finish(library_jobs._new_job("add", file=f"{n}.pdf"), "done", "ok")
        time.sleep(0.01)
    running = library_jobs._new_job("ocr", file="scan.pdf")
    jobs = library_jobs.list_jobs()
    # Running first, then the newest finished ones (the oldest is forgotten)
    assert [j["file"] for j in jobs] == ["scan.pdf", "2.pdf", "1.pdf"]
    library_jobs.clear_history()
    assert [j["id"] for j in library_jobs.list_jobs()] == [running["id"]]


def _registered(library, slug, folder="papers", **row):
    pdf = library / folder / f"{slug}.pdf"
    pdf.parent.mkdir(exist_ok=True)
    pdf.write_bytes(row.pop("data", text_pdf()))
    (library / "notes" / slug).mkdir(parents=True, exist_ok=True)
    (library / "notes" / slug / "README.md").write_text(
        "# x\n\n- [ ] Chapter 1\n", encoding="utf-8"
    )
    put(
        library / "catalog.csv",
        {"slug": slug, "title": slug, "file": f"{folder}/{slug}.pdf", "added": "2026-01-01"} | row,
    )
    return pdf


def test_repeats_by_doi_isbn_and_identical_file(library):
    _registered(library, "doe-2019-freeform", doi="10.1364/oe.27.1", type="paper")
    _registered(library, "smith-1992-lens-design", folder="books", isbn="9780070591783")
    _registered(library, "lee-2001-proceedings-paper", isbn="9780819491640", type="paper",
                data=b"%PDF-1.4 the same bytes")  # fmt: skip
    new = library / "books" / "x.pdf"
    new.write_bytes(b"%PDF-1.4 something quite different")

    def meta(**kw):
        return Meta(title="X", author="A", year="2000", **kw)

    assert add_book.repeat_of(new, meta(doi="10.1364/OE.27.1", kind="paper")) == (
        id_of(library / "catalog.csv", "doe-2019-freeform"),
        "same DOI",
    )
    assert add_book.repeat_of(new, meta(isbn="0070591784")) == (  # ISBN-10 of the same book
        id_of(library / "catalog.csv", "smith-1992-lens-design"),
        "same ISBN",
    )
    # A paper printing its proceedings volume's ISBN is not a repeat of another paper from it
    assert add_book.repeat_of(new, meta(isbn="9780819491640", kind="paper")) is None
    new.write_bytes(b"%PDF-1.4 the same bytes")  # same contents, whatever its details say
    assert add_book.repeat_of(new, meta()) == (
        id_of(library / "catalog.csv", "lee-2001-proceedings-paper"),
        "identical file",
    )


def test_every_way_in_sends_repeats_to_the_archive(library, monkeypatch):
    _registered(library, "doe-2019-freeform", doi="10.1364/oe.27.1", type="paper")
    found = Meta(title="Freeform", author="Jane Doe", year="2019", doi="10.1364/oe.27.1",
                 kind="paper")  # fmt: skip
    monkeypatch.setattr(library_jobs, "identify", lambda path, online, **kw: found)
    # An upload (the same paper under another name and year)
    job = wait(library_jobs.start_add(library_jobs.save_upload("download.pdf", text_pdf())))
    assert job["status"] == "duplicate" and "same DOI" in job["message"]
    assert (library / "archive" / "books" / "download.pdf").exists()
    # The terminal does the same
    copy = library / "books" / "copy.pdf"
    copy.write_bytes(text_pdf())
    add_book.add_book(copy, add_book.Book("Freeform", "Jane Doe", "2019"), False, found)
    assert not copy.exists() and (library / "archive" / "books" / "copy.pdf").exists()
    assert names(library) == ["doe-2019-freeform"]


def scan_pdf() -> bytes:
    """A page without any text (like a scan without OCR)."""
    from pypdf import PdfWriter

    out = __import__("io").BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(200, 200)
    writer.write(out)
    return out.getvalue()


def test_refresh_keeps_the_richer_copy_and_moves_your_work_to_it(library):
    # The older entry is a bare scan with your work on it; the newer one has searchable text.
    # Keep the searchable one, and move ticks, last-read page, notes, words and scripts over.
    _registered(library, "doe-2019-freeform", doi="10.1/x", type="book", folder="books",
                data=scan_pdf(), added="2026-01-01", shelves="Optics")  # fmt: skip
    _registered(library, "doe-2019-freeform-optics", doi="10.1/x", type="book", folder="books",
                added="2026-03-01", journal="Optics Express")  # fmt: skip
    old = library / "notes" / "doe-2019-freeform"
    (old / "README.md").write_text(
        "# x\n\n## Reading progress\n\nLast read: page 4, 2026-03-02\n\n"
        "- [x] [Ch 1: Intro](ch01-intro.md)\n- [ ] [Ch 2: Stops](ch02-stops.md)\n",
        encoding="utf-8",
    )
    (old / "ch01-intro.md").write_text("# Chapter 1\n\nMy notes on the intro.\n", encoding="utf-8")
    (old / "vocabulary.md").write_text("# Words\n\n- aperture\n", encoding="utf-8")
    (library / "examples" / "doe-2019-freeform").mkdir(parents=True)
    (library / "examples" / "doe-2019-freeform" / "ch01_intro.py").write_text("print(1)")
    new = library / "notes" / "doe-2019-freeform-optics"
    (new / "README.md").write_text(
        "# x\n\n## Reading progress\n\n"
        "- [ ] [Ch 1: Intro](ch01-introduction.md)\n- [ ] [Ch 2: Stops](ch02-stops.md)\n",
        encoding="utf-8",
    )
    (new / "ch01-introduction.md").write_text("# Chapter 1\n\n[Back to book](README.md)\n\n-\n")

    result = library_jobs.refresh()
    assert "1 repeat moved to archive/" in result["message"]
    assert names(library) == ["doe-2019-freeform-optics"]
    readme = (new / "README.md").read_text(encoding="utf-8")
    assert "Last read: page 4, 2026-03-02" in readme and "- [x] [Ch 1: Intro]" in readme
    intro = (new / "ch01-introduction.md").read_text(encoding="utf-8")
    assert intro.endswith("My notes on the intro.\n")  # into the matching (empty) template
    assert (new / "vocabulary.md").exists()
    assert (library / "examples" / "doe-2019-freeform-optics" / "ch01_intro.py").exists()
    assert entry(library / "catalog.csv", "doe-2019-freeform-optics")["shelves"] == "Optics"
    backup = library / "archive" / "notes" / "doe-2019-freeform" / "ch01-intro.md"
    assert backup.exists()  # the original goes to the archive as a backup
    [job] = [j for j in library_jobs.list_jobs() if j["kind"] == "repeat"]
    assert "searchable text" in job["message"] and "last-read page" in job["message"]


def test_equal_copies_keep_the_older_one(library):
    _registered(library, "doe-2019-a", doi="10.1/x", type="paper", added="2026-01-01")
    _registered(library, "doe-2019-b", doi="10.1/x", type="paper", added="2026-03-01")
    library_jobs.refresh()
    assert names(library) == ["doe-2019-a"]


def test_both_with_your_work_are_only_reported(library):
    for slug in ("doe-2019-a", "doe-2019-b"):
        _registered(library, slug, doi="10.1/x", type="paper")
        (library / "notes" / slug / "notes.md").write_text("My own idea", encoding="utf-8")
    result = library_jobs.refresh()
    assert "1 repeat(s) to check" in result["message"]
    assert len(catalog.load(library / "catalog.csv")) == 2


def test_a_better_copy_replaces_the_pdf_and_keeps_your_notes(library, monkeypatch):
    pdf = _registered(library, "doe-2019-freeform", folder="books", data=scan_pdf(),
                      isbn="9780070591783", title="Freeform")  # fmt: skip
    readme = library / "notes" / "doe-2019-freeform" / "README.md"
    readme.write_text("# x\n\nLast read: page 3, 2026-01-02\n", encoding="utf-8")
    found = Meta(title="Freeform", author="Jane Doe", year="2019", isbn="9780070591783",
                 publisher="Example Press")  # fmt: skip
    monkeypatch.setattr(library_jobs, "identify", lambda path, online, **kw: found)
    job = wait(library_jobs.start_add(library_jobs.save_upload("searchable.pdf", text_pdf())))
    assert job["status"] == "done" and "searchable text" in job["message"]
    assert PdfReader(pdf).pages[0].extract_text().startswith("Line 0")  # the new copy
    assert "Last read: page 3" in readme.read_text(encoding="utf-8")  # your notes stay
    row = entry(library / "catalog.csv", "doe-2019-freeform")
    assert row["publisher"] == "Example Press"  # details it lacked, added
    # The same file again: nothing replaced, only archived
    job = wait(library_jobs.start_add(library_jobs.save_upload("again.pdf", text_pdf())))
    assert job["status"] == "duplicate" and "moved to archive/" in job["message"]


def test_clear_archive_keeps_your_writing(library):
    archive = library / "archive"
    (archive / "books").mkdir(parents=True)
    (archive / "books" / "old.pdf").write_bytes(b"x" * 1000)
    empty = archive / "notes" / "old-2001-book"
    empty.mkdir(parents=True)
    (empty / "ch01-intro.md").write_text("# Chapter 1\n\n[Back to book](README.md)\n\n-\n")
    mine = archive / "notes" / "mine-2002-book"
    mine.mkdir()
    (mine / "ch01-intro.md").write_text("# Chapter 1\n\nWhat I learned about stops.\n")

    summary = library_jobs.archive_summary()
    assert summary["kept"] == ["notes/mine-2002-book"] and summary["files"] == 2
    library_jobs.clear_archive()
    assert not (archive / "books").exists() and not empty.exists()
    assert (mine / "ch01-intro.md").exists()
    assert library_jobs.archive_summary()["files"] == 0


def test_clear_archive_never_deletes_scripts(library):
    """Old notebooks or scripts in the archive (from earlier versions) are kept."""
    old = library / "archive" / "notebooks" / "shannon-1997-art"
    old.mkdir(parents=True)
    (old / "ch01_introduction.py").write_text("print('my work')")
    (old / ".gitkeep").write_text("")
    (library / "archive" / "books").mkdir()
    (library / "archive" / "books" / "old scan.djvu").write_bytes(b"x")
    summary = library_jobs.clear_archive()
    assert summary["kept"] == ["notebooks/shannon-1997-art"] and summary["files"] == 2
    assert (old / "ch01_introduction.py").exists()
    assert not (library / "archive" / "books").exists()


TEMPLATE = add_book.chapter_note(add_book.Chapter(1, "Intro", ["Stops"]))


def files_under(folder) -> dict:
    return {
        p.relative_to(folder).as_posix(): p.read_bytes()
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


def test_clear_archive_deletes_only_untouched_templates_and_documents(library):
    """Audit P0-2: a README's own text (with no ticks, no "Last read"), an empty README,
    images, unknown files, nested notes and PDFs kept beside notes all stay. Only archived
    documents, empty .gitkeep files and provably untouched generated templates go."""
    archive = library / "archive"
    written = archive / "notes" / "ann-2001-book"
    (written / "figures").mkdir(parents=True)
    (written / "README.md").write_text("# Ann's book\n\nMy own summary of the stops.\n")
    (written / "ch01-intro.md").write_text(TEMPLATE)  # untouched: goes
    (written / "ch02-stops.md").write_text("# Chapter 2\n\nWhat I learned.\n")
    (written / "vocabulary.md").write_text("# Vocabulary\n")
    (written / "figure.png").write_bytes(b"\x89PNG my sketch")
    (written / "attachment.pdf").write_bytes(b"%PDF my own scan")
    (written / "drawing.xyz").write_bytes(b"unknown")
    (written / "figures" / "ch03-nested.md").write_text(TEMPLATE)  # nested: stays
    empty = archive / "notes" / "bob-2002-book"
    empty.mkdir()
    (empty / "README.md").write_text("")
    (empty / "ch01-intro.md").write_text(TEMPLATE)  # untouched: goes
    paper = archive / "notes" / "cy-2003-paper"
    paper.mkdir()
    (paper / "README.md").write_text("# A paper\n\n- [ ] [Read the paper](notes.md)\n")
    (paper / "notes.md").write_text(add_book.PAPER_NOTES.format(title="A paper"))  # goes
    (archive / "books").mkdir()
    (archive / "books" / "old.pdf").write_bytes(b"%PDF old")
    (archive / "books" / ".gitkeep").write_text("")
    (archive / "odd").mkdir()
    (archive / "odd" / ".gitkeep").write_text("not empty: not a placeholder")
    (archive / "notes" / "loose.md").write_text(TEMPLATE)  # not in a document's folder
    before = files_under(archive)
    gone = {
        "notes/ann-2001-book/ch01-intro.md",
        "notes/bob-2002-book/ch01-intro.md",
        "notes/cy-2003-paper/notes.md",
        "books/old.pdf",
        "books/.gitkeep",
    }

    summary = library_jobs.archive_summary()
    assert summary["files"] == len(gone)
    library_jobs.clear_archive()
    assert files_under(archive) == {k: v for k, v in before.items() if k not in gone}
    assert (empty / "README.md").exists() and (paper / "README.md").exists()
    assert library_jobs.archive_summary()["files"] == 0


def test_clear_archive_never_goes_through_links(library, tmp_path):
    """A junction or symbolic link inside archive/ may lead outside it: never followed, the
    link itself kept, nothing behind it deleted or emptied."""
    if os.name != "nt":
        pytest.skip("junctions are a Windows feature")
    import _winapi

    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "inner").mkdir(parents=True)
    (elsewhere / "ch01-intro.md").write_text(TEMPLATE)
    (elsewhere / "book.pdf").write_bytes(b"%PDF not archived")
    (elsewhere / ".gitkeep").write_text("")
    notes = library / "archive" / "notes"
    notes.mkdir(parents=True)
    _winapi.CreateJunction(str(elsewhere), str(notes / "dee-2004-book"))
    _winapi.CreateJunction(str(elsewhere), str(library / "archive" / "books"))
    try:
        os.symlink(elsewhere / "book.pdf", library / "archive" / "linked.pdf")
    except OSError:  # symlinks need Developer Mode or administrator rights; junctions don't
        if os.environ.get("MYLIBRARY_REQUIRE_LINK_TESTS") == "1":  # CI: must be tested
            raise
    before = files_under(elsewhere)

    assert library_jobs.archive_summary()["files"] == 0
    library_jobs.clear_archive()
    assert files_under(elsewhere) == before and (elsewhere / "inner").is_dir()
    assert (notes / "dee-2004-book").exists() and (library / "archive" / "books").exists()


def test_ocr_of_a_locked_pdf_ends_with_a_message(library, monkeypatch):
    """A PDF open in another program can't be replaced: the job must end, not spin forever."""
    pdf = library / "books" / "doe-2015-scan.pdf"
    pdf.parent.mkdir(exist_ok=True)
    pdf.write_bytes(text_pdf())

    def locked(path, progress=None):
        raise SystemExit("  ! doe-2015-scan.pdf is open in another program")

    monkeypatch.setattr(library_jobs.ocr_pdf, "make_searchable", locked)
    doc = put(library / "catalog.csv", {"slug": "doe-2015-scan", "file": "books/doe-2015-scan.pdf"})
    job = wait(library_jobs.start_ocr(doc))
    assert job["status"] == "error" and "open in another program" in job["message"]
