from pathlib import Path

import add_book
import catalog
import pytest
from book_meta import Meta, clean_filename, find_isbns, identify, isbn13, parse_filename
from book_toc import tidy, toc_from_chapter_pages, toc_from_fonts, toc_from_text
from pypdf import PdfWriter


@pytest.fixture(autouse=True)
def isolated_library(tmp_path, monkeypatch):
    """Never let a test touch the real books/, notes/, examples/ or catalog.csv."""
    for name in ("BOOKS", "EXAMPLES", "NOTES"):
        monkeypatch.setattr(add_book, name, tmp_path / name.lower())
    monkeypatch.setattr(add_book, "CATALOG", tmp_path / "catalog.csv")
    monkeypatch.setattr(add_book, "ARCHIVE", tmp_path / "archive")
    monkeypatch.setattr(add_book, "PAGE_CACHE", tmp_path / ".cache" / "chapter_pages.json")


# Invented headings, shaped like real books' tables of contents
CONTENTS_TEXT = """\
CONTENTS
Preface ix
1 FIRST-ORDER OPTICS 1
1.1 Rays and Wavefronts 2
1.2 Thin Lenses . . . . . . 9
2 Stops and Pupils 20
2.1 Aperture Stop 21
3.1 Vignetting 40
10 Somewhere Street, Some City 12345
Index 400
"""


def make_pdf(path: Path, outline: dict[str, list[str]]) -> None:
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=200, height=200)
    writer.add_outline_item("Contents", 0)
    for chapter, sections in outline.items():
        parent = writer.add_outline_item(chapter, 1)
        for s in sections:
            writer.add_outline_item(s, 2, parent=parent)
    writer.write(path)


def test_contents_text_parsing():
    chapters = toc_from_text(CONTENTS_TEXT)
    assert [(c.number, c.title) for c in chapters] == [
        (1, "First-Order Optics"),
        (2, "Stops and Pupils"),
        (3, "Chapter 3"),  # heading missing from the text: placeholder
    ]
    assert chapters[0].sections == ["1.1 Rays and Wavefronts", "1.2 Thin Lenses"]
    assert chapters[2].sections == ["3.1 Vignetting"]


def test_new_pdf_gets_renamed_with_chapter_templates(tmp_path):
    add_book.BOOKS.mkdir()
    pdf = add_book.BOOKS / "Practical Lens Design{Jane Q. Doe}(2015, Example Press){1}.pdf"
    make_pdf(pdf, {"1 Basics": ["1.1 Rays", "1.2 Lenses"], "Chapter 2: Aberrations": []})

    meta = identify(pdf, online=False)
    book = add_book.Book(meta.title, meta.author, meta.year, meta.publisher)
    add_book.add_book(pdf, book, dry_run=False)

    notes = tmp_path / "notes" / "doe-2015-practical-lens-design"
    assert (tmp_path / "books" / "doe-2015-practical-lens-design.pdf").exists()
    assert sorted(p.name for p in notes.iterdir()) == [
        "README.md",
        "ch01-basics.md",
        "ch02-aberrations.md",
    ]
    ch1 = (notes / "ch01-basics.md").read_text(encoding="utf-8")
    assert "# Chapter 1: Basics" in ch1 and "## 1.1 Rays" in ch1
    assert "[Ch 2: Aberrations](ch02-aberrations.md)" in (notes / "README.md").read_text(
        encoding="utf-8"
    )


def test_filename_styles():
    cases = {
        "Example Lens Design (Doe J.) (z-library.sk, 1lib.sk, z-lib.sk)": "Doe J.",
        "Some Optics Book (SPIE Press PM1) (Jane Doe) (z-library.sk, 1lib.sk)": "Jane Doe",
        "Optics Basics{Ann Lee}(2001, Example Press){123} libgen.li": "Ann Lee",
        "Lens Notes -- Bob Ray -- 2, 2003 -- Example Press -- isbn13 9780306406157 -- "
        "0123456789abcdef0123456789abcdef -- Anna’s Archive": "Bob Ray",
    }
    for stem, author in cases.items():
        assert parse_filename(stem).author == author, stem
    assert parse_filename(list(cases)[3]).year == "2003"
    assert "z-library" not in clean_filename(list(cases)[0])


