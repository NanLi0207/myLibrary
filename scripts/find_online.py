"""Find books, papers and theses online: the "🔎 Find online" box on the library page.

Type anything: a DOI, an arXiv number, an ISBN, a title, an author, a topic. What it searches:
  - a DOI: Crossref, else DataCite (via doi.org); OpenAlex adds the free PDF, if there is one
  - an arXiv number: arXiv;  an ISBN: Open Library
  - anything else: OpenAlex (250 million works: papers, books, theses), plus, when it looks like
    a person's name, the works of the best-matching author, and Open Library for books
Each result says whether it's already in your library, and where it can be read for free
(open access). Links to other search engines (Google Scholar, 百度学术 Baidu Scholar, ...)
search the same words there. Uses only public catalogues and legal open-access copies.
"""

import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import book_meta
import catalog
import paths
import thesis_meta
from book_meta import _words, find_dois, find_isbns
from book_toc import STOP_WORDS

CATALOG = paths.LIBRARY / "catalog.csv"
PER_PAGE = 12

# Other places to search the same words: (label, URL with {q})
ENGINES = [
    ("Google Scholar", "https://scholar.google.com/scholar?q={q}"),
    ("Semantic Scholar", "https://www.semanticscholar.org/search?q={q}"),
    ("百度学术 Baidu Scholar", "https://xueshu.baidu.com/s?wd={q}"),
    ("知网 CNKI", "https://kns.cnki.net/kns8s/defaultresult/index?kw={q}"),
    ("arXiv", "https://arxiv.org/search/?searchtype=all&query={q}"),
    ("Google Books", "https://www.google.com/search?tbm=bks&q={q}"),
    ("Open Library", "https://openlibrary.org/search?q={q}"),
    ("WorldCat", "https://search.worldcat.org/search?q={q}"),
]
# OpenAlex's types -> the library's kinds
KINDS = {"dissertation": "thesis", "book": "book", "monograph": "book", "book-chapter": "chapter",
         "edited-book": "book", "reference-book": "book"}  # fmt: skip


def engines(query: str) -> list[dict]:
    q = urllib.parse.quote(query)
    return [{"label": label, "url": url.format(q=q)} for label, url in ENGINES]


def _from_openalex(work: dict) -> dict:
    doi = book_meta.openalex_doi(work)
    source = (work.get("primary_location") or {}).get("source") or {}
    best = work.get("best_oa_location") or {}
    kind = KINDS.get(work.get("type") or "", "paper")
    venue = source.get("display_name") or ""
    if kind == "thesis":  # its university rather than the repository's name
        venue = thesis_meta._source_institution(work) or venue
    return {
        "title": book_meta.clean_title(work.get("title") or work.get("display_name") or ""),
        "authors": book_meta.join_names(book_meta.openalex_names(work)),
        "year": str(work.get("publication_year") or ""),
        "kind": kind,
        "venue": venue,
        "doi": doi,
        "url": f"https://doi.org/{doi}" if doi else (best.get("landing_page_url") or ""),
        "pdf": best.get("pdf_url") or "",
        "free": (work.get("open_access") or {}).get("oa_url") or "",
        "cited": work.get("cited_by_count"),
        "source": "OpenAlex",
    }


def _from_meta(meta: book_meta.Meta, source: str) -> dict:
    return {
        "title": meta.title,
        "authors": meta.author,
        "year": meta.year,
        "kind": meta.kind if meta.kind in ("paper", "thesis") else "book",
        "venue": meta.journal or meta.institution or meta.publisher,
        "doi": meta.doi,
        "url": meta.url or (f"https://doi.org/{meta.doi}" if meta.doi else ""),
        "pdf": "",
        "free": "",
        "cited": None,
        "isbn": meta.isbn,
        "source": source,
    }


def _openalex(url: str) -> list[dict]:
    data = book_meta._get_json(url) or {}
    return [_from_openalex(w) for w in data.get("results") or [] if w.get("title")]


def search_works(query: str) -> list[dict]:
    """OpenAlex's full search: titles, abstracts and full texts, best matches first."""
    return _openalex(
        f"https://api.openalex.org/works?per-page={PER_PAGE}&search=" + urllib.parse.quote(query)
    )


def looks_like_person(query: str) -> bool:
    """'Robert Shannon', 'R. R. Shannon', 'Shannon, Robert'; not a DOI, a year or a long title."""
    words = re.findall(r"[^\W\d_]+", query)
    return (
        2 <= len(words) <= 4
        and not re.search(r"\d", query)
        and not any(w.lower() in STOP_WORDS for w in words)  # "lens of the eye"
    )


