"""Opening and switching libraries: one server per library, a running one reused, never a
server of another library; the canonical Test & Demo library refused; the launcher's two-level
menu; the page's library API; the old commands unchanged. Temporary libraries only; every
server started here is stopped (Quit) at the end of its test."""

import json
import re
import subprocess
import sys
import threading
import time
import urllib.request

import launch_library
import libraries
import library_server
import paths
import pytest
from test_libraries import own_registry, personal_copy, snapshot  # noqa: F401 (the fixture)

SERVER = paths.APP / "scripts" / "library_server.py"


@pytest.fixture
def servers(monkeypatch):
    """Servers started without downloads; every one still running at the end is quit."""
    monkeypatch.setattr(libraries, "SERVER_ARGS", ["--no-download"])
    started: list[int] = []
    yield started
    for port in started:
        quit_server(port)


def quit_server(port: int) -> None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10) as page:
            token = re.search(r'"token": "([^"]+)"', page.read().decode("utf-8"))[1]
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/quit", data=b"{}", method="POST",
            headers={"X-Library-Token": token, "Content-Type": "application/json"},
        )  # fmt: skip
        urllib.request.urlopen(request, timeout=10).close()
    except OSError:
        return
    for _ in range(80):
        if libraries.port_free(port):
            return
        time.sleep(0.25)


def free_ports(n: int) -> list[int]:
    found = [p for p in reversed(libraries.PORTS) if libraries.port_free(p)][:n]
    assert len(found) == n
    return found


def port_of(url: str) -> int:
    return int(re.search(r":(\d+)/", url)[1])


def test_a_server_says_which_library_it_shows(tmp_path, servers):
    library = personal_copy(tmp_path / "书库 A")
    (port,) = free_ports(1)
    libraries.start_server(library, port)
    servers.append(port)
    assert libraries.same_place(libraries.server_at(port), library)
    assert libraries.find_server(library) == port
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/whoami", timeout=10) as r:
        about = json.load(r)
    assert about["id"] == libraries.info(library)["id"] and about["test"] is False


def test_switching_reuses_a_running_server_and_never_opens_another_library(tmp_path, servers):
    one = personal_copy(tmp_path / "one")
    two = personal_copy(tmp_path / "two")
    first, spare = free_ports(2)
    libraries.start_server(one, first)
    servers.append(first)
    assert port_of(libraries.open_library(one, spare)) == first  # already open: reused
    assert libraries.port_free(spare)
    url = libraries.open_library(two, first)  # its port shows library one: another port
    servers.append(port_of(url))
    assert port_of(url) != first
    assert libraries.same_place(libraries.server_at(port_of(url)), two)
    assert libraries.same_place(libraries.server_at(first), one)  # still running as it was


