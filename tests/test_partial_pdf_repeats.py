"""L21: a PDF holding one or a few chapters of a book that is already in the library, and
carrying that book's ISBN, added through the library page's own add job (library_jobs.start_add:
the real identify, repeat_of, handle_repeat, replace_pdf, archive and catalog). Temporary
libraries and invented PDFs only; the network is replaced at its one door (book_meta._get_json):
Open Library knows the book's ISBN, nothing else is found online."""

import hashlib
import io
import json
import time
from pathlib import Path

import add_book
import book_meta
import book_ocr
import book_toc
import catalog
import library_jobs
import pytest
import reader
from book_meta import Meta
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Highlight
from pypdf.generic import ArrayObject, FloatObject
from reportlab.pdfgen import canvas

ISBN = "9783161484100"  # a valid ISBN-13, invented book
BOOK = {"title": "Practical Optical Design", "authors": [{"name": "Jane Doe"}],
        "publish_date": "2015", "publishers": [{"name": "Invented Press"}]}  # fmt: skip
MY_NOTE = "# Ch 1\n\nMy own words about chapter one.\n"


@pytest.fixture
def library(tmp_path, monkeypatch):
    """An empty library in a temporary folder; Open Library knows BOOK by ISBN (unless a test
    says otherwise); nothing else online; no real search index or page build."""
    for name in ("BOOKS", "PAPERS", "THESES", "EXAMPLES", "NOTES"):
        monkeypatch.setattr(add_book, name, tmp_path / name.lower())
    monkeypatch.setattr(add_book, "CATALOG", tmp_path / "catalog.csv")
    monkeypatch.setattr(add_book, "ARCHIVE", tmp_path / "archive")
    monkeypatch.setattr(add_book, "LIBRARY", tmp_path)
    monkeypatch.setattr(add_book, "PAGE_CACHE", tmp_path / ".cache" / "chapter_pages.json")
    monkeypatch.setattr(reader, "LIBRARY", tmp_path)
    monkeypatch.setattr(library_jobs.library_page, "build", lambda: None)
    monkeypatch.setattr(library_jobs.book_search, "update", lambda: 0)
    monkeypatch.setattr(library_jobs, "_jobs", {})
    known = {"book": BOOK}

    def get_json(url, *a, **k):  # the network's one door
        if "openlibrary.org/api/books" in url and ISBN in url and known["book"]:
            return {f"ISBN:{ISBN}": known["book"]}
        return None

    monkeypatch.setattr(book_meta, "_get_json", get_json)
    nothing = lambda pdf, pages, **kw: {}  # noqa: E731  (blank scans: OCR would find no text)
    monkeypatch.setattr(book_ocr, "ocr_pages", nothing)
    monkeypatch.setattr(book_toc, "ocr_pages", nothing)
    (tmp_path / "books").mkdir()
    return {"root": tmp_path, "known": known}


# --- invented PDFs ----------------------------------------------------------------------------


def scan(pages: int) -> bytes:
    """A scanned book: pages without text."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(400, 600)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def searchable(pages: int, first_lines: list[str], title: str = "") -> bytes:
    """Pages with text; the first page starts with `first_lines`; PDF metadata title `title`."""
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=(400, 600))
    if title:
        c.setTitle(title)
    for n in range(pages):
        lines = first_lines if n == 0 else []
        for i, line in enumerate([*lines, f"Invented text on page {n + 1} about lenses."]):
            c.drawString(30, 560 - 20 * i, line)
        c.showPage()
    c.save()
    return out.getvalue()


def marked(data: bytes) -> bytes:
    """`data` with a highlight, as the reading view saves it."""
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(data)))
    quad = ArrayObject([FloatObject(v) for v in (10, 30, 100, 30, 10, 10, 100, 10)])
    writer.add_annotation(
        page_number=0, annotation=Highlight(rect=(10, 10, 100, 30), quad_points=quad)
    )
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def chapter_pdf(pages: int = 12, chapters: str = "Chapter 3: Aberrations") -> bytes:
    """A publisher's chapter download: the chapter's title, and the book's ISBN on page 1."""
    return searchable(
        pages,
        [chapters, f"In: {BOOK['title']}, Invented Press 2015", "ISBN 978-3-16-148410-0"],
        title=chapters,
    )


