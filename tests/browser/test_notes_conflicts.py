"""A note changed elsewhere while it's open (task 4 M4): VS Code (here: the file written by the
test), another tab. With nothing unsaved it's simply reloaded; with unsaved text it's a
conflict: autosave stops, both texts are kept, and the user chooses Keep mine (the disk version
archived first), Use the disk version (theirs archived first) or Compare. Never silent."""

import re
import time

from helpers import (
    EDITOR,
    drafts_in_browser,
    editor_text,
    notes_settled,
    open_document,
    poll,
    type_at_end,
    wait_save_state,
)
from playwright.sync_api import expect
from test_notes_content import book_with_notes

ELSEWHERE = b"# Chapter 1\r\n\r\nwritten in VS Code\r\n"
AGAIN = b"# Chapter 1\r\n\r\nwritten in VS Code, twice\r\n"


def chapter_one(library, doc):
    return library.root / library.row(doc)["notes"] / "ch01-basics.md"


def archived(library):
    """{name: bytes} of everything in archive/notes-conflicts/."""
    folder = library.root / "archive" / "notes-conflicts"
    return (
        {p.name: p.read_bytes() for p in folder.rglob("*") if p.is_file()}
        if folder.exists()
        else {}
    )


def open_book(library, server_factory, page, clock=False):
    doc = book_with_notes(library)
    server = server_factory()
    if clock:
        page.clock.install()
    open_document(page, server, doc, page_no=2)
    notes_settled(page)
    if clock:
        page.clock.pause_at(int(time.time() * 1000) + 2_000)
    return doc, server


def into_conflict(page, library, doc, mine="my own words"):
    """The file changes elsewhere, then the user types and saves: a conflict."""
    chapter_one(library, doc).write_bytes(ELSEWHERE)
    type_at_end(page, mine)
    page.keyboard.press("Control+s")
    wait_save_state(page, "conflict")


def test_a_note_changed_elsewhere_with_nothing_unsaved_is_reloaded(
    library, server_factory, reader_page
):
    doc, _ = open_book(library, server_factory, reader_page, clock=True)
    chapter_one(library, doc).write_bytes(ELSEWHERE)
    reader_page.clock.run_for(5_000)  # the 5 s check (decision D6)
    reader_page.wait_for_function(
        "t => document.getElementById('mlNoteText').value === t",
        arg="# Chapter 1\n\nwritten in VS Code\n",
    )
    assert reader_page.evaluate("() => document.body.dataset.mlSaveState") == "clean"
    expect(reader_page.locator("#mlNotesStatus")).to_contain_text("Updated from disk")
    assert chapter_one(library, doc).read_bytes() == ELSEWHERE  # nothing written back


def test_keep_mine_archives_the_other_version_first(library, server_factory, reader_page):
    doc, _ = open_book(library, server_factory, reader_page)
    sent = []
    reader_page.on(
        "request", lambda r: sent.append(1) if r.url.endswith("/api/notes/save") else None
    )
    into_conflict(reader_page, library, doc)
    expect(reader_page.locator("#mlNoteBar")).to_contain_text("changed elsewhere")
    saves = len(sent)
    reader_page.keyboard.type(" and more")  # autosave is paused during a conflict
    poll(reader_page, lambda: any(t.endswith("and more")
                                  for t in drafts_in_browser(reader_page).values()),
         message="the draft didn't follow the typing")  # fmt: skip
    assert len(sent) == saves and reader_page.evaluate(
        "() => document.body.dataset.mlSaveState") == "conflict"  # fmt: skip
    reader_page.locator("#mlCompare").click()  # both, without changing either
    expect(reader_page.locator("#mlCompareText")).to_have_value(
        "# Chapter 1\n\nwritten in VS Code\n"
    )
    assert chapter_one(library, doc).read_bytes() == ELSEWHERE and archived(library) == {}
    reader_page.locator("#mlKeepMine").click()
    wait_save_state(reader_page, "clean")
    assert chapter_one(library, doc).read_bytes().replace(b"\r\n", b"\n").endswith(
        b"my own words and more")  # fmt: skip
    assert list(archived(library).values()) == [ELSEWHERE]
    expect(reader_page.locator("#mlNotesStatus")).to_contain_text("archive/notes-conflicts/")
    assert drafts_in_browser(reader_page) == {}


def test_use_the_disk_version_archives_mine_first(library, server_factory, reader_page):
    doc, _ = open_book(library, server_factory, reader_page)
    into_conflict(reader_page, library, doc, mine="words I set aside")
    mine = editor_text(reader_page)
    reader_page.locator("#mlUseDisk").click()
    wait_save_state(reader_page, "clean")
    assert editor_text(reader_page) == "# Chapter 1\n\nwritten in VS Code\n"
    assert chapter_one(library, doc).read_bytes() == ELSEWHERE  # nothing written to the note
    [(name, data)] = archived(library).items()
    assert name.endswith(".mine.md")
    assert data.replace(b"\r\n", b"\n").decode("utf-8-sig") == mine  # my text, kept
    expect(reader_page.locator("#mlNotesStatus")).to_contain_text("archive/notes-conflicts/")
    assert drafts_in_browser(reader_page) == {}


