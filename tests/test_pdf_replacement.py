"""D15: a library PDF replaced by a rebuilt copy (OCR's text layer, new bookmarks, a better
copy of a repeat) never takes away marks saved meanwhile. OCR works on a snapshot taken under
the PDF's lock and records its content (SHA-256); the replacement happens only under that
lock, and only if the PDF is still exactly that content. Otherwise nothing is replaced and the
job says why. Saving marks is never held up by a running OCR. Temporary libraries, invented
PDFs, a stand-in OCR engine paused and released with events (no sleeps)."""

import io
import threading
from pathlib import Path

import add_book
import add_bookmarks
import catalog
import library_jobs
import ocr_pdf
import pytest
import reader
from book_meta import Meta
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Highlight
from pypdf.generic import ArrayObject, FloatObject
from reportlab.pdfgen import canvas
from testlib import put

NAME = "doe-2015-scan"
FILE = f"books/{NAME}.pdf"
WAIT = 30  # s: the most any step here may take (a failure, not a timing)


def scan(pages: int = 2) -> bytes:
    """Pages without text, like a scan."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(300, 400)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def searchable(pages: int = 2) -> bytes:
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=(300, 400))
    for n in range(pages):
        c.drawString(20, 300, f"Invented searchable text on page {n + 1} " * 3)
        c.showPage()
    c.save()
    return out.getvalue()


def marked(data: bytes) -> bytes:
    """`data` with a highlight, as the reading view's saveDocument sends it."""
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(data)))
    quad = ArrayObject([FloatObject(v) for v in (10, 30, 100, 30, 10, 10, 100, 10)])
    writer.add_annotation(
        page_number=0, annotation=Highlight(rect=(10, 10, 100, 30), quad_points=quad)
    )
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def highlights(pdf: Path) -> int:
    return sum(len(page.get("/Annots") or []) for page in PdfReader(pdf).pages)


class StandInOcr:
    """ocr_boxes without an OCR engine: one word per page. With `paused`, page 0 waits (after
    saying so in `inside`) until the test sets `release`."""

    def __init__(self):
        self.inside, self.release = threading.Event(), threading.Event()
        self.release.set()
        self.fail = False
        self.pages_read = []

    def pause(self):
        self.release.clear()
        return self

    def __call__(self, src, page, document=None):
        self.pages_read.append(page)
        if page == 0:
            self.inside.set()
            assert self.release.wait(WAIT), "never released"
        if self.fail:
            raise RuntimeError("the OCR engine failed")
        return [[40, 80, 200, 100, "Recognised"]]


@pytest.fixture
def lib(tmp_path, monkeypatch):
    """A library with one scanned book; every module pointed at it; a stand-in OCR."""
    for name in ("BOOKS", "PAPERS", "THESES", "EXAMPLES", "NOTES"):
        monkeypatch.setattr(add_book, name, tmp_path / name.lower())
    monkeypatch.setattr(add_book, "CATALOG", tmp_path / "catalog.csv")
    monkeypatch.setattr(add_book, "ARCHIVE", tmp_path / "archive")
    monkeypatch.setattr(add_book, "LIBRARY", tmp_path)
    monkeypatch.setattr(add_book, "PAGE_CACHE", tmp_path / ".cache" / "chapter_pages.json")
    monkeypatch.setattr(reader, "LIBRARY", tmp_path)
    for module in (ocr_pdf, add_bookmarks):
        monkeypatch.setattr(module, "LIBRARY", tmp_path)
        monkeypatch.setattr(module, "ARCHIVE_BOOKS", tmp_path / "archive" / "books")
    monkeypatch.setattr(ocr_pdf, "OUTPUT_DIR", tmp_path / ".cache" / "ocr-output")
    monkeypatch.setattr(add_bookmarks, "OUTPUT_DIR", tmp_path / ".cache" / "bookmarks-output")
    monkeypatch.setattr(library_jobs.library_page, "build", lambda: None)
    monkeypatch.setattr(library_jobs.book_search, "update", lambda: 0)
    monkeypatch.setattr(library_jobs, "_jobs", {})
    refreshed = []
    monkeypatch.setattr(add_book, "refresh_chapters", lambda pdf, dry_run: refreshed.append(pdf))
    ocr = StandInOcr()
    monkeypatch.setattr(ocr_pdf, "ocr_boxes", ocr)
    (tmp_path / "books").mkdir()
    (tmp_path / FILE).write_bytes(scan())
    doc = put(tmp_path / "catalog.csv", {"slug": NAME, "title": "Scan", "type": "book",
                                         "file": FILE, "doi": "10.1/scan"})  # fmt: skip
    return {"root": tmp_path, "pdf": tmp_path / FILE, "doc": doc, "ocr": ocr,
            "refreshed": refreshed}  # fmt: skip


