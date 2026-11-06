# myLibrary roadmap

How myLibrary grows from 0.2.5 into a mature, local-first application for reading English
books, academic papers and technical documents. The product goals, principles and constraints
are in [DEVELOPMENT_SPEC.md](DEVELOPMENT_SPEC.md); this file is the working plan based on the
actual code.

**Keeping this file current.** Maintain it together with the code. When you finish a task,
tick it and add the version. When you find a bug or limitation, add it to *Known bugs*. Name
the function or file, not just a line number, since line numbers drift. When a plan changes,
change it here. CLAUDE.md asks every Claude Code session to read and update this file.

Last full review: 2026-11-06, at 0.2.5. It covered every script, the page and reader
JavaScript, all tests, and the example library. 139 tests pass and ruff is clean. Findings
marked **C** were confirmed (code path traced, or reproduced in a scratch copy, never in
`library/`). Findings marked **S** are suspected.

**Status (2026-11-06):** v0.3 task 1 (safe file writing and background jobs) is done but not
yet released; `pyproject.toml` still says 0.2.5. 158 tests pass. **Next: task 2** (Chinese
name collisions and accidental PDF replacement).

---

## 1. Architecture today

- **Python, standard library server.** `library_server.py` is a `ThreadingHTTPServer` on
  127.0.0.1. It checks the Host header, a per-run token on every POST, and serves only PDFs
  listed in the catalog. Background work runs in daemon threads (`library_jobs.py`, one thread
  per job).
- **Library page.** `library_page.py` renders one HTML page from a roughly 1,500-line
  HTML/CSS/JS template inside a Python string. A static copy, `library.html`, is written too.
- **Reading view.** PDF.js 4.10.38 (downloaded by `reader.py` into `.cache/reader/`).
  `viewer.html` is served with `reader_static/lookup.js` and `lookup.css` injected. The reader
  is opened as `/pdfjs/web/viewer.html?file=/<books|papers|theses>/<slug>.pdf#page=N`, and
  `lookup.js` gets the slug from that file path.
- **Data: plain files in one library folder.**
  - `catalog.csv` has one row per document; the key is the **slug**, which is also the file
    name.
  - Each document has a notes folder `notes/<slug>/`: `README.md` (details, chapter checklist,
    "Last read"), `chNN-*.md` (chapter notes), `notes.md` (papers) and `vocabulary.md`.
  - Library-wide notes: `notes/topics/<term>.md`, `notes/reading-log.json`,
    `notes/vocabulary-review.json`.
  - Glossaries: `glossaries/*.csv`.
  - Rebuildable data under `.cache/`: `books.db` (FTS5 search index), `chapter_pages.json`,
    OCR text, hashes.
  - Marks are saved **inside the PDFs**; the original is kept once in `archive/before-marks/`.
- **Identifiers.** The slug is the only document ID. Chapters are identified by number. Notes,
  vocabulary entries and annotations have no IDs.
- **Notes are edited outside the app.** `open_in_editor` opens VS Code, Notepad or a custom
  editor.

## 2. Gap analysis

The features are listed in the order of DEVELOPMENT_SPEC.md. **Status** is one of: complete,
partial, not integrated, or missing. **Size** is the implementation effort: S, M or L.

### 2.1 Reading and notes (P0)

- **Status:** not integrated.
- **What exists:**
  - PDF.js reader with a lookup popup (`lookup.js`).
  - Chapter notes as Markdown (`add_book.write_chapter_notes`), opened in an external editor
    (`library_server.open_in_editor`, `open_chapter`).
  - Topic notes with book and page references (`library_server.topic_note`).
  - "Last read" position (`save_position`).
- **Limitations:**
  - No notes inside the reader; every note means switching windows.
  - No link from a note back to a passage, no notes created from a selection, and no
    selection menu beyond the popup.
- **Proposal:** side panel in the reader (section 5). Size L.
- **Risk:** the user also edits the same files in VS Code, so saves need a conflict check.
  Notes must stay plain Markdown.

### 2.2 Structured annotations (P0)

- **Status:** partial.
- **What exists:** PDF.js editor marks (highlight, ink, text, stamp) saved into the PDF
  (`lookup.js keepMarks` → `reader.save_marks`), with the original kept once.
- **Limitations:**
  - Marks can't be listed, searched, filtered, tagged or exported, and aren't linked to notes.
  - Saving rewrites the whole PDF, and two tabs overwrite each other (D5).
  - Every save changes the file stamp, so `book_search` re-indexes the whole book.
- **Proposal:**
  - Keep marks in the PDF, since PDF annotations are portable to other readers.
  - Read them back with pypdf into a sidecar index, `notes/<slug>/annotations.json`, keyed by
    the annotation's `/NM` name. User comments and tags live in the sidecar only.
  - Add an annotation panel in the reader, and an export to Markdown.
  - Size L.
