import ocr_pdf
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader


def make_scan(path, lines):
    """An image-only PDF page, like a scanner produces."""
    image = Image.new("RGB", (1240, 1754), "white")  # A4 at 150 dpi
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("arial.ttf", 44)
    for n, line in enumerate(lines):
        draw.text((120, 150 + 90 * n), line, fill="black", font=font)
    image.save(path, "PDF", resolution=150)


def test_scan_becomes_searchable(tmp_path):
    scan = tmp_path / "scan.pdf"
    make_scan(scan, ["CONTENTS", "1 Paraxial Optics 1", "2 Stops and Pupils 20"])
    assert ocr_pdf.needs_ocr(scan)

    out = tmp_path / "searchable.pdf"
    ocr_pdf.add_text_layer(scan, out)

    text = PdfReader(out).pages[0].extract_text()
    for word in ("CONTENTS", "Paraxial", "Optics", "Stops", "Pupils"):
        assert word in text
    # Each printed line comes out as one line, number + title + page number together,
    # so the Contents parser can read it
    lines = [" ".join(ln.split()) for ln in text.splitlines() if ln.strip()]
    assert "1 Paraxial Optics 1" in lines and "2 Stops and Pupils 20" in lines
    from book_toc import toc_from_text

    assert [(c.number, c.title) for c in toc_from_text(text)] == [
        (1, "Paraxial Optics"),
        (2, "Stops and Pupils"),
    ]
    # The page still shows the same scanned image
    assert len(PdfReader(out).pages[0].images) == 1


def test_add_book_asks_about_remaining_scans(tmp_path, monkeypatch):
    import argparse

    import add_book

    for name in ("BOOKS", "PAPERS", "THESES", "EXAMPLES", "NOTES"):
        monkeypatch.setattr(add_book, name, tmp_path / name.lower())
    monkeypatch.setattr(add_book, "CATALOG", tmp_path / "catalog.csv")
    monkeypatch.setattr(add_book, "LIBRARY", tmp_path)
    monkeypatch.setattr(add_book, "ARCHIVE", tmp_path / "archive")
    monkeypatch.setattr(ocr_pdf, "ARCHIVE_BOOKS", tmp_path / "archive" / "books")
    monkeypatch.setattr(ocr_pdf, "OUTPUT_DIR", tmp_path / ".cache" / "ocr-output")
    add_book.BOOKS.mkdir()
    scan = add_book.BOOKS / "doe-2015-scanned-book.pdf"
    # Enough text that, once OCR'd, the page counts as having a text layer (> 200 characters)
    topics = ["Paraxial Optics", "Stops and Pupils", "Thin Lenses", "Aberrations", "Tolerances"]
    topics += ["Glass Selection", "Mirror Systems", "Image Quality"]
    make_scan(
        scan,
        ["CONTENTS"] + [f"{n} {t} of Optical Systems {n * 7}" for n, t in enumerate(topics, 1)],
    )
    args = argparse.Namespace(no_ocr=False, ocr=False, dry_run=False)

    questions = []
    monkeypatch.setattr(add_book, "ask", lambda q, default=True: questions.append(q) or False)
    add_book.check_remaining_scans(args)
    assert len(questions) == 1 and scan.name in questions[0]
    assert ocr_pdf.needs_ocr(scan)  # answered no: left alone

    monkeypatch.setattr(add_book, "ask", lambda q, default=True: True)
    add_book.check_remaining_scans(args)
    assert not ocr_pdf.needs_ocr(scan)  # answered yes: now searchable
    assert (tmp_path / "archive" / "books" / scan.name).exists()  # original kept

    questions.clear()
    monkeypatch.setattr(add_book, "ask", lambda q, default=True: questions.append(q) or False)
    add_book.check_remaining_scans(args)
    assert questions == []  # nothing left to ask about
