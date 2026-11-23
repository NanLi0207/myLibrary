"""💾 Back up to a folder (folder_backup.py), and the OpenAlex key from Settings."""

import os
import re
import shutil
import zipfile
from contextlib import contextmanager
from pathlib import Path

import book_meta
import folder_backup
import paths
import pytest


def make_library(root):
    lib = root / "lib"
    (lib / "notes" / "a-book").mkdir(parents=True)
    (lib / "notes" / "a-book" / "README.md").write_text("Last read: page 3\n", encoding="utf-8")
    (lib / "notes" / "vocabulary-review.json").write_text("{}", encoding="utf-8")
    (lib / "catalog.csv").write_text("slug\na-book\n", encoding="utf-8")
    (lib / "library.toml").write_text('name = "Nan\'s library"\n', encoding="utf-8")
    (lib / "books").mkdir()
    (lib / "books" / "a-book.pdf").write_bytes(b"%PDF-1.4 book")
    (lib / "archive").mkdir()
    (lib / "archive" / "old.pdf").write_bytes(b"%PDF old")
    (lib / ".cache").mkdir()
    (lib / ".cache" / "books.db").write_bytes(b"index")
    (lib / "library.html").write_text("<html>", encoding="utf-8")
    return lib


@pytest.fixture(autouse=True)
def no_settings(monkeypatch):
    monkeypatch.setattr(paths, "load_settings", lambda: dict(paths.SETTINGS_DEFAULTS))


def test_a_zip_of_your_work_without_pdfs_archive_or_caches(tmp_path):
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    result = folder_backup.back_up(dest, pdfs=False, library=lib)
    (made,) = dest.glob("*.zip")
    assert made.name.startswith("Nan's library ") and result["file"] == made.name
    names = set(zipfile.ZipFile(made).namelist())
    assert names == {"RESTORE.txt", "catalog.csv", "library.toml", "notes/a-book/README.md",
                     "notes/vocabulary-review.json"}  # fmt: skip
    assert not (dest / "PDFs").exists()


def test_pdfs_are_copied_once_and_kept(tmp_path):
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    assert folder_backup.back_up(dest, pdfs=True, library=lib)["pdfs"] == 1
    assert (dest / "PDFs" / "books" / "a-book.pdf").read_bytes() == b"%PDF-1.4 book"
    assert folder_backup.back_up(dest, pdfs=True, library=lib)["pdfs"] == 0  # already there
    (lib / "books" / "a-book.pdf").unlink()  # removed from the library: stays in the backup
    folder_backup.back_up(dest, pdfs=True, library=lib)
    assert (dest / "PDFs" / "books" / "a-book.pdf").exists()


def test_only_the_newest_are_kept_and_unchanged_libraries_skip(tmp_path, monkeypatch):
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    monkeypatch.setattr(folder_backup, "KEEP", 2)
    for _ in range(3):
        folder_backup.back_up(dest, pdfs=False, library=lib)
    assert len(folder_backup.zips(dest, lib)) == 2
    (dest / "someone else's.zip").write_bytes(b"")  # not ours: never deleted
    newest = folder_backup.zips(dest, lib)[-1]
    later = newest.stat().st_mtime + 60
    for f in folder_backup.your_files(lib):
        os.utime(f, (later - 3600, later - 3600))
    result = folder_backup.back_up(dest, pdfs=False, library=lib, only_if_changed=True)
    assert result["file"] == "" and "nothing changed" in result["message"]
    assert (dest / "someone else's.zip").exists()


def test_bad_folders_are_refused_with_a_message(tmp_path):
    lib = make_library(tmp_path)
    with pytest.raises(ValueError, match="choose a backup folder"):
        folder_backup.back_up("", library=lib)
    with pytest.raises(ValueError, match="inside the library"):
        folder_backup.back_up(lib / "backups", library=lib)


def test_auto_backup_does_nothing_without_a_folder_or_drive(tmp_path, monkeypatch):
    lib = make_library(tmp_path)
    assert folder_backup.auto_backup(lib) == ""
    gone = tmp_path / "usb-stick"
    monkeypatch.setattr(paths, "load_settings", lambda: {"backup_folder": str(gone)})
    assert "not found" in folder_backup.auto_backup(lib)
    gone.mkdir()
    assert "saved" in folder_backup.auto_backup(lib)
    assert folder_backup.auto_backup(lib) == ""  # once a day


# --- M7.1 S2: the content decides (FA-04: PDFs; FA-05: the zip) ---------------------------------


def set_times(path, ns):
    os.utime(path, ns=(ns, ns))


def backup_pdf(dest):
    return dest / "PDFs" / "books" / "a-book.pdf"


def contents(dest):
    """What a backup folder holds, but the backup lock's marker file."""
    return sorted(p.name for p in dest.iterdir() if p.name != folder_backup.LOCK_NAME)


def leftovers(folder):
    return sorted(p.name for p in folder.rglob("*.part"))


@pytest.mark.parametrize(
    "case", ["source one second newer", "same times", "source older", "backup in the future"]
)
def test_a_changed_pdf_of_the_same_size_is_copied_whatever_the_times(tmp_path, case):
    """FA-04 (D1.1, D1.2): equal size and a backup copy at least as new used to be taken as
    "already there", so marks saved into a PDF (same length, any time) were never backed up."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    folder_backup.back_up(dest, pdfs=True, library=lib)
    pdf, copy = lib / "books" / "a-book.pdf", backup_pdf(dest)
    before = copy.stat().st_mtime_ns
    pdf.write_bytes(b"%PDF-1.4 BOOK")  # same length, different bytes
    shift = {
        "source one second newer": 1_000_000_000,
        "same times": 0,
        "source older": -3_600_000_000_000,
        "backup in the future": -3_600_000_000_000,
    }[case]
    set_times(pdf, before + shift)
    if case == "backup in the future":
        set_times(copy, before + 86_400_000_000_000)
    result = folder_backup.back_up(dest, pdfs=True, library=lib)
    assert result["pdfs"] == 1 and "1 PDF copied" in result["message"]
    assert copy.read_bytes() == b"%PDF-1.4 BOOK"
    assert leftovers(dest) == []


def test_an_unchanged_pdf_is_not_copied_again_whatever_its_times(tmp_path):
    """D1.3: the same bytes under a newer (or older) time: nothing to copy, the copy stays."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    folder_backup.back_up(dest, pdfs=True, library=lib)
    pdf = lib / "books" / "a-book.pdf"
    for ns in (pdf.stat().st_mtime_ns + 7_200_000_000_000, 1_000_000_000_000_000_000):
        set_times(pdf, ns)
        result = folder_backup.back_up(dest, pdfs=True, library=lib)
        assert result["pdfs"] == 0 and "already there" in result["message"]
    assert backup_pdf(dest).read_bytes() == pdf.read_bytes() == b"%PDF-1.4 book"


def test_new_and_resized_pdfs_are_copied_and_the_library_is_left_alone(tmp_path):
    """D1.3, D1.6: a missing copy and a different size are copied; the library's PDFs are only
    read (byte for byte the same, times kept on the copy as before)."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    (lib / "papers").mkdir()
    (lib / "papers" / "p.pdf").write_bytes(b"%PDF paper")
    folder_backup.back_up(dest, pdfs=True, library=lib)
    (lib / "books" / "a-book.pdf").write_bytes(b"%PDF-1.4 book, now longer")
    snapshot = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in lib.rglob("*.pdf")}
    assert folder_backup.back_up(dest, pdfs=True, library=lib)["pdfs"] == 1
    assert backup_pdf(dest).read_bytes() == b"%PDF-1.4 book, now longer"
    assert (dest / "PDFs" / "papers" / "p.pdf").read_bytes() == b"%PDF paper"
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in lib.rglob("*.pdf")} == snapshot
    pdf = lib / "books" / "a-book.pdf"
    assert backup_pdf(dest).stat().st_mtime_ns == pdf.stat().st_mtime_ns


def test_a_changed_pdf_is_backed_up_even_when_the_zip_is_skipped(tmp_path):
    """D1.5: only_if_changed with unchanged notes: no new zip, but the changed PDF is copied;
    pdfs=False never touches the PDF copies."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    folder_backup.back_up(dest, pdfs=True, library=lib)
    pdf, copy = lib / "books" / "a-book.pdf", backup_pdf(dest)
    pdf.write_bytes(b"%PDF-1.4 BOOK")
    set_times(pdf, copy.stat().st_mtime_ns)
    assert folder_backup.back_up(dest, pdfs=False, library=lib, only_if_changed=True) == {
        "message": f"Backed up to {dest}: nothing changed since the last backup",
        "file": "",
        "pdfs": 0,
    }
    assert copy.read_bytes() == b"%PDF-1.4 book"
    result = folder_backup.back_up(dest, pdfs=True, library=lib, only_if_changed=True)
    assert result["file"] == "" and result["pdfs"] == 1
    assert copy.read_bytes() == b"%PDF-1.4 BOOK"


