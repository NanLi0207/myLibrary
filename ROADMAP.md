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

**Status (2026-11-07):**
- **Tasks 1 and 2** are committed and pushed (`419a46f`, `ad47aff`); Windows CI passed.
- **Task 3** (UUID-only identity, indexing reliability, search-result highlighting, correcting
  marks, Undo / Redo, Preview Mode, persistence audit) is committed and pushed: `5b82b6d`
  (code, tests, docs) and `17dd9c4` (the migrated example data).
  - The user's manual acceptance tests passed, including the six persistence checks.
  - The real library is migrated and verified; the migration backup stays local in
    `library/.myLibrary/`.
  - **CI failure, then fixed in a follow-up commit:**
    - Two tests failed on CI: `test_a_lasting_link_opens_the_document_whatever_its_name` and
      `test_continue_opens_last_page_and_its_chapter`.
    - They assumed PDF.js was installed, which a fresh checkout never is. Without it, the app
      rightly links to the bare PDF.
    - The tests now say the reading view is set up. All 213 tests pass in a clean clone.
- **Next:** task 4, once its plan is reviewed.
- **Not released yet:** `pyproject.toml` still says 0.2.5.

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
- **Identifiers** (since v0.3 task 3). Every document has a permanent UUID (`catalog.csv`'s
  `id`), its only identity. The slug is just its file and folder name, and retired ids keep
  tombstones (see task 3). Chapters are identified by number within a document. Notes,
  vocabulary entries and annotations have no ids of their own yet (task 5).
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
  (`lookup.js keepMarks` → `reader.save_marks`), with the original kept once. A mark can be
  selected by clicking it, removed (🗑 or Delete), undone (Ctrl+Z or the Undo bar), and the
  removal is saved the same way (`lookup.js easyMarkEditing`, task 3). ↶ Undo and ↷ Redo are
  on the toolbar, with Ctrl+Z, Ctrl+Y and Ctrl+Shift+Z, also while reading (`undoRedo`).
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

- **Status:** made safe in v0.3 task 2. Repeats now need proof (DOI, ISBN or an identical
  file), and a name collision gets a free name. Replacement is limited and reversible. Still
  automatic: no Keep / Replace / Merge choice and no Undo yet (task 6). The original
  assessment follows.
- **Status before task 2:** complete but unsafe.
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
D9, D10, D11. Fixed in task 2, with tests in `tests/test_names_and_repeats.py`: D6, D7, D8,
D12. They are kept below for the record. Still open: D5 (task 5).

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
- **D6 (C, fixed in task 2) Different documents can get the same slug.**
  - Slugs keep ASCII only (`book_meta.surname`, `add_book.short_title`), so two Chinese-titled
    items from the same year both become `unknown-<year>-untitled`.
  - "Part A" and "Part B" of a report collide too.
  - Same slug counts as the same work, so the second is archived, or its PDF replaces the
    first one's under the first one's notes.
- **D7 (C, fixed in task 2) Archive names can collide.**
  - `archive_target` adds `-removed-<date>` without checking the name is free, so a third
    archive of the same name on one day raises `FileExistsError`.
  - `remove_book` can then stop halfway: the PDF moved, the notes not, the row still in the
    catalog.
- **D8 (C, fixed in task 2) `refresh_chapters` deletes notes.** It deletes (`unlink`) notes
  that contain only headings, `-` lines and the back link, including headings the user typed.
  They now go to `archive/notes/<slug>/`.
- **D12 (C, fixed in task 2) A shared ISBN or DOI alone could swap in a different book.** An
  ISBN read from the wrong page (B16) made a "richer" unrelated file replace the library's PDF.
  Replacement now also needs the titles to agree (`titles_agree`), and never happens when the
  library's PDF has marks.
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
- **B17 (S) A native fault in pdfium can occur during text extraction.** Seen once (an
  access violation while indexing). It isn't reproducible, so the cause is unconfirmed (see
  task 3). Indexing now survives it per document. If it recurs, run `book_search.page_texts`
  in a subprocess, so the server process never continues in an unsafe native state.
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
  - Untested routes: PDF GET, the Host check, `/api/reading`,
    `/api/review`, `/api/search`, `/api/topic`, `/api/shelves`, `/api/upload`,
    `/api/settings`, quit and restart.
  - `open_in_editor` is always stubbed in tests.
  - Packaging has no automated test.
  - The reader's browser checks (scratchpad scripts driving Edge, see task 3) aren't part of
    the test suite or CI.
- **L12 Closing the browser by force loses unsaved marks.** The reader warns before a tab with
  unsaved marks is closed, reloaded or left (task 3). Nothing protects against ending Edge in
  Task Manager, a crash, or a power cut in the second after a change. A saved state is
  durable (written atomically and flushed to disk before "Marks saved").
