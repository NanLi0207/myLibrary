"""The notes' preview (task 4 M5a): 源码 / 预览 / 分屏 (Source / Preview / Split) views of the
note, rendered with markdown-it (html: false). The preview only reads the session's text:
switching views never saves; autosave, conflicts and drafts work as in M4 in every view. Raw
HTML is shown as text and never run; only safe links are links; images aren't loaded yet.
Temporary libraries only; markdown-it from the tool's cache (reader.py --setup-preview)."""

import time

import pytest
from helpers import (
    EDITOR,
    editor_text,
    leave,
    notes_settled,
    open_document,
    type_at_end,
    wait_save_state,
)
from playwright.sync_api import expect

RICH = """# Rich note

Some *emphasis* and **strong** text.

## Lists here

- one
- two

1. first
2. second

> a quote

`inline code` and a block:

```python
print("$x$ stays code")
```

| Term | 中文 |
|---|---|
| pupil | 光瞳 |

<script>window.__pwned = 1</script>
<img src="x.png" onerror="window.__pwned = 2">

[js](javascript:window.__pwned=3) [data](data:text/html,hi) [web](https://example.com/page)
[below](#lists-here) [chapter two](ch02-aberrations.md) [unknown](other.md)

![a figure](figure.png)
"""
CH2 = "# Chapter 2: Aberrations\n\nAberrations text.\n"
PREVIEW = "#mlNotePreview"
VIEW = "() => document.body.dataset.mlNoteView"
KEY = "() => document.body.dataset.mlNoteKey"


def rich_book(library, chapter_one: str = RICH):
    doc = library.add_book("doe-2020-preview-test", "Preview test")
    library.add_notes(doc, ["Basics", "Aberrations"],
                      {"ch01-basics.md": chapter_one.encode("utf-8"),
                       "ch02-aberrations.md": CH2.encode("utf-8")})  # fmt: skip
    library.cache_chapter_pages(doc, {1: 1, 2: 3})
    return doc


def note_path(library, doc, name="ch01-basics.md"):
    return library.root / library.row(doc)["notes"] / name


def open_rich(library, server_factory, page, chapter_one: str = RICH, clock=False):
    doc = rich_book(library, chapter_one)
    server = server_factory()
    if clock:
        page.clock.install()
    open_document(page, server, doc, page_no=1)
    page.wait_for_function("() => document.body.dataset.mlNotes")  # (notes.js has started)
    if page.evaluate("() => document.body.dataset.mlNotes") == "closed":  # narrow: starts closed
        page.locator("#mlNotesToggle").click()
    notes_settled(page)
    assert page.evaluate(KEY) == "file:ch01-basics.md"
    if clock:
        page.clock.pause_at(int(time.time() * 1000) + 2_000)
    return doc, server


def choose_view(page, name: str) -> None:
    page.locator(f'.ml-view-switch button[data-view="{name}"]').click()
    page.wait_for_function(f"() => document.body.dataset.mlNoteView === '{name}'")


def saves(page) -> list:
    sent = []
    page.on("request", lambda r: r.url.endswith("/api/notes/save") and sent.append(r.url))
    return sent


def test_the_views_and_what_the_preview_shows(library, server_factory, reader_page):
    open_rich(library, server_factory, reader_page)
    assert reader_page.evaluate(VIEW) == "source"  # as before M5a
    expect(reader_page.locator(PREVIEW)).to_be_hidden()
    choose_view(reader_page, "preview")
    preview = reader_page.locator(PREVIEW)
    expect(preview).to_be_visible()
    expect(reader_page.locator(EDITOR)).to_be_hidden()
    expect(preview.locator("h1")).to_have_text("Rich note")
    expect(preview.locator("h2")).to_have_text("Lists here")
    expect(preview.locator("strong")).to_have_text("strong")
    expect(preview.locator("ul > li")).to_have_count(2)
    expect(preview.locator("ol > li")).to_have_count(2)
    expect(preview.locator("blockquote")).to_contain_text("a quote")
    expect(preview.locator("pre code")).to_contain_text('print("$x$ stays code")')
    expect(preview.locator("table th")).to_have_text(["Term", "中文"])
    expect(preview.locator("table td")).to_have_text(["pupil", "光瞳"])
    choose_view(reader_page, "split")
    expect(reader_page.locator(EDITOR)).to_be_visible()
    expect(preview).to_be_visible()
    text_box = reader_page.locator(EDITOR).bounding_box()
    preview_box = preview.bounding_box()
    panel_width = reader_page.locator("#mlNotes").bounding_box()["width"]
    if panel_width >= 720:  # a wide panel: side by side
        assert preview_box["x"] > text_box["x"] + 50
    else:  # stacked
        assert preview_box["y"] > text_box["y"] + 50
    reader_page.reload()  # the view is remembered in this browser
    notes_settled(reader_page)
    assert reader_page.evaluate(VIEW) == "split"
    expect(reader_page.locator(f"{PREVIEW} h1")).to_have_text("Rich note")