def test_a_failed_pdf_copy_keeps_the_earlier_copy_and_is_not_reported_as_done(
    tmp_path, monkeypatch
):
    """D1.4: a copy cut off halfway, or one that can't be put in place, leaves the earlier
    backup copy byte for byte, no temporary file, and an error rather than a success; the
    other PDFs are still backed up."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    (lib / "papers").mkdir()
    folder_backup.back_up(dest, pdfs=True, library=lib)
    (lib / "books" / "a-book.pdf").write_bytes(b"%PDF-1.4 BOOK")
    (lib / "papers" / "p.pdf").write_bytes(b"%PDF paper")
    real_copy = folder_backup.shutil.copyfile

    def cut_off(source, target):
        if str(source).endswith("a-book.pdf"):
            with open(target, "wb") as out:
                out.write(b"%PDF")  # part of it written, then the disk is full
            raise OSError(28, "No space left on device")
        return real_copy(source, target)

    monkeypatch.setattr(folder_backup.shutil, "copyfile", cut_off)
    with pytest.raises(folder_backup.BackupIncomplete) as failed:
        folder_backup.back_up(dest, pdfs=True, library=lib)
    message = str(failed.value)
    assert "not complete" in message and "books/a-book.pdf (No space left on device)" in message
    assert backup_pdf(dest).read_bytes() == b"%PDF-1.4 book"
    assert (dest / "PDFs" / "papers" / "p.pdf").read_bytes() == b"%PDF paper"
    assert leftovers(dest) == []

    monkeypatch.setattr(folder_backup.shutil, "copyfile", real_copy)

    def locked(tmp, path):
        raise PermissionError("a-book.pdf is open in another program")

    monkeypatch.setattr(folder_backup, "_put_in_place", locked)
    with pytest.raises(folder_backup.BackupIncomplete, match="open in another program"):
        folder_backup.back_up(dest, pdfs=True, library=lib)
    assert backup_pdf(dest).read_bytes() == b"%PDF-1.4 book"
    assert leftovers(dest) == []


def test_a_pdf_changing_while_it_is_copied_is_copied_again_or_reported(tmp_path, monkeypatch):
    """D1.4: a PDF whose marks are saved while it's copied: what was copied isn't what it holds,
    so it is copied again (TRIES); one that never settles is reported, its earlier copy kept."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    folder_backup.back_up(dest, pdfs=True, library=lib)
    pdf = lib / "books" / "a-book.pdf"
    real_copy = folder_backup.shutil.copyfile
    versions = iter([b"%PDF-1.4 v1", b"%PDF-1.4 v2 marks saved"])

    def save_marks_meanwhile(source, target):
        real_copy(source, target)
        if (version := next(versions, None)) is not None:
            pdf.write_bytes(version)  # the reader saved marks during the copy

    monkeypatch.setattr(folder_backup.shutil, "copyfile", save_marks_meanwhile)
    pdf.write_bytes(b"%PDF-1.4 v0")
    assert folder_backup.back_up(dest, pdfs=True, library=lib)["pdfs"] == 1
    assert backup_pdf(dest).read_bytes() == b"%PDF-1.4 v2 marks saved"

    def never_settles(source, target):
        real_copy(source, target)
        pdf.write_bytes(pdf.read_bytes() + b"!")

    monkeypatch.setattr(folder_backup.shutil, "copyfile", never_settles)
    pdf.write_bytes(b"%PDF-1.4 v3")
    with pytest.raises(folder_backup.BackupIncomplete, match="changed while it was being copied"):
        folder_backup.back_up(dest, pdfs=True, library=lib)
    assert backup_pdf(dest).read_bytes() == b"%PDF-1.4 v2 marks saved"
    assert leftovers(dest) == []


def test_comparing_reads_in_bounded_chunks(tmp_path, monkeypatch):
    """Big PDFs are compared and copied a chunk at a time, never read whole."""
    monkeypatch.setattr(folder_backup, "CHUNK", 64)
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    body = bytes(range(256)) * 40
    (lib / "books" / "a-book.pdf").write_bytes(b"%PDF" + body)
    folder_backup.back_up(dest, pdfs=True, library=lib)
    reads = []
    real_read = folder_backup._read
    monkeypatch.setattr(folder_backup, "_read", lambda f: reads.append(1) or real_read(f))
    changed = bytearray(b"%PDF" + body)
    changed[-1] ^= 1  # only the very last byte differs
    (lib / "books" / "a-book.pdf").write_bytes(bytes(changed))
    assert folder_backup.back_up(dest, pdfs=True, library=lib)["pdfs"] == 1
    assert backup_pdf(dest).read_bytes() == bytes(changed)
    assert len(reads) > 2 * len(changed) // 64  # chunk by chunk, to the last one


def test_a_deep_library_and_backup_folder_work(tmp_path):
    """D1.6: a PDF whose backup copy's path is past Windows' 260-character limit is compared,
    copied and replaced like any other."""
    deep = tmp_path / ("d" * 50) / ("e" * 50)
    lib, dest = make_library(deep), deep / "backups"
    long_name = "a-" + "x" * 90 + ".pdf"
    source = lib / "books" / long_name
    folder_backup.safe_io.write_bytes(source, b"%PDF long")
    folder_backup.back_up(dest, pdfs=True, library=lib)
    copy = dest / "PDFs" / "books" / long_name
    assert len(str(copy)) > 260 and folder_backup.safe_io.read_bytes(copy) == b"%PDF long"
    assert folder_backup.back_up(dest, pdfs=True, library=lib)["pdfs"] == 0
    folder_backup.safe_io.write_bytes(source, b"%PDF LONG")
    assert folder_backup.back_up(dest, pdfs=True, library=lib)["pdfs"] == 1
    assert folder_backup.safe_io.read_bytes(copy) == b"%PDF LONG"
    assert leftovers(dest) == []


def test_a_backup_folder_in_a_protected_library_is_refused_before_anything_is_written(
    tmp_path, monkeypatch
):
    lib, frozen = make_library(tmp_path), tmp_path / "showcase"
    frozen.mkdir()
    monkeypatch.setattr(folder_backup.safe_io, "_frozen", [])
    folder_backup.safe_io.freeze(frozen)
    with pytest.raises(ValueError, match="showcase or test library"):
        folder_backup.back_up(frozen / "backups", pdfs=True, library=lib)
    assert list(frozen.iterdir()) == []


def make_assets(lib):
    (lib / "notes" / "a-book" / "images").mkdir()
    (lib / "notes" / "a-book" / "images" / "fig.png").write_bytes(b"\x89PNG fig")
    (lib / "notes" / "a-book" / "ch01-intro.md").write_text("# Ch 1\nmine\n", encoding="utf-8")
    (lib / ".myLibrary").mkdir()
    (lib / ".myLibrary" / "references.json").write_text("{}", encoding="utf-8")


def age_everything(lib, dest):
    """Every library file's time well before the last zip: the old timestamp check saw no
    change, so only the content can tell."""
    newest = folder_backup.zips(dest, lib)[-1]
    old = newest.stat().st_mtime_ns - 3_600_000_000_000
    for f in lib.rglob("*"):
        if f.is_file():
            set_times(f, old)


def zip_names(path):
    with zipfile.ZipFile(path) as z:
        return set(z.namelist())


