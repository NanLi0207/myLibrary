"""Permanent document ids: the identity model, the one-time migration, tombstones, renaming.

Temporary libraries and invented documents only.
"""

import csv
import hashlib
import io
import json
import threading
import urllib.error
import urllib.request
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path

import add_book
import book_search
import catalog
import library_jobs
import library_page
import library_server
import migrate_ids
import pytest
import reading_log
import safe_io
import vocab_review
from reportlab.pdfgen import canvas
from testlib import entry, id_of, put

INDEX_BOOKS = book_search.update  # the real one (the fixtures stub it for the jobs)

OLD_HEADER = [c for c in catalog.COLUMNS if c != "id"] + ["my rating"]  # a column of your own
OLD_ROWS = [
    {"slug": "shannon-1997-art-science-optical-design", "type": "book",
     "title": "The art and science of optical design", "authors": "Robert R. Shannon",
     "year": "1997", "shelves": "Optics", "my rating": "5"},
    {"slug": "unknown-2020-untitled", "type": "book", "title": "光学设计", "authors": "张三",
     "year": "2020"},
    {"slug": "unknown-2020-untitled-2", "type": "book", "title": "激光技术", "authors": "李四",
     "year": "2020", "keywords": "激光; laser"},
    {"slug": "doe-2019-freeform", "type": "paper", "title": "Freeform optics, part 1",
     "authors": "Jane Doe", "year": "2019", "doi": "10.1/x", "file": "papers/doe-2019-freeform.pdf",
     "notes": "notes/doe-2019-freeform/"},
]  # fmt: skip


def pdf_bytes(text: str) -> bytes:
    out = io.BytesIO()
    c = canvas.Canvas(out)
    c.drawString(72, 720, text)
    c.showPage()
    c.save()
    return out.getvalue()


@pytest.fixture
def old_library(tmp_path, monkeypatch):
    """A library in the old format (documents known by name), with notes, words, a reading log,
    review progress, PDFs, caches and a topic note."""
    for row in OLD_ROWS:
        row.setdefault("file", f"books/{row['slug']}.pdf")
        row.setdefault("notes", f"notes/{row['slug']}/")
        pdf = tmp_path / row["file"]
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(pdf_bytes(row["title"].encode("ascii", "replace").decode()))
        notes = tmp_path / row["notes"]
        notes.mkdir(parents=True)
        (notes / "README.md").write_text(
            f"# {row['title']}\n\n| File | `{row['file']}` |\n\n## Reading progress\n\n"
            "Last read: page 4, 2026-11-01\n\n- [x] [Ch 1: Intro](ch01-intro.md)\n",
            encoding="utf-8",
        )
        (notes / "ch01-intro.md").write_text("# Chapter 1\n\nMy own words.\n", encoding="utf-8")
    vocab = tmp_path / "notes" / "unknown-2020-untitled" / "vocabulary.md"
    vocab.write_text(
        "# Vocabulary\n\n| Word | Phonetic | 中文 | Page | Added |\n|---|---|---|---|---|\n"
        "| aperture |  | 孔径 | 3 | 2026-11-01 |\n",
        encoding="utf-8",
    )
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=OLD_HEADER)
    writer.writeheader()
    writer.writerows(sorted(OLD_ROWS, key=lambda r: r["slug"]))
    (tmp_path / "catalog.csv").write_bytes(out.getvalue().encode("utf-8-sig"))
    log = {
        "2026-11-01": {"shannon-1997-art-science-optical-design": {"s": 600, "p": [1, 2]},
                       "unknown-2020-untitled": {"s": 120, "p": [3]}},
        "2026-11-02": {"doe-2019-freeform": {"s": 60, "p": [1]}},
    }  # fmt: skip
    (tmp_path / "notes" / "reading-log.json").write_text(json.dumps(log, indent=1), "utf-8")
    (tmp_path / "notes" / "vocabulary-review.json").write_text('{"aperture": {"box": 2}}', "utf-8")
    (tmp_path / "notes" / "topics").mkdir()
    (tmp_path / "notes" / "topics" / "vignetting.md").write_text("# Vignetting\n", "utf-8")
    (tmp_path / ".cache").mkdir()
    (tmp_path / ".cache" / "chapter_pages.json").write_text('{"doe-2019-freeform": {"1": 1}}')
    (tmp_path / ".cache" / "subjects_tried.json").write_text('["doe-2019-freeform"]')
    _point_modules_at(tmp_path, monkeypatch)
    return tmp_path