def test_a_second_start_on_another_port_opens_the_running_one(tmp_path, servers):
    library = personal_copy(tmp_path / "lib")
    first, second = free_ports(2)
    libraries.start_server(library, first)
    servers.append(first)
    done = subprocess.run(
        [sys.executable, str(SERVER), "--library", str(library), "--port", str(second),
         "--no-browser", "--no-download"],
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    assert f":{first}" in done.stdout and "already shows this library" in done.stdout
    assert libraries.port_free(second)  # no second server writing the same library


def test_the_canonical_test_library_is_never_served():
    before = snapshot(libraries.TEST_CANONICAL)
    (port,) = free_ports(1)
    done = subprocess.run(
        [sys.executable, str(SERVER), "--library", str(libraries.TEST_CANONICAL),
         "--port", str(port), "--no-browser", "--no-download"],
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )  # fmt: skip
    assert done.returncode != 0 and "canonical Test & Demo library" in done.stderr
    assert libraries.port_free(port)
    assert snapshot(libraries.TEST_CANONICAL) == before


def test_test_mode_opens_the_working_copy(servers):
    url = libraries.open_test()
    servers.append(port_of(url))
    assert libraries.same_place(libraries.server_at(port_of(url)), libraries.TEST_WORKING)


def test_the_launcher_menu_has_two_levels(tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr(libraries, "open_personal", lambda key: opened.append(key) or "u1")
    monkeypatch.setattr(libraries, "open_test", lambda: opened.append("test") or "u2")
    existing = personal_copy(tmp_path / "existing", name="Existing")
    answers = iter([
        "1",  # 私人书库 (Personal Libraries)
        "a", str(existing), "", "y",  # add an existing library
        "n", str(tmp_path / "新 library"), "Biology",  # create one
        "b",  # back to the modes
        "1", "2",  # personal again: open the second one
    ])  # fmt: skip
    said = []
    assert launch_library.choose(lambda _: next(answers), said.append) == "u1"
    listed = libraries.personal()
    assert [e["label"] for e in listed] == ["Existing", "Biology"]
    assert opened == [listed[1]["key"]]
    assert any("选择书库模式 (Choose a Library Mode)" in line for line in said)
    answers = iter(["2", "o"])
    assert launch_library.choose(lambda _: next(answers), said.append) == "u2"
    assert opened[-1] == "test"
    answers = iter(["q"])
    assert launch_library.choose(lambda _: next(answers), said.append) is None


def test_the_page_api_lists_registers_and_reports_errors(tmp_path):
    library = personal_copy(tmp_path / "lib", name="API")
    listed = library_server.libraries_api("/api/libraries", {})
    assert listed["personal"] == [] and listed["test_available"] is True
    assert listed["current"]["mode"] == "personal"
    checked = library_server.libraries_api("/api/libraries/check", {"folder": str(library)})
    assert checked["check"]["ok"]
    added = library_server.libraries_api(
        "/api/libraries/register", {"folder": str(library), "label": "Physics"}
    )["library"]
    again = library_server.libraries_api("/api/libraries/register", {"folder": str(library)})
    assert "already on the list" in again["error"]
    gone = library_server.libraries_api("/api/libraries/unregister", {"key": added["key"]})
    assert gone["library"]["label"] == "Physics" and library.is_dir()
    with pytest.raises(ValueError):
        library_server.libraries_api("/api/libraries/delete-everything", {})


def test_settings_never_make_the_test_library_the_default(tmp_path):
    working = libraries.test_library()
    for folder in (working, libraries.TEST_CANONICAL):
        with pytest.raises(ValueError, match="Test & Demo"):
            library_server.change_settings({"library": str(folder)})


# --- one server per library, also when started at the same moment (L15) ----------------------


def test_the_library_lock_is_exclusive_and_never_left_behind(tmp_path):
    library = personal_copy(tmp_path / "lib")
    held = libraries.hold_library(library)
    assert held is not None
    assert libraries.hold_library(library) is None  # (another handle: as another process)
    held.close()
    again = libraries.hold_library(library)
    assert again is not None  # the marker file stays; nothing stale blocks
    again.close()
    holder = subprocess.Popen(
        [sys.executable, "-c", (
            "import sys, time; sys.path.insert(0, sys.argv[1]); import libraries; "
            "lock = libraries.hold_library(libraries.Path(sys.argv[2])); "
            "print('held', flush=True); "
            "time.sleep(120)"
        ), str(paths.APP / "scripts"), str(library)],
        stdout=subprocess.PIPE, text=True,
    )  # fmt: skip
    try:
        assert holder.stdout.readline().strip() == "held"
        assert libraries.hold_library(library) is None
    finally:
        holder.kill()  # as a crash or Task Manager: no clean shutdown
        holder.wait(30)
    # Windows lets go of a dead process's locks a moment later ("depends upon available
    # system resources", LockFileEx): never left behind, but not always at once (the server
    # keeps trying for a minute, hold_or_find)
    deadline = time.monotonic() + 10
    while (after_crash := libraries.hold_library(library)) is None:
        assert time.monotonic() < deadline, "the dead holder's lock was never released"
        time.sleep(0.1)
    after_crash.close()


def test_simultaneous_launches_share_one_server(tmp_path, servers):
    """Four launchers (the page, the .cmd, two terminals) open the same library at the same
    moment, each with its own port: one server, and all of them get its address."""
    library = personal_copy(tmp_path / "lib")
    ports = free_ports(4)
    start = threading.Barrier(4)
    results: list = [None] * 4

    def launch(n: int) -> None:
        start.wait()
        try:
            results[n] = libraries.open_library(library, ports[n])
        except Exception as e:  # (reported below)
            results[n] = e

    threads = [threading.Thread(target=launch, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(180)
    serving = [p for p in ports if not libraries.port_free(p)]
    servers.extend(serving)
    assert all(isinstance(r, str) for r in results), results
    assert len(set(results)) == 1 and len(serving) == 1
    assert port_of(results[0]) == serving[0]
    assert libraries.same_place(libraries.server_at(serving[0]), library)


def test_servers_started_at_once_give_way_to_one(tmp_path, servers):
    """library_server.py started three times at once on three ports: one serves, the others
    open it and end; none runs the library's start-up work beside it."""
    library = personal_copy(tmp_path / "lib")
    ports = free_ports(3)
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                str(SERVER),
                "--library",
                str(library),
                "--port",
                str(port),
                "--no-browser",
                "--no-download",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
        )  # fmt: skip
        for port in ports
    ]
    try:
        deadline = time.monotonic() + 120
        while sum(p.poll() is not None for p in processes) < 2 and time.monotonic() < deadline:
            time.sleep(0.25)
        ended = [p for p in processes if p.poll() is not None]
        assert len(ended) == 2, "two of three must give way"
        for p in ended:
            assert p.returncode == 0 and "already shows this library" in p.stdout.read()
        serving = [port for port in ports if not libraries.port_free(port)]
        servers.extend(serving)
        assert len(serving) == 1
        assert libraries.find_server(library) == serving[0]
    finally:
        for p in processes:
            if p.poll() is None and not servers:
                p.kill()


def test_different_libraries_start_at_once_independently(tmp_path, servers):
    one, two = personal_copy(tmp_path / "one"), personal_copy(tmp_path / "two")
    first, second = free_ports(2)
    results = {}
    threads = [
        threading.Thread(target=lambda: results.update(one=libraries.open_library(one, first))),
        threading.Thread(target=lambda: results.update(two=libraries.open_library(two, first))),
    ]  # (the same suggested port: one of them must move to another)
    for t in threads:
        t.start()
    for t in threads:
        t.join(180)
    servers.extend(port_of(u) for u in results.values())
    assert set(results) == {"one", "two"} and results["one"] != results["two"]
    assert libraries.same_place(libraries.server_at(port_of(results["one"])), one)
    assert libraries.same_place(libraries.server_at(port_of(results["two"])), two)
    assert second  # (a second free port existed for the move)


def test_a_server_on_an_unusual_port_is_found_through_its_note(tmp_path, servers):
    library = personal_copy(tmp_path / "lib")
    unusual = next(p for p in range(49200, 49300) if libraries.port_free(p))
    process = subprocess.Popen(
        [sys.executable, str(SERVER), "--library", str(library), "--port", str(unusual),
         "--no-browser", "--no-download"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )  # fmt: skip
    servers.append(unusual)
    deadline = time.monotonic() + 60
    while libraries.server_at(unusual) is None and time.monotonic() < deadline:
        assert process.poll() is None
        time.sleep(0.25)
    (spare,) = free_ports(1)
    assert libraries.open_library(library, spare) == f"http://127.0.0.1:{unusual}/"
    assert libraries.port_free(spare)
