"""One-time migration of a library to permanent document ids (see catalog.py).

Before ids, documents were known by their name (the slug). This gives every document a
permanent id and moves every reference that used its name to the id:

    catalog.csv                 a new first column, `id` (every other value stays as it was)
    notes/reading-log.json      {day: {name: ...}} becomes {day: {id: ...}} (values unchanged)
    .cache/books.db, .cache/chapter_pages.json, .cache/subjects_tried.json
                                caches: deleted, rebuilt by the app

Nothing else holds a document's name as a reference: PDFs, notes, chapter notes, vocabulary,
review progress, marks and file names stay exactly as they are.

    uv run scripts/migrate_ids.py --library <folder>              # dry run: what would change
    uv run scripts/migrate_ids.py --library <folder> --apply      # do it
    uv run scripts/migrate_ids.py --library <folder> --resume     # finish an interrupted one
    uv run scripts/migrate_ids.py --library <folder> --rollback   # put the old files back
    uv run scripts/migrate_ids.py --library <folder> --check      # are the ids all right?

Several files change, so --apply works in steps it can recover from. Copies of the originals and
the complete new versions go first to the library's .myLibrary/migrations/<time>-uuid/ (a
dedicated place: "Clear archive" never touches it, git ignores it), checked, with a manifest.
Only then are the files swapped in, one at a time, the manifest recording each step; then
everything is verified value by value. An interruption at any point leaves a manifest that
isn't "done": the app refuses to open the library until --resume finishes the job or --rollback
puts the old files back. The app must not be running meanwhile (this checks).

The ids a dry run shows are examples: --apply makes new ones.
"""

import argparse
import csv
import hashlib
import io
import json
import shutil
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

import catalog
import safe_io

TARGETS = ("catalog.csv", "notes/reading-log.json")  # your data that refers to documents
CACHES = (".cache/books.db", ".cache/chapter_pages.json", ".cache/subjects_tried.json")
UNFINISHED = ("prepared", "committing", "committed")


class MigrationError(Exception):
    """The migration can't go on; the message says why and what to do."""


def migrations_dir(library: Path) -> Path:
    return library / ".myLibrary" / "migrations"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- the plan (read-only) ---------------------------------------------------------------------


def plan(library: Path) -> dict:
    """What the migration would do, without writing anything: {"migrated": bool, "blocking":
    [problems that stop it], "warnings": [...], "mapping": {name: id}, "new": {target: bytes},
    "old": {target: bytes}, "rows": n, "log": {...}}."""
    path = library / "catalog.csv"
    result = {"migrated": False, "blocking": [], "warnings": [], "mapping": {}, "new": {},
              "old": {}, "rows": 0, "log_entries": 0, "log_days": 0}  # fmt: skip
    if not path.exists():
        result["blocking"].append("no catalog.csv in this library")
        return result
    header, rows = catalog.read_rows(path)
    if "id" in header:
        result["migrated"] = True
        result["blocking"] = catalog.check(path)
        return result
    result["rows"] = len(rows)
    names = {}
    for n, row in enumerate(rows, 2):
        slug = row.get("slug") or ""
        if None in row:
            result["blocking"].append(
                f"catalog.csv line {n} ({slug}) has more cells than "
                "columns: fix it first, or a value would be lost"
            )
        if not slug:
            result["blocking"].append(f"catalog.csv line {n} has no name (slug)")
        elif slug in names:
            result["blocking"].append(f"catalog.csv lines {names[slug]} and {n} have the same "
                                      f"name {slug}: which is which?")  # fmt: skip
        else:
            names[slug] = n
    mapping = {slug: catalog.new_id() for slug in names}
    result["mapping"] = mapping
    # Warnings: things worth knowing that don't stop it
    for row in rows:
        pdf = library / (row.get("file") or "")
        if not row.get("file") or not pdf.is_file():
            result["warnings"].append(f"{row.get('slug')}: its PDF {row.get('file') or '?'} "
                                      "isn't there (the entry is migrated anyway)")  # fmt: skip
        if row.get("notes") and not (library / row["notes"]).is_dir():
            result["warnings"].append(f"{row.get('slug')}: its notes folder {row['notes']} "
                                      "isn't there")  # fmt: skip
    known_notes = {(library / r["notes"]).resolve() for r in rows if r.get("notes")}
    for folder in sorted((library / "notes").glob("*/")) if (library / "notes").exists() else []:
        if folder.name != "topics" and folder.resolve() not in known_notes:
            result["warnings"].append(f"notes/{folder.name}/ belongs to no entry (left as it "
                                      "is)")  # fmt: skip
    # The new catalog: the same rows and values, each with its id
    old_catalog = safe_io.read_bytes(path)
    new_rows = [{"id": mapping.get(r.get("slug"), "")} | r for r in rows]
    result["old"]["catalog.csv"] = old_catalog
    result["new"]["catalog.csv"] = catalog.dumps(new_rows).encode("utf-8-sig")
    # The reading log, by id
    log_path = library / "notes" / "reading-log.json"
    if log_path.exists():
        old_log_bytes = safe_io.read_bytes(log_path)
        try:
            log = json.loads(old_log_bytes.decode("utf-8"))
        except ValueError as e:
            result["blocking"].append(f"notes/reading-log.json can't be read ({e}); repair it")
            return result
        new_log = {}
        for day, entries in log.items():
            for slug, entry in entries.items():
                if slug not in mapping:
                    result["blocking"].append(f"notes/reading-log.json {day}: {slug} is no "
                                              "entry's name: whose reading is it?")  # fmt: skip
                    continue
                new_log.setdefault(day, {})[mapping[slug]] = entry
                result["log_entries"] += 1
        result["log_days"] = len(log)
        result["old"]["notes/reading-log.json"] = old_log_bytes
        result["new"]["notes/reading-log.json"] = json.dumps(
            new_log, ensure_ascii=False, indent=1, sort_keys=True
        ).encode("utf-8")
    return result