# --- running the real add job -----------------------------------------------------------------


def wait(job: dict) -> dict:
    for _ in range(400):
        current = next(j for j in library_jobs.list_jobs() if j["id"] == job["id"])
        if current["status"] != "working":
            return current
        time.sleep(0.05)
    raise AssertionError("job didn't finish")


def add(name: str, data: bytes) -> dict:
    return wait(library_jobs.start_add(library_jobs.save_upload(name, data)))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def the_book(library, data: bytes, monkeypatch, with_work: bool = True) -> dict:
    """The complete book, added through the add job (its details as Open Library has them, as
    for a scan nothing can be read from), plus the user's own work beside it."""
    pages = str(len(PdfReader(io.BytesIO(data)).pages))
    meta = Meta(title=BOOK["title"], author="Jane Doe", year="2015",
                publisher="Invented Press", isbn=ISBN, pages=pages)  # fmt: skip
    with monkeypatch.context() as m:
        m.setattr(library_jobs, "identify", lambda path, online, **kw: meta)
        done = add("full book.pdf", data)
    assert done["status"] == "done", done
    row = catalog.load(library["root"] / "catalog.csv")[done["doc_id"]]
    notes = library["root"] / row["notes"]
    if with_work:
        note = sorted(notes.glob("ch*.md")) or [notes / "ch01-intro.md"]
        note[0].write_text(MY_NOTE, encoding="utf-8")
        readme = notes / "README.md"
        readme.write_text(readme.read_text(encoding="utf-8") + "\nLast read: page 7\n", "utf-8")
    return state(library, done["doc_id"])


def state(library, doc_id: str) -> dict:
    root = library["root"]
    rows = catalog.load(root / "catalog.csv")
    row = rows.get(doc_id, {})
    pdf = root / row["file"] if row else None
    notes = root / row["notes"] if row else None
    return {
        "ids": sorted(rows),
        "row": dict(row),
        "pdf_sha": sha(pdf) if pdf and pdf.exists() else None,
        "pdf_pages": len(PdfReader(pdf).pages) if pdf and pdf.exists() else None,
        "notes": {p.name: p.read_text(encoding="utf-8") for p in sorted(notes.glob("*.md"))}
        if notes and notes.exists()
        else {},
        "archived": sorted(
            p.relative_to(root / "archive").as_posix() for p in (root / "archive").rglob("*.pdf")
        )
        if (root / "archive").exists()
        else [],  # fmt: skip
        "tombstones": json.loads((root / "retired-documents.json").read_text(encoding="utf-8"))
        if (root / "retired-documents.json").exists()
        else {},
    }


# --- the cases ------------------------------------------------------------------------------


def full_copy(pages: int = 40) -> bytes:
    return searchable(pages, [BOOK["title"], "ISBN 978-3-16-148410-0"], title=BOOK["title"])


def chapter_cache(library, doc_id: str):
    cache = library["root"] / ".cache" / "chapter_pages.json"
    return json.loads(cache.read_text(encoding="utf-8")).get(doc_id) if cache.exists() else None


def kept_as_it_was(library, before: dict) -> None:
    """The book's entry, PDF, notes, chapter mapping, the archive and the tombstones: as before."""
    after = state(library, before["row"]["id"])
    assert after["row"] == before["row"]  # id, file, pages, chapters, isbn, title, slug...
    assert after["pdf_sha"] == before["pdf_sha"]
    assert after["notes"] == before["notes"]  # the user's words, ticks, last-read page
    assert after["archived"] == before["archived"]  # nothing moved to archive/
    assert after["tombstones"] == before["tombstones"]  # no identity retired
    assert chapter_cache(library, before["row"]["id"]) == before["chapter_cache"]


