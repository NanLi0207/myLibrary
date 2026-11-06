"""Local reading server for myLibrary.

    uv run scripts/library_server.py          # opens http://127.0.0.1:8765 in your browser

"Read" / "Continue" on a book (or "Read" on one chapter) opens everything for that chapter:
  - the PDF in the browser, at the page where the chapter starts
  - in VS Code (the project window): the chapter's notes file, and its Python script
    examples/<slug>/chNN_<topic>.py if you have made one
"Script" on a chapter creates that script (from a short template) and opens it: a place to
check the book's worked examples in Python.
Ticking a chapter on the page writes "- [x]" into notes/<slug>/README.md.

PDFs open in the reading view (PDF.js + word lookup, see reader.py): double-click a word
for its glossary / dictionary meaning in Chinese, and save it to notes/<slug>/vocabulary.md.

Only listens on 127.0.0.1, and every action needs the token embedded in the page,
so other websites can't trigger it. Stop with Ctrl+C.
"""

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

import backup
import book_search
import catalog
import find_online
import library_jobs
import library_page
import paths
import reader as reading_view
from add_book import short_title
from book_ocr import has_text_layer
from book_toc import CHAPTER_TITLE_RE, contents_pages, scanned_chapter_pages, tidy
from pypdf import PdfReader

LIBRARY = paths.LIBRARY
CATALOG = LIBRARY / "catalog.csv"
CACHE = LIBRARY / ".cache" / "chapter_pages.json"
TOKEN = secrets.token_urlsafe(24)

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


def chapter_page(slug: str, number: int | None, chapters: list[dict]) -> int | None:
    if number is None:
        return None
    # One lookup per book at a time: the background warm-up and a Read click shouldn't both
    # run the (slow) search for the same book
    with _cache_lock:
        book_lock = _book_locks.setdefault(slug, threading.Lock())
    with book_lock:
        with _cache_lock:
            cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
        if slug not in cache:
            pdf = LIBRARY / catalog.load(CATALOG)[slug]["file"]
            if not pdf.exists():
                return None  # PDF deleted: notes and scripts still open, just no page
            found = find_chapter_pages(pdf, chapters)
            with _cache_lock:
                cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
                cache[slug] = {str(k): v for k, v in found.items()}
                CACHE.parent.mkdir(exist_ok=True)
                CACHE.write_text(json.dumps(cache, indent=1), encoding="utf-8")
    # Not found (e.g. OCR-garbled title): start of the nearest earlier chapter is close enough
    known = {int(k): v for k, v in cache[slug].items() if int(k) <= number}
    return known[max(known)] if known else None


def warm_cache() -> None:
    """Find chapter pages for every book in the background, so the first Read is quick;
    also bring the full-text index (在我的书中 / In my books) up to date."""
    try:
        if n := book_search.update():
            print(f"  full-text index updated ({n} book{'s' if n > 1 else ''})")
    except Exception as e:
        print(f"  ! couldn't update the full-text index: {e}")
    for slug in catalog.load(CATALOG):
        try:
            chapter_page(slug, 1, library_page.chapters(slug))
        except Exception as e:  # one damaged PDF shouldn't stop the others
            print(f"  ! couldn't find chapter pages for {slug}: {e}")


# --- chapter scripts ----------------------------------------------------------------------

