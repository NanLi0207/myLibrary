"""Give new books (books/), papers (papers/) and theses (theses/) a consistent name and create
their notes.

Every book gets a slug:  <author-surname>-<year>-<short-title>
    e.g. shannon-1997-art-science-optical-design

Title, author and year come from the book itself where possible (ISBN -> Open Library,
PDF metadata, copyright page), with the filename as a fallback; see book_meta.py.

Papers are found by their DOI, arXiv number, or title (see book_meta.identify) and always
end up in papers/; a PDF put into papers/ is a paper even if nothing online knows it.

Theses (PhD, master's, ...) are recognised by their title page ("A thesis submitted ... for the
degree of Doctor of Philosophy", "Dissertation zur Erlangung ...", see thesis_meta.py) and end up
in theses/, with degree, university and supervisors in the catalog. Like books, they get one
notes template per chapter.

A document's identity is its id (a UUID, given once when it's added: see catalog.py); the
slug is only its human-readable name, the base of its file and folder names:
    books/<slug>.pdf  or  papers/<slug>.pdf  or  theses/<slug>.pdf
    notes/<slug>/README.md   (title, author, year, progress)
    notes/<slug>/chNN-<chapter>.md   (one empty notes template per chapter, from the PDF's
                                      table of contents; headings only, you write the content)
    examples/<slug>/chNN_<topic>.py  (only when you ask for one: "Script" on the library page)

Usage:
    uv run scripts/add_book.py --dry-run       # show the proposed names and where they came from
    uv run scripts/add_book.py                 # name new books; add missing chapter templates
    uv run scripts/add_book.py --offline       # don't look ISBNs up on Open Library
    uv run scripts/add_book.py --refresh-chapters   # re-read chapters (keeps notes you wrote)
    uv run scripts/add_book.py --remove <name or id>  # move a document's files to archive/
    uv run scripts/add_book.py --ocr / --no-ocr     # scanned PDFs: OCR without asking / never
    uv run scripts/add_book.py --refresh-keywords   # keywords for papers/theses without any
    uv run scripts/add_book.py books/foo.pdf --author "Warren J. Smith" --year 2008 \
        --title "Modern Optical Engineering"   # override anything that came out wrong
"""

import argparse
import re
import sys
import threading
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import book_meta
import catalog
import library_page
import notes_store
import paths
import safe_io
import shelves
import subjects
import thesis_meta
from book_meta import Meta, ascii_words, identify, isbn13, surname
from book_toc import STOP_WORDS, Chapter, read_toc
from ocr_pdf import ask, make_searchable, needs_ocr, ocr_minutes
from pypdf import PdfReader

LIBRARY = paths.LIBRARY
BOOKS, EXAMPLES, NOTES = LIBRARY / "books", LIBRARY / "examples", LIBRARY / "notes"
PAPERS = LIBRARY / "papers"
THESES = LIBRARY / "theses"


def folders() -> list[Path]:
    """Where the PDFs live: books/, papers/, theses/."""
    return [BOOKS, PAPERS, THESES]


def folder_for(kind: str) -> Path:
    """books/ for a book, papers/ for a paper, theses/ for a thesis."""
    return {"paper": PAPERS, "thesis": THESES}.get(kind, BOOKS)


def kind_word(meta: Meta) -> str:
    """'book', 'paper', 'PhD thesis', "Master's thesis", 'thesis'."""
    if meta.kind == "thesis":
        return thesis_meta.degree_label(meta.degree).replace("Thesis", "thesis")
    return "paper" if meta.kind == "paper" else "book"


def library_pdfs() -> list[Path]:
    """Every PDF in books/, papers/ and theses/."""
    return [pdf for folder in folders() for pdf in sorted(folder.glob("*.pdf"))]


CATALOG = LIBRARY / "catalog.csv"
ARCHIVE = LIBRARY / "archive"
PAGE_CACHE = LIBRARY / ".cache" / "chapter_pages.json"

MAX_TITLE_WORDS = 5

# Already-named files, e.g. shannon-1997-art-science-optical-design.pdf
SLUG_RE = re.compile(r"^[a-z]+-\d{4}-[a-z0-9-]+$")
# Filing documents (checking for repeats, taking a name, moving PDFs, merging, archiving): one
# at a time, so concurrent jobs on the library page never take the same name or move the same
# file. Identifying a document (the slow, online part) is not under it.
FILING = threading.RLock()


@dataclass
class Book:
    title: str
    author: str
    year: str
    publisher: str = ""
    name: str = ""  # the name actually given, when the usual one was taken (free_slug)

    @property
    def base_slug(self) -> str:
        """The usual name: <first-author-surname>-<year>-<short-title>."""
        return f"{surname(self.author)}-{self.year}-{short_title(self.title)}"

    @property
    def slug(self) -> str:
        return self.name or self.base_slug


def short_title(title: str) -> str:
    volume = re.search(r"\bvol(?:ume)?\.?\s*(\d+|[ivx]+)\b", title, re.IGNORECASE)
    # drop subtitles, edition notes and the volume part
    title = re.split(r"[:(]|,?\s*\bvol(?:ume)?\b", title, flags=re.IGNORECASE)[0]
    words = [w for w in ascii_words(title) if w not in STOP_WORDS][:MAX_TITLE_WORDS]
    if volume:
        words.append(f"vol{volume[1].lower()}")
    return "-".join(words) or "untitled"


def chapter_filename(ch: Chapter) -> str:
    return f"ch{ch.number:02d}-{'-'.join(short_title(ch.title).split('-')[:4])}.md"


def chapter_note(ch: Chapter) -> str:
    sections = "".join(f"## {s}\n\n- \n\n" for s in ch.sections)
    return f"""# Chapter {ch.number}: {ch.title}

[Back to book](README.md)

## Key ideas

-

{sections}## Equations

## Questions

## Check it in Python

"""


def progress_list(chapters: list[Chapter]) -> str:
    if not chapters:
        return "- [ ] Chapter 1"
    return "\n".join(f"- [ ] [Ch {c.number}: {c.title}]({chapter_filename(c)})" for c in chapters)


def book_chapters(path: Path) -> list[Chapter]:
    try:
        chapters = read_toc(path)
    except Exception as e:  # damaged or encrypted PDFs shouldn't stop the renaming
        print(f"  ! couldn't read the PDF ({e}); skipping chapter templates")
        return []
    if not chapters:
        print("  ! no table of contents found; create chapter notes by hand")
    return chapters


def write_chapter_notes(notes_dir: Path, chapters: list[Chapter]) -> None:
    for ch in chapters:
        note = notes_dir / chapter_filename(ch)
        if not note.exists():
            safe_io.write_text(note, chapter_note(ch))
    if chapters:
        print(f"  -> {len(chapters)} chapter templates in notes/{notes_dir.name}/")


def is_untouched_template(note: Path) -> bool:
    """True if the file only has the generated headings and empty bullets (nothing you wrote)."""
    for line in note.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not (
            line.startswith("#")
            or line == "-"
            or line in ("[Back to book](README.md)", "[Back to the paper](README.md)")
        ):
            return False
    return True


