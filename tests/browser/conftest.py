"""The reader in a real browser: Microsoft Edge, driven by Playwright (pytest-playwright).

Every test gets its own temporary library (small PDFs generated here), its own settings file
and home folder, and its own myLibrary server, started the way users start it:
library_server.py --library <tmp> --port 0 --no-browser --no-download. Before a test does
anything, the server is asked which library it serves; anything but the temporary one stops
the test. Nothing is downloaded while tests run: PDF.js must be installed first.

    uv sync --group browser
    uv run scripts/reader.py --setup-viewer
    uv run pytest tests/browser

On a failure, the test's folder under test-results/ gets the server's log, the page's console,
the library's file list, and (with --tracing / --screenshot) a Playwright trace and screenshot.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import random
import re
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

import catalog
import paths
import pytest
import reader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

SERVER = paths.APP / "scripts" / "library_server.py"
VERSIONS: dict[str, str] = {}


def pytest_configure(config):
    if not hasattr(config.option, "browser_channel"):
        return  # pytest-playwright isn't installed: tests/conftest.py says what to do
    if not config.option.browser_channel:  # Edge unless --browser-channel says otherwise
        config.option.browser_channel = "msedge"


def pytest_collection_modifyitems(items):
    here = Path(__file__).parent
    for item in items:
        if here in item.path.parents:
            item.add_marker(pytest.mark.browser)


FAILED = pytest.StashKey[bool]()  # set on a test whose setup, call or teardown failed


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    item.stash.setdefault(FAILED, False)
    if report.failed:
        item.stash[FAILED] = True
    return report


def pytest_terminal_summary(terminalreporter):
    if VERSIONS:
        terminalreporter.write_line(
            "browser: " + ", ".join(f"{k} {v}" for k, v in VERSIONS.items())
        )


@pytest.fixture(scope="session", autouse=True)
def reading_view_installed():
    if not (reader.PDFJS / "web" / "viewer.html").exists():
        pytest.exit(
            "PDF.js isn't installed, so the reader can't be tested. Install it first "
            "(checksum verified): uv run scripts/reader.py --setup-viewer",
            returncode=4,
        )


@pytest.fixture(scope="session", autouse=True)
def versions(browser, pytestconfig):
    VERSIONS.update(
        {
            "channel": pytestconfig.option.browser_channel or "chromium (Playwright's own)",
            "browser": browser.version,
            "Playwright": importlib.metadata.version("playwright"),
            "pytest-playwright": importlib.metadata.version("pytest-playwright"),
            "PDF.js": reader.viewer_installed() or "missing",
        }
    )
    print("\n" + json.dumps(VERSIONS))


# --- test PDFs and libraries -------------------------------------------------------------------

LINE = "Page {page} line {line}: the entrance pupil limits the aperture of the system."
LINES = 12  # per page; line n is drawn at y = 740 - 30 n (PDF points)


def make_pdf(path: Path, pages: list[list[str]]) -> None:
    """A small original PDF with one text line per entry (Helvetica 14, searchable)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    for lines in pages:
        c.setFont("Helvetica", 14)
        for n, text in enumerate(lines):
            c.drawString(72, 740 - 30 * n, text)
        c.showPage()
    c.save()


def standard_pages(
    count: int = 5, extra: dict[tuple[int, int], str] | None = None
) -> list[list[str]]:
    """`count` pages of numbered lines; extra = {(page, line): text} replaces those lines."""
    pages = [[LINE.format(page=page, line=n) for n in range(LINES)] for page in range(1, count + 1)]
    for (page, line), text in (extra or {}).items():
        pages[page - 1][line] = text
    return pages


