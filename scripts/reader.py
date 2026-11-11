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
"加入生词本" (Save word) adds the word to the document's notes/<name>/vocabulary.md.
"""

import argparse
import codecs
import csv
import hashlib
import io
import json
import re
import shutil
import sqlite3
import sys
import tarfile
import tomllib
import urllib.request
import uuid
import zipfile
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

import catalog
import notes_store
import paths
import safe_io

LIBRARY = paths.LIBRARY
CACHE = paths.APP / ".cache" / "reader"
PDFJS = CACHE / "pdfjs"
DICT_DB = CACHE / "ecdict.db"
GLOSSARIES = LIBRARY / "glossaries"
GLOSSARY_CONFIG = GLOSSARIES / "glossaries.toml"
STATIC = Path(__file__).resolve().parent / "reader_static"

PDFJS_VERSION = "4.10.38"
PDFJS_URL = (
    f"https://github.com/mozilla/pdf.js/releases/download/v{PDFJS_VERSION}/"
    f"pdfjs-{PDFJS_VERSION}-dist.zip"
)
# The release zip, checked before it's installed. Taken 2026-11-07 from GitHub (which publishes
# no digest for this release) and confirmed against an earlier download: all 377 files equal.
PDFJS_SHA256 = "32bdd9c5198b77dbaa8f02de81f34476888b3abdd64b9fb5f607f81f01487e6a"
PDFJS_SIZE = 6_066_797
PDFJS_MARKER = ".myLibrary-pdfjs.txt"  # in an installed viewer: its version and zip checksum
ECDICT_URL = "https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv"

# The notes' preview (task 4 M5a): markdown-it, its self-contained browser build. The npm
# package, checked before it's installed: taken 2026-11-08 from the npm registry, whose own
# integrity value (SHA-512) it matched. Only the two files below are taken from it.
MARKDOWN_IT = CACHE / "markdown-it"
MARKDOWN_IT_VERSION = "15.0.3"
MARKDOWN_IT_URL = f"https://registry.npmjs.org/markdown-it/-/markdown-it-{MARKDOWN_IT_VERSION}.tgz"
MARKDOWN_IT_SHA256 = "98a7453983ab0e268c17dbd5260bf7190ba46b4cca912327fc1c1a2578e4b56d"
MARKDOWN_IT_SIZE = 587_613
MARKDOWN_IT_FILES = {  # in the package -> installed as
    "package/dist/browser/markdown-it.umd.min.js": "markdown-it.min.js",
    "package/LICENSE": "LICENSE",
}
MARKDOWN_IT_MARKER = ".myLibrary-markdown-it.txt"

# Maths in the notes' preview (task 4 M5b): KaTeX's browser build, its stylesheet and fonts.
# The npm package, checked before it's installed: taken 2026-11-11 from the npm registry, whose
# own integrity values (SHA-512 and SHA-1) it matched; every file below was also byte-identical
# to the one in KaTeX's GitHub release (v0.19.1, katex.tar.gz). Each installed file is checked
# against its SHA-256 here whenever the reader page is made, so a damaged or partial copy is
# never loaded (the preview then shows the formulas as written). Only the WOFF2 fonts are
# taken: katex.min.css names them first, and Edge (and WebView2) always use them.
KATEX = CACHE / "katex"
KATEX_VERSION = "0.19.1"
KATEX_URL = f"https://registry.npmjs.org/katex/-/katex-{KATEX_VERSION}.tgz"
KATEX_SHA256 = "24da5a599eb2fcede2e270b99a6ff48bca816beecc95feeb84e8cccbd1bb34fd"
KATEX_SIZE = 1_499_956
KATEX_FONTS = {  # fonts/KaTeX_<name>.woff2 -> its SHA-256
    "AMS-Regular": "0cdd387c9590a1a9f9794560022dbb59654a7d86f187aa0c81495ad42d3a7308",
    "Caligraphic-Bold": "de7701e42cf1f4cf0b766c03fb27977207eee2f4fd5d76fa82188406da43ea4c",
    "Caligraphic-Regular": "5d53e70ad607c2352162dec9e0923fb54ecdafaccbf604cd8dcf7d00facb989b",
    "Fraktur-Bold": "74444efd593c005e3f4573b44524704c0af0a937fe911cca9e94068d0d140d3f",
    "Fraktur-Regular": "51814d270d06ff0255dba0799994fa4d8c84d11f09951d47595f4abb1f3602dc",
    "Main-Bold": "0f60d1b897938ec918c8ce073092411baf9438f6739465693ff18b0f9d20b021",
    "Main-BoldItalic": "99cd42a3c072d918f2f44984a807cf7aa16e13545fd0875fc07c6c65f99e715b",
    "Main-Italic": "97479ca6cce906abc961ecac96faa5f9ca2e61b8e7670d475826bcdee9a7c267",
    "Main-Regular": "c2342cd8b869e01752a9321dc17213fc40d4d04c79688c1d43f2cf316abd7866",
    "Math-BoldItalic": "dc47344dbb6cb5b655c8460d561f4df5f501b90c804ad3c6cec65fe322351ab1",
    "Math-Italic": "7af58c5ec8f132a2ddde9027c6d7814decce4d3b822a11192a42a20e2e973264",
    "SansSerif-Bold": "e99ae51144bf1232efcc1bfe5add36262c6866b0faab24fa75740e1b98577a62",
    "SansSerif-Italic": "00b26ac825e2095056396e0553b8ac26d3f8ad158c3826e28b4c45b385c4714a",
    "SansSerif-Regular": "68e8c73ef42afd3ccec58bf0fba302cce448938e7fc020a5e31f8a952eee1342",
    "Script-Regular": "036d4e95149b69ff9bcc0cd55771efeb25ffa3947293e69acd78d5ac328c684b",
    "Size1-Regular": "6b47c40166b6dbe21a5dfca7718413f2147fd2399be1ba605d8ad39cedf25dfe",
    "Size2-Regular": "d04c54219f9eaec6d4d4fd42dfb28785975a4794d6b2fc71e566b9cd6db842dd",
    "Size3-Regular": "73d591271b1604960cb10bb90fee021670af7297017e0e98480b332d11f51995",
    "Size4-Regular": "a4af7d414440a1c1790825cfb700cf9cf43b0f2c4b04f0ebc523011ad9853ec0",
    "Typewriter-Regular": "71d517d67827787cfabdf186914cc3358eda539e37931941f2b2fd4a21f68c0b",
}
KATEX_FILES = {  # installed as (from package/dist/, LICENSE from package/) -> its SHA-256
    "katex.min.js": "fa140498b8cfc8302cbe5e7cb1bdbc1f952bc38b3fa258ede09e73edbf9a74bc",
    "katex.min.css": "00e0b094171b07f58422075f469b4feac2b2f7bce1aeec943c08da4d697f4dcf",
    "LICENSE": "766ccc1f306c885aa45542a9846bbd0a505b27a0374f146778171c2254ce18e3",
    **{f"fonts/KaTeX_{name}.woff2": digest for name, digest in KATEX_FONTS.items()},
}
KATEX_MARKER = ".myLibrary-katex.txt"

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
    ".woff2": "font/woff2",
}


# --- one-time setup -----------------------------------------------------------------------


def viewer_ready() -> bool:
    """PDF.js is installed, so books open in the reading view. The dictionary is optional:
    without it lookups find only the glossaries, but the reader works."""
    return (PDFJS / "web" / "viewer.html").exists()


def missing() -> list[str]:
    """What setup() still has to fetch."""
    parts = []
    if not (PDFJS / "web" / "viewer.html").exists():
        parts.append("PDF viewer")
    if not DICT_DB.exists():
        parts.append("dictionary")
    if not markdown_it_installed():
        parts.append("notes preview")
    if not katex_installed():
        parts.append("maths")
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


def _check_zip(z: zipfile.ZipFile) -> None:
    """A PDF.js release zip: no file may land outside the folder, and the viewer must be in it."""
    names = z.namelist()
    for name in names:
        parts = Path(name).parts
        if name.startswith(("/", "\\")) or ".." in parts or ":" in name:
            raise ValueError(f"the PDF.js archive has an unsafe file name: {name!r}")
    for needed in ("web/viewer.html", "web/viewer.mjs", "build/pdf.mjs", "build/pdf.worker.mjs"):
        if needed not in names:
            raise ValueError(f"the PDF.js archive lacks {needed}")


def install_viewer(zip_path: Path) -> None:
    """Install PDF.js from its release zip, after checking its size, SHA-256 and contents.
    The new viewer is unpacked beside the old one and only then swapped in, so a wrong or
    broken download leaves a working viewer as it was."""
    data = zip_path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != PDFJS_SIZE or digest != PDFJS_SHA256:
        raise ValueError(
            f"the PDF.js download isn't the expected file ({len(data):,} bytes, SHA-256 "
            f"{digest[:16]}…; expected {PDFJS_SIZE:,} bytes, {PDFJS_SHA256[:16]}…)"
        )
    new = CACHE / f"pdfjs.new-{uuid.uuid4().hex[:8]}"
    old = CACHE / f"pdfjs.old-{uuid.uuid4().hex[:8]}"
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            _check_zip(z)
            z.extractall(new)
        (new / PDFJS_MARKER).write_text(f"{PDFJS_VERSION}\n{PDFJS_SHA256}\n", encoding="utf-8")
        if PDFJS.exists():
            PDFJS.replace(old)
        new.replace(PDFJS)
    except BaseException:
        if old.exists() and not PDFJS.exists():
            old.replace(PDFJS)  # put the working viewer back
        raise
    finally:
        shutil.rmtree(new, ignore_errors=True)
        shutil.rmtree(old, ignore_errors=True)


def viewer_installed() -> str:
    """How the installed viewer was checked: "verified <version>", "unverified" (installed
    before checksums), or "" when there's none."""
    if not (PDFJS / "web" / "viewer.html").exists():
        return ""
    marker = PDFJS / PDFJS_MARKER
    lines = marker.read_text(encoding="utf-8").split() if marker.exists() else []
    return f"verified {lines[0]}" if lines[1:2] == [PDFJS_SHA256] else "unverified"


