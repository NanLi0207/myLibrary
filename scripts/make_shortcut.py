"""Create a "myLibrary" shortcut on the Desktop and in the Start menu (Windows).

    uv run scripts/make_shortcut.py

Double-clicking it starts the library server (in a minimized window: close that window to
stop it) and opens the library page; if the server is already running it just opens the page.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _ps_quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def make_shortcut(link: Path, uv: str) -> None:
    script = f"""
$s = (New-Object -ComObject WScript.Shell).CreateShortcut({_ps_quote(str(link))})
$s.TargetPath = {_ps_quote(uv)}
$s.Arguments = 'run scripts/library_server.py'
$s.WorkingDirectory = {_ps_quote(str(ROOT))}
$s.WindowStyle = 7
$s.Description = 'Open myLibrary (books, notes, reading view)'
$s.IconLocation = '%SystemRoot%\\System32\\imageres.dll,112'
$s.Save()
"""
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], check=True)


def folders() -> list[Path]:
    script = "[Environment]::GetFolderPath('Desktop'); [Environment]::GetFolderPath('Programs')"
    out = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [Path(line) for line in out.splitlines() if line.strip()]


def main() -> None:
    if sys.platform != "win32":
        sys.exit("Windows only. Elsewhere: uv run scripts/library_server.py")
    uv = shutil.which("uv")
    if not uv:
        sys.exit("uv not found on PATH")
    for folder in folders():
        link = folder / "myLibrary.lnk"
        make_shortcut(link, uv)
        print(f"created {link}")


if __name__ == "__main__":
    main()
