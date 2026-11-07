"""Marks are never lost silently: leaving a tab with unsaved marks (close, navigation, reload,
with no delay) brings the browser's "Leave site?" warning; "Marks saved" appears only after
the server wrote the file; failures stay visible with Retry; the last change wins. Slow and
failing servers are simulated by the test answering the page's save requests (page.route).

The closes here are Playwright's page.close(run_before_unload=True): the page's beforeunload
handlers run as for a user's close. The browser's own ✕ and Ctrl+W are outside the page and
were checked by hand (task 3 acceptance), not here."""

import json

import pytest
from helpers import (
    click_mark_on_line,
    highlight_line,
    highlighted_lines,
    leave,
    leave_tool,
    marks_state,
    open_document,
    poll,
    saved_marks,
    wait_marks_saved,
)
from playwright.sync_api import expect

SAVE = "**/api/save-marks"


def fail(route, message="simulated disk error"):
    route.fulfill(status=500, content_type="application/json", body=json.dumps({"error": message}))


@pytest.mark.parametrize("how", ["close", "navigate", "reload"])
def test_a_new_mark_then_leaving_at_once_warns_until_saved(library, server, reader_page, how):
    doc = library.add_book("doe-2020-marks-test", "Marks test")
    open_document(reader_page, server, doc)
    highlight_line(reader_page, 0)
    assert leave(reader_page, how, stay=True)  # warned; "Stay"
    wait_marks_saved(reader_page)
    assert highlighted_lines(library.pdf(doc)) == [0]
    reader_page.locator(".ml-marks").wait_for(state="hidden")  # nothing pending any more
    assert not leave(reader_page, how)  # saved: leaving is free


@pytest.mark.parametrize("how", ["close", "navigate", "reload"])
def test_deleting_a_saved_mark_then_leaving_at_once(library, server, reader_page, how):
    doc = library.add_book("doe-2020-marks-test", "Marks test")
    saved_marks(reader_page, server, doc, [0, 3])
    page = reader_page.context.new_page()
    open_document(page, server, doc)
    click_mark_on_line(page, 0)
    page.keyboard.press("Delete")
    assert leave(page, how, stay=True)
    wait_marks_saved(page)
    assert highlighted_lines(library.pdf(doc)) == [3]
    page.locator(".ml-marks").wait_for(state="hidden")
    assert not leave(page, how)


def test_one_failed_save_is_shown_then_tried_again(library, server, reader_page):
    doc = library.add_book("doe-2020-marks-test", "Marks test")
    calls = []

    def once_failing(route):
        calls.append(route.request.url)
        fail(route) if len(calls) == 1 else route.continue_()

    reader_page.route(SAVE, once_failing)
    open_document(reader_page, server, doc)
    highlight_line(reader_page, 6)
    leave_tool(reader_page)
    status = reader_page.locator(".ml-marks")
    expect(status).to_have_attribute("data-state", "failed")
    expect(status).to_contain_text("simulated disk error")
    expect(status.get_by_role("button", name="Retry")).to_be_visible()
    assert highlighted_lines(library.pdf(doc)) == []  # nothing claimed, nothing written
    wait_marks_saved(reader_page)  # the automatic second attempt
    assert len(calls) == 2 and highlighted_lines(library.pdf(doc)) == [6]


def test_a_lasting_failure_stays_visible_and_retry_saves(library, server, reader_page):
    doc = library.add_book("doe-2020-marks-test", "Marks test")
    calls, failing = [], [True]

    def handler(route):
        calls.append(1)
        fail(route) if failing[0] else route.continue_()

    reader_page.route(SAVE, handler)
    open_document(reader_page, server, doc)
    highlight_line(reader_page, 7)
    leave_tool(reader_page)
    poll(reader_page, lambda: len(calls) >= 3, 20, "the automatic attempts didn't happen")
    reader_page.wait_for_timeout(4000)  # longer than the 3 s between attempts: no 4th one
    assert len(calls) == 3 and marks_state(reader_page) == "failed"
    assert highlighted_lines(library.pdf(doc)) == []
    assert leave(reader_page, "close", stay=True)  # still unsaved: warned

    failing[0] = False
    reader_page.locator(".ml-marks").get_by_role("button", name="Retry").click()
    wait_marks_saved(reader_page)
    assert highlighted_lines(library.pdf(doc)) == [7]


