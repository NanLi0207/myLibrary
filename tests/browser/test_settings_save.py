"""M7.1 S3: the Settings dialog saves only what was changed, so a dialog left open in another tab
never undoes a save made meanwhile; while a save is on its way the dialog can't be closed,
refilled or saved twice; a failed save keeps the edits for another try (T-B1..B9). Each test
on its own temporary library, settings file and server."""

import json
import tomllib

from helpers import poll


def settings_file(server):
    return server.home / "settings.toml"


def saved(server) -> dict:
    return tomllib.loads(settings_file(server).read_text(encoding="utf-8"))


def open_page(page, server):
    page.goto(server.base + "/")
    page.locator("#openSettings").wait_for()


def open_settings(page):
    page.locator("#openSettings").click()
    shown = (
        "() => document.getElementById('settingsDialog').open"
        " && (typeof settingsShown === 'undefined' || settingsShown !== null)"
    )
    poll(page, lambda: page.evaluate(shown), message="the Settings dialog didn't open")


def saves_sent(page) -> list:
    """The `save` objects this page sends to /api/settings, as they are sent."""
    sent = []

    def on_request(request):
        if request.url.endswith("/api/settings") and request.method == "POST":
            body = json.loads(request.post_data or "{}")
            if "save" in body:
                sent.append(body["save"])

    page.on("request", on_request)
    return sent


def save_and_reload(page):
    with page.expect_navigation(timeout=30_000):
        page.locator("#saveSettings").click()


def test_only_the_changed_field_is_sent(library, server_factory, reader_page):
    """T-B1."""
    server = server_factory(settings="editor = 'vscode'\nbackup_pdfs = false\n")
    page = reader_page
    open_page(page, server)
    sent = saves_sent(page)
    open_settings(page)
    page.locator("#setEditor").select_option("notepad")
    save_and_reload(page)
    assert sent == [{"editor": "notepad"}]
    assert saved(server) == {"editor": "notepad", "backup_pdfs": False}
    assert settings_file(server).read_text(encoding="utf-8").startswith("# browser test settings")


def test_no_change_sends_nothing(library, server_factory, reader_page):
    """T-B2, T-B3: Save with nothing changed, or a field changed and changed back: no request,
    no reload, the dialog closes."""
    server = server_factory(settings="editor_command = 'code {file}'\neditor = 'custom'\n")
    page = reader_page
    open_page(page, server)
    sent = saves_sent(page)
    before = settings_file(server).read_bytes()
    page.evaluate("() => { window.mlSameDocument = true; }")
    open_settings(page)
    page.locator("#saveSettings").click()
    poll(page, lambda: not page.evaluate("() => document.getElementById('settingsDialog').open"))
    open_settings(page)
    page.locator("#setCommand").fill("something else")
    page.locator("#setEditor").select_option("system")
    page.locator("#setEditor").select_option("custom")
    page.locator("#setCommand").fill("  code {file} ")  # (the same once trimmed)
    page.locator("#saveSettings").click()
    poll(page, lambda: not page.evaluate("() => document.getElementById('settingsDialog').open"))
    page.wait_for_timeout(300)  # (a request would have been sent at once)
    assert sent == [] and page.evaluate("() => window.mlSameDocument === true")
    assert settings_file(server).read_bytes() == before


def test_two_stale_dialogs_changing_different_fields_keep_both(
    library, server_factory, reader_page
):
    """T-B4: two tabs open Settings; one saves the editor, then the other (its dialog still
    showing the old editor) saves backup_pdfs: both changes stay."""
    server = server_factory(settings="editor = 'vscode'\nbackup_pdfs = false\n")
    first = reader_page
    second = first.context.new_page()
    for page in (first, second):
        open_page(page, server)
        open_settings(page)
    first.locator("#setEditor").select_option("notepad")
    save_and_reload(first)
    second.locator("#setBackupPdfs").check()
    save_and_reload(second)
    assert saved(server) == {"editor": "notepad", "backup_pdfs": True}


def test_two_dialogs_changing_the_same_field_the_later_wins(library, server_factory, reader_page):
    """T-B5 (D1): the later save of the same setting is kept; each tab reloads and shows it."""
    server = server_factory(settings="editor = 'vscode'\n")
    first = reader_page
    second = first.context.new_page()
    for page in (first, second):
        open_page(page, server)
        open_settings(page)
    first.locator("#setEditor").select_option("notepad")
    save_and_reload(first)
    second.locator("#setEditor").select_option("system")
    save_and_reload(second)
    assert saved(server)["editor"] == "system"
    open_settings(first)
    assert first.locator("#setEditor").input_value() == "system"


def test_clearing_an_optional_field_sends_empty_text(library, server_factory, reader_page):
    """T-B6."""
    server = server_factory(settings="editor = 'custom'\neditor_command = 'code {file}'\n")
    page = reader_page
    open_page(page, server)
    sent = saves_sent(page)
    open_settings(page)
    page.locator("#setCommand").fill("")
    save_and_reload(page)
    assert sent == [{"editor_command": ""}] and saved(server)["editor_command"] == ""


