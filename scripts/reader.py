"""Reading view with an English-Chinese word lookup, used by library_server.py.

    uv run scripts/reader.py --setup          # one-time download (~72 MB), also run by the server
    uv run scripts/reader.py aberrations      # look a word up in the terminal

Books open in PDF.js (Mozilla's PDF viewer, kept in .cache/reader/pdfjs/). Double-click a
word, or drag over a phrase, to see:
  - its meaning in your subject glossaries (glossaries/*.csv, e.g. glossaries/optics.csv),
    with a short definition: your own lists, add terms any time
  - its general meaning from ECDICT (open-source English-Chinese dictionary, offline,
    kept in .cache/reader/ecdict.db)
  - 在我的书中 (In my books): the pages of your books that discuss it most (book_search.py),
    and links to Wikipedia / 维基百科 (Chinese Wikipedia) / 百度百科 (Baidu Baike)
"加入生词本" (Save word) adds the word to notes/<slug>/vocabulary.md.
"""

import argparse
import csv
import io
import re
import shutil
import sqlite3
import sys
import tomllib
import urllib.request
import zipfile
from datetime import date
from functools import lru_cache
from pathlib import Path

import catalog
import paths

LIBRARY = paths.LIBRARY
CACHE = paths.APP / ".cache" / "reader"
PDFJS = CACHE / "pdfjs"
DICT_DB = CACHE / "ecdict.db"
GLOSSARIES = LIBRARY / "glossaries"
GLOSSARY_CONFIG = GLOSSARIES / "glossaries.toml"
STATIC = Path(__file__).resolve().parent / "reader_static"

PDFJS_URL = "https://github.com/mozilla/pdf.js/releases/download/v4.10.38/pdfjs-4.10.38-dist.zip"
ECDICT_URL = "https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv"

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".ftl": "text/plain; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".gif": "image/gif",
    ".wasm": "application/wasm",
}


# --- one-time setup -----------------------------------------------------------------------


def missing() -> list[str]:
    """What setup() still has to fetch."""
    parts = []
    if not (PDFJS / "web" / "viewer.html").exists():
        parts.append("PDF viewer")
    if not DICT_DB.exists():
        parts.append("dictionary")
    return parts


def _download(url: str, dest: Path) -> None:
    print(f"  downloading {url.rsplit('/', 1)[-1]} ...")
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=60) as response, open(tmp, "wb") as out:
        shutil.copyfileobj(response, out)
    tmp.replace(dest)


def build_dictionary(csv_path: Path, db_path: Path) -> int:
    """ECDICT's CSV -> a small SQLite table (word, phonetic, translation, exchange)."""
    tmp = db_path.with_suffix(".part")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.execute(
        "CREATE TABLE dict (word TEXT, lc TEXT, phonetic TEXT, translation TEXT, exchange TEXT)"
    )
    with open(csv_path, encoding="utf-8", newline="") as f:
        rows = (
            (r["word"], r["word"].lower(), r["phonetic"], r["translation"], r["exchange"])
            for r in csv.DictReader(f)
            if r["word"] and r["translation"]
        )
        con.executemany("INSERT INTO dict VALUES (?, ?, ?, ?, ?)", rows)
    con.execute("CREATE INDEX dict_lc ON dict (lc)")
    count = con.execute("SELECT count(*) FROM dict").fetchone()[0]
    con.commit()
    con.close()
    tmp.replace(db_path)
    return count


def setup() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    if not (PDFJS / "web" / "viewer.html").exists():
        zip_path = CACHE / "pdfjs.zip"
        if not zip_path.exists():
            _download(PDFJS_URL, zip_path)
        shutil.rmtree(PDFJS, ignore_errors=True)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(PDFJS)
        zip_path.unlink()
        print("  PDF viewer ready")
    if not DICT_DB.exists():
        csv_path = CACHE / "ecdict.csv"
        if not csv_path.exists():
            _download(ECDICT_URL, csv_path)
        print("  building the dictionary (about a minute) ...")
        count = build_dictionary(csv_path, DICT_DB)
        csv_path.unlink()
        print(f"  dictionary ready: {count:,} words")


# --- lookup -------------------------------------------------------------------------------


def _connect() -> sqlite3.Connection | None:
    return sqlite3.connect(f"file:{DICT_DB}?mode=ro", uri=True) if DICT_DB.exists() else None


