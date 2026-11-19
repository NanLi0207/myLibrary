"""M7.1 S1a (FA-03): merging a repeated document never loses an acknowledged note save.

`add_book.merge_into` copies the dropped document's notes into the kept copy's chapter notes.
A save from the notes panel (`notes_store.save`) into the same note may run at the same time.
Whichever takes the note's lock first, an acknowledged save must survive in the note or in an
explicit copy, and a save the merge overtook must come back as a version conflict (the panel
keeps its text), never as a silent success that is then written over.

Real threads, synchronised at the merge's write and the save's request for the lock (events,
not sleeps; timeouts are only deadlock guards). Synthetic libraries in temporary folders only.
The audit's own proof re-entered the same thread's RLock and so can't show the repair; these
tests use separate threads. Parametrised over the plain layout, the library reached through a
junction, and a notes folder kept elsewhere through a junction (one lock per real file)."""

import json
import os
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import add_book
import catalog
import library_page
import library_server
import notes_store
import pytest
import safe_io
from test_note_assets import NAME, OTHER, make_doc
from test_notes_containment import link_or_skip

GUARD = 15  # seconds: only ever reached if something deadlocks
MINE = "# Basics\n\nTyped by you in the notes panel.\n"
THEIRS = "# Basics\n\nWritten in the copy that is merged away.\n"
TEMPLATE = "# Basics\n"


def junction(target: Path, link: Path) -> None:
    if sys.platform != "win32":
        pytest.skip("junctions are Windows'")
    import _winapi

    _winapi.CreateJunction(str(target), str(link))


@pytest.fixture(params=["plain", "library-through-a-junction", "notes-folder-elsewhere"])
def pair(request, tmp_path, monkeypatch):
    """(root the notes panel uses, kept row, dropped row): the kept copy's ch01 note is still a
    template, the dropped one's holds text. add_book is pointed at `merge_root`, which may be
    another spelling of the same library."""
    root = tmp_path / "lib"
    root.mkdir()
    kept = make_doc(root, NAME, "Practical Lens Design")
    dropped = make_doc(root, OTHER, "Optics Primer")
    for row in (kept, dropped):  # (a PDF recorded, as for any document: remove_book needs one)
        catalog.set_field(root / "catalog.csv", row["id"], "file", f"books/{row['slug']}.pdf")
        row["file"] = f"books/{row['slug']}.pdf"
    (root / dropped["notes"] / "ch01-basics.md").write_text(THEIRS, encoding="utf-8")
    merge_root = root
    if request.param == "library-through-a-junction":
        merge_root = tmp_path / "alias"
        junction(root, merge_root)
    elif request.param == "notes-folder-elsewhere":  # the kept copy's notes kept elsewhere
        away = tmp_path / "away" / NAME
        away.parent.mkdir()
        (root / kept["notes"]).rename(away)
        junction(away, root / kept["notes"])
    point_add_book_at(merge_root, monkeypatch)
    return root, kept, dropped


def point_add_book_at(root: Path, monkeypatch) -> None:
    for name, value in (("LIBRARY", root), ("CATALOG", root / "catalog.csv"),
                        ("NOTES", root / "notes"), ("EXAMPLES", root / "examples"),
                        ("BOOKS", root / "books"), ("PAPERS", root / "papers"),
                        ("THESES", root / "theses"), ("ARCHIVE", root / "archive"),
                        ("PAGE_CACHE", root / ".cache" / "chapter_pages.json")):  # fmt: skip
        monkeypatch.setattr(add_book, name, value)


def note_of(root: Path, row: dict, name: str = "ch01-basics.md") -> Path:
    return root / row["notes"] / name


def copies_of(root: Path, row: dict) -> list[str]:
    folder = root / row["notes"]
    return sorted(p.read_text(encoding="utf-8") for p in folder.glob("ch01-basics-from-*.md"))


class Race:
    """The merge in one thread, held just before it writes the kept note (after deciding what
    to write there), and a notes-panel save in another, seen asking for the note's lock."""

    def __init__(self, monkeypatch, kept_note: Path):
        self.decided, self.go, self.locking = (
            threading.Event(),
            threading.Event(),
            threading.Event(),
        )
        self.merge_thread = self.save_thread = None
        self.merge_error = self.save_result = self.save_error = None
        real_write, real_lock = safe_io.write_text, safe_io.lock_for
        target = kept_note.name

        def write_text(path, text, *args, **kwargs):
            if threading.current_thread() is self.merge_thread and Path(path).name == target:
                self.decided.set()
                assert self.go.wait(GUARD), "the test never let the merge go on"
            return real_write(path, text, *args, **kwargs)

        def lock_for(path):
            if threading.current_thread() is self.save_thread:
                self.locking.set()
            return real_lock(path)

        monkeypatch.setattr(safe_io, "write_text", write_text)
        monkeypatch.setattr(safe_io, "lock_for", lock_for)

    def merge(self, src: str, dst: str):
        def run():
            try:
                add_book.merge_into(src, dst)
            except Exception as e:  # (reported by the test)
                self.merge_error = e

        self.merge_thread = threading.Thread(target=run)
        self.merge_thread.start()

    def save(self, root: Path, row: dict, key: str, text: str, base):
        def run():
            try:
                self.save_result = notes_store.save(root, row, key, text, base)
            except Exception as e:
                self.save_error = e

        self.save_thread = threading.Thread(target=run)
        self.save_thread.start()

    def finish(self):
        self.go.set()
        for t in (self.merge_thread, self.save_thread):
            if t is not None:
                t.join(GUARD)
                assert not t.is_alive(), "deadlock"
        assert self.merge_error is None, self.merge_error


