# 多个书库 (Several libraries), 测试/示例书库 (Test & Demo) and moving a library

myLibrary works on one **library** at a time: a folder with your PDFs, notes, marks, vocabulary,
reading history and catalog. You can have as many libraries as you like, anywhere on the
computer, and copy or move a whole library to another computer.

## 1. 选择书库模式 (Choose a Library Mode)

Start with **`Start myLibrary Dev.cmd`** (or `uv run scripts/launch_library.py`):

```
选择书库模式 (Choose a Library Mode)
  1. 私人书库 (Personal Libraries)
  2. 测试/示例书库 (Test & Demo Library)
```

- **私人书库 (Personal Libraries)**: your own libraries. Then choose one, or create or add one.
- **测试/示例书库 (Test & Demo Library)**: a complete example library to try things out, with
  a yellow banner on its page. Nothing you do there touches your own libraries.

Shortcuts: `launch_library.py --test`, `launch_library.py --personal "<label>"`. The usual
commands still work as before: `uv run scripts/library_server.py` opens your default library,
and `library_server.py --library <folder>` opens any library, even one not on the list.

## 2. 私人书库 (Personal Libraries)

In the launcher's second level, or on the library page with **📚 切换书库 (Switch library)**:

| Action | What it does |
|---|---|
| **打开 (Open)** | Opens the library in its own server and browser tab (a running one is reused). |
| **新建书库 (Create new)** | Makes a new, empty library in a new or empty folder, with its own library id. |
| **添加已有书库 (Add existing)** | Checks the folder first, **only reading it** (see 4), shows what it found, and adds it after you confirm. |
| **重命名 (Rename)** | Changes the label on the list only; the folder keeps its name. |
| **移出列表 (Remove from list)** | Takes it off the list; the folder and everything in it stay as they are. |
| **重新定位 (Locate moved folder)** | A library on the list was moved: point its entry at the new folder (it must be the same library: the same library id). |
| **← 书库模式 (Library modes)** | Back to the first level (Personal or Test & Demo). |

- The library named in ⚙ Settings (Library folder) is the **默认 (default)** library: always
  on the list, opened by a plain `library_server.py`, and never changed by anything here.
- Labels may repeat ("Physics" twice is fine); each entry is still its own library.
- A library whose drive isn't plugged in shows **找不到 (not found)**; nothing is removed.
- Each library gets its own server and port (default 8765, Test & Demo 8766, the others from
  8767). Switching starts or finds the other library's server; the current one keeps running,
  so saves, marks and background jobs in progress are never cut off. Quit each from its page.
- A library is only ever shown by one server: a running server holds its library's lock
  (`.myLibrary/server.lock`, released by the system when it ends, however it ends), so a
  second start, even at the same moment from another window, opens the first one instead.

The list is kept on this computer only: `.myLibrary-local/libraries.json` next to the settings
file (`local.toml` in a source checkout, `%APPDATA%/myLibrary/` in the package). It is never put
in a library or in git, and each computer has its own.

## 3. 复制或移动书库 (Copying or moving a library to another computer)

1. Close myLibrary on computer A (Quit).
2. Copy the **whole library folder** (with `books/`, `papers/`, `theses/`, `notes/`,
   `catalog.csv`, `library.toml`, …) to computer B, anywhere: another drive letter, user
   name or folder name, spaces and Chinese in the path are all fine.
3. On B: 私人书库 (Personal Libraries) → **添加已有书库 (Add existing)** → choose the folder.

Everything in a library refers to its own files *relative to the library folder*, and every
document keeps its permanent id, so nothing needs editing or importing again.

**Travels with the folder (portable):** all PDFs and the marks saved in them, document ids,
catalog details, shelves and subjects, chapter notes, paper notes, topic notes, vocabulary,
review progress, reading progress ("Last read", ticked chapters), reading log, glossaries,
chapter scripts and `code/`, the library's name and library id.

