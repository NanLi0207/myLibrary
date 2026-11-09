"""Several libraries on one computer: the list of your personal libraries, checking a folder
before it's added (read-only), each library's identity, the Test & Demo library, and finding or
starting the server that shows a library.

Two modes (docs/LIBRARIES.md):

- **Personal libraries**: your own, anywhere on this computer. Their list is this computer's
  (paths.LOCAL_DIR / libraries.json; never inside a library, never in git): a label, the
  folder and a port for each. The library the settings name (`library = ...`) is always on it,
  as the default. Adding a folder to the list only reads it (check()); taking it off the list
  never touches the folder. Nothing here changes which library is the default.
- **Test & Demo**: test_library/ in the tool's folder is the canonical copy, kept in git and
  never opened directly. Test & Demo mode opens a working copy of it (LOCAL_DIR /
  test-library-working), made on first use, kept across restarts, and replaced only by an
  explicit reset_test_library().

A library is portable: everything in it names its own files relative to its folder (the
catalog's `file` and `notes` columns), so the whole folder can be copied or moved anywhere. Its
identity is the `id` in its library.toml (libraries made since library ids were added have
one; an older one without it still works and is told apart by its folder). Two folders with
the same id are a library and its copy (or a moved one): never a reason to merge or overwrite
anything.

Each library is shown by its own server process (a server binds to one library when it
starts), on its own port: DEFAULT_PORT for the default library, TEST_PORT for Test & Demo,
the next free one in PORTS for the others. Before a server is started for a library, every
port in PORTS is checked for one already showing it, and a port showing another library is
never used for this one.
"""

import argparse
import hashlib
import os
import shutil
import socket
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

import catalog
import paths
import safe_io

REGISTRY = paths.LOCAL_DIR / "libraries.json"
LOGS = paths.LOCAL_DIR / "logs"
TEST_CANONICAL = paths.APP / paths.CANONICAL_TEST_LIBRARY
TEST_WORKING = paths.LOCAL_DIR / "test-library-working"
TEST_PREVIOUS = paths.LOCAL_DIR / "test-library-previous"  # the copy the last reset replaced

DEFAULT_PORT = 8765
TEST_PORT = 8766
PORTS = range(8765, 8865)  # where myLibrary servers are looked for and given ports
SERVER_NAME = "myLibrary"  # library_server.Handler.server_version
DOC_FOLDERS = ("books", "papers", "theses")


class LibraryError(ValueError):
    """Something the page or the launcher shows as it is (English, with Chinese where the
    UI shows it)."""


# --- a library's identity ------------------------------------------------------------------


def same_place(a, b) -> bool:
    """Whether two paths are the same folder on this computer (links followed, Windows'
    case-insensitivity respected)."""
    return _norm(a) == _norm(b)


def _norm(path) -> str:
    return os.path.normcase(str(safe_io.real_path(Path(path).expanduser())))


def _inside(path, folder) -> bool:
    path, folder = _norm(path), _norm(folder)
    return path == folder or path.startswith(folder.rstrip("\\/") + os.sep)


