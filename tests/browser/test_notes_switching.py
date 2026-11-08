"""Switching notes in the reader's panel (audit P0-1): the box's text, the note it belongs to
and the session that saves it always agree. While another note loads, or after it failed to
load, the box is read-only and holds no other note's text, so typing can never save one note's
text into another's file; a late answer never replaces a newer choice; a composition started
in one note never leaves that note unable to autosave. Temporary libraries only."""

from helpers import EDITOR, editor_text, poll, type_at_end, wait_save_state
from playwright.sync_api import expect
from test_notes_content import CH1_SHOWN, VOCABULARY, choose
from test_notes_editing import note_file, open_chapter_one

FAIL = {"status": 500, "content_type": "application/json", "body": '{"error": "the disk is full"}'}
KEY = "() => document.body.dataset.mlNoteKey"


def shown(page, key: str, text: str | None = None) -> None:
    """Wait until note `key` is on screen (loaded, not loading), with `text` if given."""
    page.wait_for_function(
        "([k, t]) => document.body.dataset.mlNoteKey === k"
        " && document.body.dataset.mlNoteState !== 'loading'"
        " && (t === null || document.getElementById('mlNoteText').value === t)",
        arg=[key, text],
    )


def gets_of(page, key: str, answer=None) -> list:
    """Every /api/notes/get for note `key` is held (answered only when the test says), or,
    with `answer`, fulfilled with it. The held routes, in order."""
    held = []

    def handler(route):
        if (route.request.post_data_json or {}).get("key") != key:
            route.continue_()
        elif answer is not None:
            route.fulfill(**answer)
        else:
            held.append(route)

    page.route("**/api/notes/get", handler)
    return held


def files_of(library, doc) -> dict:
    folder = library.root / library.row(doc)["notes"]
    return {p.name: p.read_bytes() for p in sorted(folder.iterdir()) if p.is_file()}


def previously_opened_vocabulary(page) -> None:
    """The vocabulary note was opened (so loaded in this tab), then chapter 1 again."""
    choose(page, "file:vocabulary.md")
    shown(page, "file:vocabulary.md", VOCABULARY)
    choose(page, "file:ch01-basics.md")
    shown(page, "file:ch01-basics.md", CH1_SHOWN)


def test_typing_while_an_opened_note_loads_never_reaches_it(library, server_factory, reader_page):
    doc, _ = open_chapter_one(library, server_factory, reader_page)
    previously_opened_vocabulary(reader_page)
    before = files_of(library, doc)
    held = gets_of(reader_page, "file:vocabulary.md")
    choose(reader_page, "file:vocabulary.md")
    poll(reader_page, lambda: held, message="the note was never asked for")
    # Loading: the box holds no other note's text and takes no typing
    assert reader_page.evaluate(KEY) == "file:vocabulary.md"
    assert reader_page.evaluate(f"() => document.querySelector('{EDITOR}').readOnly")
    assert editor_text(reader_page) == ""
    reader_page.locator(EDITOR).click(force=True)
    reader_page.keyboard.press("Control+End")
    reader_page.keyboard.type("stray words")
    held[0].continue_()
    shown(reader_page, "file:vocabulary.md")
    assert editor_text(reader_page) == VOCABULARY  # its own text, nothing else
    wait_save_state(reader_page, "clean")
    assert files_of(library, doc) == before  # byte-identical, both notes

    # Normal editing and autosave on it still work, and go to its own file only
    type_at_end(reader_page, "new word")
    reader_page.keyboard.press("Control+s")
    wait_save_state(reader_page, "clean")
    after = files_of(library, doc)
    assert after["vocabulary.md"] == VOCABULARY.encode("utf-8") + b"new word"
    assert after["ch01-basics.md"] == before["ch01-basics.md"]


def test_a_failed_load_never_leaves_another_notes_text_editable(
    library, server_factory, reader_page
):
    doc, _ = open_chapter_one(library, server_factory, reader_page, clock=True)
    previously_opened_vocabulary(reader_page)
    before = files_of(library, doc)
    gets_of(reader_page, "file:vocabulary.md", answer=FAIL)
    choose(reader_page, "file:vocabulary.md")
    reader_page.wait_for_function("() => document.body.dataset.mlNoteState === 'error'")
    assert reader_page.evaluate(KEY) == "file:vocabulary.md"
    assert reader_page.evaluate(f"() => document.querySelector('{EDITOR}').readOnly")
    assert editor_text(reader_page) == ""  # not chapter 1's text under the vocabulary's name
    reader_page.locator(EDITOR).click(force=True)
    reader_page.keyboard.type("stray words")
    reader_page.clock.run_for(5_000)  # any autosave would have gone by now
    reader_page.unroute("**/api/notes/get")
    reader_page.locator("#mlNotesStatus button").click()  # Retry
    shown(reader_page, "file:vocabulary.md")
    assert editor_text(reader_page) == VOCABULARY
    assert files_of(library, doc) == before


def test_a_late_answer_never_replaces_a_newer_choice(library, server_factory, reader_page):
    doc, _ = open_chapter_one(library, server_factory, reader_page)
    previously_opened_vocabulary(reader_page)
    readme = note_file(library, doc, "README.md")
    before = files_of(library, doc)
    held = gets_of(reader_page, "file:vocabulary.md")
    choose(reader_page, "file:vocabulary.md")
    poll(reader_page, lambda: held, message="the note was never asked for")
    choose(reader_page, "file:README.md")  # chosen while the vocabulary is still loading
    shown(reader_page, "file:README.md")
    type_at_end(reader_page, "my own words")
    held[0].continue_()  # the vocabulary's answer arrives late
    reader_page.keyboard.press("Control+s")
    wait_save_state(reader_page, "clean")
    expect(reader_page.locator("#mlNoteSelect")).to_have_value("file:README.md")
    assert reader_page.evaluate(KEY) == "file:README.md"
    assert editor_text(reader_page).endswith("my own words")
    after = files_of(library, doc)
    assert after["README.md"] == readme.read_bytes() and after["README.md"].endswith(
        b"my own words"
    )
    assert after["vocabulary.md"] == before["vocabulary.md"]
    assert after["ch01-basics.md"] == before["ch01-basics.md"]


def test_a_composition_across_a_switch_never_stops_autosave(library, server_factory, reader_page):
    """A composition that starts in one note and ends after another is shown (the order a
    browser may deliver them in) ends in the note it started in: that note still autosaves."""
    doc, _ = open_chapter_one(library, server_factory, reader_page, clock=True)
    reader_page.evaluate(
        f"() => document.querySelector('{EDITOR}')"
        ".dispatchEvent(new CompositionEvent('compositionstart'))"
    )
    choose(reader_page, "file:vocabulary.md")
    shown(reader_page, "file:vocabulary.md", VOCABULARY)
    reader_page.evaluate(
        f"() => document.querySelector('{EDITOR}')"
        ".dispatchEvent(new CompositionEvent('compositionend'))"
    )
    choose(reader_page, "file:ch01-basics.md")
    shown(reader_page, "file:ch01-basics.md", CH1_SHOWN)
    type_at_end(reader_page, "typed later")
    reader_page.clock.run_for(1_600)  # the autosave delay (decision D6)
    wait_save_state(reader_page, "clean")
    assert note_file(library, doc, "ch01-basics.md").read_bytes().endswith(b"typed later")
    assert note_file(library, doc, "vocabulary.md").read_bytes() == VOCABULARY.encode("utf-8")