class Library:
    """A temporary library: library.toml, books/, notes/, catalog.csv."""

    def __init__(self, root: Path):
        self.root = root
        self.catalog = root / "catalog.csv"
        for sub in ("books", "notes/topics"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        (root / "library.toml").write_text('name = "Browser test"\n', encoding="utf-8")

    def add_book(self, slug: str, title: str, pages: list[list[str]] | None = None) -> str:
        make_pdf(self.root / "books" / f"{slug}.pdf", pages or standard_pages())
        notes = self.root / "notes" / slug
        notes.mkdir(parents=True, exist_ok=True)
        (notes / "README.md").write_text(
            f"# {title}\n\n## Reading progress\n\n- [ ] Chapter 1: Basics\n", encoding="utf-8"
        )
        return catalog.add(
            self.catalog,
            {
                "slug": slug,
                "title": title,
                "type": "book",
                "file": f"books/{slug}.pdf",
                "notes": f"notes/{slug}/",
            },
        )

    def row(self, doc_id: str) -> dict:
        return catalog.load(self.catalog)[doc_id]

    def pdf(self, doc_id: str) -> Path:
        return self.root / self.row(doc_id)["file"]

    def readme(self, doc_id: str) -> str:
        return (self.root / self.row(doc_id)["notes"] / "README.md").read_text(encoding="utf-8")

    def reading_log(self) -> dict:
        path = self.root / "notes" / "reading-log.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def files(self) -> str:
        return "\n".join(
            f"{p.relative_to(self.root).as_posix()}  {p.stat().st_size}"
            for p in sorted(self.root.rglob("*"))
            if p.is_file()
        )


@pytest.fixture
def library(tmp_path) -> Library:
    return Library(tmp_path / "library")


# --- the server ----------------------------------------------------------------------------------


# The test server's port: chosen here, from the dynamic/private range (IANA, 49152-65535).
# Browsers refuse some lower ports (Chromium's "unsafe" ports, e.g. 2049 for NFS, all below
# 10080), and Windows may hand out any free port from 1024 up when asked for one (--port 0),
# so a test could fail with ERR_UNSAFE_PORT. No list of those ports to keep up to date.
SAFE_PORTS = range(49152, 65536)
START_ATTEMPTS = 5  # server starts (not test runs): a port can be taken meanwhile


def browser_safe(port: int) -> bool:
    return port in SAFE_PORTS


def random_ports():
    rng = random.Random()
    while True:
        yield rng.choice(SAFE_PORTS)


class Server:
    """A myLibrary server for one temporary library, as a subprocess, on a browser-safe port.
    A start that fails (the port was taken meanwhile) is cleaned up and tried again on another
    port, at most START_ATTEMPTS times in all; the test itself is never run again."""

    def __init__(self, library: Library, home: Path, wait_for_index: bool, ports=None):
        self.library = library
        self.home = home
        self.log_path = home / "server.log"
        settings = home / "settings.toml"
        settings.write_text("# browser test settings: nothing set\n", encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if not k.startswith("MYLIBRARY_")}
        env |= {
            "MYLIBRARY_SETTINGS": str(settings),  # never the real local.toml
            "USERPROFILE": str(home),
            "HOME": str(home),
            "APPDATA": str(home / "AppData" / "Roaming"),
            "LOCALAPPDATA": str(home / "AppData" / "Local"),
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
        }
        self.env = env
        self.lines: list[str] = []
        self.attempts: list[subprocess.Popen] = []  # every server process started
        tried = []
        candidates = iter(random_ports() if ports is None else ports)
        for _ in range(START_ATTEMPTS):
            port = next(candidates)
            if not browser_safe(port):
                tried.append(f"{port}: refused by browsers, not started")
                continue
            if self._start(port):
                break
            tried.append(f"{port}: {self.lines[-1] if self.lines else 'no output'}")
        else:
            pytest.fail(
                f"the myLibrary test server didn't start in {START_ATTEMPTS} attempts:\n"
                + "\n".join(tried)
            )
        try:
            assert browser_safe(self.port), self.port
            if wait_for_index and not self._indexed.wait(60):
                pytest.fail(f"the server's full-text index wasn't ready:\n{self.log()}")
            self._check_library()
        except BaseException:
            self.stop()  # never left running when the test can't use it
            raise

    def _start(self, port: int) -> bool:
        """One server process on `port`; True once it serves there. A failed one is stopped
        (and waited for) before this returns False."""
        header = f"--- starting on port {port}"
        self.lines.append(header)
        command = [sys.executable, "-u", str(SERVER), "--library", str(self.library.root),
                   "--port", str(port), "--no-browser", "--no-download"]  # fmt: skip
        self.process = subprocess.Popen(
            command,
            cwd=self.home,  # not the tool's folder: nothing may depend on where it's started
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
        )
        self.attempts.append(self.process)
        self._ready = threading.Event()  # its "myLibrary at" line came
        self._settled = threading.Event()  # that line came, or its output ended
        self._indexed = threading.Event()
        reader = threading.Thread(target=self._read_output, args=(self.process, header))
        reader.daemon = True
        reader.start()
        self._settled.wait(30)
        if self._ready.is_set() and self.process.poll() is None and self.port == port:
            return True
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(10)
        return False

    def _read_output(self, process: subprocess.Popen, header: str) -> None:
        with open(self.log_path, "a", encoding="utf-8") as log:
            log.write(header + "\n")
            for line in process.stdout:
                log.write(line)
                log.flush()
                self.lines.append(line.rstrip())
                if m := re.search(r"myLibrary at (http://127\.0\.0\.1:(\d+))", line):
                    self.base, self.port = m[1], int(m[2])
                    self._ready.set()
                    self._settled.set()
                if "full-text index" in line:
                    self._indexed.set()
        self._settled.set()  # the process ended (a failed start says why in its last line)

    def log(self) -> str:
        return "\n".join(self.lines[-80:])

    def _check_library(self) -> None:
        """Stop unless the server serves the temporary library (never the real one)."""
        with urllib.request.urlopen(self.base + "/", timeout=10) as page:
            served = urllib.request.unquote(page.headers.get("X-myLibrary-Library", ""))
            html = page.read().decode("utf-8")
        if not served or Path(served).resolve() != self.library.root.resolve():
            self.stop()
            pytest.exit(f"the test server serves {served!r}, not the temporary library", 3)
        self.token = re.search(r'"token": "([^"]+)"', html)[1]

    def post(self, path: str, body: dict) -> dict:
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "X-Library-Token": self.token},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as answer:
            return json.load(answer)

    def stop(self) -> None:
        """Quit the normal way (finishing writes), then make sure it's gone."""
        if self.process.poll() is None and getattr(self, "token", None):
            try:
                self.post("/api/quit", {})
                self.process.wait(10)
            except Exception:
                pass
        for process in self.attempts:  # every one started, should a failed start remain
            if process.poll() is None:
                process.kill()
                process.wait(10)


