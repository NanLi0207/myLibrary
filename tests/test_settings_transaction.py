"""M7.1 S3, FA-06: saving settings is one transaction at a time, across threads and processes.
Saves of different settings never undo each other; of one setting, the later wins (D1). Both
locks within one 5 s deadline; the lock marker and the settings file checked before and after
locking; failures told apart by phase, never leaving the file changed or a lock held.
Temporary settings and libraries only (T-R8, T-R9, T-P1..P7, T-L1..L12, T-S1..S10)."""

import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tomllib
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import folder_backup
import library_server
import paths
import platform_services
import pytest
import safe_io
import settings_toml
from link_policy import symlink_or_skip

WINDOWS = pytest.mark.skipif(os.name != "nt", reason="Windows file locks and junctions")
CHILD = Path(__file__).with_name("settings_child.py")
WAIT = 60  # (a handshake not seen within this fails the test; it never makes one pass)


@pytest.fixture
def settings(tmp_path, monkeypatch):
    folder = tmp_path / "settings folder"
    folder.mkdir()
    file = folder / "settings.toml"
    file.write_text("# mine\neditor = 'vscode'\n", encoding="utf-8")
    monkeypatch.setattr(paths, "SETTINGS_FILE", file)
    monkeypatch.setattr(paths, "SETTINGS_SOURCE", "explicit")
    return file


def read(file: Path) -> dict:
    return tomllib.loads(file.read_text(encoding="utf-8"))


def temp_files(folder: Path) -> list[Path]:
    return [p for p in folder.iterdir() if p.name.endswith(".tmp")]


class Child:
    """tests/settings_child.py in its own process, on a settings file spelled `settings`."""

    def __init__(self, tmp_path: Path, settings: Path, *args):
        env = {k: v for k, v in os.environ.items() if k not in (paths.ENV_VAR, paths.SETTINGS_VAR)}
        env["PYTHONPATH"] = str(paths.APP / "scripts")
        env[paths.SETTINGS_VAR] = str(settings)
        env[paths.ENV_VAR] = str(tmp_path / "child library")
        env["USERPROFILE"] = env["HOME"] = str(tmp_path / "child home")
        self.process = subprocess.Popen(
            [sys.executable, str(CHILD), *map(str, args)], env=env, cwd=tmp_path, text=True,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )  # fmt: skip
        self.lines: queue.Queue = queue.Queue()
        self.seen: list[str] = []
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.process.stdout:
            self.lines.put(line.rstrip("\n"))
        self.lines.put(None)

    def expect(self, prefix: str) -> str:
        deadline = time.monotonic() + WAIT
        while time.monotonic() < deadline:
            try:
                line = self.lines.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty:
                break
            if line is None:
                break
            self.seen.append(line)
            if line.startswith(prefix):
                return line
        self.process.kill()
        err = self.process.stderr.read()
        raise AssertionError(f"expected {prefix!r}; saw {self.seen}; stderr: {err}")

    def release(self):
        self.process.stdin.write("release\n")
        self.process.stdin.flush()

    def finish(self) -> str:
        line = self.expect("done")
        self.process.wait(WAIT)
        return line

    def kill(self):
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(WAIT)


@pytest.fixture
def children():
    started: list[Child] = []
    yield started
    for child in started:
        child.kill()


def child(children, tmp_path, settings, *args) -> Child:
    started = Child(tmp_path, settings, *args)
    children.append(started)
    return started


def save_in_thread(updates, results, name):
    def run():
        try:
            results[name] = paths.save_settings(updates)
        except BaseException as e:  # (reported to the test)
            results[name] = e

    thread = threading.Thread(target=run)
    thread.start()
    return thread


def quick_save_elsewhere(tmp_path, children, settings, key="python_features", value=False):
    """Another thread and another process can both save at once: no lock was left held."""
    results = {}
    save_in_thread({key: value}, results, "t").join(WAIT)
    assert isinstance(results["t"], dict), results["t"]
    other = child(children, tmp_path, settings, "save", key, json.dumps(not value), 2)
    assert other.finish().startswith("done")


# --- contention ------------------------------------------------------------------------------


def test_two_threads_saving_different_settings_keep_both(settings, monkeypatch):
    """T-L1: A is inside its transaction; B is seen reaching the lock and waiting (its
    contention hook fired: it really tried); B hasn't read the file; then both are saved."""
    a_inside, a_go, b_waiting = threading.Event(), threading.Event(), threading.Event()
    reads_by_b = []
    real_probe = paths._probe_settings

    def before_publish():
        if threading.current_thread().name == "A":
            a_inside.set()
            assert a_go.wait(WAIT)

    def contended(kind):
        if threading.current_thread().name == "B" and kind == "thread":
            b_waiting.set()

    def probe(path, source):
        if threading.current_thread().name == "B":
            reads_by_b.append(path)
        return real_probe(path, source)

    monkeypatch.setattr(paths, "_on_before_publish", before_publish)
    monkeypatch.setattr(paths, "_on_lock_contended", contended)
    monkeypatch.setattr(paths, "_probe_settings", probe)
    results = {}
    a = threading.Thread(
        target=lambda: results.update(a=paths.save_settings({"editor": "notepad"})), name="A"
    )
    a.start()
    assert a_inside.wait(WAIT)
    b = threading.Thread(
        target=lambda: results.update(b=paths.save_settings({"backup_pdfs": True})), name="B"
    )
    b.start()
    assert b_waiting.wait(WAIT), "B never reached the lock: the test proves nothing"
    assert reads_by_b == [] and "backup_pdfs" not in read(settings)
    a_go.set()
    a.join(WAIT)
    b.join(WAIT)
    saved = read(settings)
    assert saved["editor"] == "notepad" and saved["backup_pdfs"] is True
    assert settings.read_text(encoding="utf-8").startswith("# mine\n")


def test_two_processes_saving_different_settings_keep_both(settings, tmp_path, children):
    """T-L2: P1 holds both locks; P2 reports that it found the OS lock taken (handshake),
    hasn't written; P1 goes on; both settings are kept."""
    p1 = child(children, tmp_path, settings, "hold", "editor", '"notepad"')
    p1.expect("held")
    p2 = child(children, tmp_path, settings, "save", "backup_pdfs", "true")
    p2.expect("contended:os")
    assert "backup_pdfs" not in read(settings)
    p1.release()
    assert p1.finish().startswith("done")
    assert p2.finish().startswith("done")
    saved = read(settings)
    assert saved["editor"] == "notepad" and saved["backup_pdfs"] is True


def _short_name(path: Path) -> Path | None:
    import ctypes

    size = ctypes.windll.kernel32.GetShortPathNameW(str(path), None, 0)
    buffer = ctypes.create_unicode_buffer(size)
    ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, size)
    short = Path(buffer.value)
    return short if buffer.value and short != path else None


def _junction(link: Path, target: Path) -> None:
    import _winapi

    _winapi.CreateJunction(str(target), str(link))


@WINDOWS
@pytest.mark.parametrize("alias", ["junction", "case", "short name"])
def test_processes_using_other_spellings_of_one_file_share_its_lock(
    settings, tmp_path, children, alias
):
    """T-L2b, T-S7: the same file through a junction, in other case, or by its 8.3 short
    name: one lock (the second process waits), both settings kept."""
    if alias == "junction":
        link = tmp_path / "linked"
        _junction(link, settings.parent)
        other = link / settings.name
    elif alias == "case":
        other = Path(str(settings).upper())
    else:
        other = _short_name(settings)
        if other is None:
            pytest.skip("8.3 short names are off on this volume")
    p1 = child(children, tmp_path, settings, "hold", "editor", '"notepad"')
    p1.expect("held")
    p2 = child(children, tmp_path, other, "save", "backup_pdfs", "true")
    p2.expect("contended:os")
    p1.release()
    assert p1.finish().startswith("done") and p2.finish().startswith("done")
    saved = read(settings)
    assert saved["editor"] == "notepad" and saved["backup_pdfs"] is True


# --- the deadline -------------------------------------------------------------------------------


def test_a_lock_held_in_this_process_past_the_deadline(settings, monkeypatch):
    """T-L3: the thread lock held elsewhere for the whole budget: SettingsBusy; the OS lock
    is never tried; the file unchanged."""
    monkeypatch.setattr(paths, "SETTINGS_LOCK_WAIT", 0.3)
    tried = []
    monkeypatch.setattr(paths, "_try_os_lock", lambda fd: tried.append(fd) or True)
    holder_has_it, done = threading.Event(), threading.Event()
    lock = safe_io.lock_for(paths._settings_destination())

    def hold():
        with lock:
            holder_has_it.set()
            done.wait(WAIT)

    holder = threading.Thread(target=hold)
    holder.start()
    assert holder_has_it.wait(WAIT)
    before = settings.read_bytes()
    try:
        with pytest.raises(paths.SettingsBusy):
            paths.save_settings({"editor": "notepad"})
    finally:
        done.set()
        holder.join(WAIT)
    assert tried == [] and settings.read_bytes() == before