def loaded(lib) -> str:
    """The version of the PDF a tab would have loaded now (D5: every save names it)."""
    return reader._version(lib["pdf"])


def in_thread(work) -> tuple[threading.Thread, dict]:
    """Run `work` in a thread; its result or exception lands in the dict."""
    outcome = {}

    def run():
        try:
            outcome["result"] = work()
        except BaseException as e:  # (also SystemExit: what ocr_pdf raises for a locked file)
            outcome["error"] = e

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, outcome


def leftovers(lib) -> list[str]:
    """Temporary files OCR or bookmarks left behind."""
    cache = lib["root"] / ".cache"
    folders = [cache / "ocr-output", cache / "bookmarks-output"]
    return [p.name for f in folders if f.exists() for p in f.rglob("*") if p.is_file()]


def archived_books(lib) -> list[str]:
    folder = lib["root"] / "archive" / "books"
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


def wait_job(job: dict) -> dict:
    for _ in range(WAIT * 50):
        (current,) = [j for j in library_jobs.list_jobs() if j["id"] == job["id"]]
        if current["status"] != "working":
            return current
        threading.Event().wait(0.02)  # polling a job's state (not timing the race)
    raise AssertionError("the job didn't finish")


# --- the race: marks saved while OCR runs ------------------------------------------------------


def test_marks_saved_while_ocr_runs_are_kept(lib):
    """OCR starts from the PDF as it is; the user saves marks; OCR finishes: its result (built
    without the marks) is refused, and the PDF with the marks stays."""
    pdf, ocr = lib["pdf"], lib["ocr"].pause()
    original = pdf.read_bytes()
    running, ocr_outcome = in_thread(lambda: ocr_pdf.make_searchable(pdf))
    assert ocr.inside.wait(WAIT)  # OCR is reading page 1 of its snapshot
    mine = marked(original)
    saving, saved = in_thread(lambda: reader.save_marks(FILE, mine, base=loaded(lib)))
    saving.join(WAIT)  # never held up by the OCR
    assert not saving.is_alive() and saved["result"]["saved"] is True
    ocr.release.set()
    running.join(WAIT)
    assert not running.is_alive()
    assert isinstance(ocr_outcome.get("error"), ocr_pdf.PdfChanged), ocr_outcome
    assert pdf.read_bytes() == mine and highlights(pdf) == 1  # the marks, untouched
    assert archived_books(lib) == [] and leftovers(lib) == []
    # The original scan is still kept once, by the marks themselves
    assert (lib["root"] / "archive" / "before-marks" / FILE).read_bytes() == original


