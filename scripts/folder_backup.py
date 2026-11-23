"""💾 Back up the library to a folder you choose (OneDrive, a USB stick, another disk): the
library page's backup for everyone without git (e.g. the ready-to-use package).

    uv run scripts/folder_backup.py     # the same from the terminal

Each backup is a dated zip of everything you made: notes, reading progress, vocabulary and
review progress, topic notes, glossaries, catalog, shelves, scripts, code ("<library name>
[<key>] 2026-11-06 1530.zip"; the newest KEEP are kept). The PDFs are big and don't change, so
they don't go into every zip: with "backup_pdfs" they're copied once into "PDFs" next to the
zips, and later only new or changed ones. A PDF removed from the library stays in the backup.

What counts as "the same" is always the content, read in full at this backup (M7.1 S2): a
file's size, times or id never prove it unchanged (FA-04: a PDF with marks saved can keep its
size and time; FA-05: a deleted or renamed file leaves no newer time behind). A PDF is skipped
only when its backup copy holds the same bytes, and the zip only when the last zip holds
exactly the library's files with the same bytes. Files are compared in chunks (CHUNK), never
whole in memory. A new copy or zip is written under a temporary name, checked, and only then
put in place, so a failed or interrupted backup leaves the previous one as it was and is never
reported as done.

Also (M7.1 S2, after Codex's review): files are listed and read through Windows' long-path
form, and a folder or file that can't be read fails the backup rather than shrinking it (B41).
One backup at a time works in a backup folder, whichever process or spelling of the folder
(_one_backup_at_a_time); a finished zip is never replaced by another. Old zips are deleted by
the dates in their names, never the one just made, and none at all while any date is in the
future. Every member of the last zip, the instructions too, is read to its end before it counts
as "the same". A library's own RESTORE.txt (any case) keeps its name: the instructions take
another (INSTRUCTIONS), a plain 8.3 name.

And (round 3): on Windows every file is read and written through the extended-length form, so
a name is always taken exactly as written; a name Windows would drop a dot or space from,
keeps for a device, doesn't allow, could take for a short name, or can't tell from a sibling's
but by case fails the backup before anything is written, naming it (_name_problem). User files
are never renamed or changed by the backup.

Several libraries can share one backup folder: each one's backups carry its key
(libraries.scope: its library id and folder), so one library never counts, replaces or deletes
another's, even when both have the same name. A library without a library id (made before
libraries had ids) keeps the old names ("<library name> 2026-11-06 1530.zip", PDFs in
"PDFs/"). The Test & Demo library is never backed up.

The server backs up by itself once a day when it starts (auto_backup), and only when
something changed since the last zip.
"""

import argparse
import os
import re
import shutil
import time
import tomllib
import uuid
import zipfile
import zlib
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import libraries
import paths
import safe_io

