"""The notes panel beside the PDF (task 4 M3), its layout: opening and closing, the divider,
what's remembered, narrow windows, PDF.js's toolbar and zoom beside it, and keys.
Numbers are checked, not just "looks right": widths in px, PDF.js's page width, its page."""

import pytest
from helpers import layout, notes_open, notes_settled, open_document, page_width_changes
from playwright.sync_api import expect

PAGE_WIDTH = "() => { PDFViewerApplication.pdfViewer.currentScaleValue = 'page-width'; }"


def book(library):
    return library.add_book("doe-2020-optics-test", "Optics test")


def toggle(page):
    page.locator("#mlNotesToggle").click()


def test_first_use_opens_the_notes_beside_the_pdf(library, server, reader_page):
    doc = book(library)
    open_document(reader_page, server, doc)
    assert notes_open(reader_page)  # nothing stored yet: open
    notes_settled(reader_page)
    sizes = layout(reader_page)
    assert sizes["mode"] == "side"
    assert sizes["notes"] == pytest.approx(0.38 * 1400, abs=1)
    assert sizes["pdf"] == pytest.approx(1400 - sizes["notes"], abs=1)
    assert sizes["page"] < sizes["pdf"]  # PDF.js laid its pages out in its own area
    expect(reader_page.locator("#mlNotesToggle")).to_have_attribute("aria-pressed", "true")


def test_the_pdf_refits_when_the_notes_open_and_close(library, server, reader_page):
    """Page-width zoom follows the PDF area; the page you're on stays."""
    doc = book(library)
    open_document(reader_page, server, doc, page_no=3)
    reader_page.evaluate(PAGE_WIDTH)
    reader_page.wait_for_function("() => PDFViewerApplication.page === 3")
    beside = layout(reader_page)

    toggle(reader_page)
    page_width_changes(reader_page, beside["page"])
    alone = layout(reader_page)
    assert not alone["open"] and alone["pdf"] == 1400
    # the page grew with the area (the same margins either way)
    assert alone["pdf"] - alone["page"] == pytest.approx(beside["pdf"] - beside["page"], abs=3)
    assert reader_page.evaluate("() => PDFViewerApplication.page") == 3

    toggle(reader_page)
    page_width_changes(reader_page, alone["page"])
    assert layout(reader_page)["page"] == pytest.approx(beside["page"], abs=2)
    assert reader_page.evaluate("() => PDFViewerApplication.page") == 3


def test_a_chosen_zoom_stays_as_it_is(library, server, reader_page):
    doc = book(library)
    open_document(reader_page, server, doc)
    reader_page.evaluate("() => { PDFViewerApplication.pdfViewer.currentScaleValue = '1.5'; }")
    reader_page.wait_for_function("() => PDFViewerApplication.pdfViewer.currentScale === 1.5")
    toggle(reader_page)
    reader_page.wait_for_function("() => document.body.dataset.mlNotes === 'closed'")
    toggle(reader_page)
    reader_page.wait_for_function("() => document.body.dataset.mlNotes === 'open'")
    assert reader_page.evaluate("() => PDFViewerApplication.pdfViewer.currentScaleValue") == "1.5"


def test_the_divider_resizes_both_and_is_remembered(library, server, reader_page):
    doc = book(library)
    open_document(reader_page, server, doc)
    reader_page.evaluate(PAGE_WIDTH)
    notes_settled(reader_page)
    start = layout(reader_page)
    y = 500

    def drag_to(x):
        edge = layout(reader_page)["pdf"]
        reader_page.mouse.move(edge, y)
        reader_page.mouse.down()
        reader_page.mouse.move(x, y, steps=8)
        reader_page.mouse.up()

    drag_to(700)
    page_width_changes(reader_page, start["page"])
    sizes = layout(reader_page)
    assert sizes["pdf"] == pytest.approx(700, abs=2) and sizes["notes"] == pytest.approx(700, abs=2)
    assert sizes["pdf"] - sizes["page"] == pytest.approx(start["pdf"] - start["page"], abs=3)
    assert reader_page.evaluate("() => String(getSelection())") == ""  # nothing selected

    drag_to(1350)  # the notes can't get narrower than 320 px
    assert layout(reader_page)["notes"] == pytest.approx(320, abs=1)
    drag_to(50)  # nor the PDF than 480 px
    assert layout(reader_page)["pdf"] == pytest.approx(480, abs=1)

    drag_to(800)
    remembered = layout(reader_page)["notes"]
    reader_page.reload()
    reader_page.wait_for_function("() => PDFViewerApplication.pdfDocument")
    notes_settled(reader_page)
    assert layout(reader_page)["notes"] == pytest.approx(remembered, abs=1)
    # in a different window size, the same share of it
    reader_page.set_viewport_size({"width": 1200, "height": 1000})
    reader_page.wait_for_function(
        "w => Math.abs(document.getElementById('mlNotes').getBoundingClientRect().width - w) < 2",
        arg=remembered / 1400 * 1200,
    )
    assert layout(reader_page)["pdf"] == pytest.approx(1200 - remembered / 1400 * 1200, abs=2)


