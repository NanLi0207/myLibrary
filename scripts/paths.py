"""Where the tool is (APP), where the library is (LIBRARY), and the user's settings.

The tool (this repository's scripts/) works on one library: a folder with your books, notes,
glossaries and chapter scripts. Which library, in this order:

  1. --library <folder> on the command line (any script)
  2. the MYLIBRARY_LIBRARY environment variable
  3. `library` in the settings file:   library = "library"
  4. otherwise a new library in Documents/myLibrary Library, created on first start
     (ensure_library(), called by library_server.py and add_book.py) and remembered there

The settings file is local.toml in the tool's folder (not in git), or, in the ready-to-use
package (a package.toml next to scripts/), %APPDATA%/myLibrary/settings.toml on Windows
(platform_services.user_data_dir), so a new version of the package keeps them. Besides the
library, it holds which editor opens notes and whether the Python features (chapter scripts)
are shown; see SETTINGS_DEFAULTS. The MYLIBRARY_SETTINGS environment variable names another
settings file instead (the browser tests use a temporary one, so they never read or change the
real settings).
A relative library path is relative to the tool's folder.
"""

import os
import re
import shutil
import stat
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import platform_services
import safe_io
import settings_toml

APP = Path(__file__).resolve().parent.parent
IS_PACKAGE = (APP / "package.toml").exists()
ENV_VAR = "MYLIBRARY_LIBRARY"
SETTINGS_VAR = "MYLIBRARY_SETTINGS"


class SettingsUnreadable(OSError):
    """The settings file couldn't be read (still blocked after the retries, or another
    operating-system error). Never taken for "no settings" (M7.1 S3, B44)."""


class SettingsDanglingAlias(SettingsUnreadable):
    """A link (symbolic link or junction) on the way to the settings file leads nowhere."""


class SettingsMissing(SettingsUnreadable):
    """The settings file named by MYLIBRARY_SETTINGS isn't there (any more). Only the usual
    settings file may be missing (a first start); a chosen one never becomes "no settings"."""


class SettingsBusy(ValueError):
    """The settings are being saved elsewhere (another window, another myLibrary): not obtained
    within SETTINGS_LOCK_WAIT. Nothing was changed; trying again later works."""


class SettingsMoved(SettingsBusy):
    """The settings file (or its lock) changed while this save waited for it."""


class SettingsBlocked(ValueError):
    """The new settings file couldn't replace the old one because the file was in use (D3,
    confirmed by platform_services.windows_file_in_use). Nothing was changed; retry."""


class SettingsSaveFailed(OSError):
    """Saving failed for another reason (creating or writing the new file, a replacement that
    wasn't confirmed to be blocked by use, cleaning up); its message says what the settings file
    holds now."""


SettingsDamaged = settings_toml.SettingsDamaged
SettingsNotWritable = settings_toml.SettingsNotWritable

_SOURCE_DEFAULT, _SOURCE_EXPLICIT = "default", "explicit"
_RESERVED_FOLDER = ".myLibrary-local"  # this computer's own records; holds the settings lock


def _refuse_reserved(path: Path) -> None:
    """No settings file inside .myLibrary-local or named *.lock: it could take the place of a
    settings lock marker (whose replacement would orphan the lock another process holds)."""
    if path.parent.name.lower() == _RESERVED_FOLDER.lower() or path.name.lower().endswith(".lock"):
        raise SettingsNotWritable(
            f"{path.name} in {path.parent.name} can't be a settings file: that place is kept "
            "for myLibrary's own lock files. Choose a settings file elsewhere."
        )


class SettingsPathAmbiguous(SettingsNotWritable):
    """(Windows) A settings path with a name Windows' ordinary path form changes: a trailing dot
    or space, a device name, a stream (:), "." or "..". Through \\\\?\\ such a path names one
    file and in the ordinary form another (S3 round 1: "settings.toml." read, "settings.toml"
    written). Refused before anything is read, locked or written; nothing is renamed."""


_WINDOWS_DEVICES = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} | {
    f"{port}{n}" for port in ("COM", "LPT") for n in (*"123456789", "¹", "²", "³")
}
_NOT_IN_WINDOWS_NAMES = set('<>:"|?*') | {chr(c) for c in range(32)}


def _windows_name_problem(name: str) -> str:
    if name in (".", ".."):
        return 'is "." or ".."'
    if name.endswith((".", " ")):
        return "ends in a dot or a space, which Windows' ordinary path form drops"
    if _NOT_IN_WINDOWS_NAMES & set(name):
        return "has a character Windows doesn't allow in names (or a stream, :)"
    if name.split(".")[0].rstrip(" ").upper() in _WINDOWS_DEVICES:
        return "is a name Windows keeps for a device"
    return ""