def _row(con: sqlite3.Connection | None, word: str) -> dict | None:
    if con is None:
        return None
    row = con.execute(
        "SELECT word, phonetic, translation, exchange FROM dict WHERE lc = ? "
        "ORDER BY word = ? DESC LIMIT 1",
        (word.lower(), word),
    ).fetchone()
    if not row:
        return None
    return {
        "word": row[0],
        "phonetic": row[1],
        "translation": row[2].replace("\\n", "\n"),
        "exchange": row[3],
    }


@lru_cache(maxsize=20000)
def _lemma(word: str, db_key: str) -> str:
    """'aberrations' -> 'aberration', 'focusing' -> 'focus' (db_key only keys the cache)."""
    con = _connect()
    if con is None:
        return _plain_lemma(word)
    try:
        row = _row(con, word)
        if row and (m := re.search(r"(?:^|/)0:([^/]+)", row["exchange"] or "")):
            return m[1].lower()
        if row:
            return word
        for guess in _guesses(word):
            if _row(con, guess):
                return guess
        return _plain_lemma(word)  # not a dictionary word: at least singular (Zernikes)
    finally:
        con.close()


def _guesses(word: str):
    """Possible base forms: rays -> ray, mirrors -> mirror, stopped -> stop, making -> make."""
    for suffix in ("ies", "es", "s", "ing", "ed"):
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            stem = word[: -len(suffix)]
            yield stem + "y" if suffix == "ies" else stem
            if suffix in ("ing", "ed"):
                yield stem + "e"
                if stem[-1] == stem[-2]:
                    yield stem[:-1]


def _plain_lemma(word: str) -> str:
    """Without the dictionary: just strip a plural s (rays -> ray, lenses -> lens)."""
    if word.endswith("ses") and len(word) > 4:
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def _file_key(path: Path) -> tuple:
    """Changes whenever the file does (even two edits within one clock tick, or another file)."""
    stat = path.stat()
    return (str(path), stat.st_mtime_ns, stat.st_size)


# --- glossaries ---------------------------------------------------------------------------
#
# One CSV per subject in glossaries/ (columns: term, zh, note, definition). All of them are
# used. glossaries/glossaries.toml (optional) names them for the popup and picks the one that
# 加入术语表 (Add to glossary) adds to:
#
#     default = "optics"
#     [optics]
#     label = "光学 Optics"


def _config() -> dict:
    if not GLOSSARY_CONFIG.exists():
        return {}
    with open(GLOSSARY_CONFIG, "rb") as f:
        return tomllib.load(f)


def glossary_files() -> list[dict]:
    """[{name, label, path}] for each glossary in use; the default one (for new terms) first."""
    if not GLOSSARIES.is_dir():
        return []
    config = _config()
    found = []
    for path in sorted(GLOSSARIES.glob("*.csv")):
        settings = config.get(path.stem) if isinstance(config.get(path.stem), dict) else {}
        if settings.get("enabled", True) is False:
            continue
        label = str(settings.get("label") or path.stem)
        found.append({"name": path.stem, "label": label, "path": path})
    default = config.get("default")
    found.sort(key=lambda g: g["name"] != default)  # stable: the rest stay alphabetical
    return found


def _glossaries_key() -> tuple:
    files = glossary_files()
    config = _file_key(GLOSSARY_CONFIG) if GLOSSARY_CONFIG.exists() else ()
    return (config, *(_file_key(g["path"]) for g in files))