def test_a_lock_held_by_another_process_past_the_deadline(
    settings, tmp_path, children, monkeypatch
):
    """T-L4: SettingsBusy after the deadline (real time, 0.5 s), file and folder unchanged."""
    holder = child(children, tmp_path, settings, "lock")
    holder.expect("held")
    monkeypatch.setattr(paths, "SETTINGS_LOCK_WAIT", 0.5)
    before = settings.read_bytes()
    started = time.monotonic()
    with pytest.raises(paths.SettingsBusy, match="nothing was changed"):
        paths.save_settings({"editor": "notepad"})
    assert 0.45 <= time.monotonic() - started < 5
    assert settings.read_bytes() == before and not temp_files(settings.parent)
    holder.release()
    holder.finish()


class FakeTime:
    def __init__(self):
        self.now = 1000.0
        self.sleeps: list[tuple[float, float]] = []  # (slept, remaining then)

    def clock(self):
        return self.now


@pytest.mark.parametrize("thread_wait", [4.9, 5.0, 6.0])
def test_one_deadline_covers_both_locks(settings, monkeypatch, thread_wait):
    """T-L5: the thread lock used most (or all) of the budget: the OS lock gets only what is
    left; no sleep goes past the deadline; no try after it; none at all when nothing is left."""
    fake = FakeTime()
    attempts = []

    class SlowLock:
        def acquire(self, blocking=True, timeout=-1):
            if not blocking:
                return False
            fake.now += min(thread_wait, timeout)
            return thread_wait <= timeout

        def release(self):
            pass

    def sleep(seconds):
        remaining = 1000.0 + paths.SETTINGS_LOCK_WAIT - fake.now
        fake.sleeps.append((seconds, remaining))
        fake.now += seconds

    def try_lock(fd):
        attempts.append(fake.now)
        return False

    monkeypatch.setattr(paths, "_clock", fake.clock)
    monkeypatch.setattr(paths, "_sleep", sleep)
    monkeypatch.setattr(paths, "_try_os_lock", try_lock)
    monkeypatch.setattr(safe_io, "lock_for", lambda path: SlowLock())
    with pytest.raises(paths.SettingsBusy):
        paths.save_settings({"editor": "notepad"})
    deadline = 1000.0 + paths.SETTINGS_LOCK_WAIT
    assert all(at < deadline for at in attempts)
    assert all(0 <= slept <= remaining for slept, remaining in fake.sleeps)
    assert fake.now <= deadline + 1e-9 or thread_wait > paths.SETTINGS_LOCK_WAIT
    if thread_wait >= paths.SETTINGS_LOCK_WAIT:
        assert attempts == []  # (nothing left: not even one try)
    else:
        assert attempts and sum(s for s, _ in fake.sleeps) <= 0.1 + 1e-9


# --- failures leave nothing held ---------------------------------------------------------------


def _blocked_publication(dest, data, **kwargs):
    error = safe_io.ReplaceBlocked("settings.toml is open in another program")
    raise error


def _io_error(dest, data, **kwargs):
    raise OSError(5, "Input/output error")


@pytest.mark.parametrize(
    "failure",
    ["change raises", "invalid inside", "damaged file", "blocked", "publication error",
     "quitting", "interrupted"],
)  # fmt: skip
def test_every_failure_releases_both_locks(settings, tmp_path, children, monkeypatch, failure):
    """T-L6: whatever goes wrong inside a transaction, both locks are released: another thread
    and another process save at once; no temporary file is left."""
    expected = {
        "change raises": ZeroDivisionError, "invalid inside": ValueError,
        "damaged file": settings_toml.SettingsSyntax, "blocked": paths.SettingsBlocked,
        "publication error": paths.SettingsSaveFailed, "quitting": safe_io.ShuttingDown,
        "interrupted": KeyboardInterrupt,
    }[failure]  # fmt: skip
    change = lambda current: {"editor": "notepad"}  # noqa: E731
    if failure == "change raises":
        change = lambda current: 1 / 0  # noqa: E731
    elif failure == "invalid inside":
        change = lambda current: {"editor": 5}  # noqa: E731
    elif failure == "damaged file":
        settings.write_text("editor = [\n", encoding="utf-8")
    elif failure == "blocked":
        monkeypatch.setattr(safe_io, "write_bytes", _blocked_publication)
        monkeypatch.setattr(platform_services, "windows_file_in_use", lambda path: True)
        if os.name != "nt":
            expected = paths.SettingsSaveFailed
    elif failure == "publication error":
        monkeypatch.setattr(safe_io, "write_bytes", _io_error)
    elif failure == "quitting":
        safe_io.close(timeout=1)
    elif failure == "interrupted":

        def change(current):
            raise KeyboardInterrupt

    try:
        with pytest.raises(expected):
            paths.update_settings(change)
    finally:
        safe_io.reopen()
    monkeypatch.undo()
    monkeypatch.setattr(paths, "SETTINGS_FILE", settings)
    monkeypatch.setattr(paths, "SETTINGS_SOURCE", "explicit")
    if failure == "damaged file":
        settings.write_text("editor = 'vscode'\n", encoding="utf-8")
    assert not temp_files(settings.parent)
    quick_save_elsewhere(tmp_path, children, settings)


def test_a_holder_killed_while_holding_the_lock(settings, tmp_path, children, monkeypatch):
    """T-L7: the operating system releases a dead process's lock; the next save gets it within
    the deadline; the marker stays (it is never deleted)."""
    holder = child(children, tmp_path, settings, "lock")
    holder.expect("held")
    marker = settings.parent / ".myLibrary-local" / "settings.toml.lock"
    assert marker.is_file()
    holder.kill()
    paths.save_settings({"editor": "notepad"})
    assert read(settings)["editor"] == "notepad" and marker.is_file()


def test_a_nested_save_is_refused_at_once(settings):
    """T-L8: a save inside a save: RuntimeError, no wait; the outer one is unaffected."""
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="nested"):
        paths.update_settings(lambda current: paths.save_settings({"editor": "system"}) and {})
    assert time.monotonic() - started < 2
    paths.save_settings({"editor": "notepad"})
    assert read(settings)["editor"] == "notepad"


def test_the_later_save_of_one_setting_wins(settings, monkeypatch):
    """T-L9 (D1): two saves of the same setting, the second waiting for the first: both
    succeed and the later one's value is kept."""
    a_inside, a_go, b_waiting = threading.Event(), threading.Event(), threading.Event()

    def before_publish():
        if threading.current_thread().name == "A":
            a_inside.set()
            assert a_go.wait(WAIT)

    monkeypatch.setattr(paths, "_on_before_publish", before_publish)
    monkeypatch.setattr(
        paths, "_on_lock_contended",
        lambda kind: threading.current_thread().name == "B" and b_waiting.set(),
    )  # fmt: skip
    results = {}
    a = threading.Thread(
        target=lambda: results.update(a=paths.save_settings({"editor": "notepad"})), name="A"
    )
    a.start()
    assert a_inside.wait(WAIT)
    b = threading.Thread(
        target=lambda: results.update(b=paths.save_settings({"editor": "system"})), name="B"
    )
    b.start()
    assert b_waiting.wait(WAIT)
    a_go.set()
    a.join(WAIT)
    b.join(WAIT)
    assert results["a"]["editor"] == "notepad" and results["b"]["editor"] == "system"
    assert read(settings)["editor"] == "system"


def test_a_library_remembered_meanwhile_is_not_overwritten(tmp_path, monkeypatch):
    """T-L10: ensure_library remembers the default library only if no library is in the file
    when it holds the locks: one saved meanwhile (after its first look) is kept."""
    file = tmp_path / "local.toml"
    monkeypatch.setattr(paths, "SETTINGS_FILE", file)
    monkeypatch.setattr(paths, "SETTINGS_SOURCE", "default")
    library = tmp_path / "default library"
    monkeypatch.setattr(paths, "LIBRARY", library)
    monkeypatch.setattr(paths, "LIBRARY_SOURCE", "default")
    real_saved = paths._saved

    def first_look_then_another_writer():  # (the look outside the locks says: none yet)
        found = real_saved()
        file.write_text("library = 'D:/Chosen meanwhile'\n", encoding="utf-8")
        return found

    monkeypatch.setattr(paths, "_saved", first_look_then_another_writer)
    paths.ensure_library()
    assert read(file)["library"] == "D:/Chosen meanwhile"


def test_settings_save_is_independent_of_the_backup_lock(settings, tmp_path):
    """T-L11: a folder backup holding its own lock doesn't make a settings save wait."""
    dest = tmp_path / "backups"
    dest.mkdir()
    with folder_backup._one_backup_at_a_time(dest, 1):
        started = time.monotonic()
        paths.save_settings({"editor": "notepad"})
        assert time.monotonic() - started < 2


