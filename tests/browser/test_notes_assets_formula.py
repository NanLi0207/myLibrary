"""M5d/M5e in Edge: real image uploads and one real OCR round trip; explicitly mocked
recognition responses for deterministic UI, late responses and error cases. Invented data only.
"""

import base64
import io
import json
import re

import formula_ocr
import pytest
from helpers import EDITOR, editor_text, wait_save_state
from PIL import Image
from playwright.sync_api import expect
from test_notes_format import open_note, select
from test_notes_preview import PREVIEW, choose_view, note_path


def image_bytes(kind="PNG"):
    out = io.BytesIO()
    Image.new("RGB", (100, 40), "white").save(out, kind)
    return out.getvalue()


def paste(page, data=None, mime="image/png", selector=EDITOR):
    page.locator(selector).evaluate(
        """(target, [data, mime]) => {
          const bytes = Uint8Array.from(atob(data), c => c.charCodeAt(0));
          const clipboard = new DataTransfer();
          clipboard.items.add(new File([bytes], 'screenshot', {type: mime}));
          target.dispatchEvent(new ClipboardEvent('paste', {clipboardData: clipboard,
            bubbles: true, cancelable: true}));
        }""",
        [base64.b64encode(data or image_bytes()).decode(), mime],
    )


def mock_ocr(page, candidates=None, error=None):
    """Mock only the recognizer HTTP reply; real dialog, KaTeX, insertion and saves."""
    answer = (
        {"error": error, "code": error}
        if error
        else {
            "candidates": [
                {"latex": t, "score": -0.1 - i / 100}
                for i, t in enumerate(candidates or [r"E=h\nu"])
            ],
            "engine": "UI test stand-in",
            "seconds": 0.01,
            "similar": False,
        }
    )
    page.route(
        "**/api/formula/recognize", lambda r: r.fulfill(status=503 if error else 200, json=answer)
    )


def open_formula(page, data=None):
    page.locator("#mlFormulaButton").click()
    paste(page, data=data, selector=".ml-formula-drop")


@pytest.mark.parametrize(
    "kind,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")]
)
def test_paste_save_render_and_undo(library, server_factory, reader_page, kind, mime):
    page = reader_page
    doc = open_note(library, server_factory, page, "My note\n")
    select(page, 8, 8)
    data = image_bytes(kind)
    paste(page, data, mime)
    page.wait_for_function("() => document.body.dataset.mlPaste === 'inserted'")
    source = editor_text(page)
    assert source.startswith("My note\n![image](assets/")
    relative = re.search(r"\]\((assets/[^)]+)\)", source)[1]
    path = note_path(library, doc).parent / relative
    assert path.read_bytes() == data
    page.keyboard.press("Control+s")
    wait_save_state(page, "clean")
    assert note_path(library, doc).read_text("utf-8") == source
    for view in ("preview", "split"):
        choose_view(page, view)
        shown = page.locator(f"{PREVIEW} img.ml-image")
        expect(shown).to_have_count(1)
        expect(shown).to_have_js_property("naturalWidth", 100)
    page.locator(EDITOR).focus()
    page.keyboard.press("Control+z")
    expect(page.locator(EDITOR)).to_have_value("My note\n")
    assert path.read_bytes() == data  # Undo never deletes the image


def test_redo_after_undoing_an_image_link(library, server_factory, reader_page):
    page = reader_page
    doc = open_note(library, server_factory, page, "My note\n")
    select(page, 8, 8)
    paste(page)
    page.wait_for_function("() => document.body.dataset.mlPaste === 'inserted'")
    linked = editor_text(page)
    image = note_path(library, doc).parent / re.search(r"\]\((assets/[^)]+)\)", linked)[1]
    page.locator(EDITOR).focus()
    page.keyboard.press("Control+z")
    expect(page.locator(EDITOR)).to_have_value("My note\n")
    page.keyboard.press("Control+y")  # Redo puts the same link back, as one step
    expect(page.locator(EDITOR)).to_have_value(linked)
    page.keyboard.press("Control+s")
    wait_save_state(page, "clean")
    assert note_path(library, doc).read_text("utf-8") == linked
    assert image.read_bytes() == image_bytes()
    assert len(list(image.parent.iterdir())) == 1  # Undo and Redo never save it again


