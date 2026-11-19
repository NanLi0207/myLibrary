"""M7.1 S1a: a note being edited in a document that is merged into another meanwhile.

The real thing, end to end: the copy without your work is open in the reader and its chapter
note is being typed (the save can't get through yet); ⟳ Refresh (the server's own
/api/refresh) merges the identical copy into the one kept and retires it; the held save then
gets the server's real 410, never redirected. The draft stays under the document and note it
was typed in. In the document that stays, the notes panel offers it: restored only into a
note the user chooses, with the usual version check and conflict, and its original kept until
that save is confirmed; a failed or cancelled recovery keeps it. Synthetic library only."""

import json

from helpers import (
    drafts_in_browser,
    editor_text,
    notes_settled,
    open_document,
    poll,
    type_at_end,
    wait_save_state,
)
from playwright.sync_api import expect

KEPT_TEXT = "# Basics\n\nThe kept copy's own notes.\n"
TYPED = "typed in the copy that is merged away"


def merged_while_editing(library, server_factory, page, ch02: bytes | None = None):
    """(kept id, dropped id, server): the dropped copy's ch01 typed into while it is merged
    into the kept one; the panel has had the real 410. `ch02`: the kept copy's chapter 2 note
    (not written yet if None)."""
    kept = library.add_book("doe-2020-optics-test", "Optics test")
    files = {"ch01-basics.md": KEPT_TEXT.encode()}
    if ch02 is not None:
        files["ch02-stops.md"] = ch02
    library.add_notes(kept, ["Basics", "Stops"], files)
    dropped = library.add_book("doe-2020-optics-test-copy", "Optics test (copy)")
    library.add_notes(dropped, ["Basics"], {})  # (a chapter note not written yet: no work)
    for doc in (kept, dropped):
        library.cache_chapter_pages(doc, {1: 1, 2: 3})
    assert library.pdf(kept).read_bytes() == library.pdf(dropped).read_bytes()  # (identical)
    tried = library.root / ".cache" / "subjects_tried.json"  # (Refresh asks nothing online)
    tried.write_text(json.dumps([kept, dropped]), encoding="utf-8")
    server = server_factory()
    open_document(page, server, dropped)
    notes_settled(page)
    page.route("**/api/notes/save", lambda route: route.abort())  # (not through yet)
    type_at_end(page, TYPED)
    wait_save_state(page, "offline", timeout=20_000)
    poll(page, lambda: any(dropped in k and t.endswith(TYPED)
                           for k, t in drafts_in_browser(page).items()))  # fmt: skip
    server.post("/api/refresh", {})  # ⟳ Refresh: the real merge and retirement
    assert dropped not in library_ids(library) and kept in library_ids(library)
    page.unroute("**/api/notes/save")
    page.locator("#mlRetry").click()
    wait_save_state(page, "restarted")  # the server's 410: nothing saved, nothing redirected
    expect(page.locator("#mlNoteBar")).to_contain_text("merged into another")
    assert editor_text(page).endswith(TYPED)
    assert kept_note(library, kept).read_bytes() == KEPT_TEXT.encode()
    assert not (library.root / "notes" / "doe-2020-optics-test-copy").exists()
    return kept, dropped, server


def library_ids(library) -> set[str]:
    from catalog import load

    return set(load(library.catalog))


def kept_note(library, kept, name="ch01-basics.md"):
    return library.root / library.row(kept)["notes"] / name


def original_draft(page, dropped) -> list[str]:
    """The texts of `dropped`'s drafts still offered: in storage and not marked as dealt with
    (a marker binds the exact stored string, note_session.js drafts.settle)."""
    return page.evaluate(
        """id => Object.keys(localStorage)
            .filter(k => k.startsWith('myLibrary.draft.') && k.includes(`:${id}|`))
            .filter(k => {
              try {
                const m = JSON.parse(localStorage.getItem('myLibrary.settled.' + k));
                return m?.raw !== localStorage.getItem(k);
              } catch { return true; }
            })
            .map(k => JSON.parse(localStorage.getItem(k)).text)""",
        dropped,
    )


