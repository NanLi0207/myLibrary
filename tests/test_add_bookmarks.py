import add_bookmarks
from add_bookmarks import Mark, estimate_missing_starts
from book_toc import Chapter
from pypdf import PdfReader, PdfWriter


def test_missing_chapter_start_estimated_from_printed_page():
    chapters = [Chapter(1, "A", page=1), Chapter(2, "B", page=20), Chapter(3, "C", page=40)]
    starts = {1: 13, 3: 52}  # chapter 2's opening page wasn't found; shift here is +12
    estimate_missing_starts(chapters, starts, page_count=100)
    assert starts[2] == 32


def test_estimate_never_breaks_chapter_order():
    chapters = [Chapter(1, "A", page=1), Chapter(2, "B", page=90), Chapter(3, "C", page=40)]
    starts = {1: 13, 3: 52}  # a garbled printed page for chapter 2 would land after chapter 3
    estimate_missing_starts(chapters, starts, page_count=200)
    assert 2 not in starts


def test_bookmarks_written_and_original_kept(tmp_path, monkeypatch):
    monkeypatch.setattr(add_bookmarks, "ARCHIVE_BOOKS", tmp_path / "archive")
    monkeypatch.setattr(add_bookmarks, "OUTPUT_DIR", tmp_path / "out")
    pdf = tmp_path / "doe-2015-practical-lens-design.pdf"
    writer = PdfWriter()
    for _ in range(10):
        writer.add_blank_page(width=200, height=200)
    writer.write(pdf)

    marks = [
        Mark("Contents", 1),
        Mark("1  Basics", 3, [Mark("1.1 Rays", 4)]),
        Mark("2  Aberrations", 7),
    ]
    add_bookmarks.write_bookmarks(pdf, marks)

    reader = PdfReader(pdf)
    top = [item for item in reader.outline if not isinstance(item, list)]
    assert [(m.title, reader.get_destination_page_number(m)) for m in top] == [
        ("Contents", 1),
        ("1  Basics", 3),
        ("2  Aberrations", 7),
    ]
    nested = reader.outline[2]  # children follow their parent as a list
    assert [(m.title, reader.get_destination_page_number(m)) for m in nested] == [("1.1 Rays", 4)]
    assert (tmp_path / "archive" / "doe-2015-practical-lens-design-before-bookmarks.pdf").exists()


def test_false_chapter_match_is_replaced_by_estimate():
    chapters = [Chapter(n, str(n), page=p) for n, p in enumerate([1, 27, 49, 65, 96, 105], 1)]
    starts = {1: 14, 2: 40, 3: 62, 5: 31, 6: 118}  # chapter 5 "found" on a caption, page 31
    estimate_missing_starts(chapters, starts, page_count=154)
    assert starts[5] == 96 + 13 and starts[4] == 65 + 13
