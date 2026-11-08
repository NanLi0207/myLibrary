"""D5 (fixed): marks are saved on the version of the PDF they were made on. Every save names
that version (the SHA-256 of the bytes the tab loaded, then of what it last saved); the server
writes the PDF only if it is still exactly that. Otherwise (another tab saved, OCR replaced
the PDF) nothing is written to it, the tab's PDF is kept, verified, in
archive/marks-conflicts/, and the tab says where. It keeps warning before it's left until its
latest marks are in such a copy; Reload then shows the current PDF, to mark again.

A save that got no answer (but was written) is recognised by its own version: no false
conflict. Temporary libraries; the server's answers are held or replaced with page.route."""

import hashlib
import io

from helpers import (
    highlight_line,
    highlighted_lines,
    leave,
    leave_tool,
    marks_state,
    open_document,
    poll,
    screen_lines,
    wait_marks_saved,
)
from playwright.sync_api import expect
from pypdf import PdfReader, PdfWriter

SAVE = "**/api/save-marks"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def saves_sent(page) -> list[dict]:
    """Every marks save the page sends: its body and its version headers."""
    sent = []

    def on_request(request):
        if request.url.endswith("/api/save-marks"):
            headers = request.headers
            sent.append({"body": request.post_data_buffer,
                         "base": headers.get("x-pdf-version"),
                         "unconfirmed": headers.get("x-pdf-unconfirmed", ""),
                         "action": headers.get("x-marks-action", "save")})  # fmt: skip

    page.on("request", on_request)
    return sent


def copies(library) -> list:
    folder = library.root / "archive" / "marks-conflicts"
    return sorted(p for p in folder.rglob("*.pdf")) if folder.exists() else []


def wait_marks_state(page, state: str, timeout: float = 20_000) -> None:
    page.wait_for_function(
        "s => document.querySelector('.ml-marks')?.dataset.state === s", arg=state,
        timeout=timeout,
    )  # fmt: skip


def reloaded(page) -> None:
    """After a reload: the reader is back, its first page's text shown."""
    page.wait_for_load_state()
    page.locator('.page[data-page-number="1"] .textLayer span').first.wait_for()


def two_tabs_in_conflict(library, server, reader_page):
    """Both tabs load the PDF; the first saves a mark on line 0; the second marks line 3."""
    doc = library.add_book("doe-2020-marks-test", "Marks test")
    first, second = reader_page, reader_page.context.new_page()
    open_document(first, server, doc)
    open_document(second, server, doc)
    highlight_line(first, 0)
    leave_tool(first)
    wait_marks_saved(first)
    assert highlighted_lines(library.pdf(doc)) == [0]
    sent = saves_sent(second)
    highlight_line(second, 3)
    leave_tool(second)
    return doc, first, second, sent


def test_marks_from_two_tabs_are_never_lost(library, server, reader_page):
    doc, first, second, sent = two_tabs_in_conflict(library, server, reader_page)
    wait_marks_state(second, "conflict")
    # The first tab's mark stays in the library's PDF
    assert highlighted_lines(library.pdf(doc)) == [0]
    # The second tab's PDF is kept whole: the bytes it sent, readable, with its mark
    [copy] = copies(library)
    assert copy.read_bytes() == sent[-1]["body"] and highlighted_lines(copy) == [3]
    assert len(PdfReader(copy).pages) == len(PdfReader(library.pdf(doc)).pages)
    status = second.locator(".ml-marks")
    kept = copy.relative_to(library.root).as_posix()
    expect(status).to_contain_text(kept)
    assert str(library.root) not in status.inner_text()  # (its place in the library only)
    expect(status).to_contain_text("Marks conflict")
    # Still warned before leaving (its marks aren't in the library's PDF); no automatic
    # retries making more copies
    assert leave(second, "close", stay=True)
    assert len(copies(library)) == 1 and marks_state(second) == "conflict"
    # Reload shows the current PDF (the first tab's mark); the mark is made again and saved
    status.get_by_role("button", name="Reload").click()
    reloaded(second)
    poll(second, lambda: screen_lines(second) == [0], 10, "the current PDF wasn't shown")
    highlight_line(second, 3)
    leave_tool(second)
    wait_marks_saved(second)
    assert highlighted_lines(library.pdf(doc)) == [0, 3]
    assert len(copies(library)) == 1


def test_marks_made_after_a_conflict_need_a_new_copy_first(library, server, reader_page):
    doc, first, second, sent = two_tabs_in_conflict(library, server, reader_page)
    wait_marks_state(second, "conflict")
    status = second.locator(".ml-marks")
    expect(status.get_by_role("button", name="Reload")).to_be_visible()
    highlight_line(second, 6)  # after the copy was made: the copy no longer has everything
    leave_tool(second)
    expect(status.get_by_role("button", name="Reload")).to_have_count(0)
    expect(status.get_by_role("button", name="Keep another copy")).to_be_visible()
    assert leave(second, "close", stay=True)
    assert len(copies(library)) == 1  # nothing kept or saved by itself
    status.get_by_role("button", name="Keep another copy").click()
    poll(second, lambda: len(copies(library)) == 2, 10, "no second copy")
    newest = copies(library)[-1]  # (named by time: the later one sorts last)
    assert highlighted_lines(newest) == [3, 6] and newest.read_bytes() == sent[-1]["body"]
    assert sent[-1]["action"] == "keep-copy"
    expect(status.get_by_role("button", name="Reload")).to_be_visible()
    assert highlighted_lines(library.pdf(doc)) == [0]  # the library's PDF: never touched


