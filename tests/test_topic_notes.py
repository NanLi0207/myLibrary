"""D17: a topic note (notes/topics/<term>.md, from 主题笔记 / Topic note in the popup) is
created from its template only if nothing is there: never over a note written meanwhile (by
the notes API, an editor, another request) while the slow full-text search ran. The search runs
without the lock; the file's lock is taken to decide, and safe_io.create_bytes publishes the
whole file without ever replacing anything (an existing file, a link, a dangling link). A link
out of notes/topics/ is refused. Temporary libraries; the search is held with events."""

import errno
import os
import sys
import threading

import library_server
import notes_store
import pytest
import safe_io

REQUIRE_LINKS = os.environ.get("MYLIBRARY_REQUIRE_LINK_TESTS") == "1"  # CI: never skipped
WAIT = 30
ROW = {"slug": "doe-2015-optics", "notes": "notes/doe-2015-optics/"}  # (topic keys ignore it)
MINE = b"# Entrance pupil\n\nMy own words about the entrance pupil.\n"


def link_or_skip(make_link, what: str) -> None:
    try:
        make_link()
    except OSError as e:
        reason = f"this system doesn't allow creating a {what} here ({e.strerror})"
        if REQUIRE_LINKS:
            pytest.fail(f"MYLIBRARY_REQUIRE_LINK_TESTS=1, but {reason}", pytrace=False)
        pytest.skip(reason)


class HeldSearch:
    """book_search.search that waits, after saying so, until the test releases it."""

    def __init__(self, waiting: int = 1):
        self.arrived = threading.Barrier(waiting + 1)
        self.release = threading.Event()
        self.calls = 0

    def __call__(self, term, limit=8):
        self.calls += 1
        self.arrived.wait(WAIT)
        assert self.release.wait(WAIT), "never released"
        return {"results": [{"title": "Optics", "page": 12}]}


@pytest.fixture
def lib(tmp_path, monkeypatch):
    monkeypatch.setattr(library_server, "LIBRARY", tmp_path)
    found = {"results": [{"title": "Optics", "page": 12}]}
    monkeypatch.setattr(library_server.book_search, "search", lambda term, limit=8: found)
    (tmp_path / "notes" / "topics").mkdir(parents=True)
    return tmp_path


def topic(lib, name="entrance-pupil"):
    return lib / "notes" / "topics" / f"{name}.md"


def in_thread(work):
    outcome = {}

    def run():
        try:
            outcome["result"] = work()
        except BaseException as e:
            outcome["error"] = e

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, outcome


def leftovers(folder) -> list[str]:
    return sorted(p.name for p in folder.iterdir() if p.name.endswith(".tmp"))


# --- the races --------------------------------------------------------------------------------


def test_a_note_saved_through_the_notes_api_during_the_search_stays(lib, monkeypatch):
    search = HeldSearch()
    monkeypatch.setattr(library_server.book_search, "search", search)
    running, outcome = in_thread(lambda: library_server.topic_note("Entrance pupil"))
    search.arrived.wait(WAIT)  # the search is running, without the file's lock
    notes_store.save(lib, ROW, "topic:entrance-pupil", MINE.decode(), None)
    search.release.set()
    running.join(WAIT)
    assert outcome.get("result") == topic(lib), outcome
    # The user's note, not the template (a new note is written with the system's line endings)
    assert topic(lib).read_bytes().replace(b"\r\n", b"\n") == MINE
    assert leftovers(topic(lib).parent) == []


def test_a_note_written_by_an_editor_during_the_search_stays(lib, monkeypatch):
    search = HeldSearch()
    monkeypatch.setattr(library_server.book_search, "search", search)
    running, outcome = in_thread(lambda: library_server.topic_note("Entrance pupil"))
    search.arrived.wait(WAIT)
    topic(lib).write_bytes(MINE)  # e.g. VS Code saving the file
    search.release.set()
    running.join(WAIT)
    assert outcome.get("result") == topic(lib) and topic(lib).read_bytes() == MINE


