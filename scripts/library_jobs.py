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
import shelves
import subjects
from book_meta import identify

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


HISTORY = 50  # finished jobs kept for the page's History (since the server started)


def _active(job: dict) -> bool:
    return job["status"] == "working"


def list_jobs() -> list[dict]:
    """Jobs still running, then the finished ones of this session, newest first (at most
    HISTORY; older ones are forgotten)."""
    with _lock:
        finished = sorted((j for j in _jobs.values() if not _active(j)),
                          key=lambda j: j.get("ended", 0), reverse=True)  # fmt: skip
        for old in finished[HISTORY:]:
            del _jobs[old["id"]]
        return [dict(j) for j in _jobs.values() if _active(j)] + [
            dict(j) for j in finished[:HISTORY]
        ]


def clear_history() -> None:
    """Forget the finished jobs ("Clear" in the page's History); running ones go on."""
    with _lock:
        for job_id in [i for i, j in _jobs.items() if not _active(j)]:
            del _jobs[job_id]


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
    _in_background(_add, job, path)
    return job


def start_download(url: str, title: str = "") -> dict:
    """Download a free (open-access) PDF found with "Find online", then add it like an upload."""
    if not re.match(r"https?://", url):
        raise ValueError("not a web address")
    name = (title or "download")[:100]
    job = _new_job("add", file=name, message="Downloading…")
    _in_background(_download, job, url, name)
    return job


