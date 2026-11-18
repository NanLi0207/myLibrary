"""Task 4 M7: back from a note to its passage (note → PDF). A reference link M6 wrote is
followed in the reader: the passage found again and outlined for a moment, Back to where you
were, the note and its Undo untouched, reading progress left alone. Temporary libraries and
original synthetic PDFs only (the quote test PDF of test_quotes.py)."""

import json
from urllib.parse import urlsplit

import pytest
from helpers import editor_text, eventually, notes_settled, open_document, poll
from playwright.sync_api import expect
from test_quotes import ARIAL, LINES, NOTE, alt_q, links, quote_pdf, select

UUID = "0b6f6c1e-2d3a-4c5b-8e9f-0123456789ab"
RID = "r0123456789abcdef"


@pytest.fixture
def book(library):
    """M6's quote test PDF (page 1: the quote cases, page 2: numbered lines, page 3: no
    text) with two chapter notes, as test_quotes.py's book."""
    if not ARIAL.exists():
        pytest.skip("Arial (Windows) is needed for the ligature and Greek test PDF")
    doc = library.add_book("quote-2024-test", "Quote test")
    quote_pdf(library.pdf(doc))
    library.add_notes(doc, ["Basics", "Second"], {"ch01-basics.md": NOTE.encode("utf-8"),
                                                  "ch02-second.md": b"# Second\n"})  # fmt: skip
    library.cache_chapter_pages(doc, {1: 1, 2: 2})
    return doc


# --- stage 1: the pure parts (anchors.js) ------------------------------------------------------

PARSE = "(href) => window.myLibraryAnchors.parseReference(href)"


LINKS = [
    (f"/read/{UUID}?page=3&ref={RID}", "reference"),
    (f"/read/{UUID}?page=3&ref={RID}&q=the%20exit%20pupil", "reference"),
    (f"http://127.0.0.1:8765/read/{UUID}?page=3&ref={RID}", "reference"),
    (f"http://127.0.0.1:1/read/{UUID}?page=3&ref={RID}", "reference"),  # an old port
    (f"http://localhost/read/{UUID}?page=3&ref={RID}", "reference"),
    (f"https://[::1]:9000/read/{UUID}?page=3&ref={RID}#x", "reference"),
    (f"/read/{UUID}?page=3&ref={RID}&extra=1", "reference"),  # (others ignored)
    # ordinary: no ref, another host, a user name, not /read/<uuid>
    (f"/read/{UUID}?page=3", "ordinary"),
    (f"/read/{UUID}?page=3&find=pupil", "ordinary"),
    (f"http://example.com/read/{UUID}?page=3&ref={RID}", "ordinary"),
    (f"http://user:pw@127.0.0.1:8765/read/{UUID}?page=3&ref={RID}", "ordinary"),
    (f"http://127.0.0.2/read/{UUID}?page=3&ref={RID}", "ordinary"),
    (f"//127.0.0.1/read/{UUID}?page=3&ref={RID}", "ordinary"),
    (f"/read/{UUID.upper()}?page=3&ref={RID}", "ordinary"),
    (f"/read/{UUID}/x?page=3&ref={RID}", "ordinary"),
    (f"file:///read/{UUID}?page=3&ref={RID}", "ordinary"),
    ("javascript:alert(1)", "ordinary"),
    ("ch02-second.md", "ordinary"),
    # malformed: the form of a reference, but something wrong in it
    (f"/read/{UUID}?page=3&ref=r123", "malformed"),
    (f"/read/{UUID}?page=0&ref={RID}", "malformed"),
    (f"/read/{UUID}?page=x&ref={RID}", "malformed"),
    (f"/read/{UUID}?ref={RID}", "malformed"),
    (f"/read/{UUID}?page=3&ref={RID}&ref={RID}", "malformed"),
    (f"/read/{UUID}?page=3&page=4&ref={RID}", "malformed"),
    (f"/read/{UUID}?page=3&ref={RID}&q=a&q=b", "malformed"),
    (f"/read/{UUID}?page=3&ref={RID}&q={'x' * 61}", "malformed"),
]


def test_reference_links_are_told_apart(library, book, server_factory, reader_page):
    server = server_factory()
    open_document(reader_page, server, book)
    for href, kind in LINKS:
        parsed = reader_page.evaluate(PARSE, href)
        assert parsed["kind"] == kind, (href, parsed)
        if kind == "reference":
            assert (parsed["id"], parsed["rid"], parsed["page"]) == (UUID, RID, 3), href
        if kind == "malformed":
            assert parsed["id"] == UUID, href


def test_the_safe_link_is_always_this_servers_preview(library, book, server_factory,
                                                      reader_page):  # fmt: skip
    server = server_factory()
    open_document(reader_page, server, book)
    safe = (
        "(href) => window.myLibraryAnchors.safeHref(window.myLibraryAnchors.parseReference(href))"
    )
    old_port = f"http://127.0.0.1:1/read/{UUID}?page=3&ref={RID}&q=the%20exit"
    assert reader_page.evaluate(safe, old_port) == (
        f"/read/{UUID}?page=3&ref={RID}&q=the%20exit&preview=1"
    )
    assert reader_page.evaluate(safe, f"http://127.0.0.1:1/read/{UUID}?page=3&ref=bad") == (
        f"/read/{UUID}?page=3&preview=1"
    )
    assert reader_page.evaluate(safe, f"/read/{UUID}?ref=bad") == f"/read/{UUID}?preview=1"


# The page text rebuilt from getTextContent (as PDF.js's text layer builds it) must be exactly
# the drawn layer's text (layerText, what M6 anchored), with and without find highlights
SAME_TEXT = """async (n) => {
  const v = PDFViewerApplication.pdfViewer;
  const view = v.getPageView(n - 1);
  const content = await view.pdfPage.getTextContent(
    { includeMarkedContent: true, disableNormalization: true });
  const rebuilt = window.myLibraryAnchors.textFromContent(content);
  const layer = document.querySelector(`.page[data-page-number="${n}"] .textLayer`);
  return { rebuilt, drawn: window.myLibraryReader.layerText(layer).text };
}"""


def drawn(page, n):
    page.evaluate("n => { PDFViewerApplication.page = n; }", n)
    page.wait_for_function(
        'n => document.querySelector(`.page[data-page-number="${n}"] .textLayer .endOfContent`)',
        arg=n,
    )


def test_text_rebuilt_from_content_is_the_drawn_layers_text(library, book, server_factory,
                                                             reader_page):  # fmt: skip
    server = server_factory()
    page = reader_page
    open_document(page, server, book)
    for n in (1, 2, 3):
        drawn(page, n)
        same = page.evaluate(SAME_TEXT, n)
        assert same["rebuilt"] == same["drawn"], n
    # with the find bar's highlights in the layer (it splits the text into more nodes)
    page.evaluate("""() => PDFViewerApplication.eventBus.dispatch("find", {
        source: null, type: "", query: "pupil", caseSensitive: false, entireWord: false,
        highlightAll: true, findPrevious: false, matchDiacritics: true })""")
    drawn(page, 1)
    page.wait_for_function("() => document.querySelector('.textLayer .highlight')")
    same = page.evaluate(SAME_TEXT, 1)
    assert same["rebuilt"] == same["drawn"]


CANDIDATES = """([text, exact, prefix, suffix]) =>
  window.myLibraryAnchors.candidates(text, exact, prefix, suffix)"""


def test_candidates_and_their_context(library, book, server_factory, reader_page):
    server = server_factory()
    page = reader_page
    open_document(page, server, book)
    text = "aa the pupil bb. cc the pupil dd."
    found = page.evaluate(CANDIDATES, [text, "the pupil", "aa ", " bb. cc the pupil dd."])
    assert [(c["start"], c["full"]) for c in found] == [(3, True), (20, False)]
    assert page.evaluate(CANDIDATES, [text, "", "", ""]) == []
    # q only where a passage can start: not inside a word
    q = "(a) => window.myLibraryAnchors.queryMatches(a[0], a[1])"
    found = page.evaluate(q, ["the pupil; repupil pupil", "pupil"])
    assert [c["start"] for c in found] == [4, 19]
    assert page.evaluate(q, ["anything", "  "]) == []


