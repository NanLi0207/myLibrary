"""Editing notes in the reader's panel (task 4 M4, mode A: Markdown source): typing is saved in
the file's own form, after a pause or at once with Ctrl+S / Save; one save at a time; the
browser's own Undo/Redo; keys stay in the text; Chinese input; 🔒; a chapter note started by
typing; switching notes. Temporary libraries only; Playwright's fake clock where timing is the
point (autosave delay), never fixed sleeps."""

import time

from helpers import (
    EDITOR,
    editor_text,
    leave,
    notes_settled,
    open_document,
    poll,
    record_save_states,
    save_state,
    type_at_end,
    wait_save_state,
)
from playwright.sync_api import expect
from test_notes_content import BOM, CH1_SHOWN, VOCABULARY, book_with_notes, choose


def note_file(library, doc, name):
    return library.root / library.row(doc)["notes"] / name


def open_chapter_one(library, server_factory, page, clock=False):
    """The book's chapter 1 note (CRLF, BOM, Chinese, a formula) open in the panel."""
    doc = book_with_notes(library)
    server = server_factory()
    if clock:
        page.clock.install()  # the page's timers, moved on by the test
    open_document(page, server, doc, page_no=2)
    notes_settled(page)
    assert page.evaluate("() => document.body.dataset.mlNoteKey") == "file:ch01-basics.md"
    if clock:
        page.clock.pause_at(int(time.time() * 1000) + 2_000)  # no timer runs unless moved on
    return doc, server


def saves_sent(page) -> list:
    """Every /api/notes/save the page sends, in order: their texts, and the order of requests
    and answers (to check that one never starts while another is unanswered)."""
    log = {"texts": [], "events": []}

    def request(r):
        if r.url.endswith("/api/notes/save"):
            log["texts"].append(r.post_data_json["text"])
            log["events"].append("request")

    def answered(r):
        if r.url.endswith("/api/notes/save"):
            log["events"].append("answer")

    page.on("request", request)
    page.on("requestfinished", answered)
    page.on("requestfailed", answered)
    return log


def test_typing_is_saved_in_the_files_own_form(library, server_factory, reader_page):
    doc, _ = open_chapter_one(library, server_factory, reader_page)
    record_save_states(reader_page)
    typed = "My words: 渐晕 (vignetting), $\\Delta n = n_F - n_C$ | a | b |"
    type_at_end(reader_page, typed)
    wait_save_state(reader_page, "clean")
    expected = BOM + (CH1_SHOWN + typed).replace("\n", "\r\n")  # CRLF and BOM kept
    assert note_file(library, doc, "ch01-basics.md").read_bytes() == expected.encode("utf-8")
    states = reader_page.evaluate("() => window.__states")
    assert states[0] == "clean" and states[-1] == "clean", states
    assert states.index("dirty") < states.index("saving"), states
    expect(reader_page.locator("#mlSaveState")).to_contain_text("Saved")


def test_autosave_comes_only_after_typing_stops(library, server_factory, reader_page):
    doc, _ = open_chapter_one(library, server_factory, reader_page, clock=True)
    log = saves_sent(reader_page)
    type_at_end(reader_page, "a")
    assert save_state(reader_page) == "dirty"
    reader_page.clock.run_for(1_000)
    reader_page.keyboard.type("b")  # still typing: the 1.5 s start again
    reader_page.clock.run_for(1_000)
    assert log["texts"] == [] and save_state(reader_page) == "dirty"
    reader_page.clock.run_for(600)
    wait_save_state(reader_page, "clean")
    assert len(log["texts"]) == 1 and log["texts"][0].endswith("ab")
    assert note_file(library, doc, "ch01-basics.md").read_bytes().endswith(b"ab")


def test_ctrl_s_and_save_save_at_once(library, server_factory, reader_page):
    doc, _ = open_chapter_one(library, server_factory, reader_page, clock=True)
    type_at_end(reader_page, "x")
    reader_page.keyboard.press("Control+s")  # no time passes: not the autosave
    wait_save_state(reader_page, "clean")
    assert note_file(library, doc, "ch01-basics.md").read_bytes().endswith(b"x")
    reader_page.keyboard.type("y")
    reader_page.locator("#mlNoteSave").click()
    wait_save_state(reader_page, "clean")
    assert note_file(library, doc, "ch01-basics.md").read_bytes().endswith(b"xy")