def _refuse_ambiguous_path(path) -> None:
    """Windows only: refuse a settings path that could name one file through \\\\?\\ and
    another in the ordinary form (SettingsPathAmbiguous). 8.3 short names, junctions and links
    are fine: they reach the same file, which _follow_existing checks by its identity."""
    if os.name != "nt":
        return
    text = os.fspath(path)
    for prefix in ("\\\\?\\UNC\\", "//?/UNC/", "\\\\?\\", "//?/"):
        if text.startswith(prefix):
            text = ("\\\\" if "UNC" in prefix else "") + text[len(prefix) :]
            break
    plain = Path(text)
    for part in plain.parts[1:] if plain.anchor else plain.parts:
        if problem := _windows_name_problem(part):
            raise SettingsPathAmbiguous(
                f"The settings path {path} has a name, {part!r}, that {problem}: Windows could "
                "take it for another file. Rename it (or choose another settings file); "
                "nothing was changed."
            )


def _dangling_on_the_way(path: Path) -> bool:
    """Whether a folder on the way to `path` is a link whose target is missing (a missing
    folder itself is fine: nothing is there)."""
    for folder in path.parents:
        try:
            os.lstat(safe_io._os_path(folder))
        except FileNotFoundError:
            continue
        except OSError:
            return False  # (reported by the read itself)
        return not os.path.exists(safe_io._os_path(folder))
    return False


def _missing_message(path: Path) -> str:
    return (
        f"{SETTINGS_VAR} names a settings file that doesn't exist: {path}\n"
        f"Create it (it may be empty), or unset {SETTINGS_VAR} to use the usual settings."
    )


def _probe_settings(path: Path, source: str) -> bytes | None:
    """The settings file's bytes; None only when it's confirmed absent and may be (the usual
    settings file, source "default"). One policy for the start and every later read (B44):
    sharing failures are retried (safe_io.read_bytes); a folder, a dangling link, retries
    exhausted and other errors raise; absence is confirmed by a second look. A path Windows
    could read as another file is refused first (SettingsPathAmbiguous)."""
    _refuse_ambiguous_path(path)
    for attempt in (1, 2):
        if os.path.isdir(safe_io._os_path(path)):
            if source == _SOURCE_EXPLICIT:
                raise SettingsMissing(_missing_message(path))
            raise SettingsUnreadable(f"The settings file {path} is a folder, not a file.")
        try:
            return safe_io.read_bytes(path)
        except FileNotFoundError:
            try:
                os.lstat(safe_io._os_path(path))
            except FileNotFoundError:
                if _dangling_on_the_way(path):
                    raise SettingsDanglingAlias(
                        f"A folder on the way to the settings file {path} is a link whose "
                        "target is missing."
                    ) from None
                if attempt == 1:
                    time.sleep(0.05)  # (a file being swapped in: look once more)
                    continue
                if source == _SOURCE_EXPLICIT:
                    raise SettingsMissing(_missing_message(path)) from None
                return None
            except OSError as e:
                raise SettingsUnreadable(f"The settings file {path} can't be read: {e}") from None
            raise SettingsDanglingAlias(
                f"The settings file {path} is a link whose target is missing."
            ) from None
        except PermissionError:  # (still refused after safe_io's retries; its text guesses why)
            raise SettingsUnreadable(
                f"The settings file {path} couldn't be read (access was refused on every try). "
                "Try again in a moment."
            ) from None
        except OSError as e:
            raise SettingsUnreadable(f"The settings file {path} can't be read: {e}") from None
    raise AssertionError("unreachable")


def _settings_file(is_package: bool | None = None, platform: str | None = None) -> Path:
    """The settings file: MYLIBRARY_SETTINGS if set (tests, a desktop wrapper), else in the
    package settings.toml in this computer's user-data folder (Windows: %APPDATA%/myLibrary;
    a future macOS package: ~/Library/Application Support/myLibrary; see
    platform_services.user_data_dir), else local.toml in the tool's folder (development).
    A file named by MYLIBRARY_SETTINGS must exist: falling back to the usual settings would
    open the usual library and write there. It is read here with the same retries as every
    read, and refused in the place kept for lock files."""
    if chosen := os.environ.get(SETTINGS_VAR):
        try:
            _refuse_ambiguous_path(chosen)  # (before resolve() can drop what Windows would)
        except SettingsNotWritable as e:
            raise SystemExit(str(e)) from None
        path = Path(chosen).expanduser().resolve()
        try:
            _refuse_reserved(path)
            _probe_settings(path, _SOURCE_EXPLICIT)
        except (SettingsUnreadable, SettingsNotWritable) as e:
            raise SystemExit(str(e)) from None
        return path
    if IS_PACKAGE if is_package is None else is_package:
        return platform_services.user_data_dir(platform) / "settings.toml"
    return APP / "local.toml"