def book_then(library, monkeypatch, book: bytes, incoming: bytes, unknown: bool = False):
    """The complete book (with the user's work), then `incoming` added: (before, job)."""
    before = the_book(library, book, monkeypatch)
    before["chapter_cache"] = chapter_cache(library, before["row"]["id"])
    if unknown:
        library["known"]["book"] = None
    return before, add("incoming.pdf", incoming)


def kept_apart(library, before: dict, job: dict) -> dict:
    """`job` added its PDF as a document of its own, beside the book: its row."""
    assert job["status"] == "done", job["message"]
    rows = catalog.load(library["root"] / "catalog.csv")
    assert set(rows) == {before["row"]["id"], job["doc_id"]}  # two documents, two ids
    new = rows[job["doc_id"]]
    assert new["notes"] != before["row"]["notes"]  # its own notes folder
    assert (library["root"] / new["file"]).is_file()
    return new


SHARING = [
    # (the book in the library, the PDF added, Open Library doesn't know the ISBN)
    pytest.param(lambda: scan(40), chapter_pdf, False, id="1-scan+chapter"),
    pytest.param(lambda: scan(40), lambda: chapter_pdf(25, "Chapters 3-5"), False, id="2-several"),
    pytest.param(lambda: searchable(40, [BOOK["title"]]), chapter_pdf, False, id="1b-searchable"),
    pytest.param(lambda: marked(scan(40)), chapter_pdf, False, id="4-marked-book"),
    pytest.param(lambda: scan(40), chapter_pdf, True, id="5-title-differs"),
    pytest.param(lambda: scan(40), lambda: full_copy(36), False, id="nearly-complete"),
    pytest.param(lambda: scan(30), lambda: full_copy(30), False, id="different-30-pages"),
    pytest.param(lambda: scan(40), full_copy, False, id="3-better-complete-copy"),
]


@pytest.mark.parametrize("book, incoming, unknown", SHARING)
def test_pdfs_that_only_share_an_isbn_are_kept_apart(library, monkeypatch, book, incoming, unknown):
    """L21: a shared ISBN proves nothing about what a PDF holds. Whatever the page counts, text
    layers or titles, the book stays exactly as it was and the new PDF becomes a document of its
    own, with a message saying it shares the ISBN. Includes a better complete copy (3): kept
    beside the scan, the user decides (no automatic replacement without proof)."""
    before, job = book_then(library, monkeypatch, book(), incoming(), unknown)
    kept_as_it_was(library, before)
    new = kept_apart(library, before, job)
    assert "shares its ISBN" in job["message"] and before["row"]["slug"] in job["message"]
    assert new["isbn"] == ISBN  # (read from its page 1 when Open Library is no help)


def test_two_different_chapters_of_the_same_length_are_both_kept(library):
    """Two chapter PDFs of one book, same ISBN, the same number of pages: different content."""
    first = add("chapter3.pdf", chapter_pdf(12, "Chapter 3: Aberrations"))
    second = add("chapter5.pdf", chapter_pdf(12, "Chapter 5: Stops and pupils"))
    assert first["status"] == second["status"] == "done", second["message"]
    rows = catalog.load(library["root"] / "catalog.csv")
    assert set(rows) == {first["doc_id"], second["doc_id"]}
    assert "shares its ISBN" in second["message"]


def test_a_chapter_first_then_the_complete_book(library):
    """Case 8: the book never takes the chapter's place."""
    chapter = add("chapter.pdf", chapter_pdf())
    before = state(library, chapter["doc_id"])
    book = add("full book.pdf", full_copy())
    after = state(library, chapter["doc_id"])
    assert book["status"] == "done" and book["doc_id"] != chapter["doc_id"]
    assert after["row"] == before["row"] and after["pdf_sha"] == before["pdf_sha"]
    assert after["archived"] == before["archived"] == []


