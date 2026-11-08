"""When saving goes wrong (task 4 M4): a failing or silent server, the server stopped and
started again, the tab closed, reloaded or crashed, the browser refusing to keep drafts. In
every case the typed text stays on screen or in the recovery draft until the server confirms
it, and nothing is overwritten. Temporary libraries only."""

import json
import os
import time

from helpers import (
    EDITOR,
    drafts_in_browser,
    editor_text,
    eventually,
    leave,
    notes_settled,
    open_document,
    poll,
    type_at_end,
    wait_save_state,
)
from playwright.sync_api import expect
from test_notes_content import book_with_notes

FAIL = {"status": 500, "content_type": "application/json", "body": '{"error": "the disk is full"}'}


def chapter_one(library, doc):
    return library.root / library.row(doc)["notes"] / "ch01-basics.md"


def open_book(library, server_factory, page, clock=False):
    doc = book_with_notes(library)
    server = server_factory()
    if clock:
        page.clock.install()
    open_document(page, server, doc, page_no=2)
    notes_settled(page)
    if clock:
        page.clock.pause_at(int(time.time() * 1000) + 2_000)
    return doc, server


CRASH_WAIT = 10  # s for both crash signals to arrive


def crash(page):
    """The tab's renderer really crashes (DevTools Page.crash), as in a browser crash: no close
    or unload events run.

    - The command goes through the browser's own DevTools session (Target.sendMessageToTarget),
      which answers at once that it was delivered: a session on the tab itself waits for the
      crashing renderer's own answer, which may never come.
    - A delivered command isn't proof. Two independent signals must both arrive (at most 10 s,
      both listened for before the crash): Playwright's page "crash" event, and Chromium's own
      Target.targetCrashed for this tab's target id. Otherwise the test fails with everything
      seen (the target, the session, the reply, the tab's answers, both signals, whether the
      page still runs JavaScript).
    - The crashed page isn't closed here: Playwright's close() of a crashed renderer may never
      return. Closing the context at the end of the test disposes of it."""
    seen = {"playwright": False, "chromium": [], "tab": [], "other": []}
    page.once("crash", lambda *_: seen.__setitem__("playwright", True))
    browser = page.context.browser.new_browser_cdp_session()
    browser.on("Target.targetCrashed", lambda e: seen["chromium"].append(e))
    browser.on("Target.receivedMessageFromTarget", lambda e: seen["tab"].append(e.get("message")))
    browser.on("Target.detachedFromTarget", lambda e: seen["other"].append(("detached", e)))
    browser.on("Target.targetDestroyed", lambda e: seen["other"].append(("destroyed", e)))
    try:
        browser.send("Target.setDiscoverTargets", {"discover": True})  # target events on
        targets = browser.send("Target.getTargets")["targetInfos"]
        tabs = [t for t in targets if t["type"] == "page" and t["url"] == page.url]
        assert len(tabs) == 1, targets  # exactly this tab
        target = tabs[0]["targetId"]
        session = browser.send("Target.attachToTarget", {"targetId": target, "flatten": False})
        session = session["sessionId"]
        message = json.dumps({"id": 1, "method": "Page.crash"})
        sent = browser.send(
            "Target.sendMessageToTarget", {"sessionId": session, "message": message}
        )

        def ours():
            return [c for c in seen["chromium"] if c.get("targetId") == target]

        start = time.monotonic()
        end = start + CRASH_WAIT
        while time.monotonic() < end and not (seen["playwright"] and ours()):
            browser.send("Target.getTargets")  # each call lets the events of both arrive
            time.sleep(0.05)
        if log := os.environ.get("MYLIBRARY_CRASH_LOG"):  # evidence of each crash, when asked
            evidence = {
                "target": target,
                "sent": sent,
                "playwright": seen["playwright"],
                "chromium": ours(),
                "seconds": round(time.monotonic() - start, 2),
            }
            with open(log, "a", encoding="utf-8") as out:
                out.write(json.dumps(evidence) + "\n")
        if not (seen["playwright"] and ours()):
            try:
                page.evaluate("() => 1")
                responsive = "yes: the page still runs JavaScript"
            except Exception as error:
                responsive = f"no ({type(error).__name__}: {str(error)[:120]})"
            listed = [(t["type"], t["url"][:70], t["targetId"][:8]) for t in targets]
            raise AssertionError(
                f"the tab didn't crash as required within {CRASH_WAIT} s\n"
                f"target: {tabs[0]}\nsession: {session}; sent: {sent}\n"
                f"Playwright crash event: {seen['playwright']}\n"
                f"Chromium targetCrashed: {seen['chromium']}\n"
                f"tab answers: {seen['tab']}\nother target events: {seen['other']}\n"
                f"page responsive: {responsive}\n"
                f"targets before: {listed}"
            )
    finally:
        browser.detach()
    assert not page.is_closed()  # crashed, not closed: no unload of any kind ran