SETTINGS_FILE = _settings_file()
# Where SETTINGS_FILE came from, fixed for the whole process: only the usual ("default") file
# may be missing (a first start); a file chosen with MYLIBRARY_SETTINGS ("explicit") that
# disappears is an error at every later read, never "no settings" (M7.1 S3)
SETTINGS_SOURCE = _SOURCE_EXPLICIT if os.environ.get(SETTINGS_VAR) else _SOURCE_DEFAULT
DEFAULT_LIBRARY = Path.home() / "Documents" / "myLibrary Library"

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
# Each setting's one accepted type: a value of another type is refused, never converted
# ("false" is not False, 1 is not True), when saving and when found in the file (D4)
SETTINGS_TYPES = {"library": str} | {k: type(v) for k, v in SETTINGS_DEFAULTS.items()}


def _saved() -> dict:
    """What the settings file holds ({} only for a usual settings file that isn't there yet).
    Typed errors otherwise (SettingsUnreadable and its kinds, SettingsDamaged): never {} for a
    file that couldn't be read, so another library is never opened by mistake and the page
    never shows defaults for settings it couldn't read."""
    data = _probe_settings(SETTINGS_FILE, SETTINGS_SOURCE)
    if data is None:
        return {}
    return settings_toml.parse(data, SETTINGS_FILE.name)


def load_settings() -> dict:
    """The settings file merged over the defaults."""
    return SETTINGS_DEFAULTS | _saved()


_toml_value = settings_toml.value_text  # (the way values have always been written)


def _check_updates(updates) -> None:
    """Every setting known, of its one type, the editor one of EDITORS, the library not blank.
    Checked whoever asks (the page, ensure_library, a script)."""
    if not isinstance(updates, dict):
        raise ValueError("settings to save must be a dictionary")
    unknown = set(updates) - set(SETTINGS_TYPES)
    if unknown:
        raise ValueError(f"unknown settings: {', '.join(sorted(map(str, unknown)))}")
    for key, value in updates.items():
        if type(value) is not SETTINGS_TYPES[key]:
            kind = "true or false" if SETTINGS_TYPES[key] is bool else "text"
            raise ValueError(f"{key} must be {kind}, not {value!r}")
    if "editor" in updates and updates["editor"] not in EDITORS:
        raise ValueError(f"editor must be one of {', '.join(EDITORS)}")
    if "library" in updates and not updates["library"].strip():
        raise ValueError("the library can't be empty")


# --- saving: one transaction at a time, across threads and processes (M7.1 S3, FA-06) ---------

SETTINGS_LOCK_WAIT = 5.0  # seconds to obtain both locks (not the length of the save itself)
_POLL = 0.025  # between tries for the operating-system lock (never past the deadline)
_clock = time.monotonic  # (tests use a fake clock)
_sleep = time.sleep  # (and a fake sleep)
_in_transaction = threading.local()


def _on_lock_contended(kind: str) -> None:
    """Test hook: a lock ("thread" or "os") was found taken and this save will wait for it."""


def _on_before_publish() -> None:
    """Test hook: both locks held, the new bytes ready, nothing written yet."""


def _on_settings_outcome(kind: str, data=None) -> None:
    """Test hook, called once per save that got its locks, where its outcome is decided:
    "noop", "committed" (data: the bytes published), "blocked" and "failed" (data: the
    error), "refused" (data: the error: invalid settings, or a file it won't change)."""


def _strict_real(path: Path) -> Path:
    """The real location of an existing path (links, junctions, short names followed), or
    OSError: never a guess for a link that can't be followed."""
    real = os.path.realpath(safe_io._os_path(path), strict=True)
    if real.startswith("\\\\?\\UNC\\"):
        real = "\\\\" + real[len("\\\\?\\UNC\\") :]
    elif real.startswith("\\\\?\\"):
        real = real[len("\\\\?\\") :]
    return Path(real)


def _refuse_case_sensitive(folder: Path) -> None:
    """Windows only (D5): settings and their lock only in a folder that positively answers
    that it doesn't tell upper and lower case apart. Set, or no reliable answer: refused."""
    if os.name != "nt":
        return
    try:
        sensitive = platform_services.windows_case_sensitive(str(safe_io._os_path(folder)))
    except Exception as e:  # (any failure to get an answer, ctypes' own included: refused)
        raise SettingsNotWritable(
            f"myLibrary couldn't confirm that the folder {folder.name} treats upper and lower "
            f"case the usual Windows way ({e}), so it won't save settings there."
        ) from None
    if sensitive:
        raise SettingsNotWritable(
            f"The folder {folder.name} is set to treat upper and lower case as different (a "
            "Windows per-folder setting), which myLibrary doesn't support for its settings. "
            f'Turn it off (fsutil file setCaseSensitiveInfo "{folder}" disable) or use '
            "another folder."
        )