def test_a_missing_pdf_is_never_reattached_by_its_isbn(library, monkeypatch):
    """The book's PDF is missing (another computer, a restore) and its page count unknown: a PDF
    with the same ISBN becomes its own document; the entry keeps its id, notes and place, still
    waiting for its own PDF."""
    before = the_book(library, scan(40), monkeypatch)
    root = library["root"]
    (root / before["row"]["file"]).unlink()
    catalog.update(root / "catalog.csv", before["row"]["id"], {"pages": ""})
    before = state(library, before["row"]["id"])
    before["chapter_cache"] = chapter_cache(library, before["row"]["id"])
    job = add("incoming.pdf", full_copy())
    kept_as_it_was(library, before)  # including: still no PDF at its place
    assert not (root / before["row"]["file"]).exists()
    kept_apart(library, before, job)


def test_identical_copies_are_still_repeats(library, monkeypatch):
    book = scan(40)
    before = the_book(library, book, monkeypatch)
    job = add("incoming.pdf", book)
    assert job["status"] == "duplicate" and "identical file" in job["message"]
    after = state(library, before["row"]["id"])
    assert after["ids"] == before["ids"] and after["pdf_sha"] == before["pdf_sha"]
    assert after["archived"] == ["books/incoming.pdf"]  # the copy, kept in archive/


def _refresh(library) -> None:
    library_jobs.refresh()
    deadline = time.monotonic() + 30
    while any(j["status"] == "working" for j in library_jobs.list_jobs()):
        assert time.monotonic() < deadline, "Refresh's jobs didn't finish"
        time.sleep(0.05)


def test_refresh_never_merges_pdfs_that_only_share_an_isbn(library, monkeypatch):
    """Case 7: the book added without its ISBN, a chapter PDF with it its own document; the
    book's ISBN filled later (as fill_details would). Refresh, twice: both stay, untouched."""
    root = library["root"]
    meta = Meta(title=BOOK["title"], author="Jane Doe", year="2015", pages="40")
    with monkeypatch.context() as m:
        m.setattr(library_jobs, "identify", lambda path, online, **kw: meta)
        book = add("full book.pdf", searchable(40, [BOOK["title"]]))
    chapter = add("chapter.pdf", chapter_pdf())
    assert chapter["status"] == "done"
    catalog.update(root / "catalog.csv", book["doc_id"], {"isbn": ISBN})
    before = {d: state(library, d) for d in (book["doc_id"], chapter["doc_id"])}
    for _ in range(2):
        _refresh(library)
        for doc_id, was in before.items():
            now = state(library, doc_id)
            assert now["row"]["id"] == doc_id and now["pdf_sha"] == was["pdf_sha"]
            assert now["notes"] == was["notes"]
            assert now["archived"] == was["archived"] and now["tombstones"] == {}
    assert not [j for j in library_jobs.list_jobs() if j["kind"] == "repeat"]


def test_refresh_keeps_two_partial_pdfs_of_one_book(library):
    first = add("chapter3.pdf", chapter_pdf(12, "Chapter 3: Aberrations"))
    second = add("chapters5-6.pdf", chapter_pdf(20, "Chapters 5-6"))
    for _ in range(2):
        _refresh(library)
        rows = catalog.load(library["root"] / "catalog.csv")
        assert {first["doc_id"], second["doc_id"]} <= set(rows)
    assert state(library, first["doc_id"])["tombstones"] == {}


def test_the_command_line_keeps_them_apart_too(library, monkeypatch, capsys):
    before = the_book(library, scan(40), monkeypatch)
    upload = library["root"] / "books" / "chapter.pdf"
    upload.write_bytes(chapter_pdf())
    meta = book_meta.identify(upload)  # the real identification (the network stubbed)
    assert meta.isbn == ISBN and meta.title == BOOK["title"]  # the book's title, from the ISBN
    add_book.add_book(upload, add_book.Book(meta.title, meta.author, meta.year), False, meta)
    assert "shares its ISBN" in capsys.readouterr().out
    rows = catalog.load(library["root"] / "catalog.csv")
    assert len(rows) == 2 and rows[before["row"]["id"]] == before["row"]


# --- what already held and still holds ---------------------------------------------------------


