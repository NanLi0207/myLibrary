"""M7.1 S3, B44: reading the settings file. One policy for the start and every later read:
sharing failures retried, a missing file only for the usual settings (a first start), and
nothing that couldn't be read ever taken for "no settings" (which would open another library
or show the defaults). Temporary settings files only (T-R1..R5, R7, R10..R14 of the S3 plan)."""

import json
import os
import re
import subprocess
import sys
import textwrap
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import library_server
import paths
import pytest
import safe_io
import settings_toml
from link_policy import symlink_or_skip

WINDOWS = pytest.mark.skipif(os.name != "nt", reason="Windows byte-range locks")


@pytest.fixture
def chosen(tmp_path, monkeypatch):
    """A settings file chosen explicitly (as with MYLIBRARY_SETTINGS)."""
    file = tmp_path / "settings.toml"
    file.write_text("editor = 'notepad'\nbackup_pdfs = true\n", encoding="utf-8")
    monkeypatch.setattr(paths, "SETTINGS_FILE", file)
    monkeypatch.setattr(paths, "SETTINGS_SOURCE", "explicit", raising=False)
    return file


@pytest.fixture
def usual(tmp_path, monkeypatch):
    """The usual settings file (local.toml), which may be missing on a first start."""
    file = tmp_path / "local.toml"
    monkeypatch.setattr(paths, "SETTINGS_FILE", file)
    monkeypatch.setattr(paths, "SETTINGS_SOURCE", "default", raising=False)
    return file


def _byte_lock(file):
    """Another handle's lock on the file's first byte: reads through other handles get
    "permission denied" while it's held (as while a file is being swapped in)."""
    import msvcrt

    handle = open(file, "r+b")  # noqa: SIM115 (released by the test)
    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

    def release():
        if not handle.closed:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            handle.close()

    return release


@WINDOWS
def test_a_read_refused_for_a_moment_is_tried_again(chosen, monkeypatch):
    """T-R1: the first read is refused (a byte lock held elsewhere); the retry's wait lets
    the holder go; the settings are read, not lost."""
    release = _byte_lock(chosen)
    waits = []

    def wait(seconds):  # safe_io's wait between tries: the holder lets go during the first
        waits.append(seconds)
        release()

    monkeypatch.setattr(safe_io.time, "sleep", wait)
    try:
        settings = paths.load_settings()
    finally:
        release()
    assert waits, "the first read wasn't refused: the test proves nothing"
    assert settings["editor"] == "notepad" and settings["backup_pdfs"] is True


@WINDOWS
def test_a_read_refused_every_time_is_an_error_not_empty_settings(chosen, monkeypatch):
    """T-R2: still refused after the retries: an error, never {} (the defaults)."""
    monkeypatch.setattr(safe_io, "TRIES", 2)
    monkeypatch.setattr(safe_io.time, "sleep", lambda s: None)
    release = _byte_lock(chosen)
    try:
        with pytest.raises(paths.SettingsUnreadable, match="couldn't be read"):
            paths.load_settings()
        with pytest.raises(SystemExit, match="couldn't be read"):
            paths._resolve([])
    finally:
        release()


def test_damaged_settings_have_their_own_errors(chosen, tmp_path, monkeypatch):
    """T-R3: not TOML, not UTF-8, not readable at all: three different errors, each saying
    so; none of them is "no settings"."""
    chosen.write_bytes(b"editor = 'notepad\n")
    with pytest.raises(settings_toml.SettingsSyntax, match="can't be read"):
        paths.load_settings()
    chosen.write_bytes(b"editor = '\xff\xfe'\n")
    with pytest.raises(settings_toml.SettingsNotUTF8, match="isn't UTF-8"):
        paths.load_settings()
    folder = tmp_path / "a folder.toml"
    folder.mkdir()
    monkeypatch.setattr(paths, "SETTINGS_FILE", folder)
    monkeypatch.setattr(paths, "SETTINGS_SOURCE", "default")
    with pytest.raises(paths.SettingsUnreadable, match="folder"):
        paths.load_settings()
    for error in (settings_toml.SettingsSyntax, settings_toml.SettingsNotUTF8):
        assert issubclass(error, settings_toml.SettingsDamaged)
    assert not issubclass(paths.SettingsUnreadable, ValueError)  # (an I/O error, not bad input)


