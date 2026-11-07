"""The reader's notes panel, server side (task 4 M1): reading and saving a document's
Markdown notes without ever losing or silently overwriting text. Temporary libraries only."""

import json
import os
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import library_page
import library_server
import notes_store
import pytest
from notes_store import Conflict, NoteError
from testlib import put

NAME = "doe-2015-practical-lens-design"
README = (
    "# Practical Lens Design\r\n\r\n## Reading progress\r\n\r\n"
    "- [ ] [Ch 1: Basics](ch01-basics.md)\r\n"
    "- [ ] [Ch 2: Aberrations](ch02-aberrations.md)\r\n\r\n## Notes\r\n"
)


@pytest.fixture
def lib(tmp_path):
    """A one-book library: README (CRLF), chapter 1 written (LF), chapter 2 not yet."""
    notes = tmp_path / "notes" / NAME
    notes.mkdir(parents=True)
    (notes / "README.md").write_bytes(README.encode())
    (notes / "ch01-basics.md").write_bytes(b"# Chapter 1: Basics\n\n- my idea\n")
    doc = put(
        tmp_path / "catalog.csv",
        {"slug": NAME, "title": "Practical Lens Design", "notes": f"notes/{NAME}/"},
    )
    return tmp_path, {"id": doc, "slug": NAME, "title": "Practical Lens Design",
                      "notes": f"notes/{NAME}/"}  # fmt: skip


def raw(library, name):
    return (library / "notes" / NAME / name).read_bytes()


def test_read_and_save_keep_the_files_form(lib):
    library, row = lib
    note = notes_store.read(library, row, "file:README.md")
    assert note["exists"] and "\r" not in note["text"]  # the browser always gets "\n"
    assert note["version"] == notes_store.version_of(raw(library, "README.md"))

    saved = notes_store.save(
        library, row, "file:README.md", note["text"] + "\nMy summary.\n", note["version"]
    )
    data = raw(library, "README.md")
    assert saved["saved"] and saved["version"] == notes_store.version_of(data)
    assert data.endswith(b"## Notes\r\n\r\nMy summary.\r\n")  # still CRLF everywhere
    assert data.count(b"\n") == data.count(b"\r\n")

    chapter = notes_store.read(library, row, "file:ch01-basics.md")
    notes_store.save(library, row, "file:ch01-basics.md", chapter["text"] + "- more\n",
                     chapter["version"])  # fmt: skip
    assert b"\r" not in raw(library, "ch01-basics.md")  # an LF file stays LF


def test_bom_and_missing_final_newline_survive(lib):
    library, row = lib
    path = library / "notes" / NAME / "ch01-basics.md"
    path.write_bytes(notes_store.BOM + "# Ch 1\r\n\r\nΔn ≈ 0.01 (光阑 aperture stop)".encode())
    note = notes_store.read(library, row, "file:ch01-basics.md")
    assert note["text"] == "# Ch 1\n\nΔn ≈ 0.01 (光阑 aperture stop)"
    notes_store.save(library, row, "file:ch01-basics.md", note["text"] + " ok", note["version"])
    expected = "# Ch 1\r\n\r\nΔn ≈ 0.01 (光阑 aperture stop) ok".encode()
    assert path.read_bytes() == notes_store.BOM + expected


def test_saving_unchanged_text_writes_nothing(lib):
    library, row = lib
    path = library / "notes" / NAME / "README.md"
    before = path.stat().st_mtime_ns
    note = notes_store.read(library, row, "file:README.md")
    result = notes_store.save(library, row, "file:README.md", note["text"], note["version"])
    assert result == {"version": note["version"], "saved": False, "kept": None}
    assert path.stat().st_mtime_ns == before and path.read_bytes() == README.encode()