def info(library: Path) -> dict:
    """What library.toml says (read-only): {"name", "id" ("" if none or not a valid id),
    "test" (the Test & Demo library), "error" ("" or why it can't be read)}."""
    found = {"name": "", "id": "", "test": False, "error": ""}
    toml = Path(library) / "library.toml"
    if not safe_io.is_file(toml):
        return found
    try:
        data = tomllib.loads(safe_io.read_text(toml).lstrip("\ufeff"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
        return found | {"error": f"library.toml can't be read: {e}"}
    library_id = str(data.get("id") or "")
    try:
        library_id = str(uuid.UUID(library_id)) if library_id else ""
    except ValueError:
        library_id = ""
    return found | {
        "name": str(data.get("name") or ""),
        "id": library_id,
        "test": data.get("test_library") is True,
    }


def scope(library: Path) -> str:
    """A short key for this library in this place: its id and its folder. The browser keeps
    recovery drafts under it and backups are named with it, so neither ever turns up in
    another library, even one on the same port later or a copy with the same id."""
    text = f"{info(library)['id']}|{_norm(library)}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def is_test_library(library: Path) -> bool:
    """The Test & Demo library (its working copy, or the canonical one)."""
    return info(library)["test"] or _inside(library, TEST_CANONICAL)


# --- checking a folder, read-only ----------------------------------------------------------


def _internal(library: Path, real_root: str, value: str, what: str, where: str) -> str:
    """Why a catalog path isn't a safe path inside the library ("" if it is)."""
    if not value:
        return ""
    if (
        Path(value).is_absolute()
        or Path(value).drive
        or value.startswith(("/", "\\"))
        or ":" in value
    ):
        return f"{where}: {what} is a full path ({value}), not a place inside the library"
    if ".." in Path(value.replace("\\", "/")).parts:
        return f"{where}: {what} leads out of the library ({value})"
    target = Path(library) / value
    if safe_io.exists(target) and not _inside(target, real_root):
        return f"{where}: {what} is a link to a place outside the library ({value})"
    return ""


def check(folder) -> dict:
    """Look at a folder before it's added as a library, without writing anything.

    {"path", "ok" (it can be added), "errors" (why not), "warnings" (it can be added, but say
    these first), "name", "id", "test", "documents" {"book": n, ...}, "missing" [files]}.
    Errors: no such folder, not a library (neither library.toml nor catalog.csv), an
    old-format catalog (scripts/migrate_ids.py first), broken document ids. Warnings: missing
    PDFs or notes folders (an incomplete copy), paths that are absolute, lead out of the
    library or through a link out of it, an unfinished migration or rename, no library id."""
    path = Path(folder).expanduser()
    result = {"path": str(path), "ok": False, "errors": [], "warnings": [], "name": "",
              "id": "", "test": False, "documents": {}, "missing": []}  # fmt: skip
    errors, warnings = result["errors"], result["warnings"]
    if not str(folder).strip() or not path.is_absolute():
        errors.append("give the library's full folder path, e.g. D:\\Books\\My library")
        return result
    if not safe_io.exists(path):
        errors.append(f"no such folder: {path}")
        return result
    if not path.is_dir():
        errors.append(f"not a folder: {path}")
        return result
    about = info(path)
    result.update(name=about["name"], id=about["id"], test=is_test_library(path))
    if about["error"]:
        errors.append(about["error"])
    has_toml = safe_io.is_file(path / "library.toml")
    catalog_file = path / "catalog.csv"
    if not has_toml and not safe_io.is_file(catalog_file):
        errors.append(
            "this folder isn't a myLibrary library (it has neither library.toml nor "
            "catalog.csv). To start a new library there, use Create instead."
        )
        return result
    if result["test"]:
        errors.append("this is the Test & Demo library: open it with Test & Demo mode")
    real_root = _norm(path)
    if os.path.normcase(str(path.absolute())) != real_root:
        warnings.append(f"the folder is a link; its real place is {safe_io.real_path(path)}")
    if safe_io.is_file(catalog_file):
        try:
            header, rows = catalog.read_rows(catalog_file)
        except (OSError, UnicodeDecodeError) as e:
            errors.append(f"catalog.csv can't be read: {e}")
            rows, header = [], ["id"]
        if header and "id" not in header:
            errors.append(
                "catalog.csv is in the old format (documents without permanent ids): run "
                f'uv run scripts/migrate_ids.py --library "{path}" first'
            )
            rows = []
        errors += [f"catalog.csv {p}" for p in catalog.problems(rows)[:10]]
        for row in rows:
            where = row.get("slug") or row.get("id") or "a document"
            kind = row.get("type") or "book"
            result["documents"][kind] = result["documents"].get(kind, 0) + 1
            for column in ("file", "notes"):
                if problem := _internal(path, real_root, row.get(column) or "", column, where):
                    warnings.append(problem)
            file = row.get("file") or ""
            if file and not _internal(path, real_root, file, "file", where):
                if not safe_io.is_file(path / file):
                    result["missing"].append(file)
            notes = row.get("notes") or ""
            if notes and not _internal(path, real_root, notes, "notes", where):
                if not safe_io.exists(path / notes):
                    warnings.append(f"{where}: its notes folder {notes} is missing")
    if result["missing"]:
        shown = ", ".join(result["missing"][:5])
        more = f" and {len(result['missing']) - 5} more" if len(result["missing"]) > 5 else ""
        warnings.append(
            f"{len(result['missing'])} PDF(s) listed in the catalog aren't in the folder "
            f"({shown}{more}): an incomplete copy? Their notes are kept; copy the PDFs in later."
        )
    journals = path / ".myLibrary"
    for sub, what in (("migrations", "an id migration"), ("operations", "a rename")):
        folder_ = journals / sub
        if folder_.is_dir() and any(p.suffix == ".json" for p in folder_.rglob("*.json")):
            warnings.append(
                f"{what} was recorded in .myLibrary/{sub}; if it was left unfinished, the "
                "library's server finishes or rolls it back when it starts"
            )
    if has_toml and not about["id"] and not about["error"]:
        warnings.append(
            "this library has no library id yet (made before libraries had ids); it works the "
            "same and is told apart from its copies by its folder"
        )
    result["ok"] = not errors
    return result


# --- the list of personal libraries --------------------------------------------------------


def _registry() -> dict:
    data = safe_io.load_json(REGISTRY, {"libraries": []})
    if not isinstance(data, dict) or not isinstance(data.get("libraries"), list):
        raise LibraryError(f"{REGISTRY} isn't a list of libraries; fix or move it away")
    return data


def configured_library() -> Path | None:
    """The library the settings name: the default, opened by a plain library_server.py."""
    chosen = paths.load_settings().get("library")
    if not chosen:
        return None
    path = Path(chosen).expanduser()
    return (path if path.is_absolute() else paths.APP / path).resolve()


def _entry(raw: dict) -> dict:
    path = Path(raw.get("path") or "")
    entry = {
        "key": str(raw.get("key") or ""),
        "label": str(raw.get("label") or path.name),
        "path": str(path),
        "port": raw.get("port") if isinstance(raw.get("port"), int) else 0,
        "library_id": str(raw.get("library_id") or ""),
        "default": False,
        "available": path.is_absolute() and path.is_dir(),
        "problem": "",
    }
    if not entry["available"]:
        entry["problem"] = "the folder isn't there (moved, renamed, or on a drive not plugged in)"
    return entry


def personal() -> list[dict]:
    """Your personal libraries: the default one first, then the list's in its order. Each:
    {"key", "label", "path", "port", "library_id", "default", "available", "problem"}."""
    entries = [_entry(raw) for raw in _registry()["libraries"]]
    default = configured_library()
    if default is not None:
        for entry in entries:
            if entry["available"] and same_place(entry["path"], default):
                entry.update(default=True, port=DEFAULT_PORT)
                break
        else:
            entry = _entry({"key": "default", "path": str(default), "port": DEFAULT_PORT,
                            "label": info(default)["name"] or default.name})  # fmt: skip
            entry["default"] = True
            if entry["available"]:
                entry["library_id"] = info(default)["id"]
            entries.insert(0, entry)
    entries.sort(key=lambda e: not e["default"])
    return entries


def find(key: str) -> dict:
    for entry in personal():
        if entry["key"] == key:
            return entry
    raise LibraryError("that library isn't on the list any more; reload the list")


def _free_port(taken: set[int]) -> int:
    for port in PORTS:
        if port not in taken and port not in (DEFAULT_PORT, TEST_PORT) and port_free(port):
            return port
    raise LibraryError(f"no free port between {PORTS.start} and {PORTS.stop - 1}")


def _assigned() -> set[int]:
    return {e["port"] for e in _registry()["libraries"] if isinstance(e.get("port"), int)}


def register(folder, label: str = "") -> dict:
    """Put an existing library on the list. Only reads the folder (check()); refuses one with
    errors, the Test & Demo library, and a folder already on the list. A folder with the same
    library id as one on the list is a copy or a moved library: it's added as a library of its
    own (relocate() is for a moved one), never merged. Returns the new entry with the
    check's warnings."""
    report = check(folder)
    if not report["ok"]:
        raise LibraryError("; ".join(report["errors"]))
    path = Path(folder).expanduser()
    if _inside(path, paths.LOCAL_DIR) or _inside(path, TEST_CANONICAL):
        raise LibraryError("this folder belongs to the tool (Test & Demo), not a personal library")
    for entry in personal():
        if entry["available"] and same_place(entry["path"], path):
            raise LibraryError(f"this folder is already on the list, as “{entry['label']}”")
    raw = {
        "key": str(uuid.uuid4()),
        "label": " ".join(label.split())[:80] or report["name"] or path.name,
        "path": str(path),
        "library_id": report["id"],
        "added": datetime.now().isoformat(timespec="seconds"),
    }

    def add(data: dict) -> None:
        taken = {e.get("port") for e in data["libraries"]}
        raw["port"] = _free_port(taken)
        data["libraries"].append(raw)

    _change(add)
    entry = _entry(raw)
    entry["warnings"] = report["warnings"]
    entry["same_id"] = [
        e["label"] for e in personal()
        if report["id"] and e["library_id"] == report["id"] and e["key"] != raw["key"]
    ]  # fmt: skip
    return entry


def create(folder, label: str = "") -> dict:
    """Make a new, empty library in a folder that doesn't exist yet or is empty, and put it on
    the list. Never makes a library inside another library or inside the tool."""
    path = Path(folder).expanduser()
    if not path.is_absolute():
        raise LibraryError("give the new library's full folder path, e.g. D:\\Books\\Physics")
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise LibraryError(
            "that folder isn't empty: choose a new or empty folder (to use an existing "
            "library, use Add existing instead)"
        )
    for parent in [path, *path.parents]:
        if safe_io.is_file(parent / "library.toml") or safe_io.is_file(parent / "catalog.csv"):
            raise LibraryError(f"that folder is inside the library {parent}")
    if _inside(path, paths.APP) or _inside(path, paths.LOCAL_DIR):
        raise LibraryError("choose a folder outside the tool's own folders")
    paths.ensure_library(path)
    if label:
        name = " ".join(label.split())[:80].replace("\\", "").replace('"', "'")
        safe_io.update_text(
            path / "library.toml",
            lambda text: text.replace('name = "My library"', f'name = "{name}"', 1),
        )
    return register(path, label)


def _change(change) -> object:
    """Change the list under its lock, keeping the previous version (.bak)."""

    def checked(data: dict):
        if not isinstance(data.get("libraries"), list):
            raise LibraryError(f"{REGISTRY} isn't a list of libraries; fix or move it away")
        return change(data)

    return safe_io.update_json(
        REGISTRY, checked, {"libraries": []}, backup=True, ensure_ascii=False, indent=2
    )


def _raw_index(data: dict, key: str) -> int:
    for i, raw in enumerate(data["libraries"]):
        if raw.get("key") == key:
            return i
    raise LibraryError("that library isn't on the list any more; reload the list")


def rename(key: str, label: str) -> dict:
    """Change a library's label on the list (never its folder or its library.toml). The
    default library, if not on the list yet, is added to it to keep the label."""
    label = " ".join(str(label).split())[:80]
    if not label:
        raise LibraryError("the label can't be empty")
    entry = find(key)

    def change(data: dict) -> None:
        if key == "default":
            added = datetime.now().isoformat(timespec="seconds")
            raw = {"key": str(uuid.uuid4()), "label": label, "path": entry["path"]}
            raw |= {"port": DEFAULT_PORT, "library_id": entry["library_id"], "added": added}
            data["libraries"].insert(0, raw)
        else:
            data["libraries"][_raw_index(data, key)]["label"] = label

    _change(change)
    return next(e for e in personal() if same_place(e["path"], entry["path"]))


def unregister(key: str) -> dict:
    """Take a library off the list. The folder and everything in it stay as they are. The
    default library (the settings' one) can't be taken off: change the default in Settings."""
    entry = find(key)
    if entry["default"]:
        raise LibraryError("this is the default library (⚙ Settings); it stays on the list")
    _change(lambda data: data["libraries"].pop(_raw_index(data, key)))
    return entry


def relocate(key: str, folder) -> dict:
    """A library on the list was moved: point its entry at the new folder (label and port kept).
    The new folder is checked first (read-only) and must have the same library id, when the
    entry has one."""
    entry = find(key)
    if entry["default"]:
        raise LibraryError("the default library is moved in ⚙ Settings (Library folder)")
    report = check(folder)
    if not report["ok"]:
        raise LibraryError("; ".join(report["errors"]))
    if entry["library_id"] and report["id"] != entry["library_id"]:
        raise LibraryError(
            "that folder is a different library (its library id differs); add it as a new one"
        )
    for other in personal():
        if other["key"] != key and other["available"] and same_place(other["path"], folder):
            raise LibraryError(f"that folder is already on the list, as “{other['label']}”")

    def change(data: dict) -> None:
        data["libraries"][_raw_index(data, key)]["path"] = str(Path(folder).expanduser())

    _change(change)
    return find(key) | {"warnings": report["warnings"]}


# --- the Test & Demo library ---------------------------------------------------------------


def test_library() -> Path:
    """The Test & Demo working copy, made from test_library/ the first time (later starts keep
    what you changed in it)."""
    if safe_io.is_file(TEST_WORKING / "library.toml"):
        if not info(TEST_WORKING)["test"]:
            raise LibraryError(f"{TEST_WORKING} isn't the Test & Demo library; move it away")
        return TEST_WORKING
    if not safe_io.is_file(TEST_CANONICAL / "library.toml"):
        raise LibraryError("the Test & Demo library (test_library/) isn't in this copy of the tool")
    if TEST_WORKING.exists() and any(TEST_WORKING.iterdir()):
        raise LibraryError(f"{TEST_WORKING} has files but no library.toml; move it away first")
    with safe_io.critical():
        part = TEST_WORKING.with_name(TEST_WORKING.name + ".part")
        if part.exists():  # a copy cut off before: ours, never anything else
            if not _inside(part, paths.LOCAL_DIR):
                raise LibraryError(f"unexpected {part}")
            shutil.rmtree(part)
        shutil.copytree(TEST_CANONICAL, part)
        if TEST_WORKING.exists():
            TEST_WORKING.rmdir()  # (empty: checked above)
        part.rename(TEST_WORKING)
    return TEST_WORKING


def reset_test_library() -> Path:
    """Replace the Test & Demo working copy with a fresh copy of test_library/. Refused while a
    server shows it. Only ever touches TEST_WORKING (checked to be the Test & Demo library) and
    TEST_PREVIOUS: the replaced copy is kept there until the next reset."""
    if safe_io.exists(TEST_WORKING):
        if not safe_io.is_file(TEST_WORKING / "library.toml") or not info(TEST_WORKING)["test"]:
            raise LibraryError(f"{TEST_WORKING} isn't the Test & Demo library; nothing was reset")
        if port := find_server(TEST_WORKING):
            raise LibraryError(
                f"the Test & Demo library is open (port {port}): Quit it from its page first"
            )
        with safe_io.critical():
            if TEST_PREVIOUS.exists():
                if not info(TEST_PREVIOUS)["test"]:
                    raise LibraryError(f"{TEST_PREVIOUS} isn't an old Test & Demo copy")
                shutil.rmtree(TEST_PREVIOUS)
            TEST_WORKING.rename(TEST_PREVIOUS)
    return test_library()


# --- servers -------------------------------------------------------------------------------


def port_free(port: int) -> bool:
    """Nothing listens on 127.0.0.1:port (binding is instant; connecting to a closed port
    takes Windows about two seconds)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if sys.platform == "win32":
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def server_at(port: int) -> str | None:
    """The library folder of the myLibrary server on this port ("" if it doesn't say), or None
    when no myLibrary server answers there."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/whoami", timeout=3) as r:
            headers = r.headers
    except urllib.error.HTTPError as e:  # (an older server: no /api/whoami, still the header)
        headers = e.headers
    except OSError:
        return None
    if not (headers.get("Server") or "").startswith(SERVER_NAME):
        return None
    return unquote(headers.get("X-myLibrary-Library") or "")


def find_server(library: Path, ports=PORTS, skip: int | None = None) -> int | None:
    """The port of a server already showing this library, if any: the port its server noted
    in the library (any port, e.g. --port 9000), then every port in PORTS. A port only counts
    when the server there says it shows this very library."""
    noted = safe_io.load_json(Path(library) / ".myLibrary" / SERVED_NAME, {}, cache=True)
    first = (
        [noted["port"]] if isinstance(noted, dict) and isinstance(noted.get("port"), int) else []
    )
    for port in [*first, *ports]:
        if port == skip or not 0 < port < 65536 or port_free(port):
            continue
        shown = server_at(port)
        if shown and same_place(shown, library):
            return port
    return None


# --- one server per library (L15) ---------------------------------------------------------
#
# A server holds its library's lock (.myLibrary/server.lock, an operating-system lock on an
# empty file) from before it touches anything until its process ends: a second server for the
# same library, started at the same moment from another launcher, tab or terminal, can't take
# it and opens the first one instead. The system releases the lock with the process, however
# it ends (Quit, a crash, Task Manager), so a lock is never left behind; the file itself is
# just a marker. .myLibrary/server.json notes the holder's port, so it's found on any port.

LOCK_NAME = "server.lock"
SERVED_NAME = "server.json"


def hold_library(library: Path):
    """Take the library's server lock: an open file to keep for as long as the server runs,
    or None when another process holds it."""
    folder = Path(library) / ".myLibrary"
    folder.mkdir(parents=True, exist_ok=True)
    handle = open(folder / LOCK_NAME, "a+b")  # (never truncated: it stays an empty marker)
    try:
        if sys.platform == "win32":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def note_port(library: Path, port: int) -> None:
    """The lock holder's port, for find_server (a hint: always checked against the server)."""
    safe_io.write_json(
        Path(library) / ".myLibrary" / SERVED_NAME, {"port": port, "pid": os.getpid()}
    )


def hold_or_find(library: Path, wait: float = 60):
    """(lock, None) once this process holds the library's lock; (None, port) once another
    server shows the library (its holder may still be starting); (None, None) if neither
    happens within `wait` seconds. The lock is tried again all along: a holder that ends
    (e.g. a start that lost its port) lets go of it."""
    deadline = time.monotonic() + wait
    while True:
        if (lock := hold_library(library)) is not None:
            return lock, None
        if port := find_server(library):
            return None, port
        if time.monotonic() > deadline:
            return None, None
        time.sleep(0.5)


SERVER_ARGS: list[str] = []  # more arguments for the servers started (tests: --no-download)


class PortTaken(LibraryError):
    """The server couldn't use its port (another program or library took it meanwhile)."""


def start_server(library: Path, port: int, wait: float = 90) -> int:
    """Start library_server.py for this library on this port, on its own (it keeps running
    after the launcher ends) and wait until a server shows this library: the port it answers
    on. That's another port when a server of this library started meanwhile (the new process
    then gives way to it: the library's lock). Output goes to LOGS/server-<port>.log."""
    LOGS.mkdir(parents=True, exist_ok=True)
    log_path = LOGS / f"server-{port}.log"
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    script = paths.APP / "scripts" / "library_server.py"
    with open(log_path, "ab") as log:  # (a log, appended to: not the user's data)
        process = subprocess.Popen(
            [sys.executable, str(script), "--library", str(library), "--port", str(port),
             "--no-browser", *SERVER_ARGS],
            stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            cwd=paths.APP, creationflags=flags, close_fds=True,
        )  # fmt: skip
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        shown = server_at(port)
        if shown is not None:
            if shown and same_place(shown, library):
                return port
            # Our process can't get this port: wait until it has ended (and let go of the
            # library's lock) before another port is tried, never cutting off its start-up
            try:
                process.wait(wait)
            except subprocess.TimeoutExpired:
                raise LibraryError(f"port {port} shows another library, and the server started "
                                   f"for this one doesn't end ({log_path})") from None  # fmt: skip
            raise PortTaken(f"port {port} shows another library ({shown or 'unknown'})")
        if process.poll() is not None:
            if running := find_server(library):  # gave way to this library's own server
                return running
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-600:].strip()
            if not port_free(port):
                raise PortTaken(f"port {port} was taken meanwhile:\n{tail}")
            raise LibraryError(f"the library's server stopped at start:\n{tail}")
        time.sleep(0.25)
    raise LibraryError(f"the library's server didn't answer within {wait:.0f} s ({log_path})")


def open_library(library: Path, port: int, key: str = "") -> str:
    """The address of a server showing this library: one already running (on any port), else
    a new one on `port`, or on another free port if that one is taken (then remembered for the
    entry `key`). Never a server of another library; never two servers of this one (the
    library's lock decides between launches at the same moment)."""
    if not Path(library).is_dir():
        raise LibraryError(f"the library's folder isn't there: {library}")
    if running := find_server(library):
        return f"http://127.0.0.1:{running}/"
    tried: set[int] = set()
    for _ in range(3):
        if port in tried or not port_free(port):
            shown = server_at(port)
            if shown and same_place(shown, library):
                return f"http://127.0.0.1:{port}/"
            if port in (DEFAULT_PORT, TEST_PORT) and shown is None and not tried:
                raise LibraryError(
                    f"port {port} is used by another program; close it and try again"
                )
            port = _free_port(_assigned() | tried | {port})
            if key and key != "default":

                def remember(data: dict, port=port) -> None:
                    data["libraries"][_raw_index(data, key)]["port"] = port

                _change(remember)
        tried.add(port)
        try:
            return f"http://127.0.0.1:{start_server(Path(library), port)}/"
        except PortTaken:
            continue
    raise LibraryError(f"no port could be used for this library (tried {sorted(tried)})")


def open_personal(key: str) -> str:
    entry = find(key)
    if not entry["available"]:
        raise LibraryError(f"“{entry['label']}”: {entry['problem']} ({entry['path']})")
    report = check(entry["path"])
    if not report["ok"]:
        raise LibraryError(f"“{entry['label']}” can't be opened: " + "; ".join(report["errors"]))
    if entry["library_id"] and report["id"] and report["id"] != entry["library_id"]:
        raise LibraryError(
            f"the folder of “{entry['label']}” now holds a different library (another library "
            "id): take it off the list and add the folder again if that's right"
        )
    return open_library(Path(entry["path"]), entry["port"] or DEFAULT_PORT, entry["key"])


def open_test() -> str:
    return open_library(test_library(), TEST_PORT)


def current(library: Path) -> dict:
    """What a server tells its page about the library it shows: {"mode": "test" | "personal",
    "label", "path", "key" (its entry on the list, "" if none)}."""
    if is_test_library(library):
        return {"mode": "test", "label": "Test & Demo", "path": str(library), "key": ""}
    for entry in personal():
        if entry["available"] and same_place(entry["path"], library):
            return {"mode": "personal", "label": entry["label"], "path": str(library),
                    "key": entry["key"]}  # fmt: skip
    return {"mode": "personal", "label": info(library)["name"] or Path(library).name,
            "path": str(library), "key": ""}  # fmt: skip


def main() -> None:
    parser = argparse.ArgumentParser(description="Your libraries on this computer")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="the personal libraries")
    p = sub.add_parser("check", help="check a folder before adding it (read-only)")
    p.add_argument("folder")
    sub.add_parser("reset-test", help="replace the Test & Demo working copy with a fresh one")
    args = parser.parse_args()
    if args.command == "list":
        for e in personal():
            mark = "*" if e["default"] else " "
            state = "" if e["available"] else f"  ({e['problem']})"
            print(f"{mark} {e['label']}  {e['path']}  port {e['port']}{state}")
    elif args.command == "check":
        report = check(args.folder)
        print("OK" if report["ok"] else "Can't be added")
        for line in report["errors"]:
            print(f"  error: {line}")
        for line in report["warnings"]:
            print(f"  note: {line}")
    elif args.command == "reset-test":
        answer = input(f"Replace the Test & Demo library at {TEST_WORKING}? Type RESET: ")
        if answer.strip() != "RESET":
            print("Nothing was reset.")
            return
        print(f"Fresh copy: {reset_test_library()} (previous one in {TEST_PREVIOUS})")


if __name__ == "__main__":
    main()
