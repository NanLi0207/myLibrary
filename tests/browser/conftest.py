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
import owned_processes
import paths
import pytest
import reader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

SERVER = paths.APP / "scripts" / "library_server.py"
VERSIONS: dict[str, str] = {}


def pytest_addoption(parser):
    parser.addoption(
        "--notes-closed",
        action="store_true",
        help="start every reader with the notes panel closed, as a user who closed it "
        "(to check the reader without the panel too)",
    )


def pytest_configure(config):
    if not hasattr(config.option, "browser_channel"):
        return  # pytest-playwright isn't installed: tests/conftest.py says what to do
    if not config.option.browser_channel:  # Edge unless --browser-channel says otherwise
        config.option.browser_channel = "msedge"


@pytest.fixture(autouse=True)
def where_a_stuck_test_waits(request):
    """pytest ends a test that runs longer than faulthandler_timeout (pyproject.toml), printing
    every thread's stack. A browser test's own code runs in a greenlet those stacks don't show,
    so a few seconds earlier its own lines are printed here: the test, and where it waits."""
    limit = float(request.config.getini("faulthandler_timeout") or 0)
    if not limit:
        yield
        return

    def where():
        import gc
        import traceback

        import greenlet

        lines = [f"\n=== still running after {limit - 5:.0f} s: {request.node.nodeid} ===\n"]
        for g in gc.get_objects():
            if isinstance(g, greenlet.greenlet) and g.gr_frame is not None:
                stack = traceback.format_stack(g.gr_frame)
                lines += [line for line in stack if "site-packages" not in line]
        # To the real stderr, as pytest's own stack dump: the test's captured output is lost
        # when the process is ended (pytest's copy of it, else the original)
        try:
            from _pytest.faulthandler import fault_handler_stderr_fd_key

            fd = request.config.stash[fault_handler_stderr_fd_key]
        except ImportError, KeyError:
            fd = sys.__stderr__.fileno()
        os.write(fd, "".join(lines).encode("utf-8", "replace"))

    timer = threading.Timer(max(1.0, limit - 5), where)
    timer.daemon = True
    timer.start()
    yield
    timer.cancel()


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

    def add_notes(self, doc_id: str, chapters: list[str], files: dict[str, bytes]) -> Path:
        """The document's README with a checklist linking chapter notes ch01-…md, ch02-…md
        (`chapters` are their titles), and the note files given (name -> exact bytes)."""
        folder = self.root / self.row(doc_id)["notes"]
        items = "".join(
            f"- [ ] [Ch {n}: {title}](ch{n:02d}-{title.lower().replace(' ', '-')}.md)\n"
            for n, title in enumerate(chapters, 1)
        )
        readme = f"# {self.row(doc_id)['title']}\n\n## Reading progress\n\n{items}"
        (folder / "README.md").write_text(readme, encoding="utf-8", newline="\n")
        for name, data in files.items():
            (folder / name).write_bytes(data)
        return folder

    def cache_chapter_pages(self, doc_id: str, starts: dict[int, int]) -> None:
        """What the server's chapter-pages cache knows (before it starts: then it never
        searches the PDF for this document)."""
        cache = self.root / ".cache" / "chapter_pages.json"
        cache.parent.mkdir(parents=True, exist_ok=True)
        known = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
        known[doc_id] = {str(n): page for n, page in starts.items()}
        cache.write_text(json.dumps(known), encoding="utf-8")

    def note_files(self, doc_id: str) -> dict[str, tuple[bytes, int]]:
        """Every file in the document's notes folder: its bytes and modification time."""
        folder = self.root / self.row(doc_id)["notes"]
        return {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in sorted(folder.iterdir())}

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

    def __init__(
        self, library: Library, home: Path, wait_for_index: bool, ports=None, settings: str = ""
    ):
        self.library = library
        self.settings = settings
        self.home = home
        self.log_path = home / "server.log"
        settings_file = home / "settings.toml"
        settings_file.write_text(
            "# browser test settings\n" + settings, encoding="utf-8"
        )  # never the real ones: e.g. an editor that only records what it was asked to open
        env = {k: v for k, v in os.environ.items() if not k.startswith("MYLIBRARY_")}
        env |= {
            "MYLIBRARY_SETTINGS": str(settings_file),  # never the real local.toml
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
        # owned by this test run: ended with it however it ends (owned_processes)
        self.process = owned_processes.start(
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

    def start(wait_for_index: bool = False, settings: str = "") -> Server:
        home = tmp_path / "home"
        home.mkdir(exist_ok=True)
        server = Server(library, home, wait_for_index, settings=settings)
        started.append(server)
        return server

    def restart(old: Server) -> Server:
        """Stop a server and start a new one for the same library on the same port (as when the
        user restarts myLibrary): an open reader page keeps its address, not its access token."""
        old.stop()
        server = Server(library, old.home, False, ports=[old.port] * 5, settings=old.settings)
        started.append(server)
        return server

    start.restart = restart
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
def context(context, pytestconfig):
    """With --notes-closed, the notes panel is remembered as closed before any page loads."""
    if pytestconfig.getoption("--notes-closed"):
        context.add_init_script(
            "try { localStorage.setItem('myLibrary.notes.open', '0'); } catch {}"
        )
    return context


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
