"""platform_services: every branch checked with the system calls mocked, so the Windows, macOS
and other branches run on any computer. Nothing is launched and no dialog opens. The macOS
branches are tested this way only (ROADMAP X1), never on a Mac."""

import os
import subprocess
from pathlib import Path

import library_server
import paths
import platform_services as ps
import pytest

# A path with spaces, Chinese and a quote: one argument, whatever it holds
ODD = Path("C:/书库 Library/notes/第1章 Paraxial optics/it's ch01.md")


@pytest.fixture
def launched(monkeypatch):
    """What was started: (args, kwargs) for every Popen, and every os.startfile."""
    calls = {"popen": [], "startfile": []}
    monkeypatch.setattr(
        ps.subprocess, "Popen", lambda args, **kw: calls["popen"].append((args, kw))
    )
    monkeypatch.setattr(ps.os, "startfile", calls["startfile"].append, raising=False)
    return calls


# --- opening files ------------------------------------------------------------------------


def test_windows_editors_behave_as_they_always_did(launched):
    ps.open_for_editing(ODD, "system", platform="win32")
    assert launched["startfile"] == [ODD]  # the app set for .md files
    ps.open_for_editing(ODD, "notepad", platform="win32")
    assert launched["popen"][-1][0] == ["notepad.exe", str(ODD)]
    # A custom command: the command line as written, the file quoted at the end when the
    # command has no {file}; handed to CreateProcess, never to a shell
    ps.open_for_editing(ODD, "custom", r'"C:\Tools\ed.exe" -n', platform="win32")
    args, kw = launched["popen"][-1]
    assert args == rf'"C:\Tools\ed.exe" -n "{ODD}"' and not kw.get("shell")
    ps.open_for_editing(ODD, "custom", 'ed.exe --file="{file}"', platform="win32")
    assert launched["popen"][-1][0] == f'ed.exe --file="{ODD}"'
    ps.open_for_editing(ODD, "custom", "   ", platform="win32")  # empty: the system app
    assert launched["startfile"] == [ODD, ODD]


@pytest.mark.parametrize("platform", ["win32", "darwin", "linux"])
@pytest.mark.parametrize("name", ["ch01_optics.py", "CH01_OPTICS.PY"])
def test_a_python_script_is_never_opened_with_its_default_app(launched, platform, name):
    """Opening a .py with its default app can *run* it: it goes to a text editor, or nowhere."""
    script = ODD.with_name(name)
    for editor in ("system", "notepad", "vscode"):  # (vscode here: code wasn't found)
        if platform == "linux":
            with pytest.raises(OSError):
                ps.open_for_editing(script, editor, platform=platform)
        else:
            ps.open_for_editing(script, editor, platform=platform)
    assert launched["startfile"] == []
    expected = {"win32": ["notepad.exe", str(script)], "darwin": ["open", "-t", str(script)]}
    assert all(args == expected[platform] for args, _ in launched["popen"])
    assert len(launched["popen"]) == (0 if platform == "linux" else 3)


def test_macos_opens_with_the_default_app_or_text_editor(launched):
    ps.open_for_editing(ODD, "system", platform="darwin")
    ps.open_for_editing(ODD, "notepad", platform="darwin")  # no Notepad: the text editor
    assert [a for a, _ in launched["popen"]] == [["open", str(ODD)], ["open", "-t", str(ODD)]]
    assert launched["startfile"] == []


def test_a_custom_command_on_macos_gets_the_path_as_one_argument(launched):
    nasty = Path("/Users/me/My Books/书/a'; rm -rf ~; echo '.md")
    ps.open_for_editing(nasty, "custom", "subl -w", platform="darwin")
    ps.open_for_editing(nasty, "custom", "'/Applications/My Editor.app/bin/ed' --goto {file}:1",
                        platform="darwin")  # fmt: skip
    (first, kw1), (second, kw2) = launched["popen"]
    assert first == ["subl", "-w", str(nasty)]
    assert second == ["/Applications/My Editor.app/bin/ed", "--goto", f"{nasty}:1"]
    assert not kw1.get("shell") and not kw2.get("shell")
    with pytest.raises(OSError, match="can't be read"):
        ps.open_for_editing(nasty, "custom", 'ed "unclosed', platform="darwin")


def test_open_in_editor_uses_the_settings_and_reports_failure(launched, monkeypatch):
    monkeypatch.setattr(library_server.shutil, "which", lambda name: None)  # no VS Code
    monkeypatch.setattr(paths, "load_settings", lambda: {"editor": "vscode"})
    assert library_server.open_in_editor(ODD) is True
    assert launched["startfile"] == [ODD] or launched["popen"]  # fell back to the system app

    def broken(*a, **k):
        raise OSError("no such program")

    monkeypatch.setattr(ps.subprocess, "Popen", broken)
    monkeypatch.setattr(paths, "load_settings", lambda: {"editor": "notepad"})
    assert library_server.open_in_editor(ODD) is False


# --- the folder dialog --------------------------------------------------------------------


