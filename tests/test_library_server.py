import io
import json
import socket
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import library_page
import library_server
import pytest
from testlib import entry, id_of, put  # noqa: F401

NAME = "doe-2015-practical-lens-design"


def doc(library) -> str:
    """The one book's id."""
    return id_of(library / "catalog.csv", NAME)


README = """# Practical Lens Design

## Reading progress

- [ ] [Ch 1: Basics](ch01-basics.md)
- [ ] [Ch 2: Aberrations](ch02-aberrations.md)

## Notes
"""


@pytest.fixture
def library(tmp_path, monkeypatch):
    """A one-book library in a temporary folder."""
    for module in (library_server, library_page):
        monkeypatch.setattr(module, "LIBRARY", tmp_path)
        monkeypatch.setattr(module, "CATALOG", tmp_path / "catalog.csv")
    notes = tmp_path / "notes" / "doe-2015-practical-lens-design"
    notes.mkdir(parents=True)
    (notes / "README.md").write_text(README, encoding="utf-8")
    put(
        tmp_path / "catalog.csv",
        {
            "slug": "doe-2015-practical-lens-design",
            "title": "Practical Lens Design",
            "file": "books/doe-2015-practical-lens-design.pdf",
            "notes": "notes/doe-2015-practical-lens-design/",
        },
    )
    return tmp_path


def test_tick_round_trip(library):
    chapters = library_server.tick(doc(library), 2, True)
    assert [c["done"] for c in chapters] == [False, True]
    chapters = library_server.tick(doc(library), 2, False)
    assert [c["done"] for c in chapters] == [False, False]


def test_chapter_script_created_only_when_asked(library):
    chapter = library_page.chapters(doc(library))[1]
    row = entry(library / "catalog.csv", NAME)
    assert library_server.script_for(row, chapter) is None  # Read doesn't create one
    row["title"] = 'A "Book" with C:\\paths and """quotes"""'
    script = library_server.script_for(row, chapter, create=True)
    assert script == library / "examples" / NAME / "ch02_aberrations.py"
    # Asking again returns the same file instead of overwriting it
    script.write_text(script.read_text(encoding="utf-8") + "# my edits\n", encoding="utf-8")
    again = library_server.script_for(row, chapter, create=True)
    assert again == script and "# my edits" in again.read_text(encoding="utf-8")
    # The template runs as it is, and passes the linter (no unused imports)
    run = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    lint = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--isolated", str(script)],
        capture_output=True,
        text=True,
    )
    assert lint.returncode == 0, lint.stdout


