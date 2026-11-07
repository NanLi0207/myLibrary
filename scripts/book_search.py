"""Full-text search across all books, page by page ("在我的书中" / In my books, in the reader).

    uv run scripts/book_search.py vignetting          # where do my books explain it?
    uv run scripts/book_search.py --status            # which documents are (not) indexed

The page text of every PDF in catalog.csv is kept in the library's .cache/books.db (SQLite FTS5,
English stemming, so "vignetting" also finds "vignetted"). library_server.py updates it in
the background at start; a book is re-read only when its PDF changes. Documents are known by
their id (catalog.py); an index from before ids (keyed by name) is simply rebuilt.

Each document is indexed on its own: its text is read first, then its old pages are replaced in
one transaction, so a failure (a damaged PDF, an error in the PDF library) leaves its previous
pages exactly as they were and never stops the others. The `status` table says, per document,
whether it is indexed, failed, or stale (an older version of a changed PDF still in the index),
with the last error and the number of attempts; a failed document is tried again by the next
update. update() reports what happened, and a run with failures is never reported as complete.
"""

import argparse
import re
import sqlite3
import threading
import time
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
    columns = {r[1] for r in con.execute("PRAGMA table_info(books)")}
    if columns and "doc_id" not in columns:  # the old index, by name: it's a cache, start again
        con.execute("DROP TABLE IF EXISTS pages")
        con.execute("DROP TABLE IF EXISTS books")
        con.commit()
    con.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS pages USING fts5("
        "doc_id UNINDEXED, page UNINDEXED, text, tokenize='porter unicode61')"
    )
    # books: the stamp (size:mtime) of the PDF version whose pages are in the index
    con.execute("CREATE TABLE IF NOT EXISTS books (doc_id TEXT PRIMARY KEY, stamp TEXT)")
    # status: each document's last indexing attempt, failed ones included
    con.execute(
        "CREATE TABLE IF NOT EXISTS status (doc_id TEXT PRIMARY KEY, state TEXT, stamp TEXT, "
        "error TEXT, attempts INTEGER, last_attempt TEXT, last_success TEXT)"
    )
    con.commit()
    return con


def page_texts(pdf: Path) -> list[str]:
    """The text of every page. Every pdfium object is closed explicitly, in order (text page,
    page, document), rather than left for the garbage collector to finalize later."""
    doc = pdfium.PdfDocument(pdf)
    texts = []
    try:
        for i in range(len(doc)):
            page = doc[i]
            try:
                textpage = page.get_textpage()
                try:
                    texts.append(re.sub(r"\s+", " ", textpage.get_text_range()).strip())
                finally:
                    textpage.close()
            finally:
                page.close()
    finally:
        doc.close()
    return texts


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _record_failure(con: sqlite3.Connection, doc_id: str, stamp: str, error: str) -> str:
    """Note a failed attempt; returns "stale" (its older pages stay searchable) or "failed"."""
    has_pages = con.execute("SELECT 1 FROM books WHERE doc_id = ?", (doc_id,)).fetchone()
    state = "stale" if has_pages else "failed"
    with con:
        con.execute(
            "INSERT INTO status (doc_id, state, stamp, error, attempts, last_attempt, "
            "last_success) VALUES (?, ?, ?, ?, 1, ?, NULL) ON CONFLICT(doc_id) DO UPDATE SET "
            "state = excluded.state, stamp = excluded.stamp, error = excluded.error, "
            "attempts = status.attempts + 1, last_attempt = excluded.last_attempt",
            (doc_id, state, stamp, error[:2000], _now()),
        )
    return state


def update(verbose: bool = False, extract=page_texts) -> dict:
    """(Re)index documents whose PDF is new or changed (or failed last time); drop removed ones.

    Returns {"indexed": [ids], "failed": [{"id", "slug", "error", "state"}], "unchanged": n,
    "missing": [ids whose PDF isn't there], "removed": n, "complete": bool}; `complete` only if
    every document's current PDF is in the index. `extract` reads a PDF's page texts (tests)."""
    report = {"indexed": [], "failed": [], "unchanged": 0, "missing": [], "removed": 0,
              "complete": False}  # fmt: skip
    with _build_lock:
        con = _connect()
        try:
            rows = catalog.load(CATALOG)
            known = dict(con.execute("SELECT doc_id, stamp FROM books"))
            tracked = set(known) | {r[0] for r in con.execute("SELECT doc_id FROM status")}
            for doc_id in tracked - set(rows):  # documents no longer in the library
                with con:
                    con.execute("DELETE FROM pages WHERE doc_id = ?", (doc_id,))
                    con.execute("DELETE FROM books WHERE doc_id = ?", (doc_id,))
                    con.execute("DELETE FROM status WHERE doc_id = ?", (doc_id,))
                report["removed"] += doc_id in known
            for doc_id, row in rows.items():
                pdf = LIBRARY / row["file"]
                if not pdf.is_file():
                    report["missing"].append(doc_id)
                    continue
                stat = pdf.stat()
                stamp = f"{stat.st_size}:{stat.st_mtime_ns}"
                if known.get(doc_id) == stamp:
                    report["unchanged"] += 1
                    continue
                if verbose:
                    print(f"  indexing {row['slug']} ...")
                try:
                    texts = extract(pdf)  # read it all first: nothing in the index changes yet
                    with con:  # one transaction: the old pages are replaced whole, or not at all
                        con.execute("DELETE FROM pages WHERE doc_id = ?", (doc_id,))
                        con.executemany(
                            "INSERT INTO pages (doc_id, page, text) VALUES (?, ?, ?)",
                            [(doc_id, i + 1, t) for i, t in enumerate(texts) if t],
                        )
                        con.execute("INSERT OR REPLACE INTO books VALUES (?, ?)", (doc_id, stamp))
                        con.execute(
                            "INSERT OR REPLACE INTO status VALUES (?, 'indexed', ?, NULL, 0, ?, ?)",
                            (doc_id, stamp, _now(), _now()),
                        )
                except Exception as e:  # this document only (rolled back); the others go on
                    error = f"{type(e).__name__}: {e}"
                    state = _record_failure(con, doc_id, stamp, error)
                    report["failed"].append(
                        {"id": doc_id, "slug": row["slug"], "error": error, "state": state}
                    )
                    kept = "; its older pages stay searchable" if state == "stale" else ""
                    print(f"  ! couldn't index {row['slug']} ({error}){kept}")
                    continue
                report["indexed"].append(doc_id)
            report["complete"] = not report["failed"] and not report["missing"]
            return report
        finally:
            con.close()


