"""Task 4 M6: 引用到笔记 (Quote to note) and 引用此页 (Reference this page). A selection in the
PDF goes into the open note as a short quote with its source link; the anchor (the whole
selection, its context, positions, the PDF's fingerprint) is kept only in the library's
private .myLibrary/references/<document id>.json. Temporary libraries and an original
synthetic PDF only."""

import http.client
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from conftest import standard_pages
from helpers import editor_text, notes_settled, open_document, poll, wait_save_state
from playwright.sync_api import expect
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ARIAL = Path("C:/Windows/Fonts/arial.ttf")
NOTE = "# Basics\n\nMy own words.\n"
LINES = [
    "Single line: the exit pupil is the image of the aperture stop.",
    "Across lines: the chief ray passes through the centre of",
    "the aperture stop and defines the image height.",
    "Vignetting reduces the illumi-",
    "nation towards the edge of the field.",
    "Ligatures: the \ufb01eld lens and the \ufb02ux are \ufb01xed.",
    "Greek: the angle \u03b8, wavelength \u03bb and phase \u0394\u03c6 \u2248 2\u03c0\u00b7n.",
    None,  # line 7: two fonts (spans), drawn below
    "Repeat: the entrance pupil limits the aperture.",
    "Again: the entrance pupil limits the aperture.",
]


def quote_pdf(path: Path) -> None:
    """Page 1: the cases above (Arial, which has the ligatures and Greek); page 2: ordinary
    numbered lines; page 3: no text at all (a drawing only, as a scan without OCR)."""
    pdfmetrics.registerFont(TTFont("ArialTest", str(ARIAL)))
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    for n, line in enumerate(LINES):
        y = 740 - 30 * n
        if line is None:
            text = c.beginText(72, y)
            text.setFont("Helvetica-Bold", 14)
            text.textOut("Bold words ")
            text.setFont("ArialTest", 14)
            text.textOut("and plain words follow here.")
            c.drawText(text)
            continue
        c.setFont("ArialTest", 14)
        c.drawString(72, y, line)
    c.showPage()
    c.setFont("Helvetica", 14)
    for n, line in enumerate(standard_pages(1)[0]):
        c.drawString(72, 740 - 30 * n, line)
    c.showPage()
    c.rect(100, 300, 300, 300)  # a page without any text
    c.showPage()
    c.save()


@pytest.fixture
def quote_book(library):
    if not ARIAL.exists():
        pytest.skip("Arial (Windows) is needed for the ligature and Greek test PDF")
    doc = library.add_book("quote-2024-test", "Quote test")
    quote_pdf(library.pdf(doc))
    library.add_notes(doc, ["Basics", "Second"], {"ch01-basics.md": NOTE.encode("utf-8"),
                                                  "ch02-second.md": b"# Second\n"})  # fmt: skip
    library.cache_chapter_pages(doc, {1: 1, 2: 2})
    return doc


def open_quote_book(page, server, doc, page_no=1):
    open_document(page, server, doc, page_no=page_no)
    notes_settled(page)
    note = "file:ch01-basics.md" if page_no == 1 else "file:ch02-second.md"  # (chapter 2: page 2)
    assert page.evaluate("() => document.body.dataset.mlNoteKey") == note


# Select `needle` (its nth occurrence) in a page's text layer, as the user's drag would
SELECT = """([pageNo, needle, nth]) => {
  const layer = document.querySelector(`.page[data-page-number="${pageNo}"] .textLayer`);
  const nodes = [];
  let text = "";
  const walk = document.createTreeWalker(layer, NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode()) {
    nodes.push([n, text.length]);
    text += n.data;
  }
  let at = -1;
  for (let k = 0; k <= nth; k++) { at = text.indexOf(needle, at + 1); if (at < 0) return false; }
  const end = at + needle.length;
  const find = (off, isEnd) => {
    for (const [n, s] of nodes) {
      const inside = isEnd ? off <= s + n.data.length : off < s + n.data.length;
      if (off >= s && inside) return [n, off - s];
    }
  };
  const [sn, so] = find(at, false);
  const [en, eo] = find(end, true);
  const r = document.createRange();
  r.setStart(sn, so);
  r.setEnd(en, eo);
  const sel = getSelection();
  sel.removeAllRanges();
  sel.addRange(r);
  return true;
}"""


def select(page, needle, nth=0, page_no=1):
    assert page.evaluate(SELECT, [page_no, needle, nth]), f"{needle!r} isn't on page {page_no}"


def quote_state(page):
    return page.evaluate("() => document.body.dataset.mlQuote || ''")