def test_a_failed_save_keeps_the_text_and_is_retried(library, server_factory, reader_page):
    doc, _ = open_book(library, server_factory, reader_page)
    failures = []

    def fail_twice(route):
        if len(failures) < 2:
            failures.append(1)
            route.fulfill(**FAIL)
        else:
            route.continue_()

    reader_page.route("**/api/notes/save", fail_twice)
    type_at_end(reader_page, "kept through failures")
    reader_page.keyboard.press("Control+s")
    wait_save_state(reader_page, "failed")
    expect(reader_page.locator("#mlNoteBar")).to_contain_text("the disk is full")
    assert any(t.endswith("kept through failures") for t in drafts_in_browser(reader_page).values())
    poll(reader_page, lambda: len(failures) == 2, timeout=10, message="not retried by itself")
    reader_page.locator("#mlRetry").click()  # 重试 (Retry): at once
    wait_save_state(reader_page, "clean")
    assert chapter_one(library, doc).read_bytes().endswith(b"kept through failures")
    assert drafts_in_browser(reader_page) == {}  # confirmed: the draft is spent


def test_a_save_without_an_answer_fails_then_is_retried(library, server_factory, reader_page):
    doc, _ = open_book(library, server_factory, reader_page, clock=True)
    silent = []
    reader_page.route("**/api/notes/save", lambda route: silent.append(route))  # never answered
    type_at_end(reader_page, "no answer yet")
    reader_page.keyboard.press("Control+s")
    poll(reader_page, lambda: silent, message="the save never left")
    reader_page.clock.run_for(15_000)  # no answer in time
    wait_save_state(reader_page, "failed")
    assert editor_text(reader_page).endswith("no answer yet")
    reader_page.unroute("**/api/notes/save")
    reader_page.clock.run_for(2_000)  # the first retry
    wait_save_state(reader_page, "clean")
    assert chapter_one(library, doc).read_bytes().endswith(b"no answer yet")


def test_the_server_stopped_then_started_again(library, server_factory, reader_page):
    """The server goes away (VS Code closed, Quit) while typing: "server not reachable", the
    text kept here and as a draft. Started again, it has a new access token, so the page says
    to reload; after the reload (warned first) the draft is offered and saved."""
    doc, server = open_book(library, server_factory, reader_page)
    type_at_end(reader_page, "one")
    reader_page.keyboard.press("Control+s")
    wait_save_state(reader_page, "clean")
    server.stop()
    reader_page.keyboard.type(" two")
    reader_page.keyboard.press("Control+s")
    wait_save_state(reader_page, "offline")
    assert any(t.endswith("one two") for t in drafts_in_browser(reader_page).values())
    server_factory.restart(server)
    wait_save_state(reader_page, "restarted", timeout=30_000)  # retried, and told to reload
    expect(reader_page.locator("#mlNoteBar")).to_contain_text("reload this page")
    assert editor_text(reader_page).endswith("one two")
    assert leave(reader_page, "reload", stay=False)  # warned before the reload
    reader_page.wait_for_function("() => window.PDFViewerApplication?.pdfDocument")
    assert notes_settled(reader_page) in ("shown", "empty")
    wait_save_state(reader_page, "draft")
    reader_page.locator("#mlRestoreDraft").click()  # 恢复 (Restore)
    wait_save_state(reader_page, "clean")
    assert editor_text(reader_page).endswith("one two")
    assert chapter_one(library, doc).read_bytes().endswith(b"one two")
    assert drafts_in_browser(reader_page) == {}