def setup_viewer() -> None:
    """Download and install PDF.js (pinned version, checksum checked) unless it's there."""
    if viewer_installed():
        print(f"  PDF viewer already installed ({viewer_installed()})")
        return
    CACHE.mkdir(parents=True, exist_ok=True)
    zip_path = CACHE / f"pdfjs-{PDFJS_VERSION}-dist.zip"
    try:
        _download(PDFJS_URL, zip_path)
        install_viewer(zip_path)
    finally:
        zip_path.unlink(missing_ok=True)
    print(f"  PDF viewer ready (PDF.js {PDFJS_VERSION}, checksum verified)")


def install_markdown_it(package_path: Path) -> None:
    """Install markdown-it's browser build from its npm package, after checking the package's
    size and SHA-256. Only the named files are read from it (never extracted as a whole, so no
    name in it can reach outside the folder); the new copy is put beside the old one and only
    then swapped in, so a wrong download leaves a working preview as it was."""
    data = package_path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != MARKDOWN_IT_SIZE or digest != MARKDOWN_IT_SHA256:
        raise ValueError(
            f"the markdown-it download isn't the expected file ({len(data):,} bytes, SHA-256 "
            f"{digest[:16]}…; expected {MARKDOWN_IT_SIZE:,} bytes, {MARKDOWN_IT_SHA256[:16]}…)"
        )
    new = CACHE / f"markdown-it.new-{uuid.uuid4().hex[:8]}"
    old = CACHE / f"markdown-it.old-{uuid.uuid4().hex[:8]}"
    try:
        new.mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as package:
            for member_name, installed_name in MARKDOWN_IT_FILES.items():
                member = package.getmember(member_name)  # KeyError if it isn't there
                if not member.isfile() or member.size > 5_000_000:
                    raise ValueError(f"the markdown-it package has an unexpected {member_name}")
                (new / installed_name).write_bytes(package.extractfile(member).read())
        (new / MARKDOWN_IT_MARKER).write_text(
            f"{MARKDOWN_IT_VERSION}\n{MARKDOWN_IT_SHA256}\n", encoding="utf-8"
        )
        if MARKDOWN_IT.exists():
            MARKDOWN_IT.replace(old)
        new.replace(MARKDOWN_IT)
    except BaseException:
        if old.exists() and not MARKDOWN_IT.exists():
            old.replace(MARKDOWN_IT)  # put the working copy back
        raise
    finally:
        shutil.rmtree(new, ignore_errors=True)
        shutil.rmtree(old, ignore_errors=True)


