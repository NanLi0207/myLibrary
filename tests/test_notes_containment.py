"""D19: a document's notes folder comes from catalog.csv, which a person may edit by hand. A
value outside notes/ (an absolute path, "..", another folder), or a README / vocabulary file
that is a link pointing out of its notes folder, is refused by everything that reads or writes
there (reading progress, ticks, saved words, chapter refresh, merging repeats), before anything
changes. One such entry never makes the library page unusable, Refresh only reports it, and the
messages never show a full path. A notes folder (or notes/ itself) kept elsewhere through a
junction, as on OneDrive, still works. Temporary libraries only."""

import io
import json
import os
import shutil
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import add_book
import catalog
import library_jobs
import library_page
import library_server
import notes_store
import pytest
import reader
from book_toc import Chapter
from reportlab.pdfgen import canvas
from testlib import id_of, put

NAME = "doe-2015-optics"
README = """# Optics

## Reading progress

- [ ] [Ch 1: Basics](ch01-basics.md)
- [ ] [Ch 2: Lenses](ch02-lenses.md)

## Notes
"""
ECDICT = "word,phonetic,definition,translation,pos,collins,oxford,tag,bnc,frq,exchange,detail,audio\npupil,'pju:pl,,n. 瞳孔,,,,,0,0,,,\n"  # noqa: E501
CHAPTERS = [Chapter(1, "Basics", ["Rays"]), Chapter(2, "Lenses")]
REQUIRE_LINKS = os.environ.get("MYLIBRARY_REQUIRE_LINK_TESTS") == "1"  # CI: never skipped
BAD = ["windows-absolute", "posix-absolute", "traversal", "outside-notes"]


def pdf_bytes() -> bytes:
    out = io.BytesIO()
    c = canvas.Canvas(out)
    c.drawString(72, 720, "Invented text.")
    c.showPage()
    c.save()
    return out.getvalue()


@pytest.fixture
def lib(tmp_path, monkeypatch):
    """A one-book library (its README lists 2 chapters), every module pointed at it."""
    library = tmp_path / "library"
    for name in ("BOOKS", "PAPERS", "THESES", "EXAMPLES", "NOTES"):
        monkeypatch.setattr(add_book, name, library / name.lower())
    monkeypatch.setattr(add_book, "CATALOG", library / "catalog.csv")
    monkeypatch.setattr(add_book, "ARCHIVE", library / "archive")
    monkeypatch.setattr(add_book, "LIBRARY", library)
    monkeypatch.setattr(add_book, "PAGE_CACHE", library / ".cache" / "chapter_pages.json")
    monkeypatch.setattr(add_book, "book_chapters", lambda pdf: CHAPTERS)
    for module in (library_server, library_page):
        monkeypatch.setattr(module, "LIBRARY", library)
        monkeypatch.setattr(module, "CATALOG", library / "catalog.csv")
    monkeypatch.setattr(library_server.webbrowser, "open", lambda *a, **k: True)
    monkeypatch.setattr(library_server, "open_in_editor", lambda *files: True)
    monkeypatch.setattr(library_page, "build", lambda: None)
    monkeypatch.setattr(library_jobs.book_search, "update", lambda: 0)
    monkeypatch.setattr(library_jobs, "_jobs", {})
    # A one-word dictionary, no glossaries
    (library / ".cache").mkdir(parents=True)
    (tmp_path / "ecdict.csv").write_text(ECDICT, encoding="utf-8")
    db = tmp_path / "ecdict.db"
    reader.build_dictionary(tmp_path / "ecdict.csv", db)
    (library / "glossaries").mkdir()
    monkeypatch.setattr(reader, "LIBRARY", library)
    monkeypatch.setattr(reader, "DICT_DB", db)
    monkeypatch.setattr(reader, "GLOSSARIES", library / "glossaries")
    monkeypatch.setattr(reader, "GLOSSARY_CONFIG", library / "glossaries" / "glossaries.toml")
    monkeypatch.setattr(reader, "_glossary_cache", None)
    monkeypatch.setattr(reader, "_glossary_words_cache", None)
    reader._lemma.cache_clear()
    (library / "books").mkdir()
    (library / "books" / f"{NAME}.pdf").write_bytes(pdf_bytes())
    notes = library / "notes" / NAME
    notes.mkdir(parents=True)
    (notes / "README.md").write_text(README, encoding="utf-8")
    row = {"slug": NAME, "title": "Optics", "type": "book", "file": f"books/{NAME}.pdf"}
    put(library / "catalog.csv", row | {"notes": f"notes/{NAME}/"})
    yield library
    reader._lemma.cache_clear()