def doc_for_pdf(pdf: Path) -> dict | None:
    """The catalog entry whose PDF this is (found by its file, not its name)."""
    try:
        file = pdf.resolve().relative_to(LIBRARY.resolve()).as_posix()
    except ValueError:
        return None
    return catalog.by_file(catalog.load(CATALOG), file)


def notes_dir_of(row: dict) -> Path:
    """A document's notes folder: the catalog's `notes` column (notes/<name>/), checked as the
    notes panel checks it: notes_store.NoteError if it isn't under notes/ (an absolute path,
    "..", a hand-edited catalog), so nothing is ever read, written or moved outside."""
    return notes_store.notes_dir(LIBRARY, row)


def examples_dir_of(row: dict) -> Path:
    """A document's chapter scripts: examples/<name>/."""
    return EXAMPLES / row["slug"]


def refresh_chapters(pdf: Path, dry_run: bool) -> None:
    """Regenerate chapter templates after the reader improved, keeping any notes you wrote."""
    row = doc_for_pdf(pdf)
    # Checked before anything changes (NoteError: a notes folder outside notes/, or a README
    # linked from outside it)
    notes_dir = notes_dir_of(row) if row else NOTES / pdf.stem  # (a named PDF not added yet)
    readme = notes_store.notes_file(LIBRARY, row, "README.md") if row else notes_dir / "README.md"
    print(pdf.name)
    chapters = book_chapters(pdf)
    if not chapters:
        return
    old = sorted(  # a template that is a link out of the folder is never read or moved
        n for n in notes_dir.glob("ch[0-9][0-9]*.md") if notes_store.inside(n, notes_dir)
    )
    kept = [n for n in old if not is_untouched_template(n)]
    print(f"  -> {len(old) - len(kept)} old templates replaced by {len(chapters)} chapters")
    for note in kept:
        print(f"  ! kept {note.name}: it has your notes in it")
    if dry_run:
        return
    # The old templates go to archive/notes/<slug>/, never deleted: "untouched" means only
    # headings and empty bullets, and a heading may still be one you typed. One with the same
    # name as a chapter about to be written simply stays (write_chapter_notes keeps it).
    new_names = {chapter_filename(ch) for ch in chapters}
    for note in old:
        if note not in kept and note.name not in new_names:
            moved = move_to_archive(note, folder=f"notes/{notes_dir.name}")
            print(f"  -> {note.name} moved to {moved.relative_to(ARCHIVE.parent).as_posix()}")
    write_chapter_notes(notes_dir, chapters)
    if readme.exists():

        def new_list(text: str) -> str:
            if re.search(r"^- \[x\]", text, re.MULTILINE | re.IGNORECASE):
                print("  ! README progress list has ticked chapters; left it as it is")
                return text
            return re.sub(
                r"(## Reading progress\n\n)(?:- \[ \].*\n?)+",
                lambda m: m[1] + progress_list(chapters) + "\n",
                text,
            )

        safe_io.update_text(readme, new_list)  # a page turn may write "Last read" meanwhile
    if row:
        catalog.update(CATALOG, row["id"], {"chapters": str(len(chapters))})
        forget_chapter_pages(row["id"])  # chapters changed: the server looks their pages up again


def forget_chapter_pages(doc_id: str) -> None:
    """Drop a document from library_server.py's cache of chapter start pages."""
    if PAGE_CACHE.exists():
        safe_io.update_json(PAGE_CACHE, lambda cache: cache.pop(doc_id, None), {}, cache=True,
                            indent=1)  # fmt: skip


def archive_target(path: Path, folder: str = "") -> Path:
    """archive/<folder, else the item's own folder: books|notes|examples...>/<name>; if that's
    taken, <name>-removed-<date>, then -2, -3, ...: never anything already in the archive."""
    base = ARCHIVE / (folder or path.parent.name) / path.name
    target, n = base, 1
    while target.exists():
        extra = f"-{n}" if n > 1 else ""
        target = base.with_name(f"{path.stem}-removed-{date.today()}{extra}{path.suffix}")
        n += 1
    return target


def free_path(path: Path) -> Path:
    """`path`, or <stem>-2<suffix>, -3, ... : the first name not taken (copies never overwrite)."""
    target, n = path, 2
    while target.exists():
        target = path.with_name(f"{path.stem}-{n}{path.suffix}")
        n += 1
    return target


# --- names ------------------------------------------------------------------------------------


def name_taken(slug: str) -> bool:
    """Whether anything in the library already uses this name: a catalog entry, a PDF in
    books/, papers/ or theses/, or a notes or examples folder (even one without a book)."""
    return (
        catalog.by_slug(catalog.load(CATALOG), slug) is not None
        or any((folder / f"{slug}.pdf").exists() for folder in folders())
        or (NOTES / slug).exists()
        or (EXAMPLES / slug).exists()
    )


def free_slug(slug: str) -> str:
    """`slug`, or slug-2, slug-3, ... if a different document already has it (e.g. two
    Chinese-titled books of one year both come out as unknown-<year>-untitled). Call it holding
    FILING, together with taking the name (place_book + reserve_row)."""
    name, n = slug, 2
    while name_taken(name):
        name = f"{slug}-{n}"
        n += 1
    return name


def _same_text(a: str, b: str) -> bool:
    """The same text whatever the case, spaces or punctuation, in any script ("Optical
    Design" == "optical design."; 光学设计 == 光学 设计: Chinese has no spaces to rely on)."""
    letters = lambda s: re.sub(r"[\W_]+", "", (s or "").casefold())  # noqa: E731
    return bool(letters(a)) and letters(a) == letters(b)


def titles_agree(a: str, b: str) -> bool:
    """Two titles of the same work: the same words, or the same short title (subtitle and
    edition notes left out, as in names), when that isn't empty."""
    short = short_title(a)
    return _same_text(a, b) or (short != "untitled" and short == short_title(b))


def possible_repeat(book: Book, doc_id: str = "") -> dict | None:
    """An entry (other than `doc_id`) with the same full title, year and first author but no
    proof that it's the same work (no shared DOI or ISBN, not an identical file): maybe another
    copy of it, maybe a different document. Only reported, never merged or replaced."""
    for row in catalog.load(CATALOG).values():
        if (
            row["id"] != doc_id
            and row.get("year") == book.year
            and _same_text(row.get("title", ""), book.title)
            and surname(row.get("authors", "")) == surname(book.author)
        ):
            return row
    return None


# --- repeats ----------------------------------------------------------------------------------
# The same work twice, proven: the same DOI, the same ISBN (books and theses: a paper may carry
# its proceedings volume's ISBN), or a byte-identical file. A name, or a title, alone never is.


