"""RS1: a document's reading status, chosen by the user, kept as one line in its notes README
("Reading status: to read / reading / finished (date)"); no line is "automatic". Every other
line of the README, its line endings and byte-order mark are kept; a line myLibrary doesn't
understand (or more than one) is never written over. Saved with the README's lock and the
same server-controlled versions as ticks (B32). Temporary libraries only."""

import json
import threading
import urllib.error
import urllib.request
import zipfile
from datetime import date
from http.server import ThreadingHTTPServer

import folder_backup
import library_page
import library_server
import pytest
from test_library_server import NAME, README, doc
from testlib import put


@pytest.fixture
def library(tmp_path, monkeypatch):
    """A one-book library in a temporary folder (as in test_library_server)."""
    for module in (library_server, library_page):
        monkeypatch.setattr(module, "LIBRARY", tmp_path)
        monkeypatch.setattr(module, "CATALOG", tmp_path / "catalog.csv")
    notes = tmp_path / "notes" / NAME
    notes.mkdir(parents=True)
    (notes / "README.md").write_text(README, encoding="utf-8")
    row = {"slug": NAME, "title": "Practical Lens Design", "file": f"books/{NAME}.pdf"}
    put(tmp_path / "catalog.csv", row | {"notes": f"notes/{NAME}/"})
    return tmp_path


PLAIN = (
    "# Practical Lens Design\n\nSome details.\n\n## Reading progress\n\n"
    "Last read: page 12 (Ch 2: Aberrations), 2026-11-01\n\n"
    "- [x] [Ch 1: Basics](ch01-basics.md)\n- [ ] [Ch 2: Aberrations](ch02-aberrations.md)\n\n"
    "## Notes\n\nStatus: my own words, not a reading status.\n"
)
NO_LAST_READ = "# T\n\n## Reading progress\n\n- [ ] [Ch 1: Basics](ch01-basics.md)\n"
NO_SECTION = "# T\n\nJust details."


@pytest.fixture
def versions(monkeypatch):
    monkeypatch.setattr(library_server, "_tick_versions", {})
    return library_server


def readme_of(library) -> Path:  # noqa: F821
    return library_page.readme_path(doc(library))


# --- the line ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (None, {"stored": "auto", "date": "", "problem": ""}),
        ("Reading status: to read", {"stored": "to-read", "date": "", "problem": ""}),
        ("Reading status: reading", {"stored": "reading", "date": "", "problem": ""}),
        ("Reading status: finished (2026-11-11)",
         {"stored": "finished", "date": "2026-11-11", "problem": ""}),
        ("Reading status: Finished", {"stored": "finished", "date": "", "problem": ""}),
        ("Reading status:   reading  ", {"stored": "reading", "date": "", "problem": ""}),
    ],
)  # fmt: skip
def test_a_status_line_is_read(line, expected):
    text = PLAIN if line is None else PLAIN.replace("## Notes", f"{line}\n\n## Notes")
    assert library_page.reading_status(text) == expected
    assert library_page.reading_status(text.replace("\n", "\r\n")) == expected  # CRLF too


@pytest.mark.parametrize(
    "line",
    ["Reading status: done", "Reading status: finished (2026-13-45)", "Reading status: ",
     "Reading status: reading (2026-11-11)", "Reading status: to read later"],
)  # fmt: skip
def test_a_line_it_doesnt_understand_is_invalid(line):
    found = library_page.reading_status(PLAIN + line + "\n")
    assert found["stored"] == "invalid" and "isn't one myLibrary understands" in found["problem"]