def test_the_divider_by_keyboard_and_double_click(library, server, reader_page):
    doc = book(library)
    open_document(reader_page, server, doc)
    notes_settled(reader_page)
    before = layout(reader_page)["notes"]
    divider = reader_page.locator(".ml-notes-divider")
    divider.focus()
    reader_page.keyboard.press("ArrowLeft")  # notes wider
    assert layout(reader_page)["notes"] == pytest.approx(before + 24, abs=1)
    reader_page.keyboard.press("ArrowRight")
    reader_page.keyboard.press("ArrowRight")
    assert layout(reader_page)["notes"] == pytest.approx(before - 24, abs=1)
    assert reader_page.evaluate("() => PDFViewerApplication.page") == 1  # no page turned
    divider.dblclick()
    reader_page.wait_for_function("() => document.body.dataset.mlNotes === 'closed'")


def test_open_or_closed_is_remembered(library, server, reader_page):
    doc = book(library)
    open_document(reader_page, server, doc)
    notes_settled(reader_page)
    reader_page.locator("#mlNotesClose").click()
    reader_page.reload()
    reader_page.wait_for_function("() => PDFViewerApplication.pdfDocument")
    assert not notes_open(reader_page)
    assert layout(reader_page)["pdf"] == 1400
    toggle(reader_page)
    notes_settled(reader_page)
    reader_page.reload()
    assert notes_open(reader_page)


def test_narrow_windows_open_over_the_pdf_and_leave_the_wide_setting_alone(
    library, server, reader_page
):
    doc = book(library)
    open_document(reader_page, server, doc)
    notes_settled(reader_page)  # wide: open (first use)

    reader_page.set_viewport_size({"width": 1000, "height": 900})
    reader_page.wait_for_function("() => document.body.dataset.mlNotesMode === 'drawer'")
    sizes = layout(reader_page)
    assert not sizes["open"] and sizes["pdf"] == 1000  # starts closed
    toggle(reader_page)
    notes_settled(reader_page)
    sizes = layout(reader_page)
    assert sizes["notes"] == 420 and sizes["pdf"] == 1000  # over the PDF, which keeps its width
    assert reader_page.evaluate("() => document.activeElement.id") == "mlNoteSelect"
    reader_page.keyboard.press("Escape")  # closes the drawer
    reader_page.wait_for_function("() => document.body.dataset.mlNotes === 'closed'")

    reader_page.set_viewport_size({"width": 700, "height": 900})
    reader_page.wait_for_function("() => document.body.dataset.mlNotesMode === 'full'")
    toggle(reader_page)
    notes_settled(reader_page)
    assert layout(reader_page)["notes"] == 700
    reader_page.locator("#mlNotesClose").click()
    reader_page.wait_for_function("() => document.body.dataset.mlNotes === 'closed'")
    assert reader_page.evaluate("() => document.activeElement.id") == "viewerContainer"

    # wide again: as it was left there (open), whatever was done in the narrow windows
    reader_page.set_viewport_size({"width": 1400, "height": 900})
    reader_page.wait_for_function("() => document.body.dataset.mlNotesMode === 'side'")
    assert layout(reader_page)["open"]
    assert reader_page.evaluate("() => localStorage.getItem('myLibrary.notes.open')") is None


@pytest.mark.parametrize("width", [1400, 1200, 1100])
def test_the_pdf_toolbar_stays_usable_beside_the_notes(library, server, reader_page, width):
    doc = book(library)
    reader_page.set_viewport_size({"width": width, "height": 900})
    open_document(reader_page, server, doc)
    notes_settled(reader_page)
    fits = reader_page.evaluate(
        """() => {
          const area = document.getElementById('outerContainer').getBoundingClientRect();
          const bar = document.getElementById('toolbarContainer').getBoundingClientRect();
          const popups = '#findbar, .doorHanger, .editorParamsToolbar, #secondaryToolbar';
          const shown = [...document.querySelectorAll(
              '#toolbarContainer button, #toolbarContainer select, #toolbarContainer input')]
            .filter(e => e.offsetParent && !e.closest(popups))
            .map(e => e.getBoundingClientRect());
          const outside = shown.filter(r => r.right > area.right + 1 || r.top > bar.top + 4);
          return {height: bar.height, outside: outside.length, count: shown.length};
        }"""
    )
    assert fits["height"] <= 33 and fits["outside"] == 0, fits  # one row, inside the PDF area
    before = reader_page.evaluate("() => PDFViewerApplication.pdfViewer.currentScale")
    reader_page.locator("#zoomInButton").click()
    reader_page.wait_for_function(f"() => PDFViewerApplication.pdfViewer.currentScale > {before}")
    reader_page.locator("#viewerContainer").click(position={"x": 30, "y": 300})
    reader_page.keyboard.press("Control+f")  # PDF.js's find bar, inside the PDF area
    expect(reader_page.locator("#findbar")).to_be_visible()
    box = reader_page.locator("#findbar").bounding_box()
    assert box["x"] + box["width"] <= layout(reader_page)["pdf"] + 1


