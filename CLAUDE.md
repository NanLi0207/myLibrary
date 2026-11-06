# myLibrary

A general study tool for learning from your own PDF books (any subject): reading view with
English–Chinese lookup and subject glossaries, book search, progress, shelves, notes, topic notes,
and per-chapter Python scripts for checking a book's worked examples. No marimo/notebooks.
Keep the tool subject-neutral: nothing in `scripts/` should assume optics. The repo is public;
the books never go in it. See README.md.

## Working on this project (always apply)

**ROADMAP.md is the plan; DEVELOPMENT_SPEC.md is the product spec.** At the start of any
development session, read ROADMAP.md: the architecture, the gap analysis, the known bugs (IDs
like D1, B5, L3), the v0.3/v0.4/v0.5 tasks and the design notes. Read DEVELOPMENT_SPEC.md for
the goals, principles and constraints behind them (local-first, offline-first, optional
network and AI, no destructive migrations, no rewrites). Work through the current milestone in
order; don't start the next milestone, or features outside it, unless the user asks. Keep
ROADMAP.md current in the same change as the code: tick finished tasks with the version, add
bugs and limitations you find (name the function or file; line numbers drift), remove ones you
fix, and update the architecture and gap analysis when they change. If a plan changes, change
the file rather than leaving it stale. Don't claim a feature works unless it was verified; say
when browser, Windows-specific or package testing wasn't done.

**Stable IDs (from v0.3).** Once the catalog has an `id` column (ROADMAP task 3.1), new
sidecar data (anchors, annotations, topic links) refers to documents by `id`, not slug or
title. Slugs stay the file and folder names.

**Protect the user's data.** Notes, vocabulary, topic notes, reading log, review progress,
marks in PDFs, `catalog.csv` and `library.toml` are the user's work. Never delete them; move to
the library's `archive/` (`add_book.move_to_archive`, which refuses anything outside the
library's folders).

**Write files through `scripts/safe_io.py`, never with `Path.write_text` or `open("w")`:**
- `write_text`/`write_bytes` are atomic.
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
For page or reader changes, also try it in the browser with
`uv run scripts/library_server.py --port <other port>`. The JavaScript in `library_page.py` and
`reader_static/` has no tests yet, so check it by hand and say what you checked.

**Environment:** Windows, Python 3.14 via uv (installed with winget). A terminal opened before
uv was installed won't find it; restart VS Code. Use forward-slash paths and UTF-8 explicitly
when reading/writing text.

**Versions:** `pyproject.toml` `version` is the package version; bump it and rebuild the
package only when the user asks for a package release.

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
SHA-256 with size prefilter, or same slug) always go to `archive/` from every path, CLI included;
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
  `library.html` is the static read-only copy (built by `scripts/library_page.py`, rebuilt by
  add_book.py). Chapter start pages are cached in the library's `.cache/chapter_pages.json`
  (`--refresh-chapters` clears a book's entry automatically).
- To take a book out, use `uv run scripts/add_book.py --remove <slug>`: it moves the PDF, notes
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
