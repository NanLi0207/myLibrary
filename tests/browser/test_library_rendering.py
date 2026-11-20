"""M7.1 S1c (FA-02): a library's name, a shelf label or a title is shown as text on the library
page, never run. The audit's reproduction: a library named "</script><script>…" ran its
script when the page loaded. Here a real server shows a synthetic library whose library.toml
name, registered label, shelf label and book title hold such text; nothing may run, the page
must still start (no page errors) and show each text exactly. Requests to anywhere but the
test server are blocked, so nothing could leave even if something ran."""

import json

import catalog
from playwright.sync_api import expect

PAYLOAD = "Lib </script><script>window.__fa02=731</script> «光学» & \"q\" 'a'"
REGISTERED = "</ScRiPt ><img src=x onerror=window.__fa02=2><!--<script>"
SHELF = "光学 </script><script>window.__fa02=3</script>"
TITLE = "Optics __API__ __DATA__ <b>bold</b> & Ωμέγα </script><script>window.__fa02=4</script>"


def a_library(library, name: str, title: str = TITLE, shelf: str = SHELF) -> str:
    """library.toml with `name` and one shelf label; one book on that shelf. Its id."""
    (library.root / "library.toml").write_text(
        f"name = {json.dumps(name)}\n\n[shelves]\nOptics = {json.dumps(shelf)}\n",
        encoding="utf-8",
    )  # (JSON's string escapes are TOML's)
    doc = library.add_book("doe-2020-optics-test", title)
    catalog.set_field(library.catalog, doc, "shelves", "Optics")
    return doc


def open_page(page, server) -> list[str]:
    """The library page, only the test server reachable; the page errors seen."""
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.context.route(
        "**/*",
        lambda route: (
            route.continue_() if route.request.url.startswith(server.base) else route.abort()
        ),
    )
    page.goto(server.base + "/")
    page.wait_for_load_state("load")  # (every script on the page has run by now)
    return errors


def nothing_ran(page) -> None:
    assert page.evaluate("() => window.__fa02") is None
    assert page.locator("img[src='x']").count() == 0
    injected = page.evaluate(
        "() => [...document.scripts].filter(s => s.textContent.trim().startsWith('window.')).length"
    )
    assert injected == 0


def test_a_hostile_library_name_shelf_and_title_are_shown_never_run(library, server_factory, page):
    doc = a_library(library, PAYLOAD)
    server = server_factory()
    errors = open_page(page, server)
    nothing_ran(page)
    card = page.locator(f'[data-id="{doc}"]')
    expect(card).to_be_visible()  # (the page's own script ran: it drew the card)
    assert page.evaluate("() => API.library.label") == PAYLOAD
    assert page.evaluate("() => SHELF_LABELS") == {"Optics": SHELF}
    assert TITLE in card.inner_text()
    assert SHELF in page.locator("#shelves").inner_text()
    # The page's token still works, and nothing works without it
    status = page.evaluate(
        """async () => [
             (await fetch("/api/jobs", {method: "POST", body: "{}", headers: {
               "Content-Type": "application/json", "X-Library-Token": API.token}})).status,
             (await fetch("/api/jobs", {method: "POST", body: "{}",
               headers: {"Content-Type": "application/json"}})).status]"""
    )
    assert status == [200, 403]
    assert not errors, errors


def test_a_hostile_registered_label_is_shown_never_run(library, server_factory, page):
    a_library(library, "Browser test", title="Optics test", shelf="光学 Optics")
    server = server_factory()
    added = server.post("/api/libraries/register", {"folder": str(library.root),
                                                    "label": REGISTERED})  # fmt: skip
    assert "error" not in added, added
    errors = open_page(page, server)
    nothing_ran(page)
    expect(page.locator("#grid .card, #grid [data-id]").first).to_be_visible()
    assert page.evaluate("() => API.library.label") == REGISTERED
    page.locator("#switchLibrary").click()  # the list of libraries shows it as text
    expect(page.locator("#libList li b").first).to_have_text(REGISTERED)
    nothing_ran(page)
    assert not errors, errors


def test_an_ordinary_name_with_unicode_and_quotes_works_as_before(library, server_factory, page):
    name = "我的书库 · Ωμέγα “Library” & 'Notes' \"two\""
    doc = a_library(library, name, title="Optics test «光学»", shelf="光学 Optics")
    server = server_factory()
    errors = open_page(page, server)
    expect(page.locator(f'[data-id="{doc}"]')).to_be_visible()
    assert page.evaluate("() => API.library.label") == name
    page.locator("#openSettings").click()  # (the page's controls work)
    expect(page.locator("#settingsDialog")).to_be_visible()
    assert not errors, errors
