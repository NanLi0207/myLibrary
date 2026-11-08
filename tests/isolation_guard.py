"""D20: tests can't write the user's real library or settings.

Two layers, both started by tests/conftest.py before any of the app's modules is imported:

1. Redirect. Where the real library and settings are is found first, read-only: a separate
   Python process (no bytecode written) imports `paths` with the environment as it was and
   prints them. Then MYLIBRARY_SETTINGS and MYLIBRARY_LIBRARY name a new, empty settings file
   and library made for this run, so every module's paths (LIBRARY, CATALOG, ARCHIVE, ...)
   point there. Subprocesses the tests start inherit the same environment.
2. Guard. A Python audit hook refuses writes to the protected places (the real library, the
   settings files, the default library, a backup folder from the settings, library/ in this
   repository), and records each attempt: the test fails even if the code it ran caught the
   refusal (conftest's fixture). Reads are allowed. The paths written are compared as Windows
   compares them (case, \\\\?\\ forms), and also once links and junctions are followed.

What it doesn't cover (it isn't an operating-system sandbox):
- writes not made through Python's own file functions (native code writing on its own);
- subprocesses: they get the redirected environment, but no guard; one given an explicit
  real path isn't stopped (the browser tests' servers check which library they serve);
- a hard link into the library made before the run (one made during the run from a
  protected file is refused);
- operations relative to a directory file descriptor (dir_fd), which this code doesn't use.
The checksums of the real library taken around test runs stay an independent check.

Never installed by the app itself: only tests/conftest.py starts it.
"""

from __future__ import annotations

import atexit
import errno
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from importlib.util import find_spec
from pathlib import Path

PROTECTED_VAR = "MYLIBRARY_TEST_PROTECTED"  # the protected places, handed to inner test runs
RUN_MARKER = ".myLibrary-test-run"  # in the run's own folder: the only folder finish() deletes

_roots: list[str] = []  # protected places: normalised, plus their real locations
_extra: list[str] = []  # protected for a while by a test (protecting())
_watchers: list[list] = []  # the current test's record of refused writes (innermost last)
session_violations: list[str] = []  # refused writes outside any test
_state = threading.local()
_lock = threading.Lock()
run: dict = {}  # this run's folder, library and settings file (start())


# --- paths as Windows compares them ---------------------------------------------------------


def _text(path) -> str | None:
    if path is None or isinstance(path, int):  # (a file descriptor: no path to check)
        return None
    try:
        text = os.fsdecode(os.fspath(path))
    except TypeError:
        return None
    if text.startswith("file:"):  # an SQLite URI
        text = text[5:].split("?", 1)[0]
    if text.startswith("\\\\?\\UNC\\"):
        text = "\\\\" + text[8:]
    elif text.startswith("\\\\?\\"):
        text = text[4:]
    return text


def _forms(path) -> list[str]:
    """The path as written (absolute, case-folded) and where it really is (links and junctions
    followed, also for a file not created yet)."""
    text = _text(path)
    if not text:
        return []
    forms = [os.path.normcase(os.path.abspath(text))]
    try:
        real = os.path.normcase(os.path.realpath(text))
    except OSError, ValueError:
        real = forms[0]
    if real != forms[0]:
        forms.append(real)
    return forms


def _within(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("\\/") + os.sep)


def _protected_root(path) -> str | None:
    """The protected place `path` is in, if any."""
    with _lock:
        roots = _roots + _extra
    for form in _forms(path):
        for root in roots:
            if _within(form, root):
                return root
    return None


def _holds_protected(path) -> str | None:
    """The protected place inside folder `path` (deleting or moving `path` would take it)."""
    with _lock:
        roots = _roots + _extra
    for form in _forms(path):
        for root in roots:
            if _within(root, form):
                return root
    return None


# --- the guard ----------------------------------------------------------------------------------

_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC


