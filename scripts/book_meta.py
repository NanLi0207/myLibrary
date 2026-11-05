"""Work out a book's title, author and year, whatever its filename looks like.

Sources, most trusted first:
  1. An ISBN found in the filename or on the first pages, looked up on Open Library
  2. The PDF's own metadata (Title / Author), when it looks sensible
  3. The filename, after stripping download-site tags, hashes and ISBNs
The year also falls back to the copyright line ("(c) 2008 ...") on the first pages.
Only metadata is read; no book text is stored anywhere.
"""

import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

FRONT_PAGES = 12  # the title and copyright pages are near the front
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
ISBN_RE = re.compile(
    r"(?:ISBN(?:-1[03])?[:\s]*|isbn13\s*)?\b((?:97[89][-\s]?)?(?:\d[-\s]?){9}[\dXx])\b"
)
COPYRIGHT_RE = re.compile(r"(?:©|\(c\)|copyright)[^\n]{0,60}?\b((?:19|20)\d{2})\b", re.IGNORECASE)

# Things download sites add to filenames
NOISE_RES = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\((?:[^()]*\b(?:z-library|1lib|z-lib|libgen|annas?-archive)\b[^()]*)\)",
        r"\{[^}]*\}",  # libgen ids
        r"\b[0-9a-f]{32}\b",  # md5 hashes
        r"\bAnna[’']?s Archive\b",
        r"\blibgen(?:\.\w+)?\b",
        r"\bz-library\.\w+\b",
        r"\bisbn(?:13|10)?\s*[\d-]{10,17}\b",
    )
]
BAD_METADATA = re.compile(
    r"^(untitled|title|unknown|document|microsoft word|book|pdf|\W*)$|\.(pdf|docx?|indd|tex)\b|"
    r"^\d+$|^[a-z]:\\|adobe|acrobat|calibre|"
    # web addresses, e-mails and the software that made the PDF (e.g. "https://imagemagick.org")
    r"://|www\.|@|\.(com|org|net|edu|io)\b|imagemagick|ghostscript|abbyy|scansnap|"
    r"pdftk|distiller|pdfcreator|libreoffice|openoffice|latex|\btex\b|mathematica|matlab",
    re.IGNORECASE,
)


def ascii_words(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+", text.lower())


def surname(author: str) -> str:
    """First author's surname: 'Robert R. Shannon', 'Shannon, Robert', 'Smith W.J.', 'A; B'."""
    first = re.split(r";|&| and |\betc\b", author)[0].split(",")[0]
    tokens = re.findall(r"[^\W\d_][\w'’-]*\.?", first)
    # Drop initials such as "R." or "W.J." so they aren't mistaken for the surname
    names = [t for t in tokens if not (t.endswith(".") and len(t) <= 3) and len(t) > 1]
    words = ascii_words(names[-1] if names else first)
    return words[-1] if words else "unknown"


def looks_like_name(text: str) -> bool:
    """'Robert R. Shannon' yes; 'https://imagemagick.org', 'admin', '12345' no."""
    words = re.findall(r"[^\W\d_]{2,}", text)
    return bool(words) and not BAD_METADATA.search(text) and not re.search(r"\d{3,}", text)


@dataclass
class Meta:
    title: str = ""
    author: str = ""
    year: str = ""
    publisher: str = ""
    isbn: str = ""
    pages: str = ""
    subjects: str = ""
    url: str = ""
    sources: dict[str, str] = field(default_factory=dict)  # field -> where it came from

    def fill(self, source: str, **values: str) -> None:
        """Set fields that are still empty."""
        for key, value in values.items():
            value = " ".join((value or "").split()).strip(" ,;-")  # keep "." for initials
            if value and not getattr(self, key):
                setattr(self, key, value)
                self.sources[key] = source

    @property
    def complete(self) -> bool:
        return bool(self.title and self.author and self.year)


def valid_isbn(isbn: str) -> bool:
    digits = [10 if c in "Xx" else int(c) for c in isbn]
    if len(digits) == 10:
        return sum((10 - i) * d for i, d in enumerate(digits)) % 11 == 0
    if len(digits) == 13 and 10 not in digits:
        return sum(d * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits)) % 10 == 0
    return False


def isbn13(isbn: str) -> str:
    """ISBN-10 -> ISBN-13, so the catalog uses one format."""
    if len(isbn) != 10:
        return isbn
    core = "978" + isbn[:9]
    check = (10 - sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(core)) % 10) % 10
    return core + str(check)


def find_isbns(text: str) -> list[str]:
    found = []
    for m in ISBN_RE.finditer(text):
        isbn = re.sub(r"[-\s]", "", m[1])
        if valid_isbn(isbn) and isbn not in found:
            found.append(isbn)
    return found


def clean_filename(stem: str) -> str:
    for noise in NOISE_RES:
        stem = noise.sub(" ", stem)
    return " ".join(stem.replace("_", " ").split()).strip(" -")