def markdown_it_installed() -> str:
    """How the preview library is installed: "verified <version>" when it is the pinned one,
    "" when it isn't there (or isn't the one checked)."""
    marker = MARKDOWN_IT / MARKDOWN_IT_MARKER
    if not (MARKDOWN_IT / "markdown-it.min.js").is_file() or not marker.is_file():
        return ""
    lines = marker.read_text(encoding="utf-8").split()
    if lines[:2] != [MARKDOWN_IT_VERSION, MARKDOWN_IT_SHA256]:
        return ""
    return f"verified {MARKDOWN_IT_VERSION}"


def setup_preview() -> None:
    """Download and install markdown-it for the notes' preview (pinned, checksum checked)."""
    if markdown_it_installed():
        print(f"  notes preview already installed ({markdown_it_installed()})")
        return
    CACHE.mkdir(parents=True, exist_ok=True)
    package_path = CACHE / f"markdown-it-{MARKDOWN_IT_VERSION}.tgz"
    try:
        _download(MARKDOWN_IT_URL, package_path)
        install_markdown_it(package_path)
    finally:
        package_path.unlink(missing_ok=True)
    print(f"  notes preview ready (markdown-it {MARKDOWN_IT_VERSION}, checksum verified)")


def _katex_member(name: str) -> str:
    return f"package/{name}" if name == "LICENSE" else f"package/dist/{name}"


