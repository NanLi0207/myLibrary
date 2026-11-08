"""The tests' own safety net (tests/conftest.py).

- A job a test starts in the background (library_jobs) must end inside that test, while its
  redirections to a temporary library still hold (background_jobs_end_with_the_test).
- D20 (tests/isolation_guard.py): the test run uses its own library and settings, set before
  any app module is imported, and a guard refuses writes to the user's real data, failing the
  test even when the code under test catches the refusal. The guard's tests aim it at invented
  folders only (isolation_guard.protecting), never at the real library.

Cases that need a whole test session run one in a subprocess with a copy of the real
conftest.py, so removing or breaking it fails these tests."""

import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

import isolation_guard
import paths
import pytest
import safe_io

pytest_plugins = ["pytester"]

CONFTEST = Path(__file__).with_name("conftest.py")
TESTS = Path(__file__).parent  # (isolation_guard.py, which the conftest imports)
SCRIPTS = Path(__file__).parent.parent / "scripts"

# A job that outlives its test's body: what page does it see when it gets to "write"?
OUTLIVES_ITS_TEST = """
import threading, time
import library_jobs, library_page

seen = {}
done = threading.Event()

def test_a_starts_a_slow_job():
    seen["test"] = library_page.PAGE  # this test's redirected page (conftest)
    def job():
        time.sleep(0.3)  # still working when the test's body has returned
        seen["job"] = library_page.PAGE  # where it would write the page now
        done.set()
    library_jobs._in_background(job)

def test_b_the_job_used_test_a_s_library():
    assert done.wait(10), "the job never ended"
    assert seen["job"] == seen["test"], f"the job wrote to {seen['job']}, not {seen['test']}"
"""

# A job that doesn't end in time (it only stops when asked): the run must stop there
NEVER_ENDS = """
import library_jobs

ran = []

def test_a_starts_a_job_that_waits_to_be_stopped():
    library_jobs._in_background(lambda: library_jobs._stopping.wait(30))

def test_b_must_not_run_beside_it():
    ran.append("b")
"""


def session(pytester, tests: str, conftest: str | None = None):
    pytester.makeconftest(conftest or CONFTEST.read_text(encoding="utf-8"))
    pytester.makeini(f"[pytest]\npythonpath = {SCRIPTS.as_posix()} {TESTS.as_posix()}\n")
    pytester.makepyfile(test_inner=tests)
    return pytester.runpytest_subprocess("-p", "no:cacheprovider", "-v")


def test_a_background_job_ends_inside_its_test(pytester):
    result = session(pytester, OUTLIVES_ITS_TEST)
    result.assert_outcomes(passed=2)


def test_a_job_that_doesnt_end_stops_the_whole_run(pytester):
    text = CONFTEST.read_text(encoding="utf-8")
    assert "JOB_WAIT = 30" in text
    result = session(pytester, NEVER_ENDS, text.replace("JOB_WAIT = 30", "JOB_WAIT = 0.5"))
    assert result.ret == 3, result.stdout.str()
    result.stdout.fnmatch_lines(["*didn't finish within 0.5 s of its test*"])
    assert "test_b_must_not_run_beside_it" not in result.stdout.str()


# --- D20: the run's own library and settings -----------------------------------------------------


def test_the_app_uses_this_runs_library_and_settings():
    import add_book
    import library_page
    import library_server
    import reader

    run = isolation_guard.run
    assert paths.LIBRARY == run["library"] and paths.SETTINGS_FILE == run["settings"]
    assert paths.LIBRARY_SOURCE == paths.ENV_VAR
    for module in (add_book, library_page, library_server, reader):
        assert module.LIBRARY == run["library"], module.__name__
    assert add_book.ARCHIVE.is_relative_to(run["library"])
    for place in (paths.LIBRARY, paths.SETTINGS_FILE):
        assert isolation_guard._protected_root(place) is None
    # The user's own places are what's protected (found before the redirect)
    protected = isolation_guard.protected()
    assert os.path.normcase(str(paths.APP / "library")) in protected
    assert os.path.normcase(str(paths.APP / "local.toml")) in protected


