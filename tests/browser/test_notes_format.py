"""The notes' formatting toolbar and display preferences (task 4 M5c). Every action edits the
Markdown source only (format.js), as one insertText: one Undo reverts one action, and it is
saved like typing (autosave, conflicts); a second click takes it off again where practical.
Ctrl+B / Ctrl+I act only in the note and never reach PDF.js; nothing happens while the note
can't be typed in or a word is being composed. Display preferences are this browser's own and
never touch the note. Temporary libraries only."""

import json
import time
from pathlib import Path

import paths
import pytest
from helpers import EDITOR, editor_text, leave, type_at_end, wait_save_state
from playwright.sync_api import expect
from test_notes_preview import PREVIEW, choose_view, note_path, open_rich, saves

FORMAT_JS = paths.APP / "scripts" / "reader_static" / "format.js"
BAR = "#mlFormatBar"

# (text with [selection] or | caret, action, the text after it, then after the same action again)
CASES = [
    ("a [word] b", "bold", "a **[word]** b", "a [word] b"),
    ("a [word] b", "italic", "a *[word]* b", "a [word] b"),
    ("a [word] b", "strike", "a ~~[word]~~ b", "a [word] b"),
    ("a [word] b", "code", "a `[word]` b", "a [word] b"),
    ("a [x`y] b", "code", "a `` [x`y] `` b", "a [x`y] b"),
    ("a [x^2] b", "math", "a $[x^2]$ b", "a [x^2] b"),
    ("a [**word**] b", "bold", "a [word] b", "a **[word]** b"),
    ("a **[word]** b", "italic", "a ***[word]*** b", "a **[word]** b"),
    ("a [word ]b", "bold", "a **[word]** b", "a [word] b"),  # (spaces stay outside)
    ("a | b", "bold", "a **|** b", "a | b"),
    ("[one\ntwo]", "bold", "[**one**\n**two**]", "[one\ntwo]"),
    ("[- one\n- two]", "italic", "[- *one*\n- *two*]", "[- one\n- two]"),
    ("Ti|tle", "h1", "# Ti|tle", "Ti|tle"),
    ("Ti|tle", "h2", "## Ti|tle", "Ti|tle"),
    ("Ti|tle", "h3", "### Ti|tle", "Ti|tle"),
    ("Ti|tle", "h4", "#### Ti|tle", "Ti|tle"),
    ("Ti|tle", "h5", "##### Ti|tle", "Ti|tle"),
    ("Ti|tle", "h6", "###### Ti|tle", "Ti|tle"),
    ("## Ti|tle", "h3", "### Ti|tle", "Ti|tle"),
    ("## Ti|tle", "h0", "Ti|tle", "Ti|tle"),
    ("[one\ntwo]", "bullet", "[- one\n- two]", "[one\ntwo]"),
    ("[1. one\n2. two]", "bullet", "[- one\n- two]", "[one\ntwo]"),
    ("[one\ntwo]", "number", "[1. one\n2. two]", "[one\ntwo]"),
    ("[one\ntwo]", "task", "[- [ ] one\n- [ ] two]", "[one\ntwo]"),
    ("- o|ne", "task", "- [ ] o|ne", "o|ne"),
    ("  [nested]", "bullet", "  - [nested]", "  [nested]"),
    ("[one\n\ntwo]", "quote", "[> one\n>\n> two]", "[one\n\ntwo]"),
    ("[x = 1]", "codeblock", "```\n[x = 1]\n```", "[x = 1]"),
    ("|", "codeblock", "```\n|\n```", "|"),
    ("[E = mc^2]", "mathblock", "$$\n[E = mc^2]\n$$", "[E = mc^2]"),
    ("see [docs]", "link", "see [docs]([https://])", "see [docs]"),
    ("see [[docs](https://x.org)]", "link", "see [docs]", "see [docs]([https://])"),
    ("[fig]", "image", "![fig]([image.png])", "[fig]"),
    ("text|", "table", "text\n\n| | |   |\n| --- | --- |\n|   |   |", None),
    (
        "before\n|\nafter",
        "table",
        "before\n\n| | |   |\n| --- | --- |\n|   |   |\n\nafter",
        None,
    ),  # fmt: skip
]