def verify(old: dict[str, bytes], new: dict[str, bytes], mapping: dict[str, str]) -> list[str]:
    """Every value of the old files is in the new ones, under the right id (value by value,
    not by bytes: a new column changes every line). Returns the differences (none, normally)."""
    found = []
    # Catalog: the same rows, every column the same, plus a valid unique id that's the mapping's
    _, old_rows = _rows(old["catalog.csv"])
    header, new_rows = _rows(new["catalog.csv"])
    if header[:1] != ["id"]:
        found.append("the new catalog doesn't start with the id column")
    by_slug = {r.get("slug"): r for r in new_rows}
    if len(new_rows) != len(old_rows):
        found.append(f"{len(old_rows)} entries before, {len(new_rows)} after")
    found += catalog.problems(new_rows)
    for row in old_rows:
        after = by_slug.get(row.get("slug"))
        if after is None:
            found.append(f"{row.get('slug')} is missing")
            continue
        if after.get("id") != mapping.get(row.get("slug")):
            found.append(f"{row.get('slug')} has the wrong id")
        for key, value in row.items():
            if key != "id" and (after.get(key) or "") != (value or ""):
                found.append(f"{row.get('slug')}: {key} was {value!r}, is {after.get(key)!r}")
        if extra := set(after) - set(row) - {"id"} - {k for k in after if not after[k]}:
            found.append(f"{row.get('slug')}: new values in {sorted(extra)}")
    # Reading log: every record the same, under its document's id, nothing else
    if "notes/reading-log.json" in old:
        before = json.loads(old["notes/reading-log.json"].decode("utf-8"))
        after = json.loads(new["notes/reading-log.json"].decode("utf-8"))
        if sorted(before) != sorted(after):
            found.append("the reading log's days changed")
        for day, entries in before.items():
            moved = {mapping.get(slug): entry for slug, entry in entries.items()}
            if after.get(day) != moved:
                found.append(f"reading log {day}: records differ")
    return found


def _rows(data: bytes) -> tuple[list[str], list[dict]]:
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
    rows = list(reader)
    return list(reader.fieldnames or []), rows


# --- applying, resuming, rolling back ------------------------------------------------------------


def _manifests(library: Path) -> list[Path]:
    folder = migrations_dir(library)
    return sorted(folder.glob("*-uuid/manifest.json")) if folder.exists() else []


def unfinished(library: Path) -> str:
    """The migration folder of a migration that didn't finish ("" if none)."""
    for manifest in _manifests(library):
        try:
            state = json.loads(manifest.read_text(encoding="utf-8")).get("state")
        except OSError, ValueError:
            return str(manifest.parent)  # can't tell: treat as unfinished, never guess
        if state in UNFINISHED:
            return str(manifest.parent)
    return ""


def _set_state(manifest: Path, info: dict, state: str) -> None:
    info["state"] = state
    info.setdefault("history", []).append([state, datetime.now().isoformat(timespec="seconds")])
    safe_io.write_json(manifest, info, ensure_ascii=False, indent=1)


