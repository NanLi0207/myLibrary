"""The notes panel's content (task 4 M3, read-only): which note opens, its exact text, switching,
the empty / not written / error states, that nothing in it is ever run or written, the editor
button, and that lookup, search and marks still work beside it."""

import json
import sys

from helpers import (
    click_mark_on_line,
    eventually,
    highlight_line,
    highlighted_lines,
    leave,
    leave_tool,
    line_span,
    notes_settled,
    open_document,
    wait_marks_saved,
)
from playwright.sync_api import expect

BOM = chr(0xFEFF)
CH1 = (
    BOM + "# Chapter 1: Basics\r\n\r\n- 光阑 (aperture stop) limits the beam\r\n"
    "- $n_1 \\sin\\theta_1 = n_2 \\sin\\theta_2$\r\n"
)
CH1_SHOWN = CH1.removeprefix(BOM).replace("\r\n", "\n")  # as the panel shows it
VOCABULARY = "# Vocabulary\n\n- vignetting 渐晕\n"
TEXT = "() => document.getElementById('mlNoteText').textContent"
KEY = "() => document.body.dataset.mlNoteKey"


def book_with_notes(library, pages: dict[int, int] | None = None):
    """A book whose README lists 3 chapters: ch01 written (CRLF, BOM, Chinese, a formula),
    ch02 not written yet, ch03 empty; and a vocabulary note. `pages`: the chapter start
    pages the server has cached ({} = none known)."""
    doc = library.add_book("doe-2020-optics-test", "Optics test")
    library.add_notes(
        doc,
        ["Basics", "Aberrations", "Imaging"],
        {
            "ch01-basics.md": CH1.encode("utf-8"),
            "ch03-imaging.md": b"",
            "vocabulary.md": VOCABULARY.encode("utf-8"),
        },
    )
    library.cache_chapter_pages(doc, {1: 1, 2: 3, 3: 5} if pages is None else pages)
    return doc


def answers(page, count: int) -> None:
    """Wait until the page has had `count` answers to /api/notes/get (resource timing)."""
    page.wait_for_function(
        "n => performance.getEntriesByType('resource')"
        ".filter(e => e.name.endsWith('/api/notes/get')).length >= n",
        arg=count,
    )


def choose(page, key):
    page.locator("#mlNoteSelect").select_option(key)


def test_the_chapter_of_the_opened_page_with_its_exact_text(library, server_factory, reader_page):
    doc = book_with_notes(library)
    server = server_factory()
    open_document(reader_page, server, doc, page_no=2)  # chapter 1 runs from page 1 to 2
    assert notes_settled(reader_page) == "shown"
    assert reader_page.evaluate(KEY) == "file:ch01-basics.md"
    assert reader_page.evaluate(TEXT) == CH1_SHOWN
    labels = reader_page.locator("#mlNoteSelect option").all_inner_texts()
    assert labels == [
        "README.md",
        "Ch 1: Basics",
        "Ch 2: Aberrations（还没有 not written yet）",
        "Ch 3: Imaging",
        "vocabulary.md",
    ]

    open_document(reader_page, server, doc, page_no=4)  # chapter 2, not written yet
    assert notes_settled(reader_page) == "missing"
    assert reader_page.evaluate(KEY) == "file:ch02-aberrations.md"
    expect(reader_page.locator("#mlNotesStatus")).to_contain_text("No notes for this chapter yet")
    expect(reader_page.locator("#mlNoteOpen")).to_be_disabled()
    reader_page.locator("#next").click()  # reading on never switches the note by itself
    reader_page.wait_for_function("() => PDFViewerApplication.page === 5")
    assert reader_page.evaluate(KEY) == "file:ch02-aberrations.md"


def test_without_chapter_pages_the_last_choice_then_the_readme(
    library, server_factory, reader_page
):
    doc = book_with_notes(library, pages={})
    server = server_factory()
    open_document(reader_page, server, doc, page_no=4)
    notes_settled(reader_page)
    assert reader_page.evaluate(KEY) == "file:README.md"  # no chapter pages known
    choose(reader_page, "file:ch03-imaging.md")
    reader_page.wait_for_function("() => document.body.dataset.mlNoteState === 'empty'")
    expect(reader_page.locator("#mlNotesStatus")).to_contain_text("This note is empty")
    reader_page.reload()
    notes_settled(reader_page)
    assert reader_page.evaluate(KEY) == "file:ch03-imaging.md"  # the last one chosen here


