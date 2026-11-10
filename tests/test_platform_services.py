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


# --- B28: VS Code's code.CMD and cmd.exe ------------------------------------------------------

CODE_CMD = (
    "@echo off\nsetlocal\nset VSCODE_DEV=\nset ELECTRON_RUN_AS_NODE=1\n"
    '"%~dp0..\\Code.exe" "%~dp0..\\c4453f8ea4\\resources\\app\\out\\cli.js" %*\n'
    "IF %ERRORLEVEL% NEQ 0 EXIT /b %ERRORLEVEL%\nendlocal\n"
)  # as VS Code's own bin/code.CMD


def _vscode(tmp_path, complete: bool = True) -> Path:
    """A fake VS Code install: bin/code.CMD, and (complete) the Code.exe and cli.js it runs."""
    root = tmp_path / "Microsoft VS Code"
    code = root / "bin" / "code.CMD"
    code.parent.mkdir(parents=True)
    code.write_text(CODE_CMD, encoding="utf-8")
    if complete:
        (root / "Code.exe").write_bytes(b"")
        cli = root / "c4453f8ea4" / "resources" / "app" / "out" / "cli.js"
        cli.parent.mkdir(parents=True)
        cli.write_text("", encoding="utf-8")
    return code


def _cli(code: Path) -> list[str]:
    root = code.parent.parent
    return [
        str(root / "Code.exe"),
        str(root / "c4453f8ea4" / "resources" / "app" / "out" / "cli.js"),
    ]


SAFE = ["D:/书库 Library", "D:/书库 Library/notes/doe-2020-optics/ch01-intro.md"]


def test_vscode_command_keeps_ordinary_paths_as_they_were(tmp_path):
    code = str(_vscode(tmp_path))
    assert ps.vscode_command(code, SAFE, platform="win32") == ([code, *SAFE], None)  # as always
    assert ps.vscode_command(code, [], platform="win32") == ([code], None)
    for platform in ("darwin", "linux"):  # no cmd.exe there: as always, whatever the path
        assert ps.vscode_command("/usr/local/bin/code", ["/R&D %x"], platform) == (
            ["/usr/local/bin/code", "/R&D %x"],
            None,
        )
    shim = str(tmp_path / "code.exe")  # a real program (e.g. a package manager's shim)
    assert ps.vscode_command(shim, ["D:/R&D"], platform="win32") == ([shim, "D:/R&D"], None)


def test_vscode_command_never_hands_cmd_exe_a_special_path(tmp_path, monkeypatch):
    code = _vscode(tmp_path)
    monkeypatch.setenv("VSCODE_DEV", "1")  # code.CMD clears it
    monkeypatch.delenv("ELECTRON_RUN_AS_NODE", raising=False)
    for special in sorted(ps.CMD_SPECIAL):
        args = [f"D:/lib{special}x", f"D:/lib{special}x/notes/a/ch01.md"]
        command, env = ps.vscode_command(str(code), args, platform="win32")
        # What code.CMD runs, without cmd.exe: Code.exe, VS Code's cli.js, the paths as they are
        assert command == [*_cli(code), *args], special
        assert env["ELECTRON_RUN_AS_NODE"] == "1" and "VSCODE_DEV" not in env
        assert env["PATH"] == os.environ["PATH"]  # otherwise this environment
    # The note's path alone can be the special one too
    command, _ = ps.vscode_command(str(code), ["D:/lib", "D:/lib/a%TEMP%.md"], platform="win32")
    assert command[:2] == _cli(code)


def test_vscode_command_never_runs_code_exe_with_a_path_first(tmp_path):
    """Code.exe with ELECTRON_RUN_AS_NODE set (as for programs VS Code starts) runs its first
    argument as a Node.js script: that is always cli.js, never a library path."""
    code = _vscode(tmp_path)
    command, _ = ps.vscode_command(str(code), ["D:/R&D", "D:/R&D/a.md"], platform="win32")
    assert command[1].endswith("cli.js") and command[2:] == ["D:/R&D", "D:/R&D/a.md"]
    # Without Code.exe and cli.js where code.CMD says, or a code.CMD that doesn't say: nothing
    bare = _vscode(tmp_path / "bare", complete=False)
    assert ps.vscode_command(str(bare), ["D:/R&D"], platform="win32") is None
    assert ps.vscode_command(str(bare), SAFE, platform="win32") == ([str(bare), *SAFE], None)
    odd = _vscode(tmp_path / "odd")
    odd.write_text('@"%~dp0..\\Code.exe" %*\n', encoding="utf-8")  # no cli.js named
    assert ps.vscode_command(str(odd), ["D:/R&D"], platform="win32") is None