@WINDOWS
def test_a_settings_file_moved_while_waiting_is_not_saved(tmp_path, monkeypatch):
    """T-L12: the junction leading to the settings is pointed elsewhere while a save waits:
    after getting the locks it sees the change and saves nothing, anywhere."""
    first, second = tmp_path / "first", tmp_path / "second"
    for folder, editor in ((first, "vscode"), (second, "custom")):
        folder.mkdir()
        (folder / "settings.toml").write_text(f"editor = '{editor}'\n", encoding="utf-8")
    link = tmp_path / "link"
    _junction(link, first)
    monkeypatch.setattr(paths, "SETTINGS_FILE", link / "settings.toml")
    monkeypatch.setattr(paths, "SETTINGS_SOURCE", "explicit")
    a_inside, a_go, b_waiting = threading.Event(), threading.Event(), threading.Event()

    def before_publish():
        if threading.current_thread().name == "A":
            a_inside.set()
            assert a_go.wait(WAIT)

    monkeypatch.setattr(paths, "_on_before_publish", before_publish)
    monkeypatch.setattr(
        paths, "_on_lock_contended",
        lambda kind: threading.current_thread().name == "B" and b_waiting.set(),
    )  # fmt: skip
    results = {}
    a_thread = threading.Thread(target=lambda: _keep(results, "a", {"editor": "notepad"}), name="A")
    a_thread.start()
    assert a_inside.wait(WAIT)
    b_thread = threading.Thread(target=lambda: _keep(results, "b", {"backup_pdfs": True}), name="B")
    b_thread.start()
    assert b_waiting.wait(WAIT)
    os.rmdir(link)  # (removes the junction only)
    _junction(link, second)
    a_go.set()
    a_thread.join(WAIT)
    b_thread.join(WAIT)
    assert isinstance(results["b"], paths.SettingsMoved)
    assert read(first / "settings.toml") == {"editor": "notepad"}  # (A's own save only)
    assert read(second / "settings.toml") == {"editor": "custom"}


def _keep(results, name, updates):
    try:
        results[name] = paths.save_settings(updates)
    except BaseException as e:
        results[name] = e


# --- the destination and the marker -------------------------------------------------------------


def _extended(path: Path) -> str:
    return "\\\\?\\" + str(path)


def _write_long(path: Path, text: str) -> None:
    with open(_extended(path), "w", encoding="utf-8") as f:
        f.write(text)


def _read_long(path: Path) -> bytes:
    with open(_extended(path), "rb") as f:
        return f.read()


@WINDOWS
@pytest.mark.parametrize(
    "odd_name", ["settings.toml.", "settings.toml ", "settings.toml. .", "CON.toml"]
)
def test_a_settings_path_windows_reads_as_another_file_is_refused(tmp_path, monkeypatch, odd_name):
    """Round 1, HIGH (Codex): "settings.toml" holds editor = 'system'; a second file reachable
    only through \\\\?\\ ("settings.toml.", a trailing space, a device name) holds 'vscode'.
    Chosen with MYLIBRARY_SETTINGS in its \\\\?\\ form: the start stops; saving in-process is
    refused before anything is read, locked or written; both files keep their bytes, no lock
    marker is made, no neighbour is written; an ordinary settings path still saves."""
    folder = tmp_path / "f"
    folder.mkdir()
    plain, odd = folder / "settings.toml", folder / odd_name
    plain.write_text("editor = 'system'\n", encoding="utf-8")
    _write_long(odd, "editor = 'vscode'\n")
    before = (plain.read_bytes(), _read_long(odd))
    env = {k: v for k, v in os.environ.items() if k not in (paths.ENV_VAR, paths.SETTINGS_VAR)}
    env.update({"PYTHONPATH": str(paths.APP / "scripts"), paths.SETTINGS_VAR: _extended(odd),
                paths.ENV_VAR: str(tmp_path / "lib"),
                "USERPROFILE": str(tmp_path / "home")})  # fmt: skip
    code = (
        "import paths\n"
        "print(paths.load_settings()['editor'])\n"
        "paths.save_settings({'backup_pdfs': True}); print('saved')\n"
    )
    started = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=WAIT
    )
    assert started.returncode != 0 and started.stdout == "", started.stdout
    assert odd_name.rstrip() in started.stderr or "device" in started.stderr
    monkeypatch.setattr(paths, "SETTINGS_FILE", Path(_extended(odd)))
    monkeypatch.setattr(paths, "SETTINGS_SOURCE", "explicit")
    with pytest.raises(paths.SettingsPathAmbiguous, match="another file"):
        paths.save_settings({"backup_pdfs": True})
    with pytest.raises(paths.SettingsPathAmbiguous):
        paths.load_settings()
    assert (plain.read_bytes(), _read_long(odd)) == before
    assert not (folder / ".myLibrary-local").exists()
    monkeypatch.setattr(paths, "SETTINGS_FILE", plain)
    paths.save_settings({"backup_pdfs": True})
    assert read(plain) == {"editor": "system", "backup_pdfs": True}
    assert _read_long(odd) == before[1]
    assert sorted(p.name for p in (folder / ".myLibrary-local").iterdir()) == ["settings.toml.lock"]


def test_a_real_location_that_is_another_file_is_refused(settings, tmp_path, monkeypatch):
    """Round 1: whatever way a path is followed, the place locked and written must be the same
    file as the one named (device and file id): if following gives another file, no lock
    marker for it is made and nothing is written to either file."""
    neighbour = tmp_path / "neighbour.toml"
    neighbour.write_text("editor = 'custom'\n", encoding="utf-8")
    real_strict = paths._strict_real
    monkeypatch.setattr(
        paths, "_strict_real",
        lambda p: neighbour if Path(p) == settings else real_strict(p),
    )  # fmt: skip
    before = (settings.read_bytes(), neighbour.read_bytes())
    with pytest.raises(paths.SettingsNotWritable, match="aren't the same file"):
        paths.save_settings({"editor": "notepad"})
    assert (settings.read_bytes(), neighbour.read_bytes()) == before
    assert not (tmp_path / ".myLibrary-local").exists()
    assert not (settings.parent / ".myLibrary-local").exists()


@WINDOWS
def test_the_extended_form_of_an_ordinary_path_shares_its_lock(settings, tmp_path, children):
    """Round 1: two writers, one naming the file in the ordinary form, one in the \\\\?\\ form:
    one lock (the second waits: handshake), one marker, both settings kept."""
    p1 = child(children, tmp_path, settings, "hold", "editor", '"notepad"')
    p1.expect("held")
    p2 = child(children, tmp_path, _extended(settings), "save", "backup_pdfs", "true")
    p2.expect("contended:os")
    p1.release()
    assert p1.finish().startswith("done") and p2.finish().startswith("done")
    assert read(settings) == {"editor": "notepad", "backup_pdfs": True}
    assert sorted(p.name for p in (settings.parent / ".myLibrary-local").iterdir()) == [
        "settings.toml.lock"
    ]


@WINDOWS
@pytest.mark.parametrize("where", ["settings folder", "existing lock folder"])
def test_the_start_refuses_a_chosen_file_where_case_cant_be_confirmed(settings, monkeypatch, where):
    """Round 1 (D5 at the start): for a settings file chosen with MYLIBRARY_SETTINGS, an
    unanswerable case-sensitivity question about its folder, or about a .myLibrary-local
    already there, stops the start (_resolve: SystemExit), creating nothing."""
    if where == "existing lock folder":
        (settings.parent / ".myLibrary-local").mkdir()
    real = platform_services.windows_case_sensitive

    def unanswerable(folder):
        is_sidecar = Path(folder).name == ".myLibrary-local"
        if is_sidecar == (where == "existing lock folder"):
            raise OSError("the folder couldn't say (Windows error 50)")
        return real(folder)

    monkeypatch.setattr(platform_services, "windows_case_sensitive", unanswerable)
    before = sorted(p.name for p in settings.parent.iterdir())
    with pytest.raises(SystemExit, match="upper and lower"):
        paths._resolve(["--library", str(settings.parent / "lib")])
    assert sorted(p.name for p in settings.parent.iterdir()) == before


def test_the_start_check_creates_no_lock_folder(settings):
    """Round 1: checking a chosen settings file at the start never creates .myLibrary-local."""
    paths._check_chosen_at_start()
    assert not (settings.parent / ".myLibrary-local").exists()


def _snapshot(folder: Path) -> dict:
    """Every file under `folder` (links not followed) with its bytes."""
    found = {}
    for root, _dirs, files in os.walk(folder):
        for name in files:
            found[os.path.relpath(os.path.join(root, name), folder)] = Path(root, name).read_bytes()
    return found


