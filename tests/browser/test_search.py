"""📚 在我的书中 (In my books): a word looked up in one book, found in another, opened at the
page with the term highlighted by PDF.js's own find (on screen only)."""

import re

import pytest
from conftest import LINES, standard_pages
from helpers import open_document
from playwright.sync_api import Error, expect

TERM = "vignetting"


def two_books(library, line: int = 4):
    """Book A mentions vignetting once (page 2, on `line`); book B on pages 3 and 5."""
    a = library.add_book(
        "doe-2020-optics-test",
        "Optics test",
        standard_pages(extra={(2, line): "Vignetting darkens the corners of the field."}),
    )
    pages_b = [[f"Chapter two text {n}: the lens has no stop here." for n in range(LINES)]] * 5
    pages_b = [list(lines) for lines in pages_b]
    pages_b[2][4] = "In this design the vignetting is about ten percent at the edge."
    pages_b[4][7] = "Some vignetting remains at the corners of the image."
    b = library.add_book("roe-2021-lens-test", "Lens test", pages_b)
    return a, b


def search_from_a(page, server, a):
    """Double-click "Vignetting" in book A, then 📚 In my books: the result list."""
    open_document(page, server, a, page_no=2)
    word = page.locator('.page[data-page-number="2"] .textLayer span').filter(has_text="Vignetting")
    word.scroll_into_view_if_needed()  # in a small window (nothing moves if it's in view)
    box = word.bounding_box()
    page.mouse.dblclick(box["x"] + 25, box["y"] + box["height"] / 2)
    popup = page.locator(".ml-popup")
    popup.get_by_role("button", name="In my books").click()
    results = popup.locator(".ml-result")
    expect(results.first).to_be_visible()
    return popup, results


def test_a_term_is_found_across_books(library, server_factory, reader_page):
    a, b = two_books(library)
    server = server_factory(wait_for_index=True)
    popup, results = search_from_a(reader_page, server, a)
    expect(popup).to_contain_text("in 2 books")
    texts = results.all_inner_texts()
    assert any("p. 2" in t and "this book" in t for t in texts)  # where we are
    assert any("p. 3" in t for t in texts) and any("p. 5" in t for t in texts)  # book B


def test_a_result_opens_the_other_book_at_the_page_highlighted(
    library, server_factory, reader_page
):
    a, b = two_books(library)
    server = server_factory(wait_for_index=True)
    _, results = search_from_a(reader_page, server, a)
    with reader_page.context.expect_page() as opened:
        results.filter(has_text="p. 3").first.click()
    other = opened.value
    other.locator('.page[data-page-number="3"] .textLayer .highlight.selected').wait_for()
    other.wait_for_function("() => PDFViewerApplication.page === 3")
    assert f"/read/{b}" not in other.url and f"id={b}" in other.url  # the reader, by id
    # the term as looked up ("vignetting", or "Vignetting" without the dictionary installed)
    assert "find=vignetting" in other.url.lower() and "preview=1" in other.url
    selected = other.locator(".textLayer .highlight.selected")
    expect(selected).to_have_text("vignetting", ignore_case=True)
    assert other.evaluate("() => PDFViewerApplication.findBar.opened")
    expect(other.locator("#findInput")).to_have_value(re.compile(TERM, re.IGNORECASE))

    # ▼ next match: page 5; ▲ back to page 3
    other.locator("#findNextButton").click()
    other.wait_for_function("() => PDFViewerApplication.findController.selected.pageIdx === 4")
    other.locator("#findPreviousButton").click()
    other.wait_for_function("() => PDFViewerApplication.findController.selected.pageIdx === 2")

    # closing the find bar clears the highlights (they were never written into the PDF)
    other.locator("#viewFindButton").click()
    expect(other.locator(".textLayer .highlight")).to_have_count(0)
    other.close()


def test_a_term_missing_from_the_page_keeps_the_page(library, server, reader_page):
    """A result's word form may not be on the page as typed: the reader stays on the page."""
    a = library.add_book("doe-2020-optics-test", "Optics test")
    open_document(reader_page, server, a, page_no=2, query="&find=astigmatism")
    expect(reader_page.locator(".ml-saved.ml-find")).to_be_visible()
    assert reader_page.evaluate("() => PDFViewerApplication.page") == 2


# --- B18: the popup stays inside the window when the results make it taller ---------------------