def test_a_save_while_the_merge_writes_is_never_lost(pair, monkeypatch):
    """The audit's interleaving with real threads: the merge has decided the kept note is only
    a template and is about to write; a save of that note comes in. Before the repair the save
    was acknowledged and then written over. Now the save waits for the note's lock, then meets
    the merged text as a version conflict (nothing acknowledged is lost)."""
    root, kept, dropped = pair
    note = note_of(root, kept)
    base = notes_store.version_of(note.read_bytes())
    race = Race(monkeypatch, note)
    race.merge(dropped["id"], kept["id"])
    assert race.decided.wait(GUARD), "the merge never reached the kept note"
    race.save(root, kept, "file:ch01-basics.md", MINE, base)
    assert race.locking.wait(GUARD), "the save never asked for the note's lock"
    race.save_thread.join(1)  # (bounded: it finishes only if nothing holds the note's lock)
    race.finish()
    on_disk = note.read_text(encoding="utf-8")
    kept_mine = MINE.strip() in on_disk or any(MINE.strip() in c for c in copies_of(root, kept))
    # The merge held the note's lock: the save must not have been acknowledged meanwhile
    assert race.save_error is not None, (
        "the save was acknowledged while the merge was writing the note; your text "
        + ("survived" if kept_mine else "is gone")
    )
    assert isinstance(race.save_error, notes_store.Conflict)  # the panel keeps its text
    assert THEIRS.strip() in on_disk


def test_a_save_before_the_merge_takes_the_note_survives_and_theirs_goes_beside_it(
    pair, monkeypatch
):
    """The other order: the save is acknowledged before the merge takes the note's lock. The
    merge then finds your text, leaves it, and puts the merged text in a -from- copy."""
    root, kept, dropped = pair
    note = note_of(root, kept)
    held, go = threading.Event(), threading.Event()
    real_lock = notes_store.note_lock
    merge_thread = None

    def note_lock(path):
        if threading.current_thread() is merge_thread and Path(path).name == note.name \
                and Path(path).parent.name == NAME:  # fmt: skip
            held.set()
            assert go.wait(GUARD)
        return real_lock(path)

    monkeypatch.setattr(notes_store, "note_lock", note_lock)
    errors = []
    merge_thread = threading.Thread(
        target=lambda: _record(errors, add_book.merge_into, dropped["id"], kept["id"])
    )
    merge_thread.start()
    assert held.wait(GUARD), "the merge never asked for the kept note's lock"
    base = notes_store.version_of(note.read_bytes())  # (the template as written: CRLF here)
    saved = notes_store.save(root, kept, "file:ch01-basics.md", MINE, base)
    assert saved["saved"]
    go.set()
    merge_thread.join(GUARD)
    assert not merge_thread.is_alive() and not errors, errors
    assert note.read_text(encoding="utf-8") == MINE  # your acknowledged text, untouched
    assert [c for c in copies_of(root, kept) if THEIRS.strip() in c]  # theirs beside it


def _record(errors, fn, *args):
    try:
        fn(*args)
    except Exception as e:
        errors.append(e)


def test_a_new_note_saved_while_the_merge_creates_it_is_never_lost(pair, monkeypatch):
    """The kept copy's chapter 2 note doesn't exist yet (the README links it); the merge and a
    first save from the panel create it at the same time. Only one publication wins; the other
    becomes a conflict, never an acknowledged save written over. In every layout."""
    root, kept, dropped = pair
    readme2 = "- [ ] [Ch 2: Stops](ch02-stops.md)\n"
    for row in (kept, dropped):
        (root / row["notes"] / "README.md").write_text(
            (root / row["notes"] / "README.md").read_text("utf-8") + readme2, "utf-8")  # fmt: skip
    (root / dropped["notes"] / "ch02-stops.md").write_text("# Stops\n\nTheirs.\n", "utf-8")
    note = root / kept["notes"] / "ch02-stops.md"
    assert not note.exists()
    race = Race(monkeypatch, note)
    race.merge(dropped["id"], kept["id"])
    assert race.decided.wait(GUARD)
    race.save(root, kept, "file:ch02-stops.md", "# Stops\n\nMine.\n", None)  # a new note
    assert race.locking.wait(GUARD)
    race.save_thread.join(1)
    race.finish()
    text = note.read_text(encoding="utf-8")
    assert race.save_error is not None, "a first save was acknowledged, then written over"
    assert isinstance(race.save_error, notes_store.Conflict)
    assert "Theirs." in text


