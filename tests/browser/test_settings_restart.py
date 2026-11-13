"""B35: after a Settings change that restarts myLibrary, the library page reloads only from the
NEW server (another instance id), never from the old one that is still answering while it lets
its jobs finish; old tabs are refused with a clear message, unsaved notes are neither lost nor
written into another library, and 📚 Switch library leaves the original server running.
Temporary libraries, settings and list of libraries only; every server started is quit here."""

import json
import socket
import threading
import time
import urllib.request

import libraries
import pytest
from helpers import drafts_in_browser, editor_text, poll, type_at_end, wait_save_state
from test_library_switching import quit_server
from test_notes_editing import open_chapter_one
from test_notes_preview import note_path


def whoami(port: int) -> dict:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/whoami", timeout=10) as answer:
        return json.load(answer)


def page_keys(page) -> dict:
    return page.evaluate("() => ({token: API.token, instance: API.instance})")


def change_library_in_settings(page, folder) -> None:
    page.locator("#openSettings").click()
    page.locator("#setLibrary").fill(str(folder))
    page.locator("#saveSettings").click()


def test_the_page_waits_for_the_new_server_not_the_old_one(
    library, server_factory, reader_page, tmp_path
):
    page = reader_page
    server = server_factory()
    second = tmp_path / "Second library 第二个书库"
    try:
        page.goto(server.base + "/")
        old = page_keys(page)
        before = whoami(server.port)
        assert before["instance"] == old["instance"] and "token" not in json.dumps(before)
        old_tab = page.context.new_page()
        old_tab.goto(server.base + "/")

        # The old server, still answering while it lets running jobs finish: until the test lets
        # the real answers through, /api/whoami says the OLD instance (deterministic: no timing)
        held = {"answers": 0, "on": True}

        def old_server(route):
            if held["on"]:
                held["answers"] += 1
                route.fulfill(status=200, json=before)
            else:
                route.continue_()

        page.route("**/api/whoami", old_server)
        page.evaluate("() => { window.mlSameDocument = true; }")
        change_library_in_settings(page, second)
        poll(page, lambda: held["answers"] >= 4, timeout=30,
             message="the page didn't keep asking which server answers")  # fmt: skip
        # four answers from the old server, and the page is still the same document
        assert page.evaluate("() => window.mlSameDocument === true")
        with page.expect_navigation(timeout=120_000):
            held["on"] = False  # the new server's own answers from now on
        new = page_keys(page)
        assert new["instance"] != old["instance"] and new["token"] != old["token"]
        now = whoami(server.port)
        assert libraries.same_place(now["library"], second)
        assert now["scope"] == libraries.scope(second)  # the intended library, accepted
        # the new page's key works: a write goes through (the reported "forbidden" is gone)
        refreshed = page.evaluate("() => api('/api/refresh', {}).then(() => 'ok', e => e.message)")
        assert refreshed == "ok"
        # a tab still holding the old key is refused, says why, and never shows a key
        said = old_tab.evaluate(
            "() => api('/api/refresh', {}).then(() => 'done', e => `${e.status} ${e.message}`)"
        )
        assert said.startswith("403 Request refused (403). This page may be outdated."), said
        assert "Reload myLibrary and check whether your previous changes were saved" in said
        assert "nothing was changed" not in said  # a 403 can't tell what earlier writes did
        assert old["token"] not in said and new["token"] not in said
    finally:
        quit_server(server.port)  # the restarted server (the test's own one has exited)


def test_an_unsaved_note_survives_a_restart_and_goes_into_no_library(
    library, server_factory, reader_page, tmp_path
):
    doc, server = open_chapter_one(library, server_factory, reader_page)
    note = note_path(library, doc)
    original = note.read_bytes()
    second = tmp_path / "Second library"
    try:
        reader_page.route("**/api/notes/save", lambda route: route.abort())  # not saved yet
        type_at_end(reader_page, "\nunsaved words 未保存")
        reader_page.keyboard.press("Control+s")
        wait_save_state(reader_page, "offline")
        library_tab = reader_page.context.new_page()
        library_tab.goto(server.base + "/")
        old = page_keys(library_tab)
        with library_tab.expect_navigation(timeout=120_000):
            change_library_in_settings(library_tab, second)
        assert page_keys(library_tab)["instance"] != old["instance"]
        reader_page.unroute("**/api/notes/save")
        reader_page.keyboard.press("Control+s")  # tried again: the new server refuses the old key
        wait_save_state(reader_page, "restarted", timeout=30_000)
        assert "unsaved words 未保存" in editor_text(reader_page)  # still on screen
        assert any("unsaved words 未保存" in t for t in drafts_in_browser(reader_page).values())
        assert note.read_bytes() == original  # not written into the old library
        written = [
            p
            for p in second.rglob("*")
            if p.is_file()
            and p.suffix in (".md", ".json")
            and "unsaved words" in p.read_text(encoding="utf-8", errors="ignore")
        ]
        assert not written  # nor into the new one
    finally:
        quit_server(server.port)


