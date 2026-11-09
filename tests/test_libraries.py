"""Several libraries on one computer (scripts/libraries.py): the list of personal libraries,
read-only checking before one is added, portability (a library copied or moved anywhere keeps
its documents, ids and study data), and backups that never mix libraries. Every library here
is a temporary copy of test_library/ with invented data; the list of libraries, the Test & Demo
working copy and the logs are this test's own (fixture `own_registry`)."""

import hashlib
import json
import os
import shutil
import string
import subprocess
import sys
import uuid
from pathlib import Path

import catalog
import folder_backup
import libraries
import notes_store
import paths
import pytest
import safe_io
from pypdf import PdfReader


@pytest.fixture(autouse=True)
def own_registry(tmp_path, monkeypatch):
    local = tmp_path / "local"
    monkeypatch.setattr(libraries, "REGISTRY", local / "libraries.json")
    monkeypatch.setattr(libraries, "LOGS", local / "logs")
    monkeypatch.setattr(libraries, "TEST_WORKING", local / "test-library-working")
    monkeypatch.setattr(libraries, "TEST_PREVIOUS", local / "test-library-previous")
    monkeypatch.setattr(libraries, "configured_library", lambda: None)
    return local


def personal_copy(where: Path, name: str = "Physics", library_id: str | None = None) -> Path:
    """A personal library with real study data: test_library/'s documents and notes, with its
    own name and library id (and without the Test & Demo mark)."""
    shutil.copytree(
        libraries.TEST_CANONICAL, where,
        ignore=shutil.ignore_patterns("fixtures", "MANIFEST.json", "README.md"),
    )  # fmt: skip
    (where / "library.toml").write_text(
        f'name = "{name}"\nid = "{library_id or uuid.uuid4()}"\n', encoding="utf-8"
    )
    return where


def snapshot(folder: Path) -> dict:
    """Every file and folder: content hash, size and modification time (a read-only check)."""
    found = {}
    for path in sorted(folder.rglob("*")):
        rel = path.relative_to(folder).as_posix()
        if path.is_dir():
            found[rel] = "dir"
        else:
            stat = path.stat()
            found[rel] = (hashlib.sha256(path.read_bytes()).hexdigest(), stat.st_size,
                          stat.st_mtime_ns)  # fmt: skip
    return found


def study_data(library: Path) -> dict:
    """What a library holds for the user, read through the app's own functions: document ids
    and their rows, every note's text, PDF marks, reading log, review progress, vocabulary,
    glossaries, shelves, topic notes."""
    rows = catalog.load(library / "catalog.csv")
    notes = {}
    for doc_id, row in rows.items():
        for entry in notes_store.entries(library, row):
            notes[(doc_id, entry["key"])] = notes_store.read(library, row, entry["key"])["text"]
    marks = {}
    for doc_id, row in rows.items():
        pdf = PdfReader(library / row["file"])
        if pdf.is_encrypted:
            pdf.decrypt("")
        marks[doc_id] = sorted(
            str(a.get_object().get("/NM")) for page in pdf.pages for a in page.get("/Annots") or []
        )
    read = lambda rel: (library / rel).read_text(encoding="utf-8")  # noqa: E731
    return {
        "rows": rows,
        "notes": notes,
        "marks": marks,
        "log": json.loads(read("notes/reading-log.json")),
        "review": json.loads(read("notes/vocabulary-review.json")),
        "glossaries": {p.name: p.read_bytes() for p in (library / "glossaries").iterdir()},
        "topics": {p.name: p.read_bytes() for p in (library / "notes" / "topics").iterdir()},
        "shelves": {doc_id: row["shelves"] for doc_id, row in rows.items()},
    }


# --- checking a folder, read-only -------------------------------------------------------------


def test_a_complete_library_checks_clean_and_nothing_is_written(tmp_path):
    library = personal_copy(tmp_path / "Physics")
    before = snapshot(library)
    report = libraries.check(library)
    assert report["ok"] and report["errors"] == [] and report["warnings"] == []
    assert report["documents"] == {"book": 9, "paper": 7, "thesis": 2}
    assert report["name"] == "Physics" and uuid.UUID(report["id"])
    assert snapshot(library) == before


