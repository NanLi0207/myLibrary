"""Small helpers for tests that set up catalog entries (documents are known by their id; tests
often find them by their name, the way a person would)."""

from pathlib import Path

import catalog


def put(path: Path, row: dict) -> str:
    """Add the entry named row["slug"], or update it if it's there; returns its id."""
    rows = catalog.load(path) if path.exists() else {}
    if existing := catalog.by_slug(rows, row["slug"]):
        catalog.update(path, existing["id"], row)
        return existing["id"]
    return catalog.add(path, row)


def entry(path: Path, slug: str) -> dict:
    """The entry named `slug` (KeyError if there's none)."""
    found = catalog.by_slug(catalog.load(path), slug)
    if found is None:
        raise KeyError(slug)
    return found


def id_of(path: Path, slug: str) -> str:
    return entry(path, slug)["id"]