def _refuse_frozen_settings(path: Path) -> None:
    if reason := frozen_reason(path):
        raise SettingsNotWritable(reason)


def _nearest_existing(folder: Path) -> Path:
    while not os.path.lexists(safe_io._os_path(folder)):
        if folder.parent == folder:
            raise SettingsUnreadable(f"no folder of {folder} exists")
        folder = folder.parent
    return folder


def _follow_existing(spelled: Path) -> Path:
    """The real location of an existing settings file or folder, proven to be the same thing
    as `spelled`: followed strictly (a link that can't be followed is refused), the result free
    of names Windows changes, and the same file system entry as `spelled` itself (device and
    file id), so the ordinary form used from here on can never reach a neighbour (S3 round 1)."""
    try:
        real = _strict_real(spelled)
    except FileNotFoundError:
        raise SettingsDanglingAlias(f"{spelled} is a link whose target is missing.") from None
    except OSError as e:
        raise SettingsUnreadable(f"{spelled} can't be followed: {e}") from None
    _refuse_ambiguous_path(real)
    try:
        same = _same_entry(os.stat(safe_io._os_path(spelled)), os.stat(safe_io._os_path(real)))
    except OSError as e:
        raise SettingsUnreadable(f"{spelled} can't be checked: {e}") from None
    if not same:
        raise SettingsNotWritable(
            f"{spelled} and its real location {real} aren't the same file; myLibrary won't "
            "save settings through it. Choose the settings file by its ordinary path."
        )
    return real


def _check_chosen_at_start() -> None:
    """At the start, for a settings file chosen with MYLIBRARY_SETTINGS: a path Windows reads
    as another file, and (D5) a case-sensitive or unanswerable settings folder, or an
    existing .myLibrary-local that is a link, not a folder, case-sensitive or can't be
    checked, stop the start before anything else. Creates nothing; only "not found" counts
    as no lock folder (S3 round 2: a folder that can't be looked at is never taken as absent)."""
    if SETTINGS_SOURCE != _SOURCE_EXPLICIT:
        return
    spelled = Path(SETTINGS_FILE)
    _refuse_ambiguous_path(spelled)
    _refuse_reserved(spelled)
    if not os.path.lexists(safe_io._os_path(spelled)):
        return  # (missing: _saved says so, with its own message)
    real = _follow_existing(spelled)
    _refuse_case_sensitive(real.parent)
    sidecar = real.parent / _RESERVED_FOLDER
    # (S3 round 3: .myLibrary-local can also hold the library registry, logs and Test & Demo
    # copies, so these messages never suggest deleting it, and nothing here changes it.)
    try:
        info = os.lstat(safe_io._os_path(sidecar))
    except FileNotFoundError:
        return  # (made at the first save, and checked then)
    except OSError as e:
        raise _sidecar_unreadable(sidecar, e, _START_STOPS) from None
    if _is_link(info):
        raise _sidecar_is_link(sidecar, _START_STOPS)
    if not stat.S_ISDIR(info.st_mode):
        raise _sidecar_not_folder(sidecar, _START_STOPS)
    _refuse_case_sensitive(sidecar)


# The same guidance at the start and at a save (S3 round 3/4): .myLibrary-local can also hold
# the library registry, logs and Test & Demo copies, so it is never called empty and never
# offered for deletion; myLibrary itself changes nothing there.
_START_STOPS = ("won't start with these settings", "start again")
_SAVE_STOPS = ("won't save the settings; nothing was changed", "save again")
# (a save that can't look may already have made .myLibrary-local, or the settings folder, on
# its way: only the settings file is said to be unchanged; S3 final, Codex's Low finding)
_SAVE_UNREADABLE = ("won't save the settings; the settings file was not changed", "save again")


def _sidecar_unreadable(sidecar: Path, error: OSError, stops) -> SettingsUnreadable:
    return SettingsUnreadable(
        f"myLibrary can't safely look at its local-data folder {sidecar} ({error}), so it "
        f"{stops[0]}. Check that the folder and its drive are available and that your account "
        f"may read it, then {stops[1]}. Don't delete the folder: it can hold myLibrary's own "
        "records, not only the settings lock."
    )


def _sidecar_is_link(sidecar: Path, stops) -> SettingsNotWritable:
    return SettingsNotWritable(
        f"{sidecar} is a link or junction to another folder; myLibrary doesn't support keeping "
        f"its local-data folder through a link, so it {stops[0]}. If you remove the link, "
        "remove only the link itself, never the folder it points to: keep that folder and "
        "everything in it."
    )