def test_the_users_work_survives(library, monkeypatch):
    before = the_book(library, scan(40), monkeypatch)
    readme = library["root"] / before["row"]["notes"] / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8").replace("- [ ] Chapter 1", "- [x] Chapter 1"),
        encoding="utf-8",
    )
    add("incoming.pdf", chapter_pdf())
    text = readme.read_text(encoding="utf-8")
    assert "- [x] Chapter 1" in text and "Last read: page 7" in text
    assert MY_NOTE in state(library, before["row"]["id"])["notes"].values()


# --- B29: the same question for a DOI ----------------------------------------------------------
# A DOI names a work (an article), not a PDF: the article, its supplementary material, an
# accepted manuscript, an erratum can all print it. Only an identical file proves a repeat.

DOI = "10.1364/oe.27.1"
ARTICLE = {"type": "journal-article", "title": ["Freeform Surfaces in Optical Design"],
           "author": [{"given": "Jane", "family": "Doe"}], "issued": {"date-parts": [[2019]]},
           "container-title": ["Optics Express"], "volume": "27", "page": "1-8"}  # fmt: skip


@pytest.fixture
def crossref(monkeypatch):
    """Crossref knows the article by its DOI; nothing else is found online."""

    def get_json(url, *a, **k):
        if "api.crossref.org/works/" in url and DOI.split("/")[1] in url.lower():
            return {"message": ARTICLE}
        return None

    monkeypatch.setattr(book_meta, "_get_json", get_json)


def article_pdf(pages: int = 8) -> bytes:
    return searchable(pages, [ARTICLE["title"][0], "Jane Doe", f"doi:{DOI}"])


def supplement_pdf(pages: int = 20) -> bytes:
    return searchable(pages, ["Supplementary material", f"for {ARTICLE['title'][0]}", f"doi:{DOI}"])


def the_article(library, monkeypatch, data: bytes) -> dict:
    """The article, added through the add job, with the user's own notes and place in it."""
    found = Meta(title=ARTICLE["title"][0], author="Jane Doe", year="2019", doi=DOI,
                 kind="paper", journal="Optics Express")  # fmt: skip
    with monkeypatch.context() as m:
        m.setattr(library_jobs, "identify", lambda path, online, **kw: found)
        done = add("article.pdf", data)
    assert done["status"] == "done", done
    notes = library["root"] / catalog.load(library["root"] / "catalog.csv")[done["doc_id"]]["notes"]
    (notes / "notes.md").write_text(MY_NOTE, encoding="utf-8")
    readme = notes / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\nLast read: page 3\n", "utf-8")
    before = state(library, done["doc_id"])
    before["chapter_cache"] = chapter_cache(library, done["doc_id"])
    return before


SHARING_A_DOI = [
    pytest.param(article_pdf, supplement_pdf, id="1-supplement"),
    pytest.param(
        article_pdf,
        lambda: searchable(8, ["Accepted manuscript", f"doi:{DOI}"]),
        id="3-similar-pages",
    ),  # fmt: skip
    pytest.param(lambda: marked(article_pdf()), supplement_pdf, id="4-annotated-article"),
]


@pytest.mark.parametrize("article, incoming", SHARING_A_DOI)
def test_pdfs_that_only_share_a_doi_are_kept_apart(
    library, monkeypatch, crossref, article, incoming
):
    """B29: a PDF printing the article's DOI (identified through Crossref as the article, so the
    title check passes) never replaces, archives or merges with it: it becomes a document of its
    own, with a message saying it shares the DOI; the article stays exactly as it was."""
    before = the_article(library, monkeypatch, article())
    job = add("incoming.pdf", incoming())
    kept_as_it_was(library, before)
    new = kept_apart(library, before, job)
    assert f"shares its DOI with {before['row']['slug']}" in job["message"]
    assert "duplicate" not in job["status"] and new["doi"] == DOI