@pytest.mark.skipif(os.name != "nt", reason="cmd.exe and code.CMD are Windows'")
def test_open_in_editor_with_a_special_library_folder(tmp_path, monkeypatch, launched, capsys):
    code = _vscode(tmp_path)
    started = []
    monkeypatch.setattr(
        library_server.subprocess, "Popen", lambda args, **kw: started.append((args, kw))
    )
    monkeypatch.setattr(library_server.shutil, "which", lambda name: str(code))
    monkeypatch.setattr(paths, "load_settings", lambda: {"editor": "vscode"})
    note = Path("notes/doe-2020-optics/ch01-intro.md")
    for folder, program in (
        ("书库 Library", [str(code)]),  # ordinary: code.CMD, as always
        ("R&D", _cli(code)),  # B28: what code.CMD runs, without cmd.exe
        ("lib%OS%x", _cli(code)),
    ):
        workspace = tmp_path / "libs" / folder
        monkeypatch.setattr(paths, "WORKSPACE", workspace)
        started.clear()
        assert library_server.open_in_editor(workspace / note) is True
        ((args, kw),) = started
        assert args == [*program, str(workspace), str(workspace / note)]
        assert kw["cwd"] == workspace and not kw.get("shell")
        assert (kw["env"] is None) == (program == [str(code)])
    # VS Code not complete: a special folder never reaches code.CMD; the system editor instead,
    # and the server's log says why
    (code.parent.parent / "Code.exe").unlink()
    workspace = tmp_path / "libs" / "R&D"
    monkeypatch.setattr(paths, "WORKSPACE", workspace)
    started.clear()
    assert library_server.open_in_editor(workspace / note) is True
    assert started == [] and launched["startfile"] == [workspace / note]
    logged = capsys.readouterr().out
    assert "VS Code wasn't used" in logged and str(workspace) not in logged  # no paths in it
    # ... and a chapter script there goes to Notepad, never to its default app
    launched["startfile"].clear()
    script = workspace / "examples" / "doe" / "ch01_optics.py"
    assert library_server.open_in_editor(script) is True
    # (Popen is the one subprocess module's: the calls land in `started`)
    assert launched["startfile"] == [] and started[-1][0] == ["notepad.exe", str(script)]


def _short(path: Path) -> str:
    """The path without spaces (Windows' short 8.3 form), as on a drive like D:/Books."""
    import ctypes

    buffer = ctypes.create_unicode_buffer(32768)
    ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, len(buffer))
    return buffer.value or str(path)


@pytest.mark.skipif(os.name != "nt", reason="cmd.exe and code.CMD are Windows'")
def test_the_hazard_itself_is_real_and_avoided(tmp_path):
    """B28, reproduced with a harmless built-in (ver): a batch file given an unquoted path with
    & runs the rest as a command. The command myLibrary now builds never goes through it."""
    import json
    import sys

    root = _short(tmp_path)
    if " " in root:
        pytest.skip("no short path without spaces here")
    logger = Path(root) / "logger.py"
    logger.write_text(
        "import json, sys, pathlib\n"
        "pathlib.Path(sys.argv[1]).write_text(json.dumps(sys.argv[2:]), encoding='utf-8')\n",
        encoding="utf-8",
    )
    log = Path(root) / "args.json"
    code = Path(root) / "vscode" / "bin" / "code.cmd"  # as VS Code's: the program, then %*
    code.parent.mkdir(parents=True)
    code.write_text(f'@"{sys.executable}" "{logger}" "{log}" %*\n', encoding="utf-8")
    library = Path(root) / "lib&ver"
    library.mkdir()

    done = subprocess.run([str(code), str(library)], cwd=library, capture_output=True)
    assert b"Microsoft Windows" in done.stdout  # `ver` ran: the hazard B28 describes
    assert json.loads(log.read_text(encoding="utf-8")) == [str(Path(root) / "lib")]  # cut

    # What open_in_editor would start now: not the batch file (no Code.exe here: nothing)
    assert ps.vscode_command(str(code), [str(library)], platform="win32") is None
    # A program (as Code.exe is) gets such paths as they are: no cmd.exe in between. Python
    # itself stands in for Code.exe here.
    odd = [str(library), str(Path(root) / "lib%OS%x"), str(Path(root) / "lib^x(1)")]
    shown = subprocess.run(
        [sys.executable, "-c", "import json, sys; print(json.dumps(sys.argv[1:]))", *odd],
        cwd=library,
        capture_output=True,
        text=True,
    )
    assert json.loads(shown.stdout) == odd and "Microsoft Windows" not in shown.stdout