def _sidecar_not_folder(sidecar: Path, stops) -> SettingsNotWritable:
    return SettingsNotWritable(
        f"{sidecar} exists but isn't a folder, and myLibrary needs a folder there for its "
        f"local data, so it {stops[0]}. Look at what that item is and keep anything you need "
        "from it; myLibrary hasn't changed it."
    )


def _settings_destination() -> Path:
    """The one place a save locks, rereads and replaces: the settings file's real location.
    An existing file: followed strictly and proven the same file (_follow_existing), a regular
    file with no second hard link. A missing one: only the usual settings file (source
    "default"), under its folder's real location. Never a path Windows reads as another file,
    inside .myLibrary-local, a frozen library, or (Windows) a folder that tells case apart."""
    spelled = Path(SETTINGS_FILE)
    _refuse_ambiguous_path(spelled)
    _refuse_reserved(spelled)
    try:
        os.lstat(safe_io._os_path(spelled))
        exists = True
    except FileNotFoundError:
        exists = False
    except OSError as e:
        raise SettingsUnreadable(f"The settings file {spelled} can't be checked: {e}") from None
    if not exists:
        if SETTINGS_SOURCE == _SOURCE_EXPLICIT:
            raise SettingsMissing(_missing_message(spelled))
        if _dangling_on_the_way(spelled):
            raise SettingsDanglingAlias(
                f"A folder on the way to the settings file {spelled} is a link whose target "
                "is missing."
            )
        existing = _nearest_existing(spelled.parent)
        real_existing = _follow_existing(existing)
        dest = real_existing / spelled.parent.relative_to(existing) / spelled.name
        _refuse_case_sensitive(real_existing)
    else:
        dest = _follow_existing(spelled)
        info = os.stat(safe_io._os_path(dest))
        if not stat.S_ISREG(info.st_mode):
            raise SettingsNotWritable(f"The settings file {dest} isn't a file.")
        if info.st_nlink > 1:
            raise SettingsNotWritable(
                f"The settings file {dest.name} has another hard link; saving would separate "
                "the two names. Remove the other link first."
            )
        _refuse_case_sensitive(dest.parent)
    _refuse_ambiguous_path(dest)
    _refuse_reserved(dest)
    _refuse_frozen_settings(dest)
    return dest


def _same_entry(a: os.stat_result, b: os.stat_result) -> bool:
    return (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino)


def _is_link(info: os.stat_result) -> bool:
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & reparse)


def _marker_for(dest: Path) -> Path:
    """The lock marker for `dest`, its folder made and checked: .myLibrary-local next to the
    real settings file, a real folder (not a link or junction), never in a frozen library,
    (Windows) not case-sensitive; the marker itself, if there, a plain file with one name."""
    parent = dest.parent
    if not os.path.lexists(safe_io._os_path(parent)):
        _refuse_frozen_settings(parent)
        os.makedirs(safe_io._os_path(parent), exist_ok=True)  # (a package's first start)
    sidecar = parent / _RESERVED_FOLDER
    _refuse_frozen_settings(sidecar)
    try:
        os.mkdir(safe_io._os_path(sidecar))
    except FileExistsError:
        pass
    try:
        info = os.lstat(safe_io._os_path(sidecar))
    except OSError as e:
        raise _sidecar_unreadable(sidecar, e, _SAVE_UNREADABLE) from None
    if _is_link(info):
        raise _sidecar_is_link(sidecar, _SAVE_STOPS)
    if not stat.S_ISDIR(info.st_mode):
        raise _sidecar_not_folder(sidecar, _SAVE_STOPS)
    try:
        real = _strict_real(sidecar)
    except OSError as e:
        raise _sidecar_unreadable(sidecar, e, _SAVE_UNREADABLE) from None
    if os.path.normcase(str(real)) != os.path.normcase(str(sidecar)):
        raise _sidecar_is_link(sidecar, _SAVE_STOPS)
    _refuse_case_sensitive(sidecar)
    marker = sidecar / f"{dest.name}.lock"
    try:
        info = os.lstat(safe_io._os_path(marker))
    except FileNotFoundError:
        return marker
    except OSError as e:
        raise SettingsUnreadable(
            f"myLibrary can't safely look at its settings lock {marker} ({e}), so it won't save "
            "the settings; the settings file was not changed. Check that the folder and its "
            "drive are available and that your account may read it, then save again. Don't "
            "delete anything there."
        ) from None
    # (S3 round 5: whatever is at the marker's name may be someone's data, so each refusal says
    # what was found and never calls it empty or suggests deleting it; nothing is changed.)
    if _is_link(info):
        raise SettingsNotWritable(
            f"The settings lock {marker} is a link or junction; myLibrary doesn't support a "
            "linked lock, so it won't save the settings; nothing was changed. If you remove the "
            "link, remove only the link itself, never what it points to: keep that and "
            "everything in it."
        )
    if stat.S_ISDIR(info.st_mode):
        found = "a folder"
    elif not stat.S_ISREG(info.st_mode):
        found = "an item that isn't a plain file"
    elif info.st_nlink > 1:
        found = "a file that also has another name (a hard link), so another file shares it"
    else:
        return marker
    raise SettingsNotWritable(
        f"myLibrary expected its settings lock {marker} to be a plain file of its own, but found "
        f"{found}, so it won't save the settings; nothing was changed. Look at what that item is "
        "and keep anything you need from it; myLibrary hasn't changed it."
    )


