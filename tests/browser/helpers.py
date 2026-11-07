"""Actions and checks in the reader, shared by the browser tests. They wait on states the
reader shows (PDF.js loaded, the marks' save status, files on disk), never for a fixed time."""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import Error, Page, expect
from pypdf import PdfReader

MODE = "PDFViewerApplication.pdfViewer.annotationEditorMode"
HIGHLIGHT = 9  # PDF.js AnnotationEditorType
MARKS_STATE = ".ml-marks[data-state]"


def open_document(page: Page, server, doc_id: str, page_no: int = 1, query: str = "") -> None:
    """/read/<id>?page=N (the lasting link) and wait until the reader is ready on that page."""
    page.goto(f"{server.base}/read/{doc_id}?page={page_no}{query}")
    page.wait_for_function(
        """n => window.PDFViewerApplication?.pdfDocument && PDFViewerApplication.page === n
             && document.querySelector(`.page[data-page-number="${n}"] .textLayer span`)
             && document.getElementById("mlUndo")""",
        arg=page_no,
    )


def app(page: Page, expression: str):
    return page.evaluate(f"() => {expression}")


def line_span(page: Page, line: int, page_no: int = 1):
    return page.locator(f'.page[data-page-number="{page_no}"] .textLayer span').filter(
        has_text=f"line {line}:"
    )


def highlight_line(page: Page, line: int, page_no: int = 1) -> None:
    """The user's way: the highlight tool on (toolbar), then a drag across the line."""
    if app(page, MODE) != HIGHLIGHT:
        page.locator("#editorHighlightButton").click()
        page.wait_for_function(f"() => {MODE} === {HIGHLIGHT}")
    # A new mark stays selected, with its small toolbar (🗑) just below it, over the next
    # line: unselect it first (Esc with a mark selected only unselects; the tool stays on)
    if page.locator(".selectedEditor").count():
        page.keyboard.press("Escape")
        expect(page.locator(".selectedEditor")).to_have_count(0)
        assert app(page, MODE) == HIGHLIGHT
    before = page.locator(".annotationEditorLayer .highlightEditor").count()
    box = line_span(page, line, page_no).bounding_box()
    y = box["y"] + box["height"] / 2
    # Across the left part of the line: PDF.js's colour panel for the tool opens at the top
    # right, over the end of the first lines, and a drag released on it selects the panel
    page.mouse.move(box["x"] + 2, y)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * 0.4, y, steps=6)
    page.mouse.up()
    expect(page.locator(".annotationEditorLayer .highlightEditor")).to_have_count(before + 1)


def leave_tool(page: Page) -> None:
    """Esc until no editing tool is on (the first Esc may only unselect a mark)."""
    for _ in range(3):
        if app(page, MODE) == 0:
            return
        page.keyboard.press("Escape")
        page.wait_for_timeout(100)  # lets PDF.js switch; the loop checks the actual mode
    page.wait_for_function(f"() => {MODE} === 0")


def click_mark_on_line(page: Page, line: int, page_no: int = 1) -> None:
    """Click a highlight while reading: the reader turns the tool on and selects it."""
    box = line_span(page, line, page_no).bounding_box()
    page.mouse.click(box["x"] + 20, box["y"] + box["height"] / 2)
    expect(page.locator(".highlightEditor.selectedEditor")).to_have_count(1)


def marks_state(page: Page) -> str:
    return page.locator(".ml-marks").get_attribute("data-state") or ""


def wait_marks_saved(page: Page, timeout: float = 20_000) -> None:
    page.wait_for_function(
        "() => document.querySelector('.ml-marks')?.dataset.state === 'saved'", timeout=timeout
    )


def highlighted_lines(pdf: Path, page_index: int = 0) -> list[int]:
    """The lines of a generated test page that have a highlight saved in the PDF itself."""
    annotations = PdfReader(pdf).pages[page_index].get("/Annots") or []
    lines = []
    for ref in annotations:
        annotation = ref.get_object()
        if annotation.get("/Subtype") == "/Highlight":
            top = float(annotation["/Rect"][3])  # Helvetica 14: about 13.6 pt above the baseline
            lines.append(round((740 + 13.58 - top) / 30))
    return sorted(lines)