@pytest.mark.parametrize(
    "change",
    [
        "delete a note",
        "delete an image",
        "delete the references",
        "rename a note, time kept",
        "add a file with an old time",
        "edit a note, size and time kept",
    ],
)
def test_a_change_under_old_times_makes_a_new_zip(tmp_path, change):
    """FA-05 (D2.1, D2.2): only the time of files still there was checked, so a deletion (or a
    rename, or a change under an old time) was "nothing changed" and never backed up."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    make_assets(lib)
    folder_backup.back_up(dest, pdfs=False, library=lib)
    (first,) = folder_backup.zips(dest, lib)
    before = zip_names(first)
    note = lib / "notes" / "a-book" / "ch01-intro.md"
    age_everything(lib, dest)
    old = note.stat().st_mtime_ns
    if change == "delete a note":
        note.unlink()
    elif change == "delete an image":
        (lib / "notes" / "a-book" / "images" / "fig.png").unlink()
    elif change == "delete the references":
        (lib / ".myLibrary" / "references.json").unlink()
    elif change == "rename a note, time kept":
        note.rename(note.with_name("ch01-renamed.md"))
    elif change == "add a file with an old time":
        (lib / "notes" / "topics").mkdir()
        (lib / "notes" / "topics" / "lens.md").write_text("# lens\n", encoding="utf-8")
        set_times(lib / "notes" / "topics" / "lens.md", old)
    else:
        note.write_text("# Ch 1\nMINE\n", encoding="utf-8")
        set_times(note, old)
    result = folder_backup.back_up(dest, pdfs=False, library=lib, only_if_changed=True)
    assert result["file"], result["message"]
    first_again, made = folder_backup.zips(dest, lib)
    assert first_again == first and zip_names(first) == before  # the earlier one is kept
    expected = {"RESTORE.txt"} | {
        f.relative_to(lib).as_posix() for f in folder_backup.your_files(lib)
    }
    assert zip_names(made) == expected
    with zipfile.ZipFile(made) as z:
        for name in expected - {"RESTORE.txt"}:
            assert z.read(name) == (lib / name).read_bytes()


def test_an_unchanged_library_skips_whatever_the_times_and_ignores_what_isnt_backed_up(
    tmp_path,
):
    """D2.3: the same files and bytes under newer times: no new zip; changes only in caches,
    the archive or the generated page never make one."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    make_assets(lib)
    folder_backup.back_up(dest, pdfs=False, library=lib)
    newest = folder_backup.zips(dest, lib)[-1].stat().st_mtime_ns
    for f in folder_backup.your_files(lib):
        set_times(f, newest + 3_600_000_000_000)  # touched, not changed
    (lib / ".cache" / "books.db").write_bytes(b"rebuilt index")
    (lib / "archive" / "gone.md").write_text("moved away", encoding="utf-8")
    (lib / "library.html").write_text("<html>rebuilt", encoding="utf-8")
    (lib / "books" / "new.pdf").write_bytes(b"%PDF new")
    result = folder_backup.back_up(dest, pdfs=False, library=lib, only_if_changed=True)
    assert result["file"] == "" and "nothing changed" in result["message"]
    assert len(folder_backup.zips(dest, lib)) == 1


def test_auto_backup_sees_a_deletion_once_a_day(tmp_path, monkeypatch):
    """D2.4: the daily automatic backup (not just back_up) makes a zip after a deletion alone;
    inside the day it still waits. Times are set, never slept."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    make_assets(lib)
    dest.mkdir()
    monkeypatch.setattr(
        paths, "load_settings", lambda: {"backup_folder": str(dest), "backup_pdfs": False}
    )
    assert "saved" in folder_backup.auto_backup(lib)
    (first,) = folder_backup.zips(dest, lib)
    (lib / "notes" / "a-book" / "ch01-intro.md").unlink()
    assert folder_backup.auto_backup(lib) == ""  # the same day: not yet
    yesterday = first.stat().st_mtime_ns - 21 * 3_600_000_000_000
    for f in lib.rglob("*"):
        if f.is_file():
            set_times(f, yesterday - 60_000_000_000)
    set_times(first, yesterday)
    assert "saved" in folder_backup.auto_backup(lib)
    first_again, made = folder_backup.zips(dest, lib)
    assert "notes/a-book/ch01-intro.md" in zip_names(first_again)
    assert "notes/a-book/ch01-intro.md" not in zip_names(made)


def write_zip(path, members):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in members:
            z.writestr(name, data)


@pytest.mark.filterwarnings("ignore:Duplicate name")  # (made on purpose: "name twice")
@pytest.mark.parametrize(
    "damage", ["truncated", "not a zip", "bad CRC", "name twice", "no RESTORE"]
)
def test_a_damaged_or_odd_last_zip_is_never_taken_as_the_same(tmp_path, damage):
    """D2.5: a last zip that can't be read in full, has a name twice or isn't laid out as ours
    never means "nothing changed": a new zip is made, the message says why when it's damaged,
    and the questionable zip is kept as it is."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    folder_backup.back_up(dest, pdfs=False, library=lib)
    (last,) = folder_backup.zips(dest, lib)
    members = [("RESTORE.txt", folder_backup.RESTORE)] + [
        (f.relative_to(lib).as_posix(), f.read_bytes()) for f in folder_backup.your_files(lib)
    ]
    if damage == "truncated":
        last.write_bytes(last.read_bytes()[:-40])
    elif damage == "not a zip":
        last.write_bytes(b"this is not a zip")
    elif damage == "bad CRC":
        write_zip(last, members)
        data = last.read_bytes()
        at = data.index(b"Last read: page 3")
        last.write_bytes(data[:at] + b"l" + data[at + 1 :])  # same size, other byte
    elif damage == "name twice":
        write_zip(last, [*members, members[-1]])
    else:
        write_zip(last, members[1:])
    kept = last.read_bytes()
    result = folder_backup.back_up(dest, pdfs=False, library=lib, only_if_changed=True)
    assert result["file"]
    if damage in ("truncated", "not a zip", "bad CRC", "name twice"):
        assert "wasn't trusted" in result["message"]
    assert last.read_bytes() == kept
    assert len(folder_backup.zips(dest, lib)) == 2