def a_notes_folder(folder) -> None:
    """What a document's notes folder holds: a README, saved words, a chapter template."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "README.md").write_text(README, encoding="utf-8")
    (folder / "vocabulary.md").write_text("# Vocabulary: someone else's\n", encoding="utf-8")
    (folder / "ch02-old.md").write_text("# Chapter 2: Old\n\n## Key ideas\n\n-\n", "utf-8")


def files_under(folder) -> dict:
    return {p.relative_to(folder).as_posix(): p.read_bytes()
            for p in sorted(folder.rglob("*")) if p.is_file()}  # fmt: skip


def bad_notes(kind: str, library, outside) -> str:
    """A hand-edited catalog `notes` value naming the folder `outside`."""
    if kind == "windows-absolute":
        return str(outside) + "\\"
    if kind == "posix-absolute":  # "/Users/.../elsewhere/": the library's drive, no letter
        return outside.as_posix().split(":", 1)[-1] + "/"
    if kind == "traversal":
        return "notes/../" + os.path.relpath(outside, library).replace("\\", "/") + "/"
    return outside.relative_to(library).as_posix() + "/"  # in the library, not in notes/


def outside_folder(kind: str, library, tmp_path):
    folder = library / "other" if kind == "outside-notes" else tmp_path / "elsewhere"
    a_notes_folder(folder)
    return folder


def operations(library, doc_id):
    """Everything that reads or writes a document's notes folder outside the panel."""
    pdf = library / "books" / f"{NAME}.pdf"
    return {
        "Last read": lambda: library_server.save_position(doc_id, 12),
        "tick": lambda: library_server.tick(doc_id, 1, True),
        "save word": lambda: reader.save_word(doc_id, "Optics", "pupil", "", 3),
        "chapter refresh": lambda: add_book.refresh_chapters(pdf, dry_run=False),
        "own work": lambda: add_book.has_own_work(
            add_book.notes_dir_of(catalog.load(library / "catalog.csv")[doc_id])
        ),  # fmt: skip
    }


@pytest.mark.parametrize("kind", BAD)
def test_a_notes_folder_outside_notes_is_refused_before_anything_changes(lib, tmp_path, kind):
    outside = outside_folder(kind, lib, tmp_path)
    doc_id = id_of(lib / "catalog.csv", NAME)
    catalog.set_field(lib / "catalog.csv", doc_id, "notes", bad_notes(kind, lib, outside))
    before, catalog_before = files_under(outside), (lib / "catalog.csv").read_bytes()
    for name, operation in operations(lib, doc_id).items():
        with pytest.raises(notes_store.NoteError) as refused:
            operation()
        assert str(outside) not in str(refused.value), name  # no full path in the message
        assert outside.as_posix() not in str(refused.value), name
        assert files_under(outside) == before, name
    assert (lib / "catalog.csv").read_bytes() == catalog_before
    assert not (lib / "archive").exists()  # chapter refresh archived nothing


def link_or_skip(make_link, what: str) -> None:
    """Create the test's link, or skip (fail in CI: MYLIBRARY_REQUIRE_LINK_TESTS=1) where
    this system doesn't allow it (symlinks need Developer Mode or administrator rights)."""
    try:
        make_link()
    except OSError as e:
        reason = f"this system doesn't allow creating a {what} here ({e.strerror})"
        if REQUIRE_LINKS:
            pytest.fail(f"MYLIBRARY_REQUIRE_LINK_TESTS=1, but {reason}", pytrace=False)
        pytest.skip(reason)


