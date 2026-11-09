"""The showcase library/ in the tool's folder is frozen: kept as it is in git, never opened or
changed by the app. paths.ensure_library refuses it (the server and add_book.py start there),
every write through safe_io into it is refused, and each script that writes into a library
refuses it before doing anything. test_library/ (the canonical Test & Demo library) is frozen the
same way. Nothing here writes into either: every refusal comes before any file is touched, and
the folders are compared before and after."""

import subprocess
import sys
from pathlib import Path

import book_search
import libraries
import library_server
import paths
import pytest
import safe_io
from test_libraries import own_registry, personal_copy  # noqa: F401 (the fixture)

SHOWCASE = paths.APP / paths.SHOWCASE_LIBRARY
SCRIPTS = paths.APP / "scripts"


def stat_snapshot(folder: Path) -> dict:
    """Every file and folder with its size and modification time (cheap: the showcase holds
    the author's PDFs locally, which aren't hashed here)."""
    return {
        p.relative_to(folder).as_posix(): (p.is_dir(), p.stat().st_size, p.stat().st_mtime_ns)
        for p in sorted(folder.rglob("*"))
    }


@pytest.fixture(scope="module")
def showcase_before():
    if not (SHOWCASE / "catalog.csv").is_file():
        pytest.skip("no showcase library/ in this checkout")
    return stat_snapshot(SHOWCASE)


def test_the_frozen_folders_are_known(tmp_path):
    assert paths.frozen_reason(SHOWCASE) and "public showcase" in paths.frozen_reason(SHOWCASE)
    assert paths.frozen_reason(SHOWCASE / "notes" / "anything.md")
    assert "Test & Demo" in paths.frozen_reason(paths.APP / paths.CANONICAL_TEST_LIBRARY)
    assert paths.frozen_reason(tmp_path) == ""
    assert paths.frozen_reason(paths.APP / "library-copy") == ""  # (only that folder)
    with pytest.raises(SystemExit, match="public showcase"):
        paths.ensure_library(SHOWCASE)


def test_safe_io_refuses_every_write_into_the_showcase(showcase_before):
    target = SHOWCASE / "notes" / "never-written.md"
    for write in (
        lambda: safe_io.write_text(target, "x"),
        lambda: safe_io.write_bytes(target, b"x"),
        lambda: safe_io.create_text(target, "x"),
        lambda: safe_io.update_text(SHOWCASE / "catalog.csv", lambda text: text + "x"),
        lambda: safe_io.update_json(SHOWCASE / "notes" / "reading-log.json", lambda d: None, {}),
    ):
        with pytest.raises(safe_io.FrozenLocation):
            write()
    assert stat_snapshot(SHOWCASE) == showcase_before


def test_normal_libraries_stay_writable(tmp_path):
    library = personal_copy(tmp_path / "Copy of the showcase")
    safe_io.write_text(library / "notes" / "mine.md", "my own words\n")
    assert (library / "notes" / "mine.md").read_text(encoding="utf-8") == "my own words\n"
    assert paths.ensure_library(library) == library


@pytest.mark.skipif(sys.platform != "win32", reason="junctions are Windows'")
def test_a_link_into_a_frozen_folder_is_refused_too(tmp_path, monkeypatch):
    import _winapi

    frozen = tmp_path / "frozen"
    (frozen / "notes").mkdir(parents=True)
    monkeypatch.setattr(safe_io, "_frozen", list(safe_io._frozen))
    safe_io.freeze(frozen)
    _winapi.CreateJunction(str(frozen), str(tmp_path / "way-in"))
    with pytest.raises(safe_io.FrozenLocation):
        safe_io.write_text(tmp_path / "way-in" / "notes" / "x.md", "x")
    assert not (frozen / "notes" / "x.md").exists()


def test_the_search_index_is_never_built_there(monkeypatch, showcase_before):
    monkeypatch.setattr(book_search, "INDEX", SHOWCASE / ".cache" / "books.db")
    with pytest.raises(safe_io.FrozenLocation):
        book_search._connect()
    assert stat_snapshot(SHOWCASE) == showcase_before


def test_it_is_never_added_or_chosen_as_a_library(own_registry, showcase_before):  # noqa: F811
    report = libraries.check(SHOWCASE)
    assert not report["ok"] and any("public showcase" in e for e in report["errors"])
    with pytest.raises(libraries.LibraryError, match="public showcase"):
        libraries.register(SHOWCASE)
    with pytest.raises(ValueError, match="public showcase"):
        library_server.change_settings({"library": str(SHOWCASE)})
    assert stat_snapshot(SHOWCASE) == showcase_before


@pytest.mark.parametrize("script, args", [
    ("library_server.py", ["--port", "0", "--no-browser", "--no-download"]),
    ("add_book.py", ["--dry-run"]),
    ("book_search.py", []),
    ("add_bookmarks.py", []),
    ("ocr_pdf.py", ["books/x.pdf"]),
    ("shelves.py", []),
    ("subjects.py", []),
    ("backup.py", []),
    ("library_page.py", []),
])  # fmt: skip
def test_every_writing_script_refuses_it(script, args, showcase_before):
    done = subprocess.run(
        [sys.executable, str(SCRIPTS / script), "--library", str(SHOWCASE), *args],
        capture_output=True, text=True, encoding="utf-8", timeout=120, cwd=paths.APP,
    )  # fmt: skip
    assert done.returncode != 0, done.stdout
    assert "public showcase" in done.stderr, done.stderr[-500:]
    assert stat_snapshot(SHOWCASE) == showcase_before


def test_migrate_ids_never_migrates_it(showcase_before):
    done = subprocess.run(
        [sys.executable, str(SCRIPTS / "migrate_ids.py"), "--library", str(SHOWCASE), "--apply"],
        capture_output=True, text=True, encoding="utf-8", timeout=120, cwd=paths.APP,
    )  # fmt: skip
    assert done.returncode != 0 and "frozen" in done.stderr
    assert stat_snapshot(SHOWCASE) == showcase_before
