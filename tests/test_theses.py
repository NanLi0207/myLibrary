"""Theses: recognised by their title page, with degree, university and supervisors."""

import add_book
import book_meta
import citation
import library_page
import library_server
import pytest
import thesis_meta
from pypdf import PdfWriter
from reportlab.pdfgen import canvas
from testlib import entry, id_of, put  # noqa: F401


@pytest.fixture
def library(tmp_path, monkeypatch):
    for module in (library_server, library_page):
        monkeypatch.setattr(module, "LIBRARY", tmp_path)
        monkeypatch.setattr(module, "CATALOG", tmp_path / "catalog.csv")
    for name in ("BOOKS", "PAPERS", "THESES", "EXAMPLES", "NOTES"):
        monkeypatch.setattr(add_book, name, tmp_path / name.lower())
    monkeypatch.setattr(add_book, "LIBRARY", tmp_path)
    monkeypatch.setattr(add_book, "CATALOG", tmp_path / "catalog.csv")
    monkeypatch.setattr(add_book, "PAGE_CACHE", tmp_path / ".cache" / "chapter_pages.json")
    monkeypatch.setattr(library_server, "CACHE", tmp_path / ".cache" / "chapter_pages.json")
    return tmp_path


def thesis_pdf(path, lines=None):
    """An invented PhD thesis: title page (title in a large font), then chapters with bookmarks."""
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path))
    c.setFont("Helvetica", 11)
    c.drawString(72, 790, "UNIVERSITY OF EXAMPLETOWN")
    c.setFont("Helvetica-Bold", 24)
    c.drawString(72, 700, "Freeform Mirrors for")
    c.drawString(72, 672, "Compact Telescopes")
    c.setFont("Helvetica", 12)
    for i, line in enumerate(
        lines
        or [
            "A thesis submitted in partial fulfilment of the requirements",
            "for the degree of Doctor of Philosophy",
            "by",
            "Jane Q. Doe",
            "Supervisor: Prof. John Smith",
            "Department of Physics, University of Exampletown",
            "March 2019",
        ]
    ):
        c.drawString(72, 600 - 20 * i, line)
    c.showPage()
    for chapter in ("1 Introduction", "2 Mirror Design", "3 Results"):
        for _ in range(3):
            c.setFont("Helvetica", 11)
            c.drawString(72, 750, f"Chapter {chapter}: some text of the invented thesis.")
            c.showPage()
    c.save()
    writer = PdfWriter(clone_from=str(path))
    for number, title in enumerate(("1 Introduction", "2 Mirror Design", "3 Results")):
        writer.add_outline_item(title, 1 + 3 * number)
    writer.write(str(path))


def test_title_page_gives_everything_offline(tmp_path):
    pdf = tmp_path / "scan_2019_final(1).pdf"
    thesis_pdf(pdf)
    meta = book_meta.identify(pdf, online=False)
    assert meta.kind == "thesis"
    assert (meta.title, meta.author, meta.year) == (
        "Freeform Mirrors for Compact Telescopes",
        "Jane Q. Doe",
        "2019",
    )
    assert (meta.degree, meta.institution, meta.supervisors) == (
        "PhD",
        "University of Exampletown",
        "Prof. John Smith",
    )
    assert add_book.Book(meta.title, meta.author, meta.year).slug == (
        "doe-2019-freeform-mirrors-compact-telescopes"
    )


def test_master_thesis_and_name_without_by(tmp_path):
    pdf = tmp_path / "x.pdf"
    thesis_pdf(pdf, ["Master Thesis", "Max Mustermann", "Betreuer: Dr. Erika Muster", "2021"])
    meta = book_meta.identify(pdf, online=False)
    assert (meta.kind, meta.degree, meta.author, meta.supervisors) == (
        "thesis",
        "Master",
        "Max Mustermann",
        "Dr. Erika Muster",
    )


@pytest.mark.parametrize(
    "page, degree",
    [
        (
            "Femtosecond Laser Ablation\nDissertation\nzur Erlangung des Doktorgrades des\n"
            "Fachbereichs Physik der Universität Dortmund\nvorgelegt von\nM.Sc. Vanja Margetic\n"
            "Dortmund 2002",
            "PhD",
        ),  # fmt: skip
        (
            "LASER CLADDING WITH POWDER\nPROEFSCHRIFT\nter verkrijging van\nde graad van doctor "
            "aan de Universiteit Twente\ndoor\nMarcel Fredrik Schneider",
            "PhD",
        ),  # fmt: skip
        (
            "Optical Design\nMasterarbeit\nim Studiengang Physik\nvorgelegt von\nErika Muster\n"
            "Betreuer: Prof. Dr.-Ing. A. B",
            "Master",
        ),  # fmt: skip
        ("激光加工研究\n博士学位论文\n作者姓名：张三\n指导教师：李四 教授\n清华大学\n2020", "PhD"),
        ("A Study of Lenses\nBachelor's Thesis\nby Ann Lee\n2022", "Bachelor"),
    ],
)
def test_title_page_formulas(page, degree):
    found = thesis_meta.find_title_page(["", page])
    assert found and found.index == 1
    assert thesis_meta.degree(page) == degree


