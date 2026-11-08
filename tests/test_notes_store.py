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


def test_the_list_gives_chapter_pages_from_the_cache_only(server, monkeypatch):
    """The notes panel opens the chapter of the page being read: chapter start pages come from
    the chapter-pages cache, and the (slow) chapter search is never started for the list."""
    library, row, post = server

    def no_search(*args):
        raise AssertionError("the chapter search was started for the notes list")

    monkeypatch.setattr(library_server, "find_chapter_pages", no_search)
    status, listed = post("/api/notes/list", {"id": row["id"]})
    assert status == 200 and not any("page" in e for e in listed["notes"])  # nothing cached

    cache = library / ".cache" / "chapter_pages.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({row["id"]: {"1": 3, "2": 17}}), encoding="utf-8")
    monkeypatch.setattr(library_server, "CACHE", cache)
    status, listed = post("/api/notes/list", {"id": row["id"]})
    pages = {e["key"]: e.get("page") for e in listed["notes"]}
    assert pages["file:ch01-basics.md"] == 3 and pages["file:ch02-aberrations.md"] == 17
    assert pages["file:README.md"] is None


def test_the_api_opens_an_existing_note_in_the_editor(server, monkeypatch):
    """/api/notes/open: an existing note of this document, through the same checks as reading;
    nothing is created or changed, and an editor that can't start says so."""
    library, row, post = server
    opened = []
    monkeypatch.setattr(library_server, "open_in_editor", lambda *f: opened.extend(f) or True)
    before = {p.name: p.read_bytes() for p in (library / "notes" / NAME).iterdir()}

    status, answer = post("/api/notes/open", {"id": row["id"], "key": "file:ch01-basics.md"})
    assert status == 200 and answer["opened"]
    assert opened == [library / "notes" / NAME / "ch01-basics.md"]

    for key in ("file:ch02-aberrations.md", "file:../../catalog.csv", "file:C:/Windows/x.md", 7):
        status, answer = post("/api/notes/open", {"id": row["id"], "key": key})
        assert status == 400 and answer["error"], key  # not written yet, or not a note
    assert len(opened) == 1
    assert not (library / "notes" / NAME / "ch02-aberrations.md").exists()  # not created

    monkeypatch.setattr(library_server, "open_in_editor", lambda *f: False)
    status, answer = post("/api/notes/open", {"id": row["id"], "key": "file:README.md"})
    assert status == 200 and not answer["opened"] and "editor" in answer["message"]
    assert {p.name: p.read_bytes() for p in (library / "notes" / NAME).iterdir()} == before

    unknown = "0" * 8 + "-0000-4000-8000-" + "0" * 12
    status, answer = post("/api/notes/open", {"id": unknown, "key": "file:README.md"})
    assert status == 404 and answer["error"]


def test_listing_and_reading_never_start_the_editor(server, monkeypatch):
    library, row, post = server

    def no_editor(*files):
        raise AssertionError(f"the editor was started for {files}")

    monkeypatch.setattr(library_server, "open_in_editor", no_editor)
    assert post("/api/notes/list", {"id": row["id"]})[0] == 200
    for key in ("file:README.md", "file:ch01-basics.md", "file:ch02-aberrations.md"):
        assert post("/api/notes/get", {"id": row["id"], "key": key})[0] == 200


@pytest.mark.parametrize("kind", ["symlink", "junction"])
def test_the_editor_is_never_given_a_note_linked_from_outside(server, monkeypatch, kind,
                                                               tmp_path_factory):  # fmt: skip
    """/api/notes/open goes through path_of: a note that's a link pointing out of the notes
    folder (a file symlink; a junction named like a note) is refused, and nothing opens."""
    library, row, post = server
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    (elsewhere / "secret.md").write_bytes(SECRET)
    link = library / "notes" / NAME / "evil.md"
    if kind == "symlink":
        symlink_or_skip(elsewhere / "secret.md", link)
    else:
        if sys.platform != "win32":
            pytest.skip("directory junctions are a Windows feature")
        import _winapi

        _winapi.CreateJunction(str(elsewhere), str(link))
    opened = []
    monkeypatch.setattr(library_server, "open_in_editor", lambda *f: opened.extend(f) or True)
    status, answer = post("/api/notes/open", {"id": row["id"], "key": "file:evil.md"})
    assert status == 400 and answer["error"] and opened == []
    assert (elsewhere / "secret.md").read_bytes() == SECRET


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