def install_katex(package_path: Path) -> None:
    """Install KaTeX (maths in the notes' preview) from its npm package, after checking the
    package's size and SHA-256, and then each file taken from it against its own SHA-256. Only
    the named files are read (never extracted as a whole); the new copy is put beside the old
    one and only then swapped in, so a wrong download leaves the installed copy as it was."""
    data = package_path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != KATEX_SIZE or digest != KATEX_SHA256:
        raise ValueError(
            f"the KaTeX download isn't the expected file ({len(data):,} bytes, SHA-256 "
            f"{digest[:16]}…; expected {KATEX_SIZE:,} bytes, {KATEX_SHA256[:16]}…)"
        )
    new = CACHE / f"katex.new-{uuid.uuid4().hex[:8]}"
    old = CACHE / f"katex.old-{uuid.uuid4().hex[:8]}"
    try:
        (new / "fonts").mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as package:
            for name, expected in KATEX_FILES.items():
                member = package.getmember(_katex_member(name))  # KeyError if it isn't there
                if not member.isfile() or member.size > 5_000_000:
                    raise ValueError(f"the KaTeX package has an unexpected {member.name}")
                body = package.extractfile(member).read()
                if hashlib.sha256(body).hexdigest() != expected:
                    raise ValueError(f"the KaTeX package's {member.name} isn't the expected file")
                (new / name).write_bytes(body)
        (new / KATEX_MARKER).write_text(f"{KATEX_VERSION}\n{KATEX_SHA256}\n", encoding="utf-8")
        if KATEX.exists():
            KATEX.replace(old)
        new.replace(KATEX)
    except BaseException:
        if old.exists() and not KATEX.exists():
            old.replace(KATEX)  # put the installed copy back
        raise
    finally:
        shutil.rmtree(new, ignore_errors=True)
        shutil.rmtree(old, ignore_errors=True)


def katex_installed() -> str:
    """ "verified <version>" when KaTeX is the pinned one and every file of it is there and
    unchanged (each checked against its SHA-256: about 0.6 MB, read whenever the reader page is
    made); "" otherwise: then the page doesn't load it, and the preview shows the formulas as
    written."""
    marker = KATEX / KATEX_MARKER
    try:
        if marker.read_text(encoding="utf-8").split()[:2] != [KATEX_VERSION, KATEX_SHA256]:
            return ""
        for name, expected in KATEX_FILES.items():
            if hashlib.sha256((KATEX / name).read_bytes()).hexdigest() != expected:
                return ""
    except OSError, UnicodeDecodeError:
        return ""
    return f"verified {KATEX_VERSION}"


def setup_maths() -> None:
    """Download and install KaTeX for maths in the notes' preview (pinned, checksums checked);
    a missing or damaged copy is replaced."""
    if katex_installed():
        print(f"  maths already installed (KaTeX {katex_installed()})")
        return
    CACHE.mkdir(parents=True, exist_ok=True)
    package_path = CACHE / f"katex-{KATEX_VERSION}.tgz"
    try:
        _download(KATEX_URL, package_path)
        install_katex(package_path)
    finally:
        package_path.unlink(missing_ok=True)
    print(f"  maths ready (KaTeX {KATEX_VERSION}, checksums verified)")


def setup() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    setup_viewer()
    setup_preview()
    setup_maths()
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
# Words that look like a plural but name something of their own in technical texts, so they are
# never taken for their stem's plural, in a lookup or when a term is added (L23): "glasses"
# (spectacles) is not "glass" (the material). Kept small and explicit; add a word only with a
# real case of two different terms.
OWN_TERMS = frozenset({"glasses"})


def lemma(word: str, also: frozenset[str] = frozenset()) -> str:
    """Base form of a word. A form a glossary uses wins over the dictionary's choice:
    ECDICT gives "lenses" -> "lense", but the optics glossary says "lens". `also`: words to
    count as glossary words too (a term about to be added, B30)."""
    word = word.lower()
    if word in IRREGULAR_PLURALS:
        return IRREGULAR_PLURALS[word]
    if word in OWN_TERMS:
        return word  # never taken for the plural of its stem (L23)
    vocab = _glossary_words() | also if also else _glossary_words()
    for guess in _guesses(word):  # before the word itself: "fringes" -> "fringe"
        if guess in vocab:
            return guess
    if word in vocab:
        return word
    db_key = str(DICT_DB.stat().st_mtime) if DICT_DB.exists() else ""
    return _lemma(word, db_key)


def tokens(text: str, also: frozenset[str] = frozenset()) -> list[str]:
    return [lemma(t, also) for t in re.findall(r"[a-z0-9]+", text.lower())]


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


_glossary_index_cache: tuple | None = None