def test_ctrl_s_in_the_pdf_is_pdfjs_s_own(library, server_factory, reader_page):
    """Decision D4: Ctrl+S in the PDF stays PDF.js's "save the PDF" (a download), and doesn't
    save the note; in the note it saves the note and never downloads the PDF."""
    doc, _ = open_chapter_one(library, server_factory, reader_page)
    reader_page.locator(EDITOR).click()
    downloads = []
    reader_page.on("download", lambda d: downloads.append(d.suggested_filename))
    reader_page.keyboard.press("Control+s")  # in the note, nothing typed: nothing at all
    reader_page.locator("#viewerContainer").focus()
    with reader_page.expect_download() as download:
        reader_page.keyboard.press("Control+s")
    assert download.value.suggested_filename.endswith(".pdf")
    assert downloads == [download.value.suggested_filename]  # only the PDF's own Ctrl+S
    assert save_state(reader_page) == "clean"


def test_one_save_at_a_time_and_a_late_answer_never_marks_newer_text_saved(
    library, server_factory, reader_page
):
    doc, _ = open_chapter_one(library, server_factory, reader_page)
    log = saves_sent(reader_page)
    held = []

    def hold_first(route):
        if not held:
            held.append(route)  # answered only when the test says
        else:
            route.continue_()

    reader_page.route("**/api/notes/save", hold_first)
    type_at_end(reader_page, "first ")
    reader_page.keyboard.press("Control+s")
    poll(reader_page, lambda: held, message="the first save never left")
    record_save_states(reader_page)
    reader_page.keyboard.type("second")  # typed while the first save is on its way
    reader_page.keyboard.press("Control+s")
    assert save_state(reader_page) == "saving" and len(log["texts"]) == 1
    held[0].continue_()  # the first answer arrives: "first " saved, "second" isn't yet
    wait_save_state(reader_page, "clean")
    assert log["texts"][0].endswith("first ") and log["texts"][-1].endswith("first second")
    states = reader_page.evaluate("() => window.__states")
    assert "clean" not in states[:-1], states  # never "saved" before the newest text was
    events = log["events"]
    assert all(a != b for a, b in zip(events, events[1:], strict=False)), (
        events
    )  # never two at once
    assert note_file(library, doc, "ch01-basics.md").read_bytes().endswith(b"first second")


def test_the_texts_own_undo_and_the_markdown_helpers(library, server_factory, reader_page):
    doc = book_with_notes(library)
    server = server_factory()
    open_document(reader_page, server, doc, page_no=2)
    notes_settled(reader_page)
    choose(reader_page, "file:vocabulary.md")
    reader_page.wait_for_function("t => document.getElementById('mlNoteText').value === t",
                                  arg=VOCABULARY)  # fmt: skip
    editor = reader_page.locator(EDITOR)
    editor.click()
    reader_page.keyboard.press("Control+End")

    reader_page.keyboard.type("abc")
    undos = 0  # the browser's own Undo (it may take the typing back key by key)
    while editor_text(reader_page) != VOCABULARY and undos < 3:
        reader_page.keyboard.press("Control+z")
        undos += 1
    assert editor_text(reader_page) == VOCABULARY
    for _ in range(undos):
        reader_page.keyboard.press("Control+y")
    assert editor_text(reader_page) == VOCABULARY + "abc"
    for _ in range(undos):
        reader_page.keyboard.press("Control+z")
    assert editor_text(reader_page) == VOCABULARY

    reader_page.keyboard.type("- focus")
    reader_page.keyboard.press("Enter")  # the list goes on
    assert editor_text(reader_page) == VOCABULARY + "- focus\n- "
    reader_page.keyboard.press("Enter")  # an empty item ends it
    assert editor_text(reader_page) == VOCABULARY + "- focus\n"
    reader_page.keyboard.press("Control+z")  # and Undo brings the item back
    assert editor_text(reader_page) == VOCABULARY + "- focus\n- "
    reader_page.keyboard.press("Tab")  # indents the item
    assert editor_text(reader_page) == VOCABULARY + "- focus\n  - "
    reader_page.keyboard.press("Shift+Tab")
    assert editor_text(reader_page) == VOCABULARY + "- focus\n- "
    reader_page.keyboard.press("Control+z")
    assert editor_text(reader_page) == VOCABULARY + "- focus\n  - "

    editor.fill(VOCABULARY)  # a known text again
    reader_page.keyboard.press("Control+End")
    reader_page.keyboard.type("> quoted")
    reader_page.keyboard.press("Enter")  # a quote goes on too
    assert editor_text(reader_page) == VOCABULARY + "> quoted\n> "
    reader_page.keyboard.press("Enter")  # and ends on an empty quote line
    assert editor_text(reader_page) == VOCABULARY + "> quoted\n"
    expect(reader_page.locator("#mlUndo")).to_be_disabled()  # the PDF's marks: untouched