def test_damaged_settings_stop_the_start_whatever_chooses_the_library(chosen, tmp_path):
    """T-R3, T-R7: at the start a damaged file stops everything, also with --library or
    MYLIBRARY_LIBRARY (no bypass), so no library is opened with settings it couldn't read."""
    chosen.write_bytes(b"editor = [\n")
    with pytest.raises(SystemExit, match="can't be read"):
        paths._resolve(["--library", str(tmp_path / "lib")])
    assert os.environ.get(paths.ENV_VAR)  # (set for the whole test run, D20: also no bypass)
    with pytest.raises(SystemExit, match="can't be read"):
        paths._resolve([])


def test_the_usual_settings_may_be_missing_on_a_first_start(usual, monkeypatch):
    """T-R4, T-R14: no usual settings file: the defaults (a first start); found on the second
    look (being swapped in): read."""
    assert paths._saved() == {}
    assert paths.load_settings()["editor"] in paths.EDITORS
    looks = []

    def appears_meanwhile(seconds):  # the second look's wait: the file arrives
        looks.append(seconds)
        usual.write_text("editor = 'custom'\n", encoding="utf-8")

    monkeypatch.setattr(paths.time, "sleep", appears_meanwhile)
    assert paths._saved() == {"editor": "custom"} and len(looks) == 1


def test_other_read_errors_are_never_empty_settings(chosen, usual, monkeypatch):
    """T-R5 (other errors) and T-R14: an unexpected I/O error, for either kind of file."""

    def broken(path):
        raise OSError(5, "Input/output error", str(path))

    usual.write_text("", encoding="utf-8")
    monkeypatch.setattr(safe_io, "read_bytes", broken)
    with pytest.raises(paths.SettingsUnreadable, match="Input/output"):
        paths._saved()
    monkeypatch.setattr(paths, "SETTINGS_FILE", chosen)
    monkeypatch.setattr(paths, "SETTINGS_SOURCE", "explicit")
    with pytest.raises(paths.SettingsUnreadable, match="Input/output"):
        paths._saved()


def _junction(link, target):
    import _winapi

    _winapi.CreateJunction(str(target), str(link))


@WINDOWS
def test_a_link_that_leads_nowhere_is_refused_not_a_first_start(usual, tmp_path, monkeypatch):
    """T-R5: the settings folder reached through a junction whose target is gone: refused as
    a dangling link, never "no settings yet"."""
    target = tmp_path / "real settings folder"
    target.mkdir()
    link = tmp_path / "linked"
    _junction(link, target)
    (target / "local.toml").write_text("editor = 'notepad'\n", encoding="utf-8")
    monkeypatch.setattr(paths, "SETTINGS_FILE", link / "local.toml")
    assert paths._saved() == {"editor": "notepad"}  # (through the junction: fine)
    (target / "local.toml").unlink()
    target.rmdir()
    with pytest.raises(paths.SettingsDanglingAlias):
        paths._saved()
    with pytest.raises(SystemExit, match="link"):
        paths._resolve([])


@WINDOWS
def test_a_settings_file_link_that_leads_nowhere_is_refused(usual, tmp_path, monkeypatch):
    """T-R5: the settings file itself a symbolic link to a missing file."""
    link = tmp_path / "local.toml"
    symlink_or_skip(tmp_path / "gone.toml", link)
    with pytest.raises(paths.SettingsDanglingAlias):
        paths._saved()


@pytest.mark.parametrize("required", [False, True], ids=["local", "required"])
@pytest.mark.parametrize("failure", ["privilege", "unexpected", "missing folder", "none"])
def test_a_link_test_skips_only_for_a_missing_privilege(tmp_path, monkeypatch, failure, required):
    """S3 (rounds 2 and final): making the link fails (simulated): locally only the missing
    Windows privilege (1314) skips; any other error, a missing folder included, is raised as
    it is; with MYLIBRARY_REQUIRE_LINK_TESTS=1 every failure fails the test. A link that is
    made goes through, so the test's own checks run."""
    if required:
        monkeypatch.setenv("MYLIBRARY_REQUIRE_LINK_TESTS", "1")
    else:
        monkeypatch.delenv("MYLIBRARY_REQUIRE_LINK_TESTS", raising=False)
    errors = {
        "privilege": OSError(None, "A required privilege is not held by the client", None, 1314),
        "unexpected": OSError(5, "Input/output error (simulated)"),
    }
    made = []

    def symlink(target, link):
        if failure in errors:
            raise errors[failure]
        made.append((target, link))

    monkeypatch.setattr(os, "symlink", symlink)
    folder = tmp_path / "missing" if failure == "missing folder" else tmp_path
    link = folder / "link"
    if failure == "none":
        symlink_or_skip(tmp_path / "target", link)  # (no skip, no failure)
        assert made == [(tmp_path / "target", link)]
        return
    if required:
        expected = pytest.fail.Exception
    elif failure == "privilege" and os.name == "nt":
        expected = pytest.skip.Exception
    elif failure == "missing folder":
        expected = FileNotFoundError
    else:
        expected = OSError
    with pytest.raises(expected) as caught:
        symlink_or_skip(tmp_path / "target", link)
    assert not isinstance(caught.value, pytest.skip.Exception) or failure == "privilege"
    assert ("MYLIBRARY_REQUIRE_LINK_TESTS=1" in str(caught.value)) is required
    assert made == [] and not os.path.lexists(link)