def _glossary_index() -> tuple[list, dict, dict]:
    """For lookups that count their own words as glossary words (L23), kept with the glossary
    and re-made when a glossary file changes: ([(term, entry, its key)], {stored word: indexes
    of the terms with it}, {a guess (_guesses): the stored words it is a guess of})."""
    global _glossary_index_cache
    key = _glossaries_key()
    if _glossary_index_cache is None or _glossary_index_cache[0] != key:
        terms = glossary()
        pairs = [(e["term"], e, k) for k, entries in terms.items() for e in entries]
        word_terms: dict[str, set[int]] = {}
        guessed_by: dict[str, set[str]] = {}
        for i, (term, _, _) in enumerate(pairs):
            for word in re.findall(r"[a-z0-9]+", term.lower()):
                word_terms.setdefault(word, set()).add(i)
                for guess in _guesses(word):
                    guessed_by.setdefault(guess, set()).add(word)
        _glossary_index_cache = (key, (pairs, word_terms, guessed_by))
    return _glossary_index_cache[1]


class _Terms:
    """The glossary's terms by key, as they are once `words` count as glossary words too: the
    cached keys, plus the other key of each term whose base forms those words change (only
    those are worked out again, through _glossary_index)."""

    def __init__(self, terms: dict, other: dict):
        self.terms, self.other = terms, other

    def get(self, key: tuple, default=None) -> list[dict]:
        found = list(self.terms.get(key, []))
        found += [e for e in self.other.get(key, []) if e not in found]
        return found or (default if default is not None else [])

    def __contains__(self, key: tuple) -> bool:
        return key in self.terms or key in self.other

    def __getitem__(self, key: tuple) -> list[dict]:
        return self.get(key)

    def __iter__(self):
        yield from self.terms
        yield from (k for k in self.other if k not in self.terms)


def _terms_for(words: frozenset[str]) -> _Terms:
    """The glossary's terms as B30's "same term" sees them when `words` (a selection and its
    context) are added: a term saved as "veiling glares" is then also under (veiling, glare)
    for a query with "glare", whatever other glossaries hold. Only words new to the glossaries
    can change a stored word's base form, and only stored words they are a guess of."""
    terms = glossary()
    new = words - _glossary_words()
    pairs, word_terms, guessed_by = _glossary_index()
    touched = {i for w in new for stored in guessed_by.get(w, ()) for i in word_terms[stored]}
    other: dict[tuple, list[dict]] = {}
    for i in touched:
        term, entry, key = pairs[i]
        if (now := tuple(tokens(term, words))) != key:
            other.setdefault(now, []).append(entry)
    return _Terms(terms, other)


def glossary_matches(text: str, context: str = "") -> list[dict]:
    """Glossary entries for the selected text: the text itself, plus longer terms around it in
    the context ('pupil' inside '... the entrance pupil is ...' also gives 'entrance pupil'),
    plus the terms inside a longer selection.

    Two readings of the words (L23): as the glossaries have them now, and as B30's "same term"
    sees them once these words are in a glossary too, the rule that decides what may be added.
    The second finds a term saved only as "veiling glares" for "veiling glare", whatever other
    glossaries hold; the first keeps every match there was."""
    words = frozenset(re.findall(r"[a-z0-9]+", f"{text} {context}".lower()))
    terms = _terms_for(words)
    query = tuple(tokens(text))
    if not query:
        return []
    readings = [(query, tuple(tokens(context)))]
    if (asked := (tuple(tokens(text, words)), tuple(tokens(context, words)))) != readings[0]:
        readings.append(asked)
    found: list[dict] = []

    def add(entries: list[dict]) -> None:
        found.extend(e for e in entries if e not in found)

    for q, _ in readings:
        add(terms.get(q, []))
    longest = max((len(k) for k in terms), default=0)
    for q, ctx in readings:
        for size in range(longest, len(q), -1):
            for i in range(len(ctx) - size + 1):
                window = ctx[i : i + size]
                has_query = any(window[j : j + len(q)] == q for j in range(size - len(q) + 1))
                if has_query and window in terms:
                    add(terms[window])
    # Longer terms are more specific: show them first, the bare word last
    # (and, as long, the term spelled as asked first: "veiling glare" before "veiling glares")
    found.sort(key=lambda e: (-len(tokens(e["term"])), e["term"].lower() != text.lower()))
    # A longer selection ("the entrance pupil of a lens"): the terms inside it, longest first,
    # skipping words already covered by a longer term ("pupil" inside "entrance pupil")
    for q, _ in readings:
        covered = [q in terms] * len(q)
        for size in range(min(longest, len(q) - 1), 0, -1):
            for i in range(len(q) - size + 1):
                window = q[i : i + size]
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


def book_subject_words(doc_id: str | None) -> set[str]:
    """What the book being read is about, as words (stemmed: "optical" and "optics" are both
    "optic"): its shelves, its subject topic and its field, from catalog.csv."""
    import shelves  # its word matching, so a glossary matches the way shelves do

    row = catalog.load(LIBRARY / "catalog.csv").get(doc_id) if doc_id else None
    if not row:
        return set()
    return set(
        shelves.tokens(" ".join(str(row.get(k) or "") for k in ("shelves", "topic", "field")))
    )