def _never_advises_deleting(message: str) -> None:
    """Round 3: .myLibrary-local can hold the library registry, logs and Test & Demo copies,
    so no start message may tell the user to delete it (or call it empty)."""
    assert "holds nothing" not in message and "only the settings lock" not in message.replace(
        "not only the settings lock", ""
    )
    for verb in re.finditer(r"\b(delete|remove|erase)\b", message, re.IGNORECASE):
        before = message[: verb.start()].lower()
        after = message[verb.end() :].lower()
        # (allowed: "Don't delete …", or removing the link itself, never what it leads to)
        assert before.endswith("don't ") or after.startswith((" the link", " only the link")), (
            message
        )
    for command in ("rmdir", "rd /s", "rm -r", "-recurse", "del /"):
        assert command not in message.lower()


def test_the_start_accepts_a_real_lock_folder_and_changes_nothing(settings):
    """Round 2: a .myLibrary-local that is a real folder (its marker in it) passes the start
    check; nothing in the settings folder changes."""
    sidecar = settings.parent / ".myLibrary-local"
    sidecar.mkdir()
    (sidecar / "settings.toml.lock").write_bytes(b"")
    before = _snapshot(settings.parent)
    paths._check_chosen_at_start()
    assert paths._saved()["editor"] == "vscode"
    assert _snapshot(settings.parent) == before


@pytest.mark.parametrize(
    "error",
    [
        PermissionError(13, "Access is denied"),
        OSError(5, "Input/output error (simulated)"),
    ],
    ids=["access denied", "unexpected error"],
)
def test_the_start_never_takes_an_unreadable_lock_folder_for_none(settings, monkeypatch, error):
    """Round 2: looking at .myLibrary-local fails (access denied, any other error): the start
    stops with the reason (before, os.path.isdir called that "no folder" and went on); only
    "not found" means there is none. Nothing created or changed."""
    sidecar = settings.parent / ".myLibrary-local"
    sidecar.mkdir()
    (sidecar / "settings.toml.lock").write_bytes(b"")
    before = _snapshot(settings.parent)
    real_lstat = os.lstat

    def failing(path, *args, **kwargs):
        if os.path.basename(os.fspath(path)) == ".myLibrary-local":
            raise error
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", failing)
    with pytest.raises(SystemExit, match="can't safely look at its local-data folder") as caught:
        paths._resolve(["--library", str(settings.parent / "lib")])
    message = str(caught.value)
    assert error.strerror in message and str(sidecar) in message
    assert "available" in message and "may read it" in message  # (what to check instead)
    assert "Don't delete the folder" in message and "not only the settings lock" in message
    _never_advises_deleting(message)
    monkeypatch.setattr(os, "lstat", real_lstat)
    assert _snapshot(settings.parent) == before


@pytest.mark.parametrize("kind", ["file", "junction", "symbolic link"])
def test_the_start_refuses_a_lock_folder_that_is_a_link_or_a_file(settings, tmp_path, kind):
    """Round 2: an existing .myLibrary-local that is a file, a junction or a symbolic link
    stops the start (as a save refuses it); nothing changed there or where a link leads."""
    sidecar = settings.parent / ".myLibrary-local"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "precious.txt").write_bytes(b"mine")
    if kind == "file":
        sidecar.write_bytes(b"not a folder")
    elif kind == "junction":
        if os.name != "nt":
            pytest.skip("junctions are Windows only")
        _junction(sidecar, elsewhere)
    else:
        symlink_or_skip(elsewhere, sidecar)
    before = _snapshot(settings.parent), _snapshot(elsewhere)
    with pytest.raises(SystemExit) as caught:
        paths._resolve(["--library", str(settings.parent / "lib")])
    message = str(caught.value)
    assert str(sidecar) in message and "won't start" in message
    if kind == "file":
        assert "isn't a folder" in message and "keep anything you need" in message
        assert "hasn't changed it" in message
    else:  # (round 3: the link is told apart from the folder it leads to, which is kept)
        assert "link or junction" in message and "remove only the link itself" in message
        assert "never the folder it points to" in message and "keep that folder" in message
    _never_advises_deleting(message)
    assert (_snapshot(settings.parent), _snapshot(elsewhere)) == before
    assert sidecar.is_file() if kind == "file" else os.path.lexists(sidecar)
    assert not (settings.parent / "lib").exists()


def test_a_first_save_creates_the_settings_and_the_lock_folder(tmp_path, monkeypatch):
    """T-S1, T-S2: no settings file, no .myLibrary-local, not even the settings folder (a
    package's first start): all made by the first save."""
    file = tmp_path / "appdata" / "myLibrary" / "settings.toml"
    monkeypatch.setattr(paths, "SETTINGS_FILE", file)
    monkeypatch.setattr(paths, "SETTINGS_SOURCE", "default")
    paths.save_settings({"editor": "notepad"})
    assert read(file) == {"editor": "notepad"}
    assert (file.parent / ".myLibrary-local" / "settings.toml.lock").is_file()


@WINDOWS
def test_a_frozen_library_reached_through_a_junction_is_refused(tmp_path, monkeypatch):
    """T-S3: settings in the canonical test library, reached through a junction: refused
    before anything is created there."""
    app = tmp_path / "app"
    frozen = app / "test_library"
    frozen.mkdir(parents=True)
    (frozen / "settings.toml").write_text("editor = 'vscode'\n", encoding="utf-8")
    link = tmp_path / "innocent"
    _junction(link, frozen)
    monkeypatch.setattr(paths, "APP", app)
    monkeypatch.setattr(safe_io, "_frozen", [os.path.normcase(os.path.realpath(frozen))])
    monkeypatch.setattr(paths, "SETTINGS_FILE", link / "settings.toml")
    monkeypatch.setattr(paths, "SETTINGS_SOURCE", "explicit")
    before = sorted(p.name for p in frozen.iterdir())
    with pytest.raises(paths.SettingsNotWritable, match="test_library"):
        paths.save_settings({"editor": "notepad"})
    assert sorted(p.name for p in frozen.iterdir()) == before
    assert read(frozen / "settings.toml") == {"editor": "vscode"}


