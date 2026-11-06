"""💾 Back up the library to a folder you choose (OneDrive, a USB stick, another disk): the
library page's backup for everyone without git (e.g. the ready-to-use package).

    uv run scripts/folder_backup.py     # the same from the terminal

Each backup is a dated zip of everything you made: notes, reading progress, vocabulary and
review progress, topic notes, glossaries, catalog, shelves, scripts, code ("<library name>
2026-11-06 1530.zip"; the newest KEEP are kept). The PDFs are big and don't change, so they
don't go into every zip: with "backup_pdfs" they're copied once into "PDFs" next to the zips,
and later only new or changed ones. A PDF removed from the library stays in the backup.

The server backs up by itself once a day when it starts (auto_backup), and only when
something changed since the last zip.
"""

import argparse
import re
import shutil
import tomllib
import zipfile
from datetime import datetime
from pathlib import Path

import paths

LIBRARY = paths.LIBRARY
KEEP = 30  # zips kept; older ones are deleted (only ours, by name)
PDF_FOLDERS = ("books", "papers", "theses")
# Not in the zip: the PDFs (copied separately), the archive (removed items, original scans),
# caches and the page that is rebuilt from the catalog
SKIP_TOP = {"archive", ".cache", ".git", "library.html"}
SKIP_SUFFIXES = {".pdf", ".djvu", ".epub"}
SKIP_ANYWHERE = {"__pycache__", ".pytest_cache", ".ipynb_checkpoints"}
ZIP_RE = re.compile(r" (\d{4}-\d{2}-\d{2} \d{4})(?:-\d+)?\.zip$")
RESTORE = """myLibrary backup / 书库备份
================================

这个 zip 里是你的笔记、阅读进度、生词本和书目。恢复：把它解压到书库文件夹里
（设置 ⚙ Settings 里的 Library folder），再把 "PDFs" 文件夹里的 books、papers、theses
复制回去，然后在书库页点 ⟳ Refresh（刷新）。
This zip holds your notes, reading progress, vocabulary and catalog. To restore: unzip it
into your library folder (⚙ Settings, Library folder), copy books, papers and theses from
the "PDFs" folder next to it back into that folder, then click ⟳ Refresh on the library page.
"""


def library_name(library: Path) -> str:
    try:
        with open(library / "library.toml", "rb") as f:
            name = str(tomllib.load(f).get("name") or "")
    except OSError, ValueError:
        name = ""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name or library.name).strip(" .")
    return name or "myLibrary"


def your_files(library: Path) -> list[Path]:
    """What goes into the zip: everything in the library but PDFs, archive and caches."""
    found = []
    for path in sorted(library.rglob("*")):
        rel = path.relative_to(library)
        if not path.is_file() or rel.parts[0] in SKIP_TOP or path.suffix.lower() in SKIP_SUFFIXES:
            continue
        if SKIP_ANYWHERE & set(rel.parts) or (
            rel.parts[0] in PDF_FOLDERS and rel.name == ".gitkeep"
        ):
            continue
        found.append(path)
    return found


def zips(dest: Path, library: Path) -> list[Path]:
    """This library's backups in dest, oldest first."""
    prefix = library_name(library) + " "
    if not dest.is_dir():
        return []
    ours = [p for p in dest.glob("*.zip") if p.name.startswith(prefix) and ZIP_RE.search(p.name)]
    return sorted(ours, key=lambda p: p.stat().st_mtime)


def status(dest: str | Path, library: Path | None = None) -> dict:
    """For Settings: the last backup ({} if none)."""
    library = library or LIBRARY
    if not dest:
        return {}
    found = zips(Path(dest), library)
    if not found:
        return {"count": 0}
    last = found[-1]
    when = datetime.fromtimestamp(last.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    return {"count": len(found), "last": last.name, "when": when}


def _changed_since(files: list[Path], since: float) -> bool:
    return any(f.stat().st_mtime > since for f in files)


def _copy_pdfs(library: Path, dest: Path) -> tuple[int, int]:
    """New or changed PDFs into dest/PDFs/<folder>/; (files copied, bytes)."""
    copied = size = 0
    for folder in PDF_FOLDERS:
        for pdf in sorted((library / folder).glob("*.pdf")):
            target = dest / "PDFs" / folder / pdf.name
            info = pdf.stat()
            if target.exists():
                there = target.stat()
                if there.st_size == info.st_size and there.st_mtime >= info.st_mtime - 2:
                    continue  # already there (2 s: FAT drives keep coarse times)
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(".pdf.part")
            shutil.copy2(pdf, tmp)
            tmp.replace(target)
            copied += 1
            size += info.st_size
    return copied, size


def back_up(
    dest: str | Path | None = None,
    pdfs: bool | None = None,
    library: Path | None = None,
    only_if_changed: bool = False,
) -> dict:
    """Make a backup now: {"message", "file", "pdfs"}. Raises ValueError with a message the
    page can show when there's no folder or it can't be written."""
    library = library or LIBRARY
    settings = paths.load_settings()
    dest = Path(dest if dest is not None else settings.get("backup_folder") or "")
    pdfs = settings.get("backup_pdfs") if pdfs is None else pdfs
    if not str(dest) or str(dest) == ".":
        raise ValueError("choose a backup folder first (⚙ Settings)")
    if not dest.is_absolute():
        raise ValueError("the backup folder must be a full path, e.g. D:\\Backups")
    if dest.resolve() == library.resolve() or library.resolve() in dest.resolve().parents:
        raise ValueError("the backup folder can't be inside the library itself")
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ValueError(f"can't use {dest}: {e.strerror or e}") from None

    files = your_files(library)
    previous = zips(dest, library)
    made = None
    if not (only_if_changed and previous and not _changed_since(
        files, previous[-1].stat().st_mtime
    )):  # fmt: skip
        stamp = datetime.now().strftime("%Y-%m-%d %H%M")
        target = dest / f"{library_name(library)} {stamp}.zip"
        n = 1
        while target.exists():  # two backups in one minute
            n += 1
            target = dest / f"{library_name(library)} {stamp}-{n}.zip"
        part = target.with_suffix(".zip.part")
        with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("RESTORE.txt", RESTORE)
            for f in files:
                z.write(f, f.relative_to(library).as_posix())
        part.replace(target)
        made = target
        for old in zips(dest, library)[:-KEEP]:
            old.unlink(missing_ok=True)

    copied, size = _copy_pdfs(library, dest) if pdfs else (0, 0)
    parts = []
    if made:
        parts.append(f"saved {made.name} ({len(files)} files)")
    else:
        parts.append("nothing changed since the last backup")
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
    if not folder:
        return ""
    dest = Path(folder)
    if not dest.is_dir():  # e.g. the USB stick isn't plugged in
        return f"backup folder {dest} not found; no backup today"
    previous = zips(dest, library)
    if previous and datetime.now().timestamp() - previous[-1].stat().st_mtime < 20 * 3600:
        return ""
    try:
        return back_up(dest, library=library, only_if_changed=True)["message"]
    except (OSError, ValueError) as e:
        return f"backup failed: {e}"


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
