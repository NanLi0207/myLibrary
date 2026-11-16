"""Quote anchors (task 4 M6): where a quotation in a note came from, kept privately.

`<library>/.myLibrary/references/<document id>.json`, one file per SOURCE document, named by
its permanent id (never a slug): {"format": 1, "references": {rid: record}}. The note itself
gets only a short quote and a link (/read/<id>?page=N&ref=<rid>); the whole selection, its
context, positions and the PDF's fingerprint are here: not in git (.myLibrary/ is ignored), in
💾 backup, never in the public notes/ folder.

A record (DEVELOPMENT_SPEC 9.2; M7 finds the passage again from it, the structured-annotation
work links PDF marks to it through `nm`):
- `rid`, `doc` (the source PDF's id), `kind` ("text", or "page" for a page without usable text),
  `page` (page index, from 0; links count from 1), `pages`;
- text quotes: `exact` (the selection in the normalised page text: anchors.js normalize(),
  version `normalize`), `text` (as shown), `prefix`/`suffix` (context), `start`/`end` (offsets in
  the normalised page text, JavaScript string units), `page_len` and `page_hash` (SHA-256 of
  the normalised page text: equal means the offsets still hold, whatever happened to the file);
- `rects`: [x0, y0, x1, y1] relative to the page (0-1, top-left origin) in its unrotated PDF
  space, `page_size` [w, h] in PDF units and the page's own `rotation`, so PDF coordinates
  (QuadPoints) can be derived later;
- `fingerprint`: SHA-256 of the library's PDF when quoted (computed here); `loaded`: the version
  the tab had loaded (the bytes its text came from; differs when the PDF changed meanwhile);
  `pdfjs` / `pdfjs_version`: PDF.js's fingerprint of the file and its version (the text layer
  defines the offsets); `nm`: a PDF mark's /NM, later; `created`; `note` (where it was quoted
  into: a hint, never an identity); `nonce` (the request: a repeated request finds its record
  instead of making another).

Written only through safe_io.update_json (the file's lock, atomic replace, .bak of the last
good version). A damaged file is never replaced: its copy is kept, and the previous version is
used if it reads, else nothing is written (DamagedFile). A file of a newer format is refused.

Containment (Codex M6 review): the store stays inside the library's real folder. `.myLibrary`,
`references`, the file and its `.bak` must be a plain folder or file, never a symlink or junction
(the library folder itself may be one: the user's own arrangement, as for notes), and the file's
real path must be exactly where it is expected. Checked, under the file's lock, before each
folder is created, before anything is read or written (a read may write a `.damaged-*` copy)
and again afterwards; otherwise UnsafeStore, and nothing there is deleted, moved or replaced.
A frozen library (paths.FROZEN, also reached through a link) is refused before any folder is
made, the tree left exactly as it was (FrozenLocation).
What remains: a process that can write to the library could swap a junction in between the
check and the write (milliseconds). The check after the write detects such a redirect only if
it is still there when checked: it can't undo a write that already escaped, nor see a swap that
was put back before it. Such a process could change the notes themselves, so pinning the folder
(Windows handles) isn't attempted.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import secrets
import threading
from datetime import UTC, datetime
from pathlib import Path

import safe_io

FORMAT = 1
FOLDER = (".myLibrary", "references")
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
RID_RE = re.compile(r"r[0-9a-f]{16}")
HEX64_RE = re.compile(r"[0-9a-f]{64}")
NONCE_RE = re.compile(r"[0-9a-f]{32}")
PDFJS_RE = re.compile(r"[0-9a-fA-F]{0,64}")
VERSION_RE = re.compile(r"[0-9A-Za-z.+-]{0,32}")
MAX_BODY = 512 * 1024  # a create request (JSON); refused before it is read
MAX_TEXT = 20_000  # characters of a quoted selection
MAX_CONTEXT = 64  # prefix, suffix
MAX_RECTS = 500
MAX_PAGES = 100_000
MAX_PAGE_LEN = 2_000_000  # characters of a page's normalised text
MAX_SIZE = 100_000.0  # PDF units: a page's width or height
KINDS = ("text", "page")


class BadReference(ValueError):
    """A request that can't be stored as a reference: nothing was written."""


class UnsafeStore(Exception):
    """The references folder or file is a link or junction, or not a plain folder or file:
    nothing was read or written through it, and nothing there was changed."""


def path_for(library: Path, doc_id: str) -> Path:
    """The references file of a document: only ever named by a canonical document id."""
    if not isinstance(doc_id, str) or not UUID_RE.fullmatch(doc_id):
        raise BadReference("not a document id")
    return Path(library).joinpath(*FOLDER, f"{doc_id}.json")