SCRIPT_TEMPLATE = '''"""{book}
{chapter}

Check this chapter's worked examples in Python: recompute a result, then compare it with the
book's answer. Run it with VS Code's Run button, or in a terminal:

    uv run {path}

Notes for this chapter: notes/{slug}/{note}
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


def script_for(slug: str, chapter: dict, book_title: str, create: bool = False) -> Path | None:
    """examples/<slug>/chNN_<topic>.py: the existing one, or with create, a new one from the
    template. None if there's none and create is False."""
    folder = LIBRARY / "examples" / slug
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
            book=safe(book_title),
            chapter=safe(chapter["title"]),
            path=paths.display(path),
            slug=slug,
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
        if code:
            subprocess.Popen([code, str(paths.WORKSPACE), *map(str, files)], cwd=paths.WORKSPACE)
            return True
        editor = "system"  # VS Code isn't installed (any more): fall back
    try:
        for f in files:
            command = settings.get("editor_command", "").strip()
            if editor == "custom" and command:
                if "{file}" not in command:
                    command += ' "{file}"'
                subprocess.Popen(command.replace("{file}", str(f)))
            elif editor == "notepad" or f.suffix == ".py":
                # never "open" a .py with its default app: on Windows that can *run* it
                subprocess.Popen(["notepad.exe", str(f)])
            elif hasattr(os, "startfile"):
                os.startfile(f)  # Windows: the app set for .md files (e.g. Typora, Notepad)
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(f)])
        return True
    except OSError:
        return False


def python_features() -> bool:
    """Chapter scripts (checking a book's examples in Python): off in the package."""
    return bool(paths.load_settings().get("python_features"))


def pick_folder() -> str | None:
    """Ask for a folder with Windows' own folder dialog (the server runs on this computer)."""
    if sys.platform != "win32":
        return None
    script = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$owner = New-Object System.Windows.Forms.Form -Property @{TopMost = $true};"
        "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
        "$d.Description = 'Choose the folder for your library (books and notes)';"
        "$d.ShowNewFolderButton = $true;"
        "if ($d.ShowDialog($owner) -eq 'OK') { $d.SelectedPath }"
    )
    done = subprocess.run(
        ["powershell", "-NoProfile", "-STA", "-Command", script],
        capture_output=True,
        text=True,
        timeout=900,
    )
    return done.stdout.strip() or None


def change_settings(updates: dict) -> dict:
    """Save settings from the page; a new library folder is created if it doesn't exist."""
    clean = {}
    if "editor" in updates:
        clean["editor"] = str(updates["editor"])
    if "editor_command" in updates:
        clean["editor_command"] = str(updates["editor_command"])[:500]
    if "python_features" in updates:
        clean["python_features"] = bool(updates["python_features"])
    restart = False
    if updates.get("library"):
        folder = Path(str(updates["library"])).expanduser()
        if not folder.is_absolute():
            raise ValueError("choose a full folder path, e.g. D:\\Study\\My Library")
        if folder.resolve() != LIBRARY.resolve():
            paths.ensure_library(folder)
            clean["library"] = folder.as_posix()
            restart = True
    paths.save_settings(clean)
    return {"restart": restart}


# --- actions ------------------------------------------------------------------------------


def pdf_url(base_url: str, file: str, page: int | None = None) -> str:
    """The reading view (PDF.js + word lookup) once it's set up, else the bare PDF; `file` is
    the catalog's path in the library, books/, papers/ or theses/<slug>.pdf."""
    if reading_view.missing():
        url = f"{base_url}/{file}"
    else:
        url = f"{base_url}/pdfjs/web/viewer.html?file=/{file}"
    return url + (f"#page={page}" if page else "")


def chapter_at(slug: str, page: int, chapters: list[dict]) -> dict | None:
    """The chapter that page belongs to: the last one starting on or before it."""
    chapter_page(slug, 1, chapters)  # makes sure the book's chapter pages are cached
    with _cache_lock:
        cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    starts = {int(n): p for n, p in cache.get(slug, {}).items() if p <= page}
    if not starts:
        return None
    number = max(starts, key=lambda n: (starts[n], n))
    return next((c for c in chapters if c["number"] == number), None)


def save_position(slug: str, page: int) -> dict:
    """Write "Last read: page N (Ch k: ...), date" under "## Reading progress" in the README."""
    readme = LIBRARY / "notes" / slug / "README.md"
    if not readme.exists():
        return {}
    is_paper = catalog.load(CATALOG).get(slug, {}).get("type") == "paper"
    chapter = None if is_paper else chapter_at(slug, page, library_page.chapters(slug))
    line = f"Last read: page {page}" + (f" ({chapter['title']})" if chapter else "")
    line += f", {date.today().isoformat()}"
    text = readme.read_text(encoding="utf-8")
    new, count = library_page.LAST_READ_RE.subn(lambda _: line, text, count=1)
    if not count:
        heading = re.search(r"^## Reading progress[ \t]*\n(?:[ \t]*\n)?", text, re.MULTILINE)
        if heading:
            rest = text[heading.end() :].lstrip("\n")
            new = text[: heading.end()] + line + "\n\n" + rest
        else:
            new = text.rstrip("\n") + "\n\n" + line + "\n"
    if new != text:
        readme.write_text(new, encoding="utf-8")
    return library_page.last_read(slug) or {}


def open_chapter(slug: str, number: int | None, base_url: str, resume: bool = False) -> str:
    """Open a chapter (PDF at its first page, notes, and its script if there is one); with
    resume, open the page you last read and the chapter it belongs to."""
    row = catalog.load(CATALOG)[slug]
    chapters = library_page.chapters(slug)
    last = library_page.last_read(slug) if resume else None
    is_paper = row.get("type") == "paper"
    if last and not is_paper:
        chapter = chapter_at(slug, last["page"], chapters)
    else:
        chapter = next((c for c in chapters if c["number"] == number), None)
    if is_paper:  # its one item, "Read the paper", whose notes are notes.md
        chapter = next((c for c in chapters if c["number"] == 1), None)
    notes_dir = LIBRARY / "notes" / slug
    opened = []

    if (LIBRARY / row["file"]).exists():
        if last:
            page = last["page"]
        elif is_paper:
            page = 1
        else:
            page = chapter_page(slug, chapter["number"], chapters) if chapter else None
        webbrowser.open(pdf_url(base_url, row["file"], page))
        opened.append(f"PDF (p. {page})" if page else "PDF")
    else:
        opened.append(f"no PDF ({row['file']} is missing)")

    note = notes_dir / chapter["note"] if chapter and chapter["note"] else notes_dir / "README.md"
    if not note.exists():
        note = notes_dir / "README.md"
    files = [note]
    script = script_for(slug, chapter, row["title"]) if chapter and python_features() else None
    if script:
        files.append(script)
    if open_in_editor(*files):
        opened.append(f"notes and script {script.name}" if script else "notes")
    else:
        opened.append("no notes: the editor couldn't be started (see Settings)")

    what = chapter["title"] if chapter else row["title"]
    if last:
        what = f"Continuing at page {last['page']}" + (f" ({chapter['title']})" if chapter else "")
    return f"{what}: opened " + ", ".join(opened)


def open_script(slug: str, number: int) -> str:
    """The chapter's Python script, created from the template the first time, in VS Code."""
    row = catalog.load(CATALOG)[slug]
    chapter = next((c for c in library_page.chapters(slug) if c["number"] == number), None)
    if chapter is None:
        raise ValueError(f"no chapter {number}")
    path = script_for(slug, chapter, row["title"], create=True)
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
    path = LIBRARY / "notes" / "topics" / f"{name}.md"
    if not path.exists():
        found = book_search.search(term, limit=8)["results"]
        sources = "\n".join(f"- {r['title']}: PDF page {r['page']}" for r in found) or "-"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(TOPIC_TEMPLATE.format(term=term, sources=sources), encoding="utf-8")
    return path


def open_topic(term: str) -> dict:
    path = topic_note(term)
    where = paths.display(path)
    opened = open_in_editor(path)
    return {"file": where, "opened": opened}


def tick(slug: str, number: int, done: bool) -> list[dict]:
    readme = LIBRARY / "notes" / slug / "README.md"
    text = readme.read_text(encoding="utf-8")
    paper = rf"|\[{re.escape(library_page.PAPER_ITEM)}\]" if number == 1 else ""
    pattern = re.compile(rf"^- \[[ xX]\] (\[?Ch(?:apter)?\.?\s*{number}:{paper})", re.MULTILINE)
    new, count = pattern.subn(lambda m: f"- [{'x' if done else ' '}] {m[1]}", text, count=1)
    if not count:
        raise ValueError(f"chapter {number} not found in {readme.name}")
    readme.write_text(new, encoding="utf-8")
    return library_page.chapters(slug)


# --- HTTP ---------------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    server_version = "myLibrary"

    def log_message(self, format, *args):  # keep the terminal quiet
        pass

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    def _local_host(self) -> bool:
        # Blocks DNS-rebinding: a page on another site can't pretend to be us
        return self.headers.get("Host", "").split(":")[0] in {"127.0.0.1", "localhost"}

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: dict) -> None:
        self._send(status, json.dumps(data).encode(), "application/json")

    def do_GET(self):
        if not self._local_host():
            return self._send(HTTPStatus.FORBIDDEN, b"forbidden", "text/plain")
        path = self.path.split("?")[0].split("#")[0]
        if path in ("/", "/index.html"):
            # library_page appends "/<file>.pdf" to pdf_base
            pdf_base = pdf_url(self.base_url, "").removesuffix("/")
            api = {"token": TOKEN, "python": python_features(), "package": paths.IS_PACKAGE,
                   "backup": backup.available()}  # fmt: skip
            html = library_page.render(api, pdf_base=pdf_base)
            return self._send(HTTPStatus.OK, html.encode(), "text/html; charset=utf-8")
        if path == "/pdfjs/web/viewer.html" and not reading_view.missing():
            html = reading_view.viewer_html(TOKEN)
            return self._send(HTTPStatus.OK, html, "text/html; charset=utf-8")
        if found := reading_view.static_file(path):
            return self._send(HTTPStatus.OK, *found)
        if m := re.fullmatch(r"/((?:books|papers|theses)/[a-z0-9-]+\.pdf)", path):
            known = {r["file"] for r in catalog.load(CATALOG).values()}
            pdf = LIBRARY / m[1]
            if m[1] in known and pdf.exists():
                return self._send(HTTPStatus.OK, pdf.read_bytes(), "application/pdf")
        self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")

    def do_POST(self):
        if not self._local_host() or self.headers.get("X-Library-Token") != TOKEN:
            return self._json(HTTPStatus.FORBIDDEN, {"error": "forbidden"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            if self.path == "/api/upload":  # a PDF from "Add books": raw bytes, not JSON
                if length > library_jobs.MAX_UPLOAD:
                    return self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "too big"})
                name = unquote(self.headers.get("X-Filename", "book.pdf"))
                path = library_jobs.save_upload(name, self.rfile.read(length))
                return self._json(HTTPStatus.OK, {"job": library_jobs.start_add(path)})
            body = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/api/books":  # the page refreshes itself after reading
                pdf_base = pdf_url(self.base_url, "").removesuffix("/")
                return self._json(HTTPStatus.OK, {"books": library_page.books(pdf_base)})
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
                try:
                    url, title = str(body.get("url", "")), str(body.get("title", ""))[:200]
                    job = library_jobs.start_download(url, title)
                except ValueError as e:
                    return self._json(HTTPStatus.BAD_REQUEST, {"error": str(e)})
                return self._json(HTTPStatus.OK, {"job": job})
            if self.path == "/api/add-details":
                details = {k: str(body.get(k, ""))[:200] for k in ("title", "author", "year")}
                job = library_jobs.continue_add(str(body.get("job", "")), details)
                return self._json(HTTPStatus.OK, {"job": job})
            if self.path == "/api/settings":
                if isinstance(body.get("save"), dict):
                    result = change_settings(body["save"])
                    if result["restart"]:
                        restart_later(self.server)
                    return self._json(HTTPStatus.OK, result)
                settings = paths.load_settings() | {"library": str(LIBRARY)}
                return self._json(
                    HTTPStatus.OK,
                    {"settings": settings, "editors": paths.EDITORS, "package": paths.IS_PACKAGE},
                )
            if self.path == "/api/pick-folder":
                return self._json(HTTPStatus.OK, {"folder": pick_folder()})
            if self.path == "/api/quit":
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return self._json(HTTPStatus.OK, {"message": "myLibrary has stopped"})
            if self.path == "/api/lookup":
                text, context = str(body.get("text", "")), str(body.get("context", ""))[:1000]
                book = body.get("slug") if isinstance(body.get("slug"), str) else None
                return self._json(HTTPStatus.OK, reading_view.lookup(text, context, book))
            if self.path == "/api/search":
                current = body.get("slug") if isinstance(body.get("slug"), str) else None
                found = book_search.search(str(body.get("text", ""))[:100], current)
                return self._json(HTTPStatus.OK, found)
            if self.path == "/api/topic":
                try:
                    return self._json(HTTPStatus.OK, open_topic(str(body.get("text", ""))))
                except ValueError as e:
                    return self._json(HTTPStatus.BAD_REQUEST, {"error": str(e)})
            if self.path == "/api/glossary":
                term, zh, definition = (
                    str(body.get(k, ""))[:1000] for k in ("term", "zh", "definition")
                )
                name = body.get("glossary") if isinstance(body.get("glossary"), str) else None
                try:
                    added = reading_view.add_glossary_term(
                        term, zh, definition, glossary_name=name or None
                    )
                except ValueError as e:
                    return self._json(HTTPStatus.BAD_REQUEST, {"error": str(e)})
                return self._json(HTTPStatus.OK, added)
            slug = body.get("slug")
            if slug not in catalog.load(CATALOG):
                return self._json(HTTPStatus.NOT_FOUND, {"error": "unknown book"})
            chapter = body.get("chapter")
            if chapter is not None and not isinstance(chapter, int):
                return self._json(HTTPStatus.BAD_REQUEST, {"error": "bad chapter"})
            if self.path == "/api/open":
                resume = body.get("resume") is True
                message = open_chapter(slug, chapter, self.base_url, resume)
                return self._json(HTTPStatus.OK, {"message": message})
            if self.path == "/api/open-notes":
                notes = LIBRARY / "notes" / slug / "README.md"
                if (notes.parent / "notes.md").exists():  # a paper: its one notes file
                    notes = notes.parent / "notes.md"
                if open_in_editor(notes):
                    message = "opened the notes"
                else:
                    message = "the editor couldn't be started (see Settings)"
                return self._json(HTTPStatus.OK, {"message": message})
            if self.path == "/api/ocr":
                return self._json(HTTPStatus.OK, {"job": library_jobs.start_ocr(slug)})
            if self.path == "/api/script" and chapter is not None:
                if not python_features():
                    return self._json(HTTPStatus.BAD_REQUEST, {"error": "Python features are off"})
                return self._json(HTTPStatus.OK, {"message": open_script(slug, chapter)})
            if self.path == "/api/shelves":
                shelves = catalog.split_list(str(body.get("shelves", ""))[:300])
                if len(shelves) > 12 or any(len(s) > 40 for s in shelves):
                    return self._json(HTTPStatus.BAD_REQUEST, {"error": "too many or too long"})
                catalog.set_field(CATALOG, slug, "shelves", "; ".join(shelves))
                library_page.build()  # keep the static copy in step
                return self._json(HTTPStatus.OK, {"shelves": shelves})
            if self.path == "/api/position":
                page = body.get("page")
                if not isinstance(page, int) or page < 1:
                    return self._json(HTTPStatus.BAD_REQUEST, {"error": "bad page"})
                return self._json(HTTPStatus.OK, {"last_read": save_position(slug, page)})
            if self.path == "/api/save-word":
                page = body.get("page")
                saved = reading_view.save_word(
                    slug,
                    catalog.load(CATALOG)[slug]["title"],
                    str(body.get("text", "")),
                    str(body.get("context", ""))[:1000],
                    page if isinstance(page, int) else None,
                )
                return self._json(HTTPStatus.OK, saved)
            if self.path == "/api/tick" and chapter is not None:
                chapters = tick(slug, chapter, bool(body.get("done")))
                library_page.build()  # keep the static copy in step
                return self._json(HTTPStatus.OK, {"chapter_list": chapters})
            self._json(HTTPStatus.NOT_FOUND, {"error": "unknown action"})
        except ValueError as e:  # something the page sent that can't be done
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(e)})
        except Exception as e:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(e)})


def restart_later(server) -> None:
    """Start a fresh server (it reads the new settings) once this one has let go of its port;
    the page reloads itself when the new one answers."""

    def go() -> None:
        time.sleep(0.5)  # let the answer reach the page first
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


def setup_reader() -> None:
    try:
        reading_view.setup()
        print("Reading view ready: reload the library page.")
    except Exception as e:
        print(f"  ! reading view setup failed ({e}); try: uv run scripts/reader.py --setup")


class Server(ThreadingHTTPServer):
    # On Windows SO_REUSEADDR lets a second server share the port and steal requests
    allow_reuse_address = sys.platform != "win32"


def already_running(port: int) -> bool:
    """Is a myLibrary server answering on this port?"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as response:
            return response.headers.get("Server", "").startswith(Handler.server_version)
    except OSError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    paths.add_argument(parser)
    args = parser.parse_args()
    paths.ensure_library()

    url = f"http://127.0.0.1:{args.port}"
    if already_running(args.port):
        print(f"myLibrary is already running at {url}; opening it.")
        if not args.no_browser:
            webbrowser.open(url)
        return
    try:
        server = Server(("127.0.0.1", args.port), Handler)
    except OSError as e:
        sys.exit(f"Port {args.port} is used by another program ({e}); try --port 8766")
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"myLibrary at {url}  (Ctrl+C to stop)")
    threading.Thread(target=warm_cache, daemon=True).start()
    if parts := reading_view.missing():
        print(f"Setting up the reading view ({' + '.join(parts)}, one-time download ~72 MB);")
        print("  until it's ready, books open as plain PDFs.")
        threading.Thread(target=setup_reader, daemon=True).start()
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")


if __name__ == "__main__":
    main()
