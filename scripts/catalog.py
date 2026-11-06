"""catalog.csv: one row per book, kept up to date by add_book.py.

Plain CSV so it opens in Excel, greps easily and diffs cleanly in git.
Browse it on the library page, or search it e.g. with `Select-String aberration catalog.csv`.
"""

import csv
import io
from pathlib import Path

import safe_io

COLUMNS = [
    "slug",
    "type",  # "book" (or empty: a book), "paper" or "thesis"
    "title",
    "authors",
    "year",
    "publisher",
    "isbn",
    "journal",  # papers: journal, volume, issue, pages, DOI
    "volume",
    "issue",
    "page_range",
    "doi",
    "degree",  # theses: PhD / Master / Bachelor / Diploma, university, supervisors
    "institution",
    "supervisors",
    "pages",
    "chapters",
    "subjects",
    "keywords",  # papers and theses: their own keywords, "laser; weed control"
    "field",  # subject (OpenAlex): field, "Engineering"; topic; how sure OpenAlex is (0-1)
    "topic",
    "topic_score",
    "shelves",  # your own grouping, e.g. "Optics; Lasers"
    "file",
    "notes",
    "added",
    "openlibrary",
    "metadata_sources",
]


def load(path: Path) -> dict[str, dict[str, str]]:
    # Always a whole file: it's only ever replaced in one go (safe_io), never rewritten in place
    if not path.exists():
        return {}
    text = safe_io.read_bytes(path).decode("utf-8-sig")  # waits out a write in progress
    return {row["slug"]: row for row in csv.DictReader(io.StringIO(text, newline=""))}


def _write(path: Path, rows: dict[str, dict[str, str]]) -> None:
    # Columns you added yourself (e.g. in Excel) are kept, after the tool's own
    extra = list(dict.fromkeys(k for r in rows.values() for k in r if k and k not in COLUMNS))
    out = io.StringIO(newline="")
    # extrasaction: a row with more cells than the header has them under None; dropped as before
    writer = csv.DictWriter(out, fieldnames=COLUMNS + extra, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(sorted(rows.values(), key=lambda r: r["slug"]))
    # utf-8-sig so Excel shows accents (e.g. Sasián) correctly
    safe_io.write_text(path, out.getvalue(), encoding="utf-8-sig", newline="")


def _change(path: Path, change):
    """Load, change, write catalog.csv as one step: one writer at a time, so concurrent jobs
    (several uploads, Refresh, Shelves) never lose each other's rows."""
    with safe_io.lock_for(path), safe_io.critical():
        rows = load(path)
        result = change(rows)
        if result is not False:
            _write(path, rows)
        return result


def remove(path: Path, slug: str) -> bool:
    return _change(path, lambda rows: rows.pop(slug, None) is not None)


def set_field(path: Path, slug: str, field: str, value: str) -> None:
    """Set one column of one book, even to an empty value (upsert keeps old values instead)."""
    if field not in COLUMNS:
        raise ValueError(f"unknown column {field}")

    def change(rows):
        if slug not in rows:
            raise KeyError(slug)
        rows[slug][field] = value

    _change(path, change)


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

    def change(rows):
        old = rows.get(row["slug"], {})
        rows[row["slug"]] = (
            old  # your own columns stay
            | {c: row.get(c) or old.get(c, "") for c in COLUMNS}
            | {"added": old.get("added") or row.get("added", "")}
        )

    _change(path, change)
