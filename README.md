# myLibrary

A self-hosted study companion for learning from your own PDF books, in any subject.

- **Read** in a browser-based reading view that remembers where you stopped.
- **Look up** any English word or phrase: double-click it for its meaning in your **subject
  glossaries** (with a short definition in Chinese) and in an offline **English–Chinese
  dictionary**.
- **Search all your books at once** to see how different authors explain a term.
- **Track progress** chapter by chapter, with a notes file per chapter, and a Python script
  to check the book's worked examples when you want one.

Everything runs on your own computer. **No books are included**: bring your own PDFs.

**Free for non-commercial use** (personal study, schools, research; see [License](#13-license-contributing-and-the-ready-to-use-package)).
A **ready-to-use package** (no Python or command line needed) is coming soon, for **9.9 RMB**.
Contributions are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md).

> The author uses it to learn optical design. Their library is included in `library/` as a
> worked example: shelves, notes, an optics glossary of ~300 terms, chapter scripts and a small
> optics code module (the books themselves are not included). Your own library lives in its own
> folder, for any subjects you like (see [Use it for your own subject](#use-it-for-your-own-subject)).

**Contents**

1. [Quick start](#1-quick-start)
2. [A typical study session](#2-a-typical-study-session)
3. [The library page](#3-the-library-page)
4. [The reading view](#4-the-reading-view)
5. [Looking up words and terms (查词, look-up)](#5-looking-up-words-and-terms-查词-look-up)
6. [Glossaries](#6-glossaries)
7. [Notes and chapter scripts](#7-notes-and-chapter-scripts)
8. [Managing books](#8-managing-books)
9. [Where things are stored](#9-where-things-are-stored)
10. [Command reference](#10-command-reference)
11. [Troubleshooting and FAQ](#11-troubleshooting-and-faq)
12. [Built with](#12-built-with)
13. [License, contributing and the ready-to-use package](#13-license-contributing-and-the-ready-to-use-package)

---

## 1. Quick start

You need [uv](https://docs.astral.sh/uv/) (it installs Python and the packages) and, for notes
and chapter scripts, [VS Code](https://code.visualstudio.com/) (with its Python extension). The
shortcut below is for Windows; on other systems start the server from a terminal.

```powershell
# The tool goes into your home folder, e.g. C:\Users\<you>\myLibrary
git clone https://github.com/NanLi0207/myLibrary.git "$HOME\myLibrary"
cd "$HOME\myLibrary"
uv sync                                # install Python and the packages (.venv)
uv run scripts/make_shortcut.py        # Windows: Desktop + Start menu shortcut "myLibrary"
```

This folder only holds the tool. Your books and notes go into a separate *library* folder
(created on first start, see below), so updating the tool with `git pull` never touches them.

**Your library.** The tool works on a *library*: one folder with your books, notes,
glossaries and chapter scripts, for every subject you study. The first start creates an empty
one in `Documents\myLibrary Library` and remembers it (in `local.toml`, see
[Where things are stored](#9-where-things-are-stored)). Put your PDFs into its `books/` folder and
register them (see [Managing books](#8-managing-books)):

```powershell
uv run scripts/add_book.py --dry-run   # preview the names it will give them
uv run scripts/add_book.py             # register them
```

This repository's own `library/` folder is the author's library (optical design), included as
a real example: browse it to see what a well-used library looks like. Leave it as it is; your
library lives in its own folder, so `git pull` never mixes the two.

**Every day:** double-click **myLibrary** (or press Win and type "myLibrary"; elsewhere run
`uv run scripts/library_server.py`). The library page opens in your browser; click
**Continue** on a book.

The shortcut starts a small server in a **minimized window**. It only listens on your own
computer (`http://127.0.0.1:8765`); close the window to stop it. Starting the shortcut while the
server runs just opens the page again.

The first start downloads the PDF viewer and the offline dictionary (~72 MB, once) and indexes
your books for search (seconds). Until the download finishes, books open as plain PDFs without
word lookup.

### Use it for your own subject

1. **Shelves:** say which subjects you study in your library's `library.toml` (e.g.
   `Biology = "生物 Biology"`), and put each book on one or more shelves with the **Shelves**
   button on the library page.
2. **Glossaries:** create one for your subject, e.g. `glossaries/biology.csv` in your library,
   starting with the line `term,zh,note,definition` (see [Glossaries](#6-glossaries)). Or just
   start reading: the first term you add from the popup creates `glossaries/my-terms.csv`. For
   an example, copy `library/glossaries/optics.csv` from this repository.
3. **Packages:** add the Python packages your chapter scripts need with `uv add <package>`.

## 2. A typical study session

1. **Open the library** and click **Continue · p. N** on the book you're reading. This opens:
   - the book, in the reading view, at the page where you stopped;
   - in VS Code, the **notes** file for that chapter (`notes/<book>/chNN-*.md`), and the
     chapter's Python script if you've made one.
2. **Read.** Double-click any word you don't know, or drag over a phrase (see
   [section 5](#5-looking-up-words-and-terms-查词-look-up)). Save useful words with **加入生词本** (Save word).
3. **Take notes** in your own words in the chapter notes file: key ideas, equations,
   questions.
4. **Check it in Python** (optional): click **Script** on the chapter and recompute a worked
   example, re-derive a result or plot something (see [section 7](#7-notes-and-chapter-scripts)).
5. **Stop whenever you like.** Your page is saved automatically; just close the tab.
6. When you've **finished a chapter**, tick it on the library page (Chapters → checkbox).

## 3. The library page

One card per book. The **shelf bar** under the search box shows your subjects (All, 光学
Optics, 激光 Lasers, …) with how many books each has; click one to see only those books. Use the
search box to filter (title, author, subject, shelf, chapter titles) and the sort menu to order
the cards (title, author, newest, progress, recently added, recently read). The **Books and
papers** menu shows only books or only papers.

At the top: **＋ Add** (choose PDFs to add, see [Managing books](#8-managing-books)),
**☁ Back up** (below), **⚙ Settings** (below) and **Quit** (stops myLibrary; your place in each
book is already saved).

**☁ Back up** saves your library to GitHub in one click: it commits only the library folder
(notes, reading progress, vocabulary, shelves, topic notes, glossaries, catalog; never PDFs, and
never other changes in the repository) and pushes it. It's shown when the library is in a git
repository with a remote, as `library/` is here. If there are unpushed *code* changes, it stops
and asks you to push those yourself; if GitHub can't be reached, it says so (your changes stay
saved locally). From the terminal: `uv run scripts/backup.py`.

| On a card | What it does |
|---|---|
| **Continue · p. N** | Opens the book at the page you last read, plus that chapter's notes (and script, if any) |
| **Start reading** / **Continue** (no page saved yet) | Opens the first chapter you haven't ticked |
| **PDF** | Opens the book in the reading view at its first page (notes not opened) |
| **Notes** | Opens the book's notes in your editor (see Settings) |
| **OCR (~N min)** | Only on scanned books: adds a text layer so the book can be looked up and searched |
| **Chapters** | Shows the chapter list: **Read** opens one chapter, **Script** its Python script; the checkbox ticks it |
| **Shelves** | Which shelves the book is on, separated by `;` (e.g. `Optics; Lasers`) |
| **Mark as read** | Papers only (instead of Chapters): mark the paper as read, or not |
| **DOI** | Papers: the paper's page at its publisher |
| **Cite ▾** | A menu of citation formats, each with a preview; click one to copy it: APA, IEEE, GB/T 7714 (中国国标 Chinese standard), BibTeX (LaTeX) and RIS (EndNote, Zotero, Mendeley) |
| Green tags | The book's shelves |
| Progress bar, "0/8 chapters · 3%" | How far you are (see below) |
| "Last read: page 41 · Ch 2 · date" | Where you stopped |

**Settings** (⚙ Settings at the top of the page):

| Setting | What it does |
|---|---|
| **Library folder** | Where your books and notes are kept. **Choose…** opens Windows' folder dialog. Another folder opens the library there, or starts a new, empty one; the current library stays where it is |
| **Open notes with** | The app set for `.md` files (e.g. Typora, Obsidian), Notepad, VS Code, or your own command (`{file}` stands for the note) |
| **Show the Python features** | The **Script** button per chapter (see [Chapter scripts](#chapter-scripts-examplesbookchnn_topicpy)) |

They're saved in `local.toml` in the tool's folder (in the ready-to-use package:
`%APPDATA%\myLibrary\settings.toml`, so a new version keeps them).

**Ticking chapters.** A ticked chapter is one you've marked as *finished*. Ticking writes
`- [x]` into the book's `notes/<book>/README.md`; you can also edit that checklist by hand.
Nothing ticks a chapter automatically: skimming isn't the same as finishing.

**Shelves** group books by subject, and a book can be on several: *Laser-Induced Damage of
Optical Materials* is on Optics, Lasers and Materials. They're stored in the `shelves` column of
`catalog.csv`. Give a shelf a label (Chinese with its English translation) in `library.toml`:

```toml
[shelves]
Optics = "光学 Optics"
"Lens design" = "镜头设计 Lens design"
```

A shelf also decides which glossary comes first in the lookup popup: reading a book on the
Optics shelf, the `optics` glossary's meanings are listed first.

**Progress** is whichever is further: the share of chapters ticked, or the page you last read out
of the book's pages. **Sort: progress** puts the furthest-along book first, then the one read
most recently.

`uv run scripts/library_page.py` writes `library.html`, a static, read-only copy of the page
(no buttons) that opens without the server. It's local only (not in git).

## 4. The reading view

Books open in **PDF.js** (Mozilla's PDF viewer, the one inside Firefox), served by the local
server. Its toolbar works as usual: page number, zoom, search (Ctrl+F), sidebar with
thumbnails and the book's outline.

**Your place is saved automatically.** About 2 seconds after you stop on a page, and when you
close the tab, the page is written to the book's notes README under "Reading progress":

```
Last read: page 41 (Ch 2: Design Forms), 2026-11-05
```

Opening a chapter just to look something up doesn't move your place; only turning pages does.
Because it's in your notes, it's kept in git along with them.

## 5. Looking up words and terms (查词, look-up)

### Ways to look something up

| You do | What happens |
|---|---|
| **Double-click a word** | A popup opens with its meaning |
| **Drag over 1–6 words** (e.g. *veiling glare*) | Looked up right away, like a double-click |
| **Drag over a longer passage** | A **翻译** (Translate) button appears; it opens Bing Translator (online) |
| **Edit the word at the top of the popup** and press **Enter** | Looks up what you typed |

If a drag starts or ends in the middle of a word, the whole word is taken ("eiling gla" →
*veiling glare*), and the highlight on the page shows what was looked up. In **scanned books**
the invisible OCR text can sit slightly off the printed letters, so a selection may still catch
the wrong characters, or the OCR may have misread a letter. Then fix the word at the top of the
popup and press Enter.

### What the popup shows

1. **The word**, its phonetics, and 🔊 to hear it read aloud.
2. **Glossary meanings**, shown first, each tagged with its glossary's label (e.g.
   *光学 Optics*): the Chinese term, a short definition and, where needed, a warning about the
   everyday meaning. In optics, *stop* → 光阑 (aperture stop), not 停止 (to stop); *pupil* → 光瞳
   (optical pupil), not 学生 (school pupil). If several glossaries have the term, you see each
   subject's meaning. Longer terms around the word are found too: double-clicking *pupil* in
   "the exit pupil" shows 出瞳 (exit pupil) as well as 光瞳 (pupil). For a longer selection, the
   glossary terms *inside* it are listed.
3. **Dictionary meaning** from ECDICT (an open-source English–Chinese dictionary, offline).
   Plurals and verb forms are handled (*aberrations* → *aberration*, *matrices* → *matrix*).
   For a phrase the dictionary doesn't know, each word's meaning is listed.
4. **Learn more**, under each term:
   - **📚 在我的书中** (In my books): the pages of *all* your books that discuss the term most, with a short
     snippet (the book you're reading first). Click one to jump to that page. Often the best way
     to really understand a term: see how two or three authors explain it.
   - **📝 主题笔记** (Topic note): opens your note on this term across all your books (see
     [Topic notes](#topic-notes-notestopicstopicmd)).
   - **Wikipedia**, **维基百科** (Chinese Wikipedia), **百度百科** (Baidu Baike), all online.
5. **＋ 加入术语表** (Add to glossary): shown when the word or phrase isn't in a glossary yet
   ([section 6](#6-glossaries)).
6. **加入生词本** (Save word): adds the word to the book's vocabulary list.

### Your vocabulary list

**加入生词本** (Save word) adds a row to `notes/<book>/vocabulary.md`:

```
| Word | Phonetic | 中文 Chinese | Page | Added |
|---|---|---|---|---|
| vignetting |  | 渐晕 | 16 | 2026-11-05 |
```

(渐晕 is Chinese for *vignetting*.) The 中文 (Chinese) column takes the glossary meaning if
there is one. Each word is saved once per book.

### From the terminal

```powershell
uv run scripts/reader.py entrance pupil      # glossary + dictionary meaning
uv run scripts/book_search.py vignetting     # where your books discuss it
```

## 6. Glossaries

A general dictionary gives everyday meanings; a subject gives words special ones. Glossaries
fix that: one CSV per subject in `glossaries/`, and **all of them are used**.

```
term,zh,note,definition
vignetting,渐晕,,轴外光束的一部分被孔径光阑以外的通光口径挡住，使视场边缘照度下降；...
```

(In English: *vignetting*, 渐晕; "part of an off-axis beam is blocked by apertures other than
the aperture stop, so the edge of the field gets darker; ...")

| Column | Meaning |
|---|---|
| `term` | English term, singular (*entrance pupil*, not *entrance pupils*) |
| `zh` | Chinese term (required) |
| `note` | Optional: abbreviation or a warning (e.g. *PSF*, or *不是“学生”*: "not 'school pupil'") |
| `definition` | Optional: short definition |

`glossaries/glossaries.toml` (optional) sets how each glossary is labeled in the popup, which
one new terms go to, and lets you switch one off without deleting it:

```toml
default = "optics"          # where ＋ 加入术语表 (Add to glossary) adds terms (else the first alphabetically)

[optics]
label = "光学 Optics"       # the tag shown in the popup (else the file name)

[biology]
label = "生物 Biology"
# enabled = false           # stop using this glossary
```

**Adding terms.** Easiest from the popup: **＋ 加入术语表** (Add to glossary), type the
Chinese term and (optionally) a definition in your own words, choose the glossary if you have
several, then **保存** (Save).
Or edit the CSV in VS Code or Excel (save as UTF-8). Changes show at the next lookup; no restart
needed.

**The bundled optics glossary** (`glossaries/optics.csv`, ~300 terms: paraxial optics,
aberrations, image quality, design and tolerancing, stray light, coatings, lasers,
optomechanics) shows what a good glossary looks like. Its definitions are short summaries; if
one disagrees with your books, trust the book and correct the row.

## 7. Notes and chapter scripts

### Notes (`notes/<book>/`)

| File | Contents |
|---|---|
| `README.md` | Book details, the chapter checklist (ticks), the "Last read" line |
| `chNN-<chapter>.md` | One per chapter: headings for each section, plus *Key ideas*, *Equations*, *Questions*, *Check it in Python* |
| `vocabulary.md` | Words you saved while reading |

The chapter files start with headings only. Write the notes **in your own words**; don't paste
text from the books (they're copyrighted, and rewriting is how you learn it). Notes are plain
Markdown, so equations can be written as `$E = mc^2$`.

### Topic notes (`notes/topics/<topic>.md`)

Chapter notes follow one book; a **topic note** follows one idea across all your books, e.g.
`aberrations.md` combining what Kingslake, Fischer and Geary say. Open one from the lookup popup
with **📝 主题笔记** (Topic note): the first time, it's created with headings and a list of the
pages in your books that discuss the term most (book and page only), ready for your own summary.

### Chapter scripts (`examples/<book>/chNN_<topic>.py`)

For technical books, recomputing a worked example is one of the best ways to check that you
understood it. Click **Script** next to a chapter on the library page: the first time, it creates
a short, plain Python script for that chapter from a template, and opens it in VS Code. After
that, **Read** and **Continue** open it together with the chapter's notes.

Write your calculation in `main()`, then run it with VS Code's **Run** button (▶), or:

```powershell
uv run library/examples/<book>/ch03_aberrations.py   # the path is shown in the script's header
```

`uv sync` installs `numpy`, `scipy`, `sympy` and `matplotlib` (the `science` group) for these
scripts. Ideas:

- recompute a worked example and print it next to the book's answer;
- re-derive an equation with `sympy`;
- plot how a result changes with a parameter (`matplotlib`);
- fit a model to data with `scipy`.

Scripts are created only when you ask for one; a chapter without calculations needs none.

### Your own code (`code/`)

When a function proves useful in more than one script, move it into your library's `code/`
folder, grouped by subject (e.g. `code/optics/paraxial.py`). Chapter scripts can import it
directly (`from optics.paraxial import thin_lens`): the script template puts `code/` on Python's
import path. Add tests next to it, in `code/tests/`, checking it against results from a book;
`uv run pytest` runs them along with the tool's tests.

## 8. Managing books

### Naming

Every book has one **slug**: `<first-author-surname>-<year>-<short-title>`, lowercase, e.g.
`shannon-1997-art-science-optical-design`. The same slug names the PDF, its notes folder and
its scripts folder. Books are always PDFs.

### Adding a book

**From the library page:** click **＋ Add** and choose one or more PDFs. Each is copied
into your library, identified (ISBN, the PDF's details, Open Library), named and registered in
the background; a panel shows the progress. If the title, author or year can't be found, the
page asks for them. A scanned book gets an **OCR** button (see below).

**From the terminal:** put the PDF into your library's `books/` folder with any file name, then:

```powershell
uv run scripts/add_book.py --dry-run   # preview: proposed name, and where each detail came from
uv run scripts/add_book.py             # do it
```

The script identifies the book (from an ISBN, the PDF's metadata, the file name or the
copyright page, looked up on Open Library), renames it to its slug, adds a row to `catalog.csv`,
and creates the notes folder with one notes template per chapter, read from the PDF's table of
contents. Check anything the dry run marks as coming from the "filename". If a detail is wrong:

```powershell
uv run scripts/add_book.py "books/scan123.pdf" --author "Warren J. Smith" --year 2008 --title "Modern Optical Engineering"
```

If the chapter list came out wrong, `--refresh-chapters` reads it again (your notes are kept).

### Papers

Papers live in the library's own **`papers/`** folder, next to `books/`. Add them with
**＋ Add** on the library page, or put the PDFs into `papers/` and run
`uv run scripts/add_book.py`. Everything is filled in automatically, found in this order:

1. its **DOI**, from the PDF's details or its first two pages (never the reference list, whose
   DOIs belong to other papers), looked up on [Crossref](https://www.crossref.org/), the DOI
   registry: title, all authors, year, journal, volume, issue, pages;
2. its **arXiv number** (`arXiv:2101.01234`, or a file named `2101.01234.pdf`), looked up on
   arXiv; if the preprint was published since, the journal version is used;
3. no number at all, as in most **old papers**: the **title and authors at the top of the first
   page**, searched on Crossref (publishers have given many old papers a DOI afterwards, back to
   the 1800s), then on [OpenAlex](https://openalex.org), an open catalogue that also lists works
   without any DOI. A result is used only if its whole title appears on that page, and when a
   paper was reprinted, the version whose year is printed on the page wins (the original, not a
   later reprint). A **scanned** paper's first page is read with OCR first (a few seconds).

Only if all three fail does the page ask for the title, author and year. A PDF in `papers/` is
always a paper; one added through the page or put into `books/` becomes a paper when it's
recognised as one, and is moved to `papers/`. It gets the same kind of name as a book
(`doe-2019-freeform-optics-compact-imaging`).

Instead of chapter notes, a paper has one notes file, `notes/<slug>/notes.md`, with *Summary (in
my own words)*, *Key results*, *Method*, *Questions* and *How it relates to my books*; its
README has the details and one checkbox, *Read the paper*. A paper's **keywords** are recorded too (from the PDF's details, else its
first page's "Keywords:" line, else OpenAlex) and shown as small tags on its card, above the
shelf tags. On the library page a paper shows its
journal, **Mark as read** instead of Chapters, and a **DOI** link; **Read** / **Continue** open it
at page 1 (or where you stopped) with `notes.md`.

### Scanned books

A scan has only page images, so its text can't be selected or searched. On the library page,
such a book has an **OCR (~N min)** button: it adds the text layer in the background, with a
progress bar, and you can keep reading meanwhile. From the terminal, `add_book.py` offers to
add an **invisible OCR text layer** (`--ocr` to always do it, `--no-ocr` to never), and at the
end of every run it asks about each scan in `books/` that still has none (Enter = no). By hand:

```powershell
uv run scripts/ocr_pdf.py books/<slug>.pdf   # ~1.5 s per page; asks first
```

The page images stay the same; the original scan is kept in the library's `archive/books/`. An interrupted
run continues where it stopped. OCR text is never perfectly placed or perfectly spelled; see
[section 5](#ways-to-look-something-up).

### Bookmarks

`uv run scripts/add_bookmarks.py` adds a clickable outline (chapters and sections) to books
that have none, using the chapter pages the library has found. Books that already have
bookmarks are never changed; originals are kept in `archive/books/`.

### Removing a book

```powershell
uv run scripts/add_book.py --remove <slug> --dry-run   # preview
uv run scripts/add_book.py --remove <slug>             # asks before moving anything
```

The PDF, notes and scripts move to `archive/`; nothing is deleted. To bring a book back,
move its files back and run `add_book.py`. If you only delete the PDF, the card stays and says
"PDF missing"; its notes and scripts still open.

## 9. Where things are stored

The repository has two parts: **the tool**, and **a library** it works on.

```
myLibrary/                   the tool (this repository)
├── scripts/                 the tool itself
├── tests/                   the tool's tests (uv run pytest)
├── local.toml               which library this computer opens (local only, not in git)
├── .cache/reader/           PDF viewer and dictionary, shared by every library (local only)
└── library/                 the author's library, included as an example

<your library>/              e.g. Documents/myLibrary Library
├── library.toml             its name, and your shelves with their labels
├── catalog.csv              one row per book: title, authors, year, ISBN, pages, shelves, ...
├── books/<slug>.pdf         your books (never in git: they're copyrighted)
├── papers/<slug>.pdf        your papers (never in git either)
├── notes/<slug>/            per book: notes, ticks, last-read page, vocabulary
├── notes/topics/            your topic notes, across books
├── glossaries/              your subject glossaries (*.csv) and glossaries.toml
├── examples/<slug>/         your chapter scripts (created with "Script")
├── code/                    your reusable Python code, by subject, and its tests
├── library.html             static copy of the library page (local only)
├── archive/                 removed books, original scans (local only)
└── .cache/                  search index, chapter pages, OCR results (local only)
```

**Which library the tool opens**, in this order: `--library <folder>` on any command, the
`MYLIBRARY_LIBRARY` environment variable, then `local.toml` in the tool's folder
(`library = "D:/Study/My Library"`; a relative path is relative to the tool's folder). With none
of these, the first start creates `Documents\myLibrary Library` and writes `local.toml`.

**Your own work** (back it up, never delete): your library's `notes/`, `examples/`, `code/`,
`glossaries/`, `catalog.csv` and `library.toml`. Version it with git if you like, in its own
repository (private or public).

**The books are never in git**, because they're copyrighted: `.gitignore` excludes every PDF.
Git doesn't back them up, so keep your own copy of the PDFs somewhere else (an external drive,
or a private cloud folder).

**Safe to delete** (rebuilt automatically when needed):

| What | Where | Rebuilt by |
|---|---|---|
| PDF viewer, dictionary | the tool's `.cache/reader/` | the server on start, or `uv run scripts/reader.py --setup` |
| Full-text index for 在我的书中 (In my books) | the library's `.cache/books.db` | the server on start |
| Where each chapter starts in each PDF | the library's `.cache/chapter_pages.json` | the server, on first use |
| OCR results | the library's `.cache/ocr/` | `ocr_pdf.py` / `add_book.py` (slow: re-runs OCR) |

## 10. Command reference

Run these in the tool's folder (PowerShell, a terminal, or the VS Code terminal). Every
command works on your library (see [above](#9-where-things-are-stored)); add `--library <folder>`
to use another one.

| Command | Does |
|---|---|
| `uv run scripts/library_server.py` | Start the library (same as the shortcut); `--port 8766` to use another port, `--no-browser` to not open a tab |
| `uv run scripts/make_shortcut.py` | (Re)create the Desktop and Start menu shortcuts (Windows) |
| `uv run scripts/add_book.py --dry-run` / no flag | Preview / register new books in `books/` |
| `uv run scripts/add_book.py --refresh-chapters` | Re-read chapter lists (keeps your notes) |
| `uv run scripts/add_book.py --remove <slug>` | Move a book to `archive/` |
| `uv run scripts/add_book.py --refresh-keywords` | Fill in keywords for papers that have none |
| `uv run scripts/add_book.py --offline` | Don't look books up on Open Library |
| `uv run scripts/ocr_pdf.py books/<slug>.pdf` | Add an OCR text layer to a scan |
| `uv run scripts/add_bookmarks.py --dry-run` / no flag | Preview / add bookmarks to books without any |
| `uv run scripts/reader.py <word or phrase>` | Look up a word in the terminal |
| `uv run scripts/reader.py --setup` | Download the PDF viewer and dictionary |
| `uv run scripts/book_search.py <term>` | Search all books for a term |
| `uv run scripts/library_page.py` | Write the static `library.html` |
| `uv run scripts/backup.py` | Back up the library to GitHub (like ☁ Back up) |
| `uv run scripts/build_package.py` | Build the ready-to-use package: `dist/myLibrary-<version>-win64.zip` |
| `uv run <library>/examples/<book>/chNN_<topic>.py` | Run a chapter script |
| `uv sync` | Create or update the Python environment (`--group optics` adds the optics packages) |
| `uv add <package>` | Add a Python package |
| `uv run pytest` | Run the tests |
| `uv run ruff check . ; uv run ruff format .` | Lint and format the code |

Your library's `catalog.csv` also opens in Excel, or search it from the terminal:
`Select-String -Path library/catalog.csv -Pattern aberration`.

## 11. Troubleshooting and FAQ

**Something new doesn't show up after an update.** The server may still be running old code:
close its minimized window and start it again. Changes to the popup only need a reload of the
book tab (F5).

**Double-clicking does nothing / books open without the popup.** The viewer and dictionary may
still be downloading on first start (see the server window), or the book was opened as a plain
PDF from somewhere else. Open it from the library page.

**"Port 8765 is used by another program".** Something else uses that port. Start with
`uv run scripts/library_server.py --port 8766`.

**Continue or Read opens the wrong page or chapter.** The chapter start pages are found once and
cached. Delete the book's entry from the library's `.cache/chapter_pages.json` (or the whole file) and restart
the server to find them again; if the chapter *list* itself is wrong, run
`uv run scripts/add_book.py --refresh-chapters`.

**The selection in a scanned book catches the wrong letters.** Expected with OCR text; edit the
word at the top of the popup and press Enter ([section 5](#ways-to-look-something-up)).

**The dictionary gives the everyday meaning, not my subject's.** Add the term to your glossary
(**＋ 加入术语表**, Add to glossary), with the Chinese term you found in your books.

**`uv sync` removed the optics packages.** They're an optional group: `uv sync --group optics`.

**在我的书中 (In my books) says the index is still being built.** The server indexes new or changed books in
the background when it starts; try again in a few seconds.

**What does "ticked" mean?** A chapter you've marked as finished with its checkbox; see
[section 3](#3-the-library-page).

**Is anything sent over the internet?** Only in three cases:
- when you click Wikipedia, 维基百科 (Chinese Wikipedia), 百度百科 (Baidu Baike) or 翻译
  (Translate), which sends the selected text to that site;
- when adding a book, for the Open Library lookup (`--offline` skips it);
- for the one-time download of the viewer and dictionary.

Word lookups, book search and everything else run on your computer.

**Other languages?** The dictionary is English → Chinese (ECDICT). Glossaries work for any
subject, but their meanings are written in Chinese (the `zh` column).

## 12. Built with

- **[PDF.js](https://mozilla.github.io/pdf.js/)** (Mozilla): the PDF viewer
- **[ECDICT](https://github.com/skywind3000/ECDICT)**: the offline English–Chinese dictionary
- **numpy / scipy / sympy / matplotlib** (`science` group): numerics, symbolic math and plots in
  chapter scripts
- **pypdf / pypdfium2 / rapidocr / reportlab**: reading PDFs, OCR for scans, writing text layers
- **optiland / rayoptics** (optional `optics` group): lens design for the optics example

All third-party components and their licenses: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## 13. License, contributing and the ready-to-use package

**License: [PolyForm Noncommercial 1.0.0](LICENSE).** In plain words (the license text is what
counts):

- **You may** read, use, change and share myLibrary for any **non-commercial** purpose:
  personal study, hobby projects, research, teaching, or use by schools, charities and public
  institutions.
- **You may not** use it for commercial purposes: for example, selling it or a modified
  version, or using it in a paid product or service. Commercial use needs written permission
  from the author.
- If you share it, include the [LICENSE](LICENSE) file (with its "Required Notice" line).

**Ready-to-use package (9.9 RMB).** Setting myLibrary up yourself, as described above, is free
for non-commercial use. The package saves you the setup: unzip it and double-click; Python, the
PDF viewer and the dictionary are included (it works offline from the first start), and there's
no command line. It has everything for reading and studying (adding books, OCR, lookup,
glossaries, shelves, notes, progress) but not the Python chapter scripts. Where to get it:
coming soon.

Building it (Windows): `uv run scripts/build_package.py` makes
`dist/myLibrary-<version>-win64.zip` (~170 MB) from `package/` (launcher, guide, licenses) and
this repository; the package marks itself with a `package.toml`.

**Contributing.** Everyone is welcome to help: report bugs, suggest ideas, fix things, add
features or glossaries for new subjects. Fork the repository, make your change on a branch, and
open a pull request; [CONTRIBUTING.md](CONTRIBUTING.md) explains the steps, the project rules,
and the contributor terms (contributions are licensed like the project, plus a license that
lets the author include them in the paid package).