def _real(path: Path) -> str:
    try:  # (safe_io.real_path: links are followed also past Windows' usual path limit)
        return os.path.normcase(str(safe_io.real_path(path)))
    except (OSError, RuntimeError) as e:  # a link loop, or a link that can't be followed
        raise UnsafeStore(f"{path.name} can't be followed ({e.__class__.__name__})") from None


def _redirected(path: Path) -> bool:
    os_path = safe_io._os_path(path)
    return os.path.islink(os_path) or os.path.isjunction(os_path)


def _checked(library: Path, doc_id: str, *, create: bool = False) -> Path:
    """path_for, once the store is known to be inside the library (see the module's
    docstring); with `create`, its missing folders are made, each one only after the folder
    it goes into was checked (never a folder made through a junction). UnsafeStore otherwise."""
    path = path_for(library, doc_id)
    if create:  # A frozen library (paths.FROZEN, also reached through a link) is refused before
        # any folder is made: safe_io's own refusal only comes with the write, after the mkdirs
        safe_io._refuse_frozen(path)
    shown = "/".join(FOLDER)
    fix = "make it a plain folder in the library again (nothing was read or written there)"
    root = _real(Path(library))
    if not os.path.isdir(root):
        raise UnsafeStore("the library's folder isn't there")
    here = Path(library)
    for name in FOLDER:
        here = here / name
        os_here = safe_io._os_path(here)
        if create and not os.path.lexists(os_here):
            try:
                os.mkdir(os_here)
            except FileExistsError:
                pass  # made meanwhile: checked below like any other
        if not os.path.lexists(os_here):
            break  # (not there yet: neither is anything in it)
        if _redirected(here) or not os.path.isdir(os_here):
            raise UnsafeStore(f"{shown}: {name} is a link or junction, or not a folder; {fix}")
    expected = os.path.join(root, *FOLDER)
    for file in (path, path.with_name(path.name + ".bak")):
        os_file = safe_io._os_path(file)
        if os.path.lexists(os_file) and (_redirected(file) or not os.path.isfile(os_file)):
            raise UnsafeStore(
                f"{shown}/{file.name} is a link or junction, or not a file; "
                "make it a plain file again (nothing was read or written)"
            )
        if _real(file) != os.path.normcase(os.path.join(expected, file.name)):
            raise UnsafeStore(f"{shown}/{file.name} leads out of the library; {fix}")
    return path


def empty() -> dict:
    """A new references file's content (a new object each time: update_json changes it)."""
    return {"format": FORMAT, "references": {}}


def load(library: Path, doc_id: str) -> dict:
    """The document's references ({rid: record}); {} when there are none. DamagedFile when the
    file and its previous version can't be read; BadReference for a newer format; UnsafeStore
    when the store isn't a plain folder in the library (checked before and after reading)."""
    path = path_for(library, doc_id)
    with safe_io.lock_for(path):
        _checked(library, doc_id)
        data = safe_io.load_json(path, empty())
        _checked(library, doc_id)  # (changed while reading: what was read isn't used)
    return _references(data)


def _references(data) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get("references"), dict):
        raise BadReference("the references file isn't in a form this version knows")
    if data.get("format") != FORMAT:
        raise BadReference("the references file was written by a newer myLibrary")
    return data["references"]


# --- the PDF's fingerprint -----------------------------------------------------------------

_digests: dict[str, tuple[tuple, str]] = {}
_digests_lock = threading.Lock()


def fingerprint(pdf: Path) -> str:
    """SHA-256 of the PDF as it is now, read under the PDF's own lock (every writer that
    replaces it takes that lock: marks, OCR). Remembered while the file stays the same (size,
    times and file id): hashing a large book again for every quote isn't needed."""
    with safe_io.lock_for(pdf):
        stat = os.stat(safe_io._os_path(pdf))
        same = (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino)
        key = os.path.normcase(str(pdf))
        with _digests_lock:
            known = _digests.get(key)
        if known and known[0] == same:
            return known[1]
        with open(safe_io._os_path(pdf), "rb") as f:
            digest = hashlib.file_digest(f, "sha256").hexdigest()
    with _digests_lock:
        _digests[key] = (same, digest)
    return digest


# --- checking what the page sent -----------------------------------------------------------


def _integer(body: dict, name: str, low: int, high: int) -> int:
    value = body.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise BadReference(f"bad {name}")
    return value


