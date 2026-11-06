"""Data safety: concurrent writers, interrupted writes, damaged files, stopping mid-job.

Everything here uses temporary folders and invented data, never the real library.
"""

import io
import json
import os
import threading
import time
import tomllib

import add_book
import catalog
import library_jobs
import paths
import pytest
import reading_log
import safe_io
import vocab_review
from book_meta import Meta
from reportlab.pdfgen import canvas


def numbered_pdf(n: int) -> bytes:
    """A small text PDF whose bytes differ for every n (identical files count as repeats)."""
    out = io.BytesIO()
    c = canvas.Canvas(out)
    for line in range(10):
        c.drawString(72, 720 - 20 * line, f"Invented study text number {n}, line {line}.")
    c.showPage()
    c.save()
    return out.getvalue()


@pytest.fixture
def library(tmp_path, monkeypatch):
    """An empty temporary library; no network, no page building, no search index."""
    for name in ("BOOKS", "PAPERS", "THESES", "EXAMPLES", "NOTES"):
        monkeypatch.setattr(add_book, name, tmp_path / name.lower())
    monkeypatch.setattr(add_book, "CATALOG", tmp_path / "catalog.csv")
    monkeypatch.setattr(add_book, "ARCHIVE", tmp_path / "archive")
    monkeypatch.setattr(add_book, "LIBRARY", tmp_path)
    monkeypatch.setattr(add_book, "PAGE_CACHE", tmp_path / ".cache" / "chapter_pages.json")
    monkeypatch.setattr(library_jobs.library_page, "build", lambda: None)
    monkeypatch.setattr(library_jobs.book_search, "update", lambda: 0)
    monkeypatch.setattr(library_jobs, "_jobs", {})
    return tmp_path


def wait_all(jobs: list[dict], seconds: float = 60) -> list[dict]:
    ids = {j["id"] for j in jobs}
    end = time.time() + seconds
    while time.time() < end:
        current = [j for j in library_jobs.list_jobs() if j["id"] in ids]
        if all(j["status"] != "working" for j in current):
            return current
        time.sleep(0.05)
    raise AssertionError("jobs didn't finish")


def row(slug: str, **fields) -> dict:
    return {"slug": slug, "title": fields.pop("title", slug), "file": f"books/{slug}.pdf"} | fields


# --- atomic writes -----------------------------------------------------------------------------


def test_an_interrupted_write_leaves_the_old_file_whole(tmp_path, monkeypatch):
    path = tmp_path / "notes.md"
    path.write_text("my own notes\n", encoding="utf-8")

    def crash(*args):  # the disk fills up or the process is killed before the swap
        raise OSError("disk full")

    monkeypatch.setattr(safe_io.os, "replace", crash)
    with pytest.raises(OSError):
        safe_io.write_text(path, "half a new versi")
    assert path.read_text(encoding="utf-8") == "my own notes\n"
    assert [p.name for p in tmp_path.iterdir()] == ["notes.md"]  # no temporary file left


def test_an_interrupted_catalog_write_keeps_every_row(tmp_path, monkeypatch):
    path = tmp_path / "catalog.csv"
    for n in range(5):
        catalog.upsert(path, row(f"doe-2015-book-{n}"))
    before = path.read_bytes()

    def crash(*args):
        raise OSError("killed")

    monkeypatch.setattr(safe_io.os, "replace", crash)
    with pytest.raises(OSError):
        catalog.upsert(path, row("doe-2015-book-new"))
    assert path.read_bytes() == before
    assert len(catalog.load(path)) == 5


def test_writes_keep_line_endings_and_encoding(tmp_path):
    """Same bytes as Path.write_text gave before: notes stay as the user's editor saw them."""
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_text("Linse (lens)\n光阑 (aperture stop)\n", encoding="utf-8")
    safe_io.write_text(b, "Linse (lens)\n光阑 (aperture stop)\n")
    assert a.read_bytes() == b.read_bytes()


# --- concurrent writers --------------------------------------------------------------------------


