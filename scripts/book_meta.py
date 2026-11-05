"""Work out a book's title, author and year, whatever its filename looks like.

Sources, most trusted first:
  1. An ISBN found in the filename or on the first pages, looked up on Open Library
  2. The PDF's own metadata (Title / Author), when it looks sensible
  3. The filename, after stripping download-site tags, hashes and ISBNs
The year also falls back to the copyright line ("(c) 2008 ...") on the first pages.
Only metadata is read; no book text is stored anywhere.
"""

import html
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

FRONT_PAGES = 12  # the title and copyright pages are near the front
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
ISBN_RE = re.compile(
    r"(?:ISBN(?:-1[03])?[:\s]*|isbn13\s*)?\b((?:97[89][-\s]?)?(?:\d[-\s]?){9}[\dXx])\b"
)
# A DOI: "10." + registrant + "/" + suffix (e.g. 10.1364/OE.27.012345)
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.IGNORECASE)
# Crossref types that are papers (everything else, e.g. "book" or "monograph", is a book)
PAPER_TYPES = {"journal-article", "proceedings-article", "posted-content", "report",
               "dissertation", "peer-review", "article", "preprint"}  # fmt: skip
# An arXiv identifier: "arXiv:2101.01234v2" in the text, or a file named "2101.01234v2.pdf"
ARXIV_RE = re.compile(r"arxiv[:\s]*(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)
ARXIV_NAME_RE = re.compile(r"^(\d{4}\.\d{4,5})(?:v\d+)?$")
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
    kind: str = "book"  # or "paper"
    doi: str = ""
    journal: str = ""
    volume: str = ""
    issue: str = ""
    page_range: str = ""
    keywords: str = ""  # papers: "laser; weed control; ..."
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


def find_dois(text: str) -> list[str]:
    """DOIs in the text, in order (trailing punctuation from the sentence removed)."""
    found = []
    for m in DOI_RE.finditer(text):
        doi = m[1].rstrip(".,;:)]}'\"").lower()
        if doi not in found:
            found.append(doi)
    return found


def clean_title(title: str) -> str:
    """'XV.\n  <i>On the theory of optical images</i>' -> 'On the theory of optical images'.
    Also escaped markup, as some publishers send it: '&lt;title&gt;Specifying…&lt;/title&gt;'."""
    title = html.unescape(title)
    title = " ".join(re.sub(r"<[^>]+>", " ", title).split())
    return re.sub(r"^[IVXLC]+\.\s+", "", title)  # old journals numbered their articles


def crossref(doi: str) -> Meta:
    """A DOI's details from Crossref (the DOI registry): title, all authors, year, journal..."""
    data = _get_json(f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='/')}")
    work = (data or {}).get("message") or {}
    meta = Meta()
    if not work:
        return meta
    source = f"Crossref (DOI {doi})"
    names = [
        " ".join(filter(None, (a.get("given"), a.get("family")))) or a.get("name", "")
        for a in work.get("author") or []
    ]
    dates = [work.get(k, {}).get("date-parts", [[None]])[0][0] for k in ("issued", "published")]
    year = next((str(y) for y in dates if y), "")
    first = lambda key: (work.get(key) or [""])[0]  # noqa: E731
    meta.fill(
        source,
        title=clean_title(first("title")),
        author="; ".join(n for n in names if n),
        year=year,
        publisher=work.get("publisher", ""),
        journal=first("container-title"),
        volume=str(work.get("volume", "")),
        issue=str(work.get("issue", "")),
        page_range=str(work.get("page", "")),
        doi=doi,
        url=f"https://doi.org/{doi}",
    )
    meta.kind = "paper" if work.get("type") in PAPER_TYPES else "book"
    return meta


