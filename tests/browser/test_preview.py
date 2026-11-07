"""Preview Mode: a search result opened to look something up records no reading, until
开始阅读 (Start reading)."""

from helpers import eventually, leave, open_document
from playwright.sync_api import expect

PREVIEW = "&find=entrance%20pupil&preview=1"
VIEWER = "document.getElementById('viewerContainer')"


def arrival(page) -> str:
    """The search-result arrival's outcome once it's decided (lookup.js, data-ml-arrival)."""
    page.wait_for_function(
        "() => ['centred', 'left', 'elsewhere', 'not-found']"
        ".includes(document.body.dataset.mlArrival)"
    )
    return page.evaluate("() => document.body.dataset.mlArrival")


def settled_scroll(page) -> float:
    """The viewer's scroll position once it has stopped moving (5 frames alike)."""
    return page.evaluate(
        f"""() => new Promise(done => {{
          const viewer = {VIEWER};
          let last = -1, same = 0;
          const frame = () => {{
            const now = viewer.scrollTop;
            same = now === last ? same + 1 : 0;
            last = now;
            if (same >= 5) done(now); else requestAnimationFrame(frame);
          }};
          frame();
        }})"""
    )


def log_pages(library, doc):
    return sorted(
        {p for day in library.reading_log().values() for p in day.get(doc, {}).get("p", [])}
    )


def test_a_preview_records_nothing(library, server, reader_page):
    doc = library.add_book("doe-2020-optics-test", "Optics test")
    open_document(reader_page, server, doc, page_no=2, query=PREVIEW)
    expect(reader_page.locator(".ml-preview")).to_contain_text("Preview: not counted as reading")
    expect(reader_page.locator(".textLayer .highlight").first).to_be_visible()  # search kept
    for page_no in (3, 4):
        reader_page.locator("#next").click()
        reader_page.wait_for_function(f"() => PDFViewerApplication.page === {page_no}")
    reader_page.locator("#zoomInButton").click()
    assert not leave(reader_page, "close")

    # A normal tab afterwards (page 1 -> 2): its reading arrives; the preview's never did
    normal = reader_page.context.new_page()
    open_document(normal, server, doc, page_no=1)
    normal.locator("#next").click()
    normal.wait_for_function("() => PDFViewerApplication.page === 2")
    leave(normal, "close")
    eventually(lambda: "Last read: page 2" in library.readme(doc), message="normal reading lost")
    pages = eventually(lambda: log_pages(library, doc), message="no reading-log entry arrived")
    assert 2 in pages and not {3, 4} & set(pages), pages
    assert "Last read: page 4" not in library.readme(doc)


def test_start_reading_counts_from_the_current_page(library, server, reader_page):
    doc = library.add_book("doe-2020-optics-test", "Optics test")
    open_document(reader_page, server, doc, page_no=2, query=PREVIEW)
    # the arrival has positioned the reader (the match highlighted isn't enough: it's centred
    # a moment later; B19)
    assert arrival(reader_page) == "centred"
    reader_page.locator("#next").click()
    reader_page.wait_for_function("() => PDFViewerApplication.page === 3")
    assert "Last read" not in library.readme(doc)

    reader_page.locator(".ml-preview button").click()  # 开始阅读 (Start reading)
    expect(reader_page.locator(".ml-preview")).to_have_count(0)
    assert "preview=" not in reader_page.evaluate("() => location.search")  # a reload reads
    eventually(lambda: "Last read: page 3" in library.readme(doc), message="current page not saved")

    reader_page.locator("#next").click()
    reader_page.wait_for_function("() => PDFViewerApplication.page === 4")
    assert not leave(reader_page, "close")
    eventually(lambda: "Last read: page 4" in library.readme(doc), message="page 4 not saved")
    pages = eventually(lambda: log_pages(library, doc), message="no reading-log entry arrived")
    assert 4 in pages and 2 not in pages, pages


# --- B19: the user's own moves win over the arrival's positioning ------------------------------


def test_turning_the_page_at_once_is_never_undone(library, server, reader_page):
    """Next straight after a search result opens, then Start reading: the reader stays on the
    page chosen, and that page is the one saved. Before the fix, the arrival's later scroll to
    the match pulled the reader back to the result's page."""
    doc = library.add_book("doe-2020-optics-test", "Optics test")
    open_document(reader_page, server, doc, page_no=2, query=PREVIEW)
    reader_page.locator("#next").click()  # at once, before the arrival has positioned anything
    reader_page.wait_for_function("() => PDFViewerApplication.page === 3")
    reader_page.locator(".ml-preview button").click()  # 开始阅读 (Start reading)
    # whichever comes first: the arrival's outcome, or a jump back to the result's page
    reader_page.wait_for_function(
        "() => ['centred', 'left'].includes(document.body.dataset.mlArrival)"
        " || PDFViewerApplication.page === 2"
    )
    assert reader_page.evaluate("() => PDFViewerApplication.page") == 3, "pulled back"
    assert arrival(reader_page) == "left"
    reader_page.locator(".textLayer .highlight.selected").wait_for()  # the find has finished
    assert reader_page.evaluate("() => PDFViewerApplication.page") == 3, "pulled back"
    eventually(lambda: "Last read: page 3" in library.readme(doc), message="page 3 not saved")
    assert "Last read: page 2" not in library.readme(doc)


def test_scrolling_within_the_result_page_is_kept(library, server, reader_page):
    """A scroll on the result's own page straight after arriving: neither the arrival nor
    PDF.js's own scroll to the match moves the reader afterwards."""
    doc = library.add_book("doe-2020-optics-test", "Optics test")
    open_document(reader_page, server, doc, page_no=2, query=PREVIEW)
    box = reader_page.locator("#viewerContainer").bounding_box()
    reader_page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    reader_page.mouse.wheel(0, 200)  # down a little, still on page 2
    assert arrival(reader_page) == "left"
    mine = settled_scroll(reader_page)
    reader_page.locator(".textLayer .highlight.selected").wait_for()  # the find has finished
    assert settled_scroll(reader_page) == mine
    assert reader_page.evaluate("() => PDFViewerApplication.page") == 2


def test_without_any_move_the_match_is_centred(library, server, reader_page):
    """The arrival's normal behaviour: the match is brought to the middle of the viewer."""
    doc = library.add_book("doe-2020-optics-test", "Optics test")
    open_document(reader_page, server, doc, page_no=2, query=PREVIEW)
    assert arrival(reader_page) == "centred"
    settled_scroll(reader_page)
    offset = reader_page.evaluate(
        f"""() => {{
          const match = document.querySelector('.textLayer .highlight.selected')
            .getBoundingClientRect();
          const viewer = {VIEWER}.getBoundingClientRect();
          return ((match.top + match.bottom) / 2 - (viewer.top + viewer.bottom) / 2)
            / viewer.height;
        }}"""
    )
    assert abs(offset) < 0.1, f"the match is {offset:.0%} of the viewer away from its middle"
    assert reader_page.evaluate("() => PDFViewerApplication.page") == 2
    assert "Last read" not in library.readme(doc)  # still a preview: nothing recorded