def test_reloading_while_the_server_is_down(library, server_factory, reader_page):
    """Typed while the server is down, then the tab reloaded (warned), which fails: the text is
    in the draft. Once the server is back, opening the book offers it."""
    doc, server = open_book(library, server_factory, reader_page)
    server.stop()
    type_at_end(reader_page, "typed offline")
    wait_save_state(reader_page, "offline", timeout=20_000)
    poll(reader_page, lambda: any(t.endswith("typed offline")
                                  for t in drafts_in_browser(reader_page).values()))  # fmt: skip
    assert leave(reader_page, "reload", stay=False)  # warned; the reload itself fails
    server = server_factory.restart(server)
    open_document(reader_page, server, doc, page_no=2)
    notes_settled(reader_page)
    wait_save_state(reader_page, "draft")
    expect(reader_page.locator("#mlNoteBar")).to_contain_text("unsaved draft")
    reader_page.locator("#mlRestoreDraft").click()
    wait_save_state(reader_page, "clean")
    assert chapter_one(library, doc).read_bytes().endswith(b"typed offline")


def test_closing_with_unconfirmed_text_warns_and_stay_keeps_it(
    library, server_factory, reader_page
):
    doc, _ = open_book(library, server_factory, reader_page)
    held = []

    def hold_first(route):  # (no unroute: it would let the held request go too)
        if not held:
            held.append(route)
        else:
            route.continue_()

    reader_page.route("**/api/notes/save", hold_first)
    type_at_end(reader_page, "on its way")
    reader_page.keyboard.press("Control+s")
    poll(reader_page, lambda: held, message="the save never left")
    for how in ("close", "reload", "navigate"):
        assert leave(reader_page, how, stay=True), how  # "Leave site?" and Stay
    assert editor_text(reader_page).endswith("on its way")
    held[0].continue_()
    wait_save_state(reader_page, "clean")
    assert chapter_one(library, doc).read_bytes().endswith(b"on its way")
    assert not leave(reader_page, "close")  # all saved: no question


def test_closing_at_once_still_saves_a_small_note(library, server_factory, reader_page):
    """Typed and closed straight away (Leave): the last save is sent as the tab goes (best
    effort, for notes under 60 KB). A draft left behind that equals the file is spent quietly."""
    doc, server = open_book(library, server_factory, reader_page)
    type_at_end(reader_page, "closed at once")
    assert leave(reader_page, "close", stay=False)
    eventually(lambda: chapter_one(library, doc).read_bytes().endswith(b"closed at once"),
               message="the last save didn't arrive")  # fmt: skip
    again = reader_page.context.new_page()
    open_document(again, server, doc, page_no=2)
    notes_settled(again)
    assert wait_save_state(again, "clean") == "clean"
    assert drafts_in_browser(again) == {}


def test_a_draft_after_a_crash_is_offered_and_restored(library, server_factory, reader_page):
    doc, server = open_book(library, server_factory, reader_page)
    reader_page.route("**/api/notes/save", lambda route: route.fulfill(**FAIL))
    type_at_end(reader_page, "only in the draft")
    wait_save_state(reader_page, "failed")
    before = chapter_one(library, doc).read_bytes()
    context = reader_page.context
    crash(reader_page)
    again = context.new_page()
    open_document(again, server, doc, page_no=2)
    notes_settled(again)
    wait_save_state(again, "draft")
    assert editor_text(again).encode("utf-8") != before and "only in the draft" not in editor_text(
        again
    )
    expect(again.locator(EDITOR)).to_have_attribute("readonly", "")  # until a choice is made
    again.locator("#mlCompare").click()  # 对比 (Compare): the draft beside the file
    expect(again.locator("#mlCompareText")).to_have_value(
        __import__("re").compile("only in the draft$")
    )
    assert chapter_one(library, doc).read_bytes() == before  # nothing written by looking
    again.locator("#mlRestoreDraft").click()
    wait_save_state(again, "clean")
    assert chapter_one(library, doc).read_bytes().endswith(b"only in the draft")
    assert drafts_in_browser(again) == {}