def second_tab(page, server, kept):
    """Another tab of the same browser on the kept document (its own tab id: other drafts)."""
    other = page.context.new_page()
    open_document(other, server, kept)
    notes_settled(other)
    return other


def typed_on_in_the_first_tab(first, dropped, more: str) -> str:
    """The first tab (still on the merged copy, after its 410) goes on typing: its draft, under
    the same storage key, is now newer than the one offered elsewhere."""
    type_at_end(first, more)
    text = editor_text(first)
    assert text.endswith(more)
    poll(first, lambda: original_draft(first, dropped) == [text],
         message="the first tab's newer draft was never written")  # fmt: skip
    return text


def go_to_the_kept_document(page):
    """The 410 bar's "Open the document that stays" (a reload past the "Leave site?" asked
    because the text isn't saved)."""
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator("#mlOpenKept").click()
    page.wait_for_function("() => window.PDFViewerApplication?.pdfDocument"
                           " && document.getElementById('mlUndo')")  # fmt: skip
    notes_settled(page)


def test_a_draft_of_a_merged_document_is_restored_where_the_user_chooses(
    library, server_factory, reader_page
):
    page = reader_page
    kept, dropped, _ = merged_while_editing(library, server_factory, page)
    go_to_the_kept_document(page)
    assert f"id={kept}" in page.url
    offer = page.locator("#mlElsewhere")
    expect(offer).to_be_visible()
    expect(offer).to_contain_text("Optics test (copy)")
    target = offer.locator(".ml-elsewhere-target")
    expect(target).to_have_value("file:ch01-basics.md")  # (the same note name: proposed)
    assert original_draft(page, dropped) == [TYPED]  # (nothing applied by itself)
    target.select_option("file:ch02-stops.md")  # the user's choice: a note not written yet
    offer.locator("#mlAdoptDraft").click()
    poll(page, lambda: kept_note(library, kept, "ch02-stops.md").exists(), timeout=20,
         message="the restored draft was never saved")  # fmt: skip
    wait_save_state(page, "clean", timeout=20_000)
    assert kept_note(library, kept, "ch02-stops.md").read_bytes().decode().endswith(TYPED)
    assert kept_note(library, kept).read_bytes() == KEPT_TEXT.encode()  # (untouched)
    poll(page, lambda: not original_draft(page, dropped), message="the original wasn't spent")
    expect(offer).to_be_hidden()


def test_a_failed_or_cancelled_recovery_keeps_the_draft(library, server_factory, reader_page):
    page = reader_page
    kept, dropped, _ = merged_while_editing(library, server_factory, page)
    go_to_the_kept_document(page)
    offer = page.locator("#mlElsewhere")
    # Into the kept copy's own written note: another version, so a conflict, never written
    # over; "Use the disk version" cancels (the draft's text is kept in archive/ too)
    offer.locator("#mlAdoptDraft").click()
    wait_save_state(page, "conflict")
    assert original_draft(page, dropped) == [TYPED]
    page.locator("#mlUseDisk").click()
    wait_save_state(page, "clean")
    assert kept_note(library, kept).read_bytes() == KEPT_TEXT.encode()
    assert original_draft(page, dropped) == [TYPED]
    expect(offer).to_be_visible()
    # A save that fails: the original stays
    page.route(
        "**/api/notes/save",
        lambda route: route.fulfill(
            status=500, content_type="application/json", body='{"error": "made by the test"}'
        ),
    )
    offer.locator(".ml-elsewhere-target").select_option("file:ch02-stops.md")
    offer.locator("#mlAdoptDraft").click()
    wait_save_state(page, "failed", timeout=20_000)
    assert original_draft(page, dropped) == [TYPED]
    assert not kept_note(library, kept, "ch02-stops.md").exists()
    # Still offered after a reload
    page.once("dialog", lambda dialog: dialog.accept())
    page.reload()
    page.wait_for_function("() => window.PDFViewerApplication?.pdfDocument")
    notes_settled(page)
    expect(page.locator("#mlElsewhere")).to_contain_text("Optics test (copy)")
    assert original_draft(page, dropped) == [TYPED]
    assert kept_note(library, kept).read_bytes() == KEPT_TEXT.encode()