- **L13 Reading time can lose up to a minute.** It is sent every minute and when the tab is
  hidden or closed (`keepalive`). After a crash or a forced close, the last minute is lost. A
  report the server refuses isn't retried. No warning is shown for it, since reading isn't an
  edit.
- **L14 Notes open in an outside editor.** myLibrary never writes a chapter note. It does
  write the notes README ("Last read", chapter ticks, under a file lock). If the README is
  open with unsaved edits in VS Code, VS Code reports the newer file when it saves, and the
  user chooses.

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

### Task 1. Safe file writing and background jobs *(D1–D4, D9–D11, B1)*: done, committed `419a46f`

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

### Task 2. Name collisions and accidental PDF replacement *(D6, D7, D8, D12)*: done, committed `ad47aff`

- [x] **Unique names, same convention.**
  - `Book.base_slug` is unchanged (`<surname>-<year>-<short-title>`).
  - If a *different* document already has that name, `add_book.free_slug` gives `-2`, `-3`,
    and so on. "Has that name" means a catalog entry, a PDF in books/, papers/ or theses/, or
    a notes or examples folder (even an orphaned one).
  - The name is chosen in `place_book` under `FILING`, together with taking it and
    `reserve_row`, so concurrent imports can't collide.
  - `place_book` refuses to move a file over an existing one.
  - Existing files and entries are never renamed.
  - The job message (and the command line) says when a different name was given.
- [x] **Repeats need proof.**
  - `repeat_of` and `find_repeat` accept only the same DOI, the same ISBN (not for papers),
    or an identical file (SHA-256). The old "same author, year and title" rule is gone.
  - Same title, author and year with a different file (`possible_repeat`) is kept as its own
    document and reported ("possibly the same work as …; if they are the same, remove one").
    It is never merged, archived or replaced.
- [x] **Replacement is safe** (`handle_repeat(reason=…)`, `replace_pdf`):
  - It needs a proven reason, and never happens for an identical file.
  - It never happens when the library's PDF has marks (`has_marks`: PDF annotations, or an
    original in `archive/before-marks/`; if the file can't be read, it counts as marked).
  - It never happens when the titles don't agree (`titles_agree`).
  - Both paths are checked (`library_pdf`, `_library_item`): `file` must be
    `books|papers|theses/<name>.pdf`, the target can't be a folder, and the source must be a
    PDF file in the library's folders.
  - If putting the new copy in place fails, the old PDF is moved back.
  - Refresh's `catalog_repeats` counts marks as the user's work, and always keeps the copy
    with marks.
- [x] **Unique, recoverable archiving.**
  - `archive_target` loops: `<name>-removed-<date>`, then `-2`, `-3`, ...
  - `move_to_archive` chooses and moves in one locked step, and refuses the library itself,
    its top folders, the archive, and anything outside.
  - `remove_book` is all or nothing: on failure it moves back what it already moved, and the
    catalog entry stays.
  - `merge_into` never overwrites an earlier `-from-…` note or script copy (`free_path`).
  - `ocr_pdf.replace_pdf` puts the original back if the swap fails.
- [x] **Chapter notes.**
  - `refresh_chapters` moves replaced templates to `archive/notes/<slug>/` instead of deleting
    them.
  - Templates whose name matches a chapter being written stay in place.
  - Notes with the user's writing are never touched, as before.
- [x] **Tests** (`tests/test_names_and_repeats.py`, 27 test cases, temporary libraries only):
  - two Chinese-titled documents of one year, and 12 concurrent imports with one candidate
    name, each with its own whole PDF and notes;
  - numbered names, and orphaned notes not reused;
  - the exact same PDF uploaded again, both one after another and at once (added once; five
    archived copies, none overwritten);
  - different PDFs with the same upload name;
  - a same-titled different file never replacing the library's PDF;
  - a PDF with marks and notes never replaced;
  - marks saved from the reading view, and Refresh keeping the copy with marks;
  - a shared ISBN with a different title;
  - archive collisions (sequential, concurrent, repeated removal);
  - interrupted replacement, removal and OCR swap;
  - entries without a proper PDF, a folder named like a PDF, and the library and its folders
    never moved;
  - no placing over an existing file;
  - chapter refresh;
  - the command-line paths.
- **Changed existing tests** (intended behaviour change):
  - `test_upload_is_identified_named_and_registered` and
    `test_refresh_adds_pdfs_put_into_the_folders_by_hand` used a *different* file with the
    same title to mean "the same book". They now use the identical file for the repeat case.
    The first also checks that a same-titled different file is kept as `-2` with a note.
  - `test_a_better_copy_replaces_the_pdf_and_keeps_your_notes` gives its entry a real title
    instead of its slug.