# --- stages 3 and 4: in place, Back, finding the passage -----------------------------------------


def opened(page, server, doc):
    """The quote book open with chapter 1's note in the panel, whether the panel started open
    or closed (the --notes-closed run): opened with Alt+N, as you would."""
    open_document(page, server, doc)
    if page.evaluate("() => document.body.dataset.mlNotes") == "closed":
        page.keyboard.press("Alt+n")
        page.wait_for_function("() => document.body.dataset.mlNotes === 'open'")
    notes_settled(page)
    assert page.evaluate("() => document.body.dataset.mlNoteKey") == "file:ch01-basics.md"


def quoted(page, needle, nth=0, page_no=1) -> str:
    """Quote `needle` with M6 (Alt+Q) into the open note: the link M6 wrote."""
    select(page, needle, nth, page_no)
    alt_q(page)
    return links(editor_text(page))[-1][0]


def page_link(page, page_no) -> str:
    """M6's 引用此页 (Reference this page) for page `page_no`: the link it wrote."""
    page.evaluate("n => { PDFViewerApplication.page = n; }", page_no)
    page.wait_for_function("n => PDFViewerApplication.page === n", arg=page_no)
    page.evaluate("() => { delete document.body.dataset.mlQuote; }")
    page.locator("#mlPageRefButton").click()
    page.wait_for_function("() => document.body.dataset.mlQuote === 'inserted'")
    return links(editor_text(page))[-1][0]


def follow(page, url):
    assert page.evaluate("u => window.myLibraryNavigate.follow(u)", url)


def result(page, *states, timeout=15_000) -> str:
    page.wait_for_function(
        "s => s.includes(document.body.dataset.mlRefResult)", arg=list(states), timeout=timeout
    )
    return page.evaluate("() => document.body.dataset.mlRefResult")


def dataset(page, name):
    return page.evaluate("n => document.body.dataset[n] ?? null", name)


VIEW = """() => { const v = PDFViewerApplication.pdfViewer;
  return { top: v.container.scrollTop, left: v.container.scrollLeft,
           scale: v.currentScaleValue, page: v.currentPageNumber }; }"""


def view(page) -> dict:
    return page.evaluate(VIEW)


def still(page) -> dict:
    """The view once it stopped moving (programmatic moves settle within about a second)."""
    page.wait_for_timeout(1300)
    return view(page)


MARK_Y = """() => { const r = document.querySelector('.ml-ref-mark').getBoundingClientRect();
  return (r.top + r.bottom) / 2; }"""
LINE_Y = """([n, text]) => {
  const layer = document.querySelector(`.page[data-page-number="${n}"] .textLayer`);
  const span = [...layer.querySelectorAll('span')].find((s) => s.textContent.includes(text));
  const r = span.getBoundingClientRect(); return (r.top + r.bottom) / 2; }"""


def test_a_reference_lands_on_its_passage_in_place_and_back_returns(library, book, server_factory,
                                                                    reader_page):  # fmt: skip
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url = quoted(page, "the entrance pupil limits the aperture", nth=1)  # the second of two
    page.evaluate("() => { window.__same = 1; PDFViewerApplication.page = 2; }")
    page.wait_for_function("() => PDFViewerApplication.page === 2")
    before = still(page)
    tabs = len(page.context.pages)
    follow(page, url)
    assert result(page, "exact", "page", "found", "error") == "exact"
    assert dataset(page, "mlRefSource") == "unchanged"
    assert page.evaluate("() => window.__same") == 1  # never reloaded
    assert len(page.context.pages) == tabs  # never another tab
    y = page.evaluate(MARK_Y)
    again, repeat = (page.evaluate(LINE_Y, [1, w]) for w in ("Again:", "Repeat:"))
    assert abs(y - again) < abs(y - repeat)  # the occurrence quoted, not the other one
    assert dataset(page, "mlBack") == "1"
    page.locator(".ml-nav-back").click()
    page.wait_for_function("t => PDFViewerApplication.pdfViewer.container.scrollTop === t",
                           arg=before["top"])  # fmt: skip
    assert still(page) == before
    assert page.locator(".ml-ref-mark").count() == 0 and dataset(page, "mlBack") == "0"
    assert page.locator(".ml-nav").is_hidden()


def test_the_note_its_caret_and_undo_survive_jumps_and_back(library, book, server_factory,
                                                            reader_page):  # fmt: skip
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url = quoted(page, "the exit pupil is the image of the aperture stop")
    box = page.locator("#mlNoteText")
    box.click()
    page.keyboard.press("Control+End")
    page.keyboard.type(" typed now")
    value = editor_text(page)
    caret = page.evaluate("() => document.getElementById('mlNoteText').selectionStart")
    page.evaluate("() => { PDFViewerApplication.page = 3; }")
    page.wait_for_function("() => PDFViewerApplication.page === 3")
    follow(page, url)
    result(page, "exact")
    follow(page, url)  # (again: a second entry)
    result(page, "exact")
    page.locator(".ml-nav-back").click()
    page.locator(".ml-nav-back").click()
    focused = page.evaluate("() => document.activeElement.id")
    assert focused == "mlNoteText"  # the Back button never took the focus
    assert editor_text(page) == value
    assert page.evaluate("() => document.getElementById('mlNoteText').selectionStart") == caret
    assert dataset(page, "mlNoteKey") == "file:ch01-basics.md"
    page.keyboard.press("Control+z")  # the typing is still undone in one step
    page.wait_for_function(
        "() => !document.getElementById('mlNoteText').value.includes('typed now')"
    )
    page.keyboard.press("Control+y")
    page.wait_for_function(
        "() => document.getElementById('mlNoteText').value.includes('typed now')"
    )
    assert editor_text(page) == value


def test_consecutive_jumps_go_back_one_at_a_time_and_the_first_place_is_kept(
    library, book, server_factory, reader_page
):
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url1 = quoted(page, "the exit pupil is the image of the aperture stop")
    url2, url3 = page_link(page, 2), page_link(page, 3)
    page.evaluate("() => { PDFViewerApplication.page = 1; }")
    places = [still(page)]
    for url, wanted in ((url3, "page-reference"), (url2, "page-reference"), (url1, "exact")):
        follow(page, url)
        result(page, wanted)
        places.append(still(page))
    for expected in reversed(places[:-1]):
        page.locator(".ml-nav-back").click()
        assert still(page) == expected
    assert dataset(page, "mlBack") == "0"
    # 52 jumps: the stack keeps 50, and the original place stays at the bottom
    for k in range(52):
        follow(page, url3 if k % 2 == 0 else url2)
        result(page, "page-reference")
        page.evaluate("() => { delete document.body.dataset.mlRefResult; }")
    assert page.evaluate("() => window.myLibraryNavigate.depth()") == 50
    for _ in range(50):
        page.evaluate("() => window.myLibraryNavigate.back()")
    assert still(page) == places[0]


# Another version of the quote PDF (other bytes), its pages given as lines (None: no text)
def variant(path, pages, title="Another version"):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    pdfmetrics.registerFont(TTFont("ArialTest", str(ARIAL)))
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    c.setTitle(title)
    for lines in pages:
        if lines is None:
            c.rect(100, 300, 300, 300)
        for n, line in enumerate(lines or []):
            c.setFont("ArialTest", 14)
            c.drawString(72, 740 - 30 * n, line)
        c.showPage()
    c.save()


def edit_record(library, doc, change):
    path = library.root / ".myLibrary" / "references" / f"{doc}.json"
    data = json.loads(path.read_text("utf-8"))
    for record in data["references"].values():
        change(record)
    path.write_text(json.dumps(data), "utf-8")


ORIGINAL_P1 = [line for line in LINES if line is not None]


