"""Build the public Test & Demo library (test_library/) from scratch: synthetic PDFs plus
synthetic study data, filed by the app's own code. Run it only to (re)make the canonical
library on purpose; its output is committed to git as it is.

    uv run tests/make_test_library.py --out test_library     # the folder must not exist yet

Everything is made here, offline, from the project's own dependencies (reportlab, pypdf,
pypdfium2, rapidocr for the one genuine OCR layer). No font is embedded except reportlab's own
standard fonts (Helvetica, Times, Courier, Symbol) and the non-embedded Adobe CID font
STSong-Light for Chinese, so nothing in the corpus carries a third party's font licence.

How it works: a temporary library and settings (as the tests' isolation does) are chosen
before any app module is imported; each PDF is filed with add_book.add_book(online=False),
exactly as ＋ Add would file it, and the study data is written through the app's own functions
(ticks, Last read, reading log, review answers, topic notes) or in their formats (notes,
vocabulary). The result is copied to --out without caches. MANIFEST.json records every PDF's
checksum and what the tests expect of it (tests/test_test_library.py).
"""

import argparse
import io
import json
import os
import random
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
LIBRARY_ID = "6f1c2a9e-3b7d-4e58-9a0c-1d2e3f405162"  # the canonical test library's id

# A rebuild gives the same library: every document keeps its id (keyed by the name of the file
# it is built from), every "today" is this date (added, Last read, vocabulary), and encryption
# salts come from a seeded generator. A new document needs a new line here (a fresh UUID4,
# uuid.uuid4()); an id is never changed or reused.
CORPUS_DATE = date(2026, 11, 9)
FIXED_IDS = {
    "optics": "6fab383f-5072-4992-9321-c2cc86506da6",
    "linalg": "f7bfc074-91e2-4ce0-98da-9cfdb9b71904",
    "algorithms": "cde9bf07-3628-4a41-bd3d-634237aed39c",
    "writing": "94d23a3d-3b0c-4a21-8456-4351292c1271",
    "cell-scan": "93579638-7741-4575-9f69-dd3da3a606bc",
    "anatomy-ocr": "f23d1178-c524-4eaf-9861-16a33d7b9524",
    "stats-mixed": "6fa7184a-4e6f-465e-ba80-9fb95baaac90",
    "fieldnotes": "14b61393-0edd-4639-9d2b-09f7071648a5",
    "legacy": "5483d057-5dd1-44ae-bc93-6f9ff4897f49",
    "sparse": "9fc5c34a-33a4-400d-a804-9d981331d79f",
    "thermal": "f8bbb5a6-1ce8-4366-af6f-fac2188f4114",
    "sleep": "57960acb-5d8f-4cbb-bc29-bb68f2aaada0",
    "sparse-preprint": "3ae79daf-9785-49b4-8965-3dfab62f9a22",
    "survey": "b1bfbc17-5be4-4b6c-82a9-26995dde02b5",
    "thesis-phd": "919f34ff-956c-4c54-80bb-573e30ea236f",
    "thesis-ma": "5ebd6a73-feab-4053-8ebe-ff2c429f0a01",
    "plos-optics": "c57d06cb-85a1-4c94-970d-dd9b9d0a3526",
    "plos-tsr": "3f959bb0-9c15-4d7d-ba77-d61059dde8f8",
}

# --- a temporary library before any app module is imported -------------------------------

WORK = Path(tempfile.mkdtemp(prefix="myLibrary-make-test-library-"))
(WORK / "library").mkdir()
(WORK / "settings.toml").write_text("# make_test_library\n", encoding="utf-8")
os.environ["MYLIBRARY_LIBRARY"] = str(WORK / "library")
os.environ["MYLIBRARY_SETTINGS"] = str(WORK / "settings.toml")
sys.path.insert(0, str(APP / "scripts"))

import add_book  # noqa: E402
import catalog  # noqa: E402
import library_server  # noqa: E402
import ocr_pdf  # noqa: E402
import paths  # noqa: E402
import pypdfium2  # noqa: E402
import reader  # noqa: E402
import reading_log  # noqa: E402
import safe_io  # noqa: E402
import vocab_review  # noqa: E402
from book_meta import Meta  # noqa: E402
from PIL import Image  # noqa: E402
from pypdf import PdfReader, PdfWriter  # noqa: E402
from pypdf.generic import (  # noqa: E402
    ArrayObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
    TextStringObject,
)
from reportlab.lib.pagesizes import A4, landscape  # noqa: E402
from reportlab.lib.utils import ImageReader, simpleSplit  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.cidfonts import UnicodeCIDFont  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

assert paths.LIBRARY == (WORK / "library").resolve(), "not the temporary library"
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
ocr_pdf.FONT_FILES = []  # the OCR layer in Helvetica: never a system font embedded
LIB = paths.LIBRARY
STAGE = WORK / "stage"
STAGE.mkdir()
CREATOR = "myLibrary test corpus (tests/make_test_library.py)"
W, H = A4

LOREM = (
    "This paragraph is synthetic text written for the myLibrary test corpus. It has no "
    "meaning beyond giving the reader, the search index and the notes panel something to "
    "work with. Words such as aperture, convergence, eigenvalue, recursion, membrane and "
    "archive appear so that searches find them on known pages."
)


# --- drawing helpers --------------------------------------------------------------------------


def new_canvas(path: Path, title: str, author: str, subject: str = "", size=A4):
    c = canvas.Canvas(str(path), pagesize=size, invariant=1, pageCompression=1)
    c.setTitle(title)
    c.setAuthor(author)
    c.setSubject(subject)
    c.setCreator(CREATOR)
    c.setProducer(CREATOR)
    return c


def para(c, text: str, x: float, y: float, width: float, font="Times-Roman", size=11.0, lead=14):
    """Wrapped text from (x, y) downwards; returns the y below it."""
    c.setFont(font, size)
    for line in simpleSplit(text, font, size, width):
        c.drawString(x, y, line)
        y -= lead
    return y - lead * 0.4


def heading(c, text: str, x: float, y: float, size=16):
    c.setFont("Helvetica-Bold", size)
    c.drawString(x, y, text)
    return y - size * 1.8


def footer(c, number: int, size=A4):
    c.setFont("Helvetica", 9)
    c.drawCentredString(size[0] / 2, 30, str(number))


