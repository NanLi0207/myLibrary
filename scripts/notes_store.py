"""A document's Markdown notes, read and saved safely for the reader's notes panel (task 4).

The browser names a note by a key, never by a path:
  file:<name>.md   a note in the document's notes folder (README.md, notes.md, chNN-*.md, ...)
  topic:<name>     a topic note, notes/topics/<name>.md
The server finds the folder through the document's catalog row (its `notes` column).

Every read gives the text (lines end in "\\n") and its version: the SHA-256 of the file's
bytes, or None for a note that doesn't exist yet. A save says which version its text was based
on, and is written only if the file still has that version (checked and written under the
file's lock, atomically). Otherwise it's a Conflict and nothing is written: the file may have
been changed in VS Code meanwhile. Keeping your text over a changed file is an explicit choice
(`overwrite`), and the file's version on disk is first copied to archive/notes-conflicts/.

Files keep their form: line endings (CRLF or LF, whichever the file uses), a byte-order mark,
and the final newline (or its absence). A save that changes nothing doesn't touch the file.
"""

from __future__ import annotations

import codecs
import hashlib
import os
import re
from datetime import datetime
from pathlib import Path

import library_page
import safe_io

MAX_BYTES = 5_000_000  # a note larger than this is refused (5 MB of text)
NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._ -]{0,150}\.md")
TOPIC_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,80}")  # as library_server.topic_note names them
BOM = codecs.BOM_UTF8
NOT_GIVEN = object()  # save(): no overwrite asked for


class NoteError(ValueError):
    """A request that can't be done (bad key, not UTF-8 text, too large). Nothing is written."""


class Conflict(Exception):
    """The note changed since the text being saved was read: nothing was written.
    `current` is the note as it is now (what read() returns)."""

    def __init__(self, current: dict):
        super().__init__("the note was changed meanwhile (in another editor?)")
        self.current = current


def notes_dir(library: Path, row: dict) -> Path:
    """The document's notes folder: its catalog `notes` column (notes/<name>/). A value that
    names a place outside notes/ (an absolute path, "..") is refused."""
    name = Path(row.get("notes") or f"notes/{row['slug']}")
    parts = name.parts
    if name.is_absolute() or name.drive or len(parts) < 2 or parts[0] != "notes" \
            or ".." in parts:  # fmt: skip
        raise NoteError(f"the catalog's notes folder isn't under notes/: {str(name)[:80]!r}")
    return library / name


def topics_dir(library: Path) -> Path:
    return library / "notes" / "topics"


def _inside(path: Path, folder: Path) -> bool:
    """`path` is still in `folder` once links are followed. A symlink or junction *in* a notes
    folder that points out of it isn't: such a file is never listed, read or written. A link on
    the folder itself (a notes folder kept on OneDrive through a junction) is the user's own
    arrangement, and its files count as the folder's."""
    try:
        return path.resolve().is_relative_to(folder.resolve())
    except OSError, RuntimeError:  # a link loop, or a link that can't be followed
        return False


def version_of(data: bytes | None) -> str | None:
    return None if data is None else hashlib.sha256(data).hexdigest()


def _linked(folder: Path) -> list[dict]:
    """The README's checklist (chapters, or a paper's one item), with each item's note file."""
    readme = folder / "README.md"
    if not readme.is_file() or not _inside(readme, folder):  # a README linked from elsewhere
        return []
    return library_page.chapters_in(safe_io.read_text(readme))


def path_of(library: Path, row: dict, key: str, *, creating: bool = False) -> Path:
    """The file a key names. A file that doesn't exist yet is allowed only when `creating`, and
    only if the README links to it (a chapter note not written yet) or it's a topic note."""
    if not isinstance(key, str):
        raise NoteError("no note named")
    kind, _, name = key.partition(":")
    if kind == "file" and NAME_RE.fullmatch(name):
        folder = notes_dir(library, row)
    elif kind == "topic" and TOPIC_RE.fullmatch(name):
        folder, name = topics_dir(library), name + ".md"
    else:
        raise NoteError(f"not a note: {key[:80]!r}")
    path = folder / name
    if not _inside(path, folder):  # a link or junction pointing out
        raise NoteError(f"not a note: {key[:80]!r}")
    if path.exists():
        if not path.is_file():
            raise NoteError(f"not a note: {key[:80]!r}")
        return path
    if creating and (kind == "topic" or name in {c["note"] for c in _linked(folder)}):
        return path
    raise NoteError(f"there is no note {name}")