# --- B28: custom editor commands on Windows ---------------------------------------------------

windows_only = pytest.mark.skipif(os.name != "nt", reason="CreateProcess and cmd.exe are Windows'")


@pytest.fixture
def editors(tmp_path, monkeypatch):
    """Harmless editor launchers in a temporary folder, some of them on PATH; the current folder
    holds none of them."""
    tools = tmp_path / "tools"
    (tools / "My Tools").mkdir(parents=True)
    for name in ("myedit.cmd", "myedit.bat", "My Tools/myedit.cmd"):
        (tools / name).write_text("@echo off\n", encoding="utf-8")
    (tools / "editor.exe").write_bytes(b"")  # a native program (never actually started here)
    on_path, later = tmp_path / "on path", tmp_path / "later"
    on_path.mkdir()
    later.mkdir()
    (on_path / "pathedit.cmd").write_text("@echo off\n", encoding="utf-8")
    (on_path / "dual.cmd").write_text("@echo off\n", encoding="utf-8")  # PATHEXT finds this
    (later / "dual.exe").write_bytes(b"")  # ... CreateProcess this
    (later / "nativeedit.exe").write_bytes(b"")
    monkeypatch.setenv("PATH", os.pathsep.join([str(on_path), str(later), os.environ["PATH"]]))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    return tools


def _note(tmp_path, folder: str, name: str = "ch01-intro.md") -> Path:
    note = tmp_path / "libs" / folder / "notes" / "doe-2020-optics" / name
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("# Ch 1\n", encoding="utf-8")
    return note


SPECIAL_FOLDERS = ["R&D", "lib%OS%x", "lib^x", "lib(1)", "lib!x", "a&b c"]


def _unsafe_commands(tools: Path) -> list[str]:
    return [
        f'"{tools}\\myedit.cmd"',  # the path appended automatically (in quotes)
        f'"{tools}\\myedit.cmd" {{file}}',  # unquoted
        f'"{tools}\\myedit.cmd" "{{file}}"',  # quoted: % still expands
        f'"{tools}\\myedit.bat" "{{file}}"',
        f'"{tools}\\MYEDIT.CMD" {{file}}',  # any case
        f'"{tools}\\myedit.cmd." {{file}}',  # Windows drops the trailing dot: still the .cmd
        f"{tools}\\My Tools\\myedit.cmd {{file}}",  # unquoted program with a space
        "pathedit.cmd {file}",  # found through PATH
        "pathedit {file}",  # bare: CreateProcess can't find it, PATHEXT finds the .cmd
        "dual {file}",  # bare: dual.exe for CreateProcess, but PATHEXT finds dual.cmd first
        'cmd /c start "" "{file}"',  # cmd.exe itself
        "nosuch.exe {file}",  # can't be found: not assumed to be a program
    ]


