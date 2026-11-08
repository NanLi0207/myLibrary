"""The browser tests' own safety nets: a stuck test is stopped by the per-test limit
(pyproject.toml, faulthandler_timeout + faulthandler_exit_on_timeout), and the processes a test
run owns (owned_processes: its myLibrary test servers) never outlive it, whether it ends
normally or is killed."""

import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

HERE = Path(__file__).parent
ROOT = HERE.parent.parent

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="job objects are Windows'")


def alive(pid: int) -> bool:
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                         capture_output=True, text=True).stdout  # fmt: skip
    return str(pid) in out


def wait_gone(pid: int, seconds: float = 15) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if not alive(pid):
            return True
        time.sleep(0.2)
    return not alive(pid)


def owner_script(tmp_path: Path, then: str) -> Path:
    """A small program that starts a long-running child through owned_processes (as the test
    servers are started), prints the child's pid, then does `then`."""
    script = tmp_path / "owner.py"
    script.write_text(
        textwrap.dedent(f"""
        import sys, time
        sys.path.insert(0, {str(HERE)!r})
        import owned_processes
        child = owned_processes.start([sys.executable, "-c", "import time; time.sleep(120)"])
        print(child.pid, flush=True)
        {then}
    """),
        encoding="utf-8",
    )
    return script


@windows_only
@pytest.mark.parametrize("ending", ["normal exit", "killed"])
def test_an_owned_process_never_outlives_the_test_run(tmp_path, ending):
    # The owner waits for a line before ending normally, so the child is seen alive first
    then = "sys.stdin.readline()" if ending == "normal exit" else "time.sleep(120)"
    owner = subprocess.Popen([sys.executable, str(owner_script(tmp_path, then))],
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, text=True)  # fmt: skip
    child = int(owner.stdout.readline())
    assert alive(child)
    if ending == "killed":
        subprocess.run(["taskkill", "/F", "/PID", str(owner.pid)], capture_output=True)
    else:
        owner.stdin.write("end\n")  # it ends normally, without stopping its child
        owner.stdin.flush()
    owner.wait(30)
    assert wait_gone(child), f"pid {child} outlived its owner ({ending})"


@windows_only
def test_only_what_it_starts_is_owned(tmp_path):
    """Our own process isn't put in the job: ending the owner leaves this test running."""
    owner = subprocess.Popen([sys.executable, str(owner_script(tmp_path, "pass"))],
                             stdout=subprocess.PIPE, text=True)  # fmt: skip
    child = int(owner.stdout.readline())
    owner.wait(30)
    assert wait_gone(child) and alive(owner.pid) is False
    assert alive(__import__("os").getpid())  # this process, untouched


def test_a_stuck_test_is_stopped_by_the_per_test_limit(tmp_path):
    """A test that never ends is stopped after the limit (here 3 s instead of 180 s), with the
    stacks printed: the run doesn't wait for it."""
    (tmp_path / "test_stuck.py").write_text(
        "import time\n\ndef test_stuck():\n    time.sleep(600)\n", encoding="utf-8"
    )
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\nfaulthandler_timeout = 3\nfaulthandler_exit_on_timeout = true\n",
        encoding="utf-8",
    )
    start = time.monotonic()
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-p",
            "no:playwright",
            str(tmp_path / "test_stuck.py"),
        ],  # fmt: skip
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
    )
    took = time.monotonic() - start
    assert run.returncode != 0 and took < 60, (run.returncode, took)
    assert "Timeout (0:00:03)!" in run.stderr + run.stdout
    assert "test_stuck" in run.stderr + run.stdout  # which test, and where


def test_the_project_sets_the_per_test_limit():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "faulthandler_timeout = 180" in text and "faulthandler_exit_on_timeout = true" in text