def test_an_image_pasted_during_ime_composition_is_not_taken(library, server_factory, reader_page):
    page = reader_page
    doc = open_note(library, server_factory, page, "中文\n")
    uploads = []
    page.on("request", lambda r: uploads.append(r.url) if "/api/notes/asset" in r.url else None)
    select(page, 2, 2)
    editor = page.locator(EDITOR)
    editor.dispatch_event("compositionstart", {"data": ""})
    paste(page)  # (Chinese input still composing a word: the paste is the IME's, not ours)
    page.wait_for_timeout(500)
    assert not uploads and editor_text(page) == "中文\n"
    assert "mlPaste" not in page.evaluate("() => ({...document.body.dataset})")
    assert not (note_path(library, doc).parent / "assets").exists()
    editor.dispatch_event("compositionend", {"data": ""})
    paste(page)  # once the word is done, an image is pasted as usual
    page.wait_for_function("() => document.body.dataset.mlPaste === 'inserted'")
    assert len(uploads) == 1 and "![image](assets/" in editor_text(page)


def insert_formula(page, latex: str, inline: bool = False) -> None:
    mock_ocr(page, ["x"])
    open_formula(page)
    expect(page.locator("#mlFormulaEditor")).to_have_value("x")
    page.locator("#mlFormulaEditor").fill(latex)
    if inline:
        page.locator("#mlFormulaInline").check()
    page.locator("#mlFormulaInsert").click()
    expect(page.locator("#mlFormulaDialog")).not_to_be_visible()


@pytest.mark.parametrize(
    "text, at, latex, inline, written, typesets",
    [
        # a "$" of the formula's own: kept as written, the delimiters chosen to fit it
        ("Price  each", 6, r"\text{cost $x$}", True, r"Price \(\text{cost $x$}\) each", True),
        ("Price each\n", 11, r"\text{cost $x$}", False,
         "Price each\n\n$$\n\\text{cost $x$}\n$$\n", True),
        # "\\" (a line break) before a "$": that "$" isn't escaped (KaTeX itself refuses this
        # formula, as written; it is still one formula, never text broken up)
        ("Price  each", 6, r"a\\$b", True, r"Price \(a\\$b\) each", False),
        # a digit straight after: "$x$5" would be read as dollar signs
        ("Price each5\n", 10, "x", True, "Price each\\(x\\)5\n", True),
        # the usual case is unchanged: $…$
        ("Price  each", 6, "x^2", True, "Price $x^2$ each", True),
    ],
)  # fmt: skip
def test_a_confirmed_formula_is_written_so_it_reads_back_whole(
    library, server_factory, reader_page, text, at, latex, inline, written, typesets
):
    page = reader_page
    doc = open_note(library, server_factory, page, text)
    select(page, at, at)
    insert_formula(page, latex, inline)
    assert editor_text(page) == written
    choose_view(page, "preview")
    expect(page.locator(f"{PREVIEW} .ml-math")).to_have_count(1)  # one formula, all of it
    if typesets:
        expect(page.locator(f"{PREVIEW} .katex annotation")).to_have_text(latex)
    page.keyboard.press("Control+s")
    wait_save_state(page, "clean")
    assert note_path(library, doc).read_text("utf-8") == written


def test_clean_takes_off_only_a_formulas_own_delimiters(library, server_factory, reader_page):
    page = reader_page
    open_note(library, server_factory, page, "x\n")
    clean = "s => window.myLibraryFormula.clean(s)"
    for typed, cleaned in [
        ("$$ x^2 $$", "x^2"),
        (r"\[x\]", "x"),
        (r"\(x\)", "x"),
        ("$x$", "x"),
        ("$a$ and $b$", "$a$ and $b$"),  # two formulas: nothing taken off
        ("$$a$$ and $$b$$", "$$a$$ and $$b$$"),
        (r"$x\$", r"$x\$"),  # the last "$" is an escaped one
    ]:
        assert page.evaluate(clean, typed) == cleaned, typed


def test_native_clipboard_ctrl_v(library, server_factory, reader_page):
    page = reader_page
    doc = open_note(library, server_factory, page, "Clipboard\n")
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.evaluate(
        """async data => {
      const bytes = Uint8Array.from(atob(data), c => c.charCodeAt(0));
      await navigator.clipboard.write([new ClipboardItem({
        'image/png': new Blob([bytes], {type: 'image/png'})})]);
    }""",
        base64.b64encode(image_bytes()).decode(),
    )
    select(page, 10, 10)
    page.keyboard.press("Control+v")
    page.wait_for_function("() => document.body.dataset.mlPaste === 'inserted'")
    assert "![image](assets/" in editor_text(page)
    assert len(list((note_path(library, doc).parent / "assets").iterdir())) == 1