SECRET = b"Practical Lens Design: SECRET text kept outside the notes\n"


# CI sets this: a link-security test that can't create its link fails instead of skipping, so
# missing coverage can't pass unnoticed. Without it (a developer's PC) such a test skips.
REQUIRE_LINKS = os.environ.get("MYLIBRARY_REQUIRE_LINK_TESTS") == "1"


def link_or_skip(make_link, what: str) -> None:
    """Create the test's link, or skip (fail in CI) when this system doesn't allow it. Only
    the link's creation is caught here: the security checks after it fail as usual."""
    try:
        make_link()
    except OSError as e:  # Windows: symlinks need Developer Mode or administrator rights
        reason = f"this system doesn't allow creating a {what} here ({e.strerror})"
        if REQUIRE_LINKS:
            pytest.fail(
                f"MYLIBRARY_REQUIRE_LINK_TESTS=1, but {reason}: the link-security test "
                "couldn't run (a missing right on this machine, not a failed check)",
                pytrace=False,
            )
        pytest.skip(reason)


def symlink_or_skip(target, link):
    link_or_skip(lambda: os.symlink(target, link), "symlink")


@pytest.fixture
def reads(monkeypatch):
    """Every file the notes store reads as text (to show an outside file is never read)."""
    seen = []
    real = notes_store.safe_io.read_text

    def spy(path, *args, **kwargs):
        seen.append(os.path.realpath(path))
        return real(path, *args, **kwargs)

    monkeypatch.setattr(notes_store.safe_io, "read_text", spy)
    return seen


def listed_keys(library, row):
    return [e["key"] for e in notes_store.entries(library, row)]


def assert_normal_notes_work(library, row):
    """The document's own notes are still listed, read and saved."""
    keys = listed_keys(library, row)
    assert "file:ch01-basics.md" in keys, keys
    note = notes_store.read(library, row, "file:ch01-basics.md")
    notes_store.save(library, row, "file:ch01-basics.md", note["text"] + "- ok\n", note["version"])
    assert raw(library, "ch01-basics.md").endswith(b"- ok\n")


def test_a_symlink_pointing_outside_the_notes_is_refused(lib, tmp_path_factory, reads):
    library, row = lib
    outside = tmp_path_factory.mktemp("elsewhere") / "secret.md"
    outside.write_bytes(SECRET)
    symlink_or_skip(outside, library / "notes" / NAME / "evil.md")
    with pytest.raises(NoteError):
        notes_store.read(library, row, "file:evil.md")
    with pytest.raises(NoteError):
        notes_store.save(library, row, "file:evil.md", "x", notes_store.version_of(SECRET))
    listed = notes_store.entries(library, row)
    assert "file:evil.md" not in {e["key"] for e in listed}
    assert "SECRET" not in json.dumps(listed)
    assert_normal_notes_work(library, row)
    assert outside.read_bytes() == SECRET
    assert os.path.realpath(outside) not in reads


def test_a_topic_note_symlink_pointing_outside_is_neither_listed_nor_read(
    lib, tmp_path_factory, reads
):
    library, row = lib
    topics = library / "notes" / "topics"
    topics.mkdir()
    (topics / "coma.md").write_text("- Practical Lens Design: PDF page 4\n", encoding="utf-8")
    outside = tmp_path_factory.mktemp("elsewhere") / "secret.md"
    outside.write_bytes(SECRET)  # it mentions the book, so it would be listed if it were read
    symlink_or_skip(outside, topics / "vignetting.md")
    listed = notes_store.entries(library, row)
    keys = [e["key"] for e in listed]
    assert "topic:coma" in keys and "topic:vignetting" not in keys, keys
    assert "SECRET" not in json.dumps(listed)
    assert os.path.realpath(outside) not in reads  # not even read to decide
    with pytest.raises(NoteError):
        notes_store.read(library, row, "topic:vignetting")
    with pytest.raises(NoteError):
        notes_store.save(library, row, "topic:vignetting", "x", notes_store.version_of(SECRET))
    assert notes_store.read(library, row, "topic:coma")["exists"]
    assert_normal_notes_work(library, row)
    assert outside.read_bytes() == SECRET