# Wraps Response.json for the settings response: when the test asks, the dialog is closed
# natively right after the failed answer has been parsed and before the page's own code goes on,
# so its "close" notification is still queued while the page recovers
CLOSE_AT_PARSED_RESPONSE = """() => {
  const settingsDialog = document.getElementById("settingsDialog");
  window.mlCloseAtParse = false;
  window.mlClosedAtParse = null;
  window.mlCloseEvents = [];
  settingsDialog.addEventListener("close", () => mlCloseEvents.push(settingsDialog.open));
  const json = Response.prototype.json;
  Response.prototype.json = async function () {
    const data = await json.call(this);
    if (window.mlCloseAtParse && this.url.endsWith("/api/settings") && !this.ok) {
      window.mlCloseAtParse = false;
      settingsDialog.close();
      window.mlClosedAtParse = settingsDialog.open;  // false: it really closed, natively
    }
    return data;
  };
}"""


def test_a_save_on_its_way_cant_be_dismissed_and_a_failure_keeps_the_edits(
    library, server_factory, reader_page
):
    """T-B7, T-B8: while the save is held, Escape (twice), Cancel, the backdrop, ⚙ Settings and
    Save again change nothing: the dialog stays with the edit, one request only. A native close
    while saving is undone. Then the dialog is closed natively at the moment the failed answer is
    parsed (its notification still queued): after recovery the dialog is open with the edit and
    the controls usable, and the late notification doesn't close it. Save again sends the same
    change and it is saved."""
    server = server_factory(settings="editor = 'vscode'\n")
    page = reader_page
    open_page(page, server)
    page.evaluate(CLOSE_AT_PARSED_RESPONSE)
    held = []
    state = {"hold": True}

    def hold_saves(route):
        if route.request.method == "POST" and "save" in json.loads(route.request.post_data or "{}"):
            if state["hold"]:
                held.append(route)
                return
        route.continue_()

    page.route("**/api/settings", hold_saves)
    sent = saves_sent(page)
    open_settings(page)
    page.locator("#setEditor").select_option("notepad")
    page.locator("#saveSettings").click()
    poll(page, lambda: held, message="the save wasn't sent")
    dialog_open = "() => document.getElementById('settingsDialog').open"
    for _ in range(2):
        page.keyboard.press("Escape")
        page.wait_for_timeout(100)
        assert page.evaluate(dialog_open)
    assert page.locator("#settingsForm button[value=cancel]").is_disabled()
    assert page.locator("#saveSettings").is_disabled()
    page.evaluate("() => document.querySelector('#settingsForm button[value=cancel]').click()")
    page.mouse.click(5, 5)  # (the backdrop)
    page.evaluate("() => document.getElementById('openSettings').click()")
    page.evaluate("() => document.getElementById('folderBackup')?.click()")
    page.evaluate("() => { document.getElementById('saveSettings').click(); saveSettings(); }")
    page.evaluate(
        "() => document.getElementById('settingsDialog').close()"
    )  # a native close while saving: undone
    poll(page, lambda: page.evaluate(dialog_open), message="a close while saving wasn't undone")
    page.wait_for_timeout(200)
    assert page.evaluate(dialog_open) and len(sent) == 1 and len(held) == 1
    assert page.locator("#setEditor").input_value() == "notepad"

    # the failure, with a native close at the parsed-answer point
    page.evaluate("() => { window.mlCloseAtParse = true; mlCloseEvents.length = 0; }")
    held.pop().fulfill(status=400, json={"error": "a failure for the test"})
    poll(page, lambda: page.evaluate("() => mlCloseEvents.length > 0"),
         message="the native close's notification never came")  # fmt: skip
    page.wait_for_timeout(200)
    assert page.evaluate("() => window.mlClosedAtParse") is False  # (closed for real)
    assert page.evaluate("() => mlCloseEvents") == [True]  # (delivered after the recovery)
    assert page.evaluate(dialog_open)
    assert page.locator("#setEditor").input_value() == "notepad"
    assert page.locator("#saveSettings").is_enabled() and page.locator("#setEditor").is_enabled()
    assert "a failure for the test" in page.locator("#toast").inner_text()
    assert saved(server) == {"editor": "vscode"}

    state["hold"] = False
    save_and_reload(page)
    assert sent == [{"editor": "notepad"}, {"editor": "notepad"}]
    assert saved(server) == {"editor": "notepad"}


def test_clearing_the_library_is_refused_with_a_message(library, server_factory, reader_page):
    """T-B9."""
    server = server_factory(settings="editor = 'vscode'\n")
    page = reader_page
    open_page(page, server)
    before = settings_file(server).read_bytes()
    open_settings(page)
    page.locator("#setLibrary").fill("")
    page.locator("#saveSettings").click()
    poll(page, lambda: "can't be empty" in page.locator("#toast").inner_text(),
         message="no message about the empty library")  # fmt: skip
    assert page.evaluate("() => document.getElementById('settingsDialog').open")
    assert page.locator("#setLibrary").input_value() == ""
    assert settings_file(server).read_bytes() == before