- **Risk:** PDF.js `/NM` names must stay stable across saves (verify before building on them).
  Must never rewrite the PDF for a comment or tag.

### 2.3 Metadata correction (P0)

- **Status:** partial.
- **What exists:**
  - Strong automatic identification (`book_meta.identify`, `thesis_meta`, `subjects`).
  - The source of every field is recorded (`metadata_sources`).
  - Shelves can be edited on the page.
  - Corrections are possible from the command line only (`add_book.py --author/--year/--title`).
- **Limitations:**
  - No editing form.
  - `upsert` can't clear a field.
  - Refresh and lookups could overwrite corrections; nothing marks a field as "set by you".
  - No report, standard or manual type (L1).
- **Proposal:**
  - An edit-details dialog on the page that writes the catalog row and the README together.
  - Corrected fields are marked `you` in `metadata_sources`, and every automatic path skips
    them.
  - Size M.
- **Risk:** a changed title or author changes the slug (renaming files, notes and links), so a
  stable ID is needed first (task 3).

### 2.4 Chapter correction (P0)

- **Status:** partial.
- **What exists:**
  - Chapters found from bookmarks, the printed contents or OCR (`book_toc.py`).
  - Start pages cached in `.cache/chapter_pages.json`.
  - `--refresh-chapters` regenerates the templates.
- **Limitations:**
  - Chapter titles and pages can't be edited.
  - The page cache is a rebuildable cache, so corrections stored there would be lost.
  - `refresh_chapters` deletes headings-only notes (D8).
- **Proposal:**
  - A `chapters.json` per document in `notes/<slug>/` holding user-confirmed titles and pages,
    which wins over detection.
  - A chapter editor on the page.
  - Size M.
- **Risk:** existing chapter note files are named by number and title, and must keep working.

### 2.5 Duplicates (P0)

- **Status:** complete but unsafe.
- **What exists:** `add_book.repeat_of` (same DOI, ISBN, hash or slug), `catalog_repeats`,
  `merge_into` and `replace_pdf`.
- **Limitations:**
  - Fully automatic, with no user choice.
  - A slug match alone counts as "the same work", so two different Chinese-titled documents
    collide (D6) and a PDF can be replaced under someone else's notes.
  - Archive names can collide (D7).
- **Proposal:**
  - Only DOI, ISBN, identical hash, or title plus year counts as a repeat.
  - Ambiguous cases go to a "possible duplicates" list on the page with Keep both / Replace /
    Merge.
  - Every destructive step can be undone from `archive/`.
  - Size M.
- **Risk:** must not undo merges the user already accepted.

### 2.6 Persistence and integrity (cross-cutting, P0)

- **Status:** done in v0.3 task 1 (unreleased).
- **What exists now:** `scripts/safe_io.py`:
  - atomic writes (temp file, fsync, `os.replace`, with Windows retries);
  - per-file locks for read-change-write;
  - a damaged JSON file is kept and reported, never replaced; caches are rebuilt;
  - `critical()` sections that quitting waits for.
- **Jobs:** they still run in parallel. Only filing a document is serialized
  (`add_book.FILING`), and `library_jobs.shutdown()` lets jobs reach a safe point.
- **Remaining:** the locks are per process (see section 4, task 1).

### 2.7 Backup and recovery (P0)

- **Status:** partial.
- **What exists:**
  - git backup of the library folder (`backup.py`).
  - Dated zip backups (`folder_backup.py`), with PDFs in the package.
  - Daily automatic backup.
- **Limitations:**
  - No restore path or restore test.
  - Non-ASCII file names break git backup (B2).
  - Two libraries can prune each other's zips (B3).
  - Clear archive removes the only unmarked originals (B13).
- **Proposal:**
  - Fix B2, B3 and B13.
  - "Restore from a backup zip" into a new library folder, never over the current one.
  - A test that a backup restores into a library that opens.
  - Size M.

### 2.8 Contextual translation (P1)

- **Status:** partial.
- **What exists:**
  - Offline ECDICT with inflections (`reader._base_forms`), glossaries ranked by subject.
  - Read aloud, phrases of up to 6 words.
  - The surrounding context is sent to `/api/lookup`.
- **Limitations:**
  - Context is used only to find glossary terms; it isn't shown or stored.
  - Sentences only get a Bing link.
  - Hyphenation breaks lookup (B6).
- **Proposal:**
  - Show the sentence in the popup.
  - Clearly separate "dictionary" from "generated".
  - A pluggable translation/explanation provider, off by default, that shows exactly what will
    be sent.
  - Size M (interface) plus L (a provider).

### 2.9 Selection toolbar (P1)

- **Status:** partial.
- **What exists:** the popup appears on double-click or drag, with Save word, Topic note,
  "In my books" search and read aloud.
- **Limitations:** no Highlight, Add to notes, Translate or Explain actions.
- **Proposal:** a compact action bar on selection that reuses the popup's code. Size S–M.

