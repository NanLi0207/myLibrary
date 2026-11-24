"""M7.1 S3, T-R6: settings read in one process while another saves them, for real (atomic
replacements on Windows). A characterization, with mandatory checks: every read either fails
loudly (none may) or holds what is in the file (a persisted sentinel, never the defaults); every
save attempt is made and accounted for at its decision point; the file ends as the last
committed save left it; the reader and writer really overlapped (a shared-memory handshake).
Saves blocked by the readers' open handles (D3, accepted) are counted, not failed.

The suite runs a short version. The characterization runs are longer (S3 evidence):
  MYLIBRARY_STRESS_ATTEMPTS=1500 MYLIBRARY_STRESS_MODE=tight
    uv run pytest tests/test_settings_stress.py -s
"""

import json
import os
import subprocess
import sys
import tomllib
from multiprocessing import shared_memory
from pathlib import Path

import paths
import pytest
import settings_toml

WORKER = Path(__file__).with_name("settings_stress_worker.py")
SEED = (
    "# stress seed: these lines must survive\n"
    "s3_sentinel = 20261123\n"
    "editor = 'vscode'\n"
    "\n"
    "[s3_table]\n"
    "keep = [1, 2.5]\n"
)
ATTEMPTS = int(os.environ.get("MYLIBRARY_STRESS_ATTEMPTS", "150"))
# (the suite: readers at a realistic pace; tight-loop readers, which provoke many D3 blocks, are
# the characterization runs recorded in the S3 evidence)
MODES = [os.environ.get("MYLIBRARY_STRESS_MODE", "light")]
THREADS = 4


@pytest.mark.parametrize("mode", MODES)
def test_reads_during_real_saves_never_fall_back_and_every_save_is_accounted_for(tmp_path, mode):
    settings = tmp_path / "settings.toml"
    settings.write_bytes(SEED.encode())
    env = {k: v for k, v in os.environ.items() if k not in (paths.ENV_VAR, paths.SETTINGS_VAR)}
    env.update({
        "PYTHONPATH": str(paths.APP / "scripts"), paths.SETTINGS_VAR: str(settings),
        paths.ENV_VAR: str(tmp_path / "library"), "USERPROFILE": str(tmp_path / "home"),
        "HOME": str(tmp_path / "home"),
    })  # fmt: skip
    memory = shared_memory.SharedMemory(create=True, size=8 * 4)
    try:
        memory.buf.cast("q")[:] = memoryview(bytes(32)).cast("q")
        run = [sys.executable, str(WORKER)]
        reader = subprocess.Popen(
            [*run, "reader", memory.name, str(THREADS), mode], env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )  # fmt: skip
        writer = subprocess.Popen(
            [*run, "writer", memory.name, str(ATTEMPTS), str(THREADS)], env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )  # fmt: skip
        timeout = 60 + ATTEMPTS
        w_out, w_err = writer.communicate(timeout=timeout)
        r_out, r_err = reader.communicate(timeout=timeout)
    finally:
        memory.close()
        memory.unlink()
    assert writer.returncode == 0, w_err
    assert reader.returncode == 0, r_err
    wrote = json.loads(w_out.strip().splitlines()[-1])
    read = json.loads(r_out.strip().splitlines()[-1])
    final = settings.read_bytes()
    parsed = tomllib.loads(final.decode("utf-8"))
    expected = bytes.fromhex(wrote["last_committed"]) if wrote["last_committed"] else SEED.encode()
    report = {"mode": mode, "writer": wrote | {"last_committed": "..."}, "reader": read,
              "final_is_last_commit": final == expected}  # fmt: skip
    print("\nT-R6 " + json.dumps(report))
    # mandatory: never normalised
    assert wrote["overlap_established"], "the reader and the writer never overlapped"
    assert wrote["completed"] == wrote["planned"] == ATTEMPTS  # (no early stop)
    assert wrote["committed"] + wrote["noop"] + wrote["blocked"] == wrote["completed"]
    assert wrote["unexpected"] == {}
    assert wrote["committed"] >= 1  # (the first attempt differs from the seed)
    assert read["errors"] == {} and read["fallbacks"] == 0
    assert read["good"] == read["attempts"] and read["good"] > 0
    assert final == expected
    assert type(parsed["s3_sentinel"]) is int and parsed["s3_sentinel"] == 20261123
    assert settings_toml.same(parsed["s3_table"], {"keep": [1, 2.5]})
    assert final.decode().startswith("# stress seed: these lines must survive\n")
