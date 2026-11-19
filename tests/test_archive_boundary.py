"""M7.1 S1b (FA-01): "Clear archive" never deletes anything outside the library.

The audit's reproduction: archive/ itself a junction to a folder elsewhere, then Clear archive
deleted a PDF there (only what is inside archive/ was ever checked for links). Now archive/
itself is checked first (library_jobs._checked_archive), every planned file is checked again
before anything is deleted, and a refusal deletes nothing. Synthetic temporary folders only;
link tests skip locally without the right to make symlinks, and fail instead in CI
(MYLIBRARY_REQUIRE_LINK_TESTS=1)."""

import json
import os
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import add_book
import library_jobs
import library_server
import pytest
import safe_io
from test_library_jobs import TEMPLATE
from test_notes_containment import link_or_skip


@pytest.fixture
def library(tmp_path, monkeypatch):
    """An empty library in a temporary folder (as in test_library_jobs)."""
    root = tmp_path / "library"
    root.mkdir()
    monkeypatch.setattr(add_book, "LIBRARY", root)
    monkeypatch.setattr(add_book, "ARCHIVE", root / "archive")
    return root


def junction(target: Path, link: Path) -> None:
    if sys.platform != "win32":
        pytest.skip("directory junctions are a Windows feature")
    import _winapi

    _winapi.CreateJunction(str(target), str(link))


def tree(folder: Path) -> dict[str, bytes]:
    """Every file under `folder` (links not followed) and its bytes; folders too, as None."""
    found = {}
    for here, dirs, files in os.walk(folder):
        for name in dirs + files:
            path = Path(here) / name
            key = path.relative_to(folder).as_posix()
            found[key] = path.read_bytes() if path.is_file() and not path.is_symlink() else None
    return found


@pytest.fixture
def outside(tmp_path) -> Path:
    """A folder outside the library that looks like an archive: a PDF, a template, nested
    folders, other files. Nothing in it may ever be deleted."""
    root = tmp_path / "outside"
    (root / "books").mkdir(parents=True)
    (root / "books" / "elsewhere.pdf").write_bytes(b"%PDF not in the library")
    (root / "books" / ".gitkeep").write_text("")
    (root / "notes" / "doe-2001-book").mkdir(parents=True)
    (root / "notes" / "doe-2001-book" / "ch01-intro.md").write_text(TEMPLATE)
    (root / "notes" / "doe-2001-book" / "README.md").write_bytes(b"# mine\n")
    (root / "notes" / "ann-2001-book").mkdir()
    (root / "books" / "old.pdf").write_bytes(b"%PDF outside, the same name as an archived one")
    (root / "other.txt").write_bytes(b"someone else's file")
    return root


def archive_of(library: Path) -> Path:
    return library / "archive"


def a_plain_archive(library: Path) -> Path:
    """archive/ as Clear archive finds it normally: a PDF and a template that go, a README
    that stays."""
    archive = archive_of(library)
    (archive / "books").mkdir(parents=True)
    (archive / "books" / "old.pdf").write_bytes(b"%PDF old")
    (archive / "notes" / "ann-2001-book").mkdir(parents=True)
    (archive / "notes" / "ann-2001-book" / "ch01-intro.md").write_text(TEMPLATE)
    (archive / "notes" / "ann-2001-book" / "README.md").write_bytes(b"# Ann's book\n")
    return archive


def refused_both_ways(library: Path, *folders: Path) -> None:
    """The summary and the clearing both refuse, and nothing anywhere changes."""
    before = {f: tree(f) for f in folders}
    with pytest.raises(library_jobs.UnsafeArchive) as refused:
        library_jobs.archive_summary()
    assert "nothing was deleted" in str(refused.value) and "什么也没有删除" in str(refused.value)
    with pytest.raises(library_jobs.UnsafeArchive):
        library_jobs.clear_archive()
    assert {f: tree(f) for f in folders} == before


# --- ordinary clearing --------------------------------------------------------------------------