@WINDOWS
def test_a_lock_folder_that_is_a_junction_is_refused(settings, tmp_path):
    """T-S4: .myLibrary-local as a junction elsewhere: refused, nothing written there."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _junction(settings.parent / ".myLibrary-local", elsewhere)
    with pytest.raises(paths.SettingsNotWritable, match="link"):
        paths.save_settings({"editor": "notepad"})
    assert list(elsewhere.iterdir()) == [] and read(settings) == {"editor": "vscode"}


@pytest.mark.parametrize("kind", ["file", "junction", "symbolic link", "unreadable"])
def test_a_save_explains_a_bad_lock_folder_without_advising_deletion(
    settings, tmp_path, monkeypatch, kind
):
    """Round 4: a save that finds .myLibrary-local a file, a link or junction, or a folder it
    can't look at says which (the startup wording), never calls a file a link and never
    advises deleting the folder; the settings, the item and any link target are unchanged."""
    sidecar = settings.parent / ".myLibrary-local"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "precious.txt").write_bytes(b"mine")
    if kind == "file":
        sidecar.write_bytes(b"not a folder")
    elif kind == "junction":
        if os.name != "nt":
            pytest.skip("junctions are Windows only")
        _junction(sidecar, elsewhere)
    elif kind == "symbolic link":
        symlink_or_skip(elsewhere, sidecar)
    else:
        sidecar.mkdir()
        (sidecar / "registry.json").write_bytes(b"{}")
    before = _snapshot(settings.parent), _snapshot(elsewhere)
    real_lstat = os.lstat
    if kind == "unreadable":

        def failing(path, *args, **kwargs):
            if os.path.basename(os.fspath(path)) == ".myLibrary-local":
                raise PermissionError(13, "Access is denied")
            return real_lstat(path, *args, **kwargs)

        monkeypatch.setattr(os, "lstat", failing)
    with pytest.raises((paths.SettingsNotWritable, paths.SettingsUnreadable)) as caught:
        paths.save_settings({"editor": "notepad"})
    monkeypatch.setattr(os, "lstat", real_lstat)
    message = str(caught.value)
    assert str(sidecar) in message
    if kind == "unreadable":  # (final: only the settings file is said to be unchanged)
        assert "won't save the settings; the settings file was not changed" in message
        assert "nothing was changed" not in message
    else:
        assert "won't save the settings; nothing was changed" in message
    if kind == "file":
        assert isinstance(caught.value, paths.SettingsNotWritable)
        assert "isn't a folder" in message and "keep anything you need" in message
        assert "link" not in message.lower()
    elif kind == "unreadable":
        assert isinstance(caught.value, paths.SettingsUnreadable)
        assert "Access is denied" in message and "may read it" in message
        assert "Don't delete the folder" in message and "not only the settings lock" in message
    else:
        assert isinstance(caught.value, paths.SettingsNotWritable)
        assert "link or junction" in message and "remove only the link itself" in message
        assert "never the folder it points to" in message and "keep that folder" in message
    _never_advises_deleting(message)
    assert (_snapshot(settings.parent), _snapshot(elsewhere)) == before
    assert read(settings) == {"editor": "vscode"}


def test_a_lock_marker_with_a_second_name_is_refused(settings, tmp_path):
    """T-S5 (hard link): the marker hard-linked to another file: refused; the other file
    untouched. (The symbolic-link case is its own test since round 3.)"""
    other = tmp_path / "precious.txt"
    other.write_bytes(b"mine")
    sidecar = settings.parent / ".myLibrary-local"
    sidecar.mkdir()
    os.link(other, sidecar / "settings.toml.lock")
    with pytest.raises(paths.SettingsNotWritable, match="lock") as caught:
        paths.save_settings({"editor": "notepad"})
    message = str(caught.value)  # (round 5: says what was found, never "it holds nothing")
    assert "hard link" in message and "hasn't changed it" in message
    _never_advises_deleting(message)
    assert other.read_bytes() == b"mine" and read(settings) == {"editor": "vscode"}
    (sidecar / "settings.toml.lock").unlink()
    assert other.read_bytes() == b"mine"


def test_a_lock_marker_that_is_a_symbolic_link_is_refused(settings, tmp_path):
    """T-S5 (symbolic link, round 3: reported on its own, skipped only where a link can't be
    made locally, failing under MYLIBRARY_REQUIRE_LINK_TESTS=1): the marker a symbolic link
    to another file: refused; the other file untouched."""
    other = tmp_path / "precious.txt"
    other.write_bytes(b"mine")
    sidecar = settings.parent / ".myLibrary-local"
    sidecar.mkdir()
    symlink_or_skip(other, sidecar / "settings.toml.lock")
    with pytest.raises(paths.SettingsNotWritable) as caught:
        paths.save_settings({"editor": "notepad"})
    message = str(caught.value)  # (round 5: the link told apart from what it points to)
    assert "link or junction" in message and "remove only the link itself" in message
    assert "never what it points to" in message
    _never_advises_deleting(message)
    assert other.read_bytes() == b"mine" and read(settings) == {"editor": "vscode"}
    assert (sidecar / "settings.toml.lock").is_symlink()


@pytest.mark.parametrize("kind", ["folder", "unreadable", "valid"])
def test_a_lock_marker_that_isnt_a_plain_file_is_refused_with_safe_advice(
    settings, monkeypatch, kind
):
    """Round 5: a folder at the marker's name, or a marker that can't be looked at: the save
    is refused, says what it found, never calls it empty or advises deleting it, and changes
    nothing; an ordinary marker still saves."""
    sidecar = settings.parent / ".myLibrary-local"
    sidecar.mkdir()
    marker = sidecar / "settings.toml.lock"
    if kind == "folder":
        marker.mkdir()
        (marker / "notes.txt").write_bytes(b"mine")
    else:
        marker.write_bytes(b"")
    if kind == "valid":
        paths.save_settings({"editor": "notepad"})
        assert read(settings)["editor"] == "notepad" and marker.read_bytes() == b""
        return
    before = _snapshot(settings.parent)
    real_lstat = os.lstat
    if kind == "unreadable":

        def failing(path, *args, **kwargs):
            if os.path.basename(os.fspath(path)) == "settings.toml.lock":
                raise OSError(5, "Input/output error (simulated)")
            return real_lstat(path, *args, **kwargs)

        monkeypatch.setattr(os, "lstat", failing)
    with pytest.raises((paths.SettingsNotWritable, paths.SettingsUnreadable)) as caught:
        paths.save_settings({"editor": "notepad"})
    monkeypatch.setattr(os, "lstat", real_lstat)
    message = str(caught.value)
    assert str(marker) in message
    if kind == "unreadable":  # (final: only the settings file is said to be unchanged)
        assert "won't save the settings; the settings file was not changed" in message
        assert "nothing was changed" not in message
    else:
        assert "won't save the settings; nothing was changed" in message
    if kind == "folder":
        assert isinstance(caught.value, paths.SettingsNotWritable)
        assert "found a folder" in message and "keep anything you need" in message
        assert "link" not in message.lower()
    else:
        assert isinstance(caught.value, paths.SettingsUnreadable)
        assert "Input/output error" in message and "may read it" in message
    _never_advises_deleting(message)
    assert _snapshot(settings.parent) == before and read(settings) == {"editor": "vscode"}


def test_a_first_save_that_cant_look_at_its_marker_claims_only_the_settings_unchanged(
    settings, monkeypatch
):
    """S3 final (Codex's Low finding): a first save makes .myLibrary-local, then can't look at
    its marker: refused; the folder it made is there (empty), so the message says only that the
    settings file was not changed, never "nothing was changed"."""
    sidecar = settings.parent / ".myLibrary-local"
    assert not sidecar.exists()
    before = settings.read_bytes()
    real_lstat = os.lstat

    def failing(path, *args, **kwargs):
        if os.path.basename(os.fspath(path)) == "settings.toml.lock":
            raise OSError(5, "Input/output error (simulated)")
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", failing)
    with pytest.raises(paths.SettingsUnreadable) as caught:
        paths.save_settings({"editor": "notepad"})
    monkeypatch.setattr(os, "lstat", real_lstat)
    message = str(caught.value)
    assert "the settings file was not changed" in message
    assert "nothing was changed" not in message
    _never_advises_deleting(message)
    assert sidecar.is_dir() and list(sidecar.iterdir()) == []  # (made by this save, as said)
    assert settings.read_bytes() == before and temp_files(settings.parent) == []


def test_a_symlinked_settings_file_is_saved_in_its_target(tmp_path, monkeypatch):
    """T-S6: the settings file is a symbolic link: the save goes to the real file and the
    link stays a link (today's os.replace on the link would have replaced it)."""
    real = tmp_path / "real" / "settings.toml"
    real.parent.mkdir()
    real.write_text("editor = 'vscode'\n", encoding="utf-8")
    link = tmp_path / "settings.toml"
    symlink_or_skip(real, link)
    monkeypatch.setattr(paths, "SETTINGS_FILE", link)
    monkeypatch.setattr(paths, "SETTINGS_SOURCE", "explicit")
    paths.save_settings({"editor": "notepad"})
    assert link.is_symlink() and read(real) == {"editor": "notepad"}


def test_different_settings_files_in_one_folder_have_their_own_locks(
    settings, tmp_path, children, monkeypatch
):
    """T-S8: a.toml held by another process doesn't make b.toml in the same folder wait; a
    hard-linked settings file is refused."""
    holder = child(children, tmp_path, settings, "lock")
    holder.expect("held")
    other = settings.parent / "other.toml"
    other.write_text("", encoding="utf-8")
    monkeypatch.setattr(paths, "SETTINGS_FILE", other)
    monkeypatch.setattr(paths, "SETTINGS_LOCK_WAIT", 1)
    paths.save_settings({"editor": "notepad"})
    holder.release()
    holder.finish()
    linked = settings.parent / "linked.toml"
    os.link(other, linked)
    monkeypatch.setattr(paths, "SETTINGS_FILE", linked)
    before = other.read_bytes()
    with pytest.raises(paths.SettingsNotWritable, match="hard link"):
        paths.save_settings({"editor": "system"})
    assert other.read_bytes() == before


def _case_sensitive_folder(folder: Path) -> None:
    folder.mkdir()
    done = subprocess.run(
        ["fsutil", "file", "setCaseSensitiveInfo", str(folder), "enable"],
        capture_output=True, text=True,
    )  # fmt: skip
    if done.returncode:
        pytest.skip(f"can't make a case-sensitive folder here: {done.stdout}{done.stderr}")


def _case_insensitive_again(folder: Path) -> None:
    subprocess.run(["fsutil", "file", "setCaseSensitiveInfo", str(folder), "disable"])


@WINDOWS
def test_settings_in_a_case_sensitive_folder_are_refused(tmp_path, monkeypatch, children):
    """T-S8 (D5): a.toml and A.toml in a case-sensitive Windows folder: both saves refused
    with the D5 message, nothing created (no lock folder), every file there unchanged."""
    folder = tmp_path / "case sensitive"
    _case_sensitive_folder(folder)
    try:
        files = {}
        for name, text in (("a.toml", "editor = 'vscode'\n"), ("A.toml", "editor = 'custom'\n")):
            (folder / name).write_text(text, encoding="utf-8")
            files[name] = text
        backup = folder / "a.toml.bak"
        backup.write_bytes(b"backup")
        times = {p.name: p.stat().st_mtime_ns for p in folder.iterdir()}
        monkeypatch.setattr(paths, "SETTINGS_SOURCE", "explicit")
        for name in files:
            monkeypatch.setattr(paths, "SETTINGS_FILE", folder / name)
            with pytest.raises(paths.SettingsNotWritable, match="upper and lower case"):
                paths.save_settings({"editor": "notepad"})
        assert not (folder / ".myLibrary-local").exists()
        for name, text in files.items():
            assert (folder / name).read_text(encoding="utf-8") == text
        assert backup.read_bytes() == b"backup"
        assert {p.name: p.stat().st_mtime_ns for p in folder.iterdir()} == times
        # (round 1: a program started with such a settings file stops at the start, at import,
        # before any save is asked for; nothing is created or changed)
        env = {k: v for k, v in os.environ.items() if k not in (paths.ENV_VAR, paths.SETTINGS_VAR)}
        env.update({"PYTHONPATH": str(paths.APP / "scripts"),
                    paths.SETTINGS_VAR: str(folder / "a.toml"),
                    paths.ENV_VAR: str(tmp_path / "child library")})  # fmt: skip
        started = subprocess.run(
            [sys.executable, "-c", "import paths; print('started')"], env=env,
            capture_output=True, text=True, timeout=WAIT,
        )  # fmt: skip
        assert started.returncode != 0 and started.stdout == ""
        assert "upper and lower case" in started.stderr
        assert not (folder / ".myLibrary-local").exists()
        assert {p.name: p.stat().st_mtime_ns for p in folder.iterdir()} == times
        assert not (tmp_path / "child library").exists()
    finally:
        if (folder / "A.toml").exists():  # (case sensitivity can't be turned off with both)
            (folder / "A.toml").unlink()
        _case_insensitive_again(folder)


@WINDOWS
def test_a_case_sensitive_lock_folder_is_refused_before_the_marker(settings):
    """T-S8: an ordinary settings folder whose .myLibrary-local is case-sensitive: refused
    before the marker is created."""
    sidecar = settings.parent / ".myLibrary-local"
    _case_sensitive_folder(sidecar)
    try:
        with pytest.raises(paths.SettingsNotWritable, match="upper and lower case"):
            paths.save_settings({"editor": "notepad"})
        assert list(sidecar.iterdir()) == [] and read(settings) == {"editor": "vscode"}
    finally:
        _case_insensitive_again(sidecar)


def test_a_settings_file_can_never_be_a_lock_marker(settings, tmp_path, children, monkeypatch):
    """T-S9: process A holds the lock of <tmp>/settings.toml; B is started with its marker as
    the settings file: refused at the start; in-process too; the marker is the same file,
    A still holds the lock (C waits for it), and C saves once A lets go."""
    a = child(children, tmp_path, settings, "hold", "editor", '"notepad"')
    a.expect("held")
    marker = settings.parent / ".myLibrary-local" / "settings.toml.lock"
    # (its identity, size and time: its byte is locked by A, so it can't be read meanwhile)
    identity = (marker.stat().st_ino, marker.stat().st_size, marker.stat().st_mtime_ns)
    b = subprocess.run(
        [sys.executable, "-c", "import paths"], capture_output=True, text=True, timeout=WAIT,
        env={**os.environ, paths.SETTINGS_VAR: str(marker),
             "PYTHONPATH": str(paths.APP / "scripts")},
    )  # fmt: skip
    assert b.returncode != 0 and "lock files" in b.stderr
    monkeypatch.setattr(paths, "SETTINGS_FILE", marker)
    with pytest.raises(paths.SettingsNotWritable, match="lock files"):
        paths.save_settings({"editor": "system"})
    assert (marker.stat().st_ino, marker.stat().st_size, marker.stat().st_mtime_ns) == identity
    c = child(children, tmp_path, settings, "save", "backup_pdfs", "true")
    c.expect("contended:os")
    a.release()
    assert a.finish().startswith("done") and c.finish().startswith("done")
    assert read(settings) == {"editor": "notepad", "backup_pdfs": True}


# --- the case-sensitivity question: only a clear "no" lets a folder hold settings (D5) -------


class FakeKernel32:
    """CreateFileW / GetFileInformationByHandleEx with chosen answers."""

    def __init__(self, open_error=0, query_error=0, flags=0):
        self.open_error, self.query_error, self.flags = open_error, query_error, flags

    def CreateFileW(self, *args):  # noqa: N802 (Windows' name)
        import ctypes

        if self.open_error:
            ctypes.set_last_error(self.open_error)
            return ctypes.c_void_p(-1).value
        return 1234

    def GetFileInformationByHandleEx(self, handle, cls, buffer, size):  # noqa: N802
        import ctypes

        if self.query_error:
            ctypes.set_last_error(self.query_error)
            return 0
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ulong))[0] = self.flags
        return 1

    def CloseHandle(self, handle):  # noqa: N802
        return 1


