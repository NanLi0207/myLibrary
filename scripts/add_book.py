"""Give new books (books/) and papers (papers/) a consistent name and create their notes.

Every book gets a slug:  <author-surname>-<year>-<short-title>
    e.g. shannon-1997-art-science-optical-design

Title, author and year come from the book itself where possible (ISBN -> Open Library,
PDF metadata, copyright page), with the filename as a fallback; see book_meta.py.

Papers are found by their DOI, arXiv number, or title (see book_meta.identify) and always
end up in papers/; a PDF put into papers/ is a paper even if nothing online knows it.

The slug is used for:
    books/<slug>.pdf  or  papers/<slug>.pdf
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
    uv run scripts/add_book.py --refresh-keywords   # fill in keywords for papers without any
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
from book_meta import Meta, ascii_words, identify, surname
from book_toc import STOP_WORDS, Chapter, read_toc
from ocr_pdf import ask, make_searchable, needs_ocr, ocr_minutes
from pypdf import PdfReader

LIBRARY = paths.LIBRARY
BOOKS, EXAMPLES, NOTES = LIBRARY / "books", LIBRARY / "examples", LIBRARY / "notes"
PAPERS = LIBRARY / "papers"


def library_pdfs() -> list[Path]:
    """Every PDF in books/ and papers/."""
    return sorted(BOOKS.glob("*.pdf")) + sorted(PAPERS.glob("*.pdf"))


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
            line.startswith("#") or line == "-" or line == "[Back to book](README.md)"
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


def remove_book(slug: str, dry_run: bool, yes: bool) -> None:
    """Take a book out of the library; its PDF, notes and scripts move to archive/."""
    known = catalog.load(CATALOG)
    paths = [BOOKS / f"{slug}.pdf", PAPERS / f"{slug}.pdf", NOTES / slug, EXAMPLES / slug]
    existing = [p for p in paths if p.exists()]
    if slug not in known and not existing:
        print(f"No book '{slug}' in catalog.csv or in books/, papers/, notes/, examples/.")
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


def notes_readme(book: Book, filename: str, chapters: list[Chapter]) -> str:
    return f"""# {book.title}

| | |
|---|---|
| Author | {book.author} |
| Year | {book.year} |
| Publisher | {book.publisher or "?"} |
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


def setup_book(pdf: Path, book: Book, meta: Meta) -> None:
    """Folders, notes README, chapter templates and catalog row for a named PDF.

    Safe to repeat: existing notes are never overwritten.
    """
    slug = pdf.stem
    relative = f"{pdf.parent.name}/{pdf.name}"  # books/<slug>.pdf or papers/<slug>.pdf
    notes_dir = NOTES / slug
    notes_dir.mkdir(parents=True, exist_ok=True)
    readme = notes_dir / "README.md"
    is_paper = meta.kind == "paper"
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
            readme.write_text(notes_readme(book, relative, chapters), encoding="utf-8")
        write_chapter_notes(notes_dir, chapters)
    catalog.upsert(
        CATALOG,
        {
            "slug": slug,
            "type": "paper" if is_paper else "book",
            "title": book.title,
            "authors": book.author,
            "year": book.year,
            "publisher": book.publisher,
            "isbn": meta.isbn,
            "journal": meta.journal,
            "volume": meta.volume,
            "issue": meta.issue,
            "page_range": meta.page_range,
            "doi": meta.doi,
            "keywords": meta.keywords,
            "pages": meta.pages,
            "chapters": str(len(chapters) or ""),
            "subjects": meta.subjects,
            "file": relative,
            "notes": f"notes/{slug}/",
            "added": date.today().isoformat(),
            "openlibrary": "" if is_paper else meta.url,
            "metadata_sources": "; ".join(f"{k}: {v}" for k, v in meta.sources.items()),
        },
    )
    print(f"  -> catalog.csv row '{slug}'")


def add_book(path: Path, book: Book, dry_run: bool, meta: Meta | None = None) -> None:
    folder = PAPERS if meta and meta.kind == "paper" else BOOKS
    target = folder / f"{book.slug}{path.suffix.lower()}"
    print(f"  -> {folder.name}/{target.name}")
    if any(f.exists() and f != path for f in (BOOKS / target.name, PAPERS / target.name)):
        print(f"  ! {target.name} already exists (duplicate?), leaving this file as it is")
        return
    if dry_run:
        return
    folder.mkdir(parents=True, exist_ok=True)
    path.rename(target)
    setup_book(target, book, meta or Meta())


def unregistered_named_books() -> list[Path]:
    """Already-named PDFs missing from the catalog (e.g. renamed by hand)."""
    known = catalog.load(CATALOG)
    return [p for p in library_pdfs() if SLUG_RE.match(p.stem) and p.stem not in known]


def describe(meta: Meta) -> None:
    for key in ("title", "author", "year", "publisher"):
        if value := getattr(meta, key):
            print(f"     {key:<9} {value}   [{meta.sources[key]}]")


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
    print(f"\n{len(scans)} scanned PDF(s) in books/ or papers/ have no text layer yet:")
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


def process(path: Path, args: argparse.Namespace, rename: bool = True) -> None:
    print(path.name)
    offer_ocr(path, args)
    meta = identify(path, online=not args.offline, paper=path.parent == PAPERS)
    meta.sources.update(
        {k: "command line" for k in ("title", "author", "year") if getattr(args, k)}
    )
    book = Book(
        args.title or meta.title,
        args.author or meta.author,
        args.year or meta.year,
        args.publisher or meta.publisher,
    )
    describe(Meta(book.title, book.author, book.year, book.publisher, sources=meta.sources))
    missing = [k for k in ("title", "author", "year") if not getattr(book, k)]
    if missing:
        flags = " ".join(f"--{k} .." for k in missing)
        print(
            f'  ? missing {", ".join(missing)}; rerun: uv run scripts/add_book.py "{path}" {flags}'
        )
        return
    if rename:
        add_book(path, book, args.dry_run, meta)
    else:
        print("  -> already named; adding folders, notes and catalog row")
        if not args.dry_run:
            setup_book(path, book, meta)


def refresh_keywords(online: bool = True) -> None:
    """Papers without keywords: from the PDF's details, its first page, or OpenAlex."""
    from book_meta import paper_keywords

    rows = catalog.load(CATALOG)
    for slug, row in rows.items():
        pdf = LIBRARY / row.get("file", "")
        if row.get("type") != "paper" or row.get("keywords") or not pdf.is_file():
            continue
        reader = PdfReader(pdf)
        first_pages = "\n".join(p.extract_text() or "" for p in reader.pages[:2])
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
        help="fill in keywords for papers that have none (PDF details, first page, OpenAlex)",
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