def _point_modules_at(library: Path, monkeypatch) -> None:
    for name in ("BOOKS", "PAPERS", "THESES", "EXAMPLES", "NOTES"):
        monkeypatch.setattr(add_book, name, library / name.lower())
    for module in (add_book, library_server, library_page, book_search):
        monkeypatch.setattr(module, "LIBRARY", library)
        monkeypatch.setattr(module, "CATALOG", library / "catalog.csv")
    monkeypatch.setattr(add_book, "ARCHIVE", library / "archive")
    monkeypatch.setattr(add_book, "PAGE_CACHE", library / ".cache" / "chapter_pages.json")
    monkeypatch.setattr(library_server, "CACHE", library / ".cache" / "chapter_pages.json")
    monkeypatch.setattr(book_search, "INDEX", library / ".cache" / "books.db")
    monkeypatch.setattr(library_jobs.library_page, "build", lambda: None)
    monkeypatch.setattr(library_jobs.book_search, "update", lambda: 0)
    monkeypatch.setattr(library_jobs, "_jobs", {})


def snapshot(library: Path) -> dict[str, str]:
    """{file: sha256} of everything in the library, except the tool's own records."""
    return {
        p.relative_to(library).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(library.rglob("*"))
        if p.is_file() and ".myLibrary" not in p.parts
    }


def old_rows(library: Path) -> dict[str, dict]:
    return {r["slug"]: r for r in catalog.read_rows(library / "catalog.csv")[1]}


# --- the identity model ----------------------------------------------------------------------


def test_every_new_document_gets_its_own_permanent_id(tmp_path):
    path = tmp_path / "catalog.csv"
    ids = [catalog.add(path, {"slug": f"doe-2015-book-{n}", "title": str(n)}) for n in range(200)]
    assert len(set(ids)) == 200 and all(catalog.is_id(i) for i in ids)
    catalog.update(path, ids[0], {"title": "New title", "slug": "doe-2015-renamed"})
    assert catalog.load(path)[ids[0]]["title"] == "New title"  # details change, the id doesn't
    with pytest.raises(ValueError):
        catalog.update(path, ids[0], {"id": catalog.new_id()})
    with pytest.raises(ValueError):
        catalog.set_field(path, ids[0], "id", catalog.new_id())
    with pytest.raises(ValueError, match="already another document"):
        catalog.add(path, {"slug": "doe-2015-book-1"})  # one name, one document
    assert catalog.by_slug(catalog.load(path), "doe-2015-renamed")["id"] == ids[0]


def test_a_catalog_with_broken_ids_is_refused_never_repaired(tmp_path):
    path = tmp_path / "catalog.csv"
    a = catalog.add(path, {"slug": "doe-2015-a"})
    catalog.add(path, {"slug": "doe-2015-b"})
    good = path.read_bytes()
    text = good.decode("utf-8-sig").splitlines()
    copied = text + [text[1].replace("doe-2015-a", "doe-2015-c")]  # a row copied in Excel
    path.write_bytes(("\r\n".join(copied) + "\r\n").encode("utf-8-sig"))
    with pytest.raises(catalog.CatalogError, match="the same id"):
        catalog.load(path)
    assert any("the same id" in p for p in catalog.check(path))
    path.write_bytes(good.decode("utf-8-sig").replace(a, "").encode("utf-8-sig"))  # cleared
    with pytest.raises(catalog.CatalogError, match="no id"):
        catalog.load(path)
    with pytest.raises(catalog.CatalogError):
        catalog.add(path, {"slug": "doe-2015-d"})  # nothing is written over a broken catalog
    assert a not in path.read_text(encoding="utf-8-sig")  # left as it was