def test_a_zip_made_before_s2_is_still_a_baseline(tmp_path):
    """Compatibility: a zip written by the earlier code (same layout: RESTORE.txt, then the
    files) is read as it is; unchanged files skip, a deletion doesn't."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    dest.mkdir()
    old = dest / f"{folder_backup.backup_name(lib)} 2026-11-01 1200.zip"
    with zipfile.ZipFile(old, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("RESTORE.txt", "an older RESTORE text")
        for f in folder_backup.your_files(lib):
            z.write(f, f.relative_to(lib).as_posix())
    result = folder_backup.back_up(dest, pdfs=False, library=lib, only_if_changed=True)
    assert result["file"] == ""
    (lib / "notes" / "vocabulary-review.json").unlink()
    assert folder_backup.back_up(dest, pdfs=False, library=lib, only_if_changed=True)["file"]


def test_a_failed_zip_publishes_nothing_and_deletes_no_old_zip(tmp_path, monkeypatch):
    """A zip that can't be written in full: no zip with our name, no temporary file left,
    nothing pruned (retention runs only after a complete new zip), an error not a success."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    monkeypatch.setattr(folder_backup, "KEEP", 1)
    folder_backup.back_up(dest, pdfs=False, library=lib)
    (only,) = folder_backup.zips(dest, lib)
    (lib / "notes" / "a-book" / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    real_write = zipfile.ZipFile.write

    def disk_error(self, filename, arcname=None, *args, **kwargs):
        if arcname == "notes/a-book/README.md":
            raise OSError(5, "Input/output error")
        return real_write(self, filename, arcname, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "write", disk_error)
    with pytest.raises(folder_backup.BackupIncomplete, match="no backup made"):
        folder_backup.back_up(dest, pdfs=False, library=lib, only_if_changed=True)
    assert folder_backup.zips(dest, lib) == [only] and only.exists()
    assert leftovers(dest) == [] and contents(dest) == [only.name]


def test_a_zip_that_doesnt_read_back_is_not_published(tmp_path, monkeypatch):
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    monkeypatch.setattr(zipfile.ZipFile, "testzip", lambda self: "catalog.csv")
    with pytest.raises(folder_backup.BackupIncomplete, match="catalog.csv in the new zip"):
        folder_backup.back_up(dest, pdfs=False, library=lib)
    assert contents(dest) == []


def test_a_file_deleted_while_the_zip_is_made_is_listed_again(tmp_path, monkeypatch):
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    vanishing = lib / "notes" / "vocabulary-review.json"
    real_write = zipfile.ZipFile.write

    def deleted_meanwhile(self, filename, arcname=None, *args, **kwargs):
        if arcname == "notes/vocabulary-review.json" and vanishing.exists():
            vanishing.unlink()  # gone between the listing and the zip
        return real_write(self, filename, arcname, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "write", deleted_meanwhile)
    result = folder_backup.back_up(dest, pdfs=False, library=lib)
    (made,) = folder_backup.zips(dest, lib)
    assert result["file"] == made.name
    assert "notes/vocabulary-review.json" not in zip_names(made)
    assert leftovers(dest) == []


def test_an_interrupted_backup_leaves_the_last_complete_zip_as_the_baseline(tmp_path):
    """What a backup cut off by a crash leaves behind (a temporary .part) is never one of the
    library's backups: the next backup compares with the last complete zip."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    folder_backup.back_up(dest, pdfs=True, library=lib)
    (complete,) = folder_backup.zips(dest, lib)
    stale = dest / f".{folder_backup.backup_name(lib)} 2099-01-01 0000.zip.0123abcd.part"
    stale.write_bytes(b"PK cut off")
    (dest / "PDFs" / "books" / ".a-book.pdf.0123abcd.part").write_bytes(b"%PDF-1.4 bo")
    assert folder_backup.zips(dest, lib) == [complete]
    result = folder_backup.back_up(dest, pdfs=True, library=lib, only_if_changed=True)
    assert result["file"] == "" and result["pdfs"] == 0
    assert backup_pdf(dest).read_bytes() == b"%PDF-1.4 book"


def test_a_backup_restores_into_a_new_folder_byte_for_byte(tmp_path):
    """D2.6: unzip the newest backup into a new, empty folder and copy the PDFs back, as
    RESTORE.txt says: every backed-up file and PDF is byte for byte the library's."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    make_assets(lib)
    (lib / "papers").mkdir()
    (lib / "papers" / "p.pdf").write_bytes(b"%PDF paper " + bytes(range(256)))
    folder_backup.back_up(dest, pdfs=True, library=lib)
    (lib / "notes" / "a-book" / "images" / "fig.png").unlink()
    (lib / "books" / "a-book.pdf").write_bytes(b"%PDF-1.4 BOOK")
    folder_backup.back_up(dest, pdfs=True, library=lib, only_if_changed=True)
    restored = tmp_path / "restored"
    with zipfile.ZipFile(folder_backup.zips(dest, lib)[-1]) as z:
        z.extractall(restored)
    for folder in ("books", "papers"):
        shutil.copytree(dest / "PDFs" / folder, restored / folder)
    wanted = {f.relative_to(lib).as_posix() for f in folder_backup.your_files(lib)}
    wanted |= {"books/a-book.pdf", "papers/p.pdf"}
    got = {p.relative_to(restored).as_posix() for p in restored.rglob("*") if p.is_file()}
    assert got == wanted | {"RESTORE.txt"}
    for name in wanted:
        assert (restored / name).read_bytes() == (lib / name).read_bytes(), name
    with zipfile.ZipFile(folder_backup.zips(dest, lib)[0]) as z:  # the earlier state
        assert z.read("notes/a-book/images/fig.png") == b"\x89PNG fig"


# --- M7.1 S2, after Codex's review: long paths (B41), one backup at a time, retention, the
# instructions' CRC and name ------------------------------------------------------------------

io = folder_backup.safe_io


def put(path, data: bytes):
    io.write_bytes(path, data)  # (also past 260 characters)


def make_deep_library(root):
    """A library whose own folder is past Windows' limits (its notes and PDFs even more so),
    made through the long-path form only."""
    lib = root / ("d" * 70) / ("e" * 70) / ("f" * 70) / "lib"
    assert len(str(lib)) > 260
    put(lib / "library.toml", b'name = "Deep"\n')
    put(lib / "catalog.csv", b"slug\na-book\n")
    put(lib / "notes" / "a-book" / "README.md", b"Last read: page 3\n")
    put(lib / "books" / "a-book.pdf", b"%PDF-1.4 deep book")
    return lib


def extended(path):
    """The extended-length form of a folder, short or long (to unzip long names into it)."""
    return Path("\\\\?\\" + os.path.abspath(path)) if os.name == "nt" else path


def zip_bytes(path):
    with zipfile.ZipFile(io._os_path(path)) as z:
        return {name: z.read(name) for name in z.namelist()}


def library_bytes(lib):
    return {f.relative_to(lib).as_posix(): io.read_bytes(f) for f in folder_backup.your_files(lib)}


def test_a_note_past_260_characters_is_backed_up_and_restored(tmp_path):
    """B41: a note whose path is past 260 characters was left out of the zip without a word
    (rglob/is_file can't see it). It's in the zip, compared like the others, and restores."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    long_note = lib / "notes" / "a-book" / ("n" * 120) / ("chapter-" + "x" * 110 + ".md")
    assert len(str(long_note)) > 260
    put(long_note, b"# my long-path note\n")
    folder_backup.back_up(dest, pdfs=False, library=lib)
    (made,) = folder_backup.zips(dest, lib)
    name = long_note.relative_to(lib).as_posix()
    assert zip_bytes(made)[name] == b"# my long-path note\n"
    assert zip_bytes(made) == {"RESTORE.txt": folder_backup.RESTORE.encode()} | library_bytes(lib)
    age_everything(lib, dest)
    old = os.stat(io._os_path(long_note)).st_mtime_ns
    put(long_note, b"# MY LONG-PATH NOTE\n")  # same size, old time
    os.utime(io._os_path(long_note), ns=(old, old))
    result = folder_backup.back_up(dest, pdfs=False, library=lib, only_if_changed=True)
    assert result["file"] and zip_bytes(dest / result["file"])[name] == b"# MY LONG-PATH NOTE\n"
    restored = tmp_path / "r"
    with zipfile.ZipFile(dest / result["file"]) as z:
        z.extractall(extended(restored))
    assert io.read_bytes(restored / name) == b"# MY LONG-PATH NOTE\n"


def test_a_deep_library_folder_is_backed_up_and_restored_byte_for_byte(tmp_path):
    """B41: the library's own folder past the limit (notes, catalog, PDFs all long paths):
    nothing left out, the PDFs copied and compared, an unchanged library skips, a deletion
    makes a new zip, and the backup restores into a new folder byte for byte."""
    lib = make_deep_library(tmp_path)
    dest = tmp_path / ("g" * 70) / ("h" * 70) / ("i" * 70) / "backups"
    result = folder_backup.back_up(dest, pdfs=True, library=lib)
    assert result["pdfs"] == 1
    (made,) = folder_backup.zips(dest, lib)
    assert set(zip_bytes(made)) == {
        "RESTORE.txt",
        "library.toml",
        "catalog.csv",
        "notes/a-book/README.md",
    }
    copy = dest / "PDFs" / "books" / "a-book.pdf"
    assert io.read_bytes(copy) == b"%PDF-1.4 deep book"
    again = folder_backup.back_up(dest, pdfs=True, library=lib, only_if_changed=True)
    assert again["file"] == "" and again["pdfs"] == 0
    io._os_path(lib / "catalog.csv").unlink()
    gone = folder_backup.back_up(dest, pdfs=True, library=lib, only_if_changed=True)
    assert gone["file"] and "catalog.csv" not in zip_bytes(dest / gone["file"])
    restored = tmp_path / ("r" * 70) / ("s" * 70) / ("t" * 70) / "restored"
    with zipfile.ZipFile(io._os_path(dest / gone["file"])) as z:
        z.extractall(extended(restored))
    put(restored / "books" / "a-book.pdf", io.read_bytes(copy))
    for name, data in library_bytes(lib).items():
        assert io.read_bytes(restored / name) == data
    assert io.read_bytes(restored / "books" / "a-book.pdf") == io.read_bytes(
        lib / "books" / "a-book.pdf"
    )


def test_a_folder_that_cant_be_read_fails_the_backup_instead_of_shrinking_it(tmp_path, monkeypatch):
    """A folder in the library that can't be listed (permissions, a disk error) is never
    taken for an empty one: no zip is published, no old zip is deleted, the message says
    which folder."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    make_assets(lib)
    monkeypatch.setattr(folder_backup, "KEEP", 1)
    folder_backup.back_up(dest, pdfs=False, library=lib)
    (only,) = folder_backup.zips(dest, lib)
    (lib / "notes" / "a-book" / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    real_scandir = os.scandir

    def denied(path):
        if str(path).endswith("images"):
            raise PermissionError(13, "Access is denied", str(path))
        return real_scandir(path)

    monkeypatch.setattr(folder_backup.os, "scandir", denied)
    for only_if_changed in (False, True):
        with pytest.raises(folder_backup.BackupIncomplete, match="Access is denied: images"):
            folder_backup.back_up(dest, pdfs=False, library=lib, only_if_changed=only_if_changed)
        assert folder_backup.zips(dest, lib) == [only] and leftovers(dest) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows folder permissions (icacls)")
def process_user_sid() -> str:
    """The user SID in this process's own token (what Windows checks permissions against),
    as "S-1-5-...": not a user name, which can name another account (USERNAME, a renamed or
    domain account) so the denial would be for someone else (S2 round 3)."""
    import ctypes
    from ctypes import wintypes

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.PHANDLE]
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.PDWORD,
    ]
    advapi32.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())  # (TOKEN_QUERY)
    try:
        size = wintypes.DWORD()
        advapi32.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))  # (TokenUser)
        buffer = ctypes.create_string_buffer(size.value)
        if not advapi32.GetTokenInformation(token, 1, buffer, size, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        sid = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]  # TOKEN_USER.User.Sid
        text = wintypes.LPWSTR()
        if not advapi32.ConvertSidToStringSidW(sid, ctypes.byref(text)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return text.value
        finally:
            kernel32.LocalFree(text)
    finally:
        kernel32.CloseHandle(token)


@contextmanager
def listing_denied(folder):
    """While held, this process's own user (by its token's SID) may not list `folder`, a real
    Windows permission (icacls). Skips (not fails) only when that can't be set up here: no
    icacls, or the denial doesn't take effect (e.g. a process allowed to bypass it)."""
    import subprocess

    sid = process_user_sid()
    deny = subprocess.run(
        ["icacls", str(folder), "/deny", f"*{sid}:(RD)"], capture_output=True, text=True
    )
    if deny.returncode != 0:
        pytest.skip(f"prerequisite: icacls couldn't deny listing ({deny.stdout.strip()})")
    try:
        try:
            os.listdir(folder)
        except PermissionError:
            pass
        else:
            pytest.skip("prerequisite: the denial didn't take effect for this process")
        yield sid
    finally:
        subprocess.run(["icacls", str(folder), "/remove:d", f"*{sid}"], capture_output=True)


@pytest.mark.skipif(os.name != "nt", reason="Windows folder permissions (icacls)")
def test_a_folder_the_user_may_not_list_fails_the_backup(tmp_path, monkeypatch):
    """The same with a real Windows permission: listing the folder is denied to this process's
    own user. The backup fails naming the folder, publishes nothing and keeps the old zips."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    monkeypatch.setattr(folder_backup, "KEEP", 1)
    folder_backup.back_up(dest, pdfs=False, library=lib)
    (only,) = folder_backup.zips(dest, lib)
    kept = only.read_bytes()
    secret = lib / "notes" / "private"
    secret.mkdir()
    (secret / "mine.md").write_text("mine", encoding="utf-8")
    with listing_denied(secret):
        for only_if_changed in (False, True):
            with pytest.raises(
                folder_backup.BackupIncomplete, match="no backup made: Access is denied: private"
            ):
                folder_backup.back_up(
                    dest, pdfs=False, library=lib, only_if_changed=only_if_changed
                )
            assert folder_backup.zips(dest, lib) == [only] and leftovers(dest) == []
            assert only.read_bytes() == kept
    assert "notes/private/mine.md" in zip_names(
        dest / folder_backup.back_up(dest, pdfs=False, library=lib)["file"]
    )


def test_an_unreadable_pdf_folder_and_a_dangling_link_are_reported(tmp_path, monkeypatch):
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    (lib / "papers").mkdir()
    (lib / "papers" / "p.pdf").write_bytes(b"%PDF paper")
    real_scandir = os.scandir

    def denied(path):
        if str(path).endswith("papers"):
            raise PermissionError(13, "Access is denied", str(path))
        return real_scandir(path)

    monkeypatch.setattr(folder_backup.os, "scandir", denied)
    for pdfs in (True, False):  # (the PDF inventory, or the zip's listing, sees it first)
        with pytest.raises(folder_backup.BackupIncomplete, match="Access is denied: papers"):
            folder_backup.back_up(dest, pdfs=pdfs, library=lib)
        assert folder_backup.zips(dest, lib) == [] and contents(dest) == []  # nothing at all
    with pytest.raises(PermissionError):  # the inventory on its own: never a shorter list
        folder_backup._library_pdfs(lib)
    monkeypatch.undo()
    if os.name == "nt":
        import _winapi

        gone = tmp_path / "gone"
        gone.mkdir()
        _winapi.CreateJunction(str(gone), str(lib / "notes" / "linked"))
        gone.rmdir()  # the junction now points nowhere
        with pytest.raises(folder_backup.BackupIncomplete, match="no backup made: .*linked"):
            folder_backup.back_up(dest, pdfs=False, library=lib)
        assert folder_backup.zips(dest, lib) == []


def test_junctions_are_followed_as_before_and_a_loop_is_not(tmp_path):
    """Same as rglob before: a junction's files are backed up; one pointing back up the
    library isn't walked again (it would never end)."""
    if os.name != "nt":
        pytest.skip("junctions are a Windows thing")
    import _winapi

    lib, dest = make_library(tmp_path), tmp_path / "backups"
    outside = tmp_path / "onedrive-notes"
    outside.mkdir()
    (outside / "synced.md").write_text("synced", encoding="utf-8")
    _winapi.CreateJunction(str(outside), str(lib / "notes" / "synced"))
    _winapi.CreateJunction(str(lib / "notes"), str(lib / "notes" / "a-book" / "loop"))
    result = folder_backup.back_up(dest, pdfs=False, library=lib)
    names = zip_names(dest / result["file"])
    assert "notes/synced/synced.md" in names
    assert not any("/loop/" in n for n in names)


def hold_the_lock_in_a_thread(dest):
    """A backup to dest that holds the folder's lock until released: (started, release)."""
    import threading

    started, release = threading.Event(), threading.Event()

    def hold():
        with folder_backup._one_backup_at_a_time(dest, 5):
            started.set()
            release.wait(30)

    thread = threading.Thread(target=hold, daemon=True)
    thread.start()
    assert started.wait(10)
    return thread, release


def test_an_automatic_backup_never_runs_into_a_running_one(tmp_path, monkeypatch):
    """The automatic backup at start, while a manual one to the same folder is under way,
    makes nothing and says why (it doesn't wait: one is enough for today)."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    dest.mkdir()
    monkeypatch.setattr(paths, "load_settings", lambda: {"backup_folder": str(dest)})
    thread, release = hold_the_lock_in_a_thread(dest)
    try:
        message = folder_backup.auto_backup(lib)
        assert "another backup to this folder is running" in message
        assert folder_backup.zips(dest, lib) == []
    finally:
        release.set()
        thread.join(10)
    assert "saved" in folder_backup.auto_backup(lib)


def test_overlapping_backups_take_turns_and_never_replace_each_others_zip(tmp_path, monkeypatch):
    """A manual backup that starts while another is running waits for it (deciding what
    changed, naming, publishing and pruning happen one after the other), then makes its own
    zip under its own name; the first zip stays byte for byte."""
    import threading

    lib, dest = make_library(tmp_path), tmp_path / "backups"
    in_pdfs, go_on, waiting = threading.Event(), threading.Event(), threading.Event()
    real_copy_pdfs = folder_backup._copy_pdfs

    def slow_copy(library, to, *inventory):
        if threading.current_thread().name == "first":
            in_pdfs.set()
            assert go_on.wait(30)
        return real_copy_pdfs(library, to, *inventory)

    monkeypatch.setattr(folder_backup, "_copy_pdfs", slow_copy)
    real_pause = folder_backup._pause
    monkeypatch.setattr(folder_backup, "_pause", lambda: (waiting.set(), real_pause()))
    results = {}
    first = threading.Thread(
        name="first",
        target=lambda: results.update(first=folder_backup.back_up(dest, True, lib)),
    )
    first.start()
    assert in_pdfs.wait(10)
    (first_zip,) = folder_backup.zips(dest, lib)
    first_bytes = first_zip.read_bytes()
    second = threading.Thread(
        target=lambda: results.update(second=folder_backup.back_up(dest, True, lib))
    )
    second.start()
    assert waiting.wait(10)  # the second one is waiting for the lock...
    assert folder_backup.zips(dest, lib) == [first_zip]  # ...having done nothing yet
    go_on.set()
    first.join(30)
    second.join(30)
    assert results["first"]["file"] == first_zip.name
    assert results["second"]["file"] and results["second"]["file"] != first_zip.name
    assert [z.name for z in folder_backup.zips(dest, lib)] == [
        first_zip.name,
        results["second"]["file"],
    ]
    assert first_zip.read_bytes() == first_bytes and leftovers(dest) == []
    assert zipfile.ZipFile(dest / results["second"]["file"]).testzip() is None


def test_a_zip_is_never_published_over_one_already_there(tmp_path, monkeypatch):
    """Even a zip with the same name appearing just before publication (another version of
    the tool, another computer on a shared folder) is never replaced: the next name is used."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    real_publish = folder_backup._publish_new
    theirs = []

    def someone_else_first(part, target):
        if not theirs:
            target.write_bytes(b"someone else's finished zip")
            theirs.append(target)
        return real_publish(part, target)

    monkeypatch.setattr(folder_backup, "_publish_new", someone_else_first)
    result = folder_backup.back_up(dest, pdfs=False, library=lib)
    assert theirs[0].read_bytes() == b"someone else's finished zip"
    assert result["file"] != theirs[0].name and result["file"].endswith("-2.zip")
    assert zipfile.ZipFile(dest / result["file"]).testzip() is None


def test_another_spelling_of_the_folder_meets_the_same_lock(tmp_path, monkeypatch):
    if os.name != "nt":
        pytest.skip("junctions are a Windows thing")
    import _winapi

    lib, dest = make_library(tmp_path), tmp_path / "backups"
    dest.mkdir()
    other = tmp_path / "same-backups"
    _winapi.CreateJunction(str(dest), str(other))
    monkeypatch.setattr(folder_backup, "LOCK_WAIT", 0)
    thread, release = hold_the_lock_in_a_thread(dest)
    try:
        with pytest.raises(folder_backup.BackupBusy):
            folder_backup.back_up(other, pdfs=False, library=lib)
    finally:
        release.set()
        thread.join(10)
    assert folder_backup.back_up(other, pdfs=False, library=lib)["file"]


def test_another_process_holding_the_folder_makes_a_backup_wait(tmp_path, monkeypatch):
    """Two real processes (the lock is the operating system's, not a Python one)."""
    import subprocess
    import sys

    lib, dest = make_library(tmp_path), tmp_path / "backups"
    dest.mkdir()
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, sys.argv[1]); import folder_backup, pathlib\n"
            "with folder_backup._one_backup_at_a_time(pathlib.Path(sys.argv[2]), 5):\n"
            "    print('held', flush=True); sys.stdin.readline()",
            str(folder_backup.paths.APP / "scripts"),
            str(dest),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout.readline().strip() == "held"
        monkeypatch.setattr(folder_backup, "LOCK_WAIT", 0)
        with pytest.raises(folder_backup.BackupBusy):
            folder_backup.back_up(dest, pdfs=False, library=lib)
        assert folder_backup.zips(dest, lib) == []
    finally:
        holder.communicate("\n", timeout=30)
    assert folder_backup.back_up(dest, pdfs=False, library=lib)["file"]