def lookup(text: str, context: str = "", doc_id: str | None = None) -> dict:
    """Everything the popup shows for a double-clicked word or a selected phrase.

    A phrase that neither a glossary nor the dictionary knows also gets "words": each word's
    meaning (glossary meaning first), so an unknown phrase still says something useful.
    """
    text = re.sub(r"\s+", " ", text).strip().strip(".,;:!?()[]{}\"'“”‘’")[:100]
    matches = glossary_matches(text, context)
    own = frozenset(re.findall(r"[a-z0-9]+", text.lower()))
    # Reading a book: glossaries of its subject come first ("pupil" in an optics book: the
    # optics meaning before the biology one); longer, more specific terms still lead. A
    # glossary matches by its name or label ("optics", "光学 Optics") against the book's shelves,
    # subject and field ("Advanced optical system design", "Engineering")
    about = book_subject_words(doc_id)

    def rank(entry: dict) -> int:
        import shelves

        return 0 if set(shelves.tokens(f"{entry['glossary']} {entry['label']}")) & about else 1

    matches.sort(
        key=lambda e: (-len(tokens(e["term"])), rank(e), e["term"].lower() != text.lower())
    )
    result = {
        "query": text,
        "glossary": matches,
        # The same "same term" as adding it would use (B30, L23): the selection's own words
        # count as glossary words, so the popup never offers to add what it would refuse
        "in_glossary": any(tokens(g["term"], own) == tokens(text, own) for g in matches),
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


def _add_glossary_row(path: Path, term: str, row: list[str], label: str) -> None:
    """D16: one row more in glossary `path`, one writer at a time (the file's lock). The check
    for the term reads the file as it is now (not the cached glossary: another request may
    have just added it); the whole file is then written atomically (safe_io), keeping its BOM
    and line endings, with the row on a line of its own. A failed write changes nothing."""
    global _glossary_cache, _glossary_words_cache, _glossary_index_cache
    with safe_io.lock_for(path), safe_io.critical():
        data = safe_io.read_bytes(path) if safe_io.exists(path) else b""
        bom = data.startswith(codecs.BOM_UTF8)
        text = data[len(codecs.BOM_UTF8) :].decode("utf-8") if bom else data.decode("utf-8")
        eol = "\r\n" if "\r\n" in text else "\n"
        # The same "same term" as the glossary lookup's, as the glossary will be once this term
        # is in it (B30): lemma prefers a form a glossary uses, so with only "veiling glares"
        # stored, "glares" is its own base form and "veiling glare" looked like another term.
        # Counting the new term's words as glossary words gives both their shared base form,
        # whichever was stored first; that is the state lookup will see after the write.
        also = frozenset(re.findall(r"[a-z0-9]+", term.lower()))
        wanted = tuple(tokens(term, also))
        for existing in csv.DictReader(io.StringIO(text)):
            if tuple(tokens(existing.get("term") or "", also)) == wanted:
                raise ValueError(f"“{term}” is already in the {label} glossary")
        if not text.strip():
            text = "term,zh,note,definition" + eol
        elif not text.endswith(("\n", "\r")):
            text += eol  # (never joined to a last row without its line end)
        line = io.StringIO()
        csv.writer(line, lineterminator=eol).writerow(row)
        new = (codecs.BOM_UTF8 if bom else b"") + (text + line.getvalue()).encode("utf-8")
        safe_io.write_bytes(path, new)
    _glossary_cache = _glossary_words_cache = _glossary_index_cache = None  # (after the write)


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
    # Whether it's already there is decided once, under the file's lock, by _add_glossary_row
    # (B30): an earlier check here, on the cached glossary and without the new term's words,
    # used another "same term" and could refuse a term that check would add (focusing / focus)
    path = target["path"]
    _add_glossary_row(path, term, [term, zh, note, definition], target["label"])
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


def save_word(doc_id: str, title: str, text: str, context: str, page: int | None) -> dict:
    """Add a word to the document's notes/<name>/vocabulary.md (once per word), with its
    glossary meaning if a glossary has one (ranked by the document's subject, as in the popup),
    else the first lines of the dictionary entry."""
    row = catalog.load(LIBRARY / "catalog.csv").get(doc_id)
    if row is None:
        raise ValueError("no such document")
    # First, before anything else: never a vocabulary file outside the library's notes
    path = notes_store.notes_file(LIBRARY, row, "vocabulary.md")
    info = lookup(text, context, doc_id)
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
    path.parent.mkdir(parents=True, exist_ok=True)

    def cell(value) -> str:
        return str(value or "").replace("|", "/").replace("\n", " ").strip()

    row = (
        f"| {cell(word)} | {cell(entry.get('phonetic'))} | {cell(meaning)} | "
        f"{cell(page)} | {date.today().isoformat()} |\n"
    )
    # One save at a time (two words saved quickly from two tabs), the file replaced whole
    with safe_io.lock_for(path), safe_io.critical():
        existing = safe_io.read_text(path) if safe_io.exists(path) else ""
        if not existing:
            existing = VOCAB_HEADER.format(title=title)
        saved_words = {
            m[1].strip().lower() for m in re.finditer(r"^\| ([^|]+) \|", existing, re.MULTILINE)
        }
        if word.lower() in saved_words:
            return {"word": word, "saved": False, "file": path.relative_to(LIBRARY).as_posix()}
        safe_io.write_text(path, existing.rstrip("\n") + "\n" + row)
    return {"word": word, "saved": True, "file": path.relative_to(LIBRARY).as_posix()}


# --- your marks in the PDF -----------------------------------------------------------------


VERSION_RE = re.compile(r"[0-9a-f]{64}")  # a PDF's version: the SHA-256 of its bytes
MAX_UNCONFIRMED = 8  # a tab's saves that got no answer, named with its next save


class MarksConflict(Exception):
    """D5: the library's PDF isn't the version the marks were made on (another tab saved, OCR
    replaced it). Nothing was written to it; the tab's PDF is kept in `kept` (a path in the
    library), verified. `current` is the version on disk now."""

    def __init__(self, kept: str, current: str):
        super().__init__(
            "the PDF was changed elsewhere (another tab, or OCR), so your marks weren't "
            f"written into it; they are kept in {kept}"
        )
        self.kept, self.current = kept, current


class MarksNotKept(Exception):
    """The marks couldn't be written, or what was written couldn't be checked: never reported
    as saved (the tab keeps them as unsaved)."""


def _version(path: Path) -> str:
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def _whole_pdf(data: bytes) -> int:
    """The number of pages of a whole, readable PDF (ValueError otherwise)."""
    from pypdf import PdfReader

    if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-2048:]:
        raise ValueError("that isn't a whole PDF")
    try:
        return len(PdfReader(io.BytesIO(data)).pages)
    except Exception as e:
        raise ValueError(f"the marked PDF can't be read ({e})") from None


