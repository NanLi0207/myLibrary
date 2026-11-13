import io
import json
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import libraries
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


def NOT_A_CLICK_TIME():  # (a function: "the future" is measured when it's used)
    return ["yesterday", True, False, None, [1], {"ms": 1}, float("nan"), float("inf"),
            float("-inf"), -5, 0, time.time() * 1000 + 60_000, 1e300]  # fmt: skip


def test_a_click_time_must_be_a_real_past_time(library):
    """B32: no NaN, ±Infinity, 0, negative, future, bool, text or null passes for a click time
    (else a replay could pass for older than the README's last change)."""
    now = time.time() * 1000
    assert library_server.check_since(now - 5_000) == now - 5_000
    assert library_server.check_since(int(now)) == int(now)  # ms, as Date.now() gives it
    for bad in NOT_A_CLICK_TIME():
        with pytest.raises(ValueError):
            library_server.check_since(bad)
        if bad is None:  # (to tick() itself None is "no click time": a live tick; the HTTP
            continue  # route refuses a "since": null, test_http_requires_token)
        with pytest.raises(ValueError):  # tick() checks it too, before reading anything
            library_server.tick(doc(library), 2, True, since=bad)
    assert library_page.chapters(doc(library))[1]["done"] is False  # never written


def test_a_replayed_tick_never_overwrites_a_later_change(library):
    """B32: a tick sent again after its page closed carries the click's time ("since"); it is
    applied only if the README hasn't changed since, and the README stays the authority."""
    readme = library_page.readme_path(doc(library))
    clicked = time.time() * 1000
    assert library_server.tick(doc(library), 2, True, since=clicked)[1]["done"] is True
    # Sent again (the first answer was lost): already so, nothing written
    before = readme.stat().st_mtime_ns
    assert library_server.tick(doc(library), 2, True, since=clicked - 60_000)[1]["done"] is True
    assert readme.stat().st_mtime_ns == before
    # The README changed after an older click (e.g. unticked in an editor): that click is refused
    old_click = time.time() * 1000 - 60_000
    library_server.tick(doc(library), 2, False)  # (the README written now, after that click)
    assert library_page.chapters(doc(library))[1]["done"] is False
    with pytest.raises(library_server.TickChanged):
        library_server.tick(doc(library), 2, True, since=old_click)
    assert library_page.chapters(doc(library))[1]["done"] is False  # left as it was
    # A live click (no "since") is the user's choice now: applied
    assert library_server.tick(doc(library), 2, True)[1]["done"] is True


@pytest.fixture
def versions(monkeypatch):
    """This test's own tick versions (as a fresh server process has them)."""
    monkeypatch.setattr(library_server, "_tick_versions", {})
    return library_server


def test_an_older_click_arriving_late_never_overwrites_a_newer_one(library, versions):
    """B32: a click carries the version its page saw; the server refuses it if that chapter
    was ticked after that version, whatever order the requests arrive in."""
    doc_id = doc(library)
    seen = versions.tick_version(doc_id)  # both tabs opened here
    chapters, v1 = versions.tick_with_version(doc_id, 2, True, base=seen)  # tab B: on
    assert chapters[1]["done"] is True and v1 == seen + 1
    chapters, v2 = versions.tick_with_version(doc_id, 2, False, base=v1)  # tab B: off (newest)
    assert v2 == v1 + 1
    with pytest.raises(versions.TickChanged) as refused:  # tab A's older click: on, from `seen`
        versions.tick_with_version(doc_id, 2, True, base=seen)
    assert refused.value.chapters[1]["done"] is False and refused.value.version == v2
    assert library_page.chapters(doc_id)[1]["done"] is False  # the newest click stays
    # The reverse order: the older one first, then the newer: both applied, the newest last
    start = versions.tick_version(doc_id)
    versions.tick_with_version(doc_id, 1, True, base=start)  # A (older): on
    _, v = versions.tick_with_version(doc_id, 1, True, base=start)  # B saw "off", wants on:
    assert library_page.chapters(doc_id)[0]["done"] is True  # already so: no conflict, no write
    versions.tick_with_version(doc_id, 1, False, base=v)  # B's newest: off
    assert library_page.chapters(doc_id)[0]["done"] is False


