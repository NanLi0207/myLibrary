"""💾 Back up to a folder (folder_backup.py), and the OpenAlex key from Settings."""

import os
import zipfile

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