def test_the_old_format_is_refused_until_migrated(old_library):
    with pytest.raises(catalog.NotMigrated, match="migrate_ids.py"):
        catalog.load(old_library / "catalog.csv")
    assert "migrat" in library_server.startup_problem()


def test_tombstones_answer_for_merged_and_removed_documents(tmp_path):
    path = tmp_path / "catalog.csv"
    keep = catalog.add(path, {"slug": "doe-2019-kept", "title": "Kept"})
    gone = catalog.add(path, {"slug": "doe-2019-merged", "title": "Merged"})
    old = catalog.add(path, {"slug": "doe-2019-removed", "title": "Removed"})
    for doc_id, event, into in ((gone, "merged", keep), (old, "removed", "")):
        catalog.retire(path, doc_id, event, catalog.load(path)[doc_id], into=into)
        catalog.remove(path, doc_id)
    assert catalog.resolve(path, keep) == {"status": "live", "row": catalog.load(path)[keep],
                                           "via": []}  # fmt: skip
    merged = catalog.resolve(path, gone)
    assert merged["status"] == "live" and merged["row"]["id"] == keep and merged["via"] == [gone]
    removed = catalog.resolve(path, old)
    assert removed["status"] == "removed" and removed["tombstone"]["title"] == "Removed"
    assert catalog.resolve(path, catalog.new_id())["status"] == "unknown"
    assert catalog.check(path) == []


# --- the migration ---------------------------------------------------------------------------


def test_dry_run_writes_nothing_and_shows_every_change(old_library, capsys):
    before = snapshot(old_library)
    found = migrate_ids.plan(old_library)
    migrate_ids.report(found, old_library)
    assert snapshot(old_library) == before
    assert not (old_library / ".myLibrary").exists()
    assert found["blocking"] == [] and found["rows"] == 4 and found["log_entries"] == 3
    assert sorted(found["mapping"]) == sorted(r["slug"] for r in OLD_ROWS)
    out = capsys.readouterr().out
    assert "examples: --apply makes new ids" in out and "every value is kept" in out


def test_the_migration_keeps_every_value_and_moves_every_reference(old_library):
    before = snapshot(old_library)
    rows_before = old_rows(old_library)
    log_before = json.loads((old_library / "notes" / "reading-log.json").read_text("utf-8"))
    info = migrate_ids.apply(old_library, log=lambda *a: None)
    mapping = info["mapping"]

    # The catalog: the same entries, every value the same, each with its own new id
    rows = catalog.load(old_library / "catalog.csv")
    assert len(rows) == 4 and set(rows) == set(mapping.values())
    for slug, old in rows_before.items():
        new = rows[mapping[slug]]
        assert {k: v for k, v in new.items() if k != "id" and (v or k in old)} == old
    assert entry(old_library / "catalog.csv", "unknown-2020-untitled")["title"] == "光学设计"
    # The reading log: the same records under the documents' ids
    log = reading_log.load(old_library)
    assert log == {day: {mapping[s]: e for s, e in entries.items()}
                   for day, entries in log_before.items()}  # fmt: skip
    # Nothing else changed: PDFs, notes, chapter notes, words, review progress, topic notes
    after = snapshot(old_library)
    changed = {f for f in before if before[f] != after.get(f)}
    assert changed == {"catalog.csv", "notes/reading-log.json", ".cache/chapter_pages.json",
                       ".cache/subjects_tried.json"}  # fmt: skip
    assert not (old_library / ".cache" / "chapter_pages.json").exists()  # caches: rebuilt
    # The originals are kept where Clear archive can't reach them
    folder = Path(migrate_ids.migrations_dir(old_library))
    [manifest] = folder.glob("*-uuid/manifest.json")
    assert json.loads(manifest.read_text("utf-8"))["state"] == "done"
    kept = manifest.parent / "originals" / "catalog.csv"
    assert hashlib.sha256(kept.read_bytes()).hexdigest() == before["catalog.csv"]
    library_jobs.clear_archive()
    assert kept.exists()
    # The app opens it, and a second migration does nothing
    assert library_server.startup_problem() == "" and migrate_ids.check(old_library) == []
    with pytest.raises(migrate_ids.MigrationError, match="already"):
        migrate_ids.apply(old_library)
    assert snapshot(old_library) == after