def test_other_chapters_and_repeats_dont_conflict(library, versions):
    doc_id = doc(library)
    seen = versions.tick_version(doc_id)
    _, v1 = versions.tick_with_version(doc_id, 1, True, base=seen)  # tab A: chapter 1
    _, v2 = versions.tick_with_version(doc_id, 2, True, base=seen)  # tab B, same view: chapter 2
    assert [c["done"] for c in library_page.chapters(doc_id)] == [True, True]
    readme = library_page.readme_path(doc_id)
    written = readme.stat().st_mtime_ns
    # A request repeated (its answer lost), with its old base: already so, nothing written,
    # the version unchanged
    chapters, again = versions.tick_with_version(doc_id, 1, True, base=seen)
    assert again == v2 and readme.stat().st_mtime_ns == written and chapters[0]["done"] is True
    # Without a base (internal callers): unconditional, as before
    assert versions.tick(doc_id, 1, False)[0]["done"] is False


def test_a_base_must_be_a_version_this_server_gave(library, versions):
    doc_id = doc(library)
    now = versions.tick_version(doc_id)
    assert versions.check_base(now, doc_id) == now and versions.check_base(0, doc_id) == 0
    for bad in (True, None, "1", 1.5, float("nan"), float("inf"), -1, now + 1, [now]):
        with pytest.raises(ValueError):
            versions.check_base(bad, doc_id)
        if bad is not None:  # (None is "no base" to tick_with_version; the HTTP route refuses it)
            with pytest.raises(ValueError):
                versions.tick_with_version(doc_id, 1, True, base=bad)
    assert library_page.chapters(doc_id)[0]["done"] is False  # never written


def test_versions_of_an_earlier_server_run_never_pass_for_current(library, versions, monkeypatch):
    """A restarted server starts its versions at its own start time: a version from the earlier
    run is below every chapter's starting version, so a click made on that run's view is
    refused if the chapter now differs (that run's pages need a reload anyway: new token)."""
    doc_id = doc(library)
    _, old = versions.tick_with_version(doc_id, 1, True, base=versions.tick_version(doc_id))
    monkeypatch.setattr(versions, "TICK_START", old + 60_000)  # the next run, a minute later
    monkeypatch.setattr(versions, "_tick_versions", {})
    assert versions.tick_version(doc_id) == old + 60_000
    with pytest.raises(versions.TickChanged):  # on the old run's view: off, but it's on now
        versions.tick_with_version(doc_id, 1, False, base=old)
    assert library_page.chapters(doc_id)[0]["done"] is True
    assert versions.tick_with_version(doc_id, 1, True, base=old)[0][0]["done"]  # same: fine


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
        assert json.dumps(library_server.SCOPE) in page  # the page's key for its tick journal

        stale = tick | {"done": False, "since": 1}  # a replay from long before the README's date
        with pytest.raises(urllib.error.HTTPError) as refused:
            post("/api/tick", stale, library_server.TOKEN)
        assert refused.value.code == 409
        assert json.load(refused.value)["chapter_list"][0]["done"] is True  # unchanged
        before = library_page.readme_path(doc(library)).read_bytes()
        for bad in NOT_A_CLICK_TIME():  # refused, nothing written (json.dumps sends NaN as NaN)
            with pytest.raises(urllib.error.HTTPError) as wrong:
                post("/api/tick", tick | {"done": False, "since": bad}, library_server.TOKEN)
            assert wrong.value.code == 400, bad
        assert library_page.readme_path(doc(library)).read_bytes() == before

        # A live click's base (B32): its version, checked; a stale one refused with the state
        assert '"tick_versions"' in page  # (the page's own data carries them)
        current = library_server.tick_version(doc(library))
        for bad in (None, "1", True, -1, 1.5, current + 1):
            with pytest.raises(urllib.error.HTTPError) as wrong:
                post("/api/tick", tick | {"done": False, "base": bad}, library_server.TOKEN)
            assert wrong.value.code == 400, bad
        live = tick | {"chapter": 2, "done": True, "base": current}
        answer = json.load(post("/api/tick", live, library_server.TOKEN))
        assert answer["version"] == current + 1 and answer["chapter_list"][1]["done"] is True
        with pytest.raises(urllib.error.HTTPError) as stale:  # made on the view before that
            post("/api/tick", live | {"done": False}, library_server.TOKEN)
        assert stale.value.code == 409
        refused = json.load(stale.value)
        assert refused["version"] == current + 1 and refused["chapter_list"][1]["done"] is True
        listed = json.load(post("/api/books", {}, library_server.TOKEN))
        assert listed["tick_versions"]["documents"][doc(library)] == current + 1

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
    monkeypatch.setattr(reading_view, "KATEX", tmp_path / "reader" / "katex")  # (none: M5b)
    assert bool(reading_view.markdown_it_installed()) is preview
    assert "dictionary" in reading_view.missing()
    assert reading_view.missing() == (
        ["dictionary"] + ([] if preview else ["notes preview"]) + ["maths"]
    )
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