def _download(job: dict, url: str, name: str) -> None:
    import urllib.request

    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (myLibrary)", "Accept": "application/pdf,*/*"}
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD:
            raise ValueError("the file is too big")
        if not data.startswith(b"%PDF"):  # many "free" links lead to a web page first
            raise ValueError(
                "the link gave a web page, not a PDF. Open it, download the PDF there and "
                "drag it onto this page"
            )
        path = save_upload(f"{name}.pdf", data)
    except Exception as e:
        _finish(job, "error", f"Couldn't download it: {e}")
        return
    _update(job, path=str(path), message="Identifying…")
    _add(job, path)


def refresh() -> dict:
    """ "⟳ Refresh": what `uv run scripts/add_book.py` does, for PDFs put into books/, papers/ or
    theses/ by hand. New files are identified, named and registered; files already named
    (renamed by hand) get their notes and catalog row. One after another in the background
    (they all write catalog.csv), each with its own line in the jobs panel."""
    with _lock:  # files a job is already working on (e.g. Refresh clicked twice)
        busy = {j.get("path") for j in _jobs.values() if _active(j)}
    new = [p for p in add_book.library_pdfs()
           if not add_book.SLUG_RE.match(p.stem) and str(p) not in busy]  # fmt: skip
    named = [p for p in add_book.unregistered_named_books() if str(p) not in busy]
    steps = [
        (_add, _new_job("add", file=p.name, path=str(p), message="Waiting…"), p) for p in new
    ] + [
        (_register, _new_job("add", file=p.name, path=str(p), message="Waiting…"), p) for p in named
    ]
    # Items with no subject yet (added before subjects existed, or offline): look them up
    todo = subjects.unclassified(add_book.LIBRARY, add_book.CATALOG)
    if todo:
        job = _new_job("subjects", file="Subjects", message=f"Waiting… ({len(todo)} items)")
        steps.append((_classify_all, job, todo))
    repeats = check_catalog_repeats()  # the same work entered twice before
    moved = sum(j["status"] == "duplicate" for j in repeats)
    note = f" · {moved} repeat{'s' if moved > 1 else ''} moved to archive/" if moved else ""
    if len(repeats) > moved:
        note += f" · {len(repeats) - moved} repeat(s) to check, see History"
    if steps:
        _in_background(_one_after_another, steps)
        found = len(new) + len(named)
        what = [f"found {found} new PDF{'s' if found > 1 else ''}"] if found else []
        what += [f"looking up the subjects of {len(todo)} items"] if todo else []
        return {"started": len(steps), "message": "; ".join(what).capitalize() + note}
    library_page.build()  # nothing new: still bring the static copy up to date
    return {"started": 0, "message": f"Nothing new: every PDF is already in the library{note}"}


def _classify_all(job: dict, slugs: list[str]) -> None:
    """Look up the subject of each item (OpenAlex), put it on its subject's shelf when OpenAlex
    is sure, and give shelves to the items still on none."""
    found, shelved = 0, []
    try:
        for n, slug in enumerate(slugs, 1):
            _update(job, message=f"Looking up subjects: {n} of {len(slugs)}")
            if subjects.classify(slug, add_book.LIBRARY, add_book.CATALOG):
                found += 1
            topic = shelves.add_topic_shelf(slug, add_book.CATALOG)
            if topic or shelves.auto_shelve(slug, add_book.LIBRARY, add_book.CATALOG):
                shelved.append(slug)
        library_page.build()
        _finish(job, "done", f"Subjects found for {found} of {len(slugs)} items; "
                f"{len(shelved)} put on shelves (change any with Shelves)")  # fmt: skip
    except Exception as e:
        _finish(job, "error", f"Looking up subjects stopped: {e}")


def _one_after_another(steps: list) -> None:
    for target, job, *args in steps:
        _update(job, message="Identifying…")
        target(job, *args)


def _identify(path: Path):
    """identify() for a file in the library: one in papers/ or theses/ is a paper / thesis even
    if nobody knows it."""
    return identify(
        path,
        online=True,
        paper=path.parent == add_book.PAPERS,
        thesis=path.parent == add_book.THESES,
    )


def _register(job: dict, path: Path) -> None:
    """A PDF already named like a slug (e.g. renamed by hand) but not in the catalog yet: keep
    its name, add its notes and catalog row."""
    if problem := add_book.unreadable(path):
        _finish(job, "error", f"Not added: {problem}; the file was left as it is")
        return
    try:
        meta = _identify(path)
        if repeat := add_book.repeat_of(path, meta):
            return _repeat(job, path, meta, *repeat)
        book = add_book.Book(meta.title, meta.author, meta.year, meta.publisher)
        add_book.setup_book(path, book, meta)
        library_page.build()
        _in_background(book_search.update)
        added = f"Added the {add_book.kind_word(meta)} “{book.title}”" + _on_shelves(path.stem)
        _finish(job, "done", added, slug=path.stem)
    except Exception as e:
        _finish(job, "error", f"Couldn't add {path.name}: {e}")


def _on_shelves(slug: str) -> str:
    """' · on shelves: 光学 Optics, 激光 Lasers' (the ones it was put on), or ''."""
    on = catalog.split_list(catalog.load(add_book.CATALOG).get(slug, {}).get("shelves") or "")
    return (
        f" · on shelves: {', '.join(library_page.shelf_labels().get(s, s) for s in on)}"
        if on
        else ""
    )


def _repeat(job: dict, path: Path, meta, slug: str, reason: str) -> None:
    """A copy of something already in the library: never added twice (add_book.handle_repeat:
    a better file replaces the library's PDF, otherwise it goes to archive/)."""
    title = catalog.load(add_book.CATALOG).get(slug, {}).get("title") or slug
    replaced, what = add_book.handle_repeat(path, meta, slug)
    if replaced:
        library_page.build()
        _in_background(book_search.update)
    status = "done" if replaced else "duplicate"
    _finish(job, status, f"Already in the library as “{title}” ({reason}); {what}", slug=slug)


def check_catalog_repeats() -> list[dict]:
    """Refresh also looks for the same work entered twice: the copy without your work goes to
    archive/ (with its notes); if both have your work, the pair is only reported."""
    jobs = []
    rows = catalog.load(add_book.CATALOG)
    for pair in add_book.catalog_repeats():
        keep = rows[pair["keep"]]["title"]
        if not pair["drop"]:
            job = _new_job("repeat", file=pair["keep"])
            _finish(job, "error", f"“{keep}” is in the library twice ({pair['reason']}: "
                    f"{pair['keep']} and {pair['other']}), and both have your notes or progress. "
                    f"Keep one: uv run scripts/add_book.py --remove <slug>")  # fmt: skip
        else:
            moved = add_book.merge_into(pair["drop"], pair["keep"])
            add_book.remove_book(pair["drop"], dry_run=False, yes=True)
            job = _new_job("repeat", file=pair["drop"])
            why = f" (it has {pair['why']})" if pair["why"] != "the same" else ""
            work = f"; your work moved over: {', '.join(moved)}" if moved else ""
            message = (f"“{keep}” was in the library twice ({pair['reason']}); kept "
                       f"{pair['keep']}{why}, moved {pair['drop']} to archive/{work}")  # fmt: skip
            _finish(job, "duplicate", message)
        jobs.append(job)
    return jobs


# --- the archive --------------------------------------------------------------------------------


# What "Clear archive" deletes: the documents themselves, empty note templates and placeholder
# files. Everything else (scripts, notebooks, notes with your writing) is kept, whatever folder
# it's in: archive/ can hold things from older versions of this tool too.
DOCUMENTS = {".pdf", ".djvu", ".epub"}


def _archive_plan() -> tuple[list[Path], list[str]]:
    """(files to delete, what's kept: "folder/item" names) for "Clear archive"."""
    archive = add_book.ARCHIVE
    delete, kept = [], []
    if not archive.exists():
        return delete, kept
    for f in sorted(archive.rglob("*")):
        if not f.is_file():
            continue
        parts = f.relative_to(archive).parts
        empty_notes = (
            parts[0] == "notes"
            and len(parts) > 2
            and not add_book.has_own_work(parts[1], notes_dir=archive / "notes" / parts[1])
        )
        if f.suffix.lower() in DOCUMENTS or f.name == ".gitkeep" or empty_notes:
            delete.append(f)
        else:
            name = "/".join(parts[:2])
            if name not in kept:
                kept.append(name)
    return delete, kept


def archive_summary() -> dict:
    """What "Clear archive" would delete (number of files, bytes) and what it keeps."""
    delete, kept = _archive_plan()
    return {"files": len(delete), "bytes": sum(f.stat().st_size for f in delete), "kept": kept}


def clear_archive() -> dict:
    """Delete the archived documents (removed books and papers, repeats, original scans) and
    empty note templates; keep everything that holds your own work."""
    delete, kept = _archive_plan()
    summary = {"files": len(delete), "bytes": sum(f.stat().st_size for f in delete), "kept": kept}
    for f in delete:
        f.unlink()
    archive = add_book.ARCHIVE
    if archive.exists():  # folders left empty, deepest first
        for folder in sorted((d for d in archive.rglob("*") if d.is_dir()),
                             key=lambda d: len(d.parts), reverse=True):  # fmt: skip
            if not any(folder.iterdir()):
                folder.rmdir()
    return summary


def _add(job: dict, path: Path) -> None:
    if problem := add_book.unreadable(path):  # nothing registered, the file left as it is
        _finish(job, "error", f"Not added: {problem}; the file was left as it is")
        return
    try:
        meta = _identify(path)  # never leaves the title, author or year empty
        book = add_book.Book(meta.title.strip(), meta.author.strip(), meta.year.strip(),
                             meta.publisher)  # fmt: skip
        if repeat := add_book.find_repeat(path, meta, book):
            return _repeat(job, path, meta, *repeat)
        target = add_book.file_book(path, book, meta)
        scan = ocr_pdf.needs_ocr(target)
        library_page.build()
        _in_background(book_search.update)  # make it searchable (在我的书中 / In my books)
        _finish(
            job,
            "done",
            f"Added the {add_book.kind_word(meta)} “{book.title}”"
            + _on_shelves(book.slug)
            + (" (a scan: OCR recommended)" if scan else ""),
            slug=book.slug,
            scan=scan,
        )
    except Exception as e:  # shown on the page (in the History)
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
    except (Exception, SystemExit) as e:  # SystemExit: the PDF is open elsewhere (ocr_pdf)
        _finish(job, "error", f"OCR failed: {str(e).strip(' !')}")