def test_an_ordinary_archive_is_still_cleared(library):
    archive = a_plain_archive(library)
    assert library_jobs.archive_summary()["files"] == 2
    assert library_jobs.clear_archive()["files"] == 2
    assert tree(archive) == {"notes": None, "notes/ann-2001-book": None,
                             "notes/ann-2001-book/README.md": b"# Ann's book\n"}  # fmt: skip


def test_a_missing_archive_is_empty_and_never_made(library):
    assert library_jobs.archive_summary() == {"files": 0, "bytes": 0, "kept": []}
    assert library_jobs.clear_archive()["files"] == 0
    assert not os.path.lexists(archive_of(library))


# --- archive/ itself redirected: the audit's reproduction ----------------------------------------


@pytest.mark.parametrize("kind", ["junction", "symlink"])
def test_an_archive_redirected_elsewhere_is_refused(library, outside, kind):
    archive = archive_of(library)
    if kind == "junction":
        junction(outside, archive)
    else:
        link_or_skip(lambda: os.symlink(outside, archive, target_is_directory=True), "symlink")
    refused_both_ways(library, outside, library)
    assert os.path.lexists(archive)  # (the link itself is left as it is)


def test_an_archive_redirected_back_into_the_library_is_refused(library):
    """A junction is refused even when it leads somewhere in the library: only the plain
    folder archive/ is ever cleared."""
    elsewhere = library / "books"
    elsewhere.mkdir()
    (elsewhere / "a-book-in-the-library.pdf").write_bytes(b"%PDF in use")
    junction(elsewhere, archive_of(library))
    refused_both_ways(library, library)


def test_a_dangling_archive_link_is_refused_not_missing(library, tmp_path):
    archive = archive_of(library)
    link_or_skip(lambda: os.symlink(tmp_path / "gone", archive, target_is_directory=True),
                 "symlink")  # fmt: skip
    refused_both_ways(library, library)
    assert os.path.lexists(archive) and not (tmp_path / "gone").exists()


def test_a_file_named_archive_is_refused(library):
    archive_of(library).write_bytes(b"%PDF not a folder")
    refused_both_ways(library, library)


def test_an_archive_set_outside_the_library_is_refused(library, outside, monkeypatch):
    """A plain folder, but not the library's own archive/ (the path given for it leads out)."""
    monkeypatch.setattr(add_book, "ARCHIVE", outside)
    refused_both_ways(library, outside, library)


def test_a_frozen_library_is_never_cleared(library, monkeypatch):
    archive = a_plain_archive(library)
    monkeypatch.setattr(safe_io, "_frozen", list(safe_io._frozen))
    safe_io.freeze(library)
    before = tree(archive)
    assert library_jobs.archive_summary()["files"] == 2  # (reading it is harmless)
    with pytest.raises(library_jobs.UnsafeArchive, match="frozen"):
        library_jobs.clear_archive()
    assert tree(archive) == before


# --- links inside archive/: still never followed --------------------------------------------------


@pytest.mark.parametrize("kind", ["junction", "symlink"])
def test_nested_links_and_broken_links_are_kept_and_never_followed(
    library, outside, tmp_path, kind
):
    archive = a_plain_archive(library)
    deep = archive / "notes" / "ann-2001-book" / "figures"
    deep.mkdir()
    if kind == "junction":
        links = [deep / "elsewhere", archive / "books" / "more", archive / "books" / "broken"]
        junction(outside, links[0])
        junction(outside / "books", links[1])
        (tmp_path / "soon-gone").mkdir()
        junction(tmp_path / "soon-gone", links[2])
        (tmp_path / "soon-gone").rmdir()  # (a junction to nothing)
    else:
        links = [archive / "books" / "linked.pdf", deep / "elsewhere",
                 archive / "books" / "broken.pdf"]  # fmt: skip
        link_or_skip(lambda: os.symlink(outside / "books" / "elsewhere.pdf", links[0]),
                     "symlink")  # fmt: skip
        os.symlink(outside, links[1], target_is_directory=True)
        os.symlink(tmp_path / "gone.pdf", links[2])
    before = tree(outside)
    summary = library_jobs.archive_summary()
    assert summary["files"] == 2  # (only the archive's own PDF and template)
    library_jobs.clear_archive()
    assert tree(outside) == before
    assert all(os.path.lexists(link) for link in links)
    assert not (archive / "books" / "old.pdf").exists()