def wait_until_captured(page, pending: list, timeout_ms: int = 15_000) -> None:
    """Wait until the route handler has captured the request and its real server response.

    In Playwright's synchronous API a route handler runs only while the test is inside a
    Playwright call, so this waits with page.wait_for_timeout (which lets Playwright process
    the handler and its route.fetch), never with a Python sleep or a bare loop. Bounded: an
    informative failure if nothing is captured in time."""
    step, waited = 50, 0
    while not pending:
        if waited >= timeout_ms:
            raise AssertionError(
                f"the image upload to /api/notes/asset wasn't intercepted and fetched from "
                f"the server within {timeout_ms} ms"
            )
        page.wait_for_timeout(step)
        waited += step


def test_upload_finishing_after_note_switch_keeps_image_without_wrong_insertion(
    library,
    server_factory,
    reader_page,
):
    page = reader_page
    doc = open_note(library, server_factory, page, "First\n")
    pending = []

    def delay(route):
        pending.append((route, route.fetch()))  # (the real server write; the reply held)

    page.route("**/api/notes/asset", delay)
    paste(page)
    expect(page.locator("body")).to_have_attribute("data-ml-paste", "saving")
    # The server has written the image (route.fetch); only its reply to the page is held back,
    # captured before the note is switched (CI run 43414437518: asserted too early before)
    wait_until_captured(page, pending)
    assert len(pending) == 1
    saved = json.loads(pending[0][1].body())
    image = note_path(library, doc).parent / saved["path"]
    assert image.read_bytes() == image_bytes()  # on disk already, before the page knows
    page.locator("#mlNoteSelect").select_option("file:ch02-aberrations.md")
    expect(page.locator(EDITOR)).to_have_value(re.compile("# Chapter 2"))
    # the page still waits for the reply
    assert page.evaluate("() => document.body.dataset.mlPaste") == "saving"
    pending[0][0].fulfill(response=pending[0][1])
    expect(page.locator(".ml-paste-kept")).to_be_visible()
    assert "![image]" not in editor_text(page)  # never put into the note now shown
    page.locator(".mlInsertKept").click()
    assert f"![image]({saved['path']})" in editor_text(page)  # only on the user's choice
    assert "![image]" not in note_path(library, doc).read_text("utf-8")  # nor the first note
    assert image.read_bytes() == image_bytes()  # the image itself kept throughout


@pytest.mark.parametrize("candidates", [[r"E=h\nu"], ["x_1", "x_l", "x_I"]])
def test_mocked_candidates_edit_preview_confirm_and_normal_save(
    library,
    server_factory,
    reader_page,
    candidates,
):
    page = reader_page
    doc = open_note(library, server_factory, page, "Formula\n")
    select(page, 8, 8)
    mock_ocr(page, candidates)
    open_formula(page)
    expect(page.locator(".ml-formula-candidate")).to_have_count(len(candidates))
    expect(page.locator(".ml-formula-candidate .katex")).to_have_count(len(candidates))
    assert editor_text(page) == "Formula\n"  # no insertion until explicit confirmation
    page.locator(".ml-formula-candidate input").last.check()
    expect(page.locator("#mlFormulaEditor")).to_have_value(candidates[-1])
    page.locator("#mlFormulaEditor").fill(r"\frac{\alpha_1^2}{2}")
    expect(page.locator("#mlFormulaLive .katex")).to_have_count(1)
    expect(page.locator("#mlFormulaLive annotation")).to_have_text(r"\frac{\alpha_1^2}{2}")
    page.locator("#mlFormulaInsert").click()
    expect(page.locator("#mlFormulaDialog")).not_to_be_visible()
    assert "$$\n\\frac{\\alpha_1^2}{2}\n$$" in editor_text(page)
    page.keyboard.press("Control+s")
    wait_save_state(page, "clean")
    assert note_path(library, doc).read_text("utf-8") == editor_text(page)
    page.keyboard.press("Control+z")
    expect(page.locator(EDITOR)).to_have_value("Formula\n")


@pytest.mark.parametrize("code", ["timeout", "failed", "busy", "unavailable"])
def test_mocked_ocr_errors_preserve_the_note(library, server_factory, reader_page, code):
    page = reader_page
    open_note(library, server_factory, page, "Keep this\n")
    mock_ocr(page, error=code)
    open_formula(page)
    expect(page.locator("#mlFormulaDialog")).to_have_attribute("data-state", "error")
    expect(page.locator("#mlFormulaInsert")).to_have_count(0)
    assert editor_text(page) == "Keep this\n"
    page.keyboard.press("Escape")
    expect(page.locator("#mlFormulaDialog")).not_to_be_visible()