def test_a_copy_name_taken_meanwhile_is_never_written_over(tmp_path, monkeypatch):
    """Your kept note has text, so theirs goes to a -from- copy; that name already holds other
    text: the next free name is used, nothing is replaced, and a second merge adds nothing."""
    root = tmp_path / "lib"
    root.mkdir()
    kept = make_doc(root, NAME, "Practical Lens Design")
    dropped = make_doc(root, OTHER, "Optics Primer")
    (root / kept["notes"] / "ch01-basics.md").write_text(MINE, encoding="utf-8")
    (root / dropped["notes"] / "ch01-basics.md").write_text(THEIRS, encoding="utf-8")
    taken = root / kept["notes"] / f"ch01-basics-from-{OTHER}.md"
    taken.write_text("# Basics\n\nSomething else entirely.\n", encoding="utf-8")
    point_add_book_at(root, monkeypatch)
    before = {p.name: p.read_bytes() for p in (root / kept["notes"]).iterdir()}
    add_book.merge_into(dropped["id"], kept["id"])
    after = {p.name: p.read_bytes() for p in (root / kept["notes"]).iterdir()}
    for name in ("ch01-basics.md", taken.name):
        assert after[name] == before[name]  # never written over
    new = set(after) - set(before)
    assert new == {f"ch01-basics-from-{OTHER}-2.md"}
    assert THEIRS.strip() in (root / kept["notes"] / f"ch01-basics-from-{OTHER}-2.md").read_text(
        "utf-8"
    )
    add_book.merge_into(dropped["id"], kept["id"])  # run again: nothing new
    assert {p.name for p in (root / kept["notes"]).iterdir()} == set(after)


def test_one_lock_per_real_note_whatever_the_spelling(tmp_path):
    """The note lock is keyed on the real file: a library or notes folder reached through a
    junction shares the lock of its real path (safe_io.lock_for alone does not)."""
    real = tmp_path / "real"
    (real / "notes" / NAME).mkdir(parents=True)
    alias = tmp_path / "alias"
    junction(real, alias)
    a = real / "notes" / NAME / "ch01-basics.md"
    b = alias / "notes" / NAME / "ch01-basics.md"
    assert notes_store.note_lock(a) is notes_store.note_lock(b)
    assert safe_io.lock_for(a) is safe_io.lock_for(b)  # (every writer: README writers too)


# --- Codex S1a review: the source note's lifecycle (finding 1) -------------------------------

MINE_SRC = "# Basics\n\nTyped in the copy that is being merged away.\n"


def full_lifecycle(src: str, dst: str) -> None:
    """What Refresh does for an identical pair (library_jobs._check_catalog_repeats)."""
    with add_book.FILING, safe_io.critical():
        add_book.merge_into(src, dst)
        add_book.remove_book(src, dry_run=False, yes=True, merged_into=dst)


def test_a_source_save_before_the_merge_is_carried_over(pair):
    root, kept, dropped = pair
    src_note = note_of(root, dropped)
    base = notes_store.version_of(src_note.read_bytes())
    assert notes_store.save(root, dropped, "file:ch01-basics.md", MINE_SRC, base)["saved"]
    full_lifecycle(dropped["id"], kept["id"])
    assert MINE_SRC.strip() in "\n".join(
        copies_of(root, kept) + [note_of(root, kept).read_text("utf-8")]
    )


def test_a_source_save_after_the_merge_read_it_is_refused_not_lost(pair, monkeypatch):
    """The merge has read the dropped document's note and is writing the kept copy; a save of
    the dropped note now would be acknowledged but never reach the kept copy (it goes to
    archive/ with the folder). It must be refused as a recoverable conflict instead."""
    root, kept, dropped = pair
    src_note = note_of(root, dropped)
    held, go = threading.Event(), threading.Event()
    real = add_book._merge_note
    merge_thread = None

    def hold(*args, **kwargs):
        if threading.current_thread() is merge_thread:
            held.set()
            assert go.wait(GUARD)
        return real(*args, **kwargs)

    monkeypatch.setattr(add_book, "_merge_note", hold)
    errors = []
    merge_thread = threading.Thread(
        target=lambda: _record(errors, full_lifecycle, dropped["id"], kept["id"])
    )
    merge_thread.start()
    assert held.wait(GUARD), "the merge never reached the kept copy's note"
    base = notes_store.version_of(src_note.read_bytes())
    try:
        notes_store.save(root, dropped, "file:ch01-basics.md", MINE_SRC, base)
        acknowledged = True
    except notes_store.Retiring:
        acknowledged = False
    go.set()
    merge_thread.join(GUARD)
    assert not merge_thread.is_alive() and not errors, errors
    kept_texts = "\n".join(copies_of(root, kept) + [note_of(root, kept).read_text("utf-8")])
    assert not acknowledged or MINE_SRC.strip() in kept_texts, (
        "a save of the merged-away note was acknowledged, then left behind in archive/"
    )
    assert not acknowledged  # (refused: the panel keeps it in the editor)