def _rows(path: Path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


_glossary_words_cache: tuple[tuple, set[str]] | None = None


def _glossary_words() -> set[str]:
    """Every word used in a glossary term, as written ("lens", "matrix", "contract", ...)."""
    global _glossary_words_cache
    key = _glossaries_key()
    if _glossary_words_cache is None or _glossary_words_cache[0] != key:
        words = {
            w
            for g in glossary_files()
            for row in _rows(g["path"])
            for w in re.findall(r"[a-z0-9]+", (row.get("term") or "").lower())
        }
        _glossary_words_cache = (key, words)
    return _glossary_words_cache[1]


# Irregular plurals common in textbooks, which the dictionary gets wrong ("axes" -> "ax")
IRREGULAR_PLURALS = {
    "axes": "axis",
    "analyses": "analysis",
    "apices": "apex",
    "appendices": "appendix",
    "bacteria": "bacterium",
    "criteria": "criterion",
    "foci": "focus",
    "formulae": "formula",
    "hypotheses": "hypothesis",
    "indices": "index",
    "matrices": "matrix",
    "maxima": "maximum",
    "minima": "minimum",
    "nuclei": "nucleus",
    "phenomena": "phenomenon",
    "radii": "radius",
    "spectra": "spectrum",
    "stimuli": "stimulus",
    "theses": "thesis",
    "vertices": "vertex",
}


def lemma(word: str) -> str:
    """Base form of a word. A form a glossary uses wins over the dictionary's choice:
    ECDICT gives "lenses" -> "lense", but the optics glossary says "lens"."""
    word = word.lower()
    if word in IRREGULAR_PLURALS:
        return IRREGULAR_PLURALS[word]
    vocab = _glossary_words()
    for guess in _guesses(word):  # before the word itself: "fringes" -> "fringe"
        if guess in vocab:
            return guess
    if word in vocab:
        return word
    db_key = str(DICT_DB.stat().st_mtime) if DICT_DB.exists() else ""
    return _lemma(word, db_key)


def tokens(text: str) -> list[str]:
    return [lemma(t) for t in re.findall(r"[a-z0-9]+", text.lower())]


_glossary_cache: tuple[tuple, dict] | None = None


def glossary() -> dict[tuple[str, ...], list[dict]]:
    """{lemmatized term tokens: [entry, ...]}: one entry per glossary that has the term, each
    {term, zh, note, definition, glossary, label}. Re-read when a glossary file changes."""
    global _glossary_cache
    key = _glossaries_key()
    if _glossary_cache is None or _glossary_cache[0] != key:
        terms: dict[tuple[str, ...], list[dict]] = {}
        for g in glossary_files():
            for row in _rows(g["path"]):
                term = (row.get("term") or "").strip()
                if not term or not (row.get("zh") or "").strip():
                    continue
                entries = terms.setdefault(tuple(tokens(term)), [])
                if any(e["glossary"] == g["name"] for e in entries):
                    continue  # the same term twice in one glossary: the first row wins
                entries.append(
                    {
                        "term": term,
                        "zh": row["zh"].strip(),
                        "note": (row.get("note") or "").strip(),
                        "definition": (row.get("definition") or "").strip(),
                        "glossary": g["name"],
                        "label": g["label"],
                    }
                )
        _glossary_cache = (key, terms)
    return _glossary_cache[1]


def glossary_matches(text: str, context: str = "") -> list[dict]:
    """Glossary entries for the selected text: the text itself, plus longer terms around it in
    the context ('pupil' inside '... the entrance pupil is ...' also gives 'entrance pupil'),
    plus the terms inside a longer selection."""
    terms = glossary()
    query = tuple(tokens(text))
    if not query:
        return []
    found: list[dict] = list(terms.get(query, []))

    def add(entries: list[dict]) -> None:
        found.extend(e for e in entries if e not in found)

    ctx = tokens(context)
    longest = max((len(k) for k in terms), default=0)
    for size in range(longest, len(query), -1):
        for i in range(len(ctx) - size + 1):
            window = tuple(ctx[i : i + size])
            has_query = any(
                window[j : j + len(query)] == query for j in range(size - len(query) + 1)
            )
            if has_query and window in terms:
                add(terms[window])
    # Longer terms are more specific: show them first, the bare word last
    found.sort(key=lambda e: -len(tokens(e["term"])))
    # A longer selection ("the entrance pupil of a lens"): the terms inside it, longest first,
    # skipping words already covered by a longer term ("pupil" inside "entrance pupil")
    covered = [query in terms] * len(query)
    for size in range(min(longest, len(query) - 1), 0, -1):
        for i in range(len(query) - size + 1):
            window = query[i : i + size]
            if window in terms and not any(covered[i : i + size]):
                covered[i : i + size] = [True] * size
                add(terms[window])
    return found


STOP_WORDS = {
    "a",
    "an",
    "the",
    "of",
    "and",
    "or",
    "in",
    "on",
    "at",
    "to",
    "for",
    "by",
    "with",
    "from",
    "as",
    "is",
    "are",
    "be",
    "its",
    "it",
    "this",
    "that",
    "into",
}


def _short(translation: str, limit: int = 60) -> str:
    first = translation.splitlines()[0] if translation else ""
    return first if len(first) <= limit else first[: limit - 1] + "…"


def _norm(name: str) -> str:
    """'Lens design' / 'lens-design' / '镜头设计 Lens design' -> 'lensdesign'."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def book_shelves(slug: str | None) -> set[str]:
    """The shelves of the book being read (normalized), from catalog.csv."""
    if not slug:
        return set()
    row = catalog.load(LIBRARY / "catalog.csv").get(slug)
    return {_norm(s) for s in catalog.split_list(row.get("shelves") or "")} if row else set()


def lookup(text: str, context: str = "", slug: str | None = None) -> dict:
    """Everything the popup shows for a double-clicked word or a selected phrase.

    A phrase that neither a glossary nor the dictionary knows also gets "words": each word's
    meaning (glossary meaning first), so an unknown phrase still says something useful.
    """
    text = re.sub(r"\s+", " ", text).strip().strip(".,;:!?()[]{}\"'“”‘’")[:100]
    matches = glossary_matches(text, context)
    # Reading a book: glossaries for its shelves come first ("pupil" in an optics book: the
    # optics meaning before the biology one); longer, more specific terms still lead
    shelves = book_shelves(slug)

    def rank(entry: dict) -> int:
        return 0 if {_norm(entry["glossary"]), _norm(entry["label"])} & shelves else 1

    matches.sort(key=lambda e: (-len(tokens(e["term"])), rank(e)))
    result = {
        "query": text,
        "glossary": matches,
        "in_glossary": any(tokens(g["term"]) == tokens(text) for g in matches),
        "glossaries": [{"name": g["name"], "label": g["label"]} for g in glossary_files()],
        "entries": [],
        "words": [],
    }
    if not text:
        return result
    con = _connect()
    try:
        row = _row(con, text)
        base = lemma(text) if " " not in text else text.lower()
        if base != text.lower() and (base_row := _row(con, base)):
            base_row["from"] = text  # 'aberrations' shows the entry for 'aberration'
            result["entries"].append(base_row)
        elif row:
            result["entries"].append(row)
        if " " in text and not result["entries"] and not result["in_glossary"]:
            terms = glossary()
            explained = {t for g in matches for t in tokens(g["term"])}  # by a glossary term
            for word in re.findall(r"[A-Za-z][A-Za-z'-]*", text):
                if word.lower() in STOP_WORDS or lemma(word) in explained:
                    continue
                explained.add(lemma(word))
                own = min(terms.get((lemma(word),)) or [None], key=lambda e: e and rank(e))
                found = _row(con, lemma(word)) or _row(con, word)
                result["words"].append(
                    {
                        "word": word,
                        "zh": own["zh"] if own else "",
                        "label": own["label"] if own else "",
                        "translation": _short(found["translation"]) if found else "",
                    }
                )
    finally:
        if con:
            con.close()
    for entry in result["entries"]:
        entry.pop("exchange", None)
    result["dictionary"] = DICT_DB.exists()
    return result


NEW_GLOSSARY = "my-terms"  # created by 加入术语表 (Add to glossary) if there is none yet


def add_glossary_term(
    term: str, zh: str, definition: str = "", note: str = "", glossary_name: str | None = None
) -> dict:
    """Append your own term to a glossary (from 加入术语表 / Add to glossary in the popup): the
    one named, else
    the default one, else a new glossaries/my-terms.csv."""
    term = re.sub(r"\s+", " ", term).strip().strip(".,;:!?()[]{}\"'“”‘’")
    zh, definition, note = (re.sub(r"\s+", " ", v).strip() for v in (zh, definition, note))
    if not re.search(r"[A-Za-z]", term) or len(term) > 80:
        raise ValueError("the term should be an English word or phrase (up to 80 characters)")
    if not zh or len(zh) > 60 or len(definition) > 400 or len(note) > 200:
        raise ValueError(
            "the Chinese term (中文) is required, up to 60 characters; definition up to 400"
        )
    files = glossary_files()
    if glossary_name:
        target = next((g for g in files if g["name"] == glossary_name), None)
        if target is None:
            raise ValueError(f"no glossary called “{glossary_name}”")
    elif files:
        target = files[0]
    else:
        path = GLOSSARIES / f"{NEW_GLOSSARY}.csv"
        target = {"name": NEW_GLOSSARY, "label": NEW_GLOSSARY, "path": path}
    if any(e["glossary"] == target["name"] for e in glossary().get(tuple(tokens(term)), [])):
        raise ValueError(f"“{term}” is already in the {target['label']} glossary")
    path = target["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    with open(path, "a", encoding="utf-8", newline="") as f:
        if not existing:
            f.write("term,zh,note,definition\n")
        elif not existing.endswith("\n"):
            f.write("\n")
        csv.writer(f, lineterminator="\n").writerow([term, zh, note, definition])
    return {
        "term": term,
        "zh": zh,
        "note": note,
        "definition": definition,
        "glossary": target["name"],
        "label": target["label"],
    }


# --- vocabulary list ----------------------------------------------------------------------

VOCAB_HEADER = """# Vocabulary: {title}

Words looked up while reading (added with 加入生词本 / Save word in the reading view).

| Word | Phonetic | 中文 Chinese | Page | Added |
|---|---|---|---|---|
"""


def save_word(slug: str, title: str, text: str, context: str, page: int | None) -> dict:
    """Add a word to notes/<slug>/vocabulary.md (once per word), with its glossary meaning if
    a glossary has one, else the first lines of the dictionary entry."""
    info = lookup(text, context)
    entry = info["entries"][0] if info["entries"] else {}
    own = next((g for g in info["glossary"] if tokens(g["term"]) == tokens(text)), None)
    if own and len(tokens(text)) > 1:
        word = own["term"]
    else:
        word = entry.get("word") or info["query"]
    if own:
        meaning = own["zh"]
    else:
        lines = entry.get("translation", "").splitlines()
        meaning = "； ".join(line.strip() for line in lines[:2])[:80]
    if not word:
        raise ValueError("nothing to save")
    path = LIBRARY / "notes" / slug / "vocabulary.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if not existing:
        existing = VOCAB_HEADER.format(title=title)
    saved_words = {
        m[1].strip().lower() for m in re.finditer(r"^\| ([^|]+) \|", existing, re.MULTILINE)
    }
    if word.lower() in saved_words:
        return {"word": word, "saved": False, "file": path.relative_to(LIBRARY).as_posix()}

    def cell(value) -> str:
        return str(value or "").replace("|", "/").replace("\n", " ").strip()

    row = (
        f"| {cell(word)} | {cell(entry.get('phonetic'))} | {cell(meaning)} | "
        f"{cell(page)} | {date.today().isoformat()} |\n"
    )
    path.write_text(existing.rstrip("\n") + "\n" + row, encoding="utf-8")
    return {"word": word, "saved": True, "file": path.relative_to(LIBRARY).as_posix()}


# --- serving the viewer -------------------------------------------------------------------


def viewer_html(token: str) -> bytes:
    """PDF.js's viewer page, with the lookup popup added."""
    html = (PDFJS / "web" / "viewer.html").read_text(encoding="utf-8-sig")
    extra = (
        '<link rel="stylesheet" href="/reader/lookup.css">\n'
        f"<script>window.MYLIBRARY_TOKEN = {token!r};</script>\n"
        '<script src="/reader/lookup.js" defer></script>\n'
    )
    return html.replace("</head>", extra + "</head>", 1).encode()


def static_file(url_path: str) -> tuple[bytes, str] | None:
    """/pdfjs/... and /reader/... files; None for anything outside those folders."""
    for prefix, folder in (("/pdfjs/", PDFJS), ("/reader/", STATIC)):
        if url_path.startswith(prefix):
            base = folder.resolve()
            path = (base / url_path[len(prefix) :]).resolve()
            if path.is_file() and path.is_relative_to(base):
                kind = CONTENT_TYPES.get(path.suffix, "application/octet-stream")
                return path.read_bytes(), kind
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    paths.add_argument(parser)
    parser.add_argument("--setup", action="store_true", help="download the viewer + dictionary")
    parser.add_argument("word", nargs="*", help="look up a word or phrase")
    args = parser.parse_args()
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if args.setup or not args.word:
        setup() if missing() else print("Reading view is set up.")
    if args.word:
        info = lookup(" ".join(args.word))
        for g in info["glossary"]:
            note = f"  ({g['note']})" if g["note"] else ""
            print(f"[{g['label']}] {g['term']}: {g['zh']}{note}")
            if g["definition"]:
                print(f"       {g['definition']}")
        for e in info["entries"]:
            head = e["word"] + (f"  /{e['phonetic']}/" if e["phonetic"] else "")
            print(head + (f"   (from {e['from']})" if e.get("from") else ""))
            print("  " + e["translation"].replace("\n", "\n  "))


if __name__ == "__main__":
    main()