@pytest.mark.parametrize("name", ["README.md", "vocabulary.md"])
@pytest.mark.parametrize("link", ["symlink", "junction"])
def test_a_readme_or_vocabulary_linked_from_outside_is_refused(lib, tmp_path, name, link):
    """A README.md or vocabulary.md that is a link pointing out of the notes folder is never
    read or written; a junction (needs no rights) stands in for a folder named like the file."""
    outside = outside_folder("elsewhere", lib, tmp_path)
    own = lib / "notes" / NAME / name
    own.unlink(missing_ok=True)
    if link == "symlink":
        link_or_skip(lambda: os.symlink(outside / name, own), "symlink")
    else:
        if sys.platform != "win32":
            pytest.skip("directory junctions are a Windows feature")
        import _winapi

        _winapi.CreateJunction(str(outside), str(own))
    doc_id = id_of(lib / "catalog.csv", NAME)
    before = files_under(outside)
    uses = ["Last read", "tick", "chapter refresh"] if name == "README.md" else ["save word"]
    for use in uses:
        with pytest.raises(notes_store.NoteError):
            operations(lib, doc_id)[use]()
        assert files_under(outside) == before, use
    if name == "README.md":
        [book] = library_page.books()
        assert book["notes_problem"] and book["chapter_list"] == []


def normal_use_works(library, doc_id, folder) -> None:
    """Reading progress, ticks, saved words and chapter refresh all work, in `folder`."""
    assert library_server.save_position(doc_id, 3)["page"] == 3
    assert library_server.tick(doc_id, 2, True)[1]["done"] is True
    assert reader.save_word(doc_id, "Optics", "pupil", "", 3)["saved"] is True
    add_book.refresh_chapters(library / "books" / f"{NAME}.pdf", dry_run=False)
    readme = (folder / "README.md").read_text("utf-8")
    assert "Last read: page 3" in readme and "- [x] [Ch 2: Lenses]" in readme
    assert "| pupil |" in (folder / "vocabulary.md").read_text("utf-8")
    assert (folder / "ch01-basics.md").exists()  # the template refresh wrote


def test_normal_progress_ticks_words_and_refresh(lib):
    normal_use_works(lib, id_of(lib / "catalog.csv", NAME), lib / "notes" / NAME)


@pytest.mark.skipif(sys.platform != "win32", reason="directory junctions are a Windows feature")
@pytest.mark.parametrize("linked", ["the document's folder", "notes/"])
def test_notes_kept_elsewhere_through_a_junction_still_work(lib, tmp_path, linked):
    """The user's own arrangement (e.g. notes on OneDrive): allowed, as in the notes panel."""
    import _winapi

    onedrive = tmp_path / "OneDrive"
    onedrive.mkdir()
    here = lib / "notes" if linked == "notes/" else lib / "notes" / NAME
    shutil.move(here, onedrive / here.name)
    _winapi.CreateJunction(str(onedrive / here.name), str(here))
    folder = onedrive / "notes" / NAME if linked == "notes/" else onedrive / NAME
    normal_use_works(lib, id_of(lib / "catalog.csv", NAME), folder)


def test_one_bad_entry_never_breaks_the_library_page(lib, tmp_path):
    outside = outside_folder("elsewhere", lib, tmp_path)
    before = files_under(outside)
    good = id_of(lib / "catalog.csv", NAME)
    library_server.tick(good, 1, True)
    (lib / "books" / "roe-2016-mirrors.pdf").write_bytes(pdf_bytes())
    bad = put(lib / "catalog.csv", {"slug": "roe-2016-mirrors", "title": "Mirrors",
                                    "file": "books/roe-2016-mirrors.pdf",
                                    "notes": str(outside) + "\\"})  # fmt: skip
    books = {b["id"]: b for b in library_page.books()}
    assert books[good]["chapter_list"][0]["done"] is True and not books[good]["notes_problem"]
    assert books[bad]["notes_problem"] and books[bad]["chapter_list"] == []
    assert books[bad]["notes_uri"] == "" and books[bad]["notes"] == ""
    assert str(outside) not in json.dumps(books[bad]["notes_problem"])
    page = library_page.render()  # the whole page, with the warning on that one book
    assert "notes folder in catalog.csv" in page
    assert str(outside).replace("\\", "\\\\") not in page and outside.as_posix() not in page
    # Read still opens the PDF, without notes or progress
    message = library_server.open_chapter(bad, 1, "http://127.0.0.1:1")
    assert "PDF" in message and "no notes" in message and str(outside) not in message
    assert files_under(outside) == before


