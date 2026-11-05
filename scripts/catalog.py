"""catalog.csv: one row per book, kept up to date by add_book.py.

Plain CSV so it opens in Excel, greps easily and diffs cleanly in git.
Search it with notebooks/library.py, or e.g. `Select-String aberration catalog.csv`.
"""

import csv
from pathlib import Path

COLUMNS = [
    "slug",
    "title",
    "authors",
    "year",
    "publisher",
    "isbn",
    "pages",
    "chapters",
    "subjects",
    "file",
    "notes",
    "added",
    "openlibrary",
    "metadata_sources",
]


def load(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        return {row["slug"]: row for row in csv.DictReader(f)}


def _write(path: Path, rows: dict[str, dict[str, str]]) -> None:
    # utf-8-sig so Excel shows accents (e.g. Sasián) correctly
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(sorted(rows.values(), key=lambda r: r["slug"]))


def remove(path: Path, slug: str) -> bool:
    rows = load(path)
    if rows.pop(slug, None) is None:
        return False
    _write(path, rows)
    return True


def upsert(path: Path, row: dict[str, str]) -> None:
    """Add or update one book; keeps the original 'added' date and any columns not given."""
    rows = load(path)
    old = rows.get(row["slug"], {})
    rows[row["slug"]] = {c: row.get(c) or old.get(c, "") for c in COLUMNS} | {
        "added": old.get("added") or row.get("added", "")
    }
    _write(path, rows)