def _get_xml(url: str, timeout: float = 15) -> ElementTree.Element | None:
    request = urllib.request.Request(url, headers={"User-Agent": "myLibrary book organizer"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return ElementTree.fromstring(response.read())
    except OSError, ElementTree.ParseError:
        return None


def find_arxiv(stem: str, text: str) -> str:
    """The arXiv identifier of a preprint, from its first page or its file name ("" if none)."""
    if m := ARXIV_RE.search(text) or ARXIV_NAME_RE.match(stem):
        return m[1]
    return ""


def arxiv(identifier: str) -> Meta:
    """A preprint's details from arXiv; the journal version (via its DOI) if it was published."""
    atom = "{http://www.w3.org/2005/Atom}"
    feed = _get_xml(f"https://export.arxiv.org/api/query?id_list={identifier}")
    entry = feed.find(f"{atom}entry") if feed is not None else None
    if entry is None or entry.find(f"{atom}title") is None:
        return Meta()
    published_doi = entry.findtext("{http://arxiv.org/schemas/atom}doi", "").strip()
    if published_doi:
        journal = crossref(published_doi.lower())
        if journal.title:
            journal.kind = "paper"
            return journal
    meta = Meta(kind="paper")
    source = f"arXiv ({identifier})"
    names = [a.findtext(f"{atom}name", "").strip() for a in entry.findall(f"{atom}author")]
    meta.fill(
        source,
        title=entry.findtext(f"{atom}title", ""),
        author="; ".join(n for n in names if n),
        year=entry.findtext(f"{atom}published", "")[:4],
        journal="arXiv preprint",
        doi=f"10.48550/arxiv.{identifier}",  # arXiv's own DOI for the preprint
        url=f"https://arxiv.org/abs/{identifier}",
    )
    return meta


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKD", text).lower())


def _best_match(first_page: str, candidates: list[tuple[str, str, object]]):
    """Of (title, year, payload) search results, the first whose whole title is on the page,
    preferring one whose year is printed there too (an original rather than a later reprint)."""
    page_words = set(_words(first_page))
    # Any year from 1500 on: old papers matter here (YEAR_RE only covers 1900-2099)
    page_years = set(re.findall(r"\b(1[5-9]\d{2}|20\d{2})\b", first_page))
    matching = []
    for title, year, payload in candidates:
        words = _words(clean_title(title))
        if len(words) >= 3 and sum(w in page_words for w in words) / len(words) >= 0.9:
            matching.append((year, payload))
    return next((x for y, x in matching if y in page_years), matching[0][1] if matching else None)


def crossref_search(first_page: str) -> Meta:
    """No DOI printed: search Crossref with the top of the first page (title and authors), and
    accept a result only if its whole title really appears on that page. Many old papers got
    their DOI afterwards, so Crossref often knows them even though the paper shows none."""
    query = " ".join(first_page.split())[:300]
    if len(_words(query)) < 4:
        return Meta()
    data = _get_json(
        "https://api.crossref.org/works?rows=10&select=DOI,title,issued&query.bibliographic="
        + urllib.parse.quote(query)
    )
    items = ((data or {}).get("message") or {}).get("items") or []
    candidates = [
        (
            (item.get("title") or [""])[0],
            str((item.get("issued", {}).get("date-parts") or [[None]])[0][0]),
            item["DOI"],
        )
        for item in items
    ]
    doi = _best_match(first_page, candidates)
    return crossref(doi.lower()) if doi else Meta()


def openalex_search(first_page: str) -> Meta:
    """Crossref doesn't know it: OpenAlex (an open catalogue of scholarly works, including many
    old ones without any DOI), with the same check that the title is on the page."""
    # OpenAlex ranks by keywords: the title alone works, title + authors + journal doesn't.
    # So try the first lines of the page one by one (one of them is the title).
    lines = [" ".join(line.split()) for line in first_page.splitlines()]
    queries = [line for line in lines if len(_words(line)) >= 4][:4]
    work = None
    for query in queries:
        url = "https://api.openalex.org/works?per-page=10&search=" + urllib.parse.quote(query)
        works = (_get_json(url) or {}).get("results") or []
        candidates = [
            (w.get("title") or "", str(w.get("publication_year") or ""), w) for w in works
        ]
        if work := _best_match(first_page, candidates):
            break
    if not work:
        return Meta()
    doi = (work.get("doi") or "").removeprefix("https://doi.org/").lower()
    if doi and (found := crossref(doi)).title:  # Crossref's details are the more complete
        found.kind = "paper"
        return found
    biblio = work.get("biblio") or {}
    pages = "-".join(p for p in (biblio.get("first_page"), biblio.get("last_page")) if p)
    source = (work.get("primary_location") or {}).get("source") or {}
    names = [a.get("author", {}).get("display_name", "") for a in work.get("authorships") or []]
    meta = Meta(kind="paper")
    meta.fill(
        "OpenAlex",
        title=clean_title(work.get("title") or ""),
        author="; ".join(n for n in names if n),
        year=str(work.get("publication_year") or ""),
        journal=source.get("display_name") or "",
        volume=str(biblio.get("volume") or ""),
        issue=str(biblio.get("issue") or ""),
        page_range=pages,
        doi=doi,
        url=f"https://doi.org/{doi}" if doi else work.get("id", ""),
    )
    return meta


def _keyword_list(text: str) -> list[str]:
    parts = re.split(r"[;·•]" if re.search(r"[;·•]", text) else r",", text)
    out = []
    for part in parts:
        word = " ".join(part.split()).strip(" .,:-–—")
        if (
            word
            and len(word) <= 60
            and len(word.split()) <= 6
            and word.lower() not in map(str.lower, out)
        ):
            out.append(word)
    return out[:10]


def keywords_from_page(text: str) -> list[str]:
    """The "Keywords:" line on a paper's first page (also "Key words", "Index Terms")."""
    m = re.search(r"(?:key\s*words?|index\s+terms)\s*[:—–-]\s*", text, re.IGNORECASE)
    if not m:
        return []
    rest = text[m.end() : m.end() + 400]
    # The list ends at a blank line, or where the next part of the page starts: a heading in
    # any case ("INTRODUCTION"), or a section number, Arabic or Roman ("1." / "I.")
    stop = re.search(
        r"\n\s*\n|\b(?:Abstract|Introduction|Received|Citation|Copyright)\b|©|\n\s*(?:1|I)\.?\s",
        rest,
        re.IGNORECASE,
    )
    return _keyword_list(rest[: stop.start()] if stop else rest)


def openalex_keywords(doi: str) -> list[str]:
    """Keywords OpenAlex assigns to a work, for papers that list none themselves."""
    data = _get_json(f"https://api.openalex.org/works/doi:{urllib.parse.quote(doi, safe='/')}")
    return [k.get("display_name", "") for k in (data or {}).get("keywords") or []][:6]


def paper_keywords(info: dict, first_pages: str, doi: str = "", online: bool = True) -> str:
    """A paper's keywords: from the PDF's details, else its first page, else OpenAlex."""
    words = _keyword_list(str(info.get("/Keywords") or "")) or keywords_from_page(first_pages)
    if not words and online and doi:
        words = openalex_keywords(doi)
    return "; ".join(words)


def looks_like_paper(first_pages: str, pages: str) -> bool:
    """An article rather than a book: short, with an abstract near the start."""
    return (
        bool(re.search(r"\babstract\b", first_pages, re.IGNORECASE)) and 0 < int(pages or 0) <= 80
    )


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


def identify(path: Path, online: bool = True, paper: bool = False) -> Meta:
    """Title, authors, year and the rest. With `paper` (a file in papers/), it's a paper even if
    nothing online knows it."""
    filename = parse_filename(path.stem)
    isbns = find_isbns(path.stem)
    pdf_title = pdf_author = front_text = first_pages = pages = ""
    info: dict = {}
    if path.suffix.lower() == ".pdf":
        try:
            reader = PdfReader(path)
            pages = str(len(reader.pages))
            info = reader.metadata or {}
            pdf_title, pdf_author = info.get("/Title") or "", info.get("/Author") or ""
            front_text = "\n".join(p.extract_text() or "" for p in reader.pages[:FRONT_PAGES])
            # A paper's own DOI is in its metadata or on its first page; later pages hold the
            # references, full of other papers' DOIs
            page_text = "\n".join(p.extract_text() or "" for p in reader.pages[:2])
            if online and not page_text.strip() and reader.pages:
                # A scan (old papers often are): read the first page with OCR (~2 s), so its
                # title, authors and any DOI can be looked up. Decided on the pages' own text:
                # a scan can still carry details such as a Subject in its metadata
                from book_ocr import ocr_pages

                page_text = ocr_pages(path, [0]).get(0, "")
            first_pages = "\n".join(
                [str(info.get(k) or "") for k in ("/doi", "/DOI", "/Subject", "/Keywords")]
                + [page_text]
            )
        except Exception as e:  # damaged/encrypted PDFs: fall back to the filename
            print(f"  ! couldn't read the PDF ({e})")
        isbns += [i for i in find_isbns(front_text) if i not in isbns]

    # A paper, found online in this order: its DOI (Crossref has everything, journal
    # included), its arXiv number, or its title and authors searched on Crossref
    if online:
        found = Meta()
        for doi in find_dois(path.stem + " " + first_pages)[:2]:
            found = crossref(doi)
            if found.kind == "paper" and found.title:
                break
        else:
            if identifier := find_arxiv(path.stem, first_pages):
                found = arxiv(identifier)
            elif paper or looks_like_paper(first_pages, pages):
                found = crossref_search(first_pages)
                if not found.title:
                    found = openalex_search(first_pages)
        if found.kind == "paper" and found.title:
            found.fill("PDF", pages=pages)
            found.keywords = paper_keywords(info, first_pages, found.doi, online)
            return found

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
    if paper:  # nothing online knows it: the PDF's own details, and the user fills the rest
        meta.kind = "paper"
        meta.keywords = paper_keywords(info, first_pages, online=False)
        return meta
    if online and meta.title and not meta.complete:
        found = open_library_search(meta.title, meta.author)
        for key in ("author", "year", "publisher"):
            meta.fill(found.sources.get(key, ""), **{key: getattr(found, key)})
    return meta
