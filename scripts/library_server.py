"""Local reading server for myLibrary.

    uv run scripts/library_server.py          # opens http://127.0.0.1:8765 in your browser

"Read" / "Continue" on a book (or "Read" on one chapter) opens everything for that chapter:
  - the PDF in the browser, at the page where the chapter starts
  - in your editor (Settings: VS Code, Notepad, ...): the chapter's notes and its Python script
    examples/<name>/chNN_<topic>.py if you have made one
"Script" on a chapter creates that script (from a short template) and opens it: a place to
check the book's worked examples in Python.
Ticking a chapter on the page writes "- [x]" into the document's notes/<name>/README.md.

PDFs open in the reading view (PDF.js + word lookup, see reader.py): double-click a word
for its glossary / dictionary meaning in Chinese, and save it to notes/<name>/vocabulary.md.

Documents are known by their id (catalog.py) in every request; /read/<id> opens one in the
reading view whatever its file is called now.

Only listens on 127.0.0.1, and every action needs the token embedded in the page,
so other websites can't trigger it. Stop with Ctrl+C.
"""

import argparse
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import webbrowser
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote

import add_book
import backup
import book_search
import catalog
import find_online
import folder_backup
import formula_ocr
import image_check
import libraries
import library_jobs
import library_page
import notes_store
import paths
import platform_services
import reader as reading_view
import reading_log
import safe_io
import vocab_review
from add_book import short_title
from book_ocr import has_text_layer
from book_toc import CHAPTER_TITLE_RE, contents_pages, scanned_chapter_pages, tidy
from pypdf import PdfReader

LIBRARY = paths.LIBRARY
CATALOG = LIBRARY / "catalog.csv"
CACHE = LIBRARY / ".cache" / "chapter_pages.json"
TOKEN = secrets.token_urlsafe(24)
_LIBRARY_LOCK = None  # the library's lock while this server runs (main, libraries.hold_library)
# This library's key in the browser (recovery drafts: libraries.scope), and whether it's the
# default library (the only one that can show drafts from before there were several)
SCOPE = libraries.scope(LIBRARY)
_default = libraries.configured_library()
IS_DEFAULT = _default is not None and libraries.same_place(_default, LIBRARY)

_cache_lock = threading.Lock()
_book_locks: dict[str, threading.Lock] = {}


# --- where each chapter starts in the PDF -------------------------------------------------


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _bare_title(title: str) -> str:
    """'Ch 3: Aberrations' (as listed in the notes README) -> 'Aberrations'."""
    return re.sub(r"^Ch\s*\d+:\s*", "", title)


def find_chapter_pages(pdf: Path, chapters: list[dict]) -> dict[int, int]:
    """{chapter number: 1-based PDF page}, from bookmarks or by finding chapter-opening pages."""
    reader = PdfReader(pdf)
    if not reader.outline and not has_text_layer(reader):
        # Image-only scan: OCR the page tops (a few minutes once, then cached)
        print(f"  finding chapter pages in {pdf.name} with OCR (first time only)...")
        return scanned_chapter_pages(pdf, len(reader.pages))
    pages: dict[int, int] = {}

    def walk(items):
        for item in items:
            if isinstance(item, list):
                walk(item)
            elif (m := CHAPTER_TITLE_RE.match(tidy(item.title))) and int(m[1]) not in pages:
                try:
                    pages[int(m[1])] = reader.get_destination_page_number(item) + 1
                except Exception:  # broken bookmark target
                    pass

    walk(reader.outline)
    if pages:
        return pages

    # No numbered bookmarks: the chapter starts on the first page (after the Contents)
    # whose top lines show "Chapter N" or the chapter's title. A title found further into the
    # top lines only counts for the next chapter due: running text like "... symmetrical
    # optical systems" mustn't make chapter "Optical Systems" start there. Once the book has
    # shown "Chapter N" headings, that looser match isn't needed at all.
    wanted = [c for c in chapters if c["number"] is not None]
    titles = {c["number"]: _key(_bare_title(c["title"]))[:30] for c in wanted}
    start = max(contents_pages(reader), default=-1) + 1
    last = 0
    numbered = False
    for i in range(start, len(reader.pages)):
        top = " ".join((reader.pages[i].extract_text() or "").strip().splitlines()[:4])
        head = _key(top)
        head_start = head.lstrip("0123456789")  # past a page number
        due = min((n for n in titles if n > last and n not in pages), default=None)
        for n in sorted(titles):
            if n <= last or n in pages:
                continue
            by_number = re.match(rf"^\s*chapter\s*{n}\b", top, re.IGNORECASE)
            title = titles[n]
            by_title = len(title) >= 6 and (
                head_start.startswith(title) or (n == due and not numbered and title in head)
            )
            numbered = numbered or bool(by_number)
            if by_number or by_title:
                pages[n], last = i + 1, n
                break
    return pages


def chapter_page(doc_id: str, number: int | None, chapters: list[dict]) -> int | None:
    if number is None:
        return None
    # One lookup per book at a time: the background warm-up and a Read click shouldn't both
    # run the (slow) search for the same book
    with _cache_lock:
        book_lock = _book_locks.setdefault(doc_id, threading.Lock())
    with book_lock:
        with _cache_lock:
            cache = _read_cache()
        if doc_id not in cache:
            pdf = LIBRARY / catalog.load(CATALOG)[doc_id]["file"]
            if not pdf.exists():
                return None  # PDF deleted: notes and scripts still open, just no page
            found = find_chapter_pages(pdf, chapters)
            pages = {str(k): v for k, v in found.items()}

            def add(cached: dict) -> dict:
                cached[doc_id] = pages
                return cached

            with _cache_lock:
                cache = safe_io.update_json(CACHE, add, {}, cache=True, indent=1)
    # Not found (e.g. OCR-garbled title): start of the nearest earlier chapter is close enough
    known = {int(k): v for k, v in cache[doc_id].items() if int(k) <= number}
    return known[max(known)] if known else None


def warm_cache() -> None:
    """Find chapter pages for every book in the background, so the first Read is quick;
    also bring the full-text index (在我的书中 / In my books) up to date."""
    try:
        report = book_search.update()
        if report["indexed"] or not report["complete"]:  # says so when anything is missing
            print(f"  {book_search.describe(report)}")
    except Exception as e:  # e.g. the index file itself can't be opened: nothing was indexed
        print(f"  ! couldn't update the full-text index at all: {e!r}")
    for doc_id, row in catalog.load(CATALOG).items():
        try:
            chapter_page(doc_id, 1, library_page.chapters(doc_id, library_page.readme_of(row)))
        except Exception as e:  # one damaged PDF shouldn't stop the others
            print(f"  ! couldn't find chapter pages for {row['slug']}: {e}")


# --- chapter scripts ----------------------------------------------------------------------

SCRIPT_TEMPLATE = '''"""{book}
{chapter}

Check this chapter's worked examples in Python: recompute a result, then compare it with the
book's answer. Run it with VS Code's Run button, or in a terminal:

    uv run {path}

Notes for this chapter: {notes}{note}
"""

import sys
from pathlib import Path

# Your own reusable code is in the library's code/ folder (e.g. code/optics/paraxial.py)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "code"))

# Useful imports (uncomment what you need):
# import math
# import numpy as np
# from optics.paraxial import thin_lens


def main() -> None:
    # Example 1:
    # result = ...
    # print(f"result = {{result:.4g}}  (book: ...)")
    pass


if __name__ == "__main__":
    main()
'''


def script_for(row: dict, chapter: dict, create: bool = False) -> Path | None:
    """The document's examples/<name>/chNN_<topic>.py: the existing one, or with create, a new
    one from the template. None if there's none and create is False."""
    folder = LIBRARY / "examples" / row["slug"]
    existing = sorted(folder.glob(f"ch{chapter['number']:02d}_*.py"))
    if existing:
        return existing[0]
    if not create:
        return None
    topic = "_".join(short_title(_bare_title(chapter["title"])).split("-")[:4])
    path = folder / f"ch{chapter['number']:02d}_{topic}.py"
    folder.mkdir(parents=True, exist_ok=True)

    def safe(text: str) -> str:
        # no triple quotes (they'd end the docstring) and no backslashes in the header
        return text.replace('"' * 3, "'" * 3).replace(chr(92), "/")

    path.write_text(
        SCRIPT_TEMPLATE.format(
            book=safe(row["title"]),
            chapter=safe(chapter["title"]),
            path=paths.display(path),
            notes=row["notes"],
            note=chapter["note"],
        ),
        encoding="utf-8",
    )
    return path