LIBRARY = paths.LIBRARY
KEEP = 30  # zips kept; older ones are deleted (only ours, by name)
CHUNK = 1 << 20  # bytes read at a time when copying or comparing: memory stays bounded
TRIES = 3  # attempts when a file changes or disappears while it is being backed up
# What reading an earlier zip can raise when it is damaged, cut short or not one of ours
_UNREADABLE_ZIP = (
    OSError,
    EOFError,
    RuntimeError,
    NotImplementedError,
    ValueError,
    zipfile.BadZipFile,
    zlib.error,
)
PDF_FOLDERS = ("books", "papers", "theses")
# Not in the zip: the PDFs (copied separately), the archive (removed items, original scans),
# caches and the page that is rebuilt from the catalog
SKIP_TOP = {"archive", ".cache", ".git", "library.html"}
SKIP_SUFFIXES = {".pdf", ".djvu", ".epub"}
SKIP_ANYWHERE = {"__pycache__", ".pytest_cache", ".ipynb_checkpoints"}
# The running server's lock and port note (libraries.hold_library): this computer's, and the
# lock can't be read while held
SKIP_FILES = {(".myLibrary", "server.lock"), (".myLibrary", "server.json")}
ZIP_RE = re.compile(r" (\d{4}-\d{2}-\d{2} \d{4})(?:-(\d+))?\.zip$")
# One backup at a time per backup folder, across threads and processes (the page, the
# automatic backup at start, the terminal): an operating-system lock on this file in the folder
# itself, so every spelling of the folder (a junction, a mapped drive) meets the same lock.
LOCK_NAME = ".myLibrary-backup.lock"
LOCK_WAIT = 60  # seconds a backup waits for another one to the same folder to finish
FUTURE = 60  # seconds a backup's date may be ahead of this computer's clock (rounding)
# The instructions' name in the zip. A library with its own top-level file or folder of that
# name (in any case: Windows doesn't tell them apart) gets the next one instead, so unzipping
# never puts one over the other. Each is a plain 8.3 name: Windows gives it no second, short
# name (as it gives "RESTORE (...).txt" the short name RESTOR~1.TXT, which a library's own
# file of that name would be written over or into when unzipped: S2 round 3).
INSTRUCTIONS = ("RESTORE.txt", "RESTORE1.TXT", "RESTORE2.TXT")
# Names Windows can't keep as they are, or would restore as another name (S2 round 3): it
# drops a trailing dot or space; these names are its devices (also with an extension); these
# characters aren't allowed; and a name shaped like one of its 8.3 short names ("NOTES~1.MD")
# could be a second name of another file once unzipped.
_DEVICES = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} | {
    f"{port}{n}" for port in ("COM", "LPT") for n in (*"123456789", "¹", "²", "³")
}
_NOT_IN_NAMES = set('<>:"/\\|?*') | {chr(c) for c in range(32)}
_SHORT_NAME = re.compile(r"[^.]{0,7}~[0-9][^.]{0,6}(\.[^.]{1,3})?")
RESTORE = """myLibrary backup / 书库备份
================================

这个 zip 里是你的笔记、阅读进度、生词本和书目。恢复：把它解压到书库文件夹里
（设置 ⚙ Settings 里的 Library folder），再把 "PDFs" 文件夹（或其中以本书库命名的文件夹）里的
books、papers、theses 复制回去，然后在书库页点 ⟳ Refresh（刷新）。
This zip holds your notes, reading progress, vocabulary and catalog. To restore: unzip it
into your library folder (⚙ Settings, Library folder), copy books, papers and theses from
the "PDFs" folder next to it (or its folder named like this zip) back into that folder,
then click ⟳ Refresh on the library page.
"""


class BackupIncomplete(ValueError):
    """Part of a backup couldn't be made. What it could make is in place and complete; what it
    couldn't keeps its previous backup unchanged. A ValueError, so the page shows the message."""


class _KeptChanging(OSError):
    """A PDF changed on every attempt to copy it (TRIES)."""


def _why(error: OSError) -> str:
    """An OSError as words for the message: what went wrong and with which file."""
    what = error.strerror or str(error)
    return f"{what}: {Path(error.filename).name}" if error.filename and error.strerror else what


def library_name(library: Path) -> str:
    try:
        with open(_os(library / "library.toml"), "rb") as f:
            name = str(tomllib.load(f).get("name") or "")
    except OSError, ValueError:
        name = ""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name or library.name).strip(" .")
    return name or "myLibrary"


def backup_name(library: Path) -> str:
    """The start of this library's backup names: its name, and its key when it has a library
    id (libraries.scope; one library's backups never match another's)."""
    name = library_name(library)
    return f"{name} [{libraries.scope(library)}]" if libraries.info(library)["id"] else name


def _pdf_folder(library: Path, dest: Path) -> Path:
    if libraries.info(library)["id"]:
        return dest / "PDFs" / backup_name(library)
    return dest / "PDFs"


def _entries(folder: Path) -> list[os.DirEntry]:
    """A folder's entries, also past Windows' 260-character limit. Raises OSError when it can't
    be read: a folder that can't be listed is never taken for an empty one (B41)."""
    with os.scandir(_os(folder)) as found:
        return list(found)


def _name_problem(name: str, short_names: bool = True) -> str:
    """Why Windows can't keep this file or folder name as it is, or would restore it as another
    file ("" when it can). short_names=False leaves out the 8.3 short-name shape (in a folder's
    own path, such a name is the same folder's second name: no other folder is reached)."""
    if name.endswith((".", " ")):
        return "ends in a dot or a space, which Windows drops (it would become another name)"
    if _NOT_IN_NAMES & set(name):
        return "has a character Windows doesn't allow in names"
    if name.split(".")[0].rstrip(" ").upper() in _DEVICES:
        return "is a name Windows keeps for a device"
    if not short_names:
        return ""
    if len(name) <= 12 and _SHORT_NAME.fullmatch(name) and len(name.split(".")[0]) <= 8:
        return (
            "looks like a Windows short name (like PROGRA~1), which could be a second name of "
            "another file once restored"
        )
    return ""


