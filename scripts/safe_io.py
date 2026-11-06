"""Writing the library's files safely: whole or not at all, one writer at a time, never over
data that couldn't be read, and never cut off by quitting.

Every file the tool changes (catalog.csv, notes READMEs, vocabulary.md, the reading log, review
progress, settings, caches) goes through here:

- write_text / write_bytes: the new content goes to a temporary file in the same folder, is
  flushed to disk and then swapped in (os.replace), so a crash, a full disk or Quit leaves
  either the old file or the new one, never half of one.
- lock_for(path), update_text, update_json: a read-change-write of one file holds that file's
  lock, so two threads (two uploads, a page turn and a chapter tick) can't lose each other's
  change. Different files don't wait for each other.
- load_json: a file that can't be read is never treated as empty and saved over. For your own
  data the file is left as it is, a copy is kept next to it (<name>.damaged-<time>), the
  previous good version (<name>.bak, kept by backup=True) is used if there is one, and
  otherwise DamagedFile says which file and what to do. A cache is just rebuilt.
- critical() / close(): quitting waits until no file operation is in progress, and refuses new
  ones once it has started.

The locks are per process: the library page server and a command-line script started at the
same time still can't leave half a file, but one of two simultaneous changes can be lost.
"""

import json
import os
import shutil
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


class DamagedFile(Exception):
    """A file holding your data can't be read; it was left exactly as it was."""

    def __init__(self, path: Path, problem: str, copy: Path | None):
        self.path, self.problem, self.copy = path, problem, copy
        kept = f" A copy is kept as {copy.name}." if copy else ""
        super().__init__(
            f"{_shown(path)} can't be read ({problem}), so nothing was written to it and it was "
            f"left as it is.{kept} Repair it in a text editor, or move it away to start a new "
            "one."
        )


class ShuttingDown(RuntimeError):
    """myLibrary is quitting: no new file operations start."""

    def __init__(self):
        super().__init__("myLibrary is stopping; nothing new is written")


def _shown(path: Path) -> str:
    """notes/reading-log.json rather than the whole path, when it's in a library folder."""
    parts = path.parts
    for anchor in ("notes", ".cache", "glossaries"):
        if anchor in parts:
            return "/".join(parts[parts.index(anchor) :])
    return path.name


# --- quitting ------------------------------------------------------------------------------------

_state = threading.Condition()
_active = 0  # file operations in progress
_closing = False
_depth = threading.local()  # a thread already inside critical() may go on (nested operations)


@contextmanager
def critical():
    """A file operation (or several that belong together) that quitting must not cut off."""
    global _active
    nested = getattr(_depth, "n", 0) > 0
    with _state:
        if _closing and not nested:
            raise ShuttingDown()
        _active += 1
    _depth.n = getattr(_depth, "n", 0) + 1
    try:
        yield
    finally:
        _depth.n -= 1
        with _state:
            _active -= 1
            _state.notify_all()


def close(timeout: float = 60) -> bool:
    """Refuse new file operations and wait for the running ones (at most `timeout` seconds).
    True if none is left."""
    global _closing
    with _state:
        _closing = True
        return _state.wait_for(lambda: _active == 0, timeout)


def reopen() -> None:
    """Allow file operations again (after close(); used by tests)."""
    global _closing
    with _state:
        _closing = False


# --- locks ---------------------------------------------------------------------------------------

_locks: dict[str, threading.RLock] = {}
_locks_lock = threading.Lock()


def lock_for(path: Path) -> threading.RLock:
    """The lock for one file (the same object for every spelling of its path)."""
    key = os.path.normcase(os.path.abspath(path))
    with _locks_lock:
        return _locks.setdefault(key, threading.RLock())


# --- writing -------------------------------------------------------------------------------------

# Windows: while one thread swaps a file in, another one opening it for reading (and a virus
# scanner or the search indexer) briefly gets "permission denied", and the other way round.
# Both sides wait a little and try again: up to about 2 seconds in all.
TRIES = 10


def _retry(action, path: Path):
    for attempt in range(TRIES):
        try:
            return action()
        except PermissionError:
            if attempt == TRIES - 1:
                raise PermissionError(
                    f"{path.name} is open in another program (Excel, a PDF viewer…) that "
                    "doesn't let it be used; close it and try again"
                ) from None
            time.sleep(0.02 * (attempt + 1))


def _swap(tmp: Path, path: Path) -> None:
    _retry(lambda: os.replace(tmp, path), path)