def reset_state(page):
    page.evaluate("() => { delete document.body.dataset.mlQuote; }")


def alt_q(page, expect_state="inserted"):
    reset_state(page)
    page.keyboard.press("Alt+q")
    page.wait_for_function("s => document.body.dataset.mlQuote === s", arg=expect_state)


def references(library, doc) -> dict:
    path = library.root / ".myLibrary" / "references" / f"{doc}.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["format"] == 1
    return data["references"]


LINK = re.compile(r"\]\((http://127\.0\.0\.1:\d+/read/([0-9a-f-]{36})\?[^)\s]+)\)")


def links(text: str) -> list[tuple[str, str, dict]]:
    """(url, document id, query) of every source link in the note."""
    found = []
    for url, doc in LINK.findall(text):
        found.append((url, doc, {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}))
    return found


def resolves_to_page(url: str, page_no: int) -> None:
    """The link works while myLibrary runs: /read/<id> sends the reader to that page."""
    parts = urlsplit(url)
    connection = http.client.HTTPConnection(parts.hostname, parts.port, timeout=10)
    connection.request("GET", f"{parts.path}?{parts.query}")
    answer = connection.getresponse()
    assert answer.status == 302, answer.status
    assert f"#page={page_no}" in answer.getheader("Location"), answer.getheader("Location")
    connection.close()


def test_each_kind_of_selection_is_quoted_with_a_working_link(
    library, quote_book, server_factory, reader_page
):
    doc = quote_book
    server = server_factory()
    page = reader_page
    open_quote_book(page, server, doc)
    before = editor_text(page)
    # one line; two lines; a hyphenated word over two lines; ligatures; Greek and symbols;
    # two fonts (separate spans) on one line
    selections = [
        ("the exit pupil is the image of the aperture stop", 0,
         "the exit pupil is the image of the aperture stop"),
        ("passes through the centre of", 0, None),  # extended over the line end below
        ("Vignetting reduces the illumi", 0, None),
        ("\ufb01eld lens and the \ufb02ux", 0, "field lens and the flux"),
        ("angle \u03b8, wavelength \u03bb and phase \u0394\u03c6 \u2248 2\u03c0\u00b7n", 0,
         "angle \u03b8, wavelength \u03bb and phase \u0394\u03c6 \u2248 2\u03c0\u00b7n"),
    ]  # fmt: skip
    expected = []
    for needle, nth, exact in selections:
        if needle == "passes through the centre of":
            extend_over_line(page, needle, "the aperture stop")
            exact = "passes through the centre of the aperture stop"
        elif needle == "Vignetting reduces the illumi":
            extend_over_line(page, needle, "nation towards")
            exact = "Vignetting reduces the illumination towards"
        else:
            select(page, needle, nth)
        alt_q(page)
        expected.append(exact)
    spans = page.evaluate(SPANS)
    assert spans >= 2, "the two-font line should be two spans"
    extend_over_spans(page, "Bold words", "and plain")
    alt_q(page)
    expected.append("Bold words and plain")

    stored = references(library, doc)
    assert len(stored) == len(expected)
    by_exact = {r["exact"]: r for r in stored.values()}
    assert sorted(by_exact) == sorted(expected)
    text = editor_text(page)
    assert text.startswith(before.rstrip("\n"))  # no caret placed: each quote at the end
    found = links(text)
    assert len(found) == len(expected)
    for url, linked_doc, query in found:
        assert linked_doc == doc and query["page"] == "1"
        record = stored[query["ref"]]
        assert record["doc"] == doc and record["page"] == 0 and record["kind"] == "text"
        assert query["q"] and record["exact"].startswith(query["q"])  # q: the visible start
        resolves_to_page(url, 1)
    for exact in expected:
        assert f"> {exact}" in text or f"> {exact[:40]}" in text, exact
    # what the PDF holds and where it is, privately; the whole text never in the note
    pdf_hash = __import__("hashlib").sha256(library.pdf(doc).read_bytes()).hexdigest()
    for record in stored.values():
        assert record["fingerprint"] == pdf_hash and record["loaded"] == pdf_hash
        assert record["pages"] == 3 and record["page_size"] == [595.2756, 841.8898]
        assert record["normalize"] == 1 and len(record["page_hash"]) == 64
        assert record["note"] == {"doc": doc, "key": "file:ch01-basics.md"}
        assert all(0 <= v <= 1 for rect in record["rects"] for v in rect) and record["rects"]
    wait_save_state(page, "clean")
    saved = (library.root / library.row(doc)["notes"] / "ch01-basics.md").read_text("utf-8")
    assert saved == text.replace("\n", "\r\n") or saved == text


