import add_book
import book_meta
import citation
import library_page
import library_server
import pytest
from reportlab.pdfgen import canvas
from testlib import entry, id_of, put  # noqa: F401

# What Crossref answers for an (invented) journal article
CROSSREF = {
    "message": {
        "type": "journal-article",
        "title": ["Freeform Optics for Compact Imaging"],
        "author": [
            {"given": "Jane", "family": "Doe"},
            {"given": "Wei", "family": "Zhang"},
            {"given": "Ann", "family": "Lee"},
            {"given": "Bo", "family": "Chen"},
        ],
        "issued": {"date-parts": [[2019, 5]]},
        "container-title": ["Optics Express"],
        "volume": "27",
        "issue": "8",
        "page": "1234-1245",
        "publisher": "Optica Publishing Group",
    }
}


@pytest.fixture
def library(tmp_path, monkeypatch):
    for module in (library_server, library_page):
        monkeypatch.setattr(module, "LIBRARY", tmp_path)
        monkeypatch.setattr(module, "CATALOG", tmp_path / "catalog.csv")
    for name in ("BOOKS", "PAPERS", "THESES", "EXAMPLES", "NOTES"):
        monkeypatch.setattr(add_book, name, tmp_path / name.lower())
    monkeypatch.setattr(add_book, "LIBRARY", tmp_path)
    monkeypatch.setattr(add_book, "CATALOG", tmp_path / "catalog.csv")
    monkeypatch.setattr(library_server, "CACHE", tmp_path / ".cache" / "chapter_pages.json")
    return tmp_path


def paper_pdf(path, first_page_doi="10.1364/OE.27.001234"):
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path))
    c.drawString(72, 750, "Freeform optics for compact imaging")
    c.drawString(72, 730, f"https://doi.org/{first_page_doi}")
    for line in range(20):
        c.drawString(72, 700 - 20 * line, "Body text of an invented paper about freeform lenses.")
    c.showPage()
    for _ in range(3):  # references: other papers' DOIs, which must not be taken
        c.drawString(72, 750, "References: [1] doi:10.1000/somebody.else.2001")
        c.showPage()
    c.save()


def test_doi_on_the_first_page_identifies_a_paper(tmp_path, monkeypatch):
    asked = []
    monkeypatch.setattr(book_meta, "_get_json", lambda url: asked.append(url) or CROSSREF)
    pdf = tmp_path / "download.pdf"
    paper_pdf(pdf)
    meta = book_meta.identify(pdf)
    # Crossref for the details; then OpenAlex for keywords, since this PDF lists none
    assert asked == [
        "https://api.crossref.org/works/10.1364/oe.27.001234",
        "https://api.openalex.org/works/doi:10.1364/oe.27.001234",
    ]
    assert meta.kind == "paper" and meta.doi == "10.1364/oe.27.001234"
    assert meta.author == "Jane Doe; Wei Zhang; Ann Lee; Bo Chen" and meta.year == "2019"
    assert (meta.journal, meta.volume, meta.issue, meta.page_range) == (
        "Optics Express",
        "27",
        "8",
        "1234-1245",
    )
    book = add_book.Book(meta.title, meta.author, meta.year)
    assert book.slug == "doe-2019-freeform-optics-compact-imaging"


def test_a_book_doi_is_still_a_book(tmp_path, monkeypatch):
    answer = {"message": {**CROSSREF["message"], "type": "book"}}
    monkeypatch.setattr(book_meta, "_get_json", lambda url: answer)
    assert book_meta.crossref("10.1007/978-3-030-00000-0").kind == "book"


