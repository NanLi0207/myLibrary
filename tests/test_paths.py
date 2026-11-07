import paths
import pytest


def test_which_library(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "APP", tmp_path / "tool")
    monkeypatch.setattr(paths, "SETTINGS_FILE", tmp_path / "tool" / "local.toml")
    monkeypatch.delenv(paths.ENV_VAR, raising=False)
    (tmp_path / "tool").mkdir()

    # Nothing chosen: the default place
    assert paths._resolve([]) == (paths.DEFAULT_LIBRARY, "default")
    # local.toml, relative to the tool's folder
    paths.SETTINGS_FILE.write_text('library = "library"\n', encoding="utf-8")
    assert paths._resolve([]) == ((tmp_path / "tool" / "library").resolve(), "local.toml")
    # the environment variable wins over local.toml
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path / "env-lib"))
    assert paths._resolve([]) == ((tmp_path / "env-lib").resolve(), paths.ENV_VAR)
    # --library wins over everything, in both spellings
    for argv in (["--library", str(tmp_path / "cli")], [f"--library={tmp_path / 'cli'}"]):
        assert paths._resolve(argv) == ((tmp_path / "cli").resolve(), "--library")


def test_first_start_creates_and_remembers_a_library(tmp_path, monkeypatch):
    library = tmp_path / "My Library"
    monkeypatch.setattr(paths, "LIBRARY", library)
    monkeypatch.setattr(paths, "LIBRARY_SOURCE", "default")
    monkeypatch.setattr(paths, "SETTINGS_FILE", tmp_path / "local.toml")

    paths.ensure_library()
    for sub in ("books", "notes/topics", "glossaries", "examples"):
        assert (library / sub).is_dir()
    assert "[shelves]" in (library / "library.toml").read_text(encoding="utf-8")
    # remembered, so the next start opens the same library
    monkeypatch.setattr(paths, "APP", tmp_path)
    assert paths._resolve([]) == (library.resolve(), "local.toml")

    # A library chosen explicitly is never written into local.toml
    (tmp_path / "local.toml").unlink()
    monkeypatch.setattr(paths, "LIBRARY_SOURCE", "--library")
    paths.ensure_library()
    assert not (tmp_path / "local.toml").exists()


def test_settings_saved_with_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "SETTINGS_FILE", tmp_path / "settings.toml")
    defaults = paths.load_settings()
    assert defaults["editor"] in paths.EDITORS and "library" not in defaults

    saved = paths.save_settings(
        {"editor": "custom", "editor_command": r'"C:\Tools\Typora.exe" "{file}"'}
    )
    assert saved["editor"] == "custom"
    paths.save_settings({"library": "D:/Study/My Library", "python_features": False})
    again = paths.load_settings()  # read back from the file: Windows paths and quotes survive
    assert again["editor_command"] == r'"C:\Tools\Typora.exe" "{file}"'
    assert again["library"] == "D:/Study/My Library" and again["python_features"] is False
    with pytest.raises(ValueError):
        paths.save_settings({"editor": "emacs"})
    with pytest.raises(ValueError):
        paths.save_settings({"colour": "blue"})


# --- MYLIBRARY_SETTINGS: another settings file (tests, a desktop wrapper) ---------------------


def _paths_in_subprocess(tmp_path, settings: str | None):
    """Import paths in a fresh Python with MYLIBRARY_SETTINGS set (or not): the variable is
    read at import, before anything else could read the usual settings."""
    import os
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items() if k not in (paths.ENV_VAR, paths.SETTINGS_VAR)}
    env["PYTHONPATH"] = str(paths.APP / "scripts")
    if settings is not None:
        env[paths.SETTINGS_VAR] = settings
    code = "import paths; print(paths.SETTINGS_FILE); print(paths.LIBRARY)"
    return subprocess.run(
        [sys.executable, "-c", code], env=env, cwd=tmp_path, capture_output=True, text=True
    )


def test_a_settings_file_named_by_the_environment(tmp_path):
    real = paths.APP / "local.toml"
    before = real.stat().st_mtime_ns if real.exists() else None
    settings = tmp_path / "settings.toml"
    settings.write_text(f"library = '{(tmp_path / 'lib').as_posix()}'\n", encoding="utf-8")
    run = _paths_in_subprocess(tmp_path, str(settings))
    assert run.returncode == 0, run.stderr
    file, library = run.stdout.splitlines()
    assert file == str(settings.resolve()) and library == str((tmp_path / "lib").resolve())
    # relative to where the program starts
    run = _paths_in_subprocess(tmp_path, "settings.toml")
    assert run.stdout.splitlines()[0] == str(settings.resolve())
    assert (real.stat().st_mtime_ns if real.exists() else None) == before  # not touched


def test_a_missing_settings_file_stops_instead_of_using_the_usual_one(tmp_path):
    for named in (tmp_path / "nowhere.toml", tmp_path):  # missing, or a folder
        run = _paths_in_subprocess(tmp_path, str(named))
        assert run.returncode != 0 and run.stdout == ""
        assert paths.SETTINGS_VAR in run.stderr and "doesn't exist" in run.stderr


def test_without_the_variable_the_usual_settings_file(tmp_path):
    run = _paths_in_subprocess(tmp_path, None)
    assert run.returncode == 0, run.stderr
    assert run.stdout.splitlines()[0] == str(paths.APP / "local.toml")