### 2.10 Cross-document topics (P1)

- **Status:** partial.
- **What exists:** topic notes (`notes/topics/<term>.md`) created from the popup with book and
  page references; FTS search across books.
- **Limitations:** a topic is one free Markdown file, with no structured links, synonyms, or
  linked annotations or notes.
- **Proposal:**
  - Keep the Markdown file.
  - Add `notes/topics/<term>.json` holding confirmed source links (doc ID, page, quote),
    synonyms and linked annotation or note IDs.
  - A topic page.
  - Size L.
- **Risk:** links must survive renames, so they depend on stable IDs.

### 2.11 Library search (P1)

- **Status:** partial.
- **What exists:**
  - SQLite FTS5 page index with porter stemming and incremental updates by file stamp
    (`book_search.py`).
  - Search runs only from the popup and the CLI.
- **Limitations:**
  - Not on the library page; phrase queries only.
  - Results show PDF page indexes, not printed page numbers.
  - Notes and annotations aren't indexed.
  - Page counts include removed books (B8).
- **Proposal:**
  - A search page with snippets, highlighting and filters (type, author, year, shelf, reading
    status).
  - Index notes and annotations as their own sources.
  - Indexing in the job worker.
  - Size M.

### 2.12 Vocabulary (P2)

- **Status:** partial.
- **What exists:** `vocabulary.md` per book (`reader.save_word`); Leitner review
  (`vocab_review.py`).
- **Limitations:**
  - No sentence or English definition stored.
  - Fragile table parsing (B7).
  - The wrong glossary meaning can be saved (B5).
  - No editing, no cloze cards, no Anki export.
- **Proposal:**
  - Add sentence, definition and page columns, reading the old 5-column rows unchanged.
  - Cloze cards from the sentence; Anki TSV export.
  - Keep `BOX_DAYS`.
  - Size M.

### 2.13 Zotero, BibTeX and RIS (P2)

- **Status:** export only.
- **What exists:** `citation.py` exports APA, IEEE, GB/T 7714, BibTeX and RIS.
- **Limitations:** no import, and no matching of imported records to PDFs.
- **Proposal:**
  - BibTeX and RIS import matched by DOI, ISBN or title.
  - Then Zotero via its local export (check the actual options first).
  - Size M.

### 2.14 Large PDFs and performance (cross-cutting)

- **Status:** partial.
- **Limitations:**
  - PDFs are sent whole with no HTTP Range support (`do_GET` uses `read_bytes`).
  - The whole PDF is uploaded on every marks save.
  - Every page load runs two git commands (`backup.available`).
  - Marks trigger a full re-index of the book.
- **Proposal:** Range support, cache `backup.available`, and leave the index alone when only
  annotations changed. Measure first. Size S–M.

### 2.15 Modularization (cross-cutting)

- **Limitations:**
  - The page template is in a Python string, and no JS is tested.
  - `do_POST` is a 150-line if-chain.
  - Library paths are module globals fixed at import.
- **Proposal:**
  - Move new reader UI into new files under `reader_static/`, not into `lookup.js`.
  - Add a small route table when adding routes.
  - Split the page template only when a v0.3 page feature needs it.
  - No rewrite.

### 2.16 Download safety (cross-cutting)

- **Status:** partial.
- **What exists:** PDF.js is pinned to a version.
- **Limitations:** PDF.js has no checksum; ECDICT comes from an unpinned `master`; a corrupt
  `pdfjs.zip` is reused forever (B10).
- **Proposal:** pin ECDICT to a commit, add SHA-256 checks, replace corrupt downloads. Size S.

---

## 3. Known bugs and risks

These are referenced by ID from the tasks.

### Data safety

Fixed in v0.3 task 1, with regression tests in `tests/test_data_safety.py`: D1, D2, D3, D4,
D9, D10, D11. They are kept below for the record. Still open: D5 (task 5), and D6, D7, D8
(task 2).

- **D1 (C, fixed) `catalog.csv` loses rows under concurrent writes.**
  - It is rewritten in place with no lock (`catalog._write`, `upsert`, `set_field`).
  - Uploads run one thread each, and Refresh, Shelves and OCR also write it.
  - A scratch test with concurrent `upsert`s kept 2 of 40 rows, and readers raised
    `KeyError: 'slug'`.
  - A crash mid-write leaves an empty or partial catalog.
- **D2 (C, fixed) Broken JSON wipes the reading log and review progress.**
  `reading_log.load` and `vocab_review._load_state` treat broken JSON as `{}`, so the next
  save overwrites the whole history. Concurrent `/api/reading` reports produced broken JSON in
  a scratch test.
- **D3 (C, fixed) No write is atomic.** This covers:
  - the catalog;
  - notes READMEs (`save_position`, `tick`);
  - `.cache/chapter_pages.json`, which, once corrupt, makes every Read fail until it is
    deleted by hand;
  - `.cache/hashes.json`;
  - the OCR caches, which, once corrupt, stop resuming;
  - `subjects_tried.json`;
  - `local.toml`.
