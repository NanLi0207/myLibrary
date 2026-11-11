"""Chapter ticks on the library page (B32): a tick is the user's intention until the server
confirms it. Shown as "saving" meanwhile, kept and marked (with Retry) when it fails, reverted
to the README's state (and said so until dismissed) when the server refuses it; leaving with
one unsaved asks first. Each is stored in this browser (one entry per tab, chapter and click)
before it is sent and removed once confirmed, so a tab closed meanwhile sends it again when the
library's page opens: the newest click of each chapter, with its time, so the README, the
authority, is never overwritten by a click older than its last change. Entries that can't be
sent are removed and said so, never sent. Temporary libraries only."""

import json
import time

from helpers import eventually, leave
from playwright.sync_api import expect

TWO_CHAPTERS = "# Ticks\n\n## Reading progress\n\n- [ ] Chapter 1: Basics\n- [ ] Chapter 2: More\n"
CHAPTER_1 = {"done": False, "title": "Chapter 1: Basics", "number": 1, "note": ""}
CHAPTER_2 = {"done": False, "title": "Chapter 2: More", "number": 2, "note": ""}
STORE = "`myLibrary.tick.${encodeURIComponent(API.scope)}.`"  # (JavaScript: this library's)
ENTRIES = (  # this library's stored ticks, as the page keeps them
    f"() => Object.keys(localStorage).filter(k => k.startsWith({STORE}))"
    ".map(k => { try { return JSON.parse(localStorage.getItem(k)); } catch { return k; } })"
)
KEEP = (  # one stored entry, under the key the page itself would give it
    f"e => localStorage.setItem({STORE} + encodeURIComponent(e.id) + '.' + e.chapter + '.'"
    " + encodeURIComponent(e.op), JSON.stringify(e))"
)
DAY_MS = 86_400_000


def book(library, chapters: str = TWO_CHAPTERS) -> str:
    doc = library.add_book("doe-2020-ticks", "Ticks")
    (library.root / library.row(doc)["notes"] / "README.md").write_text(chapters, encoding="utf-8")
    return doc


def open_library(page, server) -> None:
    page.goto(server.base + "/")
    page.wait_for_function("() => typeof api === 'function' && API")
    page.mouse.click(5, 5)  # a user's click: browsers only ask before leaving after one


def box(page, doc: str, chapter: int):
    return page.locator(f'[data-id="{doc}"] input[data-tick="{chapter}"]').first


def click_tick(page, doc: str, chapter: int) -> None:
    """The user ticking (or unticking) the box (in a folded card too)."""
    page.evaluate(
        '([doc, n]) => document.querySelector(`[data-id="${doc}"] input[data-tick="${n}"]`)'
        ".click()",
        [doc, chapter],
    )


def ticked(library, doc: str) -> list[bool]:
    text = library.readme(doc)
    return [f"- [x] Chapter {n}:" in text for n in (1, 2)]


def pending(page) -> list:
    return page.evaluate(ENTRIES)


def now_ms() -> float:
    return time.time() * 1000


class Held:
    """/api/tick requests held until released (a slow server), answered or failed."""

    def __init__(self, page):
        self.routes = []
        self.bodies = []
        page.route("**/api/tick", self._hold)

    def _hold(self, route):
        self.bodies.append(json.loads(route.request.post_data))
        self.routes.append(route)

    def wait(self, page, count: int) -> None:
        end = time.monotonic() + 10
        while len(self.routes) < count and time.monotonic() < end:
            page.wait_for_timeout(50)
        assert len(self.routes) >= count, f"{len(self.routes)} tick requests, not {count}"

    def release(self) -> None:
        while self.routes:
            self.routes.pop(0).continue_()


def saved(page, doc: str, chapter: int) -> None:
    page.wait_for_function(
        "([doc, n]) => { const b = document.querySelector("
        '`[data-id="${doc}"] input[data-tick="${n}"]`); return b && !b.dataset.save; }',
        arg=[doc, chapter],
    )


def lost(page) -> None:
    """Every /api/tick request of this page fails on its way (a dropped connection): the tick
    never reaches the server, as when the tab is ended before it goes out. (A request held
    back instead may still go out after the tab closes: a keepalive request outlives it.)"""
    page.route("**/api/tick", lambda route: route.abort())


