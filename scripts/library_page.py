"""Build library.html: a local web page for browsing catalog.csv and reading progress.

    uv run scripts/library_server.py   # full version: Read / Continue buttons, tick chapters
    uv run scripts/library_page.py     # static file (add_book.py also rebuilds it)
    start library.html                 # open the static file in your browser

Each book expands to its chapter checklist, read from notes/<slug>/README.md.
The static file is read-only; the server version can open everything for a chapter and
tick chapters off (see library_server.py).
"""

import json
import re
import tomllib
from pathlib import Path
from urllib.parse import quote

import catalog
import paths

LIBRARY = paths.LIBRARY
CATALOG = LIBRARY / "catalog.csv"
PAGE = LIBRARY / "library.html"

PROGRESS_RE = re.compile(r"^- \[([ xX])\] (?:\[(.+?)\]\((.+?)\)|(.+))$", re.MULTILINE)
# Written by the reading view as you turn pages (library_server.save_position)
LAST_READ_RE = re.compile(
    r"^Last read: page (\d+)(?: \((.+)\))?, (\d{4}-\d{2}-\d{2})$", re.MULTILINE
)


def last_read(slug: str) -> dict | None:
    """{page, chapter, date} from the "Last read:" line in notes/<slug>/README.md."""
    readme = LIBRARY / "notes" / slug / "README.md"
    if not readme.exists():
        return None
    m = LAST_READ_RE.search(readme.read_text(encoding="utf-8"))
    return {"page": int(m[1]), "chapter": m[2] or "", "date": m[3]} if m else None