def test_switching_quickly_the_last_choice_wins(library, server_factory, reader_page):
    """The answer for an earlier choice arriving late never replaces the later one."""
    doc = book_with_notes(library)
    server = server_factory()
    held = []

    def hold_chapter_one(route):
        if "ch01-basics" in (route.request.post_data or "") and not held:
            held.append(route)  # answered later, after the next choice
        else:
            route.continue_()

    open_document(reader_page, server, doc, page_no=5)
    notes_settled(reader_page)  # chapter 3
    reader_page.route("**/api/notes/get", hold_chapter_one)
    choose(reader_page, "file:ch01-basics.md")
    reader_page.wait_for_function("() => document.body.dataset.mlNoteState === 'loading'")
    choose(reader_page, "file:vocabulary.md")
    reader_page.wait_for_function("t => document.getElementById('mlNoteText').textContent === t",
                                  arg=VOCABULARY)  # fmt: skip
    held[0].continue_()  # chapter 1's answer comes now, late
    answers(reader_page, 3)
    assert reader_page.evaluate(TEXT) == VOCABULARY
    assert reader_page.evaluate(KEY) == "file:vocabulary.md"
    assert reader_page.locator("#mlNoteSelect").input_value() == "file:vocabulary.md"


def test_a_failed_load_says_so_and_retries(library, server_factory, reader_page):
    doc = book_with_notes(library)
    server = server_factory()
    failures = []

    def fail_once(route):
        if not failures:
            failures.append(route.request.url)
            route.fulfill(status=500, content_type="application/json",
                          body=json.dumps({"error": "the disk is unhappy"}))  # fmt: skip
        else:
            route.continue_()

    reader_page.route("**/api/notes/get", fail_once)
    open_document(reader_page, server, doc, page_no=2)
    assert notes_settled(reader_page) == "error"
    expect(reader_page.locator("#mlNotesStatus")).to_contain_text("the disk is unhappy")
    reader_page.locator("#mlNotesStatus button").click()  # 重试 (Retry)
    reader_page.wait_for_function("() => document.body.dataset.mlNoteState === 'shown'")
    assert reader_page.evaluate(TEXT) == CH1_SHOWN


def test_a_document_without_notes(library, server, reader_page):
    doc = library.add_book("doe-2020-optics-test", "Optics test")
    (library.root / library.row(doc)["notes"] / "README.md").unlink()
    open_document(reader_page, server, doc)
    assert notes_settled(reader_page) == "none"
    expect(reader_page.locator("#mlNotesStatus")).to_contain_text("No notes for this document")
    expect(reader_page.locator("#mlNoteSelect")).to_be_disabled()


def test_a_note_is_shown_as_text_and_never_run(library, server, reader_page):
    doc = library.add_book("doe-2020-optics-test", "Optics test")
    active = (
        "# Mine\n<script>window.__ran = 1</script>\n"
        '<img src="x" onerror="window.__ran = 2">\n[link](javascript:window.__ran=3)\n'
    )
    library.add_notes(doc, [], {"README.md": active.encode()})
    open_document(reader_page, server, doc)
    notes_settled(reader_page)
    assert reader_page.evaluate(TEXT) == active  # every character as written
    assert reader_page.evaluate("() => window.__ran") is None
    assert reader_page.locator("#mlNotes img, #mlNotes script, #mlNotes a").count() == 0


def test_viewing_notes_writes_nothing(library, server_factory, reader_page):
    """In Preview Mode: open, switch through every note, scroll, use keys, come back to the
    tab, close it. The notes folder is byte-for-byte and time-for-time the same; no save,
    position or reading-time request was sent; nothing counts as reading."""
    doc = book_with_notes(library)
    server = server_factory()
    before = library.note_files(doc)
    sent = []
    reader_page.on(
        "request", lambda r: sent.append(r.url.split("?")[0]) if "/api/" in r.url else None
    )
    open_document(reader_page, server, doc, page_no=2, query="&preview=1")
    notes_settled(reader_page)
    for key in ("file:README.md", "file:ch02-aberrations.md", "file:ch03-imaging.md",
                "file:vocabulary.md", "file:ch01-basics.md"):  # fmt: skip
        choose(reader_page, key)
        reader_page.wait_for_function(
            "k => document.body.dataset.mlNoteKey === k"
            " && document.body.dataset.mlNoteState !== 'loading'",
            arg=key,
        )
    reader_page.locator("#mlNoteText").focus()
    for key in ("PageDown", "End", "Home", "a", "Control+a", "Control+c"):
        reader_page.keyboard.press(key)
    reader_page.evaluate("() => dispatchEvent(new Event('focus'))")  # back to the tab: a refresh
    answers(reader_page, 7)
    assert not leave(reader_page, "close")
    assert library.note_files(doc) == before
    assert {url.rsplit("/api/", 1)[1] for url in sent} <= {"notes/list", "notes/get"}
    assert library.reading_log() == {}
    assert "Last read" not in library.readme(doc)