def test_the_410_bar_saves_the_text_as_a_file(library, server_factory, reader_page):
    page = reader_page
    merged_while_editing(library, server_factory, page)
    with page.expect_download() as download:
        page.locator("#mlSaveDraftFile").click()
    assert open(download.value.path(), encoding="utf-8").read().endswith(TYPED)


def test_a_removed_documents_draft_can_be_saved_as_a_file(library, server_factory, reader_page):
    """A document removed (no document kept its work): its draft is offered in any other
    document's panel as a file to save, never restored into another note."""
    import catalog

    page = reader_page
    here = library.add_book("doe-2020-optics-test", "Optics test")
    library.add_notes(here, ["Basics"], {"ch01-basics.md": KEPT_TEXT.encode()})
    gone = library.add_book("roe-2021-gone-book", "A book removed")
    catalog.retire(library.catalog, gone, "removed", library.row(gone))
    catalog.remove(library.catalog, gone)
    server = server_factory()
    open_document(page, server, here)
    notes_settled(page)
    page.evaluate(
        """id => localStorage.setItem(
             `myLibrary.draft.${window.MYLIBRARY_SCOPE}:${id}|file:ch01-basics.md|othertab`,
             JSON.stringify({text: "written before it was removed", base: null, rev: 1,
                             time: Date.now()}))""",
        gone,
    )
    page.reload()
    page.wait_for_function("() => window.PDFViewerApplication?.pdfDocument")
    notes_settled(page)
    offer = page.locator("#mlElsewhere")
    expect(offer).to_contain_text("A book removed")
    expect(offer.locator("#mlAdoptDraft")).to_have_count(0)  # (nowhere to restore it into)
    with page.expect_download() as download:
        offer.locator("#mlElsewhereFile").click()
    saved = open(download.value.path(), encoding="utf-8").read()
    assert saved == "written before it was removed"
    assert original_draft(page, gone) == ["written before it was removed"]  # (kept)
    assert kept_note(library, here).read_bytes() == KEPT_TEXT.encode()


# --- Codex S1a re-review: draft identity and cleanup (two High findings) -------------------------


def test_a_newer_draft_from_another_tab_survives_an_older_recovery(
    library, server_factory, reader_page
):
    """Tab B restores the draft as listed; its save's answer is held while tab A (still on the
    merged copy) types on into the same draft. B's confirmation must never take A's newer
    text with it."""
    first = reader_page
    kept, dropped, server = merged_while_editing(library, server_factory, first)
    other = second_tab(first, server, kept)
    held = []
    other.route("**/api/notes/save", lambda route: held.append(route))
    offer = other.locator("#mlElsewhere")
    offer.locator(".ml-elsewhere-target").select_option("file:ch02-stops.md")
    offer.locator("#mlAdoptDraft").click()
    poll(other, lambda: held, message="the restored draft was never sent")
    newer = typed_on_in_the_first_tab(first, dropped, " and more from the first tab")
    held[0].continue_()  # the server writes the older snapshot and says so
    poll(other, lambda: kept_note(library, kept, "ch02-stops.md").exists(), timeout=20)
    wait_save_state(other, "clean", timeout=20_000)
    assert kept_note(library, kept, "ch02-stops.md").read_bytes().decode().endswith(TYPED)
    assert original_draft(other, dropped) == [newer]  # (A's newer text: still offered)
    expect(offer).to_be_visible()


def test_restored_text_replaced_before_it_is_saved_keeps_the_original(
    library, server_factory, reader_page
):
    page = reader_page
    kept, dropped, _ = merged_while_editing(library, server_factory, page)
    go_to_the_kept_document(page)
    page.route("**/api/notes/save", lambda route: route.abort())  # (not saved yet)
    offer = page.locator("#mlElsewhere")
    offer.locator(".ml-elsewhere-target").select_option("file:ch02-stops.md")
    offer.locator("#mlAdoptDraft").click()
    wait_save_state(page, "offline", "failed", timeout=20_000)
    page.locator("#mlNoteText").click()
    page.keyboard.press("Control+A")
    page.keyboard.type("something else entirely")  # the restored text replaced
    page.unroute("**/api/notes/save")
    page.locator("#mlRetry").click()
    poll(page, lambda: kept_note(library, kept, "ch02-stops.md").exists(), timeout=20)
    wait_save_state(page, "clean", timeout=20_000)
    assert kept_note(library, kept, "ch02-stops.md").read_bytes() == b"something else entirely"
    assert original_draft(page, dropped) == [TYPED]  # (its text was never saved: kept)
    expect(offer).to_be_visible()