def test_model_unavailable_offers_install_only_on_explicit_consent(
    library,
    server_factory,
    reader_page,
):
    page = reader_page
    open_note(library, server_factory, page, "Untouched\n")
    mock_ocr(page, error="not-installed")
    page.route(
        "**/api/formula/status",
        lambda r: r.fulfill(
            json={
                "installed": False,
                "installing": False,
                "download_bytes": 119659632,
                "engine": "UI test stand-in",
                "license": "MIT",
                "error": "",
            }
        ),
    )
    installs = []
    page.on(
        "request", lambda r: installs.append(r.url) if r.url.endswith("/formula/install") else None
    )
    open_formula(page)
    expect(page.locator("#mlFormulaInstall")).to_be_visible()
    assert not installs
    page.keyboard.press("Escape")
    assert editor_text(page) == "Untouched\n"


def test_confirmation_refuses_a_switched_note(library, server_factory, reader_page):
    page = reader_page
    open_note(library, server_factory, page, "First\n")
    mock_ocr(page)
    open_formula(page)
    expect(page.locator("#mlFormulaInsert")).to_be_visible()
    page.locator("#mlNoteSelect").evaluate("""menu => {
      menu.value = 'file:ch02-aberrations.md';
      menu.dispatchEvent(new Event('change', {bubbles: true}));
    }""")
    expect(page.locator(EDITOR)).to_have_value(re.compile("# Chapter 2"))
    page.locator("#mlFormulaInsert").click()
    expect(page.locator("#mlFormulaMessage")).to_contain_text("nothing was inserted")
    assert "$$" not in editor_text(page)


def test_stale_install_status_cannot_replace_a_reopened_dialog(
    library,
    server_factory,
    reader_page,
):
    page = reader_page
    open_note(library, server_factory, page, "Keep\n")
    mock_ocr(page, error="not-installed")
    pending = []
    page.route("**/api/formula/status", lambda route: pending.append(route))
    open_formula(page)
    page.wait_for_function(
        "() => document.querySelector('#mlFormulaDialog').dataset.state === 'recognizing'"
    )
    page.keyboard.press("Escape")
    page.locator("#mlFormulaButton").click()
    expect(page.locator("#mlFormulaDialog")).to_have_attribute("data-state", "empty")
    assert pending
    pending[0].fulfill(
        json={
            "installed": False,
            "installing": False,
            "download_bytes": 120000000,
            "engine": "stand-in",
            "license": "MIT",
            "error": "",
        }
    )
    # Drain the reply, then verify the new dialog still waits for its own image.
    page.evaluate("() => new Promise(resolve => setTimeout(resolve, 100))")
    expect(page.locator("#mlFormulaDialog")).to_have_attribute("data-state", "empty")
    assert editor_text(page) == "Keep\n"


def test_image_link_survives_conflict_and_recovery_draft(library, server_factory, reader_page):
    from helpers import drafts_in_browser, poll

    page = reader_page
    doc = open_note(library, server_factory, page, "Original\n")
    note = note_path(library, doc)
    note.write_bytes(b"Changed outside the app\n")
    paste(page)
    page.wait_for_function("() => document.body.dataset.mlPaste === 'inserted'")
    mine = editor_text(page)
    page.keyboard.press("Control+s")
    wait_save_state(page, "conflict")
    poll(
        page,
        lambda: mine in drafts_in_browser(page).values(),
        message="image Markdown was not retained in the recovery draft",
    )
    assert note.read_bytes() == b"Changed outside the app\n"
    assets = list((note.parent / "assets").iterdir())
    assert len(assets) == 1 and assets[0].read_bytes() == image_bytes()
    page.locator("#mlKeepMine").click()
    wait_save_state(page, "clean")
    assert note.read_text("utf-8") == mine
    assert assets[0].read_bytes() == image_bytes()


@pytest.mark.skipif(not formula_ocr.installed(), reason="real local model not installed")
def test_real_local_ocr_through_the_browser(library, server_factory, reader_page):
    """Real model + HTTP + UI, no mocked recognition; offline inference is tested separately."""
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib.mathtext import math_to_image

    image = io.BytesIO()
    math_to_image(r"$E=h\nu$", image, dpi=180, format="png")
    page = reader_page
    doc = open_note(library, server_factory, page, "Real OCR\n")
    select(page, 9, 9)
    open_formula(page, image.getvalue())
    expect(page.locator("#mlFormulaEditor")).to_have_value(r"E=h\nu", timeout=60_000)
    assert 1 <= page.locator(".ml-formula-candidate").count() <= 3
    page.locator("#mlFormulaInsert").click()
    page.keyboard.press("Control+s")
    wait_save_state(page, "clean")
    assert r"E=h\nu" in note_path(library, doc).read_text("utf-8")