@windows_only
@pytest.mark.parametrize("folder", SPECIAL_FOLDERS)
def test_a_batch_editor_never_gets_a_path_cmd_exe_would_act_on(
    editors, tmp_path, folder, launched, capsys
):
    note = _note(tmp_path, folder)
    for command in _unsafe_commands(editors):
        assert ps.cmd_exe_risk(command, note), command
        launched["popen"].clear()
        launched["startfile"].clear()
        ps.open_for_editing(note, "custom", command, platform="win32")
        assert launched["popen"] == [], command  # the launcher never ran
        assert launched["startfile"] == [note], command  # the system editor instead
    logged = capsys.readouterr().out
    assert "custom editor wasn't used for ch01-intro.md" in logged
    assert str(note.parent) not in logged and str(editors) not in logged  # no paths in the log
    assert note.read_text(encoding="utf-8") == "# Ch 1\n"  # the note itself untouched


@windows_only
def test_a_python_script_falls_back_to_notepad_never_its_default_app(editors, tmp_path, launched):
    script = _note(tmp_path, "R&D", "ch01_optics.py")
    ps.open_for_editing(script, "custom", f'"{editors}\\myedit.cmd" "{{file}}"', platform="win32")
    assert launched["startfile"] == [] and launched["popen"] == [(["notepad.exe", str(script)], {})]


@windows_only
def test_safe_custom_editors_run_as_they_always_did(editors, tmp_path, launched):
    special = _note(tmp_path, "R&D")
    plain = _note(tmp_path, "书库 Library")
    allowed = [
        (f'"{editors}\\editor.exe" -n "{{file}}"', special),  # a native program: no cmd.exe
        (f'"{editors}\\editor.exe"', special),
        ("nativeedit {file}", special),  # bare name, native on PATH, no batch with that name
        ("dual.exe {file}", special),  # the extension named: CreateProcess starts the .exe
        (f'"{editors}\\myedit.cmd" "{{file}}"', plain),  # batch, ordinary path: as before
        (f'"{editors}\\myedit.cmd"', plain),
        ("nosuch.exe {file}", plain),  # ordinary path: tried as before (and fails as before)
    ]
    for command, file in allowed:
        assert ps.cmd_exe_risk(command, file) == "", command
        launched["popen"].clear()
        ps.open_for_editing(file, "custom", command, platform="win32")
        assert launched["popen"] == [(ps._custom_command(command, file, "win32"), {})], command
    assert launched["startfile"] == []


@windows_only
def test_a_batch_editor_cannot_run_a_command_from_a_folder_name(tmp_path, monkeypatch):
    """B28 with a real batch editor and a real process: the command line a batch editor would get
    runs a program named in the folder (here a harmless one that writes a marker); open_for_editing
    never starts it, and nothing else runs."""
    import sys

    root = Path(_short(tmp_path))
    if " " in str(root):
        pytest.skip("no short path without spaces here")
    tools = root / "tools"
    tools.mkdir()
    marker = root / "INJECTED.txt"
    (tools / "markprog.cmd").write_text(f'@echo injected> "{marker}"\n', encoding="utf-8")
    log = root / "args.txt"
    editor = tools / "myedit.cmd"
    writer = "import sys; open(sys.argv[1], 'w').write(sys.argv[2])"
    editor.write_text(f'@"{sys.executable}" -c "{writer}" "{log}" %*\n', encoding="utf-8")
    monkeypatch.setenv("PATH", os.pathsep.join([str(tools), os.environ["PATH"]]))
    note = _note(root, "lib&markprog x")  # unquoted {file}: cmd.exe runs "markprog x\notes\..."
    command = f'"{editor}" {{file}}'

    done = subprocess.run(ps._custom_command(command, note, "win32"), capture_output=True)
    assert done.returncode is not None and marker.exists()  # the hazard: markprog ran
    marker.unlink()
    log.unlink(missing_ok=True)

    started, opened = [], []
    real_popen = ps.subprocess.Popen
    monkeypatch.setattr(
        ps.subprocess, "Popen", lambda *a, **k: started.append(a) or real_popen(*a, **k)
    )
    monkeypatch.setattr(ps.os, "startfile", opened.append, raising=False)
    ps.open_for_editing(note, "custom", command, platform="win32")
    assert started == [] and opened == [note]  # nothing was started: the system editor instead
    assert not marker.exists() and not log.exists()