def test_the_editor_button_opens_that_note(library, server_factory, reader_page, tmp_path):
    """↗ asks the server to open the shown note with the editor from the settings; here a
    stand-in that only records the file it was given."""
    doc = book_with_notes(library)
    record = tmp_path / "opened.txt"
    stand_in = tmp_path / "editor.py"
    stand_in.write_text(
        f"import sys, pathlib\npathlib.Path({str(record)!r}).write_text(sys.argv[1], 'utf-8')\n",
        encoding="utf-8",
    )
    settings = (
        f'editor = "custom"\neditor_command = \'"{sys.executable}" "{stand_in}" "{{file}}"\'\n'
    )
    server = server_factory(settings=settings)
    before = library.note_files(doc)
    open_document(reader_page, server, doc, page_no=2)
    notes_settled(reader_page)
    reader_page.locator("#mlNoteOpen").click()
    expect(reader_page.locator("#mlNotesStatus")).to_contain_text("Opened in the editor")
    opened = eventually(lambda: record.exists() and record.read_text("utf-8"), message="not opened")
    notes = library.root / library.row(doc)["notes"]
    assert opened.replace("\\", "/") == (notes / "ch01-basics.md").as_posix()
    assert library.note_files(doc) == before


def test_lookup_beside_the_notes(library, server, reader_page):
    """A word looked up in the PDF: its popup stays in the PDF's part of the window. A
    double-click in the notes looks nothing up."""
    doc = library.add_book("doe-2020-optics-test", "Optics test")
    library.add_notes(doc, [], {"README.md": b"entrance pupil and aperture\n"})
    open_document(reader_page, server, doc)
    notes_settled(reader_page)
    word = line_span(reader_page, 3)
    box = word.bounding_box()
    reader_page.mouse.dblclick(box["x"] + box["width"] - 30, box["y"] + box["height"] / 2)
    popup = reader_page.locator(".ml-popup")
    expect(popup).to_be_visible()
    reader_page.wait_for_function("() => !document.querySelector('.ml-popup .ml-muted')"
                                  " || document.querySelector('.ml-popup .ml-head')")  # fmt: skip
    right = reader_page.evaluate(
        "() => document.querySelector('.ml-popup').getBoundingClientRect().right"
    )
    pdf = reader_page.evaluate(
        "() => document.getElementById('outerContainer').getBoundingClientRect().right"
    )
    assert right <= pdf + 1
    reader_page.keyboard.press("Escape")
    expect(popup).to_have_count(0)

    text = reader_page.locator("#mlNoteText").bounding_box()
    reader_page.mouse.dblclick(text["x"] + 40, text["y"] + 20)
    assert reader_page.evaluate("() => String(getSelection()).trim()")  # a word is selected
    reader_page.evaluate("() => new Promise(r => requestAnimationFrame(() => setTimeout(r, 0)))")
    expect(popup).to_have_count(0)  # but not looked up


def test_marks_and_their_undo_beside_the_notes(library, server, reader_page):
    """Marks work as before with the notes open; Ctrl+Z in the notes never undoes a mark."""
    doc = library.add_book("doe-2020-marks-test", "Marks test")
    open_document(reader_page, server, doc)
    notes_settled(reader_page)
    highlight_line(reader_page, 2)
    leave_tool(reader_page)
    wait_marks_saved(reader_page)
    marks = reader_page.locator(".annotationEditorLayer .highlightEditor")
    expect(marks).to_have_count(1)

    reader_page.locator("#mlNoteText").focus()
    reader_page.keyboard.press("Control+z")  # in the notes: not the marks'
    expect(marks).to_have_count(1)
    expect(reader_page.locator("#mlUndo")).to_be_enabled()

    reader_page.locator("#viewerContainer").focus()
    reader_page.keyboard.press("Control+z")  # in the PDF: undone
    expect(marks).to_have_count(0)
    reader_page.keyboard.press("Control+y")
    expect(marks).to_have_count(1)
    wait_marks_saved(reader_page)
    assert highlighted_lines(library.pdf(doc)) == [2]
    click_mark_on_line(reader_page, 2)  # still selectable as before