def test_a_burst_of_connections_is_never_refused():
    """A reader page opens about 25 connections at once (PDF.js, its icons, the reader's
    scripts, the notes' first requests): the server queues them instead of refusing some
    (with the default listen backlog of 5, Windows refused a reload's /api/notes/list in CI).
    A fast accept loop may serve such a burst even with a small queue, so the configured
    backlog is checked as well as the burst itself."""
    assert library_server.Server.request_queue_size >= 64
    server = library_server.Server(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    burst = 48
    start = threading.Barrier(burst)
    results: list = [None] * burst

    def fetch(n: int) -> None:
        start.wait()
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_port}/api/whoami", timeout=30
            ) as r:
                results[n] = r.status
        except OSError as e:  # (refused, reset: reported below)
            results[n] = e

    try:
        threads = [threading.Thread(target=fetch, args=(n,)) for n in range(burst)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(60)
    finally:
        server.shutdown()
        server.server_close()
    assert results == [200] * burst, [r for r in results if r != 200]


def test_pick_folder_answers(library, monkeypatch):
    """/api/pick-folder: a folder or a cancel is a normal answer (folder null when cancelled);
    no dialog on this system, or a failing one, is an error the page shows as a message."""
    import platform_services

    server = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    asked = []

    def answer(choice):
        monkeypatch.setattr(
            library_server.platform_services,
            "pick_folder",
            lambda prompt: asked.append(prompt) or choice,
        )
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/pick-folder",
            data=json.dumps({"purpose": "backup"}).encode(),
            headers={"Content-Type": "application/json", "X-Library-Token": library_server.TOKEN},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    try:
        Choice = platform_services.FolderChoice
        assert answer(Choice("chosen", "D:/书库 Backups")) == (
            200, {"folder": "D:/书库 Backups", "status": "chosen"}
        )  # fmt: skip
        assert "backups" in asked[-1]
        assert answer(Choice("cancelled")) == (200, {"folder": None, "status": "cancelled"})
        code, data = answer(Choice("unsupported", message="no folder dialog on this system"))
        assert code == 501 and data["folder"] is None and "type the folder" in data["error"]
        code, data = answer(Choice("error", message="PowerShell failed"))
        assert code == 500 and "PowerShell failed" in data["error"]
        assert data["status"] == "error" and data["detail"] == "PowerShell failed"
    finally:
        server.shutdown()


def test_a_restarting_server_still_answers_as_itself_until_it_is_gone(library, monkeypatch):
    """B35: while a Settings restart waits for running jobs, the old server goes on answering,
    with its own instance id: a page must wait for another id, not just any answer. The id is
    no secret (it grants nothing) and the Host check still applies to it."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    holding, release, started, exited = (threading.Event() for _ in range(4))
    spawned = []

    def jobs_still_running(timeout=120):  # the old server is kept alive here, deliberately
        holding.set()
        assert release.wait(30)

    monkeypatch.setattr(library_server, "finish_jobs", jobs_still_running)
    monkeypatch.setattr(library_server.subprocess, "Popen",
                        lambda args, **kw: (spawned.append(args), started.set()))  # fmt: skip
    monkeypatch.setattr(library_server.os, "_exit", lambda code: exited.set())
    monkeypatch.setattr(library_server.sys, "argv",
                        ["library_server.py", "--library", "x", "--port", "8765"])  # fmt: skip

    def whoami(host=None):
        request = urllib.request.Request(base + "/api/whoami",
                                         headers={"Host": host} if host else {})  # fmt: skip
        with urllib.request.urlopen(request, timeout=10) as answer:
            return answer.status, json.load(answer)

    status, before = whoami()
    assert status == 200 and before["instance"] == library_server.INSTANCE
    assert before["scope"] == library_server.SCOPE  # which library, for the page's check
    assert library_server.TOKEN not in json.dumps(before)
    with pytest.raises(urllib.error.HTTPError) as foreign:
        whoami(host="evil.example")  # DNS rebinding: refused, as every route
    assert foreign.value.code == 403
    try:
        library_server.restart_later(server)
        assert holding.wait(30)  # the restart has begun and waits for "jobs"
        status, during = whoami()
        assert status == 200 and during["instance"] == before["instance"]  # still the old one
    finally:
        release.set()
    assert started.wait(30) and exited.wait(30)
    args = spawned[0]
    assert "--library" not in args and "--no-browser" in args  # the new one reads the settings


def test_a_library_change_names_the_library_the_new_server_must_show(
    library, tmp_path, monkeypatch
):
    """B35: the answer to a library change gives the scope the new server must show (the
    library's id and real folder, normalised by the server), and the page reloads only from a
    server with that scope: the same folder spelled otherwise matches, a copy (same id,
    another folder) doesn't."""
    monkeypatch.setattr(library_server.paths, "save_settings", lambda settings: None)
    folder = tmp_path / "Next library 下一个书库"
    result = library_server.change_settings({"library": str(folder)})
    assert result == {"restart": True, "expect": libraries.scope(folder)}
    assert re.fullmatch(r"[0-9a-f]{16}", result["expect"])
    assert libraries.info(folder)["id"]  # it has an id, and the scope covers more than it
    respelled = tmp_path / "elsewhere" / ".." / folder.name
    if sys.platform == "win32":  # (folder names are case-insensitive there)
        respelled = Path(str(respelled).upper())
    assert libraries.scope(respelled) == result["expect"]
    copy = tmp_path / "Copied library"
    shutil.copytree(folder, copy)
    assert libraries.info(copy)["id"] == libraries.info(folder)["id"]
    assert libraries.scope(copy) != result["expect"]
    # no library change: no restart, nothing to wait for
    assert library_server.change_settings({"library": str(library)}) == {"restart": False}


RESTART_RACE = """
import sys, threading
sys.path.insert(0, sys.argv[1])
marker = sys.argv[3]
sys.argv = ["library_server.py", "--library", sys.argv[2], "--port", "8765"]
import library_server

library_server.finish_jobs = lambda timeout=120: None
closing = library_server.Server.server_close


def slow_close(self):  # by then the main thread is surely ending (serve_forever has returned)
    threading.Event().wait(1)
    closing(self)


library_server.Server.server_close = slow_close
library_server.subprocess.Popen = lambda args, **kw: open(marker, "w").close()
server = library_server.Server(("127.0.0.1", 0), library_server.Handler)
library_server.restart_later(server)
server.serve_forever()  # returns once the restart has shut the server down: the script ends
"""


def test_a_restart_starts_the_new_server_even_as_the_main_thread_ends(library, tmp_path):
    """B35: the restart's shutdown() lets main()'s serve_forever return, so the interpreter
    starts ending while the restart has yet to start the new server. It must not be cut off
    there (it was, as a daemon thread: sometimes no new server at all, and the page waited for
    one in vain). In a real process; the new server's start is recorded, not run."""
    script, marker = tmp_path / "restart_race.py", tmp_path / "new server started"
    script.write_text(RESTART_RACE, encoding="utf-8")
    scripts = Path(library_server.__file__).parent
    run = subprocess.run(
        [sys.executable, str(script), str(scripts), str(library), str(marker)],
        capture_output=True, text=True, timeout=60, cwd=tmp_path,
    )  # fmt: skip
    assert run.returncode == 0, run.stdout + run.stderr
    assert marker.exists(), run.stdout + run.stderr