# --- Codex S1a re-review: admission and draining (finding 1) ---------------------------------
# A write admitted before a retirement (a merge, or a removal on its own) is held at the very
# moment it publishes its file. The retirement must wait for it, then carry it over (merge) or
# archive it with the rest (removal): never an acknowledged write left behind, never a folder
# recreated after it moved. Writes asked for while it waits are refused (Retiring).


class SpyAdmission(threading.Condition):
    """notes_store's admission registry, telling the test when a retirement starts to wait."""

    def __init__(self, waiting: threading.Event):
        super().__init__()
        self.waiting = waiting

    def wait_for(self, predicate, timeout=None):
        self.waiting.set()
        return super().wait_for(predicate, timeout)


PICTURE_MARK = b"made-for-the-test"


def a_picture() -> bytes:
    from test_note_assets import picture

    return picture()


def holds_bytes(folder: Path, wanted: bytes) -> bool:
    return any(wanted in f.read_bytes() for f in folder.rglob("*") if f.is_file())


@pytest.mark.parametrize("lifecycle", ["merge", "removal"])
@pytest.mark.parametrize("write", ["existing note", "new note", "image"])
def test_a_write_admitted_before_retirement_is_published_first(pair, monkeypatch, lifecycle, write):
    root, kept, dropped = pair
    if write == "new note":
        readme = root / dropped["notes"] / "README.md"
        readme.write_text(readme.read_text("utf-8") + "- [ ] [Ch 2: Stops](ch02-stops.md)\n",
                          encoding="utf-8")  # fmt: skip
    key = "file:ch02-stops.md" if write == "new note" else "file:ch01-basics.md"
    base = (
        None if write == "new note" else notes_store.version_of(note_of(root, dropped).read_bytes())
    )
    picture = a_picture()
    held, go = threading.Event(), threading.Event()
    progress, done = threading.Event(), threading.Event()  # (retirement waiting; finished)
    writer = None
    for name in ("write_bytes", "create_bytes"):  # (its publication: a note, an image)
        real = getattr(safe_io, name)

        def publish(path, *args, _real=real, **kwargs):
            if threading.current_thread() is writer:
                held.set()
                assert go.wait(GUARD), "the test never let the write publish"
            return _real(path, *args, **kwargs)

        monkeypatch.setattr(safe_io, name, publish)
    monkeypatch.setattr(notes_store, "_admission", SpyAdmission(progress), raising=False)
    outcome, errors = [], []

    def write_it():
        try:
            if write == "image":
                outcome.append(notes_store.save_asset(root, dropped, picture))
            else:
                outcome.append(notes_store.save(root, dropped, key, MINE_SRC, base))
        except Exception as e:
            outcome.append(e)

    def retire():
        try:
            if lifecycle == "merge":
                full_lifecycle(dropped["id"], kept["id"])
            else:
                add_book.remove_book(dropped["id"], dry_run=False, yes=True)
        except Exception as e:
            errors.append(e)
        finally:
            done.set()
            progress.set()

    writer = threading.Thread(target=write_it)
    writer.start()
    assert held.wait(GUARD), "the write never reached its publication"
    retirer = threading.Thread(target=retire)
    retirer.start()
    assert progress.wait(GUARD), "the retirement neither waited nor finished"
    assert not done.is_set(), "the retirement went on while an admitted write wasn't published"
    assert (root / dropped["notes"]).is_dir() and dropped["id"] in catalog.load(
        root / "catalog.csv"
    ), "something moved before the admitted write was published"
    with pytest.raises(notes_store.Retiring):  # (a new write, while it waits: refused)
        notes_store.save(root, dropped, "file:ch01-basics.md", "late\n", None, overwrite=None)
    go.set()
    for t in (writer, retirer):
        t.join(GUARD)
        assert not t.is_alive(), "deadlock"
    assert not errors, errors
    assert not isinstance(outcome[0], Exception), outcome  # acknowledged
    assert not (root / dropped["notes"]).exists(), "the merged-away notes folder was recreated"
    wanted = picture if write == "image" else b"Typed in the copy that is being merged away."
    where = root / kept["notes"] if lifecycle == "merge" else root / "archive"
    assert holds_bytes(where, wanted), "the acknowledged write was left behind"


def test_a_save_with_a_stale_row_after_retirement_writes_nothing(pair):
    root, kept, dropped = pair
    base = notes_store.version_of(note_of(root, dropped).read_bytes())
    full_lifecycle(dropped["id"], kept["id"])
    with pytest.raises(notes_store.Retiring):
        notes_store.save(root, dropped, "file:ch01-basics.md", MINE_SRC, base)
    with pytest.raises(notes_store.Retiring):  # (overwrite too)
        notes_store.save(root, dropped, "file:ch01-basics.md", MINE_SRC, base, overwrite=base)
    with pytest.raises(notes_store.Retiring):
        notes_store.save_asset(root, dropped, a_picture())
    assert not (root / dropped["notes"]).exists()