def test_the_supplement_first_then_the_article(library, monkeypatch, crossref):
    """2: the supplementary material came first; the article never takes its place."""
    first = add("supplement.pdf", supplement_pdf())
    assert first["status"] == "done"
    before = state(library, first["doc_id"])
    job = add("article.pdf", article_pdf())
    after = state(library, first["doc_id"])
    assert job["status"] == "done" and job["doc_id"] != first["doc_id"]
    assert "shares its DOI" in job["message"]
    assert after["row"] == before["row"] and after["pdf_sha"] == before["pdf_sha"]
    assert after["archived"] == before["archived"] == []


def test_a_missing_pdf_is_never_reattached_by_its_doi(library, monkeypatch, crossref):
    """5: the article's PDF is missing (another computer, a restore): a PDF with its DOI becomes
    its own document; the entry keeps its id, notes and place, still waiting for its own PDF."""
    before = the_article(library, monkeypatch, article_pdf())
    root = library["root"]
    (root / before["row"]["file"]).unlink()
    before = state(library, before["row"]["id"]) | {"chapter_cache": before["chapter_cache"]}
    job = add("incoming.pdf", article_pdf(9))
    kept_as_it_was(library, before)
    assert not (root / before["row"]["file"]).exists()
    kept_apart(library, before, job)


def test_a_missing_pdf_is_not_reattached_even_by_the_identical_file(library, monkeypatch, crossref):
    """With the PDF missing there is nothing to compare a file with, and no fingerprint of it is
    kept (the hashes in .cache/ are this computer's, by path and date): even the very same bytes
    become a document of their own. Automatic re-attachment is not possible; the entry waits."""
    data = article_pdf()
    before = the_article(library, monkeypatch, data)
    root = library["root"]
    (root / before["row"]["file"]).unlink()
    before = state(library, before["row"]["id"]) | {"chapter_cache": before["chapter_cache"]}
    job = add("incoming.pdf", data)  # byte for byte the PDF the entry had
    kept_as_it_was(library, before)
    assert not (root / before["row"]["file"]).exists()
    kept_apart(library, before, job)


def test_an_identical_file_with_the_doi_is_still_a_repeat(library, monkeypatch, crossref):
    """6: the same bytes again: a repeat, kept in archive/, the article untouched."""
    data = article_pdf()
    before = the_article(library, monkeypatch, data)
    job = add("incoming.pdf", data)
    assert job["status"] == "duplicate" and "identical file" in job["message"]
    after = state(library, before["row"]["id"])
    assert after["ids"] == before["ids"] and after["pdf_sha"] == before["pdf_sha"]
    assert after["archived"] == ["books/incoming.pdf"]  # (uploads arrive in books/)


def test_refresh_never_merges_documents_that_only_share_a_doi(library, monkeypatch, crossref):
    """7: two registered documents with one DOI, Refresh twice: both stay, with their PDFs,
    notes and ids; no repeat is reported; nothing is retired."""
    before = the_article(library, monkeypatch, article_pdf())
    other = add("supplement.pdf", supplement_pdf())
    states = {d: state(library, d) for d in (before["row"]["id"], other["doc_id"])}
    for _ in range(2):
        _refresh(library)
        for doc_id, was in states.items():
            now = state(library, doc_id)
            assert now["row"]["id"] == doc_id and now["pdf_sha"] == was["pdf_sha"]
            assert now["notes"] == was["notes"] and now["archived"] == was["archived"]
            assert now["tombstones"] == {}
    assert not [j for j in library_jobs.list_jobs() if j["kind"] == "repeat"]


def test_doi_details_and_citations_still_work(library, monkeypatch, crossref):
    """9: the DOI still identifies the work: the PDF added second gets the article's details
    from Crossref through its DOI, and both documents cite with it."""
    import citation

    before = the_article(library, monkeypatch, article_pdf())
    job = add("supplement.pdf", supplement_pdf())
    rows = catalog.load(library["root"] / "catalog.csv")
    new = rows[job["doc_id"]]
    assert new["type"] == "paper" and new["doi"] == DOI and new["journal"] == "Optics Express"
    for row in (rows[before["row"]["id"]], new):
        assert DOI in citation.bibtex(row) and DOI in citation.ris(row)
