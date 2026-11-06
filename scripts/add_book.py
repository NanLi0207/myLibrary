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

The slug is used for:
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
    uv run scripts/add_book.py --remove <slug>      # move a book's files to archive/ (asks first)
    uv run scripts/add_book.py --ocr / --no-ocr     # scanned PDFs: OCR without asking / never
    uv run scripts/add_book.py --refresh-keywords   # keywords for papers/theses without any
    uv run scripts/add_book.py books/foo.pdf --author "Warren J. Smith" --year 2008 \
        --title "Modern Optical Engineering"   # override anything that came out wrong
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import catalog
import library_page
import paths
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


@dataclass
class Book:
    title: str
    author: str
    year: str
    publisher: str = ""

    @property
    def slug(self) -> str:
        return f"{surname(self.author)}-{self.year}-{short_title(self.title)}"


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
            note.write_text(chapter_note(ch), encoding="utf-8")
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


def refresh_chapters(pdf: Path, dry_run: bool) -> None:
    """Regenerate chapter templates after the reader improved, keeping any notes you wrote."""
    notes_dir = NOTES / pdf.stem
    print(pdf.name)
    chapters = book_chapters(pdf)
    if not chapters:
        return
    old = sorted(notes_dir.glob("ch[0-9][0-9]*.md"))
    kept = [n for n in old if not is_untouched_template(n)]
    print(f"  -> {len(old) - len(kept)} old templates replaced by {len(chapters)} chapters")
    for note in kept:
        print(f"  ! kept {note.name}: it has your notes in it")
    if dry_run:
        return
    for note in old:
        if note not in kept:
            note.unlink()
    write_chapter_notes(notes_dir, chapters)
    readme = notes_dir / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        if re.search(r"^- \[x\]", text, re.MULTILINE | re.IGNORECASE):
            print("  ! README progress list has ticked chapters; left it as it is")
        else:
            text = re.sub(
                r"(## Reading progress\n\n)(?:- \[ \].*\n?)+",
                lambda m: m[1] + progress_list(chapters) + "\n",
                text,
            )
            readme.write_text(text, encoding="utf-8")
    if pdf.stem in catalog.load(CATALOG):
        catalog.upsert(CATALOG, {"slug": pdf.stem, "chapters": str(len(chapters))})
    forget_chapter_pages(pdf.stem)  # chapters changed, so the server looks their pages up again


def forget_chapter_pages(slug: str) -> None:
    """Drop a book from library_server.py's cache of chapter start pages."""
    if not PAGE_CACHE.exists():
        return
    cache = json.loads(PAGE_CACHE.read_text(encoding="utf-8"))
    if cache.pop(slug, None) is not None:
        PAGE_CACHE.write_text(json.dumps(cache, indent=1), encoding="utf-8")


def archive_target(path: Path) -> Path:
    """archive/<books|notes|examples>/<name>, with a date suffix if that name is taken."""
    target = ARCHIVE / path.parent.name / path.name
    if target.exists():
        target = target.with_name(f"{path.stem}-removed-{date.today()}{path.suffix}")
    return target


# --- repeats ----------------------------------------------------------------------------------
# The same work twice: same DOI, same ISBN (books and theses: a paper may carry its proceedings
# volume's ISBN), byte-identical file, or the same name (author, year, title)


def file_hash(path: Path) -> str:
    """SHA-256 of a PDF, remembered until the file changes (it takes a moment for a big book)."""
    import hashlib

    HASHES = LIBRARY / ".cache" / "hashes.json"  # noqa: N806  (LIBRARY can change in tests)
    stat = path.stat()
    key = f"{stat.st_size}:{stat.st_mtime_ns}"
    cache = json.loads(HASHES.read_text(encoding="utf-8")) if HASHES.exists() else {}
    if (cached := cache.get(str(path))) and cached[0] == key:
        return cached[1]
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            digest.update(chunk)
    cache[str(path)] = [key, digest.hexdigest()]
    HASHES.parent.mkdir(parents=True, exist_ok=True)
    HASHES.write_text(json.dumps(cache, indent=0), encoding="utf-8")
    return digest.hexdigest()