class AmbiguousName(BackupIncomplete):
    """A file or folder to back up whose name Windows can't keep, or would restore as another
    file (_name_problem). Nothing is written then: no zip, no PDF copy, no old zip deleted."""


def _check_names(folder_rel: tuple[str, ...], names: list[str]) -> None:
    """AmbiguousName for the first name in this folder that can't be kept as it is, or that
    differs from another only in case (Windows would make one file of the two)."""
    seen = {}
    for name in names:
        shown = "/".join((*folder_rel, name))
        if problem := _name_problem(name):
            raise AmbiguousName(
                f"can't back up {shown}: its name {problem}. Rename it and back up again "
                "(a name ending in a dot or space can be renamed in a terminal: "
                'ren "\\\\?\\<its full path>" "<new name>"); nothing was changed'
            )
        if (other := seen.setdefault(name.casefold(), name)) != name:
            raise AmbiguousName(
                f"can't back up {shown}: {other} in the same folder differs from it only in "
                "upper and lower case, and Windows would restore the two as one file. Rename "
                "one of them and back up again; nothing was changed"
            )


def your_files(library: Path) -> list[Path]:
    """What goes into the zip: everything in the library but PDFs, archive and caches.

    Listed folder by folder through the long-path form (B41: a plain rglob/is_file on Windows
    skipped, without a word, any file whose path was past 260 characters). As rglob did, it
    goes into junctions but not into folder symlinks, and takes symlinked files; a link back to
    a folder it is already inside isn't followed again. Raises OSError for anything it can't
    read or tell apart (a folder it may not list, a dangling link): never a shorter list; and
    AmbiguousName for a name Windows can't keep or would restore as another (_check_names),
    checked before anything is read through it."""
    found = []
    stack = [(library, (), {os.path.normcase(str(safe_io.real_path(library)))})]
    while stack:
        folder, rel, inside = stack.pop()
        kept = []  # (the names this folder gives the zip: their own and their folders')
        for entry in _entries(folder):
            parts = (*rel, entry.name)
            if parts[0] in SKIP_TOP or entry.name in SKIP_ANYWHERE:
                continue
            path = folder / entry.name
            if entry.is_dir(follow_symlinks=False) and not entry.is_symlink():
                _check_names(rel, [entry.name])
                kept.append(entry.name)
                real = os.path.normcase(str(safe_io.real_path(path)))
                if real not in inside:  # (a junction to a folder above: its files are listed)
                    stack.append((path, parts, inside | {real}))
            elif entry.is_symlink() and entry.is_dir():
                continue  # a folder symlink: not followed (as rglob)
            elif entry.is_file():
                if entry.name.lower().endswith(tuple(SKIP_SUFFIXES)) or parts in SKIP_FILES:
                    continue
                if parts[0] in PDF_FOLDERS and entry.name == ".gitkeep":
                    continue
                _check_names(rel, [entry.name])
                kept.append(entry.name)
                found.append((parts, path))
            else:  # a dangling link, a device: can't be backed up, and never left out silently
                raise OSError(2, "a link to something that isn't there", str(path))
        _check_names(rel, kept)  # (two that differ only in case)
    return [path for parts, path in sorted(found, key=lambda item: item[0])]


def _library_pdfs(library: Path) -> list[tuple[str, Path]]:
    """The library's PDFs, (folder, path) each: the whole inventory, taken before the backup
    publishes or deletes anything (S2 round 4). AmbiguousName for a PDF name Windows can't keep
    (never read: "NUL.pdf" in the ordinary form is a device), OSError for a PDF folder that
    can't be listed: the backup is then refused as a whole, never made without them."""
    pdfs = []
    for folder in PDF_FOLDERS:
        try:
            entries = _entries(library / folder)
        except FileNotFoundError:
            continue  # (no such folder: no PDFs of that kind)
        names = []
        for entry in sorted(entries, key=lambda e: e.name):
            if entry.name.lower().endswith(".pdf") and entry.is_file():
                names.append(entry.name)
                pdfs.append((folder, library / folder / entry.name))
        for name in names:
            _check_names((folder,), [name])
        _check_names((folder,), names)  # (two that differ only in case)
    return pdfs


