# myLibrary

A general study tool for learning from your own PDF books (any subject): reading view with
English–Chinese lookup and subject glossaries, book search, progress, shelves, notes, topic notes,
and per-chapter Python scripts for checking a book's worked examples. No marimo/notebooks.
Keep the tool subject-neutral: nothing in `scripts/` should assume optics. The repo is public;
the books never go in it. See README.md (the project homepage) and docs/USER_GUIDE.md (the
full bilingual manual). Its three pillars are learning, reading and note-taking; executable
learning (chapter scripts, `code/`) is an optional differentiator, never a required path.

## Working on this project (always apply)

**Where things are (restructured 2026-11-09):**
- `ROADMAP.md`: the active plan. Section 2 names **the current approved milestone**; section
  11 is the current list of open bugs and limitations (IDs like D18, B5, L20).
- `docs/history/ROADMAP_HISTORY.md`: the earlier roadmap, kept unchanged: the architecture
  and gap analysis of 2026-11-06, full bug descriptions, task designs (task 4's section 5:
  notes and passages, approved decisions), verification records. Read the parts the current
  milestone needs.
- `DEVELOPMENT_SPEC.md`: the product and technical spec (pillars, requirements FR-*, the
  anchor model, data safety, non-goals); `docs/history/DEVELOPMENT_SPEC_v1.md` is the original
  brief.
- `docs/COMPETITIVE_ANALYSIS.md`: the qualified comparison with BookxNote Pro, MarginNote 5 and
  Zotero 10 (sources, verification dates). Don't add competitor claims without a source.
- `docs/USER_GUIDE.md`: the user manual (formerly the README); `docs/LIBRARIES.md`: several
  libraries and the Test & Demo library.

At the start of any development session, read ROADMAP.md, and DEVELOPMENT_SPEC.md for the
goals, principles and constraints (local-first, offline-first, optional network and AI, no
destructive migrations, no rewrites). Work through the current milestone (ROADMAP section 2)
in order; don't start the next milestone, the later priorities (P2–P5) or the proposed new
items (E1–E4, R1–R3), or features outside it, unless the user asks; a competitor's feature is
no reason to change the order. Keep ROADMAP.md current in the same change as the code: tick
finished items with their commit, add bugs and limitations you find to section 11 (name the
function or file; line numbers drift), move ones you fix to "fixed", and update DEVELOPMENT_SPEC
when the architecture changes. Never edit the history files except to fix a broken link. If a
plan changes, change the file rather than leaving it stale. Don't claim a feature works unless
it was verified; say when browser, Windows-specific or package testing wasn't done. Keep the
user guide's feature-status table (section 15) in step.

**Document identity: the UUID, and only the UUID (v0.3 task 3).**
- Every document has a permanent UUID4 in `catalog.csv`'s `id` column. `catalog.load()`
  returns `{id: row}`.
- The id is the only identity:
  - every per-document API takes `id`;
  - the reading log is keyed by id;
  - the search index, chapter-page cache and jobs (`doc_id`) use it;
  - the reader gets `&id=`;
  - `/read/<id>` is the lasting link;
  - all new references (anchors, annotations, topic links) use it.
- The `slug` is only the human-readable name: the base of the file and folder names
  (`books/<slug>.pdf`, `notes/<slug>/`, `examples/<slug>/`). Find a document's paths through
  its row (`file`, `notes`; `add_book.notes_dir_of`, `examples_dir_of`), never by building them
  from a slug you were given. `catalog.by_slug` is only for a name a person typed, or a file's
  own name.
- A document leaving the library leaves a tombstone in `retired-documents.json`
  (`catalog.retire` before `catalog.remove`):
  - merged into another: `resolve()` follows it, and its reading history counts for the kept
    document, with the records never rewritten;
  - removed: it keeps its title.
- Renaming (`add_book.rename_document`) is journaled in `.myLibrary/operations/`.
  `recover_operations()` at start rolls back an interrupted one.