def test_the_quoted_bytes_are_known_by_loaded_alone(library, book, server_factory, reader_page):
    """loaded=A (the tab's bytes when quoting), fingerprint=B (the library's file then), the
    tab now shows B: never "unchanged" (plan §3.2); the page itself is shown unchanged."""
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url = quoted(page, "the exit pupil is the image of the aperture stop")
    edit_record(library, book, lambda r: r.update(loaded="a" * 64))
    follow(page, url)
    assert result(page, "verified-page", "exact", "found", "page") == "verified-page"
    assert dataset(page, "mlRefSource") == "changed"
    edit_record(library, book, lambda r: r.update(loaded=""))  # not known when quoting
    page.evaluate("() => { delete document.body.dataset.mlRefResult; }")
    follow(page, url)
    assert result(page, "verified-page", "exact", "found", "page") == "verified-page"
    assert dataset(page, "mlRefSource") == "unknown"


def reopened(page, server, doc):
    """The reader loaded again (the tab learns the PDF's bytes and merged ids anew), with the
    note open, whether the panel starts open or closed."""
    opened(page, server, doc)


def test_other_bytes_with_the_same_text_still_land_exactly(library, book, server_factory,
                                                           reader_page):  # fmt: skip
    """Like marks saved into the PDF: the file's digest changes, the page's text doesn't."""
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url = quoted(page, "the exit pupil is the image of the aperture stop")
    quote_pdf_titled = library.pdf(book)
    original = quote_pdf_titled.read_bytes()
    variant(quote_pdf_titled, [ORIGINAL_P1, None, None], title="Saved again")
    assert quote_pdf_titled.read_bytes() != original
    reopened(page, server, book)
    follow(page, url)
    assert result(page, "verified-page", "found", "exact", "page") in ("verified-page", "found")
    assert dataset(page, "mlRefSource") == "changed"


MOVED = [
    ["Moved: the exit pupil is the image of the aperture stop, said elsewhere."],  # misleading
    [LINES[0], LINES[1], LINES[2]],  # the passage itself, with its context, now on page 2
    None,
]


def test_a_moved_passage_is_found_and_the_misleading_copy_never_chosen(library, book,
                                                                       server_factory,
                                                                       reader_page):  # fmt: skip
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url = quoted(page, "the exit pupil is the image of the aperture stop")
    variant(library.pdf(book), MOVED)
    reopened(page, server, book)
    follow(page, url)
    assert result(page, "found", "choice", "page", "exact", "verified-page") == "found"
    assert dataset(page, "mlRefMark") == "2"
    expect(page.locator(".ml-nav-status")).to_contain_text("Found on page 2")


def test_a_search_cut_short_never_claims_unique(library, book, server_factory, reader_page):
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url = quoted(page, "the exit pupil is the image of the aperture stop")
    variant(library.pdf(book), [MOVED[0], [LINES[4]], MOVED[1]])  # the passage on page 3 now
    reopened(page, server, book)
    page.evaluate("""() => {  // page 3's text held back while the document is searched
      const doc = PDFViewerApplication.pdfDocument;
      const get = doc.getPage.bind(doc);
      window.__gate = new Promise((go) => { window.__release = go; });
      window.__held = 0;
      doc.getPage = async (n) => {
        const p = await get(n);
        if (n !== 3) return p;
        return new Proxy(p, { get(t, k) {
          if (k === "getTextContent") return async (...a) => {
            window.__held++; await window.__gate; return t.getTextContent(...a); };
          const v = t[k]; return typeof v === "function" ? v.bind(t) : v; } });
      };
    }""")
    follow(page, url)
    page.wait_for_function("() => window.__held > 0")
    page.locator(".ml-nav-stop").click()
    page.evaluate("() => window.__release()")
    assert result(page, "choice-incomplete", "found", "page") == "choice-incomplete"
    expect(page.locator(".ml-nav-choices")).to_contain_text("Search incomplete")


def test_two_copies_with_the_same_context_are_offered_as_a_choice(library, book, server_factory,
                                                                  reader_page):  # fmt: skip
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url = quoted(page, "the entrance pupil limits the aperture", nth=1)
    block = [LINES[8], LINES[9], "Ending line one."]
    variant(library.pdf(book), [block + block + [LINES[8]], None, None])  # twice on one page
    after = ". Ending line one. Repeat: the entrance pupil"[:32]  # (both copies' next words)
    edit_record(library, book, lambda r: r.update(suffix=after))
    reopened(page, server, book)
    follow(page, url)
    assert result(page, "choice", "found", "page") == "choice"
    choices = page.locator(".ml-nav-choice")
    # the two full-context places first ("Again:", the 2nd and 4th of the 5 matches on the
    # page), then the three others ("Repeat:"), then "only go to the page"; none chosen for you
    assert choices.count() == 6
    expect(choices.nth(0)).to_contain_text("p. 1 (2/5)")
    expect(choices.nth(1)).to_contain_text("p. 1 (4/5)")
    assert dataset(page, "mlRefMark") is None
    choices.nth(1).click()
    assert result(page, "chosen") == "chosen"
    assert dataset(page, "mlRefMark") == "1"


def test_a_hand_edited_record_is_never_taken_as_exact(library, book, server_factory, reader_page):
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url = quoted(page, "the exit pupil is the image of the aperture stop")
    edit_record(library, book, lambda r: r.update(start=r["start"] + 1, end=r["end"] + 1))
    follow(page, url)
    assert result(page, "found", "exact", "page") == "found"


# --- races ----------------------------------------------------------------------------------


def hold_gets(page) -> list:
    held = []
    page.route("**/api/references/get", lambda route: held.append(route))
    return held


def release(page, held):
    page.unroute("**/api/references/get")
    for route in held:
        try:
            route.continue_()
        except Exception:  # (its request was cancelled meanwhile: nothing to answer)
            pass


def test_a_newer_jump_supersedes_one_that_hadnt_moved(library, book, server_factory, reader_page):
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url1 = quoted(page, "the exit pupil is the image of the aperture stop")
    url3 = page_link(page, 3)
    page.evaluate("() => { PDFViewerApplication.page = 1; }")
    still(page)
    held = hold_gets(page)
    follow(page, url1)  # (already on page 1: it hasn't moved)
    poll(page, lambda: held, message="the first reference was never asked for")
    follow(page, url3)
    poll(page, lambda: len(held) == 2, message="the second reference was never asked for")
    release(page, held)
    assert result(page, "page-reference") == "page-reference"
    page.wait_for_timeout(500)
    assert dataset(page, "mlRefMark") == "3"
    assert page.evaluate("() => window.myLibraryNavigate.depth()") == 1  # no phantom entry


def test_back_while_a_passage_is_found_cancels_it(library, book, server_factory, reader_page):
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url = quoted(page, "the exit pupil is the image of the aperture stop")
    page.evaluate("() => { PDFViewerApplication.page = 3; }")
    before = still(page)
    held = hold_gets(page)
    follow(page, url)  # moves to page 1 at once, then waits for the record
    poll(page, lambda: held, message="the reference was never asked for")
    page.locator(".ml-nav-back").click()
    release(page, held)
    page.wait_for_timeout(800)
    assert still(page) == before
    assert dataset(page, "mlRefMark") is None and dataset(page, "mlRefResult") == "back"


def test_another_pdf_opened_while_finding_gets_nothing(library, book, server_factory, reader_page,
                                                       tmp_path):  # fmt: skip
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url = quoted(page, "the exit pupil is the image of the aperture stop")
    held = hold_gets(page)
    follow(page, url)
    poll(page, lambda: held, message="the reference was never asked for")
    other = tmp_path / "other.pdf"
    variant(other, [["Something else entirely."], None, None])
    page.evaluate("(d) => PDFViewerApplication.open({ data: new Uint8Array(d) })",
                  list(other.read_bytes()))  # fmt: skip
    page.wait_for_function("() => PDFViewerApplication.pdfDocument?.numPages === 3")
    release(page, held)
    page.wait_for_timeout(800)
    assert dataset(page, "mlRefMark") is None
    assert dataset(page, "mlRefResult") not in ("exact", "found", "verified-page")


def test_your_own_scroll_wins_over_the_last_fine_scroll(library, book, server_factory,
                                                        reader_page):  # fmt: skip
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url = quoted(page, "the entrance pupil limits the aperture", nth=1)
    page.evaluate("() => { PDFViewerApplication.page = 3; }")
    still(page)
    held = hold_gets(page)
    follow(page, url)
    poll(page, lambda: held, message="the reference was never asked for")
    box = page.locator("#viewerContainer").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 3, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, 60)
    mine = still(page)
    release(page, held)
    assert result(page, "exact") == "exact"
    assert dataset(page, "mlRefMark") == "1"  # still outlined
    assert still(page)["top"] == mine["top"]  # but not scrolled away from your place


