"""Work out what a PDF is (book, paper or thesis) and its details, whatever its filename.

identify() tries, in order:
  - a thesis title page ("A thesis submitted ... Doctor of Philosophy"): thesis_meta.py
  - a DOI on the first two pages (Crossref), an arXiv number (arXiv), or for something that
    looks like a paper, its first page searched on Crossref and OpenAlex
  - for a book: an ISBN (Open Library), the PDF's own details, the filename (download-site
    names understood), the copyright year, and an Open Library title search
fill_gaps() then fills whatever is still missing from the PDF itself (title on its first pages,
year printed there or the PDF's date, "Unknown" author), so nothing has to be typed in.
Only metadata is read; no book text is stored anywhere.
"""

import html
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

FRONT_PAGES = 12  # the title and copyright pages are near the front
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
# Between digit groups: a hyphen or a space; some text layers put each piece on its own line
# ("0\n-\n943396\n-\n75\n-\n1")
_ISBN_SEP = r"(?:\s*-\s*|\s)?"
ISBN_RE = re.compile(
    rf"(?:ISBN(?:-1[03])?[:\s]*|isbn13\s*)?\b((?:97[89]{_ISBN_SEP})?(?:\d{_ISBN_SEP}){{9}}[\dXx])\b"
)
# A DOI: "10." + registrant + "/" + suffix (e.g. 10.1364/OE.27.012345)
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.IGNORECASE)
# Crossref types that are papers (everything else, e.g. "book" or "monograph", is a book)
# ("dissertation" is a thesis)
PAPER_TYPES = {"journal-article", "proceedings-article", "posted-content", "report",
               "peer-review", "article", "preprint"}  # fmt: skip
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
    # placeholders some programs write (ReportLab: "anonymous")
    r"^(untitled|title|unknown|anonymous|author|user|admin|owner|document|microsoft word|book|"
    r"pdf|\W*)$|\.(pdf|docx?|indd|tex)\b|"
    r"\.dvi\b|^\d+$|^[a-z]:\\|adobe|acrobat|calibre|"
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
    kind: str = "book"  # or "paper" or "thesis"
    doi: str = ""
    journal: str = ""
    volume: str = ""
    issue: str = ""
    page_range: str = ""
    keywords: str = ""  # papers and theses: "laser; weed control; ..."
    degree: str = ""  # theses: "PhD", "Master", "Bachelor", "Diploma"
    institution: str = ""  # theses: the university
    supervisors: str = ""  # theses: "Prof. A; Dr. B"
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
    dates = [
        (work.get(k) or {}).get("date-parts", [[None]])[0][0]
        for k in ("issued", "published", "approved")  # "approved": when a thesis was accepted
    ]
    year = next((str(y) for y in dates if y), "")
    first = lambda key: (work.get(key) or [""])[0]  # noqa: E731
    meta.fill(
        source,
        title=clean_title(first("title")),
        author=join_names(names),
        year=year,
        publisher=work.get("publisher", ""),
        journal=first("container-title"),
        volume=str(work.get("volume", "")),
        issue=str(work.get("issue", "")),
        page_range=str(work.get("page", "")),
        doi=doi,
        url=f"https://doi.org/{doi}",
    )
    if work.get("type") == "dissertation":
        meta.kind, meta.journal, meta.publisher = "thesis", "", ""
        meta.fill(source, institution=(work.get("institution") or [{}])[0].get("name", ""))
    else:
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
    # The comment often says what it is: "PhD thesis", "Master thesis, EPFL"
    comment = entry.findtext("{http://arxiv.org/schemas/atom}comment", "")
    thesis = re.search(
        r"\b(?:ph\.?\s?d\.?|doctoral|master'?s?|bachelor'?s?|diploma|m\.?\s?sc\.?)\s+"
        r"(?:thesis|dissertation)\b|\bdissertation\b",
        comment,
        re.IGNORECASE,
    )
    published_doi = entry.findtext("{http://arxiv.org/schemas/atom}doi", "").strip()
    if published_doi and not thesis:  # a thesis's arXiv copy is the thesis itself
        journal = crossref(published_doi.lower())
        if journal.title:
            journal.kind = "paper"
            return journal
    meta = Meta(kind="thesis" if thesis else "paper")
    source = f"arXiv ({identifier})"
    if thesis:
        from thesis_meta import degree

        meta.fill(source, degree=degree(thesis[0]))
    names = [a.findtext(f"{atom}name", "").strip() for a in entry.findall(f"{atom}author")]
    meta.fill(
        source,
        title=entry.findtext(f"{atom}title", ""),
        author=join_names(names),
        year=entry.findtext(f"{atom}published", "")[:4],
        journal="" if thesis else "arXiv preprint",
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


def join_names(names: list[str]) -> str:
    """['Jane Doe', '', 'Wei Zhang'] -> 'Jane Doe; Wei Zhang' (the catalog's author format)."""
    return "; ".join(n for n in names if n)


def openalex_doi(work: dict) -> str:
    """An OpenAlex work's DOI, '10.1364/oe.27.001234' ('' if it has none)."""
    return (work.get("doi") or "").removeprefix("https://doi.org/").lower()


def openalex_names(work: dict) -> list[str]:
    """An OpenAlex work's authors, in order."""
    return [a.get("author", {}).get("display_name", "") for a in work.get("authorships") or []]


def openalex_match(queries: list[str], page_text: str, filter_: str = "") -> dict | None:
    """The first OpenAlex work found for one of `queries` whose whole title is on
    `page_text` (see _best_match); `filter_` narrows the search, e.g. "type:dissertation"."""
    base = "https://api.openalex.org/works?per-page=10" + (f"&filter={filter_}" if filter_ else "")
    for query in queries:
        url = f"{base}&search=" + urllib.parse.quote(query)
        works = (_get_json(url) or {}).get("results") or []
        candidates = [
            (w.get("title") or "", str(w.get("publication_year") or ""), w) for w in works
        ]
        if work := _best_match(page_text, candidates):
            return work
    return None


def openalex_search(first_page: str) -> Meta:
    """Crossref doesn't know it: OpenAlex (an open catalogue of scholarly works, including many
    old ones without any DOI), with the same check that the title is on the page."""
    # OpenAlex ranks by keywords: the title alone works, title + authors + journal doesn't.
    # So try the first lines of the page one by one (one of them is the title).
    lines = [" ".join(line.split()) for line in first_page.splitlines()]
    work = openalex_match([line for line in lines if len(_words(line)) >= 4][:4], first_page)
    if not work:
        return Meta()
    doi = openalex_doi(work)
    if doi and (found := crossref(doi)).title:  # Crossref's details are the more complete
        found.kind = "paper"
        return found
    biblio = work.get("biblio") or {}
    pages = "-".join(p for p in (biblio.get("first_page"), biblio.get("last_page")) if p)
    source = (work.get("primary_location") or {}).get("source") or {}
    meta = Meta(kind="paper")
    meta.fill(
        "OpenAlex",
        title=clean_title(work.get("title") or ""),
        author=join_names(openalex_names(work)),
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


class Unavailable(OSError):
    """The service couldn't answer (offline, daily limit used up, server error)."""


def _get_json(
    url: str,
    timeout: float = 10,
    attempts: int = 3,
    headers: dict | None = None,
    strict: bool = False,
) -> dict | None:
    """None when offline or the service keeps failing, so callers fall back to local sources.
    strict: None only when the service says it has no such record (404); raises Unavailable
    when it couldn't answer, so the caller can try again later."""
    headers = {"User-Agent": "myLibrary book organizer"} | (headers or {})
    request = urllib.request.Request(url, headers=headers)
    reason = ""
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            reason = f"HTTP {e.code}"
            if e.code == 429 and int(e.headers.get("Retry-After") or 0) > 60:
                break  # a daily limit: waiting a few seconds won't help
        except (OSError, ValueError) as e:
            reason = str(e)
        time.sleep(attempt + 1)  # Open Library sometimes rate-limits quick bursts
    if strict:
        raise Unavailable(f"{urllib.parse.urlsplit(url).netloc}: {reason}")
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


# A name this tool gave a file before ("<author>-<year>-<title-words>"): it says nothing new,
# and if the first guess was wrong it would only repeat it
OUR_NAME_RE = re.compile(r"^[a-z]+-\d{4}-[a-z0-9-]+$")


def identify(path: Path, online: bool = True, paper: bool = False, thesis: bool = False) -> Meta:
    """Title, authors, year and the rest. With `paper` (a file in papers/) it's a paper, with
    `thesis` (a file in theses/) a thesis, even if nothing online knows it. Never leaves the
    title, author or year empty (see fill_gaps), so nothing has to be typed in."""
    pdf: dict = {}  # what _identify read from the PDF, for fill_gaps
    meta = _identify(path, online, paper, thesis, pdf)
    fill_gaps(meta, path, pdf)
    return meta


def _identify(path: Path, online: bool, paper: bool, thesis: bool, pdf: dict) -> Meta:
    filename = Meta() if OUR_NAME_RE.match(path.stem) else parse_filename(path.stem)
    isbns = find_isbns(path.stem)
    front_text = first_pages = pages = ""
    info: dict = {}
    texts: list[str] = []  # the text of each of the first pages
    sized_of = lambda index: []  # noqa: E731  (a page's lines with font sizes, for theses)
    if path.suffix.lower() == ".pdf":
        try:
            reader = PdfReader(path)
            pages = str(len(reader.pages))
            info = reader.metadata or {}
            texts = [p.extract_text() or "" for p in reader.pages[:FRONT_PAGES]]
            front_text = "\n".join(texts)
            sized_of = lambda index: thesis_meta.page_lines(reader.pages[index])  # noqa: E731
            # A paper's own DOI is in its metadata or on its first page; later pages hold the
            # references, full of other papers' DOIs
            page_text = "\n".join(texts[:2])
            if online and not page_text.strip() and reader.pages:
                # A scan (old papers often are): read the first page with OCR (~2 s), so its
                # title, authors and any DOI can be looked up. Decided on the pages' own text:
                # a scan can still carry details such as a Subject in its metadata
                from book_ocr import ocr_pages

                page_text = ocr_pages(path, [0]).get(0, "")
                texts = [page_text]
                sized_of = lambda index: []  # noqa: E731  (an OCR'd page has no font sizes)
            first_pages = "\n".join(
                [str(info.get(k) or "") for k in ("/doi", "/DOI", "/Subject", "/Keywords")]
                + [page_text]
            )
        except Exception as e:  # damaged/encrypted PDFs: fall back to the filename
            print(f"  ! couldn't read the PDF ({e})")
        isbns += [i for i in find_isbns(front_text) if i not in isbns]
    pdf.update(info=info, texts=texts, sized_of=sized_of)

    # A thesis says so on its title page ("A thesis submitted ... Doctor of Philosophy")
    if thesis or (not paper and thesis_meta.find_title_page(texts)):
        meta = thesis_meta.identify_thesis(
            path.stem, texts, sized_of, online, find_arxiv(path.stem, first_pages)
        )
        return _finish_thesis(meta, filename, info, pages, isbns, "\n".join(texts[:8]), online)

    # A paper, found online in this order: its DOI (Crossref has everything, journal
    # included), its arXiv number, or its title and authors searched on Crossref
    if online:
        found = Meta()

        def is_article(m: Meta) -> bool:  # a paper or a thesis that was found
            return m.kind in ("paper", "thesis") and bool(m.title)

        for doi in find_dois(path.stem + " " + first_pages)[:2]:
            found = crossref(doi)
            if is_article(found):
                break
        else:
            if identifier := find_arxiv(path.stem, first_pages):
                found = arxiv(identifier)
            elif paper or looks_like_paper(first_pages, pages):
                found = crossref_search(first_pages)
                if not found.title:
                    found = openalex_search(first_pages)
        if found.kind == "thesis" and found.title and not paper:  # e.g. "PhD thesis" on arXiv
            return _finish_thesis(found, filename, info, pages, isbns, front_text, online)
        if is_article(found):
            found.kind = "paper"
            found.fill("PDF", pages=pages)
            found.keywords = paper_keywords(info, first_pages, found.doi, online)
            return found

    meta = open_library(isbns) if online and isbns else Meta()
    _fill_from_pdf(meta, info, pages, isbns, "PDF / filename (not verified online)")
    # A filename like "ccc.10297" is no title: then the large text on the first pages is
    # tried first (fill_gaps), and the filename only after that
    if looks_like_title(filename.title):
        meta.fill(filename.sources.get("title", "filename"), title=filename.title)
    for key in ("author", "year", "publisher"):
        meta.fill(filename.sources.get(key, "filename"), **{key: getattr(filename, key)})
    if years := COPYRIGHT_RE.findall(front_text):
        meta.fill("copyright page", year=max(years))
    if paper:  # nothing online knows it: the PDF's own details (fill_gaps does the rest)
        meta.kind = "paper"
        meta.keywords = paper_keywords(info, first_pages, online=False)
        return meta
    if online and meta.title and not meta.complete:
        found = open_library_search(meta.title, meta.author)
        for key in ("author", "year", "publisher"):
            meta.fill(found.sources.get(key, ""), **{key: getattr(found, key)})
    return meta


def _finish_thesis(
    meta: Meta, filename: Meta, info: dict, pages: str, isbns: list[str], front: str, online: bool
) -> Meta:
    """What the thesis lookup left open: pages, ISBN (Dutch theses have one), keywords, and
    the PDF's details or the filename for anything still missing."""
    _fill_from_pdf(meta, info, pages, isbns, "PDF")
    for key in ("title", "author", "year"):
        meta.fill(filename.sources.get(key, "filename"), **{key: getattr(filename, key)})
    meta.keywords = paper_keywords(info, front, meta.doi, online)
    return meta


def _fill_from_pdf(meta: Meta, info: dict, pages: str, isbns: list[str], isbn_source: str) -> None:
    """Pages, the first ISBN found, and the PDF's own Title and Author when they look right."""
    meta.fill("PDF", pages=pages)
    if isbns:
        meta.fill(isbn_source, isbn=isbn13(isbns[0]))
    title, author = str(info.get("/Title") or ""), str(info.get("/Author") or "")
    if looks_like_title(title):
        meta.fill("PDF metadata", title=title)
    if looks_like_name(author):
        meta.fill("PDF metadata", author=author)


def page_title(texts: list[str], sized_of, author: str = "") -> str:
    """The title printed on the first pages: their largest text that isn't a label, a date or
    the author (e.g. "Modern Railway Track" on a cover page)."""
    for index, text in enumerate(texts[:3]):
        if len(text.strip()) < 10:  # a cover image, a blank page
            continue
        title = thesis_meta.title_on_page(text, sized_of(index), author)
        if looks_like_title(title) and len(title) <= 200:
            return title
    return ""


def fill_gaps(meta: Meta, path: Path, pdf: dict) -> None:
    """Whatever is still missing after every lookup, from the PDF itself, so a book is never
    left waiting for someone to type its details: the title on its first pages or its
    filename; a year printed on its first page, else when the PDF was made; the author in the
    PDF's details, else "Unknown"."""
    texts, info = pdf.get("texts") or [], pdf.get("info") or {}
    if not meta.title:
        meta.fill("first pages", title=page_title(texts, pdf.get("sized_of"), meta.author))
    if not meta.title:
        name = "" if OUR_NAME_RE.match(path.stem) else clean_filename(path.stem)
        meta.fill("filename", title=name or path.stem.replace("-", " "))
    if not meta.year:
        this_year = time.localtime().tm_year
        years = [y for y in re.findall(r"(1[5-9]\d{2}|20\d{2})", texts[0] if texts else "")
                 if int(y) <= this_year]  # fmt: skip
        meta.fill("first page", year=max(years) if years else "")
    if not meta.year:
        if m := re.search(r"(1[89]\d{2}|20\d{2})", str(info.get("/CreationDate") or "")):
            meta.fill("when the PDF was made", year=m[1])
    if not meta.year:
        meta.fill("file date", year=str(time.localtime(path.stat().st_mtime).tm_year))
    if not meta.author:
        pdf_author = str(info.get("/Author") or "")
        meta.fill("PDF metadata", author=pdf_author if looks_like_name(pdf_author) else "")
    if not meta.author:
        meta.fill("nothing found", author="Unknown")


import thesis_meta  # noqa: E402  (uses this module's helpers)