def _keep_conflict_copy(file: str, data: bytes) -> str:
    """The tab's PDF in archive/marks-conflicts/<its folder>/<name>.<time>.<random>.pdf: a new
    name each time (never over another copy), written whole (safe_io: atomic, flushed to disk
    as far as the system allows), then read back and compared. Called under the PDF's lock.
    Returns its path in the library; MarksNotKept if it couldn't be kept."""
    relative = Path(file)
    folder = LIBRARY / "archive" / "marks-conflicts" / relative.parent
    while True:  # (the PDF's lock is held: no other copy of this PDF is being named now)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        copy = folder / f"{relative.stem}.{stamp}.{uuid.uuid4().hex[:8]}{relative.suffix}"
        if not safe_io.exists(copy):
            break
    try:
        safe_io.write_bytes(copy, data)
        same = safe_io.read_bytes(copy) == data
    except OSError as e:
        raise MarksNotKept(
            f"your marks couldn't be kept ({e.strerror or e}): they are only in the tab"
        ) from None
    if not same:
        raise MarksNotKept("the copy of your marks couldn't be checked: they are only in the tab")
    return copy.relative_to(LIBRARY).as_posix()


def keep_marks_copy(file: str, data: bytes) -> dict:
    """After a conflict: one more copy of the tab's PDF (marks made since), never written into
    the library's PDF."""
    _whole_pdf(data)
    path = LIBRARY / file
    with safe_io.lock_for(path), safe_io.critical():
        return {"kept": _keep_conflict_copy(file, data)}