SPANS = (
    "() => [...document.querySelectorAll('.page[data-page-number=\"1\"] .textLayer span')]"
    ".filter((s) => /Bold words|and plain words/.test(s.textContent)).length"
)


def extend_over_line(page, first: str, second: str) -> None:
    """A selection from `first` (end of one line) to `second` (start of the next)."""
    ok = page.evaluate(
        """([a, b]) => {
          const layer = document.querySelector('.page[data-page-number="1"] .textLayer');
          const nodes = [];
          const walk = document.createTreeWalker(layer, NodeFilter.SHOW_TEXT);
          for (let n = walk.nextNode(); n; n = walk.nextNode()) nodes.push(n);
          const s = nodes.find((n) => n.data.includes(a));
          const e = nodes.slice(nodes.indexOf(s) + 1).find((n) => n.data.includes(b));
          if (!s || !e || s === e) return false;
          const r = document.createRange();
          r.setStart(s, s.data.indexOf(a));
          r.setEnd(e, e.data.indexOf(b) + b.length);
          getSelection().removeAllRanges();
          getSelection().addRange(r);
          return true;
        }""",
        [first, second],
    )
    assert ok, (first, second)


extend_over_spans = extend_over_line


def test_the_same_words_twice_on_a_page_anchor_the_one_selected(
    library, quote_book, server_factory, reader_page
):
    doc = quote_book
    server = server_factory()
    open_quote_book(reader_page, server, doc)
    phrase = "the entrance pupil limits the aperture"
    select(reader_page, phrase, nth=1)  # the second time it's on the page ("Again: …")
    alt_q(reader_page)
    select(reader_page, phrase, nth=0)  # and the first ("Repeat: …")
    alt_q(reader_page)
    second, first = list(references(library, doc).values())
    assert second["exact"] == first["exact"] == phrase
    assert second["start"] > first["start"]
    assert second["prefix"].endswith("Again: ") and first["prefix"].endswith("Repeat: ")
    # their boxes: on lines 9 and 8 (y from the top of the page, A4 = 842 points)
    line_top = lambda n: (841.89 - (740 - 30 * n) - 14) / 841.89  # noqa: E731
    assert abs(second["rects"][0][1] - line_top(9)) < 0.02
    assert abs(first["rects"][0][1] - line_top(8)) < 0.02
    assert second["rects"][0][1] > first["rects"][0][1]


def test_a_page_without_text_gets_a_page_reference(
    library, quote_book, server_factory, reader_page
):
    doc = quote_book
    server = server_factory()
    page = reader_page
    open_quote_book(page, server, doc)
    # On a page with text, Alt+Q without a selection says to select first, and adds nothing
    page.evaluate("() => getSelection().removeAllRanges()")
    reset_state(page)
    page.keyboard.press("Alt+q")
    expect(page.locator(".ml-find")).to_contain_text("Select the text to quote")
    assert not references(library, doc) and quote_state(page) == ""
    # Page 3 has no text: a page link, no invented quotation
    page.evaluate("() => { PDFViewerApplication.page = 3; }")
    page.wait_for_function("() => PDFViewerApplication.page === 3")
    alt_q(page)
    (record,) = references(library, doc).values()
    assert record["kind"] == "page" and record["page"] == 2 and "exact" not in record
    text = editor_text(page)
    ((url, linked, query),) = links(text)
    assert linked == doc and query["page"] == "3" and query["ref"] == record["rid"]
    assert "q" not in query and "> " not in text.split("My own words.")[1]
    resolves_to_page(url, 3)
    # the notes panel's 引用此页 button does the same for the page shown
    reset_state(page)
    page.locator("#mlPageRefButton").click()
    page.wait_for_function("() => document.body.dataset.mlQuote === 'inserted'")
    assert len(references(library, doc)) == 2


def test_quote_from_the_bubble_and_from_the_lookup_popup(
    library, quote_book, server_factory, reader_page
):
    doc = quote_book
    server = server_factory()
    page = reader_page
    open_quote_book(page, server, doc, page_no=2)
    # a drag over most of a long line: the bubble (Translate, Quote to note)
    span = page.locator('.page[data-page-number="2"] .textLayer span').filter(has_text="line 4:")
    box = span.bounding_box()
    y = box["y"] + box["height"] / 2
    page.mouse.move(box["x"] + 2, y)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] - 2, y, steps=8)
    page.mouse.up()
    quote = page.locator(".ml-bubble .ml-quote")
    expect(quote).to_be_visible()
    expect(page.locator(".ml-bubble")).to_contain_text("Translate")  # still there
    reset_state(page)
    quote.click()
    page.wait_for_function("() => document.body.dataset.mlQuote === 'inserted'")
    (record,) = references(library, doc).values()
    assert record["page"] == 1 and "line 4:" in record["exact"]
    # a double-click on a word: the lookup popup, with its usual parts and Quote to note
    page.locator('.page[data-page-number="2"] .textLayer span').filter(
        has_text="line 6:").dblclick(position={"x": 5, "y": 5})  # fmt: skip
    popup = page.locator(".ml-popup")
    expect(popup.locator(".ml-quote")).to_be_visible()
    expect(popup).to_contain_text("Save word")  # the lookup is unchanged
    reset_state(page)
    popup.locator(".ml-quote").click()
    page.wait_for_function("() => document.body.dataset.mlQuote === 'inserted'")
    assert len(references(library, doc)) == 2