def _open_marker(marker: Path) -> int:
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOINHERIT", 0)
    fd = os.open(safe_io._os_path(marker), flags)  # (never truncated, never deleted)
    try:
        if not _same_entry(os.fstat(fd), os.lstat(safe_io._os_path(marker))):
            raise SettingsMoved("The settings lock changed while being opened; try again.")
        _refuse_frozen_settings(_strict_real(marker))
    except BaseException:
        os.close(fd)
        raise
    return fd


def _try_os_lock(fd: int) -> bool:
    os.lseek(fd, 0, os.SEEK_SET)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _os_unlock(fd: int) -> None:
    os.lseek(fd, 0, os.SEEK_SET)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)


def _busy() -> SettingsBusy:
    return SettingsBusy(
        "The settings are being saved by another myLibrary window; nothing was changed. "
        "Try again in a moment."
    )


@contextmanager
def _settings_locks():
    """Both locks for the settings file within one SETTINGS_LOCK_WAIT for the two together:
    first this process's (one thread at a time), then the operating system's on the marker
    (one process at a time); then the destination is checked again. Yields the destination.
    Released in reverse order, whatever happens."""
    dest = _settings_destination()
    deadline = _clock() + SETTINGS_LOCK_WAIT
    thread_lock = safe_io.lock_for(dest)
    if not thread_lock.acquire(blocking=False):
        _on_lock_contended("thread")
        remaining = deadline - _clock()
        if remaining <= 0 or not thread_lock.acquire(timeout=remaining):
            raise _busy()
    try:
        fd = _open_marker(_marker_for(dest))
        try:
            contended = False
            while True:
                remaining = deadline - _clock()
                if remaining <= 0:
                    raise _busy()
                if _try_os_lock(fd):
                    break
                if not contended:
                    contended = True
                    _on_lock_contended("os")
                _sleep(min(_POLL, max(0.0, deadline - _clock())))
            try:
                # Checked again with both locks held: the same file, the same marker, still a
                # folder that may hold them; anything changed while waiting: no save
                if _settings_destination() != dest:
                    raise SettingsMoved(
                        "The settings file changed while this save waited; nothing was "
                        "changed. Try again."
                    )
                if not _same_entry(os.fstat(fd), os.lstat(safe_io._os_path(_marker_for(dest)))):
                    raise SettingsMoved("The settings lock changed while waiting; try again.")
                yield dest
            finally:
                _os_unlock(fd)
        finally:
            os.close(fd)
    finally:
        thread_lock.release()


_TEMP_NAME = re.compile(r"\..+\.[0-9a-f]{8}\.tmp")


def _names_temp(error: OSError, dest: Path) -> bool:
    name = getattr(error, "filename", None)
    if not name:
        return False
    path = Path(name)
    return bool(_TEMP_NAME.fullmatch(path.name)) and path.name.startswith(f".{dest.name}.")


def _read_only(dest: Path) -> bool | None:
    """Whether the settings file is marked read-only (a lasting restriction no retry lifts);
    None when that can't be told."""
    try:
        info = os.stat(safe_io._os_path(dest))
    except OSError:
        return None
    attributes = getattr(info, "st_file_attributes", None)
    if attributes is None:
        return not os.access(safe_io._os_path(dest), os.W_OK)
    return bool(attributes & stat.FILE_ATTRIBUTE_READONLY)