def test_two_requests_at_once_make_one_template(lib, monkeypatch):
    search = HeldSearch(waiting=2)
    monkeypatch.setattr(library_server.book_search, "search", search)
    runs = [in_thread(lambda: library_server.topic_note("Entrance pupil")) for _ in range(2)]
    search.arrived.wait(WAIT)  # both are searching
    search.release.set()
    for thread, outcome in runs:
        thread.join(WAIT)
        assert outcome.get("result") == topic(lib), outcome
    text = topic(lib).read_text(encoding="utf-8")
    assert text.startswith("# Entrance pupil") and "Optics: PDF page 12" in text
    assert leftovers(topic(lib).parent) == []


def test_an_existing_note_is_never_touched(lib, monkeypatch):
    topic(lib).write_bytes(MINE)
    calls = []
    monkeypatch.setattr(library_server.book_search, "search",
                        lambda term, limit=8: calls.append(term) or {"results": []})  # fmt: skip
    assert library_server.topic_note("Entrance pupil") == topic(lib)
    assert topic(lib).read_bytes() == MINE and calls == []  # (not even searched)


def test_a_new_note_is_created_from_the_template(lib):
    path = library_server.topic_note("Entrance  pupil")
    assert path == topic(lib)
    text = path.read_bytes().decode("utf-8")
    assert text.startswith("# Entrance pupil") and "Optics: PDF page 12" in text
    lines = text.split(os.linesep)  # written with the system's line endings, as before
    assert len(lines) > 3 and not any("\n" in line or "\r" in line for line in lines)


# --- links --------------------------------------------------------------------------------------


def test_a_note_linked_from_outside_is_refused(lib, tmp_path_factory):
    elsewhere = tmp_path_factory.mktemp("elsewhere") / "secret.md"
    elsewhere.write_bytes(b"not a note\n")
    link_or_skip(lambda: os.symlink(elsewhere, topic(lib)), "symlink")
    with pytest.raises(ValueError, match="link"):
        library_server.topic_note("Entrance pupil")
    assert elsewhere.read_bytes() == b"not a note\n" and topic(lib).is_symlink()


@pytest.mark.skipif(sys.platform != "win32", reason="directory junctions are a Windows feature")
def test_a_junction_out_of_the_topics_folder_is_refused(lib, tmp_path_factory):
    import _winapi

    elsewhere = tmp_path_factory.mktemp("elsewhere")
    _winapi.CreateJunction(str(elsewhere), str(topic(lib)))
    with pytest.raises(ValueError, match="link"):
        library_server.topic_note("Entrance pupil")
    assert list(elsewhere.iterdir()) == []


@pytest.mark.skipif(sys.platform != "win32", reason="directory junctions are a Windows feature")
def test_a_dangling_junction_is_never_replaced(tmp_path):
    import _winapi

    gone = tmp_path / "gone"
    gone.mkdir()
    link = tmp_path / "note.md"
    _winapi.CreateJunction(str(gone), str(link))
    gone.rmdir()  # now it points nowhere
    with pytest.raises(FileExistsError):
        safe_io.create_bytes(link, b"template")
    assert os.path.lexists(link) and not gone.exists() and leftovers(tmp_path) == []


def test_a_dangling_symlink_is_never_replaced(tmp_path):
    link = tmp_path / "note.md"
    link_or_skip(lambda: os.symlink(tmp_path / "nowhere.md", link), "symlink")
    with pytest.raises(FileExistsError):
        safe_io.create_bytes(link, b"template")
    assert link.is_symlink() and not (tmp_path / "nowhere.md").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="directory junctions are a Windows feature")