def equation(c, x: float, y: float) -> float:
    """1/f = 1/s + 1/s' as a typeset fraction, and n1 sin(theta1) = n2 sin(theta2) with
    Symbol-font Greek."""
    c.setFont("Times-Italic", 13)
    for i, (num, den) in enumerate((("1", "f"), ("1", "s"), ("1", "s'"))):
        cx = x + 20 + i * 70
        c.drawCentredString(cx, y + 8, num)
        c.line(cx - 10, y + 4, cx + 10, y + 4)
        c.drawCentredString(cx, y - 10, den)
        if i < 2:
            c.drawCentredString(cx + 35, y, "=" if i == 0 else "+")
    c.drawString(x + 240, y, "(1.1)")
    y -= 34
    c.setFont("Times-Italic", 13)
    c.drawString(x + 10, y, "n")
    c.setFont("Times-Roman", 9)
    c.drawString(x + 17, y - 3, "1")
    c.setFont("Times-Roman", 13)
    c.drawString(x + 25, y, "sin")
    c.setFont("Symbol", 13)
    c.drawString(x + 45, y, "q")  # theta
    c.setFont("Times-Roman", 13)
    c.drawString(x + 60, y, "= n")
    c.setFont("Times-Roman", 9)
    c.drawString(x + 84, y - 3, "2")
    c.setFont("Times-Roman", 13)
    c.drawString(x + 92, y, "sin")
    c.setFont("Symbol", 13)
    c.drawString(x + 112, y, "q")
    c.setFont("Times-Roman", 13)
    c.drawString(x + 240, y, "(1.2)")
    return y - 30


def table(c, x: float, y: float, rows: list[list[str]], widths: list[float], caption: str):
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x, y, caption)
    y -= 8
    row_h = 18
    for r, row in enumerate(rows):
        c.setFont("Helvetica-Bold" if r == 0 else "Helvetica", 10)
        cx = x
        for cell, w in zip(row, widths, strict=True):
            c.rect(cx, y - row_h, w, row_h)
            c.drawString(cx + 4, y - row_h + 5, cell)
            cx += w
        y -= row_h
    return y - 20


def figure(c, x: float, y: float, caption: str) -> float:
    """A lens and three rays, with a caption."""
    c.setLineWidth(1)
    c.line(x, y - 60, x + 260, y - 60)  # axis
    c.ellipse(x + 120, y - 110, x + 140, y - 10)
    for dy in (-35, 0, 35):
        c.line(x + 10, y - 60 + dy, x + 130, y - 60 + dy)
        c.line(x + 130, y - 60 + dy, x + 240, y - 60)
    c.setFont("Helvetica-Oblique", 9.5)
    c.drawString(x, y - 128, caption)
    return y - 150


def bar_chart(c, x: float, y: float, values: list[int], caption: str) -> float:
    c.line(x, y - 100, x + 220, y - 100)
    c.line(x, y - 100, x, y)
    for i, v in enumerate(values):
        c.rect(x + 15 + i * 40, y - 100, 25, v, fill=1)
    c.setFont("Helvetica-Oblique", 9.5)
    c.drawString(x, y - 118, caption)
    return y - 140


# --- documents ----------------------------------------------------------------------------


def book_pdf(path: Path, title: str, author: str, chapters: list[tuple[str, list[str]]], *,
             subject: str, bookmarks: bool = True, contents: bool = False, extras=None,
             landscape_page: bool = False, font="Times-Roman") -> None:  # fmt: skip
    """A book: title page, (printed contents), one page per chapter with sections;
    `extras(c, chapter_number, y)` adds equations, tables or figures."""
    c = new_canvas(path, title, author, subject)
    page = 1
    c.setFont("Helvetica-Bold", 24)
    for i, line in enumerate(simpleSplit(title, "Helvetica-Bold", 24, W - 140)):
        c.drawCentredString(W / 2, H - 200 - i * 30, line)
    c.setFont("Helvetica", 14)
    c.drawCentredString(W / 2, H - 300, author)
    c.drawCentredString(W / 2, H - 330, "Synthetic test edition: not a real book")
    c.showPage()
    page += 1
    first_chapter_page = page + (1 if contents else 0)
    if contents:
        y = heading(c, "Contents", 70, H - 90, 20)
        c.setFont("Times-Roman", 12)
        for n, (name, _) in enumerate(chapters, 1):
            c.drawString(80, y, f"{n}  {name}")
            c.drawRightString(W - 80, y, str(first_chapter_page + n - 1))
            y -= 22
        footer(c, page)
        c.showPage()
        page += 1
    for n, (name, sections) in enumerate(chapters, 1):
        if landscape_page and n == len(chapters):
            c.setPageSize(landscape(A4))
        size = c._pagesize
        if bookmarks:
            key = f"ch{n}"
            c.bookmarkPage(key)
            c.addOutlineEntry(f"{n} {name}", key, level=0)
        y = heading(c, f"Chapter {n}  {name}", 70, size[1] - 90)
        for s, section in enumerate(sections, 1):
            y = heading(c, f"{n}.{s} {section}", 70, y, 12.5)
            y = para(c, LOREM, 70, y, size[0] - 140, font=font)
        if extras:
            y = extras(c, n, y)
        footer(c, page, size)
        c.showPage()
        if landscape_page and n == len(chapters):
            c.setPageSize(A4)
        page += 1
    c.save()


def two_column_paper(path: Path, title: str, authors: str, abstract: str, sections: list[str],
                     *, subject: str, journal: str, doi: str, extras=None, pages=2) -> None:  # fmt: skip
    c = new_canvas(path, title, authors, subject)
    col_w, gap, left = (W - 140 - 20) / 2, 20, 70
    for p in range(1, pages + 1):
        top = H - 70
        if p == 1:
            c.setFont("Helvetica", 9)
            c.drawString(left, H - 40, f"{journal} · doi:{doi} · synthetic test paper")
            c.setFont("Helvetica-Bold", 17)
            for i, line in enumerate(simpleSplit(title, "Helvetica-Bold", 17, W - 140)):
                c.drawString(left, top - i * 21, line)
            top -= 21 * (i + 1) + 6
            c.setFont("Helvetica", 11)
            c.drawString(left, top, authors.replace("; ", ", "))
            top = para(c, "Abstract. " + abstract, left, top - 22, W - 140, size=10, lead=13)
        for col in range(2):
            x, y = left + col * (col_w + gap), top
            for name in sections[(p - 1) * 2 + col : (p - 1) * 2 + col + 1]:
                y = heading(c, name, x, y, 11.5)
                y = para(c, LOREM + " " + LOREM, x, y, col_w, size=10, lead=12.5)
            if extras and col == 1:
                extras(c, p, x, y, col_w)
        footer(c, p)
        c.showPage()
    c.save()


