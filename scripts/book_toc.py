"""Read a PDF's table of contents (chapter + section headings only, never body text).

Strategies, first one that finds chapters wins:
  1. PDF bookmarks
  2. The printed "Contents" pages: numbered lines, tolerant of OCR noise and wrapped lines
  3. The printed "Contents" pages by font: bold lines are chapters (unnumbered books)
  4. Chapter-opening pages: pages that start with "Chapter N" (PDFs without a Contents)
Scanned PDFs with no text layer get their Contents pages read with OCR (book_ocr.py),
then parsed like strategy 2.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from book_ocr import has_text_layer, ocr_pages
from pypdf import PdfReader

FRONT_PAGES = 40  # where to look for the printed Contents
MAX_CONTENTS_PAGES = 15
MAX_CHAPTER_JUMP = 3  # numbering may skip a chapter or two when OCR garbles a line
# Dropped from slugs and filenames (add_book.py)
STOP_WORDS = {"a", "an", "the", "and", "of", "to", "in", "for", "on", "with", "by", "at"}
SMALL_WORDS = STOP_WORDS | {"or"}  # kept lowercase when tidying ALL-CAPS titles
FRONT_BACK_MATTER = re.compile(
    r"^(cover|front cover|back cover|title|copyright|(table of )?contents|preface|foreword|"
    r"acknowledg|dedication|index|bibliography|references|glossary|about the author|"
    r"editors?|contributors|color insert)",
    re.IGNORECASE,
)

# "3 Aberrations", "Chapter 3: Aberrations", "3. Aberrations"; not "3.1 Definition"
CHAPTER_TITLE_RE = re.compile(r"^(?:chapter\s+)?(\d{1,2})(?:[.:]\s*|\s+)(?!\d)(.+)$", re.IGNORECASE)
EXPLICIT_CHAPTER_RE = re.compile(r"^chapter\s+(\d{1,2})\b[.:]?\s*(.*)$", re.IGNORECASE)
SECTION_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.?\s+(?!\d)(\S.*)$")  # "2.3 Title", not "2.3.1"
SUBSECTION_RE = re.compile(r"^\d{1,2}(?:\.\d{1,2}){2,}\b")
BARE_CHAPTER_RE = re.compile(r"^(\d{1,2})\.?\s+([A-Za-z].*)$")
HEADING_START_RE = re.compile(r"^(?:chapter\s+\d|\d{1,2}(?:\.\d{1,2})*\.?\s)", re.IGNORECASE)
# A contents line ends in a page number; OCR turns some into "s", "io", "^" or "I"
# (possessive "++": a long dot leader could otherwise be split in exponentially many ways,
# which hung on letter-spaced contents such as "2 . 1 A b s o r p t i o n ......... 8")
PAGE_TOKEN_RE = re.compile(
    r"(?:\s|\.{2,})++(\d{1,4}|[ivxlcdm]{1,7}|[^\s\-]{1,2})\s*$", re.IGNORECASE
)
PAGE_HEADER_RE = re.compile(
    r"^(?:[ivxlcdm]+|\d+)?\s*(?:table of )?contents\s*(?:[ivxlcdm]+|\d+)?$", re.I
)


@dataclass
class Chapter:
    number: int
    title: str
    sections: list[str] = field(default_factory=list)
    page: int | None = None  # printed page number from the Contents, when it lists one
    section_pages: list[int | None] = field(default_factory=list)  # printed, one per section


def tidy(title: str) -> str:
    """Collapse whitespace/control characters and turn ALL-CAPS headings into Title Case."""
    title = " ".join(re.sub(r"[\x00-\x1f]", " ", title).split()).strip(" .:")
    if title.isupper():
        words = title.lower().split()
        title = " ".join(
            w if i and w in SMALL_WORDS else "-".join(p.capitalize() for p in w.split("-"))
            for i, w in enumerate(words)
        )
    return title


def read_toc(pdf: Path) -> list[Chapter]:
    reader = PdfReader(pdf)
    if not reader.outline and not has_text_layer(reader):
        print("  scanned PDF without text: reading the Contents pages with OCR...")
        return scanned_contents(pdf, len(reader.pages))[0]
    contents = contents_pages(reader)
    printed = toc_from_text("\n".join(reader.pages[i].extract_text() or "" for i in contents))
    if chapters := toc_from_outline(reader.outline):
        # Bookmarks often list chapters only; borrow section headings from the printed contents
        sections = {c.number: c.sections for c in printed}
        for ch in chapters:
            if not ch.sections:
                ch.sections = sections.get(ch.number, [])
        return chapters
    if len(printed) >= 2:
        return printed
    if len(chapters := toc_from_fonts(font_lines(reader, contents))) >= 2:
        return chapters
    return toc_from_chapter_pages([page.extract_text() or "" for page in reader.pages])


# --- 1. bookmarks -------------------------------------------------------------------------


def _entries(items: list) -> list[tuple[str, list[str]]]:
    """(title, direct-child titles) for the entries at this outline level only."""
    result = []
    for i, item in enumerate(items):
        if isinstance(item, list):
            continue
        nxt = items[i + 1] if i + 1 < len(items) else None
        kids = [c.title for c in nxt if not isinstance(c, list)] if isinstance(nxt, list) else []
        result.append((item.title, kids))
    return result


def _walk(items: list) -> list[tuple[str, list[str]]]:
    """Like _entries, but for every depth of the outline."""
    return _entries(items) + [e for item in items if isinstance(item, list) for e in _walk(item)]


def toc_from_outline(outline: list) -> list[Chapter]:
    chapters = [
        Chapter(int(m[1]), tidy(m[2]), [tidy(s) for s in kids])
        for title, kids in _walk(outline)
        if (m := CHAPTER_TITLE_RE.match(tidy(title)))
    ]
    if chapters:
        return sorted({c.number: c for c in chapters}.values(), key=lambda c: c.number)
    # Unnumbered bookmarks: top-level entries with children are chapters
    named = [(t, k) for t, k in _entries(outline) if k and not FRONT_BACK_MATTER.match(tidy(t))]
    return [Chapter(n, tidy(t), [tidy(s) for s in k]) for n, (t, k) in enumerate(named, 1)]


# --- 2. printed contents, numbered --------------------------------------------------------


def _is_contents_like(text: str) -> bool:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    ending_in_page = sum(bool(PAGE_TOKEN_RE.search(ln)) for ln in lines)
    return len(lines) >= 5 and ending_in_page / len(lines) >= 0.4


def _line_count(text: str) -> int:
    return sum(1 for ln in text.splitlines() if ln.strip())


def find_contents(texts: dict[int, str]) -> list[int]:
    """Indexes of the printed Contents pages among {page index: text}; empty if none.

    Starts at the first page with a "Contents" heading and continues while pages still look
    like contents (or repeat the "Contents" running header). One stray page is stepped over
    if contents continue right after it: a blank left-hand page, or in scans a page that
    ended up in the wrong place.
    """

    def is_contents(i: int) -> bool:
        text = texts.get(i, "")
        return _is_contents_like(text) or bool(re.search(r"\bcontents\b", text[:200], re.I))

    order = sorted(texts)
    start = next((i for i in order if re.search(r"\bcontents\b", texts[i][:400], re.I)), None)
    if start is None:
        return []
    pages, skipped = [start], False
    for i in order[order.index(start) + 1 :][:MAX_CONTENTS_PAGES]:
        if is_contents(i):
            pages.append(i)
            skipped = False
        elif not skipped and (_line_count(texts[i]) < 5 or is_contents(i + 1)):
            skipped = True
        else:
            break
    return pages


def contents_pages(reader: PdfReader) -> list[int]:
    """Indexes of the printed Contents pages; empty if the PDF has none (never body text)."""
    front = range(min(FRONT_PAGES + MAX_CONTENTS_PAGES, len(reader.pages)))
    return find_contents({i: reader.pages[i].extract_text() or "" for i in front})


def scanned_contents(pdf: Path, page_count: int) -> tuple[list[Chapter], list[int]]:
    """(chapters, indexes of the Contents pages) for an image-only scan: OCR the front
    pages until the printed Contents has been read."""
    texts: dict[int, str] = {}
    for i in range(min(FRONT_PAGES, page_count)):
        texts |= ocr_pages(pdf, [i])
        contents = find_contents(texts)
        # Stop three pages past the end of the contents (one stray page may sit between)
        if contents and i >= contents[-1] + 3:
            break
    contents = find_contents(texts)
    return toc_from_text("\n".join(texts[i] for i in contents)), contents


PAGE_TOP = 0.22  # fraction of the page read when looking for chapter openings
RUN_WINDOW = 8  # pages after an opening in which its running headers should show up


def _flat(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def chapter_opening(top_text: str, ch: Chapter) -> int:
    """How surely a page top opens this chapter: 2 = number + title, 1 = title only, 0 = no."""
    flat, key = _flat(top_text), _flat(ch.title)[:20]
    if re.search(rf"\bchapter\s*{ch.number}\b", top_text, re.I):
        return 2
    # "4 IMAGE ANALYSIS", but not a running header "284 IMAGE ANALYSIS"
    if len(key) >= 5 and re.search(rf"(?<!\d){ch.number}{re.escape(key)}", flat):
        return 2
    return 1 if len(key) >= 8 and key in flat else 0


def scanned_chapter_pages(pdf: Path, page_count: int) -> dict[int, int]:
    """{chapter number: 1-based PDF page} for an image-only scan.

    Reads the top of each page with OCR (once, cached). For each chapter in order, the
    opening is the first page after the previous chapter whose top shows the chapter's
    title and which is followed by more such pages (its running headers); a one-off
    mention elsewhere doesn't count. Chapters that still aren't found are placed using
    the Contents page numbers of the chapters around them.
    """
    chapters, contents = scanned_contents(pdf, page_count)
    body = range((contents[-1] + 1) if contents else 0, page_count)
    tops = ocr_pages(pdf, list(body), top=PAGE_TOP)

    def matches(i: int, ch: Chapter) -> int:
        return chapter_opening(tops.get(i, ""), ch)

    def opens_run(i: int, ch: Chapter) -> bool:
        # The real opening is followed by the chapter's running headers on the next pages;
        # a stray match (a caption or cross-reference mentioning the title) is not
        return sum(matches(j, ch) >= 1 for j in range(i + 1, i + 1 + RUN_WINDOW)) >= 2

    found: dict[int, int] = {}  # chapter number -> 0-based page index
    after = body.start
    for ch in chapters:
        candidates = [i for i in body if i >= after and matches(i, ch) >= 1]
        hit = next((i for i in candidates if opens_run(i, ch)), None)
        if hit is None:  # no running headers to go on: best single match
            hit = next((i for i in candidates if matches(i, ch) == 2), None)
        if hit is None and candidates:
            hit = candidates[0]
        if hit is not None:
            found[ch.number], after = hit, hit + 1

    # Place the rest using the Contents page numbers: between the chapters found around them,
    # or (past the last one) one PDF page per printed page. Chapters that would land beyond
    # the end of the PDF aren't in this scan, so they get no page.
    anchors = sorted((c.page, found[c.number]) for c in chapters if c.number in found and c.page)
    for ch in chapters:
        if ch.number in found or ch.page is None or not anchors:
            continue
        before = [a for a in anchors if a[0] <= ch.page]
        later = [a for a in anchors if a[0] > ch.page]
        if before and later:
            (p0, i0), (p1, i1) = before[-1], later[0]
            guess = round(i0 + (ch.page - p0) * (i1 - i0) / (p1 - p0))
        else:
            p0, i0 = (before or later)[-1 if before else 0]
            guess = i0 + ch.page - p0
        if body.start <= guess < page_count:
            found[ch.number] = guess
    return {n: i + 1 for n, i in sorted(found.items())}


def _page_number(line: str) -> int | None:
    """The page number a contents line ends with ('3 ABERRATIONS 164' -> 164)."""
    m = re.search(r"(?:\s|\.)(\d{1,4})\s*$", line)
    return int(m[1]) if m else None


def _strip_page(line: str) -> str:
    return PAGE_TOKEN_RE.sub("", line).strip(" .")


def _join_wrapped(lines: list[str]) -> list[str]:
    """Rejoin headings whose title wrapped onto the next line (page number on the 2nd line)."""
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        for _ in range(2):
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if (
                HEADING_START_RE.match(line)
                and not PAGE_TOKEN_RE.search(line)
                and nxt
                and not HEADING_START_RE.match(nxt)
                and len(nxt) < 60
            ):
                line, i = f"{line} {nxt}", i + 1
        out.append(line)
        i += 1
    return out


def _clean_plain_title(line: str) -> str:
    """'S BASIC OPTICS FOR DESIGN 24' (OCR-garbled chapter number) -> 'BASIC OPTICS FOR DESIGN'."""
    title = _strip_page(line)
    title = re.sub(r"^(?:\S{1,2}\s+)(?=[A-Z])", "", title)
    if PAGE_HEADER_RE.match(title) or FRONT_BACK_MATTER.match(title) or len(title) < 3:
        return ""
    return title


def toc_from_text(text: str) -> list[Chapter]:
    """Parse printed contents lines such as '3 ABERRATIONS 164' and '3.1 Definition 164'."""
    lines = _join_wrapped([ln.strip() for ln in text.splitlines() if ln.strip()])
    chapters: dict[int, Chapter] = {}
    current = 0
    plain = ""  # last unnumbered line: the title of a chapter whose number OCR lost

    def accept(n: int) -> bool:
        return n == current or 0 < n - current <= MAX_CHAPTER_JUMP

    for line in lines:
        if SUBSECTION_RE.match(line):
            plain = ""
            continue
        if (m := EXPLICIT_CHAPTER_RE.match(line)) or (
            not SECTION_RE.match(line) and (m := BARE_CHAPTER_RE.match(line))
        ):
            n, title = int(m[1]), tidy(_strip_page(m[2]))
            if n == 1 and current >= 2:
                break  # numbering restarted: past the contents, into the body
            if accept(n) and title:
                ch = chapters.setdefault(n, Chapter(n, title, page=_page_number(line)))
                if ch.title == f"Chapter {n}":
                    ch.title = title
                ch.page = ch.page or _page_number(line)
                current = n
            plain = ""
        elif m := SECTION_RE.match(line):
            n = int(m[1])
            if n == 1 and current >= 2:
                break
            if accept(n):
                if n not in chapters:
                    chapters[n] = Chapter(
                        n,
                        tidy(_clean_plain_title(plain)) or f"Chapter {n}",
                        # the unnumbered heading line carries the page; else the first section's
                        page=_page_number(plain) or _page_number(line),
                    )
                section = f"{m[1]}.{m[2]} {tidy(_strip_page(m[3]))}"
                if section not in chapters[n].sections:
                    chapters[n].sections.append(section)
                    chapters[n].section_pages.append(_page_number(line))
                current = n
            plain = ""
        else:
            plain = line
    return [chapters[n] for n in sorted(chapters)]


# --- 3. printed contents, by font ---------------------------------------------------------


def font_lines(reader: PdfReader, pages: list[int]) -> list[tuple[bool, str]]:
    """(is_bold, text) for each text run on the given pages."""
    lines: list[tuple[bool, str]] = []
    for i in pages:

        def visit(text, cm, tm, font, size):
            if text.strip():
                name = str((font or {}).get("/BaseFont", ""))
                lines.append(("bold" in name.lower(), text.strip()))

        reader.pages[i].extract_text(visitor_text=visit)
    return lines


def toc_from_fonts(lines: list[tuple[bool, str]]) -> list[Chapter]:
    """Unnumbered contents where chapters are bold and topics regular (e.g. SPIE Field Guides)."""
    chapters: list[Chapter] = []
    for bold, text in lines:
        title = tidy(_strip_page(text))
        if not title or PAGE_HEADER_RE.match(title) or not PAGE_TOKEN_RE.search(text):
            continue
        if bold:
            if not FRONT_BACK_MATTER.match(title):
                chapters.append(Chapter(len(chapters) + 1, title, page=_page_number(text)))
        elif chapters:
            chapters[-1].sections.append(title)
            chapters[-1].section_pages.append(_page_number(text))
    # Only trust this when bold really marks chapters, not every line
    return chapters if chapters and any(c.sections for c in chapters) else []


# --- 4. chapter-opening pages -------------------------------------------------------------


def toc_from_chapter_pages(page_texts: list[str]) -> list[Chapter]:
    """Pages that begin with 'Chapter N' start a chapter; 'N.M Title' lines are its sections."""
    chapters: dict[int, Chapter] = {}
    current = 0
    for text in page_texts:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if lines and (m := EXPLICIT_CHAPTER_RE.match(lines[0])) and int(m[1]) > current:
            n = int(m[1])
            title_parts = [m[2]] if m[2] else []
            for ln in lines[1:3]:  # titles often wrap over two or three short lines
                if len(" ".join(title_parts + [ln])) > 80 or ln.endswith(".") or len(ln) > 50:
                    break
                title_parts.append(ln)
            chapters[n] = Chapter(n, tidy(" ".join(title_parts)) or f"Chapter {n}")
            current = n
        if not current:
            continue
        for ln in lines:
            if (m := SECTION_RE.match(ln)) and int(m[1]) == current and len(ln) < 70:
                section = f"{m[1]}.{m[2]} {tidy(m[3])}"
                if not ln.endswith(".") and section not in chapters[current].sections:
                    chapters[current].sections.append(section)
    return [chapters[n] for n in sorted(chapters)]
