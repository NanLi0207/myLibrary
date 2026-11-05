import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import catalog
import library_page
import library_server
import pytest

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
        monkeypatch.setattr(module, "ROOT", tmp_path)
        monkeypatch.setattr(module, "CATALOG", tmp_path / "catalog.csv")
    notes = tmp_path / "notes" / "doe-2015-practical-lens-design"
    notes.mkdir(parents=True)
    (notes / "README.md").write_text(README, encoding="utf-8")
    catalog.upsert(
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
    chapters = library_server.tick("doe-2015-practical-lens-design", 2, True)
    assert [c["done"] for c in chapters] == [False, True]
    chapters = library_server.tick("doe-2015-practical-lens-design", 2, False)
    assert [c["done"] for c in chapters] == [False, False]


def test_chapter_script_created_only_when_asked(library):
    slug = "doe-2015-practical-lens-design"
    chapter = library_page.chapters(slug)[1]
    assert library_server.script_for(slug, chapter, "A Book") is None  # Read doesn't create one
    title = 'A "Book" with C:\\paths and """quotes"""'
    script = library_server.script_for(slug, chapter, title, create=True)
    assert script == library / "examples" / slug / "ch02_aberrations.py"
    # Asking again returns the same file instead of overwriting it
    script.write_text(script.read_text(encoding="utf-8") + "# my edits\n", encoding="utf-8")
    again = library_server.script_for(slug, chapter, title, create=True)
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

        tick = {"slug": "doe-2015-practical-lens-design", "chapter": 1, "done": True}
        with pytest.raises(urllib.error.HTTPError) as denied:
            post("/api/tick", tick)
        assert denied.value.code == 403

        result = json.load(post("/api/tick", tick, library_server.TOKEN))
        assert result["chapter_list"][0]["done"] is True

        with pytest.raises(urllib.error.HTTPError) as unknown:
            post("/api/open", {"slug": "../../secret", "chapter": 1}, library_server.TOKEN)
        assert unknown.value.code == 404
    finally:
        server.shutdown()


def test_missing_pdf_is_flagged_and_read_still_works(library, monkeypatch):
    opened = []
    monkeypatch.setattr(library_server.webbrowser, "open", opened.append)
    monkeypatch.setattr(library_server, "open_in_vscode", lambda *files: True)

    assert library_page.books()[0]["pdf_missing"] is True
    message = library_server.open_chapter("doe-2015-practical-lens-design", 1, "http://x")
    assert opened == []  # no browser tab for a PDF that isn't there
    assert "missing" in message and "notes in VS Code" in message


@pytest.fixture
def chapter_pages(library, monkeypatch):
    """Chapter 1 starts on PDF page 5, chapter 2 on page 30 (as if already found)."""
    cache = library / ".cache" / "chapter_pages.json"
    cache.parent.mkdir()
    cache.write_text(json.dumps({"doe-2015-practical-lens-design": {"1": 5, "2": 30}}))
    monkeypatch.setattr(library_server, "CACHE", cache)
    return library


def test_save_position_writes_and_updates_one_line(chapter_pages):
    slug = "doe-2015-practical-lens-design"
    readme = chapter_pages / "notes" / slug / "README.md"
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
    slug = "doe-2015-practical-lens-design"
    (chapter_pages / "books").mkdir()
    (chapter_pages / "books" / f"{slug}.pdf").write_bytes(b"%PDF-1.4")
    (chapter_pages / "notes" / slug / "ch02-aberrations.md").write_text("# Ch 2\n")
    opened, files = [], []
    monkeypatch.setattr(library_server.webbrowser, "open", opened.append)
    monkeypatch.setattr(library_server, "open_in_vscode", lambda *f: files.extend(f) or True)

    library_server.save_position(slug, 33)
    message = library_server.open_chapter(slug, None, "http://x", resume=True)
    assert opened[0].endswith(f"{slug}.pdf#page=33")
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