def test_insert_at_the_caret_and_undo_redo(library, quote_book, server_factory, reader_page):
    doc = quote_book
    server = server_factory()
    page = reader_page
    open_quote_book(page, server, doc)
    box = page.locator("#mlNoteText")
    start = NOTE.index("My own words.")
    box.click()  # the user puts the caret at the start of "My own words." (line 3)
    page.keyboard.press("Control+Home")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")
    assert box.evaluate("t => t.selectionStart") == start
    select(page, "the exit pupil is the image of the aperture stop")
    alt_q(page)
    text = editor_text(page)
    quote_at = text.index("> the exit pupil")
    assert NOTE[:start].rstrip("\n") in text[:quote_at]
    assert text.index("My own words.") > quote_at  # before the words the caret was at
    # one Undo takes the whole quote out; Redo puts it back
    box.focus()
    page.keyboard.press("Control+z")
    page.wait_for_function(
        "() => !document.getElementById('mlNoteText').value.includes('> the exit')"
    )
    assert editor_text(page) == NOTE
    page.keyboard.press("Control+y")
    page.wait_for_function(
        "() => document.getElementById('mlNoteText').value.includes('> the exit')"
    )
    assert editor_text(page) == text
    assert len(references(library, doc)) == 1  # the anchor stays (private, harmless)


def test_unsaved_text_and_a_note_changed_on_disk_are_kept(
    library, quote_book, server_factory, reader_page
):
    doc = quote_book
    server = server_factory()
    page = reader_page
    open_quote_book(page, server, doc)
    note = library.root / library.row(doc)["notes"] / "ch01-basics.md"
    page.route("**/api/notes/save", lambda route: route.abort())  # not saved yet
    page.locator("#mlNoteText").evaluate(
        "t => { t.focus(); t.setSelectionRange(t.value.length, t.value.length); }"
    )
    page.keyboard.type("Unsaved line.")
    select(page, "the exit pupil is the image of the aperture stop")
    alt_q(page)
    text = editor_text(page)
    assert "Unsaved line." in text and "> the exit pupil" in text
    assert text.index("Unsaved line.") < text.index("> the exit pupil")
    # Meanwhile the note is changed in another editor: nothing is overwritten
    note.write_text("# Basics\n\nEdited in VS Code.\n", encoding="utf-8")
    page.unroute("**/api/notes/save")
    page.keyboard.press("Control+s")
    wait_save_state(page, "conflict")
    assert note.read_text(encoding="utf-8") == "# Basics\n\nEdited in VS Code.\n"
    assert "> the exit pupil" in editor_text(page)  # still on screen


def held_create(page):
    """Hold /api/references/create until the test releases it."""
    held = []
    page.route("**/api/references/create", lambda route: held.append(route))
    return held


