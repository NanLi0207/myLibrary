"""Opening documents by their permanent id, turning pages, zoom, and "Last read"."""

import re
import urllib.error
import urllib.request

import catalog
from helpers import app, eventually, leave, open_document
from playwright.sync_api import expect


def test_a_document_opens_by_its_id_at_the_page(library, server, reader_page):
    doc = library.add_book("doe-2020-optics-test", "Optics test")
    open_document(reader_page, server, doc, page_no=3)
    assert app(reader_page, "PDFViewerApplication.page") == 3
    assert f"id={doc}" in reader_page.url and "#page=3" in reader_page.url
    assert app(reader_page, "PDFViewerApplication.pagesCount") == 5
    expect(reader_page.locator(".ml-preview")).to_have_count(0)  # normal reading, no preview


def test_turning_pages_and_zoom(library, server, reader_page):
    doc = library.add_book("doe-2020-optics-test", "Optics test")
    open_document(reader_page, server, doc)
    page_number = reader_page.locator("#pageNumber")
    reader_page.locator("#next").click()
    expect(page_number).to_have_value("2")
    page_number.fill("4")
    page_number.press("Enter")
    reader_page.wait_for_function("() => PDFViewerApplication.page === 4")
    reader_page.locator("#previous").click()
    expect(page_number).to_have_value("3")

    scale = app(reader_page, "PDFViewerApplication.pdfViewer.currentScale")
    reader_page.locator("#zoomInButton").click()
    reader_page.wait_for_function(f"() => PDFViewerApplication.pdfViewer.currentScale > {scale}")
    reader_page.locator("#scaleSelect").select_option("page-width")
    reader_page.wait_for_function(
        "() => PDFViewerApplication.pdfViewer.currentScaleValue === 'page-width'"
    )
    assert app(reader_page, "PDFViewerApplication.page") == 3  # zoom keeps the place


def test_last_read_is_saved_and_shown_on_the_library_page(library, server, reader_page):
    doc = library.add_book("doe-2020-optics-test", "Optics test")
    open_document(reader_page, server, doc)
    assert "Last read" not in library.readme(doc)  # opening alone doesn't count
    reader_page.locator("#pageNumber").fill("4")
    reader_page.locator("#pageNumber").press("Enter")
    readme = eventually(
        lambda: "Last read: page 4" in library.readme(doc) and library.readme(doc),
        message="Last read: page 4 never written",
    )
    assert re.search(r"^Last read: page 4\b.*, \d{4}-\d{2}-\d{2}$", readme, re.M)
    books = server.post("/api/books", {})["books"]
    assert next(b for b in books if b["id"] == doc)["last_read"]["page"] == 4  # Continue's page


def test_a_page_turned_just_before_closing_is_still_saved(library, server, reader_page):
    doc = library.add_book("doe-2020-optics-test", "Optics test")
    open_document(reader_page, server, doc)
    reader_page.locator("#pageNumber").fill("5")
    reader_page.locator("#pageNumber").press("Enter")
    reader_page.wait_for_function("() => PDFViewerApplication.page === 5")
    assert not leave(reader_page, "close")  # reading is not an edit: no warning
    eventually(
        lambda: "Last read: page 5" in library.readme(doc),
        message="the page turned before closing wasn't saved (sent on close, keepalive)",
    )


def test_unknown_and_removed_documents(library, server):
    removed = library.add_book("roe-2021-gone", "Gone")
    row = library.row(removed)
    catalog.retire(library.catalog, removed, "removed", row)
    catalog.remove(library.catalog, removed)
    for doc, code, words in ((removed, 410, "removed"), (catalog.new_id(), 404, "")):
        try:
            urllib.request.urlopen(f"{server.base}/read/{doc}", timeout=10)
            raise AssertionError("expected an error page")
        except urllib.error.HTTPError as e:
            assert e.code == code
            assert words in e.read().decode("utf-8").lower()