def test_paper_notes_progress_and_continue(library, monkeypatch):
    meta = book_meta.Meta(
        title="Freeform Optics for Compact Imaging",
        author="Jane Doe; Wei Zhang",
        year="2019",
        journal="Optics Express",
        volume="27",
        issue="8",
        page_range="1234-1245",
        doi="10.1364/oe.27.001234",
        kind="paper",
    )
    pdf = library / "books" / "doe-2019-freeform-optics-compact-imaging.pdf"
    paper_pdf(pdf)
    doc = add_book.setup_book(pdf, add_book.Book(meta.title, meta.author, meta.year), meta)

    slug = pdf.stem
    notes = library / "notes" / slug
    readme = (notes / "README.md").read_text(encoding="utf-8")
    assert "| Journal | Optics Express, 27(8), 1234-1245 |" in readme
    assert "- [ ] [Read the paper](notes.md)" in readme
    assert "## Summary (in my own words)" in (notes / "notes.md").read_text(encoding="utf-8")
    assert not list(notes.glob("ch*.md"))  # no chapter templates for a paper
    row = entry(library / "catalog.csv", slug)
    assert (row["type"], row["doi"], row["openlibrary"]) == ("paper", "10.1364/oe.27.001234", "")

    # One item, "Read the paper", that ticks like a chapter
    [item] = library_page.chapters(doc)
    assert (item["number"], item["note"], item["done"]) == (1, "notes.md", False)
    assert library_server.tick(doc, 1, True)[0]["done"] is True

    # Read / Continue: page 1 (or the page you were on) and notes.md
    opened, files = [], []
    monkeypatch.setattr(library_server.webbrowser, "open", opened.append)
    monkeypatch.setattr(library_server, "open_in_editor", lambda *f: files.extend(f) or True)
    library_server.open_chapter(doc, None, "http://x")
    assert opened[-1].endswith("#page=1") and files[0].name == "notes.md"
    library_server.save_position(doc, 3)
    assert "Last read: page 3, " in (notes / "README.md").read_text(encoding="utf-8")
    library_server.open_chapter(doc, None, "http://x", resume=True)
    assert opened[-1].endswith("#page=3") and files[-1].name == "notes.md"


def test_bibtex():
    paper = {
        "type": "paper",
        "title": "Freeform Optics for Compact Imaging",
        "authors": "Jane Doe; Wei Zhang",
        "year": "2019",
        "journal": "Optics Express",
        "volume": "27",
        "issue": "8",
        "page_range": "1234-1245",
        "doi": "10.1364/oe.27.001234",
    }
    assert citation.bibtex(paper) == (
        "@article{doe2019freeform,\n"
        "  author = {Jane Doe and Wei Zhang},\n"
        "  title = {{Freeform Optics for Compact Imaging}},\n"
        "  journal = {Optics Express},\n"
        "  year = {2019},\n"
        "  volume = {27},\n"
        "  number = {8},\n"
        "  pages = {1234--1245},\n"
        "  doi = {10.1364/oe.27.001234},\n"
        "}"
    )
    book = {
        "title": "Field Guide to Lens Design",
        "authors": "Julie Bentley, Craig Olson",
        "year": "2012",
        "publisher": "SPIE Press",
        "isbn": "9780819491640",
    }
    text = citation.bibtex(book)
    assert text.startswith("@book{bentley2012field,")
    assert "author = {Julie Bentley and Craig Olson}" in text and "publisher = {SPIE Press}" in text
    assert citation.authors("Shannon, Robert") == ["Shannon, Robert"]  # one person


def test_a_recognised_paper_moves_to_papers(library, monkeypatch):
    monkeypatch.setattr(book_meta, "_get_json", lambda url: CROSSREF)
    download = library / "books" / "some download.pdf"
    paper_pdf(download)
    meta = book_meta.identify(download)
    book = add_book.Book(meta.title, meta.author, meta.year)
    add_book.add_book(download, book, dry_run=False, meta=meta)

    target = library / "papers" / "doe-2019-freeform-optics-compact-imaging.pdf"
    assert target.exists() and not download.exists()
    row = entry(library / "catalog.csv", target.stem)
    assert row["file"] == "papers/doe-2019-freeform-optics-compact-imaging.pdf"
    readme = (library / "notes" / target.stem / "README.md").read_text(encoding="utf-8")
    assert "| File | `papers/doe-2019-freeform-optics-compact-imaging.pdf` |" in readme


