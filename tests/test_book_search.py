import book_search
import catalog
import pytest
from reportlab.pdfgen import canvas
from testlib import entry, id_of, put  # noqa: F401

PAGES = [
    "Chapter 1. First-order optics and the entrance pupil.",
    "Vignetting: the aperture stop limits the beam. Vignetting reduces edge illumination.",
    "A vignetted beam at the edge of the field.",
    "Spherical aberration and coma.",
]


def make_pdf(path, pages):
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path))
    for text in pages:
        c.drawString(72, 720, text)
        c.showPage()
    c.save()


@pytest.fixture
def books(tmp_path, monkeypatch):
    monkeypatch.setattr(book_search, "LIBRARY", tmp_path)
    monkeypatch.setattr(book_search, "CATALOG", tmp_path / "catalog.csv")
    monkeypatch.setattr(book_search, "INDEX", tmp_path / ".cache" / "books.db")
    for slug in ("doe-2015-optics", "roe-2020-lenses"):
        make_pdf(tmp_path / "books" / f"{slug}.pdf", PAGES)
        put(
            tmp_path / "catalog.csv",
            {"slug": slug, "title": slug.title(), "file": f"books/{slug}.pdf"},
        )
    return tmp_path


def test_search_finds_pages_with_stemming(books):
    first = book_search.update()
    assert len(first["indexed"]) == 2 and first["complete"] and first["failed"] == []
    again = book_search.update()  # unchanged PDFs are not read again
    assert again["indexed"] == [] and again["unchanged"] == 2 and again["complete"]
    found = book_search.search("vignetting", per_book=5)
    assert found["books"] == 2 and found["pages"] == 4  # "vignetted" counts too
    first = found["results"][0]
    assert first["page"] == 2  # the page that uses the word most ranks first
    assert book_search.MARK_START + "Vignetting" + book_search.MARK_END in first["snippet"]


def test_phrase_per_book_and_current_book_first(books):
    book_search.update()
    path = book_search.CATALOG
    roe, doe = id_of(path, "roe-2020-lenses"), id_of(path, "doe-2015-optics")
    found = book_search.search("entrance pupil", current=roe)
    assert [r["id"] for r in found["results"]] == [roe, doe]
    assert [r["file"] for r in found["results"]] == ["books/roe-2020-lenses.pdf",
                                                      "books/doe-2015-optics.pdf"]  # fmt: skip
    assert all(r["page"] == 1 for r in found["results"])
    one = book_search.search("vignetting", per_book=1)
    assert len(one["results"]) == 2  # one page from each book
    assert book_search.search("pupil entrance")["results"] == []  # words in that order only


def test_changed_and_removed_books(books):
    book_search.update()
    make_pdf(books / "books" / "doe-2015-optics.pdf", ["Astigmatism only."])
    assert len(book_search.update()["indexed"]) == 1
    assert book_search.search("astigmatism")["pages"] == 1
    catalog.remove(books / "catalog.csv", id_of(books / "catalog.csv", "roe-2020-lenses"))
    book_search.update()
    assert book_search.search("coma")["results"] == []


def test_search_before_index_exists(books):
    assert book_search.search("coma") == {"term": "coma", "results": [], "indexing": True}


# --- failures: one document never stops the others, and nothing indexed is lost ---------------


def failing_for(file_name):
    """An extractor that fails for one PDF (by its file's name) and reads the others."""

    def extract(pdf):
        if pdf.stem == file_name:
            raise RuntimeError("damaged PDF")
        return book_search.page_texts(pdf)

    return extract