def parse(marked: str) -> tuple[str, int, int]:
    """'a [b] c' -> ('a b c', 2, 3); 'a | c' -> ('a  c', 2, 2)."""
    bracketed = "[" in marked and "]" in marked and marked.index("[") < marked.rindex("]")
    if "|" in marked and not bracketed:
        at = marked.index("|")
        return marked[:at] + marked[at + 1 :], at, at
    start = marked.index("[")
    end = marked.rindex("]") - 1
    return marked[:start] + marked[start + 1 : end + 1] + marked[end + 2 :], start, end


def show(value: str, start: int, end: int) -> str:
    if start == end:
        return value[:start] + "|" + value[start:]
    return value[:start] + "[" + value[start:end] + "]" + value[end:]


def test_every_action_gives_the_right_markdown_and_toggles_off(page):
    page.set_content("<html><body></body></html>")
    page.add_script_tag(content=FORMAT_JS.read_text(encoding="utf-8"))
    actions = set(page.evaluate("() => myLibraryFormat.actions"))
    assert {case[1] for case in CASES} == actions  # every action is checked
    for marked, action, once, twice in CASES:
        value, start, end = parse(marked)
        results = []
        for _ in range(2 if twice is not None else 1):
            edit = page.evaluate(
                "([v, s, e, a]) => myLibraryFormat.apply(v, s, e, a)", [value, start, end, action]
            )
            value = value[: edit["from"]] + edit["text"] + value[edit["to"] :]
            start, end = edit["selStart"], edit["selEnd"]
            results.append(show(value, start, end))
        expected = [once] + ([twice] if twice is not None else [])
        # (the table's caret sits in its first cell, shown here as "| |")
        assert results == [e.replace("| | |", "| |  |") if action == "table" else e
                           for e in expected], (marked, action)  # fmt: skip


def open_note(library, server_factory, page, content: str, clock=False):
    doc, _ = open_rich(library, server_factory, page, chapter_one=content, clock=clock)
    choose_view(page, "source")
    return doc


def select(page, start: int, end: int) -> None:
    page.evaluate(
        "([s, e]) => { const t = document.querySelector('#mlNoteText'); t.focus();"
        " t.setSelectionRange(s, e); }",
        [start, end],
    )


def selection(page) -> list[int]:
    return page.evaluate(
        "() => { const t = document.querySelector('#mlNoteText');"
        " return [t.selectionStart, t.selectionEnd]; }"
    )


def tool(page, action: str):
    return page.locator(f'{BAR} button[data-action="{action}"]')


TOOLBAR = {  # each button on "word" selected on a line of its own
    "bold": "**word**", "italic": "*word*", "strike": "~~word~~", "bullet": "- word",
    "number": "1. word", "task": "- [ ] word", "quote": "> word", "code": "`word`",
    "codeblock": "```\nword\n```", "link": "[word](https://)", "image": "![word](image.png)",
    "math": "$word$", "mathblock": "$$\nword\n$$",
    "table": "| word |   |\n| --- | --- |\n|   |   |",
}  # fmt: skip


def test_each_button_and_heading_edits_the_source(library, server_factory, reader_page):
    doc = open_note(library, server_factory, reader_page, "# Toolbar\n\nword\n")
    expect(reader_page.locator(BAR)).to_be_visible()
    assert reader_page.locator(f"{BAR} button").count() == len(TOOLBAR)
    start = len("# Toolbar\n\n")
    for action, expected in TOOLBAR.items():
        select(reader_page, start, start + 4)
        tool(reader_page, action).click()
        assert editor_text(reader_page) == f"# Toolbar\n\n{expected}\n", action
        assert reader_page.evaluate("() => document.activeElement.id") == "mlNoteText"  # kept
        reader_page.keyboard.press("Control+z")  # one Undo: the action is gone
        assert editor_text(reader_page) == "# Toolbar\n\nword\n", action
    prefix = 0  # the heading marker now before "word" ("## " …)
    for level in range(1, 7):
        select(reader_page, start + prefix + 2, start + prefix + 2)  # "wo|rd"
        reader_page.locator("#mlFormatHeading").select_option(f"h{level}")
        assert editor_text(reader_page) == f"# Toolbar\n\n{'#' * level} word\n"
        prefix = level + 1
        assert selection(reader_page) == [start + prefix + 2] * 2  # still "wo|rd"
        assert reader_page.locator("#mlFormatHeading").input_value() == ""  # ready again
    reader_page.locator("#mlFormatHeading").select_option("h0")
    assert editor_text(reader_page) == "# Toolbar\n\nword\n"
    select(reader_page, start, start + 4)
    tool(reader_page, "bold").click()
    reader_page.keyboard.press("Control+s")
    wait_save_state(reader_page, "clean")
    assert note_path(library, doc).read_text("utf-8") == "# Toolbar\n\n**word**\n"


