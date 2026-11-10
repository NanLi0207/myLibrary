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
import re
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


# What cmd.exe acts on in a batch file's arguments: & | < > split or redirect the command, ^ is
# removed, % (even inside quotes) and ! expand variables, ( ) " change the parsing (B28)
CMD_SPECIAL = frozenset('&|<>^%!()"')


# VS Code's bin/code.CMD: "%~dp0..\Code.exe" "%~dp0..\<build>\resources\app\out\cli.js" %*
_CODE_CMD_PART = re.compile(r'"%~dp0\.\.\\([^"%]+?\.(?:exe|js))"', re.IGNORECASE)


def _what_code_cmd_runs(code: Path) -> tuple[Path, Path] | None:
    """(Code.exe, cli.js) as VS Code's code.CMD starts them, if both are there."""
    try:
        text = code.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    found = [code.parent.parent / part for part in _CODE_CMD_PART.findall(text)]
    exe = next((p for p in found if p.suffix.lower() == ".exe"), None)
    cli = next((p for p in found if p.suffix.lower() == ".js"), None)
    return (exe, cli) if exe and cli and exe.is_file() and cli.is_file() else None


def vscode_command(
    code: str, args: list[str], platform: str | None = None
) -> tuple[list[str], dict | None] | None:
    """How to start VS Code (`code`, as shutil.which found it) with these arguments: (the
    program and its arguments, the environment or None for this one's), or None when it can't
    be done safely (the caller uses another editor).

    On Windows `code` is the batch file bin/code.CMD, which Windows runs through cmd.exe: an
    argument (the library's folder, a note's path) holding a CMD_SPECIAL character can then be
    cut, changed, or even start another command (B28). For such arguments myLibrary does what
    code.CMD does, without cmd.exe: Code.exe runs VS Code's cli.js with ELECTRON_RUN_AS_NODE=1
    (and VSCODE_DEV unset), the arguments passed as they are. Never Code.exe with the paths
    alone: with ELECTRON_RUN_AS_NODE in the environment (set for programs VS Code starts) it
    would run the library folder as a Node.js script. Other arguments, and every other system,
    start `code` as always."""
    platform = platform or sys.platform
    batch = Path(code).suffix.lower() in (".cmd", ".bat")
    if platform != "win32" or not batch or not any(CMD_SPECIAL & set(a) for a in args):
        return [code, *args], None
    parts = _what_code_cmd_runs(Path(code))
    if not parts:
        return None
    exe, cli = parts
    env = {k: v for k, v in os.environ.items() if k.upper() != "VSCODE_DEV"}
    env["ELECTRON_RUN_AS_NODE"] = "1"
    return [str(exe), str(cli), *args], env


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


NATIVE_PROGRAMS = (".exe", ".com")  # what CreateProcess starts itself, without cmd.exe


def _search_folders() -> list[Path]:
    """Where CreateProcess looks for a program named without a folder: the running program's
    folder, the current folder, the system folders, then PATH (more rather than fewer)."""
    windows = Path(os.environ.get("SystemRoot") or os.environ.get("windir") or "C:/Windows")
    base = getattr(sys, "_base_executable", sys.executable)
    folders = [Path(sys.executable).parent, Path(base).parent, Path.cwd()]
    folders += [windows / "System32", windows / "System", windows]
    return folders + [Path(p) for p in os.environ.get("PATH", "").split(os.pathsep) if p.strip()]


def _found_as_createprocess_finds(name: str) -> Path | None:
    """The file CreateProcess would start for this program name, or None. Windows drops
    trailing dots and spaces from a name (so "edit.cmd." is edit.cmd); a name without an
    extension gets .exe (never PATHEXT)."""
    tidy = name.rstrip(". ")
    if not tidy:
        return None
    program = Path(tidy)
    if not program.suffix:
        program = program.with_name(program.name + ".exe")
    if program.is_absolute() or len(program.parts) > 1 or ":" in tidy:  # a folder is named
        return program if program.is_file() else None
    return next((f / program for f in _search_folders() if (f / program).is_file()), None)


def _program_names(command: str) -> list[str]:
    """The names CreateProcess tries as the program of this command line: the quoted first
    part, or (unquoted) each longer stretch up to a space, shortest first."""
    command = command.lstrip()
    if command.startswith('"'):
        end = command.find('"', 1)
        return [command[1:end] if end != -1 else command[1:]]
    pieces = re.split(r"([ \t]+)", command)
    names, so_far = [], ""
    for i, piece in enumerate(pieces):
        so_far += piece
        if i % 2 == 0:
            names.append(so_far)
    return names


def cmd_exe_risk(command: str, file: Path) -> str:
    """Why this custom editor command line mustn't be given this file on Windows ("" if it
    may), B28: the path holds a CMD_SPECIAL character and the program may be run by, or be,
    cmd.exe, which would act on it (% even inside quotes). Anything this can't settle counts
    as a risk: such a file then goes to the system editor instead."""
    if not CMD_SPECIAL & set(str(file)):
        return ""  # nothing cmd.exe would act on: the command runs as it always did
    for name in _program_names(command):
        if program := _found_as_createprocess_finds(name):
            break
    else:
        return "its program couldn't be found"
    if program.suffix.lower() not in NATIVE_PROGRAMS:
        return "it is a batch file (.bat/.cmd), which runs through cmd.exe"
    if program.stem.lower() == "cmd":
        return "it runs cmd.exe"
    bare = Path(name.rstrip(". "))
    if not bare.suffix and len(bare.parts) == 1:  # PATHEXT could find a batch file instead
        found = shutil.which(name)
        if found and Path(found).suffix.lower() not in NATIVE_PROGRAMS:
            return "its name also finds a batch file"
    return ""


def open_for_editing(
    file: Path, editor: str, command: str = "", platform: str | None = None
) -> None:
    """Open one file with the editor chosen in the settings (not VS Code: that opens the
    project window, see library_server.open_in_editor). OSError when it can't be opened.

    A .py is never opened with its default app (on Windows that can *run* it): it goes to a
    plain text editor instead, unless the user chose their own command. On Windows a custom
    command that cmd.exe would run is never given a path cmd.exe would act on (cmd_exe_risk):
    that file opens with the system editor instead, and the server's log says why."""
    platform = platform or sys.platform
    command = command.strip()
    if editor == "custom" and command:
        risk = cmd_exe_risk(command, file) if platform == "win32" else ""
        if not risk:
            subprocess.Popen(_custom_command(command, file, platform))
            return
        print(
            f"The custom editor wasn't used for {file.name}: {risk}, and the file's path holds "
            "characters cmd.exe would act on (B28). Opened with the system editor instead."
        )
        editor = "system"
    if editor == "notepad" or file.suffix.lower() == ".py":
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