def file_hash(path: Path) -> str:
    """SHA-256 of a PDF, remembered until the file changes (it takes a moment for a big book)."""
    import hashlib

    HASHES = LIBRARY / ".cache" / "hashes.json"  # noqa: N806  (LIBRARY can change in tests)
    stat = path.stat()
    key = f"{stat.st_size}:{stat.st_mtime_ns}"
    cache = safe_io.load_json(HASHES, {}, cache=True)
    if (cached := cache.get(str(path))) and cached[0] == key:
        return cached[1]
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            digest.update(chunk)
    found = [key, digest.hexdigest()]
    safe_io.update_json(HASHES, lambda c: c.update({str(path): found}), {}, cache=True, indent=0)
    return digest.hexdigest()


def _same_file(a: Path, b: Path) -> bool:
    try:
        return a.stat().st_size == b.stat().st_size and file_hash(a) == file_hash(b)
    except OSError:
        return False


PROVEN = ("same DOI", "same ISBN", "identical file")  # the reasons repeat_of gives


def repeat_of(path: Path, meta: Meta) -> tuple[str, str] | None:
    """(id, reason) of the document already in the library that `path` is proven to repeat
    (the same DOI or ISBN, or an identical file), or None."""
    is_paper = meta.kind == "paper"
    isbn = isbn13(meta.isbn) if meta.isbn else ""
    for row in catalog.load(CATALOG).values():
        existing = LIBRARY / row.get("file", "")
        if row.get("file") and existing.resolve() == path.resolve():
            continue  # the document's own file
        if meta.doi and row.get("doi", "").lower() == meta.doi.lower():
            return row["id"], "same DOI"
        if isbn and not is_paper and row.get("type") != "paper" and row.get("isbn") == isbn:
            return row["id"], "same ISBN"
        if row.get("file") and existing.is_file() and _same_file(path, existing):
            return row["id"], "identical file"
    return None


_archive_lock = threading.Lock()  # choosing a free archive name and taking it: one step


def _library_item(path: Path, folders_ok=("books", "papers", "theses", "notes", "examples")):
    """Refuse anything that isn't inside one of the library's own folders: never the library
    itself, the archive, a folder like books/ as a whole, or anything outside."""
    resolved, library = path.resolve(), LIBRARY.resolve()
    inside = [library / f for f in folders_ok] + [
        p.resolve() for p in (BOOKS, PAPERS, THESES, NOTES, EXAMPLES) if p.name in folders_ok
    ]
    if not any(folder in resolved.parents for folder in inside):
        raise ValueError(f"refusing to move {path}: it isn't an item in the library's folders")


def move_to_archive(path: Path, folder: str = "") -> Path:
    """Move a file or folder to archive/<its folder>/ (never deleted, never over anything
    already archived); returns where it went."""
    _library_item(path)
    with _archive_lock, safe_io.critical():
        target = archive_target(path, folder)
        target.parent.mkdir(parents=True, exist_ok=True)
        path.rename(target)
    return target


def library_pdf(row: dict) -> Path:
    """The library's PDF of a catalog entry, checked: `file` must be books/, papers/ or
    theses/<name>.pdf, and if something is there it must be a file. An entry without a proper
    file (e.g. half registered) raises ValueError instead of pointing at a folder."""
    file = row.get("file", "")
    if not re.fullmatch(r"(books|papers|theses)/[^/\\]+\.pdf", file, re.IGNORECASE):
        raise ValueError(f"the entry {row.get('slug', '?')} has no PDF file recorded")
    pdf = LIBRARY / file
    if pdf.exists() and not pdf.is_file():
        raise ValueError(f"{file} isn't a file")
    return pdf


MARK_TYPES = {"/Highlight", "/Underline", "/StrikeOut", "/Squiggly", "/Ink", "/FreeText",
              "/Text", "/Stamp", "/Square", "/Circle", "/Line", "/Polygon", "/PolyLine",
              "/Caret", "/FileAttachment"}  # fmt: skip


def has_marks(pdf: Path) -> bool:
    """Whether a library PDF holds marks: highlights, drawings or notes (made in the reading
    view, which keeps the original in archive/before-marks/, or in any PDF program). If the file
    can't be read, assume it does: it's never replaced on a guess."""
    try:
        relative = pdf.resolve().relative_to(LIBRARY.resolve()).as_posix()
        if (ARCHIVE / "before-marks" / relative).exists():
            return True
    except ValueError:
        pass
    try:
        for page in PdfReader(pdf).pages:
            for annot in page.get("/Annots") or []:
                if annot.get_object().get("/Subtype") in MARK_TYPES:
                    return True
    except Exception:
        return True
    return False


def has_own_work(notes_dir: Path, examples_dir: Path | None = None) -> bool:
    """Whether a document's notes hold anything of yours: a ticked chapter, the page you last
    read, notes you wrote, saved words, or a chapter script."""
    readme = notes_dir / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        if re.search(r"^- \[[xX]\]", text, re.MULTILINE) or "Last read:" in text:
            return True
    for note in notes_dir.glob("*.md"):
        if note.name != "README.md" and not is_untouched_template(note):
            return True
    return bool(examples_dir) and any(examples_dir.glob("*.py"))


def doc_has_own_work(row: dict) -> bool:
    try:
        return has_own_work(notes_dir_of(row), examples_dir_of(row))
    except notes_store.NoteError:  # notes not where they should be: treated as yours, kept
        return True


# Which copy of a repeat to keep: the one with more information
INFO_FIELDS = ("title", "authors", "year", "publisher", "isbn", "journal", "volume", "issue",
               "page_range", "doi", "degree", "institution", "supervisors", "keywords",
               "subjects")  # fmt: skip


def meta_row(meta: Meta) -> dict:
    """A Meta as catalog columns (for comparing a new copy with a catalog row)."""
    row = {k: getattr(meta, k, "") for k in INFO_FIELDS if k != "authors"}
    return row | {"authors": meta.author, "type": meta.kind}


def info_score(row: dict, pdf: Path) -> tuple:
    """How much a copy offers, most important first: searchable text (not a bare scan), the
    details filled in (DOI, ISBN, journal, ...), bookmarks, pages."""
    from book_ocr import has_text_layer

    text = bookmarks = pages = 0
    try:
        reader = PdfReader(pdf)
        text, pages = int(has_text_layer(reader)), len(reader.pages)
        bookmarks = int(bool(reader.outline))
    except Exception:
        pass
    filled = sum(bool(str(row.get(k) or "").strip()) for k in INFO_FIELDS)
    return text, filled, bookmarks, pages


def why_richer(better: tuple, worse: tuple) -> str:
    """'searchable text', 'more details', 'bookmarks', 'more pages' (the first difference)."""
    names = ("searchable text", "more details", "bookmarks", "more pages")
    return next((n for n, a, b in zip(names, better, worse, strict=True) if a > b), "the same")


def _notes_problem(row: dict) -> str:
    """Why this document's notes folder can't be used ("" if it can)."""
    try:
        notes_dir_of(row)
    except notes_store.NoteError as e:
        return f"{row['slug']}: {e}"
    return ""