def _targets(event: str, args: tuple) -> list[tuple[object, bool]]:
    """(path, whether a folder holding a protected place counts too) written by this event."""
    if event == "open":
        path, mode, flags = (tuple(args) + (None, None))[:3]
        if isinstance(mode, str):  # open(): "w", "a", "x" or "+" writes
            writes = any(c in mode for c in "wax+")
        else:  # os.open(): its flags
            writes = bool((flags or 0) & _WRITE_FLAGS)
        return [(path, False)] if writes else []
    if event in ("os.rename", "shutil.move"):  # (os.replace raises os.rename too)
        return [(args[0], True), (args[1], False)]
    if event in ("os.remove", "os.mkdir", "os.truncate", "os.chmod", "os.utime"):
        return [(args[0], False)]
    if event in ("os.rmdir", "shutil.rmtree"):
        return [(args[0], True)]
    if event in ("os.link", "os.symlink", "shutil.copyfile", "shutil.copytree"):
        # a hard link *from* a protected file would be a second name for it: refused too
        return [(args[1], False)] + ([(args[0], False)] if event == "os.link" else [])
    if event == "sqlite3.connect":
        database = args[0]
        text = os.fsdecode(database) if isinstance(database, (str, bytes, os.PathLike)) else ""
        if not text or text == ":memory:" or "mode=ro" in text:
            return []  # (read-only: allowed)
        return [(database, False)]
    if event in ("shutil.copy2", "shutil.copy"):  # (our wrappers: no event of their own)
        return [(args[1], False)]
    return []


def _refuse(event: str, path, root: str) -> None:
    message = (
        f"test isolation (D20): refused {event} on {_text(path)!r}, in the user's real data "
        f"({root}). Point the test at a temporary library (tmp_path) instead."
    )
    with _lock:
        (_watchers[-1] if _watchers else session_violations).append(message)
    raise PermissionError(errno.EACCES, message)


def _hook(event: str, args: tuple) -> None:
    if getattr(_state, "busy", False):
        return
    if event not in _EVENTS:
        return
    _state.busy = True
    try:
        for path, folder_too in _targets(event, args):
            root = _protected_root(path) or (_holds_protected(path) if folder_too else None)
            if root:
                _refuse(event, path, root)
    finally:
        _state.busy = False


_EVENTS = {
    "open", "os.rename", "os.remove", "os.rmdir", "os.mkdir", "os.truncate", "os.chmod",
    "os.utime", "os.link", "os.symlink", "shutil.copyfile", "shutil.copytree", "shutil.rmtree",
    "shutil.move", "sqlite3.connect", "shutil.copy2", "shutil.copy",
}  # fmt: skip


def _checked_copy(name: str, original):
    """shutil.copy2 / copy on Windows copy through CopyFile2, which raises no audit event."""

    def copy(src, dst, *args, **kwargs):
        target = os.path.join(dst, os.path.basename(src)) if os.path.isdir(dst) else dst
        _hook(f"shutil.{name}", (src, target))
        return original(src, dst, *args, **kwargs)

    copy.__wrapped__ = original
    return copy


_installed = False


def _install() -> None:
    global _installed
    if _installed:
        return
    sys.addaudithook(_hook)  # (for the rest of this process: a test process only)
    shutil.copy2 = _checked_copy("copy2", shutil.copy2)
    shutil.copy = _checked_copy("copy", shutil.copy)
    _installed = True


# --- what a test sees ---------------------------------------------------------------------------


@contextmanager
def watching():
    """Collect the writes refused meanwhile (a test's own record: conftest fails the test if
    it isn't empty, whether or not the code under test caught the refusal)."""
    seen: list[str] = []
    with _lock:
        _watchers.append(seen)
    try:
        yield seen
    finally:
        with _lock:
            _watchers.remove(seen)


@contextmanager
def protecting(*folders):
    """Treat these (temporary, invented) folders as the user's real data for a while: the
    guard's own tests never aim at the real library."""
    added = [form for folder in folders for form in _forms(folder)]
    with _lock:
        _extra.extend(added)
    try:
        yield
    finally:
        with _lock:
            for form in added:
                _extra.remove(form)


def protected() -> list[str]:
    with _lock:
        return list(_roots)


# --- starting and ending a run ------------------------------------------------------------------


def _app() -> Path:
    spec = find_spec("paths")  # found on pytest's pythonpath (scripts/), not imported
    if spec is None or not spec.origin:
        raise RuntimeError("test isolation (D20): scripts/paths.py isn't on the import path")
    return Path(spec.origin).resolve().parent.parent