def test_what_isnt_a_library_is_refused(tmp_path):
    (tmp_path / "plain folder").mkdir()
    (tmp_path / "plain folder" / "a.txt").write_text("x", encoding="utf-8")
    for folder, why in [
        (tmp_path / "missing", "no such folder"),
        (tmp_path / "plain folder", "isn't a myLibrary library"),
        ("relative/path", "full folder path"),
        ("", "full folder path"),
    ]:
        report = libraries.check(folder)
        assert not report["ok"] and why in " ".join(report["errors"]), (folder, report)
    with pytest.raises(libraries.LibraryError, match="isn't a myLibrary library"):
        libraries.register(tmp_path / "plain folder")
    assert libraries.personal() == []


def test_an_old_format_catalog_is_refused_not_migrated(tmp_path):
    library = tmp_path / "old"
    library.mkdir()
    (library / "catalog.csv").write_text("slug,title\nsmith-2000-x,X\n", encoding="utf-8")
    before = snapshot(library)
    report = libraries.check(library)
    assert not report["ok"] and "migrate_ids.py" in report["errors"][0]
    assert snapshot(library) == before


def test_an_incomplete_copy_is_reported_with_its_notes_kept(tmp_path):
    library = personal_copy(tmp_path / "Physics")
    rows = catalog.load(library / "catalog.csv")
    gone = next(r for r in rows.values() if r["type"] == "paper")
    (library / gone["file"]).unlink()
    report = libraries.check(library)
    assert report["ok"]  # can be added: its notes are all there
    assert report["missing"] == [gone["file"]]
    assert any("aren't in the folder" in w for w in report["warnings"])
    entry = libraries.register(library)
    assert entry["warnings"] == report["warnings"]


def test_absolute_and_outside_paths_are_reported_never_followed(tmp_path):
    library = personal_copy(tmp_path / "Physics")
    rows = catalog.load(library / "catalog.csv")
    first, second = list(rows)[:2]
    catalog.set_field(library / "catalog.csv", first, "file", "C:/Users/someone/books/x.pdf")
    catalog.set_field(library / "catalog.csv", second, "notes", "../outside/")
    before = snapshot(library)
    report = libraries.check(library)
    text = " ".join(report["warnings"])
    assert "full path" in text and "leads out of the library" in text
    assert report["ok"]  # reported; the app's own containment refuses them when used
    assert snapshot(library) == before


@pytest.mark.skipif(sys.platform != "win32", reason="junctions are Windows'")
def test_a_junction_out_of_the_library_is_reported(tmp_path):
    import _winapi

    library = personal_copy(tmp_path / "Physics")
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    row = next(iter(catalog.load(library / "catalog.csv").values()))
    notes = library / row["notes"]
    shutil.rmtree(notes)
    _winapi.CreateJunction(str(outside), str(notes))
    report = libraries.check(library)
    assert any("link to a place outside" in w for w in report["warnings"]), report["warnings"]


def test_the_test_library_is_never_a_personal_one(tmp_path):
    for folder in (libraries.TEST_CANONICAL, libraries.test_library()):
        assert "Test & Demo" in " ".join(libraries.check(folder)["errors"])
        with pytest.raises(libraries.LibraryError):
            libraries.register(folder)
    assert libraries.personal() == []


# --- the list -------------------------------------------------------------------------------------


def test_registering_reads_only_and_refuses_a_second_registration(tmp_path):
    library = personal_copy(tmp_path / "D-drive" / "我的 书库 Physics")
    before = snapshot(library)
    entry = libraries.register(library, "光学研究 Optics Research")
    assert entry["label"] == "光学研究 Optics Research" and entry["available"]
    assert entry["port"] not in (libraries.DEFAULT_PORT, libraries.TEST_PORT)
    with pytest.raises(libraries.LibraryError, match="already on the list"):
        libraries.register(library)
    with pytest.raises(libraries.LibraryError, match="already on the list"):
        libraries.register(Path(str(library).upper()) if sys.platform == "win32" else library)
    assert snapshot(library) == before
    assert [e["path"] for e in libraries.personal()] == [str(library)]
    saved = json.loads(libraries.REGISTRY.read_text(encoding="utf-8"))
    assert saved["libraries"][0]["library_id"] == libraries.info(library)["id"]


def test_same_names_and_same_ids_stay_separate_libraries(tmp_path):
    original = personal_copy(tmp_path / "A" / "lib", name="Physics")
    copy = tmp_path / "B" / "lib"
    shutil.copytree(original, copy)
    other = personal_copy(tmp_path / "C" / "lib", name="Physics")
    first = libraries.register(original)
    second = libraries.register(copy)
    third = libraries.register(other)
    assert second["same_id"] == [first["label"]] and third["same_id"] == []
    listed = libraries.personal()
    assert len({e["key"] for e in listed}) == 3 and len({e["port"] for e in listed}) == 3
    assert [e["label"] for e in listed] == ["Physics"] * 3  # duplicate labels are fine
    assert libraries.scope(original) != libraries.scope(copy) != libraries.scope(other)
    assert study_data(original) == study_data(copy)  # never merged or changed