def screen_lines(page: Page, page_no: int = 1) -> list[int]:
    """The lines of a page that show a highlight now: new marks (editors) and saved ones not
    being edited."""
    return page.evaluate(
        """n => {
          const p = document.querySelector(`.page[data-page-number="${n}"]`);
          const lines = [...p.querySelectorAll(".textLayer span")]
            .map(s => [s.textContent.match(/line (\\d+):/)?.[1], s.getBoundingClientRect()])
            .filter(([m]) => m);
          const lineAt = r => {
            const mid = (r.top + r.bottom) / 2;
            const hit = lines.find(([, b]) => mid >= b.top - 2 && mid <= b.bottom + 2);
            return hit ? Number(hit[0]) : null;
          };
          const shown = e => !e.hidden && getComputedStyle(e).display !== "none"
            && e.getBoundingClientRect().height > 0;
          const found = new Set();
          for (const e of p.querySelectorAll(".annotationEditorLayer .highlightEditor"))
            if (shown(e)) found.add(lineAt(e.getBoundingClientRect()));
          for (const a of p.querySelectorAll(".annotationLayer .highlightAnnotation"))
            if (shown(a)) found.add(lineAt(a.getBoundingClientRect()));
          return [...found].filter(x => x !== null).sort((a, b) => a - b);
        }""",
        page_no,
    )


def leave(page: Page, how: str, stay: bool = True, timeout: float = 5) -> bool:
    """Close the tab, navigate away or reload, at once. True if the browser asked "Leave
    site?" (beforeunload); `stay` answers it with Stay (True) or Leave (False).

    The close is Playwright's page.close(run_before_unload=True): it runs the page's
    beforeunload handlers as a user's close does, but it isn't the user's ✕ or Ctrl+W, which
    the browser handles outside the page (checked by hand, not here)."""
    asked: list[str] = []
    gone: list[str] = []

    def on_dialog(dialog):
        asked.append(dialog.type)
        dialog.dismiss() if stay else dialog.accept()

    page.on("dialog", on_dialog)
    page.on("close", lambda *_: gone.append("closed"))
    page.on("framenavigated", lambda f: gone.append("left") if f == page.main_frame else None)
    if how == "close":
        page.close(run_before_unload=True)
    elif how == "navigate":
        page.evaluate("() => setTimeout(() => { location.href = 'about:blank'; }, 0)")
    elif how == "reload":
        page.evaluate("() => setTimeout(() => location.reload(), 0)")
    else:
        raise ValueError(how)
    end = time.monotonic() + timeout
    while not asked and not gone and time.monotonic() < end:
        try:
            page.wait_for_timeout(50)  # lets Playwright deliver the page's events
        except Error:
            break  # the page is closed
    if not page.is_closed():
        page.remove_listener("dialog", on_dialog)
    if not asked and not gone and not page.is_closed():
        raise TimeoutError(f"{how}: neither a warning nor the page leaving")
    return bool(asked)


def eventually(check, timeout: float = 10, message: str = "") -> object:
    """Wait (up to `timeout` s) until check() returns something true; return it. For states
    outside the page (files on disk). Raises TimeoutError with `message`."""
    end = time.monotonic() + timeout
    while True:
        value = check()
        if value:
            return value
        if time.monotonic() > end:
            raise TimeoutError(message or "the expected state never came")
        time.sleep(0.1)


def poll(page: Page, check, timeout: float = 10, message: str = "") -> object:
    """Like eventually(), but lets Playwright deliver the page's events while waiting (needed
    when the test itself answers the page's requests, see page.route)."""
    end = time.monotonic() + timeout
    while True:
        value = check()
        if value:
            return value
        if time.monotonic() > end:
            raise TimeoutError(message or "the expected state never came")
        page.wait_for_timeout(100)


def saved_marks(page: Page, server, doc_id: str, lines: list[int]) -> None:
    """Setup: highlights on `lines` of page 1, saved into the PDF."""
    open_document(page, server, doc_id)
    for line in lines:
        highlight_line(page, line)
    leave_tool(page)
    wait_marks_saved(page)