- **D4 (C, fixed) Quit can stop a job mid-write.** Quit (`/api/quit`) and the library-change restart
  (`restart_later`, `os._exit`) don't wait for running jobs, and job threads are daemons.
- **D5 (C) Marks from two tabs overwrite each other.**
  - `save_marks` accepts any whole PDF with the same page count; there is no version check.
  - After 3 failed saves, `keepMarks` stops trying for the session.
- **D6 (C) Different documents can get the same slug.**
  - Slugs keep ASCII only (`book_meta.surname`, `add_book.short_title`), so two Chinese-titled
    items from the same year both become `unknown-<year>-untitled`.
  - "Part A" and "Part B" of a report collide too.
  - Same slug counts as the same work, so the second is archived, or its PDF replaces the
    first one's under the first one's notes.
- **D7 (C) Archive names can collide.**
  - `archive_target` adds `-removed-<date>` without checking the name is free, so a third
    archive of the same name on one day raises `FileExistsError`.
  - `remove_book` can then stop halfway: the PDF moved, the notes not, the row still in the
    catalog.
- **D8 (C) `refresh_chapters` deletes notes.** It deletes (`unlink`) notes that contain only
  headings, `-` lines and the back link, including headings the user typed.
- **D9 (C, fixed) A column added to `catalog.csv` by hand breaks every later write.**
  `DictWriter` uses the fixed `COLUMNS`.
- **D10 (C, fixed) A bad setting stops every script.** `paths._toml_value` writes control
  characters unescaped, so `local.toml` becomes unreadable, and `paths` loads it on import.
  An unreadable `local.toml` now stops with a message naming the file. It never falls back to
  defaults, because that would open another library and later overwrite the settings.
- **D11 (C, fixed; found during task 1) A repeat could try to move the whole library into
  `archive/`.**
  1. Copy A of a document takes its name but hasn't written its catalog row yet.
  2. Copy B of the same document arrives. `fill_details` creates a stub row with no `file`.
  3. A third copy then takes `LIBRARY / ""` (the library folder) for the book's PDF, and
     `replace_pdf` calls `move_to_archive(LIBRARY)`. Windows refused only because the folder
     was in use.

  The fix:
  - The row's essentials are written in the same locked step that takes the name
    (`add_book.reserve_row`).
  - `fill_details` never creates a row.
  - `replace_pdf` refuses an entry without a PDF.
  - `move_to_archive` refuses anything outside the library's document and notes folders.

### Correctness

- **B1 (C, fixed in task 1) Page errors show nothing.** `do_GET` had no error handling, so a
  typo in `library.toml` or an odd catalog row dropped the connection. It now answers with a
  message. The library page also shows a damaged reading log or review file instead of hiding
  it.
- **B2 (C) ☁ Back up fails with non-ASCII file names.**
  - `git diff --name-only` quotes non-ASCII paths (`core.quotepath`), so a library file with a
    Chinese name is seen as outside the library and the backup is refused.
  - A non-ASCII `.pdf` would slip past the PDF guard.
- **B3 (C) 💾 Back up can prune another library's zips.** `folder_backup.zips` matches by
  name prefix with an unanchored date pattern, so "My library" and "My library 2" sharing a
  folder count and prune each other's zips.
- **B4 (C) A library change can silently not take effect.** With `MYLIBRARY_LIBRARY` set,
  changing the library in Settings restarts into the old library.
- **B5 (C) The saved meaning can differ from the popup.** `save_word` calls `lookup` without
  the book's slug, so it can pick a different glossary.
- **B6 (C) Hyphenation breaks lookup and search.**
  - Words split across lines ("aber-") and unknown hyphenated compounds ("point-spread") find
    nothing.
  - The search index doesn't join split words.
  - Double-click isn't snapped to whole words.
- **B7 (C) `vocabulary.md` parsing is fragile.**
  - Rows are appended at the end of the file, outside the table if the user wrote below it.
  - Any 5-column table becomes cards.
  - The word "word" can't be saved.
- **B8 (C)** Search page counts include removed books until the next update.
- **B9 (C)** BibTeX escaping misses `{ } \ ~ ^`.
- **B10 (C)** A corrupt `pdfjs.zip` is reused and never replaced.
- **B11 (C) Slow when offline or rate-limited.** HTTP 429 `Retry-After` is ignored, and
  offline every lookup URL costs about 6 s of retries.
- **B12 (C) Package errors go unseen.**
  - Startup errors go only to the log file.
  - The shortcut marker is written even when creating the shortcuts failed.
- **B13 (C) Clear archive deletes the only unmarked originals.** It removes
  `archive/before-marks/` and the pre-OCR originals without saying so.