def test_typing_in_the_note_while_finding_cancels_nothing(library, book, server_factory,
                                                          reader_page):  # fmt: skip
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url = quoted(page, "the entrance pupil limits the aperture", nth=1)
    page.evaluate("() => { PDFViewerApplication.page = 3; }")
    still(page)
    held = hold_gets(page)
    follow(page, url)
    poll(page, lambda: held, message="the reference was never asked for")
    landed = still(page)
    page.locator("#mlNoteText").click()
    page.keyboard.type(" more")
    release(page, held)
    assert result(page, "exact") == "exact"
    assert still(page)["top"] != landed["top"]  # the passage was brought into view
    assert " more" in editor_text(page)


# --- without a record: the link's q, at a passage's start --------------------------------------


def test_without_a_record_the_links_text_is_used_at_a_passage_start(library, book,
                                                                    server_factory,
                                                                    reader_page):  # fmt: skip
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url = quoted(page, "the exit pupil is the image of the aperture stop")
    (library.root / ".myLibrary" / "references" / f"{book}.json").unlink()
    follow(page, url)
    assert result(page, "query", "page", "choice") == "query"
    assert dataset(page, "mlRefMark") == "1"
    base = url.split("&q=")[0]
    page.evaluate("() => { delete document.body.dataset.mlRefResult; }")
    follow(page, base + "&q=xit%20pupil")  # inside "exit": never a passage's start
    assert result(page, "page", "query", "choice") == "page"
    assert dataset(page, "mlRefReason") == "no-file"
    page.evaluate("() => { delete document.body.dataset.mlRefResult; }")
    follow(page, base + "&q=the%20entrance%20pupil")  # twice on the page: a choice
    assert result(page, "choice", "query", "page") == "choice"


# --- stage 5: reading progress left alone ------------------------------------------------------


def position_requests(page) -> list:
    seen = []
    page.on("request", lambda r: seen.append(json.loads(r.post_data or "{}"))
            if r.url.endswith("/api/position") else None)  # fmt: skip
    return seen


LATE = """([name, n]) => { const app = PDFViewerApplication;
  if (name === 'pagechanging') app.eventBus.dispatch('pagechanging',
    { source: app.pdfViewer, pageNumber: n, pageLabel: null, previous: app.page });
  else app.eventBus.dispatch('updateviewarea',
    { source: app.pdfViewer, location: app.pdfViewer._location }); }"""


def late_events(page, n):
    page.evaluate(LATE, ["pagechanging", n])
    page.evaluate(LATE, ["updateviewarea", n])


def test_jumps_back_clicks_and_late_events_never_decide_a_position(library, book, server_factory,
                                                                   reader_page):  # fmt: skip
    server = server_factory()
    page = reader_page
    opened(page, server, book)  # a chapter opened only to look at
    url3 = page_link(page, 3)
    page.evaluate("() => { PDFViewerApplication.page = 1; }")
    still(page)
    readme = library.readme(book)
    sent = position_requests(page)
    follow(page, url3)
    result(page, "page-reference")
    late_events(page, 2)  # before the settling limit
    page.wait_for_timeout(1200)
    late_events(page, 2)  # after it
    page.locator(".ml-nav-back").click()
    late_events(page, 3)
    page.wait_for_timeout(1200)
    box = page.locator("#viewerContainer").bounding_box()
    page.mouse.click(box["x"] + 40, box["y"] + 40)  # a click that moves nothing
    late_events(page, 3)
    page.wait_for_timeout(2600)  # (past the 2 s debounce)
    page.evaluate("() => window.dispatchEvent(new Event('pagehide'))")  # leaving: a flush
    page.wait_for_timeout(300)
    assert sent == [] and dataset(page, "mlDecision") is None
    assert library.readme(book) == readme


def test_your_own_move_after_back_decides_once_whatever_comes_late(library, book,
                                                                   server_factory,
                                                                   reader_page):  # fmt: skip
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url3 = page_link(page, 3)
    page.evaluate("() => { PDFViewerApplication.page = 1; }")
    still(page)
    sent = position_requests(page)
    follow(page, url3)
    result(page, "page-reference")
    page.locator(".ml-nav-back").click()
    still(page)
    page.locator("#next").click()  # your own move: page 2
    page.wait_for_function("() => PDFViewerApplication.page === 2")
    late_events(page, 1)  # the restoration's events, late
    late_events(page, 3)
    poll(page, lambda: sent, timeout=6, message="your own move decided nothing")
    page.wait_for_timeout(2500)
    assert [s["page"] for s in sent] == [2]
    eventually(lambda: "Last read: page 2" in library.readme(book), message="page 2 not saved")


def test_continue_reading_here_decides_this_page(library, book, server_factory, reader_page):
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url3 = page_link(page, 3)
    page.evaluate("() => { PDFViewerApplication.page = 1; }")
    still(page)
    sent = position_requests(page)
    follow(page, url3)
    result(page, "page-reference")
    page.locator(".ml-nav-here").click()
    poll(page, lambda: sent, message="Continue reading here decided nothing")
    assert sent[0]["page"] == 3 and dataset(page, "mlBack") == "0"
    eventually(lambda: "Last read: page 3" in library.readme(book), message="page 3 not saved")


def test_a_reference_opened_from_outside_is_a_preview(library, book, server_factory, reader_page):
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url = quoted(page, "the exit pupil is the image of the aperture stop")
    other = page.context.new_page()
    other.goto(url)  # (as from VS Code or the library page: /read/ with the reference)
    other.wait_for_function("() => document.body.dataset.mlRefResult === 'exact'", timeout=20_000)
    assert "preview=1" in other.url and "ref=" in other.url
    expect(other.locator(".ml-preview")).to_be_visible()
    assert other.evaluate("() => window.myLibraryNavigate.depth()") == 0  # no Back entry
    other.locator(".ml-preview button").click()  # 开始阅读 (Start reading)
    search = other.evaluate("() => location.search")
    assert all(k not in search for k in ("preview=", "ref=", "refdoc=", "q="))
    eventually(lambda: "Last read: page 1" in library.readme(book), message="Start reading lost")
    other.close()


# --- stage 5: pages chosen as PDF.js chooses them; decisions made once ---------------------------

STATE = """() => { const cur = PDFViewerApplication.pdfViewer.currentPageNumber;
  return { cur, replica: window.myLibraryTracking.pdfPage(cur),
           decision: document.body.dataset.mlDecision || null }; }"""


def moves_decide_pdfjs_pages(page, steps):
    """Each step a move of your own; after each, the decision (if a new one) is PDF.js's
    current page, the replica agrees, and no page is decided twice in a row. The decisions."""
    decided, last = [], page.evaluate(STATE)["decision"]
    for kind, value in steps:
        if kind == "wheel":
            page.mouse.wheel(0, value)
        elif kind == "key":
            page.keyboard.press(value)
        elif kind == "click":
            page.locator(value).click()
        else:
            field = page.locator("#pageNumber")
            field.fill(value)
            field.press("Enter")
        page.wait_for_timeout(350)
        state = page.evaluate(STATE)
        assert state["replica"] == state["cur"], (kind, value, state)
        if state["decision"] != last:
            number = int(state["decision"].split(":")[1])
            assert number == state["cur"], (kind, value, state)
            assert not decided or decided[-1] != number, (kind, value, decided)
            decided.append(number)
            last = state["decision"]
    return decided


