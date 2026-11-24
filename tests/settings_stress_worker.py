"""The two processes of the settings stress characterization (T-R6, tests/test_settings_stress.py):
a writer saving settings and a reader process with several threads reading them, at the same
time, on a temporary settings file (MYLIBRARY_SETTINGS) only.

They coordinate through one block of shared memory (never through when output is read):
  WINDOW        the attempt whose save_settings call is in progress (1-based), 0 between calls
  READY         reader threads that have made their first good read
  SYNC_DONE     1 once a reader made a whole read while attempt 1 was in progress
  WRITER_DONE   1 once the writer has made every attempt
Each process prints one JSON line of results at the end.

usage: settings_stress_worker.py writer <shared memory> <attempts> <reader threads>
       settings_stress_worker.py reader <shared memory> <threads> light|tight
"""

import json
import sys
import threading
import time
from multiprocessing import shared_memory

import paths
import settings_toml

WINDOW, READY, SYNC_DONE, WRITER_DONE = range(4)
SLOTS = 4
SENTINEL = ("s3_sentinel", 20261123)
TABLE = {"keep": [1, 2.5]}
EDITORS = ("notepad", "system", "vscode")  # (the seed has vscode: the first attempt differs)
SYNC_WAIT = 30


def _slots(name):
    memory = shared_memory.SharedMemory(name=name)
    return memory, memory.buf.cast("q")


def planned_value(attempt: int, previous: str) -> str:
    """Every fourth attempt repeats the previous value (a no-op candidate)."""
    if attempt % 4 == 0:
        return previous
    return EDITORS[(attempt - 1 - attempt // 4) % len(EDITORS)]


def writer(name: str, attempts: int, readers: int) -> dict:
    memory, slots = _slots(name)
    outcomes: list[tuple[str, object]] = []
    paths._on_settings_outcome = lambda kind, data=None: outcomes.append((kind, data))
    overlap = {"established": False}

    def before_publish():  # attempt 1 waits, with both locks held, for a whole read meanwhile
        if slots[WINDOW] != 1:
            return
        deadline = time.monotonic() + SYNC_WAIT
        while time.monotonic() < deadline:
            if slots[SYNC_DONE]:
                overlap["established"] = True
                return
            time.sleep(0.001)

    paths._on_before_publish = before_publish
    deadline = time.monotonic() + SYNC_WAIT
    while slots[READY] < readers and time.monotonic() < deadline:
        time.sleep(0.001)
    counts = {"committed": 0, "noop": 0, "blocked": 0}
    unexpected: dict[str, int] = {}
    last_committed = None
    completed = 0
    previous = "vscode"
    for attempt in range(1, attempts + 1):
        value = planned_value(attempt, previous)
        previous = value
        start = len(outcomes)
        slots[WINDOW] = attempt
        try:
            paths.save_settings({"editor": value})
            returned, error = True, None
        except Exception as e:  # (classified below, never hidden)
            returned, error = False, e
        finally:
            slots[WINDOW] = 0
        completed += 1
        mine = outcomes[start:]
        kinds = [kind for kind, _ in mine]
        if returned and kinds == ["committed"]:
            counts["committed"] += 1
            last_committed = mine[0][1]
        elif returned and kinds == ["noop"]:
            counts["noop"] += 1
        elif isinstance(error, paths.SettingsBlocked) and kinds == ["blocked"]:
            counts["blocked"] += 1
        else:
            what = f"{type(error).__name__ if error else 'returned'}:{','.join(kinds) or 'none'}"
            unexpected[what] = unexpected.get(what, 0) + 1
    slots[WRITER_DONE] = 1
    result = {
        "planned": attempts, "completed": completed, **counts, "unexpected": unexpected,
        "overlap_established": overlap["established"],
        "last_committed": last_committed.hex() if last_committed is not None else None,
    }  # fmt: skip
    slots.release()
    memory.close()
    return result


def reader(name: str, threads: int, mode: str) -> dict:
    memory, slots = _slots(name)
    lock = threading.Lock()
    totals = {
        "attempts": 0,
        "good": 0,
        "fallbacks": 0,
        "errors": {},
        "in_window": [],
        "spanning": [],
    }
    allowed = {"vscode", *EDITORS}

    def good(settings: dict) -> bool:
        return (
            type(settings.get(SENTINEL[0])) is int
            and settings[SENTINEL[0]] == SENTINEL[1]
            and settings.get("editor") in allowed
            and settings_toml.same(settings.get("s3_table"), TABLE)
        )

    def run():
        in_window = spanning = 0
        attempts = goods = fallbacks = 0
        errors: dict[str, int] = {}
        first = True
        while first or not slots[WRITER_DONE]:
            before = slots[WINDOW]
            attempts += 1
            try:
                settings = paths.load_settings()
            except Exception as e:
                errors[type(e).__name__] = errors.get(type(e).__name__, 0) + 1
                settings = None
            after = slots[WINDOW]
            if settings is not None:
                if good(settings):
                    goods += 1
                else:
                    fallbacks += 1
            if before and before == after:
                in_window += 1
                if before == 1 and settings is not None:
                    slots[SYNC_DONE] = 1
            elif before != after:
                spanning += 1
            if first:
                first = False
                with lock:
                    slots[READY] += 1
            if mode == "light":
                time.sleep(0.005)
        with lock:
            totals["attempts"] += attempts
            totals["good"] += goods
            totals["fallbacks"] += fallbacks
            for k, v in errors.items():
                totals["errors"][k] = totals["errors"].get(k, 0) + v
            totals["in_window"].append(in_window)
            totals["spanning"].append(spanning)

    workers = [threading.Thread(target=run) for _ in range(threads)]
    for w in workers:
        w.start()
    for w in workers:
        w.join()
    slots.release()
    memory.close()
    return totals


if __name__ == "__main__":
    role, shm = sys.argv[1], sys.argv[2]
    if role == "writer":
        out = writer(shm, int(sys.argv[3]), int(sys.argv[4]))
    else:
        out = reader(shm, int(sys.argv[3]), sys.argv[4])
    print(json.dumps(out), flush=True)