def _check_own_path(path: Path, what: str) -> None:
    """AmbiguousName when a folder name in the library's or the backup folder's own path is one
    Windows changes in the ordinary form (S2 round 4: "lib." was taken for "lib", another
    library, whose id, zips and PDF copies a backup of "lib." then used and deleted). Checked
    before anything is read through the path or created. Junctions, links and 8.3 short names
    in the path are fine: they reach the same folder, never another."""
    path = Path(path)
    for part in path.parts[1:] if path.anchor else path.parts:
        if part in (".", ".."):
            continue
        if problem := _name_problem(part, short_names=False):
            raise AmbiguousName(
                f"can't back up: the {what} folder's own path has a folder named {part!r}, "
                f"which {problem}; Windows would take it for another folder. Rename that folder "
                '(in a terminal: ren "\\\\?\\<its full path>" "<new name>"), choose it again in '
                "⚙ Settings and back up again; nothing was changed"
            )


def _when(zip_path: Path) -> tuple[datetime | None, int]:
    """The date and number in a backup's name ("... 2026-11-06 1530-2.zip"); None for a date
    that isn't one."""
    match = ZIP_RE.search(zip_path.name)
    try:
        stamp = datetime.strptime(match[1], "%Y-%m-%d %H%M")
    except ValueError:
        stamp = None
    return stamp, int(match[2] or 1)


def zips(dest: Path, library: Path) -> list[Path]:
    """This library's backups in dest, oldest first: exactly its name and a time (not those of
    a library whose name only starts the same, "Physics" and "Physics 2"). Ordered by the date
    in their names, which this tool writes, not by the files' times, which copying, a sync
    service or a wrong clock can change (a name with no real date sorts last)."""
    ours_re = re.compile(re.escape(backup_name(library)) + ZIP_RE.pattern)
    try:
        entries = _entries(dest)
    except OSError:
        return []
    ours = [dest / e.name for e in entries if ours_re.fullmatch(e.name) and e.is_file()]

    def order(path):
        stamp, number = _when(path)
        return (stamp is None, stamp or datetime.min, number, path.name)

    return sorted(ours, key=order)


def _mtime(path: Path) -> float:
    return os.stat(_os(path)).st_mtime


def status(dest: str | Path, library: Path | None = None) -> dict:
    """For Settings: the last backup ({} if none)."""
    library = library or LIBRARY
    if not dest:
        return {}
    found = zips(Path(dest), library)
    if not found:
        return {"count": 0}
    last = found[-1]
    when = datetime.fromtimestamp(_mtime(last)).strftime("%Y-%m-%d %H:%M")
    return {"count": len(found), "last": last.name, "when": when}


def _os(path: Path) -> Path:
    r"""The path to hand to the system for every file the backup reads or writes. On Windows,
    always the extended-length form (\\?\...) for an absolute path, short or long: in it Windows
    takes each name exactly as written. In the ordinary form it drops a trailing dot or space,
    so "note.md." would be read as "note.md", another file (S2 round 3). Lexical only
    (normpath; abspath would drop them too). Also past the 260-character limit (B41)."""
    text = os.fspath(path)
    if os.name != "nt" or text.startswith(("\\\\?\\", "//?/")) or not os.path.isabs(text):
        return safe_io._os_path(path)
    full = os.path.normpath(text)
    if full.startswith("\\\\"):  # a network path: \\server\share\... -> \\?\UNC\server\...
        return Path("\\\\?\\UNC\\" + full[2:])
    return Path("\\\\?\\" + full)


def _read(f) -> bytes:
    """The next CHUNK bytes of f (fewer only at its end)."""
    data = f.read(CHUNK)
    while data and len(data) < CHUNK:
        more = f.read(CHUNK - len(data))
        if not more:
            break
        data += more
    return data


def _same_bytes(a, b) -> bool:
    """Whether two open files hold the same bytes, read to the end of both (stops at the first
    difference). Reading a zip member to its end also checks its CRC."""
    while True:
        x, y = _read(a), _read(b)
        if x != y:
            return False
        if not x:
            return True