POPUP_BOX = """() => {
  const r = document.querySelector('.ml-popup').getBoundingClientRect();
  return {top: r.top, bottom: r.bottom, left: r.left, right: r.right};
}"""


def assert_popup_on_screen(page):
    # placed again once the results change its size (state-based: no fixed wait)
    try:
        page.wait_for_function(
            """() => { const r = document.querySelector('.ml-popup').getBoundingClientRect();
                       return r.top >= 0 && r.bottom <= innerHeight
                           && r.left >= 0 && r.right <= innerWidth; }""",
            timeout=5_000,
        )
    except Error:
        pass  # the assertions say where it is
    box = page.evaluate(POPUP_BOX)
    size = page.evaluate("() => ({width: innerWidth, height: innerHeight})")
    where = f"popup {box}, window {size}"
    assert box["top"] >= 0 and box["bottom"] <= size["height"], where
    assert box["left"] >= 0 and box["right"] <= size["width"], where


def page_of(result_text: str) -> int:
    return int(re.search(r"p\. (\d+)", result_text)[1])


@pytest.mark.parametrize("line", [0, LINES - 1], ids=["top-line", "bottom-line"])
def test_search_results_stay_on_screen(library, server_factory, reader_page, line):
    """B18: the word on the page's first or last line; the results must stay in the window."""
    a, _ = two_books(library, line=line)
    server = server_factory(wait_for_index=True)
    _, results = search_from_a(reader_page, server, a)
    expect(results).to_have_count(3)
    assert_popup_on_screen(reader_page)
    expect(results.last).to_be_in_viewport()


def test_long_results_scroll_inside_the_popup(library, server_factory, reader_page):
    """B18: in a short window the popup is taller than it may be: its list scrolls with the
    wheel, the popup stays open (also at the end of the list), and the results work by mouse
    and keyboard."""
    reader_page.set_viewport_size({"width": 900, "height": 520})
    a, b = two_books(library, line=LINES - 1)
    server = server_factory(wait_for_index=True)
    popup, results = search_from_a(reader_page, server, a)
    expect(results).to_have_count(3)
    assert_popup_on_screen(reader_page)
    scroll = """() => { const p = document.querySelector('.ml-popup');
                        return [p.scrollTop, p.scrollHeight - p.clientHeight]; }"""
    top, room = reader_page.evaluate(scroll)
    assert top == 0 and room > 0, "the popup should need scrolling in this window"

    # the wheel over the popup scrolls its list, to the end and beyond; the page stays put
    viewer = "() => document.getElementById('viewerContainer').scrollTop"
    page_scroll = reader_page.evaluate(viewer)
    box = popup.bounding_box()
    reader_page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    for _ in range(3):
        reader_page.mouse.wheel(0, room + 200)
    reader_page.wait_for_function(f"() => ({scroll})()[0] >= ({scroll})()[1] - 1")
    expect(popup).to_have_count(1)  # still open
    assert reader_page.evaluate(viewer) == page_scroll  # the wheel didn't go on to the page
    expect(results.last).to_be_in_viewport()

    # Mouse: the last result, reached by scrolling, opens its book at its page (and, as
    # always, opening a result closes the popup)
    last_page = page_of(results.last.inner_text())
    with reader_page.context.expect_page() as opened:
        results.last.click()
    by_click = opened.value
    by_click.wait_for_function(f"() => window.PDFViewerApplication?.page === {last_page}")
    assert f"id={b}" in by_click.url or f"id={a}" in by_click.url
    by_click.close()
    expect(popup).to_have_count(0)

    # Keyboard: a result is a button; Enter on it opens the book at its page
    _, results = search_from_a(reader_page, server, a)
    expect(results).to_have_count(3)
    first_page = page_of(results.first.inner_text())
    results.first.focus()
    with reader_page.context.expect_page() as opened:
        reader_page.keyboard.press("Enter")
    by_key = opened.value
    by_key.wait_for_function(f"() => window.PDFViewerApplication?.page === {first_page}")
    by_key.close()


def test_search_results_fit_a_narrow_window(library, server_factory, reader_page):
    """B18: a narrow window (a phone-width side panel): the popup fits across, too."""
    reader_page.set_viewport_size({"width": 380, "height": 700})
    a, _ = two_books(library, line=LINES - 1)
    server = server_factory(wait_for_index=True)
    _, results = search_from_a(reader_page, server, a)
    expect(results).to_have_count(3)
    assert_popup_on_screen(reader_page)
