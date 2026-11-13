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

Pasted images (M5d) are the document's assets: files in its notes folder's assets/ folder,
linked from its notes as ![…](assets/<name>). Saving one is separate from saving a note: an
image is written once under a new name (never over anything) and is never deleted by this
module, whatever happens to the note that links it (a failed save, a conflict, an Undo).
"""

from __future__ import annotations

import codecs
import hashlib
import os
import re
import secrets
import stat
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import image_check
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
        # (the value itself isn't repeated: it may be a full path, and this reaches the page)
        raise NoteError("this document's notes folder in catalog.csv isn't under notes/")
    return library / name


# The tool's own files in a document's notes folder, written by code (reading progress,
# ticks, saved words): fixed names, never one a page sent
OWN_FILES = {"README.md", "vocabulary.md"}


def notes_file(library: Path, row: dict, name: str) -> Path:
    """The document's README.md or vocabulary.md, existing or not yet: in its notes folder
    (notes_dir: never a catalog value outside notes/), and never a file that is a link or
    junction pointing out of that folder (as for the panel's notes). A link on the folder
    itself, or on notes/ (kept on OneDrive), is the user's own arrangement and allowed.
    NoteError otherwise."""
    if name not in OWN_FILES:
        raise NoteError(f"not one of the notes folder's own files: {name[:80]!r}")
    folder = notes_dir(library, row)
    path = folder / name
    if not _inside(path, folder):
        raise NoteError(f"this document's {name} is a link pointing out of its notes folder")
    return path


def topics_dir(library: Path) -> Path:
    return library / "notes" / "topics"


def _inside(path: Path, folder: Path) -> bool:
    """`path` is still in `folder` once links are followed. A symlink or junction *in* a notes
    folder that points out of it isn't: such a file is never listed, read or written. A link on
    the folder itself (a notes folder kept on OneDrive through a junction) is the user's own
    arrangement, and its files count as the folder's."""
    try:  # (safe_io.real_path: links are followed also in paths longer than Windows' limit)
        return safe_io.real_path(path).is_relative_to(safe_io.real_path(folder))
    except OSError, RuntimeError:  # a link loop, or a link that can't be followed
        return False


def inside(path: Path, folder: Path) -> bool:
    """_inside, for the other code that reads or writes a notes folder (add_book's merge
    and chapter refresh): the same rule as the panel's."""
    return _inside(path, folder)


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
    # (safe_io's checks also see files whose whole path is longer than Windows' usual limit:
    # a plain exists() would call such a note missing, and a "new" note could be written over it)
    if safe_io.exists(path):
        if not safe_io.is_file(path):
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
    return safe_io.read_bytes(path) if safe_io.exists(path) else None


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


def version_info(library: Path, row: dict, key: str) -> dict:
    """{key, version, exists, bytes}: the note on disk now, without its text (the notes panel
    checks this every few seconds for changes made elsewhere)."""
    path = path_of(library, row, key, creating=True)
    with safe_io.lock_for(path):
        data = _current(path)
    return {
        "key": key,
        "version": version_of(data),
        "exists": data is not None,
        "bytes": 0 if data is None else len(data),
    }


def _archive_path(library: Path, path: Path, tag: str = "") -> Path:
    """archive/notes-conflicts/<the note's place under notes/>/<name>.<time><tag>.md"""
    try:
        place = path.parent.resolve().relative_to((library / "notes").resolve())
    except ValueError:
        place = Path(path.parent.name)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return (
        library / "archive" / "notes-conflicts" / place / f"{path.stem}.{stamp}{tag}{path.suffix}"
    )


def _keep_conflicting(library: Path, path: Path, data: bytes) -> Path:
    """Copy the version on disk to archive/notes-conflicts/<its place under notes/> before it's
    replaced by the text the user chose to keep."""
    copy = _archive_path(library, path)
    safe_io.write_bytes(copy, data)
    return copy


def keep_copy(library: Path, row: dict, key: str, text: str) -> str:
    """Keep the user's own text of a note in archive/notes-conflicts/ (…<time>.mine.md), never
    in notes/: their side of a conflict, before the editor takes the disk version instead.
    Written in the note's own form (line endings, BOM). Returns its path in the library."""
    if not isinstance(text, str):
        raise NoteError("no text to keep")
    path = path_of(library, row, key, creating=True)
    with safe_io.lock_for(path):
        data = _current(path)
    eol, bom = (os.linesep, False) if data is None else _decode(data, path)[1:]
    kept = _encode(text, eol, bom)
    if len(kept) > MAX_BYTES:
        raise NoteError("the note is too large to keep here")
    copy = _archive_path(library, path, ".mine")
    safe_io.write_bytes(copy, kept)
    return copy.relative_to(library).as_posix()


# --- pasted images (M5d) -------------------------------------------------------------------

ASSETS = "assets"
# An image file's name in assets/: ours are img-<date>-<time>-<random>.<ext>, but one put there
# by hand may have spaces or any language's letters. Never a path (/ \ :), a control
# character, a character Windows refuses, a leading dot or space (hidden and temporary files),
# and always an image extension
ASSET_NAME_RE = re.compile(
    r'[^\x00-\x1f\x7f/\\:*?"<>|.\s][^\x00-\x1f\x7f/\\:*?"<>|]{0,140}\.(?i:png|jpe?g|webp)'
)
WINDOWS_DEVICES = frozenset(
    ["CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"]
    + [f"{d}{n}" for d in ("COM", "LPT") for n in "123456789¹²³"]
)
NEW_NAME_TRIES = 5


def asset_name_ok(name) -> bool:
    return (
        isinstance(name, str)
        and bool(ASSET_NAME_RE.fullmatch(name))
        and name.split(".")[0].strip().upper() not in WINDOWS_DEVICES
    )


def _assets_dir(library: Path, row: dict) -> tuple[Path, Path]:
    """(the notes folder, its assets/ folder), checked: the notes folder exists (a document
    being renamed or removed meanwhile is never given a new one), and assets/ is a folder in
    it, or not there yet. A link or junction named assets/ pointing elsewhere is refused (a
    link on the notes folder itself is the user's own arrangement, as for notes)."""
    folder = notes_dir(library, row)
    if not safe_io.exists(folder) or not os.path.isdir(safe_io._os_path(folder)):
        raise NoteError("this document has no notes folder")
    assets = folder / ASSETS
    if os.path.lexists(safe_io._os_path(assets)) and not os.path.isdir(safe_io._os_path(assets)):
        raise NoteError("the notes folder's assets is a file, not a folder")
    if not _inside(assets, folder):
        raise NoteError("the notes folder's assets folder is a link pointing elsewhere")
    return folder, assets


def save_asset(library: Path, row: dict, data: bytes, *, now: datetime | None = None) -> dict:
    """Keep a pasted image (PNG, JPEG or WebP, checked from its bytes: image_check) as a new
    file in the document's assets/ folder; its bytes are kept exactly as they came. Returns
    {path: "assets/<name>", name, width, height, bytes}: `path` is what a note in the folder
    links to. Never over an existing file: a new name is made until one is free. ImageError
    for an image it doesn't take, NoteError for a folder it can't write into."""
    info = image_check.inspect(data)  # (outside critical(): decoding may take a moment)
    folder, assets = _assets_dir(library, row)
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    with safe_io.critical():
        for _ in range(NEW_NAME_TRIES):
            name = f"img-{stamp}-{secrets.token_hex(3)}{info.extension}"
            path = assets / name
            try:
                safe_io.create_bytes(path, data, require_atomic=True)
            except FileExistsError:
                continue  # taken (by a file or a link): another name
            _check_created(path, assets, folder, len(data))
            return {
                "path": f"{ASSETS}/{name}",
                "name": name,
                "width": info.width,
                "height": info.height,
                "bytes": len(data),
            }
    raise NoteError("no free name for the image in assets/; try again")


def _check_created(path: Path, assets: Path, folder: Path, size: int) -> None:
    """After writing: the new file really is in the notes folder (assets/ wasn't replaced by
    a link meanwhile). If not, it is removed again, but only if it is still the very file
    just made (same file id and size): never anything else."""
    made = os.lstat(safe_io._os_path(path))
    if _inside(path, assets) and _inside(assets, folder):
        return
    try:
        now = os.lstat(safe_io._os_path(path))
        if now.st_ino == made.st_ino and now.st_size == made.st_size == size:
            os.unlink(safe_io._os_path(path))
    except OSError:
        pass
    raise NoteError("the notes folder's assets folder changed into a link while saving")


def asset_file(library: Path, row: dict, name) -> Path:
    """The existing image `name` in the document's assets/ (for showing it), checked: a valid
    image name (asset_name_ok), assets/ in the notes folder, the file in assets/ once links
    are followed, a plain file. NoteError otherwise (the page shows "image missing")."""
    if not asset_name_ok(name):
        raise NoteError("not an image name")
    folder = notes_dir(library, row)
    assets = folder / ASSETS
    path = assets / name
    if not (_inside(assets, folder) and _inside(path, assets)) or not safe_io.is_file(path):
        raise NoteError("there is no such image")
    return path


def has_assets(folder: Path) -> bool:
    """Any image in the notes folder's assets/ (the user's own work, like a written note)."""
    assets = folder / ASSETS
    try:
        return os.path.isdir(safe_io._os_path(assets)) and any(
            asset_name_ok(p.name) and safe_io.is_file(p) for p in safe_io._os_path(assets).iterdir()
        )
    except OSError:
        return True  # can't tell: treated as there, so nothing is thrown away


def check_assets_target(folder: Path) -> Path:
    """`folder`'s assets/, if images may be copied into it: a folder inside it, or not there
    yet. NoteError otherwise (checked before a merge changes anything)."""
    assets = folder / ASSETS
    not_a_folder = os.path.lexists(safe_io._os_path(assets)) and not os.path.isdir(
        safe_io._os_path(assets)
    )
    if not_a_folder or not _inside(assets, folder):
        raise NoteError("the kept document's assets folder isn't a folder in its notes folder")
    return assets


def copy_assets(src_folder: Path, dst_folder: Path, tag: str) -> tuple[int, dict[str, str]]:
    """Merging two documents (add_book.merge_into): the images of `src_folder` into
    `dst_folder`'s assets/, never over one there. Each tries its own name, then
    <name>-from-<tag>.<ext>, -from-<tag>-2, ...: a name already holding the very same image
    (a plain file in assets/, not a link) is used as it is, a free one gets a copy, any other
    file is passed over. So a merge cut off and run again copies nothing twice. The new names
    are returned as {old name: new name}, so links in the merged notes can follow. Only plain
    image files inside the folder (no links out of it). Returns (images copied, renames)."""
    src_assets = src_folder / ASSETS
    if not os.path.isdir(safe_io._os_path(src_assets)) or not _inside(src_assets, src_folder):
        return 0, {}
    dst_assets = check_assets_target(dst_folder)
    copied, renamed = 0, {}
    for path in sorted(safe_io._os_path(src_assets).iterdir()):
        if (
            not asset_name_ok(path.name)
            or not safe_io.is_file(path)
            or not _inside(path, src_assets)
        ):
            continue
        data = safe_io.read_bytes(path)
        for target in _merge_names(dst_assets, path.name, tag):
            if _same_image(target, dst_assets, data):
                break  # already there (the same name, or an earlier merge's copy)
            if os.path.lexists(safe_io._os_path(target)):
                continue  # another image (or a link): never touched
            try:
                safe_io.create_bytes(target, data, require_atomic=True)
            except FileExistsError:  # taken just now: is it this very image?
                if _same_image(target, dst_assets, data):
                    break
                continue
            copied += 1
            break
        else:
            raise NoteError(f"no free name for {path.name} in the kept document's assets")
        if target.name != path.name:
            renamed[path.name] = target.name
    return copied, renamed


def _merge_names(assets: Path, name: str, tag: str):
    """The names an image coming from a merge may take, always in the same order: its own,
    then <stem>-from-<tag>, -from-<tag>-2, ... (99 in all)."""
    yield assets / name
    stem, ext = os.path.splitext(name)
    for n in range(1, 99):
        suffix = f"-from-{tag[:40]}{'' if n == 1 else f'-{n}'}"
        # A valid long source name must still be servable after adding a collision tag.
        yield assets / f"{stem[: 141 - len(suffix)]}{suffix}{ext}"


def _same_image(target: Path, assets: Path, data: bytes) -> bool:
    """`target` is a plain file in `assets` (no link, nothing pointing elsewhere) holding
    exactly `data`."""
    try:
        info = os.lstat(safe_io._os_path(target))
    except OSError:
        return False
    if not stat.S_ISREG(info.st_mode) or info.st_size != len(data) or not _inside(target, assets):
        return False
    try:
        return safe_io.read_bytes(target) == data
    except OSError:
        return False


def relink(text: str, renamed: dict[str, str]) -> str:
    """A note's links to images that were given new names (copy_assets) made to follow them:
    ](assets/<old>) and ](./assets/<old>), also written <…> or percent-encoded."""
    for old, new in renamed.items():
        for spelled, replacement in ((old, new), (quote(old), quote(new))):
            pattern = r"(\]\(\s*<?(?:\./)?" + ASSETS + "/)" + re.escape(spelled) + r"(?=[\s)>#?])"
            text = re.sub(pattern, lambda m, r=replacement: m[1] + r, text)
    return text


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