def _same_file(a: Path, b: Path) -> bool:
    """True only when a and b hold the same bytes now. A different size proves a change; an
    equal size, time or anything else short of the content proves nothing (FA-04)."""
    if os.stat(_os(a)).st_size != os.stat(_os(b)).st_size:
        return False
    with open(_os(a), "rb") as x, open(_os(b), "rb") as y:
        return _same_bytes(x, y)


def _instructions_name(library: Path) -> str:
    """The name the instructions get in this library's zip: the first of INSTRUCTIONS that
    no top-level file or folder of the library has, in any case (Windows doesn't tell
    "restore.txt" from "RESTORE.txt", so unzipping one would put it over the other).
    BackupIncomplete if every one is taken: nothing is written then."""
    taken = {entry.name.casefold() for entry in _entries(library)}
    for name in INSTRUCTIONS:
        if name.casefold() not in taken:
            return name
    raise BackupIncomplete(
        "the library has its own files or folders named like the backup's instructions ("
        + ", ".join(INSTRUCTIONS) + "); rename one of them so the backup can hold both"
    )  # fmt: skip


def _drain(member) -> None:
    """Read a zip member to its end: that checks its CRC."""
    while _read(member):
        pass


def _zip_differs(
    previous: Path, library: Path, files: list[Path], instructions: str
) -> tuple[bool, str]:
    """(differs, problem): whether the library's files differ from what its last zip holds, read
    in full now from the zip itself (FA-05: a deleted, renamed or added file, or a change under an
    old time, all show). "The same" only once every member, the instructions too, has been read
    to its end with a correct CRC; never for a zip that can't be, has a name twice or isn't laid
    out as ours; then `problem` says why, for the message. The instructions' text may differ
    (an older version of this tool wrote other words)."""
    current = {f.relative_to(library).as_posix(): f for f in files}
    try:
        with zipfile.ZipFile(_os(previous)) as z:
            members = z.infolist()
            names = [m.filename for m in members]
            if len(set(names)) != len(names):
                return True, "it has a file name twice"
            if set(names) != {instructions, *current}:
                return True, ""  # added, deleted or renamed files
            for member in members:
                if member.filename == instructions:  # (written by us, not library content)
                    with z.open(member) as text:
                        _drain(text)
                    continue
                try:
                    now = open(_os(current[member.filename]), "rb")
                except OSError:  # gone since it was listed: a change (the new zip will tell)
                    return True, ""
                with now, z.open(member) as before:
                    if os.fstat(now.fileno()).st_size != member.file_size:
                        return True, ""
                    if not _same_bytes(before, now):
                        return True, ""
    except _UNREADABLE_ZIP as e:
        return True, f"it can't be read ({e})"
    return False, ""


def _put_in_place(tmp: Path, target: Path) -> None:
    """Replace the PDF's backup copy with the checked new one, in one step (waiting out a
    moment when another program has it open, as safe_io does)."""
    safe_io._retry(lambda: os.replace(_os(tmp), _os(target)), target)


def _copy_one(pdf: Path, target: Path) -> int:
    """Copy pdf over target, whole or not at all; the bytes copied. Written under a temporary
    name of this attempt's own, checked against the PDF, and only then put in place: a failed
    or cut-off copy leaves the earlier backup copy as it was. A PDF that changes while it is
    copied (marks being saved) is copied again, at most TRIES times."""
    _os(target.parent).mkdir(parents=True, exist_ok=True)
    for _ in range(TRIES):
        tmp = target.with_name(f".{target.name}.{uuid.uuid4().hex[:8]}.part")
        try:
            times = os.stat(_os(pdf))
            shutil.copyfile(_os(pdf), _os(tmp))  # (the system's own copy: fast for big files)
            with open(_os(tmp), "r+b") as out:  # on the disk before it replaces anything
                os.fsync(out.fileno())
            os.utime(_os(tmp), ns=(times.st_atime_ns, times.st_mtime_ns))  # (as copy2 did)
            if _same_file(pdf, tmp):  # what was copied is what the PDF holds now
                copied = os.stat(_os(tmp)).st_size
                _put_in_place(tmp, target)
                return copied
        finally:
            _os(tmp).unlink(missing_ok=True)
    raise _KeptChanging(f"it changed while it was being copied ({TRIES} tries)")