def test_retention_keeps_the_new_zip_and_everything_when_a_date_is_in_the_future(
    tmp_path, monkeypatch
):
    """Retention went by file times: zips whose times were in the future (a wrong clock, a
    copied folder) counted as the newest, so the zip just made could be the one deleted. Now
    the new zip always stays, and with any date in the future nothing is deleted."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    dest.mkdir()
    monkeypatch.setattr(folder_backup, "KEEP", 2)
    base = folder_backup.backup_name(lib)
    future = 4_102_444_800_000_000_000  # 2100-01-01
    for stamp in ("2026-01-01 1200", "2026-02-01 1200"):
        old = dest / f"{base} {stamp}.zip"
        folder_backup.back_up(dest, pdfs=False, library=lib)
        newest = folder_backup.zips(dest, lib)[-1]
        newest.rename(old)
        set_times(old, future)  # their file times in the future
    result = folder_backup.back_up(dest, pdfs=False, library=lib)
    names = [z.name for z in folder_backup.zips(dest, lib)]
    assert result["file"] in names and len(names) == 3
    assert "no older backup deleted" in result["message"]

    for z in folder_backup.zips(dest, lib):
        set_times(z, 1_700_000_000_000_000_000)  # 2023: no time in the future any more
    (dest / f"{base} 2099-12-31 2359.zip").write_bytes(
        (dest / result["file"]).read_bytes()
    )  # a name dated in the future
    later = folder_backup.back_up(dest, pdfs=False, library=lib)
    assert later["file"] in [z.name for z in folder_backup.zips(dest, lib)]
    assert len(folder_backup.zips(dest, lib)) == 5

    (dest / f"{base} 2099-12-31 2359.zip").unlink()
    last = folder_backup.back_up(dest, pdfs=False, library=lib)
    assert [z.name for z in folder_backup.zips(dest, lib)][-1] == last["file"]
    assert len(folder_backup.zips(dest, lib)) == 2  # ordinary retention again


def test_a_zip_with_a_future_time_doesnt_stop_the_daily_backup(tmp_path, monkeypatch):
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    dest.mkdir()
    monkeypatch.setattr(paths, "load_settings", lambda: {"backup_folder": str(dest)})
    assert "saved" in folder_backup.auto_backup(lib)
    (first,) = folder_backup.zips(dest, lib)
    set_times(first, 4_102_444_800_000_000_000)  # 2100
    (lib / "notes" / "vocabulary-review.json").unlink()
    assert "saved" in folder_backup.auto_backup(lib)


def test_a_damaged_instructions_member_is_never_taken_as_unchanged(tmp_path):
    """The instructions were skipped when comparing, so damage there went unseen. Every member
    is now read to its end (CRC); other instructions' words from an older version are fine."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    folder_backup.back_up(dest, pdfs=False, library=lib)
    (last,) = folder_backup.zips(dest, lib)
    members = [("RESTORE.txt", b"older instructions, other words")] + [
        (f.relative_to(lib).as_posix(), f.read_bytes()) for f in folder_backup.your_files(lib)
    ]
    write_zip(last, members)  # stored: each member's bytes are in the file as they are
    assert folder_backup.back_up(dest, pdfs=False, library=lib, only_if_changed=True)[
        "file"
    ] == ""  # fmt: skip
    data = last.read_bytes()
    at = data.index(b"older instructions")
    last.write_bytes(data[:at] + b"O" + data[at + 1 :])
    result = folder_backup.back_up(dest, pdfs=False, library=lib, only_if_changed=True)
    assert result["file"] and "wasn't trusted" in result["message"]
    assert last.read_bytes()[at] == ord("O")  # the damaged zip is kept as it is