ERROR_INVALID_FUNCTION, ERROR_ACCESS_DENIED, ERROR_INVALID_PARAMETER = 1, 5, 87
ERROR_NOT_SUPPORTED = 50


@WINDOWS
@pytest.mark.parametrize(
    "answer",
    ["sensitive", "open fails", "invalid parameter", "not supported", "invalid function",
     "access denied", "unexpected", "raises"],
)  # fmt: skip
@pytest.mark.parametrize("asked_about", ["settings folder", "lock folder"])
def test_only_a_clear_answer_lets_a_folder_hold_settings(
    settings, monkeypatch, answer, asked_about
):
    """T-S10: the flag set, or any failed or unclear answer (the codes once thought harmless
    included), refuses the folder; settings, lock folder, marker and a neighbour unchanged."""
    fakes = {
        "sensitive": FakeKernel32(flags=1),
        "open fails": FakeKernel32(open_error=ERROR_ACCESS_DENIED),
        "invalid parameter": FakeKernel32(query_error=ERROR_INVALID_PARAMETER),
        "not supported": FakeKernel32(query_error=ERROR_NOT_SUPPORTED),
        "invalid function": FakeKernel32(query_error=ERROR_INVALID_FUNCTION),
        "access denied": FakeKernel32(query_error=ERROR_ACCESS_DENIED),
        "unexpected": FakeKernel32(query_error=1234),
    }  # fmt: skip
    clear = FakeKernel32(flags=0)
    sidecar = settings.parent / ".myLibrary-local"
    neighbour = settings.parent / "neighbour.txt"
    neighbour.write_bytes(b"n")
    if asked_about == "lock folder":
        sidecar.mkdir()
    real_check = paths._refuse_case_sensitive

    def kernel_for(folder):
        if answer == "raises":
            raise ctypes_error
        is_sidecar = Path(str(folder).removeprefix("\\\\?\\")).name == ".myLibrary-local"
        return fakes.get(answer) if is_sidecar == (asked_about == "lock folder") else clear

    ctypes_error = OSError("ctypes isn't available")

    def check(folder):
        monkeypatch.setattr(platform_services, "_kernel32", lambda: kernel_for(folder))
        return real_check(folder)

    monkeypatch.setattr(paths, "_refuse_case_sensitive", check)
    before = {p.name: p.read_bytes() for p in settings.parent.iterdir() if p.is_file()}
    with pytest.raises(paths.SettingsNotWritable, match="upper and lower case"):
        paths.save_settings({"editor": "notepad"})
    assert {p.name: p.read_bytes() for p in settings.parent.iterdir() if p.is_file()} == before
    assert not (sidecar / "settings.toml.lock").exists()
    if asked_about == "settings folder":
        assert not sidecar.exists()


@WINDOWS
def test_a_real_ordinary_folder_answers_clearly(settings):
    """T-S10: the real query (nothing injected) on an ordinary NTFS folder: not
    case-sensitive, so settings are saved there."""
    assert platform_services.windows_case_sensitive(str(settings.parent)) is False
    paths.save_settings({"editor": "notepad"})
    assert read(settings)["editor"] == "notepad"


@WINDOWS
def test_a_folder_made_case_sensitive_while_waiting_is_refused(settings, monkeypatch):
    """T-S10: B waits for the lock (handshake); meanwhile its folder becomes case-sensitive
    (injected: the flag can only be set on an empty folder); after the locks B refuses."""
    a_inside, a_go, b_waiting = threading.Event(), threading.Event(), threading.Event()
    flipped = threading.Event()
    real = platform_services.windows_case_sensitive

    def before_publish():
        if threading.current_thread().name == "A":
            a_inside.set()
            assert a_go.wait(WAIT)

    monkeypatch.setattr(paths, "_on_before_publish", before_publish)
    monkeypatch.setattr(
        paths, "_on_lock_contended",
        lambda kind: threading.current_thread().name == "B" and b_waiting.set(),
    )  # fmt: skip

    def case_sensitive(folder):  # (true for B once flipped: as if set while B waited)
        if flipped.is_set() and threading.current_thread().name == "B":
            return True
        return real(folder)

    monkeypatch.setattr(platform_services, "windows_case_sensitive", case_sensitive)
    results = {}
    a = threading.Thread(target=lambda: _keep(results, "a", {"editor": "notepad"}), name="A")
    a.start()
    assert a_inside.wait(WAIT)
    b = threading.Thread(target=lambda: _keep(results, "b", {"backup_pdfs": True}), name="B")
    b.start()
    assert b_waiting.wait(WAIT)
    flipped.set()
    a_go.set()
    a.join(WAIT)
    b.join(WAIT)
    assert isinstance(results["a"], dict)
    assert isinstance(results["b"], paths.SettingsNotWritable)
    assert read(settings) == {"editor": "notepad"}