def describe(report: dict) -> str:
    """One line for a log: what an update did, and whether the index is complete."""
    parts = [f"{len(report['indexed'])} indexed", f"{report['unchanged']} unchanged"]
    if report["removed"]:
        parts.append(f"{report['removed']} removed")
    if report["missing"]:
        parts.append(f"{len(report['missing'])} without their PDF")
    if report["failed"]:
        names = ", ".join(f["slug"] for f in report["failed"])
        parts.append(f"{len(report['failed'])} FAILED ({names})")
    state = "complete" if report["complete"] else "INCOMPLETE"
    return f"full-text index {state}: " + ", ".join(parts)


def status() -> dict[str, dict]:
    """{id: {"state", "stamp", "error", "attempts", "last_attempt", "last_success"}} of every
    document an update has tried: "indexed", "failed" (not searchable) or "stale" (an older
    version of its PDF is searchable)."""
    if not INDEX.exists():
        return {}
    con = _connect()
    try:
        cur = con.execute(
            "SELECT doc_id, state, stamp, error, attempts, last_attempt, last_success FROM status"
        )
        names = [d[0] for d in cur.description]
        return {r[0]: dict(zip(names[1:], r[1:], strict=True)) for r in cur}
    finally:
        con.close()


def search(term: str, current: str | None = None, limit: int = 8, per_book: int = 2) -> dict:
    """Pages that discuss `term` most, at most `per_book` per book; the book being read first."""
    words = re.findall(r"[A-Za-z0-9]+", term)
    if not words or not INDEX.exists():
        return {"term": term, "results": [], "indexing": not INDEX.exists()}
    query = '"' + " ".join(words) + '"'  # the exact phrase (each word stemmed)
    rows = catalog.load(CATALOG)
    titles = {doc_id: row["title"] for doc_id, row in rows.items()}
    problems = {i: st for i, st in status().items() if st["state"] in ("failed", "stale")}
    con = _connect()
    try:
        hits = con.execute(
            "SELECT doc_id, page, snippet(pages, 2, ?, ?, '…', 18), bm25(pages) "
            "FROM pages WHERE pages MATCH ? ORDER BY bm25(pages) LIMIT 200",
            (MARK_START, MARK_END, query),
        ).fetchall()
        counts = dict(
            con.execute(
                "SELECT doc_id, count(*) FROM pages WHERE pages MATCH ? GROUP BY doc_id", (query,)
            )
        )
    finally:
        con.close()
    picked: list[dict] = []
    per: dict[str, int] = {}
    for doc_id, page, snippet, _ in sorted(hits, key=lambda h: h[0] != current):
        if per.get(doc_id, 0) >= per_book or doc_id not in titles:
            continue
        per[doc_id] = per.get(doc_id, 0) + 1
        picked.append(
            {
                "id": doc_id,
                "title": titles[doc_id],
                "file": rows[doc_id]["file"],
                "page": page,
                "snippet": snippet,
                # from an older version of the PDF: it changed and couldn't be read again
                "stale": problems.get(doc_id, {}).get("state") == "stale",
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
        # documents whose current PDF isn't (fully) searchable: never indexed, or stale
        "not_indexed": [
            {"id": i, "title": titles[i], "state": st["state"]}
            for i, st in problems.items()
            if i in titles
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    paths.add_argument(parser)
    parser.add_argument("term", nargs="*")
    parser.add_argument("--status", action="store_true", help="each document's index status")
    args = parser.parse_args()
    print(describe(update(verbose=True)))
    if args.status:
        names = {i: r["slug"] for i, r in catalog.load(CATALOG).items()}
        for doc_id, st in sorted(status().items(), key=lambda kv: names.get(kv[0], "")):
            extra = f" ({st['attempts']} attempts: {st['error']})" if st["error"] else ""
            print(f"  {st['state']:8} {names.get(doc_id, doc_id)}{extra}")
    if not args.term:
        return
    found = search(" ".join(args.term))
    print(f"'{found['term']}': {found['pages']} pages in {found['books']} books; best pages:")
    for r in found["results"]:
        snippet = r["snippet"].replace(MARK_START, "[").replace(MARK_END, "]")
        print(f"  {r['title'][:50]}  p.{r['page']}: {snippet}")


if __name__ == "__main__":
    main()
