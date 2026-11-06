"""Turn a scanned (image-only) PDF into a searchable PDF with an invisible text layer.

    uv run scripts/ocr_pdf.py books/<slug>.pdf        # OCR a book that's already in the library
    uv run scripts/ocr_pdf.py books/<slug>.pdf --yes  # without the confirmation question

Every page keeps its scanned image; OCR'd text is drawn invisibly on top at the same place,
so the PDF can be searched, text can be selected and copied, and the library reads its
Contents and chapter pages like any other PDF. The original file is kept in archive/books/.
add_book.py offers this automatically when a new book turns out to be a scan.

About 1.5 s per page. Progress is cached (.cache/ocr/), so an interrupted run resumes.
"""

import argparse
import io
import sys
import time
from pathlib import Path
from statistics import median

import paths
from book_ocr import group_lines, has_text_layer, ocr_boxes
from pypdf import PdfReader, PdfWriter, Transformation

LIBRARY = paths.LIBRARY
ARCHIVE_BOOKS = LIBRARY / "archive" / "books"
OUTPUT_DIR = LIBRARY / ".cache" / "ocr-output"
FONT_FILES = [Path("C:/Windows/Fonts/arial.ttf"), Path("/Library/Fonts/Arial Unicode.ttf")]
SECONDS_PER_PAGE = 1.5  # typical OCR speed, for the time estimates shown before starting

_font = None


def _font_name() -> str:
    """A TrueType font so Greek letters and symbols survive; Helvetica as a fallback."""
    global _font
    if _font is None:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        _font = "Helvetica"
        for path in FONT_FILES:
            if path.exists():
                pdfmetrics.registerFont(TTFont("OCRText", str(path)))
                _font = "OCRText"
                break
    return _font


def needs_ocr(pdf: Path) -> bool:
    return not has_text_layer(PdfReader(pdf))


def ocr_minutes(pages: int) -> float:
    return pages * SECONDS_PER_PAGE / 60


def text_overlay(width: float, height: float, boxes: list[list]):
    """A one-page PDF of the given size with the OCR'd words drawn invisibly where they are.

    One text object per printed line, on a shared baseline, words left to right, so text
    extraction gives the same lines as the printed page (OCR returns a contents entry as
    separate boxes: "2.3", title, page number).
    """
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas

    font = _font_name()
    buffer = io.BytesIO()
    page = canvas.Canvas(buffer, pagesize=(width, height))
    for line in group_lines(boxes):
        size = max(1.0, median(b[3] - b[1] for b in line) * 0.8)
        bottom = median(b[3] for b in line)
        text = page.beginText()
        text.setTextRenderMode(3)  # invisible: there for search and copy, not for the eye
        text.setFont(font, size)
        text.setTextOrigin(line[0][0], height - bottom + size * 0.25)  # baseline near the bottom
        for k, (x0, _, x1, _, word) in enumerate(line):
            if k:
                text.moveCursor(x0 - line[k - 1][0], 0)  # next word's left edge, same baseline
            natural = stringWidth(word + " ", font, size)
            # stretch each word (plus a space, so extracted words stay separated) over its box
            text.setHorizScale(100 * (x1 - x0) / natural if natural else 100)
            text.textOut(word + " ")
        page.drawText(text)
    page.showPage()
    page.save()
    buffer.seek(0)
    return PdfReader(buffer).pages[0]


def add_text_layer(src: Path, dst: Path, progress=None) -> None:
    """Write `dst`: `src` with an invisible OCR text layer on every page; `progress(done, total)`
    is called after each page (for the library page's progress bar)."""
    import pypdfium2 as pdfium

    writer = PdfWriter(clone_from=src)  # keeps bookmarks and metadata
    document = pdfium.PdfDocument(src)
    total, started, skipped = len(writer.pages), time.time(), 0
    for i, page in enumerate(writer.pages):
        if page.rotation:
            skipped += 1  # rare in scans; positions would need rotating too
        else:
            boxes = ocr_boxes(src, i, document)
            if boxes:
                box = page.mediabox
                overlay = text_overlay(float(box.width), float(box.height), boxes)
                page.merge_transformed_page(
                    overlay, Transformation().translate(float(box.left), float(box.bottom))
                )
        if progress:
            progress(i + 1, total)
        if (i + 1) % 10 == 0 or i + 1 == total:
            left = (time.time() - started) / (i + 1) * (total - i - 1)
            print(f"\r  OCR page {i + 1}/{total}, ~{left / 60:.0f} min left   ", end="", flush=True)
    print()
    document.close()
    if skipped:
        print(f"  ! {skipped} rotated pages were left without text")
    writer.compress_identical_objects()
    with dst.open("wb") as f:
        writer.write(f)


def replace_pdf(pdf: Path, new: Path, keep: Path) -> None:
    """Put `new` in place of `pdf`. The old file moves to `keep`, unless `keep` already
    holds an earlier original (then the old file, itself a derived copy, is dropped)."""
    keep.parent.mkdir(parents=True, exist_ok=True)
    try:
        if not keep.exists():
            pdf.rename(keep)
        new.replace(pdf)
    except PermissionError:
        raise SystemExit(
            f"  ! {pdf.name} is open in another program (browser tab, PDF viewer, VS Code), so "
            "Windows won't let it be replaced. Close it and run the same command again "
            "(any OCR is cached, so the second run takes seconds)."
        ) from None


def make_searchable(pdf: Path, progress=None) -> Path:
    """OCR `pdf` in place. The untouched original goes to archive/books/; returns its path."""
    keep = ARCHIVE_BOOKS / pdf.name
    if keep.exists():
        keep = keep.with_name(f"{keep.stem}-scan-{int(time.time())}{keep.suffix}")
    # Built outside books/, so a half-finished file is never mistaken for a new book
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_DIR / pdf.name
    add_text_layer(pdf, tmp, progress)
    replace_pdf(pdf, tmp, keep)
    return keep


def ask(question: str, default: bool = True) -> bool:
    """Yes/no question; Enter gives `default`."""
    try:
        answer = input(question).strip().lower()
    except EOFError:  # not run from a terminal: don't start a long job unasked
        return False
    return default if not answer else answer in ("y", "yes")


def main() -> None:
    sys.stdout.reconfigure(errors="replace")  # filenames in any language, any terminal
    import add_book  # here, not at the top: add_book imports this module
    import library_page

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    paths.add_argument(parser)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--yes", action="store_true", help="don't ask before starting")
    args = parser.parse_args()

    pdf = args.pdf.resolve()
    if not pdf.exists():
        sys.exit(f"No such file: {pdf}")
    if not needs_ocr(pdf):
        print(f"{pdf.name} already has a text layer; nothing to do.")
        return
    pages = len(PdfReader(pdf).pages)
    if not args.yes and not ask(
        f"OCR {pages} pages of {pdf.name} (~{ocr_minutes(pages):.0f} min)? [Y/n] "
    ):
        print("Nothing changed.")
        return
    keep = make_searchable(pdf)
    print(f"  -> {pdf.name} is now searchable; the original scan is in {paths.display(keep)}")

    # A book already in the library: re-read its chapters from the new text layer
    if add_book.SLUG_RE.match(pdf.stem) and pdf.parent in add_book.folders():
        add_book.refresh_chapters(pdf, dry_run=False)
        library_page.build()


if __name__ == "__main__":
    main()