def scan_of(src: Path, dst: Path, title: str, author: str, skew: float = 0.6) -> None:
    """dst: every page of src as a greyscale JPEG image only (no text): a scan."""
    document = pypdfium2.PdfDocument(str(src))
    c = new_canvas(dst, title, author, "scanned")
    for i in range(len(document)):
        page = document[i]
        image = page.render(scale=100 / 72, grayscale=True).to_pil().convert("L")
        image = image.rotate(skew, fillcolor=255, expand=False)
        data = io.BytesIO()
        image.save(data, "JPEG", quality=55)
        data.seek(0)
        c.drawImage(ImageReader(Image.open(data)), 0, 0, W, H)
        c.showPage()
    document.close()
    c.save()


def merge(parts: list[tuple[Path, list[int]]], dst: Path, title: str, author: str) -> None:
    writer = PdfWriter()
    for path, pages in parts:
        for n in pages:
            writer.add_page(PdfReader(path).pages[n])
    writer.add_metadata({"/Title": title, "/Author": author, "/Creator": CREATOR})
    with open(dst, "wb") as f:
        writer.write(f)


def legacy_pdf(dst: Path) -> None:
    """A hand-written PDF 1.3 file: classic xref table, Type1 Helvetica, two pages, no object
    streams, an Info dictionary with an old date: an older PDF's structure."""
    texts = [
        "A Legacy Document Structure: page 1 of a synthetic PDF 1.3 file.",
        "Page 2: written by hand with a classic cross-reference table.",
    ]
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 5 0 R "
        b"/Resources << /Font << /F1 7 0 R >> >> >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 6 0 R "
        b"/Resources << /Font << /F1 7 0 R >> >> >>",
    ]
    words = LOREM.replace("(", "").replace(")", "")
    for text in texts:
        lines = [text, *simpleSplit(words + " " + words, "Helvetica", 12, 460)]
        shown = " ".join(f"({line}) Tj T*" for line in lines)
        stream = f"BT /F1 12 Tf 16 TL 72 720 Td {shown} ET".encode("latin-1")
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(
        b"<< /Title (A Legacy Document Structure) /Author (Ola Format) "
        b"/Creator (myLibrary test corpus) /CreationDate (D:19990101000000) >>"
    )
    out = bytearray(b"%PDF-1.3\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for n, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % n + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        len(objects),
        xref,
    )
    dst.write_bytes(bytes(out))


def chinese_book(dst: Path) -> None:
    c = new_canvas(dst, "A Short History of Writing", "Shuwen Li", "humanities")
    c.setFont("STSong-Light", 22)
    c.drawCentredString(W / 2, H - 200, "书写简史")
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(W / 2, H - 235, "A Short History of Writing")
    c.setFont("Helvetica", 13)
    c.drawCentredString(W / 2, H - 280, "Shuwen Li · synthetic test edition")
    c.showPage()
    chapters = [
        ("Oracle Bones", "甲骨文", "甲骨文是刻在龟甲和兽骨上的文字，这里只是测试用的示例文字。"),
        ("Paper and Printing", "造纸与印刷", "造纸术与活字印刷改变了书籍的流传方式。测试文本：引号“”、书名号《》。"),
        ("Writing Today", "今日书写", "Unicode: café, naïve, Ångström, µm, ±0.5 °C, “quotes”, — dash, ½."),
    ]  # fmt: skip
    for n, (en, zh, text) in enumerate(chapters, 1):
        c.bookmarkPage(f"c{n}")
        c.addOutlineEntry(f"{n} {en}", f"c{n}", level=0)
        y = heading(c, f"Chapter {n}  {en}", 70, H - 90)
        c.setFont("STSong-Light", 16)
        c.drawString(70, y, f"第{n}章 {zh}")
        y -= 30
        c.setFont("STSong-Light", 12)
        for line in simpleSplit(text, "STSong-Light", 12, W - 140):
            c.drawString(70, y, line)
            y -= 18
        para(c, LOREM, 70, y - 10, W - 140)
        footer(c, n + 1)
        c.showPage()
    c.save()


def thesis_pdf(dst: Path, *, chinese: bool) -> None:
    if chinese:
        title_en, author = "Urban Memory and Oral History", "Mei Zhang"
        c = new_canvas(dst, title_en, author, "humanities thesis")
        c.setFont("STSong-Light", 22)
        c.drawCentredString(W / 2, H - 150, "硕士学位论文")
        c.drawCentredString(W / 2, H - 200, "城市记忆与口述历史")
        c.setFont("Helvetica-Bold", 17)
        c.drawCentredString(W / 2, H - 240, title_en)
        c.setFont("Helvetica", 12)
        lines = ["A thesis submitted for the degree of Master of Arts", f"by {author}",
                 "University of Testing", "Supervisor: Prof. Lin Archive", "2021"]  # fmt: skip
    else:
        title_en, author = "Learning Shortest Paths on Synthetic Graphs", "Elena Proof"
        c = new_canvas(dst, title_en, author, "computer science thesis")
        c.setFont("Helvetica-Bold", 19)
        c.drawCentredString(W / 2, H - 200, title_en)
        c.setFont("Helvetica", 12)
        lines = ["A thesis submitted for the degree of Doctor of Philosophy", f"by {author}",
                 "University of Testing", "Supervisors: Prof. Ada Lumen; Dr. Theo Graph", "2020"]  # fmt: skip
    for i, line in enumerate(lines):
        c.drawCentredString(W / 2, H - 300 - i * 22, line)
    c.showPage()
    parts = ["Introduction", "Background", "Method", "Results", "Conclusions"]
    y = heading(c, "Contents", 70, H - 90, 20)
    c.setFont("Times-Roman", 12)
    for n, name in enumerate(parts, 1):
        c.drawString(80, y, f"{n}  {name}")
        c.drawRightString(W - 80, y, str(n + 2))
        y -= 22
    for name, page in (("References", 8), ("Appendix A  Proofs", 9)):
        c.drawString(80, y, name)
        c.drawRightString(W - 80, y, str(page))
        y -= 22
    c.showPage()
    for n, name in enumerate(parts, 1):
        c.bookmarkPage(f"t{n}")
        c.addOutlineEntry(f"{n} {name}", f"t{n}", level=0)
        y = heading(c, f"Chapter {n}  {name}", 70, H - 90)
        y = para(c, LOREM, 70, y, W - 140)
        if chinese and n == 1:
            c.setFont("STSong-Light", 12)
            c.drawString(70, y, "口述历史记录了普通人的城市记忆。（测试文本）")
            y -= 24
        if n == 4:
            y = table(c, 70, y, [["Graph", "Nodes", "Error"], ["G1", "1,000", "0.12"],
                                 ["G2", "10,000", "0.08"]], [120, 100, 100], "Table 4.1 Results")  # fmt: skip
        footer(c, n + 2)
        c.showPage()
    for name, key in (("References", "refs"), ("Appendix A  Proofs", "appA")):
        c.bookmarkPage(key)
        c.addOutlineEntry(name, key, level=0)
        y = heading(c, name, 70, H - 90)
        if key == "refs":
            for i in range(1, 6):
                y = para(c, f"[{i}] A. Author. A synthetic reference number {i}. Journal of "
                         f"Synthetic Test Data, {2000 + i}.", 70, y, W - 140, size=10)  # fmt: skip
        else:
            y = para(c, "Proof of Lemma 1. " + LOREM, 70, y, W - 140)
        c.showPage()
    c.save()