@pytest.mark.parametrize("taken", ["RESTORE.txt", "restore.TXT", "Restore.txt/"])
def test_a_library_file_or_folder_named_like_the_instructions_is_kept_whole(tmp_path, taken):
    """A library's own RESTORE.txt (any case; or a folder of that name) went into the zip next
    to the instructions of the same name: unzipping put one over the other. The instructions
    now take another name, so the user's file restores byte for byte; nothing is left out."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    if taken.endswith("/"):
        put(lib / taken.rstrip("/") / "inside.md", b"my folder's note")
    else:
        put(lib / taken, b"my own restore notes")
    result = folder_backup.back_up(dest, pdfs=False, library=lib)
    contents_ = zip_bytes(dest / result["file"])
    assert contents_["RESTORE1.TXT"] == folder_backup.RESTORE.encode()
    assert {k: v for k, v in contents_.items() if k != "RESTORE1.TXT"} == (library_bytes(lib))
    restored = tmp_path / "restored"
    with zipfile.ZipFile(dest / result["file"]) as z:
        z.extractall(restored)
    for name, data in library_bytes(lib).items():
        assert (restored / name).read_bytes() == data
    again = folder_backup.back_up(dest, pdfs=False, library=lib, only_if_changed=True)
    assert again["file"] == ""  # a stable layout: nothing changed


def test_with_both_instruction_names_taken_the_backup_is_refused_before_anything(
    tmp_path, monkeypatch
):
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    monkeypatch.setattr(folder_backup, "KEEP", 1)
    folder_backup.back_up(dest, pdfs=False, library=lib)
    (only,) = folder_backup.zips(dest, lib)
    for name in folder_backup.INSTRUCTIONS:
        put(lib / name, b"mine")
    for only_if_changed in (False, True):
        with pytest.raises(folder_backup.BackupIncomplete, match="named like the backup's"):
            folder_backup.back_up(dest, pdfs=False, library=lib, only_if_changed=only_if_changed)
        assert folder_backup.zips(dest, lib) == [only] and leftovers(dest) == []


# --- M7.1 S2 round 3, after Codex's second review: Windows names, the 8.3 instructions -------


def exact(path):
    r"""`path` exactly as written, a trailing dot or space kept (the \\?\ form, lexical only),
    to make the odd names these tests need."""
    return Path("\\\\?\\" + os.path.normpath(str(path))) if os.name == "nt" else Path(path)


def make_exactly(path, data: bytes):
    os.makedirs(exact(path.parent), exist_ok=True)
    with open(exact(path), "wb") as f:
        f.write(data)


def with_one_backup(lib, dest, monkeypatch):
    """A library with one finished backup (KEEP 1: a new zip would delete it): (zip, bytes)."""
    monkeypatch.setattr(folder_backup, "KEEP", 1)
    folder_backup.back_up(dest, pdfs=True, library=lib)
    (only,) = folder_backup.zips(dest, lib)
    return only, only.read_bytes()


def assert_refused(lib, dest, only, kept, shown, monkeypatch):
    """Every way of backing up refuses, naming `shown`; nothing is published or deleted."""
    for only_if_changed in (False, True):
        with pytest.raises(folder_backup.AmbiguousName, match=re.escape(f"can't back up {shown}")):
            folder_backup.back_up(dest, pdfs=True, library=lib, only_if_changed=only_if_changed)
    monkeypatch.setattr(
        paths, "load_settings", lambda: {"backup_folder": str(dest), "backup_pdfs": True}
    )
    set_times(only, only.stat().st_mtime_ns - 25 * 3_600_000_000_000)  # due for today's
    assert f"backup failed: can't back up {shown}" in folder_backup.auto_backup(lib)
    assert folder_backup.zips(dest, lib) == [only] and only.read_bytes() == kept
    assert leftovers(dest) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows name rules")
@pytest.mark.parametrize("deep", [False, True], ids=["short path", "deep path"])
@pytest.mark.parametrize(
    "odd", ["note.md.", "note.md ", "drafts./x.md", "drafts /x.md"], ids=lambda s: repr(s)
)
def test_a_name_windows_would_change_is_refused_and_never_read_as_another(
    tmp_path, monkeypatch, deep, odd
):
    """A name ending in a dot or space: in a short path Windows read "note.md." as "note.md"
    (another file) into the zip; in a deep one it was read right but unzips as another name.
    Either way the backup now refuses, naming it; nothing is written, the old zip stays."""
    lib = make_deep_library(tmp_path) if deep else make_library(tmp_path)
    dest = tmp_path / "backups"
    put(lib / "notes" / "a-book" / "note.md", b"THE REAL NOTE")
    only, kept = with_one_backup(lib, dest, monkeypatch)
    make_exactly(lib / "notes" / "a-book" / odd, b"another file")
    assert_refused(lib, dest, only, kept, f"notes/a-book/{odd.split('/')[0]}", monkeypatch)


@pytest.mark.skipif(os.name != "nt", reason="Windows name rules")
@pytest.mark.parametrize("odd", ["CON.md", "nul", "COM1.txt", "NOTES~1.MD", "draft~2.md"])
def test_a_device_name_or_a_short_name_shape_is_refused(tmp_path, monkeypatch, odd):
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    only, kept = with_one_backup(lib, dest, monkeypatch)
    make_exactly(lib / "notes" / odd, b"mine")
    assert_refused(lib, dest, only, kept, f"notes/{odd}", monkeypatch)


@pytest.mark.parametrize(
    "name, problem",
    [
        ("note.md.", "dot or a space"),
        ("note.md ", "dot or a space"),
        ("a:b.md", "character"),
        ("a<b.md", "character"),
        ("back\\slash.md", "character"),
        ("tab\there.md", "character"),
        ("CON", "device"),
        ("con.txt", "device"),
        ("LPT9.md", "device"),
        ("COM¹.md", "device"),
        ("PROGRA~1", "short name"),
        ("RESTOR~1.TXT", "short name"),
        ("notes.md", ""),
        ("RESTORE1.TXT", ""),
        ("~$draft.docx", ""),
        ("a~b.md", ""),
        ("version~1 of my long note.md", ""),
        ("CONTEXT.md", ""),
        (" leading space.md", ""),
    ],
)
def test_which_names_windows_cant_keep(name, problem):
    found = folder_backup._name_problem(name)
    assert (problem in found and found) if problem else found == ""


def test_two_names_differing_only_in_case_are_refused():
    """(Possible on a case-sensitive folder or another system; Windows would restore one file.)"""
    with pytest.raises(folder_backup.AmbiguousName, match="notes/a.md: A.md"):
        folder_backup._check_names(("notes",), ["A.md", "b.md", "a.md"])
    folder_backup._check_names(("notes",), ["A.md", "b.md"])  # (no error)


@pytest.mark.skipif(os.name != "nt", reason="Windows device names")
def test_a_pdf_with_a_device_name_is_never_read_and_is_reported(tmp_path):
    """ "NUL.pdf" in the ordinary form is the NUL device: the backup "copied" it as an empty file.
    It is never read now, and the backup is refused before anything is written (round 4: the
    whole PDF inventory is checked before the zip; with existing backups, see below)."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    make_exactly(lib / "books" / "NUL.pdf", b"%PDF a real book called NUL")
    with pytest.raises(folder_backup.AmbiguousName, match="books/NUL.pdf: .*device"):
        folder_backup.back_up(dest, pdfs=True, library=lib)
    assert contents(dest) == []  # no zip, no PDF copy (not even of the other PDF)