- **Checked by hand** (throwaway library, command line): two Chinese-titled books of 2020
  became `unknown-2020-untitled` and `unknown-2020-untitled-2`, and an identical copy went to
  the archive. This found and fixed a command-line caller that hadn't been given the repeat
  reason.
- **Remaining risks:**
  - Two copies of one work that aren't byte-identical and have no shared DOI or ISBN (e.g. the
    same book from two sources) are now both kept, as `-2`, with a "possibly the same work"
    note. Nothing is lost, but the user must remove one by hand until task 6 adds a choice.
  - Archived chapter templates count as empty templates, so the user's explicit Settings →
    Clear archive deletes them. "Untouched" still includes headings the user may have typed.
    Task 6's chapter editor should mark generated templates.
  - `FILING` is per process. The command line and the page server adding at the same moment
    could pick the same free name. `place_book` then refuses rather than overwrite, so the job
    fails and the file stays for Refresh.
  - Refresh's merge of proven repeats (`catalog_repeats` + `merge_into`) is still automatic
    when only one copy has the user's work (task 6).
  - If a rollback itself fails (the old file locked too), it is printed and the file is in
    `archive/`. Nothing is deleted, but it isn't back in place.
  - `has_marks` reads every page's annotations: slow for very large PDFs, and only done when
    a replacement is considered.

### Task 3. Permanent document ids: UUID-only identity *(prerequisite for tasks 4–6)*: done, committed `5b82b6d`, `17dd9c4`

**Decisions** (user, 2026-11-06):
- **One identity model.** No old slug system alongside it and no compatibility layer.
- **Single source of truth:** `catalog.csv`, whose `id` column is the primary key. A SQLite
  table was rejected: it's a binary file in git (the example library is public), has no Excel
  view, and would mean rewriting every reader. A separate registry was rejected because it
  would be a second source of truth.
- **Explicit migration,** never at startup.
- **Old versions (0.2.x) are no longer supported** on a migrated library. Their catalog writer
  can't handle new columns and truncates the file.

**Data model:**
- **`catalog.csv`:** a new first column `id`, a UUID4, given once by `catalog.add` and never
  changed or reused. `catalog.load()` returns `{id: row}`.
- **Validated on every load and before every write:** each id valid and unique, each name
  unique. A broken catalog (a row copied or an id cleared in Excel) raises `CatalogError` and
  is never repaired.
- **An old-format catalog** raises `NotMigrated`. The server refuses to start and names the
  command to run.
- **`slug`** is only the name, the base of the file and folder names. `file` and `notes` are
  the document's paths and are always read from its row.
- **`retired-documents.json`** (next to the catalog; tracked and backed up) holds tombstones
  for ids that left: `{id: {event: merged|removed, into, date, title, slug, file}}`.
  - It's written before the row is removed, and taken back if the removal fails.
  - `catalog.resolve(id)` follows a merge to the document that kept the work, reports a
    removed id with its title, or reports `unknown`.
  - `catalog.check()` reports problems: an id both live and retired, or a merge into nothing.

**References by id:**
- **Reading log:** `{day: {id: {s, p}}}`.
- **Search index:** a `doc_id` column; an old index is rebuilt.
- **Caches:** the chapter-page cache and `subjects_tried` are keyed by id.
- **Jobs:** they carry `doc_id`, separate from the job's own `id`.
- **Review cards:** `seen` holds `{id, title, file, page}`.
- **Find online:** `in_library` holds the id.
- **Per-document APIs:** all take `id`. A merged id is followed to the kept document; a removed
  one gets a "was removed on …" answer.
- **Reader:** `X-Document-Id` on saved marks; the reader URL carries `&id=`; `lookup.js` uses
  only the id.
- **Library page:** `data-id` on every card.
- **`GET /read/<id>?page=N`:** a lasting link that redirects to the reader (302), or answers 410
  for removed and 404 for unknown documents.