def open_in_editor(*files: Path) -> bool:
    """Open notes (and scripts) with the editor chosen in the settings: VS Code (the project
    window, reused if it's open), Notepad, the file's default app, or a custom command."""
    settings = paths.load_settings()
    editor = settings.get("editor", "system")
    if editor == "vscode":
        code = shutil.which("code")
        args = [str(paths.WORKSPACE), *map(str, files)]
        launch = platform_services.vscode_command(code, args) if code else None
        if launch:  # (never code.CMD with a path cmd.exe would act on: B28)
            command, env = launch
            subprocess.Popen(command, cwd=paths.WORKSPACE, env=env)
            return True
        if code:
            print(
                "VS Code wasn't used: a path to open (the library's folder) holds characters "
                "cmd.exe would act on, and VS Code's Code.exe and cli.js weren't found to start "
                "it without cmd.exe (B28). Opened with the system editor instead."
            )
        editor = "system"  # VS Code isn't installed (any more), or can't take these: fall back
    try:
        for f in files:  # (a .py is never opened with its default app: platform_services)
            platform_services.open_for_editing(f, editor, settings.get("editor_command", ""))
        return True
    except OSError:
        return False


def python_features() -> bool:
    """Chapter scripts (checking a book's examples in Python): off in the package."""
    return bool(paths.load_settings().get("python_features"))


def pick_folder(purpose: str = "library") -> platform_services.FolderChoice:
    """Ask for a folder with the system's own folder dialog (the server runs on this computer):
    Windows (and, untested on a Mac, macOS); elsewhere "unsupported"."""
    description = {
        "library": "Choose the folder for your library (books and notes)",
        "backup": "Choose the folder for your backups (e.g. on OneDrive or a USB stick)",
    }[purpose]
    return platform_services.pick_folder(description)


def auto_backup() -> None:
    """💾 Back up once a day when a backup folder is set (folder_backup.auto_backup)."""
    if message := folder_backup.auto_backup():
        print(message)


def check_openalex_key(key: str) -> None:
    """Ask OpenAlex once with the key; a key it turns down is not saved (ValueError)."""
    request = urllib.request.Request(
        "https://api.openalex.org/works?per-page=1&select=id",
        headers={"User-Agent": "myLibrary book organizer", "Authorization": f"Bearer {key}"},
    )
    try:
        urllib.request.urlopen(request, timeout=15).close()
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise ValueError("OpenAlex didn't accept that key: check it, or open the link "
                             "in its email first") from None  # fmt: skip
    except OSError:
        pass  # offline: keep it; it's used as soon as OpenAlex can be reached


def change_settings(updates: dict) -> dict:
    """Save settings from the page; a new library folder is created if it doesn't exist."""
    clean = {}
    if "editor" in updates:
        clean["editor"] = str(updates["editor"])
    if "editor_command" in updates:
        clean["editor_command"] = str(updates["editor_command"])[:500]
    if "python_features" in updates:
        clean["python_features"] = bool(updates["python_features"])
    if "openalex_key" in updates:
        key = str(updates["openalex_key"] or "").strip()
        if key and not re.fullmatch(r"[A-Za-z0-9_\-.]{8,200}", key):
            raise ValueError("that doesn't look like an OpenAlex key (letters and digits)")
        if key and key != paths.load_settings().get("openalex_key"):
            check_openalex_key(key)
        clean["openalex_key"] = key
    if "backup_folder" in updates:
        folder = str(updates["backup_folder"] or "").strip()
        if folder and not Path(folder).expanduser().is_absolute():
            raise ValueError("choose a full folder path for backups, e.g. D:\\Backups")
        clean["backup_folder"] = Path(folder).expanduser().as_posix() if folder else ""
    if "backup_pdfs" in updates:
        clean["backup_pdfs"] = bool(updates["backup_pdfs"])
    restart = False
    if updates.get("library"):
        folder = Path(str(updates["library"])).expanduser()
        if not folder.is_absolute():
            raise ValueError("choose a full folder path, e.g. D:\\Study\\My Library")
        if folder.resolve() != LIBRARY.resolve():
            if libraries.is_test_library(folder):  # (its working copy or test_library/ itself)
                raise ValueError("that's the Test & Demo library: open it with 📚 Library modes")
            if reason := paths.frozen_reason(folder):  # the showcase library/
                raise ValueError(reason)
            paths.ensure_library(folder)
            clean["library"] = folder.as_posix()
            restart = True
    paths.save_settings(clean)
    return {"restart": restart}


# --- actions ------------------------------------------------------------------------------


def startup_problem() -> str:
    """Why the library can't be opened as it is ("" if it can): a migration that didn't
    finish, a catalog still in the old format, or broken ids. Never repaired behind your back.
    (The canonical Test & Demo library is refused before this, by paths.ensure_library.)"""
    import migrate_ids

    if unfinished := migrate_ids.unfinished(LIBRARY):
        return (f"A migration of this library didn't finish ({unfinished}). Finish it with\n"
                f"  uv run scripts/migrate_ids.py --library \"{LIBRARY}\" --resume\n"
                "or undo it with --rollback.")  # fmt: skip
    try:
        catalog.load(CATALOG)
    except catalog.CatalogError as e:
        return str(e)
    return ""


def live_id(doc_id) -> str:
    """The id of the document in the library that `doc_id` refers to: itself, or for a merged
    document the one that kept its work (its tombstone); "" for a removed or unknown id."""
    if not isinstance(doc_id, str) or not catalog.is_id(doc_id):
        return ""
    found = catalog.resolve(CATALOG, doc_id)
    return found["row"]["id"] if found["status"] == "live" else ""


def unknown_document(doc_id) -> str:
    """Why an id doesn't name a document in the library, in words for the page."""
    if not isinstance(doc_id, str) or not catalog.is_id(doc_id):
        return "no document id given"
    found = catalog.resolve(CATALOG, doc_id)
    if found["status"] == "removed":
        stone = found["tombstone"]
        return (f"“{stone['title'] or stone['slug']}” was removed from the library on "
                f"{stone['date']} (its files are in archive/)")  # fmt: skip
    return "unknown document"


def pdf_url(
    base_url: str,
    file: str,
    page: int | None = None,
    doc_id: str = "",
    find: str = "",
    preview: bool = False,
) -> str:
    """The reading view (PDF.js + word lookup) once it's set up, else the bare PDF; `file` is
    the catalog's path in the library, books/, papers/ or theses/<name>.pdf; `doc_id` tells
    the reading view which document it shows; `find`: text to highlight on arrival (a search
    result; only on screen, see lookup.js showFound); `preview`: a look-up, not reading (the
    reading view records no position or reading time until "Start reading")."""
    if not reading_view.viewer_ready():  # (the dictionary is optional)
        url = f"{base_url}/{file}"
    else:
        url = f"{base_url}/pdfjs/web/viewer.html?file=/{file}" + (f"&id={doc_id}" if doc_id else "")
        url += f"&find={quote(find, safe='')}" if find else ""
        url += "&preview=1" if preview else ""
    return url + (f"#page={page}" if page else "")


def _read_cache() -> dict:
    """{id: {chapter: start page}} (call it holding _cache_lock). A damaged cache is rebuilt
    (chapter pages are found again), instead of breaking every Read."""
    return safe_io.load_json(CACHE, {}, cache=True)


_ABSOLUTE_PATH = re.compile(r"(?:\\\\\?\\(?:UNC\\)?)?(?:[A-Za-z]:|\\\\[^\\'\"\s]+)[\\/][^'\"\n]*")


def shown_error(error: Exception) -> str:
    """An unexpected error's message for the page: its text, with every absolute path cut to
    the file's name (the full path and the traceback are in the server's log)."""
    return _ABSOLUTE_PATH.sub(lambda m: Path(m[0].rstrip("\\/")).name or "a file", str(error))


