# myLibrary

A general study tool for learning from your own PDF books (any subject): reading view with
English–Chinese lookup and subject glossaries, book search, progress, shelves, notes, topic notes,
and per-chapter Python scripts for checking a book's worked examples. No marimo/notebooks.
Keep the tool subject-neutral: nothing in `scripts/` should assume optics. The repo is public;
the books never go in it. See README.md.

## Tool vs. library (always keep them apart)

- **The tool**: `scripts/`, `tests/`, docs, `pyproject.toml`. Its own cache (`.cache/reader/`:
  PDF.js + ECDICT) is shared by every library.
- **A library**: one folder with everything personal, for all subjects. `scripts/paths.py`
  decides which: `--library`, env `MYLIBRARY_LIBRARY`, `local.toml` (gitignored), else a new
  `Documents/myLibrary Library` (created and remembered on first start). Scripts use
  `paths.LIBRARY` for data and `paths.APP` for the tool; never build data paths from the
  script's own location.
- **The user's library is `library/` in this repository** (their `local.toml` says
  `library = "library"`), public as a live example. Their subject is optical design.

**Settings** (`paths.load_settings()` / `save_settings()`): library, `editor` (vscode / notepad /
system / custom + `editor_command` with `{file}`), `python_features`. Stored in `local.toml`, or
in the package in `%APPDATA%/myLibrary/settings.toml`. Notes always open through
`library_server.open_in_editor()`, never a hard-wired editor; never open a `.py` with its default
app (that can run it). The library page's ⚙ Settings edits them; changing the library restarts
the server (`restart_later`).

**The library page does everything without a terminal**: ＋ Add books (upload →
`library_jobs.py`: identify, name, register in the background; asks for missing title/author/year),
OCR button for scans (background, progress), Settings, Quit. Keep it that way: every feature the
package needs must work from the page.

**The ready-to-use package** (paid, 9.9 RMB): `uv run scripts/build_package.py` builds
`dist/myLibrary-<version>-win64.zip` from `package/` (launcher `launch.py` with pythonw + log,
`Start myLibrary.cmd`, bilingual `README.txt`, ECDICT license) plus a portable Python with only
the core dependencies, PDF.js and the dictionary. `package.toml` marks package mode
(`paths.IS_PACKAGE`): Python features off. Test a build unzipped in a clean environment (no uv
on PATH, its own USERPROFILE/APPDATA) before calling it done.

Inside a library: `library.toml` (name, `[shelves]` labels like `Optics = "光学 Optics"`),
`catalog.csv`, `books/` (never in git), `notes/<slug>/`, `notes/topics/<topic>.md`,
`glossaries/<name>.csv` + `glossaries.toml`, `examples/<slug>/chNN_*.py`, `code/` (reusable code
by subject, e.g. `code/optics/paraxial.py`, with `code/tests/`; on pytest's path),
`library.html`, `archive/` and `.cache/` (local only).

**Chinese always comes with English (always apply).** Wherever Chinese appears in the UI, docs,
messages, file headers or config (buttons, labels, tooltips, README examples, glossary and shelf
labels), put its English translation next to it: in the popup use `bi(zh, en)` / `biEl(...)` in
`lookup.js` (Chinese, then the English smaller and grey); in text write e.g.
"**加入生词本** (Save word)" or "光阑 (aperture stop)". The glossary's `zh` column is the Chinese
term itself (its English is the `term` column); its `note` and `definition` texts are still
Chinese only.

## New books: naming convention (always apply)

When a new book file appears in the library's `books/` (or the user mentions adding one), run:

```
uv run scripts/add_book.py --dry-run   # check the proposed slug first
uv run scripts/add_book.py
```

Each book gets one slug, `<first-author-surname>-<year>-<short-title>`, lowercase ASCII,
hyphen-separated, stop words (a, the, of, and, ...) dropped, subtitle dropped, at most 5 title words.
Example: `shannon-1997-art-science-optical-design`. The slug is used (inside the library) for:

- `books/<slug>.pdf` (the book itself; never commit or push a book: `.gitignore` excludes every
  PDF, don't undo that)
- `notes/<slug>/README.md` (metadata + reading progress, incl. the "Last read" line) and
  `notes/<slug>/chNN-<chapter>.md`
- `examples/<slug>/` (plain Python scripts `chNN_<topic>.py`, created only when the user clicks
  "Script" on a chapter; the template puts the library's `code/` on the import path)

- `catalog.csv` (one row per book: title, authors, year, publisher, ISBN, pages, chapters,
  subjects, shelves, where each field came from; the original download file name is
  deliberately not recorded). After adding a book, suggest shelves for it (the user's are in
  `library/library.toml`). The user browses it with `uv run scripts/library_server.py` (local
  server: shelf bar; Read/Continue opens the PDF at the chapter page and the chapter's notes in
  VS Code, plus its script if one exists; "Script" creates/opens the chapter script; "Shelves"
  edits a book's shelves; ticking chapters edits notes READMEs).
  The server opens PDFs in PDF.js with a word lookup for the user (a Chinese reader):
  `scripts/reader.py` + `scripts/reader_static/`. Glossaries rank first when they match the
  book's shelves (the user's is `optics.csv`, label "光学 Optics": extend it with real optics
  terms). Full-text search of all books per page: `scripts/book_search.py` (index in the
  library's `.cache/books.db`). Saved words: `notes/<slug>/vocabulary.md`. Topic notes
  (📝 主题笔记 / Topic note in the popup): `notes/topics/<term>.md`, created with book + page
  references only (never book text). These are the user's own work: never delete them.
  `library.html` is the static read-only copy (built by `scripts/library_page.py`, rebuilt by
  add_book.py). Chapter start pages are cached in the library's `.cache/chapter_pages.json`
  (`--refresh-chapters` clears a book's entry automatically).
- To take a book out, use `uv run scripts/add_book.py --remove <slug>`: it moves the PDF, notes
  and scripts to the library's `archive/` and drops the catalog row. Never delete notes or
  scripts outright; they hold the user's own work. Rebuild the page after changing catalog or
  notes. If the user corrects a book's details, update its catalog row and notes README too.

Books are always PDFs (the user's choice; don't add DjVu/EPUB tooling). The script reads the
PDF's table of contents (bookmarks, else the printed Contents pages; for image-only scans the
Contents pages are read with OCR by `scripts/book_ocr.py`, cached in the library's `.cache/ocr/`;
better: `scripts/ocr_pdf.py` gives a scan a real invisible text layer, which add_book.py offers
for new scans, original kept in `archive/books/`; every add_book.py run ends by asking about each
scan still in `books/`, as the user asked) and writes one empty notes
template per chapter with the section headings. Templates hold headings only: never paste book
text into notes; the user writes the notes in their own words. If the chapter list looks wrong
(missing or placeholder "Chapter N" titles), fix the templates by checking the book's contents.

Filenames vary wildly, so `scripts/book_meta.py` identifies the book from, in order: an ISBN in
the filename or on the first pages (looked up on Open Library), the PDF metadata, the cleaned
filename, the copyright line, and finally an Open Library title search. The dry run prints where
each field came from; double-check anything marked "filename" or "check the edition".

If the script can't identify the book, or the slug looks bad (wrong author, edition year instead
of first publication, awkward title), check the real title/author/year and rerun with
`uv run scripts/add_book.py "<library>/books/<file>" --author .. --year .. --title ..`.
Prefer the year of the edition actually on disk; different editions get different slugs.

Files open in VS Code can be stale: if the user has a note open while you change it, their next
save can overwrite your change. After editing notes, check the file on disk again later.