def test_a_pdf_in_papers_is_a_paper_even_if_nobody_knows_it(tmp_path, monkeypatch):
    monkeypatch.setattr(book_meta, "_get_json", lambda url: None)  # offline / unknown
    pdf = tmp_path / "papers" / "my-notes.pdf"
    c = canvas.Canvas(str(pdf.parent.mkdir() or pdf))
    c.drawString(72, 750, "A working paper nobody has published")
    c.showPage()
    c.save()
    assert book_meta.identify(pdf, paper=True).kind == "paper"
    assert book_meta.identify(pdf).kind == "book"  # in books/: a book, as before


ARXIV_FEED = """<feed xmlns="http://www.w3.org/2005/Atom"
    xmlns:arxiv="http://arxiv.org/schemas/atom"><entry>
  <title>Learning Lens Design
    With Gradients</title>
  <published>2021-01-05T00:00:00Z</published>
  <author><name>Jane Doe</name></author><author><name>Wei Zhang</name></author>
  {doi}
</entry></feed>"""


def test_arxiv_preprints_and_their_journal_versions(monkeypatch):
    import xml.etree.ElementTree as ElementTree

    feed = ElementTree.fromstring(ARXIV_FEED.format(doi=""))
    monkeypatch.setattr(book_meta, "_get_xml", lambda url: feed)
    assert book_meta.find_arxiv("x", "Preprint arXiv:2101.01234v2 [physics.optics]") == "2101.01234"
    assert book_meta.find_arxiv("2101.01234v2", "") == "2101.01234"
    pre = book_meta.arxiv("2101.01234")
    assert (pre.kind, pre.title, pre.author, pre.year) == (
        "paper",
        "Learning Lens Design With Gradients",
        "Jane Doe; Wei Zhang",
        "2021",
    )
    assert pre.journal == "arXiv preprint" and pre.doi == "10.48550/arxiv.2101.01234"

    # Published since: the journal version from Crossref wins
    published = (
        '<arxiv:doi xmlns:arxiv="http://arxiv.org/schemas/atom">10.1364/OE.27.001234</arxiv:doi>'
    )
    feed = ElementTree.fromstring(ARXIV_FEED.format(doi=published))
    monkeypatch.setattr(book_meta, "_get_xml", lambda url: feed)
    monkeypatch.setattr(book_meta, "_get_json", lambda url: CROSSREF)
    assert book_meta.arxiv("2101.01234").journal == "Optics Express"


def test_title_search_only_accepts_a_real_match(monkeypatch):
    def answer(url):
        if "query.bibliographic" in url:
            wrong = {"DOI": "10.1/wrong", "title": ["Something Else Entirely About Optics"]}
            right = {"DOI": "10.1364/OE.27.001234", "title": [CROSSREF["message"]["title"][0]]}
            items = [wrong, right]
            return {"message": {"items": items}}
        return CROSSREF

    monkeypatch.setattr(book_meta, "_get_json", answer)
    page = "Freeform optics for compact imaging. Jane Doe, Wei Zhang. Abstract: we show..."
    assert book_meta.crossref_search(page).doi == "10.1364/oe.27.001234"
    assert book_meta.crossref_search("Notes on mirrors and nothing more than that").title == ""


def test_server_serves_papers(library):
    import json
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer

    pdf = library / "papers" / "doe-2019-x.pdf"
    paper_pdf(pdf)
    put(library / "catalog.csv", {"slug": "doe-2019-x", "file": "papers/doe-2019-x.pdf"})
    server = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/papers/doe-2019-x.pdf"
        assert urllib.request.urlopen(url, timeout=5).read().startswith(b"%PDF")
        assert json.dumps(library_page.books("http://x/viewer?file=")).count(
            "papers/doe-2019-x.pdf"
        )
    finally:
        server.shutdown()