def test_the_selection_stays_on_the_text(library, server_factory, reader_page):
    open_note(library, server_factory, reader_page, "alpha beta gamma\n")
    select(reader_page, 6, 10)  # beta
    tool(reader_page, "bold").click()
    assert editor_text(reader_page) == "alpha **beta** gamma\n"
    assert selection(reader_page) == [8, 12]  # still "beta"
    tool(reader_page, "italic").click()
    assert editor_text(reader_page) == "alpha ***beta*** gamma\n"
    assert selection(reader_page) == [9, 13]
    tool(reader_page, "quote").click()  # a line prefix: the selection moves with its text
    assert editor_text(reader_page) == "> alpha ***beta*** gamma\n"
    assert selection(reader_page) == [11, 15]
    select(reader_page, 0, 0)
    tool(reader_page, "quote").click()  # off again; the caret where the line starts
    assert editor_text(reader_page) == "alpha ***beta*** gamma\n"
    assert selection(reader_page) == [0, 0]


def test_undo_and_redo_one_action_at_a_time(library, server_factory, reader_page):
    doc = open_note(library, server_factory, reader_page, "")
    type_at_end(reader_page, "plain words")
    typed = editor_text(reader_page)
    select(reader_page, 0, 5)
    tool(reader_page, "bold").click()
    reader_page.keyboard.press("Control+i")
    tool(reader_page, "bullet").click()
    steps = [editor_text(reader_page)]
    assert steps[0] == "- ***plain*** words"
    for expected in ("***plain*** words", "**plain** words", typed):
        reader_page.keyboard.press("Control+z")
        assert editor_text(reader_page) == expected
    for expected in ("**plain** words", "***plain*** words", "- ***plain*** words"):
        reader_page.keyboard.press("Control+y")
        assert editor_text(reader_page) == expected
    reader_page.keyboard.press("Control+s")
    wait_save_state(reader_page, "clean")
    assert note_path(library, doc).read_text("utf-8") == "- ***plain*** words"


def test_ctrl_b_and_ctrl_i_only_in_the_note(library, server_factory, reader_page):
    open_note(library, server_factory, reader_page, "some text\n")
    reader_page.evaluate(
        "() => { window.__keys = []; addEventListener('keydown', (e) => (e.ctrlKey"
        " && ['KeyB', 'KeyI'].includes(e.code)) && window.__keys.push(e.code)); }"
    )
    select(reader_page, 0, 4)
    reader_page.keyboard.press("Control+b")
    reader_page.keyboard.press("Control+i")
    assert editor_text(reader_page) == "***some*** text\n"
    assert reader_page.evaluate("() => window.__keys") == []  # never reached PDF.js's listeners
    page_before = reader_page.evaluate("() => PDFViewerApplication.page")
    reader_page.locator("#viewerContainer").focus()  # in the PDF: the note is left alone
    reader_page.keyboard.press("Control+b")
    reader_page.keyboard.press("Control+i")
    assert reader_page.evaluate("() => window.__keys") == ["KeyB", "KeyI"]  # PDF.js gets them
    assert editor_text(reader_page) == "***some*** text\n"
    reader_page.keyboard.press("n")  # PDF.js's own keys work as before
    reader_page.wait_for_function(f"() => PDFViewerApplication.page === {page_before + 1}")
    reader_page.keyboard.press("p")
    reader_page.wait_for_function(f"() => PDFViewerApplication.page === {page_before}")