def test_a_change_made_meanwhile_is_never_overwritten(lib):
    library, row = lib
    note = notes_store.read(library, row, "file:ch01-basics.md")
    path = library / "notes" / NAME / "ch01-basics.md"
    path.write_bytes(b"# Chapter 1: Basics\n\n- written in VS Code\n")  # meanwhile
    with pytest.raises(Conflict) as conflict:
        notes_store.save(library, row, "file:ch01-basics.md", "mine\n", note["version"])
    assert path.read_bytes() == b"# Chapter 1: Basics\n\n- written in VS Code\n"
    current = conflict.value.current
    assert "written in VS Code" in current["text"]
    assert current["version"] == notes_store.version_of(path.read_bytes())
    # keeping mine is explicit: only over the version the user saw, which is archived first
    with pytest.raises(Conflict):
        notes_store.save(library, row, "file:ch01-basics.md", "mine\n", note["version"],
                         overwrite=note["version"])  # fmt: skip
    kept = notes_store.save(library, row, "file:ch01-basics.md", "mine\n", note["version"],
                            overwrite=current["version"])  # fmt: skip
    assert path.read_bytes() == b"mine\n"
    copy = library / kept["kept"]
    assert copy.parent == library / "archive" / "notes-conflicts" / NAME
    assert copy.read_bytes() == b"# Chapter 1: Basics\n\n- written in VS Code\n"


def test_the_tools_own_writes_are_noticed_too(lib, monkeypatch):
    """ "Last read" written by the reader while the panel has the README open: a conflict."""
    library, row = lib
    monkeypatch.setattr(library_page, "LIBRARY", library)
    monkeypatch.setattr(library_page, "CATALOG", library / "catalog.csv")
    monkeypatch.setattr(library_server, "LIBRARY", library)
    monkeypatch.setattr(library_server, "CATALOG", library / "catalog.csv")
    monkeypatch.setattr(library_server, "chapter_at", lambda *a: None)
    note = notes_store.read(library, row, "file:README.md")
    library_server.save_position(row["id"], 12)
    with pytest.raises(Conflict) as conflict:
        notes_store.save(library, row, "file:README.md", note["text"] + "x", note["version"])
    assert "Last read: page 12" in conflict.value.current["text"]