def test_no_case_question_off_windows(settings, monkeypatch):
    """T-S10: elsewhere nothing is asked."""
    monkeypatch.setattr(paths.os, "name", "posix")
    asked = []
    monkeypatch.setattr(platform_services, "windows_case_sensitive", lambda f: asked.append(f))
    paths._refuse_case_sensitive(settings.parent)
    assert asked == []


# --- publication failures, by phase -------------------------------------------------------------


@WINDOWS
def test_a_replacement_blocked_by_an_open_file_then_saved(
    settings, tmp_path, children, monkeypatch
):
    """T-R8, T-P3 (D3): an open handle without delete sharing blocks the replacement until the
    retries run out: SettingsBlocked (retry wording, no claim about who), the file's bytes
    unchanged, no temporary file, no lock held; through the page with a library change: 400
    and no restart; once the handle is closed the same save succeeds."""
    restarts = []
    monkeypatch.setattr(library_server, "restart_later", lambda server: restarts.append(1))
    outcomes = []
    monkeypatch.setattr(
        paths, "_on_settings_outcome", lambda kind, data=None: outcomes.append(kind)
    )
    before = settings.read_bytes()
    handle = open(settings, "rb")  # noqa: SIM115 (closed below)
    try:
        with pytest.raises(
            paths.SettingsBlocked, match="in use. The settings file was not changed. Try again"
        ) as e:
            paths.save_settings({"editor": "notepad"})
        assert isinstance(e.value.__cause__, safe_io.ReplaceBlocked)
        assert "another program" not in str(e.value)
        assert settings.read_bytes() == before and not temp_files(settings.parent)
        assert outcomes == ["blocked"]
        results = {}  # (the locks are free: for another thread...)
        empty_save = threading.Thread(target=lambda: _keep(results, "t", {}))
        empty_save.start()
        empty_save.join(WAIT)
        assert isinstance(results["t"], dict)
        other = child(children, tmp_path, settings, "lock", 2)
        other.expect("held")  # (...and for another process)
        other.release()
        other.finish()
        server = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/api/settings", method="POST",
                data=json.dumps({"save": {"library": str(tmp_path / "next library")}}).encode(),
                headers={"Content-Type": "application/json",
                         "X-Library-Token": library_server.TOKEN},
            )  # fmt: skip
            with pytest.raises(urllib.error.HTTPError) as answer:
                urllib.request.urlopen(request, timeout=WAIT)
            assert answer.value.code == 400
            assert "blocked" in json.load(answer.value)["error"]
        finally:
            server.shutdown()
        assert restarts == [] and settings.read_bytes() == before
    finally:
        handle.close()
    paths.save_settings({"editor": "notepad"})
    assert read(settings)["editor"] == "notepad"


@WINDOWS
def test_a_read_failing_inside_the_transaction_releases_the_locks(
    settings, tmp_path, children, monkeypatch
):
    """T-R9: the reread with both locks held fails (the file refused): SettingsUnreadable,
    nothing written, both locks released."""
    import msvcrt

    monkeypatch.setattr(safe_io, "TRIES", 2)
    monkeypatch.setattr(safe_io.time, "sleep", lambda s: None)
    handle = open(settings, "r+b")  # noqa: SIM115
    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    before = None
    try:
        with pytest.raises(paths.SettingsUnreadable):
            paths.save_settings({"editor": "notepad"})
    finally:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        handle.close()
    before = read(settings)
    assert before == {"editor": "vscode"} and not temp_files(settings.parent)
    monkeypatch.undo()
    monkeypatch.setattr(paths, "SETTINGS_FILE", settings)
    monkeypatch.setattr(paths, "SETTINGS_SOURCE", "explicit")
    quick_save_elsewhere(tmp_path, children, settings)