def _publish(dest: Path, new: bytes, old: bytes | None) -> None:
    """safe_io.write_bytes, its failures told apart by phase and cause. "Blocked" (D3,
    SettingsBlocked, retryable) only when the replacement was still refused after every retry
    (safe_io.ReplaceBlocked), the file isn't marked read-only (a lasting restriction, which wins
    over any sign of use), the in-use probe saw it held open, and the file is read back
    unchanged. Anything else is SettingsSaveFailed. Every message states what the file was
    read back to hold, never assumed; the original error stays attached (__cause__)."""
    try:
        safe_io.write_bytes(dest, new)
        return
    except OSError as error:
        failure = error
    cleanup, primary = None, failure
    if _names_temp(failure, dest) and isinstance(failure.__context__, OSError):
        cleanup, primary = failure, failure.__context__  # (removing the temporary file failed)
    elif _names_temp(failure, dest):
        try:  # creating the temporary file failed, or removing it after a replacement
            if safe_io.read_bytes(dest) == new:
                cleanup = failure
        except OSError:
            pass
    probe_error, cause, in_use = None, "", False
    if isinstance(primary, safe_io.ReplaceBlocked) and cleanup is None and os.name == "nt":
        read_only = _read_only(dest)
        if read_only:
            cause = "the settings file is marked read-only; clear that and save again"
        elif read_only is None:
            cause = "whether the settings file is read-only couldn't be checked"
        else:
            seen = _seen_in_use(dest)
            if isinstance(seen, Exception):  # (the probe couldn't answer: nothing confirmed)
                probe_error = seen
            else:
                in_use = seen
    state, sentence = _state_now(dest, new, old)
    if in_use and state == "unchanged":
        _on_settings_outcome("blocked", primary)
        raise SettingsBlocked(
            f"Saving the settings was blocked because the settings file was in use. {sentence} "
            "Try again."
        ) from primary
    if isinstance(primary, safe_io.ReplaceBlocked):  # (its own text guesses at another program)
        detail = (
            f"the new settings file couldn't replace the old one after {primary.attempts} tries"
        )
    else:
        detail = str(primary)
    if cause:
        detail += f"; {cause}"
    if in_use:
        detail += "; the settings file was in use"
    if cleanup is not None:
        detail += f"; the temporary file {Path(cleanup.filename).name} couldn't be removed"
    if probe_error is not None:
        detail += f"; whether the file was in use couldn't be checked ({probe_error})"
    _on_settings_outcome("failed", failure)
    raise SettingsSaveFailed(f"Couldn't save the settings ({detail}). {sentence}") from primary


IN_USE_LOOKS = 5  # in-use probes after a blocked replacement, PROBE_GAP apart (about 0.1 s)
PROBE_GAP = 0.02


def _seen_in_use(dest: Path):
    """True if the in-use probe sees the file held open (a sharing violation) in any of a few
    looks a moment apart: a reader's handle is often open only for an instant, so one look can
    miss what kept the replacement out. False if every look found it free (the cause is then
    unconfirmed: a read-only file, its permissions...); the last probe error if no look could
    answer at all. Only a sharing violation actually seen ever counts."""
    error = None
    answered = False
    for look in range(IN_USE_LOOKS):
        if look:
            time.sleep(PROBE_GAP)
        try:
            if platform_services.windows_file_in_use(str(safe_io._os_path(dest))):
                return True
            answered = True
        except Exception as e:
            error = e
    return False if answered else error


def _state_now(dest: Path, new: bytes, old: bytes | None) -> tuple[str, str]:
    """What the settings file holds after a failed save, read again, never assumed: ("unchanged"
    | "new" | "changed" | "unknown", the sentence saying so)."""
    try:
        now = safe_io.read_bytes(dest)
    except FileNotFoundError:
        now = None
    except OSError:
        return "unknown", (
            "Couldn't confirm what the settings file holds now; reopen Settings to check."
        )
    if now == old:
        return "unchanged", "The settings file was not changed."
    if now == new:
        return "new", "The new settings are in the settings file."
    return "changed", "The settings file may have changed; reopen Settings to check."


def update_settings(change) -> dict:
    """The one way settings are saved. `change(current)` gets the settings file's latest
    contents (read with both locks held) and returns the settings to set; only those change,
    losslessly (settings_toml.edit), and nothing is written when they're already so. Of two
    saves of one setting the later wins; saves of different settings never undo each other
    (D1). Returns all settings (defaults merged). Raises SettingsBusy (5 s to get the locks),
    SettingsBlocked, SettingsSaveFailed, the read errors, ValueError for invalid settings and
    SettingsNotWritable: the file is untouched by all of them (a SettingsSaveFailed says what
    it holds)."""
    if getattr(_in_transaction, "active", False):
        raise RuntimeError("nested settings transaction")
    _in_transaction.active = True
    try:
        with _settings_locks() as dest, safe_io.critical():
            old = _probe_settings(dest, SETTINGS_SOURCE)
            current = {} if old is None else settings_toml.parse(old, dest.name)
            try:
                updates = change(dict(current))
                _check_updates(updates)
                new = settings_toml.edit(
                    old, updates, types=SETTINGS_TYPES, name=dest.name,
                    default_newline=os.linesep,
                )  # fmt: skip
            except ValueError as e:  # (SettingsNotWritable included)
                _on_settings_outcome("refused", e)
                raise
            if new is None:
                _on_settings_outcome("noop")
                return SETTINGS_DEFAULTS | current
            _on_before_publish()
            _publish(dest, new, old)
            _on_settings_outcome("committed", new)
            return SETTINGS_DEFAULTS | settings_toml.parse(new, dest.name)
    finally:
        _in_transaction.active = False