# --- Codex S1a review: one lock for every README writer (finding 2) ---------------------------


@pytest.fixture(params=["junction", "symlink"])
def two_spellings(request, tmp_path):
    """(real root, another spelling of it): a junction, or a directory symlink."""
    root = tmp_path / "lib"
    root.mkdir()
    alias = tmp_path / "alias"
    if request.param == "junction":
        junction(root, alias)
    else:
        link_or_skip(lambda: os.symlink(root, alias, target_is_directory=True), "symlink")
    return root, alias


def test_readme_writers_through_two_spellings_never_lose_an_update(two_spellings, monkeypatch):
    """The notes panel saves the README through one spelling of the library; a tick, a page
    position or a merge updates it through another (safe_io.update_text, as they all do). The
    panel's write is held inside its lock: the other writer must wait, then apply its change on
    top, never write in between and be overwritten."""
    root, alias = two_spellings
    kept = make_doc(root, NAME, "Practical Lens Design")
    readme = root / kept["notes"] / "README.md"
    base = notes_store.version_of(readme.read_bytes())
    panel_text = readme.read_text("utf-8") + "\nMy own line about this book.\n"
    held, go, locking = threading.Event(), threading.Event(), threading.Event()
    real_write, real_lock = safe_io.write_bytes, safe_io.lock_for
    panel = writer = None

    def write_bytes(path, data, *args, **kwargs):
        if threading.current_thread() is panel and Path(path).name == "README.md":
            held.set()
            assert go.wait(GUARD)
        return real_write(path, data, *args, **kwargs)

    def lock_for(path):
        if threading.current_thread() is writer:
            locking.set()
        return real_lock(path)

    monkeypatch.setattr(safe_io, "write_bytes", write_bytes)
    monkeypatch.setattr(safe_io, "lock_for", lock_for)
    errors = []
    panel = threading.Thread(target=lambda: _record(
        errors, notes_store.save, root, kept, "file:README.md", panel_text, base))  # fmt: skip
    panel.start()
    assert held.wait(GUARD), "the panel's save never reached its write"
    alias_readme = alias / kept["notes"] / "README.md"

    def add_position(text: str) -> str:
        return text + "Last read: page 9\n"

    writer = threading.Thread(
        target=lambda: _record(errors, safe_io.update_text, alias_readme, add_position)
    )
    writer.start()
    assert locking.wait(GUARD), "the other writer never asked for the README's lock"
    writer.join(1)  # (bounded: it finishes only if nothing holds the README's lock)
    go.set()
    for t in (panel, writer):
        t.join(GUARD)
        assert not t.is_alive(), "deadlock"
    assert not errors, errors
    final = readme.read_text("utf-8")
    assert "My own line about this book." in final and "Last read: page 9" in final, final


# --- Codex S1a review: containment of every publication (finding 3) --------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="a backslash is a path separator on Windows")
def test_a_readme_link_that_climbs_out_is_never_written(tmp_path, monkeypatch):
    root = tmp_path / "lib"
    root.mkdir()
    kept = make_doc(root, NAME, "Practical Lens Design")
    dropped = make_doc(root, OTHER, "Optics Primer")
    (root / dropped["notes"] / "ch01-basics.md").write_text(THEIRS, encoding="utf-8")
    climbing = "- [ ] [Ch 1: Basics](..\\..\\escape.md)\n"  # (backslashes: Windows separators)
    (root / kept["notes"] / "README.md").write_text(
        "# Practical Lens Design\n\n## Reading progress\n\n" + climbing, encoding="utf-8"
    )
    point_add_book_at(root, monkeypatch)
    add_book.merge_into(dropped["id"], kept["id"])
    assert not (root / "escape.md").exists() and not (tmp_path / "escape.md").exists()
    inside = "\n".join(p.read_text("utf-8") for p in (root / kept["notes"]).glob("*.md"))
    assert THEIRS.strip() in inside


def dangling_link(link: Path, target: Path) -> None:
    link_or_skip(lambda: os.symlink(target, link), "symlink")


def test_a_dangling_link_in_place_of_the_kept_note_is_never_written_through(tmp_path, monkeypatch):
    root = tmp_path / "lib"
    root.mkdir()
    kept = make_doc(root, NAME, "Practical Lens Design")
    dropped = make_doc(root, OTHER, "Optics Primer")
    (root / dropped["notes"] / "ch01-basics.md").write_text(THEIRS, encoding="utf-8")
    outside = tmp_path / "outside" / "stolen.md"
    outside.parent.mkdir()
    note = root / kept["notes"] / "ch01-basics.md"
    note.unlink()
    dangling_link(note, outside)
    point_add_book_at(root, monkeypatch)
    add_book.merge_into(dropped["id"], kept["id"])
    assert not outside.exists() and note.is_symlink()  # neither written through nor replaced
    assert [c for c in copies_of(root, kept) if THEIRS.strip() in c]


