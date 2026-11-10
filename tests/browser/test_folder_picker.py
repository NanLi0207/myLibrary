"""The library page's folder buttons (📚 Libraries dialog and ⚙ Settings) and /api/pick-folder's
answers: a chosen folder fills the field; a cancel says nothing; no dialog on this system, or a
failing one, says so in the toast. On a cancel or failure the field keeps what it had, and
nothing is saved, added or opened. The endpoint is answered by the test (page.route): no real
dialog opens. Temporary library and settings only."""

import json
import re

from playwright.sync_api import expect


def _failed(code: int, status: str, detail: str) -> tuple[int, dict]:
    """As library_server answers a folder dialog that isn't there or failed."""
    error = f"No folder dialog ({detail}): type the folder instead"
    return code, {"folder": None, "status": status, "detail": detail, "error": error}


ANSWERS = {
    "chosen": (200, {"folder": "D:/书库 Libraries/Optics 光学", "status": "chosen"}),
    "cancelled": (200, {"folder": None, "status": "cancelled"}),
    "unsupported": _failed(501, "unsupported", "no folder dialog on this system"),
    "missing tool": _failed(501, "unsupported", "powershell isn't available"),
    "error": _failed(500, "error", "PowerShell failed"),
}
CHANGES = re.compile(r"/api/libraries/(register|create|open|relocate|rename|unregister)$")


def _answer_with(page, which: str) -> list:
    """Answer /api/pick-folder with ANSWERS[which]; returns the bodies the page sent."""
    sent = []

    def fulfil(route):
        sent.append(json.loads(route.request.post_data or "{}"))
        status, body = ANSWERS[which]
        route.fulfill(status=status, content_type="application/json", body=json.dumps(body))

    page.unroute("**/api/pick-folder")
    page.route("**/api/pick-folder", fulfil)
    return sent


def _changes(page) -> list[str]:
    """Every request that would save settings, add or open a library."""
    seen = []

    def note(request):
        if request.method != "POST":
            return
        if CHANGES.search(request.url):
            seen.append(request.url)
        elif request.url.endswith("/api/settings") and "save" in (request.post_data or ""):
            seen.append(request.url)

    page.on("request", note)
    return seen


def test_libraries_dialog_folder_button(library, server, page):
    changes = _changes(page)
    page.goto(server.base + "/")
    start = page.url
    page.locator("#switchLibrary").click()
    expect(page.locator("#libPersonal")).to_be_visible()
    field, button, toast = (
        page.locator("#libFolder"),
        page.locator("#libPick"),
        page.locator("#toast"),
    )
    field.fill("D:/existing library 已有")

    for which, says in (
        ("cancelled", None),
        ("unsupported", "isn't available on this system"),
        ("missing tool", "isn't available on this system"),
        ("error", "(Couldn't open the folder dialog): PowerShell failed"),
    ):
        page.evaluate("document.getElementById('toast').textContent = ''")
        sent = _answer_with(page, which)
        button.click()
        expect(button).to_be_enabled()  # never left waiting
        assert sent == [{"purpose": "library"}]
        expect(field).to_have_value("D:/existing library 已有")  # kept as it was
        if says:
            expect(toast).to_contain_text(says)
        else:
            page.wait_for_timeout(300)
            expect(toast).to_have_text("")  # a cancel says nothing
        expect(page.locator("#libPersonal")).to_be_visible()  # the dialog is still there

    _answer_with(page, "chosen")
    button.click()
    expect(field).to_have_value("D:/书库 Libraries/Optics 光学")
    expect(button).to_be_enabled()
    assert page.url == start and changes == []  # nothing added, opened or saved


def test_settings_folder_buttons(library, server, page):
    changes = _changes(page)
    page.goto(server.base + "/")
    page.locator("#openSettings").click()
    backup, library_field = page.locator("#setBackup"), page.locator("#setLibrary")
    expect(library_field).to_be_visible()
    before = library_field.input_value()
    backup.fill("E:/备份 Backups")

    sent = _answer_with(page, "error")
    page.locator("#pickBackup").click()
    expect(page.locator("#toast")).to_contain_text("Couldn't open the folder dialog")
    expect(backup).to_have_value("E:/备份 Backups")
    assert sent == [{"purpose": "backup"}]
    _answer_with(page, "unsupported")
    page.locator("#pickFolder").click()
    expect(page.locator("#toast")).to_contain_text("isn't available on this system")
    expect(library_field).to_have_value(before)

    _answer_with(page, "chosen")
    page.locator("#pickBackup").click()
    expect(backup).to_have_value("D:/书库 Libraries/Optics 光学")
    expect(library_field).to_have_value(before)  # only the field asked for
    assert changes == []  # choosing a folder saves nothing by itself
