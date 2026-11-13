"""Background jobs started from the library page: adding uploaded books, and OCR for scans.

The page polls list_jobs() to show progress; nothing here needs a terminal. The same steps as
`uv run scripts/add_book.py` and `uv run scripts/ocr_pdf.py`, without the questions.
"""

import os
import re
import threading
import time
import uuid
from pathlib import Path

import add_book
import book_meta
import book_search
import catalog
import library_page
import notes_store
import ocr_pdf
import safe_io
import shelves
import subjects
from book_meta import identify

MAX_UPLOAD = 1_000_000_000  # 1 GB: bigger than any book, smaller than a mistake
_jobs: dict[str, dict] = {}
_lock = threading.Lock()
_threads: set[threading.Thread] = set()  # running jobs, so quitting can wait for them
_stopping = threading.Event()  # set by shutdown(): no new jobs; OCR stops between pages
_upload_lock = threading.Lock()  # choosing an upload's file name


class Stopped(Exception):
    """myLibrary is quitting: the job stops at a safe point."""


STOPPED = "myLibrary was quit"


def _check_running() -> None:
    if _stopping.is_set():
        raise ValueError("myLibrary is stopping; start it again to do this")


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
    def run() -> None:
        try:
            target(*args)
        finally:
            with _lock:
                _threads.discard(threading.current_thread())

    thread = threading.Thread(target=run, daemon=True)
    with _lock:
        _threads.add(thread)
    thread.start()


def shutdown(timeout: float = 60) -> dict:
    """Before quitting (Quit, a library change, Ctrl+C): start nothing new, let running jobs
    reach a safe point (an add finishes filing its book; OCR stops after its current page,
    which is cached), then wait for every file operation in progress (safe_io). Waits at most
    `timeout` seconds for the jobs; a file operation is always waited for. Returns
    {"unfinished": [jobs still running]}."""
    _stopping.set()
    end = time.monotonic() + timeout
    while True:
        with _lock:
            running = [t for t in _threads if t.is_alive()]
        if not running or time.monotonic() >= end:
            break
        running[0].join(min(0.2, max(0.0, end - time.monotonic())))
    # Whatever is still running can't start another file operation now, and one in progress
    # is finished first (each is short: one file, or filing one book)
    safe_io.close(timeout=max(30.0, end - time.monotonic()))
    unfinished = [j["file"] for j in list_jobs() if _active(j)]
    return {"unfinished": unfinished}


def reopen() -> None:
    """Undo shutdown() (tests)."""
    _stopping.clear()
    safe_io.reopen()


# --- adding books -------------------------------------------------------------------------------


def save_upload(name: str, data: bytes) -> Path:
    """Write an uploaded PDF into the library's books/ under a safe, unused name."""
    if not data.startswith(b"%PDF"):
        raise ValueError(f"{name} is not a PDF")
    _check_running()
    stem = re.sub(r"[^\w\s().,'-]+", "_", Path(name).stem).strip(" ._") or "book"
    add_book.BOOKS.mkdir(parents=True, exist_ok=True)
    # Written to a hidden temporary file first (a half-written PDF never shows up in books/),
    # then given a free name; the name is chosen and taken in one step, so two uploads called
    # the same never end up in one file
    tmp = add_book.BOOKS / f".upload-{uuid.uuid4().hex[:12]}.part"
    try:
        safe_io.write_bytes(tmp, data)
        with _upload_lock, safe_io.critical():
            target = add_book.BOOKS / f"{stem[:120]}.pdf"
            n = 2
            while target.exists():
                target = add_book.BOOKS / f"{stem[:120]} ({n}).pdf"
                n += 1
            tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)
    return target


def start_add(path: Path) -> dict:
    """Identify, name and register an uploaded book (in the background)."""
    _check_running()
    job = _new_job("add", file=path.name, path=str(path), message="Identifying the book…")
    _in_background(_add, job, path)
    return job


def start_download(url: str, title: str = "") -> dict:
    """Download a free (open-access) PDF found with "Find online", then add it like an upload."""
    if not re.match(r"https?://", url):
        raise ValueError("not a web address")
    _check_running()
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
    _check_running()
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