@pytest.mark.parametrize("linked", ["topics", "notes"])
def test_topic_notes_kept_elsewhere_through_a_junction_still_work(lib, tmp_path_factory, linked):
    """notes/topics/ (or notes/) on OneDrive through a junction: the user's arrangement."""
    import _winapi
    import shutil

    onedrive = tmp_path_factory.mktemp("OneDrive")
    here = lib / "notes" / "topics" if linked == "topics" else lib / "notes"
    shutil.move(here, onedrive / here.name)
    _winapi.CreateJunction(str(onedrive / here.name), str(here))
    path = library_server.topic_note("Entrance pupil")
    real = onedrive / ("topics" if linked == "topics" else "notes/topics") / "entrance-pupil.md"
    assert path == topic(lib) and real.read_text("utf-8").startswith("# Entrance pupil")


# --- safe_io.create_bytes -----------------------------------------------------------------------


def test_create_bytes_makes_a_new_file_whole(tmp_path):
    safe_io.create_bytes(tmp_path / "sub" / "new.md", b"whole content\n")
    assert (tmp_path / "sub" / "new.md").read_bytes() == b"whole content\n"
    assert leftovers(tmp_path / "sub") == []


def test_create_bytes_never_replaces_an_existing_file(tmp_path):
    (tmp_path / "note.md").write_bytes(MINE)
    with pytest.raises(FileExistsError):
        safe_io.create_bytes(tmp_path / "note.md", b"template")
    assert (tmp_path / "note.md").read_bytes() == MINE and leftovers(tmp_path) == []


def unsupported(*args, **kwargs):  # what a file system without hard links answers on Windows
    raise OSError(errno.EINVAL, "The request is not supported", None, 50)


def test_without_hard_links_it_creates_exclusively(tmp_path, monkeypatch):
    monkeypatch.setattr(safe_io.os, "link", unsupported)
    safe_io.create_bytes(tmp_path / "new.md", b"via the exclusive fallback\n")
    assert (tmp_path / "new.md").read_bytes() == b"via the exclusive fallback\n"
    (tmp_path / "mine.md").write_bytes(MINE)
    with pytest.raises(FileExistsError):  # the fallback never replaces either
        safe_io.create_bytes(tmp_path / "mine.md", b"template")
    assert (tmp_path / "mine.md").read_bytes() == MINE and leftovers(tmp_path) == []


def test_already_there_is_never_taken_for_unsupported(tmp_path, monkeypatch):
    """Something appeared at the very last moment: the link says so, and that's final (no
    fallback that could write)."""

    def appeared(src, dst, *a, **k):
        raise FileExistsError(errno.EEXIST, "exists", str(dst))

    monkeypatch.setattr(safe_io.os, "link", appeared)
    with pytest.raises(FileExistsError):
        safe_io.create_bytes(tmp_path / "new.md", b"template")
    assert not (tmp_path / "new.md").exists() and leftovers(tmp_path) == []


def test_a_failed_creation_leaves_no_temporary_file(tmp_path, monkeypatch):
    def denied(src, dst, *a, **k):
        raise PermissionError(errno.EACCES, "Access is denied", str(dst))

    monkeypatch.setattr(safe_io.os, "link", denied)
    with pytest.raises(PermissionError):  # a real error: no fallback, no file
        safe_io.create_bytes(tmp_path / "new.md", b"template")
    assert not (tmp_path / "new.md").exists() and leftovers(tmp_path) == []

    def disk_full(fd):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(safe_io.os, "fsync", disk_full)
    with pytest.raises(OSError):
        safe_io.create_bytes(tmp_path / "new.md", b"template")
    assert not (tmp_path / "new.md").exists() and leftovers(tmp_path) == []


def test_create_bytes_works_past_the_windows_path_limit(tmp_path):
    deep = tmp_path
    while len(str(deep)) < 270:
        deep = deep / ("long-folder-name-" + "x" * 20)
    path = deep / "note.md"
    assert len(str(path)) > 260
    safe_io.create_bytes(path, b"far down\n")
    assert safe_io.read_bytes(path) == b"far down\n"
    with pytest.raises(FileExistsError):
        safe_io.create_bytes(path, b"template")
    assert safe_io.read_bytes(path) == b"far down\n"
