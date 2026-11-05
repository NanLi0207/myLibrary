# myLibrary

A general study tool for learning from your own PDF books (any subject): reading view with
English–Chinese lookup and subject glossaries, book search, progress, notes, and per-chapter
Python scripts (`examples/`) for checking a book's worked examples. No marimo/notebooks.
The user's own use is optical design, which is also the bundled example (optics glossary, the
`optics` dependency group, `mylibrary.paraxial`). Keep the tool itself subject-neutral: nothing
in `scripts/` should assume optics. The repo is public; the books never go in it. See README.md.

**Chinese always comes with English (always apply).** Wherever Chinese appears in the UI, docs,
messages, file headers or config (buttons, labels, tooltips, README examples, glossary labels),
put its English translation next to it: in the popup use `bi(zh, en)` / `biEl(...)` in
`lookup.js` (Chinese, then the English smaller and grey); in text write e.g.
"**加入生词本** (Save word)" or "光阑 (aperture stop)". The glossary's `zh` column is the Chinese
term itself (its English is the `term` column); its `note` and `definition` texts are still
Chinese only.

## New books: naming convention (always apply)

When a new book file appears in `books/` (or the user mentions adding one), run:

```
uv run scripts/add_book.py --dry-run   # check the proposed slug first
uv run scripts/add_book.py
```

Each book gets one slug, `<first-author-surname>-<year>-<short-title>`, lowercase ASCII,
hyphen-separated, stop words (a, the, of, and, ...) dropped, subtitle dropped, at most 5 title words.
Example: `shannon-1997-art-science-optical-design`. The slug is used for:

- `books/<slug>.<ext>` (the book itself; local only: `books/` is gitignored because the books are
  copyrighted. Never commit or push a book, and don't undo that ignore rule)
- `examples/<slug>/` (plain Python scripts `chNN_<topic>.py`, created only when the user clicks
  "Script" on a chapter; run with `uv run` or VS Code's Run button)
- `notes/<slug>/README.md` (metadata + reading progress) and `notes/<slug>/chNN-<chapter>.md`

- `catalog.csv` (one row per book: title, authors, year, publisher, ISBN, pages, chapters,
  subjects, where each field came from; the original download file name is deliberately not
  recorded). The user browses it with
  `uv run scripts/library_server.py` (local server: Read/Continue opens PDF at the chapter page,
  and the chapter's notes in VS Code, plus its script if one exists; "Script" creates/opens
  `examples/<slug>/chNN_*.py`; ticking chapters edits notes READMEs).
  The server opens PDFs in PDF.js with a word lookup for the user (a Chinese reader):
  `scripts/reader.py` + `scripts/reader_static/`, subject glossaries `glossaries/<name>.csv`
  (term, zh, note, definition: a short definition in Chinese; shown before the ECDICT meaning;
  labels, default and on/off in `glossaries/glossaries.toml`; the user's is `optics.csv`,
  label "光学 Optics": extend it with real optics terms), full-text search of all books per page
  (`scripts/book_search.py`, index in `.cache/reader/books.db`), saved words
  in `notes/<slug>/vocabulary.md` (the user's own list, never delete).
  `library.html` is the static read-only copy (built by `scripts/library_page.py`, rebuilt by
  add_book.py). Chapter start pages are cached in `.cache/chapter_pages.json`
  (`--refresh-chapters` clears a book's entry automatically).
- To take a book out, use `uv run scripts/add_book.py --remove <slug>`: it moves the PDF, notes
  and scripts to `archive/` and drops the catalog row. Never delete notes or scripts outright;
  they hold the user's own work. Rebuild the page after changing catalog or notes.
  If the user corrects a book's details, update its catalog row and notes README too.

Books are always PDFs (the user's choice; don't add DjVu/EPUB tooling). The script reads the
PDF's table of contents (bookmarks, else the printed Contents pages; for image-only scans the
Contents pages are read with OCR by `scripts/book_ocr.py`, cached in `.cache/ocr/`; better:
`scripts/ocr_pdf.py` gives a scan a real invisible text layer, which add_book.py offers for new
scans, original kept in `archive/books/`; every add_book.py run ends by asking about each
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
`uv run scripts/add_book.py "books/<file>" --author .. --year .. --title ..`.
Prefer the year of the edition actually on disk; different editions get different slugs.
