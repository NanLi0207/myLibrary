import book_search
import catalog
import pytest
from reportlab.pdfgen import canvas

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
    monkeypatch.setattr(book_search, "ROOT", tmp_path)
    monkeypatch.setattr(book_search, "CATALOG", tmp_path / "catalog.csv")
    monkeypatch.setattr(book_search, "INDEX", tmp_path / ".cache" / "reader" / "books.db")
    for slug in ("doe-2015-optics", "roe-2020-lenses"):
        make_pdf(tmp_path / "books" / f"{slug}.pdf", PAGES)
        catalog.upsert(
            tmp_path / "catalog.csv",
            {"slug": slug, "title": slug.title(), "file": f"books/{slug}.pdf"},
        )
    return tmp_path


def test_search_finds_pages_with_stemming(books):
    assert book_search.update() == 2
    assert book_search.update() == 0  # unchanged PDFs are not read again
    found = book_search.search("vignetting", per_book=5)
    assert found["books"] == 2 and found["pages"] == 4  # "vignetted" counts too
    first = found["results"][0]
    assert first["page"] == 2  # the page that uses the word most ranks first
    assert book_search.MARK_START + "Vignetting" + book_search.MARK_END in first["snippet"]


def test_phrase_per_book_and_current_book_first(books):
    book_search.update()
    found = book_search.search("entrance pupil", current="roe-2020-lenses")
    assert [r["slug"] for r in found["results"]] == ["roe-2020-lenses", "doe-2015-optics"]
    assert all(r["page"] == 1 for r in found["results"])
    one = book_search.search("vignetting", per_book=1)
    assert len(one["results"]) == 2  # one page from each book
    assert book_search.search("pupil entrance")["results"] == []  # words in that order only


def test_changed_and_removed_books(books):
    book_search.update()
    make_pdf(books / "books" / "doe-2015-optics.pdf", ["Astigmatism only."])
    assert book_search.update() == 1
    assert book_search.search("astigmatism")["pages"] == 1
    catalog.remove(books / "catalog.csv", "roe-2020-lenses")
    book_search.update()
    assert book_search.search("coma")["results"] == []


def test_search_before_index_exists(books):
    assert book_search.search("coma") == {"term": "coma", "results": [], "indexing": True}