def test_switching_chapters_while_a_quote_is_stored_never_inserts_into_the_other(
    library, quote_book, server_factory, reader_page
):
    doc = quote_book
    server = server_factory()
    page = reader_page
    open_quote_book(page, server, doc)
    held = held_create(page)
    select(page, "the exit pupil is the image of the aperture stop")
    reset_state(page)
    page.keyboard.press("Alt+q")
    page.wait_for_function("() => document.body.dataset.mlQuote === 'saving'")
    page.wait_for_timeout(100)
    assert held
    page.locator("#mlNoteSelect").select_option("file:ch02-second.md")
    page.wait_for_function("() => document.body.dataset.mlNoteKey === 'file:ch02-second.md'"
                           " && document.body.dataset.mlNoteState === 'shown'")  # fmt: skip
    held[0].continue_()
    page.wait_for_function("() => document.body.dataset.mlQuote === 'kept'")
    assert "> the exit" not in editor_text(page)  # not into chapter 2 by itself
    folder = library.root / library.row(doc)["notes"]
    assert (folder / "ch01-basics.md").read_text(encoding="utf-8") == NOTE
    assert (folder / "ch02-second.md").read_text(encoding="utf-8") == "# Second\n"
    # Offered for chapter 1 only (its record names chapter 1): in chapter 2 the button says so
    page.locator(".mlInsertQuote").click()
    expect(page.locator("#mlNotes")).to_contain_text("Go back to")
    assert editor_text(page) == "# Second\n" and quote_state(page) == "kept"
    # back in chapter 1, it goes in there
    page.locator("#mlNoteSelect").select_option("file:ch01-basics.md")
    page.wait_for_function("() => document.body.dataset.mlNoteKey === 'file:ch01-basics.md'"
                           " && document.body.dataset.mlNoteState === 'shown'")  # fmt: skip
    page.locator(".mlInsertQuote").click()
    page.wait_for_function("() => document.body.dataset.mlQuote === 'inserted'")
    assert "> the exit pupil" in editor_text(page)
    wait_save_state(page, "clean")
    assert "> the exit pupil" in (folder / "ch01-basics.md").read_text(encoding="utf-8")
    assert (folder / "ch02-second.md").read_text(encoding="utf-8") == "# Second\n"
    page.unroute("**/api/references/create")


def test_moving_to_another_document_while_a_quote_is_stored_inserts_nothing(
    library, quote_book, server_factory, reader_page
):
    doc = quote_book
    other = library.add_book("other-2023-book", "Other book")
    library.add_notes(other, ["One"], {"ch01-one.md": b"# One\n"})
    library.cache_chapter_pages(other, {1: 1})
    server = server_factory()
    page = reader_page
    open_quote_book(page, server, doc)
    held = held_create(page)
    select(page, "the exit pupil is the image of the aperture stop")
    reset_state(page)
    page.keyboard.press("Alt+q")
    page.wait_for_function("() => document.body.dataset.mlQuote === 'saving'")
    page.wait_for_timeout(100)
    assert held
    open_document(page, server, other)
    notes_settled(page)
    assert "> the exit" not in editor_text(page)
    assert (library.root / library.row(doc)["notes"] / "ch01-basics.md").read_text("utf-8") == NOTE
    assert (library.root / library.row(other)["notes"] / "ch01-one.md").read_text(
        "utf-8"
    ) == "# One\n"
    assert not references(library, other)
    page.unroute("**/api/references/create")


def test_with_the_notes_panel_closed_the_quote_opens_it(
    library, quote_book, server_factory, reader_page
):
    doc = quote_book
    server = server_factory()
    page = reader_page
    open_quote_book(page, server, doc)
    if page.evaluate("() => document.body.dataset.mlNotes") == "open":
        page.locator("#mlNotesToggle").click()
    page.wait_for_function("() => document.body.dataset.mlNotes === 'closed'")
    select(page, "the exit pupil is the image of the aperture stop")
    alt_q(page)
    assert page.evaluate("() => document.body.dataset.mlNotes") == "open"
    assert editor_text(page).rstrip().endswith(")") and "> the exit pupil" in editor_text(page)


def test_a_failed_reference_write_inserts_nothing_and_can_be_retried(
    library, quote_book, server_factory, reader_page
):
    doc = quote_book
    server = server_factory()
    page = reader_page
    open_quote_book(page, server, doc)
    # the server stored it, but the answer was lost: Retry finds it (same request), not twice
    answers = {"n": 0}

    def lost_answer(route):
        answers["n"] += 1
        if answers["n"] == 1:
            route.fetch()  # reaches the server
            route.fulfill(status=500, json={"error": "simulated failure"})
        else:
            route.continue_()

    page.route("**/api/references/create", lost_answer)
    select(page, "the exit pupil is the image of the aperture stop")
    alt_q(page, "failed")
    expect(page.locator(".ml-quote-failed")).to_contain_text("nothing was inserted")
    assert editor_text(page) == NOTE
    reset_state(page)
    page.locator(".mlQuoteRetry").click()
    page.wait_for_function("() => document.body.dataset.mlQuote === 'inserted'")
    assert len(references(library, doc)) == 1  # one record, not two
    page.unroute("**/api/references/create")
    # a damaged references file (and no good previous version): refused, never replaced
    path = library.root / ".myLibrary" / "references" / f"{doc}.json"
    path.write_bytes(b"{ damaged")
    path.with_name(path.name + ".bak").write_bytes(b"also damaged")
    text = editor_text(page)
    select(page, "Greek: the angle")
    alt_q(page, "failed")
    assert editor_text(page) == text
    assert path.read_bytes() == b"{ damaged"