def short_name(path) -> str:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    buffer = ctypes.create_unicode_buffer(32768)
    if not kernel32.GetShortPathNameW(str(exact(path)), buffer, len(buffer)):
        raise ctypes.WinError(ctypes.get_last_error())
    return Path(buffer.value).name


@pytest.mark.skipif(os.name != "nt", reason="Windows 8.3 short names")
def test_the_other_instructions_name_has_no_short_name_to_collide_with(tmp_path):
    """Round 2 named the instructions "RESTORE (myLibrary backup).txt", which Windows gives the
    short name RESTOR~1.TXT when unzipped: a library file of that name was then written into it.
    The other name is now a plain 8.3 name: unzipped, it has no second name."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    put(lib / "RESTORE.txt", b"my own restore notes")
    result = folder_backup.back_up(dest, pdfs=False, library=lib)
    restored = tmp_path / "restored"
    with zipfile.ZipFile(dest / result["file"]) as z:
        assert "RESTORE1.TXT" in z.namelist()
        z.extractall(restored)
    probe = restored / "a long name to test short names.txt"
    probe.write_bytes(b"")
    if short_name(probe) == probe.name:
        pytest.skip("prerequisite: this volume makes no 8.3 short names")
    assert short_name(restored / "RESTORE1.TXT") == "RESTORE1.TXT"
    assert (restored / "RESTORE1.TXT").read_bytes() == folder_backup.RESTORE.encode()
    assert (restored / "RESTORE.txt").read_bytes() == b"my own restore notes"


@pytest.mark.skipif(os.name != "nt", reason="Windows 8.3 short names")
def test_a_library_file_named_like_a_short_name_is_refused_not_published(tmp_path, monkeypatch):
    """The reproduced collision: RESTORE.txt and RESTOR~1.TXT in the library. Round 2 published
    a zip that lost a file when unzipped; now the backup is refused, naming RESTOR~1.TXT."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    only, kept = with_one_backup(lib, dest, monkeypatch)
    put(lib / "RESTORE.txt", b"my own restore notes")
    put(lib / "RESTOR~1.TXT", b"my short-named file")
    assert_refused(lib, dest, only, kept, "RESTOR~1.TXT", monkeypatch)


# --- M7.1 S2 round 4, after Codex's third review: the library's own path, the PDF inventory
# before publication ----------------------------------------------------------------------------


def everything_in(dest) -> dict:
    """Every file in a backup folder, byte for byte (the lock's marker file aside)."""
    found = {}
    for folder, _, names in os.walk(exact(dest)):
        for name in names:
            path = os.path.join(folder, name)
            if name != folder_backup.LOCK_NAME:
                with open(path, "rb") as f:
                    found[os.path.relpath(path, exact(dest))] = f.read()
    return found


def make_library_with_id(lib, pdf: bytes, *, library_id: str):
    """A library made through the exact form (its folder may end in a dot): its own id, the
    display name every one of these shares, a note and a PDF."""
    make_exactly(lib / "library.toml", f'name = "Same name"\nid = "{library_id}"\n'.encode())
    make_exactly(lib / "catalog.csv", b"slug\na-book\n")
    make_exactly(lib / "notes" / "a-book" / "README.md", b"Last read: page 3\n")
    make_exactly(lib / "books" / "a-book.pdf", pdf)
    return lib