def test_after_migration_everything_works_by_id(old_library):
    mapping = migrate_ids.apply(old_library, log=lambda *a: None)["mapping"]
    path = old_library / "catalog.csv"
    shannon = mapping["shannon-1997-art-science-optical-design"]
    # Reading, the reading log, notes and progress
    reading_log.record(old_library, shannon, 60, [5])
    summary = reading_log.summary(old_library, path, date(2026, 11, 2))
    assert {b["id"] for b in summary["books"]} <= set(mapping.values())
    assert library_page.last_read(shannon)["page"] == 4
    assert library_server.tick(shannon, 1, False)[0]["done"] is False
    # Review cards point at the document's id
    [card] = vocab_review.cards(old_library, path)
    assert card["seen"][0]["id"] == mapping["unknown-2020-untitled"]
    # Search: the index is rebuilt by id
    report = INDEX_BOOKS()
    assert len(report["indexed"]) == 4 and report["complete"]
    found = book_search.search("Freeform")
    assert [r["id"] for r in found["results"]] == [mapping["doe-2019-freeform"]]
    # Page data carries the ids; the reading view is told the id too
    books = {b["id"]: b for b in library_page.books("http://x/pdfjs/web/viewer.html?file=")}
    assert set(books) == set(mapping.values())
    assert books[shannon]["pdf_uri"].endswith(f"&id={shannon}")


def test_an_interrupted_migration_is_refused_then_resumed(old_library, monkeypatch):
    before = snapshot(old_library)
    real = safe_io.write_bytes
    calls = {"n": 0}

    def crash_on_second_swap(path, data, **kw):
        if Path(path).name == "reading-log.json" and ".myLibrary" not in Path(path).parts:
            raise OSError("power cut")
        calls["n"] += 1
        return real(path, data, **kw)

    monkeypatch.setattr(safe_io, "write_bytes", crash_on_second_swap)
    with pytest.raises(OSError):
        migrate_ids.apply(old_library, log=lambda *a: None)
    monkeypatch.setattr(safe_io, "write_bytes", real)
    # Half done: the catalog is new, the reading log old. The app refuses until it's finished
    assert migrate_ids.unfinished(old_library)
    assert "didn't finish" in library_server.startup_problem()
    assert snapshot(old_library)["notes/reading-log.json"] == before["notes/reading-log.json"]
    info = migrate_ids.resume(old_library, log=lambda *a: None)
    assert info["state"] == "done" and not migrate_ids.unfinished(old_library)
    log = reading_log.load(old_library)
    assert set(log["2026-11-01"]) == {info["mapping"]["shannon-1997-art-science-optical-design"],
                                      info["mapping"]["unknown-2020-untitled"]}  # fmt: skip


def test_an_interrupted_migration_can_be_rolled_back_instead(old_library, monkeypatch):
    before = snapshot(old_library)
    real = safe_io.write_bytes

    def crash(path, data, **kw):
        if Path(path).name == "reading-log.json" and ".myLibrary" not in Path(path).parts:
            raise OSError("power cut")
        return real(path, data, **kw)

    monkeypatch.setattr(safe_io, "write_bytes", crash)
    with pytest.raises(OSError):
        migrate_ids.apply(old_library, log=lambda *a: None)
    monkeypatch.setattr(safe_io, "write_bytes", real)
    migrate_ids.rollback(old_library, log=lambda *a: None)
    after = snapshot(old_library)
    assert after["catalog.csv"] == before["catalog.csv"]
    assert after["notes/reading-log.json"] == before["notes/reading-log.json"]
    assert not migrate_ids.unfinished(old_library)