def _copy_pdfs(
    library: Path, dest: Path, pdfs: list[tuple[str, Path]] | None = None
) -> tuple[int, int, list[str]]:
    """New or changed PDFs into dest/PDFs/[<backup name>/]<folder>/: (files copied, bytes,
    the PDFs that couldn't be backed up, with why). A PDF is skipped only when its backup copy
    holds the same bytes (FA-04). `pdfs`: the inventory already taken (_library_pdfs)."""
    copied = size = 0
    failed = []
    for folder, pdf in _library_pdfs(library) if pdfs is None else pdfs:
        target = _pdf_folder(library, dest) / folder / pdf.name
        try:
            if _os(target).is_file() and _same_file(pdf, target):
                continue
            size += _copy_one(pdf, target)
            copied += 1
        except OSError as e:  # this one keeps its earlier copy; the others go on
            failed.append(f"{folder}/{pdf.name} ({e.strerror or e})")
    return copied, size, failed


def _check_zip(part: Path, names: list[str]) -> None:
    """The zip just written holds exactly these members, each read back to its end with a
    correct CRC (testzip)."""
    with zipfile.ZipFile(_os(part)) as z:
        if z.namelist() != names:
            raise BackupIncomplete("the new zip doesn't hold the files it should")
        if (bad := z.testzip()) is not None:
            raise BackupIncomplete(f"{bad} in the new zip can't be read back")


def _publish_new(part: Path, target: Path) -> None:
    """Give the finished zip its name, never over an existing file (FileExistsError then): a
    zip another backup already finished is never replaced."""
    if os.name == "nt":  # (renaming onto an existing file is refused on Windows)
        safe_io._retry(lambda: os.rename(_os(part), _os(target)), target)
        return
    try:
        os.link(_os(part), _os(target))  # (refused if the name exists, on every system)
    except FileExistsError:
        raise
    except OSError:  # a drive without hard links (FAT): we hold the folder's backup lock
        if _os(target).exists():
            raise FileExistsError(17, "File exists", str(target)) from None
        os.rename(_os(part), _os(target))
        return
    _os(part).unlink()


def _publish(part: Path, dest: Path, library: Path) -> Path:
    """The finished zip under this library's dated name; "-2", "-3", ... when a backup this
    minute already has the name."""
    base = f"{backup_name(library)} {datetime.now().strftime('%Y-%m-%d %H%M')}"
    for n in range(1, 1000):
        target = dest / (f"{base}.zip" if n == 1 else f"{base}-{n}.zip")
        try:
            _publish_new(part, target)
            return target
        except FileExistsError:
            continue
    raise BackupIncomplete("no free name for the new zip in the backup folder")


def _write_zip(library: Path, dest: Path) -> tuple[Path, int]:
    """A new dated zip of the library's files: (the zip, files in it). Written under a
    temporary name, flushed to the disk and read back before it gets its real name, so a zip
    with our name is always complete. A file deleted while the zip is made: listed again (at
    most TRIES times)."""
    last = None
    for _ in range(TRIES):
        part = dest / f".{backup_name(library)} {uuid.uuid4().hex[:8]}.zip.part"
        try:
            files = your_files(library)
            instructions = _instructions_name(library)
            names = [f.relative_to(library).as_posix() for f in files]
            with open(_os(part), "xb") as out:
                with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
                    z.writestr(instructions, RESTORE)
                    for f, name in zip(files, names, strict=True):
                        z.write(_os(f), name)
                out.flush()
                os.fsync(out.fileno())
            _check_zip(part, [instructions, *names])
            return _publish(part, dest, library), len(files)
        except FileNotFoundError as e:
            if not _os(dest).exists():  # the backup folder went (a USB stick pulled out)
                raise BackupIncomplete(f"the backup folder went away ({e.strerror})") from None
            last = e  # (a file or folder went while it was listed or zipped: list again)
        finally:
            _os(part).unlink(missing_ok=True)
    raise BackupIncomplete(
        f"a file or folder kept disappearing or can't be found ({TRIES} tries; last: {_why(last)})"
    )