def test_pages_are_decided_as_pdfjs_chooses_them_at_25_and_100_percent(library, server_factory,
                                                                       reader_page):  # fmt: skip
    from conftest import standard_pages

    doc = library.add_book("zoom-2024-pages", "Zoom", standard_pages(40))
    server = server_factory()
    page = reader_page
    open_document(page, server, doc)
    page.evaluate("() => { PDFViewerApplication.pdfViewer.currentScaleValue = '0.25'; }")
    page.wait_for_timeout(500)
    box = page.locator("#viewerContainer").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)  # (focus)
    steps = [("wheel", 120)] * 4 + [("wheel", -240), ("key", "PageDown"), ("key", "PageDown"),
             ("key", "ArrowDown"), ("key", "n"), ("key", "p"), ("key", "End"), ("key", "Home"),
             ("click", "#next"), ("click", "#next"), ("click", "#previous"), ("field", "17"),
             ("field", "40"), ("click", "#previous")]  # fmt: skip
    decided = moves_decide_pdfjs_pages(page, steps)
    assert decided and decided[-1] == 39  # Previous at the end: the page changed, no scroll
    page.evaluate("() => { PDFViewerApplication.pdfViewer.currentScaleValue = '1'; }")
    page.wait_for_timeout(500)
    more = moves_decide_pdfjs_pages(page, [("click", "#previous"), ("wheel", 400),
                                           ("key", "PageDown"), ("field", "5")])  # fmt: skip
    assert more and more[-1] == 5


def recorded(page) -> list:
    bodies = []
    page.route("**/api/position", lambda route: (bodies.append(json.loads(
        route.request.post_data)), route.continue_()))  # fmt: skip
    return bodies


TAB_B = "0f0e0d0c-0b0a-4908-8706-050403020100"


def test_a_decision_answered_is_never_sent_again(library, server_factory, reader_page):
    """A newer revision learned through the idempotent answer to a retry never sends the old
    page again, nor a new decision for it (Codex scenario 1)."""
    doc = library.add_book("doe-2020-optics-test", "Optics test")
    server = server_factory()
    page = reader_page
    open_document(page, server, doc)
    bodies, lost = [], []

    def handle(route):
        bodies.append(json.loads(route.request.post_data))
        if not lost:  # the first one reaches the server and is accepted, but its answer is lost
            lost.append(route.fetch().json())
            route.abort()
        else:
            route.continue_()

    page.route("**/api/position", handle)
    page.locator("#next").click()  # a decision: page 2
    poll(page, lambda: lost, timeout=8, message="the decision was never sent")
    rev = lost[0]["rev"]
    server.post("/api/position", {"id": doc, "page": 4, "tab": TAB_B, "seq": 1, "base": rev})
    poll(page, lambda: len(bodies) >= 2, message="the decision was never retried")
    assert bodies[1] == bodies[0]  # the same request, the same authority
    page.wait_for_timeout(500)
    for _ in range(2):  # leaving, hiding: nothing new, the answered decision not again
        page.evaluate("() => window.dispatchEvent(new Event('pagehide'))")
    page.wait_for_timeout(500)
    assert len(bodies) == 2
    assert "Last read: page 4" in library.readme(doc)


def test_a_refused_decision_is_dropped_and_never_resent(library, server_factory, reader_page):
    """A newer revision learned through a stale answer: nothing is sent again (scenario 2);
    a decision still unanswered when leaving goes out as it is."""
    doc = library.add_book("doe-2020-optics-test", "Optics test")
    server = server_factory()
    page = reader_page
    open_document(page, server, doc)
    rev = server.post("/api/document/ids", {"id": doc})["position_rev"]
    server.post("/api/position", {"id": doc, "page": 4, "tab": TAB_B, "seq": 1, "base": rev})
    bodies = recorded(page)
    page.locator("#next").click()  # decided without knowing B's write
    poll(page, lambda: bodies, timeout=8, message="the decision was never sent")
    page.wait_for_timeout(500)
    page.evaluate("() => window.dispatchEvent(new Event('pagehide'))")
    page.wait_for_timeout(500)
    assert len(bodies) == 1 and "Last read: page 4" in library.readme(doc)
    # unanswered when leaving: the keepalive carries the very same body
    page.unroute("**/api/position")
    held = []
    page.route("**/api/position", lambda route: held.append(route))
    page.locator("#next").click()
    poll(page, lambda: held, timeout=8, message="the next decision was never sent")
    page.evaluate("() => window.dispatchEvent(new Event('pagehide'))")
    poll(page, lambda: len(held) >= 2, message="the leaving flush sent nothing")
    first, again = (json.loads(r.request.post_data) for r in held[:2])
    assert first == again and first["page"] == 3
    for route in held:
        route.continue_()


def test_two_moves_within_the_debounce_send_only_the_second(library, server_factory, reader_page):
    doc = library.add_book("doe-2020-optics-test", "Optics test")
    server = server_factory()
    page = reader_page
    open_document(page, server, doc)
    bodies = recorded(page)
    page.locator("#next").click()
    page.locator("#next").click()
    poll(page, lambda: bodies, timeout=8, message="nothing was sent")
    page.wait_for_timeout(2500)
    assert [b["page"] for b in bodies] == [3] and bodies[0]["seq"] == 2
    page.evaluate("() => window.dispatchEvent(new Event('pagehide'))")  # nothing waiting
    page.wait_for_timeout(400)
    assert len(bodies) == 1


# --- stage 6: links in the note, followed --------------------------------------------------------


def in_note(page, markdown):
    """Put `markdown` at the end of the open note (typed, as you would) and show the preview."""
    page.locator("#mlNoteText").click()
    page.keyboard.press("Control+End")
    page.keyboard.insert_text(markdown)
    page.keyboard.press("Alt+p")
    page.wait_for_function("() => document.body.dataset.mlNoteView === 'preview'")


def test_a_reference_clicked_in_the_preview_goes_there_in_place(library, book, server_factory,
                                                                reader_page):  # fmt: skip
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url = quoted(page, "the exit pupil is the image of the aperture stop")
    page.evaluate("() => { window.__same = 1; PDFViewerApplication.page = 3; }")
    page.keyboard.press("Alt+p")
    page.wait_for_function("() => document.body.dataset.mlNoteView === 'preview'")
    link = page.locator(".ml-note-preview a").last
    assert link.get_attribute("href").startswith(f"/read/{book}?page=1&ref=")
    assert link.get_attribute("href").endswith("&preview=1")
    tabs = len(page.context.pages)
    value = editor_text(page)
    link.click()
    assert result(page, "exact") == "exact"
    assert page.evaluate("() => window.__same") == 1 and len(page.context.pages) == tabs
    assert editor_text(page) == value and dataset(page, "mlNoteView") == "preview"
    assert url  # (the M6 link the preview drew)


def test_ctrl_click_in_the_source_follows_a_reference(library, book, server_factory, reader_page):
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    quoted(page, "the exit pupil is the image of the aperture stop")
    page.evaluate("() => { PDFViewerApplication.page = 3; }")
    value = editor_text(page)
    target = page.locator("#mlNoteText")
    # the caret inside the link M6 wrote, then a Ctrl+click there
    box = target.bounding_box()
    target.click()
    inside = value.rfind("](") + 6
    page.evaluate("i => document.getElementById('mlNoteText').setSelectionRange(i, i)", inside)
    page.keyboard.down("Control")
    page.evaluate("""() => { const t = document.getElementById('mlNoteText');
      t.dispatchEvent(new MouseEvent('click', { bubbles: true, ctrlKey: true })); }""")
    page.keyboard.up("Control")
    assert result(page, "exact") == "exact"
    assert editor_text(page) == value and box


def test_a_reference_to_another_document_opens_a_preview_tab(library, book, server_factory,
                                                             reader_page):  # fmt: skip
    other = library.add_book("other-2023-book", "Other book")
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    in_note(page, f"\n[elsewhere](http://127.0.0.1:1/read/{other}?page=2&ref={RID})\n")
    value = editor_text(page)
    with page.context.expect_page() as popup:
        page.locator(".ml-note-preview a", has_text="elsewhere").click()
    tab = popup.value
    tab.wait_for_load_state()
    assert f"id={other}" in tab.url and "preview=1" in tab.url and f"ref={RID}" in tab.url
    assert f":{urlsplit(server.base).port}/" in tab.url  # this server, never the old port
    assert editor_text(page) == value and dataset(page, "mlRefResult") is None
    tab.close()


