"""Where the tool is (APP) and where the library is (LIBRARY).

The tool (this repository's scripts/) works on one library: a folder with your books, notes,
glossaries and chapter scripts. Which library, in this order:

  1. --library <folder> on the command line (any script)
  2. the MYLIBRARY_LIBRARY environment variable
  3. local.toml in the tool's folder (not in git):   library = "library"
  4. otherwise a new library in Documents/myLibrary Library, created on first start
     (ensure_library(), called by library_server.py and add_book.py) and remembered in
     local.toml

A relative path in local.toml or --library is relative to the tool's folder.
"""

import os
import sys
import tomllib
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
LOCAL_SETTINGS = APP / "local.toml"
DEFAULT_LIBRARY = Path.home() / "Documents" / "myLibrary Library"
ENV_VAR = "MYLIBRARY_LIBRARY"


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
    elif LOCAL_SETTINGS.exists():
        with open(LOCAL_SETTINGS, "rb") as f:
            chosen = tomllib.load(f).get("library")
        source = "local.toml"
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
# "shelves", e.g. "Optics; Lasers"). Give a shelf a label to show on the library page,
# Chinese with its English translation, e.g.:
#
# [shelves]
# Optics = "光学 Optics"
"""


def ensure_library(library: Path | None = None) -> Path:
    """Create the library's folders if they're missing; a library chosen by default is
    remembered in local.toml so the next start uses the same one."""
    library = library or LIBRARY
    for sub in ("books", "notes/topics", "glossaries", "examples"):
        (library / sub).mkdir(parents=True, exist_ok=True)
    if not (library / "library.toml").exists():
        (library / "library.toml").write_text(LIBRARY_TOML, encoding="utf-8")
    if library == LIBRARY and LIBRARY_SOURCE == "default" and not LOCAL_SETTINGS.exists():
        LOCAL_SETTINGS.write_text(
            "# Which library the tool opens (see scripts/paths.py)\n"
            f"library = {str(library.as_posix())!r}\n",
            encoding="utf-8",
        )
        print(f"New library created: {library}")
    return library


# The VS Code window notes and scripts open in: the whole project when the library is inside
# the tool's folder (as for the author's library/), else the library folder itself
WORKSPACE = APP if LIBRARY.is_relative_to(APP) else LIBRARY