def test_marks_saved_while_ocr_writes_its_result_are_kept(lib, monkeypatch):
    """The window in which the old code lost marks silently on Windows: every page is read and
    the OCR engine has let go of the file, but the result isn't written yet. A save succeeds
    there; the result must then not replace the PDF."""
    pdf = lib["pdf"]
    writing, go_on = threading.Event(), threading.Event()

    class SlowWriter(PdfWriter):
        def write(self, stream):
            writing.set()
            assert go_on.wait(WAIT)
            return super().write(stream)

    monkeypatch.setattr(ocr_pdf, "PdfWriter", SlowWriter)
    running, ocr_outcome = in_thread(lambda: ocr_pdf.make_searchable(pdf))
    assert writing.wait(WAIT)
    mine = marked(pdf.read_bytes())
    assert reader.save_marks(FILE, mine, base=loaded(lib))["saved"] is True
    go_on.set()
    running.join(WAIT)
    assert isinstance(ocr_outcome.get("error"), ocr_pdf.PdfChanged), ocr_outcome
    assert pdf.read_bytes() == mine and highlights(pdf) == 1
    assert archived_books(lib) == [] and leftovers(lib) == []


def test_the_ocr_job_reports_the_change_instead_of_success(lib):
    ocr = lib["ocr"].pause()
    job = library_jobs.start_ocr(lib["doc"])
    assert ocr.inside.wait(WAIT)
    mine = marked(lib["pdf"].read_bytes())
    reader.save_marks(FILE, mine, base=loaded(lib))
    ocr.release.set()
    finished = wait_job(job)
    assert finished["status"] == "error", finished
    assert "changed while OCR was running" in finished["message"]
    assert "marks" in finished["message"] and "OCR finished" not in finished["message"]
    assert lib["pdf"].read_bytes() == mine and lib["refreshed"] == []
    assert archived_books(lib) == [] and leftovers(lib) == []


def test_ocr_of_an_unchanged_pdf_replaces_it(lib):
    pdf = lib["pdf"]
    original = pdf.read_bytes()
    finished = wait_job(library_jobs.start_ocr(lib["doc"]))
    assert finished["status"] == "done", finished
    assert "Recognised" in PdfReader(pdf).pages[0].extract_text()
    assert archived_books(lib) == [pdf.name]
    assert (lib["root"] / "archive" / "books" / pdf.name).read_bytes() == original
    assert lib["refreshed"] == [pdf] and leftovers(lib) == []


def test_a_marks_save_and_a_replacement_never_interleave(lib, monkeypatch):
    """A replacement arriving while marks are being written waits for them, then sees that the
    PDF changed, and replaces nothing."""
    pdf = lib["pdf"]
    original = pdf.read_bytes()
    source = ocr_pdf.fingerprint(pdf)
    rebuilt = lib["root"] / ".cache" / "ocr-output" / pdf.name
    rebuilt.parent.mkdir(parents=True)
    rebuilt.write_bytes(searchable())
    writing, go_on = threading.Event(), threading.Event()
    write_bytes = reader.safe_io.write_bytes

    def slow_write(path, data, **kw):
        if Path(path) == pdf:
            writing.set()
            assert go_on.wait(WAIT)
        return write_bytes(path, data, **kw)

    monkeypatch.setattr(reader.safe_io, "write_bytes", slow_write)
    mine = marked(original)
    saving, saved = in_thread(lambda: reader.save_marks(FILE, mine, base=loaded(lib)))
    assert writing.wait(WAIT)  # marks are being written, under the PDF's lock
    keep = lib["root"] / "archive" / "books" / pdf.name
    replacing, replaced = in_thread(lambda: ocr_pdf.replace_pdf(pdf, rebuilt, keep, source=source))
    go_on.set()
    saving.join(WAIT)
    replacing.join(WAIT)
    assert saved.get("result", {}).get("saved") is True, saved
    assert isinstance(replaced.get("error"), ocr_pdf.PdfChanged), replaced
    assert pdf.read_bytes() == mine and not keep.exists()