- **B14 (C) Small fixes.**
  - `upsert` can't clear a field.
  - `tick` returns 500 instead of 400 for a missing README.
  - `render()` replaces placeholders after inserting book data.
- **B15 (S) The reading log over-counts.** Fast scrolling counts every page passed, and two
  windows both add time.
- **B16 (S) Not yet confirmed.**
  - `pick_folder` decodes non-ASCII folder names in the ANSI code page.
  - Find online puts OpenAlex URLs into `href` with no scheme check.
  - `subjects.lookup` can divide by zero.
  - The copyright year isn't capped at the current year.
  - CJK OCR text drawn in Arial loses glyphs.

### Limitations

- **L1** Only book, paper and thesis types. Reports, standards and manuals (such as the
  example library's UIC guidelines) are stored as books.
- **L9** Chinese documents:
  - Contents are not recognised as 第N章 (Chapter N).
  - Chinese chapter titles become `untitled`.
  - There is no Chinese catalogue for Find online.
  - The OCR text layer is Latin only.
- **L11 Test gaps.**
  - No JavaScript tests.
  - Untested routes: PDF GET, the Host check, `/api/save-marks`, `/api/reading`,
    `/api/review`, `/api/search`, `/api/topic`, `/api/shelves`, `/api/upload`,
    `/api/settings`, quit and restart.
  - `open_in_editor` is always stubbed in tests.
  - Packaging has no automated test.

### Example library data (`library/`)

These are the user's data: fix them with the tool and only with the user's agreement.

- 11 items have an empty `type`.
- `bentley` and `chacon` list authors with commas.
- `archut-2022` and `jendrny-2024` take their year from the PDF's creation date despite having
  a DOI.
- `esveld`, `bentley` and `geary` have details from the filename.
- `yoder` and both UIC items have no topic, and are asked again on every Refresh.

---

## 4. v0.3: Complete the core reading workflow

Goal: existing features are reliable, integrated and convenient. Reading, notes and marks
happen in one place, details and chapters can be corrected on the page, and nothing the user
made can be lost by normal use.

**Order (set by the user, 2026-11-06).** Data integrity comes first, because the later tasks
add more writers of notes, annotations and metadata.

1. Safe file writing, concurrency protection, damaged-file handling, graceful shutdown.
2. Chinese name collisions and accidental PDF replacement: a data-integrity issue, not a
   metadata enhancement.
3. Permanent document IDs, backward compatible.
4. Notes panel in the reader (Markdown).
5. Structured annotations, searching them, and linking notes to passages.
6. Metadata correction, chapter editing, duplicate management.

After those: backup and recovery (7) and the remaining fixes (8). Each task ships with tests and
leaves everything else working. A task is done only when its tests pass.

### Rules for every task

- Never modify, delete, migrate or overwrite anything in the user's real `library/`.
- Test destructive, concurrency, damage and recovery cases only in temporary folders with
  invented data.
- Leave the line-ending-only changes in git and `reading-log.json` alone.
- No `git add -A`, and no automatic commits or pushes.
- Explain any production data migration and get agreement before writing it.

### Task 1. Safe file writing and background jobs *(D1–D4, D9–D11, B1)*: done, unreleased

- [x] **`scripts/safe_io.py`**:
  - `write_text` and `write_bytes` write to a temp file in the same folder, fsync it, then
    `os.replace`. They keep the bytes and line endings that `Path.write_text` gave, and retry
    while Windows briefly holds the file.
  - `read_text` and `read_bytes` retry the same way.
  - `lock_for(path)` is a per-file lock, used by `update_text` and `update_json`.
  - `load_json` handles damaged files:
    - A cache is rebuilt.
    - User data is left untouched. A copy is kept as `<name>.damaged-<time>` (one per distinct
      content), the previous version `<name>.bak` is used if it reads, and otherwise it raises
      `DamagedFile` with a plain explanation.
    - A `.bak` is only ever made from a file that read correctly.
  - `critical()`, `close()` and `reopen()`: quitting waits for file operations in progress and
    refuses new ones. Nested operations are allowed.
- [x] **Catalog** (`catalog._change`): every change is load, change and atomic write under the
  file's lock. Columns added by hand are kept. Reads wait out a swap in progress.
- [x] **Everything that writes now uses it:**
  - notes READMEs: `save_position`, `tick`, `refresh_chapters`, `merge_into`;
  - new notes and templates: `setup_book`, `write_chapter_notes`, topic notes;
  - `vocabulary.md` (`save_word`), the reading log and review progress (with `.bak`);
  - the `chapter_pages`, `hashes`, OCR and `subjects_tried` caches;
  - `local.toml` (with full TOML escaping);
  - `library.html`;
  - marks (`save_marks`): the "before marks" original is also copied whole or not at all.
- [x] **Imports stay parallel, filing is serialized.**
  - `add_book.FILING` covers only the repeat check, taking the name and writing the row's
    essentials (`place_book` + `reserve_row`), plus repeat handling and merging. Identifying
    a document runs in parallel.
  - Uploads are written to a hidden `.part` file and given a unique name in one step.
  - Starting OCR is check-and-start in one step.
- [x] **Graceful shutdown**: `library_jobs.shutdown()` does the following:
  - starts no new jobs or uploads;
  - lets an add finish filing its book;
  - stops OCR between pages (the PDF is untouched; finished pages stay cached);
  - stops Refresh between documents and subject lookups between items;
  - then waits for every file operation.

  Quit, the library-change restart (before `os._exit`) and Ctrl+C all go through
  `library_server.finish_jobs`.
- [x] **Readable errors:** `do_GET` answers with a message instead of dropping the connection.
  The library page shows a damaged reading log or review file with the explanation.
- [x] **Tests** (`tests/test_data_safety.py`, 19 tests, all on temporary data):
  - 40 concurrent imports give 40 catalog entries;
  - 40 concurrent catalog updates and 40 concurrent reading reports lose nothing;
  - interrupted writes leave the old file whole with no temp files;
  - a damaged reading log is never replaced, and is recovered from `.bak`;
  - damaged review progress is kept;
  - a damaged cache is rebuilt;
  - hand-added columns survive;
  - settings with any characters stay readable;
  - Quit waits for a book being filed;
  - Quit stops OCR without touching the PDF;
  - shutdown waits for a file operation;
  - concurrent identical uploads are added once;
  - an entry without a file never moves the library (D11).
- **Checked by hand** (throwaway library, port 8799):
  - the server reports a damaged reading log and leaves it as it was;
  - Quit exits cleanly;
  - the page loads in headless Edge with no JavaScript errors and shows the warning.
- **Remaining limitations:**
  - Locks are per process. Running `add_book.py` from the command line while the page server
    works on the same library can't leave half a file, but one of two simultaneous changes
    can be lost. A cross-process lock file is not planned yet.
  - If an add job is still identifying a document (online) when the shutdown timeout ends, it
    is cut off before filing. The PDF stays in `books/` and Refresh adds it.
  - `ocr_pdf.replace_pdf` renames the original away before swapping the new file in. If the
    second step fails, for example because the file is locked, the book's file is briefly
    missing (it's in `archive/books/`). Pre-existing; candidate for task 8.
  - A file that is damaged by something outside the tool (an editor, a sync conflict) and has
    no good `.bak` stops the reading log or review until the user repairs or moves it. This is
    deliberate: nothing is written over it.
  - Not tested on the packaged build yet; run the package clean-environment test before the
    next release.

### Task 2. Chinese name collisions and accidental PDF replacement *(D6, D7, D8)*: next

- [ ] **Slugs that don't collide:**
  - Transliterate non-ASCII names and titles where possible (pinyin for Chinese).
  - Otherwise add a short hash of the original title, so two different documents never get
    `unknown-<year>-untitled`.
  - Keep "Part A/B", volume and report numbers.
  - The same rules for the CLI and the page.
- [ ] **Same name is never "same work" on its own.** A repeat is the same DOI, the same ISBN
  (non-papers), an identical file, or the same normalized original title plus year. A name
  collision alone gets a different name, never archiving or `replace_pdf`.
- [ ] **`replace_pdf` only on a proven repeat.** Only for a DOI, ISBN or hash match, and never
  when the other item has the user's work unless the user confirms (task 6 adds the choice).
- [ ] **Unique archive names:** `archive_target` loops until the name is free, so
  `remove_book` can't stop halfway.
- [ ] **`refresh_chapters` archives instead of deleting** notes it considers untouched
  templates.
- [ ] **Tests:**
  - two Chinese-titled items from one year keep both, each with its own PDF and notes;
  - Part A and Part B;
  - a third same-day archive;
  - `refresh_chapters` keeps headings-only notes in the archive;
  - a name collision never replaces a PDF.
- **Compatibility:** existing slugs and files stay as they are; only new items get the new
  names. No migration.

### Task 3. Permanent document IDs *(prerequisite for tasks 4–6)*

- [ ] **Add an `id` column** to `catalog.csv`: a short random ID (e.g. 8 base32 characters).
  New items get one when added (`reserve_row`).
- [ ] **Existing rows get an ID** lazily the first time the tool writes the catalog, or with an
  explicit one-time step. Either way, explain it to the user and get agreement before it runs
  on their real library. A `.bak` of the catalog is kept.
- [ ] **Look up by ID or slug:** `catalog.by_id(id)` and `catalog.by_slug(slug)`. The reader
  receives the ID too (`?file=…&id=…`).
- [ ] **Sidecar references use the ID:** notes anchors, annotations and topic links refer to
  `id`. Slugs stay the file and folder names, so nothing is renamed.
- [ ] **Tests:** IDs are stable across writes; old catalogs without `id` open and work; merge
  and remove keep IDs consistent.

### Task 4. Notes panel in the reader *(2.1; design in section 5)*

- [ ] **New files:** `reader_static/notes.js` and `notes.css`, injected next to `lookup.js` by
  `reader.viewer_html`.
- [ ] **Panel:** a right-hand panel, resizable and toggled with a button and a keyboard
  shortcut. Its width and open state are remembered in `localStorage`.
- [ ] **Note choice:** the chapter note for the current page (`chapter_at`) is the default,
  with a switch to the document note (`README.md` or `notes.md`) and topic notes.
- [ ] **Editing:** Markdown in a `<textarea>` with a preview toggle.
- [ ] **Autosave:** about 1.5 s after typing stops, and on page hide.
- [ ] **New API:**
  - `POST /api/note/get {id, kind, chapter}` returns `{text, stamp}`.
  - `POST /api/note/save {..., text, stamp}` saves only if the stamp still matches, using
    `safe_io.update_text`. Otherwise it returns `409` with the current text, and the panel
    shows "changed in another editor: keep mine / take theirs".
  - Paths are resolved on the server, never sent by the client.
- [ ] **Keep "Open in editor"**, using `open_in_editor`.
- [ ] **Tests:** round-trip; a stale stamp gives 409 and no write; a path can't escape the
  notes folder.

### Task 5. Structured annotations, search and note linking *(2.2, D5)*

- [ ] **Marks that can't overwrite each other:**
  - `save_marks` checks the stamp of the PDF the viewer loaded and refuses a stale one.
  - Retry with backoff instead of giving up.
  - After a save, update `book_search`'s stamp instead of re-indexing.
- [ ] **Notes linked to passages:**
  - "Add to notes" from a selection inserts a quote and a `/read/<id>?page=…&a=<anchor>` link
    into the current note.
  - `notes/<slug>/anchors.json` stores the page, quote, surrounding text, rectangles, chapter
    and times.
  - `GET /read/<id>` opens the page and flashes the passage.
- [ ] **Annotation index:** `scripts/annotations.py` reads each mark's `/NM` name, type, page,
  rectangle, colour, highlighted text and contents. It writes `annotations.json`, keeping
  comments and tags in the sidecar.
- [ ] **Annotation panel:** list, filter, jump, "To note", comment and tag editing (sidecar
  only); search across documents.
- [ ] **Export** to `notes/<slug>/annotations.md`, generated and never mixed into the user's
  notes.
- [ ] **Tests:** a real PDF.js-saved fixture, an encrypted PDF, a stale save, sidecar comments
  surviving re-reads, anchor fallback to the page.
- First check that PDF.js keeps `/NM` stable across saves, and record the result here.

### Task 6. Metadata correction, chapter editing, duplicates *(2.3, 2.4, 2.5, L1)*

- [ ] **"Edit details" dialog:** title, authors, year, type, publisher or journal, DOI, ISBN,
  arXiv ID, keywords and subject. It writes the catalog row and the README together. Edited
  fields are marked `you` in `metadata_sources`, and nothing automatic overwrites them.
  `upsert` can clear fields.
- [ ] **New type "report"** (also standards and manuals): `institution`, `number`, `part`.
- [ ] **Chapter editor:** `notes/<slug>/chapters.json` (titles and start pages) wins over
  detection. Note files are never renamed or deleted.
- [ ] **"Possible duplicates" list** with Keep both / Replace file / Merge, never automatic
  when both items have the user's work. `archive/log.json` records moves, with Undo.
- [ ] **Tests:** edits survive Refresh; a cleared field stays cleared; `chapters.json` wins;
  undo of a merge.

### Task 7. Backup and recovery *(2.7, B2, B3, B13)*

- [ ] **Fix the backups:**
  - `backup.py` uses `-c core.quotepath=false`.
  - `folder_backup.zips` matches the exact library name.
  - Clear archive keeps `before-marks/` and OCR originals unless they are ticked separately.
- [ ] **"Restore from backup"** into a new folder, never over the current library.
- [ ] **Tests:** back up and restore into a clean folder, then check the library opens with
  notes, log and review state; a non-ASCII name in git backup.

### Task 8. Remaining fixes and release check

- [ ] **Bug fixes:** B4, B5, B7 (format unchanged), B8, B9, B10, B11, B12, B14, the
  `ocr_pdf.replace_pdf` order.
- [ ] **HTTP tests** for the untested routes in L11.
- [ ] **Release check:** the package clean-environment test (CLAUDE.md), then a manual
  add-five-PDFs-at-once followed by Quit.
- [ ] **Tidy the example library**, only with the user's agreement.

**v0.3 is done when** every box above is ticked, every test passes, and the package test
passes.

---

## 5. Design: notes and passages in the reader (tasks 4–5)

- **Where it lives.** The panel is injected into PDF.js's `viewer.html` like `lookup.js`, so
  PDF.js itself is not patched. The panel sits beside `#viewerContainer`; setting the
  container's `right` makes PDF.js re-layout pages.
- **What it edits.** It edits the existing Markdown files only:
  - `notes/<slug>/chNN-*.md` (picked by `chapter_at` for the current page);
  - `README.md` or `notes.md`;
  - `notes/topics/<term>.md`.

  The server maps `(id, kind, chapter|term)` to a path inside the library, so the client never
  sends a path.
- **Saving.**
  - Writes go through `safe_io.update_text` (atomic, under the file's lock).
  - The stamp is `mtime_ns` plus size. A mismatch returns 409; the panel never overwrites
    silently, because the same file may be open in VS Code (see CLAUDE.md's note on stale
    files).
- **Passages.**
  - The link text is ordinary Markdown, so notes stay readable in any editor and on GitHub.
  - Anchor details live in `anchors.json`; a deleted anchor just opens the page.
  - The quote plus surrounding text is matched against the page's text layer, falling back to
    the stored rectangles.
- **Selection actions.** The popup gets a small action row: Add to notes, Highlight (uses
  PDF.js's highlight editor), Add to vocabulary (existing), Search in my library (existing),
  and Translate/Explain (hidden until a provider exists, v0.4).
- **No new dependencies** except possibly a small Markdown renderer for the preview, pinned
  with a checksum.
- **Files affected:**
  - `reader.py` (`viewer_html` injection);
  - `library_server.py` (`/api/note/*`, `/read/<id>`, anchors);
  - new `reader_static/notes.js` and `notes.css`;
  - new `scripts/notes_store.py` (paths, stamps, anchors);
  - `lookup.js` (action row only);
  - tests: new `test_notes_store.py`, plus route tests.

---

## 6. v0.4: A connected learning experience

Start only when v0.3 is done.

1. [ ] **Context-aware lookup** *(2.8, B6)*:
   - Show the sentence in the popup.
   - De-hyphenate in lookup and in the search index.
   - Snap double-click to whole words.
   - Add a provider interface (`scripts/assist.py`) for translation and explanation: off by
     default, configured in Settings, showing exactly what will be sent, never the whole
     document. Dictionary and generated text are labelled differently.
2. [ ] **Selection toolbar** completed with Translate and Explain once a provider is set.
   *(2.9)*
3. [ ] **Vocabulary with context** *(2.12, B7)*:
   - Sentence, definition, page and source link stored, with old rows read unchanged.
   - Editable entries, cloze cards, Anki TSV export.
   - Library-wide vocabulary list.
4. [ ] **Library search page** *(2.11, B8)*:
   - Snippets and highlighting; filters by title, author, year, type, shelf and reading status.
   - Notes and annotations indexed; printed page labels.
   - Indexing in the job worker with progress and cancel.
5. [ ] **Topics that link sources** *(2.10)*:
   - `notes/topics/<term>.json` with confirmed links (document ID, page, quote, anchor),
     synonyms, and linked notes and annotations.
   - A topic page; links added from the selection bar and the annotation panel.
   - Manual confirmation only.
6. [ ] **Notes and annotations organised:** a library-wide annotations view; tags shared
   between annotations and topics.
7. [ ] **Large PDFs** *(2.14)*: HTTP Range for PDFs; cache `backup.available`; measure with a
   500 MB+ PDF before and after.
8. [ ] **Reading log accuracy** *(B15)*.

## 7. v0.5: Optional intelligent assistance

Start only when v0.4 is done. Every item is optional and off by default; reading, notes and
vocabulary work without it.

1. [ ] Provider plug-ins behind the `assist.py` interface: local models (e.g. an
   OpenAI-compatible local server) and user-supplied API keys. No provider is hard-wired.
2. [ ] Explanations of terms, sentences, paragraphs, formulas and methods, grounded in the
   selected passage, with sources shown and generated text labelled.
3. [ ] Question answering over the user's own library, retrieving from the FTS index, notes
   and annotations, and citing the pages it used. Citations must be ones it actually
   retrieved.
4. [ ] Suggested topic links, shown for the user to confirm and never added automatically.
5. [ ] **Imports** *(2.13)*: BibTeX and RIS, then Zotero, matched to PDFs.
6. [ ] **Chinese documents** *(L9)*: 第N章 (Chapter N) contents, Chinese chapter titles, a CJK
   font for the OCR text layer.
7. [ ] **Download safety** *(2.16)*: ECDICT pinned, SHA-256 checks.
8. [ ] **Two workspaces** (Book study and Paper research) as different defaults over the same
   data, once the shared reader is mature.

## 8. Not planned

These stay out on purpose (see CLAUDE.md and DEVELOPMENT_SPEC.md):

- DjVu or EPUB;
- notebooks;
- shadow-library sources;
- books or book text in git;
- cloud hosting, accounts or subscriptions;
- mandatory AI;
- replacing the Python backend or the browser-based interface.