def notes_with_pages(doc_id: str, row: dict) -> list[dict]:
    """The notes panel's list (notes_store.entries), each chapter with its start `page` when
    the chapter-pages cache already knows it. Never starts the (slow) chapter search: without
    the cache, chapters simply have no page."""
    entries = notes_store.entries(LIBRARY, row)
    with _cache_lock:
        starts = _read_cache().get(doc_id, {})
    for entry in entries:
        page = starts.get(str(entry["chapter"])) if entry["kind"] == "chapter" else None
        if isinstance(page, int):
            entry["page"] = page
    return entries


def chapter_at(doc_id: str, page: int, chapters: list[dict]) -> dict | None:
    """The chapter that page belongs to: the last one starting on or before it."""
    chapter_page(doc_id, 1, chapters)  # makes sure the book's chapter pages are cached
    with _cache_lock:
        cache = _read_cache()
    starts = {int(n): p for n, p in cache.get(doc_id, {}).items() if p <= page}
    if not starts:
        return None
    number = max(starts, key=lambda n: (starts[n], n))
    return next((c for c in chapters if c["number"] == number), None)


def save_position(doc_id: str, page: int) -> dict:
    """Write "Last read: page N (Ch k: ...), date" under "## Reading progress" in the README."""
    row = catalog.load(CATALOG)[doc_id]
    readme = library_page.readme_of(row)
    if not readme.exists():
        return {}
    is_paper = row.get("type") == "paper"
    chapter = None if is_paper else chapter_at(doc_id, page, library_page.chapters(doc_id, readme))
    line = f"Last read: page {page}" + (f" ({chapter['title']})" if chapter else "")
    line += f", {date.today().isoformat()}"

    def with_position(text: str) -> str:
        new, count = library_page.LAST_READ_RE.subn(lambda _: line, text, count=1)
        if not count:
            heading = re.search(r"^## Reading progress[ \t]*\n(?:[ \t]*\n)?", text, re.MULTILINE)
            if heading:
                rest = text[heading.end() :].lstrip("\n")
                new = text[: heading.end()] + line + "\n\n" + rest
            else:
                new = text.rstrip("\n") + "\n\n" + line + "\n"
        return new

    # One writer at a time: a chapter tick at the same moment isn't lost
    safe_io.update_text(readme, with_position)
    return library_page.last_read(doc_id, readme) or {}


def open_chapter(doc_id: str, number: int | None, base_url: str, resume: bool = False) -> str:
    """Open a chapter (PDF at its first page, and its script if there is one; its notes are in
    the reader's panel); with resume, open the page you last read and the chapter it belongs
    to."""
    row = catalog.load(CATALOG)[doc_id]
    try:
        readme, notes_problem = library_page.readme_of(row), ""
    except notes_store.NoteError as e:  # the PDF still opens; no notes or progress are used
        readme, notes_problem = None, str(e)
    chapters = library_page.chapters(doc_id, readme) if readme else []
    last = library_page.last_read(doc_id, readme) if resume and readme else None
    is_paper = row.get("type") == "paper"
    if last and not is_paper:
        chapter = chapter_at(doc_id, last["page"], chapters)
    else:
        chapter = next((c for c in chapters if c["number"] == number), None)
    if is_paper:  # its one item, "Read the paper", whose notes are notes.md
        chapter = next((c for c in chapters if c["number"] == 1), None)
    notes_dir = readme.parent if readme else None
    opened = []

    if (LIBRARY / row["file"]).exists():
        if last:
            page = last["page"]
        elif is_paper:
            page = 1
        else:
            page = chapter_page(doc_id, chapter["number"], chapters) if chapter else None
        webbrowser.open(pdf_url(base_url, row["file"], page, doc_id))
        opened.append(f"PDF (p. {page})" if page else "PDF")
    else:
        opened.append(f"no PDF ({row['file']} is missing)")

    # The notes are written in the reader's 📝 panel (task 4 M4, decision D5): they open in
    # the external editor only without the reading view (a plain PDF has no panel) or with ↗.
    # Two editors on one note is how conflicts start
    note = None
    if notes_dir is not None:
        note = (
            notes_dir / chapter["note"] if chapter and chapter["note"] else notes_dir / "README.md"
        )
        if not note.exists():
            note = notes_dir / "README.md"
    in_reader = reading_view.viewer_ready() and (LIBRARY / row["file"]).exists()
    files = [] if in_reader or note is None else [note]
    script = script_for(row, chapter) if chapter and python_features() else None
    if script:
        files.append(script)
    if notes_problem:
        opened.append(f"no notes ({notes_problem})")
    elif not files:
        opened.append("notes in the reader's 📝 panel")
    elif open_in_editor(*files):
        what = "notes" if not in_reader else ""
        opened.append(
            " and ".join(x for x in (what, f"script {script.name}" if script else "") if x)
        )
        if in_reader:
            opened.append("notes in the reader's 📝 panel")
    else:
        opened.append("the editor couldn't be started (see Settings)")

    what = chapter["title"] if chapter else row["title"]
    if last:
        what = f"Continuing at page {last['page']}" + (f" ({chapter['title']})" if chapter else "")
    return f"{what}: opened " + ", ".join(opened)


def open_script(doc_id: str, number: int) -> str:
    """The chapter's Python script, created from the template the first time, in your editor."""
    row = catalog.load(CATALOG)[doc_id]
    chapters = library_page.chapters(doc_id, library_page.readme_of(row))
    chapter = next((c for c in chapters if c["number"] == number), None)
    if chapter is None:
        raise ValueError(f"no chapter {number}")
    path = script_for(row, chapter, create=True)
    where = paths.display(path)
    if open_in_editor(path):
        return f"{chapter['title']}: opened {where}"
    return f"{chapter['title']}: script is {where} (the editor couldn't be started)"


# --- topic notes ------------------------------------------------------------------------------

TOPIC_TEMPLATE = """# {term}

A topic note: what several of your books say about *{term}*, in your own words.

## In my own words

-

## Where my books explain it

{sources}

## Related terms

-
"""


def topic_note(term: str) -> Path:
    """notes/topics/<term>.md, created the first time with the pages of your books that
    discuss the term most (book and page only, never book text)."""
    term = " ".join(term.split())[:80]
    name = re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")
    if not name:
        raise ValueError("a topic needs an English word or phrase")
    folder = notes_store.topics_dir(LIBRARY)
    path = folder / f"{name}.md"

    def refuse_links_out() -> None:  # (as the notes panel: never read or written through)
        if not notes_store.inside(path, folder):
            raise ValueError(f"notes/topics/{path.name} is a link pointing out of notes/topics/")

    refuse_links_out()
    if safe_io.exists(path) or os.path.lexists(path):
        return path
    # D17: the slow search runs without the file's lock; the template is then created only if
    # nothing appeared meanwhile (the notes API, an editor, another request): never over it
    found = book_search.search(term, limit=8)["results"]
    sources = "\n".join(f"- {r['title']}: PDF page {r['page']}" for r in found) or "-"
    with safe_io.lock_for(path), safe_io.critical():  # (notes_store.save takes this lock too)
        refuse_links_out()
        try:
            safe_io.create_text(path, TOPIC_TEMPLATE.format(term=term, sources=sources))
        except FileExistsError:
            pass  # written meanwhile: that note stays as it is
    return path


def open_topic(term: str) -> dict:
    path = topic_note(term)
    where = paths.display(path)
    opened = open_in_editor(path)
    return {"file": where, "opened": opened}


class TickChanged(Exception):
    """A tick refused (B32) because the chapter changed after the client last saw it: `since`
    (a replay: the README changed after the click) or `base` (a live click: the chapter was
    ticked by someone else after that version). Carries the README's chapters and their
    version, read together under the README's lock."""

    def __init__(self, message: str):
        super().__init__(message)
        self.chapters: list[dict] = []
        self.status: dict = {}  # (the README's reading status, RS1, from the same read)
        self.version = 0