def _prune(dest: Path, library: Path, made: Path) -> str:
    """Delete this library's zips beyond KEEP, oldest first by the dates in their names, never
    the one just made. When any of them has a date in the future (by its name or its file
    time) or a name with no real date, the order can't be trusted: nothing is deleted this
    time, and the message says so."""
    found = zips(dest, library)
    now = time.time()
    for z in found:
        stamp, _ = _when(z)
        if stamp is None or stamp.timestamp() > now + FUTURE or _mtime(z) > now + FUTURE:
            return f"no older backup deleted: {z.name} has a date in the future"
    others = [z for z in found if z != made]
    for old in others[: max(0, len(others) - (KEEP - 1))]:
        _os(old).unlink(missing_ok=True)
    return ""


class BackupBusy(ValueError):
    """Another backup to the same folder is running (LOCK_WAIT)."""


def _pause() -> None:
    time.sleep(0.05)


def _try_lock(handle) -> bool:
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(handle) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def _one_backup_at_a_time(dest: Path, wait: float):
    """While held, no other backup (thread or process, any library) works in this backup
    folder: deciding what changed, naming, publishing, deleting old zips and copying PDFs all
    happen inside it. An operating-system lock on dest/LOCK_NAME, as for the server's lock
    (libraries.hold_library): the system lets go of it when a process ends, however it ends.
    Waits up to `wait` seconds, then BackupBusy. The lock file stays (an empty marker)."""
    handle = open(_os(dest / LOCK_NAME), "a+b")
    try:
        deadline = time.monotonic() + wait
        while not _try_lock(handle):
            if time.monotonic() >= deadline:
                raise BackupBusy(
                    "another backup to this folder is running (from the page, the automatic "
                    "one at start or the terminal); try again when it has finished"
                )
            _pause()
        try:
            yield
        finally:
            _unlock(handle)
    finally:
        handle.close()


def back_up(
    dest: str | Path | None = None,
    pdfs: bool | None = None,
    library: Path | None = None,
    only_if_changed: bool = False,
) -> dict:
    """Make a backup now: {"message", "file", "pdfs"}. Raises ValueError with a message the
    page can show when there's no folder or it can't be written, and BackupIncomplete (a
    ValueError) when the zip or a PDF couldn't be backed up: then the previous zip, the older
    zips and each failed PDF's previous copy are all left as they were.
    only_if_changed: no new zip when the last one holds exactly the library's files, byte for
    byte (FA-05); the PDFs are still checked."""
    library = library or LIBRARY
    settings = paths.load_settings()
    dest = Path(dest if dest is not None else settings.get("backup_folder") or "")
    pdfs = settings.get("backup_pdfs") if pdfs is None else pdfs
    _check_destination(dest, library)
    with _one_backup_at_a_time(dest, LOCK_WAIT):
        return _back_up(dest, pdfs, library, only_if_changed)


def _check_destination(dest: Path, library: Path) -> None:
    """ValueError (for the page) unless dest can take this library's backups; creates it.
    The library's and the backup folder's own paths are checked first (_check_own_path), before
    the library's id is read, the paths are resolved or anything is created: the library's
    identity (its id and folder: the backups' names, the lock, containment) is then that of the
    folder named, never of another that Windows would take it for."""
    if not str(dest) or str(dest) == ".":
        raise ValueError("choose a backup folder first (⚙ Settings)")
    if not dest.is_absolute():
        raise ValueError("the backup folder must be a full path, e.g. D:\\Backups")
    _check_own_path(library, "library")
    _check_own_path(dest, "backup")
    if libraries.is_test_library(library):
        raise ValueError("the Test & Demo library isn't backed up (it can be reset instead)")
    real_dest, real_library = safe_io.real_path(dest), safe_io.real_path(library)
    if real_dest == real_library or real_library in real_dest.parents:
        raise ValueError("the backup folder can't be inside the library itself")
    try:
        safe_io._refuse_frozen(dest)
    except safe_io.FrozenLocation:
        raise ValueError("the backup folder can't be in the showcase or test library") from None
    try:
        _os(dest).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ValueError(f"can't use {dest}: {e.strerror or e}") from None


def _take_inventory(library: Path, pdfs: bool):
    """(the PDFs to copy, the zip's files, the instructions' name), every name checked. A file
    or folder that goes while it is listed: listed again, at most TRIES times (as _write_zip)."""
    for attempt in range(TRIES):
        try:
            inventory = _library_pdfs(library) if pdfs else []
            return inventory, your_files(library), _instructions_name(library)
        except FileNotFoundError:
            if attempt == TRIES - 1:
                raise