def save_settings(updates: dict) -> dict:
    """Change some settings (only known keys, each of its one type); returns all of them."""
    _check_updates(updates)
    return update_settings(lambda _current: updates)


def _from_argv(argv: list[str]) -> str | None:
    for i, arg in enumerate(argv):
        if arg == "--library" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--library="):
            return arg.split("=", 1)[1]
    return None


def _resolve(argv: list[str]) -> tuple[Path, str]:
    """(library folder, where that choice came from). The settings file is read first whatever
    chooses the library (B44): one that can't be read, is damaged or (when chosen with
    MYLIBRARY_SETTINGS) is missing stops the start, so no other library is ever opened or
    created by mistake."""
    try:
        _check_chosen_at_start()
        settings = _saved()
    except (SettingsUnreadable, SettingsDamaged, SettingsNotWritable) as e:
        raise SystemExit(str(e)) from None
    if chosen := _from_argv(argv):
        source = "--library"
    elif chosen := os.environ.get(ENV_VAR):
        source = ENV_VAR
    else:
        chosen = settings.get("library")
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


# This computer's own records, next to the settings file and never inside a library or in git:
# the list of your libraries (libraries.json), the Test & Demo library's working copy, the
# logs of servers the launcher started (scripts/libraries.py)
LOCAL_DIR = SETTINGS_FILE.parent / ".myLibrary-local"
CANONICAL_TEST_LIBRARY = "test_library"  # in the tool's folder (libraries.TEST_CANONICAL)
# The author's example library in the tool's folder: a frozen public showcase, kept as it is in
# git and never opened or changed by the app (the author's own library lives elsewhere)
SHOWCASE_LIBRARY = "library"
FROZEN = {
    SHOWCASE_LIBRARY: (
        "library/ is the public showcase (the author's example library, kept as it is in git): "
        "myLibrary never opens or changes it. Use your own library (⚙ Settings, or --library "
        "<folder>); to try it out, copy the folder elsewhere and add it as a personal library."
    ),
    CANONICAL_TEST_LIBRARY: (
        "test_library/ is the canonical Test & Demo library, kept unchanged in git: open its "
        "working copy instead (uv run scripts/launch_library.py --test)"
    ),
}


def frozen_reason(path) -> str:
    """Why the app must never write in this folder ("" if it may): the showcase library/ and
    the canonical test_library/ in the tool's folder, and anything inside them."""
    here = os.path.normcase(str(Path(path).resolve()))
    for name, reason in FROZEN.items():
        root = os.path.normcase(str((APP / name).resolve()))
        if here == root or here.startswith(root + os.sep):
            return reason
    return ""


def refuse_frozen(library=None) -> None:
    """Stop (SystemExit with the reason) before a script changes a frozen library."""
    if reason := frozen_reason(library or LIBRARY):
        raise SystemExit(reason)


# Every write through safe_io into a frozen folder is refused as well, whatever the caller
safe_io.freeze(*(APP / name for name in FROZEN))

LIBRARY_TOML = """# This library's settings.
name = "My library"
# This library's own permanent id (its documents have their own, in catalog.csv). It travels
# with the folder: a moved library is still the same one. Don't change it.
id = "{id}"

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
    remembered in the settings file so the next start uses the same one. Never a frozen library
    (the showcase library/ or the canonical test_library/ in the tool's folder, frozen_reason):
    the server and add_book.py start here, so nothing of theirs ever writes there."""
    library = library or LIBRARY
    refuse_frozen(library)
    for sub in ("books", "papers", "theses", "notes/topics", "glossaries", "examples"):
        (library / sub).mkdir(parents=True, exist_ok=True)
    if not (library / "library.toml").exists():
        try:  # (never over one that appeared meanwhile)
            safe_io.create_text(library / "library.toml", LIBRARY_TOML.format(id=uuid.uuid4()))
        except FileExistsError:
            pass
    if library == LIBRARY and LIBRARY_SOURCE == "default":
        remembered = []

        def remember(current: dict) -> dict:  # (set only if absent, decided under the locks)
            if "library" in current:
                return {}
            remembered.append(True)
            return {"library": library.as_posix()}

        if "library" not in _saved():
            update_settings(remember)
            if remembered:
                print(f"New library created: {library}")
    return library


# The VS Code window notes and scripts open in: the whole project when the library is inside
# the tool's folder (as for the author's library/), else the library folder itself
WORKSPACE = APP if LIBRARY.is_relative_to(APP) else LIBRARY
