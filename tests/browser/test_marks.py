"""Marks made with PDF.js's tools: saved into the library's PDF, selected with a click,
deleted, and undone or redone (toolbar ↶ ↷, Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z), also while
reading. Every check of what was kept reads the PDF itself."""

from helpers import (
    click_mark_on_line,
    highlight_line,
    highlighted_lines,
    leave_tool,
    open_document,
    saved_marks,
    screen_lines,
    wait_marks_saved,
)
from playwright.sync_api import expect

UNDO, REDO = "#mlUndo", "#mlRedo"


def buttons(page) -> tuple[bool, bool]:
    """(↶ enabled, ↷ enabled)"""
    return (page.locator(UNDO).is_enabled(), page.locator(REDO).is_enabled())


def test_marks_are_saved_into_the_pdf_with_the_original_kept(library, server, reader_page):
    doc = library.add_book("doe-2020-marks-test", "Marks test")
    pdf = library.pdf(doc)
    original = pdf.read_bytes()
    open_document(reader_page, server, doc)
    expect(reader_page.locator(UNDO)).to_be_disabled()  # nothing to undo yet
    expect(reader_page.locator(REDO)).to_be_disabled()
    highlight_line(reader_page, 0)
    expect(reader_page.locator(".ml-saved.ml-find")).to_contain_text("Click a mark to select it")
    highlight_line(reader_page, 3)
    leave_tool(reader_page)
    wait_marks_saved(reader_page)
    assert highlighted_lines(pdf) == [0, 3]
    assert (library.root / "archive" / "before-marks" / "books" / pdf.name).read_bytes() == original

    open_document(reader_page, server, doc)  # reopened: read back from the file
    expect(reader_page.locator(".annotationLayer .highlightAnnotation")).to_have_count(2)


def test_a_saved_mark_is_selected_deleted_and_restored(library, server, reader_page):
    doc = library.add_book("doe-2020-marks-test", "Marks test")
    saved_marks(reader_page, server, doc, [0, 3])

    page = reader_page.context.new_page()
    open_document(page, server, doc)
    click_mark_on_line(page, 0)  # while reading: the tool comes on, the mark is selected
    delete = page.locator(".selectedEditor .editToolbar button.delete")
    expect(delete).to_be_visible()
    page.keyboard.press("Delete")
    expect(page.locator(".annotationEditorLayer .highlightEditor")).to_have_count(1)
    assert screen_lines(page) == [3]
    expect(page.locator("#editorUndoBar")).to_be_visible()
    page.keyboard.press("Control+z")
    page.wait_for_function(
        "() => document.querySelectorAll('.annotationEditorLayer .highlightEditor').length === 2"
    )
    assert screen_lines(page) == [0, 3]

    leave_tool(page)
    click_mark_on_line(page, 0)
    page.locator(".selectedEditor .editToolbar button.delete").click()  # 🗑
    leave_tool(page)
    wait_marks_saved(page)
    assert highlighted_lines(library.pdf(doc)) == [3]  # only the deleted one is gone
    open_document(page, server, doc)
    expect(page.locator(".annotationLayer .highlightAnnotation")).to_have_count(1)
    assert screen_lines(page) == [3]
    page.close()


def test_undo_and_redo_with_the_tool_on_and_while_reading(library, server, reader_page):
    doc = library.add_book("doe-2020-marks-test", "Marks test")
    page = reader_page
    open_document(page, server, doc)
    highlight_line(page, 0)  # A
    highlight_line(page, 3)  # B
    assert buttons(page) == (True, False)
    click_mark_on_line(page, 0)
    page.keyboard.press("Delete")  # A deleted

    def lines_become(expected):
        page.wait_for_function(
            """expected => {
              const n = document.querySelectorAll('.annotationEditorLayer .highlightEditor').length;
              return n === expected; }""",
            arg=len(expected),
        )
        assert screen_lines(page) == expected

    lines_become([3])
    page.keyboard.press("Control+z")  # undo the deletion: A back
    lines_become([0, 3])
    page.keyboard.press("Control+z")  # undo B
    lines_become([0])
    assert buttons(page) == (True, True)
    page.keyboard.press("Control+y")  # redo B
    lines_become([0, 3])
    page.keyboard.press("Control+Shift+z")  # redo the deletion of A
    lines_become([3])
    assert buttons(page) == (True, False)

    leave_tool(page)  # Esc: reading again; the history stays
    assert buttons(page) == (True, False)
    page.locator(UNDO).click()
    lines_become([0, 3])
    page.keyboard.press("Control+z")
    lines_become([0])
    page.keyboard.press("Control+y")
    lines_become([0, 3])
    page.locator(REDO).click()
    lines_become([3])
    assert page.evaluate("() => PDFViewerApplication.pdfViewer.annotationEditorMode") == 0

    for _ in range(3):
        page.locator(UNDO).click()
    lines_become([])
    assert buttons(page) == (False, True)
    for _ in range(3):
        page.keyboard.press("Control+y")
    lines_become([3])

    page.keyboard.press("Control+z")  # A back; then a new mark drops what could be redone
    lines_become([0, 3])
    assert buttons(page) == (True, True)
    highlight_line(page, 6)
    lines_become([0, 3, 6])
    assert buttons(page) == (True, False)
    page.keyboard.press("Control+y")
    assert screen_lines(page) == [0, 3, 6]

    leave_tool(page)
    wait_marks_saved(page)
    assert highlighted_lines(library.pdf(doc)) == [0, 3, 6]  # the PDF has what's on screen


def test_undo_keys_in_a_text_field_belong_to_the_field(library, server, reader_page):
    doc = library.add_book("doe-2020-marks-test", "Marks test")
    page = reader_page
    open_document(page, server, doc)
    highlight_line(page, 0)
    leave_tool(page)
    page.evaluate("() => PDFViewerApplication.findBar.open()")
    field = page.locator("#findInput")
    field.click()
    field.press_sequentially("pupil")
    field.press("Control+z")
    field.press("Control+y")
    field.press("Control+Shift+z")
    assert screen_lines(page) == [0]  # the mark wasn't undone
    page.evaluate("() => PDFViewerApplication.findBar.close()")

    # with a tool on as well (PDF.js would otherwise take Ctrl+Z from a search-type field)
    page.locator("#editorHighlightButton").click()
    page.evaluate(
        """() => { const f = document.createElement('input'); f.type = 'search'; f.id = 'probe';
          f.style.cssText = 'position:fixed;left:8px;bottom:8px;z-index:200000';
          document.body.append(f); }"""
    )
    page.locator("#probe").click()
    page.locator("#probe").press_sequentially("lens")
    page.locator("#probe").press("Control+z")
    assert screen_lines(page) == [0]
