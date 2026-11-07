"""The test server's port (conftest.Server): always one browsers accept, chosen again when a
start fails, a bounded number of times, and no failed start left running. Ports are given
here in a known order, rather than waiting for Windows to hand out a blocked one."""

import socket
import subprocess

import conftest
import pytest
from conftest import Server, browser_safe, random_ports


def free_safe_port(taken=()) -> int:
    for port in random_ports():
        if port in taken:
            continue
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
        return port


def occupy(port: int) -> socket.socket:
    """Another program holding the port (bound, not answering)."""
    holder = socket.socket()
    holder.bind(("127.0.0.1", port))
    return holder


def start(library, tmp_path, ports) -> Server:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return Server(library, home, wait_for_index=False, ports=ports)


def all_ended(processes) -> bool:
    return all(p.poll() is not None for p in processes)


def test_ports_browsers_refuse_are_never_chosen():
    for blocked in (2049, 6000, 6667, 10080, 1, 0):  # NFS, X11, IRC, Amanda, ...
        assert not browser_safe(blocked)
    assert browser_safe(49152) and browser_safe(65535) and not browser_safe(65536)
    ports = random_ports()
    assert all(browser_safe(next(ports)) for _ in range(1000))


def test_a_blocked_port_is_passed_over_for_a_safe_one(library, tmp_path, page):
    safe = free_safe_port()
    server = start(library, tmp_path, [2049, safe])
    try:
        assert server.port == safe and server.base == f"http://127.0.0.1:{safe}"
        assert len(server.attempts) == 1  # 2049 was never even started
        assert page.goto(server.base + "/").ok  # Edge opens it
    finally:
        server.stop()
    assert all_ended(server.attempts)


def test_an_occupied_port_is_left_for_another(library, tmp_path):
    taken = free_safe_port()
    holder = occupy(taken)
    safe = free_safe_port({taken})
    try:
        server = start(library, tmp_path, [taken, safe])
        try:
            assert server.port == safe
            failed, running = server.attempts
            assert failed.poll() is not None  # the failed start was ended, not left behind
            assert running.poll() is None
            assert any(f"Port {taken} is used by another program" in line for line in server.lines)
        finally:
            server.stop()
        assert all_ended(server.attempts)
    finally:
        holder.close()


def test_the_attempts_are_limited_and_none_is_left_running(library, tmp_path, monkeypatch):
    monkeypatch.setattr(conftest, "START_ATTEMPTS", 3)
    started = []
    real = subprocess.Popen

    def popen(*args, **kwargs):  # records every server process the attempts start
        process = real(*args, **kwargs)
        started.append(process)
        return process

    monkeypatch.setattr(conftest.subprocess, "Popen", popen)
    taken = free_safe_port()
    holder = occupy(taken)
    safe = free_safe_port({taken})
    try:
        # 3 attempts: 2049 (refused, not started), then the taken port twice; never `safe`
        with pytest.raises(pytest.fail.Exception, match="didn't start in 3 attempts") as failed:
            start(library, tmp_path, [2049, taken, taken, safe])
    finally:
        holder.close()
    assert "2049: refused by browsers" in str(failed.value)
    assert len(started) == 2 and all_ended(started)