def test_a_dangling_link_on_a_copy_name_is_skipped(tmp_path, monkeypatch):
    root = tmp_path / "lib"
    root.mkdir()
    kept = make_doc(root, NAME, "Practical Lens Design")
    dropped = make_doc(root, OTHER, "Optics Primer")
    (root / kept["notes"] / "ch01-basics.md").write_text(MINE, encoding="utf-8")
    (root / dropped["notes"] / "ch01-basics.md").write_text(THEIRS, encoding="utf-8")
    outside = tmp_path / "outside" / "stolen.md"
    outside.parent.mkdir()
    trap = root / kept["notes"] / f"ch01-basics-from-{OTHER}.md"
    dangling_link(trap, outside)
    point_add_book_at(root, monkeypatch)
    add_book.merge_into(dropped["id"], kept["id"])
    assert not outside.exists() and trap.is_symlink()
    assert THEIRS.strip() in (root / kept["notes"] / f"ch01-basics-from-{OTHER}-2.md").read_text(
        "utf-8"
    )


def test_a_copy_name_claimed_at_the_last_moment_is_never_written_over(tmp_path, monkeypatch):
    """Another writer takes the copy's name between the merge's check and its write: the
    copy is created exclusively, so the claim survives and the next name is used."""
    root = tmp_path / "lib"
    root.mkdir()
    kept = make_doc(root, NAME, "Practical Lens Design")
    dropped = make_doc(root, OTHER, "Optics Primer")
    (root / kept["notes"] / "ch01-basics.md").write_text(MINE, encoding="utf-8")
    (root / dropped["notes"] / "ch01-basics.md").write_text(THEIRS, encoding="utf-8")
    claim = "# Basics\n\nClaimed by someone else.\n"
    claimed = []
    real_create, real_write = safe_io.create_bytes, safe_io.write_text

    def claim_first(path):
        if "-from-" in Path(path).name and not claimed:
            claimed.append(Path(path))
            real_write(Path(path), claim)

    def create_bytes(path, data, *args, **kwargs):
        claim_first(path)
        return real_create(path, data, *args, **kwargs)

    def write_text(path, text, *args, **kwargs):
        claim_first(path)
        return real_write(path, text, *args, **kwargs)

    monkeypatch.setattr(safe_io, "create_bytes", create_bytes)
    monkeypatch.setattr(safe_io, "write_text", write_text)
    point_add_book_at(root, monkeypatch)
    add_book.merge_into(dropped["id"], kept["id"])
    assert claimed and claimed[0].read_text("utf-8") == claim  # never written over
    assert [c for c in copies_of(root, kept) if THEIRS.strip() in c]


# --- Codex S1a review: choosing the kept copy's chapter note (finding 4) -----------------------


def test_without_a_readme_link_an_earlier_copy_is_never_taken_for_the_chapter(
    tmp_path, monkeypatch
):
    root = tmp_path / "lib"
    root.mkdir()
    kept = make_doc(root, NAME, "Practical Lens Design")
    dropped = make_doc(root, OTHER, "Optics Primer")
    (root / kept["notes"] / "README.md").write_text(
        "# Practical Lens Design\n\n## Reading progress\n\n- [ ] Ch 1: Basics\n", encoding="utf-8"
    )
    earlier = root / kept["notes"] / "ch01-basics-from-aaa-2000-older.md"
    earlier.write_text("# Basics\n\nFrom an earlier merge.\n", encoding="utf-8")
    (root / dropped["notes"] / "ch01-basics.md").write_text(THEIRS, encoding="utf-8")
    point_add_book_at(root, monkeypatch)
    before = earlier.read_bytes()
    add_book.merge_into(dropped["id"], kept["id"])
    assert note_of(root, kept).read_text("utf-8").strip() == THEIRS.strip()  # the chapter's note
    assert earlier.read_bytes() == before
    assert not list((root / kept["notes"]).glob("*-from-*-from-*.md"))  # no copy of a copy


def test_two_candidate_chapter_notes_are_never_guessed(tmp_path, monkeypatch):
    root = tmp_path / "lib"
    root.mkdir()
    kept = make_doc(root, NAME, "Practical Lens Design")
    dropped = make_doc(root, OTHER, "Optics Primer")
    (root / kept["notes"] / "README.md").write_text(
        "# Practical Lens Design\n\n## Reading progress\n\n- [ ] Ch 1: Basics\n", encoding="utf-8"
    )
    (root / kept["notes"] / "ch01-basics.md").unlink()
    a, b = root / kept["notes"] / "ch01-aa.md", root / kept["notes"] / "ch01-bb.md"
    a.write_text("# A\n\nMine A.\n", encoding="utf-8")
    b.write_text("# B\n\nMine B.\n", encoding="utf-8")
    (root / dropped["notes"] / "ch01-basics.md").write_text(THEIRS, encoding="utf-8")
    point_add_book_at(root, monkeypatch)
    add_book.merge_into(dropped["id"], kept["id"])
    assert a.read_text("utf-8") == "# A\n\nMine A.\n" and b.read_text("utf-8") == "# B\n\nMine B.\n"
    assert THEIRS.strip() in note_of(root, kept).read_text("utf-8")  # under its own name