def test_without_navigate_js_the_link_still_opens_this_servers_preview(library, book,
                                                                       server_factory,
                                                                       reader_page):  # fmt: skip
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    page.evaluate("() => { delete window.myLibraryNavigate; }")
    in_note(page, f"\n[old port](http://127.0.0.1:1/read/{book}?page=2&ref={RID})\n")
    link = page.locator(".ml-note-preview a", has_text="old port")
    assert link.get_attribute("href") == f"/read/{book}?page=2&ref={RID}&preview=1"
    with page.context.expect_page() as popup:
        link.click()
    tab = popup.value
    tab.wait_for_load_state()
    assert "preview=1" in tab.url and f":{urlsplit(server.base).port}/" in tab.url
    tab.close()


def test_malformed_and_ordinary_links(library, book, server_factory, reader_page):
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    in_note(page, f"\n[bad](http://127.0.0.1:1/read/{book}?page=2&ref=nope)\n"
                  f"[found](/read/{book}?page=2&find=pupil)\n")  # fmt: skip
    bad = page.locator(".ml-note-preview a", has_text="bad")
    assert bad.get_attribute("href") == f"/read/{book}?page=2&preview=1"
    assert "ml-link-invalid" in bad.get_attribute("class")
    found = page.locator(".ml-note-preview a", has_text="found")
    assert found.get_attribute("href") == f"/read/{book}?page=2&find=pupil"  # as before M7
    with page.context.expect_page() as popup:
        bad.click()
    tab = popup.value
    tab.wait_for_load_state()
    assert "preview=1" in tab.url and "ref=" not in tab.url
    tab.close()
    with page.context.expect_page() as popup:
        found.click()
    tab = popup.value
    tab.wait_for_load_state()
    assert "find=pupil" in tab.url and "preview" not in tab.url  # ordinary: unchanged
    tab.close()
    with page.context.expect_page() as popup:  # middle-click: the safe preview link
        bad.click(button="middle")
    popup.value.close()


def test_merged_and_removed_documents(library, book, server_factory, reader_page):
    import catalog

    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url = quoted(page, "the exit pupil is the image of the aperture stop")
    # a document merged into this one: its records stay under its old id (DEVELOPMENT_SPEC 9.2)
    old = "1d2c3b4a-5f6e-4d7c-8b9a-a1b2c3d4e5f6"
    folder = library.root / ".myLibrary" / "references"
    data = json.loads((folder / f"{book}.json").read_text("utf-8"))
    for record in data["references"].values():
        record["doc"] = old
    (folder / f"{old}.json").write_text(json.dumps(data), "utf-8")
    row = library.row(book) | {"id": old, "slug": "old-copy"}
    catalog.retire(library.catalog, old, "merged", row, into=book)
    reopened(page, server, book)  # (the tab learns its merged ids at load)
    tabs = len(page.context.pages)
    follow(page, url.replace(book, old))
    assert result(page, "exact") == "exact" and len(page.context.pages) == tabs
    # a removed document: its link opens a tab that says so
    gone = library.add_book("gone-2020-book", "Gone book")
    catalog.retire(library.catalog, gone, "removed", library.row(gone))
    catalog.remove(library.catalog, gone)
    with page.context.expect_page() as popup:
        follow(page, f"/read/{gone}?page=1&ref={RID}")
    tab = popup.value
    tab.wait_for_load_state()
    expect(tab.locator("body")).to_contain_text("Gone book")
    tab.close()


# --- the plan's remaining cases ----------------------------------------------------------------


def ten_pages(library) -> str:
    from conftest import standard_pages

    return library.add_book("ten-2024-pages", "Ten pages", standard_pages(10))


def decision(page):
    return page.evaluate("() => document.body.dataset.mlDecision || null")


def click_still(page):
    """Your own click in the PDF that moves nothing (engagement, a sample of the view)."""
    box = page.locator("#viewerContainer").bounding_box()
    page.mouse.click(box["x"] + 30, box["y"] + 30)


def unannounced_scroll(page, n):
    """A move nobody announced and you didn't make (as a layout change would cause)."""
    page.evaluate("n => PDFViewerApplication.pdfViewer.scrollPageIntoView({ pageNumber: n })", n)
    page.wait_for_timeout(600)


def test_a_layout_change_you_didnt_make_decides_no_position(library, server_factory, reader_page):
    doc = ten_pages(library)
    server = server_factory()
    page = reader_page
    open_document(page, server, doc)
    page.evaluate("() => { PDFViewerApplication.pdfViewer.currentScaleValue = '1'; }")
    page.wait_for_timeout(500)
    # the control: after your input, a move with the layout unchanged is decided
    click_still(page)
    unannounced_scroll(page, 4)
    assert decision(page).endswith(":4")
    # a resize between your input and the move: uncertain, nothing decided
    click_still(page)
    size = page.viewport_size
    page.set_viewport_size({"width": size["width"] - 200, "height": size["height"]})
    page.wait_for_timeout(400)
    unannounced_scroll(page, 6)
    assert decision(page).endswith(":4")
    # a zoom you didn't make (a script's), then a move: nothing decided
    click_still(page)
    page.evaluate("() => { PDFViewerApplication.pdfViewer.currentScaleValue = '0.8'; }")
    page.wait_for_timeout(400)
    unannounced_scroll(page, 8)
    assert decision(page).endswith(":4")
    # a zoom you made (the toolbar), then your own move: decided
    page.locator("#zoomOutButton").click()
    page.wait_for_timeout(400)
    page.locator("#next").click()
    page.wait_for_timeout(600)
    current = page.evaluate("() => PDFViewerApplication.pdfViewer.currentPageNumber")
    assert decision(page).endswith(f":{current}") and current != 4


# Each SHA-256 digest held until released by its number (navigate.js checks a page's text with
# one after its record arrived: a navigation held there is halfway)
HOLD_DIGESTS = """() => { window.__digests = [];
  const digest = crypto.subtle.digest.bind(crypto.subtle);
  crypto.subtle.digest = (...args) => new Promise((go) => {
    window.__digests.push(() => go(digest(...args))); }); }"""


def test_a_move_superseded_halfway_never_finishes(library, book, server_factory, reader_page):
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    drawn(page, 2)  # (its text layer drawn before selecting in it)
    url2 = quoted(page, "line 3: the entrance pupil", page_no=2)
    url1 = quoted(page, "the entrance pupil limits the aperture", nth=1)
    page.evaluate("() => { PDFViewerApplication.page = 3; }")
    still(page)
    page.wait_for_timeout(2300)  # (the setup's own moves decided after the Alt+Q: sent by now)
    sent = position_requests(page)
    page.evaluate(HOLD_DIGESTS)
    follow(page, url2)  # to page 2; its record arrives; it waits at its page's digest...
    page.wait_for_function("() => window.__digests.length === 1")
    follow(page, url1)  # ... and is superseded there: to page 1 for the second
    page.wait_for_function("() => window.__digests.length === 2")
    page.evaluate("() => window.__digests[1]()")  # the second finishes first
    assert result(page, "exact") == "exact"
    landed = still(page)
    page.evaluate("() => window.__digests[0]()")  # then the first one's digest comes back
    late_events(page, 2)  # with its move's events, late
    page.wait_for_timeout(800)
    assert still(page) == landed and landed["page"] == 1
    assert dataset(page, "mlRefMark") == "1" and dataset(page, "mlRefResult") == "exact"
    assert page.evaluate("() => window.myLibraryNavigate.depth()") == 2  # both had moved
    assert sent == []


DECISIONS = """() => { window.__decided = [];
  new MutationObserver(() => window.__decided.push(document.body.dataset.mlDecision))
    .observe(document.body, { attributes: true, attributeFilter: ['data-ml-decision'] }); }"""


def decided_pages(page) -> list[int]:
    return [int(d.split(":")[1]) for d in page.evaluate("() => window.__decided") if d]


