"""The browser tests in shards: CI runs them on several Windows runners at once (the suite had
grown close to one runner's time limit). Whole test files go to a shard, never parts of one:

- `--shard k/n` (tests/browser/conftest.py) keeps the files of shard k of n;
- `assign` gives every file exactly one shard, from the collected tests alone (largest file
  first, to the shard with the fewest tests so far; ties by name), so the same checkout always
  splits the same way, and a new test file needs no list to be kept up to date;
- `python tests/browser/shards.py --check N` collects the whole suite and each of the N shards
  and fails unless the shards are a partition of it (nothing left out, nothing twice).
"""

from __future__ import annotations

import subprocess
import sys
from collections import Counter


def parse(value: str) -> tuple[int, int]:
    """'1/2' -> (1, 2); anything else is an error."""
    try:
        k, n = (int(part) for part in value.split("/"))
    except ValueError:
        raise ValueError(f"--shard takes k/n, e.g. 1/2 (got {value!r})") from None
    if not 1 <= k <= n:
        raise ValueError(f"--shard k/n needs 1 <= k <= n (got {value!r})")
    return k, n


def assign(counts: dict[str, int], n: int) -> dict[str, int]:
    """{test file: number of tests} -> {test file: its shard, 1..n}."""
    loads = [0] * n
    shard_of = {}
    for name in sorted(counts, key=lambda f: (-counts[f], f)):
        k = min(range(n), key=lambda i: (loads[i], i))
        shard_of[name] = k + 1
        loads[k] += counts[name]
    return shard_of


def file_of(nodeid: str) -> str:
    return nodeid.split("::", 1)[0]


def select(nodeids: list[str], k: int, n: int) -> list[str]:
    """The tests (node ids) of shard k of n."""
    shard_of = assign(Counter(file_of(i) for i in nodeids), n)
    return [i for i in nodeids if shard_of[file_of(i)] == k]


def _collected(*args: str) -> list[str]:
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/browser", "--collect-only", "-q",
         "-p", "no:cacheprovider", *args],
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout  # fmt: skip
    return [line.strip() for line in out.splitlines() if "::" in line]


def check(n: int) -> None:
    whole = _collected()
    parts = [_collected("--shard", f"{k}/{n}") for k in range(1, n + 1)]
    seen = Counter(i for part in parts for i in part)
    twice = sorted(i for i, c in seen.items() if c > 1)
    missing = sorted(set(whole) - set(seen))
    extra = sorted(set(seen) - set(whole))
    sizes = ", ".join(f"shard {k}: {len(p)}" for k, p in enumerate(parts, 1))
    print(f"browser tests: {len(whole)}; {sizes}")
    if twice or missing or extra or not whole:
        sys.exit(f"not a partition: twice {twice}, missing {missing}, unexpected {extra}")
    print("every test in exactly one shard")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--check":
        sys.exit("usage: python tests/browser/shards.py --check N")
    check(int(sys.argv[2]))