# --- Codex S1a re-review: retirement failures (finding 2) ----------------------------------------


def a_save_works(root: Path, row: dict) -> bool:
    note = note_of(root, row)
    base = notes_store.version_of(note.read_bytes())
    return notes_store.save(root, row, "file:ch01-basics.md", "after it stayed\n", base)["saved"]


@pytest.mark.parametrize("lifecycle", ["merge", "removal"])
def test_a_tombstone_that_cant_be_written_leaves_the_document_open(pair, monkeypatch, lifecycle):
    root, kept, dropped = pair
    before = note_of(root, dropped).read_bytes()

    def no_tombstone(*args, **kwargs):
        raise OSError("disk full (made by the test)")

    monkeypatch.setattr(catalog, "retire", no_tombstone)
    with pytest.raises(OSError):
        if lifecycle == "merge":
            full_lifecycle(dropped["id"], kept["id"])
        else:
            add_book.remove_book(dropped["id"], dry_run=False, yes=True)
    assert dropped["id"] in catalog.load(root / "catalog.csv")
    assert note_of(root, dropped).read_bytes() == before
    assert not notes_store.is_retiring(dropped["id"])
    assert a_save_works(root, dropped)
    assert notes_store.save_asset(root, dropped, a_picture())["name"]


@pytest.mark.parametrize("where", ["the merge", "the removal before anything moves"])
def test_a_retirement_failing_before_any_change_reopens_the_document(pair, monkeypatch, where):
    root, kept, dropped = pair

    def broken(*args, **kwargs):
        raise OSError("made by the test")

    with add_book.FILING, safe_io.critical(), monkeypatch.context() as m:
        if where == "the merge":
            m.setattr(add_book, "_merge_into", broken)
            with pytest.raises(OSError):
                add_book.merge_into(dropped["id"], kept["id"])
        else:  # (merged: then its removal fails while finding its folders)
            add_book.merge_into(dropped["id"], kept["id"])
            m.setattr(add_book, "notes_dir_of", broken)
            with pytest.raises(OSError):
                add_book.remove_book(dropped["id"], dry_run=False, yes=True, merged_into=kept["id"])
    assert dropped["id"] in catalog.load(root / "catalog.csv")
    assert not notes_store.is_retiring(dropped["id"])
    assert a_save_works(root, dropped)


def fail_catalog_removal(monkeypatch):
    def cant(*args, **kwargs):
        raise OSError("catalog.csv is locked (made by the test)")

    monkeypatch.setattr(catalog, "remove", cant)


@pytest.mark.parametrize("lifecycle", ["merge", "removal"])
def test_a_removal_undone_completely_reopens_the_document(pair, monkeypatch, lifecycle):
    root, kept, dropped = pair
    before = note_of(root, dropped).read_bytes()
    fail_catalog_removal(monkeypatch)
    with pytest.raises(OSError):
        if lifecycle == "merge":
            full_lifecycle(dropped["id"], kept["id"])
        else:
            add_book.remove_book(dropped["id"], dry_run=False, yes=True)
    assert note_of(root, dropped).read_bytes() == before  # (moved back)
    assert catalog.resolve(root / "catalog.csv", dropped["id"])["status"] == "live"
    assert not notes_store.is_retiring(dropped["id"])
    assert a_save_works(root, dropped)


@pytest.mark.parametrize("what_fails", ["moving back", "taking the tombstone back"])
def test_a_removal_left_half_done_stays_closed(pair, monkeypatch, what_fails):
    """The removal fails and its undoing fails too: the document is left half moved (its PDF
    still in archive/, or its tombstone still there), its notes folder back in place. It must
    not take writes again until that is put right."""
    root, kept, dropped = pair
    pdf = add_book.library_pdf(dropped)
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4 made by the test")
    fail_catalog_removal(monkeypatch)
    if what_fails == "moving back":
        real = Path.rename

        def rename(self, target):  # (only the PDF can't go back)
            if "archive" in Path(self).parts and Path(self).suffix == ".pdf":
                raise OSError("in use (made by the test)")
            return real(self, target)

        monkeypatch.setattr(Path, "rename", rename)
    else:

        def no_unretire(*args, **kwargs):
            raise OSError("disk full (made by the test)")

        monkeypatch.setattr(catalog, "unretire", no_unretire)
    with pytest.raises(OSError):
        add_book.remove_book(dropped["id"], dry_run=False, yes=True)
    note = note_of(root, dropped)
    before = note.read_bytes()  # (back in place: a save would land)
    version_of = notes_store.version_of
    assert notes_store.is_retiring(dropped["id"])
    with pytest.raises(notes_store.Retiring):
        notes_store.save(root, dropped, "file:ch01-basics.md", "never", version_of(before))
    with pytest.raises(notes_store.Retiring):
        notes_store.save_asset(root, dropped, a_picture())
    assert note.read_bytes() == before
    assert not (root / dropped["notes"] / "assets").exists()


