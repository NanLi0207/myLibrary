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
    (chapter_pages / "books").mkdir()
    (chapter_pages / "books" / f"{NAME}.pdf").write_bytes(b"%PDF-1.4")
    (chapter_pages / "notes" / NAME / "ch02-aberrations.md").write_text("# Ch 2\n")
    opened, files = [], []
    monkeypatch.setattr(library_server.webbrowser, "open", opened.append)
    monkeypatch.setattr(library_server, "open_in_editor", lambda *f: files.extend(f) or True)

    library_server.save_position(slug, 33)
    message = library_server.open_chapter(slug, None, "http://x", resume=True)
    assert opened[0].endswith(f"{NAME}.pdf&id={slug}#page=33")  # the reader knows the id
    assert [f.name for f in files] == ["ch02-aberrations.md"]  # no script made for this chapter
    assert message.startswith("Continuing at page 33 (Ch 2: Aberrations)")

    # Once the chapter has a script ("Script" button), Continue opens it too
    files.clear()
    assert "examples/" in library_server.open_script(slug, 2)
    assert [f.name for f in files] == ["ch02_aberrations.py"]
    files.clear()
    library_server.open_chapter(slug, None, "http://x", resume=True)
    assert [f.name for f in files] == ["ch02-aberrations.md", "ch02_aberrations.py"]

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