@pytest.mark.skipif(os.name != "nt", reason="Windows path normalisation")
@pytest.mark.parametrize("odd", ["lib.", "lib ", "parent./lib"], ids=repr)
def test_a_library_whose_own_path_windows_would_change_never_touches_another(
    tmp_path, monkeypatch, odd
):
    """Codex's round-3 finding: "lib." (another folder, another id, other PDFs) was read as
    "lib" for its id, so its backups had lib's name: with KEEP 1, backing up "lib." deleted
    lib's zip and replaced lib's PDF copy. Now every way of backing it up is refused before
    anything is read through the path or written; lib's backups stay byte for byte."""
    import uuid

    base = tmp_path / ("parent" if odd.startswith("parent") else "")
    lib = make_library_with_id(base / "lib", b"%PDF lib's book", library_id=str(uuid.uuid4()))
    other = make_library_with_id(
        tmp_path / odd, b"%PDF the other's book", library_id=str(uuid.uuid4())
    )
    dest = tmp_path / "backups"
    monkeypatch.setattr(folder_backup, "KEEP", 1)
    folder_backup.back_up(dest, pdfs=True, library=lib)
    before = everything_in(dest)
    assert any(k.endswith("a-book.pdf") for k in before) and len(folder_backup.zips(dest, lib)) == 1
    for only_if_changed in (False, True):
        with pytest.raises(folder_backup.AmbiguousName, match=re.escape(repr(odd.split("/")[0]))):
            folder_backup.back_up(dest, pdfs=True, library=other, only_if_changed=only_if_changed)
    monkeypatch.setattr(
        paths, "load_settings", lambda: {"backup_folder": str(dest), "backup_pdfs": True}
    )
    (only,) = folder_backup.zips(dest, lib)
    set_times(only, only.stat().st_mtime_ns - 25 * 3_600_000_000_000)  # due for today's
    before = everything_in(dest)
    assert "backup failed: can't back up: the library folder" in folder_backup.auto_backup(other)
    assert everything_in(dest) == before  # lib's zip and PDF copy, byte for byte
    assert folder_backup.back_up(dest, pdfs=True, library=lib)["pdfs"] == 0  # lib's still right


@pytest.mark.skipif(os.name != "nt", reason="Windows path normalisation")
def test_a_backup_folder_whose_own_path_windows_would_change_is_refused(tmp_path):
    lib = make_library(tmp_path)
    good, odd = tmp_path / "backups", tmp_path / "backups."
    folder_backup.back_up(good, pdfs=True, library=lib)
    before = everything_in(good)
    with pytest.raises(folder_backup.AmbiguousName, match="the backup folder's own path"):
        folder_backup.back_up(odd, pdfs=True, library=lib)
    assert everything_in(good) == before and not os.path.exists(exact(odd))


@pytest.mark.skipif(os.name != "nt", reason="junctions are a Windows thing")
def test_a_junction_to_the_library_is_still_the_same_library(tmp_path):
    """What is kept: a junction (or link, or 8.3 short name) in the library's path reaches the
    same folder, never another: it is backed up as before."""
    import _winapi

    lib, dest = make_library(tmp_path), tmp_path / "backups"
    alias = tmp_path / "my-library-link"
    _winapi.CreateJunction(str(lib), str(alias))
    result = folder_backup.back_up(dest, pdfs=True, library=alias)
    assert result["file"] and result["pdfs"] == 1
    assert zip_bytes(dest / result["file"])["catalog.csv"] == (lib / "catalog.csv").read_bytes()


@pytest.mark.skipif(os.name != "nt", reason="Windows device names")
def test_an_unsafe_pdf_is_refused_before_the_zip_or_any_copy_changes(tmp_path, monkeypatch):
    """Codex's round-3 finding: books/NUL.pdf was found only after the new zip was published and
    retention (KEEP 1) had deleted the old one. The whole PDF inventory is now checked first:
    with a changed note, every way of backing up refuses, naming it and why, and every earlier
    backup (the zip and the PDF copy) stays byte for byte."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    monkeypatch.setattr(folder_backup, "KEEP", 1)
    folder_backup.back_up(dest, pdfs=True, library=lib)
    (only,) = folder_backup.zips(dest, lib)
    set_times(only, only.stat().st_mtime_ns - 25 * 3_600_000_000_000)  # due for today's
    (lib / "notes" / "a-book" / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    make_exactly(lib / "books" / "NUL.pdf", b"%PDF a real book called NUL")
    before = everything_in(dest)
    for only_if_changed in (False, True):
        with pytest.raises(folder_backup.AmbiguousName, match="books/NUL.pdf: .*device"):
            folder_backup.back_up(dest, pdfs=True, library=lib, only_if_changed=only_if_changed)
        assert everything_in(dest) == before
    monkeypatch.setattr(
        paths, "load_settings", lambda: {"backup_folder": str(dest), "backup_pdfs": True}
    )
    message = folder_backup.auto_backup(lib)
    assert "backup failed: can't back up books/NUL.pdf" in message and "device" in message
    assert everything_in(dest) == before and leftovers(dest) == []
    # without PDF copies, the PDFs aren't backed up, so their names don't stop the zip
    assert folder_backup.back_up(dest, pdfs=False, library=lib)["file"]


def test_a_pdf_copy_failing_after_the_zip_says_so_and_deletes_no_old_zip(tmp_path, monkeypatch):
    """A PDF that can't be copied after the checks (a full disk) still lets the new zip stand,
    but the backup isn't complete: the message says what was saved, copied and not, and no old
    zip is deleted (retention only after everything succeeded)."""
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    (lib / "papers").mkdir()
    monkeypatch.setattr(folder_backup, "KEEP", 1)
    folder_backup.back_up(dest, pdfs=True, library=lib)
    (only,) = folder_backup.zips(dest, lib)
    kept = only.read_bytes()
    (lib / "notes" / "a-book" / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    (lib / "books" / "a-book.pdf").write_bytes(b"%PDF-1.4 BOOK")
    (lib / "papers" / "p.pdf").write_bytes(b"%PDF paper")
    real_copy = folder_backup.shutil.copyfile

    def full_disk(source, target):
        if str(source).endswith("a-book.pdf"):
            raise OSError(28, "No space left on device")
        return real_copy(source, target)

    monkeypatch.setattr(folder_backup.shutil, "copyfile", full_disk)
    with pytest.raises(folder_backup.BackupIncomplete) as failed:
        folder_backup.back_up(dest, pdfs=True, library=lib)
    message = str(failed.value)
    assert "not complete: saved " in message and "; 1 PDF copied;" in message
    assert "books/a-book.pdf (No space left on device)" in message
    assert message.endswith("no older backup deleted")
    zips_now = folder_backup.zips(dest, lib)
    assert len(zips_now) == 2 and zips_now[0] == only and only.read_bytes() == kept
    assert backup_pdf(dest).read_bytes() == b"%PDF-1.4 book"  # its earlier copy
    assert (dest / "PDFs" / "papers" / "p.pdf").read_bytes() == b"%PDF paper"
    monkeypatch.setattr(folder_backup.shutil, "copyfile", real_copy)
    done = folder_backup.back_up(dest, pdfs=True, library=lib)  # all good again: KEEP applies
    assert [z.name for z in folder_backup.zips(dest, lib)] == [done["file"]]


def test_a_file_gone_while_the_inventory_is_taken_is_listed_again(tmp_path, monkeypatch):
    lib, dest = make_library(tmp_path), tmp_path / "backups"
    real = folder_backup.your_files
    calls = []

    def gone_once(library):
        calls.append(1)
        if len(calls) == 1:
            raise FileNotFoundError(2, "The system cannot find the file specified", "x.md")
        return real(library)

    monkeypatch.setattr(folder_backup, "your_files", gone_once)
    assert folder_backup.back_up(dest, pdfs=True, library=lib)["file"]
    assert len(calls) >= 2


def test_the_openalex_key_goes_only_to_openalex(monkeypatch):
    monkeypatch.setattr(paths, "load_settings", lambda: {"openalex_key": "abc123secret"})
    sent = []

    class Answer:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def read(self):
            return b"{}"

    def urlopen(request, timeout):
        sent.append((request.full_url, request.get_header("Authorization")))
        return Answer()

    monkeypatch.setattr(book_meta.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(book_meta.json, "load", lambda r: {})
    book_meta._get_json("https://api.openalex.org/works?search=x")
    book_meta._get_json("https://api.crossref.org/works/10.1/x")
    assert sent == [("https://api.openalex.org/works?search=x", "Bearer abc123secret"),
                    ("https://api.crossref.org/works/10.1/x", None)]  # fmt: skip