# Tick versions (B32): this server's own count of its tick writes, per document, so a click
# made on an older view of a chapter can't overwrite a newer one (optimistic concurrency).
# In memory only: they start again with each server process, at its start time in ms, so a
# version from an earlier process is always below every chapter's starting version and can't
# pass for current (that process's pages also need a reload: the token changes). Changed only
# under the README's lock. Writes made outside this server (an editor) aren't counted.
TICK_START = int(time.time() * 1000)
_tick_versions: dict[str, dict] = {}  # doc id -> {"doc": latest, "chapters": {n: its last}}


def tick_version(doc_id: str) -> int:
    """The document's tick version: TICK_START until this server ticks a chapter of it."""
    return _tick_versions.get(doc_id, {}).get("doc", TICK_START)


def tick_versions() -> dict[str, int]:
    """Every document's tick version that has moved on from TICK_START (a copy)."""
    return {doc_id: record["doc"] for doc_id, record in list(_tick_versions.items())}


def check_base(base, doc_id: str) -> int:
    """A live click's `base`: the document's tick version its page last saw with the chapters
    it showed: an integer, at least 0, never ahead of the server's; else a ValueError."""
    if isinstance(base, bool) or not isinstance(base, int):
        raise ValueError("base must be a tick version (a whole number)")
    if base < 0 or base > tick_version(doc_id):
        raise ValueError("base isn't a tick version this server has given")
    return base


SINCE_AHEAD_MS = 1_000  # how far past this computer's clock a click's time may be


def check_since(since) -> float:
    """A replayed tick's click time (ms since the epoch, as the browser's Date.now() gives it):
    a finite number above 0 and no later than now (+ SINCE_AHEAD_MS); anything else (NaN,
    ±Infinity, 0, negative, far future, bool, text, null) is a ValueError, so it can never
    pass for a click older than the README's last change."""
    if isinstance(since, bool) or not isinstance(since, int | float):
        raise ValueError("since must be a time in milliseconds")
    if not math.isfinite(since) or since <= 0 or since > time.time() * 1000 + SINCE_AHEAD_MS:
        raise ValueError("since must be a past time in milliseconds")
    return float(since)


def tick_snapshot(
    doc_id: str, number: int, done: bool, *, base: int | None = None, since: float | None = None
) -> tuple[list[dict], dict, int]:
    """Set chapter `number` done or not: an absolute state, so a request repeated (its first
    answer lost) finds it already so and writes nothing. Returns the README's chapters, its
    reading status (RS1) and the document's tick version, read together under the README's lock.

    - `base` (a live click from the library page, B32): refused (TickChanged) if this server
      ticked that chapter after version `base`, so a click made on an older view never
      overwrites a newer one; the user decides (the page's "Apply mine" sends it again with the
      newer version);
    - `since` (ms, check_since: a click sent again after its page closed or crashed): refused
      if the README changed after that click (its time is the browser's, no trusted version);
    - neither (internal callers, older code): unconditional, without that protection.
    The README stays the authority: a refused tick writes nothing."""
    if since is not None:
        since = check_since(since)
    readme = library_page.readme_path(doc_id)
    pattern = library_page.chapter_line(number)
    with safe_io.lock_for(readme):  # (the same lock update_text takes: one writer at a time)
        if base is not None:
            base = check_base(base, doc_id)
        record = _tick_versions.get(doc_id, {"doc": TICK_START, "chapters": {}})
        wrote = []

        def ticked(text: str) -> str:
            m = pattern.search(text)
            if not m:
                raise ValueError(f"chapter {number} not found in {readme.name}")
            if (m[0][3] != " ") == done:
                return text  # already so: nothing to write, the version stays
            if base is not None and record["chapters"].get(number, TICK_START) > base:
                raise TickChanged(f"chapter {number} was changed in another tab or window")
            if since is not None and readme.stat().st_mtime_ns > since * 1_000_000:
                raise TickChanged(f"the notes of chapter {number} changed after that click")
            wrote.append(True)
            return text[: m.start()] + f"- [{'x' if done else ' '}] {m[1]}" + text[m.end() :]

        try:
            text = safe_io.update_text(readme, ticked)
        except TickChanged as refused:
            text = safe_io.read_text(readme)
            refused.chapters = library_page.chapters_in(text)
            refused.status = library_page.reading_status(text)
            refused.version = record["doc"]
            raise
        if wrote:  # written: the document's version moves on, and this chapter's with it
            record["doc"] += 1
            record["chapters"][number] = record["doc"]
            _tick_versions[doc_id] = record
        return library_page.chapters_in(text), library_page.reading_status(text), record["doc"]


def tick_with_version(
    doc_id: str, number: int, done: bool, *, base: int | None = None, since: float | None = None
) -> tuple[list[dict], int]:
    """tick_snapshot without the reading status: the chapters and the version."""
    chapters, _, version = tick_snapshot(doc_id, number, done, base=base, since=since)
    return chapters, version


def tick(doc_id: str, number: int, done: bool, since: float | None = None) -> list[dict]:
    """tick_with_version without a base (internal callers): its chapters only."""
    return tick_with_version(doc_id, number, done, since=since)[0]


STATUS_CHOICES = ("auto", "to-read", "reading", "finished")


def set_status(doc_id: str, status: str, *, base: int | None = None) -> tuple[dict, list, int]:
    """Set a document's reading status (RS1) in its notes README: "auto" removes the line,
    "finished" records today's date (the server's). Returns the README's status, chapters and
    the document's version, read together under the README's lock (the same lock and version
    record as ticks: B32; the status has its own entry, so ticks and it never conflict).

    - Already that status: nothing written (a "finished" keeps its date).
    - `base`: refused (TickChanged) if this server changed the status after version `base`.
    - A status line the README has but that isn't valid (unknown, malformed, more than one):
      a ValueError; it's never written over or removed here, the user corrects it.
    - The README's own line endings, byte-order mark and every other line are kept: it is
      changed as bytes, never through a newline translation."""
    if status not in STATUS_CHOICES:
        raise ValueError(f"status must be one of {', '.join(STATUS_CHOICES)}")
    readme = library_page.readme_path(doc_id)
    with safe_io.lock_for(readme), safe_io.critical():
        if base is not None:
            base = check_base(base, doc_id)
        if not readme.exists():
            raise ValueError("this document has no notes README for its status")
        record = _tick_versions.get(doc_id, {"doc": TICK_START, "chapters": {}})
        text = safe_io.read_bytes(readme).decode("utf-8")
        current = library_page.reading_status(text)
        if current["stored"] == "invalid":
            raise ValueError(f"the README's status can't be changed here: {current['problem']}"
                             " (correct it in the README)")  # fmt: skip
        if current["stored"] != status:
            if base is not None and record["chapters"].get("status", TICK_START) > base:
                refused = TickChanged("the status was changed in another tab or window")
                refused.chapters = library_page.chapters_in(text.replace("\r\n", "\n"))
                refused.status, refused.version = current, record["doc"]
                raise refused
            line = None if status == "auto" else library_page.status_line(
                status, date.today().isoformat())  # fmt: skip
            text = library_page.with_status(text, line)
            safe_io.write_bytes(readme, text.encode("utf-8"))
            record["doc"] += 1
            record["chapters"]["status"] = record["doc"]
            _tick_versions[doc_id] = record
        plain = text.replace("\r\n", "\n")
        return library_page.reading_status(text), library_page.chapters_in(plain), record["doc"]


