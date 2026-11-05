import paths


def test_which_library(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "APP", tmp_path / "tool")
    monkeypatch.setattr(paths, "LOCAL_SETTINGS", tmp_path / "tool" / "local.toml")
    monkeypatch.delenv(paths.ENV_VAR, raising=False)
    (tmp_path / "tool").mkdir()

    # Nothing chosen: the default place
    assert paths._resolve([]) == (paths.DEFAULT_LIBRARY, "default")
    # local.toml, relative to the tool's folder
    paths.LOCAL_SETTINGS.write_text('library = "library"\n', encoding="utf-8")
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
    monkeypatch.setattr(paths, "LOCAL_SETTINGS", tmp_path / "local.toml")

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