def test_a_draft_after_the_file_changed_needs_a_choice(library, server_factory, reader_page):
    """Recovering a draft never overwrites a file changed since: it becomes a conflict."""
    doc, server = open_book(library, server_factory, reader_page)
    reader_page.route("**/api/notes/save", lambda route: route.fulfill(**FAIL))
    type_at_end(reader_page, "my draft")
    wait_save_state(reader_page, "failed")
    context = reader_page.context
    crash(reader_page)
    chapter_one(library, doc).write_bytes(b"# Chapter 1\n\nedited in VS Code meanwhile\n")
    again = context.new_page()
    open_document(again, server, doc, page_no=2)
    notes_settled(again)
    wait_save_state(again, "draft")
    again.locator("#mlRestoreDraft").click()
    wait_save_state(again, "conflict")
    assert chapter_one(library, doc).read_bytes() == b"# Chapter 1\n\nedited in VS Code meanwhile\n"
    again.locator("#mlKeepMine").click()  # 保留我的版本 (Keep mine)
    wait_save_state(again, "clean")
    assert chapter_one(library, doc).read_bytes().replace(b"\r\n", b"\n").endswith(b"my draft")
    kept = list((library.root / "archive" / "notes-conflicts").rglob("ch01-basics.*.md"))
    assert [k.read_bytes() for k in kept] == [b"# Chapter 1\n\nedited in VS Code meanwhile\n"]


def test_discarding_a_draft(library, server_factory, reader_page):
    doc, server = open_book(library, server_factory, reader_page)
    reader_page.route("**/api/notes/save", lambda route: route.fulfill(**FAIL))
    type_at_end(reader_page, "not wanted")
    wait_save_state(reader_page, "failed")
    before = chapter_one(library, doc).read_bytes()
    context = reader_page.context
    crash(reader_page)
    again = context.new_page()
    open_document(again, server, doc, page_no=2)
    notes_settled(again)
    wait_save_state(again, "draft")
    again.locator("#mlDiscardDraft").click()  # 丢弃 (Discard)
    wait_save_state(again, "clean")
    assert drafts_in_browser(again) == {} and chapter_one(library, doc).read_bytes() == before
    expect(again.locator(EDITOR)).not_to_have_attribute("readonly", "")


def test_the_draft_stays_while_newer_text_is_unsaved(library, server_factory, reader_page):
    doc, _ = open_book(library, server_factory, reader_page)
    held = []

    def hold_first(route):
        if not held:
            held.append(route)
        else:
            route.continue_()

    reader_page.route("**/api/notes/save", hold_first)
    type_at_end(reader_page, "A")
    reader_page.keyboard.press("Control+s")
    poll(reader_page, lambda: held, message="the save never left")
    reader_page.keyboard.type("B")  # newer than the save on its way

    def draft_has_ab():
        return any(t.endswith("AB") for t in drafts_in_browser(reader_page).values())

    poll(reader_page, draft_has_ab, message="the draft didn't follow the typing")
    held[0].continue_()  # "A" confirmed; "AB" isn't yet
    wait_save_state(reader_page, "dirty", "saving")
    assert any(t.endswith("AB") for t in drafts_in_browser(reader_page).values())
    wait_save_state(reader_page, "clean")
    assert drafts_in_browser(reader_page) == {}
    assert chapter_one(library, doc).read_bytes().endswith(b"AB")


def test_a_browser_that_cant_keep_drafts_says_so(library, server_factory, reader_page):
    """Storage full or blocked: the panel says crash recovery isn't available (it never
    pretends); saving itself still works."""
    reader_page.add_init_script(
        """(() => {
          const own = Storage.prototype.setItem;
          Storage.prototype.setItem = function (key, value) {
            if (String(key).startsWith('myLibrary.draft.')) {
              throw new DOMException('the quota is exceeded', 'QuotaExceededError');
            }
            return own.call(this, key, value);
          };
        })()"""
    )
    doc, _ = open_book(library, server_factory, reader_page)
    type_at_end(reader_page, "no draft possible")
    reader_page.wait_for_function("() => document.body.dataset.mlDraft === 'failed'")
    expect(reader_page.locator("#mlNoteBar")).to_contain_text("can't keep a recovery draft")
    wait_save_state(reader_page, "clean")
    reader_page.wait_for_function("() => document.body.dataset.mlDraft === 'none'")
    assert chapter_one(library, doc).read_bytes().endswith(b"no draft possible")