def catalog_repeats() -> list[dict]:
    """Pairs already in the catalog that are the same work: [{keep, drop, reason, why}] (ids).
    The copy with more information is kept (merge_into then gives it the other's work).
    drop="" when both hold your work: then nothing should be touched."""
    rows = list(catalog.load(CATALOG).values())
    found, seen = [], set()
    for i, a in enumerate(rows):
        for b in rows[i + 1 :]:
            if a["id"] in seen or b["id"] in seen:
                continue
            fa, fb = LIBRARY / a.get("file", ""), LIBRARY / b.get("file", "")
            reason = (
                "same DOI" if a.get("doi") and a["doi"].lower() == b.get("doi", "").lower()
                else "same ISBN" if a.get("isbn") and a["isbn"] == b.get("isbn")
                and "paper" not in (a.get("type"), b.get("type"))
                else "identical file" if fa.is_file() and fb.is_file() and _same_file(fa, fb)
                else ""
            )  # fmt: skip
            if not reason:
                continue
            # A notes folder outside notes/ (hand-edited catalog): neither is merged or
            # archived, the pair is only reported
            if problem := next(
                (_notes_problem(r) for r in (a, b) if _notes_problem(r)), ""
            ):  # fmt: skip
                found.append({"keep": a["id"], "drop": "", "reason": reason, "other": b["id"],
                              "problem": problem})  # fmt: skip
                continue
            # Marks live inside the PDF and can't be merged over: a PDF with marks is kept
            marks_a = fa.is_file() and has_marks(fa)
            marks_b = fb.is_file() and has_marks(fb)
            work_a = doc_has_own_work(a) or marks_a
            work_b = doc_has_own_work(b) or marks_b
            if work_a and work_b:
                found.append({"keep": a["id"], "drop": "", "reason": reason, "other": b["id"]})
                continue
            score_a, score_b = info_score(a, fa), info_score(b, fb)
            a_first = a.get("added", "") <= b.get("added", "")
            if marks_b:  # (only one of them has work here)
                keep, drop, why = b, a, "your marks in the PDF"
            elif marks_a:
                keep, drop, why = a, b, "your marks in the PDF"
            elif score_a > score_b or (score_a == score_b and a_first):
                keep, drop, why = a, b, why_richer(score_a, score_b)
            else:
                keep, drop, why = b, a, why_richer(score_b, score_a)
            found.append({"keep": keep["id"], "drop": drop["id"], "reason": reason, "why": why})
            seen.add(drop["id"])
    return found


def merge_into(src: str, dst: str) -> list[str]:
    """Before document `src` goes to the archive: give `dst` (the copy kept) everything of
    yours that `src` has, and the details it lacks (both ids). Returns what was moved, e.g.
    ["2 ticked chapters", "last-read page", "notes ch03-stops.md", "vocabulary", "1 script",
    "shelves"]. Only copies: `src` itself goes to the archive complete, as a backup. Its reading
    history stays under its own id; its tombstone (remove_book with merged_into) points to
    `dst`, so that history counts for `dst` (reading_log)."""
    import shutil

    rows = catalog.load(CATALOG)
    # Both notes folders and the README checked before anything changes: a refusal
    # (NoteError) leaves the catalog and both documents as they were
    src_dir, dst_dir = notes_dir_of(rows[src]), notes_dir_of(rows[dst])
    readme = notes_store.notes_file(LIBRARY, rows[dst], "README.md")
    moved = []
    # Catalog: details dst lacks, and the shelves of both
    fill = {
        k: rows[src].get(k, "") for k in INFO_FIELDS if not rows[dst].get(k) and rows[src].get(k)
    }
    shelves = catalog.split_list(rows[dst].get("shelves", "") + ";" + rows[src].get("shelves", ""))
    if len(shelves) > len(catalog.split_list(rows[dst].get("shelves", ""))):
        moved.append("shelves")
    catalog.update(CATALOG, dst, fill)
    catalog.set_field(CATALOG, dst, "shelves", "; ".join(shelves))

    src_name = rows[src]["slug"]
    dst_dir.mkdir(parents=True, exist_ok=True)
    if src_dir.exists() and readme.exists():
        old_readme = src_dir / "README.md"
        old = (
            old_readme.read_text(encoding="utf-8")
            if old_readme.exists() and notes_store.inside(old_readme, src_dir)
            else ""
        )

        def merged(text: str) -> str:
            # Ticks, by chapter number ("Read the paper" is chapter 1)
            ticked = 0
            for chapter in library_page.chapters_in(old):
                if chapter["done"] and chapter["number"] is not None:
                    pattern = library_page.chapter_line(chapter["number"], boxes=" ")
                    text, count = pattern.subn(lambda m: f"- [x] {m[1]}", text, count=1)
                    ticked += count
            if ticked:
                moved.append(f"{ticked} ticked chapter{'s' if ticked > 1 else ''}")
            # The page you last read (unless the kept copy has its own)
            last = library_page.LAST_READ_RE.search(old)
            if last and not library_page.LAST_READ_RE.search(text):
                heading = re.search(r"^## Reading progress[ \t]*\n(?:[ \t]*\n)?", text,
                                    re.MULTILINE)  # fmt: skip
                at = heading.end() if heading else len(text)
                text = text[:at] + last[0] + "\n\n" + text[at:].lstrip("\n")
                moved.append("last-read page")
            return text

        safe_io.update_text(readme, merged)  # a page turn may write "Last read" meanwhile
    # Notes you wrote: into the same chapter's template (still empty, so nothing is lost)
    for note in sorted(src_dir.glob("*.md")):
        if note.name == "README.md" or not notes_store.inside(note, src_dir):
            continue  # (a link out of the folder: never read)
        if is_untouched_template(note):
            continue
        target = dst_dir / note.name
        if m := re.match(r"(ch\d{2})-", note.name):
            target = next(iter(sorted(dst_dir.glob(f"{m[1]}-*.md"))), target)
        if target.exists() and not is_untouched_template(target):
            # never over notes of yours, nor over a copy from an earlier merge
            target = free_path(target.with_name(f"{target.stem}-from-{src_name}.md"))
        safe_io.write_text(target, note.read_text(encoding="utf-8"))
        moved.append("vocabulary" if note.name == "vocabulary.md" else f"notes {note.name}")
    # Chapter scripts
    scripts = sorted(examples_dir_of(rows[src]).glob("*.py"))
    for script in scripts:
        target = examples_dir_of(rows[dst]) / script.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            suffix = src_name.replace("-", "_")
            target = free_path(target.with_name(f"{target.stem}_from_{suffix}.py"))
        shutil.copy2(script, target)
    if scripts:
        moved.append(f"{len(scripts)} script{'s' if len(scripts) > 1 else ''}")
    return moved


def richer_than_library(path: Path, meta: Meta, doc_id: str) -> str:
    """Why the new copy's *file* offers more than the library's PDF of document `doc_id`
    (searchable text, bookmarks, more pages); "" if it doesn't, e.g. an identical file. Its
    details are another matter: fill_details() adds them either way."""
    row = catalog.load(CATALOG).get(doc_id)
    try:
        old_pdf = library_pdf(row or {})
    except ValueError:  # no proper PDF recorded: nothing to compare with or replace
        return ""
    if not old_pdf.exists():
        return "a PDF"  # the library's PDF is missing: this copy brings it back
    if _same_file(path, old_pdf):
        return ""
    new, old = info_score({}, path), info_score({}, old_pdf)
    return why_richer(new, old) if new > old else ""