def _ran(monkeypatch, *, stdout="", stderr="", returncode=0, raises=None):
    seen = []

    def run(args, **kw):
        seen.append(args)
        if raises:
            raise raises
        return subprocess.CompletedProcess(args, returncode, stdout, stderr)

    monkeypatch.setattr(ps.subprocess, "run", run)
    return seen


def test_windows_folder_dialog(monkeypatch):
    seen = _ran(monkeypatch, stdout="C:\\书库 My Library\r\n")
    choice = ps.pick_folder("Choose the folder for Nan's library", platform="win32")
    assert choice == ps.FolderChoice("chosen", "C:\\书库 My Library")
    assert seen[0][:3] == ["powershell", "-NoProfile", "-STA"]
    assert "'Choose the folder for Nan''s library'" in seen[0][-1]  # quote doubled

    _ran(monkeypatch, stdout="\r\n")
    assert ps.pick_folder("x", platform="win32").status == "cancelled"
    _ran(monkeypatch, returncode=1, stderr="Add-Type : cannot load")
    assert ps.pick_folder("x", platform="win32") == ps.FolderChoice(
        "error", message="Add-Type : cannot load"
    )
    _ran(monkeypatch, raises=FileNotFoundError(2, "not found", "powershell"))
    assert ps.pick_folder("x", platform="win32").status == "unsupported"
    _ran(monkeypatch, raises=subprocess.TimeoutExpired("powershell", 900))
    assert ps.pick_folder("x", platform="win32").status == "error"


def test_macos_folder_dialog(monkeypatch):
    monkeypatch.setattr(ps.shutil, "which", lambda name: "/usr/bin/osascript")
    seen = _ran(monkeypatch, stdout="/Users/me/My Books/书库/\n")
    prompt = 'Choose "the" folder'
    choice = ps.pick_folder(prompt, platform="darwin")
    assert choice == ps.FolderChoice("chosen", "/Users/me/My Books/书库")
    args = seen[0]
    assert args[0] == "osascript" and args[-1] == prompt  # an argument, not script text
    assert all(prompt not in a for a in args[:-1])

    _ran(monkeypatch, returncode=1, stderr="execution error: User canceled. (-128)")
    assert ps.pick_folder(prompt, platform="darwin").status == "cancelled"
    _ran(monkeypatch, returncode=1, stderr="execution error: something else (-1700)")
    assert ps.pick_folder(prompt, platform="darwin").status == "error"
    _ran(monkeypatch, stdout="/\n")
    assert ps.pick_folder(prompt, platform="darwin").folder == "/"

    monkeypatch.setattr(ps.shutil, "which", lambda name: None)
    seen = _ran(monkeypatch)
    assert ps.pick_folder(prompt, platform="darwin").status == "unsupported" and seen == []


def test_no_folder_dialog_elsewhere(monkeypatch):
    seen = _ran(monkeypatch)
    choice = ps.pick_folder("x", platform="linux")
    assert choice.status == "unsupported" and choice.folder is None and seen == []


# --- where the settings are -------------------------------------------------------------


def test_settings_file_in_development_and_in_the_package(tmp_path, monkeypatch):
    monkeypatch.delenv(paths.SETTINGS_VAR)  # (the test run's own settings file otherwise)
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    home = tmp_path / "home"
    monkeypatch.setattr(ps.Path, "home", lambda: home)

    assert paths._settings_file(is_package=False) == paths.APP / "local.toml"  # development
    for platform in ("win32", "darwin", "linux"):  # development is the same everywhere
        assert paths._settings_file(is_package=False, platform=platform) == paths.APP / "local.toml"

    # The package on Windows: %APPDATA%/myLibrary, as always
    win = paths._settings_file(is_package=True, platform="win32")
    assert win == tmp_path / "Roaming" / "myLibrary" / "settings.toml"
    monkeypatch.delenv("APPDATA")
    assert paths._settings_file(is_package=True, platform="win32") == (
        home / "myLibrary" / "settings.toml"
    )  # without APPDATA: the home folder, as before
    # A future macOS package: Application Support
    mac = paths._settings_file(is_package=True, platform="darwin")
    assert mac == home / "Library" / "Application Support" / "myLibrary" / "settings.toml"
    # Nothing was created or moved: these only say where to look
    assert not (tmp_path / "Roaming").exists() and not home.exists()
    # Never inside the application's folder
    for found in (win, mac):
        assert not found.resolve().is_relative_to(paths.APP.resolve())


def test_the_settings_variable_still_wins(tmp_path, monkeypatch):
    chosen = tmp_path / "settings.toml"
    chosen.write_text("", encoding="utf-8")
    monkeypatch.setenv(paths.SETTINGS_VAR, str(chosen))
    for platform in ("win32", "darwin"):
        assert paths._settings_file(is_package=True, platform=platform) == chosen.resolve()


def test_the_running_settings_file_is_unchanged():
    """This run's settings come from MYLIBRARY_SETTINGS (tests/isolation_guard.py): the
    refactor didn't change which file the app reads."""
    assert paths.SETTINGS_FILE == Path(os.environ[paths.SETTINGS_VAR]).resolve()