def test_rename_and_unregister_never_touch_the_folder(tmp_path):
    library = personal_copy(tmp_path / "Physics")
    before = snapshot(library)
    entry = libraries.register(library, "Old label")
    libraries.rename(entry["key"], "  New   label ")
    assert [e["label"] for e in libraries.personal()] == ["New label"]
    removed = libraries.unregister(entry["key"])
    assert removed["path"] == str(library) and libraries.personal() == []
    assert snapshot(library) == before


def test_the_default_library_is_listed_and_stays(tmp_path, monkeypatch):
    library = personal_copy(tmp_path / "Default")
    monkeypatch.setattr(libraries, "configured_library", lambda: library)
    (entry,) = libraries.personal()
    assert entry["default"] and entry["port"] == libraries.DEFAULT_PORT
    with pytest.raises(libraries.LibraryError, match="default library"):
        libraries.unregister(entry["key"])
    renamed = libraries.rename(entry["key"], "My default")
    assert renamed["default"] and renamed["label"] == "My default"
    assert len(libraries.personal()) == 1  # renamed, not listed twice


def test_create_makes_a_new_library_with_its_own_id(tmp_path):
    made = libraries.create(tmp_path / "新 书库", "计算机科学 Computer Science")
    folder = Path(made["path"])
    about = libraries.info(folder)
    assert uuid.UUID(about["id"]) and about["name"] == "计算机科学 Computer Science"
    assert (folder / "books").is_dir() and made["library_id"] == about["id"]
    assert libraries.check(folder)["ok"]
    (tmp_path / "full").mkdir()
    (tmp_path / "full" / "x.txt").write_text("x", encoding="utf-8")
    refused = [(tmp_path / "full", "isn't empty"), (folder / "inner", "inside the library"),
               (paths.APP / "my new library", "outside the tool")]  # fmt: skip
    for where, why in refused:
        with pytest.raises(libraries.LibraryError, match=why):
            libraries.create(where)
    assert not (paths.APP / "my new library").exists()


def test_a_moved_library_is_located_again(tmp_path):
    library = personal_copy(tmp_path / "old place" / "Physics")
    entry = libraries.register(library, "Physics")
    moved = tmp_path / "new place" / "Physics"
    moved.parent.mkdir()
    shutil.move(library, moved)
    (gone,) = libraries.personal()
    assert not gone["available"] and "isn't there" in gone["problem"]
    with pytest.raises(libraries.LibraryError, match="isn't there"):
        libraries.open_personal(entry["key"])
    stranger = personal_copy(tmp_path / "stranger")
    with pytest.raises(libraries.LibraryError, match="different library"):
        libraries.relocate(entry["key"], stranger)
    found = libraries.relocate(entry["key"], moved)
    assert found["available"] and found["path"] == str(moved) and found["port"] == entry["port"]


def test_a_damaged_list_is_kept_and_reported(tmp_path):
    libraries.REGISTRY.parent.mkdir(parents=True)
    libraries.REGISTRY.write_text("{not json", encoding="utf-8")
    with pytest.raises(safe_io.DamagedFile):
        libraries.personal()
    assert libraries.REGISTRY.read_text(encoding="utf-8") == "{not json"


# --- portability ----------------------------------------------------------------------------------


def test_a_moved_library_works_from_its_new_place_with_everything_in_it(tmp_path):
    """Computer A to computer B: another drive, user and folder name, with spaces and Chinese;
    the original place is gone."""
    original = personal_copy(tmp_path / "C" / "Users" / "alice" / "Documents" / "Physics")
    before = study_data(original)
    target = tmp_path / "E" / "Users" / "王 bob" / "书库 Library (copy)" / "Physics"
    target.parent.mkdir(parents=True)
    shutil.move(original, target)
    assert not original.exists()
    report = libraries.check(target)
    assert report["ok"] and report["warnings"] == [] and report["missing"] == []
    entry = libraries.register(target, "Physics on B")
    assert entry["library_id"] == libraries.info(target)["id"]
    after = study_data(target)
    assert after == before  # ids, rows, notes, marks, log, review, glossaries, shelves, topics
    rows = catalog.load(target / "catalog.csv")
    assert {r["type"] for r in rows.values()} == {"book", "paper", "thesis"}
    for row in rows.values():
        assert not Path(row["file"]).is_absolute() and (target / row["file"]).is_file()
        assert notes_store.notes_dir(target, row).is_dir()