def fill_details(doc_id: str, meta: Meta) -> list[str]:
    """Details a repeat knows that the library's entry lacks (DOI, journal, keywords, ...):
    added to the entry. Returns their names. Never creates an entry."""
    row = catalog.load(CATALOG).get(doc_id)
    if not row:
        return []
    fill = {k: v for k, v in meta_row(meta).items() if k in INFO_FIELDS and v and not row.get(k)}
    if fill:
        catalog.update(CATALOG, doc_id, fill)
    return list(fill)


def replace_pdf(doc_id: str, path: Path, meta: Meta) -> Path:
    """A new copy of something already in the library that offers more (e.g. searchable text,
    or a DOI): it takes the old PDF's place under the same name, so your notes and progress stay
    with it; the old PDF goes to archive/. Returns where the old one went.

    Only for a proven repeat (handle_repeat), and both files are checked first. If putting the
    new copy in place fails, the old PDF is moved back: the book is never left without its PDF.
    """
    row = catalog.load(CATALOG)[doc_id]
    pdf = library_pdf(row)  # ValueError for an entry without a proper PDF: nothing is touched
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise ValueError(f"{path.name} isn't a PDF file; nothing was replaced")
    if path.resolve() == pdf.resolve():
        raise ValueError("that is the library's own PDF; nothing was replaced")
    _library_item(path, folders_ok=("books", "papers", "theses"))
    with FILING, safe_io.critical():
        old = move_to_archive(pdf) if pdf.exists() else None
        try:
            path.rename(pdf)
        except Exception:
            if old is not None:
                old.rename(pdf)  # put the library's PDF back where it was
            raise
    old = old or pdf
    fill_details(doc_id, meta)  # the same document, a better file: its id stays
    catalog.update(CATALOG, doc_id, {"pages": meta.pages or row.get("pages", "")})
    forget_chapter_pages(doc_id)
    if not row.get("chapters") and row.get("type") != "paper":  # now it may have bookmarks
        refresh_chapters(pdf, dry_run=False)
    return old


def find_document(name_or_id: str) -> dict | None:
    """A document by its id, or by its name (as typed on the command line: the file name, with
    or without .pdf)."""
    rows = catalog.load(CATALOG)
    key = Path(name_or_id).stem if name_or_id.lower().endswith(".pdf") else name_or_id
    return rows.get(key) or catalog.by_slug(rows, key)


def remove_book(doc_id: str, dry_run: bool, yes: bool, merged_into: str = "") -> None:
    """Take a document out of the library; its PDF, notes and scripts move to archive/. It
    leaves a tombstone (catalog.retire): "removed", or "merged" into `merged_into` (the
    document that got its work), so references to its id keep an answer."""
    row = catalog.load(CATALOG).get(doc_id)
    if row is None:
        print(f"No document {doc_id} in catalog.csv.")
        return
    candidates = [library_pdf(row), notes_dir_of(row), examples_dir_of(row)]
    existing = [p for p in candidates if p.exists()]
    print(f"Remove '{row['title'] or row['slug']}' ({row['slug']}) from the library:")
    for p in existing:
        print(
            f"  move {p.relative_to(BOOKS.parent)} -> {archive_target(p).relative_to(BOOKS.parent)}"
        )
    print("  remove its row from catalog.csv (its id is kept as a tombstone)")
    if dry_run:
        return
    if not yes:
        try:
            answer = input("Go ahead? [y/N] ")
        except EOFError:
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            print("Nothing changed.")
            return
    # All or nothing: if a step fails, what was already moved goes back, the tombstone is taken
    # back and the entry stays. The tombstone comes first: never a moment without an answer.
    moved: list[tuple[Path, Path]] = []
    with FILING, safe_io.critical():
        event = "merged" if merged_into else "removed"
        catalog.retire(CATALOG, doc_id, event, row, into=merged_into)
        try:
            for p in existing:
                moved.append((p, move_to_archive(p)))
            catalog.remove(CATALOG, doc_id)
        except Exception:
            for original, archived in reversed(moved):
                try:
                    archived.rename(original)
                except OSError as e:
                    print(f"  ! couldn't move {archived} back to {original}: {e}")
            catalog.unretire(CATALOG, doc_id)
            raise
    forget_chapter_pages(doc_id)
    print("Done. To restore it, move the files back from archive/ and run add_book.py.")


# --- renaming -----------------------------------------------------------------------------------
# A rename changes a document's name, its files' and folders' names and the catalog's paths;
# its id, and so everything that refers to it, stays. Several files move, so it keeps a journal
# (in the library's .myLibrary/operations/) while it works: any failure puts everything back at
# once, and an interruption (power cut) is put back by recover_operations() at the next start.


def operations_dir() -> Path:
    return LIBRARY / ".myLibrary" / "operations"


def rename_document(doc_id: str, new_slug: str) -> dict:
    """Rename document `doc_id` to `new_slug`: its PDF, notes folder, chapter scripts and the
    original kept before marks move to the new name, the README's File line and the catalog's
    name and paths follow. Returns the updated entry."""
    if not SLUG_RE.match(new_slug):
        raise ValueError(f"{new_slug!r} isn't a valid name (author-year-title, a-z 0-9 -)")
    with FILING, safe_io.critical():
        row = catalog.load(CATALOG).get(doc_id)
        if row is None:
            raise KeyError(doc_id)
        if new_slug == row["slug"]:
            return row
        if name_taken(new_slug):
            raise ValueError(f"the name {new_slug} is already taken")
        pdf = library_pdf(row)
        new_file = f"{pdf.parent.name}/{new_slug}.pdf"
        moves = [(pdf, LIBRARY / new_file)]
        old_notes, new_notes = notes_dir_of(row), NOTES / new_slug
        moves.append((old_notes, new_notes))
        moves.append((examples_dir_of(row), EXAMPLES / new_slug))
        marks = ARCHIVE / "before-marks" / row["file"]
        moves.append((marks, ARCHIVE / "before-marks" / new_file))
        moves = [(a, b) for a, b in moves if a.exists()]
        if clash := [b for _, b in moves if b.exists()]:
            raise FileExistsError(f"{clash[0]} already exists; nothing was renamed")
        readme = new_notes / "README.md"
        old_readme = (old_notes / "README.md").read_text("utf-8") if old_notes.exists() and (
            old_notes / "README.md").exists() else None  # fmt: skip
        to = {"slug": new_slug, "file": new_file, "notes": f"notes/{new_slug}/"}
        journal = operations_dir() / f"rename-{doc_id}.json"
        safe_io.write_json(journal, {
            "op": "rename", "id": doc_id,
            "from": {k: row.get(k, "") for k in to}, "to": to,
            "moves": [[str(a), str(b)] for a, b in moves],
            "readme": {"path": str(readme), "text": old_readme},
        }, ensure_ascii=False, indent=1)  # fmt: skip
        try:
            for a, b in moves:
                b.parent.mkdir(parents=True, exist_ok=True)
                a.rename(b)
            if old_readme is not None:
                text = old_readme.replace(f"`{row['file']}`", f"`{new_file}`")
                safe_io.write_text(readme, text)
            catalog.set_fields(CATALOG, doc_id, to)
        except BaseException:
            _undo_rename(safe_io.load_json(journal, {}))
            journal.unlink(missing_ok=True)
            raise
        journal.unlink()
        return catalog.load(CATALOG)[doc_id]


