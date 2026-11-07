import importlib.util
from pathlib import Path

import book_ocr
import library_jobs
import library_page
import library_server
import pytest
import subjects

# The browser tests (tests/browser/, Playwright + Edge) need the optional `browser` dependency
# group. Plain `pytest` leaves them out; `pytest tests/browser` runs them.
BROWSER_TESTS = Path(__file__).parent / "browser"


def _asks_for_browser_tests(config) -> bool:
    here = config.invocation_params.dir
    for arg in config.args:
        path = (here / arg.split("::")[0]).resolve()
        if path == BROWSER_TESTS or BROWSER_TESTS in path.parents:
            return True
    return False


def pytest_configure(config):
    if _asks_for_browser_tests(config):
        missing = [
            m for m in ("playwright", "pytest_playwright") if not importlib.util.find_spec(m)
        ]
        if missing:
            raise pytest.UsageError(
                f"The browser tests need {' and '.join(missing)}, in the optional `browser` "
                "dependency group: run `uv sync --group browser`, "
                "then `uv run pytest tests/browser`."
            )


def pytest_ignore_collect(collection_path, config):
    if collection_path == BROWSER_TESTS and not _asks_for_browser_tests(config):
        return True  # plain `pytest`: no browser, no Playwright needed
    return None


@pytest.fixture(autouse=True)
def no_writes_to_real_project(tmp_path, monkeypatch):
    """Redirect every file the scripts write, so tests never touch the real library."""
    monkeypatch.setattr(library_page, "PAGE", tmp_path / "library.html")
    monkeypatch.setattr(library_server, "CACHE", tmp_path / ".cache" / "chapter_pages.json")
    monkeypatch.setattr(book_ocr, "CACHE_DIR", tmp_path / ".cache" / "ocr")
    # No subject lookups online in tests (a test that needs one gives its own answer)
    monkeypatch.setattr(subjects, "lookup", lambda row: {})


@pytest.fixture(autouse=True)
def not_quitting():
    """A test that quits (library_jobs.shutdown) doesn't leave the next one unable to write."""
    yield
    library_jobs.reopen()
