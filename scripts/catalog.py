"""catalog.csv: one row per book, kept up to date by add_book.py.

Plain CSV so it opens in Excel, greps easily and diffs cleanly in git.
Browse it on the library page, or search it e.g. with `Select-String aberration catalog.csv`.
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
    "shelves",  # your own grouping, e.g. "Optics; Lasers"
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


def set_field(path: Path, slug: str, field: str, value: str) -> None:
    """Set one column of one book, even to an empty value (upsert keeps old values instead)."""
    if field not in COLUMNS:
        raise ValueError(f"unknown column {field}")
    rows = load(path)
    if slug not in rows:
        raise KeyError(slug)
    rows[slug][field] = value
    _write(path, rows)


def split_list(value: str) -> list[str]:
    """'Optics; Lasers' -> ['Optics', 'Lasers'] (also accepts commas)."""
    seen: list[str] = []
    for part in value.replace(",", ";").split(";"):
        part = " ".join(part.split())
        if part and part.lower() not in (s.lower() for s in seen):
            seen.append(part)
    return seen


def upsert(path: Path, row: dict[str, str]) -> None:
    """Add or update one book; keeps the original 'added' date and any columns not given."""
    rows = load(path)
    old = rows.get(row["slug"], {})
    rows[row["slug"]] = {c: row.get(c) or old.get(c, "") for c in COLUMNS} | {
        "added": old.get("added") or row.get("added", "")
    }
    _write(path, rows)