def test_every_s3_symlink_test_uses_the_link_policy():
    """S3 final: the settings tests make symbolic links only through symlink_or_skip (no
    os.symlink of their own that could skip or pass silently); five regressions use it."""
    here = os.path.dirname(__file__)
    calls = 0  # (statements starting with the call; the policy test above makes two)
    for name in ("test_settings_read.py", "test_settings_transaction.py"):
        with open(os.path.join(here, name), encoding="utf-8") as file:
            source = file.read()
        assert not re.search(r"\bos\.symlink\((?!\")", source), name  # (calls, not this text)
        calls += len(re.findall(r"^ +symlink_or_skip\(", source, re.MULTILINE))
    assert calls - 2 == 5


def test_a_chosen_settings_file_that_disappears_is_an_error_not_defaults(chosen):
    """T-R13: a file chosen with MYLIBRARY_SETTINGS that is gone at a later read: an error at
    every read, never the defaults."""
    assert paths._saved()["editor"] == "notepad"
    chosen.unlink()
    with pytest.raises(paths.SettingsMissing, match="doesn't exist"):
        paths.load_settings()
    with pytest.raises(paths.SettingsMissing):
        paths.save_settings({"editor": "system"})
    assert not chosen.exists()  # (never created in its place)
    with pytest.raises(SystemExit, match="doesn't exist"):
        paths._resolve([])


def _settings_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"

    def post(body):
        request = urllib.request.Request(
            base + "/api/settings", data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json", "X-Library-Token": library_server.TOKEN},
        )  # fmt: skip
        try:
            with urllib.request.urlopen(request, timeout=30) as answer:
                return answer.status, json.load(answer)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    return server, post


def test_the_settings_page_never_shows_defaults_for_unreadable_settings(chosen, monkeypatch):
    """T-R3, T-R13 through the page's own request (POST /api/settings): a damaged file and a
    missing chosen file are errors with a message, never the defaults; a save to a missing
    chosen file creates nothing."""
    restarts = []
    monkeypatch.setattr(library_server, "restart_later", lambda server: restarts.append(1))
    server, post = _settings_server()
    try:
        status, answer = post({})
        assert status == 200 and answer["settings"]["editor"] == "notepad"
        chosen.write_bytes(b"editor = [\n")
        status, answer = post({})
        assert status == 400 and "can't be read" in answer["error"]
        chosen.unlink()
        status, answer = post({})
        assert status == 500 and "doesn't exist" in answer["error"]
        assert "settings" not in answer
        status, answer = post({"save": {"editor": "system"}})
        assert status == 500 and "doesn't exist" in answer["error"]
        assert not chosen.exists() and not restarts
    finally:
        server.shutdown()


# --- at the start, in a fresh process (the settings are chosen at import) ----------------------


def _start(tmp_path, settings, before_import="", argv=(), library_env=None):
    """Import paths in a new Python as a program would start: MYLIBRARY_SETTINGS = settings,
    a private home (so the default library would be made there, not in the real one)."""
    env = {k: v for k, v in os.environ.items() if k not in (paths.ENV_VAR, paths.SETTINGS_VAR)}
    env["PYTHONPATH"] = str(paths.APP / "scripts")
    env[paths.SETTINGS_VAR] = str(settings)
    env["USERPROFILE"] = env["HOME"] = str(tmp_path / "home")
    if library_env:
        env[paths.ENV_VAR] = str(library_env)
    code = (
        "import sys\n"
        f"sys.argv = ['start', *{list(map(str, argv))!r}]\n"
        + textwrap.dedent(before_import)
        + "import paths\nprint(paths.LIBRARY); print(paths.SETTINGS_SOURCE)\n"
    )
    return subprocess.run(
        [sys.executable, "-c", code], env=env, cwd=tmp_path, capture_output=True, text=True,
        timeout=120,
    )  # fmt: skip