def _classify_all(job: dict, doc_ids: list[str]) -> None:
    """Look up the subject of each item (OpenAlex), put it on its subject's shelf when OpenAlex
    is sure, and give shelves to the items still on none."""
    found, shelved, unavailable = 0, [], ""
    try:
        for n, doc_id in enumerate(doc_ids, 1):
            if _stopping.is_set():  # the rest are looked up by the next Refresh
                _finish(job, "error", f"Stopped after {n - 1} of {len(doc_ids)} items: {STOPPED}; "
                        "Refresh looks up the rest")  # fmt: skip
                return
            _update(job, message=f"Looking up subjects: {n} of {len(doc_ids)}")
            try:
                if not unavailable and subjects.classify(
                    doc_id, add_book.LIBRARY, add_book.CATALOG
                ):
                    found += 1
            except book_meta.Unavailable as e:
                unavailable = str(e)  # don't ask again for the rest; the next Refresh will
            topic = shelves.add_topic_shelf(doc_id, add_book.CATALOG)
            if topic or shelves.auto_shelve(doc_id, add_book.LIBRARY, add_book.CATALOG):
                shelved.append(doc_id)
        library_page.build()
        note = (f" OpenAlex couldn't answer ({unavailable}); Refresh again later (its free"
                " daily limit resets at midnight UTC)." if unavailable else "")  # fmt: skip
        _finish(job, "done", f"Subjects found for {found} of {len(doc_ids)} items; "
                f"{len(shelved)} put on shelves (change any with Shelves).{note}")  # fmt: skip
    except Exception as e:
        _finish(job, "error", f"Looking up subjects stopped: {e}")


def _one_after_another(steps: list) -> None:
    for target, job, *args in steps:
        if _stopping.is_set():  # not started: the file is still there for the next Refresh
            _finish(job, "error", f"Not started: {STOPPED}; Refresh adds it next time")
            continue
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
        with add_book.FILING:  # see _add
            _check_stopping(job)
            repeat = add_book.repeat_of(path, meta)
            if repeat:
                return _repeat(job, path, meta, *repeat)
            book = add_book.Book(meta.title, meta.author, meta.year, meta.publisher)
            with safe_io.critical():
                doc_id = add_book.reserve_row(path, book, meta)
        with safe_io.critical():  # notes and catalog row written before quitting
            add_book.setup_book(path, book, meta, doc_id=doc_id)
        library_page.build()
        _in_background(book_search.update)
        added = f"Added the {add_book.kind_word(meta)} “{book.title}”" + _on_shelves(doc_id)
        if shared := add_book.sharing_note(meta, doc_id):  # (L21, B29: kept apart, said so)
            added += f" · {shared}"
        _finish(job, "done", added, doc_id=doc_id)
    except Stopped:
        _finish(job, "error", f"Not registered: {STOPPED}; Refresh does it next time")
    except Exception as e:
        _finish(job, "error", f"Couldn't add {path.name}: {e}")


def _on_shelves(doc_id: str) -> str:
    """' · on shelves: 光学 Optics, 激光 Lasers' (the ones it was put on), or ''."""
    on = catalog.split_list(catalog.load(add_book.CATALOG).get(doc_id, {}).get("shelves") or "")
    return (
        f" · on shelves: {', '.join(library_page.shelf_labels().get(s, s) for s in on)}"
        if on
        else ""
    )


def _repeat(job: dict, path: Path, meta, doc_id: str, reason: str) -> None:
    """A copy of a document already in the library: never added twice (add_book.handle_repeat:
    a better file replaces the library's PDF, otherwise it goes to archive/)."""
    row = catalog.load(add_book.CATALOG).get(doc_id, {})
    title = row.get("title") or row.get("slug") or doc_id
    with add_book.FILING, safe_io.critical():  # moves PDFs: never two at once, never cut off
        replaced, what = add_book.handle_repeat(path, meta, doc_id, reason=reason)
    if replaced:
        library_page.build()
        _in_background(book_search.update)
    status = "done" if replaced else "duplicate"
    _finish(job, status, f"Already in the library as “{title}” ({reason}); {what}", doc_id=doc_id)


def check_catalog_repeats() -> list[dict]:
    """Refresh also looks for the same work entered twice: the copy without your work goes to
    archive/ (with its notes); if both have your work, the pair is only reported."""
    with add_book.FILING, safe_io.critical():  # merging and archiving move files: one at a time
        return _check_catalog_repeats()