def test_split_is_stacked_on_a_narrow_panel(library, server_factory, reader_page):
    reader_page.set_viewport_size({"width": 700, "height": 900})  # the notes take the window
    open_rich(library, server_factory, reader_page)
    choose_view(reader_page, "split")
    text_box = reader_page.locator(EDITOR).bounding_box()
    preview_box = reader_page.locator(PREVIEW).bounding_box()
    assert preview_box["y"] > text_box["y"] + 50 and abs(preview_box["x"] - text_box["x"]) < 5


def test_raw_html_and_unsafe_links_never_run(library, server_factory, reader_page):
    requested = []
    reader_page.on("request", lambda r: requested.append(r.url))
    open_rich(library, server_factory, reader_page)
    choose_view(reader_page, "preview")
    preview = reader_page.locator(PREVIEW)
    expect(preview).to_contain_text("<script>window.__pwned = 1</script>")  # shown as text
    expect(preview).to_contain_text('<img src="x.png" onerror=')
    for selector in ("script", "img", "iframe", "[onerror]", "[onclick]", "a[href^='javascript']",
                     "a[href^='data']", "a[href^='vbscript']"):  # fmt: skip
        expect(preview.locator(selector)).to_have_count(0)
    expect(preview).to_contain_text("[js](javascript:window.__pwned=3)")  # plain text, no link
    expect(preview.locator(".ml-image-placeholder")).to_contain_text("a figure")
    assert reader_page.evaluate("() => window.__pwned") is None
    assert not [u for u in requested if u.endswith(("x.png", "figure.png"))]  # never fetched


FILLER = "".join(
    f"Paragraph {n} of filler text, to make the preview scroll.\n\n" for n in range(60)
)
LINKS = (
    RICH.replace("[below](#lists-here)", "[below](#far-below)")
    + "\n" + FILLER + "## Far below\n\nThe end.\n"
)  # fmt: skip


def test_links_in_the_preview(library, server_factory, reader_page):
    open_rich(library, server_factory, reader_page, chapter_one=LINKS)
    reader_page.context.route("https://example.com/**",
                              lambda route: route.fulfill(body="<p>elsewhere</p>",
                                                          content_type="text/html"))  # fmt: skip
    choose_view(reader_page, "preview")
    preview = reader_page.locator(PREVIEW)
    hash_before = reader_page.evaluate("() => location.hash")
    preview.get_by_role("link", name="below").click()  # #heading: scrolls the preview only
    reader_page.wait_for_function(
        "() => { const p = document.getElementById('mlNotePreview');"
        " const h = document.getElementById('ml-h-far-below').getBoundingClientRect();"
        " const r = p.getBoundingClientRect();"
        " return p.scrollTop > 0 && h.top >= r.top && h.bottom <= r.bottom; }"  # in view
    )
    assert reader_page.evaluate("() => location.hash") == hash_before  # PDF.js's #page=… kept
    with reader_page.context.expect_page() as popup:
        preview.get_by_role("link", name="web").click()
    page = popup.value
    page.wait_for_load_state()
    assert page.url == "https://example.com/page"
    assert page.evaluate("() => window.opener") is None  # noopener
    page.close()
    preview.get_by_role("link", name="unknown").click()  # not a note: stays, says so
    expect(reader_page.locator("#mlNotesStatus")).to_contain_text("Not a note of this document")
    assert reader_page.evaluate(KEY) == "file:ch01-basics.md"
    preview.get_by_role("link", name="chapter two").click()  # another note: the panel shows it
    reader_page.wait_for_function(
        "() => document.body.dataset.mlNoteKey === 'file:ch02-aberrations.md'"
    )
    expect(reader_page.locator(f"{PREVIEW} h1")).to_have_text("Chapter 2: Aberrations")


def test_switching_views_writes_nothing(library, server_factory, reader_page):
    doc, _ = open_rich(library, server_factory, reader_page)
    sent = saves(reader_page)
    before = note_path(library, doc).read_bytes()
    for name in ("preview", "split", "source", "split", "preview", "source"):
        choose_view(reader_page, name)
    reader_page.locator(EDITOR).click()
    for _ in range(4):
        reader_page.keyboard.press("Alt+p")
    reader_page.wait_for_timeout(2_000)  # longer than the autosave delay: nothing comes
    assert sent == [] and note_path(library, doc).read_bytes() == before
    assert reader_page.evaluate("() => document.body.dataset.mlSaveState") == "clean"


def test_typing_in_split_updates_the_preview_and_is_saved(library, server_factory, reader_page):
    doc, _ = open_rich(library, server_factory, reader_page, clock=True)
    choose_view(reader_page, "split")
    type_at_end(reader_page, "\n## Added heading\n")
    reader_page.clock.run_for(100)
    expect(reader_page.locator(f"{PREVIEW} h2")).to_have_count(1)  # not yet: still typing
    reader_page.clock.run_for(200)
    expect(reader_page.locator(f"{PREVIEW} h2").last).to_have_text("Added heading")
    reader_page.clock.run_for(1_600)  # the autosave delay (D6)
    wait_save_state(reader_page, "clean")
    assert note_path(library, doc).read_text("utf-8").endswith("## Added heading\n")