def _undo_rename(plan: dict) -> list[str]:
    """Put a rename back as far as it got: files moved back, the README's text and the
    catalog's name and paths restored. Returns what couldn't be put back (nothing, normally)."""
    left = []
    rows = catalog.load(CATALOG)
    row = rows.get(plan.get("id", ""))
    if row and row.get("slug") == plan["to"]["slug"]:
        catalog.set_fields(CATALOG, plan["id"], plan["from"])
    readme = plan.get("readme") or {}
    for a, b in reversed(plan.get("moves", [])):
        a, b = Path(a), Path(b)
        if b.exists() and not a.exists():
            try:
                b.rename(a)
            except OSError as e:
                left.append(f"{b} -> {a}: {e}")
    if readme.get("text") is not None:
        old_readme = Path(readme["path"])
        for a, b in plan.get("moves", []):  # the README went back with its folder
            if Path(readme["path"]).is_relative_to(b):
                old_readme = Path(a) / Path(readme["path"]).relative_to(b)
        if old_readme.exists():
            safe_io.write_text(old_readme, readme["text"])
    return left


def recover_operations() -> list[str]:
    """At start: put back any rename an interruption left halfway (see rename_document)."""
    done = []
    folder = operations_dir()
    for journal in sorted(folder.glob("rename-*.json")) if folder.exists() else []:
        plan = safe_io.load_json(journal, {})
        left = _undo_rename(plan)
        if left:
            done.append(f"! an interrupted rename of {plan.get('id')} couldn't be fully put "
                        f"back: {'; '.join(left)} (journal kept: {journal})")  # fmt: skip
            continue
        journal.unlink()
        done.append(f"an interrupted rename of {plan['from'].get('slug')} was put back")
    return done


def notes_readme(
    book: Book, filename: str, chapters: list[Chapter], meta: Meta | None = None
) -> str:
    if meta and meta.kind == "thesis":
        doi = f"[{meta.doi}](https://doi.org/{meta.doi})" if meta.doi else "?"
        rows = f"""| Degree | {thesis_meta.degree_label(meta.degree)} |
| University | {meta.institution or "?"} |
| Supervisors | {meta.supervisors or "?"} |
| DOI | {doi} |"""
    else:
        rows = f"| Publisher | {book.publisher or '?'} |"
    return f"""# {book.title}

| | |
|---|---|
| Author | {book.author} |
| Year | {book.year} |
{rows}
| File | `{filename}` |

## Reading progress

{progress_list(chapters)}

## Notes

One Markdown file per chapter (`chNN-*.md`). Python scripts for checking the book's
examples live in `examples/{Path(filename).stem}/` ("Script" on the library page).
"""


PAPER_ITEM = library_page.PAPER_ITEM  # a paper's one "chapter" in its README checklist


def paper_readme(book: Book, filename: str, meta: Meta) -> str:
    where = ", ".join(
        part
        for part in (
            meta.journal,
            meta.volume + (f"({meta.issue})" if meta.issue else ""),
            meta.page_range,
        )
        if part
    )
    doi = f"[{meta.doi}](https://doi.org/{meta.doi})" if meta.doi else "?"
    return f"""# {book.title}

| | |
|---|---|
| Authors | {book.author} |
| Year | {book.year} |
| Journal | {where or "?"} |
| DOI | {doi} |
| File | `{filename}` |

## Reading progress

- [ ] [{PAPER_ITEM}](notes.md)

## Notes

Your notes on this paper are in [notes.md](notes.md).
"""


PAPER_NOTES = """# {title}

[Back to the paper](README.md)

## Summary (in my own words)

-

## Key results

-

## Method

-

## Questions

-

## How it relates to my books

-
"""


def setup_book(pdf: Path, book: Book, meta: Meta, online: bool = True, doc_id: str = "") -> str:
    """Folders, notes README, chapter templates and catalog row for a named PDF. `doc_id`: its
    entry (reserve_row); without one, the entry for this file, else a new one. Returns the id.

    Safe to repeat: existing notes are never overwritten.
    """
    if not doc_id:
        with FILING:
            row = doc_for_pdf(pdf)
            doc_id = row["id"] if row else reserve_row(pdf, book, meta)
    slug = pdf.stem
    relative = f"{pdf.parent.name}/{pdf.name}"  # books/, papers/ or theses/<slug>.pdf
    notes_dir = NOTES / slug
    notes_dir.mkdir(parents=True, exist_ok=True)
    readme = notes_dir / "README.md"
    is_paper, is_thesis = meta.kind == "paper", meta.kind == "thesis"
    if is_paper:  # one notes file, and "Read the paper" instead of chapters
        chapters = []
        if not readme.exists():
            safe_io.write_text(readme, paper_readme(book, relative, meta))
        notes = notes_dir / "notes.md"
        if not notes.exists():
            safe_io.write_text(notes, PAPER_NOTES.format(title=book.title))
    else:
        chapters = book_chapters(pdf)
        if not readme.exists():
            safe_io.write_text(readme, notes_readme(book, relative, chapters, meta))
        write_chapter_notes(notes_dir, chapters)
    catalog.update(
        CATALOG,
        doc_id,
        {
            "slug": slug,
            "type": meta.kind if meta.kind in ("paper", "thesis") else "book",
            "title": book.title,
            "authors": book.author,
            "year": book.year,
            "publisher": "" if is_thesis else book.publisher,  # a thesis: its university
            "isbn": meta.isbn,
            "journal": meta.journal,
            "volume": meta.volume,
            "issue": meta.issue,
            "page_range": meta.page_range,
            "doi": meta.doi,
            "degree": meta.degree,
            "institution": meta.institution,
            "supervisors": meta.supervisors,
            "keywords": meta.keywords,
            "pages": meta.pages,
            "chapters": str(len(chapters) or ""),
            "subjects": meta.subjects,
            "file": relative,
            "notes": f"notes/{slug}/",
            "added": date.today().isoformat(),
            "openlibrary": "" if is_paper or is_thesis else meta.url,
            "metadata_sources": "; ".join(f"{k}: {v}" for k, v in meta.sources.items()),
        },
    )
    print(f"  -> catalog.csv row '{slug}' (id {doc_id})")
    # Its subject (OpenAlex), then shelves: the subject's, and yours that fit (only if it's on
    # none yet)
    if online and not catalog.load(CATALOG).get(doc_id, {}).get("topic"):
        try:
            if found := subjects.classify(doc_id, LIBRARY, CATALOG):
                print(f"  -> subject: {found['field']} / {found['topic']} ({found['score']})")
        except book_meta.Unavailable as e:
            print(f"  ! subject not looked up ({e}); Refresh tries again later")
    if found := shelves.auto_shelve(doc_id, LIBRARY, CATALOG):
        print(f"  -> shelves: {'; '.join(found)} (change them with Shelves on the library page)")
    return doc_id


