"""Add bookmarks (the PDF outline) to books that don't have any.

    uv run scripts/add_bookmarks.py --dry-run          # what every book without bookmarks would get
    uv run scripts/add_bookmarks.py                    # add them (asks first)
    uv run scripts/add_bookmarks.py books/<slug>.pdf   # one book

Bookmarks come from what the library already knows about a book:
  - "Contents" -> the printed Contents page
  - one bookmark per chapter -> the page where the chapter starts (as used by Read)
  - its sections nested inside -> page = the section's printed page number, shifted by the
    same amount as its chapter (so missing or extra pages elsewhere in a scan don't matter).
    A section whose page is unreadable or doesn't fall inside its chapter is left out.

Books that already have bookmarks are never touched. The first time a book is changed, the
original is kept in archive/books/.
"""

import argparse
import hashlib
import io
import sys
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median

import paths
import safe_io
from book_toc import contents_pages, read_toc
from ocr_pdf import PdfChanged, ask, replace_pdf
from pypdf import PdfReader, PdfWriter

LIBRARY = paths.LIBRARY
BOOKS = LIBRARY / "books"
ARCHIVE_BOOKS = LIBRARY / "archive" / "books"
OUTPUT_DIR = LIBRARY / ".cache" / "bookmarks-output"
# How far one chapter's printed-to-PDF shift may differ from the others' (scans drift a few
# pages where pages are missing; a false match is usually off by dozens)
MAX_SHIFT_DRIFT = 10


@dataclass
class Mark:
    title: str
    page: int  # 0-based PDF page index
    children: list[Mark] = field(default_factory=list)


def estimate_missing_starts(chapters, starts: dict[int, int], page_count: int) -> None:
    """Fill in chapters whose opening page wasn't found, from their printed Contents page.

    Uses the printed-to-PDF shift of the nearest earlier chapter that was found (else the
    nearest later one), and only if the result keeps the chapters in order.
    """
    shifts = {
        c.number: starts[c.number] - c.page for c in chapters if c.number in starts and c.page
    }
    if not shifts:
        return
    # A found start far off the shift the other chapters agree on is a false match (e.g. the
    # title in a figure caption): drop it and estimate that chapter like the missing ones
    if len(shifts) >= 3:
        typical = median(shifts.values())
        for n, shift in list(shifts.items()):
            if abs(shift - typical) > MAX_SHIFT_DRIFT:
                del shifts[n], starts[n]
    for ch in chapters:
        if ch.number in starts or ch.page is None:
            continue
        earlier = [n for n in shifts if n < ch.number]
        nearest = max(earlier) if earlier else min(shifts)
        page = ch.page + shifts[nearest]
        before = [p for n, p in starts.items() if n < ch.number]
        after = [p for n, p in starts.items() if n > ch.number]
        if (
            1 <= page <= page_count
            and (not before or page > max(before))
            and (not after or page < min(after))
        ):
            starts[ch.number] = page


def plan_bookmarks(pdf: Path) -> list[Mark]:
    """The bookmarks this PDF should get; empty if it already has some or nothing was found."""
    from library_server import find_chapter_pages

    reader = PdfReader(pdf)
    if reader.outline:
        return []
    page_count = len(reader.pages)
    chapters = read_toc(pdf)
    starts = find_chapter_pages(pdf, [{"number": c.number, "title": c.title} for c in chapters])
    estimate_missing_starts(chapters, starts, page_count)

    marks: list[Mark] = []
    if contents := contents_pages(reader):
        marks.append(Mark("Contents", contents[0]))
    numbered = [c for c in chapters if c.number in starts]
    for k, ch in enumerate(numbered):
        start = starts[ch.number] - 1
        end = starts[numbered[k + 1].number] - 1 if k + 1 < len(numbered) else page_count
        mark = Mark(f"{ch.number}  {ch.title}", start)
        if ch.page is not None:
            shift = start - ch.page  # printed page -> PDF index, measured at this chapter
            last = start
            for title, printed in zip(ch.sections, ch.section_pages, strict=False):
                if printed is None:
                    continue
                page = printed + shift
                if last <= page < max(end, start + 1):  # inside the chapter, in order
                    mark.children.append(Mark(title, page))
                    last = page
        marks.append(mark)
    return marks if numbered else []


def write_bookmarks(pdf: Path, marks: list[Mark]) -> None:
    """Rewrite `pdf` with these bookmarks; the first original is kept in archive/books/.
    ocr_pdf.PdfChanged if the PDF changed (marks saved) meanwhile: then it stays as it is."""
    with safe_io.lock_for(pdf):  # read whole, never half-way through a marks save
        data = pdf.read_bytes()
    source = hashlib.sha256(data).hexdigest()  # (ocr_pdf.fingerprint of what was read)
    writer = PdfWriter(clone_from=io.BytesIO(data))
    for mark in marks:
        parent = writer.add_outline_item(mark.title, mark.page)
        for child in mark.children:
            writer.add_outline_item(child.title, child.page, parent=parent)
    writer.page_mode = "/UseOutlines"  # open with the bookmarks panel showing
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_DIR / pdf.name
    try:
        with tmp.open("wb") as f:
            writer.write(f)
        replace_pdf(pdf, tmp, ARCHIVE_BOOKS / f"{pdf.stem}-before-bookmarks.pdf", source=source)
    finally:  # (after a replacement, tmp is the PDF already)
        tmp.unlink(missing_ok=True)


def describe(marks: list[Mark]) -> str:
    chapters = [m for m in marks if m.title != "Contents"]
    sections = sum(len(m.children) for m in marks)
    contents = " + Contents" if len(chapters) < len(marks) else ""
    return f"{len(chapters)} chapters, {sections} sections{contents}"


def main() -> None:
    sys.stdout.reconfigure(errors="replace")  # filenames in any language, any terminal
    import add_book
    import library_page

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    paths.add_argument(parser)
    parser.add_argument("pdf", nargs="?", type=Path, help="one book (default: all in books/)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true", help="don't ask before changing a PDF")
    args = parser.parse_args()

    targets = [args.pdf.resolve()] if args.pdf else sorted(BOOKS.glob("*.pdf"))
    for pdf in targets:
        if not pdf.exists():
            sys.exit(f"No such file: {pdf}")
        if PdfReader(pdf).outline:
            if args.pdf:
                print(f"{pdf.name} already has bookmarks; leaving it as it is.")
            continue
        print(pdf.name)
        marks = plan_bookmarks(pdf)
        if not marks:
            print("  ! no chapters found, so no bookmarks to add")
            continue
        print(f"  -> {describe(marks)}")
        if args.dry_run or not (args.yes or ask("  Add these bookmarks? [Y/n] ")):
            continue
        try:
            write_bookmarks(pdf, marks)
        except PdfChanged as e:
            print(f"  ! {e}; run this again to add the bookmarks to it")
            continue
        add_book.forget_chapter_pages(pdf.stem)  # Read now uses the bookmarks
        print("  -> bookmarks added")
    if not args.dry_run:
        library_page.build()


if __name__ == "__main__":
    main()