def test_a_conflict_and_leaving_work_the_same_in_preview(library, server_factory, reader_page):
    doc, _ = open_rich(library, server_factory, reader_page)
    choose_view(reader_page, "split")
    note_path(library, doc).write_bytes(b"# Changed elsewhere\n")
    type_at_end(reader_page, "my own words")
    reader_page.keyboard.press("Control+s")
    wait_save_state(reader_page, "conflict")
    choose_view(reader_page, "preview")
    expect(reader_page.locator("#mlNoteBar")).to_be_visible()  # the decision is still offered
    expect(reader_page.locator(PREVIEW)).to_contain_text("my own words")  # the text kept here
    assert leave(reader_page, "close", stay=True)  # unsaved: still warned
    assert note_path(library, doc).read_bytes() == b"# Changed elsewhere\n"
    reader_page.locator("#mlNoteBar").get_by_role("button", name="Keep mine").click()
    wait_save_state(reader_page, "clean")
    assert note_path(library, doc).read_text("utf-8").endswith("my own words")


def test_keys_in_the_preview_stay_in_the_notes(library, server_factory, reader_page):
    open_rich(library, server_factory, reader_page)
    choose_view(reader_page, "preview")
    reader_page.locator(PREVIEW).focus()
    page_before = reader_page.evaluate("() => PDFViewerApplication.page")
    for key in ("PageDown", "Space", "n", "ArrowRight", "End"):
        reader_page.keyboard.press(key)
    assert reader_page.evaluate("() => PDFViewerApplication.page") == page_before
    reader_page.keyboard.press("Alt+p")  # back to the source, the focus with it
    reader_page.wait_for_function("() => document.body.dataset.mlNoteView === 'source'")
    assert reader_page.evaluate(
        f"() => document.activeElement === document.querySelector('{EDITOR}')"
    )


def contrast(page) -> float:
    return page.evaluate(
        """() => {
          const p = document.getElementById('mlNotePreview');
          const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
          const lum = ([r, g, b]) => {
            const f = (v) => {
              v /= 255;
              return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
            };
            return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
          };
          const s = getComputedStyle(p);
          const [a, b] = [lum(rgb(s.color)), lum(rgb(s.backgroundColor))].sort((x, y) => y - x);
          return (a + 0.05) / (b + 0.05);
        }"""
    )


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_readable_in_light_and_dark(library, server_factory, reader_page, scheme):
    reader_page.emulate_media(color_scheme=scheme)
    open_rich(library, server_factory, reader_page)
    choose_view(reader_page, "preview")
    assert contrast(reader_page) >= 4.5
    if scheme == "dark":  # really dark: the background darker than the text
        assert reader_page.evaluate(
            "() => { const s = getComputedStyle(document.getElementById('mlNotePreview'));"
            " const n = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number).reduce((a, b) => a + b);"
            " return n(s.backgroundColor) < n(s.color); }"
        )


def test_a_wide_table_scrolls_inside_the_preview(library, server_factory, reader_page):
    wide = "| " + " | ".join(f"column{n}-with-a-long-heading" for n in range(12)) + " |\n"
    wide += "|" + "---|" * 12 + "\n| " + " | ".join("x" * 30 for _ in range(12)) + " |\n"
    open_rich(library, server_factory, reader_page, chapter_one=f"# Wide\n\n{wide}")
    panel_before = reader_page.locator("#mlNotes").bounding_box()["width"]
    choose_view(reader_page, "preview")
    sizes = reader_page.evaluate(
        "() => { const p = document.getElementById('mlNotePreview');"
        " const t = p.querySelector('table');"
        " return [t.scrollWidth, t.clientWidth, p.scrollWidth, p.clientWidth]; }"
    )
    assert sizes[0] > sizes[1]  # the table scrolls sideways
    assert sizes[2] <= sizes[3] + 1  # the preview itself doesn't
    assert reader_page.locator("#mlNotes").bounding_box()["width"] == panel_before


def test_without_markdown_it_the_plain_text_shows(library, server_factory, reader_page):
    reader_page.route("**/vendor/markdown-it/**", lambda route: route.abort())
    doc, _ = open_rich(library, server_factory, reader_page)
    choose_view(reader_page, "preview")
    preview = reader_page.locator(PREVIEW)
    expect(preview).to_contain_text("--setup-preview")
    expect(preview.locator(".ml-preview-plain")).to_contain_text("# Rich note")
    expect(preview.locator("h1")).to_have_count(0)
    choose_view(reader_page, "source")  # editing and saving as always
    type_at_end(reader_page, "still saved")
    reader_page.keyboard.press("Control+s")
    wait_save_state(reader_page, "clean")
    assert note_path(library, doc).read_text("utf-8").endswith("still saved")
    assert editor_text(reader_page).endswith("still saved")