def test_a_failure_while_preparing_changes_nothing(old_library, monkeypatch):
    before = snapshot(old_library)
    real = safe_io.write_bytes

    def disk_full(path, data, **kw):
        if "new" in Path(path).parts:  # writing the staged copies
            raise OSError("disk full")
        return real(path, data, **kw)

    monkeypatch.setattr(safe_io, "write_bytes", disk_full)
    with pytest.raises(OSError):
        migrate_ids.apply(old_library, log=lambda *a: None)
    assert snapshot(old_library) == before
    assert not migrate_ids.unfinished(old_library)
    assert not list(migrate_ids.migrations_dir(old_library).glob("*"))


def test_rollback_after_migrating_restores_the_old_files(old_library):
    before = snapshot(old_library)
    migrate_ids.apply(old_library, log=lambda *a: None)
    migrate_ids.rollback(old_library, log=lambda *a: None)
    after = snapshot(old_library)
    for f in ("catalog.csv", "notes/reading-log.json"):
        assert after[f] == before[f]


def test_rollback_is_refused_when_it_would_lose_new_work(old_library):
    mapping = migrate_ids.apply(old_library, log=lambda *a: None)["mapping"]
    reading_log.record(old_library, mapping["doe-2019-freeform"], 30, [2])  # read since
    with pytest.raises(migrate_ids.MigrationError, match="would lose"):
        migrate_ids.rollback(old_library, log=lambda *a: None)
    assert catalog.load(old_library / "catalog.csv")  # still migrated, nothing changed


def test_ambiguous_data_blocks_the_migration(old_library):
    log = json.loads((old_library / "notes" / "reading-log.json").read_text("utf-8"))
    log["2026-11-03"] = {"someone-1999-gone": {"s": 30, "p": [1]}}  # whose reading?
    (old_library / "notes" / "reading-log.json").write_text(json.dumps(log), "utf-8")
    before = snapshot(old_library)
    found = migrate_ids.plan(old_library)
    assert any("someone-1999-gone" in b for b in found["blocking"])
    with pytest.raises(migrate_ids.MigrationError, match="can't migrate yet"):
        migrate_ids.apply(old_library, log=lambda *a: None)
    assert snapshot(old_library) == before


def test_verification_compares_values_not_bytes():
    old = {"catalog.csv": catalog.dumps([{"slug": "a-2000-x", "title": "X"}]).encode()}
    doc = catalog.new_id()
    good = {"catalog.csv": catalog.dumps([{"id": doc, "slug": "a-2000-x", "title": "X"}]).encode()}
    assert migrate_ids.verify(old, good, {"a-2000-x": doc}) == []
    bad = {"catalog.csv": catalog.dumps([{"id": doc, "slug": "a-2000-x", "title": "Y"}]).encode()}
    assert any("title" in p for p in migrate_ids.verify(old, bad, {"a-2000-x": doc}))


# --- merging, removing, renaming ---------------------------------------------------------------


@pytest.fixture
def library(tmp_path, monkeypatch):
    _point_modules_at(tmp_path, monkeypatch)
    return tmp_path


def registered(library, slug, text, **row) -> str:
    pdf = library / "books" / f"{slug}.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(pdf_bytes(text))
    notes = library / "notes" / slug
    notes.mkdir(parents=True, exist_ok=True)
    (notes / "README.md").write_text(f"# {text}\n\n| File | `books/{slug}.pdf` |\n", "utf-8")
    return put(library / "catalog.csv", {"slug": slug, "title": text, "type": "book",
                                         "file": f"books/{slug}.pdf"} | row)  # fmt: skip


def test_merged_copies_keep_both_reading_records_and_one_identity(library):
    day = date(2026, 11, 5)
    kept = registered(library, "doe-2019-freeform", "Freeform", doi="10.1/x", added="2026-01-01")
    dropped = registered(library, "doe-2019-freeform-2", "Freeform", doi="10.1/x",
                         added="2026-02-01")  # fmt: skip
    reading_log.record(library, kept, 120, [1, 2], day)  # both copies read the same day
    reading_log.record(library, dropped, 60, [2, 9], day)
    log_before = reading_log.load(library)

    [job] = library_jobs.check_catalog_repeats()  # Refresh: the same DOI
    assert job["status"] == "duplicate"
    path = library / "catalog.csv"
    assert set(catalog.load(path)) == {kept}
    # The records stay exactly as they were, both of them...
    assert reading_log.load(library) == log_before
    # ...and count for the document that was kept: one book, both times, one reading day
    [book] = reading_log.summary(library, path, day)["books"]
    assert (book["id"], book["seconds"], book["pages"], book["days"]) == (kept, 180, 4, 1)
    # The dropped id still resolves, to the kept document (its links keep working)
    assert catalog.resolve(path, dropped)["row"]["id"] == kept
    assert library_server.live_id(dropped) == kept


