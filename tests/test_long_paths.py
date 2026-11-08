"""Paths longer than Windows' usual limit (MAX_PATH, 260 characters; long paths are off by
default): safe_io's atomic writes, reads and checks, and the notes store on top of them
(conflict archives, Keep mine, Use the disk version, link containment), in a library deep
enough to pass the limit. Each folder and file name stays well under the 255-character limit
of one name: it's the whole path that is long. Temporary folders only."""

import os
import sys
from pathlib import Path

import notes_store
import pytest
import safe_io
from notes_store import Conflict, NoteError
from testlib import put

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows' path length limit")

NAME = "doe-2015-practical-lens-design"
SECRET = b"outside the notes\n"


def deep(base: Path, total: int) -> Path:
    """A folder under `base` whose path is at least `total` characters, made of 40-character
    names (created through safe_io's long-path form)."""
    folder = base
    n = 0
    while len(str(folder)) < total:
        folder = folder / f"{n:02d}-a-deep-folder-of-a-very-patient-reader"
        n += 1
    safe_io._os_path(folder).mkdir(parents=True, exist_ok=True)
    return folder


def files_in(folder: Path) -> list[str]:
    return sorted(p.name for p in safe_io._os_path(folder).iterdir())


def long_paths_are_off() -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SYSTEM\CurrentControlSet\Control\FileSystem") as key:  # fmt: skip
            return winreg.QueryValueEx(key, "LongPathsEnabled")[0] != 1
    except OSError:
        return True


# --- the helper --------------------------------------------------------------------------------


def test_only_long_absolute_paths_get_the_extended_form():
    short = Path(r"C:\Users\me\library\notes\x.md")
    assert safe_io._os_path(short) == short  # unchanged
    assert safe_io._os_path(Path("notes/x.md")) == Path("notes/x.md")  # relative: unchanged
    long = "C:\\" + "\\".join(["folder-" + "x" * 30] * 8) + "\\note.md"
    assert str(safe_io._os_path(long)) == "\\\\?\\" + long
    assert str(safe_io._os_path("\\\\?\\" + long)) == "\\\\?\\" + long  # never twice
    mixed = long.replace("\\", "/")  # "/" is normalised first (Windows doesn't, past \\?\)
    assert str(safe_io._os_path(mixed)) == "\\\\?\\" + long
    unc = "\\\\server\\share\\" + "\\".join(["folder-" + "x" * 30] * 8) + "\\note.md"
    assert (
        str(safe_io._os_path(unc))
        == "\\\\?\\UNC\\server\\share\\" + unc[len("\\\\server\\share\\") :]
    )
    assert safe_io.real_path(long) == Path(long)  # no link here: the same path, no prefix


# --- safe_io ------------------------------------------------------------------------------------


def test_a_new_file_and_its_folders_past_260_characters(tmp_path):
    folder = deep(tmp_path, 250)
    path = folder / "notes" / "ch01-basics.md"  # folders created by the write itself
    assert len(str(path)) > 260
    safe_io.write_bytes(path, "# 光阑 Aperture stop\n".encode())
    assert safe_io.read_bytes(path) == "# 光阑 Aperture stop\n".encode()
    assert safe_io.exists(path) and safe_io.is_file(path)
    if long_paths_are_off():  # the case being fixed: a plain open can't reach it
        with pytest.raises(OSError):
            open(path, "rb").close()
    assert files_in(path.parent) == ["ch01-basics.md"]  # no temporary file left


def test_replacing_a_file_past_300_characters_and_its_backup(tmp_path):
    path = deep(tmp_path, 300) / "reading-log.json"
    assert len(str(path)) > 300
    safe_io.write_json(path, {"a": 1}, backup=True)
    safe_io.write_json(path, {"a": 2}, backup=True)  # the previous one kept as .bak
    assert safe_io.load_json(path, {}) == {"a": 2}
    assert safe_io.read_text(path.with_name("reading-log.json.bak")) == '{"a": 1}'
    assert safe_io.update_json(path, lambda d: d.update(b=3), {}) is None
    assert safe_io.load_json(path, {}) == {"a": 2, "b": 3}
    assert files_in(path.parent) == ["reading-log.json", "reading-log.json.bak"]


def test_unicode_names_and_chinese_text(tmp_path):
    path = deep(tmp_path, 260) / "笔记-光阑与渐晕-aperture-and-vignetting.md"
    text = "光阑 (aperture stop) 与渐晕 (vignetting): $\\Delta n$\n"
    safe_io.write_text(path, text, newline="\n")
    assert safe_io.read_text(path) == text


def test_a_failed_write_leaves_the_original_and_no_temporary_file(tmp_path, monkeypatch):
    path = deep(tmp_path, 270) / "ch01-basics.md"
    safe_io.write_bytes(path, b"the original\n")

    def disk_full(fd):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(safe_io.os, "fsync", disk_full)
    with pytest.raises(OSError):
        safe_io.write_bytes(path, b"half of a new version")
    assert safe_io.read_bytes(path) == b"the original\n"
    assert files_in(path.parent) == ["ch01-basics.md"]


def test_ordinary_short_paths_are_unchanged(tmp_path):
    path = tmp_path / "notes" / "x.md"
    safe_io.write_bytes(path, b"x")
    assert path.read_bytes() == b"x" and len(str(path)) < 200  # the plain path, as before


# --- the notes store in a deep library -------------------------------------------------------