def test_surnames():
    assert add_book.surname("Smith W.J.") == "smith"
    assert add_book.surname("Joseph M.Geary") == "geary"
    assert add_book.surname("Shannon, Robert Rennie, 1932-") == "shannon"
    assert add_book.surname("Rudolf Kingslake; R. Barry Johnson") == "kingslake"
    assert add_book.surname("Fischer, Robert Edward. Tadic-Galeb etc.") == "fischer"


def test_isbn_detection():
    assert find_isbns("ISBN 0-306-40615-2 and ISBN-13: 978-0-306-40615-7") == [
        "0306406152",
        "9780306406157",
    ]
    assert find_isbns("phone 1234567890") == []  # bad checksum


def test_catalog_row_written_and_updated(tmp_path):
    add_book.BOOKS.mkdir()
    pdf = add_book.BOOKS / "doe-2015-practical-lens-design.pdf"  # already named by hand
    make_pdf(pdf, {"1 Basics": []})

    book = add_book.Book("Practical Lens Design", "Jane Q. Doe", "2015")
    meta = Meta(isbn="9780306406157", pages="3")
    add_book.setup_book(pdf, book, meta)
    add_book.setup_book(pdf, book, Meta(subjects="Optics"))  # rerun updates the row

    rows = catalog.load(tmp_path / "catalog.csv")
    row = rows["doe-2015-practical-lens-design"]
    assert (row["isbn"], row["pages"], row["subjects"], row["chapters"]) == (
        "9780306406157",
        "3",
        "Optics",
        "1",
    )
    assert not (tmp_path / "examples").exists()  # scripts only when asked for
    assert add_book.unregistered_named_books() == []


def test_isbn10_to_13():
    assert isbn13("0306406152") == "9780306406157"


def test_contents_with_ocr_noise_and_wrapped_lines():
    # Invented contents page with typical scan problems
    text = """\
CONTENTS
Preface ix
Chapter 1. Getting Started 1
Chapter 2. A Long Chapter Title That Wraps
Onto a Second Line 15
2.1 First Topic s
2.2 Second Topic io
S LOST NUMBER CHAPTER 40
3.1 Something 41
3.1.1 Deeper Level Ignored 42
Chapter 5. Skipped Four Because OCR Lost It 60
1.1 Body text starts here 1
"""
    chapters = toc_from_text(text)
    assert [(c.number, c.title) for c in chapters] == [
        (1, "Getting Started"),
        (2, "A Long Chapter Title That Wraps Onto a Second Line"),
        (3, "Lost Number Chapter"),
        (5, "Skipped Four Because OCR Lost It"),
    ]
    assert chapters[1].sections == ["2.1 First Topic", "2.2 Second Topic"]
    assert chapters[2].sections == ["3.1 Something"]


def test_contents_by_font():
    lines = [
        (True, "Table of Contents"),
        (True, "Glossary xi"),
        (True, "Basics 1"),
        (False, "Sign Conventions 1"),
        (False, "Paraxial Rays 2"),
        (True, "Design Forms 10"),
        (False, "Doublets 11"),
    ]
    chapters = toc_from_fonts(lines)
    assert [(c.number, c.title, c.sections) for c in chapters] == [
        (1, "Basics", ["Sign Conventions", "Paraxial Rays"]),
        (2, "Design Forms", ["Doublets"]),
    ]


def test_chapter_opening_pages():
    pages = [
        "Preface\nSome words.",
        "Chapter 1\nThe First\nChapter Title\nBody text begins here and runs on for a long while.",
        "1.1 A Section\nmore body\n1.2 Another Section",
        "Chapter 2\nSecond\nBody text.",
    ]
    chapters = toc_from_chapter_pages(pages)
    assert [(c.number, c.title) for c in chapters] == [
        (1, "The First Chapter Title"),
        (2, "Second"),
    ]
    assert chapters[0].sections == ["1.1 A Section", "1.2 Another Section"]