- **Unchanged:** notes text, chapter notes, vocabulary files, review progress (keyed by word),
  marks, file and folder names, and the `hashes` and OCR caches (they're about files).

**Merging and removing:**
- **Merge** (Refresh, a proven repeat): the kept document keeps its id. The dropped one is
  retired as `merged into` the kept one.
- **Its reading records are never rewritten.** `reading_log.attribute` counts them for the kept
  document, so two copies read on the same day keep both records. The summary adds their
  seconds, counts each record's pages separately (two copies' page numbers needn't match) and
  counts the day once.
- **Removal:** retired as `removed`; its history is shown under its old title.

**Renaming:** `add_book.rename_document(id, name)` is the base for task 6's user interface.
- It moves the PDF, the notes folder, the chapter scripts and the original kept before marks.
  It updates the README's `File:` line and the catalog's `slug`, `file` and `notes`. The id
  never changes.
- It's journaled in `.myLibrary/operations/`. Any failure puts everything back immediately. An
  interruption (power cut) is put back by `add_book.recover_operations()`, which the server and
  the CLI run at start.

**Migration** (`scripts/migrate_ids.py`): it reads the old format itself, since the app refuses
it.
- **Dry run** (the default): the provisional mapping, clearly labelled ("--apply makes new
  ids"), the changes, warnings and blocking problems, and a value-by-value check of the planned
  files. It writes nothing.
- **Blocking problems:** a reading-log key that is no entry's name, a duplicate or empty name,
  or a row with more cells than columns.
- **`--apply`, a recoverable multi-file transaction:**
  1. Copies of the originals and the full new versions are written to
     `.myLibrary/migrations/<time>-uuid/` and read back. That's a dedicated place: gitignored,
     and never touched by Clear archive.
  2. The manifest moves `prepared` → `committing`. Each file is swapped in atomically and
     recorded.
  3. `committed`: the caches are deleted.
  4. Verification compares values, not bytes: every row's every value under its mapped id, and
     every reading-log record under its id.
  5. `done`.
- **Recovery:** any manifest that isn't `done` makes the app refuse the library.
  - `--resume` rolls forward, using the hashes to tell which files are already done.
  - `--rollback` restores the originals, but refuses if a file has changed in any other way
    since (new work would be lost).
- **Also:** `--check`, and a running-server guard.
- **Planned removal:** keep it through the v0.3 release, delete it in v0.4.

**Tests:**
- **`tests/test_document_ids.py`** (21 tests):
  - ids unique across 200 documents, and immutable;
  - broken catalogs refused, never repaired; the old format refused;
  - tombstones;
  - the dry run writes nothing (whole-library hash);
  - full conversion keeps every value, and every file other than the two targets and the
    caches is byte-identical;
  - the backup survives Clear archive; a second migration does nothing;
  - after migrating, the reading log, review cards, search, page data and reader URL all work
    by id;
  - interruption mid-swap, then resume, or rollback instead;
  - a failure while staging changes nothing;
  - rollback after `done`, and refused when it would lose new work;
  - ambiguous data blocks; verification is by value;
  - a merge keeps both same-day records under one identity; removal keeps its history under
    the old title;
  - renaming, a failed rename, and an interrupted rename recovered;
  - `/read/<id>` gives 302, 410 or 404;
  - concurrent imports get distinct ids.
- **The existing 185 tests** were converted to ids (with the `tests/testlib.py` helpers).
  Several now also check that a *name* sent as an id is refused (404).
- **Total: 206 pass.** Ruff and the format check are clean.

**Checked by hand:**
- **On a temporary copy of the real library** (catalog, notes, glossaries; no PDFs):
  - dry run, `--apply` and `--check` all OK;
  - the server on the copy: `/read/<id>` redirects to the reader with `&id=`; lookup, ticking,
    reading log and review cards work by id; ticking by name is refused;
  - the library page and the reading view load in headless Edge with no script errors.
- **Read-only dry run on the real `library/`:** 31 entries, 3 reading-log records, no warnings,
  nothing blocking, "every value is kept". All 329 files were byte-identical afterwards.

**Found and fixed during development** (never committed): jobs had stored the document id in
their own `id` field, which would have broken the page's job tracking.

**Remaining risks:**
- **No JavaScript tests.** The page and reader were checked in headless Edge and through the
  API, but not by clicking through every button.
- **Old copies of the tool** (0.2.x, other checkouts) truncate a migrated `catalog.csv` if they
  write to it. That's accepted. The migration backup allows going back.
- **Locks are per process:** the migration refuses while the server is running, but two
  command-line tools at once aren't guarded.
- **Edits in Excel** that duplicate a row or clear an id stop the app until they're fixed. This
  is deliberate.

**Migration of the real library:** applied 2026-11-06 22:18, with the user's approval.
- It moved 31 documents and 3 reading-log records, and kept every value.
- These are byte-identical to before: all 32 PDFs, 273 notes files, review progress,
  glossaries and the archive.
- Journal: `prepared` → `committing` → `committed` → `done`.
- An independent backup is in `../myLibrary-checkpoints/task3-pre-migration/`.
- `--check` is clean, and a second `--apply` changes nothing.
- Read-only smoke test on the migrated library:
  - the page lists 31 documents by id;
  - `/read/<id>` redirects with `&id=`;
  - notes, progress, lookup, review cards and the reading log all work by id.

**Full-text indexing reliability** (`book_search.py`; found during that smoke test):
- **The problem:** a single exception while indexing one PDF stopped `update()` for every
  remaining document. Only "updated (n books)" was reported, so partial runs looked complete.
- **Each document is read completely first,** then replaced in **one transaction per
  document**. A failure, whether reading or writing, rolls back that document only. Its
  previous pages stay searchable, and indexing goes on with the others.
- **A `status` table** records each document's state by id:
  - states: `indexed`, `failed` (not searchable), or `stale` (an older version of a changed
    PDF is still searchable);
  - also the PDF stamp tried, the last error, the attempt count, and the time of the last
    attempt and last success.
- **Retry:** a failed document is tried again at the next update. Success resets its error and
  its attempt count.
- **Reporting:** `update()` returns a report (`indexed`, `failed`, `unchanged`, `missing`,
  `removed`, `complete`).
  - The server logs "full-text index complete: …" or "INCOMPLETE: … FAILED (names)".
  - Search results carry `stale`, and the search answer lists `not_indexed` documents.
  - `book_search.py --status` prints every document's state.
- **`page_texts` closes every pdfium object explicitly** (text page, page, document), instead
  of leaving it to the garbage collector.
- **Tests:** 6 in `tests/test_book_search.py`:
  - one failing PDF among five;
  - retry, with the attempt count reset;
  - a changed PDF that fails stays searchable and is marked stale;
  - a write interrupted halfway is rolled back;
  - a missing PDF makes the run incomplete, and removed documents leave the status table;
  - everything is keyed by id.

**The access violation (`exception: access violation reading 0x…E8`):** not reproduced.
- **What happened:** once, while the server rebuilt the index of the migrated real library
  during the smoke test, indexing stopped after 9 of 31 documents.
- **The likely origin:** the error text is a Windows memory fault that ctypes turns into an
  `OSError`. Of the libraries in that code path only **pypdfium2**, which wraps the native
  pdfium library, uses ctypes. pypdf and sqlite3 are not ctypes-based. A read at a small offset
  from address 0 usually means a NULL pointer inside native code.
- **No traceback:** `warm_cache` printed only the message.
- **Bounded attempts to reproduce it, all without a crash:**
  - stress test: 3 runs, 9 passes over all 31 PDFs (6,729 pages each), with garbage collection
    forced constantly from another thread;
  - indexing the same library alone: 22 documents completed;
  - three server attempts on a temporary copy with `faulthandler`: two with the previous
    indexer, one with the new one. Each had 41–43 load rounds during indexing (page loads,
    which parse every PDF with pypdf, the document API, `/read/<id>`, a 38 MB PDF, and the Edge
    reading view). All 31 documents were indexed every time, with 0 fault reports.
- **Suspected, unconfirmed:** a timing-dependent fault in pdfium during text extraction. One
  possible mechanism: pdfium objects finalized by the garbage collector in another thread
  while the indexing thread was inside pdfium. The explicit closing removes that path.
- **Related to Task 3?** Not in its logic. `page_texts` is unchanged except for the id. The
  migration deletes the old index (it's a cache), so the next start re-reads every PDF, and
  this is where the failure surfaced.
- **What protects the data:**
  - the index is a rebuildable cache;
  - a failed document now keeps its older pages, is reported, and is retried;
  - PDFs are only read, never written, by indexing.
- **Not done: running the extraction in a subprocess.** That would contain a native crash that
  actually takes down the process, which `try`/`except` can't do. Without a reproduction it
  wasn't justified, but it's the next step if the fault reappears (see B17).

**Manual acceptance (user, 2026-11-07, on a temporary copy of the library):**
- Passed: opening, page navigation and zoom; text lookup; saving and restoring reading
  progress; shelves; notes; scripts; highlighting and saving marks; reopening with the marks
  kept; ids in every request.
- Search across documents found and opened the right document and page, but didn't show where
  the term was on the page. That led to the next item.

**Search-result highlighting** (`reader_static/lookup.js`, `lookup.css`, `library_server.py`):
- **How a term gets there:** a result in 在我的书中 (In my books) opens
  `/read/<id>?page=N&find=<term>`. The server passes `find` on to the reader URL (encoded:
  `&`, `#` and quotes stay inside the term).
- **It reuses PDF.js's own find**, with no separate highlighter:
  - the term is highlighted on the page in yellow, the current match in orange, and moved to
    the middle of the window;
  - the find bar opens with the term and "n of N matches", and its ▲▼ buttons go through the
    matches;
  - phrases, any case, and text split across spans are handled by PDF.js;
  - closing the find bar, or Esc, clears the highlights.
- **On screen only:** nothing is written into the PDF, the highlights are not annotations, and
  the marks-saving code never sees them.
- **When the term isn't on the page:**
  - The index matches other word forms ("vignetted" for "vignetting"), so the term may not be
    on the result's page as typed. Then the reader stays on that page with a notice in Chinese
    and English, instead of jumping to another page. The find bar's arrows still reach the
    other matches.
  - If the term isn't in the document at all, or the page is a scan without text, a notice
    says so.
- **Checks:** a server test (the term passed on and encoded; nothing added without a search),
  and 11 real-browser checks in Edge through its DevTools protocol, on the temporary copy:
  - another document opened by id at the right page;
  - highlighted and centred;
  - next and previous;
  - a second document with a phrase in a different case;
  - not found in the document;
  - found only on other pages (stays on the page);
  - closing clears the highlights;
  - all 31 PDFs unchanged.
- **Fixed during these checks:** PDF.js scrolled to a match on another page *after* the reader
  had returned to the result's page. The reader now withdraws that scroll request.
- **Note:** this relies on PDF.js 4.10.38's find controller (`findBar`, the
  `updatefindcontrolstate` event, and the `_scrollMatches` field). Recheck it after a PDF.js
  upgrade.

**Correcting marks** (`reader_static/lookup.js` `easyMarkEditing`). The user's request: remove
or undo a highlight or other mark made with PDF.js's tools.
- **Built on PDF.js 4.10.38, nothing new for deleting:**
  - PDF.js already selects, deletes (🗑 on the mark's toolbar, Delete or Backspace) and undoes
    (Ctrl+Z, and the Undo bar after a deletion). This also works for marks saved in the PDF
    earlier.
  - But only while an editing tool is on, which wasn't obvious.
- **Added:**
  - A single click on a highlight while reading turns the highlight tool on and selects that
    mark, so its 🗑 shows. A double-click still looks a word up.
  - Esc with no mark selected leaves the tool. With one selected, PDF.js's Esc unselects it.
  - The first time a tool is turned on, a notice in Chinese and English says how.
- **Saving:** a deletion is a change of marks like any other. `keepMarks` writes it into the
  PDF a second later, and the original stays in `archive/before-marks/`.
- **Only the selected mark is removed;** the search highlights aren't marks and aren't affected.
- **Limits:**
  - The click selects highlights only. Other kinds of mark (drawings, text, stamps) are
    selected with their own tool, as before.
  - An undo is possible only until the tab is closed (see Undo / Redo below). After that, the
    way back is the original in `archive/before-marks/` (it has none of the later marks).
  - This relies on PDF.js internals: the `switchannotationeditormode` event,
    `annotationEditorMode`, the `.highlightEditor` and `.highlightAnnotation` layers. Recheck
    them after a PDF.js upgrade.

**Undo / Redo for marks** (`lookup.js` `undoRedo`, `keepMarks`; `lookup.css`). The user's
request: familiar Undo and Redo, as in a word processor.
- **On the toolbar:** ↶ 撤销 (Undo) and ↷ 重做 (Redo), left of PDF.js's tools. Each is greyed
  out when there is nothing to undo or redo, and its tooltip gives the shortcut.
- **Shortcuts:** Ctrl+Z undoes; Ctrl+Y and Ctrl+Shift+Z redo. They work with a tool on and
  while reading.
- **The history is PDF.js 4.10.38's own; no second history was built:**
  - one history per open document, up to 128 steps;
  - leaving a tool (Esc) doesn't clear it;
  - a new mark after an undo drops the steps that could have been redone.
  
  PDF.js turns its own shortcuts off outside a tool. These buttons and keys ask it through
  the `editingaction` event (the one its own menus use), and read its
  `annotationeditorstateschanged` event to enable or grey out the buttons.
- **Text fields keep their own Ctrl+Z / Ctrl+Y:** the find bar, the dictionary popup, forms,
  anything editable. PDF.js doesn't see the keys there either; with a tool on, it used to
  take Ctrl+Z from search-type fields and text areas.
- **Search highlights aren't marks,** so they never enter the history.
- **Bug found and fixed (was in v0.2.5):**
  - **The bug:** a mark removed after a save wasn't saved. That is an undo of a new mark, a
    redo of a deletion, and also the plain undo of a deletion. PDF.js doesn't raise its
    "modified" flag when a mark leaves its storage, and it clears the flag when the last
    mark leaves. So the PDF kept the mark.
  - **The fix:** `keepMarks` compares the marks'
    hash with the last saved one, whatever the flag says. `""`, PDF.js's hash for no
    changes, stands for the PDF as opened.
- **Saving during undo or redo:**
  - a save writes the marks as they were when it started;
  - a change during the save is saved next;
  - "标注已保存 (Marks saved)" appears only once the server has written the file.
- **Limits:**
  - The history lasts as long as the tab: reopening starts a new one, as asked.
  - It covers this tab only. Two tabs of the same PDF still overwrite each other (D5).
  - It relies on PDF.js internals: the `editingaction` and `annotationeditorstateschanged`
    events, the `#editorModeButtons` toolbar group, and the empty hash `""`. Recheck them
    after a PDF.js upgrade.
- **Checks** (real Edge, temporary library, `browser_undo_check.py`), 55 of 55:
  - A, B; delete A; Ctrl+Z restores A; Ctrl+Z removes B; Ctrl+Y restores B; Ctrl+Shift+Z
    deletes A again;
  - the same after Esc, with the buttons and the keys;
  - three undos and three redos in a row;
  - a new mark after an undo drops the redo steps;
  - Ctrl+Z and Ctrl+Y in the find field (its own undo ran), a text area and a search field
    (with a tool on) leave the marks alone;
  - the buttons enabled and greyed out at every step;
  - rapid undo/redo pairs;
  - an undo, redo and undo during a save slowed to 3 s:
    - "Marks saved" not shown early;
    - a second save followed;
    - the PDF ends with exactly the final marks;
  - a saved mark deleted, restored with ↶ and deleted again with ↷, saved;
  - reopened: the final marks, and a new, empty history.
  
  The earlier marks and Preview checks pass again, apart from the two reading-log checks
  described there.

**Preview Mode** (`lookup.js` `previewBar`; `library_server.pdf_url(..., preview=True)`). The
user's request: opening a search result shouldn't count as reading.
- A result in 在我的书中 (In my books) opens `/read/<id>?page=N&find=<term>&preview=1`. The
  server passes `preview=1` on to the reader.
- **In a preview:**
  - nothing is recorded: no "Last read" in the notes README, no reading time, no pages in the
    reading log, whatever you do (turn pages, zoom, search, close);
  - a small bar at the top says 预览：不计入阅读进度 (Preview: not counted as reading);
  - notes, saved words and marks still work as usual, because you made them yourself.
- **开始阅读 (Start reading)** on the bar makes it a normal reading tab:
  - the current page is saved as "Last read" at once, and reading time is counted from then;
  - `preview` is taken out of the address, so a reload reads normally.
- **Read and Continue** on the library page are unchanged.

**Checks for both** (real Edge through the DevTools protocol, on a temporary library with two
invented PDFs, server on port 8767; script `browser_marks_check.py`):
- Marks, 21 of 21:
  - two highlights made and saved into the PDF (checked with pypdf); original archived;
  - reopened: a click on one selects it and shows 🗑;
  - Delete removes it, the Undo bar shows, Ctrl+Z restores it;
  - Esc leaves the tool;
  - 🗑 removes the first. After saving, the PDF has exactly the other one, also after reopening.
- Preview, 12 checks:
  - the bar shows and the search highlights stay;
  - turning pages, zooming and closing leaves no "Last read" and no reading-log entry;
  - Start reading removes the bar and `preview` from the address, and saves the current page;
  - later pages count, and a normal open still saves "Last read".
- **Not settled by that run:**
  - In the full run, the reading-log entries sent as a tab closes reached the server only when
    the headless browser exited. That send is unchanged code (v0.2.5).
  - Checked on its own, both navigating away and closing the tab delivered them within
    4 seconds, and the log held no page from the preview part.
- **Not tested by hand yet:** the user's own acceptance test of both.
- 212 Python tests pass. The server test checks that `preview=1` is passed on.

**Persistence audit (2026-11-07).** The user found that a highlight made, or a saved one
deleted, just before closing the tab could be lost, and asked for a review of every write.

| Change | Starts in | When it's sent | Server writes | Saved shown after | Close at once | Errors | Concurrent writes |
|---|---|---|---|---|---|---|---|
| Marks: make, edit, delete, undo, redo | reader (PDF.js) | 1 s after the last change, or Save now | whole PDF, atomic + fsync, original kept once | server's answer | **was lost** → now warned until saved | status + Retry | one save at a time; changes during a save saved next; two tabs: D5 |
| Reading position | reader | 2 s after a page turn; on close (`keepalive`) | README line, locked | none shown | arrives | none shown | last arrival wins |
| Reading time | reader | every minute; on hide or close (`keepalive`) | `reading-log.json`, locked | none shown | arrives; up to 1 min lost on a crash (L13) | none shown | adds up, locked |
| Save word, add glossary term, topic note | popup button | on click (`keepalive` now) | file, locked | server's answer (button) | arrives | button says "Save failed" | locked |
| Chapter tick, shelves, review answer, settings, Script | library page | on click (`keepalive` now) | file or catalog, locked | server's answer (toast) | arrives | toast | locked; catalog via `catalog.*` |
| Add, OCR, Refresh, backups, Find online → Add | library page | on click | background job | job finished | job continues on the server | job history | `FILING` lock |
| Chapter notes, scripts' contents | outside editor (VS Code) | the editor's own save | not by myLibrary | the editor | the editor's own | the editor | L14 |

There is no metadata editing yet (task 6); Refresh and adding change details in background
jobs.

- **Confirmed and fixed:**
  - **Marks lost on closing** (release-blocking).
    - Causes:
      - The reader saved only after 2.5 s without changes, checked every second.
      - Before that, the only protection was PDF.js's own close warning. It follows a flag
        that PDF.js doesn't raise when a mark is removed, and clears when the last mark goes.
      - So a deletion, or an undo after a save, could close without a warning and was lost.
      - In one run, deleting a saved highlight and leaving at once gave no warning, and the
        PDF kept the highlight. Two reruns of that case did warn: the miss is intermittent,
        and its exact trigger wasn't pinned down.
    - Now the reader tracks the marks themselves (`lookup.js` `keepMarks`). While PDF.js's
      hash of the marks differs from the last one the server confirmed, or a save is under
      way:
      - the browser's own "Leave site?" warning comes up on close, reload or navigation;
      - a status shows 标注未保存 (Marks not saved yet) with 立即保存 (Save now);
      - then 正在保存 (Saving);
      - 标注已保存 (Marks saved) appears only after the server's answer.
    - A failure shows 标注没保存 (Marks not saved) with the error and 重试 (Retry):
      - it is tried again automatically 3 times, 3 s apart;
      - it stays visible until a save succeeds.
    - Saves start after 1 s without changes, checked 4 times a second.
    - Nothing is sent while closing: a whole PDF can't be sent reliably then.
  - **A marked PDF or upload cut short was accepted.**
    - When the tab closes while the PDF is being sent, the server read fewer bytes than
      announced.
    - For marks, the cut-off copy could pass the "%%EOF near the end" check, because the
      original's own %%EOF is still near the end. The cut-off copy was then written over the
      book.
    - `Handler._body` now refuses a short body (400, "cut short"), and the book is left as it
      was.
    - Test: `test_marks_cut_short_are_refused`. It fails without the fix.
- **Safe already:**
  - Small writes reach the server in one request and are written under a lock before the
    answer.
  - The page shows the answer.
  - They now also use `keepalive`, so a click just before closing still arrives.
- **Checks** (real Edge, temporary library, `browser_close_check.py`), 53 of 53. Each
  action is followed by close, navigation or reload with no delay:
  - Make a highlight and leave (close, navigate, reload): warned. After Stay: saved, and on
    disk.
  - Delete a saved highlight and leave: the same.
  - Rapid changes with undo and redo, then close: warned. After Stay, the final state is on
    disk.
  - Failure, once: shown with the error, then saved automatically.
  - Lasting failure: still shown after the automatic attempts, warned on close, nothing on
    disk. Then Retry saves it.
  - Slow server (4 s): "Saving" until the answer, warned on close, then saved.
  - Save now: saved, then closing is free.
  - Browsing only (tool on and off over saved marks, pages, zoom): no status, no warning.
  - Position: a page turn and leave at once (close, navigate, reload): saved, no warning.
  - A chapter tick and Save word sent just before closing: both written.
  - Undo/Redo checks: 54 of 55. The one miss is a check timing artifact: saves now come
    sooner, so the expected new "Marks saved" never appeared, and the PDF check after it
    passed.
  - Marks and Preview checks: unchanged.
- **Distinctions:**
  - *Verified persistence:* every case above whose final state was read back from the disk.
  - *Correctly warned:* closing with unsaved or still-saving marks.
  - *Not supported:* forced or OS termination (L12); reading time on a crash (L13).
- **Not verified:**
  - closing with the window's ✕ or Ctrl+W by hand. The checks close tabs through the
    DevTools protocol, which runs the same warning;
  - a real disk failure (simulated in the page).
  - The library page's own beforeunload: none was added. Its writes are single requests,
    without pending edits.
- **Note:** clicking Save now unselects a new highlight, and PDF.js then stores it slightly
  differently. So a second, short save can follow; closing during it warns, as it should.

**Finishing:**
- [x] Apply the migration to the real `library/` (done and verified; `--check` clean).
- [x] Commit the code (`5b82b6d`) and the migrated example data (`17dd9c4`:
      `library/catalog.csv` and `library/notes/reading-log.json`, the latter including the
      uncommitted reading data), then push both together.

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