def test_a_copy_and_its_original_are_independent(tmp_path):
    original = personal_copy(tmp_path / "A" / "Physics")
    copy = tmp_path / "B" / "Physics copy"
    shutil.copytree(original, copy)
    before = study_data(original)
    row = next(r for r in catalog.load(copy / "catalog.csv").values() if r["type"] == "paper")
    safe_io.update_text(copy / row["notes"] / "notes.md", lambda t: t + "\nOnly in the copy.\n")
    assert study_data(original) == before
    assert study_data(copy)["rows"] == before["rows"]  # the same document ids
    assert libraries.info(copy)["id"] == libraries.info(original)["id"]


@pytest.mark.skipif(sys.platform != "win32", reason="drive letters are Windows'")
def test_a_library_on_another_drive_letter(tmp_path):
    original = personal_copy(tmp_path / "Physics")
    before = study_data(original)
    taken = {d for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")}
    free = [d for d in "QRSTUVWXY" if d not in taken]
    if not free:
        pytest.skip("no free drive letter for subst")
    drive = f"{free[-1]}:"
    if subprocess.run(["subst", drive, str(tmp_path)], capture_output=True).returncode:
        pytest.skip("subst isn't available")
    try:
        moved = Path(f"{drive}\\Physics")
        assert libraries.check(moved)["ok"]
        assert study_data(moved) == before
        libraries.register(moved)
        with pytest.raises(libraries.LibraryError, match="already on the list"):
            libraries.register(original)  # the same folder under another name
    finally:
        subprocess.run(["subst", drive, "/D"], capture_output=True)


# --- backups never mix libraries -------------------------------------------------------------


def test_backups_of_libraries_with_the_same_name_stay_apart(tmp_path, monkeypatch):
    monkeypatch.setattr(folder_backup, "KEEP", 2)
    dest = tmp_path / "Backups"
    one = personal_copy(tmp_path / "one" / "Physics", name="Physics")
    two = personal_copy(tmp_path / "two" / "Physics", name="Physics")
    folder_backup.back_up(dest, pdfs=True, library=two)
    for _ in range(3):
        folder_backup.back_up(dest, pdfs=False, library=one)
    assert len(folder_backup.zips(dest, one)) == 2  # its own old ones went
    assert len(folder_backup.zips(dest, two)) == 1  # the other library's stayed
    assert all(f"[{libraries.scope(two)}]" in z.name for z in folder_backup.zips(dest, two))
    pdfs = dest / "PDFs" / folder_backup.backup_name(two)
    assert len(list(pdfs.rglob("*.pdf"))) == 18


def test_legacy_backup_names_match_only_their_own_library(tmp_path):
    dest = tmp_path / "Backups"
    dest.mkdir()
    physics = tmp_path / "Physics"
    physics.mkdir()
    (physics / "library.toml").write_text('name = "Physics"\n', encoding="utf-8")  # no id
    for name in ("Physics 2026-11-01 1200.zip", "Physics 2 2026-11-01 1200.zip",
                 "Physics [0123456789abcdef] 2026-11-01 1200.zip"):  # fmt: skip
        (dest / name).write_bytes(b"")
    assert [z.name for z in folder_backup.zips(dest, physics)] == ["Physics 2026-11-01 1200.zip"]


def test_a_copied_library_without_its_old_backup_folder_still_starts(tmp_path, monkeypatch):
    library = personal_copy(tmp_path / "Physics")
    settings = paths.SETTINGS_DEFAULTS | {"backup_folder": str(tmp_path / "USB stick (absent)")}
    monkeypatch.setattr(paths, "load_settings", lambda: settings)
    assert "not found" in folder_backup.auto_backup(library)


def test_a_backup_while_the_server_holds_the_library(tmp_path):
    """The server's lock and port note are this computer's: never in a backup (and a held lock
    can't be read, so including it would make every backup of an open library fail)."""
    import zipfile

    library = personal_copy(tmp_path / "Physics")
    held = libraries.hold_library(library)
    libraries.note_port(library, 8767)
    try:
        made = folder_backup.back_up(tmp_path / "Backups", pdfs=False, library=library)
    finally:
        held.close()
    names = zipfile.ZipFile(tmp_path / "Backups" / made["file"]).namelist()
    assert "catalog.csv" in names
    assert not any(n.startswith(".myLibrary/server.") for n in names)