def add_marks(pdf: Path) -> None:
    """A highlight and a sticky note on page 3, with /NM names: PDF annotation fixtures."""
    writer = PdfWriter(clone_from=str(pdf))

    x1, y1, x2, y2 = 70, H - 160, 300, H - 145
    highlight = DictionaryObject({
        NameObject("/Type"): NameObject("/Annot"),
        NameObject("/Subtype"): NameObject("/Highlight"),
        NameObject("/Rect"): ArrayObject([FloatObject(v) for v in (x1, y1, x2, y2)]),
        NameObject("/QuadPoints"): ArrayObject([FloatObject(v) for v in (x1, y2, x2, y2, x1, y1, x2, y1)]),
        NameObject("/C"): ArrayObject([FloatObject(1), FloatObject(0.9), FloatObject(0.2)]),
        NameObject("/NM"): TextStringObject("mylibrary-test-highlight-1"),
        NameObject("/Contents"): TextStringObject("A synthetic highlight"),
        NameObject("/F"): NumberObject(4),
    })  # fmt: skip
    note = DictionaryObject({
        NameObject("/Type"): NameObject("/Annot"),
        NameObject("/Subtype"): NameObject("/Text"),
        NameObject("/Rect"): ArrayObject([FloatObject(v) for v in (W - 90, H - 120, W - 70, H - 100)]),
        NameObject("/NM"): TextStringObject("mylibrary-test-note-1"),
        NameObject("/Contents"): TextStringObject("A synthetic sticky note: check eq. (1.1)."),
        NameObject("/F"): NumberObject(4),
    })  # fmt: skip
    writer.add_annotation(page_number=2, annotation=highlight)
    writer.add_annotation(page_number=2, annotation=note)
    with open(pdf, "wb") as f:
        writer.write(f)


def rotate_page(pdf: Path, index: int) -> None:
    writer = PdfWriter(clone_from=str(pdf))
    writer.pages[index].rotate(90)
    with open(pdf, "wb") as f:
        writer.write(f)


class _SeededSecrets:
    """pypdf's salts and keys from a generator seeded with the file's name: the same file on
    every rebuild (a test fixture: its encryption protects nothing)."""

    def __init__(self, seed: str):
        self._random = random.Random(seed)

    def token_bytes(self, n: int) -> bytes:
        return self._random.randbytes(n)


def encrypt(src: Path, dst: Path, user_password: str) -> None:
    import pypdf._crypt_providers._cryptography as provider
    import pypdf._encryption as encryption

    writer = PdfWriter(clone_from=str(src))
    seeded = _SeededSecrets(dst.name)  # salts, keys and each stream's IV
    real = encryption.secrets, provider.secrets
    encryption.secrets = provider.secrets = seeded
    try:
        writer.encrypt(user_password=user_password, owner_password="owner-test",
                       algorithm="AES-256")  # fmt: skip
        with open(dst, "wb") as f:
            writer.write(f)
    finally:
        encryption.secrets, provider.secrets = real


class _CorpusDate(date):
    @classmethod
    def today(cls):
        return CORPUS_DATE


for _module in (add_book, library_server, reader):  # their date.today() is CORPUS_DATE
    _module.date = _CorpusDate


# --- the corpus ---------------------------------------------------------------------------

DOCS = []  # filled by build(): what each catalog document is and what tests expect


def doc(kind: str, title: str, author: str, year: str, pdf: Path, *, subject: str, field: str,
        topic: str, features: list[str], meta: dict | None = None,
        expect: dict | None = None, provenance: dict | None = None) -> None:  # fmt: skip
    DOCS.append({"kind": kind, "title": title, "author": author, "year": year, "pdf": pdf,
                 "subject": subject, "field": field, "topic": topic, "features": features,
                 "meta": meta or {}, "expect": expect or {}, "provenance": provenance})  # fmt: skip


# Real documents, each with a licence verified at the source (test_library/README.md). They
# are put into the library as they are, byte for byte: --real-from names a folder holding the
# files (download them from pdf_url); each must match its SHA-256, or nothing is built.
REAL = [
    {
        "file": "plos-optics.pdf",
        "sha256": "bb943236476a97bae2ce84f0455c35f9cf535bd55a8977da727372e65b5a32e1",
        "kind": "paper",
        "title": "Optimizing the internal phase reference to shape the output of a multimode optical fiber",
        "author": "Liam Collard; Linda Piscopo; Filippo Pisano; Di Zheng; Massimo De Vittorio; Ferruccio Pisanello",
        "year": "2023",
        "meta": {
            "journal": "PLOS ONE",
            "volume": "18",
            "issue": "9",
            "page_range": "e0290300",
            "doi": "10.1371/journal.pone.0290300",
            "publisher": "Public Library of Science",
        },
        "subject": "physics/optics",
        "field": "Physics and Astronomy",
        "topic": "Optical Fibers and Wavefront Shaping",
        "features": [
            "real research paper",
            "PDF 1.6, publisher typesetting, embedded fonts",
            "figures, equations, references",
            "12 pages",
        ],
        "expect": {"text": True, "first_page_contains": "e0290300"},
        "provenance": {
            "source_url": "https://doi.org/10.1371/journal.pone.0290300",
            "pdf_url": "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0290300&type=printable",
            "licence": "CC BY 4.0",
            "licence_url": "https://creativecommons.org/licenses/by/4.0/",
            "attribution": "Collard L, Piscopo L, Pisano F, Zheng D, De Vittorio M, Pisanello F (2023) Optimizing the internal phase reference to shape the output of a multimode optical fiber. PLoS ONE 18(9): e0290300. https://doi.org/10.1371/journal.pone.0290300. Licensed under CC BY 4.0; unchanged.",
            "evidence": 'Article page (journals.plos.org, checked 2026-11-09): "This is an open access article distributed under the terms of the Creative Commons Attribution License", linked to creativecommons.org/licenses/by/4.0/; the same statement is printed on page 1 of the PDF. No figure is marked as reproduced from elsewhere.',
        },
    },
    {
        "file": "plos-tsr.pdf",
        "sha256": "93b6752052ef18f987fee5be87009e5027be03bf78624ea160c9229bb20db5e9",
        "kind": "paper",
        "title": "Ten Simple Rules for Writing a PLOS Ten Simple Rules Article",
        "author": "Harriet Dashnow; Andrew Lonsdale; Philip E. Bourne",
        "year": "2014",
        "meta": {
            "journal": "PLOS Computational Biology",
            "volume": "10",
            "issue": "10",
            "page_range": "e1003858",
            "doi": "10.1371/journal.pcbi.1003858",
            "publisher": "Public Library of Science",
        },
        "subject": "computational biology / scientific writing",
        "field": "Biochemistry, Genetics and Molecular Biology",
        "topic": "Scientific Writing and Publishing",
        "features": ["real article (editorial format)", "public domain (CC0)", "5 pages"],
        "expect": {"text": True, "first_page_contains": "e1003858"},
        "provenance": {
            "source_url": "https://doi.org/10.1371/journal.pcbi.1003858",
            "pdf_url": "https://journals.plos.org/ploscompbiol/article/file?id=10.1371/journal.pcbi.1003858&type=printable",
            "licence": "CC0 1.0 (public domain dedication)",
            "licence_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "attribution": "None required (CC0). Given as courtesy: Dashnow H, Lonsdale A, Bourne PE (2014) Ten Simple Rules for Writing a PLOS Ten Simple Rules Article. PLoS Comput Biol 10(10): e1003858. https://doi.org/10.1371/journal.pcbi.1003858.",
            "evidence": 'Article page (journals.plos.org, checked 2026-11-09): "... may be freely reproduced, distributed, transmitted, modified, built upon, or otherwise used by anyone for any lawful purpose. The work is made available under the Creative Commons CC0 public domain dedication."; the same statement is printed on page 1 of the PDF.',
        },
    },
]