def test_nothing_while_a_word_is_being_composed(library, server_factory, reader_page):
    doc = open_note(library, server_factory, reader_page, "")
    reader_page.locator(EDITOR).click()
    ime = reader_page.context.new_cdp_session(reader_page)
    ime.send("Input.imeSetComposition", {"text": "zhong", "selectionStart": 5, "selectionEnd": 5})
    expect(tool(reader_page, "bold")).to_be_disabled()  # while composing: no formatting
    reader_page.keyboard.press("Control+b")
    assert "*" not in editor_text(reader_page)  # the word being composed is untouched
    ime.send("Input.insertText", {"text": "中"})  # the word is chosen
    assert editor_text(reader_page) == "中"
    expect(tool(reader_page, "bold")).to_be_enabled()  # at once, without another key
    select(reader_page, 0, 1)
    tool(reader_page, "bold").click()  # and now it formats
    assert editor_text(reader_page) == "**中**"
    reader_page.keyboard.press("Control+s")
    wait_save_state(reader_page, "clean")
    assert note_path(library, doc).read_text("utf-8") == "**中**"


def test_the_toolbar_waits_while_the_note_cant_be_typed_in(library, server_factory, reader_page):
    open_note(library, server_factory, reader_page, "locked text\n")
    reader_page.locator("#mlNoteLock").click()  # 🔒 read-only
    expect(tool(reader_page, "bold")).to_be_disabled()
    expect(reader_page.locator("#mlFormatHeading")).to_be_disabled()
    select(reader_page, 0, 6)
    reader_page.keyboard.press("Control+b")
    assert editor_text(reader_page) == "locked text\n"
    reader_page.locator("#mlNoteLock").click()  # 🔓
    expect(tool(reader_page, "bold")).to_be_enabled()
    select(reader_page, 0, 6)
    reader_page.keyboard.press("Control+b")
    assert editor_text(reader_page) == "**locked** text\n"


def test_formatting_autosaves_like_typing(library, server_factory, reader_page):
    doc = open_note(library, server_factory, reader_page, "auto saved\n", clock=True)
    sent = saves(reader_page)
    select(reader_page, 0, 4)
    tool(reader_page, "strike").click()
    assert reader_page.evaluate("() => document.body.dataset.mlSaveState") == "dirty"
    reader_page.clock.run_for(1_600)  # the autosave delay (D6)
    wait_save_state(reader_page, "clean")
    assert len(sent) == 1
    assert note_path(library, doc).read_text("utf-8") == "~~auto~~ saved\n"


def test_formatting_during_a_conflict_keeps_the_choice(library, server_factory, reader_page):
    doc = open_note(library, server_factory, reader_page, "mine to keep\n")
    note_path(library, doc).write_bytes(b"# Changed elsewhere\n")
    select(reader_page, 0, 4)
    tool(reader_page, "bold").click()
    reader_page.keyboard.press("Control+s")
    wait_save_state(reader_page, "conflict")
    assert note_path(library, doc).read_bytes() == b"# Changed elsewhere\n"  # never written over
    select(reader_page, 9, 11)  # "to" in "**mine** to keep"
    tool(reader_page, "italic").click()  # still typing here: kept as mine
    assert leave(reader_page, "close", stay=True)  # unsaved: still warned
    reader_page.locator("#mlNoteBar").get_by_role("button", name="Keep mine").click()
    wait_save_state(reader_page, "clean")
    assert note_path(library, doc).read_text("utf-8") == "**mine** *to* keep\n"


def test_the_toolbar_follows_the_views(library, server_factory, reader_page):
    open_note(library, server_factory, reader_page, "x squared\n")
    choose_view(reader_page, "preview")
    expect(reader_page.locator(BAR)).to_be_hidden()  # formatting edits the source
    choose_view(reader_page, "split")
    expect(reader_page.locator(BAR)).to_be_visible()
    select(reader_page, 0, 1)
    tool(reader_page, "bold").click()
    expect(reader_page.locator(f"{PREVIEW} strong")).to_have_text("x")
    select(reader_page, len("**x** "), len("**x** squared"))
    tool(reader_page, "math").click()  # maths (M5b) from the button
    expect(reader_page.locator(f"{PREVIEW} .ml-math .katex")).to_have_count(1)
    assert editor_text(reader_page) == "**x** $squared$\n"


def test_a_narrow_panel_wraps_the_toolbar(library, server_factory, reader_page):
    reader_page.set_viewport_size({"width": 700, "height": 900})
    open_note(library, server_factory, reader_page, "narrow\n")
    sizes = reader_page.evaluate(
        "() => { const b = document.getElementById('mlFormatBar');"
        " return [b.scrollWidth, b.clientWidth, document.getElementById('mlNotes').clientWidth]; }"
    )
    assert sizes[0] <= sizes[1] + 1 and sizes[1] <= sizes[2]  # never wider than the panel