def test_clean_titles_and_originals_over_reprints(monkeypatch):
    assert book_meta.clean_title("XV.\n   <i>On the theory of optical images</i>") == (
        "On the theory of optical images"
    )
    # The same title twice: the 1903 reprint first, the 1896 original second
    title = "XV. <i>On the theory of optical images, with special reference to the microscope</i>"
    items = [
        {"DOI": "10.1/reprint", "title": [title], "issued": {"date-parts": [[1903]]}},
        {"DOI": "10.1/original", "title": [title], "issued": {"date-parts": [[1896]]}},
    ]
    asked = []

    def answer(url):
        asked.append(url)
        if "query.bibliographic" in url:
            return {"message": {"items": items}}
        return {"message": {"type": "journal-article", "title": [title],
                            "issued": {"date-parts": [[1896]]}}}  # fmt: skip

    monkeypatch.setattr(book_meta, "_get_json", answer)
    page = (
        "XV. On the theory of optical images, with special reference to the microscope.\n"
        "By Lord Rayleigh. Philosophical Magazine, 1896"
    )
    found = book_meta.crossref_search(page)
    assert asked[-1].endswith("/works/10.1/original")  # the year printed on the page wins
    assert found.title.startswith("On the theory of optical images")  # no tags, no "XV."


def test_openalex_for_papers_crossref_does_not_know(monkeypatch):
    work = {
        "title": "On the Brightness of Old Lenses",
        "publication_year": 1871,
        "authorships": [{"author": {"display_name": "A. Lensmaker"}}],
        "primary_location": {"source": {"display_name": "Proceedings of an Old Society"}},
        "biblio": {"volume": "3", "issue": None, "first_page": "11", "last_page": "19"},
        "doi": None,
        "id": "https://openalex.org/W123",
    }
    queries = []

    def answer(url):
        queries.append(url)
        if "openalex" in url and "brightness" in url.lower():  # only the title line finds it
            return {"results": [work]}
        return {"results": [], "message": {"items": []}}

    monkeypatch.setattr(book_meta, "_get_json", answer)
    page = "ON THE BRIGHTNESS OF OLD LENSES.\nBy A. Lensmaker, Esq.\nRead before the Society, 1871"
    assert book_meta.crossref_search(page).title == ""
    meta = book_meta.openalex_search(page)
    assert (meta.kind, meta.title, meta.author, meta.year) == (
        "paper",
        "On the Brightness of Old Lenses",
        "A. Lensmaker",
        "1871",
    )
    assert (meta.journal, meta.volume, meta.page_range) == (
        "Proceedings of an Old Society",
        "3",
        "11-19",
    )


def test_a_scanned_paper_is_read_with_ocr_first(tmp_path, monkeypatch):
    import book_ocr

    pdf = tmp_path / "papers" / "scan.pdf"
    pdf.parent.mkdir()
    c = canvas.Canvas(str(pdf))
    c.rect(100, 100, 200, 200, fill=1)  # only a picture: no text layer, like a scan
    c.showPage()
    c.save()
    read = []
    monkeypatch.setattr(
        book_ocr,
        "ocr_pages",
        lambda path, pages: read.append(pages) or {0: "doi:10.1364/OE.27.001234"},
    )
    monkeypatch.setattr(book_meta, "_get_json", lambda url: CROSSREF)
    meta = book_meta.identify(pdf, paper=True)
    assert read == [[0]] and meta.title == "Freeform Optics for Compact Imaging"


PAPER_ROW = {
    "type": "paper",
    "title": "Freeform Optics for Compact Imaging",
    "authors": "Jane Doe; Che-Ming Li; Mattie De Meester; Bo Chen",
    "year": "2019",
    "journal": "Optics Express",
    "volume": "27",
    "issue": "8",
    "page_range": "1234-1245",
    "doi": "10.1364/oe.27.001234",
}
BOOK_ROW = {"title": "Practical Lens Design", "authors": "Smith W.J.", "year": "2015",
            "publisher": "Example Press", "isbn": "9780306406157"}  # fmt: skip