def test_title_page_details_in_other_languages():
    german = (
        "Femtosecond Laser Ablation\nDissertation\nzur Erlangung des Doktorgrades des\n"
        "Fachbereichs Physik der Universität Dortmund\nvorgelegt von\nM.Sc. Vanja Margetic\n"
        "aus Zagreb\nDortmund 2002"
    )
    assert thesis_meta.institution(german) == "Universität Dortmund"
    assert thesis_meta.author_on_page(german) == "Vanja Margetic"  # no "M.Sc.", no "aus ..."
    assert thesis_meta.printed_year(german) == "2002"
    dutch = (
        "Promotor:\nProf.dr. L.H.J.F. Beckmann (Universiteit Twente)\n"
        "Erstgutachter: Prof. Dr . K. Niemax"
    )
    assert thesis_meta.supervisors(dutch) == "Prof.dr. L.H.J.F. Beckmann; Prof. Dr. K. Niemax"
    chinese = "激光加工研究\n博士学位论文\n作者姓名：张三\n指导教师：李四\n清华大学\n2020"
    assert thesis_meta.institution(chinese) == "清华大学"
    assert thesis_meta.author_on_page(chinese) == "张三"
    assert thesis_meta.supervisors(chinese) == "李四"
    # Letter-spaced names can't be read: better none than a wrong one
    assert thesis_meta.author_on_page("vorgelegt von\nVa n j a M a r g e t i c") == ""


def test_papers_and_books_are_not_theses():
    # A paper's first page is full of text, even if it mentions a thesis in passing
    paper = "Freeform optics\nAbstract\n" + "This work is part of my PhD thesis on lenses. " * 50
    assert thesis_meta.find_title_page([paper]) is None
    preface = "Preface\nThis book grew out of lectures on optical design for engineers."
    assert thesis_meta.find_title_page([preface, "Contents\n1 Basics 1"]) is None


def test_online_details_with_the_pages_spelling_and_year(tmp_path, monkeypatch):
    work = {
        "title": "freeform mirrors for compact telescopes",
        "publication_year": 2020,  # put online a year after the defence
        "doi": "https://doi.org/10.5555/thesis.1",
        "authorships": [{"author": {"display_name": "Jane Doé"}, "institutions": []}],
        "primary_location": {"source": {"display_name": "Repo (University of Exampletown)"}},
    }
    asked = []

    def answer(url, **kwargs):
        asked.append(url)
        return {"results": [work]} if "type:dissertation" in url else None

    monkeypatch.setattr(book_meta, "_get_json", answer)
    pdf = tmp_path / "x.pdf"
    thesis_pdf(pdf)
    meta = book_meta.identify(pdf)
    assert "filter=type:dissertation" in asked[0]
    assert meta.title == "Freeform Mirrors for Compact Telescopes"  # the page's capitals
    assert meta.author == "Jane Doé" and meta.doi == "10.5555/thesis.1"
    assert meta.year == "2019" and meta.sources["year"].startswith("title page")


def test_crossref_dissertation_and_datacite(monkeypatch):
    crossref = {
        "message": {
            "type": "dissertation",
            "title": ["Nano-crystalline ceramic laser materials and lasers"],
            "author": [{"given": "Hua", "family": "Gong"}],
            "approved": {"date-parts": [[2011]]},
            "institution": [{"name": "Nanyang Technological University"}],
            "publisher": "Nanyang Technological University",
        }
    }
    monkeypatch.setattr(book_meta, "_get_json", lambda url, **kw: crossref)
    meta = book_meta.crossref("10.32657/10356/44837")
    assert (meta.kind, meta.year, meta.institution, meta.publisher) == (
        "thesis",
        "2011",
        "Nanyang Technological University",
        "",
    )
    csl = {
        "title": "Femtosecond laser ablation",
        "author": [{"family": "Margetic", "given": "Vanja"}],
        "issued": {"date-parts": [[2003, 1, 7]]},
        "contributor": [{"literal": "Technische Universität Dortmund"}],
        "publisher": "Eldorado",
    }
    seen = {}
    monkeypatch.setattr(book_meta, "_get_json", lambda url, **kw: seen.update(kw) or csl)
    meta = thesis_meta.doi_csl("10.17877/de290r-14813")
    assert seen["headers"]["Accept"] == "application/vnd.citationstyles.csl+json"
    assert (meta.author, meta.year, meta.institution) == (
        "Vanja Margetic",
        "2003",
        "Technische Universität Dortmund",
    )


