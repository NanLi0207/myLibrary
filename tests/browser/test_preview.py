"""Preview Mode: a search result opened to look something up records no reading, until
开始阅读 (Start reading)."""

from helpers import eventually, leave, open_document
from playwright.sync_api import expect

PREVIEW = "&find=entrance%20pupil&preview=1"


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
    # the arrival scroll to the match has finished
    reader_page.locator('.page[data-page-number="2"] .textLayer .highlight.selected').wait_for()
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