def save_marks(file: str, data: bytes, *, base: str, unconfirmed=()) -> dict:
    """Write the PDF with your highlights, drawings and notes (PDF.js's saveDocument: the
    PDF the tab loaded plus all its marks) over the library's copy, if the library's PDF is
    still `base`: the version the marks were made on. `unconfirmed`: versions of the tab's own
    earlier saves that got no answer; if one of them is the PDF now, it was the tab's own write
    and this save follows on it.

    Otherwise nothing is written to the PDF, the tab's PDF is kept (MarksConflict). The first
    time, the untouched original is kept in archive/before-marks/. Refused if it isn't a whole
    PDF with the same pages. Returns the new version, read back and checked."""
    if not isinstance(base, str) or not VERSION_RE.fullmatch(base):
        raise ValueError("a save of marks needs the version of the PDF they were made on")
    own = {v for v in unconfirmed if isinstance(v, str) and VERSION_RE.fullmatch(v)}
    new_pages = _whole_pdf(data)
    from pypdf import PdfReader

    path = LIBRARY / file
    original = LIBRARY / "archive" / "before-marks" / file
    # Checked and written in one step under the PDF's lock, which every app writer that
    # replaces the PDF also takes (OCR, bookmarks, a better copy: D15): none of them can swap
    # the PDF between the check and the write
    with safe_io.lock_for(path), safe_io.critical():  # quitting never cuts this off
        if not path.is_file():
            raise ValueError("the PDF isn't in the library any more")
        current = _version(path)
        if current != base and current not in own:  # changed elsewhere: theirs stays
            raise MarksConflict(_keep_conflict_copy(file, data), current)
        try:
            old_pages = len(PdfReader(path).pages)
        except Exception as e:
            raise ValueError(f"the library's PDF can't be read ({e})") from None
        if new_pages != old_pages:
            raise ValueError(f"the marked PDF has {new_pages} pages, the book {old_pages}")
        if not original.exists():  # copied whole or not at all: it's kept only once
            original.parent.mkdir(parents=True, exist_ok=True)
            part = original.with_name(original.name + ".part")
            shutil.copy2(path, part)
            part.replace(original)
        try:
            safe_io.write_bytes(path, data)
        except PermissionError:
            raise ValueError(
                "the PDF is open in another program; close it and mark again"
            ) from None
        try:
            written = safe_io.read_bytes(path) == data
        except OSError:
            written = False
        if not written:
            raise MarksNotKept(
                "the PDF was written but couldn't be checked: your marks stay unsaved in the tab"
            )
    return {"saved": True, "bytes": len(data), "version": hashlib.sha256(data).hexdigest()}


# --- serving the viewer -------------------------------------------------------------------


def viewer_html(token: str, scope: str = "", legacy_drafts: bool = False) -> bytes:
    """PDF.js's viewer page, with the lookup popup and the notes panel added (notes.js runs
    after lookup.js, whose helpers it uses, and after preview.js and markdown-it, when the
    latter is installed: without it, the preview shows the plain text). KaTeX (maths, M5b) is
    loaded before preview.js only when every file of it passes its check: without it, the
    preview shows the formulas as written and says why.

    `scope` is the library's key in this browser (libraries.scope): recovery drafts and the
    last note of a document are kept under it, so another library (a copy with the same
    document ids, or another library later on the same port) never sees them.
    `legacy_drafts`: drafts from before libraries had ids had no scope; only the default
    library shows them (it was the only one then)."""
    html = (PDFJS / "web" / "viewer.html").read_text(encoding="utf-8-sig")
    library = (
        '<script src="/vendor/markdown-it/markdown-it.min.js" defer></script>\n'
        if markdown_it_installed()
        else ""
    )
    maths, maths_style = (
        (
            '<script src="/vendor/katex/katex.min.js" defer></script>\n',
            '<link rel="stylesheet" href="/vendor/katex/katex.min.css">\n',
        )
        if katex_installed()
        else ("", "")
    )
    extra = (
        f"{maths_style}"
        '<link rel="stylesheet" href="/reader/lookup.css">\n'
        '<link rel="stylesheet" href="/reader/notes.css">\n'
        f"<script>window.MYLIBRARY_TOKEN = {token!r};"
        f" window.MYLIBRARY_SCOPE = {json.dumps(scope)};"
        f" window.MYLIBRARY_LEGACY_DRAFTS = {json.dumps(bool(legacy_drafts))};</script>\n"
        '<script src="/reader/lookup.js" defer></script>\n'
        '<script src="/reader/note_session.js" defer></script>\n'
        f"{library}"
        f"{maths}"
        '<script src="/reader/preview.js" defer></script>\n'
        '<script src="/reader/format.js" defer></script>\n'
        '<script src="/reader/notes.js" defer></script>\n'
    )
    return html.replace("</head>", extra + "</head>", 1).encode()


def static_file(url_path: str) -> tuple[bytes, str] | None:
    """/pdfjs/..., /reader/..., /vendor/markdown-it/... and /vendor/katex/... files; None for
    anything outside those folders."""
    for prefix, folder in (
        ("/pdfjs/", PDFJS), ("/reader/", STATIC), ("/vendor/markdown-it/", MARKDOWN_IT),
        ("/vendor/katex/", KATEX),
    ):  # fmt: skip
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
    parser.add_argument(
        "--setup-viewer",
        action="store_true",
        help="download and install only the PDF viewer (PDF.js), checksum verified",
    )
    parser.add_argument(
        "--setup-preview",
        action="store_true",
        help="download and install only the notes' preview (markdown-it), checksum verified",
    )
    parser.add_argument(
        "--setup-maths",
        action="store_true",
        help="download and install only the maths in the notes' preview (KaTeX), checksums "
        "verified",
    )
    parser.add_argument("word", nargs="*", help="look up a word or phrase")
    args = parser.parse_args()
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if args.setup_viewer:
        setup_viewer()
        return
    if args.setup_preview:
        setup_preview()
        return
    if args.setup_maths:
        setup_maths()
        return
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