DISPLAY = "#mlDisplay"
CHOICES = {"font": "serif", "size": "18", "line": "2", "para": "1.6", "width": "narrow"}


def styles(page) -> dict:
    return page.evaluate(
        """() => {
          const t = getComputedStyle(document.getElementById('mlNoteText'));
          const preview = document.getElementById('mlNotePreview');
          const p = preview.querySelector('p');
          return { textFont: t.fontFamily, textSize: t.fontSize, textLine: t.lineHeight,
                   textMax: t.maxWidth, previewSize: getComputedStyle(preview).fontSize,
                   paragraph: p ? getComputedStyle(p).marginBottom : null,
                   paragraphWidth: p ? p.getBoundingClientRect().width : null,
                   previewWidth: preview.clientWidth };
        }"""
    )


def test_display_preferences_are_this_browsers_only(library, server_factory, reader_page):
    doc = open_note(library, server_factory, reader_page, "# Look\n\nOne paragraph.\n\nTwo.\n")
    before = note_path(library, doc).read_bytes()
    sent = saves(reader_page)
    choose_view(reader_page, "split")
    default = styles(reader_page)
    assert default["textSize"] == "14px" and default["paragraph"] == "11.2px"  # as before M5c
    reader_page.locator("#mlDisplayToggle").click()
    expect(reader_page.locator(DISPLAY)).to_be_visible()
    for name, value in CHOICES.items():
        reader_page.locator(f'{DISPLAY} select[data-pref="{name}"]').select_option(value)
    chosen = styles(reader_page)
    assert "Georgia" in chosen["textFont"] and chosen["textSize"] == "18px"
    assert chosen["textLine"] == "36px" and chosen["previewSize"] == "18px"
    assert chosen["paragraph"] == "28.8px"  # 1.6 em at 18 px
    assert chosen["textMax"] == "min(100%, 612px)"  # 34 em at 18 px
    assert chosen["paragraphWidth"] <= 34 * 18 + 1
    stored = json.loads(
        reader_page.evaluate("() => localStorage.getItem('myLibrary.notes.display')")
    )
    assert stored == CHOICES
    reader_page.reload()  # remembered in this browser
    reader_page.wait_for_function("() => document.body.dataset.mlNoteState === 'shown'")
    assert styles(reader_page)["textSize"] == "18px"
    assert reader_page.locator(f'{DISPLAY} select[data-pref="width"]').input_value() == "narrow"
    reader_page.locator("#mlDisplayToggle").click()
    reader_page.locator("#mlDisplayReset").click()
    assert styles(reader_page)["textSize"] == "14px"
    reader_page.wait_for_timeout(2_000)  # longer than the autosave delay: nothing is saved
    assert sent == [] and note_path(library, doc).read_bytes() == before


@pytest.mark.parametrize("stored", ["not json", '{"size": "99", "font": "comic"}', "[1, 2]"])
def test_unknown_stored_preferences_fall_back_to_the_defaults(
    library, server_factory, reader_page, stored
):
    reader_page.context.add_init_script(
        f"try {{ localStorage.setItem('myLibrary.notes.display', {json.dumps(stored)}); }}"
        " catch {}"
    )
    open_note(library, server_factory, reader_page, "text\n")
    assert styles(reader_page)["textSize"] == "14px"
    assert reader_page.evaluate("() => document.body.dataset.mlNoteDisplay") == (
        "font=system size=14 line=1.6 para=0.8 width=full"
    )


def test_the_note_file_is_untouched_by_display_and_views(library, server_factory, reader_page):
    content = "# Same\n\n**bold** and $x$\n"
    doc = open_note(library, server_factory, reader_page, content)
    reader_page.locator("#mlDisplayToggle").click()
    reader_page.locator(f'{DISPLAY} select[data-pref="size"]').select_option("20")
    for name in ("preview", "split", "source"):
        choose_view(reader_page, name)
    time.sleep(0.1)
    assert editor_text(reader_page) == content
    assert Path(note_path(library, doc)).read_text("utf-8") == content
