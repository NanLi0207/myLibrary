"""OCR for scanned PDFs whose pages are images with no text layer.

Pages are rendered with pypdfium2 and read with RapidOCR (pure pip packages, no system
install). Results are cached in .cache/ocr/, so each page is only read once (~1.5 s/page).
Used by book_toc.py to read the printed Contents of a scanned book.
"""

import json
import logging
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / ".cache" / "ocr"
RENDER_SCALE = 1.5  # ~110 dpi for a typical scan: sharp enough for contents pages

_engine = None


def _ocr_engine():
    global _engine
    if _engine is None:
        from rapidocr import RapidOCR

        logging.getLogger("RapidOCR").setLevel(logging.WARNING)
        _engine = RapidOCR()
    return _engine


def group_lines(boxes: list[list]) -> list[list[list]]:
    """OCR boxes [x0, y0, x1, y1, text] grouped into printed lines (top to bottom), each
    sorted left to right.

    Contents pages put the title on the left and the page number far to the right, which
    OCR returns as separate boxes; boxes at the same height belong to one line.
    """
    if not boxes:
        return []
    tolerance = 0.5 * median(b[3] - b[1] for b in boxes)
    lines: list[list[list]] = []
    for box in sorted(boxes, key=lambda b: (b[1] + b[3]) / 2):
        center = (box[1] + box[3]) / 2
        if lines and abs(center - median((b[1] + b[3]) / 2 for b in lines[-1])) <= tolerance:
            lines[-1].append(box)
        else:
            lines.append([box])
    return [sorted(line, key=lambda b: b[0]) for line in lines]


def _bounds(box) -> list[float]:
    """[x0, y0, x1, y1] of an OCR box given as four corner points."""
    xs, ys = [p[0] for p in box], [p[1] for p in box]
    return [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]


def _cache_file(pdf: Path, kind: str = "") -> Path:
    # name + size: a different file with the same name doesn't reuse stale results
    return CACHE_DIR / f"{pdf.stem}-{pdf.stat().st_size}{kind}.json"


def ocr_pages(pdf: Path, pages: list[int], top: float | None = None) -> dict[int, str]:
    """{page index: text} for the given 0-based pages, using the cache where possible.

    With `top` (e.g. 0.22) only that top fraction of each page is read: about 3x faster,
    enough to spot a chapter's opening heading.
    """
    cache_file = _cache_file(pdf, f"-top{int(top * 100)}" if top else "")
    cache = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}
    missing = [i for i in pages if str(i) not in cache]
    if missing:
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(pdf)
        for i in missing:
            if i >= len(document):
                continue
            image = document[i].render(scale=1.0 if top else RENDER_SCALE).to_pil()
            if top:
                image = image.crop((0, 0, image.width, int(image.height * top)))
            result = _ocr_engine()(image)
            boxes = [
                [*_bounds(box), text]
                for box, text in zip(
                    result.boxes if result.boxes is not None else [],
                    result.txts or [],
                    strict=False,
                )
            ]
            cache[str(i)] = "\n".join(" ".join(b[4] for b in line) for line in group_lines(boxes))
        document.close()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return {i: cache.get(str(i), "") for i in pages}


MIN_SCORE = 0.5  # drop OCR boxes the engine itself isn't sure about


def ocr_boxes(pdf: Path, page: int, document=None) -> list[list]:
    """Words on one page as [x0, y0, x1, y1, text] in PDF points, measured from the top-left.

    Cached like ocr_pages (one file per PDF), so an interrupted run picks up where it stopped.
    Pass an open pypdfium2 `document` when calling for many pages.
    """
    cache_file = _cache_file(pdf, "-boxes")
    cache = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}
    if str(page) not in cache:
        import pypdfium2 as pdfium

        doc = document or pdfium.PdfDocument(pdf)
        result = _ocr_engine()(doc[page].render(scale=RENDER_SCALE).to_pil())
        if document is None:
            doc.close()
        boxes = []
        for box, text, score in zip(
            result.boxes if result.boxes is not None else [],
            result.txts or [],
            result.scores or [],
            strict=False,
        ):
            if score >= MIN_SCORE and text.strip():
                boxes.append([round(v / RENDER_SCALE, 2) for v in _bounds(box)] + [text])
        cache[str(page)] = boxes
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return cache[str(page)]


def has_text_layer(reader, sample: int = 12) -> bool:
    """False for image-only scans: the first pages give (almost) no extractable text."""
    pages = reader.pages[: min(sample, len(reader.pages))]
    return sum(len((p.extract_text() or "").strip()) for p in pages) > 200