def test_one_failing_pdf_never_stops_the_others(books):
    for n in range(3):  # five documents in all
        make_pdf(books / "books" / f"poe-2021-extra-{n}.pdf", [f"Extra book {n} on coma."])
        put(books / "catalog.csv", {"slug": f"poe-2021-extra-{n}", "title": f"Extra {n}",
                                    "file": f"books/poe-2021-extra-{n}.pdf"})  # fmt: skip
    bad = id_of(books / "catalog.csv", "doe-2015-optics")
    report = book_search.update(extract=failing_for("doe-2015-optics"))
    assert len(report["indexed"]) == 4 and not report["complete"]
    [failed] = report["failed"]
    assert (failed["id"], failed["state"]) == (bad, "failed")
    assert "RuntimeError: damaged PDF" in failed["error"]
    st = book_search.status()[bad]
    assert (st["state"], st["attempts"], st["last_success"]) == ("failed", 1, None)
    assert "INCOMPLETE" in book_search.describe(report) and "doe-2015-optics" in (
        book_search.describe(report))  # fmt: skip
    found = book_search.search("coma", per_book=5)
    assert bad not in {r["id"] for r in found["results"]}
    assert found["not_indexed"] == [{"id": bad, "title": "Doe-2015-Optics", "state": "failed"}]


def test_a_failed_document_is_retried_and_its_attempts_counted(books):
    bad = id_of(books / "catalog.csv", "doe-2015-optics")
    book_search.update(extract=failing_for("doe-2015-optics"))
    second = book_search.update(extract=failing_for("doe-2015-optics"))  # tried again
    assert [f["id"] for f in second["failed"]] == [bad]
    assert book_search.status()[bad]["attempts"] == 2
    third = book_search.update()  # it works this time
    assert third["indexed"] == [bad] and third["complete"]
    st = book_search.status()[bad]
    assert (st["state"], st["attempts"], st["error"]) == ("indexed", 0, None)
    assert st["last_success"]
    assert book_search.search("coma")["not_indexed"] == []


def test_a_changed_pdf_that_fails_keeps_its_older_pages_marked_stale(books):
    book_search.update()
    doc = id_of(books / "catalog.csv", "doe-2015-optics")
    make_pdf(books / "books" / "doe-2015-optics.pdf", ["A new edition about astigmatism."])
    report = book_search.update(extract=failing_for("doe-2015-optics"))
    assert report["failed"][0]["state"] == "stale"
    # The older version's pages are still found, and marked as such
    found = book_search.search("vignetting", per_book=5)
    stale = [r for r in found["results"] if r["id"] == doc]
    assert stale and all(r["stale"] for r in stale)
    assert all(not r["stale"] for r in found["results"] if r["id"] != doc)
    assert found["not_indexed"] == [{"id": doc, "title": "Doe-2015-Optics", "state": "stale"}]
    assert book_search.search("astigmatism")["results"] == []  # the new text isn't in yet


def test_an_interrupted_write_keeps_the_previous_pages(books):
    book_search.update()
    doc = id_of(books / "catalog.csv", "doe-2015-optics")
    before = book_search.search("vignetting", per_book=5)["pages"]
    make_pdf(books / "books" / "doe-2015-optics.pdf", ["Changed."])

    def breaks_halfway(pdf):
        if pdf.stem != "doe-2015-optics":
            return book_search.page_texts(pdf)

        def pages():  # the old pages are already deleted when this fails
            yield "First page of the new version."
            raise OSError("disk full")

        return pages()

    report = book_search.update(extract=breaks_halfway)
    assert [f["id"] for f in report["failed"]] == [doc] and "disk full" in report["failed"][0][
        "error"
    ]
    assert book_search.search("vignetting", per_book=5)["pages"] == before  # rolled back
    assert book_search.search("First page")["results"] == []
    assert book_search.status()[doc]["state"] == "stale"


def test_a_missing_pdf_makes_the_run_incomplete_and_removed_documents_leave(books):
    (books / "books" / "roe-2020-lenses.pdf").unlink()
    report = book_search.update()
    roe = id_of(books / "catalog.csv", "roe-2020-lenses")
    assert report["missing"] == [roe] and not report["complete"]
    book_search.update(extract=failing_for("doe-2015-optics"))
    doe = id_of(books / "catalog.csv", "doe-2015-optics")
    catalog.remove(books / "catalog.csv", doe)
    catalog.remove(books / "catalog.csv", roe)
    book_search.update()
    assert book_search.status() == {}  # status follows the catalog, by id


def test_the_index_and_status_are_keyed_by_document_id(books):
    book_search.update()
    ids = set(catalog.load(books / "catalog.csv"))
    assert set(book_search.status()) == ids
    assert {r["id"] for r in book_search.search("vignetting", per_book=5)["results"]} == ids