def test_two_lines_are_invalid():
    text = PLAIN + "Reading status: reading\nReading status: finished (2026-11-11)\n"
    found = library_page.reading_status(text)
    assert found["stored"] == "invalid" and "2 “Reading status:” lines" in found["problem"]


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
@pytest.mark.parametrize("text", [PLAIN, NO_LAST_READ, NO_SECTION, NO_SECTION + "\n"])
def test_set_replace_and_remove_keep_everything_else(text, newline):
    original = text.replace("\n", newline)
    added = library_page.with_status(original, "Reading status: reading")
    assert library_page.reading_status(added)["stored"] == "reading"
    assert ("\r\n" in added) == (newline == "\r\n") and ("\n" in added.replace("\r\n", ""))\
        is (newline == "\n" and "\n" in original)  # fmt: skip
    if "Last read:" in original:  # right after it
        assert f"2026-11-01{newline}Reading status: reading{newline}" in added
    elif "## Reading progress" in original:  # first under the heading
        assert f"## Reading progress{newline}{newline}Reading status: reading{newline}" in added
    else:
        assert added.endswith(f"Reading status: reading{newline}")
    replaced = library_page.with_status(added, "Reading status: finished (2026-11-11)")
    assert replaced == added.replace("reading" + newline, "finished (2026-11-11)" + newline, 1) \
        or replaced.endswith("finished (2026-11-11)" + newline)  # fmt: skip
    assert library_page.reading_status(replaced)["date"] == "2026-11-11"
    removed = library_page.with_status(replaced, None)
    expected = original if original.endswith("\n") or not original else original + newline
    assert removed == expected  # exactly as before (an end without a line break gains one)
    assert library_page.with_status(original, None) == original  # nothing to remove


def test_a_heading_without_a_blank_line_after_it():
    text = "# T\n## Reading progress\n- [ ] [Ch 1: Basics](ch01-basics.md)\n"
    added = library_page.with_status(text, "Reading status: to read")
    assert (
        added == "# T\n## Reading progress\nReading status: to read\n"
        "- [ ] [Ch 1: Basics](ch01-basics.md)\n"
    )
    assert library_page.with_status(added, None) == text


# --- setting it -----------------------------------------------------------------------------


def test_each_choice_is_saved_in_the_readme(library, versions):
    readme = readme_of(library)
    readme.write_bytes(PLAIN.replace("\n", "\r\n").encode("utf-8-sig"))  # CRLF and a BOM
    before = readme.read_bytes()
    today = date.today().isoformat()
    choices = (
        ("to-read", "Reading status: to read"),
        ("reading", "Reading status: reading"),
        ("finished", f"Reading status: finished ({today})"),
    )
    for choice, line in choices:
        status, chapters, _ = versions.set_status(doc(library), choice)
        assert status["stored"] == choice and chapters[0]["done"] is True
        data = readme.read_bytes()
        assert data.startswith(b"\xef\xbb\xbf") and line.encode() + b"\r\n" in data
        assert data.replace(line.encode() + b"\r\n", b"") == before  # nothing else changed
    status, _, _ = versions.set_status(doc(library), "auto")
    assert status["stored"] == "auto" and readme.read_bytes() == before  # exactly as it was


def test_already_so_writes_nothing_and_finished_keeps_its_date(library, versions):
    readme = readme_of(library)
    marked = PLAIN.replace("## Notes", "Reading status: finished (2026-01-02)\n\n## Notes")
    readme.write_text(marked,
                      encoding="utf-8", newline="\n")  # fmt: skip
    before, seen = readme.read_bytes(), versions.tick_version(doc(library))
    status, _, version = versions.set_status(doc(library), "finished", base=seen)
    assert status == {"stored": "finished", "date": "2026-01-02", "problem": ""}
    assert readme.read_bytes() == before and version == seen  # no write, the version stays


UNREADABLE = ["Reading status: someday", "Reading status: reading\nReading status: to read"]


@pytest.mark.parametrize("line", UNREADABLE)
def test_a_line_it_doesnt_understand_is_never_written_over(library, versions, line):
    readme = readme_of(library)
    readme.write_text(PLAIN + line + "\n", encoding="utf-8", newline="\n")
    before = readme.read_bytes()
    for choice in ("auto", "finished", "reading"):
        with pytest.raises(ValueError, match="correct it in the README"):
            versions.set_status(doc(library), choice)
    assert readme.read_bytes() == before