def test_pdf_keys_typed_into_the_note_stay_in_it(library, server_factory, reader_page):
    doc, _ = open_chapter_one(library, server_factory, reader_page)
    type_at_end(reader_page, "nnn jj kp ")
    reader_page.keyboard.press("PageDown")
    reader_page.keyboard.press("Home")
    assert editor_text(reader_page).endswith("nnn jj kp ")
    assert reader_page.evaluate("() => PDFViewerApplication.page") == 2
    reader_page.keyboard.press("Escape")  # back to the PDF
    reader_page.keyboard.press("n")  # PDF.js's own key: next page
    reader_page.wait_for_function("() => PDFViewerApplication.page === 3")


def test_a_chapter_note_is_created_only_by_typing_in_it(library, server_factory, reader_page):
    """Decision D2: opening, focusing, clicking a note not written yet creates nothing; the
    first save of typed text creates it."""
    doc = book_with_notes(library)
    server = server_factory()
    path = note_file(library, doc, "ch02-aberrations.md")
    reader_page.clock.install()
    open_document(reader_page, server, doc, page_no=4)  # chapter 2: not written yet
    assert notes_settled(reader_page) == "missing"
    reader_page.clock.pause_at(int(time.time() * 1000) + 2_000)
    reader_page.locator(EDITOR).click()
    reader_page.keyboard.press("End")
    reader_page.locator("#mlNoteSave").click(force=True)  # disabled: nothing to save
    reader_page.clock.run_for(10_000)  # far past the autosave delay
    assert not path.exists() and save_state(reader_page) == "clean"
    type_at_end(reader_page, "# Chapter 2: my notes")
    reader_page.clock.run_for(1_600)
    wait_save_state(reader_page, "clean")
    assert path.read_bytes() == b"# Chapter 2: my notes"
    expect(reader_page.locator("#mlNoteOpen")).to_be_enabled()  # it exists now


def test_read_only_is_a_remembered_choice(library, server_factory, reader_page):
    doc, server = open_chapter_one(library, server_factory, reader_page)
    reader_page.locator("#mlNoteLock").click()  # 🔒
    expect(reader_page.locator(EDITOR)).to_have_attribute("readonly", "")
    before = editor_text(reader_page)
    type_at_end(reader_page, "typed while read-only")
    assert editor_text(reader_page) == before and save_state(reader_page) == "clean"
    reader_page.reload()
    notes_settled(reader_page)
    expect(reader_page.locator(EDITOR)).to_have_attribute("readonly", "")
    reader_page.locator("#mlNoteLock").click()
    expect(reader_page.locator(EDITOR)).not_to_have_attribute("readonly", "")