def sent_ticks(page) -> list:
    sent = []
    page.on("request", lambda r: "/api/tick" in r.url and sent.append(json.loads(r.post_data)))
    return sent


def test_saved_only_when_the_server_confirms(library, server, reader_page):
    doc = book(library)
    open_library(reader_page, server)
    held = Held(reader_page)
    click_tick(reader_page, doc, 1)
    held.wait(reader_page, 1)
    expect(box(reader_page, doc, 1)).to_be_checked()  # as clicked, at once
    assert box(reader_page, doc, 1).get_attribute("data-save") == "saving"
    expect(reader_page.locator("#tickStatus")).to_contain_text("Saving 1 tick")
    assert [e["done"] for e in pending(reader_page)] == [True]  # kept before it was sent
    assert ticked(library, doc) == [False, False]  # nothing on disk yet
    held.release()
    saved(reader_page, doc, 1)
    expect(reader_page.locator("#tickStatus")).to_be_hidden()
    assert ticked(library, doc) == [True, False]
    assert pending(reader_page) == []  # confirmed: forgotten


def test_leaving_asks_only_while_a_tick_is_unsaved(library, server, reader_page):
    doc = book(library)
    open_library(reader_page, server)
    held = Held(reader_page)
    click_tick(reader_page, doc, 1)
    held.wait(reader_page, 1)
    assert leave(reader_page, "close", stay=True)  # a slow answer: the browser asks
    held.release()
    saved(reader_page, doc, 1)
    assert not leave(reader_page, "close")  # all saved: closes without asking
    assert ticked(library, doc) == [True, False]


def test_a_refused_tick_goes_back_to_the_readme_and_says_so(library, server, reader_page):
    doc = book(library)
    open_library(reader_page, server)
    answers = iter([
        (409, {"error": "the notes of chapter 1 changed after that click",
               "chapter_list": [CHAPTER_1, CHAPTER_2]}),
        (400, {"error": "chapter 2 not found in README.md"}),
    ])  # fmt: skip

    def refuse(route):
        status, body = next(answers)
        route.fulfill(status=status, json=body)

    reader_page.route("**/api/tick", refuse)
    status = reader_page.locator("#tickStatus")
    click_tick(reader_page, doc, 1)
    expect(status).to_contain_text("Not saved: “Ticks”, chapter 1: its notes changed")
    expect(box(reader_page, doc, 1)).not_to_be_checked()  # the README's state, shown
    click_tick(reader_page, doc, 2)
    expect(status).to_contain_text("Not saved: “Ticks”, chapter 2: chapter 2 not found")
    expect(box(reader_page, doc, 2)).not_to_be_checked()
    reader_page.wait_for_timeout(5_000)  # (longer than a toast): still shown
    expect(status.locator(".tick-notice")).to_have_count(2)
    assert pending(reader_page) == []  # refused: nothing kept to send again
    for _ in range(2):
        status.locator(".tick-notice button").first.click()  # OK: read
    expect(status).to_be_hidden()
    assert not leave(reader_page, "close")
    assert ticked(library, doc) == [False, False]


def test_no_answer_keeps_the_tick_and_retry_saves_it(library, server, reader_page):
    doc = book(library)
    open_library(reader_page, server)
    failures = iter(["abort", "500"])

    def fail(route):
        if next(failures, "pass") == "abort":
            route.abort()  # no connection
        else:
            route.fulfill(status=500, json={"error": "server error"})

    reader_page.route("**/api/tick", fail)
    click_tick(reader_page, doc, 1)
    expect(reader_page.locator("#tickStatus")).to_contain_text("1 tick not saved")
    expect(box(reader_page, doc, 1)).to_be_checked()  # the intention is kept, marked
    assert box(reader_page, doc, 1).get_attribute("data-save") == "failed"
    assert [e["done"] for e in pending(reader_page)] == [True]
    reader_page.locator("#tickRetry").click()  # a server error this time: still not saved
    expect(reader_page.locator("#tickStatus")).to_contain_text("1 tick not saved")
    assert leave(reader_page, "close", stay=True)  # unsaved: the browser asks
    assert ticked(library, doc) == [False, False]
    reader_page.unroute("**/api/tick")
    reader_page.locator("#tickRetry").click()
    saved(reader_page, doc, 1)
    assert ticked(library, doc) == [True, False] and pending(reader_page) == []