def find_repeat(path: Path, meta: Meta, book: Book) -> tuple[str, str] | None:
    """(id, reason) if `path` is proven to repeat a document already in the library (same DOI
    or ISBN, or an identical file: repeat_of); else None. The same name is not a repeat: the new
    document gets a free name of its own (place_book)."""
    return repeat_of(path, meta)


def handle_repeat(
    path: Path, meta: Meta, doc_id: str, dry_run: bool = False, reason: str = ""
) -> tuple[bool, str]:
    """A proven repeat of document `doc_id` (repeat_of's `reason`). With the same DOI or ISBN,
    a copy whose file is better (searchable text, ...) replaces the library's PDF (your notes
    stay, and the document keeps its id), unless the library's PDF has your marks in it.
    Otherwise this copy goes to archive/ (it never becomes a document, so it gets no id).
    Details the entry lacks are added either way. Returns (whether the PDF was replaced, what
    happened)."""
    if reason not in PROVEN:
        raise ValueError(f"not a proven repeat ({reason or 'no reason'}); nothing was moved")
    better = richer_than_library(path, meta, doc_id) if reason != "identical file" else ""
    marked = ""
    if better:
        row = catalog.load(CATALOG)[doc_id]
        pdf = library_pdf(row)
        if pdf.exists() and has_marks(pdf):  # replacing it would take your marks away
            marked = f"this copy has {better}, but the library's PDF has your marks, so it stays; "
            better = ""
        elif not titles_agree(row.get("title", ""), meta.title):
            # An ISBN or DOI read from the wrong page (a series advert, a cited work) would
            # otherwise swap in a different book: the titles must agree too
            marked = (f"this copy has {better}, but its title (“{meta.title or '?'}”) differs "
                      "from the entry's, so the library's PDF stays; ")  # fmt: skip
            better = ""
    if better:
        if dry_run:
            return True, f"this copy has {better}: would replace its PDF"
        old = replace_pdf(doc_id, path, meta)
        return True, (f"this copy has {better}, so it replaces the PDF (your notes stay; the "
                      f"old PDF is in archive/{old.parent.name}/)")  # fmt: skip
    if dry_run:
        return False, f"{marked}would be moved to archive/"
    added = fill_details(doc_id, meta)
    kept = move_to_archive(path)
    details = f"added its {', '.join(added)} to the entry; " if added else ""
    return False, f"{marked}{details}this copy was moved to archive/{kept.parent.name}/{kept.name}"


def place_book(path: Path, book: Book, meta: Meta) -> Path:
    """Move a new PDF into books/, papers/ or theses/ under its name; returns where it is now.
    If another document already has the usual name, this one gets the next free one
    (free_slug: <name>-2, ...), recorded in book.name. Call it holding FILING (the library page
    does, around find_repeat + this + reserve_row), so two jobs can't take one name."""
    if not path.is_file():
        raise ValueError(f"{path} isn't a file")
    with FILING:
        book.name = free_slug(book.base_slug) if not book.name else book.name
        folder = folder_for(meta.kind)
        target = folder / f"{book.slug}{path.suffix.lower()}"
        if target.exists():  # rename would replace it on some systems: never
            raise FileExistsError(f"{target.name} is already in {folder.name}/")
        folder.mkdir(parents=True, exist_ok=True)
        path.rename(target)
    return target


def reserve_row(pdf: Path, book: Book, meta: Meta) -> str:
    """A new document: its catalog entry, and with it its permanent id, with the essentials
    (name, file, title, authors, year), written in the same FILING step that took the file's
    name, so a copy of the same work arriving meanwhile sees a whole entry with its file.
    setup_book fills in the rest. Returns the id."""
    return catalog.add(CATALOG, {
        "slug": pdf.stem,
        "type": meta.kind if meta.kind in ("paper", "thesis") else "book",
        "title": book.title,
        "authors": book.author,
        "year": book.year,
        "file": f"{pdf.parent.name}/{pdf.name}",
        "notes": f"notes/{pdf.stem}/",
        "added": date.today().isoformat(),
    })  # fmt: skip


def file_book(path: Path, book: Book, meta: Meta, online: bool = True) -> Path:
    """Move a new PDF into place under its name, give it its entry and id, and set it up;
    returns where it is now."""
    with FILING:
        target = place_book(path, book, meta)
        doc_id = reserve_row(target, book, meta)
    setup_book(target, book, meta, online, doc_id=doc_id)
    return target


def add_book(
    path: Path, book: Book, dry_run: bool, meta: Meta | None = None, online: bool = True
) -> None:
    meta = meta or Meta()
    with FILING:
        if repeat := find_repeat(path, meta, book):
            name = catalog.load(CATALOG)[repeat[0]]["slug"]
            print(f"  ! already in the library as {name} ({repeat[1]}); "
                  + handle_repeat(path, meta, repeat[0], dry_run, reason=repeat[1])[1])  # fmt: skip
            return
        book.name = free_slug(book.base_slug)
        print(f"  -> {folder_for(meta.kind).name}/{book.slug}{path.suffix.lower()}")
        if note := name_note(book):
            print(f"  ! {note}")
        if dry_run:
            return
        target = place_book(path, book, meta)
        doc_id = reserve_row(target, book, meta)
    setup_book(target, book, meta, online, doc_id=doc_id)


def name_note(book: Book, doc_id: str = "") -> str:
    """What to know about the name a new document (`doc_id`, once it has one) got: another one
    already had the usual name, or an entry looks like the same work without proof. "" if
    nothing."""
    notes = []
    if book.slug != book.base_slug:
        notes.append(f"named {book.slug}: {book.base_slug} is another document's name")
    if other := possible_repeat(book, doc_id):
        notes.append(f"possibly the same work as {other['slug']} (same title, author and year, "
                     "but a different file and no shared DOI or ISBN): both kept; if they are "
                     "the same, remove one")  # fmt: skip
    return "; ".join(notes)


def unregistered_named_books() -> list[Path]:
    """Already-named PDFs that no catalog entry has as its file (e.g. renamed by hand)."""
    files = {r.get("file") for r in catalog.load(CATALOG).values()}
    return [p for p in library_pdfs()
            if SLUG_RE.match(p.stem) and f"{p.parent.name}/{p.name}" not in files]  # fmt: skip


def describe(book: Book, meta: Meta) -> None:
    """The book as it will be added (command-line overrides included) and where each detail
    came from."""
    if meta.kind == "thesis":
        print(f"     a {kind_word(meta)}")
    for key in ("title", "author", "year", "publisher", "institution", "supervisors"):
        if value := getattr(book, key, None) or getattr(meta, key):
            print(f"     {key:<11} {value}   [{meta.sources.get(key, '')}]")