def _back_up(dest: Path, pdfs: bool, library: Path, only_if_changed: bool) -> dict:
    """back_up, holding the backup folder's lock. In this order (S2 round 4): the whole
    inventory and its names are checked (the PDFs' too, when they are backed up), then what
    changed, then the zip is written, checked and published, then the PDFs are copied, and only
    when all of that succeeded are old zips deleted. An inventory that can't be taken or a name
    that can't be kept refuses the backup before anything in the backup folder changes."""
    previous = zips(dest, library)
    made, count, problem = None, 0, ""
    differs = True
    try:
        inventory, files, instructions = _take_inventory(library, pdfs)
        if only_if_changed and previous:
            differs, problem = _zip_differs(previous[-1], library, files, instructions)
        if differs:
            made, count = _write_zip(library, dest)
    except OSError as e:  # nothing new is published and no old zip is deleted
        raise BackupIncomplete(f"no backup made: {_why(e)}") from None

    copied, size, failed = _copy_pdfs(library, dest, inventory) if pdfs else (0, 0, [])
    parts = []
    if made:
        parts.append(f"saved {made.name} ({count} files)")
        if problem:  # the earlier zip is kept as it is, for the user to look at
            parts.append(f"the last backup {previous[-1].name} wasn't trusted: {problem}")
    else:
        parts.append("nothing changed since the last backup")
    if failed:  # never reported as a finished backup; and no old zip deleted for it
        raise BackupIncomplete(
            f"Backup to {dest} not complete: " + "; ".join(parts)
            + (f"; {copied} PDF{'s' if copied != 1 else ''} copied" if copied else "")
            + f"; {len(failed)} PDF{'s' if len(failed) != 1 else ''} not backed up, their "
            "earlier copies kept: " + "; ".join(failed)
            + ("; no older backup deleted" if made else "")
        )  # fmt: skip
    if made and (kept := _prune(dest, library, made)):  # only once all of it succeeded
        parts.append(kept)
    if pdfs:
        parts.append(
            f"{copied} PDF{'s' if copied != 1 else ''} copied ({size / 1e6:.0f} MB)"
            if copied else "the PDFs were already there"
        )  # fmt: skip
    return {
        "message": f"Backed up to {dest}: " + "; ".join(parts),
        "file": made.name if made else "",
        "pdfs": copied,
    }


def auto_backup(library: Path | None = None) -> str:
    """At start: back up once a day when a folder is set and something changed. Never
    raises (a missing USB stick just means no backup today); returns what happened."""
    library = library or LIBRARY
    settings = paths.load_settings()
    folder = settings.get("backup_folder")
    if not folder or libraries.is_test_library(library):
        return ""
    dest = Path(folder)
    if not _os(dest).is_dir():  # e.g. the USB stick isn't plugged in
        return f"backup folder {dest} not found; no backup today"
    try:
        _check_destination(dest, library)
        # Never waits: another backup to this folder is running (one is enough for today)
        with _one_backup_at_a_time(dest, 0):
            if _backed_up_lately(dest, library):  # (decided under the lock)
                return ""
            return _back_up(dest, settings.get("backup_pdfs"), library, True)["message"]
    except (OSError, ValueError) as e:
        return f"backup failed: {e}"


def _backed_up_lately(dest: Path, library: Path) -> bool:
    """A zip of this library made in the last 20 hours. A zip whose time is in the future
    (a wrong clock, a copied folder) doesn't count: it never holds back the daily backup."""
    now = time.time()
    times = [t for z in zips(dest, library) if (t := _mtime(z)) <= now + FUTURE]
    return bool(times) and now - max(times) < 20 * 3600


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    paths.add_argument(parser)
    parser.add_argument("--to", metavar="FOLDER", help="backup folder (default: ⚙ Settings)")
    parser.add_argument("--pdfs", action="store_true", help="also copy the PDFs")
    args = parser.parse_args()
    try:
        print(back_up(args.to, pdfs=True if args.pdfs else None)["message"])
    except ValueError as e:
        raise SystemExit(f"Not backed up: {e}") from None


if __name__ == "__main__":
    _main()