def test_a_held_key_and_a_scrollbar_drag_decide_the_pages_passed(library, server_factory,
                                                                 reader_page):  # fmt: skip
    doc = ten_pages(library)
    server = server_factory()
    page = reader_page
    open_document(page, server, doc)
    page.evaluate("() => { PDFViewerApplication.pdfViewer.currentScaleValue = '0.5'; }")
    page.wait_for_timeout(500)
    click_still(page)  # (the focus in the PDF)
    page.evaluate(DECISIONS)
    for _ in range(40):  # a key held down: its repeats
        page.keyboard.down("ArrowDown")
        page.wait_for_timeout(40)
    page.keyboard.up("ArrowDown")
    page.wait_for_timeout(600)
    pages = decided_pages(page)
    current = page.evaluate("() => PDFViewerApplication.pdfViewer.currentPageNumber")
    assert len(pages) >= 2 and pages == sorted(pages) and pages[-1] == current, pages
    assert all(a != b for a, b in zip(pages, pages[1:], strict=False))
    # A scrollbar drag: one press, then the view keeps moving with no further input. (Playwright's
    # headless browser hides scrollbars, so the drag's scrolling is done for it, step by step,
    # between your real press and release: what the page sees of a drag)
    box = page.locator("#viewerContainer").bounding_box()
    top = page.evaluate("() => PDFViewerApplication.pdfViewer.container.scrollTop")
    page.mouse.move(box["x"] + box["width"] - 8, box["y"] + 60)
    page.mouse.down()
    for _ in range(15):
        page.evaluate("() => { PDFViewerApplication.pdfViewer.container.scrollTop += 120; }")
        page.wait_for_timeout(60)
    page.mouse.up()
    page.wait_for_timeout(600)
    assert page.evaluate("() => PDFViewerApplication.pdfViewer.container.scrollTop") > top + 1000
    more = decided_pages(page)[len(pages) :]
    current = page.evaluate("() => PDFViewerApplication.pdfViewer.currentPageNumber")
    assert more and more[-1] == current and current > pages[-1], (pages, more)
    assert all(a != b for a, b in zip(more, more[1:], strict=False))


HOLD_FRAMES = """() => { const queued = []; window.__raf = window.requestAnimationFrame;
  window.requestAnimationFrame = (callback) => { queued.push(callback); return queued.length; };
  window.__releaseFrames = () => { window.requestAnimationFrame = window.__raf;
    queued.forEach((callback) => window.__raf(callback)); }; }"""


def test_your_input_while_pdfjs_has_an_update_pending_decides_nothing(library, server_factory,
                                                                      reader_page):  # fmt: skip
    doc = ten_pages(library)
    server = server_factory()
    page = reader_page
    open_document(page, server, doc)
    page.locator("#next").click()  # your reading: page 2 decided
    page.wait_for_timeout(600)
    assert decision(page).endswith(":2")
    page.evaluate(HOLD_FRAMES)  # PDF.js updates its page on the next animation frame
    page.evaluate("() => PDFViewerApplication.pdfViewer.container.scrollTop += 4000")
    stale = page.evaluate("() => { const v = PDFViewerApplication.pdfViewer;"
                          " return [v.currentPageNumber, window.myLibraryTracking.pdfPage("
                          "v.currentPageNumber)]; }")  # fmt: skip
    assert stale[0] != stale[1]  # PDF.js hasn't caught up with the view yet
    click_still(page)  # your click now: the view it samples isn't one PDF.js has seen
    page.evaluate("() => window.__releaseFrames()")
    page.wait_for_timeout(800)
    assert decision(page).endswith(":2")  # PDF.js's catching up is not your move


def test_the_pinned_pdfjs_has_its_page_list(library, server_factory, reader_page):
    """The guard of plan §5.3 rule 5: if a PDF.js upgrade drops or changes the internal
    pdfViewer._getVisiblePages, this fails (recheck lookup.js's replica then)."""
    doc = ten_pages(library)
    server = server_factory()
    page = reader_page
    open_document(page, server, doc)
    assert page.evaluate("() => typeof PDFViewerApplication.pdfViewer._getVisiblePages") == (
        "function"
    )
    for n in (1, 4, 10):
        page.evaluate("n => { PDFViewerApplication.page = n; }", n)
        page.wait_for_timeout(300)
        cur, replica = page.evaluate("() => { const v = PDFViewerApplication.pdfViewer;"
                                     " return [v.currentPageNumber, window.myLibraryTracking"
                                     ".pdfPage(v.currentPageNumber)]; }")  # fmt: skip
        assert cur == replica == n


def test_without_the_page_list_nothing_breaks_and_nothing_is_guessed(library, book,
                                                                     server_factory,
                                                                     reader_page):  # fmt: skip
    server = server_factory()
    page = reader_page
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    opened(page, server, book)
    url3 = page_link(page, 3)
    page.evaluate("() => { PDFViewerApplication.page = 1; }")
    still(page)
    sent = position_requests(page)
    # A PDF.js upgrade that renamed it: PDF.js keeps working (its own calls), but myLibrary's
    # code (lookup.js, navigate.js) no longer finds it
    page.evaluate(r"""() => { const v = PDFViewerApplication.pdfViewer;
      const real = v._getVisiblePages;
      Object.defineProperty(v, "_getVisiblePages", { configurable: true, get() {
        return /reader\/(lookup|navigate)\.js/.test(new Error().stack || "") ? undefined : real;
      } }); }""")
    page.wait_for_timeout(2300)  # (the setup's own moves decided after the Alt+Q: sent by now)
    sent.clear()
    page.locator("#next").click()  # your move, but its page can't be checked: not guessed
    page.wait_for_timeout(2600)
    assert sent == [] and decision(page) is None
    follow(page, url3)  # following references still works
    assert result(page, "page-reference", "error") == "page-reference"
    page.locator(".ml-nav-back").click()
    still(page)
    assert errors == [], errors


CLOCK = """(() => { window.__shift = 0;
  Date.now = () => 1800000000000 + window.__shift; })()"""  # (the same frozen time in each tab)


def test_browser_clocks_never_order_positions(library, server_factory, reader_page):
    import re

    doc = ten_pages(library)
    server = server_factory()
    reader_page.context.add_init_script(CLOCK)
    a = reader_page
    open_document(a, server, doc)
    b = a.context.new_page()
    open_document(b, server, doc)  # (both learned the same revision)

    def go(tab, n, shift):
        tab.evaluate("s => { window.__shift = s; }", shift)
        field = tab.locator("#pageNumber")
        field.fill(str(n))
        field.press("Enter")
        tab.wait_for_function("n => PDFViewerApplication.page === n", arg=n)
        tab.wait_for_timeout(400)
        # Sent now (leaving's flush), and waited for until the server has answered it (written
        # or refused as stale), up to 10 s: never a fixed delay (CI run 44110143759 read the
        # README 0.7 s after a request that hadn't been answered yet)
        position = lambda r: r.url.endswith("/api/position")  # noqa: E731
        with tab.expect_response(position, timeout=10_000) as answered:
            tab.evaluate("() => window.dispatchEvent(new Event('pagehide'))")
        assert answered.value.ok, answered.value.status
        assert json.loads(answered.value.request.post_data)["page"] == n  # (this step's)

    def last():
        return int(re.search(r"Last read: page (\d+)", library.readme(doc))[1])

    go(a, 2, 0)
    assert last() == 2
    go(b, 3, -36_000_000)  # B ten hours behind, deciding without knowing A's write: refused
    assert last() == 2
    go(b, 4, -36_000_000)  # B's next decision, knowing it: written
    assert last() == 4
    go(a, 7, 36_000_000)  # A ten hours ahead: still refused, B wrote after A's revision
    assert last() == 4
    go(a, 8, 36_000_000)
    assert last() == 8
    go(b, 9, 0)  # equal clocks: the server's order decides, as always
    assert last() == 8
    go(b, 5, 0)
    assert last() == 5
    b.close()


# --- Codex implementation review: three blockers -----------------------------------------------


def page_mode(page):
    """PDF.js's page-at-a-time scrolling (ScrollMode.PAGE): one page shown at a time."""
    page.evaluate("() => { PDFViewerApplication.pdfViewer.scrollMode = 3; }")
    page.wait_for_function("() => PDFViewerApplication.pdfViewer.scrollMode === 3")