# --- HTTP ---------------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    server_version = "myLibrary"

    def log_message(self, format, *args):  # keep the terminal quiet
        pass

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    @property
    def pdf_base(self) -> str:
        """Where the page's PDF links point: the reading view, or the bare PDFs."""
        return pdf_url(self.base_url, "").removesuffix("/")

    def _local_host(self) -> bool:
        # Blocks DNS-rebinding: a page on another site can't pretend to be us
        return self.headers.get("Host", "").split(":")[0] in {"127.0.0.1", "localhost"}

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        # Lets a second start see whose library this server shows (already_running)
        self.send_header("X-myLibrary-Library", quote(str(LIBRARY)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: dict) -> None:
        self._send(status, json.dumps(data).encode(), "application/json")

    def do_GET(self):
        try:
            self._get()
        except Exception as e:  # e.g. a typo in library.toml: say so instead of a blank page
            message = (f"myLibrary couldn't show this page: {e}\n\nFix the file named above "
                       "(or ask for help with this message), then reload.")  # fmt: skip
            print(f"  ! GET {self.path}: {e!r}")
            try:
                self._send(HTTPStatus.INTERNAL_SERVER_ERROR, message.encode(),
                           "text/plain; charset=utf-8")  # fmt: skip
            except OSError:
                pass  # the browser went away

    def _get(self):
        if not self._local_host():
            return self._send(HTTPStatus.FORBIDDEN, b"forbidden", "text/plain")
        path = self.path.split("?")[0].split("#")[0]
        if path in ("/", "/index.html"):
            # library_page appends "/<file>.pdf" to pdf_base
            # (scope: this library's key in the browser, for stored ticks; tick_versions: taken
            # before the page's chapters are read, so never newer than what it shows; B32)
            ticks = {"start": TICK_START, "documents": tick_versions()}
            api = {"token": TOKEN, "python": python_features(), "package": paths.IS_PACKAGE,
                   "backup": backup.available(),
                   "backup_deferred": backup.DEFERRED,  # (shown, paused: never hidden)
                   "folder_backup": bool(paths.load_settings().get("backup_folder"))
                   and not libraries.is_test_library(LIBRARY),
                   "library": page_library(), "scope": SCOPE,
                   "tick_versions": ticks}  # fmt: skip
            html = library_page.render(api, pdf_base=self.pdf_base)
            return self._send(HTTPStatus.OK, html.encode(), "text/html; charset=utf-8")
        if path == "/api/whoami":  # which library this is (libraries.server_at)
            test = libraries.is_test_library(LIBRARY)
            about = {"library": str(LIBRARY), "id": libraries.info(LIBRARY)["id"], "test": test}
            return self._json(HTTPStatus.OK, about)
        if path == "/pdfjs/web/viewer.html" and reading_view.viewer_ready():
            html = reading_view.viewer_html(TOKEN, SCOPE, legacy_drafts=IS_DEFAULT)
            return self._send(HTTPStatus.OK, html, "text/html; charset=utf-8")
        if found := reading_view.static_file(path):
            return self._send(HTTPStatus.OK, *found)
        if m := re.fullmatch(r"/read/([0-9a-f-]{36})", path):
            # A document's lasting link (/read/<id>?page=N): the reading view at that page,
            # whatever its file is called now; a merged one opens the document that kept it
            # ?page=N, and &find=<text> for a search result (highlighted when it opens)
            query = {k: v[0] for k, v in parse_qs(self.path.partition("?")[2]).items()}
            page = int(query["page"]) if query.get("page", "").isdigit() else None
            find = " ".join(query.get("find", "").split())[:200]
            if doc_id := live_id(m[1]):
                row = catalog.load(CATALOG)[doc_id]
                self.send_response(HTTPStatus.FOUND)
                preview = query.get("preview") == "1"  # a search result: not reading
                where = pdf_url(self.base_url, row["file"], page, doc_id, find, preview)
                self.send_header("Location", where)
                self.send_header("Content-Length", "0")
                return self.end_headers()
            status = HTTPStatus.GONE if catalog.resolve(CATALOG, m[1])["status"] == "removed" \
                else HTTPStatus.NOT_FOUND  # fmt: skip
            return self._send(status, unknown_document(m[1]).encode(), "text/plain; charset=utf-8")
        if m := re.fullmatch(r"/notes-assets/([0-9a-f-]{36})/([^/]+)", path):
            return self._asset(m[1], m[2])
        if m := re.fullmatch(r"/((?:books|papers|theses)/[a-z0-9-]+\.pdf)", path):
            known = {r["file"] for r in catalog.load(CATALOG).values()}
            pdf = LIBRARY / m[1]
            if m[1] in known and pdf.exists():
                return self._send(HTTPStatus.OK, pdf.read_bytes(), "application/pdf")
        self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")

    # A pasted image's response: never anything but the image (no sniffing, no scripts even
    # if opened on its own, not for other sites' pages); revalidated cheaply (ETag) since the
    # preview is redrawn while typing
    ASSET_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox",
        "Cross-Origin-Resource-Policy": "same-origin",
        "Cache-Control": "private, no-cache",
    }

    def _asset(self, raw_id: str, raw_name: str):
        """GET /notes-assets/<document id>/<image name, percent-encoded> (M5d): one image in the
        document's notes folder's assets/ (notes_store.asset_file: a valid name, contained,
        links followed). No token in the URL: like the PDFs, only for this computer (the Host
        check), and only for this server's own pages (Sec-Fetch-Site, when the browser sends
        it). Its type is read from its bytes, never from its name: anything that isn't a PNG,
        JPEG or WebP image is refused."""
        if self.headers.get("Sec-Fetch-Site", "same-origin") not in ("same-origin", "none"):
            return self._send(HTTPStatus.FORBIDDEN, b"forbidden", "text/plain")
        try:
            name = unquote(raw_name, errors="strict")
        except UnicodeDecodeError:
            name = ""
        doc_id = live_id(raw_id)
        try:
            if not doc_id:
                raise notes_store.NoteError("no such document")
            path = notes_store.asset_file(LIBRARY, catalog.load(CATALOG)[doc_id], name)
            stat = os.stat(safe_io._os_path(path))
        except notes_store.NoteError, OSError:
            return self._send(HTTPStatus.NOT_FOUND, b"no such image", "text/plain")
        if stat.st_size > image_check.MAX_BYTES:
            return self._send(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, b"too large", "text/plain")
        try:
            data = safe_io.read_bytes(path)
        except OSError:
            return self._send(HTTPStatus.NOT_FOUND, b"no such image", "text/plain")
        # Always checked in full, also for a "not modified" answer: a file's size, time or id
        # never prove what it holds now
        try:
            info = image_check.inspect(data)
        except image_check.ImageError:
            return self._send(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, b"not an image", "text/plain")
        # The ETag names these very bytes (checked just now), so "not modified" can only ever
        # confirm the image the tab already has
        etag = f'"{hashlib.sha256(data).hexdigest()[:32]}"'
        if etag in {t.strip() for t in self.headers.get("If-None-Match", "").split(",")}:
            self.send_response(HTTPStatus.NOT_MODIFIED)
            for key, value in {**self.ASSET_HEADERS, "ETag": etag}.items():
                self.send_header(key, value)
            return self.end_headers()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", info.mime)
        self.send_header("Content-Length", str(len(data)))
        for key, value in {**self.ASSET_HEADERS, "ETag": etag}.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def _formula(self, data: bytes):
        """/api/formula/recognize (M5e): the image's LaTeX candidates (formula_ocr). Errors
        come back with a `code` the page acts on: not-installed, damaged, busy, timeout,
        failed (and 400 for an image it can't take)."""
        try:
            return self._json(HTTPStatus.OK, formula_ocr.recognize(data))
        except formula_ocr.FormulaError as e:
            status = {
                "timeout": HTTPStatus.GATEWAY_TIMEOUT,
                "failed": HTTPStatus.INTERNAL_SERVER_ERROR,
            }.get(e.code, HTTPStatus.SERVICE_UNAVAILABLE)  # not installed, damaged, busy
            return self._json(status, {"error": str(e), "code": e.code})

    def _save_marks(self, file: str, data: bytes):
        """/api/save-marks (D5): the body is the tab's whole PDF; X-PDF-Version the version
        its marks were made on, X-PDF-Unconfirmed its saves that got no answer (comma-
        separated). 409 when the PDF changed elsewhere: nothing written to it, the tab's PDF
        kept ("kept"). X-Marks-Action: keep-copy keeps one more copy only. 500 when a copy or
        a write couldn't be checked: never reported as saved."""
        try:
            if self.headers.get("X-Marks-Action", "save") == "keep-copy":
                return self._json(HTTPStatus.OK, reading_view.keep_marks_copy(file, data))
            unconfirmed = self.headers.get("X-PDF-Unconfirmed", "").split(",")
            answer = reading_view.save_marks(
                file, data, base=self.headers.get("X-PDF-Version", ""),
                unconfirmed=unconfirmed[: reading_view.MAX_UNCONFIRMED],
            )  # fmt: skip
            return self._json(HTTPStatus.OK, answer)
        except reading_view.MarksConflict as conflict:
            return self._json(HTTPStatus.CONFLICT, {
                "conflict": True, "kept": conflict.kept, "current": conflict.current,
                "error": str(conflict),
            })  # fmt: skip
        except reading_view.MarksNotKept as e:
            return self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(e)})

    def _notes(self, doc_id: str, body: dict):
        """/api/notes/list {id}, /api/notes/get {id, key}, /api/notes/version {id, key},
        /api/notes/open {id, key}, /api/notes/keep-copy {id, key, text} (into
        archive/notes-conflicts/ only), /api/notes/save {id, key, text, base[, overwrite]}. A
        save based on an old version answers 409 with the note as it is now, and writes
        nothing (notes_store.save)."""
        row = catalog.load(CATALOG)[doc_id]
        if self.path == "/api/notes/list":
            return self._json(HTTPStatus.OK, {"notes": notes_with_pages(doc_id, row)})
        if self.path == "/api/notes/get":
            return self._json(HTTPStatus.OK, notes_store.read(LIBRARY, row, body.get("key")))
        if self.path == "/api/notes/version":
            return self._json(
                HTTPStatus.OK, notes_store.version_info(LIBRARY, row, body.get("key"))
            )
        if self.path == "/api/notes/keep-copy":
            kept = notes_store.keep_copy(LIBRARY, row, body.get("key"), body.get("text"))
            return self._json(HTTPStatus.OK, {"kept": kept})
        if self.path == "/api/notes/open":
            # An existing note only (path_of without creating: the same containment checks);
            # the editor from the settings, started without a shell. Nothing is written
            path = notes_store.path_of(LIBRARY, row, body.get("key"))
            if open_in_editor(path):
                return self._json(HTTPStatus.OK, {"opened": True, "message": "opened the note"})
            return self._json(
                HTTPStatus.OK,
                {"opened": False, "message": "the editor couldn't be started (see Settings)"},
            )
        if self.path == "/api/notes/save":
            # base: the version the text was read at; null for a note that didn't exist yet
            base = body.get("base", "missing")
            if base is not None and not (isinstance(base, str) and len(base) == 64):
                return self._json(HTTPStatus.BAD_REQUEST, {"error": "no base version"})
            overwrite = body["overwrite"] if "overwrite" in body else notes_store.NOT_GIVEN
            try:
                saved = notes_store.save(
                    LIBRARY, row, body.get("key"), body.get("text"), base, overwrite=overwrite
                )
            except notes_store.Conflict as conflict:
                return self._json(
                    HTTPStatus.CONFLICT, {"error": str(conflict), "current": conflict.current}
                )
            return self._json(HTTPStatus.OK, saved)
        return self._json(HTTPStatus.NOT_FOUND, {"error": "unknown action"})

    def _body(self, length: int) -> bytes:
        """The request's whole body. A body cut short (the tab closed while it was being sent)
        is refused: half a PDF must never be written over the library's copy."""
        data = self.rfile.read(length)
        if len(data) != length:
            raise ValueError(f"the request was cut short ({len(data)} of {length} bytes)")
        return data

    def do_POST(self):
        if not self._local_host() or self.headers.get("X-Library-Token") != TOKEN:
            return self._json(HTTPStatus.FORBIDDEN, {"error": "forbidden"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            if self.path == "/api/upload":  # a PDF from "Add books": raw bytes, not JSON
                if length > library_jobs.MAX_UPLOAD:
                    return self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "too big"})
                name = unquote(self.headers.get("X-Filename", "book.pdf"))
                path = library_jobs.save_upload(name, self._body(length))
                return self._json(HTTPStatus.OK, {"job": library_jobs.start_add(path)})
            if self.path == "/api/save-marks":  # the reading view: the PDF with your marks
                row = catalog.load(CATALOG).get(self.headers.get("X-Document-Id", ""))
                if not row or not row.get("file"):
                    return self._json(HTTPStatus.NOT_FOUND, {"error": "unknown book"})
                if length > library_jobs.MAX_UPLOAD:
                    return self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "too big"})
                data = self._body(length)
                return self._save_marks(row["file"], data)
            if self.path in ("/api/notes/asset", "/api/formula/recognize"):  # raw image bytes
                if length > image_check.MAX_BYTES:
                    return self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                                      {"error": "the image is larger than 10 MB"})  # fmt: skip
                data = self._body(length)
                if self.path == "/api/formula/recognize":  # M5e: nothing is stored
                    return self._formula(data)
                # M5d: a pasted image, for one of the document's own notes (a file: note: its
                # folder's assets/), checked before anything is written
                doc_id = live_id(self.headers.get("X-Document-Id", ""))
                if not doc_id:
                    return self._json(HTTPStatus.NOT_FOUND, {"error": unknown_document(
                        self.headers.get("X-Document-Id"))})  # fmt: skip
                row = catalog.load(CATALOG)[doc_id]
                key = unquote(self.headers.get("X-Note-Key", ""))
                if not key.startswith("file:"):
                    refusal = "images can be pasted only into a document's own notes"
                    return self._json(HTTPStatus.BAD_REQUEST, {"error": refusal})
                notes_store.path_of(LIBRARY, row, key, creating=True)  # NoteError: 400
                return self._json(HTTPStatus.OK, notes_store.save_asset(LIBRARY, row, data))
            body = json.loads(self._body(length) or b"{}")
            if self.path == "/api/formula/status":  # M5e: is the model installed?
                return self._json(HTTPStatus.OK, formula_ocr.status())
            if self.path == "/api/formula/install":  # only on the user's explicit choice
                if body.get("consent") is not True:
                    return self._json(HTTPStatus.BAD_REQUEST, {"error": "no consent given"})
                cancelled = library_jobs._stopping.is_set
                return self._json(HTTPStatus.OK, formula_ocr.start_install(cancelled))
            if self.path == "/api/books":  # the page refreshes itself after reading
                # (the tick versions first: never newer than the chapters read after them)
                versions = {"start": TICK_START, "documents": tick_versions()}
                books = library_page.books(self.pdf_base)
                return self._json(HTTPStatus.OK, {"books": books, "tick_versions": versions})
            if self.path == "/api/backup":
                return self._json(HTTPStatus.OK, backup.back_up())
            if self.path == "/api/jobs":
                if body.get("clear") is True:  # "Clear" in the History
                    library_jobs.clear_history()
                return self._json(HTTPStatus.OK, {"jobs": library_jobs.list_jobs()})
            if self.path == "/api/archive":  # Settings: the archive's size; "Clear archive"
                if body.get("clear") is True:
                    return self._json(HTTPStatus.OK, library_jobs.clear_archive())
                return self._json(HTTPStatus.OK, library_jobs.archive_summary())
            if self.path == "/api/refresh":  # "⟳ Refresh": PDFs put into the folders by hand
                return self._json(HTTPStatus.OK, library_jobs.refresh())
            if self.path == "/api/find-online":  # "🔎 Find online": DOI, title, author, ...
                return self._json(HTTPStatus.OK, find_online.find(str(body.get("query", ""))))
            if self.path == "/api/download":  # add a free PDF found online
                url, title = str(body.get("url", "")), str(body.get("title", ""))[:200]
                return self._json(HTTPStatus.OK, {"job": library_jobs.start_download(url, title)})
            if self.path == "/api/settings":
                if isinstance(body.get("save"), dict):
                    result = change_settings(body["save"])
                    if result["restart"]:
                        restart_later(self.server)
                    return self._json(HTTPStatus.OK, result)
                settings = paths.load_settings() | {"library": str(LIBRARY)}
                settings["backup_status"] = folder_backup.status(settings["backup_folder"])
                return self._json(
                    HTTPStatus.OK,
                    {"settings": settings, "editors": paths.EDITORS, "package": paths.IS_PACKAGE},
                )
            if self.path.startswith("/api/libraries"):
                return self._json(HTTPStatus.OK, libraries_api(self.path, body))
            if self.path == "/api/pick-folder":
                purpose = "backup" if body.get("purpose") == "backup" else "library"
                choice = pick_folder(purpose)
                if choice.status in ("chosen", "cancelled"):  # cancelled: folder is null
                    return self._json(
                        HTTPStatus.OK, {"folder": choice.folder, "status": choice.status}
                    )
                # No dialog here, or it failed: the page shows the message (type the folder)
                return self._json(
                    HTTPStatus.NOT_IMPLEMENTED
                    if choice.status == "unsupported"
                    else HTTPStatus.INTERNAL_SERVER_ERROR,
                    {
                        "folder": None,
                        "status": choice.status,
                        "detail": choice.message,  # (the page words the rest itself)
                        "error": f"No folder dialog ({choice.message}): type the folder instead",
                    },
                )
            if self.path == "/api/folder-backup":  # 💾 Back up: a zip (+ PDFs) in a folder
                return self._json(HTTPStatus.OK, folder_backup.back_up())
            if self.path == "/api/quit":
                running = sum(j["status"] == "working" for j in library_jobs.list_jobs())
                threading.Thread(target=stop, args=(self.server,), daemon=True).start()
                message = "myLibrary has stopped"
                if running:  # they reach a safe point first (stop): nothing is left half done
                    message = (f"myLibrary stops as soon as {running} running "
                               f"job{'s' if running > 1 else ''} reach a safe point")  # fmt: skip
                return self._json(HTTPStatus.OK, {"message": message})
            if self.path == "/api/review":  # 📇 Review words: the cards due; an answer
                if isinstance(body.get("answer"), dict):
                    word = str(body["answer"].get("word", ""))[:200]
                    knew = body["answer"].get("knew")
                    if not isinstance(knew, bool):
                        return self._json(HTTPStatus.BAD_REQUEST, {"error": "bad answer"})
                    return self._json(HTTPStatus.OK, vocab_review.answer(LIBRARY, word, knew))
                return self._json(HTTPStatus.OK, vocab_review.summary(LIBRARY, CATALOG))
            if self.path == "/api/reading-log":  # 📈 the library page's reading log
                return self._json(HTTPStatus.OK, reading_log.summary(LIBRARY, CATALOG))
            if self.path == "/api/lookup":
                text, context = str(body.get("text", "")), str(body.get("context", ""))[:1000]
                book = body.get("id") if isinstance(body.get("id"), str) else None
                return self._json(HTTPStatus.OK, reading_view.lookup(text, context, book))
            if self.path == "/api/search":
                current = body.get("id") if isinstance(body.get("id"), str) else None
                found = book_search.search(str(body.get("text", ""))[:100], current)
                return self._json(HTTPStatus.OK, found)
            if self.path == "/api/topic":
                return self._json(HTTPStatus.OK, open_topic(str(body.get("text", ""))))
            if self.path == "/api/glossary":
                term, zh, definition = (
                    str(body.get(k, ""))[:1000] for k in ("term", "zh", "definition")
                )
                name = body.get("glossary") if isinstance(body.get("glossary"), str) else None
                added = reading_view.add_glossary_term(
                    term, zh, definition, glossary_name=name or None
                )
                return self._json(HTTPStatus.OK, added)
            # Every other action is about one document, named by its id. A merged document's id
            # still works (it's followed to the document that kept its work); a removed one says so
            doc_id = live_id(body.get("id"))
            if not doc_id:
                return self._json(HTTPStatus.NOT_FOUND, {"error": unknown_document(body.get("id"))})
            chapter = body.get("chapter")
            if chapter is not None and not isinstance(chapter, int):
                return self._json(HTTPStatus.BAD_REQUEST, {"error": "bad chapter"})
            if self.path == "/api/open":
                resume = body.get("resume") is True
                message = open_chapter(doc_id, chapter, self.base_url, resume)
                return self._json(HTTPStatus.OK, {"message": message})
            if self.path.startswith("/api/notes/"):  # the reader's notes panel (notes_store)
                return self._notes(doc_id, body)
            if self.path == "/api/open-notes":
                notes = library_page.readme_path(doc_id)
                if (notes.parent / "notes.md").exists():  # a paper: its one notes file
                    notes = notes.parent / "notes.md"
                if open_in_editor(notes):
                    message = "opened the notes"
                else:
                    message = "the editor couldn't be started (see Settings)"
                return self._json(HTTPStatus.OK, {"message": message})
            if self.path == "/api/ocr":
                return self._json(HTTPStatus.OK, {"job": library_jobs.start_ocr(doc_id)})
            if self.path == "/api/script" and chapter is not None:
                if not python_features():
                    return self._json(HTTPStatus.BAD_REQUEST, {"error": "Python features are off"})
                return self._json(HTTPStatus.OK, {"message": open_script(doc_id, chapter)})
            if self.path == "/api/shelves":
                shelves = catalog.split_list(str(body.get("shelves", ""))[:300])
                if len(shelves) > 12 or any(len(s) > 40 for s in shelves):
                    return self._json(HTTPStatus.BAD_REQUEST, {"error": "too many or too long"})
                catalog.set_field(CATALOG, doc_id, "shelves", "; ".join(shelves))
                library_page.build()  # keep the static copy in step
                return self._json(HTTPStatus.OK, {"shelves": shelves})
            if self.path == "/api/position":
                page = body.get("page")
                if not isinstance(page, int) or page < 1:
                    return self._json(HTTPStatus.BAD_REQUEST, {"error": "bad page"})
                return self._json(HTTPStatus.OK, {"last_read": save_position(doc_id, page)})
            if self.path == "/api/reading":  # the reading view: a minute of reading
                seconds, pages = body.get("seconds"), body.get("pages")
                if not isinstance(seconds, int) or not isinstance(pages, list):
                    return self._json(HTTPStatus.BAD_REQUEST, {"error": "bad report"})
                return self._json(
                    HTTPStatus.OK, reading_log.record(LIBRARY, doc_id, seconds, pages[:500])
                )
            if self.path == "/api/save-word":
                page = body.get("page")
                saved = reading_view.save_word(
                    doc_id,
                    catalog.load(CATALOG)[doc_id]["title"],
                    str(body.get("text", "")),
                    str(body.get("context", ""))[:1000],
                    page if isinstance(page, int) else None,
                )
                return self._json(HTTPStatus.OK, saved)
            if self.path == "/api/tick" and chapter is not None:
                # "since" present at all (even null) must be a valid click time (check_since)
                # "since" / "base" present at all (even null) must be valid (check_since, _base)
                since = check_since(body["since"]) if "since" in body else None
                base = check_base(body["base"], doc_id) if "base" in body else None
                try:
                    chapters, status, version = tick_snapshot(
                        doc_id, chapter, bool(body.get("done")), base=base, since=since
                    )
                except TickChanged as changed:  # the README wins; the page is told its state
                    return self._json(HTTPStatus.CONFLICT, {
                        "error": str(changed), "chapter_list": changed.chapters,
                        "reading_status": changed.status, "version": changed.version})  # fmt: skip
                library_page.build()  # keep the static copy in step
                return self._json(HTTPStatus.OK, {"chapter_list": chapters, "version": version,
                                                  "reading_status": status})  # fmt: skip
            if self.path == "/api/status":  # RS1: the reading status chosen on the page
                base = check_base(body["base"], doc_id) if "base" in body else None
                try:
                    status, chapters, version = set_status(
                        doc_id, str(body.get("status", "")), base=base
                    )
                except TickChanged as changed:  # the README wins; the page is told its state
                    return self._json(HTTPStatus.CONFLICT, {
                        "error": str(changed), "chapter_list": changed.chapters,
                        "reading_status": changed.status, "version": changed.version})  # fmt: skip
                library_page.build()  # keep the static copy in step
                return self._json(HTTPStatus.OK, {"chapter_list": chapters, "version": version,
                                                  "reading_status": status})  # fmt: skip
            self._json(HTTPStatus.NOT_FOUND, {"error": "unknown action"})
        except ValueError as e:  # something the page sent that can't be done
            self._json(HTTPStatus.BAD_REQUEST, {"error": shown_error(e)})  # no full paths
        except Exception as e:
            traceback.print_exc()  # an unexpected error: where it happened, in the server's log
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": shown_error(e)})


