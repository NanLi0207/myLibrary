"""Where the tool is (APP), where the library is (LIBRARY), and the user's settings.

The tool (this repository's scripts/) works on one library: a folder with your books, notes,
glossaries and chapter scripts. Which library, in this order:

  1. --library <folder> on the command line (any script)
  2. the MYLIBRARY_LIBRARY environment variable
  3. `library` in the settings file:   library = "library"
  4. otherwise a new library in Documents/myLibrary Library, created on first start
     (ensure_library(), called by library_server.py and add_book.py) and remembered there

The settings file is local.toml in the tool's folder (not in git), or, in the ready-to-use
package (a package.toml next to scripts/), %APPDATA%/myLibrary/settings.toml, so a new version
of the package keeps them. Besides the library, it holds which editor opens notes and whether
the Python features (chapter scripts) are shown; see SETTINGS_DEFAULTS.
A relative library path is relative to the tool's folder.
"""

import os
import shutil
import sys
import tomllib
from pathlib import Path

import safe_io

APP = Path(__file__).resolve().parent.parent
IS_PACKAGE = (APP / "package.toml").exists()
if IS_PACKAGE:
    SETTINGS_FILE = Path(os.environ.get("APPDATA") or Path.home()) / "myLibrary" / "settings.toml"
else:
    SETTINGS_FILE = APP / "local.toml"
DEFAULT_LIBRARY = Path.home() / "Documents" / "myLibrary Library"
ENV_VAR = "MYLIBRARY_LIBRARY"

EDITORS = ("vscode", "notepad", "system", "custom")
SETTINGS_DEFAULTS = {
    # Which program opens notes: VS Code, Notepad, the file's default app ("system", e.g.
    # Typora), or your own command with {file} in it ("custom")
    "editor": "vscode" if shutil.which("code") else "system",
    "editor_command": "",
    # Chapter scripts (checking a book's examples in Python); off in the ready-to-use package
    "python_features": not IS_PACKAGE,
    # Your own free OpenAlex key (subjects, 🔎 Find online): without one, OpenAlex shares a
    # small daily budget among everyone on your network. Free:
    # https://openalex.org/settings/api-key
    "openalex_key": "",
    # 💾 Back up (folder_backup.py): a dated zip of your notes, progress and the rest in this
    # folder (e.g. on OneDrive or a USB stick), and with backup_pdfs a copy of the PDFs next
    # to it (on in the package, where nothing else keeps the books safe)
    "backup_folder": "",
    "backup_pdfs": IS_PACKAGE,
}


def _saved() -> dict:
    """What the settings file holds ({} without one)."""
    if not SETTINGS_FILE.exists():
        return {}
    with open(SETTINGS_FILE, "rb") as f:
        try:
            return tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            # Never fall back to the defaults: that would open (and create) another library,
            # and the next save would write over your other settings
            raise SystemExit(
                f"The settings file {SETTINGS_FILE} can't be read ({e}). Fix that line in a text "
                "editor (or delete the file to start with the default settings)."
            ) from None


def load_settings() -> dict:
    """The settings file merged over the defaults."""
    return SETTINGS_DEFAULTS | _saved()


_TOML_ESCAPES = {"\\": "\\\\", '"': '\\"', "\b": "\\b", "\t": "\\t", "\n": "\\n", "\f": "\\f",
                 "\r": "\\r"}  # fmt: skip


def _toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    control = any(ord(c) < 0x20 or ord(c) == 0x7F for c in text)
    if "'" not in text and not control:
        return f"'{text}'"  # literal string: backslashes in Windows paths stay as they are
    # Basic string: every character a TOML reader would refuse is escaped, so the settings file
    # always stays readable (an unreadable one would stop every script)
    escaped = "".join(
        _TOML_ESCAPES.get(c) or (f"\\u{ord(c):04X}" if ord(c) < 0x20 or ord(c) == 0x7F else c)
        for c in text
    )
    return f'"{escaped}"'


def save_settings(updates: dict) -> dict:
    """Change some settings (only known keys); returns all of them."""
    unknown = set(updates) - set(SETTINGS_DEFAULTS) - {"library"}
    if unknown:
        raise ValueError(f"unknown settings: {', '.join(sorted(unknown))}")
    if "editor" in updates and updates["editor"] not in EDITORS:
        raise ValueError(f"editor must be one of {', '.join(EDITORS)}")
    saved = _saved() | updates
    lines = ["# myLibrary settings (see scripts/paths.py)"]
    lines += [f"{key} = {_toml_value(value)}" for key, value in saved.items()]
    safe_io.write_text(SETTINGS_FILE, "\n".join(lines) + "\n")
    return SETTINGS_DEFAULTS | saved


def _from_argv(argv: list[str]) -> str | None:
    for i, arg in enumerate(argv):
        if arg == "--library" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--library="):
            return arg.split("=", 1)[1]
    return None


def _resolve(argv: list[str]) -> tuple[Path, str]:
    """(library folder, where that choice came from)."""
    if chosen := _from_argv(argv):
        source = "--library"
    elif chosen := os.environ.get(ENV_VAR):
        source = ENV_VAR
    else:
        chosen = load_settings().get("library")
        source = SETTINGS_FILE.name
    if not chosen:
        return DEFAULT_LIBRARY, "default"
    path = Path(chosen).expanduser()
    return (path if path.is_absolute() else APP / path).resolve(), source


LIBRARY, LIBRARY_SOURCE = _resolve(sys.argv[1:])


def add_argument(parser) -> None:
    """--library for a script's argparse (the value itself is read above, at import)."""
    parser.add_argument(
        "--library",
        metavar="FOLDER",
        help=f"the library to use (now: {display(LIBRARY)}, from {LIBRARY_SOURCE})",
    )


def display(path: Path) -> str:
    """A path for messages: relative to the tool's folder when inside it."""
    try:
        return path.resolve().relative_to(APP).as_posix()
    except ValueError:
        return path.resolve().as_posix()


LIBRARY_TOML = """# This library's settings.
name = "My library"

# Shelves group your books by subject; a book can be on several (catalog.csv, column
# "shelves"). Each new item is put on its subject's shelf (from OpenAlex), and you can add
# your own with the Shelves button. Give a shelf a label to show on the library page,
# Chinese with its English translation, e.g.:
#
# [shelves]
# "Advanced optical system design" = "先进光学系统设计 Advanced optical system design"
"""


def ensure_library(library: Path | None = None) -> Path:
    """Create the library's folders if they're missing; a library chosen by default is
    remembered in the settings file so the next start uses the same one."""
    library = library or LIBRARY
    for sub in ("books", "papers", "theses", "notes/topics", "glossaries", "examples"):
        (library / sub).mkdir(parents=True, exist_ok=True)
    if not (library / "library.toml").exists():
        (library / "library.toml").write_text(LIBRARY_TOML, encoding="utf-8")
    if library == LIBRARY and LIBRARY_SOURCE == "default" and "library" not in _saved():
        save_settings({"library": library.as_posix()})
        print(f"New library created: {library}")
    return library


# The VS Code window notes and scripts open in: the whole project when the library is inside
# the tool's folder (as for the author's library/), else the library folder itself
WORKSPACE = APP if LIBRARY.is_relative_to(APP) else LIBRARY