- An old-format catalog (no `id`) is refused, never upgraded silently: the one-time
  `scripts/migrate_ids.py` (dry run, `--apply`, `--resume`, `--rollback`, `--check`; journal and
  backups in `.myLibrary/migrations/`) converts it. Never add a slug-keyed reference or a
  compatibility layer back.

**Protect the user's data.** Notes, vocabulary, topic notes, reading log, review progress,
marks in PDFs, `catalog.csv` and `library.toml` are the user's work. Never delete them; move to
the library's `archive/` (`add_book.move_to_archive`, which refuses anything outside the
library's folders).

**Write files through `scripts/safe_io.py`, never with `Path.write_text` or `open("w")`:**
- `write_text`/`write_bytes` are atomic, also past Windows' 260-character path limit
  (`safe_io._os_path` at the OS call). Checking or following a path that may be long goes
  through `safe_io.exists`/`is_file`/`real_path`, not `Path.exists`/`resolve`.
- A read-change-write goes through `update_text`/`update_json` (they take the file's lock), or
  holds `safe_io.lock_for(path)`.
- Catalog changes go through `catalog.upsert`/`set_field`/`remove`.
- JSON goes through `load_json`: `cache=True` for rebuildable caches; user data keeps a `.bak`
  and raises `DamagedFile` rather than being replaced.
- Several threads write at once (one per job, plus request threads).
- Steps that move PDFs or take a name hold `add_book.FILING`. Keep anything slow or online out
  of it.
- Multi-step operations that must not be cut off by Quit run inside `safe_io.critical()`.
- Long jobs check `library_jobs._stopping` at safe points.

**The user's standing rules for development (2026-11-06):**
- Never modify, delete, migrate or overwrite files in the real `library/`.
- Test destructive, concurrency, damage and recovery cases only in temporary folders with
  invented data.
- Don't reset, clean or normalize the line-ending-only changes git shows under `library/`.
- Don't revert or overwrite `library/notes/reading-log.json`.
- No broad staging (`git add -A`, `git add .`).
- No automatic commits or pushes.
- Explain any production data migration and get agreement before implementing it.

**Checks before calling a change done:** `uv run pytest`, `uv run ruff check .`,
`uv run ruff format --check .` (CI runs the same on Windows). Add or update tests for every
behavior change; test with a temporary library (see `tests/conftest.py`), never the real one.
For reader changes (`reader_static/`, `/read`, saving marks), run and extend the browser tests:
`uv sync --group browser`, then `uv run pytest tests/browser` (Edge; each test on its own
temporary library, settings and server; CI job `browser`). Plain `pytest` leaves them out.
The library page's JavaScript (`library_page.py`) has no tests yet: try it in the browser with
`uv run scripts/library_server.py --port <other port>` and say what you checked.

**Environment:** Windows, Python 3.14 via uv (installed with winget). A terminal opened before
uv was installed won't find it; restart VS Code. Use forward-slash paths and UTF-8 explicitly
when reading/writing text.

**Versions:** `pyproject.toml` `version` is the package version; bump it and rebuild the
package only when the user asks for a package release.

## Product direction: a desktop app later, packaging-friendly now (always apply)

myLibrary is a local-first academic PDF reading, annotation and notes application. It keeps
its Python backend and HTML/CSS/JS frontend (PDF.js, Markdown notes, SQLite and local files,
UUID identity), and will later ship as a Windows desktop app (EXE/installer, a webview window)
**without rewriting the interface**.
- No Electron, React, Qt or other framework switch without a specific reason and the user's
  approval.
- No EXE, installer, desktop-window or licence work until the packaging milestone (ROADMAP
  section 9; details in the history's section 8).
- Core features come first.

Rules for all new code:
- **Resources:**
  - Find the tool's files through `paths.APP`, never the working directory or absolute
    paths.
  - Bundled resources are read-only: PDF.js, Markdown and maths renderers, CSS, fonts.
  - Frontend assets are local files, pinned and checksum-verified, loaded without a network.
    No CDNs at runtime, and no build step.
- **User data:**
  - Data lives only in the library (`paths.LIBRARY`) or the settings file. That covers
    PDFs, notes, marks, vocabulary, reading history, catalog and ids, indexes and caches,
    settings, reference metadata, and migration journals and backups.
  - Never write into the installation folder or a temporary extraction folder.
  - Updates and reinstalls must leave it untouched.
  - Moving the data elsewhere later needs an explicit, verified, backed-up and reversible
    migration, agreed first.
- **Server:**
  - It listens on 127.0.0.1 only, with a configurable port. The port is never part of a
    stored identity: links are found by the `/read/<id>` path, whatever the host and port.
  - It must keep working from a browser (development) and when started by a future desktop
    wrapper: clean startup and shutdown, and the existing duplicate-instance check.
- **Dependencies:** light, pinned, no global tools assumed. Without PDF.js in development,
  the plain-PDF fallback stays.

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

**The library page does everything without a terminal**: ＋ Add (upload →
`library_jobs.py`: identify, name, register in the background; never asks: `book_meta.fill_gaps`
fills a missing title/year/author from the PDF itself; a name this tool gave before is not
trusted (`OUR_NAME_RE`); repeats (`add_book.repeat_of`: same DOI, same ISBN for non-papers, identical file by
SHA-256 with size prefilter; a name or title alone never is, see Task 2 in docs/history/ROADMAP_HISTORY.md) always go
to `archive/` from every path, CLI included;
the richer copy wins (`info_score`: text layer, filled INFO_FIELDS, bookmarks, pages): on
adding, a better *file* replaces the PDF in place (`replace_pdf`), details always merge
(`fill_details`); Refresh runs `catalog_repeats` (keeps the richer entry, ties: the older),
`merge_into` copies the other's work (ticks, Last read, written notes into the matching
chapter template, vocabulary, scripts, shelves) before archiving it; both with work: report only; Settings → Clear archive (`library_jobs.clear_archive`) deletes only
documents (.pdf/.djvu/.epub), empty note templates and .gitkeep, and keeps everything else; ⟳ Refresh = `library_jobs.refresh`;
`cryptography` is a core dependency because publisher PDFs are often AES-encrypted),
OCR button for scans (background, progress), ☁ Back up (`scripts/backup.py`: commits only the
library folder with `--only`, refuses when unpushed commits touch code, never prompts for a
password; shown only when the library is in a repo with an upstream), 💾 Back up
(`scripts/folder_backup.py`: dated zip of everything but PDFs/archive/caches in the Settings
`backup_folder`, `KEEP` 30; with `backup_pdfs`, on in the package, PDFs copied once into
`PDFs/`, never deleted there; `auto_backup` once a day at start, only if something changed;
shown without git or with a folder set), Settings (incl. `openalex_key`: sent as a Bearer
header to api.openalex.org only, checked on save; never ask OpenAlex for a key on the user's
behalf), Quit. Keep it that way: every feature the
package needs must work from the page.

**The ready-to-use package** (paid, 9.9 RMB): `uv run scripts/build_package.py` builds
`dist/myLibrary-<version>-win64.zip` from `package/` (launcher `launch.py` with pythonw + log,
`Start myLibrary.cmd`, bilingual `README.txt`, ECDICT license) plus a portable Python with only
the core dependencies, PDF.js and the dictionary. `package.toml` marks package mode
(`paths.IS_PACKAGE`): Python features off. Test a build unzipped in a clean environment (no uv
on PATH, its own USERPROFILE/APPDATA) before calling it done. The launcher's shortcuts go to
the real Desktop and Start menu whatever the profile, so first write the unzipped folder's
path to `<test APPDATA>/myLibrary/shortcuts-for.txt` (skips them), use another `--port`, and
Quit the test server afterwards.

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
Example: `shannon-1997-art-science-optical-design`. The slug is the document's name, never its
identity (that's its `id`, see above). Inside the library it's the base of:

- `books/<slug>.pdf` (the book itself; never commit or push a book: `.gitignore` excludes every
  PDF, don't undo that; its one narrow exception is the public, synthetic `test_library/`,
  see docs/LIBRARIES.md and test_library/README.md)
- `notes/<slug>/README.md` (metadata + reading progress, incl. the "Last read" line) and
  `notes/<slug>/chNN-<chapter>.md`
- `examples/<slug>/` (plain Python scripts `chNN_<topic>.py`, created only when the user clicks
  "Script" on a chapter; the template puts the library's `code/` on the import path)

- `catalog.csv` (one row per book: title, authors, year, publisher, ISBN, pages, chapters,
  subjects, shelves, where each field came from; the original download file name is
  deliberately not recorded). After adding a book, suggest shelves for it (the user's are in
  `library/library.toml`). The user browses it with `uv run scripts/library_server.py` (local
  server: shelf bar; Read/Continue opens the PDF at the chapter page with the chapter's notes in
  the reader's 📝 panel, plus its script in the editor if one exists (the notes open in the
  editor too only without the reading view: task 4 M4 decision D5); "Script" creates/opens the chapter script; "Shelves"
  edits a book's shelves; ticking chapters edits notes READMEs).
  The server opens PDFs in PDF.js with a word lookup for the user (a Chinese reader):
  `scripts/reader.py` + `scripts/reader_static/`. Glossaries rank first when they match the book's shelves, subject or field by word (`reader.book_subject_words`: "Advanced optical system
  design" matches the `optics` glossary; the user's is `optics.csv`, label "光学 Optics": extend
  it with real optics terms). Full-text search of all books per page: `scripts/book_search.py` (index in the
  library's `.cache/books.db`). Marks made with PDF.js's
  editor tools are saved into the library's PDF (`lookup.js` `keepMarks`: `saveDocument()` a
  few seconds after the annotation hash stops changing → `/api/save-marks` →
  `reader.save_marks`: whole PDF, same page count, original kept once in
  `archive/before-marks/`). 📈 Reading log: `lookup.js`
  `trackReading` (active time: visible + activity within 2 min; pages seen) → `/api/reading` →
  `scripts/reading_log.py` → the library's `notes/reading-log.json`; the stats line links to
  the log (`/api/reading-log`). Saved words: `notes/<slug>/vocabulary.md`;
  📇 Review words (library page, `scripts/vocab_review.py`, `/api/review`) turns them into
  spaced-repetition cards (one per word across books; Leitner boxes `BOX_DAYS`; progress in
  the library's `notes/vocabulary-review.json`; never edits the vocabulary files). Topic notes
  (📝 主题笔记 / Topic note in the popup): `notes/topics/<term>.md`, created with book + page
  references only (never book text). These are the user's own work: never delete them.
  📝 Notes panel (task 4 M3, M4: editing as Markdown source): `reader_static/notes.js` +
  `notes.css`, beside PDF.js (`--ml-notes-space` narrows `#outerContainer`; PDF.js gets an
  explicit `resize` event; container queries mirror PDF.js's toolbar breakpoints). The text
  and its saving are `note_session.js`'s `NoteSession` (one per note: revisions, one save in
  flight, base versions and 409 conflicts, retries, offline, a restarted server (403: reload
  needed), recovery drafts in `localStorage`, version checks). Future preview and visual modes
  are views of the same session, never a second save path, and never lossy. It uses
  lookup.js's `window.myLibraryReader` and only `/api/notes/list|get|version|save|keep-copy|open`,
  by document id and note key, never a path. Opening or viewing writes nothing; never position
  or reading time; lookup.js leaves the panel alone (`inNotes`). Browser tests:
  `test_notes_panel.py`, `test_notes_content.py`, `test_notes_editing.py`,
  `test_notes_failures.py`, `test_notes_conflicts.py`; `--notes-closed` runs any of them with
  the panel closed. A browser test is stopped after 180 s (pyproject `faulthandler_timeout`);
  test servers start through `tests/browser/owned_processes.py` (a job object: never orphaned).
  `library.html` is the static read-only copy (built by `scripts/library_page.py`, rebuilt by
  add_book.py). Chapter start pages are cached in the library's `.cache/chapter_pages.json`
  (`--refresh-chapters` clears a book's entry automatically).
- To take a book out, use `uv run scripts/add_book.py --remove <name or id>`: it moves the PDF, notes
  and scripts to the library's `archive/` and drops the catalog row. Never delete notes or
  scripts outright; they hold the user's own work. Rebuild the page after changing catalog or
  notes. If the user corrects a book's details, update its catalog row and notes README too.

**Papers** live in the library's `papers/` folder (catalog `type` = paper, `file` =
`papers/<slug>.pdf`, plus journal / volume / issue / page_range / doi). `book_meta.identify`
tries, in order: a DOI in the PDF metadata and first two pages only (never the references) →
Crossref (`crossref()`; types in `PAPER_TYPES` are papers, others books); an arXiv number →
`arxiv()` (journal version if published); for files in `papers/` or that look like papers, the
top of page 1 → `crossref_search()` (accepted only if the whole title is on the page). A PDF in
`papers/` is always a paper (`identify(..., paper=True)`); recognised papers move to `papers/`.
PDFs are served from `/books/` and `/papers/`; links use the catalog's `file`. A paper's notes: README with one checklist item
`library_page.PAPER_ITEM` ("Read the paper", counts as chapter 1) + `notes.md`. Citations
(Cite button): `scripts/citation.py` (BibTeX).

**Theses** live in the library's `theses/` folder (catalog `type` = thesis, plus `degree`
PhD/Master/Bachelor/Diploma, `institution`, `supervisors`; `publisher` stays empty).
`scripts/thesis_meta.py` recognises one by its title page (`find_title_page`: formulas such as
"thesis submitted", "Dissertation zur Erlangung", "Proefschrift", "博士学位论文" (doctoral
dissertation), on a sparse page or as a line of its own) and fills details from: a DOI →
Crossref (`dissertation` type) or DataCite (`doi_csl`); arXiv (its comment); OpenAlex
`type:dissertation`; the title page (title = largest font, author after "by"/"von"/"door",
degree, university, supervisors). The page's printed year and spelling win when they agree.
A thesis has chapters like a book. A PDF in `theses/` is always a thesis.

**Subjects**: `scripts/subjects.py`: OpenAlex topics (DOI, else title search filtered by
title and author, all matching records' topic scores added up) -> catalog `field`, `topic`,
`topic_score`; `SURE` = 0.5 makes the topic a shelf (`shelves.add_topic_shelf`, and first in
`auto_shelve`, where other subjects' shelves are then left out). Looked up when adding (online)
and by Refresh for items without one (`.cache/subjects_tried.json` avoids asking again).
No record: `similar_works` (main topics of the works found for title + keywords, share >=
`VOTE` 0.3). In `auto_shelve`, after the sure topic and the user's own shelves: a less sure topic
(>= `LESS_SURE` 0.3), then `closest_shelf` (similarity >= `CLOSEST`, 2+ shared words, twice the
runner-up). The user's old hand-made shelves (Optics, Lens design, ...) were removed on
2026-11-06 at their request: shelves are now the subjects. `FIELDS_ZH`: the 26 fields in
Chinese. tests/conftest.py stubs `subjects.lookup`.

**Shelves for new items**: `scripts/shelves.py` (`auto_shelve`, called from
`add_book.setup_book` for items on no shelf; never overrides the user's shelves, never invents
one): shelf name in title/keywords/subjects/journal (stemmed), similarity to the shelf's items
(words typical of the shelf vs the rest, shelves with 2+ items, 2+ shared words), glossary
specialist terms (multi-word or 8+ letters, 2+ needed) for the glossary's shelf, and shelves
always used together (3+ items, 90%). Pass the library/catalog paths in (tests).

**🔎 Find online** (library page; `scripts/find_online.py`, `/api/find-online`): a DOI →
Crossref/DataCite + OpenAlex (free copy); arXiv number → arXiv; ISBN → Open Library; other text →
OpenAlex works search, the matching author's works (only if every typed word is in the name),
and Open Library books. Results are marked "in your library" (DOI, ISBN, or title + year).
"＋ Add to library" (`/api/download`, `library_jobs.start_download`) only for legal open-access
PDFs; a link that returns a web page is refused with a message, never scraped. Never add
shadow-library sources (Sci-Hub, LibGen, Anna's Archive).

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