def _check_catalog_repeats() -> list[dict]:
    jobs = []
    rows = catalog.load(add_book.CATALOG)
    name = {doc_id: row["slug"] for doc_id, row in rows.items()}
    for pair in add_book.catalog_repeats():
        keep = rows[pair["keep"]]["title"]
        if not pair["drop"]:
            job = _new_job("repeat", file=name[pair["keep"]])
            why = (f"and a notes folder in catalog.csv isn't under notes/ ({pair['problem']}): "
                   "nothing was merged or moved. Correct catalog.csv" if pair.get("problem")
                   else "and both have your notes or progress. Keep one: add_book.py --remove "
                   "<name>")  # fmt: skip
            _finish(job, "error", f"“{keep}” is in the library twice ({pair['reason']}: "
                    f"{name[pair['keep']]} and {name[pair['other']]}), {why}")  # fmt: skip
        else:
            try:
                moved = add_book.merge_into(pair["drop"], pair["keep"])
            except (notes_store.NoteError, OSError) as e:
                # Nothing archived: both documents stay, and the next Refresh tries again
                # (images already copied are used again, never copied twice). The reason only,
                # never a full path
                e = getattr(e, "strerror", None) or e
                job = _new_job("repeat", file=name[pair["drop"]])
                _finish(job, "error", f"“{keep}” is in the library twice ({pair['reason']}: "
                        f"{name[pair['keep']]} and {name[pair['drop']]}), but merging them "
                        f"stopped: {e}. Neither was moved to archive/.")  # fmt: skip
                jobs.append(job)
                continue
            # Its tombstone points to the one kept: its reading history counts for that one
            add_book.remove_book(pair["drop"], dry_run=False, yes=True, merged_into=pair["keep"])
            job = _new_job("repeat", file=name[pair["drop"]])
            why = f" (it has {pair['why']})" if pair["why"] != "the same" else ""
            work = f"; your work moved over: {', '.join(moved)}" if moved else ""
            message = (f"“{keep}” was in the library twice ({pair['reason']}); kept "
                       f"{name[pair['keep']]}{why}, moved {name[pair['drop']]} to "
                       f"archive/{work}")  # fmt: skip
            _finish(job, "duplicate", message)
        jobs.append(job)
    return jobs


# --- the archive --------------------------------------------------------------------------------


# What "Clear archive" deletes: only what is positively known to hold none of your work:
# - archived documents (removed books and papers, repeats, original scans), except in the
#   folders of notes and scripts (a PDF kept beside notes is yours);
# - empty .gitkeep placeholders;
# - generated chapter or paper templates (by name: chNN-....md, notes.md) still untouched,
#   directly in an archived document's notes folder (archive/notes/<name>/).
# Everything else is kept, whatever folder it's in: every README (even empty or as generated),
# images, unknown files, nested folders, and anything reached through a link or junction
# (never followed: it may lead outside the archive). archive/ can hold things from older
# versions of this tool too. If in doubt, a file is kept.
DOCUMENTS = {".pdf", ".djvu", ".epub"}
OWN_FOLDERS = {"notes", "notes-conflicts", "marks-conflicts", "examples"}  # yours
# (marks-conflicts: a tab's marked PDF kept after a conflict, D5: never deleted here)
TEMPLATE_NAME = re.compile(r"ch\d{2,}-[a-z0-9-]*\.md|notes\.md")


def _archive_walk(archive: Path) -> tuple[list[Path], list[Path], list[Path]]:
    """(plain files, folders, everything else: links, junctions, unreadable folders) under
    `archive`, never through a link or junction."""
    files, folders, other = [], [], []
    stack = [archive]
    while stack:
        folder = stack.pop()
        try:
            entries = list(os.scandir(folder))
        except OSError:  # unreadable: whatever is in it is kept
            other.append(folder)
            continue
        for entry in entries:
            path = Path(entry.path)
            if entry.is_symlink() or entry.is_junction():
                other.append(path)
            elif entry.is_dir(follow_symlinks=False):
                folders.append(path)
                stack.append(path)
            elif entry.is_file(follow_symlinks=False):
                files.append(path)
            else:
                other.append(path)
    return sorted(files), folders, other


def _deletable(path: Path, parts: tuple[str, ...]) -> bool:
    """Whether "Clear archive" may delete this archived file (see above)."""
    name = path.name
    if name == ".gitkeep":
        return path.stat().st_size == 0
    if path.suffix.lower() in DOCUMENTS:
        return parts[0] not in OWN_FOLDERS
    if parts[0] == "notes" and len(parts) == 3 and TEMPLATE_NAME.fullmatch(name):
        try:
            return add_book.is_untouched_template(path)
        except OSError, UnicodeError:
            return False
    return False


