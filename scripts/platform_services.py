"""What differs between operating systems, in one place: where an installed myLibrary keeps
this computer's own settings, opening a file for editing, and the folder dialog.

Windows is what myLibrary is developed and tested on; its behaviour here is the behaviour the
app always had. The macOS branches are groundwork for a later macOS version (ROADMAP X1): they
are tested with mocked system calls only, never on a Mac. Other systems keep what they had
(xdg-open; no folder dialog).

Every function takes `platform` (default: sys.platform) so the tests can check each branch on
any computer. Nothing here starts a shell: programs get their arguments as a list, so a path
with spaces, quotes or Chinese characters is passed as it is.
"""

import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "myLibrary"


def user_data_dir(platform: str | None = None) -> Path:
    """The folder for this computer's own records of an installed (packaged) myLibrary: the
    settings file, logs, the list of libraries. Never inside the application's folder, so an
    update or a reinstall leaves it alone. Windows: %APPDATA%/myLibrary (as always); macOS:
    ~/Library/Application Support/myLibrary (for a future macOS package); elsewhere what it
    always was. Nothing is moved: this only says where to look."""
    platform = platform or sys.platform
    if platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path(os.environ.get("APPDATA") or Path.home()) / APP_NAME


# --- opening a file for editing -----------------------------------------------------------


def _custom_command(command: str, file: Path, platform: str) -> str | list[str]:
    """The user's own editor command with the file in it. On Windows the command line goes to
    CreateProcess as written (as it always did; no shell). Elsewhere it's split into arguments
    first and {file} replaced inside them, so the path is one argument whatever it contains."""
    if platform == "win32":
        if "{file}" not in command:
            command += ' "{file}"'
        return command.replace("{file}", str(file))
    try:
        args = shlex.split(command)
    except ValueError as e:  # e.g. an unclosed quote
        raise OSError(f"the editor command can't be read: {e}") from None
    if not args:
        raise OSError("the editor command is empty")
    if not any("{file}" in a for a in args):
        args.append("{file}")
    return [a.replace("{file}", str(file)) for a in args]


def open_for_editing(
    file: Path, editor: str, command: str = "", platform: str | None = None
) -> None:
    """Open one file with the editor chosen in the settings (not VS Code: that opens the
    project window, see library_server.open_in_editor). OSError when it can't be opened.

    A .py is never opened with its default app (on Windows that can *run* it): it goes to a
    plain text editor instead, unless the user chose their own command."""
    platform = platform or sys.platform
    command = command.strip()
    if editor == "custom" and command:
        subprocess.Popen(_custom_command(command, file, platform))
    elif editor == "notepad" or file.suffix.lower() == ".py":
        if platform == "win32":
            subprocess.Popen(["notepad.exe", str(file)])
        elif platform == "darwin":
            subprocess.Popen(["open", "-t", str(file)])  # the default *text editor*, never run
        else:
            raise OSError(f"no plain text editor known here for {file.name}")
    elif platform == "win32":
        os.startfile(file)  # the app set for .md files (e.g. Typora, Notepad)
    elif platform == "darwin":
        subprocess.Popen(["open", str(file)])
    else:
        subprocess.Popen(["xdg-open", str(file)])


# --- the folder dialog --------------------------------------------------------------------


@dataclass
class FolderChoice:
    """What the folder dialog gave: status "chosen" (with folder), "cancelled", "unsupported"
    (no dialog on this system) or "error"; message says why for the last two."""

    status: str
    folder: str | None = None
    message: str = ""


def _ps_quote(text: str) -> str:
    """A PowerShell string literal (a quote doubled)."""
    return "'" + text.replace("'", "''") + "'"


def _windows_folder(prompt: str) -> FolderChoice:
    script = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$owner = New-Object System.Windows.Forms.Form -Property @{TopMost = $true};"
        "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
        f"$d.Description = {_ps_quote(prompt)};"
        "$d.ShowNewFolderButton = $true;"
        "if ($d.ShowDialog($owner) -eq 'OK') { $d.SelectedPath }"
    )
    done = subprocess.run(
        ["powershell", "-NoProfile", "-STA", "-Command", script],
        capture_output=True,
        text=True,
        timeout=900,
    )
    if done.returncode != 0:
        return FolderChoice(
            "error", message=(done.stderr or "").strip()[-300:] or "PowerShell failed"
        )
    folder = done.stdout.strip()
    return FolderChoice("chosen", folder) if folder else FolderChoice("cancelled")


def _mac_folder(prompt: str) -> FolderChoice:
    if not shutil.which("osascript"):
        return FolderChoice("unsupported", message="osascript isn't available")
    # The prompt goes in as an argument (argv), never into the script's text
    done = subprocess.run(
        ["osascript", "-e", "on run argv",
         "-e", "return POSIX path of (choose folder with prompt (item 1 of argv))",
         "-e", "end run", prompt],
        capture_output=True,
        text=True,
        timeout=900,
    )  # fmt: skip
    if done.returncode != 0:
        if "-128" in (done.stderr or ""):  # "User canceled. (-128)"
            return FolderChoice("cancelled")
        return FolderChoice(
            "error", message=(done.stderr or "").strip()[-300:] or "osascript failed"
        )
    folder = done.stdout.strip()
    if len(folder) > 1:
        folder = folder.rstrip("/")  # POSIX path of a folder ends in "/"
    return FolderChoice("chosen", folder) if folder else FolderChoice("cancelled")


def pick_folder(prompt: str, platform: str | None = None) -> FolderChoice:
    """Ask for a folder with the system's own dialog (the server runs on this computer)."""
    platform = platform or sys.platform
    try:
        if platform == "win32":
            return _windows_folder(prompt)
        if platform == "darwin":
            return _mac_folder(prompt)
    except FileNotFoundError as e:  # the system tool itself is missing
        return FolderChoice(
            "unsupported", message=f"{Path(e.filename or '?').name} isn't available"
        )
    except subprocess.TimeoutExpired:
        return FolderChoice("error", message="the folder dialog was open too long")
    except OSError as e:
        return FolderChoice("error", message=str(e))
    return FolderChoice("unsupported", message="no folder dialog on this system")
