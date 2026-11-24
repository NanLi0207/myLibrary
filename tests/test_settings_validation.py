"""M7.1 S3: settings are checked as they were sent, before anything is converted, at every
layer: the page's request (POST /api/settings), library_server.change_settings and
paths.save_settings. "false" is not false; nothing invalid is written, asked of OpenAlex,
created or restarted (T-V1..V10). Temporary settings and libraries only."""

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import library_server
import paths
import pytest


@pytest.fixture
def settings(tmp_path, monkeypatch):
    file = tmp_path / "settings.toml"
    file.write_text("# mine\neditor = 'vscode'\nbackup_pdfs = false\n", encoding="utf-8")
    monkeypatch.setattr(paths, "SETTINGS_FILE", file)
    monkeypatch.setattr(paths, "SETTINGS_SOURCE", "explicit")
    return file


@pytest.fixture
def no_network(monkeypatch):
    asked = []
    monkeypatch.setattr(library_server, "check_openalex_key", lambda key: asked.append(key))
    return asked


@pytest.fixture
def restarts(monkeypatch):
    done = []
    monkeypatch.setattr(library_server, "restart_later", lambda server: done.append(1))
    return done


def unchanged(file, call, *args):
    before, when = file.read_bytes(), file.stat().st_mtime_ns
    with pytest.raises(ValueError):
        call(*args)
    assert file.read_bytes() == before and file.stat().st_mtime_ns == when


NOT_BOOLEANS = ["false", "true", 0, 1, None, [], "", 0.0]
NOT_TEXT = [1, None, [], {}, True, 2.5]
TEXT_SETTINGS = ["editor", "editor_command", "openalex_key", "backup_folder", "library"]


@pytest.mark.parametrize("key", ["backup_pdfs", "python_features"])
@pytest.mark.parametrize("value", NOT_BOOLEANS)
def test_switches_take_true_or_false_only(settings, key, value, no_network):
    """T-V1, T-V8: the page's API and the backend both refuse anything but a real boolean
    (Codex: "false" used to be stored as true)."""
    unchanged(settings, library_server.change_settings, {key: value})
    unchanged(settings, paths.save_settings, {key: value})


@pytest.mark.parametrize("key", TEXT_SETTINGS)
@pytest.mark.parametrize("value", NOT_TEXT)
def test_text_settings_take_text_only(settings, key, value, no_network):
    """T-V2."""
    unchanged(settings, library_server.change_settings, {key: value})
    unchanged(settings, paths.save_settings, {key: value})
    assert no_network == []


def test_unknown_settings_are_refused(settings):
    """T-V3: a key the page doesn't have is refused (it used to be dropped silently)."""
    unchanged(settings, library_server.change_settings, {"colour": "blue"})
    unchanged(settings, library_server.change_settings, {"editor": "system", "zoom": 3})
    unchanged(settings, paths.save_settings, {"zoom": 3})


def test_the_library_cant_be_cleared(settings, tmp_path, monkeypatch):
    """T-V4: an empty library is refused (it used to be ignored); the current one: no write."""
    for empty in ("", "   "):
        unchanged(settings, library_server.change_settings, {"library": empty})
        unchanged(settings, paths.save_settings, {"library": empty})
    monkeypatch.setattr(library_server, "LIBRARY", tmp_path)
    before = settings.stat().st_mtime_ns
    assert library_server.change_settings({"library": str(tmp_path)}) == {"restart": False}
    assert settings.stat().st_mtime_ns == before


def test_optional_settings_can_be_cleared(settings):
    """T-V5: clearing the editor command, the OpenAlex key or the backup folder saves ""."""
    settings.write_text(
        "editor_command = 'code {file}'\nopenalex_key = 'abcdefgh1'\nbackup_folder = 'D:/B'\n",
        encoding="utf-8",
    )
    library_server.change_settings({"editor_command": "", "openalex_key": "", "backup_folder": ""})
    assert paths.load_settings() | {} == paths.SETTINGS_DEFAULTS | {
        "editor_command": "", "openalex_key": "", "backup_folder": "",
    }  # fmt: skip


def test_an_editor_command_too_long_is_refused_not_cut(settings):
    """T-V6: over 500 characters: refused (it used to be cut short silently); 500 is fine."""
    unchanged(settings, library_server.change_settings, {"editor_command": "x" * 501})
    library_server.change_settings({"editor_command": "x" * 500})
    assert paths.load_settings()["editor_command"] == "x" * 500


def test_editor_and_openalex_checks_are_as_before(settings, no_network):
    """T-V7: the editor must be one of the four; an OpenAlex key must look like one and is
    checked online only when it changes."""
    unchanged(settings, library_server.change_settings, {"editor": "emacs"})
    unchanged(settings, library_server.change_settings, {"openalex_key": "no!"})
    library_server.change_settings({"openalex_key": " abcdefgh12 "})
    library_server.change_settings({"openalex_key": "abcdefgh12"})
    assert no_network == ["abcdefgh12"]
    assert paths.load_settings()["openalex_key"] == "abcdefgh12"


def test_a_refused_request_asks_nothing_and_creates_nothing(settings, tmp_path, no_network):
    """T-V10: any invalid setting in a request: OpenAlex isn't asked, no library is created,
    even when the invalid setting comes after them."""
    new_library = tmp_path / "new library"
    for request in (
        {"openalex_key": "abcdefgh99", "library": "relative/path"},
        {"library": str(new_library), "editor": "emacs"},
        {"library": str(new_library), "backup_folder": "relative"},
        {"openalex_key": "abcdefgh99", "backup_pdfs": "false"},
    ):
        unchanged(settings, library_server.change_settings, request)
    assert no_network == [] and not new_library.exists()


def _server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def post(body):
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/settings", method="POST",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "X-Library-Token": library_server.TOKEN},
        )  # fmt: skip
        try:
            with urllib.request.urlopen(request, timeout=30) as answer:
                return answer.status, json.load(answer)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    return server, post


def test_the_page_request_is_checked_as_sent(settings, restarts, no_network):
    """T-V9: raw JSON through POST /api/settings: "false", a list for `save`, a body that
    isn't an object: 400, nothing written; a valid request still works."""
    server, post = _server()
    before = settings.read_bytes()
    try:
        for body in (
            {"save": {"backup_pdfs": "false"}}, {"save": {"python_features": 0}},
            {"save": []}, {"save": "editor=notepad"}, {"save": None}, {"save": {"zoom": 3}},
            [1, 2],
        ):  # fmt: skip
            status, answer = post(body)
            assert status == 400 and answer["error"], body
            assert settings.read_bytes() == before
        status, answer = post({"save": {"backup_pdfs": True}})
        assert status == 200 and answer == {"restart": False}
        assert paths.load_settings()["backup_pdfs"] is True and restarts == []
    finally:
        server.shutdown()


def test_a_failed_save_after_making_a_new_library_doesnt_restart(
    settings, tmp_path, restarts, monkeypatch
):
    """T-V10: the new library folder is made (outside the settings locks), then the save is
    refused (busy): an error, no restart, settings unchanged; the empty new library stays."""

    def busy(updates):
        raise paths.SettingsBusy("The settings are being saved by another myLibrary window")

    monkeypatch.setattr(paths, "save_settings", busy)
    server, post = _server()
    before = settings.read_bytes()
    new_library = tmp_path / "next library"
    try:
        status, answer = post({"save": {"library": str(new_library)}})
    finally:
        server.shutdown()
    assert status == 400 and "another myLibrary window" in answer["error"]
    assert restarts == [] and settings.read_bytes() == before
    assert (new_library / "library.toml").is_file()