def page_library() -> dict:
    """The library this server shows, for its page: Test & Demo or personal, and its label."""
    try:
        return libraries.current(LIBRARY)
    except (libraries.LibraryError, safe_io.DamagedFile, OSError) as e:
        print(f"  ! the list of libraries can't be read: {e}")
        return {"mode": "test" if libraries.is_test_library(LIBRARY) else "personal",
                "label": LIBRARY.name, "path": str(LIBRARY), "key": ""}  # fmt: skip


def libraries_api(path: str, body: dict) -> dict:
    """The library list (Switch library / 切换书库): /api/libraries[/<action>]. Errors come
    back as {"error"} with the folder named in full: it's one you chose, on this computer."""
    action = path.removeprefix("/api/libraries").strip("/")
    key, folder = str(body.get("key") or ""), str(body.get("folder") or "").strip()
    label = str(body.get("label") or "")
    try:
        if action == "":
            test = libraries.TEST_CANONICAL.joinpath("library.toml").is_file()
            listed, here = libraries.personal(), libraries.current(LIBRARY)
            return {"current": here, "personal": listed, "test_available": test}
        if action == "check":
            return {"check": libraries.check(folder)}
        if action == "register":
            return {"library": libraries.register(folder, label)}
        if action == "create":
            return {"library": libraries.create(folder, label)}
        if action == "rename":
            return {"library": libraries.rename(key, label)}
        if action == "unregister":
            return {"library": libraries.unregister(key)}
        if action == "relocate":
            return {"library": libraries.relocate(key, folder)}
        if action == "open":  # another server shows it; this one keeps running as it is
            if body.get("mode") == "test":
                return {"url": libraries.open_test()}
            return {"url": libraries.open_personal(key)}
    except (libraries.LibraryError, safe_io.DamagedFile) as e:
        return {"error": str(e)}
    except OSError as e:
        return {"error": f"{e.strerror or e}: {e.filename or ''}".strip(": ")}
    raise ValueError("unknown library action")