def search_author(query: str) -> tuple[str, list[dict]]:
    """The author whose name matches every word typed, and their most cited works."""
    data = book_meta._get_json(
        "https://api.openalex.org/authors?per-page=5&search=" + urllib.parse.quote(query)
    )
    typed = [w for w in _words(query) if len(w) > 1]  # initials can be anything
    for author in (data or {}).get("results") or []:
        name = author.get("display_name") or ""
        if typed and all(w in _words(name) for w in typed):
            author_id = (author.get("id") or "").rsplit("/", 1)[-1]
            institution = ((author.get("last_known_institutions") or [{}])[0] or {}).get(
                "display_name", ""
            )
            works = _openalex(
                f"https://api.openalex.org/works?per-page={PER_PAGE}"
                f"&filter=author.id:{author_id}&sort=cited_by_count:desc"
            )
            label = name + (f" ({institution})" if institution else "")
            return label, works
    return "", []


def search_books(query: str) -> list[dict]:
    """Open Library: books by title and author, with the year of the first edition."""
    data = book_meta._get_json(
        "https://openlibrary.org/search.json?limit=6&fields=title,author_name,first_publish_year,"
        "publisher,isbn,key&q=" + urllib.parse.quote(query)
    )
    results = []
    for doc in (data or {}).get("docs") or []:
        isbns = doc.get("isbn") or []
        results.append(
            {
                "title": doc.get("title", ""),
                "authors": book_meta.join_names(doc.get("author_name") or []),
                "year": str(doc.get("first_publish_year") or ""),
                "kind": "book",
                "venue": (doc.get("publisher") or [""])[0],
                "doi": "",
                "url": f"https://openlibrary.org{doc['key']}" if doc.get("key") else "",
                "pdf": "",
                "free": "",
                "cited": None,
                "isbn": next((i for i in isbns if len(i) == 13), isbns[0] if isbns else ""),
                "source": "Open Library",
            }
        )
    return results


def by_identifier(query: str) -> list[dict]:
    """A DOI, arXiv number or ISBN typed in: that one work ([] if the query is none of these)."""
    if dois := find_dois(query):
        doi = dois[0]
        found = thesis_meta.doi_lookup(doi)
        work = book_meta._get_json(
            "https://api.openalex.org/works/doi:" + urllib.parse.quote(doi, safe="/")
        )
        if work and work.get("title"):  # OpenAlex knows where it's free to read
            result = _from_openalex(work)
            if found.title:
                result |= {k: v for k, v in _from_meta(found, "Crossref").items()
                           if v and k not in ("pdf", "free", "cited", "source")}  # fmt: skip
            return [result]
        return [_from_meta(found, "Crossref / DataCite")] if found.title else []
    if identifier := book_meta.find_arxiv(query, query):
        found = book_meta.arxiv(identifier)
        if not found.title:
            return []
        result = _from_meta(found, "arXiv")
        result["pdf"] = f"https://arxiv.org/pdf/{identifier}"
        result["free"] = f"https://arxiv.org/abs/{identifier}"
        return [result]
    if isbns := find_isbns(re.sub(r"(?<=\d)[-\s](?=\d)", "", query)):
        found = book_meta.open_library(isbns)
        return [_from_meta(found, "Open Library")] if found.title else []
    return []


def _mark_owned(results: list[dict]) -> None:
    """'in_library': the id of the same work in the catalog (same DOI or ISBN, or same title
    and year)."""
    rows = catalog.load(CATALOG).values()
    by_doi = {r["doi"].lower(): r["id"] for r in rows if r.get("doi")}
    by_isbn = {r["isbn"]: r["id"] for r in rows if r.get("isbn")}
    by_title = {(" ".join(_words(r["title"])), r.get("year", "")): r["id"] for r in rows}
    for result in results:
        result["in_library"] = (
            by_doi.get(result.get("doi", ""))
            or by_isbn.get(result.get("isbn", ""))
            or by_title.get((" ".join(_words(result["title"])), result["year"]))
            or ""
        )


def find(query: str) -> dict:
    """{query, sections: [{title, results}], engines} for the page."""
    query = " ".join(query.split())[:300]
    if not query:
        return {"query": "", "sections": [], "engines": []}
    sections = []
    if exact := by_identifier(query):
        sections.append({"title": "Found by its identifier", "results": exact})
    else:
        with ThreadPoolExecutor(3) as pool:  # three catalogues at once
            works = pool.submit(search_works, query)
            author = pool.submit(search_author, query) if looks_like_person(query) else None
            books = pool.submit(search_books, query)
            if author and (found := author.result())[1]:
                sections.append({"title": f"Works by {found[0]}", "results": found[1]})
            sections.append({"title": "Papers, books and theses", "results": works.result()})
            sections.append({"title": "Books (Open Library)", "results": books.result()})
    sections = [s for s in sections if s["results"]]
    for section in sections:
        _mark_owned(section["results"])
    return {"query": query, "sections": sections, "engines": engines(query)}