def test_the_server_answers_400_without_a_full_path(lib, tmp_path):
    outside = outside_folder("elsewhere", lib, tmp_path)
    doc_id = id_of(lib / "catalog.csv", NAME)
    catalog.set_field(lib / "catalog.csv", doc_id, "notes", str(outside) + "\\")
    before = files_under(outside)
    server = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        page = urllib.request.urlopen(base + "/", timeout=10).read().decode()
        assert "notes folder in catalog.csv" in page and outside.as_posix() not in page
        assert str(outside).replace("\\", "\\\\") not in page
        for path, body in [("/api/tick", {"chapter": 1, "done": True}),
                           ("/api/position", {"page": 4}),
                           ("/api/notes/list", {})]:  # fmt: skip
            request = urllib.request.Request(
                base + path, method="POST",
                data=json.dumps({"id": doc_id} | body).encode(),
                headers={"Content-Type": "application/json",
                         "X-Library-Token": library_server.TOKEN},
            )  # fmt: skip
            with pytest.raises(urllib.error.HTTPError) as refused:
                urllib.request.urlopen(request, timeout=10)
            answer = refused.value.read().decode()
            assert refused.value.code == 400, (path, answer)
            assert "notes" in answer and str(outside).replace("\\", "\\\\") not in answer
            assert outside.as_posix() not in answer, path
    finally:
        server.shutdown()
    assert files_under(outside) == before


def two_copies(library, outside):
    """The same work twice (same DOI, different details and shelves); the second's catalog
    notes folder points outside the library."""
    first = id_of(library / "catalog.csv", NAME)
    catalog.update(library / "catalog.csv", first, {"doi": "10.1/x", "added": "2026-01-01",
                                                    "shelves": "Optics"})  # fmt: skip
    (library / "books" / "doe-2015-optics-2.pdf").write_bytes(pdf_bytes())
    second = put(library / "catalog.csv", {
        "slug": "doe-2015-optics-2", "title": "Optics", "type": "book", "doi": "10.1/x",
        "file": "books/doe-2015-optics-2.pdf", "notes": str(outside) + "\\",
        "publisher": "Example Press", "added": "2026-02-01", "shelves": "Lens design",
    })  # fmt: skip
    return first, second


def test_refresh_never_merges_or_archives_a_pair_with_an_unsafe_notes_folder(lib, tmp_path):
    outside = outside_folder("elsewhere", lib, tmp_path)
    two_copies(lib, outside)
    before, catalog_before = files_under(outside), (lib / "catalog.csv").read_bytes()
    library_before = files_under(lib)
    [job] = library_jobs.check_catalog_repeats()
    assert job["status"] == "error" and "isn't under notes/" in job["message"]
    assert "nothing was merged or moved" in job["message"] and str(outside) not in job["message"]
    assert (lib / "catalog.csv").read_bytes() == catalog_before
    assert files_under(lib) == library_before and files_under(outside) == before


@pytest.mark.parametrize("direction", ["into the unsafe one", "from the unsafe one"])
def test_a_refused_merge_changes_nothing(lib, tmp_path, direction):
    """merge_into checks both notes folders and the README first: the catalog (details,
    shelves) and both documents stay exactly as they were."""
    outside = outside_folder("elsewhere", lib, tmp_path)
    first, second = two_copies(lib, outside)
    src, dst = (first, second) if direction == "into the unsafe one" else (second, first)
    before, catalog_before = files_under(outside), (lib / "catalog.csv").read_bytes()
    library_before = files_under(lib)
    with pytest.raises(notes_store.NoteError):
        add_book.merge_into(src, dst)
    assert (lib / "catalog.csv").read_bytes() == catalog_before
    assert files_under(lib) == library_before and files_under(outside) == before


def test_shown_errors_never_hold_a_full_path():
    error = ValueError(r"can't use C:\Users\someone\Documents\private\notes\x.md here")
    assert library_server.shown_error(error) == "can't use x.md here"


@pytest.mark.parametrize("operation", ["remove", "rename"])
def test_remove_and_rename_refuse_before_any_change(lib, tmp_path, operation):
    """No tombstone, no journal, no file moved, the catalog as it was."""
    outside = outside_folder("elsewhere", lib, tmp_path)
    doc_id = id_of(lib / "catalog.csv", NAME)
    catalog.set_field(lib / "catalog.csv", doc_id, "notes", str(outside) + "\\")
    before, library_before = files_under(outside), files_under(lib)
    with pytest.raises(notes_store.NoteError):
        if operation == "remove":
            add_book.remove_book(doc_id, dry_run=False, yes=True)
        else:
            add_book.rename_document(doc_id, "doe-2015-optics-renamed")
    assert files_under(lib) == library_before and files_under(outside) == before