def _discover(app: Path) -> list[str]:
    """Where the real library and settings are, as the app would find them now. Read-only: a
    separate process imports `paths` (which only reads its settings) and writes no bytecode."""
    code = (
        "import json, os, sys; sys.path.insert(0, sys.argv[1]); import paths; "
        "s = paths.load_settings(); "
        "print(json.dumps({'library': str(paths.LIBRARY), 'settings': str(paths.SETTINGS_FILE), "
        "'default': str(paths.DEFAULT_LIBRARY), 'backup': s.get('backup_folder') or ''}))"
    )
    done = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code, str(app / "scripts")],
        capture_output=True, text=True, encoding="utf-8", timeout=60, cwd=app,
    )  # fmt: skip
    if done.returncode:
        raise RuntimeError(
            "test isolation (D20): couldn't find where the real library and settings are, so "
            f"no test runs:\n{done.stdout}{done.stderr}"
        )
    found = json.loads(done.stdout.strip().splitlines()[-1])
    places = [found["library"], found["settings"], found["default"]]
    if found["backup"]:
        backup = Path(found["backup"]).expanduser()
        places.append(str(backup if backup.is_absolute() else app / backup))
    return places


def start() -> dict:
    """Before any app module is imported: protect the real places, make this run's own library
    and settings, point the environment at them, install the guard."""
    stray = sorted(
        m for m in ("paths", "safe_io", "catalog", "library_server", "add_book", "reader")
        if m in sys.modules
    )  # fmt: skip
    if stray:
        raise RuntimeError(
            f"test isolation (D20): {', '.join(stray)} was imported before tests/conftest.py "
            "could point it at a temporary library (a plugin or an earlier conftest?): no "
            "test runs with the real library's paths"
        )
    app = _app()
    if inherited := os.environ.get(PROTECTED_VAR):  # an inner test run: the outer run's list
        places = json.loads(inherited)
    else:
        places = _discover(app)
        if chosen := os.environ.get("MYLIBRARY_LIBRARY"):
            places.append(chosen)
        appdata = os.environ.get("APPDATA")
        places += [str(app / "library"), str(app / "local.toml")]
        if appdata:
            places.append(str(Path(appdata) / "myLibrary"))
    with _lock:
        _roots[:] = sorted({form for place in places for form in _forms(place)})
    folder = Path(tempfile.mkdtemp(prefix="myLibrary-test-run-"))
    (folder / RUN_MARKER).write_text("this test run's own library and settings\n")
    library, settings = folder / "library", folder / "settings.toml"
    library.mkdir()
    settings.write_text("# test run settings (tests/isolation_guard.py)\n", encoding="utf-8")
    if _protected_root(folder):
        raise RuntimeError(f"test isolation (D20): the temporary folder {folder} is protected")
    os.environ[PROTECTED_VAR] = json.dumps(places)
    os.environ["MYLIBRARY_LIBRARY"] = str(library)
    os.environ["MYLIBRARY_SETTINGS"] = str(settings)
    sys.dont_write_bytecode = True  # (no .pyc into library/code/, whose tests run too)
    run.update(folder=folder, library=library.resolve(), settings=settings.resolve())
    atexit.register(finish)  # also when the run never gets as far as pytest_unconfigure
    _install()
    return run


# Paths that only name a real place without being used as the library here: where a library
# would be made if none were chosen (one is: the run's). Still protected by the guard
NAMES_ONLY = {"paths.DEFAULT_LIBRARY"}


def check_modules() -> None:
    """After the app's modules are imported: their paths are the run's, never protected ones."""
    import paths

    if paths.LIBRARY != run["library"] or paths.SETTINGS_FILE != run["settings"]:
        raise RuntimeError(
            f"test isolation (D20): paths gives {paths.LIBRARY} and {paths.SETTINGS_FILE}, not "
            "this run's temporary library and settings"
        )
    scripts = str(_app() / "scripts")
    wrong = []
    for name, module in list(sys.modules.items()):
        if not str(getattr(module, "__file__", "") or "").startswith(scripts):
            continue
        for attr, value in vars(module).items():
            if f"{name}.{attr}" in NAMES_ONLY:
                continue
            if isinstance(value, Path) and (root := _protected_root(value)):
                wrong.append(f"{name}.{attr} = {value} (in {root})")
    if wrong:
        raise RuntimeError("test isolation (D20): still the real paths:\n" + "\n".join(wrong))


def finish() -> None:
    """Remove this run's own folder, and nothing else: only a folder this run made (its marker
    inside), never a protected one (the guard would refuse it too)."""
    remove_run_folder(run.get("folder"))


def remove_run_folder(folder) -> bool:
    if not folder:
        return False
    folder = Path(folder)
    if _protected_root(folder) or _holds_protected(folder):
        raise PermissionError(errno.EACCES, f"test isolation (D20): {folder} is protected")
    if not (folder / RUN_MARKER).is_file():
        return False  # not a test run's folder: left alone
    shutil.rmtree(folder, ignore_errors=True)
    return True