def test_a_readme_symlink_pointing_outside_is_neither_listed_nor_read(lib, tmp_path_factory, reads):
    """Its checklist isn't used either: no chapters from it, and no "not written yet" note it
    names can be created."""
    library, row = lib
    outside = tmp_path_factory.mktemp("elsewhere") / "README.md"
    secret_readme = b"# SECRET\n\n- [ ] [SECRET chapter](secret.md)\n"
    outside.write_bytes(secret_readme)
    readme = library / "notes" / NAME / "README.md"
    readme.unlink()
    symlink_or_skip(outside, readme)
    listed = notes_store.entries(library, row)
    keys = [e["key"] for e in listed]
    assert "file:README.md" not in keys and "file:secret.md" not in keys, keys
    assert "SECRET" not in json.dumps(listed)
    assert os.path.realpath(outside) not in reads
    with pytest.raises(NoteError):
        notes_store.read(library, row, "file:README.md")
    with pytest.raises(NoteError):
        notes_store.save(library, row, "file:README.md", "x", notes_store.version_of(secret_readme))
    with pytest.raises(NoteError):  # named only by the outside README: not a note to create
        notes_store.save(library, row, "file:secret.md", "x", None)
    assert not (library / "notes" / NAME / "secret.md").exists()
    assert_normal_notes_work(library, row)
    assert outside.read_bytes() == secret_readme


@pytest.mark.skipif(sys.platform != "win32", reason="directory junctions are a Windows feature")
def test_junctions_named_like_notes_are_neither_listed_nor_opened(lib, tmp_path_factory, reads):
    """Junctions need no special rights, so this runs everywhere on Windows: a junction in the
    notes or topics folder, named like a note, pointing outside."""
    import _winapi

    library, row = lib
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    (elsewhere / "README.md").write_bytes(SECRET)
    topics = library / "notes" / "topics"
    topics.mkdir()
    _winapi.CreateJunction(str(elsewhere), str(library / "notes" / NAME / "trap.md"))
    _winapi.CreateJunction(str(elsewhere), str(topics / "trap.md"))
    keys = listed_keys(library, row)
    assert "file:trap.md" not in keys and "topic:trap" not in keys, keys
    for key in ("file:trap.md", "topic:trap"):
        with pytest.raises(NoteError):
            notes_store.read(library, row, key)
        with pytest.raises(NoteError):
            notes_store.save(library, row, key, "x", None)
    assert_normal_notes_work(library, row)
    assert sorted(p.name for p in elsewhere.iterdir()) == ["README.md"]
    assert (elsewhere / "README.md").read_bytes() == SECRET
    assert not any(path.startswith(os.path.realpath(elsewhere)) for path in reads)


@pytest.mark.parametrize(
    "notes",
    ["../elsewhere/", "notes/../../elsewhere/", "elsewhere/", "notes/", "ABSOLUTE"],
)
def test_a_catalog_notes_folder_outside_notes_is_refused(lib, tmp_path_factory, notes):
    """The folder named by the catalog row must be under notes/, with no link involved."""
    library, row = lib
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    (elsewhere / "README.md").write_bytes(SECRET)
    if notes == "ABSOLUTE":
        notes = elsewhere.as_posix() + "/"
    bad = {**row, "notes": notes}
    with pytest.raises(NoteError):
        notes_store.entries(library, bad)
    with pytest.raises(NoteError):
        notes_store.read(library, bad, "file:README.md")
    with pytest.raises(NoteError):
        notes_store.save(library, bad, "file:README.md", "x", notes_store.version_of(SECRET))
    assert (elsewhere / "README.md").read_bytes() == SECRET
    assert_normal_notes_work(library, row)  # the real row still works


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
    link_or_skip(lambda: os.link(outside, link), "hard link")
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


# --- for the editor (task 4 M4) ---------------------------------------------------------------


def test_the_version_check_matches_reading_and_sends_no_text(server):
    library, row, post = server
    for key in ("file:README.md", "file:ch01-basics.md", "file:ch02-aberrations.md"):
        status, info = post("/api/notes/version", {"id": row["id"], "key": key})
        _, note = post("/api/notes/get", {"id": row["id"], "key": key})
        assert status == 200 and "text" not in info
        assert (info["version"], info["exists"]) == (note["version"], note["exists"])
    assert info == {"key": "file:ch02-aberrations.md", "version": None, "exists": False, "bytes": 0}
    assert post("/api/notes/version", {"id": row["id"], "key": "file:../x.md"})[0] == 400