def test_citation_formats():
    assert citation.split_name("Mattie De Meester") == ("Mattie", "De Meester")
    assert citation.split_name("Smith W.J.") == ("W.J.", "Smith")
    assert citation.split_name("Shannon, Robert R.") == ("Robert R.", "Shannon")
    assert citation.initials("Che-Ming") == "C.-M." and citation.initials("W.J.") == "W. J."

    assert citation.apa(PAPER_ROW) == (
        "Doe, J., Li, C.-M., De Meester, M., & Chen, B. (2019). Freeform Optics for Compact "
        "Imaging. Optics Express, 27(8), 1234–1245. https://doi.org/10.1364/oe.27.001234"
    )
    assert citation.ieee(PAPER_ROW) == (
        'J. Doe, C.-M. Li, M. De Meester, and B. Chen, "Freeform Optics for Compact Imaging," '
        "Optics Express, vol. 27, no. 8, pp. 1234–1245, 2019, doi: 10.1364/oe.27.001234."
    )
    assert citation.gbt(PAPER_ROW) == (
        "DOE J, LI C-M, DE MEESTER M, et al. Freeform Optics for Compact Imaging[J]. "
        "Optics Express, 2019, 27(8): 1234-1245. DOI:10.1364/oe.27.001234."
    )
    ris = citation.ris(PAPER_ROW).splitlines()
    assert ris[0] == "TY  - JOUR" and "AU  - De Meester, Mattie" in ris
    assert "SP  - 1234" in ris and "EP  - 1245" in ris and ris[-1] == "ER  - "

    assert citation.apa(BOOK_ROW) == "Smith, W. J. (2015). Practical Lens Design. Example Press."
    assert citation.ieee(BOOK_ROW) == "W. J. Smith, Practical Lens Design. Example Press, 2015."
    assert citation.gbt(BOOK_ROW) == "SMITH W J. Practical Lens Design[M]. Example Press, 2015."
    # An article number instead of pages (common in open-access journals)
    assert "Art. no. 474" in citation.ieee(PAPER_ROW | {"page_range": "474"})
    # No authors: no stray punctuation
    no_author = {"title": "An Untitled Report", "year": "1950"}
    assert citation.apa(no_author) == "An Untitled Report (1950)."
    assert citation.gbt(no_author) == "An Untitled Report[M]. 1950."
    assert [f["key"] for f in citation.all_formats(PAPER_ROW)] == [
        "apa",
        "ieee",
        "gbt",
        "bibtex",
        "ris",
    ]


def test_paper_keywords_from_details_page_or_openalex(monkeypatch):
    details = {"/Keywords": "laser; weed control; laser; fiber laser"}
    assert book_meta.paper_keywords(details, "") == "laser; weed control; fiber laser"
    page = (
        "Some Title\nJane Doe\nKeywords: beam shaping, homogenizer, excimer laser\n\n"
        "1. Introduction\nText of the paper."
    )
    assert book_meta.paper_keywords({}, page) == "beam shaping; homogenizer; excimer laser"
    assert book_meta.keywords_from_page("Index Terms—Optics; lenses\nI. INTRODUCTION") == [
        "Optics",
        "lenses",
    ]
    answer = {"keywords": [{"display_name": "Excimer laser"}, {"display_name": "Uniformity"}]}
    monkeypatch.setattr(book_meta, "_get_json", lambda url: answer)
    assert book_meta.paper_keywords({}, "no keyword line here", "10.1117/12.143846") == (
        "Excimer laser; Uniformity"
    )
    assert book_meta.paper_keywords({}, "nothing", "10.1/x", online=False) == ""
