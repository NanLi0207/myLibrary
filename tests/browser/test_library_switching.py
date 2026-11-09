"""The library page's 📚 Switch library / Library modes dialog (library_page.py): adding an
existing personal library (read-only check, then confirmation), opening it in its own server,
going back to the modes and opening the Test & Demo library with its banner. Temporary
libraries, settings and list of libraries only; every server the page starts is quit here."""

import re
import shutil
import time
import urllib.request
import uuid

import libraries
from playwright.sync_api import expect


def quit_server(port: int) -> None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10) as page:
            token = re.search(r'"token": "([^"]+)"', page.read().decode("utf-8"))[1]
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/quit", data=b"{}", method="POST",
            headers={"X-Library-Token": token, "Content-Type": "application/json"},
        )  # fmt: skip
        urllib.request.urlopen(request, timeout=10).close()
    except OSError:
        return
    for _ in range(80):
        if libraries.port_free(port):
            return
        time.sleep(0.25)


def elsewhere_than(port: int) -> re.Pattern:
    """A myLibrary address on any port but this one."""
    return re.compile(rf"http://127\.0\.0\.1:(?!{port}/)\d+/")


def test_switching_library_and_mode_from_the_page(library, server_factory, page, tmp_path):
    library.add_book("doe-2020-optics-test", "Optics test")
    other = tmp_path / "其他 书库 Other"
    skip = shutil.ignore_patterns("fixtures", "MANIFEST.json", "README.md")
    shutil.copytree(libraries.TEST_CANONICAL, other, ignore=skip)
    (other / "library.toml").write_text(
        f'name = "Other"\nid = "{uuid.uuid4()}"\n', encoding="utf-8"
    )
    server = server_factory()
    page.on("dialog", lambda dialog: dialog.accept())
    started = []
    try:
        page.goto(server.base + "/")
        expect(page.locator("#testBanner")).to_be_hidden()
        page.locator("#switchLibrary").click()  # personal mode: straight to the list
        expect(page.locator("#libPersonal")).to_be_visible()
        expect(page.locator("#libList")).to_contain_text("还没有私人书库")
        page.locator("#libFolder").fill(str(other))
        page.locator("#libLabel").fill("光学研究 Optics Research")
        page.locator("#libAdd").click()
        expect(page.locator("#libReport")).to_contain_text("✓ Other")
        item = page.locator("#libList li", has_text="光学研究 Optics Research")
        expect(item).to_be_visible()
        assert (other / "library.toml").read_text(encoding="utf-8").startswith('name = "Other"')

        item.locator("[data-lib=open]").click()  # its own server; this one keeps running
        page.wait_for_url(elsewhere_than(server.port), timeout=60_000)
        started.append(int(re.search(r":(\d+)/", page.url)[1]))
        assert libraries.same_place(libraries.server_at(started[-1]), other)
        assert libraries.same_place(libraries.server_at(server.port), library.root)
        expect(page.locator(".card")).to_have_count(18)

        page.locator("#switchLibrary").click()
        page.locator("#libBack").click()  # 书库模式 (Library modes)
        expect(page.locator("#libModes")).to_be_visible()
        page.locator("[data-mode=test]").click()
        page.wait_for_url(elsewhere_than(started[-1]), timeout=60_000)
        started.append(int(re.search(r":(\d+)/", page.url)[1]))
        expect(page.locator("#testBanner")).to_be_visible()
        expect(page.locator("#switchLibrary")).to_contain_text("Library modes")
        assert libraries.is_test_library(libraries.server_at(started[-1]))
    finally:
        for port in started:
            quit_server(port)