def test_a_removed_document_keeps_its_history_under_its_old_title(library):
    doc = registered(library, "doe-2015-x", "Old Optics")
    reading_log.record(library, doc, 120, [4])
    add_book.remove_book(doc, dry_run=False, yes=True)
    path = library / "catalog.csv"
    assert catalog.load(path) == {}
    [book] = reading_log.summary(library, path)["books"]
    assert (book["id"], book["title"], book["removed"], book["seconds"]) == (doc, "Old Optics",
                                                                             True, 120)  # fmt: skip
    assert library_server.live_id(doc) == ""
    assert "was removed from the library" in library_server.unknown_document(doc)


def test_renaming_moves_everything_and_keeps_the_identity(library):
    doc = registered(library, "doe-2015-x", "Practical Optics")
    reading_log.record(library, doc, 60, [1])
    (library / "examples" / "doe-2015-x").mkdir(parents=True)
    (library / "examples" / "doe-2015-x" / "ch01_check.py").write_text("print(1)\n")
    marks = library / "archive" / "before-marks" / "books" / "doe-2015-x.pdf"
    marks.parent.mkdir(parents=True)
    marks.write_bytes(b"%PDF original")
    pdf_before = (library / "books" / "doe-2015-x.pdf").read_bytes()

    row = add_book.rename_document(doc, "doe-2015-practical-optics")
    assert row["id"] == doc and row["slug"] == "doe-2015-practical-optics"
    assert row["file"] == "books/doe-2015-practical-optics.pdf"
    assert row["notes"] == "notes/doe-2015-practical-optics/"
    assert (library / row["file"]).read_bytes() == pdf_before
    readme = (library / row["notes"] / "README.md").read_text("utf-8")
    assert "`books/doe-2015-practical-optics.pdf`" in readme
    assert (library / "examples" / "doe-2015-practical-optics" / "ch01_check.py").exists()
    assert (library / "archive" / "before-marks" / row["file"]).read_bytes() == b"%PDF original"
    assert not any((library / p).exists() for p in ("books/doe-2015-x.pdf", "notes/doe-2015-x"))
    # Everything that refers to it still does: the reading log, its page data
    assert doc in reading_log.load(library)[date.today().isoformat()]
    assert library_page.readme_path(doc) == library / row["notes"] / "README.md"
    assert not list(add_book.operations_dir().glob("*"))  # no journal left
    with pytest.raises(ValueError, match="already taken"):
        add_book.rename_document(registered(library, "roe-2020-y", "Y"),
                                 "doe-2015-practical-optics")  # fmt: skip


def test_a_failed_rename_puts_everything_back(library, monkeypatch):
    doc = registered(library, "doe-2015-x", "Practical Optics")
    before = snapshot(library)

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(catalog, "set_fields", fail)  # the last step fails
    with pytest.raises(OSError):
        add_book.rename_document(doc, "doe-2015-practical-optics")
    assert snapshot(library) == before
    assert entry(library / "catalog.csv", "doe-2015-x")["id"] == doc
    assert not list(add_book.operations_dir().glob("*"))