def test_a_newer_status_from_another_tab_is_never_overwritten(library, versions):
    seen = versions.tick_version(doc(library))  # both tabs opened here
    _, _, v1 = versions.set_status(doc(library), "finished", base=seen)  # tab B
    with pytest.raises(versions.TickChanged) as refused:  # tab A, on its older view
        versions.set_status(doc(library), "to-read", base=seen)
    assert refused.value.status["stored"] == "finished" and refused.value.version == v1
    # A tick in between doesn't conflict with a status, nor a status with a tick
    _, v2 = versions.tick_with_version(doc(library), 2, True, base=v1)
    status, _, _ = versions.set_status(doc(library), "reading", base=v1)
    assert status["stored"] == "reading"
    assert versions.tick_with_version(doc(library), 1, True, base=v2)[0][0]["done"]


def test_reaching_the_end_never_finishes_it(library, versions):
    versions.tick_with_version(doc(library), 1, True)
    versions.tick_with_version(doc(library), 2, True)  # every chapter ticked: 100%
    assert library_page.status_of(readme_of(library))["stored"] == "auto"  # still automatic


def test_a_status_survives_a_restart_and_a_backup(library, versions, tmp_path_factory, monkeypatch):
    versions.set_status(doc(library), "finished")
    monkeypatch.setattr(versions, "_tick_versions", {})  # a new server run
    [book] = library_page.books()
    assert book["reading_status"]["stored"] == "finished"
    dest = tmp_path_factory.mktemp("backups")  # (outside the library: tmp_path is it)
    result = folder_backup.back_up(dest, pdfs=False, library=library)
    with zipfile.ZipFile(dest / result["file"]) as z:
        name = next(n for n in z.namelist() if n.endswith(f"{NAME}/README.md"))
        restored = z.read(name)
    assert restored == readme_of(library).read_bytes()  # restored as it was, line and all
    assert library_page.reading_status(restored.decode("utf-8"))["stored"] == "finished"


def test_the_static_page_carries_the_status(library, versions):
    versions.set_status(doc(library), "reading")
    page = library_page.render(None)
    data = json.loads(page.split('<script type="application/json" id="data">')[1]
                      .split("</script>")[0].replace("<\\/", "</"))  # fmt: skip
    assert data[0]["reading_status"]["stored"] == "reading"
    assert 'id="statusFilter"' in page


# --- over HTTP -----------------------------------------------------------------------------


def test_the_status_over_http(library, versions):
    server = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    def post(body):
        request = urllib.request.Request(
            base_url + "/api/status", data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json", "X-Library-Token": library_server.TOKEN},
        )  # fmt: skip
        return json.load(urllib.request.urlopen(request, timeout=5))

    try:
        seen = library_server.tick_version(doc(library))
        answer = post({"id": doc(library), "status": "finished", "base": seen})
        assert answer["reading_status"]["stored"] == "finished" and answer["version"] == seen + 1
        assert answer["chapter_list"][0]["number"] == 1
        again = post({"id": doc(library), "status": "finished", "base": seen})  # a retry
        assert again["version"] == seen + 1  # already so: nothing written
        with pytest.raises(urllib.error.HTTPError) as stale:
            post({"id": doc(library), "status": "to-read", "base": seen})
        assert stale.value.code == 409
        assert json.load(stale.value)["reading_status"]["stored"] == "finished"
        bad_bodies = (
            {"status": "done"},
            {"status": None},
            {"status": "reading", "base": None},
            {"status": "reading", "base": seen + 99},
            {"status": "reading", "base": "1"},
        )
        for bad in bad_bodies:
            with pytest.raises(urllib.error.HTTPError) as wrong:
                post({"id": doc(library)} | bad)
            assert wrong.value.code == 400, bad
        assert library_page.status_of(readme_of(library))["stored"] == "finished"
    finally:
        server.shutdown()
