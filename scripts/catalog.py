"""catalog.csv: one row per document, and the only place a document's identity lives.

Every document has an `id`: a random UUID4, given once when it's added, never changed and never
reused. It is the document's identity everywhere (the reading log, the search index, the page,
the reading view, every API); nothing else identifies a document. The `slug`
(shannon-1997-art-science-optical-design) is only its human-readable name: the base of its file
and folder names. `file` and `notes` are where its PDF and notes are. Renaming a document
changes those three and nothing else.

A document taken out of the library (merged into another, or removed) leaves a tombstone in
retired-documents.json next to the catalog, so a reference to its id still says what became of
it (resolve). An id is either in the catalog or retired, never both.

Plain CSV so it opens in Excel, greps easily and diffs cleanly in git. Loading checks the ids
(each one valid and unique) and refuses a catalog that breaks them, rather than guessing: an
edit in Excel that copies a row or clears an id is reported, never "fixed".
"""

import csv
import io
import re
import uuid
from datetime import date
from pathlib import Path

import safe_io

COLUMNS = [
    "id",  # the document's identity: a UUID4, never changed (see above)
    "slug",  # its name: the base of its file and folder names, nothing more
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

ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


class CatalogError(ValueError):
    """catalog.csv breaks a rule (a missing, malformed or repeated id, a repeated name)."""


class NotMigrated(CatalogError):
    """catalog.csv is in the old format (documents known by their name, without ids)."""


def new_id() -> str:
    return str(uuid.uuid4())


def is_id(value: str) -> bool:
    return bool(ID_RE.match(value or ""))


# --- reading and writing ---------------------------------------------------------------------


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """(header, rows) exactly as in the file, whatever its format (also the old one: the
    migration reads it with this)."""
    text = safe_io.read_bytes(path).decode("utf-8-sig")  # waits out a write in progress
    reader = csv.DictReader(io.StringIO(text, newline=""))
    rows = list(reader)
    return list(reader.fieldnames or []), rows


def problems(rows: list[dict[str, str]]) -> list[str]:
    """What's wrong with a catalog's ids and names (empty if nothing)."""
    found, ids, names = [], {}, {}
    for n, row in enumerate(rows, 2):  # line 1 is the header
        doc_id, slug = row.get("id") or "", row.get("slug") or ""
        where = f"line {n} ({slug or 'no name'})"
        if not is_id(doc_id):
            found.append(f"{where}: {'no id' if not doc_id else f'not a valid id: {doc_id!r}'}")
        elif doc_id in ids:
            found.append(f"{where}: the same id as line {ids[doc_id]}")
        else:
            ids[doc_id] = n
        if not slug:
            found.append(f"{where}: no name (slug)")
        elif slug in names:
            found.append(f"{where}: the same name as line {names[slug]}")
        else:
            names[slug] = n
    return found


def load(path: Path) -> dict[str, dict[str, str]]:
    """{id: row}. Raises NotMigrated for an old-format catalog, CatalogError for broken ids."""
    # Always a whole file: it's only ever replaced in one go (safe_io), never rewritten in place
    if not path.exists():
        return {}
    header, rows = read_rows(path)
    if header and "id" not in header:
        raise NotMigrated(
            f"{path.name} is in the old format (documents without permanent ids). Run the "
            "one-time migration first: uv run scripts/migrate_ids.py --library <folder>"
        )
    if found := problems(rows):
        raise CatalogError(
            f"{path.name} can't be used: " + "; ".join(found[:5])
            + (f"; and {len(found) - 5} more" if len(found) > 5 else "")
            + ". Fix it in a text editor or Excel (each document needs its own id), or restore "
            "it from a backup."
        )  # fmt: skip
    return {row["id"]: row for row in rows}


def dumps(rows) -> str:
    """The catalog as CSV text (rows sorted by name, so diffs stay small)."""
    rows = list(rows.values()) if isinstance(rows, dict) else list(rows)
    # Columns you added yourself (e.g. in Excel) are kept, after the tool's own
    extra = list(dict.fromkeys(k for r in rows for k in r if k and k not in COLUMNS))
    out = io.StringIO(newline="")
    # extrasaction: a row with more cells than the header has them under None; dropped as before
    writer = csv.DictWriter(out, fieldnames=COLUMNS + extra, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(sorted(rows, key=lambda r: r["slug"]))
    return out.getvalue()


def _write(path: Path, rows: dict[str, dict[str, str]]) -> None:
    if found := problems(list(rows.values())):  # a bug must never write a broken catalog
        raise CatalogError("not written: " + "; ".join(found[:5]))
    # utf-8-sig so Excel shows accents (e.g. Sasián) correctly
    safe_io.write_text(path, dumps(rows), encoding="utf-8-sig", newline="")


def _change(path: Path, change):
    """Load, change, write catalog.csv as one step: one writer at a time, so concurrent jobs
    (several uploads, Refresh, Shelves) never lose each other's rows."""
    with safe_io.lock_for(path), safe_io.critical():
        rows = load(path)
        result = change(rows)
        if result is not False:
            _write(path, rows)
        return result


# --- changing entries ------------------------------------------------------------------------


def add(path: Path, row: dict[str, str]) -> str:
    """Add a new document; it gets its permanent id here. Returns the id."""
    if not row.get("slug"):
        raise ValueError("a document needs a name (slug)")
    doc_id = new_id()

    def change(rows):
        if by_slug(rows, row["slug"]):
            raise ValueError(f"the name {row['slug']} is already another document's")
        rows[doc_id] = {c: row.get(c) or "" for c in COLUMNS} | {"id": doc_id}
        rows[doc_id]["notes"] = rows[doc_id]["notes"] or f"notes/{row['slug']}/"  # the usual

    _change(path, change)
    return doc_id


def update(path: Path, doc_id: str, fields: dict[str, str]) -> None:
    """Fill in or change some columns of one document; empty values leave a column as it is
    (set_field can empty one), the original 'added' date stays, and the id never changes."""
    if fields.get("id", doc_id) != doc_id:
        raise ValueError("a document's id never changes")

    def change(rows):
        old = rows.get(doc_id)
        if old is None:
            raise KeyError(doc_id)
        rows[doc_id] = (
            old  # your own columns stay
            | {c: fields.get(c) or old.get(c, "") for c in COLUMNS}
            | {"id": doc_id, "added": old.get("added") or fields.get("added", "")}
        )

    _change(path, change)


def set_field(path: Path, doc_id: str, field: str, value: str) -> None:
    """Set one column of one document, even to an empty value (update keeps old values)."""
    if field not in COLUMNS or field == "id":
        raise ValueError(f"can't set column {field}")

    def change(rows):
        if doc_id not in rows:
            raise KeyError(doc_id)
        rows[doc_id][field] = value

    _change(path, change)


def set_fields(path: Path, doc_id: str, fields: dict[str, str]) -> None:
    """Set several columns of one document in one write, even to empty values."""
    if "id" in fields or any(f not in COLUMNS for f in fields):
        raise ValueError(f"can't set columns {', '.join(fields)}")

    def change(rows):
        if doc_id not in rows:
            raise KeyError(doc_id)
        rows[doc_id].update(fields)

    _change(path, change)


def remove(path: Path, doc_id: str) -> dict[str, str] | None:
    """Take a document's row out (see retire for what's kept of it); returns the row."""
    removed = {}

    def change(rows):
        if doc_id not in rows:
            return False
        removed.update(rows.pop(doc_id))

    _change(path, change)
    return removed or None


def by_slug(rows: dict, slug: str) -> dict | None:
    """The document named `slug` (names are unique), e.g. for a file named after it."""
    return next((r for r in rows.values() if r.get("slug") == slug), None)


def by_file(rows: dict, file: str) -> dict | None:
    """The document whose PDF is `file` (books/<name>.pdf, ...)."""
    return next((r for r in rows.values() if r.get("file") == file), None)


def split_list(value: str) -> list[str]:
    """'Optics; Lasers' -> ['Optics', 'Lasers'] (also accepts commas)."""
    seen: list[str] = []
    for part in value.replace(",", ";").split(";"):
        part = " ".join(part.split())
        if part and part.lower() not in (s.lower() for s in seen):
            seen.append(part)
    return seen


# --- retired ids (tombstones) ----------------------------------------------------------------


def retired_path(path: Path) -> Path:
    """retired-documents.json next to catalog.csv."""
    return path.with_name("retired-documents.json")


def retired(path: Path) -> dict[str, dict]:
    """{id: tombstone} of documents no longer in the library."""
    return safe_io.load_json(retired_path(path), {})


def retire(path: Path, doc_id: str, event: str, row: dict, into: str = "") -> None:
    """Leave a tombstone for a document leaving the library: "merged" (into: the id that kept
    its work) or "removed". Written before the row is taken out of the catalog, so a reference
    to it is never left without an answer. Its title and name are kept to show in histories."""
    if event not in ("merged", "removed") or (event == "merged") != bool(into):
        raise ValueError(f"bad tombstone: {event} {into}")

    def add(stones: dict) -> None:
        stones[doc_id] = {
            "event": event,
            "into": into,
            "date": date.today().isoformat(),
            "title": row.get("title", ""),
            "slug": row.get("slug", ""),
            "file": row.get("file", ""),
        }

    safe_io.update_json(retired_path(path), add, {}, backup=True, ensure_ascii=False, indent=1,
                        sort_keys=True)  # fmt: skip


def unretire(path: Path, doc_id: str) -> None:
    """Take a tombstone back (an operation that was rolled back)."""
    if retired_path(path).exists():
        safe_io.update_json(retired_path(path), lambda s: s.pop(doc_id, None), {}, backup=True,
                            ensure_ascii=False, indent=1, sort_keys=True)  # fmt: skip


def resolve(path: Path, doc_id: str) -> dict:
    """What a document id refers to now: {"status": "live", "row"} for a document in the
    library; a merged one is followed to the document that kept its work ({"status": "live",
    "row", "via": [the retired ids]}); {"status": "removed", "tombstone"}; {"status":
    "unknown"}."""
    rows = load(path)
    stones = retired(path) if retired_path(path).exists() else {}
    via, current = [], doc_id
    while current not in rows:
        stone = stones.get(current)
        if not stone:
            return {"status": "unknown", "via": via}
        if stone["event"] == "removed":
            return {"status": "removed", "tombstone": stone, "via": via}
        via.append(current)
        current = stone["into"]
        if current in via or len(via) > 50:  # a loop can only come from a hand edit
            return {"status": "unknown", "via": via}
    return {"status": "live", "row": rows[current], "via": via}


def check(path: Path) -> list[str]:
    """Everything wrong with the identities in this library (empty if nothing): the catalog's
    ids and names, and the tombstones (an id both live and retired, a merge into nothing)."""
    if not path.exists():
        return []
    header, rows = read_rows(path)
    if header and "id" not in header:
        return ["catalog.csv is in the old format: run the one-time migration"]
    found = problems(rows)
    live = {r.get("id") for r in rows}
    if retired_path(path).exists():
        for doc_id, stone in retired(path).items():
            if doc_id in live:
                found.append(f"{doc_id} is both in the catalog and retired")
            if stone.get("event") == "merged" and resolve(path, doc_id)["status"] != "live":
                found.append(f"{doc_id} was merged into {stone.get('into')}, which isn't found")
    return found