def test_using_the_notes_records_no_reading(library, server_factory, reader_page):
    """Normal reading (not a preview): opening, closing, resizing, scrolling and switching the
    notes send no reading position, no reading time and no page beyond the one the book opened
    at. Turning a page in the PDF afterwards is still recorded as before."""
    doc = book_with_notes(library)
    server = server_factory()
    reports = []

    def watch(request):
        if "/api/position" in request.url or "/api/reading" in request.url:
            reports.append((request.url.rsplit("/api/", 1)[1], request.post_data_json))

    reader_page.on("request", watch)
    open_document(reader_page, server, doc, page_no=2)
    notes_settled(reader_page)
    toggle = reader_page.locator("#mlNotesToggle")
    toggle.click()  # close, open
    reader_page.wait_for_function("() => document.body.dataset.mlNotes === 'closed'")
    toggle.click()
    notes_settled(reader_page)
    edge = reader_page.evaluate(
        "() => document.getElementById('outerContainer').getBoundingClientRect().right"
    )
    reader_page.mouse.move(edge, 400)  # resize by dragging, then by keys
    reader_page.mouse.down()
    reader_page.mouse.move(edge - 150, 400, steps=6)
    reader_page.mouse.up()
    reader_page.locator(".ml-notes-divider").focus()
    reader_page.keyboard.press("ArrowRight")
    for key in ("file:vocabulary.md", "file:ch03-imaging.md", "file:ch01-basics.md"):
        choose(reader_page, key)
    reader_page.wait_for_function("() => document.body.dataset.mlNoteState === 'shown'")
    box = reader_page.locator("#mlNoteText").bounding_box()
    reader_page.mouse.move(box["x"] + 50, box["y"] + 50)
    reader_page.mouse.wheel(0, 300)  # scrolling the note
    reader_page.locator("#mlNoteText").focus()
    reader_page.keyboard.press("PageDown")
    reader_page.keyboard.press("Alt+n")
    reader_page.keyboard.press("Alt+n")
    notes_settled(reader_page)
    assert reader_page.evaluate("() => PDFViewerApplication.page") == 2
    assert not leave(reader_page, "close")

    assert [kind for kind, _ in reports if kind == "position"] == []  # "Last read" untouched
    for kind, body in reports:  # what closing the tab reported: nothing read
        assert kind == "reading" and body["seconds"] == 0 and set(body["pages"]) <= {2}, reports
    assert "Last read" not in library.readme(doc)

    # The PDF's own reading is still recorded: a page turned, then the tab closed
    reading = reader_page.context.new_page()
    open_document(reading, server, doc, page_no=2)
    reading.locator("#next").click()
    reading.wait_for_function("() => PDFViewerApplication.page === 3")
    leave(reading, "close")
    eventually(lambda: "Last read: page 3" in library.readme(doc), message="reading not saved")
    days = eventually(lambda: library.reading_log(), message="no reading-log entry arrived")
    assert any(3 in day.get(doc, {}).get("p", []) for day in days.values()), days


def test_time_in_the_notes_is_not_reading_time(library, server_factory, reader_page):
    """Reading time counts while the PDF is in use (task 4 decision 3), in 15 s steps sent each
    minute. With Playwright's fake clock: after the reader has been idle, a minute of mouse and
    wheel in the notes reports no reading time; the same in the PDF reports 60 s."""
    doc = book_with_notes(library)
    server = server_factory()
    reports = []
    reader_page.on(
        "request",
        lambda r: reports.append(r.post_data_json) if "/api/reading" in r.url else None,
    )
    reader_page.clock.install()  # the page's timers and Date, moved on by the test
    open_document(reader_page, server, doc)
    notes_settled(reader_page)

    def a_minute_of_input_in(selector):
        reader_page.clock.run_for(3 * 60_000)  # idle first: no reading activity for > 2 min
        reports.clear()
        box = reader_page.locator(selector).bounding_box()
        for _ in range(8):  # input every 7.5 s for a minute
            reader_page.mouse.move(box["x"] + 30, box["y"] + 60)
            reader_page.mouse.wheel(0, 40)
            reader_page.mouse.move(box["x"] + 60, box["y"] + 90)
            reader_page.clock.run_for(7_500)
        reader_page.clock.run_for(1_000)  # past the minute's report
        return [r["seconds"] for r in reports]

    assert sum(a_minute_of_input_in("#mlNoteText")) == 0
    assert sum(a_minute_of_input_in("#viewerContainer")) == 60  # the PDF: counted as before