def test_switch_library_leaves_the_original_server_and_tab_working(
    library, server_factory, reader_page, tmp_path
):
    server = server_factory()
    page = reader_page
    started = []
    try:
        page.goto(server.base + "/")
        mine = page_keys(page)
        made = page.evaluate(
            "f => api('/api/libraries/create', {folder: f, label: 'Other'})",
            str(tmp_path / "Other library"),
        )  # fmt: skip
        opened = page.evaluate("k => api('/api/libraries/open', {key: k})", made["library"]["key"])
        started.append(int(opened["url"].split(":")[2].split("/")[0]))
        assert started[0] != server.port
        assert whoami(server.port)["instance"] == mine["instance"]  # the same server, running
        assert whoami(started[0])["instance"] != mine["instance"]
        assert page.evaluate("() => api('/api/books', {}).then(() => 'ok', e => e.message)") == "ok"
    finally:
        for port in started:
            quit_server(port)


def test_only_the_intended_library_s_new_server_counts(server, reader_page):
    """B35: a reload needs an answer with a valid instance id other than the page's own and the
    scope the save named; anything else (missing, empty, malformed, the old instance, another
    library, no or a malformed scope) is not the new server. The positive case: accepted."""
    page = reader_page
    page.goto(server.base + "/")
    mine = page_keys(page)["instance"]
    expect, other = "0123456789abcdef", "fedcba9876543210"
    new = "a1b2c3d4e5f60718"
    assert new != mine
    cases = {
        "the intended library's new server": ({"instance": new, "scope": expect}, True),
        "no instance": ({"scope": expect}, False),
        "an empty instance": ({"instance": "", "scope": expect}, False),
        "a malformed instance": ({"instance": "not-an-id", "scope": expect}, False),
        "an instance that isn't text": ({"instance": 12345, "scope": expect}, False),
        "the old instance": ({"instance": mine, "scope": expect}, False),
        "another library": ({"instance": new, "scope": other}, False),
        "no scope": ({"instance": new}, False),
        "an empty scope": ({"instance": new, "scope": ""}, False),
        "a scope that isn't text": ({"instance": new, "scope": 7}, False),
        "no answer object": (None, False),
        "a list": ([new, expect], False),
    }
    for name, (about, wanted) in cases.items():
        got = page.evaluate("([a, e]) => isReplacement(a, e)", [about, expect])
        assert got is wanted, name
    for bad_expect in (None, "", "short", 5):  # a save answer without a valid scope: never
        assert not page.evaluate(
            "([a, e]) => isReplacement(a, e)", [{"instance": new, "scope": bad_expect}, bad_expect]
        )


def stalled_server():
    """A server that accepts, sends the headers and part of the body, and never finishes."""
    listener = socket.create_server(("127.0.0.1", 0))
    held = []

    def serve():
        while True:
            try:
                conn, _ = listener.accept()
            except OSError:
                return
            conn.recv(65536)
            conn.sendall(
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                b'Content-Length: 1000\r\n\r\n{"instance": '
            )
            held.append(conn)

    threading.Thread(target=serve, daemon=True).start()
    return listener, held


@pytest.mark.parametrize("answer", ["none", "stalled body", "another library"])
def test_a_restart_that_never_brings_the_library_back_is_reported_in_time(
    answer, server_factory, reader_page, tmp_path
):
    """B35: the wait after a library change has one overall deadline (shortened here): a
    whoami request the server accepts but never answers, or whose body stops halfway, is cut
    off, and a server of another library isn't taken for the new one. The page then says so
    and doesn't reload."""
    page = reader_page
    server = server_factory()
    listener, held = stalled_server()
    asked = []
    other = {"instance": "a1b2c3d4e5f60718", "scope": "fedcba9876543210", "library": "x"}

    def whoami_route(route):
        asked.append(answer)
        if answer == "none":
            return  # accepted, never answered
        if answer == "stalled body":
            return route.continue_(url=f"http://127.0.0.1:{listener.getsockname()[1]}/api/whoami")
        route.fulfill(status=200, json=other)

    try:
        page.goto(server.base + "/")
        page.route("**/api/whoami", whoami_route)
        page.evaluate("() => { window.mlSameDocument = true; window.mlRestartWaitMs = 4000; }")
        started = time.monotonic()
        change_library_in_settings(page, tmp_path / "Second library")
        said = ""
        while time.monotonic() - started < 60 and "didn't come back" not in said:
            page.wait_for_timeout(200)
            said = page.locator("#toast").text_content() or ""
        took = time.monotonic() - started
        assert "didn't come back" in said, said
        assert took < 30, took  # the 4 s deadline held, not 150 s nor a request's stall
        assert asked, "the page never asked"
        why = {"none": "no complete answer in time", "stalled body": "no complete answer in time",
               "another library": "another server or library"}[answer]  # fmt: skip
        assert why in said, said
        if answer == "stalled body":
            assert held, "the stalled server was never reached"
        assert page.evaluate("() => window.mlSameDocument === true")  # not reloaded
    finally:
        page.unroute_all(behavior="ignoreErrors")
        listener.close()
        for conn in held:
            conn.close()
        quit_server(server.port)  # the restarted server