def test_control_characters_in_bookmarks():
    assert tidy("Chapter 5:\rScattering from\rDust\x00") == "Chapter 5: Scattering from Dust"


def test_remove_book_archives_everything(tmp_path):
    add_book.BOOKS.mkdir()
    pdf = add_book.BOOKS / "doe-2015-practical-lens-design.pdf"
    make_pdf(pdf, {"1 Basics": []})
    add_book.setup_book(pdf, add_book.Book("Practical Lens Design", "Jane Doe", "2015"), Meta())
    note = tmp_path / "notes" / "doe-2015-practical-lens-design" / "ch01-basics.md"
    note.write_text("my own notes", encoding="utf-8")
    script = tmp_path / "examples" / "doe-2015-practical-lens-design" / "ch01_basics.py"
    script.parent.mkdir(parents=True)
    script.write_text("print('my check')\n", encoding="utf-8")
    add_book.PAGE_CACHE.parent.mkdir()
    add_book.PAGE_CACHE.write_text('{"doe-2015-practical-lens-design": {"1": 3}}', encoding="utf-8")

    add_book.remove_book("doe-2015-practical-lens-design", dry_run=True, yes=True)
    assert pdf.exists()  # dry run changes nothing

    add_book.remove_book("doe-2015-practical-lens-design", dry_run=False, yes=True)
    archive = tmp_path / "archive"
    assert not pdf.exists() and (archive / "books" / pdf.name).exists()
    archived_note = archive / "notes" / "doe-2015-practical-lens-design" / "ch01-basics.md"
    assert archived_note.read_text(encoding="utf-8") == "my own notes"
    archived_script = archive / "examples" / "doe-2015-practical-lens-design" / "ch01_basics.py"
    assert archived_script.read_text(encoding="utf-8") == "print('my check')\n"
    assert catalog.load(tmp_path / "catalog.csv") == {}
    assert add_book.PAGE_CACHE.read_text(encoding="utf-8").strip() == "{}"


def test_pdf_author_must_look_like_a_name():
    from book_meta import looks_like_name

    assert looks_like_name("Robert R. Shannon")
    assert looks_like_name("Smith W.J.")
    for junk in ("https://imagemagick.org", "www.example.com", "me@example.com", "Ghostscript", ""):
        assert not looks_like_name(junk), junk


def test_ocr_boxes_grouped_into_lines():
    from book_ocr import group_lines

    # [x0, y0, x1, y1, text]: title and page number are separate boxes on one line
    boxes = [
        [900, 91, 930, 111, "12"],
        [100, 90, 400, 110, "1.2 Thin Lenses"],
        [100, 130, 300, 150, "1.3 Stops"],
        [905, 131, 935, 151, "20"],
    ]
    lines = [" ".join(b[4] for b in line) for line in group_lines(boxes)]
    assert lines == ["1.2 Thin Lenses 12", "1.3 Stops 20"]


def test_contents_continue_past_one_stray_page():
    from book_toc import find_contents

    contents = "CONTENTS\n" + "\n".join(f"{n}.1 Topic {n} {n * 10}" for n in range(1, 7))
    more = "\n".join(f"{n}.1 Topic {n} {n * 10}" for n in range(7, 13))
    body = "\n".join(["Ordinary text without page numbers on each line."] * 8)
    texts = {0: "Title page", 1: contents, 2: body, 3: more, 4: body, 5: body}
    assert find_contents(texts) == [1, 3]


def test_chapter_opening_ignores_running_headers():
    from book_toc import Chapter, chapter_opening

    ch = Chapter(4, "Image Analysis")
    assert chapter_opening("4\nIMAGE ANALYSIS", ch) == 2  # the opening page
    assert chapter_opening("Chapter 4", ch) == 2
    assert chapter_opening("284 IMAGE ANALYSIS", ch) == 1  # running header: title only
    assert chapter_opening("4.1 Image Quality Measures", ch) == 0
