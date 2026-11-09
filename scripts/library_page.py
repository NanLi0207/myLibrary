"""Build library.html: a local web page for browsing catalog.csv and reading progress.

    uv run scripts/library_server.py   # full version: Read / Continue buttons, tick chapters
    uv run scripts/library_page.py     # static file (add_book.py also rebuilds it)
    start library.html                 # open the static file in your browser

Each document expands to its chapter checklist, read from its notes/<name>/README.md. On the
page, documents are known by their id (catalog.py), which every request to the server carries.
The static file is read-only; the server version can open everything for a chapter and
tick chapters off (see library_server.py).
"""

import json
import re
import tomllib
from pathlib import Path
from urllib.parse import quote

import catalog
import citation
import paths
import safe_io
import subjects
import thesis_meta
from book_ocr import has_text_layer
from ocr_pdf import ocr_minutes
from pypdf import PdfReader

LIBRARY = paths.LIBRARY
CATALOG = LIBRARY / "catalog.csv"
PAGE = LIBRARY / "library.html"

PAPER_ITEM = "Read the paper"  # a paper's one checklist item (counts as chapter 1)
PROGRESS_RE = re.compile(r"^- \[([ xX])\] (?:\[(.+?)\]\((.+?)\)|(.+))$", re.MULTILINE)
# Written by the reading view as you turn pages (library_server.save_position)
LAST_READ_RE = re.compile(
    r"^Last read: page (\d+)(?: \((.+)\))?, (\d{4}-\d{2}-\d{2})$", re.MULTILINE
)


def readme_of(row: dict) -> Path:
    """A document's notes README (details, progress, "Last read" line): <its notes>/README.md.
    notes_store.NoteError if the catalog's notes folder isn't under notes/, or the README is a
    link pointing out of it: progress is never read or written outside the library."""
    # Imported here, not at the top: notes_store imports this module (chapters_in), so a
    # top-level import here would be circular
    import notes_store

    return notes_store.notes_file(LIBRARY, row, "README.md")


def readme_path(doc_id: str) -> Path:
    """The notes README of the document with this id (KeyError if there is none)."""
    return readme_of(catalog.load(CATALOG)[doc_id])


def chapter_line(number: int, boxes: str = " xX") -> re.Pattern:
    """The checklist line of chapter `number` in a notes README ("Read the paper" is chapter 1),
    with one of `boxes` in its checkbox; group 1 is the text after the box."""
    paper = rf"|\[{re.escape(PAPER_ITEM)}\]" if number == 1 else ""
    return re.compile(rf"^- \[[{boxes}]\] (\[?Ch(?:apter)?\.?\s*{number}:{paper})", re.MULTILINE)


def last_read(doc_id: str, readme: Path | None = None) -> dict | None:
    """{page, chapter, date} from the "Last read:" line in the document's notes README."""
    readme = readme or readme_path(doc_id)
    if not readme.exists():
        return None
    m = LAST_READ_RE.search(safe_io.read_text(readme))
    return {"page": int(m[1]), "chapter": m[2] or "", "date": m[3]} if m else None


def chapters(doc_id: str, readme: Path | None = None) -> list[dict]:
    readme = readme or readme_path(doc_id)
    return chapters_in(safe_io.read_text(readme)) if readme.exists() else []


def chapters_in(text: str) -> list[dict]:
    """The checklist of a notes README: [{done, title, number, note}]."""
    result = []
    for m in PROGRESS_RE.finditer(text):
        title = m[2] or m[4]
        number = re.match(r"(?:Ch(?:apter)?\.?\s*)(\d+)", title)
        result.append(
            {
                "done": m[1] != " ",
                "title": title,
                "number": int(number[1]) if number else (1 if title == PAPER_ITEM else None),
                "note": m[3] or "",
            }
        )
    return result


def shelf_labels() -> dict[str, str]:
    """{shelf: label} from the library's library.toml, e.g. {"Optics": "光学 Optics"}."""
    path = LIBRARY / "library.toml"
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        shelves = tomllib.load(f).get("shelves", {})
    return {str(k): str(v) for k, v in shelves.items()} if isinstance(shelves, dict) else {}


_scans: dict[str, tuple[tuple, bool, int]] = {}


def scan_info(pdf: Path) -> tuple[bool, int]:
    """(is it a scan without a text layer, pages); remembered until the file changes."""
    if not pdf.exists():
        return False, 0
    stat = pdf.stat()
    key = (stat.st_size, stat.st_mtime_ns)
    cached = _scans.get(str(pdf))
    if cached and cached[0] == key:
        return cached[1], cached[2]
    try:
        reader = PdfReader(pdf)
        info = (not has_text_layer(reader), len(reader.pages))
    except Exception:  # a damaged PDF: just no OCR button
        info = (False, 0)
    _scans[str(pdf)] = (key, *info)
    return info