def apply(library: Path, log=print) -> dict:
    """Migrate the library (see the module's description). Returns the manifest."""
    if where := unfinished(library):
        raise MigrationError(f"a migration didn't finish ({where}): use --resume or --rollback")
    found = plan(library)
    if found["migrated"]:
        raise MigrationError("this library already has document ids; nothing to do")
    if found["blocking"]:
        raise MigrationError("can't migrate yet:\n  " + "\n  ".join(found["blocking"]))
    if problems := verify(found["old"], found["new"], found["mapping"]):
        raise MigrationError("the new files wouldn't match the old ones (nothing was "
                             "changed):\n  " + "\n  ".join(problems[:20]))  # fmt: skip
    folder = migrations_dir(library) / f"{datetime.now():%Y%m%d-%H%M%S}-uuid"
    if folder.exists():
        raise MigrationError(f"{folder} exists already; try again in a second")
    # 1. Copies of the originals and the complete new versions, checked, before anything changes
    try:
        files = []
        for target, data in found["new"].items():
            original, staged = folder / "originals" / target, folder / "new" / target
            safe_io.write_bytes(original, found["old"][target])
            safe_io.write_bytes(staged, data)
            if (safe_io.read_bytes(original) != found["old"][target]
                    or safe_io.read_bytes(staged) != data):  # fmt: skip
                raise MigrationError(f"the copies of {target} didn't read back the same")
            files.append({"path": target, "original": _sha(found["old"][target]),
                          "new": _sha(data), "done": False})  # fmt: skip
        manifest = folder / "manifest.json"
        info = {"kind": "document ids", "created": datetime.now().isoformat(timespec="seconds"),
                "library": str(library), "mapping": found["mapping"], "files": files,
                "caches": list(CACHES)}  # fmt: skip
        _set_state(manifest, info, "prepared")
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)  # nothing in the library was touched yet
        raise
    log(f"Backed up the originals in {folder}")
    return _commit(library, manifest, info, log)


def _commit(library: Path, manifest: Path, info: dict, log=print) -> dict:
    """Swap the new versions in (skipping ones already in), then caches, then verify."""
    folder = manifest.parent
    with safe_io.critical():
        _set_state(manifest, info, "committing")
        for item in info["files"]:
            target = library / item["path"]
            current = _sha(safe_io.read_bytes(target)) if target.exists() else ""
            if current == item["new"]:
                item["done"] = True
                continue
            if current != item["original"]:
                raise MigrationError(
                    f"{item['path']} changed since the migration started; it "
                    "was left as it is. Use --rollback after checking it."
                )
            staged = safe_io.read_bytes(folder / "new" / item["path"])
            if _sha(staged) != item["new"]:
                raise MigrationError(f"the staged copy of {item['path']} is damaged; use "
                                     "--rollback")  # fmt: skip
            safe_io.write_bytes(target, staged)
            item["done"] = True
            safe_io.write_json(manifest, info, ensure_ascii=False, indent=1)
            log(f"  -> {item['path']} migrated")
        _set_state(manifest, info, "committed")
        for cache in info["caches"]:
            (library / cache).unlink(missing_ok=True)
        old = {
            i["path"]: safe_io.read_bytes(folder / "originals" / i["path"]) for i in info["files"]
        }
        new = {i["path"]: safe_io.read_bytes(library / i["path"]) for i in info["files"]}
        if problems := verify(old, new, info["mapping"]):
            raise MigrationError("verification failed after migrating (use --rollback):\n  "
                                 + "\n  ".join(problems[:20]))  # fmt: skip
        _set_state(manifest, info, "done")
    log(f"Done: {len(info['mapping'])} documents have permanent ids.")
    return info


def _latest(library: Path, states: tuple) -> tuple[Path, dict]:
    for manifest in reversed(_manifests(library)):
        info = json.loads(manifest.read_text(encoding="utf-8"))
        if info.get("state") in states:
            return manifest, info
    raise MigrationError("no such migration in this library")


def resume(library: Path, log=print) -> dict:
    """Finish a migration that was interrupted (its staged files are swapped in)."""
    manifest, info = _latest(library, UNFINISHED)
    log(f"Resuming {manifest.parent} (it stopped at: {info['state']})")
    return _commit(library, manifest, info, log)