def test_rapid_clicks_end_in_the_last_one(library, server, reader_page):
    doc = book(library)
    open_library(reader_page, server)
    held = Held(reader_page)
    for _ in range(3):  # on, off, on: while the first is on its way
        click_tick(reader_page, doc, 1)
    click_tick(reader_page, doc, 2)
    held.wait(reader_page, 2)  # one for each chapter, never two at once for one
    reader_page.wait_for_timeout(300)
    assert sorted((b["chapter"], b["done"]) for b in held.bodies) == [(1, True), (2, True)]
    expect(box(reader_page, doc, 1)).to_be_checked()
    click_tick(reader_page, doc, 1)  # off again, still waiting
    kept = sorted((e["chapter"], e["done"]) for e in pending(reader_page))
    assert kept == [(1, False), (2, True)]  # one entry a chapter: the newer replaced the older
    held.release()
    held.wait(reader_page, 1)  # the last click, sent after the first answer
    assert held.bodies[-1] == {"id": doc, "chapter": 1, "done": False}
    held.release()
    saved(reader_page, doc, 1)
    saved(reader_page, doc, 2)
    assert ticked(library, doc) == [False, True]
    assert len(held.bodies) == 3 and pending(reader_page) == []


def test_a_tab_closed_before_the_answer_sends_it_again(library, server, reader_page):
    """Ended at once (no beforeunload, as a crash or a killed tab): the tick never reached the
    server; the next time the library's page opens, it is sent again and saved."""
    doc = book(library)
    open_library(reader_page, server)
    lost(reader_page)  # the request never reaches the server
    click_tick(reader_page, doc, 2)
    reader_page.wait_for_function(f"() => ({ENTRIES})().length === 1")
    context = reader_page.context
    reader_page.close()  # (Playwright's default: no beforeunload)
    assert ticked(library, doc) == [False, False]
    again = context.new_page()
    sent = sent_ticks(again)
    again.goto(server.base + "/")
    eventually(lambda: ticked(library, doc) == [False, True], message="the tick wasn't sent again")
    assert len(sent) == 1 and sent[0]["done"] is True
    assert 0 < sent[0]["since"] <= now_ms()  # with the click's time (ms)
    again.wait_for_function(f"() => ({ENTRIES})().length === 0")
    expect(again.locator("#tickStatus")).to_be_hidden()
    again.close()


def test_a_closed_tab_after_saving_leaves_nothing_to_send(library, server, reader_page):
    doc = book(library)
    open_library(reader_page, server)
    click_tick(reader_page, doc, 1)
    saved(reader_page, doc, 1)
    context = reader_page.context
    assert not leave(reader_page, "close")
    again = context.new_page()
    sent = sent_ticks(again)
    again.goto(server.base + "/")
    again.wait_for_function("() => typeof api === 'function' && API")
    again.wait_for_timeout(500)
    assert sent == [] and ticked(library, doc) == [True, False]
    again.close()


def test_an_older_click_never_overwrites_a_later_change(library, server, reader_page):
    """A tick kept from before the README's last change (e.g. unticked in an editor since) is
    refused by the server, removed and said so; the README stays as it is."""
    doc = book(library)
    open_library(reader_page, server)
    long_ago = now_ms() - 600_000  # before the README was written
    reader_page.evaluate(
        KEEP, {"id": doc, "chapter": 1, "done": True, "op": "old", "time": long_ago}
    )
    reader_page.reload()
    expect(reader_page.locator("#tickStatus")).to_contain_text(
        "Not saved: “Ticks”, chapter 1: its notes changed"
    )
    assert ticked(library, doc) == [False, False]
    assert pending(reader_page) == []
    recent = now_ms()  # after the README's last change: applied
    reader_page.evaluate(KEEP, {"id": doc, "chapter": 1, "done": True, "op": "new", "time": recent})
    reader_page.reload()
    eventually(lambda: ticked(library, doc) == [True, False], message="the recent tick wasn't sent")
    reader_page.wait_for_function(f"() => ({ENTRIES})().length === 0")