def entries(library: Path, row: dict) -> list[dict]:
    """The notes the panel can open for this document, in a sensible order:
    the README, the paper's notes.md, the chapters (also ones not written yet), any other
    Markdown files in the folder, then topic notes that mention the document."""
    folder = notes_dir(library, row)
    found: list[dict] = []
    seen: set[str] = set()

    def add(name: str, kind: str, title: str, chapter: int | None = None) -> None:
        if name in seen or not NAME_RE.fullmatch(name):
            return
        path = folder / name
        if not _inside(path, folder):  # a link pointing out of the folder: not a note
            return
        seen.add(name)
        found.append(
            {
                "key": f"file:{name}",
                "kind": kind,
                "title": title,
                "chapter": chapter,
                "exists": path.is_file(),
            }
        )

    if (folder / "README.md").is_file():
        add("README.md", "document", "README")
    if (folder / "notes.md").is_file():
        add("notes.md", "document", "Notes")
    for item in _linked(folder):
        if item["note"] and "/" not in item["note"] and "\\" not in item["note"]:
            add(item["note"], "chapter", item["title"], item["number"])
    if folder.is_dir():
        for path in sorted(folder.glob("*.md")):
            add(path.name, "other", path.stem)
    topics = topics_dir(library)
    if topics.is_dir():
        title = (row.get("title") or "").strip().lower()
        for path in sorted(topics.glob("*.md")):
            if not TOPIC_RE.fullmatch(path.stem) or not _inside(path, topics):
                continue  # (a link pointing out is never read)
            try:
                text = safe_io.read_text(path).lower()
            except OSError, UnicodeDecodeError:
                continue
            if (title and title in text) or row["id"] in text:
                found.append(
                    {
                        "key": f"topic:{path.stem}",
                        "kind": "topic",
                        "title": path.stem.replace("-", " "),
                        "chapter": None,
                        "exists": True,
                    }
                )
    return found


def _decode(data: bytes, path: Path) -> tuple[str, str, bool]:
    """(text with "\\n" line ends, the file's line ending, whether it starts with a BOM)."""
    if len(data) > MAX_BYTES:
        raise NoteError(f"{path.name} is too large to edit here; open it in VS Code")
    bom = data.startswith(BOM)
    try:
        text = data[len(BOM) if bom else 0 :].decode("utf-8")
    except UnicodeDecodeError:
        raise NoteError(f"{path.name} isn't UTF-8 text; open it in VS Code") from None
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    eol = "\r\n" if crlf > lf else "\n" if lf else os.linesep
    return text.replace("\r\n", "\n"), eol, bom


def _encode(text: str, eol: str, bom: bool) -> bytes:
    text = text.replace("\r\n", "\n")
    if eol != "\n":
        text = text.replace("\n", eol)
    return (BOM if bom else b"") + text.encode("utf-8")


def _current(path: Path) -> bytes | None:
    return safe_io.read_bytes(path) if path.exists() else None


def _result(key: str, path: Path, data: bytes | None) -> dict:
    if data is None:
        return {"key": key, "text": "", "version": None, "exists": False}
    text = _decode(data, path)[0]
    return {"key": key, "text": text, "version": version_of(data), "exists": True}


def read(library: Path, row: dict, key: str) -> dict:
    """{key, text, version, exists} for one note (a chapter note not written yet: empty)."""
    path = path_of(library, row, key, creating=True)
    with safe_io.lock_for(path):
        return _result(key, path, _current(path))


def _keep_conflicting(library: Path, path: Path, data: bytes) -> Path:
    """Copy the version on disk to archive/notes-conflicts/<its place under notes/> before it's
    replaced by the text the user chose to keep."""
    try:
        place = path.parent.resolve().relative_to((library / "notes").resolve())
    except ValueError:
        place = Path(path.parent.name)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    copy = library / "archive" / "notes-conflicts" / place / f"{path.stem}.{stamp}{path.suffix}"
    safe_io.write_bytes(copy, data)
    return copy


def save(
    library: Path,
    row: dict,
    key: str,
    text: str,
    base: str | None,
    *,
    overwrite=NOT_GIVEN,
) -> dict:
    """Write `text` to the note if it still has version `base`; returns {version, saved, kept}.
    `saved` is False when the text was already what the file says (nothing written).

    If the note has another version now, Conflict (nothing written), unless `overwrite` is that
    very version: the user saw the changed note and chose to keep their text. Then the changed
    note is copied to archive/notes-conflicts/ first (`kept`), and the text is written."""
    if not isinstance(text, str):
        raise NoteError("no text to save")
    path = path_of(library, row, key, creating=True)
    with safe_io.lock_for(path), safe_io.critical():
        data = _current(path)
        version = version_of(data)
        kept = None
        if version != base:
            if overwrite is NOT_GIVEN or overwrite != version:
                raise Conflict(_result(key, path, data))
            if data is not None:
                kept = _keep_conflicting(library, path, data)
        if data is None:
            eol, bom = os.linesep, False
        else:
            _, eol, bom = _decode(data, path)
        new = _encode(text, eol, bom)
        if len(new) > MAX_BYTES:
            raise NoteError("the note is too large to save here")
        if new == data:
            return {"version": version, "saved": False, "kept": None}
        safe_io.write_bytes(path, new)
        return {
            "version": version_of(new),
            "saved": True,
            "kept": kept.relative_to(library).as_posix() if kept else None,
        }