def read_bytes(path: Path) -> bytes:
    """Path.read_bytes, waiting out a moment when another thread is swapping the file in."""
    return _retry(Path(path).read_bytes, Path(path))


def read_text(path: Path, encoding: str = "utf-8") -> str:
    """Path.read_text (same newline handling), waiting out a swap in progress (read_bytes)."""
    return _retry(lambda: Path(path).read_text(encoding=encoding), Path(path))


def write_bytes(path: Path, data: bytes, *, backup: bool = False) -> None:
    """Replace `path` with `data`, whole or not at all. backup=True first keeps the current
    version as <name>.bak (for files whose history matters: the reading log, review progress)."""
    path = Path(path)
    with critical():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
        try:
            with open(tmp, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            if backup and path.exists():
                _keep_previous(path)
            _swap(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)


def write_text(
    path: Path, text: str, *, encoding: str = "utf-8", newline: str | None = None,
    backup: bool = False,
) -> None:  # fmt: skip
    """Like Path.write_text (same line endings: newline=None writes "\\n" as the system's),
    but whole or not at all."""
    if newline is None:
        newline = os.linesep
    if newline != "":
        text = text.replace("\n", newline)
    write_bytes(path, text.encode(encoding), backup=backup)


def _keep_previous(path: Path) -> None:
    bak = path.with_name(path.name + ".bak")
    tmp = bak.with_name(f".{bak.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        shutil.copy2(path, tmp)
        _swap(tmp, bak)
    finally:
        tmp.unlink(missing_ok=True)


def update_text(path: Path, change, *, encoding: str = "utf-8") -> str:
    """Read `path`, apply change(text) -> new text, write it if it changed; one writer at a
    time. Returns the new text."""
    path = Path(path)
    with lock_for(path), critical():
        old = read_text(path, encoding)
        new = change(old)
        if new != old:
            write_text(path, new, encoding=encoding)
        return new


# --- JSON ----------------------------------------------------------------------------------------


def _parse(path: Path):
    return json.loads(read_text(path))


def _keep_damaged(path: Path) -> Path | None:
    """A copy of a damaged file next to it (one per distinct content)."""
    data = read_bytes(path)
    for earlier in path.parent.glob(f"{path.name}.damaged-*"):
        try:
            if earlier.read_bytes() == data:
                return earlier
        except OSError:
            continue
    copy = path.with_name(f"{path.name}.damaged-{datetime.now():%Y%m%d-%H%M%S-%f}")
    try:
        write_bytes(copy, data)
    except OSError:
        return None
    return copy


def load_json(path: Path, default, *, cache: bool = False):
    """The JSON in `path`, or `default` if there is no file.

    A file that can't be read: a cache (cache=True) starts again from `default` (it's rebuilt
    from the books). Your own data is never replaced: the file is left as it is, a copy kept,
    and its previous version (.bak) used if it reads; otherwise DamagedFile.
    """
    return _load(Path(path), default, cache)[0]


def _load(path: Path, default, cache: bool):
    """(data, whether it came from the file itself in good order)."""
    if not path.exists():
        return default, True
    try:
        return _parse(path), True
    except (ValueError, UnicodeDecodeError) as e:
        if cache:
            print(f"  ! {_shown(path)} couldn't be read ({e}); it's a cache, so it's rebuilt")
            return default, False
        problem = str(e)
    copy = _keep_damaged(path)
    bak = path.with_name(path.name + ".bak")
    try:
        data = _parse(bak)
    except OSError, ValueError, UnicodeDecodeError:
        raise DamagedFile(path, problem, copy) from None
    kept = f" (the damaged one is kept as {copy.name})" if copy else ""
    print(f"  ! {_shown(path)} couldn't be read ({problem}); using its previous version{kept}")
    return data, False


def write_json(path: Path, data, *, backup: bool = False, **dump_options) -> None:
    write_text(path, json.dumps(data, **dump_options), backup=backup)


def update_json(path: Path, change, default, *, cache: bool = False, backup: bool = False,
                **dump_options):  # fmt: skip
    """Load (see load_json), apply change(data) (it changes data in place and may return a
    result), write; one writer at a time. Returns what change returned."""
    path = Path(path)
    with lock_for(path), critical():
        data, intact = _load(path, default, cache)
        result = change(data)
        # .bak is the last good version: never replace it with a copy of a damaged file
        write_json(path, data, backup=backup and intact, **dump_options)
        return result