def test_two_saves_from_the_same_version_one_wins(lib):
    library, row = lib
    note = notes_store.read(library, row, "file:ch01-basics.md")
    outcomes, start = [], threading.Barrier(2)

    def save(text):
        start.wait()
        try:
            notes_store.save(library, row, "file:ch01-basics.md", text, note["version"])
            outcomes.append(("saved", text))
        except Conflict:
            outcomes.append(("conflict", text))

    threads = [threading.Thread(target=save, args=(t,)) for t in ("first\n", "second\n")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(o[0] for o in outcomes) == ["conflict", "saved"]
    winner = next(text for result, text in outcomes if result == "saved")
    assert raw(library, "ch01-basics.md") == winner.encode()


def test_a_chapter_note_not_written_yet(lib):
    library, row = lib
    note = notes_store.read(library, row, "file:ch02-aberrations.md")
    assert note == {"key": "file:ch02-aberrations.md", "text": "", "version": None,
                    "exists": False}  # fmt: skip
    saved = notes_store.save(library, row, "file:ch02-aberrations.md", "# Ch 2\n", None)
    assert saved["saved"] and raw(library, "ch02-aberrations.md").replace(b"\r", b"") == b"# Ch 2\n"
    with pytest.raises(Conflict):  # created meanwhile: "not there yet" is stale now
        notes_store.save(library, row, "file:ch02-aberrations.md", "other\n", None)
    with pytest.raises(NoteError):  # a file the README doesn't link to isn't created
        notes_store.save(library, row, "file:ch09-made-up.md", "x\n", None)


@pytest.mark.parametrize(
    "key",
    [
        "README.md",
        "file:../README.md",
        "file:..\\README.md",
        f"file:../{NAME}/README.md",
        "file:sub/x.md",
        "file:C:/Windows/win.ini.md",
        "file:README.txt",
        "file:.hidden.md",
        "topic:../secret",
        "topic:Upper",
        "elsewhere:README.md",
        None,
        42,
    ],
)
def test_a_key_never_reaches_outside_the_notes(lib, key):
    library, row = lib
    with pytest.raises(NoteError):
        notes_store.read(library, row, key)
    with pytest.raises(NoteError):
        notes_store.save(library, row, key, "x", None)


def test_text_that_isnt_utf8_is_refused_not_replaced(lib):
    library, row = lib
    path = library / "notes" / NAME / "ch01-basics.md"
    path.write_bytes(b"# Kapitel \xe4\xf6\xfc\n")  # Latin-1
    with pytest.raises(NoteError, match="UTF-8"):
        notes_store.read(library, row, "file:ch01-basics.md")
    version = notes_store.version_of(path.read_bytes())
    with pytest.raises(NoteError, match="UTF-8"):
        notes_store.save(library, row, "file:ch01-basics.md", "new\n", version)
    assert path.read_bytes() == b"# Kapitel \xe4\xf6\xfc\n"


def test_too_large(lib, monkeypatch):
    library, row = lib
    monkeypatch.setattr(notes_store, "MAX_BYTES", 100)
    note = notes_store.read(library, row, "file:ch01-basics.md")
    with pytest.raises(NoteError, match="too large"):
        notes_store.save(library, row, "file:ch01-basics.md", "x" * 200, note["version"])
    assert raw(library, "ch01-basics.md") == b"# Chapter 1: Basics\n\n- my idea\n"


def test_the_list_of_notes(lib):
    library, row = lib
    (library / "notes" / NAME / "vocabulary.md").write_text("# Vocabulary\n", encoding="utf-8")
    topics = library / "notes" / "topics"
    topics.mkdir()
    (topics / "vignetting.md").write_text("- Practical Lens Design: PDF page 4\n", encoding="utf-8")
    (topics / "coma.md").write_text("- Another Book: PDF page 9\n", encoding="utf-8")
    listed = {e["key"]: e for e in notes_store.entries(library, row)}
    assert list(listed) == [
        "file:README.md",
        "file:ch01-basics.md",
        "file:ch02-aberrations.md",
        "file:vocabulary.md",
        "topic:vignetting",
    ]
    assert listed["file:ch02-aberrations.md"] == {
        "key": "file:ch02-aberrations.md", "kind": "chapter", "title": "Ch 2: Aberrations",
        "chapter": 2, "exists": False,
    }  # fmt: skip
    assert listed["file:README.md"]["kind"] == "document"


# --- over HTTP --------------------------------------------------------------------------------


@pytest.fixture
def server(lib, monkeypatch):
    library, row = lib
    for module in (library_server, library_page):
        monkeypatch.setattr(module, "LIBRARY", library)
        monkeypatch.setattr(module, "CATALOG", library / "catalog.csv")
    server = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"

    def post(path, body):
        request = urllib.request.Request(
            base + path,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "X-Library-Token": library_server.TOKEN},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as answer:
                return answer.status, json.load(answer)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    yield library, row, post
    server.shutdown()


def test_the_api(server):
    library, row, post = server
    status, listed = post("/api/notes/list", {"id": row["id"]})
    assert status == 200 and listed["notes"][0]["key"] == "file:README.md"

    status, note = post("/api/notes/get", {"id": row["id"], "key": "file:ch01-basics.md"})
    assert status == 200 and note["text"] == "# Chapter 1: Basics\n\n- my idea\n"

    body = {"id": row["id"], "key": "file:ch01-basics.md", "text": "edited\n"}
    status, saved = post("/api/notes/save", body | {"base": note["version"]})
    assert status == 200 and saved["saved"] and raw(library, "ch01-basics.md") == b"edited\n"

    status, conflict = post("/api/notes/save", body | {"text": "late\n", "base": note["version"]})
    assert status == 409 and conflict["current"]["text"] == "edited\n"
    assert raw(library, "ch01-basics.md") == b"edited\n"

    status, kept = post("/api/notes/save", body | {"text": "late\n", "base": note["version"],
                                                   "overwrite": saved["version"]})  # fmt: skip
    assert status == 200 and kept["kept"].startswith("archive/notes-conflicts/")
    assert raw(library, "ch01-basics.md") == b"late\n"


@pytest.mark.parametrize(
    "body",
    [
        {"key": "file:ch01-basics.md", "text": "x"},  # no base
        {"key": "file:ch01-basics.md", "text": "x", "base": "abc"},  # not a version
        {"key": "file:ch01-basics.md", "text": 5, "base": None},  # not text
        {"key": "file:../../catalog.csv", "text": "x", "base": None},  # outside the notes
    ],
)
def test_the_api_refuses_bad_requests(server, body):
    library, row, post = server
    before = raw(library, "ch01-basics.md")
    status, answer = post("/api/notes/save", {"id": row["id"]} | body)
    assert status == 400 and answer["error"]
    assert raw(library, "ch01-basics.md") == before
    assert (library / "catalog.csv").read_bytes().count(b"\n") == 2  # header + the one book


def test_the_api_needs_a_known_document(server):
    _, _, post = server
    status, answer = post("/api/notes/get", {"id": "0" * 8 + "-0000-4000-8000-" + "0" * 12,
                                             "key": "file:README.md"})  # fmt: skip
    assert status == 404


# --- links and other editors -----------------------------------------------------------------


def test_a_symlink_pointing_outside_the_notes_is_refused(lib, tmp_path_factory):
    library, row = lib
    outside = tmp_path_factory.mktemp("elsewhere") / "secret.md"
    outside.write_bytes(b"not a note\n")
    link = library / "notes" / NAME / "evil.md"
    try:
        os.symlink(outside, link)
    except OSError as e:  # Windows: needs Developer Mode or administrator rights
        pytest.skip(f"this system doesn't allow creating a symlink here ({e.strerror})")
    with pytest.raises(NoteError):
        notes_store.read(library, row, "file:evil.md")
    with pytest.raises(NoteError):
        notes_store.save(library, row, "file:evil.md", "x", notes_store.version_of(b"not a note\n"))
    assert outside.read_bytes() == b"not a note\n"
    assert "file:evil.md" not in {e["key"] for e in notes_store.entries(library, row)}


@pytest.mark.skipif(sys.platform != "win32", reason="directory junctions are a Windows feature")
def test_a_notes_folder_that_is_a_junction_still_works(lib, tmp_path_factory):
    """A whole notes folder kept elsewhere (e.g. on OneDrive) through a junction is the user's
    own choice and works; only links *inside* a notes folder are refused (test above)."""
    import _winapi
    import shutil

    library, row = lib
    folder = library / "notes" / NAME
    elsewhere = tmp_path_factory.mktemp("onedrive") / NAME
    shutil.move(folder, elsewhere)
    _winapi.CreateJunction(str(elsewhere), str(folder))
    note = notes_store.read(library, row, "file:ch01-basics.md")
    notes_store.save(library, row, "file:ch01-basics.md", note["text"] + "- via junction\n",
                     note["version"])  # fmt: skip
    assert (elsewhere / "ch01-basics.md").read_bytes().endswith(b"- via junction\n")


def test_a_hard_link_is_never_written_through(lib, tmp_path_factory):
    """A save replaces the file (atomically) instead of writing into it, so a file hard-linked
    into the notes folder from elsewhere is never changed by a save."""
    library, row = lib
    outside = tmp_path_factory.mktemp("elsewhere") / "shared.md"
    outside.write_bytes(b"shared text\n")
    link = library / "notes" / NAME / "linked.md"
    try:
        os.link(outside, link)
    except OSError as e:
        pytest.skip(f"this file system doesn't allow hard links here ({e.strerror})")
    note = notes_store.read(library, row, "file:linked.md")
    notes_store.save(library, row, "file:linked.md", "changed\n", note["version"])
    assert outside.read_bytes() == b"shared text\n" and link.read_bytes() == b"changed\n"


def test_an_editor_rewriting_the_file_in_place_is_noticed(lib):
    """Some editors write into the file instead of replacing it, keeping its size (and, at the
    file system's resolution, perhaps its time): the version is the content's hash, so the
    change is still seen."""
    library, row = lib
    path = library / "notes" / NAME / "ch01-basics.md"
    note = notes_store.read(library, row, "file:ch01-basics.md")
    stat = path.stat()
    with open(path, "r+b") as f:  # same length, different text, written in place
        f.write(b"# Chapter 1: BASICS")
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))  # even with the old time
    with pytest.raises(Conflict):
        notes_store.save(library, row, "file:ch01-basics.md", "mine\n", note["version"])
    assert path.read_bytes() == b"# Chapter 1: BASICS\n\n- my idea\n"