def test_while_a_save_is_on_its_way_closing_warns_and_later_changes_follow(
    library, server, reader_page
):
    doc = library.add_book("doe-2020-marks-test", "Marks test")
    held = []

    def hold(route):  # the first save waits until the test lets it go; later ones pass
        if held:
            route.continue_()
        else:
            held.append(route)

    reader_page.route(SAVE, hold)
    open_document(reader_page, server, doc)
    highlight_line(reader_page, 0)
    poll(reader_page, lambda: held, 10, "no save was sent")
    expect(reader_page.locator(".ml-marks")).to_have_attribute("data-state", "saving")
    highlight_line(reader_page, 3)  # changed while the first save is still on its way
    assert leave(reader_page, "close", stay=True)  # saving: warned
    assert marks_state(reader_page) == "saving"  # no "Marks saved" before the answer

    held[0].continue_()  # the first save (line 0 only) reaches the server now
    poll(reader_page, lambda: highlighted_lines(library.pdf(doc)) == [0, 3], 20,
         "the change made during the first save wasn't saved next")  # fmt: skip
    wait_marks_saved(reader_page)


def test_rapid_changes_end_in_the_last_state(library, server, reader_page):
    doc = library.add_book("doe-2020-marks-test", "Marks test")
    open_document(reader_page, server, doc)
    for line in (9, 10, 11):
        highlight_line(reader_page, line)
    leave_tool(reader_page)
    for key in ("Control+z", "Control+y", "Control+z"):  # 11 out, back, out again
        reader_page.keyboard.press(key)
    assert leave(reader_page, "close", stay=True)
    wait_marks_saved(reader_page)
    poll(reader_page, lambda: highlighted_lines(library.pdf(doc)) == [9, 10], 10,
         f"the PDF has {highlighted_lines(library.pdf(doc))}")  # fmt: skip


def test_save_now(library, server, reader_page):
    doc = library.add_book("doe-2020-marks-test", "Marks test")
    open_document(reader_page, server, doc)
    highlight_line(reader_page, 11)
    status = reader_page.locator(".ml-marks")
    expect(status).to_have_attribute("data-state", "unsaved")
    status.get_by_role("button", name="Save now").click()
    wait_marks_saved(reader_page)
    assert highlighted_lines(library.pdf(doc)) == [11]
    status.wait_for(state="hidden")  # (unselecting the mark may bring one more short save)
    assert not leave(reader_page, "close")


def test_browsing_without_changes_never_warns(library, server, reader_page):
    doc = library.add_book("doe-2020-marks-test", "Marks test")
    saved_marks(reader_page, server, doc, [0])
    page = reader_page.context.new_page()
    open_document(page, server, doc)
    page.locator("#editorHighlightButton").click()  # the tool on and off over a saved mark
    page.wait_for_function("() => PDFViewerApplication.pdfViewer.annotationEditorMode === 9")
    leave_tool(page)
    page.locator("#next").click()
    page.locator("#zoomInButton").click()
    page.wait_for_function("() => PDFViewerApplication.page === 2")
    expect(page.locator(".ml-marks")).to_be_hidden()
    assert not leave(page, "close")


def test_small_writes_sent_just_before_closing_arrive(library, server, reader_page):
    """A chapter tick on the library page and Save word in the reader are single requests
    (keepalive): sent, then the tab closed at once, they still reach the server."""
    doc = library.add_book("doe-2020-marks-test", "Marks test")
    reader_page.goto(server.base + "/")
    reader_page.wait_for_function("() => typeof api === 'function' && API")
    reader_page.evaluate(f"() => {{ api('/api/tick', {{id: '{doc}', chapter: 1, done: true}}); }}")
    reader_page.close()
    words = reader_page.context.new_page()
    open_document(words, server, doc)
    word = {"id": doc, "text": "pupil", "context": "the entrance pupil", "page": 1}
    words.evaluate(
        """word => { fetch('/api/save-word', {method: 'POST', keepalive: true,
          headers: {'Content-Type': 'application/json', 'X-Library-Token': window.MYLIBRARY_TOKEN},
          body: JSON.stringify(word)}); }""",
        word,
    )
    words.close()
    from helpers import eventually

    eventually(lambda: "- [x] Chapter 1: Basics" in library.readme(doc), message="tick lost")
    vocabulary = library.root / library.row(doc)["notes"] / "vocabulary.md"
    eventually(lambda: vocabulary.exists() and "pupil" in vocabulary.read_text("utf-8"),
               message="saved word lost")  # fmt: skip