def _fail_at(monkeypatch, phase: str):
    """Make safe_io.write_bytes fail in one phase, for real where possible."""
    import builtins

    real_open, real_replace = builtins.open, os.replace

    def is_temp(name) -> bool:
        return str(name).endswith(".tmp")

    if phase == "create":

        def failing_open(file, mode="r", *args, **kwargs):
            if is_temp(file) and "w" in mode:
                raise PermissionError(13, "Permission denied", str(file))
            return real_open(file, mode, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", failing_open)
    elif phase in ("write", "write-permission", "flush"):

        class Failing:
            def __init__(self, f):
                self.f = f

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                self.f.close()

            def write(self, data):
                if phase == "write":
                    raise OSError(5, "Input/output error")
                if phase == "write-permission":
                    raise PermissionError(13, "Permission denied")
                return self.f.write(data)

            def flush(self):
                raise OSError(5, "Input/output error")

            def fileno(self):
                return self.f.fileno()

        def failing_open(file, mode="r", *args, **kwargs):
            f = real_open(file, mode, *args, **kwargs)
            return Failing(f) if is_temp(file) and "w" in mode else f

        monkeypatch.setattr(builtins, "open", failing_open)
    elif phase == "fsync":

        def failing_fsync(fd):
            raise OSError(5, "Input/output error")

        monkeypatch.setattr(os, "fsync", failing_fsync)
    elif phase == "replace-other":

        def failing_replace(src, dst):
            raise OSError(18, "Invalid cross-device link")

        monkeypatch.setattr(os, "replace", failing_replace)
    return real_replace


@pytest.mark.parametrize(
    "phase", ["create", "write", "write-permission", "flush", "fsync", "replace-other"]
)
def test_failures_before_or_outside_contention_are_never_called_blocked(
    settings, tmp_path, children, monkeypatch, phase
):
    """T-P1, T-P2, T-P5: creating, writing, flushing or syncing the temporary file fails (also
    with "permission denied"), or the replacement fails otherwise: SettingsSaveFailed, never
    SettingsBlocked, the in-use probe never asked; the file's bytes unchanged and said so;
    no temporary file; locks released; a retry without the failure succeeds."""
    probes = []
    monkeypatch.setattr(platform_services, "windows_file_in_use", lambda p: probes.append(p))
    outcomes = []
    monkeypatch.setattr(
        paths, "_on_settings_outcome", lambda kind, data=None: outcomes.append(kind)
    )
    _fail_at(monkeypatch, phase)
    before = settings.read_bytes()
    with pytest.raises(paths.SettingsSaveFailed, match="was not changed") as e:
        paths.save_settings({"editor": "notepad"})
    assert not isinstance(e.value, paths.SettingsBlocked) and probes == []
    assert outcomes == ["failed"]
    monkeypatch.undo()
    monkeypatch.setattr(paths, "SETTINGS_FILE", settings)
    monkeypatch.setattr(paths, "SETTINGS_SOURCE", "explicit")
    assert settings.read_bytes() == before and not temp_files(settings.parent)
    quick_save_elsewhere(tmp_path, children, settings)
    paths.save_settings({"editor": "notepad"})
    assert read(settings)["editor"] == "notepad"


@WINDOWS
def test_a_read_only_settings_file_is_not_called_blocked(settings, tmp_path, children, monkeypatch):
    """T-P4: a read-only file refuses the replacement with the same Windows error as an open
    one: SettingsSaveFailed naming the read-only mark, not SettingsBlocked; once writable again
    the save succeeds."""
    import stat

    monkeypatch.setattr(safe_io.time, "sleep", lambda s: None)
    before = settings.read_bytes()
    os.chmod(settings, stat.S_IREAD)
    try:
        with pytest.raises(paths.SettingsSaveFailed, match="marked read-only") as e:
            paths.save_settings({"editor": "notepad"})
        assert isinstance(e.value.__cause__, safe_io.ReplaceBlocked)
        assert "was not changed" in str(e.value) and "another program" not in str(e.value)
        assert settings.read_bytes() == before
    finally:
        os.chmod(settings, stat.S_IWRITE | stat.S_IREAD)
    assert not temp_files(settings.parent)
    paths.save_settings({"editor": "notepad"})
    assert read(settings)["editor"] == "notepad"


@WINDOWS
def test_a_read_only_file_also_held_open_is_not_called_blocked(settings, monkeypatch):
    """Round 1 (Codex): read-only AND held open by a reader: the lasting restriction wins over
    the sign of use: SettingsSaveFailed (read-only named), never a retryable D3 block; the
    original error kept; locks released (the next save, made writable and closed, succeeds)."""
    import stat

    monkeypatch.setattr(safe_io.time, "sleep", lambda s: None)
    probes = []
    real_probe = platform_services.windows_file_in_use
    monkeypatch.setattr(
        platform_services, "windows_file_in_use", lambda p: probes.append(p) or real_probe(p)
    )
    before = settings.read_bytes()
    os.chmod(settings, stat.S_IREAD)
    reader = open(settings, "rb")  # noqa: SIM115 (closed below)
    try:
        with pytest.raises(paths.SettingsSaveFailed, match="marked read-only") as e:
            paths.save_settings({"editor": "notepad"})
        assert not isinstance(e.value, paths.SettingsBlocked)
        assert isinstance(e.value.__cause__, safe_io.ReplaceBlocked)
        assert "was not changed" in str(e.value) and probes == []  # (no probe needed)
        assert settings.read_bytes() == before
    finally:
        reader.close()
        os.chmod(settings, stat.S_IWRITE | stat.S_IREAD)
    paths.save_settings({"editor": "notepad"})
    assert read(settings)["editor"] == "notepad"


@WINDOWS
def test_an_inconclusive_probe_is_never_called_blocked(settings, monkeypatch):
    """Round 1: a real open reader blocks the replacement, but the in-use probe can't answer
    (errors of every kind): SettingsSaveFailed saying it couldn't be checked, not blocked."""
    monkeypatch.setattr(safe_io.time, "sleep", lambda s: None)
    before = settings.read_bytes()
    reader = open(settings, "rb")  # noqa: SIM115 (closed below)
    try:
        for probe_error in (OSError("access denied"), OSError("unexpected"), RuntimeError("x")):

            def probe(path, error=probe_error):
                raise error

            monkeypatch.setattr(platform_services, "windows_file_in_use", probe)
            with pytest.raises(paths.SettingsSaveFailed, match="couldn't be checked") as e:
                paths.save_settings({"editor": "notepad"})
            assert "was not changed" in str(e.value)
            assert isinstance(e.value.__cause__, safe_io.ReplaceBlocked)
    finally:
        reader.close()
    assert settings.read_bytes() == before


@WINDOWS
def test_blocked_only_when_the_file_is_read_back_unchanged(settings, monkeypatch):
    """Round 1: a real open reader (in use seen) but the file can't be read back afterwards:
    not "blocked, nothing changed" but SettingsSaveFailed saying it couldn't be confirmed."""
    monkeypatch.setattr(safe_io.time, "sleep", lambda s: None)
    monkeypatch.setattr(
        paths, "_state_now",
        lambda dest, new, old: ("unknown", "Couldn't confirm what the settings file holds now."),
    )  # fmt: skip
    reader = open(settings, "rb")  # noqa: SIM115 (closed below)
    try:
        with pytest.raises(paths.SettingsSaveFailed, match="Couldn't confirm") as e:
            paths.save_settings({"editor": "notepad"})
        assert "was in use" in str(e.value) and "was not changed" not in str(e.value)
    finally:
        reader.close()


@pytest.mark.parametrize(
    ("answers", "blocked"),
    [([False, False, True], True), ([False] * 5, False), ([OSError("x"), True], True),
     ([OSError("x")] * 5, False)],
)  # fmt: skip
def test_in_use_is_confirmed_only_by_a_sharing_violation_seen(
    settings, monkeypatch, answers, blocked
):
    """T-P3/T-P4: after a blocked replacement the file is probed a few times (a reader's
    handle may be open only for an instant): blocked only if one look sees it in use; looks
    that find it free or can't answer never count; at most IN_USE_LOOKS looks."""
    monkeypatch.setattr(paths.os, "name", "nt")
    monkeypatch.setattr(safe_io, "write_bytes", _blocked_publication)
    monkeypatch.setattr(paths.time, "sleep", lambda s: None)
    looks = []

    def probe(path):
        answer = answers[min(len(looks), len(answers) - 1)]
        looks.append(answer)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(platform_services, "windows_file_in_use", probe)
    with pytest.raises(paths.SettingsBlocked if blocked else paths.SettingsSaveFailed):
        paths.save_settings({"editor": "notepad"})
    assert len(looks) <= paths.IN_USE_LOOKS
    assert read(settings) == {"editor": "vscode"}


def test_a_cleanup_failure_after_a_failed_replacement(settings, tmp_path, children, monkeypatch):
    """T-P6: the replacement fails, then removing the temporary file fails too: the error
    names both and the file left behind; the settings unchanged and said so; locks released."""
    real_unlink = Path.unlink
    left = []

    def failing_replace(src, dst):
        raise OSError(5, "Input/output error")

    def failing_unlink(self, missing_ok=False):
        if self.name.endswith(".tmp"):
            left.append(self)
            raise PermissionError(13, "Permission denied", str(self))
        return real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(os, "replace", failing_replace)
    monkeypatch.setattr(Path, "unlink", failing_unlink)
    before = settings.read_bytes()
    with pytest.raises(paths.SettingsSaveFailed) as e:
        paths.save_settings({"editor": "notepad"})
    message = str(e.value)
    assert "Input/output error" in message and left and left[0].name in message
    assert "couldn't be removed" in message and "was not changed" in message
    monkeypatch.undo()
    monkeypatch.setattr(paths, "SETTINGS_FILE", settings)
    monkeypatch.setattr(paths, "SETTINGS_SOURCE", "explicit")
    assert settings.read_bytes() == before
    for leftover in temp_files(settings.parent):
        leftover.unlink()  # (the test's own injected left-over)
    quick_save_elsewhere(tmp_path, children, settings)


def test_a_cleanup_failure_after_a_successful_replacement(
    settings, tmp_path, children, monkeypatch
):
    """T-P6 (Codex): the replacement succeeded, then the clean-up step raised: the new bytes
    stay in place, the error says the new settings are in the file (never that the old ones
    survived), no restart, both locks released, and the next save works."""
    restarts = []
    monkeypatch.setattr(library_server, "restart_later", lambda server: restarts.append(1))
    real_unlink = Path.unlink

    def failing_unlink(self, missing_ok=False):  # (the settings file's temporary file only)
        if self.name.startswith(f".{settings.name}.") and self.name.endswith(".tmp"):
            raise PermissionError(13, "Permission denied", str(self))
        return real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", failing_unlink)
    with pytest.raises(paths.SettingsSaveFailed) as e:
        paths.save_settings({"editor": "notepad"})
    message = str(e.value)
    assert "The new settings are in the settings file" in message
    assert "was not changed" not in message and "couldn't be removed" in message
    assert read(settings) == {"editor": "notepad"}
    server = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/settings", method="POST",
            data=json.dumps({"save": {"library": str(tmp_path / "next library")}}).encode(),
            headers={"Content-Type": "application/json", "X-Library-Token": library_server.TOKEN},
        )  # fmt: skip
        with pytest.raises(urllib.error.HTTPError) as answer:
            urllib.request.urlopen(request, timeout=WAIT)
        assert answer.value.code == 500
        assert "The new settings are in the settings file" in json.load(answer.value)["error"]
    finally:
        server.shutdown()
    assert restarts == []
    monkeypatch.undo()
    monkeypatch.setattr(paths, "SETTINGS_FILE", settings)
    monkeypatch.setattr(paths, "SETTINGS_SOURCE", "explicit")
    quick_save_elsewhere(tmp_path, children, settings)
    paths.save_settings({"editor": "system"})
    assert read(settings)["editor"] == "system"


def test_the_file_state_message_is_read_not_assumed(settings, monkeypatch):
    """T-P7: one outcome per failed save; when the file can't be read back the message says
    so instead of claiming anything."""
    outcomes = []
    monkeypatch.setattr(
        paths, "_on_settings_outcome", lambda kind, data=None: outcomes.append(kind)
    )
    monkeypatch.setattr(safe_io, "write_bytes", _io_error)
    real_read = safe_io.read_bytes
    calls = []

    def read_then_fail(path):
        calls.append(path)
        if len(calls) > 1:  # (the transaction's own read works; the read-back doesn't)
            raise PermissionError(13, "Permission denied")
        return real_read(path)

    monkeypatch.setattr(safe_io, "read_bytes", read_then_fail)
    with pytest.raises(paths.SettingsSaveFailed, match="Couldn't confirm what the settings file"):
        paths.save_settings({"editor": "notepad"})
    assert outcomes == ["failed"]


def test_replace_blocked_is_still_a_permission_error_with_the_same_message(tmp_path, monkeypatch):
    """safe_io's one S3 change: exhausted replacement retries raise ReplaceBlocked, a
    PermissionError with the message every caller already shows."""
    monkeypatch.setattr(safe_io.time, "sleep", lambda s: None)
    attempts = []

    def refused(src, dst):
        attempts.append(1)
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(os, "replace", refused)
    with pytest.raises(PermissionError, match="is open in another program") as e:
        safe_io.write_text(tmp_path / "f.txt", "x")
    assert isinstance(e.value, safe_io.ReplaceBlocked)
    assert e.value.attempts == safe_io.TRIES == len(attempts)
    assert e.value.target == tmp_path / "f.txt"
    assert not list(tmp_path.iterdir())  # (no temporary file left)