def test_chinese_input_is_saved_only_once_composed(library, server_factory, reader_page):
    """An IME composition ("zhong" becoming 中) isn't saved half-way, however long it takes;
    the composed text is, and Undo takes it back."""
    doc, _ = open_chapter_one(library, server_factory, reader_page, clock=True)
    log = saves_sent(reader_page)
    reader_page.locator(EDITOR).click()
    reader_page.keyboard.press("Control+End")
    ime = reader_page.context.new_cdp_session(reader_page)
    ime.send("Input.imeSetComposition", {"text": "zhong", "selectionStart": 5, "selectionEnd": 5})
    reader_page.clock.run_for(5_000)
    assert log["texts"] == []  # nothing saved mid-composition
    ime.send("Input.insertText", {"text": "中"})  # the word is chosen
    reader_page.clock.run_for(1_600)
    wait_save_state(reader_page, "clean")
    assert log["texts"][-1].endswith("中") and "zhong" not in log["texts"][-1]
    assert note_file(library, doc, "ch01-basics.md").read_bytes().endswith("中".encode())
    reader_page.keyboard.press("Control+z")
    assert not editor_text(reader_page).endswith("中")


def test_switching_notes_saves_first_and_never_discards(library, server_factory, reader_page):
    doc, _ = open_chapter_one(library, server_factory, reader_page)
    held = []

    def hold_first(route):
        if not held:
            held.append(route)
        else:
            route.continue_()

    reader_page.route("**/api/notes/save", hold_first)
    type_at_end(reader_page, "before switching")
    reader_page.keyboard.press("Control+s")
    poll(reader_page, lambda: held, message="the save never left")
    choose(reader_page, "file:vocabulary.md")  # while that save is on its way
    assert reader_page.evaluate("() => document.body.dataset.mlNoteKey") == "file:ch01-basics.md"
    held[0].continue_()
    reader_page.wait_for_function("() => document.body.dataset.mlNoteKey === 'file:vocabulary.md'")
    reader_page.wait_for_function("t => document.getElementById('mlNoteText').value === t",
                                  arg=VOCABULARY)  # fmt: skip
    assert note_file(library, doc, "ch01-basics.md").read_bytes().endswith(b"before switching")

    # A save that fails: the note stays, with its text; nothing is discarded
    reader_page.unroute("**/api/notes/save")
    reader_page.route(
        "**/api/notes/save",
        lambda route: route.fulfill(
            status=500, content_type="application/json", body='{"error": "the disk is full"}'
        ),
    )
    before = note_file(library, doc, "vocabulary.md").read_bytes()
    type_at_end(reader_page, "unsaved words")
    choose(reader_page, "file:README.md")
    expect(reader_page.locator("#mlNotesStatus")).to_contain_text("isn't saved yet")
    assert reader_page.evaluate("() => document.body.dataset.mlNoteKey") == "file:vocabulary.md"
    assert editor_text(reader_page) == VOCABULARY + "unsaved words"
    assert reader_page.locator("#mlNoteSelect").input_value() == "file:vocabulary.md"
    assert note_file(library, doc, "vocabulary.md").read_bytes() == before


def test_editing_in_preview_mode_records_no_reading(library, server_factory, reader_page):
    doc = book_with_notes(library)
    server = server_factory()
    open_document(reader_page, server, doc, page_no=2, query="&find=entrance%20pupil&preview=1")
    notes_settled(reader_page)
    type_at_end(reader_page, "noted while looking something up")
    reader_page.keyboard.press("Control+s")
    wait_save_state(reader_page, "clean")
    assert not leave(reader_page, "close")
    assert note_file(library, doc, "ch01-basics.md").read_bytes().endswith(b"looking something up")
    assert "Last read" not in library.readme(doc) and library.reading_log() == {}


def test_typing_notes_is_not_reading_time(library, server_factory, reader_page):
    """With the fake clock: after the reader was idle, a minute of typing in the note reports
    no reading time (task 4 decision 3)."""
    doc = book_with_notes(library)
    server = server_factory()
    reports = []
    reader_page.on(
        "request",
        lambda r: reports.append(r.post_data_json) if "/api/reading" in r.url else None,
    )
    reader_page.clock.install()
    open_document(reader_page, server, doc, page_no=2)
    notes_settled(reader_page)
    reader_page.clock.run_for(3 * 60_000)
    reports.clear()
    reader_page.locator(EDITOR).click()
    for n in range(8):
        reader_page.keyboard.type(f"word{n} ")
        reader_page.clock.run_for(7_500)
    reader_page.clock.run_for(1_000)
    assert sum(r["seconds"] for r in reports) == 0, reports