def parse_filename(stem: str) -> Meta:
    """Best-effort guess from the common download-site naming patterns."""
    meta = Meta()
    year = (YEAR_RE.findall(stem) or [""])[-1]
    if m := re.match(r"^(?P<t>[^{]+)\{(?P<a>[^}]*)\}\((?P<y>\d{4})(?:,\s*(?P<p>[^)]*))?\)", stem):
        meta.fill("filename", title=m["t"], author=m["a"], year=m["y"], publisher=m["p"] or "")
        return meta
    if " -- " in stem:  # "Title -- Author -- edition, year -- Publisher -- isbn -- hash"
        parts = [p.strip() for p in stem.split(" -- ")]
        meta.fill("filename", title=parts[0], author=parts[1], year=year)
        if len(parts) > 3 and not re.search(r"\d|isbn|archive", parts[3], re.IGNORECASE):
            meta.fill("filename", publisher=parts[3])
        return meta
    stem = clean_filename(stem)
    if " - " in stem:  # "Author - Title (2nd ed) - 1999"
        parts = [p.strip() for p in stem.split(" - ")]
        title = YEAR_RE.sub("", re.sub(r"\(.*?\)", "", parts[1]))
        meta.fill("filename", title=title, author=parts[0], year=year)
    elif m := re.match(r"^(?P<t>.+)\((?P<a>[^()]*[A-Za-z][^()]*)\)$", stem):  # "Title (Author)"
        meta.fill("filename", title=m["t"], author=m["a"], year=year)
    else:
        meta.fill("filename", title=YEAR_RE.sub("", stem), year=year)
    return meta


def _get_json(url: str, timeout: float = 10, attempts: int = 3) -> dict | None:
    """None when offline or the service keeps failing, so callers fall back to local sources."""
    request = urllib.request.Request(url, headers={"User-Agent": "myLibrary book organizer"})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except OSError, ValueError:
            time.sleep(attempt + 1)  # Open Library sometimes rate-limits quick bursts
    return None


def looks_like_title(text: str) -> bool:
    """Reject metadata like 'I127-00-1-10' or 'Microsoft Word - ch1.doc'."""
    real_words = re.findall(r"[A-Za-z]{3,}", text)
    return len(real_words) >= 2 and not BAD_METADATA.search(text)


def open_library(isbns: list[str]) -> Meta:
    """Look up the first ISBN that Open Library knows."""
    for isbn in isbns:
        response = _get_json(
            "https://openlibrary.org/api/books?format=json&jscmd=data&bibkeys=ISBN:"
            + urllib.parse.quote(isbn)
        )
        if data := (response or {}).get(f"ISBN:{isbn}"):
            meta = Meta()
            meta.fill(
                f"Open Library (ISBN {isbn})",
                title=data.get("title", ""),
                author="; ".join(a["name"] for a in data.get("authors", [])),
                year=(YEAR_RE.findall(data.get("publish_date", "")) or [""])[-1],
                publisher=", ".join(p["name"] for p in data.get("publishers", [])),
                isbn=isbn13(isbn),
                subjects="; ".join(s["name"] for s in data.get("subjects", [])[:8]),
                url=data.get("url", ""),
            )
            return meta
    return Meta()


def open_library_search(title: str, author: str) -> Meta:
    """Title/author search, for books without a readable ISBN. Gives the first-edition year."""
    title = re.split(r"[:(]", title)[0]
    last = surname(author) if author else ""  # "Joseph M.Geary" or "Geary, Joseph" -> "geary"
    if last == "unknown":
        last = ""
    attempts = [(title, last), (" ".join(title.split()[:4]), last), (title, "")]
    docs = []
    for t, a in dict.fromkeys(attempts):  # most specific query first, skipping duplicates
        query = {"title": t, "limit": "1", "fields": "author_name,first_publish_year,publisher"}
        if a:
            query["author"] = a
        response = _get_json("https://openlibrary.org/search.json?" + urllib.parse.urlencode(query))
        if docs := (response or {}).get("docs") or []:
            break
    meta = Meta()
    if docs:
        doc = docs[0]
        meta.fill(
            "Open Library search (check the edition)",
            author="; ".join(doc.get("author_name", [])),
            year=str(doc.get("first_publish_year", "")),
            publisher=(doc.get("publisher") or [""])[0],
        )
    return meta


def identify(path: Path, online: bool = True) -> Meta:
    filename = parse_filename(path.stem)
    isbns = find_isbns(path.stem)
    pdf_title = pdf_author = front_text = pages = ""
    if path.suffix.lower() == ".pdf":
        try:
            reader = PdfReader(path)
            pages = str(len(reader.pages))
            info = reader.metadata or {}
            pdf_title, pdf_author = info.get("/Title") or "", info.get("/Author") or ""
            front_text = "\n".join(p.extract_text() or "" for p in reader.pages[:FRONT_PAGES])
        except Exception as e:  # damaged/encrypted PDFs: fall back to the filename
            print(f"  ! couldn't read the PDF ({e})")
        isbns += [i for i in find_isbns(front_text) if i not in isbns]

    meta = open_library(isbns) if online and isbns else Meta()
    meta.fill("PDF", pages=pages)
    if isbns:
        meta.fill("PDF / filename (not verified online)", isbn=isbn13(isbns[0]))
    if looks_like_title(str(pdf_title)):
        meta.fill("PDF metadata", title=str(pdf_title))
    if looks_like_name(str(pdf_author)):
        meta.fill("PDF metadata", author=str(pdf_author))
    for key in ("title", "author", "year", "publisher"):
        meta.fill(filename.sources.get(key, "filename"), **{key: getattr(filename, key)})
    if years := COPYRIGHT_RE.findall(front_text):
        meta.fill("copyright page", year=max(years))
    if online and meta.title and not meta.complete:
        found = open_library_search(meta.title, meta.author)
        for key in ("author", "year", "publisher"):
            meta.fill(found.sources.get(key, ""), **{key: getattr(found, key)})
    return meta