_ocr_asked: set[tuple[int, int]] = set()  # PDFs already asked about in this run


def _file_key(path: Path) -> tuple[int, int]:
    """Identifies a file across renames (size + modification time stay the same)."""
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def offer_ocr(path: Path, args: argparse.Namespace) -> None:
    """Scans without text get an OCR text layer first, so title, ISBN and chapters can be read."""
    if not needs_ocr(path):
        return
    _ocr_asked.add(_file_key(path))
    minutes = ocr_minutes(len(PdfReader(path).pages))
    if args.dry_run or args.no_ocr:
        print(f"  ! scanned PDF without text; OCR would take ~{minutes:.0f} min (skipped)")
        return
    if args.ocr or ask(
        f"  Scanned PDF without text. Add a text layer with OCR (~{minutes:.0f} min)? [Y/n] "
    ):
        keep = make_searchable(path)
        print(f"  -> text layer added; the original scan is in {keep.relative_to(BOOKS.parent)}")


def check_remaining_scans(args: argparse.Namespace) -> None:
    """Last step of every run: offer OCR for scanned PDFs in books/ that still have no text."""
    if args.no_ocr:
        return
    scans = [p for p in library_pdfs() if _file_key(p) not in _ocr_asked and needs_ocr(p)]
    if not scans:
        return
    print(f"\n{len(scans)} scanned PDF(s) in books/, papers/ or theses/ have no text layer yet:")
    for pdf in scans:
        pages = len(PdfReader(pdf).pages)
        about = f"{pages} pages, ~{ocr_minutes(pages):.0f} min"
        if args.dry_run:
            print(f"  {pdf.name} ({about})")
            continue
        question = f"  {pdf.name} ({about}): make it searchable now? [y/N] "
        if not (args.ocr or ask(question, default=False)):
            continue
        keep = make_searchable(pdf)
        print(f"  -> text layer added; the original scan is in {keep.relative_to(BOOKS.parent)}")
        if pdf.stem in catalog.load(CATALOG):
            refresh_chapters(pdf, dry_run=False)  # chapters and pages from the new text


def unreadable(path: Path) -> str:
    """Why a PDF can't be added ("" if it can): a damaged or incomplete file (e.g. a download
    that stopped halfway) would otherwise be registered with made-up details."""
    try:
        if not len(PdfReader(path).pages):
            return "it has no pages"
    except Exception as e:
        return f"it isn't a readable PDF ({e})"
    return ""


def process(path: Path, args: argparse.Namespace, rename: bool = True) -> None:
    print(path.name)
    if problem := unreadable(path):
        print(f"  ! skipped: {problem}")
        return
    offer_ocr(path, args)
    meta = identify(
        path, online=not args.offline, paper=path.parent == PAPERS, thesis=path.parent == THESES
    )
    meta.sources.update(
        {k: "command line" for k in ("title", "author", "year") if getattr(args, k)}
    )
    book = Book(
        args.title or meta.title,
        args.author or meta.author,
        args.year or meta.year,
        args.publisher or meta.publisher,
    )
    describe(book, meta)
    if rename:
        add_book(path, book, args.dry_run, meta, online=not args.offline)
    elif repeat := repeat_of(path, meta):
        name = catalog.load(CATALOG)[repeat[0]]["slug"]
        with FILING:
            what = handle_repeat(path, meta, repeat[0], args.dry_run, reason=repeat[1])[1]
        print(f"  ! already in the library as {name} ({repeat[1]}); {what}")
    else:
        print("  -> already named; adding folders, notes and catalog row")
        if not args.dry_run:
            setup_book(path, book, meta, online=not args.offline)


def refresh_keywords(online: bool = True) -> None:
    """Papers and theses without keywords: from the PDF's details, its first pages (a thesis:
    its abstract), or OpenAlex."""
    from book_meta import paper_keywords

    rows = catalog.load(CATALOG)
    for doc_id, row in rows.items():
        pdf = LIBRARY / row.get("file", "")
        kind = row.get("type")
        if kind not in ("paper", "thesis") or row.get("keywords") or not pdf.is_file():
            continue
        reader = PdfReader(pdf)
        front = reader.pages[: 2 if kind == "paper" else 8]
        first_pages = "\n".join(p.extract_text() or "" for p in front)
        words = paper_keywords(reader.metadata or {}, first_pages, row.get("doi", ""), online)
        print(f"{row['slug']}: {words or '(none found)'}")
        if words:
            catalog.set_field(CATALOG, doc_id, "keywords", words)


def main() -> None:
    sys.stdout.reconfigure(errors="replace")  # filenames in any language, any terminal
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    paths.add_argument(parser)
    parser.add_argument("file", nargs="?", type=Path, help="one book file (default: scan books/)")
    parser.add_argument("--author")
    parser.add_argument("--year")
    parser.add_argument("--title")
    parser.add_argument("--publisher", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--offline", action="store_true", help="skip the Open Library lookup")
    parser.add_argument(
        "--refresh-chapters",
        action="store_true",
        help="re-read every named book's chapters; replaces only untouched templates",
    )
    parser.add_argument(
        "--remove",
        metavar="SLUG",
        help="take a book out of the library (its PDF, notes and scripts move to archive/)",
    )
    parser.add_argument("--yes", action="store_true", help="don't ask before --remove")
    parser.add_argument(
        "--refresh-keywords",
        action="store_true",
        help="fill in keywords for papers and theses that have none (PDF, OpenAlex)",
    )
    ocr = parser.add_mutually_exclusive_group()
    ocr.add_argument("--ocr", action="store_true", help="OCR scanned PDFs without asking")
    ocr.add_argument("--no-ocr", action="store_true", help="never OCR scanned PDFs")
    args = parser.parse_args()
    paths.ensure_library()
    for done in recover_operations():  # a rename an interruption left halfway
        print(done)

    if args.refresh_keywords:
        refresh_keywords(online=not args.offline)
        library_page.build()
        return
    if args.remove:
        if not (doc := find_document(args.remove)):
            sys.exit(f"No document named {args.remove} (or with that id) in catalog.csv.")
        remove_book(doc["id"], args.dry_run, args.yes)
    elif args.refresh_chapters:
        targets = [args.file.resolve()] if args.file else library_pdfs()
        for pdf in targets:
            if SLUG_RE.match(pdf.stem):
                refresh_chapters(pdf, args.dry_run)
    elif args.file:
        process(args.file.resolve(), args)
    else:
        pending = [p for p in library_pdfs() if not SLUG_RE.match(p.stem)]
        unregistered = unregistered_named_books()
        if not pending and not unregistered:
            print(
                "Nothing new: every PDF in books/, papers/ and theses/ is named and in catalog.csv."
            )
        for path in unregistered:
            process(path, args, rename=False)
        for path in pending:
            process(path, args)

    check_remaining_scans(args)
    if not args.dry_run and CATALOG.exists():
        print(f"Updated {library_page.build().name}")


if __name__ == "__main__":
    main()