def test_back_in_page_at_a_time_mode_returns_to_the_page(library, book, server_factory,
                                                         reader_page):  # fmt: skip
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url1 = quoted(page, "the entrance pupil limits the aperture", nth=1)
    url2 = page_link(page, 2)
    page_mode(page)
    page.evaluate("() => { PDFViewerApplication.page = 3; }")
    page.wait_for_function("() => PDFViewerApplication.page === 3")
    page.evaluate("() => { PDFViewerApplication.pdfViewer.container.scrollTop += 40; }")
    origin = still(page)
    assert origin["page"] == 3
    follow(page, url1)  # one jump, then Back
    result(page, "exact")
    assert still(page)["page"] == 1
    page.locator(".ml-nav-back").click()
    assert still(page) == origin
    follow(page, url2)  # two jumps in a row, then Back twice
    result(page, "page-reference")
    middle = still(page)
    assert middle["page"] == 2
    page.evaluate("() => { delete document.body.dataset.mlRefResult; }")
    follow(page, url1)
    result(page, "exact")
    page.locator(".ml-nav-back").click()
    assert still(page) == middle
    page.locator(".ml-nav-back").click()
    assert still(page) == origin
    assert dataset(page, "mlBack") == "0"


def seconds_read(library, doc) -> int:
    return sum(day.get(doc, {}).get("s", 0) for day in library.reading_log().values())


def test_continue_reading_here_counts_reading_without_another_move(library, book,
                                                                   server_factory,
                                                                   reader_page):  # fmt: skip
    server = server_factory()
    page = reader_page
    page.clock.install()  # (the reading tick moved on by the test)
    opened(page, server, book)
    url3 = page_link(page, 3)
    page.evaluate("() => { PDFViewerApplication.page = 1; }")
    still(page)
    follow(page, url3)
    result(page, "page-reference")
    still(page)
    page.locator(".ml-nav-here").click()  # 在这里继续阅读: nothing else done afterwards
    page.clock.run_for(16_000)  # one reading tick
    page.evaluate("() => window.dispatchEvent(new Event('pagehide'))")  # the minute's report
    eventually(lambda: seconds_read(library, book) > 0, message="no reading time was counted")
    pages = {p for day in library.reading_log().values() for p in day.get(book, {}).get("p", [])}
    assert 3 in pages


def test_start_reading_in_a_reference_preview_counts_reading(library, book, server_factory,
                                                             reader_page):  # fmt: skip
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url = quoted(page, "the exit pupil is the image of the aperture stop")
    other = page.context.new_page()
    other.clock.install()
    other.goto(url)
    other.wait_for_function("() => document.body.dataset.mlRefResult === 'exact'", timeout=20_000)
    other.locator(".ml-preview button").click()  # 开始阅读: nothing else done afterwards
    other.clock.run_for(16_000)
    other.evaluate("() => window.dispatchEvent(new Event('pagehide'))")
    eventually(lambda: seconds_read(library, book) > 0, message="no reading time was counted")
    other.close()


# --- reading time: eligible elapsed time only (Codex M7 re-review) -----------------------------


def pause(tab):
    """The fake clock stopped: from now on only run_for moves the page's time (real waits in
    the test don't), so every second is the test's own."""
    tab.clock.pause_at(tab.evaluate("() => Date.now()") + 1_000)


def flushed(tab, library, doc) -> int:
    """Send the tab's statistics now (as leaving does) and return the seconds recorded."""
    before = seconds_read(library, doc)
    tab.evaluate("() => window.dispatchEvent(new Event('pagehide'))")
    tab.wait_for_timeout(800)
    return seconds_read(library, doc) - before


def test_continue_reading_here_counts_only_eligible_time(library, book, server_factory,
                                                         reader_page):  # fmt: skip
    server = server_factory()
    page = reader_page
    page.clock.install()
    opened(page, server, book)
    url3 = page_link(page, 3)
    page.evaluate("() => { PDFViewerApplication.page = 1; }")
    still(page)
    page.wait_for_timeout(2300)  # (the setup's own decisions sent)
    pause(page)  # (stopping it moves it on: recorded in the next line, before measuring)
    flushed(page, library, book)  # (the setup's reading time recorded: measured from here)
    start = seconds_read(library, book)
    box = page.locator("#viewerContainer").bounding_box()
    page.mouse.move(box["x"] + 50, box["y"] + 50)  # (active)
    page.clock.run_for(10_000)  # 10 s of legitimate reading before the visit
    follow(page, url3)
    result(page, "page-reference")
    page.clock.run_for(14_000)  # 14 s visiting: suppressed
    page.locator(".ml-nav-here").click()  # 在这里继续阅读
    page.clock.run_for(1_000)  # 1 s of reading
    recorded = flushed(page, library, book)
    total = seconds_read(library, book) - start
    assert 10 <= total <= 13, total  # the 10 s before and the 1 s after: never the 14 s
    assert recorded == total and flushed(page, library, book) == 0  # nothing counted twice


def test_start_reading_counts_only_eligible_time(library, book, server_factory, reader_page):
    server = server_factory()
    page = reader_page
    opened(page, server, book)
    url = quoted(page, "the exit pupil is the image of the aperture stop")
    other = page.context.new_page()
    other.clock.install()
    other.goto(url)
    other.wait_for_function("() => document.body.dataset.mlRefResult === 'exact'", timeout=20_000)
    pause(other)
    start = seconds_read(library, book)
    other.clock.run_for(14_000)  # 14 s in the preview: suppressed
    other.locator(".ml-preview button").click()  # 开始阅读
    other.clock.run_for(1_000)
    gained = flushed(other, library, book)
    assert 1 <= gained <= 3, gained  # the second after Start reading, not a 15 s tick
    assert seconds_read(library, book) - start == gained
    assert flushed(other, library, book) == 0
    other.close()


def reading_tab(library, server_factory, page) -> str:
    """A document open on a stopped fake clock, its setup's reading already recorded."""
    doc = ten_pages(library)
    server = server_factory()
    page.clock.install()
    open_document(page, server, doc)
    page.wait_for_timeout(500)
    pause(page)  # (stopping it moves it on a second: recorded in the next line)
    flushed(page, library, doc)
    return doc


VISIBILITY = """(hidden) => {
  Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });
  Object.defineProperty(document, "visibilityState", { configurable: true,
    get: () => (hidden ? "hidden" : "visible") });
  document.dispatchEvent(new Event("visibilitychange")); }"""


def active(page, x):
    """A mouse movement over the PDF (you're there): activity, not a move of the view."""
    box = page.locator("#viewerContainer").bounding_box()
    page.mouse.move(box["x"] + x, box["y"] + 200)


def test_time_read_before_hiding_is_kept_and_the_hidden_time_never_counts(library,
                                                                          server_factory,
                                                                          reader_page):  # fmt: skip
    page = reader_page
    doc = reading_tab(library, server_factory, page)
    start = seconds_read(library, doc)
    active(page, 100)
    page.clock.run_for(10_000)  # 10 s read, before the first tick
    page.evaluate(VISIBILITY, True)  # hidden: its report goes out now
    page.wait_for_timeout(800)
    assert seconds_read(library, doc) - start == 10
    page.clock.run_for(30_000)  # 30 s hidden
    page.evaluate(VISIBILITY, False)
    active(page, 120)
    page.clock.run_for(4_000)  # 4 s read after coming back
    assert flushed(page, library, doc) == 4
    assert seconds_read(library, doc) - start == 14


def test_idle_time_is_never_counted_after_you_come_back(library, server_factory, reader_page):
    page = reader_page
    doc = reading_tab(library, server_factory, page)
    start = seconds_read(library, doc)
    active(page, 100)
    page.clock.run_for(130_000)  # 130 s without any activity: 120 s count, then idle
    active(page, 140)  # you're back
    page.clock.run_for(5_000)
    flushed(page, library, doc)
    assert seconds_read(library, doc) - start == 125  # never 135


def test_fractions_carry_and_repeated_flushes_count_nothing_twice(library, server_factory,
                                                                   reader_page):  # fmt: skip
    page = reader_page
    doc = reading_tab(library, server_factory, page)
    start = seconds_read(library, doc)
    active(page, 100)
    page.clock.run_for(2_500)
    assert flushed(page, library, doc) == 2  # (the half second kept for later)
    assert flushed(page, library, doc) == 0
    page.clock.run_for(600)
    assert flushed(page, library, doc) == 1  # 0.5 + 0.6
    assert flushed(page, library, doc) == 0
    assert seconds_read(library, doc) - start == 3