def test_a_failed_replacement_puts_the_pdf_back(lib):
    """The existing rollback: the new file can't be put in place, so the PDF moves back."""
    pdf = lib["pdf"]
    original = pdf.read_bytes()
    keep = lib["root"] / "archive" / "books" / pdf.name
    missing = lib["root"] / ".cache" / "ocr-output" / "gone.pdf"
    with pytest.raises(FileNotFoundError):
        ocr_pdf.replace_pdf(pdf, missing, keep, source=ocr_pdf.fingerprint(pdf))
    assert pdf.read_bytes() == original and not keep.exists()


def test_an_ocr_failure_leaves_the_pdf_unchanged(lib):
    lib["ocr"].fail = True
    original = lib["pdf"].read_bytes()
    finished = wait_job(library_jobs.start_ocr(lib["doc"]))
    assert finished["status"] == "error" and "OCR engine failed" in finished["message"]
    assert lib["pdf"].read_bytes() == original
    assert archived_books(lib) == [] and leftovers(lib) == [] and lib["refreshed"] == []


def test_quitting_during_ocr_replaces_nothing(lib):
    ocr = lib["ocr"].pause()
    original = lib["pdf"].read_bytes()
    job = library_jobs.start_ocr(lib["doc"])
    assert ocr.inside.wait(WAIT)
    quitting, _ = in_thread(lambda: library_jobs.shutdown(timeout=WAIT))
    try:
        assert library_jobs._stopping.wait(WAIT)  # Quit has begun
        ocr.release.set()  # page 1 ends: OCR stops there
        quitting.join(WAIT)
        finished = wait_job(job)
    finally:
        library_jobs.reopen()
    assert finished["status"] == "error" and "stopped" in finished["message"]
    assert lib["pdf"].read_bytes() == original
    assert archived_books(lib) == [] and leftovers(lib) == []


# --- the other writers that replace a library PDF ---------------------------------------------


def test_new_bookmarks_never_replace_a_pdf_marked_meanwhile(lib, monkeypatch):
    """add_bookmarks rebuilds the PDF the same way (a copy with bookmarks, then replace_pdf)."""
    pdf = lib["pdf"]
    mine = marked(pdf.read_bytes())

    class MarksMeanwhile(PdfWriter):
        def write(self, stream):  # the copy is being written when marks are saved
            reader.save_marks(FILE, mine, base=loaded(lib))
            return super().write(stream)

    monkeypatch.setattr(add_bookmarks, "PdfWriter", MarksMeanwhile)
    with pytest.raises(ocr_pdf.PdfChanged):
        add_bookmarks.write_bookmarks(pdf, [add_bookmarks.Mark("1  Basics", 0)])
    assert pdf.read_bytes() == mine and archived_books(lib) == [] and leftovers(lib) == []


def test_a_better_copy_never_replaces_a_pdf_marked_meanwhile(lib, monkeypatch):
    """A searchable copy of the scanned book (same DOI) would replace its PDF, but the marks
    are saved between the check for marks and the replacement: the PDF stays, with them; the
    copy goes to the archive."""
    pdf = lib["pdf"]
    upload = lib["root"] / "books" / "upload.pdf"
    upload.write_bytes(searchable())
    mine = marked(pdf.read_bytes())
    has_marks = add_book.has_marks
    checks = []

    def marks_arrive_after_the_first_check(path):
        checks.append(path)
        answer = has_marks(path)
        if len(checks) == 1:
            reader.save_marks(FILE, mine, base=loaded(lib))  # just after handle_repeat looked
        return answer

    monkeypatch.setattr(add_book, "has_marks", marks_arrive_after_the_first_check)
    meta = Meta(title="Scan", doi="10.1/scan", pages="2")
    replaced, message = add_book.handle_repeat(upload, meta, lib["doc"], reason="same DOI")
    assert replaced is False and "marks" in message, message
    assert pdf.read_bytes() == mine and highlights(pdf) == 1
    assert not upload.exists() and archived_books(lib) == ["upload.pdf"]
    assert catalog.load(lib["root"] / "catalog.csv")[lib["doc"]]["file"] == FILE