@pytest.fixture
def server_factory(library, tmp_path, request, output_path):
    started: list[Server] = []

    def start(wait_for_index: bool = False) -> Server:
        home = tmp_path / "home"
        home.mkdir(exist_ok=True)
        server = Server(library, home, wait_for_index)
        started.append(server)
        return server

    yield start
    for server in started:
        server.stop()
    if request.node.stash.get(FAILED, False):  # diagnostics for the artifact
        out = Path(output_path)
        out.mkdir(parents=True, exist_ok=True)
        for n, server in enumerate(started):
            (out / f"server-{n}.log").write_text(
                server.log_path.read_text(encoding="utf-8"), encoding="utf-8"
            )
        (out / "library-files.txt").write_text(library.files(), encoding="utf-8")


@pytest.fixture
def server(server_factory) -> Server:
    return server_factory()


# --- the browser page ----------------------------------------------------------------------------


@pytest.fixture
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 1400, "height": 1000}}


@pytest.fixture
def reader_page(page, request, output_path):
    """The test's page; a JavaScript error in it fails the test. Its console is kept for the
    failure artifacts."""
    errors: list[str] = []
    console: list[str] = []
    page.on("pageerror", lambda e: errors.append(f"{e.name}: {e.message}"))
    page.on("console", lambda m: console.append(f"[{m.type}] {m.text}"))
    page.set_default_timeout(15_000)
    yield page
    if request.node.stash.get(FAILED, False) or errors:
        out = Path(output_path)
        out.mkdir(parents=True, exist_ok=True)
        (out / "console.txt").write_text("\n".join(console), encoding="utf-8")
    assert not errors, "JavaScript errors in the page:\n" + "\n".join(errors)
