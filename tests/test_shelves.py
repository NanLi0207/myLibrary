"""Shelves for new items, learned from how the others are shelved."""

import add_book
import catalog
import pytest
import shelves
from book_meta import Meta
from reportlab.pdfgen import canvas

BOOKS = [
    # slug, title, keywords, shelves
    ("a-2001-lens-design-basics", "Lens Design Basics", "", "Optics; Lens design"),
    ("b-2002-practical-lens-design", "Practical Lens Design", "aberrations", "Optics; Lens design"),
    ("c-2003-modern-lens-design", "Modern Lens Design", "", "Optics; Lens design"),
    ("d-2004-laser-beam-shaping", "Laser Beam Shaping", "beam optics", "Optics; Lasers"),
    ("e-2005-laser-damage", "Laser-induced Damage of Optical Materials", "", "Optics; Lasers"),
    ("f-2006-railway-track", "Modern Railway Track", "ballast; sleepers", ""),
]


@pytest.fixture
def library(tmp_path, monkeypatch):
    (tmp_path / "library.toml").write_text(
        '[shelves]\nOptics = "光学 Optics"\n"Lens design" = "镜头设计 Lens design"\n'
        'Lasers = "激光 Lasers"\nOptomechanics = "光机设计 Optomechanics"\n',
        encoding="utf-8",
    )
    glossaries = tmp_path / "glossaries"
    glossaries.mkdir()
    (glossaries / "optics.csv").write_text(
        "term,zh,note,definition\nfocal length,焦距,,\nrefractive index,折射率,,\n"
        "diffraction,衍射,,\nfield,视场,,\nsurface,表面,,\n",
        encoding="utf-8",
    )
    (glossaries / "glossaries.toml").write_text('[optics]\nlabel = "光学 Optics"\n', "utf-8")
    for slug, title, keywords, on in BOOKS:
        catalog.upsert(
            tmp_path / "catalog.csv",
            {"slug": slug, "title": title, "keywords": keywords, "shelves": on},
        )
    monkeypatch.setattr(shelves, "LIBRARY", tmp_path)
    for name in ("BOOKS", "PAPERS", "THESES", "EXAMPLES", "NOTES"):
        monkeypatch.setattr(add_book, name, tmp_path / name.lower())
    monkeypatch.setattr(add_book, "LIBRARY", tmp_path)
    monkeypatch.setattr(add_book, "CATALOG", tmp_path / "catalog.csv")
    return tmp_path


def suggest(library, **row):
    rows = list(catalog.load(library / "catalog.csv").values())
    return shelves.suggest(row, rows, library, library / "catalog.csv")


def test_by_name_and_shelves_that_always_come_together(library):
    # "lens design" in the title -> Lens design; and every Lens design book is on Optics
    assert suggest(library, title="Lens Design Fundamentals") == ["Optics", "Lens design"]
    # Any form of the name: "lasers" for Lasers, "opto-mechanical" for Optomechanics
    assert "Lasers" in suggest(library, title="Beam uniformity of flat top lasers")
    assert suggest(library, title="Opto-Mechanical Systems Design") == ["Optomechanics"]


def test_by_glossary_terms_but_not_everyday_words(library):
    found = suggest(library, title="Fresnel biprism", keywords="focal length; refractive index")
    assert found == ["Optics"]
    # "field" and "surface" are in the glossary too, but they're everyday words
    assert (
        suggest(library, title="A field test of leaf contamination on the railhead surface") == []
    )


def test_unrelated_items_stay_unshelved(library):
    assert suggest(library, title="Pro Git", keywords="version control") == []
    assert suggest(library, title="Friction in Wheel-Rail Contacts") == []


def test_a_shelf_is_never_made_up(library):
    assert set(suggest(library, title="Laser lens design optics")) <= {
        "Optics",
        "Lens design",
        "Lasers",
        "Optomechanics",
    }


def test_new_items_are_shelved_once_and_never_overruled(library):
    pdf = library / "books" / "smith-1992-lens-design-fundamentals.pdf"
    pdf.parent.mkdir()
    c = canvas.Canvas(str(pdf))
    c.drawString(72, 700, "Lens Design Fundamentals")
    c.save()
    meta = Meta(title="Lens Design Fundamentals", author="Smith", year="1992")
    add_book.setup_book(pdf, add_book.Book(meta.title, meta.author, meta.year), meta)
    row = catalog.load(library / "catalog.csv")[pdf.stem]
    assert row["shelves"] == "Optics; Lens design"
    # Your own choice afterwards is kept: setting it up again doesn't touch it
    catalog.set_field(library / "catalog.csv", pdf.stem, "shelves", "Lasers")
    add_book.setup_book(pdf, add_book.Book(meta.title, meta.author, meta.year), meta)
    assert catalog.load(library / "catalog.csv")[pdf.stem]["shelves"] == "Lasers"