def _archive_plan() -> tuple[list[Path], list[str]]:
    """(files to delete, what's kept: "folder/item" names) for "Clear archive"."""
    archive = add_book.ARCHIVE
    delete, kept = [], []
    if not archive.is_dir():
        return delete, kept
    files, _, other = _archive_walk(archive)
    for f, plain in [(f, True) for f in files] + [(f, False) for f in sorted(other)]:
        parts = f.relative_to(archive).parts
        if plain and _deletable(f, parts):
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
    untouched note templates; keep everything else (see DOCUMENTS above)."""
    delete, kept = _archive_plan()
    summary = {"files": len(delete), "bytes": sum(f.stat().st_size for f in delete), "kept": kept}
    for f in delete:
        f.unlink()
    archive = add_book.ARCHIVE
    if archive.is_dir():  # folders left empty, deepest first; never through a link
        _, folders, _ = _archive_walk(archive)
        for folder in sorted(folders, key=lambda d: len(d.parts), reverse=True):
            if not any(folder.iterdir()):
                folder.rmdir()
    return summary


def _add(job: dict, path: Path) -> None:
    if problem := add_book.unreadable(path):  # nothing registered, the file left as it is
        _finish(job, "error", f"Not added: {problem}; the file was left as it is")
        return
    try:
        meta = _identify(path)  # never leaves the title, author or year empty (in parallel)
        book = add_book.Book(meta.title.strip(), meta.author.strip(), meta.year.strip(),
                             meta.publisher)  # fmt: skip
        # Filing is one step at a time: checking for a repeat and taking the name must not
        # interleave with another job doing the same (two copies of one book dropped together)
        with add_book.FILING:
            _check_stopping(job)
            repeat = add_book.find_repeat(path, meta, book)
            if repeat:
                return _repeat(job, path, meta, *repeat)
            with safe_io.critical():
                # A different document with the same usual name gets the next free name (-2)
                target = add_book.place_book(path, book, meta)
                doc_id = add_book.reserve_row(target, book, meta)
            note = add_book.name_note(book, doc_id, meta)
        # Notes and the catalog row (other books are filed meanwhile); quitting waits for it
        with safe_io.critical():
            add_book.setup_book(target, book, meta, doc_id=doc_id)
        scan = ocr_pdf.needs_ocr(target)
        library_page.build()
        _in_background(book_search.update)  # make it searchable (在我的书中 / In my books)
        _finish(
            job,
            "done",
            f"Added the {add_book.kind_word(meta)} “{book.title}”"
            + _on_shelves(doc_id)
            + (" (a scan: OCR recommended)" if scan else "")
            + (f" · {note}" if note else ""),
            doc_id=doc_id,
            scan=scan,
        )
    except Stopped:
        _finish(job, "error", f"Not added: {STOPPED}; {path.name} is still in "
                f"{path.parent.name}/, and Refresh adds it next time")  # fmt: skip
    except Exception as e:  # shown on the page (in the History)
        _finish(job, "error", f"Couldn't add {path.name}: {e}")


def _check_stopping(job: dict) -> None:
    """Before filing a book: once quitting, leave the file where it is (Refresh adds it)."""
    if _stopping.is_set():
        raise Stopped()


# --- OCR --------------------------------------------------------------------------------------


def start_ocr(doc_id: str) -> dict:
    """Give a scanned book an invisible text layer (in the background, one book at a time)."""
    row = catalog.load(add_book.CATALOG).get(doc_id)
    if row is None:
        raise ValueError("no such document")
    pdf = add_book.library_pdf(row)
    if not pdf.exists():
        raise ValueError("that book's PDF isn't in the library")
    _check_running()
    with _lock:  # checking and starting in one step: two clicks can't start two OCRs
        if any(j["kind"] == "ocr" and j["status"] == "working" for j in _jobs.values()):
            raise ValueError("another book is being OCR'd; try again when it's done")
        job = {"id": uuid.uuid4().hex[:12], "kind": "ocr", "status": "working",
               "started": time.time(), "doc_id": doc_id, "done": 0, "total": 0,
               "message": "Starting OCR…"}  # fmt: skip
        _jobs[job["id"]] = job
    _in_background(_ocr, job, pdf)
    return job


def _ocr(job: dict, pdf: Path) -> None:
    def progress(done: int, total: int) -> None:
        _update(job, done=done, total=total, message=f"OCR page {done} of {total}")
        if _stopping.is_set():  # the PDF isn't touched until every page is done
            raise Stopped()

    try:
        ocr_pdf.make_searchable(pdf, progress)
        add_book.forget_chapter_pages(pdf.stem)  # chapter pages are found again from the text
        add_book.refresh_chapters(pdf, dry_run=False)
        book_search.update()
        library_page.build()
        _finish(job, "done", "OCR finished: the book can now be searched and looked up")
    except Stopped:
        _finish(job, "error", f"OCR stopped because {STOPPED}; the book is unchanged. Start OCR "
                "again: the pages already read are remembered")  # fmt: skip
    except ocr_pdf.PdfChanged:  # D15: its result would have taken the marks away
        _finish(job, "error", "OCR not applied: the PDF changed while OCR was running (your "
                "marks were saved meanwhile), so it was left as it is, with your marks. Start "
                "OCR again to add the text layer to it")  # fmt: skip
    except (Exception, SystemExit) as e:  # SystemExit: the PDF is open elsewhere (ocr_pdf)
        _finish(job, "error", f"OCR failed: {str(e).strip(' !')}")
