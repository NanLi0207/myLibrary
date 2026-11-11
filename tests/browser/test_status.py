"""Reading status on the library page (RS1): Automatic (derived: Reading once a chapter is
ticked or a page read, else To Read; never Finished), To Read, Reading or Finished, chosen by
the user and kept in the notes README. Sort: progress puts Reading (furthest first), then To
Read (newest added first), then Finished (most recently finished first); a status filter,
remembered in this browser; "Mark as finished?" at 100%, only on a click. Saved like ticks
(B32): saving, failed with Retry, a conflict with Apply mine / OK, the leave warning.
Temporary libraries only."""

from datetime import date

import catalog
import library_page
from helpers import leave
from playwright.sync_api import expect
from test_ticks import Held, click_tick, open_library

TWO = (
    "# {title}\n\n## Reading progress\n\n{last}- [{a}] Chapter 1: Basics\n- [{b}] Chapter 2: More\n"
)
TODAY = date.today().isoformat()


def book(library, slug, title, *, ticks=(" ", " "), last="", status="", added=""):
    doc = library.add_book(slug, title)
    text = TWO.format(title=title, last=last, a=ticks[0], b=ticks[1])
    if status:
        text = text.replace("- [", f"{status}\n\n- [", 1)
    (library.root / library.row(doc)["notes"] / "README.md").write_text(text, encoding="utf-8")
    if added:
        catalog.set_field(library.catalog, doc, "added", added)
    return doc


ORDER = (  # the documents shown, in order (a list line and its card count once)
    "() => [...document.querySelectorAll('#grid [data-id]')].map(e => e.dataset.id)"
    ".filter((id, i, all) => all.indexOf(id) === i)"
)


def readme(library, doc) -> str:
    return library.readme(doc)


def status_lines(library, doc) -> list[str]:
    return [
        line for line in readme(library, doc).splitlines() if line.startswith("Reading status:")
    ]


def menu(page, doc):
    return page.locator(f'[data-id="{doc}"] select[data-status]').first


def choose(page, doc, value) -> None:
    menu(page, doc).select_option(value)


def settled(page, doc) -> None:
    page.wait_for_function(
        'doc => { const m = document.querySelector(`[data-id="${doc}"] select[data-status]`);'
        " return m && !m.dataset.save; }",
        arg=doc,
    )


def order(page) -> list[str]:
    return page.evaluate(ORDER)


def test_each_choice_is_kept_in_the_readme(library, server, reader_page):
    doc = book(library, "doe-2020-status", "Status")
    open_library(reader_page, server)
    expect(menu(reader_page, doc).locator("option").first).to_have_text("Automatic (To Read)")
    choices = (
        ("to-read", "Reading status: to read"),
        ("reading", "Reading status: reading"),
        ("finished", f"Reading status: finished ({TODAY})"),
    )
    for value, line in choices:
        choose(reader_page, doc, value)
        settled(reader_page, doc)
        assert status_lines(library, doc) == [line]
    expect(reader_page.locator(f'[data-id="{doc}"] .status-date')).to_have_text(f"since {TODAY}")
    choose(reader_page, doc, "auto")
    settled(reader_page, doc)
    assert status_lines(library, doc) == []
    click_tick(reader_page, doc, 1)  # reading activity: Automatic now means Reading
    expect(menu(reader_page, doc).locator("option").first).to_have_text("Automatic (Reading)")
    reader_page.reload()  # kept on disk, read again
    expect(menu(reader_page, doc)).to_have_value("auto")
    assert not leave(reader_page, "close")  # all saved: no question


def test_all_read_is_suggested_never_assumed(library, server, reader_page):
    doc = book(library, "doe-2020-done", "Done", ticks=("x", "x"))  # every chapter ticked
    open_library(reader_page, server)
    expect(menu(reader_page, doc)).to_have_value("auto")  # 100%, still not Finished
    expect(menu(reader_page, doc).locator("option").first).to_have_text("Automatic (Reading)")
    suggestion = reader_page.locator(f'[data-id="{doc}"] [data-finish]').first
    expect(suggestion).to_be_visible()
    reader_page.wait_for_timeout(500)
    assert status_lines(library, doc) == []  # nothing changed by itself
    suggestion.click()  # only on the user's click
    settled(reader_page, doc)
    assert status_lines(library, doc) == [f"Reading status: finished ({TODAY})"]
    expect(reader_page.locator(f'[data-id="{doc}"] [data-finish]')).to_have_count(0)