def chapters(slug: str) -> list[dict]:
    readme = LIBRARY / "notes" / slug / "README.md"
    if not readme.exists():
        return []
    result = []
    for m in PROGRESS_RE.finditer(readme.read_text(encoding="utf-8")):
        title = m[2] or m[4]
        number = re.match(r"(?:Ch(?:apter)?\.?\s*)(\d+)", title)
        result.append(
            {
                "done": m[1] != " ",
                "title": title,
                "number": int(number[1]) if number else None,
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


def books(pdf_base: str | None = None) -> list[dict]:
    """Catalog rows plus chapter progress; pdf_base is the server URL prefix for PDFs."""
    result = []
    for row in catalog.load(CATALOG).values():
        pdf = LIBRARY / row["file"]
        result.append(
            row
            | {
                "chapter_list": chapters(row["slug"]),
                "shelf_list": catalog.split_list(row.get("shelves") or ""),
                "last_read": last_read(row["slug"]),
                "pdf_missing": not pdf.exists(),
                "pdf_uri": f"{pdf_base}/{pdf.name}" if pdf_base else pdf.as_uri(),
                "notes_uri": "vscode://file/"
                + quote((LIBRARY / row["notes"]).as_posix(), safe="/:"),
            }
        )
    return result


def render(api: dict | None = None, pdf_base: str | None = None) -> str:
    """The page HTML; with `api` (from library_server.py) the Read buttons are enabled."""
    data = json.dumps(books(pdf_base), ensure_ascii=False).replace("</", "<\\/")
    labels = json.dumps(shelf_labels(), ensure_ascii=False).replace("</", "<\\/")
    return (
        TEMPLATE.replace("__DATA__", data)
        .replace("__API__", json.dumps(api))
        .replace("__SHELF_LABELS__", labels)
    )


def build() -> Path:
    PAGE.write_text(render(), encoding="utf-8")
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
.controls { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; }
.controls input, .controls select { font: inherit; color: var(--text); background: var(--surface);
  border: 1px solid var(--line); border-radius: 8px; padding: 9px 12px; }
.controls input { flex: 1 1 260px; }
.grid { display: grid; gap: 14px; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
  padding: 16px 18px; display: flex; flex-direction: column; gap: 8px; }
.card h2 { margin: 0; font-size: 17px; line-height: 1.3; }
.byline { color: var(--muted); font-size: 14px; }
.meta { display: flex; gap: 14px; flex-wrap: wrap; color: var(--muted); font-size: 13px; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip.shelf { background: var(--done); color: #fff; }
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
.actions .read { background: var(--accent); color: var(--surface); border-color: var(--accent);
  font-weight: 600; }
.actions .read:hover { filter: brightness(1.1); }
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
.empty { color: var(--muted); padding: 40px 0; text-align: center; }
footer { color: var(--muted); font-size: 12.5px; margin-top: 28px; }
code { font-size: 12.5px; }
</style>
</head>
<body>
<main>
  <header>
    <h1>myLibrary</h1>
    <p class="stats" id="stats"></p>
  </header>
  <div class="controls">
    <input id="q" type="search" placeholder="Search title, author, ISBN, subject, chapter…" autofocus>
    <select id="sort">
      <option value="title">Sort: title</option>
      <option value="author">Sort: author</option>
      <option value="year">Sort: newest</option>
      <option value="progress">Sort: progress</option>
      <option value="added">Sort: recently added</option>
    </select>
  </div>
  <nav class="shelves" id="shelves" aria-label="Shelves"></nav>
  <div class="grid" id="grid"></div>
  <footer id="footer"></footer>
</main>
<div class="toast" id="toast" role="status"></div>
<script type="application/json" id="data">__DATA__</script>
<script>
const API = __API__;  // set when served by library_server.py; null in the static file
const books = JSON.parse(document.getElementById("data").textContent);
const SHELF_LABELS = __SHELF_LABELS__;  // from library.toml: {"Optics": "光学 Optics"}
const shelfLabel = name => SHELF_LABELS[name] || name;
let shelf = "";  // the shelf being shown ("" = all books)
try { shelf = localStorage.getItem("library-shelf") || ""; } catch {}
document.getElementById("footer").innerHTML = API
  ? `<b>Read</b> opens the PDF at the chapter, and its notes in VS Code. <b>Script</b> opens a
     Python script for checking the chapter's worked examples (created the first time).
     The page you're on is saved as you read; <b>Continue · p. N</b> takes you back there.
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

// The shelf bar: All, then every shelf in use, with how many books are on it
function renderShelves() {
  const counts = new Map();
  for (const b of books) for (const s of b.shelf_list) counts.set(s, (counts.get(s) || 0) + 1);
  if (shelf && !counts.has(shelf)) shelf = "";
  const names = [...counts.keys()].sort((a, b) => counts.get(b) - counts.get(a) || a.localeCompare(b));
  const button = (name, label, n) =>
    `<button type="button" data-shelf="${esc(name)}" class="${name === shelf ? "on" : ""}">`
    + `${esc(label)}<span class="count">${n}</span></button>`;
  document.getElementById("shelves").innerHTML = names.length
    ? button("", "All", books.length) + names.map(s => button(s, shelfLabel(s), counts.get(s))).join("")
    : "";
}

function stats() {
  const ch = books.reduce((n, b) => n + b.chapter_list.length, 0);
  const dn = books.reduce((n, b) => n + done(b), 0);
  const pages = books.reduce((n, b) => n + (+b.pages || 0), 0);
  document.getElementById("stats").textContent =
    `${books.length} books · ${pages.toLocaleString()} pages · ${dn} of ${ch} chapters read`;
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

function chapterItem(c) {
  const tick = API
    ? `<input type="checkbox" data-tick="${c.number}" ${c.done ? "checked" : ""} aria-label="Read">`
    : `<span class="tick">${c.done ? "✓" : ""}</span>`;
  const read = API && c.number != null
    ? `<button type="button" data-read="${c.number}">Read</button>`
      + `<button type="button" data-script="${c.number}" title="A Python script to check this chapter's worked examples">Script</button>`
    : "";
  return `<li class="${c.done ? "done" : ""}">${tick}<span class="name">${esc(c.title)}</span>${read}</li>`;
}

function card(b) {
  const subjects = (b.subjects || "").split(";").map(s => s.trim()).filter(Boolean).slice(0, 4);
  const n = b.chapter_list.length;
  const chapters = b.chapter_list.map(chapterItem).join("");
  const next = nextChapter(b);
  return `<article class="card" data-slug="${esc(b.slug)}">
    <h2>${esc(b.title)}</h2>
    <div class="byline">${esc((b.authors || "").replaceAll(";", ","))}</div>
    <div class="meta">
      ${b.year ? `<span>${esc(b.year)}</span>` : ""}
      ${b.publisher ? `<span>${esc(b.publisher)}</span>` : ""}
      ${b.pages ? `<span>${esc(b.pages)} pages</span>` : ""}
      ${b.isbn ? `<span>ISBN ${esc(b.isbn)}</span>` : ""}
    </div>
    ${b.shelf_list.length || subjects.length ? `<div class="chips">${b.shelf_list.map(s => `<span class="chip shelf">${esc(shelfLabel(s))}</span>`).join("")}${subjects.map(s => `<span class="chip">${esc(s)}</span>`).join("")}</div>` : ""}
    <div class="progress"><div class="bar"><span style="width:${Math.round(pct(b) * 100)}%"></span></div>
      ${n ? `${done(b)}/${n} chapters` : "no chapters"}${pct(b) > 0 ? ` · ${Math.round(pct(b) * 100) || "<1"}%` : ""}</div>
    ${b.last_read ? `<div class="next">Last read: page ${b.last_read.page}${b.last_read.chapter ? ` · ${esc(b.last_read.chapter)}` : ""} · ${esc(b.last_read.date)}</div>`
      : API && next && done(b) < n ? `<div class="next">Next: ${esc(next.title)}</div>` : ""}
    <div class="actions">
      ${readButton(b)}
      ${b.pdf_missing ? `<span class="missing" title="books/${esc(b.slug)}.pdf is gone; notes and scripts are still here">PDF missing</span>`
        : `<a href="${esc(b.pdf_uri)}" target="_blank" rel="noopener">PDF</a>`}
      <a href="${esc(b.notes_uri)}">Notes</a>
      ${b.openlibrary ? `<a href="${esc(b.openlibrary)}" target="_blank" rel="noopener">Open Library</a>` : ""}
      ${n ? `<button type="button" data-toggle>Chapters</button>` : ""}
      ${API ? `<button type="button" data-shelves title="Which shelves this book is on">Shelves</button>` : ""}
    </div>
    ${n ? `<ol class="chapters" hidden>${chapters}</ol>` : ""}
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
  }[sort.value];
  const shown = books
    .filter(b => !shelf || b.shelf_list.includes(shelf))
    .filter(b => {
      const hay = [b.title, b.authors, b.year, b.publisher, b.isbn, b.subjects,
                   ...b.shelf_list, ...b.shelf_list.map(shelfLabel),
                   ...b.chapter_list.map(c => c.title)].join(" ").toLowerCase();
      return words.every(w => hay.includes(w));
    })
    .sort(keyed);
  grid.innerHTML = shown.length ? shown.map(card).join("")
    : `<p class="empty">No books match “${esc(q.value)}”.</p>`;
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
    headers: {"Content-Type": "application/json", "X-Library-Token": API.token},
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

const bookOf = el => books.find(b => b.slug === el.closest(".card").dataset.slug);
const openLists = () => new Set([...grid.querySelectorAll("ol.chapters:not([hidden])")]
  .map(ol => ol.closest(".card").dataset.slug));

document.getElementById("shelves").addEventListener("click", e => {
  const button = e.target.closest("[data-shelf]");
  if (!button) return;
  shelf = button.dataset.shelf;
  try { localStorage.setItem("library-shelf", shelf); } catch {}
  renderShelves();
  render();
});

grid.addEventListener("click", async e => {
  const edit = e.target.closest("[data-shelves]");
  if (edit && API) {
    const b = bookOf(edit);
    const answer = prompt(
      `Shelves for “${b.title}”, separated by ; (e.g. Optics; Lasers):`, b.shelf_list.join("; "));
    if (answer === null) return;
    try {
      const r = await api("/api/shelves", {slug: b.slug, shelves: answer});
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
      const r = await api("/api/script", {slug: bookOf(script).slug, chapter: +script.dataset.script});
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
      const r = await api("/api/open", {slug: b.slug, chapter, resume});
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
  const keepOpen = openLists();
  try {
    const r = await api("/api/tick", {slug: b.slug, chapter: +box.dataset.tick, done: box.checked});
    b.chapter_list = r.chapter_list;
    stats();
    render();
    keepOpen.forEach(slug => grid.querySelector(`.card[data-slug="${CSS.escape(slug)}"] ol.chapters`)
      ?.removeAttribute("hidden"));
  } catch (err) {
    box.checked = !box.checked;
    toast(`Couldn't save: ${err.message}`);
  }
});
q.addEventListener("input", render);
sort.addEventListener("change", () => {
  try { localStorage.setItem("library-sort", sort.value); } catch {}
  render();
});
stats();
renderShelves();
render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    print(f"wrote {paths.display(build())}")