@pytest.fixture
def deep_lib(tmp_path):
    """A one-book library whose notes folder is about 225 characters deep: the notes themselves
    are reachable as before, while archive/notes-conflicts/<folder>/<note>.<time>.md and its
    temporary file go past 260 (the case that failed)."""
    library = deep(tmp_path, 225 - len("\\notes\\" + NAME + "\\ch01-basics.md"))
    notes = library / "notes" / NAME
    readme = (
        "# Practical Lens Design\n\n## Reading progress\n\n- [ ] [Ch 1: Basics](ch01-basics.md)\n"
    )
    safe_io.write_text(notes / "README.md", readme, newline="\n")
    safe_io.write_bytes(notes / "ch01-basics.md", "# Ch 1\n\n- 我的笔记\n".encode())
    row = {"slug": NAME, "title": "Practical Lens Design", "notes": f"notes/{NAME}/"}
    doc = put(safe_io._os_path(library / "catalog.csv"), dict(row))
    return library, {"id": doc, **row}


def archived(library: Path) -> dict[str, bytes]:
    folder = library / "archive" / "notes-conflicts" / NAME
    if not safe_io.exists(folder):
        return {}
    return {p.name: safe_io.read_bytes(folder / p.name)
            for p in safe_io._os_path(folder).iterdir()}  # fmt: skip


def test_keep_mine_archives_into_a_path_past_260(deep_lib):
    library, row = deep_lib
    note = notes_store.read(library, row, "file:ch01-basics.md")
    path = library / "notes" / NAME / "ch01-basics.md"
    safe_io.write_bytes(path, b"# Ch 1\n\nchanged in VS Code\n")  # changed elsewhere
    with pytest.raises(Conflict) as conflict:
        notes_store.save(library, row, "file:ch01-basics.md", "mine\n", note["version"])
    disk = conflict.value.current
    saved = notes_store.save(library, row, "file:ch01-basics.md", "mine\n", note["version"],
                             overwrite=disk["version"])  # fmt: skip
    assert len(str(library / saved["kept"])) > 255  # the archive copy is where it failed
    assert safe_io.read_bytes(library / saved["kept"]) == b"# Ch 1\n\nchanged in VS Code\n"
    assert safe_io.read_bytes(path) == b"mine\n"


def test_use_the_disk_version_keeps_mine_past_260(deep_lib):
    library, row = deep_lib
    kept = notes_store.keep_copy(library, row, "file:ch01-basics.md", "我的版本 mine\n")
    assert len(str(library / kept)) > 255 and kept.endswith(".mine.md")
    assert safe_io.read_bytes(library / kept) == "我的版本 mine\n".encode()
    assert list(archived(library)) == [Path(kept).name]
    note = safe_io.read_bytes(library / "notes" / NAME / "ch01-basics.md")
    assert note == "# Ch 1\n\n- 我的笔记\n".encode()  # the note itself untouched


def test_a_long_note_path_is_never_taken_for_a_missing_note(deep_lib):
    """The danger behind the fix: a plain exists() calls a file past the limit missing, and a
    save meant for a new note (base: none) could then be written over it."""
    library, row = deep_lib
    notes = library / "notes" / NAME  # about 215 characters: a long note name passes 260
    long_name = "ch02-" + "a-very-long-chapter-title-" * 2 + "x.md"
    readme = safe_io.read_text(notes / "README.md") + f"- [ ] [Ch 2: Long]({long_name})\n"
    safe_io.write_text(notes / "README.md", readme, newline="\n")
    path = notes / long_name
    safe_io.write_bytes(path, b"# Ch 2\n\nalready written\n")
    if len(str(path)) <= 260:
        pytest.skip("the temporary folder is too short for this case")
    note = notes_store.read(library, row, f"file:{long_name}")
    assert note["exists"] and note["text"] == "# Ch 2\n\nalready written\n"
    with pytest.raises(Conflict):  # "new note" against an existing one: a conflict, not a write
        notes_store.save(library, row, f"file:{long_name}", "overwritten?\n", None)
    assert safe_io.read_bytes(path) == b"# Ch 2\n\nalready written\n"
    saved = notes_store.save(library, row, f"file:{long_name}", "edited\n", note["version"])
    assert saved["saved"] and safe_io.read_bytes(path) == b"edited\n"


def test_links_pointing_out_are_still_refused_in_a_deep_library(deep_lib, tmp_path_factory):
    """Containment follows links also past the limit: a junction named like a note, in the deep
    notes folder, pointing outside, is neither listed nor opened nor written."""
    import _winapi

    library, row = deep_lib
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    (elsewhere / "secret.md").write_bytes(SECRET)
    trap = library / "notes" / NAME / ("trap-" + "x" * 40 + ".md")
    _winapi.CreateJunction(str(elsewhere), str(safe_io._os_path(trap)))
    assert not notes_store._inside(trap, library / "notes" / NAME)
    key = f"file:{trap.name}"
    assert key not in {e["key"] for e in notes_store.entries(library, row)}
    for action in (lambda: notes_store.read(library, row, key),
                   lambda: notes_store.save(library, row, key, "x", None),
                   lambda: notes_store.keep_copy(library, row, key, "x")):  # fmt: skip
        with pytest.raises(NoteError):
            action()
    assert sorted(os.listdir(elsewhere)) == ["secret.md"]
    assert (elsewhere / "secret.md").read_bytes() == SECRET
    # the ordinary note beside it still works
    assert notes_store.read(library, row, "file:ch01-basics.md")["exists"]