def test_an_interrupted_rename_is_put_back_at_the_next_start(library):
    doc = registered(library, "doe-2015-x", "Practical Optics")
    before = snapshot(library)
    # As if the power went off halfway: the journal written, the PDF already moved
    old_pdf, new_pdf = library / "books" / "doe-2015-x.pdf", library / "books" / "doe-2015-y.pdf"
    journal = add_book.operations_dir() / f"rename-{doc}.json"
    safe_io.write_json(journal, {
        "op": "rename", "id": doc,
        "from": {"slug": "doe-2015-x", "file": "books/doe-2015-x.pdf",
                 "notes": "notes/doe-2015-x/"},
        "to": {"slug": "doe-2015-y", "file": "books/doe-2015-y.pdf",
               "notes": "notes/doe-2015-y/"},
        "moves": [[str(old_pdf), str(new_pdf)],
                  [str(library / "notes" / "doe-2015-x"), str(library / "notes" / "doe-2015-y")]],
        "readme": {"path": str(library / "notes" / "doe-2015-y" / "README.md"), "text": None},
    })  # fmt: skip
    old_pdf.rename(new_pdf)
    done = add_book.recover_operations()
    assert done and "put back" in done[0]
    assert snapshot(library) == before
    assert not journal.exists()


def test_a_lasting_link_opens_the_document_whatever_its_name(library):
    doc = registered(library, "doe-2015-x", "Practical Optics")
    add_book.rename_document(doc, "doe-2015-practical-optics")
    removed = registered(library, "roe-2020-y", "Gone")
    add_book.remove_book(removed, dry_run=False, yes=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kw):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        with pytest.raises(urllib.error.HTTPError) as moved:
            opener.open(f"{base}/read/{doc}?page=3", timeout=5)
        assert moved.value.code == 302
        where = moved.value.headers["Location"]
        assert "doe-2015-practical-optics.pdf" in where and f"id={doc}" in where
        assert where.endswith("#page=3")
        assert "find=" not in where  # nothing to highlight unless a search asks
        # A search result: the searched text goes along, to be highlighted (on screen only)
        with pytest.raises(urllib.error.HTTPError) as found:
            opener.open(f"{base}/read/{doc}?page=7&find=entrance%20%20pupil", timeout=5)
        assert found.value.headers["Location"].endswith(f"&id={doc}&find=entrance%20pupil#page=7")
        # Characters that would break the address stay inside the find text
        with pytest.raises(urllib.error.HTTPError) as odd:
            opener.open(f"{base}/read/{doc}?page=2&find=a%26page%3D9%23x%22", timeout=5)
        assert odd.value.headers["Location"].endswith("&find=a%26page%3D9%23x%22#page=2")
        # A search result opens as a preview (a look-up: no reading progress recorded)
        with pytest.raises(urllib.error.HTTPError) as look:
            opener.open(f"{base}/read/{doc}?page=7&find=pupil&preview=1", timeout=5)
        assert look.value.headers["Location"].endswith("&find=pupil&preview=1#page=7")
        assert "preview" not in where  # Read / Continue and other links: normal reading
        with pytest.raises(urllib.error.HTTPError) as gone:
            opener.open(f"{base}/read/{removed}", timeout=5)
        assert gone.value.code == 410
        with pytest.raises(urllib.error.HTTPError) as unknown:
            opener.open(f"{base}/read/{catalog.new_id()}", timeout=5)
        assert unknown.value.code == 404
    finally:
        server.shutdown()


def test_concurrent_imports_get_distinct_ids(library, monkeypatch):
    from book_meta import Meta

    metas = {f"c{n}": Meta(title=f"光学{n}", author="王五", year="2021") for n in range(10)}
    monkeypatch.setattr(library_jobs, "identify", lambda path, online, **kw: metas[path.stem])
    uploads = [library_jobs.save_upload(f"{k}.pdf", pdf_bytes(k)) for k in metas]
    jobs = [library_jobs.start_add(p) for p in uploads]
    for job in jobs:
        for _ in range(400):
            current = next(j for j in library_jobs.list_jobs() if j["id"] == job["id"])
            if current["status"] != "working":
                break
            threading.Event().wait(0.02)
    rows = catalog.load(library / "catalog.csv")
    assert len(rows) == 10 and catalog.check(library / "catalog.csv") == []
    assert {r["title"] for r in rows.values()} == {m.title for m in metas.values()}
    assert len({j["doc_id"] for j in library_jobs.list_jobs()}) == 10
    assert id_of(library / "catalog.csv", rows[next(iter(rows))]["slug"]) in rows