def test_finished_stays_finished_when_read_again(library, server, reader_page):
    doc = book(library, "doe-2020-again", "Again", status="Reading status: finished (2026-01-02)")
    open_library(reader_page, server)
    expect(menu(reader_page, doc)).to_have_value("finished")
    readme_path = library.root / library.row(doc)["notes"] / "README.md"
    text = readme_path.read_text(encoding="utf-8")  # reading it again: a new "Last read"
    heading = "## Reading progress\n\n"
    again = text.replace(heading, heading + f"Last read: page 2, {TODAY}\n", 1)
    readme_path.write_text(again, encoding="utf-8")
    reader_page.reload()
    expect(menu(reader_page, doc)).to_have_value("finished")
    assert status_lines(library, doc) == ["Reading status: finished (2026-01-02)"]


def test_progress_sort_reading_then_to_read_then_finished(library, server, reader_page):
    half = book(library, "a-2020-half", "Half read", ticks=("x", " "))
    full = book(library, "b-2020-full", "All read, not finished", ticks=("x", "x"))
    old = book(library, "c-2020-old", "To read, added long ago", added="2025-01-01")
    new = book(library, "d-2020-new", "To read, added lately", added="2026-06-01")
    chosen = book(library, "e-2020-chosen", "Chosen to read", ticks=("x", " "),
                  status="Reading status: to read", added="2026-03-01")  # fmt: skip
    earlier = book(library, "f-2020-earlier", "Finished earlier",
                   status="Reading status: finished (2026-02-01)")  # fmt: skip
    later = book(library, "g-2020-later", "Finished later", ticks=("x", "x"),
                 status="Reading status: finished (2026-05-01)")  # fmt: skip
    open_library(reader_page, server)
    reader_page.locator("#sort").select_option("progress")
    assert order(reader_page) == [full, half, new, chosen, old, later, earlier]


def test_the_status_filter_is_remembered(library, server, reader_page):
    reading = book(library, "a-2020-r", "Reading one", ticks=("x", " "))
    to_read = book(library, "b-2020-t", "To read one")
    finished = book(
        library, "c-2020-f", "Finished one", status="Reading status: finished (2026-01-01)"
    )
    open_library(reader_page, server)
    labels = reader_page.locator("#statusFilter option").all_inner_texts()
    assert labels == ["Any status (3)", "To Read (1)", "Reading (1)", "Finished (1)"]
    reader_page.locator("#statusFilter").select_option("finished")
    assert order(reader_page) == [finished]
    reader_page.reload()
    expect(reader_page.locator("#statusFilter")).to_have_value("finished")
    assert order(reader_page) == [finished]
    reader_page.locator("#statusFilter").select_option("to-read")
    assert order(reader_page) == [to_read]
    reader_page.locator("#statusFilter").select_option("")
    assert sorted(order(reader_page)) == sorted([reading, to_read, finished])


def test_a_failed_save_is_kept_with_retry(library, server, reader_page):
    doc = book(library, "doe-2020-fail", "Fail")
    open_library(reader_page, server)
    reader_page.route("**/api/status", lambda route: route.abort())
    choose(reader_page, doc, "finished")
    expect(reader_page.locator("#tickStatus")).to_contain_text("1 reading status not saved")
    expect(menu(reader_page, doc)).to_have_value("finished")  # as chosen, marked
    assert menu(reader_page, doc).get_attribute("data-save") == "failed"
    assert leave(reader_page, "close", stay=True)  # unsaved: the browser asks
    assert status_lines(library, doc) == []
    reader_page.unroute("**/api/status")
    reader_page.locator("#statusRetry").click()
    settled(reader_page, doc)
    assert status_lines(library, doc) == [f"Reading status: finished ({TODAY})"]
    expect(reader_page.locator("#tickStatus")).to_be_hidden()


def test_rapid_choices_end_in_the_last_one(library, server, reader_page):
    doc = book(library, "doe-2020-rapid", "Rapid")
    open_library(reader_page, server)
    held = Held(reader_page)
    reader_page.unroute("**/api/tick")
    reader_page.route("**/api/status", held._hold)
    choose(reader_page, doc, "reading")
    held.wait(reader_page, 1)
    choose(reader_page, doc, "finished")
    choose(reader_page, doc, "to-read")  # the last choice, while the first is on its way
    reader_page.wait_for_timeout(300)
    assert [b["status"] for b in held.bodies] == ["reading"]  # never two at once
    held.release()
    held.wait(reader_page, 1)
    assert (
        held.bodies[-1]["status"] == "to-read" and held.bodies[-1]["base"] > held.bodies[0]["base"]
    )
    held.release()
    settled(reader_page, doc)
    assert status_lines(library, doc) == ["Reading status: to read"]