def test_a_tab_on_a_pdf_replaced_meanwhile_never_writes_over_it(library, server, reader_page):
    """As after OCR: the PDF on disk is another version than the tab loaded."""
    doc = library.add_book("doe-2020-marks-test", "Marks test")
    open_document(reader_page, server, doc)
    writer = PdfWriter(clone_from=library.pdf(doc))
    writer.add_metadata({"/Subject": "replaced while the tab was open (as by OCR)"})
    replaced = io.BytesIO()
    writer.write(replaced)
    library.pdf(doc).write_bytes(replaced.getvalue())
    sent = saves_sent(reader_page)
    highlight_line(reader_page, 2)
    leave_tool(reader_page)
    wait_marks_state(reader_page, "conflict")
    assert library.pdf(doc).read_bytes() == replaced.getvalue()  # the new version stays
    [copy] = copies(library)
    assert copy.read_bytes() == sent[-1]["body"] and highlighted_lines(copy) == [2]


def test_saves_in_a_row_each_build_on_the_last(library, server, reader_page):
    doc = library.add_book("doe-2020-marks-test", "Marks test")
    loaded = sha(library.pdf(doc).read_bytes())
    sent = saves_sent(reader_page)
    open_document(reader_page, server, doc)
    for n, line in enumerate((0, 3, 6)):
        highlight_line(reader_page, line)
        leave_tool(reader_page)
        poll(reader_page, lambda n=n: len(sent) > n and marks_state(reader_page) == "saved",
             20, "not saved")  # fmt: skip
        assert highlighted_lines(library.pdf(doc)) == [0, 3, 6][: n + 1]
    saves = [s for s in sent if s["action"] == "save"]
    assert saves[0]["base"] == loaded
    for earlier, later in zip(saves, saves[1:], strict=False):
        assert later["base"] == sha(earlier["body"])  # the version the last save made
    assert copies(library) == []


def test_marks_made_while_a_save_is_on_its_way_follow_on_its_version(library, server, reader_page):
    doc = library.add_book("doe-2020-marks-test", "Marks test")
    held, sent = [], saves_sent(reader_page)

    def hold_first(route):
        if held:
            route.continue_()
        else:
            held.append(route)

    reader_page.route(SAVE, hold_first)
    open_document(reader_page, server, doc)
    highlight_line(reader_page, 0)
    poll(reader_page, lambda: held, 10, "no save was sent")
    highlight_line(reader_page, 4)  # while the first save is unanswered
    leave_tool(reader_page)
    assert marks_state(reader_page) == "saving" and len(sent) == 1  # one save at a time
    held[0].continue_()
    poll(reader_page, lambda: highlighted_lines(library.pdf(doc)) == [0, 4], 20,
         "the later mark wasn't saved next")  # fmt: skip
    wait_marks_saved(reader_page)
    assert sent[1]["base"] == sha(sent[0]["body"]) and copies(library) == []


def test_a_save_whose_answer_was_lost_is_no_conflict(library, server, reader_page):
    """The server wrote the PDF but the tab never heard: its next save names that write as
    its own (X-PDF-Unconfirmed), so it simply follows on it."""
    doc = library.add_book("doe-2020-marks-test", "Marks test")
    lost, sent = [], saves_sent(reader_page)

    def lose_the_first_answer(route):
        if lost:
            route.continue_()
        else:
            lost.append(route.fetch())  # it reaches the server, which writes the PDF
            route.abort("connectionreset")  # but the tab gets no answer

    reader_page.route(SAVE, lose_the_first_answer)
    open_document(reader_page, server, doc)
    highlight_line(reader_page, 5)
    leave_tool(reader_page)
    poll(reader_page, lambda: lost and highlighted_lines(library.pdf(doc)) == [5], 20,
         "the first save didn't reach the server")  # fmt: skip
    assert lost[0].status == 200
    wait_marks_saved(reader_page)  # the next attempt: saved, no conflict
    assert sent[1]["unconfirmed"] == sha(sent[0]["body"])
    assert copies(library) == [] and highlighted_lines(library.pdf(doc)) == [5]
    reader_page.locator(".ml-marks").wait_for(state="hidden")
    assert not leave(reader_page, "close")


def test_a_copy_that_couldnt_be_kept_leaves_the_marks_unsaved(library, server, reader_page):
    doc, first, second, sent = two_tabs_in_conflict(library, server, reader_page)
    failing = [True]

    def copy_fails(route):
        if failing[0]:
            route.fulfill(status=500, content_type="application/json",
                          body='{"error": "your marks couldn\'t be kept (disk full): they are '
                               'only in the tab"}')  # fmt: skip
        else:
            route.continue_()

    second.route(SAVE, copy_fails)
    wait_marks_state(second, "failed")
    status = second.locator(".ml-marks")
    expect(status).to_contain_text("only in the tab")
    assert leave(second, "close", stay=True)
    assert copies(library) == [] and highlighted_lines(library.pdf(doc)) == [0]
    failing[0] = False
    status.get_by_role("button", name="Retry").click()
    wait_marks_state(second, "conflict")
    [copy] = copies(library)
    assert highlighted_lines(copy) == [3] and highlighted_lines(library.pdf(doc)) == [0]