# --- the note is taken with the click or key, before the PDF side's work (Codex M6 review) -----

# Hold the PDF side's own capture (not the request that stores it) until release_capture:
# a text quote's digests, or a page's text content (Alt+Q without a selection looks at it)
HOLD = """(what) => {
  window.__mlHeld = 0;
  window.__mlGate = new Promise((go) => { window.__mlRelease = go; });
  const wait = async () => { window.__mlHeld++; await window.__mlGate; };
  if (what === "digest") {
    const digest = crypto.subtle.digest.bind(crypto.subtle);
    crypto.subtle.digest = async (...args) => { await wait(); return digest(...args); };
  } else {
    const pdfPage = PDFViewerApplication.pdfViewer.getPageView(what).pdfPage;
    const content = pdfPage.getTextContent.bind(pdfPage);
    // (its content got first: what this PDF answers, held back until the release)
    pdfPage.getTextContent = async (...args) => {
      const got = await content(...args);
      await wait();
      return got;
    };
  }
}"""


def hold_capture(page, what="digest"):
    page.evaluate(HOLD, what)


def wait_held(page):
    page.wait_for_function("() => window.__mlHeld > 0")


def release_capture(page):
    page.evaluate("() => window.__mlRelease()")


def choose_note(page, key):
    page.locator("#mlNoteSelect").select_option(key)
    page.wait_for_function(
        "k => document.body.dataset.mlNoteKey === k"
        " && document.body.dataset.mlNoteState === 'shown'",
        arg=key,
    )


def notes_on_disk(library, doc) -> tuple[str, str]:
    folder = library.root / library.row(doc)["notes"]
    return tuple((folder / name).read_text(encoding="utf-8")
                 for name in ("ch01-basics.md", "ch02-second.md"))  # fmt: skip


def test_a_chapter_chosen_while_the_pdf_side_captures_gets_nothing(
    library, quote_book, server_factory, reader_page
):
    doc = quote_book
    server = server_factory()
    page = reader_page
    open_quote_book(page, server, doc)
    hold_capture(page)
    select(page, "the exit pupil is the image of the aperture stop")
    reset_state(page)
    page.keyboard.press("Alt+q")
    wait_held(page)
    choose_note(page, "file:ch02-second.md")
    release_capture(page)
    page.wait_for_function("() => document.body.dataset.mlQuote === 'refused'")
    expect(page.locator("#mlNotes")).to_contain_text("Another note was chosen while quoting")
    assert editor_text(page) == "# Second\n"
    assert not references(library, doc)  # nothing recorded for a quote that went nowhere
    assert notes_on_disk(library, doc) == (NOTE, "# Second\n")
    choose_note(page, "file:ch01-basics.md")
    assert editor_text(page) == NOTE


def test_back_in_the_original_chapter_before_the_capture_ends_it_goes_there_at_the_caret(
    library, quote_book, server_factory, reader_page
):
    doc = quote_book
    server = server_factory()
    page = reader_page
    open_quote_book(page, server, doc)
    box = page.locator("#mlNoteText")
    box.click()  # the caret at the start of "My own words." when quoting
    page.keyboard.press("Control+Home")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")
    hold_capture(page)
    select(page, "the exit pupil is the image of the aperture stop")
    reset_state(page)
    page.keyboard.press("Alt+q")
    wait_held(page)
    choose_note(page, "file:ch02-second.md")
    choose_note(page, "file:ch01-basics.md")
    release_capture(page)
    page.wait_for_function("() => document.body.dataset.mlQuote === 'inserted'")
    text = editor_text(page)
    assert text.index("> the exit pupil") < text.index("My own words.")  # the caret then
    (record,) = references(library, doc).values()
    assert record["note"]["key"] == "file:ch01-basics.md"
    wait_save_state(page, "clean")  # saved like any edit
    assert notes_on_disk(library, doc) == (text, "# Second\n")
    box.focus()  # one Undo takes it out, and that is saved too
    page.keyboard.press("Control+z")
    page.wait_for_function(
        "() => !document.getElementById('mlNoteText').value.includes('> the exit')"
    )
    assert editor_text(page) == NOTE
    wait_save_state(page, "clean")
    assert notes_on_disk(library, doc) == (NOTE, "# Second\n")