def two_tabs(library, server, page_a, doc):
    """Tab A chooses To Read (held); tab B, on the same view, chooses Finished (saved)."""
    other = page_a.context.new_page()
    open_library(other, server)
    held = Held(page_a)
    page_a.unroute("**/api/tick")
    page_a.route("**/api/status", held._hold)
    choose(page_a, doc, "to-read")
    held.wait(page_a, 1)
    choose(other, doc, "finished")
    settled(other, doc)
    return other, held


def test_an_older_choice_never_overwrites_a_newer_one_ok(library, server, reader_page):
    doc = book(library, "doe-2020-conflict", "Conflict")
    open_library(reader_page, server)
    other, held = two_tabs(library, server, reader_page, doc)
    held.release()  # A's older choice, late
    conflict = reader_page.locator("#tickStatus .status-conflict")
    expect(conflict).to_contain_text("you chose To Read, but its reading status was changed")
    expect(conflict).to_contain_text("it is Finished now")
    assert status_lines(library, doc) == [f"Reading status: finished ({TODAY})"]  # kept
    expect(menu(reader_page, doc)).to_have_value("to-read")  # A's choice, still shown
    assert menu(reader_page, doc).get_attribute("data-save") == "conflict"
    reader_page.wait_for_timeout(1_000)
    assert len(held.bodies) == 1  # never sent again by itself
    conflict.get_by_role("button", name="OK").click()  # keep the newer one
    expect(menu(reader_page, doc)).to_have_value("finished")
    expect(reader_page.locator("#tickStatus")).to_be_hidden()
    other.close()


def test_an_older_choice_applied_only_when_the_user_says_so(library, server, reader_page):
    doc = book(library, "doe-2020-apply", "Apply")
    open_library(reader_page, server)
    other, held = two_tabs(library, server, reader_page, doc)
    held.release()
    conflict = reader_page.locator("#tickStatus .status-conflict")
    expect(conflict).to_be_visible()
    conflict.get_by_role("button", name="Apply mine").click()
    held.wait(reader_page, 1)
    assert (
        held.bodies[-1]["status"] == "to-read" and held.bodies[-1]["base"] > held.bodies[0]["base"]
    )
    held.release()
    settled(reader_page, doc)
    assert status_lines(library, doc) == ["Reading status: to read"]
    other.close()


def test_a_status_line_it_doesnt_understand_is_shown_not_changed(library, server, reader_page):
    doc = book(library, "doe-2020-odd", "Odd", status="Reading status: someday")
    open_library(reader_page, server)
    problem = reader_page.locator(f'[data-id="{doc}"] [data-status-problem]').first
    expect(problem).to_contain_text("not understood")
    assert "someday" in problem.get_attribute("title")
    expect(reader_page.locator(f'[data-id="{doc}"] select[data-status]')).to_have_count(0)
    assert status_lines(library, doc) == ["Reading status: someday"]


def test_the_static_page_shows_and_filters_without_editing(library, page, tmp_path, monkeypatch):
    reading = book(library, "a-2020-r", "Reading one", ticks=("x", " "))
    finished = book(
        library, "b-2020-f", "Finished one", status="Reading status: finished (2026-01-01)"
    )
    monkeypatch.setattr(library_page, "LIBRARY", library.root)  # (the test's library only)
    monkeypatch.setattr(library_page, "CATALOG", library.catalog)
    static = tmp_path / "library.html"  # outside the library: nothing written into it
    static.write_text(library_page.render(None), encoding="utf-8")
    page.goto(static.as_uri())
    expect(page.locator("select[data-status], [data-finish]")).to_have_count(0)
    expect(page.locator(f'[data-id="{reading}"] [data-status-text]').first).to_have_text(
        "Reading (automatic)"
    )
    expect(page.locator(f'[data-id="{finished}"] [data-status-text]').first).to_have_text(
        "Finished"
    )
    page.locator("#statusFilter").select_option("finished")
    assert order(page) == [finished]
