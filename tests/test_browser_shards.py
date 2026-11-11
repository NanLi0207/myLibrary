"""The browser tests' shards (tests/browser/shards.py): whole files, every file in exactly one
shard, the same split from the same tests, balanced by the number of tests. (CI also checks the
real collected suite with `shards.py --check` before each shard runs.)"""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "shards", Path(__file__).parent / "browser" / "shards.py"
)
shards = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shards)

SIZES = (("a", 7), ("b", 3), ("c", 3), ("d", 2), ("e", 1))
IDS = [
    f"tests/browser/test_{name}.py::t{i}[chromium]" for name, count in SIZES for i in range(count)
]


@pytest.mark.parametrize("n", [1, 2, 3, 5])
def test_every_test_in_exactly_one_shard(n):
    parts = [shards.select(IDS, k, n) for k in range(1, n + 1)]
    flat = [i for part in parts for i in part]
    assert sorted(flat) == sorted(IDS) and len(flat) == len(set(flat))
    for part in parts:  # whole files only
        files = {shards.file_of(i) for i in part}
        assert all(shards.file_of(i) in files for i in IDS if i in part)
        for name in files:
            assert all(i in part for i in IDS if shards.file_of(i) == name)


def test_the_split_is_stable_and_balanced():
    assert shards.select(IDS, 1, 2) == shards.select(list(reversed(IDS)), 1, 2)[::-1]
    sizes = [len(shards.select(IDS, k, 2)) for k in (1, 2)]
    assert sizes == [8, 8]  # a: 7 + e: 1; b + c + d: 8


@pytest.mark.parametrize("bad", ["0/2", "3/2", "1", "a/b", "1/0", ""])
def test_a_wrong_shard_is_refused(bad):
    with pytest.raises(ValueError):
        shards.parse(bad)
