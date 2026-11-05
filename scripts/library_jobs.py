"""Background jobs started from the library page: adding uploaded books, and OCR for scans.

The page polls list_jobs() to show progress; nothing here needs a terminal. The same steps as
`uv run scripts/add_book.py` and `uv run scripts/ocr_pdf.py`, without the questions.
"""

import re
import threading
import time
import uuid
from pathlib import Path

import add_book
import book_search
import catalog
import library_page
import ocr_pdf
from book_meta import identify
from pypdf import PdfReader

MAX_UPLOAD = 1_000_000_000  # 1 GB: bigger than any book, smaller than a mistake
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def _new_job(kind: str, **fields) -> dict:
    job = {"id": uuid.uuid4().hex[:12], "kind": kind, "status": "working", "started": time.time()}
    job |= fields
    with _lock:
        _jobs[job["id"]] = job
    return job


def _update(job: dict, **fields) -> None:
    with _lock:
        job.update(fields)


def list_jobs() -> list[dict]:
    """Jobs still running, waiting for details, or finished in the last 10 minutes."""
    now = time.time()
    with _lock:
        return [
            dict(j)
            for j in _jobs.values()
            if j["status"] in ("working", "needs_details") or now - j.get("ended", now) < 600
        ]


def _finish(job: dict, status: str, message: str, **fields) -> None:
    _update(job, status=status, message=message, ended=time.time(), **fields)


def _in_background(target, *args) -> None:
    threading.Thread(target=target, args=args, daemon=True).start()


# --- adding books -------------------------------------------------------------------------------


def save_upload(name: str, data: bytes) -> Path:
    """Write an uploaded PDF into the library's books/ under a safe, unused name."""
    if not data.startswith(b"%PDF"):
        raise ValueError(f"{name} is not a PDF")
    stem = re.sub(r"[^\w\s().,'-]+", "_", Path(name).stem).strip(" ._") or "book"
    add_book.BOOKS.mkdir(parents=True, exist_ok=True)
    target = add_book.BOOKS / f"{stem[:120]}.pdf"
    n = 2
    while target.exists():
        target = add_book.BOOKS / f"{stem[:120]} ({n}).pdf"
        n += 1
    target.write_bytes(data)
    return target


def start_add(path: Path) -> dict:
    """Identify, name and register an uploaded book (in the background)."""
    job = _new_job("add", file=path.name, path=str(path), message="Identifying the book…")
    _in_background(_add, job, path, {})
    return job


def continue_add(job_id: str, details: dict) -> dict:
    """The page filled in what couldn't be found (title / author / year): register now."""
    with _lock:
        job = _jobs.get(job_id)
    if not job or job["status"] != "needs_details":
        raise ValueError("no book is waiting for details")
    _update(job, status="working", message="Registering the book…")
    _in_background(_add, job, Path(job["path"]), details)
    return job


def _add(job: dict, path: Path, details: dict) -> None:
    try:
        meta = identify(path, online=True)
        book = add_book.Book(
            (details.get("title") or meta.title or "").strip(),
            (details.get("author") or meta.author or "").strip(),
            (details.get("year") or meta.year or "").strip(),
            meta.publisher,
        )
        missing = [k for k in ("title", "author", "year") if not getattr(book, k)]
        if missing:
            guess = {"title": book.title, "author": book.author, "year": book.year}
            _update(job, status="needs_details", missing=missing, guess=guess,
                    message="Please fill in what couldn't be found")  # fmt: skip
            return
        folder = add_book.PAPERS if meta.kind == "paper" else add_book.BOOKS
        target = folder / f"{book.slug}.pdf"
        existing = [add_book.BOOKS / target.name, add_book.PAPERS / target.name]
        if any(f.exists() and f != path for f in existing):
            path.unlink()  # an uploaded copy of a book that's already in the library
            _finish(job, "duplicate", f"“{book.title}” is already in the library", slug=book.slug)
            return
        add_book.add_book(path, book, dry_run=False, meta=meta)
        scan = ocr_pdf.needs_ocr(target)
        pages = len(PdfReader(target).pages)
        library_page.build()
        _in_background(book_search.update)  # make it searchable (在我的书中 / In my books)
        _finish(
            job,
            "done",
            f"Added the {'paper' if meta.kind == 'paper' else 'book'} “{book.title}”"
            + (" (a scan: OCR recommended)" if scan else ""),
            slug=book.slug,
            title=book.title,
            scan=scan,
            minutes=round(ocr_pdf.ocr_minutes(pages)) if scan else 0,
        )
    except Exception as e:  # shown on the page; the uploaded file stays in books/
        _finish(job, "error", f"Couldn't add {path.name}: {e}")


# --- OCR --------------------------------------------------------------------------------------


def start_ocr(slug: str) -> dict:
    """Give a scanned book an invisible text layer (in the background, one book at a time)."""
    row = catalog.load(add_book.CATALOG).get(slug) or {}
    pdf = add_book.LIBRARY / row["file"] if row.get("file") else add_book.BOOKS / f"{slug}.pdf"
    if not pdf.exists():
        raise ValueError("that book's PDF isn't in the library")
    if any(j["kind"] == "ocr" and j["status"] == "working" for j in list_jobs()):
        raise ValueError("another book is being OCR'd; try again when it's done")
    job = _new_job("ocr", slug=slug, done=0, total=0, message="Starting OCR…")
    _in_background(_ocr, job, pdf)
    return job


def _ocr(job: dict, pdf: Path) -> None:
    def progress(done: int, total: int) -> None:
        _update(job, done=done, total=total, message=f"OCR page {done} of {total}")

    try:
        ocr_pdf.make_searchable(pdf, progress)
        add_book.forget_chapter_pages(pdf.stem)  # chapter pages are found again from the text
        add_book.refresh_chapters(pdf, dry_run=False)
        book_search.update()
        library_page.build()
        _finish(job, "done", "OCR finished: the book can now be searched and looked up")
    except Exception as e:
        _finish(job, "error", f"OCR failed: {e}")
