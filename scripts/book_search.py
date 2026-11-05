"""Full-text search across all books, page by page ("在我的书中" / In my books, in the reader).

    uv run scripts/book_search.py vignetting          # where do my books explain it?

The page text of every PDF in catalog.csv is kept in the library's .cache/books.db (SQLite FTS5,
English stemming, so "vignetting" also finds "vignetted"). library_server.py updates it in
the background at start; a book is re-read only when its PDF changes.
"""

import argparse
import re
import sqlite3
import threading
from pathlib import Path

import catalog
import paths
import pypdfium2 as pdfium

LIBRARY = paths.LIBRARY
CATALOG = LIBRARY / "catalog.csv"
INDEX = LIBRARY / ".cache" / "books.db"

_build_lock = threading.Lock()
MARK_START, MARK_END = "\x02", "\x03"  # around the matched words in snippets


def _connect() -> sqlite3.Connection:
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(INDEX, timeout=30)
    con.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS pages USING fts5("
        "slug UNINDEXED, page UNINDEXED, text, tokenize='porter unicode61')"
    )
    con.execute("CREATE TABLE IF NOT EXISTS books (slug TEXT PRIMARY KEY, stamp TEXT)")
    return con


def page_texts(pdf: Path) -> list[str]:
    doc = pdfium.PdfDocument(pdf)
    try:
        return [
            re.sub(r"\s+", " ", doc[i].get_textpage().get_text_range()).strip()
            for i in range(len(doc))
        ]
    finally:
        doc.close()


def update(verbose: bool = False) -> int:
    """(Re)index books whose PDF is new or changed, drop removed ones; returns books indexed."""
    with _build_lock:
        con = _connect()
        try:
            rows = catalog.load(CATALOG)
            known = dict(con.execute("SELECT slug, stamp FROM books"))
            for slug in set(known) - set(rows):
                con.execute("DELETE FROM pages WHERE slug = ?", (slug,))
                con.execute("DELETE FROM books WHERE slug = ?", (slug,))
            done = 0
            for slug, row in rows.items():
                pdf = LIBRARY / row["file"]
                if not pdf.exists():
                    continue
                stat = pdf.stat()
                stamp = f"{stat.st_size}:{stat.st_mtime_ns}"
                if known.get(slug) == stamp:
                    continue
                if verbose:
                    print(f"  indexing {slug} ...")
                texts = page_texts(pdf)
                con.execute("DELETE FROM pages WHERE slug = ?", (slug,))
                con.executemany(
                    "INSERT INTO pages (slug, page, text) VALUES (?, ?, ?)",
                    [(slug, i + 1, t) for i, t in enumerate(texts) if t],
                )
                con.execute("INSERT OR REPLACE INTO books VALUES (?, ?)", (slug, stamp))
                con.commit()
                done += 1
            con.commit()
            return done
        finally:
            con.close()


def ready() -> bool:
    if not INDEX.exists():
        return False
    con = _connect()
    try:
        return con.execute("SELECT count(*) FROM books").fetchone()[0] > 0
    finally:
        con.close()


def search(term: str, current: str | None = None, limit: int = 8, per_book: int = 2) -> dict:
    """Pages that discuss `term` most, at most `per_book` per book; the book being read first."""
    words = re.findall(r"[A-Za-z0-9]+", term)
    if not words or not INDEX.exists():
        return {"term": term, "results": [], "indexing": not INDEX.exists()}
    query = '"' + " ".join(words) + '"'  # the exact phrase (each word stemmed)
    rows = catalog.load(CATALOG)
    titles = {slug: row["title"] for slug, row in rows.items()}
    con = _connect()
    try:
        hits = con.execute(
            "SELECT slug, page, snippet(pages, 2, ?, ?, '…', 18), bm25(pages) "
            "FROM pages WHERE pages MATCH ? ORDER BY bm25(pages) LIMIT 200",
            (MARK_START, MARK_END, query),
        ).fetchall()
        counts = dict(
            con.execute(
                "SELECT slug, count(*) FROM pages WHERE pages MATCH ? GROUP BY slug", (query,)
            )
        )
    finally:
        con.close()
    picked: list[dict] = []
    per: dict[str, int] = {}
    for slug, page, snippet, _ in sorted(hits, key=lambda h: h[0] != current):
        if per.get(slug, 0) >= per_book or slug not in titles:
            continue
        per[slug] = per.get(slug, 0) + 1
        picked.append(
            {
                "slug": slug,
                "title": titles[slug],
                "file": rows[slug]["file"],
                "page": page,
                "snippet": snippet,
            }
        )
        if len(picked) >= limit:
            break
    return {
        "term": " ".join(words),
        "results": picked,
        "books": len(counts),
        "pages": sum(counts.values()),
        "indexing": _build_lock.locked(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    paths.add_argument(parser)
    parser.add_argument("term", nargs="+")
    args = parser.parse_args()
    update(verbose=True)
    found = search(" ".join(args.term))
    print(f"'{found['term']}': {found['pages']} pages in {found['books']} books; best pages:")
    for r in found["results"]:
        snippet = r["snippet"].replace(MARK_START, "[").replace(MARK_END, "]")
        print(f"  {r['slug']}  p.{r['page']}: {snippet}")


if __name__ == "__main__":
    main()