def _number(value, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise BadReference("not a number")
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise BadReference("a number out of range")
    return round(value, 6)


def _string(body: dict, name: str, limit: int, *, pattern: re.Pattern | None = None,
            required: bool = False) -> str:  # fmt: skip
    value = body.get(name, "")
    if not isinstance(value, str) or len(value) > limit:
        raise BadReference(f"bad {name}")
    if pattern is not None and not pattern.fullmatch(value):
        raise BadReference(f"bad {name}")
    if required and not value.strip():
        raise BadReference(f"no {name}")
    return value


def record_from(doc_id: str, body: dict) -> dict:
    """The record to store, built field by field from what the page sent (nothing else is
    kept); BadReference when any of it is missing, malformed or out of range."""
    if not isinstance(body, dict):
        raise BadReference("no reference")
    kind = body.get("kind")
    if kind not in KINDS:
        raise BadReference("bad kind")
    pages = _integer(body, "pages", 1, MAX_PAGES)
    size = body.get("page_size")
    if not isinstance(size, list) or len(size) != 2:
        raise BadReference("bad page_size")
    record = {
        "doc": doc_id,
        "kind": kind,
        "page": _integer(body, "page", 0, pages - 1),
        "pages": pages,
        "rotation": _integer(body, "rotation", 0, 270),
        "page_size": [_number(v, 1e-3, MAX_SIZE) for v in size],
        "normalize": _integer(body, "normalize", 1, 1000),
        "loaded": _string(body, "loaded", 64, pattern=re.compile(r"(?:[0-9a-f]{64})?")),
        "pdfjs": _string(body, "pdfjs", 64, pattern=PDFJS_RE),
        "pdfjs_version": _string(body, "pdfjs_version", 32, pattern=VERSION_RE),
        "nonce": _string(body, "nonce", 32, pattern=NONCE_RE),
        "nm": None,
    }
    if record["rotation"] % 90:
        raise BadReference("bad rotation")
    if kind == "page":
        return record
    page_len = _integer(body, "page_len", 1, MAX_PAGE_LEN)
    start = _integer(body, "start", 0, page_len)
    end = _integer(body, "end", start + 1, page_len)
    rects = body.get("rects")
    if not isinstance(rects, list) or len(rects) > MAX_RECTS:
        raise BadReference("bad rects")
    boxes = []
    for rect in rects:
        if not isinstance(rect, list) or len(rect) != 4:
            raise BadReference("bad rects")
        x0, y0, x1, y1 = (_number(v, 0.0, 1.0) for v in rect)
        if x0 > x1 or y0 > y1:
            raise BadReference("bad rects")
        boxes.append([x0, y0, x1, y1])
    record |= {
        "exact": _string(body, "exact", MAX_TEXT, required=True),
        "text": _string(body, "text", MAX_TEXT),
        "prefix": _string(body, "prefix", MAX_CONTEXT),
        "suffix": _string(body, "suffix", MAX_CONTEXT),
        "start": start,
        "end": end,
        "page_len": page_len,
        "page_hash": _string(body, "page_hash", 64, pattern=HEX64_RE),
        "rects": boxes,
    }
    return record


# --- storing ---------------------------------------------------------------------------------


def create(library: Path, row: dict, body: dict, note: dict) -> dict:
    """Store a reference for the document `row` (its PDF is the source) from the page's
    request, quoted into `note` ({doc, key}, already checked). Returns {"rid", "repeated"}:
    a repeated request (the same nonce) gets the record it made before, nothing new."""
    doc_id = row["id"]
    record = record_from(doc_id, body)
    # Hashed under the PDF's lock, which is let go before the references file's lock is taken:
    # the two are never held together
    record["fingerprint"] = fingerprint(Path(library) / row["file"])
    record["created"] = datetime.now(UTC).isoformat(timespec="seconds")
    record["note"] = {"doc": str(note["doc"]), "key": str(note["key"])}

    def add(data: dict):
        references = _references(data)  # (raises before anything is changed)
        for rid, earlier in references.items():
            if isinstance(earlier, dict) and earlier.get("nonce") == record["nonce"]:
                return {"rid": rid, "repeated": True}
        rid = "r" + secrets.token_hex(8)
        while rid in references:
            rid = "r" + secrets.token_hex(8)
        references[rid] = {"rid": rid, **record}
        return {"rid": rid, "repeated": False}

    path = path_for(library, doc_id)
    # The same spelling of the path for the lock as for update_json (which takes it again)
    with safe_io.lock_for(path):
        _checked(library, doc_id, create=True)  # before safe_io makes any folder (parents=True)
        made = safe_io.update_json(path, add, empty(), backup=True, indent=1)
        try:
            _checked(library, doc_id)
        except UnsafeStore as e:  # swapped in meanwhile: said so, nothing undone or deleted
            raise UnsafeStore(f"the references folder changed while saving: {e}") from None
    return made