def test_a_valid_chosen_settings_file_at_the_start(tmp_path):
    """T-R10."""
    settings = tmp_path / "s.toml"
    settings.write_text(f"library = '{(tmp_path / 'lib').as_posix()}'\n", encoding="utf-8")
    run = _start(tmp_path, settings)
    assert run.returncode == 0, run.stderr
    library, source = run.stdout.splitlines()
    assert library == str((tmp_path / "lib").resolve()) and source == "explicit"


# Deletes the settings file right after its first successful read (the check made when the
# file is chosen), before the library is chosen: a file that disappears between the two
_DELETE_AFTER_FIRST_READ = """
import os, safe_io
_real = safe_io.read_bytes
def _read_then_delete(path):
    data = _real(path)
    os.remove(path)
    safe_io.read_bytes = _real
    return data
safe_io.read_bytes = _read_then_delete
"""


@pytest.mark.parametrize("how", ["settings", "--library", "MYLIBRARY_LIBRARY"])
def test_a_chosen_settings_file_gone_before_the_library_is_chosen(tmp_path, how):
    """T-R11, T-R12: the file passes the first check, then disappears before the library is
    chosen: the start stops with the usual message, whatever chooses the library; no library
    is chosen from the defaults or created."""
    settings = tmp_path / "s.toml"
    settings.write_text(f"library = '{(tmp_path / 'lib').as_posix()}'\n", encoding="utf-8")
    argv = ["--library", str(tmp_path / "cli")] if how == "--library" else []
    env_library = tmp_path / "env" if how == "MYLIBRARY_LIBRARY" else None
    run = _start(tmp_path, settings, _DELETE_AFTER_FIRST_READ, argv, env_library)
    assert run.returncode != 0 and run.stdout == "", run.stdout
    assert paths.SETTINGS_VAR in run.stderr and "doesn't exist" in run.stderr
    assert not settings.exists()
    assert not (tmp_path / "home").exists()  # (no default library, no folder of it)
    assert not (tmp_path / "lib").exists() and not (tmp_path / "cli").exists()


# The chosen file is refused once (a byte lock held by another handle), released at safe_io's
# first wait: the start goes on
_REFUSED_ONCE_AT_START = """
import msvcrt, os, safe_io, time
_h = open(os.environ["MYLIBRARY_SETTINGS"], "r+b")
msvcrt.locking(_h.fileno(), msvcrt.LK_NBLCK, 1)
_waits = []
def _wait(seconds):
    _waits.append(seconds)
    if not _h.closed:
        _h.seek(0); msvcrt.locking(_h.fileno(), msvcrt.LK_UNLCK, 1); _h.close()
safe_io.time.sleep = _wait
"""


@WINDOWS
def test_a_chosen_settings_file_refused_for_a_moment_at_the_start(tmp_path):
    """T-R7: the start's own read of the chosen file is retried like every other read."""
    settings = tmp_path / "s.toml"
    settings.write_text(f"library = '{(tmp_path / 'lib').as_posix()}'\n", encoding="utf-8")
    code = _REFUSED_ONCE_AT_START + "\nimport atexit; atexit.register(lambda: print(len(_waits)))\n"
    run = _start(tmp_path, settings, code)
    assert run.returncode == 0, run.stderr
    library, source, waits = run.stdout.splitlines()
    assert library == str((tmp_path / "lib").resolve()) and int(waits) >= 1


@WINDOWS
def test_a_chosen_settings_file_refused_every_time_stops_the_start(tmp_path):
    """T-R2 at the start: still refused after the retries: the start stops; no library."""
    settings = tmp_path / "s.toml"
    settings.write_text(f"library = '{(tmp_path / 'lib').as_posix()}'\n", encoding="utf-8")
    hold = """
import msvcrt, os, safe_io
_h = open(os.environ["MYLIBRARY_SETTINGS"], "r+b")
msvcrt.locking(_h.fileno(), msvcrt.LK_NBLCK, 1)
safe_io.time.sleep = lambda s: None
"""
    run = _start(tmp_path, settings, hold)
    assert run.returncode != 0 and run.stdout == ""
    assert "couldn't be read" in run.stderr
    assert not (tmp_path / "home").exists()


def test_a_damaged_chosen_file_stops_the_start_even_with_library_given(tmp_path):
    """T-R7: --library or MYLIBRARY_LIBRARY don't skip reading the settings."""
    settings = tmp_path / "s.toml"
    settings.write_text("editor = [\n", encoding="utf-8")
    for argv, env_library in ((["--library", str(tmp_path / "cli")], None), ([], tmp_path / "e")):
        run = _start(tmp_path, settings, argv=argv, library_env=env_library)
        assert run.returncode != 0 and run.stdout == ""
        assert "can't be read" in run.stderr