def test_a_page_reference_never_goes_into_a_chapter_chosen_meanwhile(
    library, quote_book, server_factory, reader_page
):
    doc = quote_book
    server = server_factory()
    page = reader_page
    open_quote_book(page, server, doc)
    page.evaluate("() => { PDFViewerApplication.page = 3; }")  # (page 3 has no text)
    page.wait_for_function("() => PDFViewerApplication.page === 3")
    page.evaluate("() => getSelection().removeAllRanges()")
    hold_capture(page, 2)
    reset_state(page)
    page.keyboard.press("Alt+q")
    wait_held(page)
    choose_note(page, "file:ch02-second.md")
    release_capture(page)
    page.wait_for_function("() => document.body.dataset.mlQuote === 'refused'")
    assert editor_text(page) == "# Second\n" and not references(library, doc)
    assert notes_on_disk(library, doc) == (NOTE, "# Second\n")


def test_quoting_again_while_a_quote_is_captured_inserts_it_once(
    library, quote_book, server_factory, reader_page
):
    doc = quote_book
    server = server_factory()
    page = reader_page
    open_quote_book(page, server, doc)
    hold_capture(page)
    select(page, "the exit pupil is the image of the aperture stop")
    reset_state(page)
    page.keyboard.press("Alt+q")
    wait_held(page)
    page.keyboard.press("Alt+q")
    page.keyboard.press("Alt+q")
    expect(page.locator("#mlNotes")).to_contain_text("The previous quote isn't finished yet")
    release_capture(page)
    page.wait_for_function("() => document.body.dataset.mlQuote === 'inserted'")
    page.wait_for_timeout(300)  # (anything else would have arrived by now)
    assert editor_text(page).count("> the exit pupil") == 1
    assert len(references(library, doc)) == 1


def test_moving_to_another_document_while_the_pdf_side_captures_inserts_nothing(
    library, quote_book, server_factory, reader_page
):
    doc = quote_book
    other = library.add_book("other-2023-book", "Other book")
    library.add_notes(other, ["One"], {"ch01-one.md": b"# One\n"})
    library.cache_chapter_pages(other, {1: 1})
    server = server_factory()
    page = reader_page
    open_quote_book(page, server, doc)
    hold_capture(page)
    select(page, "the exit pupil is the image of the aperture stop")
    page.keyboard.press("Alt+q")
    wait_held(page)
    open_document(page, server, other)
    notes_settled(page)
    assert editor_text(page) == "# One\n"
    assert notes_on_disk(library, doc) == (NOTE, "# Second\n")
    assert not references(library, doc) and not references(library, other)


def other_version(path: Path) -> bytes:
    """Another PDF with the same three pages' shape (text, text, none): what a tab could open
    instead of the document's own while a quote is captured."""
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    c.setTitle("Another version")
    for words in ("Another version, page one.", "Page two."):
        c.setFont("Helvetica", 14)
        c.drawString(72, 740, words)
        c.showPage()
    c.rect(50, 50, 200, 200)  # (no text: a page reference, as in the first PDF)
    c.showPage()
    c.save()
    return path.read_bytes()


def test_alt_q_on_a_page_never_mixes_two_pdfs_opened_in_turn(
    library, quote_book, server_factory, reader_page, tmp_path
):
    """Codex M6 review: Alt+Q without a selection looks at the page's text first; another
    PDF opened in the tab meanwhile must never give the reference its page or fingerprint."""
    doc = quote_book
    server = server_factory()
    page = reader_page
    open_quote_book(page, server, doc)
    page.evaluate("() => { PDFViewerApplication.page = 3; }")  # (page 3 has no text)
    page.wait_for_function("() => PDFViewerApplication.page === 3")
    page.evaluate("() => getSelection().removeAllRanges()")
    first = page.evaluate("() => PDFViewerApplication.pdfDocument.fingerprints[0]")
    hold_capture(page, 2)  # the first PDF's page 3: its text content held back
    reset_state(page)
    page.keyboard.press("Alt+q")
    wait_held(page)
    data = list(other_version(tmp_path / "other.pdf"))
    page.evaluate("(data) => PDFViewerApplication.open({ data: new Uint8Array(data) })", data)
    page.wait_for_function(
        "f => PDFViewerApplication.pdfDocument?.fingerprints[0] !== f"
        " && PDFViewerApplication.pagesCount === 3",
        arg=first,
    )
    # the other PDF's page 3 loaded too: had the page been read again after the wait, it
    # would now give a whole reference to the wrong PDF (not merely fail)
    page.evaluate("() => { PDFViewerApplication.page = 3; }")
    page.wait_for_function("() => PDFViewerApplication.pdfViewer.getPageView(2)?.pdfPage")
    release_capture(page)
    page.wait_for_function(  # refused (said), or (the defect) recorded and inserted
        "() => document.querySelector('.ml-find') || document.body.dataset.mlQuote"
    )
    page.wait_for_timeout(300)  # (a record or an insertion would have arrived by now)
    assert references(library, doc) == {}  # never a record mixing the two PDFs
    assert quote_state(page) == "" and editor_text(page) == NOTE
    expect(page.locator(".ml-find")).to_contain_text("the PDF was opened again while quoting")
    assert notes_on_disk(library, doc) == (NOTE, "# Second\n")