def restart_later(server) -> None:
    """Start a fresh server (it reads the new settings) once this one has let go of its port;
    the page reloads itself when the new one answers."""

    def go() -> None:
        time.sleep(0.5)  # let the answer reach the page first
        finish_jobs()  # os._exit below would otherwise cut running jobs off mid-write
        server.shutdown()
        server.server_close()
        args, skip = [], False
        for arg in sys.argv[1:]:  # an explicit --library would win over the new setting
            if skip:
                skip = False
            elif arg == "--library":
                skip = True
            elif not arg.startswith("--library=") and arg != "--no-browser":
                args.append(arg)
        subprocess.Popen([sys.executable, sys.argv[0], *args, "--no-browser"], cwd=paths.APP)
        os._exit(0)

    threading.Thread(target=go, daemon=True).start()


def finish_jobs(timeout: float = 120) -> None:
    """Before the process ends: running jobs reach a safe point and file writes finish
    (library_jobs.shutdown); says what's going on, as it can take a moment."""
    running = [j["file"] for j in library_jobs.list_jobs() if j["status"] == "working"]
    if running:
        print(f"Finishing {len(running)} running job(s) first: {', '.join(running)}")
    result = library_jobs.shutdown(timeout)
    if result["unfinished"]:
        print(f"  ! still running, stopped between steps: {', '.join(result['unfinished'])}")