def test_a_draft_already_in_the_chosen_note_is_dealt_with(library, server_factory, reader_page):
    page = reader_page
    kept, dropped, _ = merged_while_editing(library, server_factory, page, ch02=TYPED.encode())
    go_to_the_kept_document(page)
    offer = page.locator("#mlElsewhere")
    offer.locator(".ml-elsewhere-target").select_option("file:ch02-stops.md")
    offer.locator("#mlAdoptDraft").click()
    expect(offer).to_be_hidden()
    assert original_draft(page, dropped) == []
    assert kept_note(library, kept, "ch02-stops.md").read_bytes() == TYPED.encode()


def test_a_draft_already_in_the_note_but_rewritten_meanwhile_stays(
    library, server_factory, reader_page
):
    """The identical-content shortcut, raced: tab B finds the note already holds the draft's
    text, but tab A writes a newer draft there before B records it as dealt with."""
    first = reader_page
    kept, dropped, server = merged_while_editing(
        library, server_factory, first, ch02=TYPED.encode()
    )
    other = second_tab(first, server, kept)
    other.locator("#mlNoteSelect").select_option("file:ch02-stops.md")
    notes_settled(other)
    gets = []
    other.route("**/api/notes/get", lambda route: gets.append(route))
    offer = other.locator("#mlElsewhere")
    offer.locator(".ml-elsewhere-target").select_option("file:ch02-stops.md")
    offer.locator("#mlAdoptDraft").click()
    poll(other, lambda: gets, message="the note was never asked for")
    gets[0].continue_()  # (showing the chosen note)
    poll(other, lambda: len(gets) >= 2, message="the restore never read the note")
    newer = typed_on_in_the_first_tab(first, dropped, " and more from the first tab")
    gets[1].continue_()  # the restore finds the note equal to the snapshot it was bound to
    # (its outcome first: that snapshot dealt with; then the draft as it is now)
    expect(other.locator("#mlNotesStatus")).to_contain_text("restored and saved")
    expect(offer).to_be_visible()
    assert original_draft(other, dropped) == [newer]
    assert kept_note(library, kept, "ch02-stops.md").read_bytes() == TYPED.encode()


def test_a_stale_row_never_restores_a_newer_draft(library, server_factory, reader_page):
    first = reader_page
    kept, dropped, server = merged_while_editing(library, server_factory, first)
    other = second_tab(first, server, kept)
    offer = other.locator("#mlElsewhere")
    expect(offer).to_be_visible()  # (listed: the first snapshot)
    newer = typed_on_in_the_first_tab(first, dropped, " then more")
    offer.locator(".ml-elsewhere-target").select_option("file:ch02-stops.md")
    offer.locator("#mlAdoptDraft").click()  # the row is stale: nothing restored
    expect(other.locator("#mlNotesStatus")).to_contain_text("changed after it was listed")
    assert not kept_note(library, kept, "ch02-stops.md").exists()
    assert original_draft(other, dropped) == [newer]
    expect(offer).to_be_visible()  # (listed again: the newer snapshot)


def test_discarding_a_stale_row_keeps_a_newer_draft(library, server_factory, reader_page):
    first = reader_page
    kept, dropped, server = merged_while_editing(library, server_factory, first)
    other = second_tab(first, server, kept)
    offer = other.locator("#mlElsewhere")
    expect(offer).to_be_visible()  # (listed: the first snapshot)
    newer = typed_on_in_the_first_tab(first, dropped, " then more")
    other.once("dialog", lambda dialog: dialog.accept())
    offer.locator("#mlElsewhereDiscard").click()  # (the row shows the snapshot before)
    other.evaluate("() => 0")  # (after the click's handler: the page runs one task at a time)
    assert original_draft(other, dropped) == [newer], "discarding a stale row took the newer draft"
    expect(offer).to_be_visible()  # (still offered: the newer draft)