# --- quoting while the notes panel starts closed (Codex M6 review) -----------------------------


def open_closed(page, server, doc):
    """Open the reader with the notes panel remembered as closed: no note is loaded yet."""
    page.context.add_init_script(
        "try { localStorage.setItem('myLibrary.notes.open', '0'); } catch {}"
    )
    open_document(page, server, doc)
    page.wait_for_function("() => document.body.dataset.mlNotes === 'closed'")
    assert page.evaluate("() => document.body.dataset.mlNoteKey") is None


def held_gets(page):
    held = []
    page.route("**/api/notes/get", lambda route: held.append(route))
    return held


def test_a_quote_with_the_panel_never_opened_waits_for_its_note(
    library, quote_book, server_factory, reader_page
):
    doc = quote_book
    server = server_factory()
    page = reader_page
    open_closed(page, server, doc)
    select(page, "the exit pupil is the image of the aperture stop")
    alt_q(page)
    assert page.evaluate("() => document.body.dataset.mlNotes") == "open"
    assert page.evaluate("() => document.body.dataset.mlNoteKey") == "file:ch01-basics.md"
    text = editor_text(page)
    assert text.startswith(NOTE.rstrip("\n")) and "> the exit pupil" in text
    (record,) = references(library, doc).values()
    assert record["note"]["key"] == "file:ch01-basics.md"
    wait_save_state(page, "clean")
    assert notes_on_disk(library, doc) == (text, "# Second\n")


def test_a_quote_while_the_panel_fails_to_load_records_and_inserts_nothing(
    library, quote_book, server_factory, reader_page
):
    doc = quote_book
    server = server_factory()
    page = reader_page
    open_closed(page, server, doc)
    page.route("**/api/notes/list", lambda route: route.fulfill(status=500, json={"error": "x"}))
    select(page, "the exit pupil is the image of the aperture stop")
    alt_q(page, "refused")
    expect(page.locator("#mlNotes")).to_contain_text("Couldn't load the note")
    expect(page.locator("#mlNotes")).to_contain_text("Open a note you can edit")
    assert not references(library, doc)
    assert notes_on_disk(library, doc) == (NOTE, "# Second\n")
    page.unroute("**/api/notes/list")


def test_a_chapter_chosen_while_the_panel_first_loads_never_gets_the_quote(
    library, quote_book, server_factory, reader_page
):
    doc = quote_book
    server = server_factory()
    page = reader_page
    open_closed(page, server, doc)
    held = held_gets(page)
    select(page, "the exit pupil is the image of the aperture stop")
    reset_state(page)
    page.keyboard.press("Alt+q")
    poll(page, lambda: held, message="the first note was never asked for")
    page.locator("#mlNoteSelect").select_option("file:ch02-second.md")
    poll(page, lambda: len(held) == 2, message="the chosen note was never asked for")
    for route in held:
        route.continue_()
    page.unroute("**/api/notes/get")
    page.wait_for_function("() => document.body.dataset.mlQuote === 'refused'")
    expect(page.locator("#mlNotes")).to_contain_text("Another note was chosen while quoting")
    assert page.evaluate("() => document.body.dataset.mlNoteKey") == "file:ch02-second.md"
    assert editor_text(page) == "# Second\n" and not references(library, doc)
    assert notes_on_disk(library, doc) == (NOTE, "# Second\n")


def test_quoting_again_while_the_panel_first_loads_inserts_it_once(
    library, quote_book, server_factory, reader_page
):
    doc = quote_book
    server = server_factory()
    page = reader_page
    open_closed(page, server, doc)
    held = held_gets(page)
    select(page, "the exit pupil is the image of the aperture stop")
    reset_state(page)
    page.keyboard.press("Alt+q")
    poll(page, lambda: held, message="the first note was never asked for")
    select(page, "the exit pupil is the image of the aperture stop")
    page.keyboard.press("Alt+q")
    expect(page.locator("#mlNotes")).to_contain_text("The previous quote isn't finished yet")
    for route in held:
        route.continue_()
    page.unroute("**/api/notes/get")
    page.wait_for_function("() => document.body.dataset.mlQuote === 'inserted'")
    page.wait_for_timeout(300)
    assert editor_text(page).count("> the exit pupil") == 1
    assert len(references(library, doc)) == 1