def add_real(folder: Path) -> None:
    """The real documents from `folder`, each checked against its SHA-256 first."""
    for r in REAL:
        source = folder / r["file"]
        if not source.is_file() or ocr_pdf.fingerprint(source) != r["sha256"]:
            sys.exit(f"{source}: missing or not the expected file (SHA-256 {r['sha256']})")
        staged = STAGE / r["file"]
        shutil.copyfile(source, staged)
        doc(r["kind"], r["title"], r["author"], r["year"], staged, subject=r["subject"],
            field=r["field"], topic=r["topic"], features=r["features"], meta=r["meta"],
            expect=r["expect"], provenance=r["provenance"])  # fmt: skip


def optics_extras(c, n, y):
    if n == 1:
        y = equation(c, 70, y - 10)
        y = table(c, 70, y, [["Glass", "n_d", "V_d"], ["Crown (synthetic)", "1.517", "64.2"],
                             ["Flint (synthetic)", "1.620", "36.4"]], [160, 80, 80],
                  "Table 1.1 Two synthetic glasses")  # fmt: skip
    if n == 2:
        y = figure(c, 70, y, "Figure 2.1 A thin lens bringing parallel rays to a focus.")
    return y


def build() -> None:
    s = STAGE
    # 1. physics/optics book: native text, bookmarks, equations, table, figure, marks
    p = s / "optics.pdf"
    book_pdf(p, "A Primer of Geometrical Optics", "Ada Lumen", [
        ("Rays and Refraction", ["Snell's law", "Thin lenses"]),
        ("Imaging", ["Aperture stop", "Pupils"]),
        ("Aberrations", ["Spherical aberration", "Chromatic aberration"]),
    ], subject="optics", extras=optics_extras)  # fmt: skip
    add_marks(p)
    doc("book", "A Primer of Geometrical Optics", "Ada Lumen", "2024", p, subject="physics/optics",
        field="Physics and Astronomy", topic="Geometrical Optics (synthetic)",
        features=["native text", "bookmarks", "multi-chapter", "equations", "table", "figure",
                  "PDF annotations (highlight, sticky note)"],
        meta={"publisher": "Synthetic Press", "isbn": ""},
        expect={"text": True, "outline": 3, "first_page_contains": "Geometrical Optics",
                "annotations": 2})  # fmt: skip
    # duplicate fixture: the same bytes under another name (not in the catalog)
    DUPLICATE_OF.append(p)

    # 2. mathematics book: printed contents only, no bookmarks
    p = s / "linalg.pdf"
    book_pdf(p, "Notes on Linear Algebra", "Lina Vector", [
        ("Vectors", ["Linear combinations"]), ("Matrices", ["Eigenvalue problems"]),
        ("Determinants", ["Cofactor expansion"]), ("Inner Products", ["Orthogonality"]),
    ], subject="mathematics", bookmarks=False, contents=True)  # fmt: skip
    doc("book", "Notes on Linear Algebra", "Lina Vector", "2023", p, subject="mathematics",
        field="Mathematics", topic="Linear Algebra (synthetic)",
        features=["native text", "printed contents page, no bookmarks", "multi-chapter"],
        meta={"publisher": "Synthetic Press"},
        expect={"text": True, "outline": 0, "first_page_contains": "Linear Algebra"})  # fmt: skip

    # 3. computer science book: a landscape page and a rotated page
    def code_listing(c, n, y):
        if n == 2:
            c.setFont("Courier", 10)
            for line in ["def search(graph, start):", "    seen = {start}",
                         "    for node in graph[start]:", "        ...  # recursion"]:  # fmt: skip
                c.drawString(80, y, line)
                y -= 13
        return y

    p = s / "algorithms.pdf"
    book_pdf(p, "Algorithms by Example", "Theo Graph", [
        ("Sorting", ["Merge sort"]), ("Graph Search", ["Breadth-first search"]),
        ("Dynamic Programming", ["Memoisation"]),
    ], subject="computer science", extras=code_listing, landscape_page=True)  # fmt: skip
    rotate_page(p, 2)
    doc("book", "Algorithms by Example", "Theo Graph", "2022", p, subject="computer science",
        field="Computer Science", topic="Algorithms (synthetic)",
        features=["native text", "bookmarks", "code listing", "landscape page (last chapter)",
                  "page rotated by 90 degrees (page 3)"],
        meta={"publisher": "Synthetic Press"},
        expect={"text": True, "outline": 3, "rotated_pages": [3], "landscape_pages": [4],
                "first_page_contains": "Algorithms"})  # fmt: skip

    # 4. humanities book: Chinese and Unicode text
    p = s / "writing.pdf"
    chinese_book(p)
    doc("book", "A Short History of Writing", "Shuwen Li", "2021", p, subject="humanities",
        field="Arts and Humanities", topic="History of Writing (synthetic)",
        features=["Chinese text (STSong-Light, not embedded)", "Unicode accents and symbols",
                  "bookmarks"],
        meta={"publisher": "Synthetic Press"},
        expect={"text": True, "outline": 3, "first_page_contains": "History of Writing"})  # fmt: skip

    # 5. biology book: image-only scan
    source = s / "cell-source.pdf"
    book_pdf(source, "Cell Biology Field Guide", "Mira Cell", [
        ("Membranes", ["Lipid bilayer"]), ("Organelles", ["Mitochondria"]),
    ], subject="biology")  # fmt: skip
    p = s / "cell-scan.pdf"
    scan_of(source, p, "Cell Biology Field Guide", "Mira Cell")
    doc("book", "Cell Biology Field Guide", "Mira Cell", "2020", p, subject="biology",
        field="Biochemistry, Genetics and Molecular Biology", topic="Cell Biology (synthetic)",
        features=["image-only scan (no text layer)", "slightly skewed pages"],
        meta={"publisher": "Synthetic Press"}, expect={"text": False})  # fmt: skip

    # 6. medicine book: scan with a genuine OCR text layer (rapidocr via ocr_pdf.py)
    source = s / "anatomy-source.pdf"
    book_pdf(source, "Human Anatomy Review Sheets", "Otto Bone", [
        ("The Skeleton", ["Long bones"]), ("The Heart", ["Valves"]),
    ], subject="medicine")  # fmt: skip
    scanned = s / "anatomy-scan.pdf"
    scan_of(source, scanned, "Human Anatomy Review Sheets", "Otto Bone", skew=0)
    p = s / "anatomy-ocr.pdf"
    ocr_pdf.add_text_layer(scanned, p)
    doc("book", "Human Anatomy Review Sheets", "Otto Bone", "2019", p, subject="medicine",
        field="Medicine", topic="Anatomy (synthetic)",
        features=["scan with a genuine OCR text layer (rapidocr, invisible Helvetica text)"],
        meta={"publisher": "Synthetic Press"},
        expect={"text": True, "ocr": True, "first_page_contains": "Anatomy"})  # fmt: skip

    # 7. statistics book: mixed searchable and scanned pages
    source = s / "stats-source.pdf"
    book_pdf(source, "Statistics with Mixed Pages", "Stella Mean", [
        ("Means and Medians", ["The sample mean"]), ("Variance", ["Standard deviation"]),
        ("Regression", ["Least squares"]),
    ], subject="statistics")  # fmt: skip
    stats_scan = s / "stats-scan.pdf"
    scan_of(source, stats_scan, "Statistics with Mixed Pages", "Stella Mean")
    p = s / "stats-mixed.pdf"
    merge([(source, [0, 1]), (stats_scan, [2, 3])], p, "Statistics with Mixed Pages",
          "Stella Mean")  # fmt: skip
    doc("book", "Statistics with Mixed Pages", "Stella Mean", "2018", p, subject="mathematics",
        field="Mathematics", topic="Statistics (synthetic)",
        features=["mixed: pages 1-2 searchable, pages 3-4 image-only"],
        meta={"publisher": "Synthetic Press"},
        expect={"text": True, "image_only_pages": [3, 4]})  # fmt: skip

    # 8. incomplete metadata: no author or year in the PDF or the catalog
    p = s / "fieldnotes.pdf"
    c = new_canvas(p, "", "", "")
    para(c, "Field notes without metadata. " + LOREM, 70, H - 90, W - 140)
    c.showPage()
    c.save()
    doc("book", "Field Notes Without Metadata", "", "", p, subject="social sciences",
        field="Social Sciences", topic="Field Methods (synthetic)",
        features=["incomplete metadata: no author, no year, empty PDF Info"],
        expect={"text": True})  # fmt: skip

    # 9. an older PDF structure (PDF 1.3, written by hand)
    p = s / "legacy.pdf"
    legacy_pdf(p)
    doc("book", "A Legacy Document Structure", "Ola Format", "1999", p, subject="computer science",
        field="Computer Science", topic="Document Formats (synthetic)",
        features=["PDF 1.3 header", "classic xref table", "Type1 Helvetica, no embedded fonts"],
        expect={"text": True, "pdf_version": "1.3"})  # fmt: skip

    # 10. computer science paper: two columns
    abstract = "We study sparse graphs built only for testing. " + LOREM

    def chart(c, page, x, y, width):
        if page == 2:
            bar_chart(c, x, y - 10, [30, 55, 80, 45], "Figure 1. Synthetic search times.")

    p = s / "sparse.pdf"
    two_column_paper(p, "Sparse Graphs for Fast Search: A Synthetic Study", "Ana Node; Bo Edge",
                     abstract, ["1 Introduction", "2 Related Work", "3 Method", "4 Results"],
                     subject="computer science", journal="Journal of Synthetic Test Data",
                     doi="10.5555/mylibrary.test.cs.2024", extras=chart)  # fmt: skip
    doc("paper", "Sparse Graphs for Fast Search: A Synthetic Study", "Ana Node; Bo Edge", "2024",
        p, subject="computer science", field="Computer Science", topic="Graph Search (synthetic)",
        features=["two-column layout", "figure (bar chart)", "DOI in the 10.5555 test prefix"],
        meta={"journal": "Journal of Synthetic Test Data", "volume": "1", "issue": "1",
              "page_range": "1-2", "doi": "10.5555/mylibrary.test.cs.2024"},
        expect={"text": True, "first_page_contains": "Sparse Graphs"})  # fmt: skip

    # 11. physics paper: two columns, equations and a table
    def physics_extras(c, page, x, y, width):
        if page == 1:
            table(c, x, y - 10, [["Power", "f (m)"], ["10 W", "2.1"], ["20 W", "1.0"]],
                  [width / 2, width / 2], "Table 1. Synthetic thermal lens")  # fmt: skip
        else:
            equation(c, x - 10, y - 20)

    p = s / "thermal.pdf"
    two_column_paper(p, "Thermal Lensing in a Synthetic Laser Rod", "Ivo Photon; Rhea Wave",
                     "A synthetic laser rod forms a thermal lens. " + LOREM,
                     ["1 Introduction", "2 Model", "3 Measurements", "4 Discussion"],
                     subject="physics", journal="Synthetic Letters in Optics",
                     doi="10.5555/mylibrary.test.phys.2023", extras=physics_extras)  # fmt: skip
    doc("paper", "Thermal Lensing in a Synthetic Laser Rod", "Ivo Photon; Rhea Wave", "2023", p,
        subject="physics/optics", field="Physics and Astronomy", topic="Laser Physics (synthetic)",
        features=["two-column layout", "equations", "table"],
        meta={"journal": "Synthetic Letters in Optics", "volume": "7", "issue": "3",
              "page_range": "11-12", "doi": "10.5555/mylibrary.test.phys.2023"},
        expect={"text": True})  # fmt: skip

    # 12. medicine paper, AES-256 encrypted with an empty user password (as publishers do)
    plain = s / "sleep-plain.pdf"
    two_column_paper(plain, "A Synthetic Cohort Study of Sleep and Memory", "Nia Pulse",
                     "A synthetic cohort is described. " + LOREM,
                     ["1 Background", "2 Methods", "3 Results", "4 Conclusion"],
                     subject="medicine", journal="Synthetic Medical Reports",
                     doi="10.5555/mylibrary.test.med.2022")  # fmt: skip
    p = s / "sleep.pdf"
    encrypt(plain, p, user_password="")
    doc("paper", "A Synthetic Cohort Study of Sleep and Memory", "Nia Pulse", "2022", p,
        subject="biology/medicine", field="Medicine", topic="Sleep Research (synthetic)",
        features=["AES-256 encrypted, empty user password (opens without one)"],
        meta={"journal": "Synthetic Medical Reports", "doi": "10.5555/mylibrary.test.med.2022"},
        expect={"text": True, "encrypted": True})  # fmt: skip

    # 13. near-duplicate of 10: the preprint (no DOI, another year, slightly other title)
    p = s / "sparse-preprint.pdf"
    two_column_paper(p, "Sparse Graphs for Fast Search: A Synthetic Study (Preprint)",
                     "Ana Node; Bo Edge", abstract,
                     ["1 Introduction", "2 Related Work", "3 Method", "4 Results"],
                     subject="computer science", journal="Synthetic preprint server",
                     doi="none", extras=chart)  # fmt: skip
    doc("paper", "Sparse Graphs for Fast Search: A Synthetic Study (Preprint)",
        "Ana Node; Bo Edge", "2023", p, subject="computer science", field="Computer Science",
        topic="Graph Search (synthetic)",
        features=["near-duplicate of the 2024 paper: preprint, no DOI; kept as its own item"],
        expect={"text": True})  # fmt: skip

    # 14. social sciences paper, one column with a table
    p = s / "survey.pdf"
    c = new_canvas(p, "Reading Habits of Students: A Synthetic Survey", "Sam Survey",
                   "social sciences")  # fmt: skip
    y = heading(c, "Reading Habits of Students: A Synthetic Survey", 70, H - 80, 15)
    c.setFont("Helvetica", 11)
    c.drawString(70, y, "Sam Survey · Synthetic Journal of Social Research")
    y = para(c, "Abstract. " + LOREM, 70, y - 24, W - 140)
    y = table(c, 70, y, [["Group", "Books per year", "Share"], ["A", "12", "40 %"],
                         ["B", "5", "35 %"], ["C", "1", "25 %"]], [120, 120, 100],
              "Table 1. Synthetic survey answers")  # fmt: skip
    para(c, LOREM, 70, y, W - 140)
    c.showPage()
    c.save()
    doc("paper", "Reading Habits of Students: A Synthetic Survey", "Sam Survey", "2021", p,
        subject="social sciences", field="Social Sciences", topic="Reading Research (synthetic)",
        features=["one-column", "table"],
        meta={"journal": "Synthetic Journal of Social Research",
              "doi": "10.5555/mylibrary.test.soc.2021"},
        expect={"text": True})  # fmt: skip

    # 15. computer science PhD thesis: contents, references, appendix
    p = s / "thesis-phd.pdf"
    thesis_pdf(p, chinese=False)
    doc("thesis", "Learning Shortest Paths on Synthetic Graphs", "Elena Proof", "2020", p,
        subject="computer science/mathematics", field="Computer Science",
        topic="Graph Learning (synthetic)",
        features=["thesis title page", "contents page", "bookmarks", "references", "appendix",
                  "table"],
        meta={"degree": "PhD", "institution": "University of Testing",
              "supervisors": "Prof. Ada Lumen; Dr. Theo Graph"},
        expect={"text": True, "outline": 7})  # fmt: skip

    # 16. humanities Master thesis with a Chinese title page
    p = s / "thesis-ma.pdf"
    thesis_pdf(p, chinese=True)
    doc("thesis", "Urban Memory and Oral History", "Mei Zhang", "2021", p, subject="humanities",
        field="Arts and Humanities", topic="Oral History (synthetic)",
        features=["Chinese title page (硕士学位论文)", "contents", "references", "appendix"],
        meta={"degree": "Master", "institution": "University of Testing",
              "supervisors": "Prof. Lin Archive"},
        expect={"text": True, "outline": 7})  # fmt: skip