def stop(server) -> None:
    """Quit: finish the jobs safely, then stop serving (main() returns)."""
    finish_jobs()
    server.shutdown()


def start_setup(parts: list[str], download: bool = True) -> threading.Thread | None:
    """Fetch what the reading view still lacks (PDF.js, the dictionary) in the background,
    unless downloads are off (--no-download): then books open as plain PDFs and lookups find
    only the glossaries."""
    if not parts:
        return None
    if not download:
        effects = {"PDF viewer": "books open as plain PDFs", "dictionary": "no dictionary lookups",
                   "notes preview": "the notes' preview shows the plain text",
                   "maths": "the notes' preview shows formulas as written"}  # fmt: skip
        effect = "; ".join(effects[p] for p in parts if p in effects)
        print(f"Not downloading {' + '.join(parts)} (--no-download): {effect}.")
        return None
    print(f"Setting up the reading view ({' + '.join(parts)}, one-time download ~72 MB);")
    print("  until it's ready, books open as plain PDFs.")
    thread = threading.Thread(target=setup_reader, daemon=True)
    thread.start()
    return thread


def setup_reader() -> None:
    try:
        reading_view.setup()
        print("Reading view ready: reload the library page.")
    except Exception as e:
        print(f"  ! reading view setup failed ({e}); try: uv run scripts/reader.py --setup")


class Server(ThreadingHTTPServer):
    # On Windows SO_REUSEADDR lets a second server share the port and steal requests
    allow_reuse_address = sys.platform != "win32"
    # Connections waiting to be accepted (listen backlog). The default, 5, is too few: a reader
    # page opens about 25 at once (PDF.js, its icons, the reader's scripts, the notes' first
    # requests), and Windows refuses the ones that don't fit (seen in CI: a reload's
    # /api/notes/list refused, so the panel showed no note)
    request_queue_size = 64


def already_running(port: int) -> str | None:
    """The library folder of the myLibrary server answering on this port ("" if it doesn't
    say), or None when there is none."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as response:
            if not response.headers.get("Server", "").startswith(Handler.server_version):
                return None
            return unquote(response.headers.get("X-myLibrary-Library", ""))
    except OSError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="never download the reading view or dictionary at start (tests, offline use)",
    )
    paths.add_argument(parser)
    args = parser.parse_args()
    if args.no_download:  # the servers this one starts (another library) stay offline too
        libraries.SERVER_ARGS.append("--no-download")
    paths.ensure_library()
    # The library's lock, before anything else touches it (recovery included): a second
    # server of this library, started at the same moment, opens the first one instead (L15)
    global _LIBRARY_LOCK
    _LIBRARY_LOCK, holder = libraries.hold_or_find(LIBRARY)
    if _LIBRARY_LOCK is None:
        if holder is not None:
            print(f"myLibrary already shows this library at http://127.0.0.1:{holder}; opening it.")
            if not args.no_browser:
                webbrowser.open(f"http://127.0.0.1:{holder}")
            return
        sys.exit(
            "This library is in use by another myLibrary that doesn't answer on any known port "
            "(still starting, or started with an unusual --port). Quit it first, or wait and "
            "try again."
        )
    if problem := startup_problem():
        sys.exit(problem)
    for done in add_book.recover_operations():  # a rename an interruption left halfway
        print(f"  {done}")

    url = f"http://127.0.0.1:{args.port}"
    # Already shown by a server on another port: open that one (two servers must never write
    # the same library: their file locks don't see each other)
    if (elsewhere := libraries.find_server(LIBRARY, skip=args.port)) is not None:
        print(f"myLibrary already shows this library at http://127.0.0.1:{elsewhere}; opening it.")
        if not args.no_browser:
            webbrowser.open(f"http://127.0.0.1:{elsewhere}")
        return
    if (running := already_running(args.port)) is not None:
        if not running or Path(running).resolve() != LIBRARY.resolve():
            sys.exit(
                f"Another myLibrary is running at {url} with a different library"
                f" ({running or 'an older version'}).\n"
                f"Quit it from its page (Quit), or start this one with --port {args.port + 1}."
            )
        print(f"myLibrary is already running at {url}; opening it.")
        if not args.no_browser:
            webbrowser.open(url)
        return
    try:
        server = Server(("127.0.0.1", args.port), Handler)
    except OSError as e:
        sys.exit(f"Port {args.port} is used by another program ({e}); try --port 8766")
    url = f"http://127.0.0.1:{server.server_port}"
    libraries.note_port(LIBRARY, server.server_port)
    print(f"myLibrary at {url}  (Ctrl+C to stop)")
    threading.Thread(target=warm_cache, daemon=True).start()
    threading.Thread(target=auto_backup, daemon=True).start()
    start_setup(reading_view.missing(), download=not args.no_download)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
        finish_jobs(timeout=30)


if __name__ == "__main__":
    main()
