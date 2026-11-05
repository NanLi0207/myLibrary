"""Start myLibrary from the ready-to-use package, without a console window.

Run by the package's own Python (runtime/python/pythonw.exe), from the "myLibrary" shortcuts
or "Start myLibrary.cmd". The first run creates those shortcuts (Desktop + Start menu).
Messages go to %APPDATA%/myLibrary/myLibrary.log, since there's no console to show them.
"""

import os
import site
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent  # the unzipped package folder
DATA = Path(os.environ.get("APPDATA") or Path.home()) / "myLibrary"

site.addsitedir(str(HERE / "runtime" / "site-packages"))
sys.path.insert(0, str(HERE / "scripts"))

DATA.mkdir(parents=True, exist_ok=True)
log = open(DATA / "myLibrary.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115
sys.stdout = sys.stderr = log


def make_shortcuts() -> None:
    """Desktop + Start menu shortcuts "myLibrary" to this launcher (made once, or again if the
    package folder was moved)."""
    pythonw = HERE / "runtime" / "python" / "pythonw.exe"
    script = f"""
$shell = New-Object -ComObject WScript.Shell
$folders = @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))
foreach ($folder in $folders) {{
  $s = $shell.CreateShortcut((Join-Path $folder 'myLibrary.lnk'))
  $s.TargetPath = '{pythonw}'
  $s.Arguments = '"{HERE / "launch.py"}"'
  $s.WorkingDirectory = '{HERE}'
  $s.Description = 'myLibrary: read, look up words, take notes'
  $s.IconLocation = '%SystemRoot%\\System32\\imageres.dll,112'
  $s.Save()
}}
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def main() -> None:
    marker = DATA / "shortcuts-for.txt"
    if not marker.exists() or marker.read_text(encoding="utf-8") != str(HERE):
        make_shortcuts()
        marker.write_text(str(HERE), encoding="utf-8")
    import library_server

    library_server.main()


if __name__ == "__main__":
    main()