def test_concurrent_catalog_updates_keep_every_row(tmp_path):
    path = tmp_path / "catalog.csv"
    errors = []

    def add(n: int) -> None:
        try:
            catalog.upsert(path, row(f"doe-2015-book-{n}"))
            catalog.load(path)  # readers at the same time never see half a file
        except Exception as e:  # pragma: no cover - the failure being tested for
            errors.append(e)

    threads = [threading.Thread(target=add, args=(n,)) for n in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len(catalog.load(path)) == 40


def test_forty_concurrent_imports_keep_forty_catalog_entries(library, monkeypatch):
    """Dropping 40 PDFs on the page at once: every one is identified (in parallel) and
    registered, none is lost."""

    def identify(path, online, **kw):
        time.sleep(0.05)  # a lookup takes a moment, so the jobs really overlap
        n = int(path.stem.split("-")[1])
        return Meta(title=f"Lens Study {n}", author="Jane Doe", year="2015")

    monkeypatch.setattr(library_jobs, "identify", identify)
    uploads = [library_jobs.save_upload(f"doc-{n}.pdf", numbered_pdf(n)) for n in range(40)]
    jobs = [library_jobs.start_add(p) for p in uploads]
    done = wait_all(jobs)

    assert [j["message"] for j in done if j["status"] != "done"] == []
    rows = catalog.load(library / "catalog.csv")
    assert len(rows) == 40
    assert sorted(rows) == sorted(f"doe-2015-lens-study-{n}" for n in range(40))
    assert len(list((library / "books").glob("*.pdf"))) == 40
    assert all((library / "notes" / slug / "README.md").exists() for slug in rows)


def test_the_same_file_uploaded_twice_at_once_is_added_once(library, monkeypatch):
    meta = Meta(title="Practical Lens Design", author="Jane Doe", year="2015")
    monkeypatch.setattr(library_jobs, "identify", lambda path, online, **kw: meta)
    data = numbered_pdf(1)
    uploads = [library_jobs.save_upload("same.pdf", data) for _ in range(4)]
    assert len(set(uploads)) == 4  # four uploads, four files: none overwrote another
    done = wait_all([library_jobs.start_add(p) for p in uploads])
    assert sorted(j["status"] for j in done) == ["done", "duplicate", "duplicate", "duplicate"]
    assert list(catalog.load(library / "catalog.csv")) == ["doe-2015-practical-lens-design"]


def test_concurrent_reading_reports_are_all_counted(tmp_path):
    def report(n: int) -> None:
        reading_log.record(tmp_path, f"book-{n % 4}", 10, [n + 1])

    threads = [threading.Thread(target=report, args=(n,)) for n in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    log = reading_log.load(tmp_path)
    (day,) = log
    assert sum(entry["s"] for entry in log[day].values()) == 400
    assert sum(len(entry["p"]) for entry in log[day].values()) == 40


def test_concurrent_saves_of_one_upload_name_get_their_own_files(library):
    found = []
    pdfs = [numbered_pdf(n) for n in range(10)]  # made once: each carries its creation time
    threads = [
        threading.Thread(target=lambda d=d: found.append(library_jobs.save_upload("a.pdf", d)))
        for d in pdfs
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(found)) == 10  # ten names, and every upload is whole in its own file
    assert sorted(p.read_bytes() for p in found) == sorted(pdfs)


def test_an_entry_without_a_file_never_moves_the_library(library, monkeypatch):
    """A catalog row with an empty `file` (as a repeat arriving mid-filing used to leave) once
    made the next repeat take the library folder for the book's PDF and move it to archive/."""
    meta = Meta(title="Practical Lens Design", author="Jane Doe", year="2015")
    catalog.upsert(library / "catalog.csv", {"slug": "doe-2015-practical-lens-design"})
    upload = library_jobs.save_upload("copy.pdf", numbered_pdf(1))
    assert add_book.richer_than_library(upload, meta, "doe-2015-practical-lens-design") == ""
    with pytest.raises(ValueError, match="no PDF file"):
        add_book.replace_pdf("doe-2015-practical-lens-design", upload, meta)
    with pytest.raises(ValueError, match="isn't a library item"):
        add_book.move_to_archive(library)
    assert (library / "catalog.csv").exists() and upload.exists()
    assert add_book.fill_details("doe-2015-unknown", meta) == []  # creates no entry
    assert "doe-2015-unknown" not in catalog.load(library / "catalog.csv")


# --- damaged files -------------------------------------------------------------------------------


def damage(path, text='{"2026-11-01": {"a-book": {"s": 6'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path.read_bytes()


def test_a_damaged_reading_log_is_never_replaced_with_an_empty_one(tmp_path):
    path = reading_log.log_path(tmp_path)
    before = damage(path)
    with pytest.raises(safe_io.DamagedFile) as error:
        reading_log.record(tmp_path, "a-book", 60, [3])
    assert path.read_bytes() == before  # left exactly as it was
    assert "reading-log.json" in str(error.value)
    copies = list(path.parent.glob("reading-log.json.damaged-*"))
    assert len(copies) == 1 and copies[0].read_bytes() == before
    with pytest.raises(safe_io.DamagedFile):  # the page says so too, instead of "no reading"
        reading_log.summary(tmp_path, tmp_path / "catalog.csv")
    with pytest.raises(safe_io.DamagedFile):  # asking again doesn't pile up copies
        reading_log.record(tmp_path, "a-book", 60, [3])
    assert len(list(path.parent.glob("reading-log.json.damaged-*"))) == 1


def test_a_damaged_reading_log_comes_back_from_its_previous_version(tmp_path):
    reading_log.record(tmp_path, "a-book", 60, [1])
    reading_log.record(tmp_path, "a-book", 60, [2])  # the first state is now the .bak
    path = reading_log.log_path(tmp_path)
    damaged = damage(path)
    reading_log.record(tmp_path, "a-book", 30, [3])
    (day,) = reading_log.load(tmp_path)
    entry = reading_log.load(tmp_path)[day]["a-book"]
    assert entry["s"] == 90 and entry["p"] == [1, 3]  # at most the last report was lost
    (copy,) = path.parent.glob("reading-log.json.damaged-*")
    assert copy.read_bytes() == damaged  # and the damaged file is kept for recovery


def test_damaged_review_progress_is_kept_for_recovery(tmp_path):
    path = vocab_review.state_path(tmp_path)
    before = damage(path, '{"aperture": {"box": 3, "due": "2026-')
    with pytest.raises(safe_io.DamagedFile):
        vocab_review.answer(tmp_path, "aperture", knew=True)
    assert path.read_bytes() == before
    (copy,) = path.parent.glob(f"{path.name}.damaged-*")
    assert copy.read_bytes() == before
    with pytest.raises(safe_io.DamagedFile):
        vocab_review.summary(tmp_path, tmp_path / "catalog.csv")


def test_a_damaged_cache_is_simply_rebuilt(tmp_path):
    cache = tmp_path / ".cache" / "chapter_pages.json"
    damage(cache, '{"doe-2015-book": {"1": ')
    assert safe_io.load_json(cache, {}, cache=True) == {}
    safe_io.update_json(cache, lambda c: c.update(x=1), {}, cache=True)
    assert json.loads(cache.read_text(encoding="utf-8")) == {"x": 1}


def test_columns_added_by_hand_survive_every_change(tmp_path):
    path = tmp_path / "catalog.csv"
    catalog.upsert(path, row("doe-2015-book-a"))
    catalog.upsert(path, row("doe-2015-book-b"))
    text = path.read_text(encoding="utf-8-sig").splitlines()
    text = [text[0] + ",my rating"] + [line + ",5" for line in text[1:]]
    path.write_text("\n".join(text) + "\n", encoding="utf-8-sig")

    catalog.upsert(path, row("doe-2015-book-a", year="2016"))
    catalog.set_field(path, "doe-2015-book-b", "shelves", "Optics")
    catalog.upsert(path, row("doe-2015-book-c"))
    catalog.remove(path, "doe-2015-book-c")
    rows = catalog.load(path)
    assert rows["doe-2015-book-a"]["my rating"] == "5" and rows["doe-2015-book-a"]["year"] == "2016"
    assert rows["doe-2015-book-b"]["my rating"] == "5"


def test_settings_with_any_characters_stay_readable(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "SETTINGS_FILE", tmp_path / "local.toml")
    odd = 'C:\\Users\\me\\it\'s\t"here"\r\n\x01end'
    paths.save_settings({"backup_folder": odd, "editor_command": 'code "{file}"'})
    with open(tmp_path / "local.toml", "rb") as f:
        saved = tomllib.load(f)
    assert saved["backup_folder"] == odd and saved["editor_command"] == 'code "{file}"'


# --- stopping ------------------------------------------------------------------------------------


def test_quitting_waits_for_a_book_being_filed(library, monkeypatch):
    """Quit while a job is moving a PDF into place and writing its notes and catalog row: the
    job finishes first, so nothing is left half done."""
    real_setup = add_book.setup_book
    started = threading.Event()

    def slow_setup(*args, **kw):
        started.set()
        time.sleep(0.5)
        return real_setup(*args, **kw)

    meta = Meta(title="Practical Lens Design", author="Jane Doe", year="2015")
    monkeypatch.setattr(library_jobs, "identify", lambda path, online, **kw: meta)
    monkeypatch.setattr(add_book, "setup_book", slow_setup)
    job = library_jobs.start_add(library_jobs.save_upload("a.pdf", numbered_pdf(1)))
    assert started.wait(5)
    result = library_jobs.shutdown(timeout=10)

    assert result["unfinished"] == []
    (current,) = [j for j in library_jobs.list_jobs() if j["id"] == job["id"]]
    assert current["status"] == "done"
    assert "doe-2015-practical-lens-design" in catalog.load(library / "catalog.csv")
    assert (library / "notes" / "doe-2015-practical-lens-design" / "README.md").exists()
    with pytest.raises(ValueError, match="stopping"):  # nothing new starts once quitting
        library_jobs.start_add(library_jobs.save_upload("b.pdf", numbered_pdf(2)))
    with pytest.raises(safe_io.ShuttingDown):
        safe_io.write_text(library / "late.md", "too late")


def test_quitting_stops_ocr_between_pages_and_leaves_the_pdf_alone(library, monkeypatch):
    pdf = library / "books" / "doe-2015-scan.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(numbered_pdf(1))
    catalog.upsert(library / "catalog.csv", row("doe-2015-scan"))
    before = pdf.read_bytes()

    def slow_ocr(path, progress=None):
        for page in range(1, 200):
            time.sleep(0.02)
            progress(page, 200)
        raise AssertionError("OCR should have been stopped")

    monkeypatch.setattr(library_jobs.ocr_pdf, "make_searchable", slow_ocr)
    job = library_jobs.start_ocr("doe-2015-scan")
    time.sleep(0.1)
    result = library_jobs.shutdown(timeout=10)
    assert result["unfinished"] == []
    (current,) = [j for j in library_jobs.list_jobs() if j["id"] == job["id"]]
    assert current["status"] == "error" and "quit" in current["message"]
    assert pdf.read_bytes() == before


def test_shutdown_waits_for_a_file_operation_in_progress(tmp_path):
    inside, release = threading.Event(), threading.Event()

    def long_operation():
        with safe_io.critical():
            inside.set()
            release.wait(5)
            safe_io.write_text(tmp_path / "x.md", "finished")  # nested: still allowed

    worker = threading.Thread(target=long_operation)
    worker.start()
    assert inside.wait(5)
    threading.Timer(0.3, release.set).start()
    assert safe_io.close(timeout=10) is True
    assert (tmp_path / "x.md").read_text(encoding="utf-8") == "finished"
    worker.join()


def test_no_temporary_files_are_left_behind(tmp_path):
    for n in range(20):
        safe_io.write_text(tmp_path / "a.md", f"version {n}")
        safe_io.update_json(tmp_path / "b.json", lambda d, n=n: d.update(n=n), {}, backup=True)
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["a.md", "b.json", "b.json.bak"]
    assert not any(n.endswith(".tmp") for n in os.listdir(tmp_path))