def _mtime(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


def books(pdf_base: str | None = None) -> list[dict]:
    """Catalog rows plus chapter progress; pdf_base is the server URL prefix for PDFs."""
    import notes_store  # (see readme_of)

    result = []
    for row in catalog.load(CATALOG).values():
        pdf = LIBRARY / row["file"]
        try:
            readme, notes_problem = readme_of(row), ""
        except notes_store.NoteError as e:  # shown without progress or notes, never others lost
            readme, notes_problem = None, str(e)
        scan, pages = scan_info(pdf)
        # The reading view is told which document it shows (its id), whatever the file's name
        reader = f"{pdf_base}/{row['file']}" + ("&id=" + row["id"] if "?file=" in (pdf_base or "")
                                                else "") if pdf_base else ""  # fmt: skip
        result.append(
            row
            | {
                "chapter_list": chapters(row["id"], readme) if readme else [],
                "shelf_list": catalog.split_list(row.get("shelves") or ""),
                "kind": row.get("type") or "book",
                "field_label": subjects.field_label(row.get("field") or ""),
                "citations": citation.all_formats(row),
                "scan": scan,
                "ocr_minutes": max(1, round(ocr_minutes(pages))),
                "last_read": last_read(row["id"], readme) if readme else None,
                # When the notes README last changed (reading position, ticks): orders books
                # read on the same day for "Sort: recently read"
                "touched": _mtime(readme) if readme else 0.0,
                "pdf_missing": not pdf.exists(),
                "pdf_uri": reader or pdf.as_uri(),
                "notes_uri": ""
                if notes_problem
                else "vscode://file/" + quote(readme.parent.as_posix(), safe="/:"),
                "notes_problem": notes_problem,
                # (the bad value itself may be a full path: not put on the page; catalog.csv
                # keeps it, untouched, for the user to correct)
                **({"notes": ""} if notes_problem else {}),
            }
        )
    return result


def render(api: dict | None = None, pdf_base: str | None = None) -> str:
    """The page HTML; with `api` (from library_server.py) the Read buttons are enabled."""
    data = json.dumps(books(pdf_base), ensure_ascii=False).replace("</", "<\\/")
    labels = json.dumps(shelf_labels(), ensure_ascii=False).replace("</", "<\\/")
    return (
        TEMPLATE.replace("__DEGREE_LABELS__", json.dumps(thesis_meta.DEGREE_LABELS))
        .replace("__DATA__", data)
        .replace("__API__", json.dumps(api))
        .replace("__SHELF_LABELS__", labels)
    )


def build() -> Path:
    safe_io.write_text(PAGE, render())
    return PAGE


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>myLibrary</title>
<style>
:root {
  --bg: #f6f5f2; --surface: #ffffff; --text: #1d1d1b; --muted: #6b6a66; --line: #e3e1db;
  --accent: #2f5d8a; --accent-soft: #e6eef6; --done: #3b7a4a; --bar: #e9e7e1; --warn: #a3561c;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #161716; --surface: #1f201f; --text: #ecebe7; --muted: #9c9b96; --line: #33342f;
    --accent: #8db6dd; --accent-soft: #24303b; --done: #79b787; --bar: #2c2d2a; --warn: #e0a06a;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1100px; margin: 0 auto; padding: 32px 16px 64px; }
header h1 { margin: 0 0 4px; font-size: 26px; letter-spacing: -0.01em; }
.stats { color: var(--muted); margin: 0 0 20px; }
/* Search, menus and Cards/List on one line; the search box gives way first, and a long menu
   (e.g. a field name) is cut short rather than pushing the rest onto a second line */
.controls { display: flex; gap: 8px; flex-wrap: nowrap; align-items: stretch; margin: -10px 0 10px;
  padding: 10px 0; position: sticky; top: 0; z-index: 30; background: var(--bg); }
/* It stays at the top while you scroll; a thin line then separates it from the cards */
.controls.stuck { border-bottom: 1px solid var(--line); box-shadow: 0 6px 8px -8px rgba(0, 0, 0, 0.25); }
.controls input, .controls select { font: inherit; color: var(--text); background: var(--surface);
  border: 1px solid var(--line); border-radius: 8px; padding: 9px 12px; min-width: 0; }
.controls input { flex: 1 1 200px; }
.controls select { flex: 0 1 auto; max-width: 240px; text-overflow: ellipsis; }
.controls .view { flex: none; }
@media (max-width: 760px) {  /* four lines on a phone: too tall to keep at the top */
  .controls { flex-wrap: wrap; position: static; }
  .controls input { flex-basis: 100%; }
}
.grid { display: grid; gap: 14px; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); }
/* ☰ List mode: one row per book, paper or thesis; a row unfolds into its card */
.view { display: inline-flex; border: 1px solid var(--line); border-radius: 8px; overflow: hidden;
  background: var(--surface); }
.view button { font: inherit; font-size: 13.5px; border: 0; background: none; color: var(--muted);
  padding: 0 12px; cursor: pointer; }
.view button[aria-pressed="true"] { background: var(--accent-soft); color: var(--accent); font-weight: 600; }
.grid.list { display: block; background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
  overflow: hidden; }
.list-info { display: flex; justify-content: space-between; align-items: center; gap: 10px;
  padding: 8px 14px; font-size: 12.5px; color: var(--muted); border-bottom: 1px solid var(--line); }
.list-info button { font: inherit; font-size: 12.5px; color: var(--accent); background: none;
  border: 1px solid var(--line); border-radius: 7px; padding: 2px 9px; cursor: pointer; }
.lrow, .lhead { display: grid; align-items: center; gap: 12px; padding: 9px 14px;
  grid-template-columns: 74px minmax(0, 1fr) 168px 128px 92px 112px; }
.lhead { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .04em;
  border-bottom: 1px solid var(--line); padding-top: 7px; padding-bottom: 7px; }
.lhead button { font: inherit; color: inherit; text-transform: inherit; letter-spacing: inherit;
  background: none; border: 0; padding: 0; cursor: pointer; text-align: left; }
.lhead button.on { color: var(--accent); font-weight: 600; }
.litem { border-bottom: 1px solid var(--line); }
.litem:last-child { border-bottom: 0; }
.lrow { cursor: pointer; }
.lrow:hover, .litem.open .lrow { background: var(--accent-soft); }
.lrow:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
.lrow .kind { font-size: 11.5px; color: var(--accent); font-weight: 600; line-height: 1.25; }
.lrow .kind::before { content: "▸ "; color: var(--muted); font-weight: 400; }
.litem.open .lrow .kind::before { content: "▾ "; }
.lrow .ttl { font-weight: 600; font-size: 14.5px; line-height: 1.3; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; }
.lrow .sub { color: var(--muted); font-size: 12.5px; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; margin-top: 2px; }
.lrow .sub .tag { color: var(--done); border: 1px solid currentColor; border-radius: 6px;
  padding: 0 6px; margin-left: 8px; font-size: 11.5px; }
.lrow .ident { font-size: 12.5px; color: var(--muted); overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; font-variant-numeric: tabular-nums; }
.lrow .ident a { color: var(--accent); text-decoration: none; }
.lrow .prog { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
.lrow .prog .bar { flex: none; width: 100%; }
.lrow .last { font-size: 12px; color: var(--muted); }
.lrow .go button.read { font: inherit; font-size: 12.5px; cursor: pointer; border-radius: 7px;
  padding: 4px 10px; border: 1px solid var(--line); background: var(--surface); color: var(--accent);
  white-space: nowrap; width: 100%; }
.lrow .go button.read[data-resume] { border-color: var(--accent); background: var(--accent); color: #fff; }
.ldetail { padding: 4px 14px 14px; background: var(--accent-soft); }
/* The whole width of the list: as few lines as possible (keywords and tags on one line) */
.ldetail .card { max-width: none; }
.byline.inline { display: flex; flex-wrap: wrap; gap: 4px 14px; align-items: baseline; }
.byline.inline .meta { display: inline-flex; }
@media (max-width: 760px) {
  .lrow, .lhead { grid-template-columns: 64px minmax(0, 1fr) 96px; }
  .lrow .ident, .lrow .last, .lrow .go, .lhead .ident, .lhead .last, .lhead .go { display: none; }
}
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
  padding: 16px 18px; display: flex; flex-direction: column; gap: 8px; }
.card h2 { margin: 0; font-size: 17px; line-height: 1.3; }
/* The kind, in front of the title: "Paper", "PhD thesis" */
.kind-tag { display: inline-block; font-size: 11.5px; font-weight: 600; color: var(--accent);
  background: var(--accent-soft); border-radius: 6px; padding: 1px 7px; margin-right: 7px;
  vertical-align: 2px; white-space: nowrap; }
.meta a { color: var(--accent); text-decoration: none; }
.meta a:hover { text-decoration: underline; }
.byline { color: var(--muted); font-size: 14px; }
.subject { color: var(--muted); font-size: 12.5px; }
.chips .subject { align-self: center; }  /* "工程 Engineering ›" before its shelf tag */
.meta { display: flex; gap: 14px; flex-wrap: wrap; color: var(--muted); font-size: 13px; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip.shelf { background: var(--done); color: #fff; }
.chip.kw { background: none; color: var(--muted); border: 1px solid var(--line); }
.cite-wrap { position: relative; display: inline-flex; }
.cite-menu { position: absolute; top: calc(100% + 4px); right: 0; z-index: 20; width: min(440px, 80vw);
  background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 6px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15); display: flex; flex-direction: column; gap: 2px; }
.cite-menu button { display: flex; flex-direction: column; gap: 2px; text-align: left; font: inherit;
  font-size: 12.5px; color: var(--text); background: none; border: 0; border-radius: 7px;
  padding: 6px 8px; cursor: pointer; }
.cite-menu button:hover { background: var(--accent-soft); }
.cite-menu b { color: var(--accent); font-size: 12.5px; }
.cite-menu span { color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.shelves { display: flex; gap: 8px; flex-wrap: wrap; margin: 0 0 16px; }
.shelves button { font: inherit; font-size: 13px; cursor: pointer; color: var(--accent);
  background: none; border: 1px solid var(--line); border-radius: 999px; padding: 3px 12px; }
.shelves button.on { background: var(--accent); border-color: var(--accent); color: #fff; }
.shelves .count { opacity: 0.7; margin-left: 4px; }
.chip { background: var(--accent-soft); color: var(--accent); border-radius: 999px;
  padding: 2px 9px; font-size: 12px; }
.progress { display: flex; align-items: center; gap: 10px; font-size: 13px; color: var(--muted); }
.bar { flex: 1; height: 6px; background: var(--bar); border-radius: 3px; overflow: hidden; }
.bar span { display: block; height: 100%; background: var(--done); }
.actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 2px; }
.actions a, .actions button { font: inherit; font-size: 13px; text-decoration: none; cursor: pointer;
  color: var(--accent); background: none; border: 1px solid var(--line); border-radius: 7px;
  padding: 5px 10px; }
.actions a:hover, .actions button:hover { border-color: var(--accent); }
.actions .read, .actions .primary { background: var(--accent); color: var(--surface);
  border-color: var(--accent); font-weight: 600; }
.actions .read:hover, .actions .primary:hover { filter: brightness(1.1); }
.actions .missing { font-size: 13px; color: var(--warn); border: 1px dashed var(--warn);
  border-radius: 7px; padding: 5px 10px; cursor: help; }
.next { font-size: 13px; color: var(--muted); }
ol.chapters { margin: 4px 0 0; padding: 10px 0 0; border-top: 1px solid var(--line);
  list-style: none; font-size: 13.5px; max-height: 340px; overflow: auto; }
ol.chapters li { display: flex; align-items: center; gap: 8px; padding: 2px 0; }
ol.chapters li.done .name { color: var(--muted); }
ol.chapters .tick { width: 1.2em; flex: none; color: var(--done); }
ol.chapters input { flex: none; margin: 0; accent-color: var(--done); cursor: pointer; }
ol.chapters .name { flex: 1; }
ol.chapters button { flex: none; font: inherit; font-size: 12px; cursor: pointer; color: var(--accent);
  background: none; border: 1px solid transparent; border-radius: 6px; padding: 1px 7px; }
ol.chapters li:hover button { border-color: var(--line); }
.toast { position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%); max-width: calc(100% - 32px);
  background: var(--text); color: var(--bg); padding: 10px 16px; border-radius: 10px; font-size: 14px;
  box-shadow: 0 6px 24px rgb(0 0 0 / 0.2); opacity: 0; transition: opacity .2s; pointer-events: none; }
.toast.show { opacity: 1; }
/* ↑ Back to the top: shown once you've scrolled down */
.to-top { position: fixed; right: 24px; bottom: 24px; z-index: 40; width: 44px; height: 44px;
  border-radius: 50%; border: 1px solid var(--line); background: var(--surface); color: var(--accent);
  font-size: 20px; cursor: pointer; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.12); }
.to-top:hover { border-color: var(--accent); }
.to-top[hidden] { display: none; }
@media (max-width: 760px) { .to-top { right: 16px; bottom: 16px; } }
/* Drag PDFs anywhere onto the page to add them */
.dropzone { position: fixed; inset: 12px; z-index: 50; display: flex; align-items: center;
  justify-content: center; text-align: center; border: 3px dashed var(--accent); border-radius: 16px;
  background: color-mix(in srgb, var(--accent-soft) 88%, transparent); color: var(--accent);
  font-size: 20px; font-weight: 600; pointer-events: none; padding: 16px; }
.dropzone small { display: block; font-size: 14px; font-weight: 400; color: var(--muted); margin-top: 6px; }
.dropzone[hidden] { display: none; }
.empty { color: var(--muted); padding: 40px 0; text-align: center; }
footer { color: var(--muted); font-size: 12.5px; margin-top: 28px; }
.topbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.tools { display: flex; gap: 8px; flex-wrap: wrap; }
.tool { font: inherit; font-size: 13px; cursor: pointer; color: var(--accent); background: var(--surface);
  border: 1px solid var(--line); border-radius: 8px; padding: 6px 12px; }
.tool:hover { border-color: var(--accent); }
.jobs { display: flex; flex-direction: column; gap: 8px; margin: 0 0 16px; }
.job { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 10px 14px;
  font-size: 13.5px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.job .bar { flex: 1 1 160px; }
/* Finished jobs fold away under "History" */
.history-bar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 13px;
  color: var(--muted); }
.history-bar button { font: inherit; font-size: 13px; cursor: pointer; color: var(--accent);
  background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 4px 11px; }
.history-bar button:hover { border-color: var(--accent); }
.history-bar .problems { color: var(--warn); }
.history-bar .latest { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1 1 200px; }
.history { display: flex; flex-direction: column; gap: 6px; }
.history .job { padding: 6px 12px; font-size: 13px; }
.history[hidden] { display: none; }
.job.error { border-color: var(--warn); color: var(--warn); }
.job button { font: inherit; font-size: 12.5px; cursor: pointer; color: var(--accent);
  background: none; border: 1px solid var(--line); border-radius: 7px; padding: 2px 9px; }
dialog { border: 1px solid var(--line); border-radius: 12px; background: var(--surface); color: var(--text);
  width: min(560px, calc(100vw - 32px)); padding: 20px 22px; }
dialog::backdrop { background: rgba(0, 0, 0, 0.35); }
dialog h2 { margin: 0 0 14px; font-size: 19px; }
dialog label { display: block; font-size: 13.5px; margin: 12px 0 4px; }
dialog input[type=text], dialog select { width: 100%; font: inherit; font-size: 13.5px; padding: 6px 8px;
  border: 1px solid var(--line); border-radius: 7px; background: var(--bg); color: var(--text); }
dialog .row { display: flex; gap: 8px; }
dialog .row input { flex: 1; }
dialog .end { justify-content: flex-end; margin-top: 20px; }
dialog button { font: inherit; font-size: 13.5px; cursor: pointer; border-radius: 7px; padding: 6px 14px;
  border: 1px solid var(--line); background: none; color: var(--accent); }
dialog button.primary { background: var(--accent); border-color: var(--accent); color: var(--surface); }
dialog .hint { color: var(--muted); font-size: 12.5px; margin: 4px 0 0; }
dialog .check { display: flex; align-items: center; gap: 8px; }
dialog .archive-row { align-items: center; justify-content: space-between; font-size: 13.5px; }
/* 🔎 Find online */
dialog.find { width: min(860px, calc(100vw - 32px)); max-height: calc(100vh - 48px); }
.find form { display: flex; gap: 8px; }
.find form input { flex: 1; font-size: 15px !important; padding: 8px 10px !important; }
.find .hint { margin-top: 6px; }
.find .engines { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0 4px; font-size: 12.5px;
  align-items: center; color: var(--muted); }
.find .engines a { color: var(--accent); border: 1px solid var(--line); border-radius: 7px;
  padding: 2px 8px; text-decoration: none; }
.find h3 { font-size: 14px; margin: 18px 0 6px; color: var(--muted); font-weight: 600; }
.find .result { border-top: 1px solid var(--line); padding: 10px 0; }
.find .result .t { font-weight: 600; font-size: 14.5px; color: var(--text); text-decoration: none; }
.find .result a.t:hover { color: var(--accent); }
.find .result .who { font-size: 13px; color: var(--muted); margin-top: 2px; }
.find .result .acts { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; align-items: center;
  font-size: 12.5px; }
.find .result .acts a, .find .result .acts button { font-size: 12.5px; padding: 2px 9px;
  border: 1px solid var(--line); border-radius: 7px; color: var(--accent); text-decoration: none;
  background: none; cursor: pointer; }
.find .result .acts button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
.find .chip-kind { font-size: 11.5px; border-radius: 6px; padding: 1px 7px; background: var(--accent-soft);
  color: var(--accent); }
.find .owned { font-size: 12px; color: var(--done); font-weight: 600; }
.find .status { color: var(--muted); font-size: 13.5px; margin: 14px 0; }
.empty button { font: inherit; color: var(--accent); background: none; border: 1px solid var(--line);
  border-radius: 7px; padding: 3px 10px; cursor: pointer; margin-left: 6px; }
/* 📇 Review words */
.tool .count { font-size: 11.5px; background: var(--accent); color: var(--surface); border-radius: 9px;
  padding: 0 6px; margin-left: 5px; }
.tool .count[hidden] { display: none; }
dialog.review { width: min(520px, calc(100vw - 32px)); }
dialog.libraries { width: min(640px, calc(100vw - 32px)); max-height: calc(100vh - 48px); }
.libraries h2 small, .libraries .modes small { font-size: 13px; font-weight: normal; color: var(--muted); }
.libraries .modes { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.libraries .modes button { padding: 18px 12px; display: flex; flex-direction: column; gap: 4px; font-size: 16px; }
.libraries ul { list-style: none; padding: 0; margin: 0 0 12px; }
.libraries li { border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; margin-bottom: 8px; }
.libraries li .where { color: var(--muted); font-size: 12px; word-break: break-all; }
.libraries li .badge { font-size: 11.5px; color: var(--muted); border: 1px solid var(--line); border-radius: 6px; padding: 0 5px; margin-left: 6px; }
.libraries li .row { margin-top: 6px; flex-wrap: wrap; }
.libraries li.gone { opacity: 0.75; }
.libraries .report { font-size: 12.5px; margin-top: 8px; }
.libraries .report .bad { color: #b3261e; }
.test-banner { background: #fff4ce; color: #3d3100; border: 1px solid #e5c44a; border-radius: 8px; padding: 6px 10px;
  margin: 0 0 10px; font-size: 13.5px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.test-banner button { font: inherit; font-size: 12.5px; cursor: pointer; }
.test-banner[hidden] { display: none; }
.review .top { display: flex; justify-content: space-between; align-items: center; gap: 10px;
  font-size: 13px; color: var(--muted); }
.review .top h2 { margin: 0; }
.review .top h2 small { font-size: 13px; font-weight: normal; color: var(--muted); }
.review .top select { width: auto; max-width: 55%; }
.review .flash { margin: 18px 0 6px; padding: 26px 20px; border: 1px solid var(--line);
  border-radius: 12px; background: var(--bg); text-align: center; min-height: 170px; }
.review .word { font-size: 30px; font-weight: 600; margin: 0; overflow-wrap: anywhere; }
.review .phon { color: var(--muted); font-size: 14px; margin: 6px 0 0; }
.review .phon button { border: none; padding: 0 4px; font-size: 16px; }
.review .zh { font-size: 17px; margin: 18px 0 6px; line-height: 1.5; }
.review .seen { font-size: 12.5px; color: var(--muted); }
.review .seen a { color: var(--accent); }
.review .answers { display: flex; gap: 10px; justify-content: center; margin-top: 16px; }
.review .answers[hidden], .review .show[hidden] { display: none; }
.review .answers button { flex: 1; max-width: 190px; padding: 9px 14px; }
.review .answers .no { color: var(--warn); border-color: var(--warn); }
.review .answers small, .review .show small { display: block; font-size: 11.5px; opacity: 0.75; }
.review .show { display: block; margin: 16px auto 0; min-width: 200px; padding: 9px 14px; }
.review .finished { text-align: center; padding: 20px 0 6px; line-height: 1.6; }
/* 📈 Reading log */
.log-link { font: inherit; color: var(--accent); background: none; border: none; padding: 0;
  margin-left: 6px; cursor: pointer; }
.log-link:hover { text-decoration: underline; }
.log-link[hidden] { display: none; }
dialog.log { width: min(720px, calc(100vw - 32px)); max-height: calc(100vh - 48px); }
.log h3 { font-size: 14px; margin: 22px 0 8px; color: var(--muted); font-weight: 600; }
.log .heroes { display: flex; flex-wrap: wrap; gap: 10px; }
.log .hero { flex: 1 1 130px; border: 1px solid var(--line); border-radius: 10px; padding: 10px 14px; }
.log .hero b { display: block; font-size: 24px; font-weight: 600; line-height: 1.2; color: var(--text); }
.log .hero span { font-size: 12.5px; color: var(--muted); }
.log .cal-wrap { overflow-x: auto; padding-bottom: 4px; }
.log .cal { display: grid; grid-template-rows: repeat(7, 12px); grid-auto-flow: column;
  grid-auto-columns: 12px; gap: 3px; width: max-content; }
.log .cal i { border-radius: 3px; background: var(--bar); }
.log .cal i.future { background: none; }
.log .cal i.today { outline: 1.5px solid var(--text); outline-offset: 1px; }
.log .cal i[data-l="1"] { background: color-mix(in srgb, var(--done) 30%, var(--bar)); }
.log .cal i[data-l="2"] { background: color-mix(in srgb, var(--done) 55%, var(--bar)); }
.log .cal i[data-l="3"] { background: color-mix(in srgb, var(--done) 78%, var(--bar)); }
.log .cal i[data-l="4"] { background: var(--done); }
.log .cal-key { display: flex; align-items: center; gap: 3px; font-size: 12px; color: var(--muted);
  margin-top: 6px; justify-content: flex-end; }
.log .cal-key i { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
.log .months { display: grid; grid-auto-flow: column; grid-auto-columns: 15px; font-size: 11px;
  color: var(--muted); height: 15px; width: max-content; }
.log table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
.log td { padding: 5px 6px; border-top: 1px solid var(--line); vertical-align: middle; }
.log td.num { text-align: right; white-space: nowrap; color: var(--muted); font-variant-numeric: tabular-nums; }
.log td.len { width: 28%; }
.log td.len span { display: block; height: 6px; border-radius: 0 3px 3px 0; background: var(--done); min-width: 2px; }
@media (max-width: 560px) { .log td.len, .log td.days { display: none; } }
.log .empty-log { color: var(--muted); font-size: 13.5px; }
.log-tip { position: fixed; z-index: 50; pointer-events: none; background: var(--surface); color: var(--text);
  border: 1px solid var(--line); border-radius: 7px; padding: 4px 9px; font-size: 12.5px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15); white-space: nowrap; }
.log-tip[hidden] { display: none; }
.stopped { margin: 15vh auto; max-width: 520px; text-align: center; line-height: 1.6; }
code { font-size: 12.5px; }
</style>
</head>
<body>
<main>
  <header>
    <div class="test-banner" id="testBanner" hidden><b>🧪 测试/示例书库 (Test &amp; Demo library)</b>
      <span>这里的改动不会影响你的私人书库 (changes here never touch your personal libraries)</span>
      <button type="button" id="bannerModes">书库模式 (Library modes)</button></div>
    <div class="topbar"><h1>myLibrary</h1><div class="tools" id="tools"></div></div>
    <p class="stats"><span id="stats"></span><button type="button" class="log-link" id="openLog" hidden></button></p>
  </header>
  <div class="controls">
    <input id="q" type="search" placeholder="Search title, author, journal, university, ISBN, DOI, subject, chapter…" autofocus>
    <select id="kind" aria-label="Show">
      <option value="">All</option>
      <option value="book">Books</option>
      <option value="paper">Papers</option>
      <option value="thesis">Theses</option>
    </select>
    <select id="field" aria-label="Field" title="The subject field (from OpenAlex)" hidden></select>
    <select id="sort">
      <option value="title">Sort: title</option>
      <option value="author">Sort: author</option>
      <option value="year">Sort: newest</option>
      <option value="progress">Sort: progress</option>
      <option value="added">Sort: recently added</option>
      <option value="recent">Sort: recently read</option>
    </select>
    <div class="view" role="group" aria-label="View">
      <button type="button" data-view="cards" title="One card per book">▦ Cards</button>
      <button type="button" data-view="list" title="One line per book; click a line to see its card">☰ List</button>
    </div>
  </div>
  <section class="jobs" id="jobs" hidden></section>
  <nav class="shelves" id="shelves" aria-label="Shelves"></nav>
  <div class="grid" id="grid"></div>
  <footer id="footer"></footer>
</main>
<div class="toast" id="toast" role="status"></div>
<button type="button" class="to-top" id="toTop" title="Back to the top" aria-label="Back to the top" hidden>↑</button>
<dialog id="findDialog" class="find">
  <h2>Find online</h2>
  <form id="findForm">
    <input type="text" id="findQuery" placeholder="DOI, arXiv number, ISBN, title, author, topic…" autocomplete="off">
    <button type="submit" class="primary">Search</button>
    <button type="button" id="findClose">Close</button>
  </form>
  <p class="hint">Searches OpenAlex (papers, books, theses), Crossref, arXiv and Open Library.
    <b>＋ Add to library</b> appears when a free, legal copy (open access) can be downloaded.</p>
  <div class="engines" id="findEngines"></div>
  <div id="findResults"></div>
</dialog>
<dialog id="logDialog" class="log">
  <h2>阅读记录 <small style="font-size:13px;font-weight:normal;color:var(--muted)">Reading log</small></h2>
  <div id="logBody"></div>
  <div class="row end"><button type="button" id="logClose">关闭 Close</button></div>
</dialog>
<div class="log-tip" id="logTip" hidden></div>
<dialog id="reviewDialog" class="review">
  <div class="top">
    <h2>复习生词 <small>Review words</small></h2>
    <select id="reviewBook" title="Which words: all books, or one book"></select>
  </div>
  <div id="reviewBody"></div>
  <div class="row end"><button type="button" id="reviewClose">关闭 Close</button></div>
</dialog>
<div class="dropzone" id="dropzone" hidden>
  <div>Drop PDFs here to add them<small>Books, papers and theses are recognised automatically</small></div>
</div>
<dialog id="librariesDialog" class="libraries">
  <section id="libModes">
    <h2>选择书库模式 <small>Choose a Library Mode</small></h2>
    <div class="modes">
      <button type="button" data-mode="personal"><b>私人书库</b><small>Personal Libraries</small></button>
      <button type="button" data-mode="test"><b>测试/示例书库</b><small>Test &amp; Demo Library</small></button>
    </div>
  </section>
  <section id="libPersonal" hidden>
    <h2>私人书库 <small>Personal Libraries</small></h2>
    <ul id="libList"></ul>
    <label for="libFolder">文件夹 (Folder): 添加已有书库或新建书库 (to add an existing library, or create a new one)</label>
    <div class="row"><input type="text" id="libFolder" placeholder="D:\Books\My library">
      <button type="button" id="libPick">选择… (Choose…)</button></div>
    <label for="libLabel">名称 (Label, optional)</label>
    <input type="text" id="libLabel" placeholder="光学研究 Optics Research">
    <div class="row" style="margin-top:10px">
      <button type="button" id="libAdd">添加已有书库 (Add existing)</button>
      <button type="button" id="libCreate">新建书库 (Create new)</button></div>
    <p class="hint">添加只读取文件夹，不改动任何内容；移出列表也不会删除文件 (Adding only reads the folder;
      removing from the list never deletes anything).</p>
    <div class="report" id="libReport"></div>
  </section>
  <div class="row end"><button type="button" id="libBack">← 书库模式 (Library modes)</button>
    <button type="button" id="libClose">关闭 (Close)</button></div>
</dialog>
<dialog id="settingsDialog">
  <form method="dialog" id="settingsForm">
    <h2>Settings</h2>
    <label for="setLibrary">Library folder: where your books and notes are kept</label>
    <div class="row"><input type="text" id="setLibrary"><button type="button" id="pickFolder">Choose…</button></div>
    <p class="hint">Choosing another folder opens the library there, or starts a new, empty one.
      Your current library stays where it is.</p>
    <label for="setEditor">Open notes with</label>
    <select id="setEditor">
      <option value="system">The app set for .md files (e.g. Typora, Obsidian, Notepad)</option>
      <option value="notepad">Notepad</option>
      <option value="vscode">VS Code</option>
      <option value="custom">My own command…</option>
    </select>
    <div id="customRow" hidden>
      <label for="setCommand">Command ({file} is replaced by the note's path)</label>
      <input type="text" id="setCommand" placeholder='"C:\Program Files\Typora\Typora.exe" "{file}"'>
    </div>
    <label class="check"><input type="checkbox" id="setPython"> Show the Python features
      (a script per chapter, for checking a book's worked examples)</label>
    <label for="setBackup">💾 Backup folder: e.g. on OneDrive or a USB stick</label>
    <div class="row"><input type="text" id="setBackup" placeholder="Not backed up yet: choose a folder">
      <button type="button" id="pickBackup">Choose…</button></div>
    <label class="check"><input type="checkbox" id="setBackupPdfs"> Also keep a copy of the PDFs
      (copied once; later only new ones)</label>
    <p class="hint" id="backupInfo">Your notes, progress, vocabulary and catalog go into a dated zip
      (the last 30 are kept), by 💾 Back up and once a day by itself.</p>
    <label for="setOpenalex">OpenAlex key (optional)</label>
    <input type="text" id="setOpenalex" autocomplete="off" spellcheck="false" placeholder="Paste your free key here">
    <p class="hint">Subjects and 🔎 Find online ask OpenAlex. Without a key, everyone on your network
      shares a small daily limit; with your own free key it's yours.
      <a href="https://openalex.org/settings/api-key" target="_blank" rel="noopener">Get a key</a></p>
    <label>Archive</label>
    <div class="row archive-row"><span id="archiveInfo">…</span>
      <button type="button" id="clearArchive">Clear archive</button></div>
    <p class="hint">Removed books and papers, repeated copies and original scans (before OCR)
      and the PDFs as they were before your first highlight.
      Clearing deletes them for good; archived notes and scripts with your own work are kept.</p>
    <div class="row end"><button value="cancel">Cancel</button>
      <button type="button" class="primary" id="saveSettings">Save</button></div>
  </form>
</dialog>
<script type="application/json" id="data">__DATA__</script>
<script>
const API = __API__;  // set when served by library_server.py; null in the static file
const books = JSON.parse(document.getElementById("data").textContent);
const SHELF_LABELS = __SHELF_LABELS__;  // from library.toml: {"Optics": "光学 Optics"}
const shelfLabel = name => SHELF_LABELS[name] || name;
let shelf = "";  // the shelf being shown ("" = all books)
try { shelf = localStorage.getItem("library-shelf") || ""; } catch {}
document.getElementById("footer").innerHTML = API
  ? `<b>Read</b> opens the PDF at the chapter, and its notes in your editor (see Settings).
     ${API.python ? "<b>Script</b> opens a Python script for checking the chapter's worked examples (created the first time). " : ""}The page you're on is saved as you read; <b>Continue · p. N</b> takes you back there.
     Tick chapters here when you finish them.`
  : `This is the static copy. For the <b>Read</b> / <b>Continue</b> buttons and ticking chapters,
     run <code>uv run scripts/library_server.py</code>.`;
const grid = document.getElementById("grid"), q = document.getElementById("q"),
      sort = document.getElementById("sort");
const esc = s => String(s ?? "").replace(/[&<>"']/g,
  c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const done = b => b.chapter_list.filter(c => c.done).length;
// How far into the book you are: ticked chapters or the page you last read, whichever is further
const pct = b => Math.max(
  b.chapter_list.length ? done(b) / b.chapter_list.length : 0,
  b.last_read && +b.pages ? Math.min(1, b.last_read.page / +b.pages) : 0);
const firstAuthor = b => (b.authors || "").split(";")[0].trim();

try { sort.value = localStorage.getItem("library-sort") || "title"; } catch {}
// Cards or a list (remembered; a big library starts as a list). Unfolded lines stay unfolded
// when the list is drawn again (e.g. after ticking a chapter)
let view = books.length > 24 ? "list" : "cards";
try { view = localStorage.getItem("library-view") || view; } catch {}
const expanded = new Set();
const kindSelect = document.getElementById("kind");
try { kindSelect.value = localStorage.getItem("library-kind") || ""; } catch {}
const isPaper = b => b.kind === "paper";
const isThesis = b => b.kind === "thesis";
// "PhD thesis", "Master's thesis", ... (thesis_meta.DEGREE_LABELS)
const DEGREE_LABELS = __DEGREE_LABELS__;
const kindLabel = b => isThesis(b) ? DEGREE_LABELS[b.degree] || "Thesis" : isPaper(b) ? "Paper" : "Book";
const count = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;  // "1 book", "2 books"
// The first two authors, then "et al." ("A; B; C" for papers, "A, B, C" for most books)
function authorNames(b) {
  const raw = b.authors || "";
  let names = raw.split(";");
  if (names.length === 1 && raw.split(",").every(n => n.trim().includes(" "))) names = raw.split(",");
  return names.map(a => a.trim()).filter(Boolean);
}
function authorLine(b) {
  const names = authorNames(b);
  return names.length <= 2 ? names.join(", ") : names.slice(0, 2).join(", ") + " et al.";
}
// The list: the first author only ("Jannick P. Rolland et al.")
function firstAuthorLine(b) {
  const names = authorNames(b);
  return names.length > 1 ? `${names[0]} et al.` : names[0] || "";
}
async function copyText(text, label) {
  try {
    await navigator.clipboard.writeText(text);
    toast(`Copied the ${label} citation`);
  } catch {
    prompt("Copy the citation (Ctrl+C):", text);  // no clipboard access (e.g. the static page)
  }
}

// The Cite menu: every format with a one-line preview; click one to copy it
function closeCiteMenus() {
  document.querySelectorAll(".cite-menu").forEach(m => m.remove());
}
function openCiteMenu(button, b) {
  const open = button.parentElement.querySelector(".cite-menu");
  closeCiteMenus();
  if (open) return;  // a second click on Cite closes it
  const menu = document.createElement("div");
  menu.className = "cite-menu";
  menu.innerHTML = b.citations.map((c, i) =>
    `<button type="button" data-format="${i}"><b>${esc(c.label)}</b>`
    + `<span>${esc(c.text.replace(/\s+/g, " "))}</span></button>`).join("");
  menu.addEventListener("click", e => {
    const choice = e.target.closest("[data-format]");
    if (!choice) return;
    const c = b.citations[+choice.dataset.format];
    copyText(c.text, c.label.split(" (")[0]);
    closeCiteMenus();
  });
  button.after(menu);
}
document.addEventListener("click", e => {
  if (!e.target.closest(".cite-menu, [data-cite]")) closeCiteMenus();
});
document.addEventListener("keydown", e => {
  if (e.key === "Escape") closeCiteMenus();
});

// The Field menu: the fields your items are in (from OpenAlex), "中文 English"
const fieldSelect = document.getElementById("field");
let field = "";
try { field = localStorage.getItem("library-field") || ""; } catch {}
// Both menus show how many items each choice has: the type menu within the chosen field, the
// Field menu within the chosen type (so the numbers match what you'd see)
const MENU_KINDS = {"": "All", book: "Books", paper: "Papers", thesis: "Theses"};
const isKind = (b, kind) => !kind || b.kind === kind;  // books() always gives a kind
function renderFields() {
  for (const option of kindSelect.options) {
    const n = books.filter(b => isKind(b, option.value) && (!field || b.field === field)).length;
    option.textContent = `${MENU_KINDS[option.value]} (${n})`;
  }
  const all = new Map(), shown = new Map();
  for (const b of books) {
    if (!b.field) continue;
    all.set(b.field, (all.get(b.field) || 0) + 1);
    if (isKind(b, kindSelect.value)) shown.set(b.field, (shown.get(b.field) || 0) + 1);
  }
  if (field && !all.has(field)) field = "";
  const names = [...all.keys()].sort((a, b) => all.get(b) - all.get(a) || a.localeCompare(b));
  fieldSelect.hidden = !names.length;
  const inKind = books.filter(b => isKind(b, kindSelect.value)).length;
  fieldSelect.innerHTML = `<option value="">All fields (${inKind})</option>` + names.map(f => {
    const label = books.find(b => b.field === f).field_label;
    return `<option value="${esc(f)}">${esc(label)} (${shown.get(f) || 0})</option>`;
  }).join("");
  fieldSelect.value = field;
}
const inKindAndField = b => isKind(b, kindSelect.value) && (!field || b.field === field);

// The shelf bar: All, then every shelf in use among the items shown (kind and field), with
// how many items each has
function renderShelves() {
  const pool = books.filter(inKindAndField);
  const counts = new Map();
  for (const b of pool) for (const s of b.shelf_list) counts.set(s, (counts.get(s) || 0) + 1);
  if (shelf && !counts.has(shelf)) shelf = "";
  const names = [...counts.keys()].sort((a, b) => counts.get(b) - counts.get(a) || a.localeCompare(b));
  const button = (name, label, n) =>
    `<button type="button" data-shelf="${esc(name)}" class="${name === shelf ? "on" : ""}">`
    + `${esc(label)}<span class="count">${n}</span></button>`;
  document.getElementById("shelves").innerHTML = names.length
    ? button("", "All", pool.length) + names.map(s => button(s, shelfLabel(s), counts.get(s))).join("")
    : "";
}

function stats() {
  const ch = books.reduce((n, b) => n + b.chapter_list.length, 0);
  const dn = books.reduce((n, b) => n + done(b), 0);
  const pages = books.reduce((n, b) => n + (+b.pages || 0), 0);
  const papers = books.filter(isPaper), theses = books.filter(isThesis);
  const read = papers.filter(b => done(b)).length;
  document.getElementById("stats").textContent =
    `${count(books.length - papers.length - theses.length, "book")}${papers.length ? ` · ${count(papers.length, "paper")}` : ""}`
    + (theses.length ? ` · ${theses.length} ${theses.length === 1 ? "thesis" : "theses"}` : "")
    + ` · ${pages.toLocaleString()} pages · ${dn - read} of ${ch - papers.length} chapters read`;
}

// The chapter "Continue" goes to: first unticked one (or the first chapter if all are done)
const nextChapter = b => b.chapter_list.find(c => !c.done) || b.chapter_list[0];

function readButton(b) {
  if (!API) return "";
  if (b.last_read && !b.pdf_missing) {
    return `<button type="button" class="read" data-resume title="Open the page you last read">Continue · p. ${b.last_read.page}</button>`;
  }
  const next = nextChapter(b);
  const label = !next ? "Read" : done(b) === 0 ? "Start reading"
    : done(b) === b.chapter_list.length ? "Read again" : "Continue";
  return `<button type="button" class="read" data-read="${next?.number ?? ""}">${label}</button>`;
}

// How far along, as text: "37%" ("<1%" just started)
const pctText = b => `${Math.round(pct(b) * 100) || "<1"}%`;
// The DOI as a link to its page
const doiLink = (b, title = "Its page at the publisher or university") =>
  `<a href="https://doi.org/${esc(b.doi)}" target="_blank" rel="noopener" title="${title}">DOI ${esc(b.doi)}</a>`;
// "工程 Engineering ›", then the subject's name when it isn't one of the item's shelves
const subjectSpan = (b, tag, withTopic) =>
  `<${tag} class="subject" title="Subject (OpenAlex), how sure: ${esc(b.topic_score)}">${esc(b.field_label)} ›${
    withTopic ? ` ${esc(shelfLabel(b.topic))}` : ""}</${tag}>`;

function chapterItem(c) {
  const tick = API
    ? `<input type="checkbox" data-tick="${c.number}" ${c.done ? "checked" : ""} aria-label="Read">`
    : `<span class="tick">${c.done ? "✓" : ""}</span>`;
  const read = API && c.number != null
    ? `<button type="button" data-read="${c.number}">Read</button>` + (API.python
      ? `<button type="button" data-script="${c.number}" title="A Python script to check this chapter's worked examples">Script</button>` : "")
    : "";
  return `<li class="${c.done ? "done" : ""}">${tick}<span class="name">${esc(c.title)}</span>${read}</li>`;
}

// One book, paper or thesis. inList: opened from a line of the list (more compact: the
// publisher joins the author line, and all the buttons share one row)
function card(b, inList = false) {
  const n = b.chapter_list.length;
  const chapters = b.chapter_list.map(chapterItem).join("");
  const next = nextChapter(b);
  const venue = isPaper(b) && b.journal
    ? `${b.journal}${b.volume ? ` ${b.volume}` : ""}${b.issue ? `(${b.issue})` : ""}${b.page_range ? `, ${b.page_range}` : ""}`
    : isThesis(b) ? b.institution : b.publisher;
  const byline = [authorLine(b), b.year, inList ? venue : ""].filter(Boolean).map(esc).join(" · ");
  const details = [
    !inList && venue ? `<span>${esc(venue)}</span>` : "",
    b.isbn ? `<span>ISBN ${esc(b.isbn)}</span>` : "",
    b.doi ? doiLink(b) : "",
  ].filter(Boolean).join("");
  const keywords = (isPaper(b) || isThesis(b)) && b.keywords
    ? b.keywords.split(";").map(k => k.trim()).filter(Boolean).slice(0, 6).map(k => `<span class="chip kw">${esc(k)}</span>`).join("") : "";
  const shelfTags = (b.field_label && b.shelf_list.includes(b.topic)
      ? subjectSpan(b, "span", false) : "")
    + b.shelf_list.map(s => `<span class="chip shelf">${esc(shelfLabel(s))}</span>`).join("");
  const progress = (isPaper(b) ? (done(b) ? "Read ✓" : "Not read yet") : n ? `${done(b)}/${n} chapters` : "no chapters")
    + (pct(b) > 0 && !(isPaper(b) && done(b)) ? ` · ${pctText(b)}` : "")
    + (b.pages ? ` · ${esc(b.pages)} pages` : "");
  const main = `
      ${readButton(b)}
      ${API ? `<button type="button" class="primary" data-shelves title="Which shelves this book is on">Shelves</button>` : ""}
      ${isPaper(b) ? (API ? `<button type="button" class="primary" data-markread>${done(b) ? "✓ Read" : "Mark as read"}</button>` : "")
        : n ? `<button type="button" class="primary" data-toggle>Chapters</button>` : ""}`;
  const more = `
      ${b.pdf_missing ? `<span class="missing" title="${esc(b.file)} is gone; notes and scripts are still here">PDF missing</span>`
        : `<a href="${esc(b.pdf_uri)}" target="_blank" rel="noopener">PDF</a>`}
      ${b.notes_problem ? `<span class="missing" title="${esc(b.notes_problem)}">笔记文件夹有问题 (Notes folder problem)</span>`
        : API ? `<button type="button" data-notes>Notes</button>` : `<a href="${esc(b.notes_uri)}">Notes</a>`}
      ${b.openlibrary ? `<a href="${esc(b.openlibrary)}" target="_blank" rel="noopener">Open Library</a>` : ""}
      <span class="cite-wrap"><button type="button" data-cite title="Copy a citation: APA, IEEE, GB/T 7714, BibTeX or RIS">Cite ▾</button></span>
      ${API && b.scan && !b.pdf_missing ? `<button type="button" data-ocr title="This book is a scan: OCR adds a text layer, so its words can be looked up and searched">OCR (~${b.ocr_minutes} min)</button>` : ""}`;
  return `<article class="card" data-id="${esc(b.id)}">
    <h2><span class="kind-tag">${esc(kindLabel(b))}</span>${esc(b.title)}</h2>
    ${inList  // from the list: ISBN / DOI on the author line, to keep the card short
      ? (byline || details ? `<div class="byline inline">${byline}${details ? `<span class="meta">${details}</span>` : ""}</div>` : "")
      : `${byline ? `<div class="byline">${byline}</div>` : ""}${details ? `<div class="meta">${details}</div>` : ""}`}
    ${isThesis(b) && b.supervisors ? `<div class="next">Supervised by ${esc(b.supervisors.split(";").map(s => s.trim()).join(", "))}</div>` : ""}
    ${b.topic && !b.shelf_list.includes(b.topic) ? subjectSpan(b, "div", true) : ""}
    ${inList  // from the list: keywords and shelves share one row
      ? (keywords || shelfTags ? `<div class="chips">${shelfTags}${keywords}</div>` : "")
      : `${keywords ? `<div class="chips keywords">${keywords}</div>` : ""}${shelfTags ? `<div class="chips">${shelfTags}</div>` : ""}`}
    <div class="progress"><div class="bar"><span style="width:${Math.round(pct(b) * 100)}%"></span></div>${progress}</div>
    ${b.last_read ? `<div class="next">Last read: page ${b.last_read.page}${b.last_read.chapter ? ` · ${esc(b.last_read.chapter)}` : ""} · ${esc(b.last_read.date)}</div>`
      : API && next && done(b) < n && !isPaper(b) ? `<div class="next">Next: ${esc(next.title)}</div>` : ""}
    ${inList ? `<div class="actions">${main}${more}</div>`
      : `<div class="actions">${main}</div><div class="actions">${more}</div>`}
    ${n && !isPaper(b) ? `<ol class="chapters" hidden>${chapters}</ol>` : ""}
  </article>`;
}

function render() {
  const words = q.value.toLowerCase().split(/\s+/).filter(Boolean);
  const keyed = {
    title: (a, b) => a.title.localeCompare(b.title),
    author: (a, b) => firstAuthor(a).split(" ").pop().localeCompare(firstAuthor(b).split(" ").pop()),
    year: (a, b) => (+b.year || 0) - (+a.year || 0),
    // furthest along first; then the one read most recently; untouched books by title
    progress: (a, b) => pct(b) - pct(a)
      || (b.last_read?.date || "").localeCompare(a.last_read?.date || "")
      || a.title.localeCompare(b.title),
    added: (a, b) => (b.added || "").localeCompare(a.added || ""),
    // last read first (same day: the one touched last); books not started yet at the end
    recent: (a, b) => !!b.last_read - !!a.last_read
      || (b.last_read?.date || "").localeCompare(a.last_read?.date || "")
      || (b.last_read ? b.touched - a.touched : 0)
      || a.title.localeCompare(b.title),
  }[sort.value];
  const shown = books
    .filter(b => !shelf || b.shelf_list.includes(shelf))
    .filter(inKindAndField)
    .filter(b => {
      const hay = [b.title, b.authors, b.year, b.publisher, b.isbn, b.subjects, b.journal, b.doi, b.keywords,
                   b.institution, b.supervisors, b.topic, b.field, b.field_label, isThesis(b) ? kindLabel(b) + " thesis dissertation" : "",
                   ...b.shelf_list, ...b.shelf_list.map(shelfLabel),
                   ...b.chapter_list.map(c => c.title)].join(" ").toLowerCase();
      return words.every(w => hay.includes(w));
    })
    .sort(keyed);
  document.querySelectorAll("[data-view]").forEach(b =>
    b.setAttribute("aria-pressed", String(b.dataset.view === view)));
  grid.classList.toggle("list", view === "list" && shown.length > 0);
  if (!shown.length) {
    grid.innerHTML = `<p class="empty">No books match “${esc(q.value)}”.${API
      ? `<button type="button" data-findonline>🔎 Search online</button>` : ""}</p>`;
  } else if (view === "list") {
    const open = shown.filter(b => expanded.has(b.id)).length;
    const head = (key, label, cls = "") => key
      ? `<button type="button" data-sortby="${key}" class="${sort.value === key ? "on" : ""}" title="Sort by ${label.toLowerCase()}">${label}${sort.value === key ? " ↓" : ""}</button>`
      : label;
    grid.innerHTML = `<div class="list-info"><span>${shown.length === books.length
        ? count(shown.length, "item") : `${shown.length} of ${books.length} shown`}
        · click a line to see its card</span>
      ${open ? `<button type="button" data-foldall title="Close every open card">▴ Fold all (${open})</button>`
        : `<button type="button" data-unfoldall title="Open the card of every line shown">▾ Unfold all</button>`}</div>
      <div class="lhead"><span>Kind</span><span>${head("title", "Title")} · ${head("author", "Author")} · ${head("year", "Year")}</span>
        <span class="ident">ISBN / DOI</span><span>${head("progress", "Progress")}</span>
        <span class="last">${head("recent", "Last read")}</span><span class="go"></span></div>`
      + shown.map(listItem).join("");
  } else {
    grid.innerHTML = shown.map(b => card(b)).join("");
  }
}

// One line of the list: kind, title, ISBN or DOI, progress, last read, Continue
function listItem(b) {
  const n = b.chapter_list.length;
  // First author, year, and the shelves (no publisher or journal: the card has those)
  const sub = [firstAuthorLine(b), b.year].filter(Boolean).map(esc).join(" · ")
    + b.shelf_list.map(s => `<span class="tag">${esc(shelfLabel(s))}</span>`).join("");
  const ident = b.doi
    ? doiLink(b, "Open the DOI")
    : b.isbn ? `ISBN ${esc(b.isbn)}` : "—";
  const progress = isPaper(b) ? (done(b) ? "Read ✓" : pct(b) > 0 ? `${pctText(b)} read` : "Not read yet")
    : n ? `${done(b)}/${n} chapters${pct(b) > 0 ? ` · ${pctText(b)}` : ""}` : "no chapters";
  const last = b.last_read ? `p. ${b.last_read.page}<br>${esc(b.last_read.date)}` : "";
  const isOpen = expanded.has(b.id);
  return `<div class="litem ${isOpen ? "open" : ""}" data-id="${esc(b.id)}">
    <div class="lrow" data-row role="button" tabindex="0" aria-expanded="${isOpen}">
      <span class="kind">${esc(kindLabel(b))}</span>
      <div><div class="ttl" title="${esc(b.title)}">${esc(b.title)}</div><div class="sub">${sub}</div></div>
      <span class="ident">${ident}</span>
      <div class="prog"><div class="bar"><span style="width:${Math.round(pct(b) * 100)}%"></span></div>${progress}</div>
      <span class="last">${last}</span>
      <span class="go">${b.pdf_missing ? "" : readButton(b)}</span>
    </div>
    ${isOpen ? `<div class="ldetail">${card(b, true)}</div>` : ""}
  </div>`;
}

let toastTimer;
function toast(message) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 4000);
}

async function api(path, body) {
  const response = await fetch(path, {
    method: "POST",
    keepalive: true,  // a click's write (tick, shelves, review answer) arrives even if the tab closes
    headers: {"Content-Type": "application/json", "X-Library-Token": API.token},
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

const bookOf = el => books.find(b => b.id === el.closest("[data-id]").dataset.id);
const openLists = () => new Set([...grid.querySelectorAll("ol.chapters:not([hidden])")]
  .map(ol => ol.closest(".card").dataset.id));

document.getElementById("shelves").addEventListener("click", e => {
  const button = e.target.closest("[data-shelf]");
  if (!button) return;
  shelf = button.dataset.shelf;
  try { localStorage.setItem("library-shelf", shelf); } catch {}
  renderShelves();
  render();
});

// Draw the page again (after a change), keeping open chapter lists open; menus = the type and
// Field menus and the shelf bar too, stats = the counts at the top
function redraw({menus = false, counts = false} = {}) {
  const keepOpen = openLists();
  if (counts) stats();
  if (menus) { renderFields(); renderShelves(); }
  render();
  keepOpen.forEach(s => grid.querySelector(`.card[data-id="${CSS.escape(s)}"] ol.chapters`)
    ?.removeAttribute("hidden"));
}

function toggleLine(row) {
  const docId = row.closest("[data-id]").dataset.id;
  if (expanded.has(docId)) expanded.delete(docId);
  else expanded.add(docId);
  redraw();
  grid.querySelector(`.litem[data-id="${CSS.escape(docId)}"] .lrow`)?.focus({preventScroll: true});
}
grid.addEventListener("keydown", e => {
  const row = e.target.closest("[data-row]");
  if (row && e.target === row && (e.key === "Enter" || e.key === " ")) {
    e.preventDefault();
    toggleLine(row);
  }
});
grid.addEventListener("click", async e => {
  const row = e.target.closest("[data-row]");
  if (row && !e.target.closest("a, button, input")) return toggleLine(row);
  const sortBy = e.target.closest("[data-sortby]");
  if (sortBy) {
    sort.value = sortBy.dataset.sortby;
    try { localStorage.setItem("library-sort", sort.value); } catch {}
    return render();
  }
  if (e.target.closest("[data-foldall]")) {
    expanded.clear();
    return render();
  }
  if (e.target.closest("[data-unfoldall]")) {  // every line shown (search, type, field, shelf)
    grid.querySelectorAll(".litem[data-id]").forEach(item => expanded.add(item.dataset.id));
    return render();
  }
  const cite = e.target.closest("[data-cite]");
  if (cite) return openCiteMenu(cite, bookOf(cite));
  const markRead = e.target.closest("[data-markread]");
  if (markRead && API) {
    const b = bookOf(markRead);
    try {
      const r = await api("/api/tick", {id: b.id, chapter: 1, done: !done(b)});
      b.chapter_list = r.chapter_list;
      stats();
      render();
    } catch (err) {
      toast(`Couldn't save: ${err.message}`);
    }
    return;
  }
  const notes = e.target.closest("[data-notes]");
  if (notes && API) {
    try {
      toast((await api("/api/open-notes", {id: bookOf(notes).id})).message);
    } catch (err) {
      toast(`Couldn't open the notes: ${err.message}`);
    }
    return;
  }
  const ocr = e.target.closest("[data-ocr]");
  if (ocr && API) {
    const b = bookOf(ocr);
    if (!confirm(`OCR “${b.title}”? It takes about ${b.ocr_minutes} min; you can keep reading meanwhile.`)) return;
    try {
      await api("/api/ocr", {id: b.id});
      pollJobs();
    } catch (err) {
      toast(`Couldn't start OCR: ${err.message}`);
    }
    return;
  }
  const edit = e.target.closest("[data-shelves]");
  if (edit && API) {
    const b = bookOf(edit);
    const answer = prompt(
      `Shelves for “${b.title}”, separated by ;`, b.shelf_list.join("; "));
    if (answer === null) return;
    try {
      const r = await api("/api/shelves", {id: b.id, shelves: answer});
      b.shelf_list = r.shelves;
      renderShelves();
      render();
      toast(r.shelves.length ? `On shelves: ${r.shelves.map(shelfLabel).join(", ")}` : "Not on any shelf");
    } catch (err) {
      toast(`Couldn't save: ${err.message}`);
    }
    return;
  }
  const toggle = e.target.closest("[data-toggle]");
  if (toggle) {
    const list = toggle.closest(".card").querySelector("ol.chapters");
    list.hidden = !list.hidden;
    return;
  }
  const script = e.target.closest("[data-script]");
  if (script && API) {
    script.disabled = true;
    try {
      const r = await api("/api/script", {id: bookOf(script).id, chapter: +script.dataset.script});
      toast(r.message);
    } catch (err) {
      toast(`Couldn't open the script: ${err.message}`);
    } finally {
      script.disabled = false;
    }
    return;
  }
  const read = e.target.closest("[data-read], [data-resume]");
  if (read && API) {
    const b = bookOf(read);
    const resume = "resume" in read.dataset;
    const chapter = resume || read.dataset.read === "" ? null : +read.dataset.read;
    read.disabled = true;
    toast("Opening…");
    try {
      const r = await api("/api/open", {id: b.id, chapter, resume});
      toast(r.message);
    } catch (err) {
      toast(`Couldn't open: ${err.message}`);
    } finally {
      read.disabled = false;
    }
  }
});

grid.addEventListener("change", async e => {
  const box = e.target.closest("[data-tick]");
  if (!box || !API) return;
  const b = bookOf(box);
  try {
    const r = await api("/api/tick", {id: b.id, chapter: +box.dataset.tick, done: box.checked});
    b.chapter_list = r.chapter_list;
    redraw({counts: true});
  } catch (err) {
    box.checked = !box.checked;
    toast(`Couldn't save: ${err.message}`);
  }
});
q.addEventListener("input", render);
// ↑ Back to the top (search, menus and shelves are there)
const toTop = document.getElementById("toTop");
const controls = document.querySelector(".controls");
window.addEventListener("scroll", () => {
  toTop.hidden = window.scrollY < 600;
  // "stuck": the search row has reached the top and stays there
  controls.classList.toggle("stuck", controls.getBoundingClientRect().top <= 0 && window.scrollY > 0);
}, {passive: true});
toTop.addEventListener("click", () => window.scrollTo({top: 0, behavior: "smooth"}));
document.querySelector(".view").addEventListener("click", e => {
  const button = e.target.closest("[data-view]");
  if (!button) return;
  view = button.dataset.view;
  try { localStorage.setItem("library-view", view); } catch {}
  render();
});
kindSelect.addEventListener("change", () => {
  try { localStorage.setItem("library-kind", kindSelect.value); } catch {}
  redraw({menus: true});
});
fieldSelect.addEventListener("change", () => {
  field = fieldSelect.value;
  try { localStorage.setItem("library-field", field); } catch {}
  redraw({menus: true});
});
sort.addEventListener("change", () => {
  try { localStorage.setItem("library-sort", sort.value); } catch {}
  render();
});
// --- Tools (only with the server): add books, settings, quit ---------------------------------
const prevStatus = new Map();  // job id -> status at the last poll (to notice jobs finishing)
let pollTimer = null;

async function pollJobs() {
  clearTimeout(pollTimer);
  let jobs;
  try {
    jobs = (await api("/api/jobs", {})).jobs;
  } catch {
    return;
  }
  lastJobs = jobs;
  renderJobs(jobs);
  let finished = false;
  for (const j of jobs) {
    if (prevStatus.get(j.id) === "working" && j.status !== "working") finished = true;
    prevStatus.set(j.id, j.status);
  }
  const busy = jobs.some(j => j.status === "working");
  if (finished && !busy) {
    setTimeout(() => location.reload(), 1500);  // show the new books / searchable scans
    return;
  }
  if (busy) pollTimer = setTimeout(pollJobs, 1500);
}

// Jobs still running are shown; finished ones fold away under "History" (open or closed, as
// you left it last time)
let historyOpen = false;
try { historyOpen = localStorage.getItem("library-history-open") === "1"; } catch {}
function jobLine(j) {
  const icon = {working: "⏳", done: "✓", duplicate: "•", error: "✗"}[j.status] || "";
  const bar = j.kind === "ocr" && j.total
    ? `<div class="bar"><span style="width:${Math.round(100 * j.done / j.total)}%"></span></div>` : "";
  return `<div class="job ${j.status === "error" ? "error" : ""}">${icon} ${esc(j.file || "")}
    <span>${esc(j.message || "")}</span>${bar}</div>`;
}
function renderJobs(jobs) {
  const panel = document.getElementById("jobs");
  const active = jobs.filter(j => j.status === "working");
  const done = jobs.filter(j => !active.includes(j));
  panel.hidden = !jobs.length;
  const problems = done.filter(j => j.status === "error").length;
  const history = done.length ? `<div class="history-bar">
      <button type="button" data-history aria-expanded="${historyOpen}">🕘 History (${done.length}) ${historyOpen ? "▴" : "▾"}</button>
      ${problems ? `<span class="problems">${problems} problem${problems > 1 ? "s" : ""}</span>` : ""}
      ${historyOpen ? `<button type="button" data-clear-history title="Forget these messages">Clear</button>`
        : `<span class="latest">Latest: ${esc(done[0].message || "")}</span>`}
    </div>
    <div class="history" ${historyOpen ? "" : "hidden"}>${done.map(jobLine).join("")}</div>` : "";
  panel.innerHTML = active.map(jobLine).join("") + history;
}
let lastJobs = [];

async function upload(file) {
  const response = await fetch("/api/upload", {
    method: "POST",
    headers: {"X-Library-Token": API.token, "X-Filename": encodeURIComponent(file.name)},
    body: file,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data.job;
}

async function openSettings() {
  const {settings} = await api("/api/settings", {});
  document.getElementById("setLibrary").value = settings.library;
  document.getElementById("setEditor").value = settings.editor;
  document.getElementById("setCommand").value = settings.editor_command || "";
  document.getElementById("setPython").checked = !!settings.python_features;
  document.getElementById("customRow").hidden = settings.editor !== "custom";
  document.getElementById("setBackup").value = settings.backup_folder || "";
  document.getElementById("setBackupPdfs").checked = !!settings.backup_pdfs;
  document.getElementById("setOpenalex").value = settings.openalex_key || "";
  const b = settings.backup_status || {};
  if (b.last) document.getElementById("backupInfo").textContent =
    `Last backup: ${b.when} (${count(b.count, "backup")} in the folder). It runs once a day by itself, `
    + "or now with 💾 Back up. Your notes, progress, vocabulary and catalog go into a dated zip.";
  document.getElementById("settingsDialog").showModal();
  showArchive(await api("/api/archive", {}));
}

const megabytes = n => n >= 1e9 ? `${(n / 1e9).toFixed(1)} GB` : `${Math.max(0.1, n / 1e6).toFixed(1)} MB`;
function showArchive(a) {
  document.getElementById("archiveInfo").textContent = a.files
    ? `${count(a.files, "file")}, ${megabytes(a.bytes)}${a.kept.length ? ` (+ ${a.kept.length} kept: your notes or scripts)` : ""}`
    : a.kept.length ? `Empty, apart from ${a.kept.length} kept (your notes or scripts)` : "Empty";
  document.getElementById("clearArchive").disabled = !a.files;
}
async function clearArchive() {
  const a = await api("/api/archive", {});
  if (!a.files) return showArchive(a);
  const kept = a.kept.length
    ? `\n\nKept, because they hold your own notes or scripts:\n${a.kept.join("\n")}` : "";
  if (!confirm(`Delete ${count(a.files, "file")} (${megabytes(a.bytes)}) from the archive for good? `
      + `This can't be undone.${kept}`)) return;
  try {
    const r = await api("/api/archive", {clear: true});
    toast(`Archive cleared: ${count(r.files, "file")}, ${megabytes(r.bytes)} freed`);
    showArchive(await api("/api/archive", {}));
  } catch (err) {
    toast(`Couldn't clear the archive: ${err.message}`);
  }
}

async function saveSettings() {
  const save = {
    library: document.getElementById("setLibrary").value.trim(),
    editor: document.getElementById("setEditor").value,
    editor_command: document.getElementById("setCommand").value.trim(),
    python_features: document.getElementById("setPython").checked,
    backup_folder: document.getElementById("setBackup").value.trim(),
    backup_pdfs: document.getElementById("setBackupPdfs").checked,
    openalex_key: document.getElementById("setOpenalex").value.trim(),
  };
  try {
    const r = await api("/api/settings", {save});
    document.getElementById("settingsDialog").close();
    if (!r.restart) return location.reload();
    toast("Opening the library…");
    for (let i = 0; i < 40; i++) {  // the server restarts with the new library
      await new Promise(done => setTimeout(done, 750));
      try {
        if ((await fetch("/", {cache: "no-store"})).ok) return location.reload();
      } catch {}
    }
    toast("The library didn't come back; start myLibrary again");
  } catch (err) {
    toast(`Couldn't save: ${err.message}`);
  }
}

if (API) {
  document.getElementById("tools").innerHTML = `
    <label class="tool" title="Add PDF books, papers or theses to the library (or drag them onto this page)">＋ Add
      <input type="file" id="addFiles" accept=".pdf,application/pdf" multiple hidden></label>
    <button type="button" class="tool" id="refreshLibrary" title="Add PDFs you put into books/, papers/ or theses/ yourself (like running add_book.py)">⟳ Refresh</button>
    <button type="button" class="tool" id="findOnline" title="Search for books, papers and theses online: DOI, title, author…">🔎 Find online</button>
    <button type="button" class="tool" id="openReview" title="复习生词 (Review words): the words you saved while reading, as cards (spaced repetition)">📇 Review words<span class="count" id="reviewCount" hidden></span></button>
    ${API.backup ? `<button type="button" class="tool" id="backup" title="Save your notes, progress and vocabulary to GitHub">☁ Back up</button>` : ""}
    ${API.library?.mode !== "test" && (!API.backup || API.folder_backup) ? `<button type="button" class="tool" id="folderBackup" title="Save your notes, progress and vocabulary (and the PDFs) to your backup folder">💾 Back up</button>` : ""}
    <button type="button" class="tool" id="switchLibrary" title="${API.library?.mode === "test" ? "书库模式 (Library modes): personal libraries or Test &amp; Demo" : "切换书库 (Switch library): another of your personal libraries"}">📚 ${API.library?.mode === "test" ? "书库模式 Library modes" : "切换书库 Switch library"}</button>
    <button type="button" class="tool" id="openSettings">⚙ Settings</button>
    <button type="button" class="tool" id="quit" title="Stop myLibrary">Quit</button>`;
  // Add PDFs, from the ＋ Add button or dropped onto the page; other files are skipped
  async function addFiles(files) {
    const isPdf = f => f.name.toLowerCase().endsWith(".pdf") || f.type === "application/pdf";
    for (const file of files.filter(isPdf)) {
      toast(`Adding ${file.name}…`);
      try {
        await upload(file);
      } catch (err) {
        toast(`Couldn't add ${file.name}: ${err.message}`);
      }
    }
    const skipped = files.filter(f => !isPdf(f));
    if (skipped.length) {  // last, so the "Adding …" messages don't hide it
      toast(`Only PDFs can be added; skipped ${skipped.map(f => f.name).join(", ")}`);
    }
    pollJobs();
  }
  // 🔎 Find online: search public catalogues; add free PDFs straight to the library
  const findDialog = document.getElementById("findDialog");
  const findQuery = document.getElementById("findQuery");
  const findResults = document.getElementById("findResults");
  const RESULT_KINDS = {paper: "Paper", book: "Book", thesis: "Thesis", chapter: "Book chapter"};
  let findFound = [];  // the results shown, for their buttons
  function openFind(text) {
    if (text) findQuery.value = text;
    if (!findDialog.open) findDialog.showModal();
    findQuery.focus();
    if (text) runFind();
  }
  function resultHtml(r, i) {
    const who = [authorLine(r), r.year, r.venue].filter(Boolean).map(esc).join(" · ");
    const title = r.url ? `<a class="t" href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a>`
      : `<span class="t">${esc(r.title)}</span>`;
    const pdf = r.pdf || (r.free && /\.pdf($|\?)/i.test(r.free) ? r.free : "");
    return `<div class="result">${title}
      <div class="who">${who}</div>
      <div class="acts">
        <span class="chip-kind">${esc(RESULT_KINDS[r.kind] || "Work")}</span>
        ${r.in_library ? `<span class="owned">✓ In your library</span>` : ""}
        ${r.cited ? `<span>cited ${r.cited.toLocaleString()}×</span>` : ""}
        ${r.doi ? `<a href="https://doi.org/${esc(r.doi)}" target="_blank" rel="noopener">DOI</a>` : ""}
        ${r.free ? `<a href="${esc(r.free)}" target="_blank" rel="noopener" title="A free, legal copy (open access)">Free to read</a>` : ""}
        ${pdf && !r.in_library ? `<button type="button" class="primary" data-get="${i}" title="Download the free PDF and add it">＋ Add to library</button>` : ""}
        <a href="https://scholar.google.com/scholar?q=${encodeURIComponent(r.doi || r.title)}" target="_blank" rel="noopener">Google Scholar</a>
      </div></div>`;
  }
  async function runFind() {
    const query = findQuery.value.trim();
    if (!query) return;
    findResults.innerHTML = `<p class="status">Searching…</p>`;
    document.getElementById("findEngines").innerHTML = "";
    try {
      const r = await api("/api/find-online", {query});
      if (findQuery.value.trim() !== query) return;  // a newer search is on its way
      document.getElementById("findEngines").innerHTML = "Also search on:"
        + r.engines.map(e => `<a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.label)}</a>`).join("");
      findFound = r.sections.flatMap(s => s.results);
      let n = 0;
      findResults.innerHTML = r.sections.length
        ? r.sections.map(s => `<h3>${esc(s.title)}</h3>` + s.results.map(x => resultHtml(x, n++)).join("")).join("")
        : `<p class="status">Nothing found for “${esc(query)}”. Try the search engines above.</p>`;
    } catch (err) {
      findResults.innerHTML = `<p class="status">Couldn't search (${esc(err.message)}). Are you online?</p>`;
    }
  }
  document.getElementById("findOnline").addEventListener("click", () => openFind(""));
  // ⟳ Refresh: PDFs copied into the library's folders by hand are identified and added
  document.getElementById("refreshLibrary").addEventListener("click", async e => {
    const button = e.currentTarget;
    button.disabled = true;
    try {
      const r = await api("/api/refresh", {});
      toast(r.message);
      if (r.started) pollJobs();  // the page reloads itself when they're done
      else refreshBooks();        // nothing new: still show the latest notes and progress
    } catch (err) {
      toast(`Couldn't refresh: ${err.message}`);
    } finally {
      button.disabled = false;
    }
  });
  document.getElementById("findClose").addEventListener("click", () => findDialog.close());
  document.getElementById("findForm").addEventListener("submit", e => { e.preventDefault(); runFind(); });
  findResults.addEventListener("click", async e => {
    const get = e.target.closest("[data-get]");
    if (!get) return;
    const r = findFound[+get.dataset.get];
    get.disabled = true;
    get.textContent = "Adding…";
    try {
      await api("/api/download", {url: r.pdf || r.free, title: r.title});
      toast(`Downloading “${r.title}”…`);
      pollJobs();
    } catch (err) {
      toast(`Couldn't add it: ${err.message}`);
      get.disabled = false;
      get.textContent = "＋ Add to library";
    }
  });
  grid.addEventListener("click", e => {
    if (e.target.closest("[data-findonline]")) openFind(q.value.trim());
  });
  document.getElementById("addFiles").addEventListener("change", e => {
    const files = [...e.target.files];
    e.target.value = "";
    addFiles(files);
  });
  // Drag and drop: the drop zone shows while files are dragged over the page. dragenter and
  // dragleave fire for every element crossed, so count them to know when the drag has left.
  const dropzone = document.getElementById("dropzone");
  const draggingFiles = e => [...(e.dataTransfer?.types || [])].includes("Files");
  let dragDepth = 0;
  window.addEventListener("dragenter", e => {
    if (!draggingFiles(e)) return;
    e.preventDefault();
    dragDepth++;
    dropzone.hidden = false;
  });
  window.addEventListener("dragover", e => {
    if (!draggingFiles(e)) return;
    e.preventDefault();  // allows the drop (otherwise the browser opens the PDF itself)
    e.dataTransfer.dropEffect = "copy";
  });
  window.addEventListener("dragleave", e => {
    if (!draggingFiles(e)) return;
    dragDepth = Math.max(0, dragDepth - 1);
    if (!dragDepth) dropzone.hidden = true;
  });
  window.addEventListener("drop", e => {
    if (!draggingFiles(e)) return;
    e.preventDefault();
    dragDepth = 0;
    dropzone.hidden = true;
    addFiles([...e.dataTransfer.files]);
  });
  document.getElementById("backup")?.addEventListener("click", async e => {
    const button = e.currentTarget;
    button.disabled = true;
    toast("Backing up…");
    try {
      toast((await api("/api/backup", {})).message);
    } catch (err) {
      toast(`Couldn't back up: ${err.message}`);
    } finally {
      button.disabled = false;
    }
  });
  document.getElementById("clearArchive").addEventListener("click", clearArchive);
  document.getElementById("openSettings").addEventListener("click", () =>
    openSettings().catch(err => toast(`Couldn't open the settings: ${err.message}`)));
  document.getElementById("saveSettings").addEventListener("click", saveSettings);
  document.getElementById("setEditor").addEventListener("change", e => {
    document.getElementById("customRow").hidden = e.target.value !== "custom";
  });
  document.getElementById("pickBackup").addEventListener("click", async () => {
    try {
      const {folder} = await api("/api/pick-folder", {purpose: "backup"});
      if (folder) document.getElementById("setBackup").value = folder;
    } catch (err) {
      toast(`Couldn't open the folder dialog: ${err.message}`);
    }
  });
  document.getElementById("folderBackup")?.addEventListener("click", async e => {
    if (!API.folder_backup) {
      await openSettings().catch(err => toast(`Couldn't open the settings: ${err.message}`));
      document.getElementById("setBackup").focus();
      return toast("Choose a backup folder first, then Save");
    }
    const button = e.currentTarget;
    button.disabled = true;
    toast("Backing up…");
    try {
      toast((await api("/api/folder-backup", {})).message);
    } catch (err) {
      toast(`Not backed up: ${err.message}`);
    } finally {
      button.disabled = false;
    }
  });
  document.getElementById("pickFolder").addEventListener("click", async () => {
    try {
      const {folder} = await api("/api/pick-folder", {});
      if (folder) document.getElementById("setLibrary").value = folder;
    } catch (err) {
      toast(`Couldn't open the folder dialog: ${err.message}`);
    }
  });
  // 📚 Libraries: personal libraries (switch, add, create, rename, remove from the list) and
  // Test & Demo. Opening one starts (or finds) that library's own server; this one keeps
  // running as it is, so nothing in progress here is cut off.
  const libDialog = document.getElementById("librariesDialog");
  const libReport = document.getElementById("libReport");
  const current = API.library || {mode: "personal", key: "", path: ""};
  document.getElementById("testBanner").hidden = current.mode !== "test";
  function libLevel(level) {
    document.getElementById("libModes").hidden = level !== "modes";
    document.getElementById("libPersonal").hidden = level !== "personal";
    document.getElementById("libBack").hidden = level === "modes";
    if (!libDialog.open) libDialog.showModal();
    if (level === "personal") showLibraries().catch(err => toast(`Couldn't list the libraries: ${err.message}`));
  }
  async function libCall(action, body) {
    const r = await api(`/api/libraries/${action}`, body);
    if (r.error) throw new Error(r.error);
    return r;
  }
  async function showLibraries() {
    const r = await api("/api/libraries", {});
    if (r.error) throw new Error(r.error);
    document.getElementById("libList").innerHTML = r.personal.map(l => {
      const here = current.mode === "personal" && (l.key === current.key || l.path === current.path);
      const badges = (l.default ? `<span class="badge">默认 default</span>` : "")
        + (here ? `<span class="badge">当前 open here</span>` : "")
        + (l.available ? "" : `<span class="badge">找不到 not found</span>`);
      return `<li class="${l.available ? "" : "gone"}" data-key="${esc(l.key)}" data-label="${esc(l.label)}">
        <b>${esc(l.label)}</b>${badges}<div class="where">${esc(l.path)}${l.problem ? ` — ${esc(l.problem)}` : ""}</div>
        <div class="row">
          ${l.available && !here ? `<button type="button" class="primary" data-lib="open">打开 (Open)</button>` : ""}
          <button type="button" data-lib="rename">重命名 (Rename)</button>
          ${l.available ? "" : `<button type="button" data-lib="relocate" title="用下面的文件夹 (uses the folder below)">重新定位 (Locate moved folder)</button>`}
          ${l.default ? "" : `<button type="button" data-lib="unregister">移出列表 (Remove from list)</button>`}
        </div></li>`;
    }).join("") || `<li>还没有私人书库 (No personal libraries yet)</li>`;
  }
  function reportHtml(c) {
    const docs = Object.entries(c.documents || {}).map(([k, n]) => `${n} ${k}`).join(", ");
    return (c.errors || []).map(e => `<div class="bad">✗ ${esc(e)}</div>`).join("")
      + (c.warnings || []).map(w => `<div>⚠ ${esc(w)}</div>`).join("")
      + (c.ok ? `<div>✓ ${esc(c.name || "")} ${docs ? `(${esc(docs)})` : ""}</div>` : "");
  }
  async function openLibrary(body, what) {
    toast(`正在打开 (Opening) ${what}…`);
    try {
      location.href = (await libCall("open", body)).url;
    } catch (err) {
      toast(`打不开 (Couldn't open): ${err.message}`);
    }
  }
  document.getElementById("switchLibrary").addEventListener("click", () =>
    libLevel(current.mode === "test" ? "modes" : "personal"));
  document.getElementById("bannerModes").addEventListener("click", () => libLevel("modes"));
  document.getElementById("libBack").addEventListener("click", () => libLevel("modes"));
  document.getElementById("libClose").addEventListener("click", () => libDialog.close());
  document.querySelector("#libModes .modes").addEventListener("click", e => {
    const mode = e.target.closest("[data-mode]")?.dataset.mode;
    if (mode === "personal") return libLevel("personal");
    if (mode === "test") {
      if (current.mode === "test") return libDialog.close();
      openLibrary({mode: "test"}, "测试/示例书库 (Test & Demo library)");
    }
  });
  document.getElementById("libPick").addEventListener("click", async () => {
    const r = await api("/api/pick-folder", {purpose: "library"}).catch(() => ({}));
    if (r.folder) document.getElementById("libFolder").value = r.folder;
  });
  const libFolder = () => document.getElementById("libFolder").value.trim();
  const libLabel = () => document.getElementById("libLabel").value.trim();
  document.getElementById("libAdd").addEventListener("click", async () => {
    try {
      const c = (await libCall("check", {folder: libFolder()})).check;
      libReport.innerHTML = reportHtml(c);
      if (!c.ok) return;
      const notes = c.warnings.length ? `\n\n${c.warnings.join("\n")}` : "";
      if (!confirm(`添加这个书库？(Add this library?)\n${c.path}${notes}\n\n文件夹不会被改动 (The folder isn't changed).`)) return;
      const added = (await libCall("register", {folder: libFolder(), label: libLabel()})).library;
      const twin = added.same_id?.length ? ` — 与“${added.same_id.join("”, “")}”书库标识相同：是副本或移动后的书库，不会合并 (same library id: a copy or a moved library; never merged)` : "";
      toast(`已添加 (Added): ${added.label}${twin}`);
      showLibraries();
    } catch (err) {
      libReport.innerHTML = `<div class="bad">✗ ${esc(err.message)}</div>`;
    }
  });
  document.getElementById("libCreate").addEventListener("click", async () => {
    if (!libFolder()) return toast("先选一个新的或空的文件夹 (Choose a new or empty folder first)");
    if (!confirm(`在这里新建一个空书库？(Create a new, empty library here?)\n${libFolder()}`)) return;
    try {
      const made = (await libCall("create", {folder: libFolder(), label: libLabel()})).library;
      toast(`已新建 (Created): ${made.label}`);
      libReport.innerHTML = "";
      showLibraries();
    } catch (err) {
      libReport.innerHTML = `<div class="bad">✗ ${esc(err.message)}</div>`;
    }
  });
  document.getElementById("libList").addEventListener("click", async e => {
    const button = e.target.closest("[data-lib]");
    if (!button) return;
    const item = button.closest("[data-key]");
    const key = item.dataset.key, label = item.dataset.label;
    try {
      if (button.dataset.lib === "open") return openLibrary({key}, label);
      if (button.dataset.lib === "rename") {
        const name = prompt("新名称 (New label) — 文件夹不改名 (the folder keeps its name)", label);
        if (!name) return;
        await libCall("rename", {key, label: name});
      }
      if (button.dataset.lib === "unregister") {
        if (!confirm(`把“${label}”移出列表？(Remove “${label}” from the list?)\n文件夹和其中的一切都保持不变 (The folder and everything in it stay as they are).`)) return;
        await libCall("unregister", {key});
      }
      if (button.dataset.lib === "relocate") {
        if (!libFolder()) return toast("先在下面填写书库的新文件夹 (Enter the library's new folder below first)");
        const moved = (await libCall("relocate", {key, folder: libFolder()})).library;
        toast(`已更新位置 (Location updated): ${moved.label}`);
      }
      showLibraries();
    } catch (err) {
      toast(err.message);
    }
  });
  document.getElementById("quit").addEventListener("click", async () => {
    if (!confirm("Stop myLibrary? Your place in each book is already saved.")) return;
    try {
      await api("/api/quit", {});
    } catch {}
    document.body.innerHTML = `<div class="stopped"><h1>myLibrary has stopped</h1>
      <p>Start it again from the <b>myLibrary</b> shortcut on your Desktop or in the Start menu.</p></div>`;
  });
  document.getElementById("jobs").addEventListener("click", async e => {
    if (e.target.closest("[data-history]")) {
      historyOpen = !historyOpen;
      try { localStorage.setItem("library-history-open", historyOpen ? "1" : "0"); } catch {}
      return renderJobs(lastJobs);
    }
    if (e.target.closest("[data-clear-history]")) {
      try {
        lastJobs = (await api("/api/jobs", {clear: true})).jobs;
        renderJobs(lastJobs);
      } catch (err) {
        toast(`Couldn't clear: ${err.message}`);
      }
    }
  });
  pollJobs();  // jobs still running from before a reload (e.g. a long OCR)

  // 📇 Review words: the cards due today, one at a time. Space shows the meaning, then
  // 1 = didn't know, 2 (or Space) = knew it; S says the word. The server picks when each
  // word comes back (vocab_review.py).
  const reviewDialog = document.getElementById("reviewDialog");
  const reviewBody = document.getElementById("reviewBody");
  const reviewBook = document.getElementById("reviewBook");
  let reviewCards = [], reviewQueue = [], reviewShown = false, reviewDone = 0, reviewInfo = {};
  let reviewError = "";  // e.g. notes/vocabulary-review.json damaged: shown, never hidden
  async function loadReview() {
    try {
      reviewInfo = await api("/api/review", {});
      reviewError = "";
      reviewCards = reviewInfo.due;
      const count = document.getElementById("reviewCount");
      count.textContent = reviewCards.length;
      count.hidden = !reviewCards.length;
    } catch (e) { reviewError = e.message; }
  }
  function reviewFilter() {
    const counts = new Map(), titles = new Map();
    for (const c of reviewCards) for (const x of c.seen) {
      if (!titles.has(x.id)) titles.set(x.id, x.title);
    }
    for (const c of reviewCards) for (const docId of new Set(c.seen.map(x => x.id)))
      counts.set(docId, (counts.get(docId) || 0) + 1);
    const keep = reviewBook.value;
    const short = t => t.length > 40 ? t.slice(0, 39) + "…" : t;
    reviewBook.innerHTML = `<option value="">所有书 All books (${reviewCards.length})</option>`
      + [...counts].map(([docId, n]) => `<option value="${esc(docId)}">${esc(short(titles.get(docId)))} (${n})</option>`).join("");
    reviewBook.value = counts.has(keep) ? keep : "";
  }
  function startReview() {
    const docId = reviewBook.value;
    reviewQueue = reviewCards.filter(c => !docId || c.seen.some(x => x.id === docId));
    reviewDone = 0;
    showCard();
  }
  function seenLine(card) {
    return card.seen.map(x => {
      const book = books.find(b => b.id === x.id);
      const where = `${esc(x.title)}${x.page ? `, p. ${x.page}` : ""}`;
      return book && !book.pdf_missing
        ? `<a href="${esc(book.pdf_uri + (x.page ? `#page=${x.page}` : ""))}" target="_blank" rel="noopener" title="Open the book at this page">${where}</a>`
        : where;
    }).join(" · ");
  }
  function showCard() {
    const card = reviewQueue[0];
    if (!card) {
      const left = reviewCards.length;
      reviewBody.innerHTML = `<div class="finished">
        <p><b>${reviewDone ? "今天复习完了 (Done for today)" : "现在没有要复习的词 (Nothing to review now)"}</b></p>
        <p class="hint">${reviewDone ? `${reviewDone} answer${reviewDone === 1 ? "" : "s"}. ` : ""}`
        + `${reviewInfo.total || 0} saved words in all, ${reviewInfo.learned || 0} learned (right 4 times in a row).`
        + (left ? ` ${left} still due from other books.` : "")
        + `<br>Save words while reading with <b>加入生词本</b> (Save word).</p></div>`;
      return;
    }
    reviewShown = false;
    const label = card.box === 0 ? "新词 (New word)" : `复习 (Review), box ${card.box}`;
    reviewBody.innerHTML = `<div class="flash">
        <p class="word">${esc(card.word)}</p>
        <p class="phon">${card.phonetic ? `/${esc(card.phonetic)}/` : ""}
          <button type="button" data-say title="读出来 (Say it): S">🔊</button></p>
        <div id="reviewBack" hidden>
          <p class="zh">${esc(card.zh || "—")}</p>
          <p class="seen">${seenLine(card)}</p>
        </div>
      </div>
      <p class="hint" style="text-align:center">${label} · ${reviewQueue.length} to go</p>
      <button type="button" class="primary show" data-show>显示意思 (Show meaning)<small>Space</small></button>
      <div class="answers" hidden>
        <button type="button" class="no" data-knew="0">✗ 不认识<small>Didn't know · 1</small></button>
        <button type="button" class="primary" data-knew="1">✓ 认识<small>Knew it · 2</small></button>
      </div>`;
    reviewBody.querySelector("[data-show]").focus();
  }
  function flip() {
    if (reviewShown || !reviewQueue.length) return;
    reviewShown = true;
    document.getElementById("reviewBack").hidden = false;
    reviewBody.querySelector("[data-show]").hidden = true;
    reviewBody.querySelector(".answers").hidden = false;
    reviewBody.querySelector("[data-knew='1']").focus();
  }
  let replying = false;
  async function reply(knew) {
    if (!reviewShown || replying) return;
    replying = true;
    const card = reviewQueue[0];
    try {
      await api("/api/review", {answer: {word: card.word, knew}});
      reviewQueue.shift();
      reviewDone++;
      if (knew) reviewCards = reviewCards.filter(c => c !== card);
      else reviewQueue.push(card);  // once more before the end of this round
    } catch (err) {
      toast(`Couldn't save the answer: ${err.message}`);
    }
    replying = false;
    showCard();
  }
  function say(word) {
    if (!("speechSynthesis" in window)) return toast("This browser can't read words aloud");
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(word);
    u.lang = "en-US";
    speechSynthesis.speak(u);
  }
  document.getElementById("openReview").addEventListener("click", async () => {
    await loadReview();
    if (reviewError) {
      reviewBody.innerHTML = `<p>⚠ ${esc(reviewError)}</p>`;
      return reviewDialog.showModal();
    }
    reviewFilter();
    startReview();
    reviewDialog.showModal();
    // showModal focuses the book menu (which ignores the keys): start on the card instead
    reviewBody.querySelector("[data-show]")?.focus();
  });
  reviewBook.addEventListener("change", () => {
    startReview();
    reviewBody.querySelector("[data-show]")?.focus();
  });
  document.getElementById("reviewClose").addEventListener("click", () => reviewDialog.close());
  reviewDialog.addEventListener("close", loadReview);  // the count on the button
  reviewBody.addEventListener("click", e => {
    if (e.target.closest("[data-show]")) flip();
    else if (e.target.closest("[data-say]") && reviewQueue[0]) say(reviewQueue[0].word);
    else if (e.target.closest("[data-knew]")) reply(e.target.closest("[data-knew]").dataset.knew === "1");
  });
  reviewDialog.addEventListener("keydown", e => {
    if (e.target === reviewBook || e.ctrlKey || e.altKey || e.metaKey) return;
    if (e.key === " " || e.key === "Enter") { e.preventDefault(); reviewShown ? reply(true) : flip(); }
    else if (e.key === "1") reply(false);
    else if (e.key === "2") reply(true);
    else if (e.key.toLowerCase() === "s" && reviewQueue[0]) say(reviewQueue[0].word);
  });
  loadReview();

  // 📈 Reading log: a line under the title (streak, this week), and the log itself
  const minutes = s => {
    const m = Math.round(s / 60);
    return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h${m % 60 ? ` ${m % 60} min` : ""}`;
  };
  const longDate = iso => new Date(iso + "T12:00:00").toLocaleDateString(undefined,
    {weekday: "short", year: "numeric", month: "short", day: "numeric"});
  let logData = null, logError = "";
  async function loadLog() {
    const link = document.getElementById("openLog");
    try {
      logData = await api("/api/reading-log", {});
      logError = "";
    } catch (e) {
      // A damaged notes/reading-log.json is said, not hidden (it's kept as it is, see safe_io)
      logData = null;
      logError = e.message;
      link.textContent = "· ⚠ Reading log can't be read ›";
      link.title = logError;
      link.hidden = false;
      return;
    }
    link.title = "";
    const parts = [];
    if (logData.streak) parts.push(`🔥 ${logData.streak}-day streak`);
    if (logData.week_seconds) parts.push(`${minutes(logData.week_seconds)} this week`);
    link.textContent = `· 📈 ${parts.length ? parts.join(" · ") : "Reading log"} ›`;
    link.hidden = false;
  }
  function logHtml(d) {
    const level = s => s <= 0 ? 0 : s < 15 * 60 ? 1 : s < 30 * 60 ? 2 : s < 60 * 60 ? 3 : 4;
    const hero = (value, label) => `<div class="hero"><b>${value}</b><span>${label}</span></div>`;
    let months = "", lastMonth = "";
    d.days.forEach((day, i) => {
      if (i % 7) return;
      const m = new Date(day.date + "T12:00:00").toLocaleDateString(undefined, {month: "short"});
      months += `<span>${m !== lastMonth ? esc(m) : ""}</span>`;
      lastMonth = m;
    });
    const cells = d.days.map(day => `<i data-l="${level(day.seconds)}" data-date="${day.date}"`
      + ` data-s="${day.seconds}" data-p="${day.pages}"${day.date === d.today ? ' class="today"' : ""}></i>`).join("");
    const top = Math.max(1, ...d.books.map(b => b.seconds));
    const rows = d.books.map(b => `<tr><td>${esc(b.title)}</td>
      <td class="num">${minutes(b.seconds)}</td><td class="num">${count(b.pages, "page")}</td>
      <td class="num days">${count(b.days, "day")}</td>
      <td class="len"><span style="width:${(100 * b.seconds / top).toFixed(1)}%"></span></td></tr>`).join("");
    const key = [0, 1, 2, 3, 4].map(l => `<i data-l="${l}"></i>`).join("");
    return `<div class="heroes">
        ${hero(d.streak ? `🔥 ${d.streak}` : "0", `day streak (${d.reading_day / 60}+ min a day)`)}
        ${hero(minutes(d.today_seconds), "today")}
        ${hero(minutes(d.week_seconds), `this week · ${count(d.week_pages, "page")}`)}
        ${hero(minutes(d.total_seconds), `in all · ${count(d.reading_days, "reading day")}`)}
      </div>
      <h3>Last ${Math.round(d.days.length / 7)} weeks</h3>
      <div class="cal-wrap"><div class="months">${months}</div><div class="cal" id="logCal">${cells}</div></div>
      <div class="cal-key">less <span class="cal" style="display:flex;gap:3px">${key}</span> more
        <span style="margin-left:8px">(none · under 15 min · 30 · 60 · 60+)</span></div>
      <h3>Books, last 30 days</h3>
      ${rows ? `<table>${rows}</table>`
        : `<p class="empty-log">Nothing yet. Open a book with Start reading or Continue: the time you read is counted from now on.</p>`}
      <p class="hint">Counted while the reading view is open and you're moving through it (two minutes without
        scrolling or turning a page pause the clock). Kept in <code>notes/reading-log.json</code>.</p>`;
  }
  document.getElementById("openLog").addEventListener("click", async () => {
    await loadLog();
    if (!logData && !logError) return toast("Couldn't load the reading log");
    document.getElementById("logBody").innerHTML = logData ? logHtml(logData)
      : `<p>⚠ ${esc(logError)}</p>`;
    if (!logData) return document.getElementById("logDialog").showModal();
    document.getElementById("logDialog").showModal();
    const wrap = document.querySelector("#logBody .cal-wrap");
    wrap.scrollLeft = wrap.scrollWidth;  // this week in view on a narrow screen
  });
  document.getElementById("logClose").addEventListener("click", () => document.getElementById("logDialog").close());
  const tip = document.getElementById("logTip");
  document.getElementById("logBody").addEventListener("pointerover", e => {
    const cell = e.target.closest("#logCal i");
    if (!cell) return void (tip.hidden = true);
    const s = +cell.dataset.s, pages = +cell.dataset.p;
    tip.textContent = `${longDate(cell.dataset.date)}: ${s ? `${minutes(s)}, ${count(pages, "page")}` : "no reading"}`;
    tip.hidden = false;
    const r = cell.getBoundingClientRect();
    tip.style.left = `${Math.min(r.left, innerWidth - tip.offsetWidth - 8)}px`;
    tip.style.top = `${r.top - tip.offsetHeight - 6}px`;
  });
  document.getElementById("logBody").addEventListener("pointerleave", () => { tip.hidden = true; });
  document.getElementById("logDialog").addEventListener("close", () => { tip.hidden = true; });
  window.refreshLog = loadLog;
  loadLog();
}

// Coming back from reading: show the latest page, progress and ticks without a manual refresh.
// The reading tab saves your page as it closes, which can arrive a moment later: check twice.
async function refreshBooks() {
  try {
    const fresh = (await api("/api/books", {})).books;
    books.splice(0, books.length, ...fresh);
    redraw({menus: true, counts: true});
    window.refreshLog?.();  // the minutes just read
  } catch {}  // the server has stopped: keep showing what we have
}
let lastRefresh = 0;
function refreshSoon() {
  if (Date.now() - lastRefresh < 1000) return;  // focus + visibility fire together
  lastRefresh = Date.now();
  refreshBooks();
  setTimeout(refreshBooks, 2000);
}
if (API) {
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") refreshSoon();
  });
  window.addEventListener("focus", refreshSoon);  // e.g. the PDF in another window
}

stats();
renderFields();
renderShelves();
render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    print(f"wrote {paths.display(build())}")