**Stays on each computer (not portable):** the list of libraries; settings (editor, OpenAlex
key, **backup folder**); the Test & Demo working copy; caches (`.cache/`: search index,
chapter pages, OCR text; rebuilt by themselves); and the browser's own storage: **unsaved
recovery drafts** and view preferences. A draft is kept only in the browser that typed it:
save your notes (or restore a draft) before copying the library. A copy on another computer
shows the saved notes, never the old computer's unsaved drafts.

**Move vs. copy.** A moved library is the same library (same library id); use 重新定位 (Locate
moved folder) if it was on the list. A copy is a separate library that starts with the same
content and the same library id; the two are never synchronised or merged, and changing one
never changes the other. Adding a copy says that another library on the list has the same id.

Drafts and backups are kept per library *and* folder (its library id plus its location), so a
copy or another library on the same port never sees another's drafts, and backups of two
libraries never mix.

## 4. What "Add existing" checks (read-only)

Nothing in the folder is written, moved or "repaired" by checking or adding it. It refuses:
a folder that isn't a library (no `library.toml` or `catalog.csv`: use Create instead), an
old-format catalog (run `uv run scripts/migrate_ids.py --library "<folder>"` first, as
before), broken document ids, the Test & Demo library, a folder already on the list. It warns,
and still lets you add it, about: PDFs listed but missing (an incomplete copy: the notes are
kept, copy the PDFs in later), notes folders missing, catalog paths that are full paths of
some computer or lead out of the library, links or junctions pointing out of it, a migration or
rename journal, and a library without a library id (made before library ids; it works the
same, and is told apart by its folder). Normal use afterwards goes through the usual safe
writing (`safe_io`).

## 5. 备份 (Backups) after moving

The 💾 backup folder is a setting of each computer, not of a library, so a copied library never
writes to the old computer's backup folder; choose one in ⚙ Settings on the new computer (the
app just says "backup folder not found" until then). Several libraries can share one backup
folder: their zips are named `<library name> [<key>] <date>.zip` and their PDFs go into
`PDFs/<library name> [<key>]/`, so one library never counts, replaces or deletes another's,
even with the same name. Libraries without a library id keep the old names. Existing backups
are never renamed or deleted by this. The Test & Demo library is never backed up (☁ and 💾 are
hidden there); it can be reset instead.

## 6. 测试/示例书库 (The Test & Demo library)

| | Where | Written by |
|---|---|---|
| **Canonical** | `test_library/` in the repository, in git (PDFs included) | Only `tests/make_test_library.py`, on purpose |
| **Working copy** (Test & Demo mode) | `.myLibrary-local/test-library-working/` on each computer | You, while trying things; kept across restarts |
| **Automated tests** | Each test's own temporary folder | The tests |

- The working copy is made from `test_library/` the first time you open Test & Demo mode.
- **重置 (Reset)**: launcher → 2 → `reset`, then type `RESET`. Refused while the Test & Demo
  library is open; the replaced copy is kept once in `test-library-previous/`. It can never
  touch any other folder.
- `test_library/` itself is never opened: the server and every script refuse it.
- What's in it, where it comes from and its licences, and how to add a fixture:
  [test_library/README.md](../test_library/README.md).

## 7. 两台电脑开发 (Developing on two computers)

- GitHub carries the **code and the canonical `test_library/`**, identical on both computers.
- Each computer keeps its own private libraries and their locations, its list of libraries
  (`.myLibrary-local/`), its `local.toml`, its Test & Demo working copy, its caches and its
  browser drafts. None of these is in git, and nothing here commits or pushes them.
- Never assume the two computers' private libraries are the same. To carry one over, copy the
  folder (section 3) or use 💾 backups.
- The `library/` folder in this repository is a frozen public showcase of the author's
  library, kept as it is in git: the app refuses to open or write it (like `test_library/`).
  The author's own library lives outside the repository. To explore the showcase, copy the
  folder elsewhere and add the copy as a personal library.