def test_http_requires_token(library):
    server = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"

    def post(path, body, token=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Library-Token"] = token
        request = urllib.request.Request(
            base + path, data=json.dumps(body).encode(), headers=headers, method="POST"
        )
        return urllib.request.urlopen(request, timeout=5)

    try:
        page = urllib.request.urlopen(base + "/", timeout=5).read().decode()
        assert library_server.TOKEN in page and "Practical Lens Design" in page

        tick = {"id": doc(library), "chapter": 1, "done": True}
        with pytest.raises(urllib.error.HTTPError) as denied:
            post("/api/tick", tick)
        assert denied.value.code == 403

        result = json.load(post("/api/tick", tick, library_server.TOKEN))
        assert result["chapter_list"][0]["done"] is True

        with pytest.raises(urllib.error.HTTPError) as unknown:
            post("/api/open", {"id": "../../secret", "chapter": 1}, library_server.TOKEN)
        assert unknown.value.code == 404
        with pytest.raises(urllib.error.HTTPError) as by_name:  # names identify nothing now
            post("/api/tick", tick | {"id": NAME}, library_server.TOKEN)
        assert by_name.value.code == 404
    finally:
        server.shutdown()


def test_marks_cut_short_are_refused(library, monkeypatch):
    """The tab closed while the marked PDF was being sent: the book stays as it was."""
    from pypdf import PdfWriter

    monkeypatch.setattr(library_server.reading_view, "LIBRARY", library)
    pdf = library / "books" / f"{NAME}.pdf"
    pdf.parent.mkdir()
    writer = PdfWriter()
    writer.add_blank_page(200, 200)
    buffer = io.BytesIO()
    writer.write(buffer)
    original = buffer.getvalue()
    pdf.write_bytes(original)
    # An incremental save: the original plus a short update (its own %%EOF is near the end)
    marked = original + b"\n1 0 obj\n<< /Marks true >>\nendobj\n" + b"x" * 400 + b"\n%%EOF\n"
    sent = marked[: len(original) + 60]  # cut off inside the update

    server = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with socket.create_connection(("127.0.0.1", server.server_port), timeout=5) as s:
            head = (
                "POST /api/save-marks HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                f"X-Library-Token: {library_server.TOKEN}\r\nX-Document-Id: {doc(library)}\r\n"
                f"Content-Type: application/pdf\r\nContent-Length: {len(marked)}\r\n\r\n"
            )
            s.sendall(head.encode() + sent)
            s.shutdown(socket.SHUT_WR)  # the browser went away
            answer = b""
            while chunk := s.recv(4096):
                answer += chunk
        assert answer.startswith(b"HTTP/1.0 400 ") and b"cut short" in answer
        assert pdf.read_bytes() == original
        assert not (library / "archive").exists()
    finally:
        server.shutdown()


def test_marks_saves_name_their_version_over_http(library, monkeypatch):
    """D5 at the server: X-PDF-Version is required and checked; a stale one gives 409 with
    where the tab's PDF is kept; X-PDF-Unconfirmed names the tab's own unanswered save;
    X-Marks-Action: keep-copy only keeps a copy."""
    import hashlib

    from pypdf import PdfWriter

    monkeypatch.setattr(library_server.reading_view, "LIBRARY", library)

    def pdf(note: str) -> bytes:
        writer = PdfWriter()
        writer.add_blank_page(200, 200)
        writer.add_metadata({"/Subject": note})
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    def sha(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    book = library / "books" / f"{NAME}.pdf"
    book.parent.mkdir()
    loaded = pdf("as loaded")
    book.write_bytes(loaded)
    server = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def save(data: bytes, **headers):
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/save-marks", data=data, method="POST",
            headers={"X-Library-Token": library_server.TOKEN, "X-Document-Id": doc(library),
                     "Content-Type": "application/pdf", **headers},
        )  # fmt: skip
        try:
            with urllib.request.urlopen(request, timeout=10) as answer:
                return answer.status, json.load(answer)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    try:
        assert save(pdf("no version"))[0] == 400
        assert save(pdf("bad version"), **{"X-PDF-Version": "../etc"})[0] == 400
        first = pdf("first tab")
        status, answer = save(first, **{"X-PDF-Version": sha(loaded)})
        assert status == 200 and answer["version"] == sha(first) and book.read_bytes() == first
        stale = pdf("second tab")
        status, answer = save(stale, **{"X-PDF-Version": sha(loaded)})
        assert status == 409 and answer["conflict"] and answer["current"] == sha(first)
        assert (library / answer["kept"]).read_bytes() == stale and book.read_bytes() == first
        assert str(library) not in answer["error"]  # its place in the library only
        # The first tab's next save, its last answer lost: its own write, so it follows on it
        later = pdf("first tab, later")
        own = f"{sha(b'x')},{sha(first)}"
        status, answer = save(later, **{"X-PDF-Version": sha(loaded), "X-PDF-Unconfirmed": own})
        assert status == 200 and book.read_bytes() == later
        status, answer = save(pdf("more"), **{"X-PDF-Version": sha(loaded),
                                              "X-Marks-Action": "keep-copy"})  # fmt: skip
        assert status == 200 and (library / answer["kept"]).exists()
        assert book.read_bytes() == later  # a copy only
    finally:
        server.shutdown()


def test_missing_pdf_is_flagged_and_read_still_works(library, monkeypatch):
    opened = []
    monkeypatch.setattr(library_server.webbrowser, "open", opened.append)
    monkeypatch.setattr(library_server, "open_in_editor", lambda *files: True)

    assert library_page.books()[0]["pdf_missing"] is True
    message = library_server.open_chapter(doc(library), 1, "http://x")
    assert opened == []  # no browser tab for a PDF that isn't there
    assert "missing" in message and "notes" in message


@pytest.fixture
def chapter_pages(library, monkeypatch):
    """Chapter 1 starts on PDF page 5, chapter 2 on page 30 (as if already found)."""
    cache = library / ".cache" / "chapter_pages.json"
    cache.parent.mkdir()
    cache.write_text(json.dumps({doc(library): {"1": 5, "2": 30}}))
    monkeypatch.setattr(library_server, "CACHE", cache)
    return library


def test_save_position_writes_and_updates_one_line(chapter_pages):
    slug = doc(chapter_pages)
    readme = chapter_pages / "notes" / NAME / "README.md"
    assert library_page.last_read(slug) is None

    saved = library_server.save_position(slug, 12)
    assert saved["page"] == 12 and saved["chapter"] == "Ch 1: Basics"
    text = readme.read_text(encoding="utf-8")
    assert "## Reading progress\n\nLast read: page 12 (Ch 1: Basics), " in text

    library_server.save_position(slug, 31)
    text = readme.read_text(encoding="utf-8")
    assert text.count("Last read:") == 1 and "page 31 (Ch 2: Aberrations)" in text
    # The chapter checklist still reads the same
    titles = [c["title"] for c in library_page.chapters(slug)]
    assert titles == ["Ch 1: Basics", "Ch 2: Aberrations"]
    assert library_page.books()[0]["last_read"]["page"] == 31

    library_server.save_position(slug, 2)  # before chapter 1: no chapter named
    assert library_page.last_read(slug)["chapter"] == ""


def test_continue_opens_last_page_and_its_chapter(chapter_pages, monkeypatch):
    slug = doc(chapter_pages)
    # The reading view (PDF.js) is set up; a fresh checkout (CI) doesn't download it
    monkeypatch.setattr(library_server.reading_view, "viewer_ready", lambda: True)
    (chapter_pages / "books").mkdir()
    (chapter_pages / "books" / f"{NAME}.pdf").write_bytes(b"%PDF-1.4")
    (chapter_pages / "notes" / NAME / "ch02-aberrations.md").write_text("# Ch 2\n")
    opened, files = [], []
    monkeypatch.setattr(library_server.webbrowser, "open", opened.append)
    monkeypatch.setattr(library_server, "open_in_editor", lambda *f: files.extend(f) or True)

    library_server.save_position(slug, 33)
    message = library_server.open_chapter(slug, None, "http://x", resume=True)
    assert opened[0].endswith(f"{NAME}.pdf&id={slug}#page=33")  # the reader knows the id
    # The notes are in the reader's panel: no external editor as well (task 4 M4, D5)
    assert files == []
    assert message.startswith("Continuing at page 33 (Ch 2: Aberrations)")
    assert "📝 panel" in message

    # Once the chapter has a script ("Script" button), Continue opens it (only it)
    assert "examples/" in library_server.open_script(slug, 2)
    assert [f.name for f in files] == ["ch02_aberrations.py"]
    files.clear()
    library_server.open_chapter(slug, None, "http://x", resume=True)
    assert [f.name for f in files] == ["ch02_aberrations.py"]

    # Without the reading view (a plain PDF, no panel) the notes still open in the editor
    files.clear()
    monkeypatch.setattr(library_server.reading_view, "viewer_ready", lambda: False)
    library_server.open_chapter(slug, None, "http://x", resume=True)
    assert [f.name for f in files] == ["ch02-aberrations.md", "ch02_aberrations.py"]
    monkeypatch.setattr(library_server.reading_view, "viewer_ready", lambda: True)

    # A chapter's Read button still opens that chapter's first page
    opened.clear()
    library_server.open_chapter(slug, 1, "http://x")
    assert opened[0].endswith("#page=5")


def test_chapter_title_in_running_text_is_not_a_chapter_start(tmp_path):
    from reportlab.pdfgen import canvas

    tops = [
        "1 Basics",
        "12 Basics: the coma of symmetrical optical systems",  # chapter 3's title, mid-line
        "Design Forms",
        "Optical Systems",
    ]
    pdf = tmp_path / "book.pdf"
    c = canvas.Canvas(str(pdf))
    for top in tops:
        c.drawString(72, 720, top)
        for line in range(3):  # enough text to count as a text PDF, not a scan
            c.drawString(72, 680 - 20 * line, "Body text of the page, long enough to read.")
        c.showPage()
    c.save()
    chapters = [
        {"number": 1, "title": "Ch 1: Basics"},
        {"number": 2, "title": "Ch 2: Design Forms"},
        {"number": 3, "title": "Ch 3: Optical Systems"},
    ]
    assert library_server.find_chapter_pages(pdf, chapters) == {1: 1, 2: 3, 3: 4}


def test_topic_note_lists_pages_and_keeps_your_writing(library, monkeypatch):
    found = {
        "results": [
            {"id": "x", "title": "Practical Lens Design", "page": 7},
            {"id": "y", "title": "Optics", "page": 31},
        ]
    }
    monkeypatch.setattr(library_server.book_search, "search", lambda term, limit: found)
    opened = []
    monkeypatch.setattr(library_server, "open_in_editor", lambda *f: opened.extend(f) or True)

    result = library_server.open_topic("  Veiling  glare ")
    note = library / "notes" / "topics" / "veiling-glare.md"
    assert opened == [note] and result["opened"] is True
    text = note.read_text(encoding="utf-8")
    assert text.startswith("# Veiling glare\n")
    assert "- Practical Lens Design: PDF page 7\n- Optics: PDF page 31" in text

    note.write_text(text + "My own summary.\n", encoding="utf-8")
    library_server.open_topic("veiling glare")  # opening again never overwrites
    assert note.read_text(encoding="utf-8").endswith("My own summary.\n")
    with pytest.raises(ValueError):
        library_server.topic_note("杂光")  # needs an English term for the file name


def test_no_download_means_no_download(monkeypatch):
    """--no-download (tests, offline use): nothing is fetched at start."""
    started = []
    monkeypatch.setattr(library_server, "setup_reader", lambda: started.append(True))
    assert library_server.start_setup(["PDF viewer", "dictionary"], download=False) is None
    assert library_server.start_setup([], download=True) is None
    assert started == []
    library_server.start_setup(["dictionary"], download=True).join(5)
    assert started == [True]


@pytest.mark.parametrize("preview", [True, False], ids=["preview installed", "no preview"])
def test_without_the_dictionary_books_still_open_in_the_reader(
    library, monkeypatch, tmp_path, preview
):
    """The dictionary (ECDICT) is optional: when it is missing (a failed or pending download),
    books still open in the reading view, with the reader's own script injected, whether the
    notes' preview (markdown-it, also optional) is installed or not. Every optional part is
    this test's own, never the tool's .cache/reader (installed on one computer, not in CI)."""
    reading_view = library_server.reading_view
    pdfjs = tmp_path / "reader" / "pdfjs"
    (pdfjs / "web").mkdir(parents=True)
    (pdfjs / "web" / "viewer.html").write_text("<html><head></head><body></body></html>")
    markdown_it = tmp_path / "reader" / "markdown-it"
    if preview:  # installed as setup_preview() leaves it: the file and its verified marker
        markdown_it.mkdir(parents=True)
        (markdown_it / "markdown-it.min.js").write_text("/* markdown-it */", encoding="utf-8")
        (markdown_it / reading_view.MARKDOWN_IT_MARKER).write_text(
            f"{reading_view.MARKDOWN_IT_VERSION}\n{reading_view.MARKDOWN_IT_SHA256}\n",
            encoding="utf-8",
        )
    monkeypatch.setattr(reading_view, "PDFJS", pdfjs)
    monkeypatch.setattr(reading_view, "DICT_DB", tmp_path / "no-dictionary.db")
    monkeypatch.setattr(reading_view, "MARKDOWN_IT", markdown_it)
    assert bool(reading_view.markdown_it_installed()) is preview
    assert "dictionary" in reading_view.missing()
    assert reading_view.missing() == ["dictionary"] + ([] if preview else ["notes preview"])
    assert reading_view.viewer_ready()  # the dictionary isn't needed to read
    url = library_server.pdf_url("http://x", "books/a.pdf", 3, doc(library))
    assert url == f"http://x/pdfjs/web/viewer.html?file=/books/a.pdf&id={doc(library)}#page=3"

    server = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        address = f"http://127.0.0.1:{server.server_port}/pdfjs/web/viewer.html"
        with urllib.request.urlopen(address, timeout=5) as page:
            html = page.read()
        assert b"/reader/lookup.js" in html and b"/reader/notes.js" in html
        assert (b"/vendor/markdown-it/markdown-it.min.js" in html) is preview
    finally:
        server.shutdown()


def test_an_unexpected_errors_message_shows_no_folders():
    """A 500's message for the page: absolute paths cut to the file's name (the full path and
    the traceback stay in the server's log); a helpful message stays as it is."""
    long = r"\\?\C:\Users\me\OneDrive\Documents\myLibrary\archive\notes-conflicts\ch01.x.md.tmp"
    cases = {
        f"[WinError 3] The system cannot find the path specified: '{long}'":
            "[WinError 3] The system cannot find the path specified: 'ch01.x.md.tmp'",
        r"[Errno 2] No such file or directory: 'C:\Users\me\library\notes\ch01-basics.md'":
            "[Errno 2] No such file or directory: 'ch01-basics.md'",
        r"cannot open \\server\share\library\catalog.csv": "cannot open catalog.csv",
        "catalog.csv is open in another program (Excel, a PDF viewer…) that doesn't let it be "
        "used; close it and try again":
            "catalog.csv is open in another program (Excel, a PDF viewer…) that doesn't let it "
            "be used; close it and try again",
    }  # fmt: skip
    for message, shown in cases.items():
        assert library_server.shown_error(OSError(message)) == shown
