"""📈 Reading log: how long you read each day, in which books, and which pages you saw.

The reading view (lookup.js trackReading) counts the time you actively read (the tab is
visible and you moved, scrolled or turned a page in the last two minutes) and sends it every
minute; this module adds it up per day and document (by its id, see catalog.py) in the
library's notes/reading-log.json:

    {"2026-11-06": {"9f3c2a4e-1b7d-4c1e-9a55-2f0e6d1c3b8a": {"s": 1260, "p": [41, 42]}}}

(s = seconds read, p = the pages you looked at.) It's backed up with your notes.

A record is never rewritten once the day is over. When a document is merged into another
(Refresh found it twice), its records stay under its own id and count for the one kept (its
tombstone says which), so two copies read on the same day keep both records. A removed
document's history stays too, shown under its old title.
"""

from datetime import date, timedelta
from pathlib import Path

import catalog
import safe_io

MAX_STEP = 120  # seconds one report may add (the page sends every minute)
READING_DAY = 5 * 60  # this much reading makes a day count for the streak
WEEKS = 26  # the calendar on the library page


def log_path(library: Path) -> Path:
    return library / "notes" / "reading-log.json"


def load(library: Path) -> dict:
    """The whole log. A damaged file is never taken for an empty log (that would be saved over
    your history): its previous version is used, else safe_io.DamagedFile says what to do."""
    return safe_io.load_json(log_path(library), {})


def record(
    library: Path, doc_id: str, seconds: int, pages: list[int], today: date | None = None
) -> dict:
    """Add a report from the reading view to today's line for this document."""
    day = (today or date.today()).isoformat()
    seconds = max(0, min(int(seconds), MAX_STEP))
    pages = sorted({int(p) for p in pages if isinstance(p, int) and 0 < p < 100_000})

    def add(log: dict) -> dict:
        entry = log.setdefault(day, {}).setdefault(doc_id, {"s": 0, "p": []})
        entry["s"] = int(entry.get("s", 0)) + seconds
        entry["p"] = sorted(set(entry.get("p", [])) | set(pages))
        return {"day": day, "seconds": entry["s"], "pages": len(entry["p"])}

    # One report at a time (two open books report at once); notes/reading-log.json.bak keeps
    # the previous version in case the file is ever damaged
    return safe_io.update_json(log_path(library), add, {}, backup=True,
                               ensure_ascii=False, indent=1, sort_keys=True)  # fmt: skip


def attribute(catalog_path: Path, doc_ids: set[str]) -> dict[str, dict]:
    """Whom each recorded id's reading counts for now: {id: {"id", "title", "removed"}}. A
    document in the library: itself. A merged one: the document that kept its work (following
    its tombstone). A removed one: itself, under the title it had."""
    rows = catalog.load(catalog_path)
    stones = catalog.retired(catalog_path) if catalog.retired_path(catalog_path).exists() else {}
    found = {}
    for doc_id in doc_ids:
        current, seen = doc_id, set()
        while current not in rows and stones.get(current, {}).get("event") == "merged":
            seen.add(current)
            current = stones[current]["into"]
            if current in seen:
                break
        if current in rows:
            found[doc_id] = {"id": current, "title": rows[current].get("title") or current,
                             "removed": False}  # fmt: skip
        else:
            stone = stones.get(current, {})
            found[doc_id] = {"id": current, "removed": True,
                             "title": stone.get("title") or "(a document no longer in the "
                             "library)"}  # fmt: skip
    return found


def _day_totals(log: dict) -> dict[str, tuple[int, int]]:
    """{date: (seconds, pages)} over all books."""
    return {
        day: (
            sum(b.get("s", 0) for b in books.values()),
            sum(len(b.get("p", [])) for b in books.values()),
        )  # fmt: skip
        for day, books in log.items()
    }


def streak(totals: dict[str, tuple[int, int]], today: date) -> int:
    """Days in a row with READING_DAY or more, up to today (or yesterday: today may still
    come)."""
    day = today if totals.get(today.isoformat(), (0, 0))[0] >= READING_DAY else (
        today - timedelta(days=1)
    )  # fmt: skip
    n = 0
    while totals.get(day.isoformat(), (0, 0))[0] >= READING_DAY:
        n += 1
        day -= timedelta(days=1)
    return n


def summary(library: Path, catalog_path: Path, today: date | None = None) -> dict:
    """What the library page shows: streak, this week, totals, the calendar and the books."""
    today = today or date.today()
    log = load(library)
    totals = _day_totals(log)
    monday = today - timedelta(days=today.weekday())
    week = [totals.get((monday + timedelta(days=i)).isoformat(), (0, 0)) for i in range(7)]
    # The calendar: whole weeks, Monday first, ending with this week
    start = monday - timedelta(weeks=WEEKS - 1)
    days = []
    for i in range((today - start).days + 1):
        d = start + timedelta(days=i)
        seconds, pages = totals.get(d.isoformat(), (0, 0))
        days.append({"date": d.isoformat(), "seconds": seconds, "pages": pages})
    # Books read in the last 30 days, most time first
    since = (today - timedelta(days=29)).isoformat()
    owners = attribute(catalog_path, {doc_id for entries in log.values() for doc_id in entries})
    books: dict[str, dict] = {}
    for day, entries in log.items():
        if day < since:
            continue
        counted = set()
        for doc_id, entry in entries.items():
            owner = owners[doc_id]
            b = books.setdefault(owner["id"], owner | {"seconds": 0, "pages": set(), "days": 0})
            b["seconds"] += entry.get("s", 0)
            # Pages per record: a merged copy's page numbers needn't be the kept one's
            b["pages"] |= {(doc_id, p) for p in entry.get("p", [])}
            if owner["id"] not in counted:  # two records on one day are one reading day
                b["days"] += 1
                counted.add(owner["id"])
    book_list = sorted(
        ({**b, "pages": len(b["pages"])} for b in books.values()), key=lambda b: -b["seconds"]
    )
    return {
        "today": today.isoformat(),
        "streak": streak(totals, today),
        "today_seconds": totals.get(today.isoformat(), (0, 0))[0],
        "week_seconds": sum(s for s, _ in week),
        "week_pages": sum(p for _, p in week),
        "total_seconds": sum(s for s, _ in totals.values()),
        "reading_days": sum(s >= READING_DAY for s, _ in totals.values()),
        "days": days,
        "books": book_list,
        "reading_day": READING_DAY,
    }