def test_entries_that_cant_be_sent_are_discarded_and_said_so(library, server, reader_page):
    doc = book(library)
    open_library(reader_page, server)
    sent = sent_ticks(reader_page)
    now = now_ms()
    for entry in (
        {"id": doc, "chapter": 1, "done": True, "op": "expired", "time": now - 31 * DAY_MS},
        {"id": doc, "chapter": 2, "done": True, "op": "future", "time": now + 2 * 3_600_000},
        {"id": "not-a-document", "chapter": 1, "done": True, "op": "gone", "time": now},
        {"id": doc, "chapter": 9, "done": True, "op": "no-chapter", "time": now},
        {"id": doc, "chapter": 1, "done": "yes", "op": "malformed", "time": now},
    ):
        reader_page.evaluate(KEEP, entry)
    reader_page.evaluate(f"() => localStorage.setItem({STORE} + 'damaged', '{{not json')")
    before = library.readme(doc)
    reader_page.reload()
    status = reader_page.locator("#tickStatus")
    expect(status).to_contain_text("6 ticks from an earlier visit couldn't be sent and were "
                                   "discarded, not saved")  # fmt: skip
    expect(status).not_to_contain_text(str(library.root))  # (no file paths)
    reader_page.wait_for_timeout(500)
    assert sent == [] and pending(reader_page) == [] and library.readme(doc) == before


def test_different_chapters_in_two_tabs(library, server, reader_page):
    doc = book(library)
    open_library(reader_page, server)
    other = reader_page.context.new_page()
    open_library(other, server)
    held_a, held_b = Held(reader_page), Held(other)
    click_tick(reader_page, doc, 1)
    click_tick(other, doc, 2)
    held_a.wait(reader_page, 1)
    held_b.wait(other, 1)
    kept = sorted((e["chapter"], e["done"]) for e in pending(reader_page))
    assert kept == [(1, True), (2, True)]  # each tab's own entry, neither lost
    held_a.release()
    held_b.release()
    saved(reader_page, doc, 1)
    saved(other, doc, 2)
    assert ticked(library, doc) == [True, True] and pending(reader_page) == []
    other.close()


def test_the_same_chapter_in_two_tabs_the_newest_click_wins(library, server, reader_page):
    """Both tabs end before their answers (a crash): two entries for chapter 1, one each; the
    next page sends only the newest click and removes the older one."""
    doc = book(library)
    open_library(reader_page, server)
    other = reader_page.context.new_page()
    open_library(other, server)
    lost(reader_page), lost(other)  # the requests never reach the server
    click_tick(reader_page, doc, 1)  # tab A: on
    other.wait_for_timeout(20)
    click_tick(other, doc, 1)  # tab B: on …
    other.wait_for_timeout(20)
    click_tick(other, doc, 1)  # … then off: the newest
    entries = pending(reader_page)
    assert sorted(e["done"] for e in entries) == [False, True]  # A's and B's newest, both kept
    context = reader_page.context
    reader_page.close()
    other.close()
    again = context.new_page()
    sent = sent_ticks(again)
    again.goto(server.base + "/")
    again.wait_for_function(f"() => ({ENTRIES})().length === 0")
    assert [(b["chapter"], b["done"]) for b in sent] == [(1, False)]  # only the newest
    assert ticked(library, doc) == [False, False]
    again.close()


def test_two_tabs_send_the_same_tick_once_in_effect(library, server, reader_page):
    """Tab A's tick waits for its answer; tab B, opened meanwhile, sends the same stored tick
    again. The tick is an absolute state, so the second changes nothing."""
    doc = book(library)
    open_library(reader_page, server)
    held = Held(reader_page)
    click_tick(reader_page, doc, 1)
    held.wait(reader_page, 1)
    other = reader_page.context.new_page()
    other.goto(server.base + "/")
    eventually(lambda: ticked(library, doc) == [True, False], message="tab B didn't send it")
    other.wait_for_function("() => !document.querySelector('input[data-save]')")
    held.release()
    saved(reader_page, doc, 1)
    assert ticked(library, doc) == [True, False] and pending(reader_page) == []
    click_tick(other, doc, 1)  # B: off (B's newest click)
    saved(other, doc, 1)
    assert ticked(library, doc) == [False, False]
    other.close()