def test_subprocesses_get_the_runs_library_and_settings():
    code = f"import sys; sys.path.insert(0, {str(SCRIPTS)!r}); import paths; "
    code += "print(paths.LIBRARY); print(paths.SETTINGS_FILE)"
    done = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60, check=True
    )
    library, settings = done.stdout.split("\n")[:2]
    assert Path(library) == isolation_guard.run["library"]
    assert Path(settings) == isolation_guard.run["settings"]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_a_server_started_by_a_test_serves_the_runs_library():
    """Started as users start it, without --library: the redirected environment decides."""
    server = subprocess.Popen(
        [sys.executable, "-u", str(SCRIPTS / "library_server.py"), "--port", str(free_port()),
         "--no-browser", "--no-download"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
        errors="replace", cwd=isolation_guard.run["folder"],
    )  # fmt: skip
    found, lines, ready = {}, [], threading.Event()

    def read():
        for line in server.stdout:
            lines.append(line)
            if m := re.search(r"myLibrary at (http://127\.0\.0\.1:\d+)", line):
                found["base"] = m[1]
                ready.set()
        ready.set()  # (its output ended)

    threading.Thread(target=read, daemon=True).start()
    try:
        assert ready.wait(60) and "base" in found, "".join(lines)
        with urllib.request.urlopen(found["base"] + "/", timeout=10) as page:
            served = urllib.request.unquote(page.headers["X-myLibrary-Library"])
            token = re.search(r'"token": "([^"]+)"', page.read().decode())[1]
        assert Path(served).resolve() == isolation_guard.run["library"]
        quitting = urllib.request.Request(
            found["base"] + "/api/quit", data=b"{}", method="POST",
            headers={"Content-Type": "application/json", "X-Library-Token": token},
        )  # fmt: skip
        urllib.request.urlopen(quitting, timeout=10).close()
        server.wait(30)
    finally:
        if server.poll() is None:
            server.kill()
            server.wait(10)


def test_an_app_module_imported_too_early_stops_the_run(pytester):
    """A plugin that imports the app before conftest.py can redirect it: no test runs."""
    pytester.makepyfile(early_plugin="import paths\n")
    pytester.makeconftest(CONFTEST.read_text(encoding="utf-8"))
    pytester.makeini(f"[pytest]\npythonpath = {SCRIPTS.as_posix()} {TESTS.as_posix()}\n")
    pytester.makepyfile(test_inner="def test_never_runs():\n    pass\n")
    result = pytester.runpytest_subprocess("-p", "early_plugin", "-p", "no:cacheprovider")
    assert result.ret != 0
    assert "was imported before tests/conftest.py" in result.stdout.str() + result.stderr.str()


# --- D20: the guard, on invented "real data" ------------------------------------------------------


def contents(folder: Path) -> dict:
    return {
        p.relative_to(folder).as_posix(): (p.read_bytes() if p.is_file() else "folder")
        for p in sorted(folder.rglob("*"))
    }


@pytest.fixture
def users_data(tmp_path):
    """An invented library the guard protects for this test (inside an invented home folder,
    to try deleting a folder that holds it), and a place outside it. Nothing in it changes."""
    home = tmp_path / "home"
    data = home / "users-library"
    (data / "notes").mkdir(parents=True)
    (data / "notes" / "a.md").write_text("my notes\n")
    (data / "catalog.csv").write_text("id,slug\n")
    sqlite3.connect(data / "index.db").close()
    outside = tmp_path / "outside"
    (outside / "tree").mkdir(parents=True)
    (outside / "file.txt").write_text("outside\n")
    (outside / "tree" / "t.txt").write_text("tree\n")
    before = contents(home)
    with isolation_guard.protecting(data), isolation_guard.watching() as refused:
        yield data, outside, refused
    assert contents(home) == before  # the invented real data is exactly as it was


WRITES = {
    "open w": lambda d, o: open(d / "catalog.csv", "w"),
    "open a": lambda d, o: open(d / "catalog.csv", "a"),
    "open r+": lambda d, o: open(d / "catalog.csv", "r+"),
    "a new file": lambda d, o: (d / "notes" / "new.md").write_text("x"),
    "os.open create": lambda d, o: os.open(d / "x.md", os.O_CREAT | os.O_WRONLY),
    "safe_io atomic write": lambda d, o: safe_io.write_text(d / "notes" / "a.md", "x"),
    "replace into it": lambda d, o: os.replace(o / "file.txt", d / "notes" / "a.md"),
    "rename out of it": lambda d, o: os.rename(d / "notes" / "a.md", o / "moved.md"),
    "Path.replace out of it": lambda d, o: (d / "catalog.csv").replace(o / "moved.csv"),
    "remove": lambda d, o: os.remove(d / "notes" / "a.md"),
    "unlink": lambda d, o: (d / "catalog.csv").unlink(),
    "rmdir": lambda d, o: os.rmdir(d / "notes"),
    "rmtree": lambda d, o: shutil.rmtree(d),
    "rmtree of a folder holding it": lambda d, o: shutil.rmtree(d.parent),
    "rename a folder holding it": lambda d, o: os.rename(d.parent, o / "home-moved"),
    "move": lambda d, o: shutil.move(d / "notes" / "a.md", o / "m.md"),
    "mkdir": lambda d, o: (d / "new-folder").mkdir(),
    "makedirs": lambda d, o: os.makedirs(d / "x" / "y"),
    "copyfile into it": lambda d, o: shutil.copyfile(o / "file.txt", d / "copy.txt"),
    "copy2 into it": lambda d, o: shutil.copy2(o / "file.txt", d / "copy2.txt"),
    "copy into its folder": lambda d, o: shutil.copy(o / "file.txt", d / "notes"),
    "copytree into it": lambda d, o: shutil.copytree(o / "tree", d / "tree"),
    "truncate": lambda d, o: os.truncate(d / "catalog.csv", 0),
    "time stamps": lambda d, o: os.utime(d / "catalog.csv"),
    "hard link from it": lambda d, o: os.link(d / "catalog.csv", o / "alias.csv"),
    "hard link into it": lambda d, o: os.link(o / "file.txt", d / "alias.txt"),
    "SQLite, its database": lambda d, o: sqlite3.connect(d / "index.db"),
    "SQLite, a new database": lambda d, o: sqlite3.connect(d / "new.db"),
}


@pytest.mark.parametrize("write", WRITES)
def test_a_write_to_the_users_data_is_refused_and_recorded(users_data, write):
    data, outside, refused = users_data
    with pytest.raises(PermissionError, match="test isolation"):
        WRITES[write](data, outside)
    # (safe_io retries a refused write a few times, as for a file Windows has locked)
    assert refused and all(r.startswith("test isolation (D20): refused") for r in refused)


@pytest.mark.parametrize("spelling", ["upper case", "forward slashes", "long-path form"])
def test_any_spelling_of_its_path_is_refused(users_data, spelling):
    data, _, refused = users_data
    text = str(data / "catalog.csv")
    if spelling == "upper case":
        text = text.upper()
    elif spelling == "forward slashes":
        text = text.replace(os.sep, "/")
    else:
        text = "\\\\?\\" + text  # the form safe_io uses for long paths
    with pytest.raises(PermissionError):
        open(text, "w")
    assert len(refused) == 1


def test_reads_are_allowed(users_data):
    data, outside, refused = users_data
    assert (data / "catalog.csv").read_text() == "id,slug\n"
    assert sorted(os.listdir(data)) == ["catalog.csv", "index.db", "notes"]
    database = sqlite3.connect(f"file:{(data / 'index.db').as_posix()}?mode=ro", uri=True)
    database.execute("select 1")
    database.close()
    shutil.copyfile(data / "catalog.csv", outside / "a-copy.csv")  # copying *from* it: a read
    assert refused == []


def test_ordinary_temporary_writes_work(users_data):
    _, outside, refused = users_data
    (outside / "new.txt").write_text("x")
    safe_io.write_text(outside / "atomic.txt", "x")
    os.replace(outside / "new.txt", outside / "renamed.txt")
    shutil.copy2(outside / "renamed.txt", outside / "copied.txt")
    os.link(outside / "copied.txt", outside / "linked.txt")
    shutil.rmtree(outside / "tree")
    database = sqlite3.connect(outside / "fresh.db")
    database.execute("create table t (x)")
    database.close()
    assert refused == []


@pytest.mark.skipif(sys.platform != "win32", reason="directory junctions are a Windows feature")
def test_a_junction_into_the_users_data_is_refused(users_data, tmp_path):
    import _winapi

    data, outside, refused = users_data
    _winapi.CreateJunction(str(data), str(tmp_path / "way-in"))
    _winapi.CreateJunction(str(outside), str(tmp_path / "way-elsewhere"))
    with pytest.raises(PermissionError):
        (tmp_path / "way-in" / "notes" / "a.md").write_text("through a junction")
    (tmp_path / "way-elsewhere" / "ok.txt").write_text("fine")  # a junction to temp: allowed
    assert len(refused) == 1


def test_a_symlink_into_the_users_data_is_refused(users_data, tmp_path):
    data, _, refused = users_data
    link = tmp_path / "way-in.csv"
    try:
        os.symlink(data / "catalog.csv", link)
    except OSError as e:  # symlinks need Developer Mode or administrator rights; CI has them
        if os.environ.get("MYLIBRARY_REQUIRE_LINK_TESTS") == "1":
            pytest.fail(f"MYLIBRARY_REQUIRE_LINK_TESTS=1, but no symlink here ({e.strerror})")
        pytest.skip(f"this system doesn't allow creating a symlink here ({e.strerror})")
    with pytest.raises(PermissionError):
        open(link, "w")
    assert len(refused) == 1


SWALLOWS_THE_REFUSAL = """
import isolation_guard


def test_swallows_it(tmp_path):
    data = tmp_path / "users-library"
    data.mkdir()
    with isolation_guard.protecting(data):
        try:
            (data / "x.txt").write_text("x")
        except Exception:  # the code under test catches it and carries on
            pass


def test_an_ordinary_test(tmp_path):
    (tmp_path / "x.txt").write_text("x")
"""


def test_a_caught_refusal_still_fails_the_test(pytester):
    result = session(pytester, SWALLOWS_THE_REFUSAL)
    result.assert_outcomes(passed=2, errors=1)  # the refusal fails test_swallows_it
    result.stdout.fnmatch_lines(["*ERROR at teardown of test_swallows_it*", "*test isolation*"])


def test_the_runs_folder_is_removed_and_nothing_else(tmp_path):
    protected = tmp_path / "users-library"
    protected.mkdir()
    (protected / isolation_guard.RUN_MARKER).write_text("pretending to be a run folder\n")
    with isolation_guard.protecting(protected), isolation_guard.watching():
        with pytest.raises(PermissionError):
            isolation_guard.remove_run_folder(protected)
        with pytest.raises(PermissionError):  # nor a folder that holds it
            isolation_guard.remove_run_folder(tmp_path)
    assert (protected / isolation_guard.RUN_MARKER).exists()
    unmarked = tmp_path / "someone-elses"
    unmarked.mkdir()
    assert isolation_guard.remove_run_folder(unmarked) is False and unmarked.exists()
    ours = tmp_path / "a-run"
    ours.mkdir()
    (ours / isolation_guard.RUN_MARKER).write_text("")
    assert isolation_guard.remove_run_folder(ours) is True and not ours.exists()


def test_the_app_itself_never_installs_the_guard():
    for script in SCRIPTS.glob("*.py"):
        text = script.read_text(encoding="utf-8")
        assert "addaudithook" not in text and "isolation_guard" not in text, script.name