# --- a linked library folder: the user's own arrangement ------------------------------------------


def test_a_library_reached_through_a_junction_is_cleared_normally(
    library, outside, tmp_path, monkeypatch
):
    archive = a_plain_archive(library)
    alias = tmp_path / "alias"
    junction(library, alias)
    monkeypatch.setattr(add_book, "LIBRARY", alias)
    monkeypatch.setattr(add_book, "ARCHIVE", alias / "archive")
    before = tree(outside)
    assert library_jobs.clear_archive()["files"] == 2
    assert not (archive / "books" / "old.pdf").exists()
    assert (archive / "notes" / "ann-2001-book" / "README.md").exists()
    assert tree(outside) == before


def test_a_frozen_library_reached_through_a_junction_is_never_cleared(
    library, tmp_path, monkeypatch
):
    archive = a_plain_archive(library)
    alias = tmp_path / "alias"
    junction(library, alias)
    monkeypatch.setattr(add_book, "LIBRARY", alias)
    monkeypatch.setattr(add_book, "ARCHIVE", alias / "archive")
    monkeypatch.setattr(safe_io, "_frozen", list(safe_io._frozen))
    safe_io.freeze(library)
    before = tree(archive)
    with pytest.raises(library_jobs.UnsafeArchive, match="frozen"):
        library_jobs.clear_archive()
    assert tree(archive) == before


# --- changed between planning and deleting ------------------------------------------------


@pytest.mark.parametrize("what", ["archive/", "a planned folder"])
def test_a_redirect_made_after_planning_deletes_nothing(library, outside, monkeypatch, what):
    """Something replaced by a junction between the plan and the deleting (a cooperating
    check: not a defence against another program swapping folders between two checks)."""
    archive = a_plain_archive(library)
    real_plan = library_jobs._archive_plan

    def plan_then_swap(*args, **kwargs):
        planned = real_plan(*args, **kwargs)
        if what == "archive/":
            archive.rename(library / "archive-moved")
            junction(outside, archive)
        else:
            (archive / "books").rename(library / "books-moved")
            junction(outside / "books", archive / "books")
        return planned

    monkeypatch.setattr(library_jobs, "_archive_plan", plan_then_swap)
    before = tree(outside)
    with pytest.raises(library_jobs.UnsafeArchive):
        library_jobs.clear_archive()
    assert tree(outside) == before
    if what == "a planned folder":  # (nothing of the archive's own was deleted either)
        assert (archive / "notes" / "ann-2001-book" / "ch01-intro.md").exists()


# --- over HTTP: the Settings dialog's request ----------------------------------------------


@pytest.fixture
def served(library, monkeypatch):
    monkeypatch.setattr(library_server, "LIBRARY", library)
    monkeypatch.setattr(library_server, "CATALOG", library / "catalog.csv")
    server = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def call(body):
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/archive", data=json.dumps(body).encode(),
            method="POST", headers={"Content-Type": "application/json",
                                    "X-Library-Token": library_server.TOKEN},
        )  # fmt: skip
        try:
            with urllib.request.urlopen(request, timeout=10) as answer:
                return answer.status, json.load(answer)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    yield call
    server.shutdown()
    server.server_close()


def test_the_settings_request_is_refused_with_a_reason(library, outside, served):
    junction(outside, archive_of(library))
    before = tree(outside)
    for body in ({}, {"clear": True}):
        status, answer = served(body)
        assert status == 409 and "nothing was deleted" in answer["error"]
    assert tree(outside) == before