def test_keep_copy_writes_only_into_the_conflicts_archive(server):
    """The user's side of a conflict: kept under archive/notes-conflicts/ in the note's own
    form (CRLF here), the note itself untouched; refused for anything but a note."""
    library, row, post = server
    before = {p.name: p.read_bytes() for p in (library / "notes" / NAME).iterdir()}
    status, answer = post(
        "/api/notes/keep-copy", {"id": row["id"], "key": "file:README.md", "text": "mine\n光阑\n"}
    )
    assert status == 200 and answer["kept"].startswith(f"archive/notes-conflicts/{NAME}/README.")
    assert answer["kept"].endswith(".mine.md")
    assert (library / answer["kept"]).read_bytes() == "mine\r\n光阑\r\n".encode()  # README is CRLF
    assert {p.name: p.read_bytes() for p in (library / "notes" / NAME).iterdir()} == before

    # a chapter not written yet: kept too (the user may have typed it)
    body = {"id": row["id"], "key": "file:ch02-aberrations.md", "text": "x"}
    status, answer = post("/api/notes/keep-copy", body)
    assert status == 200 and not (library / "notes" / NAME / "ch02-aberrations.md").exists()

    refused = [
        {"key": "file:../../catalog.csv", "text": "x"},  # not a note
        {"key": "file:README.md"},  # no text
        {"key": "file:README.md", "text": 5},
    ]
    for body in refused:
        assert post("/api/notes/keep-copy", {"id": row["id"]} | body)[0] == 400


def test_two_saves_at_once_one_wins_the_other_is_a_conflict(lib):
    """Two editors (tabs, threads) saving from the same version at the same moment: exactly one
    is written; the other gets the conflict and writes nothing."""
    library, row = lib
    version = notes_store.read(library, row, "file:ch01-basics.md")["version"]
    start = threading.Barrier(2)
    outcomes = {}

    def save(name):
        start.wait()
        try:
            text = name + "\n"
            outcomes[name] = notes_store.save(library, row, "file:ch01-basics.md", text, version)
        except Conflict:
            outcomes[name] = "conflict"

    threads = [threading.Thread(target=save, args=(n,)) for n in ("first", "second")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    kinds = sorted(o if o == "conflict" else "saved" for o in outcomes.values())
    assert kinds == ["conflict", "saved"]
    winner = next(n for n, o in outcomes.items() if o != "conflict")
    assert raw(library, "ch01-basics.md") == (winner + "\n").encode()


def test_a_chapter_note_is_created_only_by_a_save(lib):
    library, row = lib
    path = library / "notes" / NAME / "ch02-aberrations.md"
    notes_store.read(library, row, "file:ch02-aberrations.md")
    notes_store.version_info(library, row, "file:ch02-aberrations.md")
    assert not path.exists()  # reading and checking create nothing
    with pytest.raises(Conflict):  # a save that assumes it exists
        notes_store.save(library, row, "file:ch02-aberrations.md", "x", "0" * 64)
    assert not path.exists()
    saved = notes_store.save(library, row, "file:ch02-aberrations.md", "# Ch 2\n", None)
    assert saved["saved"] and path.read_bytes().replace(b"\r\n", b"\n") == b"# Ch 2\n"
    with pytest.raises(NoteError):  # a name the README doesn't link: never created
        notes_store.save(library, row, "file:random.md", "x", None)


def test_technical_markdown_round_trips_byte_for_byte(lib):
    library, row = lib
    text = r"""# 像差 Aberrations

| Seidel | 符号 | $W$ |
|---|---|---|
| spherical | $S_I$ | $W_{040} \rho^4$ |

$$\frac{1}{f} = (n-1)\left(\frac{1}{R_1} - \frac{1}{R_2}\right)$$

```python
print("θ = π/4")
```

[Shannon p. 41](http://127.0.0.1:8765/read/x?page=41)
<details><summary>raw HTML</summary>kept as typed</details>
"""
    assert "\\frac" in text and "\r" not in text  # LaTeX as typed: backslashes, no escapes
    note = notes_store.read(library, row, "file:ch01-basics.md")
    saved = notes_store.save(library, row, "file:ch01-basics.md", text, note["version"])
    assert raw(library, "ch01-basics.md") == text.encode("utf-8")  # an LF file stays LF
    again = notes_store.read(library, row, "file:ch01-basics.md")
    assert again["text"] == text and again["version"] == saved["version"]