# --- Codex S1a re-review: a write names its own document (finding 3), over HTTP ---------------


@pytest.fixture
def merged_over_http(tmp_path, monkeypatch):
    root = tmp_path / "lib"
    root.mkdir()
    kept = make_doc(root, NAME, "Practical Lens Design")
    dropped = make_doc(root, OTHER, "Optics Primer")
    for row in (kept, dropped):
        catalog.set_field(root / "catalog.csv", row["id"], "file", f"books/{row['slug']}.pdf")
    (root / dropped["notes"] / "ch01-basics.md").write_text(THEIRS, encoding="utf-8")
    point_add_book_at(root, monkeypatch)
    for module in (library_server, library_page):
        monkeypatch.setattr(module, "LIBRARY", root)
        monkeypatch.setattr(module, "CATALOG", root / "catalog.csv")
    full_lifecycle(dropped["id"], kept["id"])
    server = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield root, kept, dropped, f"http://127.0.0.1:{server.server_port}", library_server.TOKEN
    server.shutdown()
    server.server_close()


def http(base, token, path, data: bytes, headers=None):
    sent = {"X-Library-Token": token, **(headers or {})}
    request = urllib.request.Request(base + path, data=data, method="POST", headers=sent)
    try:
        with urllib.request.urlopen(request, timeout=10) as answer:
            return answer.status, answer.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def tree_of(folder: Path) -> dict[str, bytes]:
    return {
        f.relative_to(folder).as_posix(): f.read_bytes() for f in folder.rglob("*") if f.is_file()
    }


def test_a_merged_ids_writes_are_refused_never_redirected(merged_over_http):
    root, kept, dropped, base, token = merged_over_http
    kept_folder = root / kept["notes"]
    before = tree_of(kept_folder)
    current = notes_store.version_of(note_of(root, kept).read_bytes())  # (the kept note now)
    save = {"id": dropped["id"], "key": "file:ch01-basics.md", "text": "stale tab\n"}
    for body in (save | {"base": current},  # (its version matches the kept note's)
                 save | {"base": current, "overwrite": current},
                 save | {"base": None, "key": "file:ch09-new.md"}):  # fmt: skip
        status, answer = http(base, token, "/api/notes/save", json.dumps(body).encode(),
                              {"Content-Type": "application/json"})  # fmt: skip
        assert status == 410, (status, answer)
        assert "merged into another" in json.loads(answer)["error"]
    pasted = {"X-Document-Id": dropped["id"], "X-Note-Key": "file:ch01-basics.md"}
    status, answer = http(base, token, "/api/notes/asset", a_picture(), pasted)
    assert status == 410, (status, answer)
    assert tree_of(kept_folder) == before, "the kept document was written by a stale request"
    assert not (root / dropped["notes"]).exists()
    # (the kept document itself still takes writes: the refusal is about the id named)
    status, _ = http(base, token, "/api/notes/save", json.dumps(
        {"id": kept["id"], "key": "file:ch01-basics.md", "text": "kept\n", "base": current}
    ).encode(), {"Content-Type": "application/json"})  # fmt: skip
    assert status == 200


def test_a_410_names_the_document_that_stays_and_the_status_lookup_writes_nothing(
    merged_over_http,
):
    root, kept, dropped, base, token = merged_over_http
    removed = make_doc(root, "roe-2021-gone-book", "A book removed")
    catalog.retire(root / "catalog.csv", removed["id"], "removed", removed)
    catalog.remove(root / "catalog.csv", removed["id"])
    body = {"id": dropped["id"], "key": "file:ch01-basics.md", "text": "x", "base": None}
    status, answer = http(base, token, "/api/notes/save", json.dumps(body).encode(),
                          {"Content-Type": "application/json"})  # fmt: skip
    assert status == 410 and json.loads(answer)["into"] == kept["id"]
    unknown = "0" * 8 + "-0000-4000-8000-" + "0" * 12
    before = tree_of(root)
    status, answer = http(base, token, "/api/document/status", json.dumps(
        {"ids": [kept["id"], dropped["id"], removed["id"], unknown]}).encode(),
        {"Content-Type": "application/json"})  # fmt: skip
    assert status == 200, answer
    assert json.loads(answer)["documents"] == {
        kept["id"]: {"status": "live"},
        dropped["id"]: {"status": "merged", "into": kept["id"], "title": "Optics Primer"},
        removed["id"]: {"status": "removed", "title": "A book removed"},
        unknown: {"status": "unknown"},
    }
    assert tree_of(root) == before  # (read-only)
    for bad in ({"ids": "x"}, {"ids": ["not an id"]}, {"ids": [kept["id"]] * 201}):
        status, _ = http(base, token, "/api/document/status", json.dumps(bad).encode(),
                         {"Content-Type": "application/json"})  # fmt: skip
        assert status == 400