def rollback(library: Path, log=print) -> dict:
    """Put the files back as they were before the latest migration (finished or not). Refused
    if a file has changed since in another way (new work would be lost): it says which."""
    manifest, info = _latest(library, UNFINISHED + ("done",))
    folder = manifest.parent
    changed = []
    for item in info["files"]:
        target = library / item["path"]
        current = _sha(safe_io.read_bytes(target)) if target.exists() else ""
        if current not in (item["original"], item["new"]):
            changed.append(item["path"])
    if changed:
        raise MigrationError(f"{', '.join(changed)} changed since the migration (e.g. new "
                             "documents or reading); rolling back would lose that. Nothing "
                             "was changed.")  # fmt: skip
    with safe_io.critical():
        for item in info["files"]:
            original = safe_io.read_bytes(folder / "originals" / item["path"])
            if _sha(original) != item["original"]:
                raise MigrationError(f"the backed-up {item['path']} is damaged; nothing more "
                                     "was changed")  # fmt: skip
            safe_io.write_bytes(library / item["path"], original)
            log(f"  -> {item['path']} put back")
        for cache in info["caches"]:  # caches of the new format: rebuilt by the old one
            (library / cache).unlink(missing_ok=True)
        _set_state(manifest, info, "rolled back")
    log("Rolled back: the library is as it was before the migration.")
    return info


def check(library: Path) -> list[str]:
    """Problems with the ids of a migrated library: the catalog's and the tombstones' (see
    catalog.check), and reading-log records whose id is neither in the library nor retired."""
    path = library / "catalog.csv"
    found = catalog.check(path)
    if found:
        return found
    rows = catalog.load(path)
    stones = catalog.retired(path) if catalog.retired_path(path).exists() else {}
    log = library / "notes" / "reading-log.json"
    if log.exists():
        for day, entries in safe_io.load_json(log, {}).items():
            for doc_id in entries:
                if doc_id not in rows and doc_id not in stones:
                    found.append(f"reading log {day}: {doc_id} is no document's id")
    return found


# --- command line ----------------------------------------------------------------------------


def _server_running(library: Path, port: int) -> bool:
    """Whether a myLibrary server on this port has this library open."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as response:
            running = unquote(response.headers.get("X-myLibrary-Library", ""))
    except OSError:
        return False
    return not running or Path(running).resolve() == library.resolve()


def report(found: dict, library: Path) -> None:
    if found["migrated"]:
        print("This library already has document ids.")
        return
    print(f"Library: {library}")
    print(f"catalog.csv: {found['rows']} entries get an id (a new first column `id`; every "
          "other value stays as it is)")  # fmt: skip
    if found["log_entries"]:
        print(f"notes/reading-log.json: {found['log_entries']} records on {found['log_days']} "
              "days move from names to ids (values unchanged)")  # fmt: skip
    print("caches deleted and rebuilt: " + ", ".join(CACHES))
    print("unchanged: PDFs, file and folder names, notes, chapter notes, vocabulary, review "
          "progress, marks")  # fmt: skip
    print("\nName -> id (examples: --apply makes new ids):")
    for slug, doc_id in sorted(found["mapping"].items()):
        print(f"  {slug:60} {doc_id}")
    for title, items in (("Warnings", found["warnings"]), ("Blocking", found["blocking"])):
        if items:
            print(f"\n{title}:")
            for item in items:
                print(f"  - {item}")
    if not found["blocking"]:
        problems = verify(found["old"], found["new"], found["mapping"])
        print(
            "\nCheck of the planned files: "
            + ("every value is kept" if not problems else "; ".join(problems[:10]))
        )


def main() -> None:
    sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765, help="where the app would be running")
    what = parser.add_mutually_exclusive_group()
    for flag in ("--apply", "--resume", "--rollback", "--check"):
        what.add_argument(flag, action="store_true")
    args = parser.parse_args()
    library = args.library.resolve()
    try:
        if args.check:
            problems = check(library)
            print("\n".join(problems) if problems else "All document ids are in order.")
            sys.exit(1 if problems else 0)
        if not (args.apply or args.resume or args.rollback):
            report(plan(library), library)
            print("\nDry run: nothing was written.")
            return
        if _server_running(library, args.port):
            raise MigrationError("myLibrary is running with this library: Quit it first")
        if args.apply:
            apply(library)
        elif args.resume:
            resume(library)
        else:
            rollback(library)
    except MigrationError as e:
        sys.exit(f"Stopped: {e}")


if __name__ == "__main__":
    main()