def _same_file(a: Path, b: Path) -> bool:
    try:
        return a.stat().st_size == b.stat().st_size and file_hash(a) == file_hash(b)
    except OSError:
        return False


def repeat_of(path: Path, meta: Meta, slug: str = "") -> tuple[str, str] | None:
    """(slug, reason) of the work already in the library that `path` repeats, or None.
    `slug` is the name the new file would get (same name = same author, year and title)."""
    is_paper = meta.kind == "paper"
    isbn = isbn13(meta.isbn) if meta.isbn else ""
    for row in catalog.load(CATALOG).values():
        existing = LIBRARY / row.get("file", "")
        if existing == path or row["slug"] == path.stem:
            continue
        if meta.doi and row.get("doi", "").lower() == meta.doi.lower():
            return row["slug"], "same DOI"
        if isbn and not is_paper and row.get("type") != "paper" and row.get("isbn") == isbn:
            return row["slug"], "same ISBN"
        if slug and row["slug"] == slug:
            return row["slug"], "same author, year and title"
        if existing.is_file() and _same_file(path, existing):
            return row["slug"], "identical file"
    return None


def archive_repeat(path: Path) -> Path:
    """Move a repeated PDF to archive/<folder>/ (never deleted); returns where it went."""
    target = archive_target(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    path.rename(target)
    return target


def has_own_work(slug: str, notes_dir: Path | None = None) -> bool:
    """Whether a book's notes hold anything of yours: a ticked chapter, the page you last read,
    notes you wrote, saved words, or a chapter script."""
    notes_dir = notes_dir or NOTES / slug
    readme = notes_dir / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        if re.search(r"^- \[[xX]\]", text, re.MULTILINE) or "Last read:" in text:
            return True
    for note in notes_dir.glob("*.md") if notes_dir.exists() else []:
        if note.name != "README.md" and not is_untouched_template(note):
            return True
    return any((EXAMPLES / slug).glob("*.py")) if (EXAMPLES / slug).exists() else False


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


def catalog_repeats() -> list[dict]:
    """Pairs already in the catalog that are the same work: [{keep, drop, reason, why, move}].
    The copy with more information is kept; if the other one holds your work, `move` is True
    (move it over first). drop="" when both hold your work: then nothing should be touched."""
    rows = list(catalog.load(CATALOG).values())
    found, seen = [], set()
    for i, a in enumerate(rows):
        for b in rows[i + 1 :]:
            if a["slug"] in seen or b["slug"] in seen:
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
            work_a, work_b = has_own_work(a["slug"]), has_own_work(b["slug"])
            if work_a and work_b:
                found.append({"keep": a["slug"], "drop": "", "reason": reason, "other": b["slug"]})
                continue
            score_a, score_b = info_score(a, fa), info_score(b, fb)
            a_first = a.get("added", "") <= b.get("added", "")
            if score_a > score_b or (score_a == score_b and a_first):
                keep, drop, why = a, b, why_richer(score_a, score_b)
            else:
                keep, drop, why = b, a, why_richer(score_b, score_a)
            found.append({"keep": keep["slug"], "drop": drop["slug"], "reason": reason,
                          "why": why, "move": has_own_work(drop["slug"])})  # fmt: skip
            seen.add(drop["slug"])
    return found


def merge_into(src: str, dst: str) -> list[str]:
    """Before `src` goes to the archive: give `dst` (the copy kept) everything of yours that
    `src` has, and the details it lacks. Returns what was moved, e.g. ["2 ticked chapters",
    "last-read page", "notes ch03-stops.md", "vocabulary", "1 script", "shelves"]. Only
    copies: `src` itself goes to the archive complete, as a backup."""
    import shutil

    rows = catalog.load(CATALOG)
    moved = []
    # Catalog: details dst lacks, and the shelves of both
    fill = {
        k: rows[src].get(k, "") for k in INFO_FIELDS if not rows[dst].get(k) and rows[src].get(k)
    }
    shelves = catalog.split_list(rows[dst].get("shelves", "") + ";" + rows[src].get("shelves", ""))
    if len(shelves) > len(catalog.split_list(rows[dst].get("shelves", ""))):
        moved.append("shelves")
    catalog.upsert(CATALOG, {"slug": dst, **fill})
    catalog.set_field(CATALOG, dst, "shelves", "; ".join(shelves))

    src_dir, dst_dir = NOTES / src, NOTES / dst
    dst_dir.mkdir(parents=True, exist_ok=True)
    readme = dst_dir / "README.md"
    if src_dir.exists() and readme.exists():
        text = readme.read_text(encoding="utf-8")
        old_readme = src_dir / "README.md"
        old = old_readme.read_text(encoding="utf-8") if old_readme.exists() else ""
        # Ticks, by chapter number ("Read the paper" is chapter 1)
        ticked = 0
        for chapter in library_page.chapters_in(old):
            if chapter["done"] and chapter["number"] is not None:
                n = chapter["number"]
                paper = rf"|\[{re.escape(library_page.PAPER_ITEM)}\]" if n == 1 else ""
                pattern = re.compile(rf"^- \[ \] (\[?Ch(?:apter)?\.?\s*{n}:{paper})", re.MULTILINE)
                text, count = pattern.subn(lambda m: f"- [x] {m[1]}", text, count=1)
                ticked += count
        if ticked:
            moved.append(f"{ticked} ticked chapter{'s' if ticked > 1 else ''}")
        # The page you last read (unless the kept copy has its own)
        last = library_page.LAST_READ_RE.search(old)
        if last and not library_page.LAST_READ_RE.search(text):
            heading = re.search(r"^## Reading progress[ \t]*\n(?:[ \t]*\n)?", text, re.MULTILINE)
            at = heading.end() if heading else len(text)
            text = text[:at] + last[0] + "\n\n" + text[at:].lstrip("\n")
            moved.append("last-read page")
        readme.write_text(text, encoding="utf-8")
    # Notes you wrote: into the same chapter's template (still empty, so nothing is lost)
    for note in sorted(src_dir.glob("*.md")) if src_dir.exists() else []:
        if note.name == "README.md" or is_untouched_template(note):
            continue
        target = dst_dir / note.name
        if m := re.match(r"(ch\d{2})-", note.name):
            target = next(iter(sorted(dst_dir.glob(f"{m[1]}-*.md"))), target)
        if target.exists() and not is_untouched_template(target):
            target = target.with_name(f"{target.stem}-from-{src}.md")
        target.write_text(note.read_text(encoding="utf-8"), encoding="utf-8")
        moved.append("vocabulary" if note.name == "vocabulary.md" else f"notes {note.name}")
    # Chapter scripts
    scripts = sorted((EXAMPLES / src).glob("*.py")) if (EXAMPLES / src).exists() else []
    for script in scripts:
        target = EXAMPLES / dst / script.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target = target.with_name(f"{target.stem}_from_{src.replace('-', '_')}.py")
        shutil.copy2(script, target)
    if scripts:
        moved.append(f"{len(scripts)} script{'s' if len(scripts) > 1 else ''}")
    return moved


def richer_than_library(path: Path, meta: Meta, slug: str) -> str:
    """Why the new copy's *file* offers more than the library's PDF of `slug` (searchable
    text, bookmarks, more pages); "" if it doesn't, e.g. an identical file. Its details are
    another matter: fill_details() adds them either way."""
    row = catalog.load(CATALOG).get(slug)
    if not row:
        return ""
    old_pdf = LIBRARY / row["file"]
    if not old_pdf.is_file():
        return "a PDF"  # the library's PDF is missing: this copy brings it back
    if _same_file(path, old_pdf):
        return ""
    new, old = info_score({}, path), info_score({}, old_pdf)
    return why_richer(new, old) if new > old else ""


def fill_details(slug: str, meta: Meta) -> list[str]:
    """Details a repeat knows that the library's entry lacks (DOI, journal, keywords, ...):
    added to the entry. Returns their names."""
    row = catalog.load(CATALOG).get(slug, {})
    fill = {k: v for k, v in meta_row(meta).items() if k in INFO_FIELDS and v and not row.get(k)}
    if fill:
        catalog.upsert(CATALOG, {"slug": slug, **fill})
    return list(fill)


def replace_pdf(slug: str, path: Path, meta: Meta) -> Path:
    """A new copy of something already in the library that offers more (e.g. searchable text,
    or a DOI): it takes the old PDF's place under the same name, so your notes and progress stay
    with it; the old PDF goes to archive/. Returns where the old one went."""
    row = catalog.load(CATALOG)[slug]
    pdf = LIBRARY / row["file"]
    old = archive_repeat(pdf) if pdf.exists() else pdf
    path.rename(pdf)
    fill_details(slug, meta)
    catalog.upsert(CATALOG, {"slug": slug, "pages": meta.pages or row.get("pages", "")})
    forget_chapter_pages(slug)
    if not row.get("chapters") and row.get("type") != "paper":  # now it may have bookmarks
        refresh_chapters(pdf, dry_run=False)
    return old


def remove_book(slug: str, dry_run: bool, yes: bool) -> None:
    """Take a book out of the library; its PDF, notes and scripts move to archive/."""
    known = catalog.load(CATALOG)
    paths = [folder / f"{slug}.pdf" for folder in folders()] + [NOTES / slug, EXAMPLES / slug]
    existing = [p for p in paths if p.exists()]
    if slug not in known and not existing:
        print(f"No book '{slug}' in catalog.csv or in books/, papers/, theses/, notes/, examples/.")
        return
    title = known.get(slug, {}).get("title", slug)
    print(f"Remove '{title}' ({slug}) from the library:")
    for p in existing:
        print(
            f"  move {p.relative_to(BOOKS.parent)} -> {archive_target(p).relative_to(BOOKS.parent)}"
        )
    if slug in known:
        print("  remove its row from catalog.csv")
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
    for p in existing:
        target = archive_target(p)
        target.parent.mkdir(parents=True, exist_ok=True)
        p.rename(target)
    catalog.remove(CATALOG, slug)
    forget_chapter_pages(slug)
    print("Done. To restore it, move the files back from archive/ and run add_book.py.")


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


def setup_book(pdf: Path, book: Book, meta: Meta, online: bool = True) -> None:
    """Folders, notes README, chapter templates and catalog row for a named PDF.

    Safe to repeat: existing notes are never overwritten.
    """
    slug = pdf.stem
    relative = f"{pdf.parent.name}/{pdf.name}"  # books/, papers/ or theses/<slug>.pdf
    notes_dir = NOTES / slug
    notes_dir.mkdir(parents=True, exist_ok=True)
    readme = notes_dir / "README.md"
    is_paper, is_thesis = meta.kind == "paper", meta.kind == "thesis"
    if is_paper:  # one notes file, and "Read the paper" instead of chapters
        chapters = []
        if not readme.exists():
            readme.write_text(paper_readme(book, relative, meta), encoding="utf-8")
        notes = notes_dir / "notes.md"
        if not notes.exists():
            notes.write_text(PAPER_NOTES.format(title=book.title), encoding="utf-8")
    else:
        chapters = book_chapters(pdf)
        if not readme.exists():
            readme.write_text(notes_readme(book, relative, chapters, meta), encoding="utf-8")
        write_chapter_notes(notes_dir, chapters)
    catalog.upsert(
        CATALOG,
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
    print(f"  -> catalog.csv row '{slug}'")
    # Its subject (OpenAlex), then shelves: the subject's, and yours that fit (only if it's on
    # none yet)
    if online and not catalog.load(CATALOG).get(slug, {}).get("topic"):
        if found := subjects.classify(slug, LIBRARY, CATALOG):
            print(f"  -> subject: {found['field']} / {found['topic']} ({found['score']})")
    if found := shelves.auto_shelve(slug, LIBRARY, CATALOG):
        print(f"  -> shelves: {'; '.join(found)} (change them with Shelves on the library page)")


def add_book(
    path: Path, book: Book, dry_run: bool, meta: Meta | None = None, online: bool = True
) -> None:
    meta = meta or Meta()
    folder = folder_for(meta.kind)
    target = folder / f"{book.slug}{path.suffix.lower()}"
    taken = any(f.exists() and f != path for f in (d / target.name for d in folders()))
    if repeat := repeat_of(path, meta, book.slug) or (
        (target.stem, "same author, year and title") if taken else None
    ):
        print(f"  ! already in the library as {repeat[0]} ({repeat[1]})", end="")
        if better := richer_than_library(path, meta, repeat[0]):
            if dry_run:
                print(f"; this copy has {better}: would replace its PDF")
                return
            old = replace_pdf(repeat[0], path, meta)
            print(
                f"; this copy has {better}: it replaces the PDF (old: archive/{old.parent.name}/)"
            )
            return
        if not dry_run and (added := fill_details(repeat[0], meta)):
            print(f"; added its {', '.join(added)} to the entry", end="")
        if dry_run:
            print("; would be moved to archive/")
            return
        kept = archive_repeat(path)
        print(f"; moved to archive/{kept.parent.name}/{kept.name}")
        return
    print(f"  -> {folder.name}/{target.name}")
    if dry_run:
        return
    folder.mkdir(parents=True, exist_ok=True)
    path.rename(target)
    setup_book(target, book, meta or Meta(), online)


def unregistered_named_books() -> list[Path]:
    """Already-named PDFs missing from the catalog (e.g. renamed by hand)."""
    known = catalog.load(CATALOG)
    return [p for p in library_pdfs() if SLUG_RE.match(p.stem) and p.stem not in known]


def describe(meta: Meta) -> None:
    if meta.kind == "thesis":
        print(f"     a {kind_word(meta)}")
    for key in ("title", "author", "year", "publisher", "institution", "supervisors"):
        if value := getattr(meta, key):
            print(f"     {key:<11} {value}   [{meta.sources[key]}]")


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
    describe(
        Meta(
            book.title,
            book.author,
            book.year,
            book.publisher,
            kind=meta.kind,
            degree=meta.degree,
            institution=meta.institution,
            supervisors=meta.supervisors,
            sources=meta.sources,
        )  # fmt: skip
    )
    missing = [k for k in ("title", "author", "year") if not getattr(book, k)]
    if missing:
        flags = " ".join(f"--{k} .." for k in missing)
        print(
            f'  ? missing {", ".join(missing)}; rerun: uv run scripts/add_book.py "{path}" {flags}'
        )
        return
    if rename:
        add_book(path, book, args.dry_run, meta, online=not args.offline)
    elif repeat := repeat_of(path, meta):
        print(f"  ! already in the library as {repeat[0]} ({repeat[1]})", end="")
        if args.dry_run:
            print("; would be moved to archive/")
        else:
            kept = archive_repeat(path)
            print(f"; moved to archive/{kept.parent.name}/{kept.name}")
    else:
        print("  -> already named; adding folders, notes and catalog row")
        if not args.dry_run:
            setup_book(path, book, meta, online=not args.offline)


def refresh_keywords(online: bool = True) -> None:
    """Papers and theses without keywords: from the PDF's details, its first pages (a thesis:
    its abstract), or OpenAlex."""
    from book_meta import paper_keywords

    rows = catalog.load(CATALOG)
    for slug, row in rows.items():
        pdf = LIBRARY / row.get("file", "")
        kind = row.get("type")
        if kind not in ("paper", "thesis") or row.get("keywords") or not pdf.is_file():
            continue
        reader = PdfReader(pdf)
        front = reader.pages[: 2 if kind == "paper" else 8]
        first_pages = "\n".join(p.extract_text() or "" for p in front)
        words = paper_keywords(reader.metadata or {}, first_pages, row.get("doi", ""), online)
        print(f"{slug}: {words or '(none found)'}")
        if words:
            catalog.set_field(CATALOG, slug, "keywords", words)


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

    if args.refresh_keywords:
        refresh_keywords(online=not args.offline)
        library_page.build()
        return
    if args.remove:
        remove_book(Path(args.remove).stem, args.dry_run, args.yes)
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
            print("Nothing new: every book in books/ is named and in catalog.csv.")
        for path in unregistered:
            process(path, args, rename=False)
        for path in pending:
            process(path, args)

    check_remaining_scans(args)
    if not args.dry_run and CATALOG.exists():
        print(f"Updated {library_page.build().name}")


if __name__ == "__main__":
    main()