def test_alt_n_toggles_from_anywhere_and_types_nothing(library, server, reader_page):
    doc = book(library)
    open_document(reader_page, server, doc, page_no=2)
    notes_settled(reader_page)
    reader_page.locator("#viewerContainer").click(position={"x": 30, "y": 300})
    reader_page.keyboard.press("Alt+n")
    reader_page.wait_for_function("() => document.body.dataset.mlNotes === 'closed'")
    reader_page.keyboard.press("Alt+n")
    notes_settled(reader_page)
    reader_page.locator("#mlNoteText").focus()  # from inside the panel
    reader_page.keyboard.press("Alt+n")
    reader_page.wait_for_function("() => document.body.dataset.mlNotes === 'closed'")
    assert reader_page.evaluate("() => document.activeElement.id") == "viewerContainer"
    reader_page.keyboard.press("Control+f")  # from PDF.js's find field
    reader_page.locator("#findInput").fill("pupil")
    reader_page.keyboard.press("Alt+n")
    notes_settled(reader_page)
    expect(reader_page.locator("#findInput")).to_have_value("pupil")  # no "n" typed
    assert reader_page.evaluate("() => PDFViewerApplication.page") == 2  # no page turned


def test_keys_in_the_notes_stay_in_the_notes(library, server_factory, reader_page):
    """Space, PageDown, End, n in the panel scroll the note; the PDF stays on its page. In the
    PDF, PDF.js's own keys still work. Esc in the panel goes back to the PDF."""
    doc = book(library)
    long_note = "".join(f"- line {n} of my notes\n" for n in range(300)).encode()
    library.add_notes(doc, ["Basics"], {"ch01-basics.md": long_note})
    library.cache_chapter_pages(doc, {1: 1})  # before the server starts
    server = server_factory()
    open_document(reader_page, server, doc)
    notes_settled(reader_page)
    assert reader_page.evaluate("() => document.body.dataset.mlNoteKey") == "file:ch01-basics.md"
    text = reader_page.locator("#mlNoteText")
    text.focus()
    for key in ("n", "PageDown", "Space", "End", "j", "ArrowDown"):
        reader_page.keyboard.press(key)
    # the note scrolls (Edge animates it: wait for it to move)
    reader_page.wait_for_function("() => document.getElementById('mlNoteText').scrollTop > 0")
    assert reader_page.evaluate("() => PDFViewerApplication.page") == 1
    reader_page.keyboard.press("Escape")  # back to the PDF; the panel stays
    assert reader_page.evaluate("() => document.activeElement.id") == "viewerContainer"
    assert layout(reader_page)["open"]
    reader_page.keyboard.press("n")  # PDF.js: next page
    reader_page.wait_for_function("() => PDFViewerApplication.page === 2")


@pytest.mark.parametrize("width", [1400, 1100, 900])
def test_the_preview_bar_covers_neither_the_find_bar_nor_the_notes(
    library, server, reader_page, width
):
    """A search result opened in Preview Mode: its 开始阅读 (Start reading) bar sits clear of
    PDF.js's find bar (with its ▲▼) and of the notes panel, so all of them can be clicked."""
    doc = book(library)
    reader_page.set_viewport_size({"width": width, "height": 900})
    open_document(reader_page, server, doc, page_no=2, query="&find=entrance%20pupil&preview=1")
    if not notes_open(reader_page):
        toggle(reader_page)  # narrow window: open the notes over the PDF too
    notes_settled(reader_page)
    expect(reader_page.locator("#findbar")).to_be_visible()
    boxes = {
        name: reader_page.locator(selector).bounding_box()
        for name, selector in (
            ("bar", ".ml-preview"),
            ("find", "#findbar"),
            ("notes", "#mlNotes"),
            ("toolbar", "#toolbarContainer"),
        )
    }

    def overlap(a, b):
        apart = (
            a["x"] + a["width"] <= b["x"]
            or b["x"] + b["width"] <= a["x"]
            or a["y"] + a["height"] <= b["y"]
            or b["y"] + b["height"] <= a["y"]
        )
        return not apart

    assert not overlap(boxes["bar"], boxes["find"]), boxes
    assert not overlap(boxes["bar"], boxes["toolbar"]), boxes
    side = layout(reader_page)["mode"] == "side"
    if side:  # beside the PDF: never under the notes either
        assert not overlap(boxes["bar"], boxes["notes"]), boxes
    reader_page.locator("#findNextButton").click()  # clickable, nothing over it
    if side:
        reader_page.locator(".ml-preview button").click()  # 开始阅读 (Start reading)
        expect(reader_page.locator(".ml-preview")).to_have_count(0)