def test_the_disk_changing_again_during_keep_mine(library, server_factory, reader_page):
    """Keep mine overwrites only the version the user saw: a newer one in the meantime is a
    new conflict (nothing written), shown again; Keep mine then archives that newer one."""
    doc, _ = open_book(library, server_factory, reader_page)
    into_conflict(reader_page, library, doc)
    chapter_one(library, doc).write_bytes(AGAIN)  # changed again while deciding
    reader_page.locator("#mlKeepMine").click()
    expect(reader_page.locator("#mlNotesStatus")).to_contain_text("changed again")
    assert reader_page.evaluate("() => document.body.dataset.mlSaveState") == "conflict"
    assert chapter_one(library, doc).read_bytes() == AGAIN and archived(library) == {}
    reader_page.locator("#mlCompare").click()
    expect(reader_page.locator("#mlCompareText")).to_have_value(
        "# Chapter 1\n\nwritten in VS Code, twice\n")  # fmt: skip
    reader_page.locator("#mlKeepMine").click()
    wait_save_state(reader_page, "clean")
    assert list(archived(library).values()) == [AGAIN]
    assert b"my own words" in chapter_one(library, doc).read_bytes()


def test_an_archive_failure_keeps_my_text(library, server_factory, reader_page):
    """Use the disk version: if my text can't be archived, nothing is discarded."""
    doc, _ = open_book(library, server_factory, reader_page)
    into_conflict(reader_page, library, doc, mine="must not be lost")
    reader_page.route(
        "**/api/notes/keep-copy",
        lambda route: route.fulfill(
            status=500, content_type="application/json", body='{"error": "the archive is full"}'
        ),
    )
    reader_page.locator("#mlUseDisk").click()
    expect(reader_page.locator("#mlNotesStatus")).to_contain_text("the conflict is still open")
    expect(reader_page.locator("#mlNotesStatus")).to_contain_text("Nothing was lost")
    assert reader_page.evaluate("() => document.body.dataset.mlSaveState") == "conflict"
    assert editor_text(reader_page).endswith("must not be lost")
    assert chapter_one(library, doc).read_bytes() == ELSEWHERE and archived(library) == {}
    assert any(t.endswith("must not be lost") for t in drafts_in_browser(reader_page).values())


def test_two_tabs_on_one_note(library, server_factory, reader_page):
    doc, server = open_book(library, server_factory, reader_page)
    other = reader_page.context.new_page()
    open_document(other, server, doc, page_no=2)
    notes_settled(other)
    type_at_end(reader_page, "from tab one")
    reader_page.keyboard.press("Control+s")
    wait_save_state(reader_page, "clean")
    # The other tab had nothing unsaved: it takes the new version (told by the first tab)
    other.wait_for_function(
        "() => document.getElementById('mlNoteText').value.endsWith('from tab one')")  # fmt: skip
    # Both type; the second save meets the first one's version: a conflict, nothing lost
    type_at_end(other, " / from tab two")
    type_at_end(reader_page, " / again from tab one")
    reader_page.keyboard.press("Control+s")
    wait_save_state(reader_page, "clean")
    other.keyboard.press("Control+s")
    wait_save_state(other, "conflict")
    assert editor_text(other).endswith("/ from tab two")
    assert chapter_one(library, doc).read_bytes().endswith(b"/ again from tab one")


def test_a_version_check_never_mistakes_our_own_save_for_a_conflict(
    library, server_factory, reader_page
):
    """A check of the disk version that answers late, after our own save changed it, is ignored
    (it describes the file before our save)."""
    doc, _ = open_book(library, server_factory, reader_page)
    held = []

    def hold_first_check(route):
        if not held:
            held.append(route)
        else:
            route.continue_()

    reader_page.route("**/api/notes/version", hold_first_check)
    reader_page.evaluate("() => dispatchEvent(new Event('focus'))")  # a check starts
    poll(reader_page, lambda: held, message="no version check")
    type_at_end(reader_page, "saved while the check was out")
    reader_page.keyboard.press("Control+s")
    wait_save_state(reader_page, "clean")
    held[0].continue_()  # its answer (if it says anything) is about the file before our save
    reader_page.wait_for_function(
        "() => performance.getEntriesByType('resource')"
        ".filter(e => e.name.endsWith('/api/notes/version')).length >= 1"
    )
    reader_page.evaluate("() => dispatchEvent(new Event('focus'))")  # and a fresh check
    reader_page.wait_for_function(
        "() => performance.getEntriesByType('resource')"
        ".filter(e => e.name.endsWith('/api/notes/version')).length >= 2"
    )
    assert reader_page.evaluate("() => document.body.dataset.mlSaveState") == "clean"
    expect(reader_page.locator("#mlNoteBar")).to_be_hidden()
    assert chapter_one(library, doc).read_bytes().endswith(b"saved while the check was out")


def test_compare_shows_both_and_writes_nothing(library, server_factory, reader_page):
    doc, _ = open_book(library, server_factory, reader_page)
    into_conflict(reader_page, library, doc)
    mine = editor_text(reader_page)
    reader_page.locator("#mlCompare").click()
    expect(reader_page.locator("#mlCompareText")).to_be_visible()
    expect(reader_page.locator("#mlCompareText")).to_have_attribute("readonly", "")
    expect(reader_page.locator("#mlCompareText")).to_have_value(re.compile("written in VS Code"))
    assert editor_text(reader_page) == mine
    reader_page.locator("#mlCompare").click()  # hide it again
    expect(reader_page.locator("#mlCompareText")).to_be_hidden()
    assert chapter_one(library, doc).read_bytes() == ELSEWHERE and archived(library) == {}
    expect(reader_page.locator(EDITOR)).not_to_have_attribute("readonly", "")