DUPLICATE_OF: list[Path] = []


def negative_fixtures(out: Path, paper: Path, book: Path) -> list[dict]:
    """fixtures/: files that must never open as normal documents (not in the catalog)."""
    folder = out / "fixtures"
    folder.mkdir()
    found = []
    encrypt(paper, folder / "encrypted-with-password.pdf", user_password="test")
    found.append({"file": "fixtures/encrypted-with-password.pdf",
                  "features": ["AES-256, user password 'test'"],
                  "expect": {"opens_without_password": False, "password": "test"}})  # fmt: skip
    data = book.read_bytes()
    (folder / "truncated.pdf").write_bytes(data[: len(data) * 3 // 5])
    found.append({"file": "fixtures/truncated.pdf", "features": ["cut off at 60 %: no xref, no %%EOF"],
                  "expect": {"valid": False}})  # fmt: skip
    (folder / "not-a-pdf.pdf").write_bytes(
        b"<!doctype html><html><body>A web page saved as .pdf</body></html>\n"
    )
    found.append({"file": "fixtures/not-a-pdf.pdf", "features": ["HTML with a .pdf name"],
                  "expect": {"valid": False}})  # fmt: skip
    return found


def study_data(ids: dict[str, str]) -> None:
    """Synthetic study data written by the app's own functions or in their formats."""
    optics, paper, phd = ids["optics"], ids["sparse"], ids["thesis-phd"]
    library_server.tick(optics, 1, True)
    library_server.tick(phd, 1, True)
    library_server.save_position(optics, 4)
    library_server.save_position(paper, 2)
    rows = catalog.load(LIB / "catalog.csv")
    notes = LIB / rows[optics]["notes"]
    first = sorted(notes.glob("ch01-*.md"))[0]
    safe_io.update_text(first, lambda t: t.rstrip("\n") + (
        "\n\nMy own words (synthetic test note): the thin-lens equation (1.1) relates the "
        "object and image distances; Snell's law (1.2) explains the bending of rays.\n"
    ))  # fmt: skip
    paper_notes = LIB / rows[paper]["notes"] / "notes.md"
    safe_io.update_text(paper_notes, lambda t: t.rstrip("\n") + (
        "\n\nSynthetic test note: the method keeps graphs sparse; Figure 1 compares search "
        "times.\n"
    ))  # fmt: skip
    vocabulary = (
        reader.VOCAB_HEADER.format(title=rows[optics]["title"])
        + "| aperture |  | 孔径 | 3 | 2026-11-01 |\n| convergence |  | 会聚 | 3 | 2026-11-01 |\n"
    )
    safe_io.write_text(LIB / rows[optics]["notes"] / "vocabulary.md", vocabulary)
    topic = library_server.topic_note("aperture")
    safe_io.update_text(topic, lambda t: t.rstrip("\n") + (
        "\n\nSynthetic topic note: an aperture limits the bundle of rays (my own words).\n"
    ))  # fmt: skip
    reading_log.record(LIB, optics, 900, [1, 2, 3, 4], today=date(2026, 11, 1))
    reading_log.record(LIB, paper, 300, [1, 2], today=date(2026, 11, 2))
    vocab_review.answer(LIB, "aperture", True, today=date(2026, 11, 3))
    glossaries = LIB / "glossaries"
    safe_io.write_text(glossaries / "physics.csv", (
        "term,zh,note,definition\n"
        "aperture stop,孔径光阑,,限制进入光学系统的光束大小的光阑（测试用示例）。\n"
        "thermal lens,热透镜,,由温度梯度引起的折射率变化形成的透镜效应（测试用示例）。\n"
    ))  # fmt: skip
    safe_io.write_text(glossaries / "glossaries.toml", (
        "# Glossaries of the Test & Demo library (synthetic examples)\n"
        'default = "physics"\n\n[physics]\nlabel = "物理 Physics"\n'
    ))  # fmt: skip


LIBRARY_TOML = f"""# The Test & Demo library: synthetic and openly licensed documents only (README.md).
# test_library/ is the canonical copy in git; Test & Demo mode opens a working copy of it.
name = "Test & Demo library"
id = "{LIBRARY_ID}"
test_library = true

[shelves]
"Physics and Astronomy" = "物理与天文 Physics and Astronomy"
"Mathematics" = "数学 Mathematics"
"Computer Science" = "计算机科学 Computer Science"
"Medicine" = "医学 Medicine"
"Arts and Humanities" = "人文 Arts and Humanities"
"Social Sciences" = "社会科学 Social Sciences"
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--real-from", required=True, type=Path, metavar="FOLDER",
                        help="the real documents (REAL), downloaded from their pdf_url")  # fmt: skip
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        sys.exit(f"{out} exists: move it away first (it's in git, so nothing is lost)")
    paths.ensure_library()
    safe_io.write_text(LIB / "library.toml", LIBRARY_TOML)
    build()
    add_real(args.real_from.resolve())
    ids, manifest = {}, {"library_id": LIBRARY_ID, "generator": "tests/make_test_library.py",
                         "documents": [], "fixtures": []}  # fmt: skip
    for d in DOCS:
        book = add_book.Book(d["title"], d["author"], d["year"], d["meta"].get("publisher", ""))
        meta = Meta(kind=d["kind"], title=d["title"], author=d["author"], year=d["year"],
                    sources={"title": "test corpus", "author": "test corpus"})  # fmt: skip
        for key, value in d["meta"].items():
            setattr(meta, key, value)
        if d["pdf"].stem not in FIXED_IDS:
            sys.exit(f"{d['pdf'].stem}: give it a fixed id in FIXED_IDS first")
        catalog.new_id = lambda stem=d["pdf"].stem: FIXED_IDS[stem]  # (its catalog.add)
        before = set(catalog.load(LIB / "catalog.csv"))
        add_book.add_book(d["pdf"], book, dry_run=False, meta=meta, online=False)
        (doc_id,) = set(catalog.load(LIB / "catalog.csv")) - before
        ids[d["pdf"].stem] = doc_id
        catalog.set_fields(LIB / "catalog.csv", doc_id, {
            "field": d["field"], "topic": d["topic"], "topic_score": "0.9",
            "shelves": d["field"], "subjects": d["subject"],
        })  # fmt: skip
        d["id"] = doc_id
    study_data(ids)
    shutil.copytree(LIB, out, ignore=shutil.ignore_patterns(".cache", "archive", ".myLibrary",
                                                            "library.html", "*.bak"))  # fmt: skip
    rows = catalog.load(out / "catalog.csv")
    for d in DOCS:
        row = rows[d["id"]]
        pdf = out / row["file"]
        origin = d["provenance"] or {"licence": "synthetic, made for this project (see README)"}
        manifest["documents"].append({
            "id": d["id"], "file": row["file"], "type": row["type"], "title": d["title"],
            "subject": d["subject"], "source": "real" if d["provenance"] else "synthetic",
            **origin,
            "sha256": ocr_pdf.fingerprint(pdf), "bytes": pdf.stat().st_size,
            "pages": len(PdfReader(pdf).pages), "features": d["features"],
            "expect": d["expect"],
        })  # fmt: skip
    if DUPLICATE_OF:
        target = rows[DOCS[0]["id"]]["file"]
        dup = out / "fixtures"
        by_stem = {d["pdf"].stem: out / rows[d["id"]]["file"] for d in DOCS}
        fixtures = negative_fixtures(out, by_stem["sparse"], by_stem["linalg"])
        shutil.copyfile(out / target, dup / "Downloaded copy (1).pdf")
        fixtures.append({"file": "fixtures/Downloaded copy (1).pdf",
                         "features": [f"byte-identical copy of {target}"],
                         "expect": {"repeat_of": DOCS[0]["id"]}})  # fmt: skip
        for f in fixtures:
            path = out / f["file"]
            f |= {"sha256": ocr_pdf.fingerprint(path), "bytes": path.stat().st_size,
                  "source": "synthetic", "licence": "synthetic, made for this project (see README)"}  # fmt: skip
        manifest["fixtures"] = fixtures
    (out / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    total = sum(p.stat().st_size for p in out.rglob("*.pdf"))
    print(f"{out}: {len(manifest['documents'])} documents, {len(manifest['fixtures'])} fixtures, "
          f"{total / 1e6:.1f} MB of PDFs")  # fmt: skip
    shutil.rmtree(WORK, ignore_errors=True)


if __name__ == "__main__":
    main()