def test_arxiv_comment_says_thesis(monkeypatch):
    feed = """<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <entry><title>Numerical treatment of disorder in PHC slabs</title>
      <author><name>Momchil Minkov</name></author><published>2015-08-19T00:00:00Z</published>
      <arxiv:comment>Master thesis</arxiv:comment>
      <arxiv:doi>10.1000/a.paper.from.it</arxiv:doi></entry></feed>"""
    import xml.etree.ElementTree as ElementTree

    monkeypatch.setattr(book_meta, "_get_xml", lambda url: ElementTree.fromstring(feed))
    meta = book_meta.arxiv("1508.04630")
    assert (meta.kind, meta.degree, meta.journal) == ("thesis", "Master", "")
    assert meta.doi == "10.48550/arxiv.1508.04630"  # the thesis, not a paper made from it


def test_thesis_is_filed_with_chapters_and_details(library):
    download = library / "books" / "thesis_final.pdf"
    thesis_pdf(download)
    meta = book_meta.identify(download, online=False)
    add_book.add_book(download, add_book.Book(meta.title, meta.author, meta.year), False, meta)

    slug = "doe-2019-freeform-mirrors-compact-telescopes"
    assert (library / "theses" / f"{slug}.pdf").exists() and not download.exists()
    notes = library / "notes" / slug
    readme = (notes / "README.md").read_text(encoding="utf-8")
    assert "| Degree | PhD thesis |" in readme
    assert "| University | University of Exampletown |" in readme
    assert "| Supervisors | Prof. John Smith |" in readme
    assert "[Ch 2: Mirror Design](ch02-mirror-design.md)" in readme  # chapters, like a book
    assert (notes / "ch01-introduction.md").exists() and not (notes / "notes.md").exists()
    row = entry(library / "catalog.csv", slug)
    assert (row["type"], row["degree"], row["institution"], row["file"]) == (
        "thesis",
        "PhD",
        "University of Exampletown",
        f"theses/{slug}.pdf",
    )
    assert row["publisher"] == "" and row["openlibrary"] == ""

    # The library page: "PhD thesis", and the chapters work as for a book
    [book] = library_page.books()
    assert book["kind"] == "thesis" and len(book["chapter_list"]) == 3
    assert '"PhD": "PhD thesis"' in library_page.render()
    # A PDF already in theses/ is a thesis even without a title page
    other = library / "theses" / "notes-from-my-supervisor.pdf"
    writer = PdfWriter()
    writer.add_blank_page(200, 200)
    writer.write(other)
    assert book_meta.identify(other, online=False, thesis=True).kind == "thesis"


def test_thesis_citations():
    row = {
        "type": "thesis",
        "title": "Freeform Mirrors for Compact Telescopes",
        "authors": "Jane Q. Doe",
        "year": "2019",
        "degree": "PhD",
        "institution": "University of Exampletown",
        "doi": "10.5555/thesis.1",
    }
    assert citation.apa(row) == (
        "Doe, J. Q. (2019). Freeform Mirrors for Compact Telescopes [Doctoral dissertation, "
        "University of Exampletown]. https://doi.org/10.5555/thesis.1"
    )
    assert citation.ieee(row | {"degree": "Master"}) == (
        'J. Q. Doe, "Freeform Mirrors for Compact Telescopes," M.S. thesis, '
        "University of Exampletown, 2019."
    )
    assert citation.gbt(row) == (
        "DOE J Q. Freeform Mirrors for Compact Telescopes[D]. University of Exampletown, 2019."
    )
    assert citation.bibtex(row).startswith("@phdthesis{doe2019freeform,")
    assert "school = {University of Exampletown}" in citation.bibtex(row)
    assert citation.bibtex(row | {"degree": "Master"}).startswith("@mastersthesis{")
    ris = citation.ris(row).splitlines()
    assert ris[0] == "TY  - THES" and "PB  - University of Exampletown" in ris
    assert "M3  - Doctoral dissertation" in ris
