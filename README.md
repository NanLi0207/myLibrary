# myLibrary

**用你自己的 PDF 学习：阅读、查词、做笔记、记录进度，全部在你自己的电脑上。**
**Study from your own PDFs: read, look up words, take notes and track progress, all on your own computer.**

myLibrary 是一个本地运行的学习工具，适用于任何学科的书籍、论文和学位论文。
myLibrary is a study tool that runs locally, for books, papers and theses in any subject.

- **阅读 Read**：在浏览器里的阅读器（PDF.js）中读书，自动记住读到哪一页。
  Read in a browser-based reader (PDF.js) that remembers where you stopped.
- **查词 Look up**：双击单词或拖选短语，先看学科术语表的释义，再看离线英汉词典。
  Double-click a word or drag over a phrase: your subject glossaries first, then an offline
  English–Chinese dictionary.
- **搜索 Search**：一次搜索你所有的书，看看不同作者如何解释同一个概念。
  Search all your books at once to see how different authors explain the same idea.
- **笔记 Notes**：每章一个 Markdown 笔记，可以在 PDF 旁边直接编辑和预览。
  One Markdown note per chapter, edited and previewed right beside the PDF.
- **进度 Progress**：章节勾选、阅读记录、生词复习卡片，以及（可选）检验例题的 Python 脚本。
  Chapter ticks, a reading log, vocabulary review cards and (optionally) Python scripts for
  checking worked examples.

**不包含任何书籍**：请使用你自己的 PDF。**No books are included**: bring your own PDFs.

**非商业用途免费**（个人学习、学校、研究；见[许可](#18-许可贡献与安装包--license-contributing-and-the-package)）。
免安装的**现成安装包**（不需要 Python 或命令行）即将推出，价格 **9.9 元人民币**。欢迎贡献：见
[CONTRIBUTING.md](CONTRIBUTING.md)。
**Free for non-commercial use** (personal study, schools, research; see
[License](#18-许可贡献与安装包--license-contributing-and-the-package)). A **ready-to-use
package** (no Python or command line needed) is coming soon, for **9.9 RMB**. Contributions are
welcome: see [CONTRIBUTING.md](CONTRIBUTING.md).

> 作者用它学习光学设计。作者自己的书库放在本仓库的 `library/` 中作为真实示例：书架、笔记、约 300
> 条的光学术语表、章节脚本和一个小型光学代码模块（书本身不包含在内）。你自己的书库放在单独的文件夹里，
> 可以用于任何学科（见[用于你自己的学科](#16-用于你自己的学科--use-it-for-your-own-subject)）。
> The author uses it to learn optical design. Their library is included in `library/` as a
> worked example: shelves, notes, an optics glossary of about 300 terms, chapter scripts and a
> small optics code module (the books themselves are not included). Your own library lives in
> its own folder, for any subject (see
> [Use it for your own subject](#16-用于你自己的学科--use-it-for-your-own-subject)).

**关于本文档 / About this guide.** 中文在前，英文紧随其后。按钮名称按界面原样写出（界面上的中文按钮都带英文）。
Chinese comes first, English right after it. Button names are written exactly as they appear
in the app (every Chinese label in the app has its English next to it).

---

## 目录 / Contents

1. [安装与首次启动 / Installation and first launch](#1-安装与首次启动--installation-and-first-launch)
2. [一次典型的学习 / A typical study session](#2-一次典型的学习--a-typical-study-session)
3. [书库页面 / The library page](#3-书库页面--the-library-page)
4. [添加和管理文档 / Adding and managing documents](#4-添加和管理文档--adding-and-managing-documents)
5. [阅读器 / The reader](#5-阅读器--the-reader)
6. [查词与学术阅读 / Looking up words and terms](#6-查词与学术阅读--looking-up-words-and-terms)
7. [术语表 / Glossaries](#7-术语表--glossaries)
8. [搜索与发现 / Search and discovery](#8-搜索与发现--search-and-discovery)
9. [笔记 / Notes](#9-笔记--notes)
10. [学习与进度 / Learning and progress](#10-学习与进度--learning-and-progress)
11. [数据存储与安全 / Your data and keeping it safe](#11-数据存储与安全--your-data-and-keeping-it-safe)
12. [设置 / Settings](#12-设置--settings)
13. [命令参考 / Command reference](#13-命令参考--command-reference)
14. [常见问题 / Troubleshooting and FAQ](#14-常见问题--troubleshooting-and-faq)
15. [功能状态：已实现、已验证、计划中 / Feature status: implemented, verified, planned](#15-功能状态已实现已验证计划中--feature-status-implemented-verified-planned)
16. [用于你自己的学科 / Use it for your own subject](#16-用于你自己的学科--use-it-for-your-own-subject)
17. [开发与测试 / Development and testing](#17-开发与测试--development-and-testing)
18. [许可、贡献与安装包 / License, contributing and the package](#18-许可贡献与安装包--license-contributing-and-the-package)
19. [使用的组件 / Built with](#19-使用的组件--built-with)

---

## 1. 安装与首次启动 / Installation and first launch

### 1.1 准备 / Prerequisites

| 需要 Needed | 用途 What for |
|---|---|
| [uv](https://docs.astral.sh/uv/) | 安装 Python 和所需的包。Installs Python and the packages. |
| [Git](https://git-scm.com/) | 下载本工具（也可以下载 zip）。Downloads the tool (or download the zip). |
| 现代浏览器 A modern browser | 书库页面和阅读器（作者用 Microsoft Edge）。The library page and the reader (the author uses Microsoft Edge). |
| 可选 Optional: [VS Code](https://code.visualstudio.com/) + Python 扩展 extension | 在外部编辑器中写笔记、运行章节脚本。Notes in an outside editor, and chapter scripts. |

本工具在 **Windows** 上开发和测试（CI 也运行在 Windows 上）。桌面快捷方式和文件夹选择对话框只在 Windows 上有；在其他系统上请从终端启动服务器（未测试）。
The tool is developed and tested on **Windows** (CI runs on Windows too). The desktop shortcut
and the folder picker are Windows-only; on other systems, start the server from a terminal
(not tested).

### 1.2 安装 / Install with uv

```powershell
# 工具放在你的用户文件夹，例如 C:\Users\<you>\myLibrary
# The tool goes into your home folder, e.g. C:\Users\<you>\myLibrary
git clone https://github.com/NanLi0207/myLibrary.git "$HOME\myLibrary"
cd "$HOME\myLibrary"
uv sync                                # 安装 Python 和包 (.venv) / install Python and the packages
uv run scripts/make_shortcut.py        # Windows：桌面和开始菜单快捷方式 / Desktop + Start menu shortcut
```

这个文件夹只放**工具**。你的书和笔记放在单独的**书库**文件夹里（首次启动时创建），所以用 `git pull` 更新工具永远不会碰到它们。
This folder holds only **the tool**. Your books and notes go into a separate **library** folder
(created on first start), so updating the tool with `git pull` never touches them.

> 如果刚用 winget 安装了 uv，终端找不到 `uv`：关闭并重新打开终端（或 VS Code）。
> If you just installed uv with winget and the terminal can't find `uv`: close and reopen the
> terminal (or VS Code).

### 1.3 Windows 快捷方式 / Windows shortcuts

`uv run scripts/make_shortcut.py` 在**桌面**和**开始菜单**创建名为 **myLibrary** 的快捷方式。双击它（或按 Win 键输入 "myLibrary"）即可启动。服务器在一个**最小化的窗口**中运行。
`uv run scripts/make_shortcut.py` creates a **myLibrary** shortcut on the **Desktop** and in the
**Start menu**. Double-click it (or press Win and type "myLibrary") to start. The server runs
in a **minimized window**.

### 1.4 启动和停止 / Starting and stopping

| 操作 Action | 怎么做 How |
|---|---|
| 启动 Start | 双击 **myLibrary** 快捷方式，或运行 `uv run scripts/library_server.py`。书库页面会在浏览器中打开：`http://127.0.0.1:8765`。Double-click the **myLibrary** shortcut, or run `uv run scripts/library_server.py`. The library page opens in your browser at `http://127.0.0.1:8765`. |
| 已经在运行时再次启动 Start again while running | 只会重新打开页面（该书库已在其他端口运行时也一样）。如果另一个 myLibrary 正在用**另一个**书库运行，会提示你先退出它或换端口。It just opens the page again (also when that library is already open on another port). If another myLibrary is running with a **different** library, it tells you to quit that one or use another port. |
| 多个书库 Several libraries | 在源码目录中双击 **Start myLibrary Dev.cmd**，先选**书库模式**：私人书库 (Personal Libraries) 或 测试/示例书库 (Test & Demo)；书库页面上的 **📚 切换书库 (Switch library)** 也可以切换。见 [docs/LIBRARIES.md](docs/LIBRARIES.md)（也讲如何把整个书库复制到另一台电脑）。In a source checkout, double-click **Start myLibrary Dev.cmd** and choose a **Library Mode** first; **📚 Switch library** on the library page switches too. See [docs/LIBRARIES.md](docs/LIBRARIES.md) (also: copying a whole library to another computer). |
| 停止 Stop | 书库页面上的 **Quit**；或关闭最小化的服务器窗口；在终端中按 Ctrl+C。你在每本书中的位置已经保存。**Quit** on the library page; or close the minimized server window; or Ctrl+C in the terminal. Your place in each book is already saved. |
| 换端口 Another port | `uv run scripts/library_server.py --port 8766` |

服务器**只监听你自己的电脑**（127.0.0.1），其他电脑无法访问。
The server **listens only on your own computer** (127.0.0.1); other computers can't reach it.

### 1.5 首次启动 / The first start

1. **创建书库 Creates a library**：没有设置书库时，首次启动会创建 `文档\myLibrary Library`（`Documents\myLibrary Library`）并记住它（写入工具文件夹中的 `local.toml`）。
   With no library set, the first start creates `Documents\myLibrary Library` and remembers it
   (in `local.toml` in the tool's folder).
2. **下载阅读器组件 Downloads the reading view**：PDF 阅读器（PDF.js）、离线词典（ECDICT）和笔记预览库（markdown-it），共约 72 MB，只下载一次，固定版本并校验 checksum。下载完成前，书以普通 PDF 打开，没有查词和笔记面板。
   The PDF viewer (PDF.js), the offline dictionary (ECDICT) and the notes' preview library
   (markdown-it), about 72 MB, downloaded once, pinned and checksum-verified. Until they're
   ready, books open as plain PDFs, without lookup or the notes panel.
3. **建立搜索索引 Indexes your books** for full-text search, in the background (seconds per book).
4. **恢复中断的操作 Recovers interrupted operations**：如果上次的重命名被中断，会自动回滚。
   If a rename was interrupted last time, it's rolled back.

然后把 PDF 加进来：点击 **＋ Add**，或把 PDF 拖到页面上（见[第 4 节](#4-添加和管理文档--adding-and-managing-documents)）。
Then add your PDFs: click **＋ Add**, or drag PDFs onto the page (see
[section 4](#4-添加和管理文档--adding-and-managing-documents)).

<!-- 截图建议 / Screenshot suggestion: docs/images/library-page-first-start.png — the empty library page right after the first start, with ＋ Add highlighted. -->

### 1.6 现成安装包 / The ready-to-use package

安装包（Windows，zip）包含便携版 Python、PDF 阅读器、词典和笔记预览库，**首次启动即可离线使用**，无需命令行。
The package (Windows, zip) includes a portable Python, the PDF viewer, the dictionary and the
notes' preview library: it **works offline from the first start**, with no command line.

1. 解压到你想放的位置（例如 `D:\myLibrary`），双击 **Start myLibrary.cmd**。
   Unzip it where you want to keep it (e.g. `D:\myLibrary`) and double-click
   **Start myLibrary.cmd**.
2. 首次启动会在桌面和开始菜单创建 **myLibrary** 快捷方式，以后用它们启动。安装包不显示服务器窗口，用页面上的 **Quit** 停止。
   The first start creates **myLibrary** shortcuts on the Desktop and in the Start menu; use
   those from then on. The package shows no server window: stop it with **Quit** on the page.
3. 设置保存在 `%APPDATA%\myLibrary\settings.toml`，日志在 `%APPDATA%\myLibrary\myLibrary.log`，所以换新版本时设置保留。
   Settings are kept in `%APPDATA%\myLibrary\settings.toml` and the log in
   `%APPDATA%\myLibrary\myLibrary.log`, so a new version keeps them.

安装包关闭了 Python 功能（章节脚本），其余阅读和学习功能都有。**Show the Python features** 设置在安装包中默认关闭。
The package leaves out the Python features (chapter scripts); everything else for reading and
studying is there. The **Show the Python features** setting is off by default in the package.

### 1.7 离线使用与需要联网的功能 / Offline use and what needs the internet

首次下载完成后，阅读、查词、标注、笔记、全文搜索、生词复习和阅读记录都**完全离线**。以下功能需要联网：
After the first download, reading, lookup, marks, notes, full-text search, vocabulary review and
the reading log work **fully offline**. These need the internet:

| 功能 Feature | 联系的网站 What it contacts |
|---|---|
| 首次下载阅读器组件 First download of the reading view | PDF.js、ECDICT、markdown-it 的下载地址 Their download sites |
| 添加文档时识别信息 Identifying a document when it's added | Open Library、Crossref、DataCite、arXiv、OpenAlex（`add_book.py --offline` 跳过 Open Library 查询 / skips the Open Library lookup） |
| 学科分类 Subjects | OpenAlex（添加时和 ⟳ Refresh 时 / when adding and on ⟳ Refresh） |
| 🔎 Find online 和 ＋ Add to library | OpenAlex、Crossref、DataCite、arXiv、Open Library，以及开放获取 PDF 的网站 and the open-access PDF's site |
| 保存 OpenAlex 密钥时检查 Checking an OpenAlex key when saved | api.openalex.org |
| 弹窗中的链接 Links in the popup | Wikipedia、维基百科 (Chinese Wikipedia)、百度百科 (Baidu Baike)、Bing 翻译 (Bing Translator)：只在你点击时，并把所选文字发送给该网站 only when you click, and they send the selected text to that site |
| ☁ Back up | 你的 Git 远程仓库（如 GitHub）Your git remote (e.g. GitHub) |

离线时，添加文档仍然可以：缺少的标题、年份和作者会从 PDF 本身读取。离线时每次在线查询会先重试几秒再放弃，所以离线添加较慢。
Offline, adding documents still works: a missing title, year or author is read from the PDF
itself. Each online lookup retries for a few seconds before giving up, so adding while offline
is slower.

---

## 2. 一次典型的学习 / A typical study session

1. **打开书库**，在你正在读的书上点击 **Continue · p. N**。书会在阅读器中打开到你上次停下的那一页，这一章的笔记出现在右侧的笔记面板中。
   **Open the library** and click **Continue · p. N** on the book you're reading. It opens in
   the reader at the page where you stopped, with that chapter's notes in the notes panel on
   the right.
2. **阅读。** 双击不认识的单词，或拖选一个短语（见[第 6 节](#6-查词与学术阅读--looking-up-words-and-terms)）。用 **加入生词本** (Save word) 保存有用的单词。
   **Read.** Double-click a word you don't know, or drag over a phrase (see
   [section 6](#6-查词与学术阅读--looking-up-words-and-terms)). Keep useful words with
   **加入生词本** (Save word).
3. **用自己的话做笔记**，写在面板中：要点、公式、问题。停止输入 1.5 秒后自动保存。
   **Take notes in your own words** in the panel: key ideas, equations, questions. They're saved
   1.5 seconds after you stop typing.
4. **用 Python 检验**（可选）：在章节上点击 **Script**，重新计算例题（见[第 10.4 节](#104-章节脚本--chapter-scripts)）。
   **Check it in Python** (optional): click **Script** on the chapter and recompute a worked
   example (see [section 10.4](#104-章节脚本--chapter-scripts)).
5. **随时停下。** 位置会自动保存，直接关闭标签页即可。
   **Stop whenever you like.** Your place is saved automatically; just close the tab.
6. **读完一章后**，在书库页面上勾选它（Chapters → 复选框 checkbox）。
   **When you've finished a chapter**, tick it on the library page (Chapters → checkbox).

---

## 3. 书库页面 / The library page

书库页面是 myLibrary 的主页：每个文档一张卡片（或列表中的一行），顶部是工具按钮。
The library page is myLibrary's home: one card (or list line) per document, with the tools at
the top.

<!-- 截图建议 / Screenshot suggestion: docs/images/library-page.png — the library page with the top bar, shelf bar and a few cards. -->

### 3.1 顶部按钮 / The top bar

| 按钮 Button | 作用 What it does |
|---|---|
| **＋ Add** | 选择 PDF（书、论文或学位论文）添加到书库。也可以直接把 PDF 拖到页面上。Choose PDFs (books, papers or theses) to add. You can also drag PDFs onto the page. |
| **⟳ Refresh** | 登记你手动复制到 `books/`、`papers/` 或 `theses/` 中的 PDF；为没有学科的条目查找学科；检查重复（见 [4.8](#48-刷新--refresh)）。Registers PDFs you copied into `books/`, `papers/` or `theses/` yourself; looks up subjects for items without one; checks for repeats (see [4.8](#48-刷新--refresh)). |
| **🔎 Find online** | 在网上查找书、论文和学位论文（见 [8.3](#83-在线查找--find-online)）。Searches the internet for books, papers and theses (see [8.3](#83-在线查找--find-online)). |
| **📇 Review words** | 生词复习卡片；数字表示今天要复习的个数（见 [10.2](#102-复习生词--review-words)）。Vocabulary review cards; the number shows how many are due (see [10.2](#102-复习生词--review-words)). |
| **☁ Back up** | 把书库提交并推送到 Git 远程仓库。只在书库位于有上游分支的 Git 仓库中时显示（见 [11.4](#114-备份与恢复--backup-and-restore)）。Commits and pushes the library to its git remote. Shown only when the library is in a git repository with an upstream (see [11.4](#114-备份与恢复--backup-and-restore)). |
| **💾 Back up** | 把书库备份成带日期的 zip，放到你选择的文件夹。没有 Git 上游、或已设置备份文件夹时显示。Saves a dated zip of the library to a folder you choose. Shown without a git upstream, or when a backup folder is set. |
| **⚙ Settings** | 设置（见[第 12 节](#12-设置--settings)）。Settings (see [section 12](#12-设置--settings)). |
| **Quit** | 停止 myLibrary（先询问）。正在运行的任务会先到达安全点再停止。Stops myLibrary (asks first). Running jobs reach a safe point before it stops. |

标题下面的一行显示统计（书、论文、学位论文、页数、已读章节），以及阅读记录：**📈 🔥 3-day streak · 2 h 10 min this week ›**。点击它打开阅读记录（见 [10.1](#101-阅读记录--reading-log)）。
The line under the title shows totals (books, papers, theses, pages, chapters read) and your
reading log: **📈 🔥 3-day streak · 2 h 10 min this week ›**. Click it for the reading log (see
[10.1](#101-阅读记录--reading-log)).

### 3.2 搜索、筛选和排序 / Search, filter and sort

| 控件 Control | 作用 What it does |
|---|---|
| 搜索框 Search box | 每个词都必须出现在以下任一项中：标题、作者、年份、出版社、期刊、大学、导师、ISBN、DOI、关键词、学科、书架、章节标题。找不到时提供 **🔎 Search online**，用同样的词在网上搜索。Every word must appear in the title, authors, year, publisher, journal, university, supervisors, ISBN, DOI, keywords, subject, shelf or chapter titles. When nothing matches, **🔎 Search online** searches the internet for the same words. |
| 类型菜单 Kind menu | **All / Books / Papers / Theses**，带数量。With counts. |
| 学科领域菜单 Field menu | 一次只显示一个领域（来自 OpenAlex）；没有任何条目有领域时隐藏。Shows one field at a time (from OpenAlex); hidden when no item has one. |
| 书架栏 Shelf bar | **All** 和当前显示条目所在的每个书架，带数量；点击只看这个书架。**All** and each shelf of the items shown, with counts; click one to see only that shelf. |
| 排序 Sort | **Sort: title / author / newest / progress / recently added / recently read** |
| **▦ Cards / ☰ List** | 卡片或紧凑列表。超过 24 个条目时默认是列表。Cards or a compact list. More than 24 items starts as a list. |

类型、领域、书架、排序和视图都会记在这个浏览器里。
Kind, field, shelf, sort and view are remembered in this browser.

**列表视图 / List view.** 每行显示类型、标题、作者、年份、ISBN 或 DOI、进度、上次阅读和 **Continue · p. N**（或 **Start reading**）。点击某一行（或在行上按 Enter / 空格）展开它的完整卡片，再点一次收起。**▾ Unfold all** 展开所有显示的行，**▴ Fold all** 全部收起。点击列名（标题、作者、年份、进度、上次阅读）排序。
Each line shows the kind, title, authors, year, ISBN or DOI, progress, last read and
**Continue · p. N** (or **Start reading**). Click a line (or press Enter or Space on it) to
unfold its full card; click again to fold it. **▾ Unfold all** opens every line shown,
**▴ Fold all** closes them. The column names (title, author, year, progress, last read) sort
the list.

### 3.3 卡片上的按钮 / On each card

| 按钮或内容 Button or item | 作用 What it does |
|---|---|
| **Continue · p. N** | 在上次读到的页面打开，这一章的笔记在笔记面板中（如果有章节脚本，也在编辑器中打开）。Opens at the page you last read, with that chapter's notes in the notes panel (and its script in your editor, if there is one). |
| **Start reading** / **Continue** / **Read again** / **Read** | 还没有保存位置时：打开第一个未勾选的章节（全部勾选时是 Read again；没有章节时是 Read）。No page saved yet: opens the first unticked chapter (Read again when all are ticked; Read without chapters). |
| **PDF** | 在阅读器中从第一页打开。文件不在时显示 **PDF missing**，笔记和脚本仍然可以打开。Opens in the reader at page 1. If the file is gone, it shows **PDF missing**; notes and scripts still open. |
| **Notes** | 在外部编辑器中打开笔记的 `README.md`（论文是 `notes.md`）（见[第 12 节](#12-设置--settings)）。Opens the notes' `README.md` (`notes.md` for a paper) in your outside editor (see [section 12](#12-设置--settings)). |
| **Chapters** | 显示章节列表：每章有复选框（勾选 = 读完）、**Read**（打开这一章）和 **Script**（Python 脚本，仅在开启 Python 功能时）。Shows the chapter list: a checkbox (tick = finished), **Read** (opens that chapter) and **Script** (its Python script, only with the Python features on). |
| **Mark as read** / **✓ Read** | 仅论文（代替 Chapters）：标记已读或未读。Papers only (instead of Chapters): mark it read or unread. |
| **Shelves** | 编辑这个条目所在的书架，用 `;` 分隔（最多 12 个）。Edit the item's shelves, separated by `;` (at most 12). |
| **OCR (~N min)** | 仅扫描版：在后台添加文字层（见 [4.6](#46-扫描版与-ocr--scanned-documents-and-ocr)）。Scans only: adds a text layer in the background (see [4.6](#46-扫描版与-ocr--scanned-documents-and-ocr)). |
| **Cite ▾** | 引用格式菜单，每种都有预览，点击即复制：APA、IEEE、GB/T 7714（中国国家标准 Chinese national standard）、BibTeX (LaTeX)、RIS (EndNote, Zotero, Mendeley)。A menu of citation formats, each with a preview; click one to copy it. |
| **DOI 10.…** / **ISBN** / **Open Library** | 出版社或大学的页面链接。Links to the work's page. |
| 标签 Tags | 类型（Book / Paper / 学位类型 degree），论文和学位论文的关键词，绿色的书架标签，学科（例如 "工程 Engineering › Railway Engineering and Dynamics"）。The kind (Book / Paper / degree), keywords for papers and theses, green shelf tags, and the subject. |
| 进度 Progress | 进度条和 "0/8 chapters · 3%"；"Last read: page 41 · Ch 2 · date" 或 "Next: <chapter>"。The bar and "0/8 chapters · 3%"; "Last read: page 41 · Ch 2 · date" or "Next: <chapter>". |

书库页面**没有**删除、重命名或修改书目信息的按钮。移除文档用命令行（见 [4.9](#49-移除文档--removing-a-document)）。
The library page has **no** delete, rename or edit-details buttons. Removing a document is done
from the terminal (see [4.9](#49-移除文档--removing-a-document)).

### 3.4 进度与勾选章节 / Progress and ticking chapters

**勾选**表示你把这一章标记为**读完**。勾选会把 `- [x]` 写入这本书的 `notes/<book>/README.md`；你也可以手动编辑这个清单。没有任何操作会自动勾选章节：浏览不等于读完。
A **ticked** chapter is one you've marked as **finished**. Ticking writes `- [x]` into the
book's `notes/<book>/README.md`; you can also edit that checklist by hand. Nothing ticks a
chapter automatically: skimming isn't finishing.

**进度**取两者中较大的：已勾选章节的比例，或上次阅读的页码占全书页数的比例。**Sort: progress** 把进度最多的排在前面，相同时最近读的在前。
**Progress** is whichever is further: the share of chapters ticked, or the last page read out
of the book's pages. **Sort: progress** puts the furthest-along first, then the most recently
read.

### 3.5 学科与书架 / Subjects and shelves

**书架**按主题分组，一个条目可以在多个书架上。书架保存在 `catalog.csv` 的 `shelves` 列。
**Shelves** group documents by subject; an item can be on several. They're stored in the
`shelves` column of `catalog.csv`.

**每个条目都会得到一个学科**，来自 [OpenAlex](https://openalex.org) 对约 2.5 亿作品的分类（26 个领域，约 4,500 个主题，基于 Scopus 学科分类）：论文和学位论文按 DOI，书按标题和作者。
**Every item gets a subject** from [OpenAlex](https://openalex.org)'s classification of some
250 million works (26 fields, about 4,500 topics, based on the Scopus subject areas): a paper or
thesis by its DOI, a book by its title and author.

新条目如何放上书架（从不修改你自己放好的书架，也不凭弱证据猜测）：
How a new item is shelved (never changing shelves you set yourself, never guessing on weak
evidence):

1. OpenAlex 对主题有把握（分数 ≥ 0.5）：**这个主题成为书架**，没有的话就新建。
   OpenAlex is sure of the topic (score ≥ 0.5): **the topic becomes a shelf**, a new one if
   needed.
2. 你自己的书架：书架名出现在条目信息中（标题、关键词、学科、期刊），或条目与这个书架的条目很相似，或它使用了某个学科术语表中的专业术语；总是一起使用的书架会一起加上。
   Your own shelves: the shelf's name is in the item's details (title, keywords, subjects,
   journal), or the item closely resembles that shelf's items, or it uses the specialist terms
   of that shelf's glossary; shelves you always use together are added together.
3. 把握较小的主题（≥ 0.3），然后是最相似的书架。OpenAlex 没有记录的条目（报告、小出版社的书）取相似作品中最多的主题（如果大多数一致）。
   A less sure topic (≥ 0.3), then the clearly most similar shelf. An item OpenAlex has no
   record of (a report, a small publisher's book) gets the topic most similar works are about,
   if most of them agree.
4. 都不满足：保持不在任何书架上。
   None of these: it stays unshelved.

🕘 History 会说明条目被放到了哪里；卡片上的 **Shelves** 可以修改。在 `library.toml` 中给书架起中文名（附英文）：
The 🕘 History says where an item went; **Shelves** on its card changes it. Give a shelf a
label (Chinese with its English) in `library.toml`:

```toml
[shelves]
"Advanced optical system design" = "先进光学系统设计 Advanced optical system design"
"Railway Engineering and Dynamics" = "铁路工程与动力学 Railway Engineering and Dynamics"
```

条目的书架、学科和领域还决定查词弹窗中哪个术语表排在前面（见[第 7 节](#7-术语表--glossaries)）。
An item's shelves, subject and field also decide which glossary comes first in the lookup
popup (see [section 7](#7-术语表--glossaries)).

从终端查看 / From the terminal:

```powershell
uv run scripts/subjects.py           # 每个条目的学科 / each item's subject
uv run scripts/subjects.py --apply   # 记录学科并上架（同 ⟳ Refresh）/ record and shelve (as ⟳ Refresh does)
uv run scripts/shelves.py            # 建议的书架与你的选择对比 / suggestions next to your own choice
uv run scripts/shelves.py --apply    # 给不在任何书架上的条目上架 / shelve the items on no shelf
```

---

## 4. 添加和管理文档 / Adding and managing documents

### 4.1 名称与身份 / Names and identity

每个文档有一个**名称**（slug）：`<第一作者姓>-<年份>-<短标题>`，小写，例如 `shannon-1997-art-science-optical-design`。同一个名称用于 PDF、笔记文件夹和脚本文件夹。文档始终是 PDF。
Every document has a **name** (slug): `<first-author-surname>-<year>-<short-title>`, lowercase,
e.g. `shannon-1997-art-science-optical-design`. The same name is used for the PDF, its notes
folder and its scripts folder. Documents are always PDFs.

每个文档还有一个**永久 id**（UUID，`catalog.csv` 的第一列），添加时给定，永不改变。阅读记录、搜索、书库页面和阅读器都用这个 id。所以文档改名或修正信息后仍是同一个文档。`http://127.0.0.1:8765/read/<id>?page=12` 总能打开它（任何端口都可以）。
Every document also has a **permanent id** (a UUID, `catalog.csv`'s first column), given once
when it's added and never changed. The reading log, search, library page and reader all use
it, so a document stays the same document when it's renamed or its details are corrected.
`http://127.0.0.1:8765/read/<id>?page=12` always opens it (on whatever port the server uses).

### 4.2 从书库页面添加 / Adding from the library page

1. 点击 **＋ Add** 选择一个或多个 PDF，或从文件资源管理器**把 PDF 拖到页面上**（"Drop PDFs here to add them"）。其他文件会被跳过。
   Click **＋ Add** and choose one or more PDFs, or **drag PDFs from File Explorer onto the
   page** ("Drop PDFs here to add them"). Other files are skipped.
2. 每个 PDF 被复制到书库中，在后台识别、命名和登记；面板显示进度。
   Each PDF is copied into the library and identified, named and registered in the background;
   a panel shows the progress.
3. 完成后，消息收进 **🕘 History**（点击打开或关闭；出错会注明；**Clear** 清空）。页面会自动刷新。
   When they're done, the messages fold into **🕘 History** (click to open or close it; it
   says if anything went wrong; **Clear** empties it). The page reloads by itself.

**什么都不用输入。** 在线找不到的信息从 PDF 本身读取：首页上的大号标题、印刷的年份或 PDF 的创建日期、PDF 信息中的作者，都没有则为 "Unknown"。加密但可读的出版社 PDF 也可以添加。损坏的 PDF（例如下载中断）不会被添加，原样保留并给出提示。
**Nothing has to be typed in.** Whatever can't be found online comes from the PDF itself: the
large title on its first pages, a printed year or the PDF's creation date, the author in its
details, else "Unknown". Copy-protected (encrypted but readable) publisher PDFs work too. A
damaged PDF (e.g. a download that stopped halfway) isn't added; it's left as it is, with a
message.

书的识别顺序：文件名或前几页中的 ISBN（在 Open Library 查询）、PDF 元数据、清理后的文件名、版权页，最后是 Open Library 标题搜索。
A book is identified from, in order: an ISBN in the file name or on the first pages (looked up
on Open Library), the PDF's metadata, the cleaned file name, the copyright line, and finally an
Open Library title search.

### 4.3 重复的文档 / Repeats

同一份作品不会被添加两次，无论从哪里进来（＋ Add、拖放、Find online、⟳ Refresh、`add_book.py`）。只有以下情况算**重复**：**相同的 DOI**、**相同的 ISBN**（书和学位论文；论文可能带有论文集的 ISBN，所以不算），或**内容完全相同的文件**。仅仅标题或名称相同不算重复。
The same work is never added twice, however it comes in (＋ Add, dragging, Find online,
⟳ Refresh, `add_book.py`). Only these count as a **repeat**: the **same DOI**, the **same ISBN**
(books and theses; a paper may carry its proceedings volume's ISBN, so it doesn't count), or an
**identical file**. The same title or name alone is not a repeat.

保留**信息更多**的那一份：先看是否有可搜索的文字（而不是纯扫描），再看信息（DOI、ISBN、期刊、关键词……），然后是书签，最后是页数。
The copy with **more information** is kept: searchable text (rather than a bare scan) first,
then more details (DOI, ISBN, journal, keywords, ...), then bookmarks, then more pages.

- 新的一份更好：它**替换书库中的 PDF**（同名），你的笔记和进度保留，旧 PDF 移到 `archive/`。
  The new copy is better: it **replaces the library's PDF** (same name), keeping your notes and
  progress; the old PDF moves to `archive/`.
- 新的一份不更好：它被移到 `archive/`。
  It isn't: it's moved to `archive/`.
- 两种情况下，书库条目缺少的信息（DOI、期刊……）都会补上，History 会说明发生了什么。
  Either way, details the library's entry lacked (a DOI, the journal, ...) are added, and the
  History says what happened.

### 4.4 从终端添加 / Adding from the terminal

把 PDF 放进书库的 `books/` 文件夹（文件名随意），然后：
Put the PDF into your library's `books/` folder with any file name, then:

```powershell
uv run scripts/add_book.py --dry-run   # 预览：建议的名称，以及每项信息的来源 / preview: the name, and where each detail came from
uv run scripts/add_book.py             # 执行 / do it
```

脚本识别文档、改名为它的名称、在 `catalog.csv` 中加一行，并根据 PDF 的目录（书签，没有则读印刷的目录页，扫描版用 OCR 读）为每章创建一个笔记模板。注意检查预览中标为来自 "filename" 的信息。信息错了可以指定：
The script identifies the document, renames it to its name, adds a row to `catalog.csv`, and
creates one notes template per chapter from the PDF's table of contents (bookmarks, else the
printed Contents pages, read with OCR for a scan). Check anything the dry run marks as coming
from the "filename". If a detail is wrong:

```powershell
uv run scripts/add_book.py "<library>/books/scan123.pdf" --author "Warren J. Smith" --year 2008 --title "Modern Optical Engineering"
```

| 选项 Option | 作用 What it does |
|---|---|
| `--refresh-chapters` | 重新读取章节列表；只替换还没写过的模板，你的笔记保留。Re-read the chapter lists; replaces only untouched templates, keeping your notes. |
| `--refresh-keywords` | 为没有关键词的论文和学位论文补充关键词。Fill in keywords for papers and theses that have none. |
| `--offline` | 不查询 Open Library。Skip the Open Library lookup. |
| `--ocr` / `--no-ocr` | 扫描版总是 / 从不添加 OCR 文字层（不问）。Always / never OCR scans (without asking). |
| `--publisher` | 指定出版社。Set the publisher. |

### 4.5 论文与学位论文 / Papers and theses

**论文**放在书库的 `papers/` 文件夹中。信息按以下顺序自动填写：
**Papers** live in the library's `papers/` folder. Their details are filled in automatically,
in this order:

1. PDF 信息或前两页中的 **DOI**（从不取参考文献中的 DOI）→ [Crossref](https://www.crossref.org/)：标题、全部作者、年份、期刊、卷、期、页码。
   Its **DOI**, from the PDF's details or its first two pages (never the reference list) →
   [Crossref](https://www.crossref.org/): title, all authors, year, journal, volume, issue,
   pages.
2. **arXiv 编号**（`arXiv:2101.01234`，或名为 `2101.01234.pdf` 的文件）→ arXiv；如果已正式发表，使用期刊版本。
   Its **arXiv number** (`arXiv:2101.01234`, or a file named `2101.01234.pdf`) → arXiv; if
   it's been published since, the journal version is used.
3. 没有编号（大多数老论文）：首页顶部的标题和作者，在 Crossref 搜索，然后在 OpenAlex 搜索。只有当结果的完整标题出现在这一页上时才采用；扫描版的首页先做 OCR。
   No number (most old papers): the title and authors at the top of page 1, searched on
   Crossref, then OpenAlex. A result is used only if its whole title is on that page; a
   scanned first page is read with OCR first.

`papers/` 中的 PDF 一定是论文；从别处添加的 PDF 被识别为论文时会移到 `papers/`。论文的笔记是一个 `notes/<name>/notes.md`（*Summary (in my own words)*、*Key results*、*Method*、*Questions*、*How it relates to my books*），README 中只有一项 *Read the paper*。关键词来自 PDF 信息、首页的 "Keywords:" 行或 OpenAlex。
A PDF in `papers/` is always a paper; one added elsewhere moves to `papers/` when it's
recognised as one. A paper has one notes file, `notes/<name>/notes.md` (*Summary (in my own
words)*, *Key results*, *Method*, *Questions*, *How it relates to my books*), and its README has
one checkbox, *Read the paper*. Keywords come from the PDF's details, its first page's
"Keywords:" line, or OpenAlex.

**学位论文**（博士、硕士、学士、Diplom）放在 `theses/` 中，通过**扉页**识别，例如 *"A thesis submitted … for the degree of Doctor of Philosophy"*、*"Dissertation zur Erlangung des Doktorgrades"*、*"Proefschrift"*、*"Thèse de doctorat"* 或 *"博士学位论文"* (doctoral dissertation)。信息来源依次为：DOI（Crossref 或 DataCite）、arXiv、OpenAlex、扉页本身（标题、作者、年份、学位、大学、导师）。扉页上印的拼写和年份与网上一致时以扉页为准。学位论文像书一样有章节笔记；**Cite** 给出学位论文格式。
**Theses** (PhD, master's, bachelor's, diploma) live in `theses/` and are recognised by their
**title page**, e.g. *"A thesis submitted … for the degree of Doctor of Philosophy"*,
*"Dissertation zur Erlangung des Doktorgrades"*, *"Proefschrift"*, *"Thèse de doctorat"* or
*"博士学位论文"* (doctoral dissertation). Details come from, in order: a DOI (Crossref or
DataCite), arXiv, OpenAlex, and the title page itself (title, author, year, degree,
university, supervisors). The title page's spelling and printed year win when they agree with
what's found online. A thesis has chapter notes like a book; **Cite** gives the thesis forms.

> 限制 Limitation：只有书、论文和学位论文三种类型；报告、标准和手册按书存储。中文文档的目录（第N章）还不能识别，中文章节标题会变成 `untitled`，OCR 文字层只支持拉丁字母。
> Only three types: book, paper and thesis; reports, standards and manuals are stored as
> books. Chinese contents pages (第N章, Chapter N) aren't recognised yet, Chinese chapter titles
> become `untitled`, and the OCR text layer is Latin-only.

### 4.6 扫描版与 OCR / Scanned documents and OCR

扫描版只有页面图像，文字不能选择或搜索。书库页面上这类文档有 **OCR (~N min)** 按钮：确认后在后台添加**隐形文字层**，显示进度条，你可以同时继续阅读。一次只运行一个 OCR。
A scan has only page images, so its text can't be selected or searched. On the library page it
has an **OCR (~N min)** button: after you confirm, it adds an **invisible text layer** in the
background with a progress bar, and you can keep reading meanwhile. One OCR runs at a time.

页面图像保持不变；**OCR 会替换书库中的 PDF**，原扫描件保存在 `archive/books/`。中断后会从停下的地方继续。OCR 文字的位置和拼写不会完全准确（见 [6.1](#61-查词方式--ways-to-look-something-up)）。
The page images stay the same; **OCR replaces the PDF in the library**, and the original scan is
kept in `archive/books/`. An interrupted run continues where it stopped. OCR text is never
perfectly placed or spelled (see [6.1](#61-查词方式--ways-to-look-something-up)).

```powershell
uv run scripts/ocr_pdf.py "<library>/books/<name>.pdf"   # 每页约 1.5 秒；先询问 / ~1.5 s per page; asks first
```

`add_book.py` 在添加扫描版时会询问是否 OCR，每次运行结束时也会询问 `books/` 中还没有文字层的扫描件（Enter = 否）。
`add_book.py` offers OCR for new scans, and at the end of every run asks about each scan in
`books/` that still has no text layer (Enter = no).

### 4.7 书签 / Bookmarks

```powershell
uv run scripts/add_bookmarks.py --dry-run   # 预览 / preview
uv run scripts/add_bookmarks.py             # 为没有书签的书添加可点击的目录 / add a clickable outline to books without one
```

使用书库已找到的章节起始页。已有书签的书从不修改；原文件保存在 `archive/books/`。
It uses the chapter pages the library has found. Books that already have bookmarks are never
changed; originals are kept in `archive/books/`.

### 4.8 刷新 / Refresh

**⟳ Refresh** 做三件事 / does three things:

1. 登记你手动放进 `books/`、`papers/`、`theses/` 的 PDF（等同于 `add_book.py`）。
   Registers PDFs you put into `books/`, `papers/` or `theses/` yourself (like `add_book.py`).
2. 为还没有学科的条目查询学科。
   Looks up subjects for items that don't have one.
3. 检查书库中已有的**重复条目**：保留信息更多的那个（完全相同时保留先添加的）。如果另一个条目有你的内容，先**把内容移过去**：勾选的章节、上次阅读的位置、笔记（写入对应章节的笔记）、生词、章节脚本和书架；然后把它完整地移到 `archive/` 作为备份。如果两个都有你的内容，什么都不动，History 会列出这一对让你决定。
   Checks for **repeats already in the library**: keeps the one with more information
   (identical copies: the one added first). If the other one holds your work, it's **moved
   over first**: ticked chapters, the last-read page, your notes (into the matching chapter's
   notes), saved words, chapter scripts and shelves; the other entry then goes to `archive/`
   complete, as a backup. If both hold your work, nothing is touched and the History names the
   pair for you to decide.

### 4.9 移除文档 / Removing a document

移除只能在终端中进行 / Removing is done from the terminal:

```powershell
uv run scripts/add_book.py --remove <name or id> --dry-run   # 预览 / preview
uv run scripts/add_book.py --remove <name or id>             # 移动前会询问 / asks before moving anything
```

PDF、笔记和脚本移到 `archive/`，**不删除任何东西**。id 不会被遗忘：`retired-documents.json` 记录它已被移除，所以阅读记录仍以标题显示它。要恢复：把文件移回去，然后运行 `add_book.py`。如果你只删除了 PDF，卡片仍在并显示 "PDF missing"，笔记和脚本仍可打开。
The PDF, notes and scripts move to `archive/`; **nothing is deleted**. The id isn't forgotten:
`retired-documents.json` records that it was removed, so your reading history still shows it by
its title. To bring it back, move its files back and run `add_book.py`. If you only delete the
PDF, the card stays and says "PDF missing"; its notes and scripts still open.

如果文档信息有误（作者、年份、标题），用 [4.4](#44-从终端添加--adding-from-the-terminal) 中的 `--author/--year/--title` 重新运行；书库页面上还没有修改信息的界面。
If a document's details are wrong (author, year, title), rerun with `--author/--year/--title`
as in [4.4](#44-从终端添加--adding-from-the-terminal); there's no page for editing details yet.

### 4.10 静态页面 / The static page

```powershell
uv run scripts/library_page.py   # 写出 library.html / writes library.html
```

`library.html` 是书库页面的只读静态副本（没有按钮），不需要服务器即可打开。只在本地，不进 Git。`add_book.py` 也会重建它。
`library.html` is a static, read-only copy of the library page (no buttons) that opens without
the server. It's local only (not in git). `add_book.py` rebuilds it too.

---

## 5. 阅读器 / The reader

文档在 **PDF.js**（Mozilla 的 PDF 阅读器，就是 Firefox 内置的那个）中打开，由本地服务器提供。myLibrary 在它上面加了查词、标注保存、阅读进度和笔记面板。
Documents open in **PDF.js** (Mozilla's PDF viewer, the one inside Firefox), served by the
local server. myLibrary adds lookup, saving marks, reading progress and the notes panel on top.

<!-- 截图建议 / Screenshot suggestion: docs/images/reader-with-notes.png — a book open in the reader with the lookup popup and the notes panel in Split mode. -->

### 5.1 打开和浏览 / Opening and navigating

从书库页面打开：**Continue · p. N**、**Start reading**、章节的 **Read** 或 **PDF**（见 [3.3](#33-卡片上的按钮--on-each-card)）。PDF.js 的工具栏照常使用：
Open from the library page: **Continue · p. N**, **Start reading**, a chapter's **Read**, or
**PDF** (see [3.3](#33-卡片上的按钮--on-each-card)). PDF.js's toolbar works as usual:

| 功能 Feature | 怎么用 How |
|---|---|
| 翻页 Pages | 页码框、上一页/下一页、滚动。The page box, previous/next, scrolling. |
| 缩放 Zoom | 工具栏的缩放菜单和 +/−。The toolbar's zoom menu and +/−. |
| 文档内搜索 Search in the document | Ctrl+F（即使光标在笔记面板中也搜索 PDF）。Ctrl+F (searches the PDF even from the notes panel). |
| 目录与缩略图 Outline and thumbnails | 工具栏左侧的侧边栏按钮。The sidebar button at the left of the toolbar. |
| 章节 Chapters | 用 PDF 的目录（书签），或从书库页面打开某一章。没有书签的书可以用 `add_bookmarks.py` 添加（[4.7](#47-书签--bookmarks)）。Use the PDF's outline, or open a chapter from the library page. Books without bookmarks can get them with `add_bookmarks.py` ([4.7](#47-书签--bookmarks)). |

不经过书库页面打开的 PDF（例如直接打开文件）没有 myLibrary 的功能。
A PDF opened some other way (e.g. the file directly) has none of myLibrary's features.

### 5.2 继续阅读 / Resume reading

**位置自动保存。** 翻到新页面约 2 秒后，以及关闭或隐藏标签页时，位置写入这本书笔记 README 的 "Reading progress" 下：
**Your place is saved automatically.** About 2 seconds after you turn to a page, and when you
close or hide the tab, it's written to the book's notes README under "Reading progress":

```
Last read: page 41 (Ch 2: Design Forms), 2026-11-05
```

只是打开一章查点东西不会移动你的位置：只有翻页才会。因为它在笔记里，所以也随笔记一起备份。
Opening a chapter just to look something up doesn't move your place; only turning pages does.
Because it's in your notes, it's backed up with them.

### 5.3 搜索结果的预览标签页 / Preview tabs from search results

在查词弹窗的 **📚 在我的书中** (In my books) 中点击一个结果，会在**新标签页**中打开那一页，并用查找栏高亮这个词。这是**预览**：左下角显示 **预览：不计入阅读进度** (Preview: not counted as reading)，不保存位置也不计阅读时间。点击 **开始阅读** (Start reading) 后才开始记录。
Clicking a result under **📚 在我的书中** (In my books) in the lookup popup opens that page in a
**new tab**, with the term highlighted by the find bar. It's a **preview**: bottom left it says
**预览：不计入阅读进度** (Preview: not counted as reading), and neither your place nor reading
time is recorded. **开始阅读** (Start reading) starts recording.

### 5.4 标注 / Annotations

阅读器右上角 PDF.js 的工具（高亮、文字、画笔、图片）直接在**书本身**上做标注。myLibrary 加了：
PDF.js's tools at the top right of the reader (highlight, text, draw, image) mark **the book
itself**. myLibrary adds:

| 控件 Control | 作用 What it does |
|---|---|
| **撤销** (Undo) / **重做** (Redo) | 工具栏按钮，Ctrl+Z / Ctrl+Y（或 Ctrl+Shift+Z）。在笔记面板和文本框中不起作用。Toolbar buttons, Ctrl+Z / Ctrl+Y (or Ctrl+Shift+Z). They don't act in the notes panel or in text fields. |
| 点击一个高亮 Click a highlight | 选中它（打开高亮工具）。Delete 或 🗑 删除它。Selects it (turning on the highlight tool). Delete or 🗑 removes it. |
| Esc | 没有选中标注时退出工具。Leaves the tool when no mark is selected. |

**保存标注 / Saving marks.**

- 停止标注约 1 秒后，**书库中的 PDF 被保存**（整个文件），带上你的标注。右下角依次显示 **标注未保存** (Marks not saved yet，带 **立即保存** Save now)、**正在保存标注…** (Saving your marks…)、**标注已保存** (Marks saved)。
  About 1 second after you stop marking, **the PDF in your library is saved** (the whole file)
  with your marks. Bottom right shows **标注未保存** (Marks not saved yet, with **立即保存**
  Save now), **正在保存标注…** (Saving your marks…), then **标注已保存** (Marks saved).
- 标注写在 PDF 里，所以在任何 PDF 阅读器中都能看到。
  The marks are in the PDF, so any PDF reader shows them.
- 第一次标注前的 PDF **只保存一次**到 `archive/before-marks/`。
  The PDF as it was before your first mark is kept **once** in `archive/before-marks/`.
- 保存失败显示 **标注没保存** (Marks not saved) 和 **重试** (Retry)；3 秒后自动重试，最多 3 次。
  A failed save shows **标注没保存** (Marks not saved) with **重试** (Retry); it retries by itself
  after 3 s, up to 3 times.
- 在其他程序（例如 Acrobat）中打开着的 PDF 无法替换：先关闭它。
  A PDF open in another program (e.g. Acrobat) can't be replaced: close it there first.
- 有未保存的标注时，关闭、刷新或离开标签页会先询问。
  With unsaved marks, closing, reloading or leaving the tab asks first.

**标注冲突 / Marks conflict.** 标注只会保存到你正在看的那个 PDF 版本上。如果这个标签页打开后 PDF 在别处被改了（另一个标签页保存了标注，或 OCR），**不会覆盖它**：
Marks are saved only onto the version of the PDF you're looking at. If the PDF changed
elsewhere since this tab opened it (marks saved from another tab, or OCR), **nothing is written
over it**:

1. 状态显示 **标注冲突** (Marks conflict)，你的带标注 PDF 另存在 `archive/marks-conflicts/`，显示路径和 **复制路径** (Copy path)。
   The status says **标注冲突** (Marks conflict), and your marked PDF is kept in
   `archive/marks-conflicts/`; its path is shown with **复制路径** (Copy path).
2. **重新载入** (Reload) 显示当前的 PDF，可以重新标注。如果之后又标注了，先点 **再存一份副本** (Keep another copy)。
   **重新载入** (Reload) shows the current PDF, to mark again. If you marked more since, first
   click **再存一份副本** (Keep another copy).
3. 两个 PDF 的标注不会自动合并。冲突后不再自动保存。
   Marks from two PDFs aren't merged automatically. After a conflict, nothing is saved
   automatically.

> **注意 Caution**：在任务管理器中结束浏览器、浏览器崩溃或断电时，最后一秒内未保存的标注会丢失。
> Ending the browser in Task Manager, a crash or a power cut can lose marks made in the last
> second before they were saved.

---

## 6. 查词与学术阅读 / Looking up words and terms

### 6.1 查词方式 / Ways to look something up

| 你的操作 You do | 结果 What happens |
|---|---|
| **双击一个单词** Double-click a word | 弹窗显示它的意思。A popup opens with its meaning. |
| **拖选 1–6 个词**（最多 60 个字符，例如 *veiling glare*） Drag over 1–6 words (up to 60 characters) | 直接查询，与双击相同。Looked up at once, like a double-click. |
| **拖选更长的段落** Drag over a longer passage | 出现 **翻译** (Translate) 按钮，打开 Bing 翻译（在线）。A **翻译** (Translate) button appears; it opens Bing Translator (online). |
| **修改弹窗顶部的词**并按 **Enter** Edit the word at the top of the popup and press Enter | 查询你输入的内容。Looks up what you typed. |
| **Esc**、点击弹窗外或滚动页面 Esc, a click outside, or scrolling the page | 关闭弹窗。Closes the popup. |

拖选从单词中间开始或结束时，会扩展到整个单词（"eiling gla" → *veiling glare*），页面上的高亮显示实际查询的内容。**扫描版**中隐形的 OCR 文字可能与印刷字母略有偏移，或者 OCR 认错了字母：这时在弹窗顶部改正单词再按 Enter。
If a drag starts or ends inside a word, the whole word is taken ("eiling gla" → *veiling
glare*), and the highlight shows what was looked up. In **scanned books** the invisible OCR text
can sit slightly off the printed letters, or the OCR may have misread a letter: fix the word at
the top of the popup and press Enter.

> 限制 Limitation：行尾断开的单词（"aber-"）和词典里没有的连字符复合词（"point-spread"）查不到。
> Words split across lines ("aber-") and unknown hyphenated compounds ("point-spread") aren't
> found.

### 6.2 弹窗内容 / What the popup shows

1. **单词**、音标和 🔊（用浏览器自带的语音朗读）。
   **The word**, its phonetics and 🔊 (read aloud by the browser's built-in speech).
2. **词形还原 Base form**：复数和动词变形会还原（*aberrations* → *aberration*，*matrices* → *matrix*），并显示这一步。
   Plurals and verb forms are reduced (*aberrations* → *aberration*, *matrices* → *matrix*), and
   that step is shown.
3. **术语表释义**，排在最前，每条带术语表标签（例如 *光学 Optics*）：中文术语、简短定义，必要时提醒日常含义。例如在光学中 *stop* → 光阑 (aperture stop)，不是 停止 (to stop)。几个术语表都有时，每个学科的意思都显示。也会找到周围更长的术语：在 "the exit pupil" 中双击 *pupil*，同时显示 出瞳 (exit pupil) 和 光瞳 (pupil)。选择较长时，列出其中包含的术语。
   **Glossary meanings**, first, each tagged with its glossary's label (e.g. *光学 Optics*): the
   Chinese term, a short definition and, where needed, a warning about the everyday meaning. In
   optics, *stop* → 光阑 (aperture stop), not 停止 (to stop). If several glossaries have the term,
   you see each. Longer terms around the word are found too: double-clicking *pupil* in "the
   exit pupil" shows 出瞳 (exit pupil) as well as 光瞳 (pupil). For a longer selection, the
   glossary terms inside it are listed.
4. **词典释义**，来自 ECDICT（开源英汉词典，离线）。词典里没有的短语，逐词列出意思。
   **Dictionary meaning** from ECDICT (an open-source English–Chinese dictionary, offline). For
   a phrase it doesn't know, each word's meaning is listed.
5. **深入了解 Learn more**（见 [6.3](#63-深入了解--learn-more)）。
6. **＋ 加入术语表** (Add to glossary)：这个词或短语还不在术语表中时显示（见 [6.4](#64-加入术语表--add-to-glossary)）。
   Shown when the word or phrase isn't in a glossary yet (see
   [6.4](#64-加入术语表--add-to-glossary)).
7. **加入生词本** (Save word)，多词时还有 **整句翻译** (Translate (Bing))。
   **加入生词本** (Save word), and for several words **整句翻译** (Translate (Bing)).

### 6.3 深入了解 / Learn more

每个术语下面 / Under each term:

| 链接 Link | 作用 What it does |
|---|---|
| **📚 在我的书中** (In my books) | 你所有的书中讨论这个术语最多的页面，带一小段上下文（当前这本书排在最前；每本书最多 2 页，共 8 条）。点击在新标签页中预览那一页（[5.3](#53-搜索结果的预览标签页--preview-tabs-from-search-results)）。常常是真正理解一个术语的最好方法：看两三位作者如何解释它。The pages of all your books that discuss the term most, with a snippet (the current book first; up to 2 pages per book, 8 in all). Click one to preview that page in a new tab ([5.3](#53-搜索结果的预览标签页--preview-tabs-from-search-results)). Often the best way to really understand a term: see how two or three authors explain it. |
| **📝 主题笔记** (Topic note) | 打开或新建这个术语的主题笔记（[8.2](#82-主题笔记--topic-notes)）。Opens or starts your topic note on this term ([8.2](#82-主题笔记--topic-notes)). |
| **Wikipedia** | 英文维基百科搜索（在线）。English Wikipedia search (online). |
| **维基百科** (Chinese Wikipedia)、**百度百科** (Baidu Baike) | 只在术语表条目下显示，搜索中文术语（在线）。Shown under glossary entries only; they search the Chinese term (online). |

### 6.4 加入术语表 / Add to glossary

1. 在弹窗中点击 **＋ 加入术语表** (Add to glossary)。
   Click **＋ 加入术语表** (Add to glossary) in the popup.
2. 参考书中的解释后，填写**中文术语**（必填）和可选的**定义**（用自己的话）。
   After reading how your books explain it, type the **Chinese term** (required) and,
   optionally, a **definition** in your own words.
3. 有多个术语表时选择一个。点击 **保存** (Save)。
   If you have several glossaries, choose one. Click **保存** (Save).

默认加入 `glossaries.toml` 中的 `default` 术语表，没有则是按字母顺序的第一个；一个术语表都没有时创建 `glossaries/my-terms.csv`。已存在的术语会被拒绝。保存后弹窗会重新查询。
Terms go to the `default` glossary in `glossaries.toml`, else the first alphabetically; with no
glossary at all, `glossaries/my-terms.csv` is created. A term that's already there is refused.
After saving, the popup looks the word up again.

### 6.5 生词本 / Vocabulary

**加入生词本** (Save word) 在 `notes/<book>/vocabulary.md` 中加一行：
**加入生词本** (Save word) adds a row to `notes/<book>/vocabulary.md`:

```
| Word | Phonetic | 中文 Chinese | Page | Added |
|---|---|---|---|---|
| vignetting |  | 渐晕 | 16 | 2026-11-05 |
```

（渐晕 是 *vignetting* 的中文。）中文列优先取术语表的释义，否则取词典的前两条。每本书中每个词只保存一次（已存在时显示 **已在生词本中** Already saved）。生词用于复习卡片（[10.2](#102-复习生词--review-words)）。
(渐晕 is Chinese for *vignetting*.) The Chinese column takes the glossary meaning if there is
one, else the dictionary's first two lines. Each word is saved once per book (otherwise
**已在生词本中** Already saved). Saved words feed the review cards
([10.2](#102-复习生词--review-words)).

> 限制 Limitation：新行加在文件末尾；如果你在表格下面写了文字，新行会在表格外面。
> New rows are added at the end of the file; if you wrote text below the table, they land
> outside it.

### 6.6 在终端中查词 / Lookup from the terminal

```powershell
uv run scripts/reader.py entrance pupil      # 术语表 + 词典 / glossary + dictionary meaning
uv run scripts/book_search.py vignetting     # 你的书中哪里讨论它 / where your books discuss it
```

---

## 7. 术语表 / Glossaries

通用词典给出日常含义，而学科赋予词语特殊含义。术语表解决这个问题：`glossaries/` 中每个学科一个 CSV，**全部都会使用**。
A general dictionary gives everyday meanings; a subject gives words special ones. Glossaries fix
that: one CSV per subject in `glossaries/`, and **all of them are used**.

```
term,zh,note,definition
vignetting,渐晕,,轴外光束的一部分被孔径光阑以外的通光口径挡住，使视场边缘照度下降；...
```

（英文：*vignetting*，渐晕；"part of an off-axis beam is blocked by apertures other than the
aperture stop, so the edge of the field gets darker; ..."）

| 列 Column | 含义 Meaning |
|---|---|
| `term` | 英文术语，单数（*entrance pupil*，不是 *entrance pupils*）。English term, singular. |
| `zh` | 中文术语（必填）。Chinese term (required). |
| `note` | 可选：缩写或提醒（例如 *PSF*，或 *不是"学生"*："not 'school pupil'"）。Optional: abbreviation or a warning. |
| `definition` | 可选：简短定义。Optional: a short definition. |

`glossaries/glossaries.toml`（可选）设置每个术语表在弹窗中的标签、新术语加到哪里，并可以停用一个术语表而不删除它：
`glossaries/glossaries.toml` (optional) sets each glossary's label in the popup, which one new
terms go to, and lets you switch one off without deleting it:

```toml
default = "optics"          # ＋ 加入术语表 (Add to glossary) 加到这里 / where new terms go (else the first alphabetically)

[optics]
label = "光学 Optics"       # 弹窗中的标签（否则用文件名）/ the tag in the popup (else the file name)

[biology]
label = "生物 Biology"
# enabled = false           # 停用这个术语表 / stop using this glossary
```

**排序 / Order.** 与这本书的书架、学科或领域相符的术语表排在前面：读一本光学设计的书时，`optics` 术语表的释义先列出。
Glossaries matching the book's shelves, subject or field come first: reading a book on optical
design, the `optics` glossary's meanings are listed first.

**编辑 / Editing.** 最方便的是从弹窗添加（[6.4](#64-加入术语表--add-to-glossary)）。也可以在 VS Code 或 Excel 中编辑 CSV（保存为 UTF-8）。下次查词时生效，不用重启。
Easiest from the popup ([6.4](#64-加入术语表--add-to-glossary)). Or edit the CSV in VS Code or
Excel (save as UTF-8). Changes show at the next lookup; no restart needed.

**示例光学术语表**（`library/glossaries/optics.csv`，约 300 条：近轴光学、像差、像质、设计与公差、杂散光、镀膜、激光、光机）展示了一个好的术语表的样子。定义是简短的概括；如果与你的书不一致，以书为准并改正那一行。
**The example optics glossary** (`library/glossaries/optics.csv`, about 300 terms: paraxial
optics, aberrations, image quality, design and tolerancing, stray light, coatings, lasers,
optomechanics) shows what a good glossary looks like. Its definitions are short summaries; if
one disagrees with your books, trust the book and correct the row.

---

## 8. 搜索与发现 / Search and discovery

### 8.1 全文搜索 / Full-text search of your books

服务器启动时在后台为所有有文字层的 PDF 建立全文索引（书库的 `.cache/books.db`），新增或修改的书会重新索引。在阅读器中通过 **📚 在我的书中** (In my books) 使用（[6.3](#63-深入了解--learn-more)），或在终端中：
When the server starts, it builds a full-text index of every PDF with a text layer, in the
background (the library's `.cache/books.db`); new or changed books are re-indexed. Use it from
the reader with **📚 在我的书中** (In my books) ([6.3](#63-深入了解--learn-more)), or from the
terminal:

```powershell
uv run scripts/book_search.py vignetting   # 搜索 / search
uv run scripts/book_search.py --status     # 每个文档的索引状态 / each document's index status
```

结果按相关性排序（精确短语匹配）。扫描版要先 OCR 才能被搜索。书库页面的搜索框搜索的是书目信息和章节标题，不是全文。
Results are ranked by relevance (exact phrase match). A scan needs OCR before it can be
searched. The library page's search box searches the details and chapter titles, not the full
text.

### 8.2 主题笔记 / Topic notes

章节笔记跟着一本书；**主题笔记**跟着一个概念，横跨你所有的书，例如 `aberrations.md` 汇总 Kingslake、Fischer 和 Geary 的说法。
Chapter notes follow one book; a **topic note** follows one idea across all your books, e.g.
`aberrations.md` combining what Kingslake, Fischer and Geary say.

1. 在查词弹窗中点击 **📝 主题笔记** (Topic note)。
   Click **📝 主题笔记** (Topic note) in the lookup popup.
2. 第一次会创建 `notes/topics/<term>.md`，包含标题（*In my own words*、*Where my books explain it*、*Related terms*）和你的书中讨论这个术语最多的页面列表（只有书名和页码，没有书中原文）。已存在的文件从不覆盖。
   The first time, it creates `notes/topics/<term>.md` with headings (*In my own words*, *Where
   my books explain it*, *Related terms*) and a list of the pages in your books that discuss
   the term most (book and page only, never book text). An existing file is never overwritten.
3. 笔记在你的外部编辑器中打开（[12](#12-设置--settings)）。主题笔记目前不在阅读器的笔记面板中显示。
   The note opens in your outside editor ([12](#12-设置--settings)). Topic notes aren't shown in
   the reader's notes panel yet.

### 8.3 在线查找 / Find online

**🔎 Find online** 在网上查找书、论文和学位论文。输入任何内容：
**🔎 Find online** searches the internet for books, papers and theses. Type anything:

| 输入 You type | 搜索 Searched on |
|---|---|
| **DOI**（例如 `10.1364/AO.58.000001`） | Crossref / DataCite，以及 OpenAlex（免费副本 free copy） |
| **arXiv 编号** arXiv number | arXiv |
| **ISBN** | Open Library |
| 标题、作者或主题 Title, author or topic | OpenAlex 作品搜索、匹配的作者被引最多的作品（名字中每个词都匹配时）、Open Library 的书。OpenAlex works search, the matching author's most cited works (when every word is in the name), and Open Library books. |

每个结果显示作者、年份、期刊或大学、被引次数、**✓ In your library**（已在书库中）、**DOI** 链接，以及有合法开放获取副本时的 **Free to read**。
Each result shows the authors, year, journal or university, how often it's cited,
**✓ In your library** if you have it already, a **DOI** link and **Free to read** when there's a
legal open-access copy.

**＋ Add to library** 只在免费副本是 PDF、且书库中还没有时出现：它下载 PDF，像上传一样添加（识别、命名、归档）。链接返回的是网页而不是 PDF 时会拒绝，并提示你打开链接、手动下载 PDF 后拖到页面上；从不抓取网页，也从不使用影子图书馆。
**＋ Add to library** appears only when the free copy is a PDF and the work isn't in your
library yet: it downloads the PDF and adds it like an upload (recognised, named, filed). A link
that gives a web page instead of a PDF is refused, with a message to open it, download the PDF
there and drag it onto the page; web pages are never scraped, and shadow libraries are never
used.

**Also search on:** 同样的词一键搜索 Google Scholar、Semantic Scholar、百度学术 (Baidu Scholar)、知网 (CNKI)、arXiv、Google Books、Open Library 和 WorldCat。
The same words on Google Scholar, Semantic Scholar, 百度学术 (Baidu Scholar), 知网 (CNKI),
arXiv, Google Books, Open Library and WorldCat, in one click.

> 限制 Limitation：没有中文目录（Find online 搜不到中文图书目录）。
> There's no Chinese catalogue in Find online.

### 8.4 OpenAlex 与密钥 / OpenAlex and its key

学科分类和 🔎 Find online 使用 [OpenAlex](https://openalex.org)。没有密钥时，你网络上的所有人共享一个很小的每日额度（一次添加很多条目可能用完，学科会在以后的 ⟳ Refresh 中再查）。在 [openalex.org/settings/api-key](https://openalex.org/settings/api-key) 免费申请自己的密钥，填入 **⚙ Settings → OpenAlex key**：保存时会检查，只保存在你的设置文件中，从不放进书库，只发送给 api.openalex.org。
Subjects and 🔎 Find online use [OpenAlex](https://openalex.org). Without a key, everyone on your
network shares a small daily budget (adding many items at once can use it up; subjects are then
looked up on a later ⟳ Refresh). Get your own free key at
[openalex.org/settings/api-key](https://openalex.org/settings/api-key) and put it into
**⚙ Settings → OpenAlex key**: it's checked when you save, stays in your settings file (never in
the library) and is sent only to api.openalex.org.

---

## 9. 笔记 / Notes

### 9.1 笔记文件 / Note files

每个文档的笔记在 `notes/<name>/` 中，都是普通的 Markdown 文件：
Each document's notes are in `notes/<name>/`, all plain Markdown files:

| 文件 File | 内容 Contents |
|---|---|
| `README.md` | 文档信息、章节清单（勾选）、"Last read" 行。Details, the chapter checklist (ticks), the "Last read" line. |
| `chNN-<chapter>.md` | 每章一个：各节的标题，加上 *Key ideas*、*Equations*、*Questions*、*Check it in Python*。One per chapter: section headings, plus *Key ideas*, *Equations*, *Questions*, *Check it in Python*. |
| `notes.md` | 论文的笔记（代替章节笔记）。A paper's notes (instead of chapter notes). |
| `vocabulary.md` | 阅读时保存的生词。Words you saved while reading. |

章节模板只有标题。请**用自己的话**写笔记，不要粘贴书中原文（有版权，而且改写才是学习）。
The chapter templates hold headings only. Write the notes **in your own words**; don't paste text
from the books (they're copyrighted, and rewriting is how you learn).

### 9.2 笔记面板 / The notes panel

在阅读器中，文档的笔记显示在 PDF 旁边。
In the reader, the document's notes open beside the PDF.

| 控件 Control | 作用 What it does |
|---|---|
| **笔记** (Notes) 工具栏按钮，或 **Alt+N** | 显示或隐藏面板（任何键盘布局和输入法下都可用）。Show or hide the panel (works with any keyboard layout or IME). |
| 笔记菜单 Note menu | 选择笔记：**本书** (This document)、**章节** (Chapters)、**其他** (Other notes)。Choose a note. |
| **源码** (Source) / **预览** (Preview) / **分屏** (Split) | 视图（[9.3](#93-源码预览和分屏--source-preview-and-split)）。The view. |
| 保存状态 Save state | 例如 **已保存** (Saved)（[9.5](#95-自动保存与状态--autosave-and-status)）。E.g. **已保存** (Saved). |
| **保存** (Save) | 立即保存（Ctrl+S）。只在有未保存内容或保存失败时可用。Save now (Ctrl+S). Enabled only with unsaved text or after a failure. |
| 🔒 / 🔓 | 只读开关（[9.6](#96-只读--read-only)）。The read-only switch. |
| ↗ | 在外部编辑器中打开这条笔记（[9.9](#99-外部编辑器--outside-editor)）。Open this note in your outside editor. |
| ✕ | 收起面板。Hide the panel. |
| 分隔线 Divider | 拖动调整宽度，或聚焦后按 ←/→；双击收起。Drag to resize, or focus it and press ←/→; double-click to hide. |

**先打开哪条笔记 / Which note opens first:** 你打开的那一页所在的章节；否则是你上次在这个文档中选的笔记；否则是 `notes.md`，然后是 `README.md`。
The chapter containing the page you opened at; else the note you last chose for this document;
else `notes.md`, then `README.md`.

**还没写的章节笔记 / Chapter notes not written yet** 在菜单中显示为 "（还没有 not written yet）"。选中后显示 **这一章还没有笔记** (No notes for this chapter yet)：直接输入即可，第一次保存时才创建文件。
show as "（还没有 not written yet）" in the menu. Choosing one shows **这一章还没有笔记** (No notes
for this chapter yet): just type; the file is created when it's first saved.

**切换笔记 / Switching notes** 时，有未保存的内容会先保存；保存失败则留在当前笔记并提示先处理。
saves unsaved text first; if that fails, the panel stays on the current note and asks you to
deal with it.

**布局 / Layout.**

| 窗口宽度 Window width | 面板 Panel |
|---|---|
| ≥ 1100 px | 在 PDF 旁边；宽度和开关状态记在这个浏览器中。Beside the PDF; its width and open state are remembered in this browser. |
| 760–1099 px | 覆盖在 PDF 上（开始时关闭）。Over the PDF (closed at first). |
| < 760 px | 占满窗口（开始时关闭）。Fills the window (closed at first). |

**在面板中的按键留在面板中** / **Keys typed in the panel stay there**：空格、PageDown、方向键等滚动笔记，而不是书。Ctrl 和 Alt 组合键照常传递，所以 Ctrl+F 仍搜索 PDF。**Esc** 回到书（覆盖或全屏布局时收起面板）。
Space, PageDown, arrows and so on scroll the note, not the book. Ctrl and Alt shortcuts pass
through, so Ctrl+F still searches the PDF. **Esc** goes back to the book (in the overlay or
full layouts it hides the panel).

写笔记从不计入阅读时间，也从不移动你的阅读位置。打开或查看笔记不写入任何文件。
Writing notes never counts as reading time and never moves your place. Opening or viewing a note
writes nothing.

<!-- 截图建议 / Screenshot suggestion: docs/images/notes-panel-split.png — the notes panel in Split view beside a PDF, with the save state visible. -->

### 9.3 源码、预览和分屏 / Source, Preview and Split

| 视图 View | 显示 Shows |
|---|---|
| **源码** (Source) | 可编辑的 Markdown 文本（默认）。The editable Markdown text (the default). |
| **预览** (Preview) | 渲染后的笔记，只读。The rendered note, read-only. |
| **分屏** (Split) | 两者同时：面板宽（≥ 720 px）时左右并排，窄时上下排列；预览跟随源码滚动，停止输入后很快更新。Both: side by side on a wide panel (≥ 720 px), one above the other on a narrow one; the preview scrolls with the source and updates shortly after you stop typing. |

**Alt+P** 在源码和预览之间切换（从分屏切到预览）。选择记在这个浏览器中。预览**只是显示**笔记：`.md` 文件保持你输入的原样，切换视图不保存任何东西。没有安装预览库时，预览显示纯文本和安装方法：`uv run scripts/reader.py --setup-preview`；源码视图照常工作。
**Alt+P** switches between Source and Preview (from Split it goes to Preview). The choice is
remembered in this browser. The preview **only shows** the note: the `.md` file stays exactly as
you typed it, and switching views saves nothing. Without the preview library, the preview shows
the plain text and how to set it up: `uv run scripts/reader.py --setup-preview`; Source works
as before.

### 9.4 Markdown 语法 / Markdown formatting

预览使用 markdown-it 15.0.3（CommonMark 加表格和删除线）。
The preview uses markdown-it 15.0.3 (CommonMark plus tables and strikethrough).

| 写法 You write | 预览显示 Preview shows |
|---|---|
| `# 标题 Heading` … `###### ` | 标题 1–6 级，可用 `#heading` 链接跳转。Headings 1–6, reachable by `#heading` links. |
| `**粗体 bold**`、`*斜体 italic*`、`~~删除 struck~~` | 粗体、斜体、删除线。Bold, italic, strikethrough. |
| `- 项目 item`、`1. 项目 item` | 列表。Lists. |
| `> 引用 quote` | 引用块。A blockquote. |
| `` `code` `` 和 ```` ``` ```` 代码块 fences | 行内代码和代码块（窄面板中可横向滚动）。Inline and fenced code (scrolls sideways in a narrow panel). |
| `\| a \| b \|` 表格 tables | 表格（窄面板中可横向滚动）。Tables (scroll sideways in a narrow panel). |
| `---` | 分隔线。A horizontal rule. |
| `[文字 text](https://…)` | 在新标签页打开的网页链接。A web link, opened in a new tab. |
| `[Ch 2](ch02-….md)` | 在面板中打开这个文档的另一条笔记。Opens another note of this document in the panel. |
| `[p. 12](/read/<id>?page=12)` | 在新标签页中打开那个文档的那一页。Opens that document at that page in a new tab. |

**目前不支持 / Not supported yet:**

- **数学公式**：`$E = mc^2$` 按原样显示为文本（KaTeX 渲染计划在 M5b）。在源码中照样可以写 LaTeX，以后会被渲染。
  **Maths**: `$E = mc^2$` is shown as typed (KaTeX rendering is planned for M5b). You can still
  write LaTeX in the source; it'll render later.
- **图片**：显示为虚线占位框 "图片 Image: <描述>"，不加载图片（计划在 M5d）。
  **Images**: shown as a dashed placeholder "图片 Image: <description>", never loaded (planned
  for M5d).
- **笔记中的 HTML** 显示为文本，从不执行。其他协议的链接（`javascript:`、`data:`……）不可点击。
  **HTML in a note** is shown as text, never run. Links with other schemes (`javascript:`,
  `data:`, ...) aren't clickable.
- 单个换行不会换行（空一行开始新段落）；裸露的网址不会自动变成链接；任务列表 `- [ ]` 不显示为复选框。
  A single line break doesn't break the line (leave a blank line for a new paragraph); bare URLs
  aren't turned into links; task items `- [ ]` aren't shown as checkboxes.

### 9.5 自动保存与状态 / Autosave and status

停止输入 **1.5 秒**后自动保存，或在笔记中按 **Ctrl+S** / 点击 **保存** (Save) 立即保存。（在书中，Ctrl+S 是 PDF.js 的"保存 PDF"。）
Notes are saved **1.5 seconds** after you stop typing, or at once with **Ctrl+S** (in the note)
or **保存** (Save). (In the book, Ctrl+S is PDF.js's "save the PDF".)

| 状态 Status | 意思 Meaning |
|---|---|
| **已保存** (Saved) | 文件已写入磁盘。The file is written. |
| **未保存** (Unsaved) | 有还没保存的输入。There's text not yet saved. |
| **正在保存…** (Saving…) | 正在写入。Being written. |
| **保存失败** (Save failed) | 文字仍在这里，会在 2、5、10 秒后自动重试，之后每 30 秒一次；**重试** (Retry) 立即重试。Your text is kept here and retried after 2, 5 and 10 s, then every 30 s; **重试** (Retry) tries now. |
| **服务器未连接** (Server not reachable) | 同上，服务器连不上。As above; the server can't be reached. |
| **需要重新载入** (Reload needed) | myLibrary 重启过：按 F5 重新载入标签页，你的文字保留为恢复草稿，载入后会提供恢复。myLibrary was restarted: reload the tab (F5); your text is kept as a recovery draft and offered after the reload. |
| **有冲突** (Conflict) | 见 [9.7](#97-保存冲突--save-conflicts)。See [9.7](#97-保存冲突--save-conflicts). |
| **有未保存的草稿** (Unsaved draft) | 见 [9.8](#98-恢复草稿--recovery-drafts)。See [9.8](#98-恢复草稿--recovery-drafts). |

**编辑快捷键 / Editing keys:**

| 按键 Key | 作用 What it does |
|---|---|
| Ctrl+S | 保存笔记（从不保存 PDF）。Save the note (never the PDF). |
| Ctrl+Z / Ctrl+Y | 撤销 / 重做你的输入（浏览器自带的撤销；PDF 标注的撤销不受影响）。Undo / redo your typing (the browser's own undo; the PDF marks' undo isn't affected). |
| Tab / Shift+Tab | 缩进 / 取消缩进（2 个空格；有选择时作用于每一行）。Indent / outdent (2 spaces; every selected line). |
| Enter | 在列表（`-`、`*`、`+`、`1.`、`- [ ]`）或引用（`>`）中继续下一项；在空项上按 Enter 结束列表。Continues a list or quote; Enter on an empty item ends it. |
| Alt+P | 源码 ↔ 预览。Source ↔ Preview. |
| Alt+N | 显示 / 隐藏面板。Show / hide the panel. |
| Esc | 回到书。Back to the book. |

保存时保留文件原有的换行符（CRLF/LF）、BOM 和末尾换行。没有变化的保存不写文件。超过 5 MB 或不是 UTF-8 的笔记不能在面板中编辑，请用外部编辑器。
Saving keeps the file's own line endings (CRLF/LF), byte-order mark and final newline. A save
that changes nothing doesn't write the file. Notes over 5 MB or not in UTF-8 can't be edited in
the panel; use your outside editor.

### 9.6 只读 / Read-only

点击 **🔒** 让笔记只读（不能输入），再点一次（显示 🔓）解锁。默认可以编辑。这个选择对这个浏览器中的所有文档都有效，并会被记住。
Click **🔒** to make notes read-only (no typing); click again (🔓) to unlock. Notes are editable
by default. The choice applies to every document in this browser and is remembered.

### 9.7 保存冲突 / Save conflicts

每次保存都带着它所基于的版本。如果笔记在别处被修改了（VS Code、另一个标签页），服务器**拒绝覆盖**。面板每 5 秒检查一次打开的笔记，切回窗口时也会检查；同一浏览器中的其他标签页会立即被通知。
Every save names the version it was based on. If the note was changed elsewhere (VS Code,
another tab), the server **refuses to overwrite it**. The panel checks the open note every
5 seconds and when you come back to the window; other tabs in the same browser are told at once.

- **没有未保存的内容**：直接显示新版本（**已从磁盘更新** Updated from disk）。
  **Nothing unsaved**: the newer version simply appears (**已从磁盘更新** Updated from disk).
- **有未保存的内容**：显示 **有冲突** (Conflict)，你来选择：
  **Unsaved text**: it shows **有冲突** (Conflict), and you choose:

| 选项 Option | 结果 Result |
|---|---|
| **保留我的版本** (Keep mine) | 磁盘上的版本先复制到 `archive/notes-conflicts/…/<name>.<时间 time>.md`，然后写入你的版本。The disk version is first copied to `archive/notes-conflicts/…/<name>.<time>.md`, then yours is written. |
| **载入磁盘版本** (Use the disk version) | 你的版本先保存为 `archive/notes-conflicts/…/<name>.<时间 time>.mine.md`，然后载入磁盘版本。Yours is first saved as `….mine.md` there, then the disk version is loaded. |
| **对比** (Compare) | 显示磁盘上的版本（只读），与你的文字对照。Shows the disk version (read-only) next to your text. |

两种选择都会先保存另一份，所以都不会丢失内容。
Both choices keep a copy of the other version first, so neither loses text.

### 9.8 恢复草稿 / Recovery drafts

从你开始输入到服务器确认保存之前，未保存的文字会作为**恢复草稿**保存在浏览器中。再次打开这条笔记时，如果草稿与文件不同，会提供：**恢复** (Restore)、**丢弃** (Discard) 或 **对比** (Compare)。选择之前不会自动保存。
From your first keystroke until the server confirms the save, unsaved text is kept in the browser
as a **recovery draft**. When you open the note again and a draft differs from the file, you're
offered **恢复** (Restore), **丢弃** (Discard) or **对比** (Compare). Nothing is autosaved until you
choose.

- 关闭或刷新有未保存内容的标签页会先询问。
  Closing or reloading a tab with unsaved text asks first.
- 草稿是这台电脑上浏览器配置文件中的纯文本，保存到笔记保存为止，30 天后删除。能使用你的 Windows 账户和浏览器的人可以读到它们（就像读到你的笔记一样）。
  Drafts are plain text in this browser's profile on this PC, kept until the note is saved, and
  deleted after 30 days. Anyone using your Windows account and browser could read them, as they
  could your notes.
- 草稿属于服务器所在的地址：换了端口启动，myLibrary 看不到旧的草稿。
  Drafts belong to the server's address: started on another port, myLibrary doesn't see the old
  drafts.
- 如果浏览器无法保存草稿，面板会警告：此时浏览器崩溃会丢失未保存的文字。
  If the browser can't store drafts, the panel warns you: a browser crash would then lose unsaved
  text.

### 9.9 外部编辑器 / Outside editor

**↗** 在你的编辑器中打开当前笔记（VS Code，或 ⚙ Settings 中选择的程序），书库页面上的 **Notes** 打开笔记的 README。还没创建的笔记不能用 ↗ 打开。
**↗** opens the current note in your editor (VS Code, or what you chose in ⚙ Settings); **Notes**
on the library page opens the notes' README. A note that doesn't exist yet can't be opened
with ↗.

**Read** 和 **Continue** 不再同时在编辑器中打开笔记：它们已经在面板中，两个编辑器同时编辑一条笔记正是冲突的来源。（阅读器不可用时，笔记仍在编辑器中打开。）同时使用两者时，面板会处理冲突（[9.7](#97-保存冲突--save-conflicts)）；而 VS Code 在保存时也会提示文件已被修改，由你选择。
**Read** and **Continue** no longer also open the notes in your editor: they're in the panel, and
two editors on one note is how conflicts start. (Without the reading view, the notes still open
in the editor.) If you do use both, the panel handles conflicts
([9.7](#97-保存冲突--save-conflicts)); VS Code, when it saves, reports that the file is newer and
lets you choose.

> **注意 Caution**：在 VS Code 中打开着的笔记，如果 myLibrary 修改了它（例如勾选章节、更新 "Last read"），VS Code 中未保存的编辑再保存时可能覆盖这些修改。保存前看清 VS Code 的提示。
> If a note is open in VS Code with unsaved edits and myLibrary changes it (ticking a chapter,
> updating "Last read"), saving in VS Code can write over that change. Read VS Code's prompt
> before saving.

### 9.10 计划中的笔记功能 / Planned notes features

以下功能**尚未实现**，只是计划 / These are **not implemented yet**, only planned:

| 阶段 Phase | 计划 Plan |
|---|---|
| M5b | KaTeX 渲染 LaTeX 数学公式（`$…$`、`$$…$$`）。LaTeX maths rendered with KaTeX. |
| M5c | 基于选择的 Markdown 格式工具栏（标题、粗体、列表、表格、公式……）和排版设置（字体、字号、行距）。A selection-based Markdown formatting toolbar and display settings (font, size, line height). |
| M5d | 粘贴截图和图片（Ctrl+V），保存为笔记旁的本地文件并在预览中显示。Pasting screenshots and images (Ctrl+V), saved as local files beside the note and shown in the preview. |
| 以后 Later | 把截图识别成可编辑的公式或表格。Turning a screenshot into an editable equation or table. |

---

## 10. 学习与进度 / Learning and progress

### 10.1 阅读记录 / Reading log

在阅读器中打开一本书时，记录你**主动阅读**的时间（标签页可见，且最近两分钟内滚动、翻页或移动过鼠标）和看过的页面。笔记面板中的活动和预览标签页不计入。点击书库标题下的 **📈 … ›** 打开 **阅读记录** (Reading log)：
While a book is open in the reader, the time you **actively read** is counted (the tab is visible
and you scrolled, turned a page or moved in the last two minutes), along with the pages you saw.
Activity in the notes panel and preview tabs doesn't count. Click **📈 … ›** under the library's
title for **阅读记录** (Reading log):

- 连续天数（每天 5 分钟以上）、今天、本周、总计；
  the streak (days with 5+ minutes), today, this week, in all;
- 最近 26 周的日历（鼠标悬停看每天的分钟数和页数）；
  a calendar of the last 26 weeks (hover a day for its minutes and pages);
- 最近 30 天读过的书。
  the books you read in the last 30 days.

保存在 `notes/reading-log.json`，随笔记一起备份。阅读时间每分钟发送一次；浏览器崩溃或被强制关闭时，最后一分钟可能丢失。快速滚动经过的页面也会被计为看过。
It's kept in `notes/reading-log.json`, so it's backed up with your notes. Reading time is sent
every minute; after a crash or a forced close, the last minute can be lost. Pages scrolled past
quickly are counted as seen too.

### 10.2 复习生词 / Review words

**📇 Review words** 把你所有书中保存的生词做成卡片（同一个词在两本书中只算一张）。
**📇 Review words** turns the saved words of all your books into cards (the same word saved in two
books is one card).

1. 卡片显示单词和音标；🔊 或 **S** 朗读。
   A card shows the word and its phonetic; 🔊 or **S** says it.
2. **空格**（或 Enter）显示中文意思和出处（书和页码，点击打开那一页）。
   **Space** (or Enter) shows the Chinese meaning and where you met it (book and page, a link that
   opens the book there).
3. **认识** (Knew it)：**2** 或空格；**不认识** (Didn't know)：**1**。
   **认识** (Knew it): **2** or Space; **不认识** (Didn't know): **1**.

认识的词在 1、3、7、14、30、60 天后再出现；不认识的词在本轮再出现一次，明天再出现。顶部菜单可以只复习一本书的词。进度保存在 `notes/vocabulary-review.json`；生词本文件本身从不修改。
A word you knew comes back after 1, 3, 7, 14, 30, then 60 days; one you didn't comes back once
more in this round and again tomorrow. The menu at the top picks one book's words. Progress is
kept in `notes/vocabulary-review.json`; the vocabulary files themselves are never changed.

### 10.3 章节完成情况 / Chapter completion

见 [3.4](#34-进度与勾选章节--progress-and-ticking-chapters)：在书库页面 **Chapters** 中勾选读完的章节；论文用 **Mark as read**。
See [3.4](#34-进度与勾选章节--progress-and-ticking-chapters): tick finished chapters under
**Chapters** on the library page; for a paper, use **Mark as read**.

### 10.4 章节脚本 / Chapter scripts

需要开启 **⚙ Settings → Show the Python features**（从源码安装时默认开启，安装包中关闭）。
Needs **⚙ Settings → Show the Python features** (on by default when installed from source, off in
the package).

对于技术类书籍，重新计算例题是检验理解的最好方法之一。在书库页面的章节上点击 **Script**：第一次会从模板创建一个简短的 Python 脚本 `examples/<book>/chNN_<topic>.py`，并在编辑器中打开。之后 **Read** 和 **Continue** 也会打开它。
For technical books, recomputing a worked example is one of the best ways to check that you
understood it. Click **Script** next to a chapter on the library page: the first time, it creates
a short Python script `examples/<book>/chNN_<topic>.py` from a template and opens it in your
editor. After that, **Read** and **Continue** open it too.

在 `main()` 中写计算，然后用 VS Code 的 **Run** (▶) 运行，或者：
Write your calculation in `main()`, then run it with VS Code's **Run** (▶), or:

```powershell
uv run "<library>/examples/<book>/ch03_aberrations.py"   # 路径写在脚本开头 / the path is in the script's header
```

`uv sync` 为这些脚本安装 `numpy`、`scipy`、`sympy` 和 `matplotlib`（`science` 组）。思路：重新计算例题并与书中答案对比；用 `sympy` 推导公式；用 `matplotlib` 画出结果随参数的变化；用 `scipy` 拟合数据。脚本只在你需要时创建。`.py` 文件从不用系统默认程序打开（那可能会运行它）。
`uv sync` installs `numpy`, `scipy`, `sympy` and `matplotlib` (the `science` group) for these
scripts. Ideas: recompute a worked example and print it next to the book's answer; re-derive an
equation with `sympy`; plot how a result changes with a parameter (`matplotlib`); fit a model to
data with `scipy`. Scripts are created only when you ask for one. A `.py` file is never opened
with its default app (that could run it).

**你自己的代码 / Your own code (`code/`).** 在多个脚本中都有用的函数，可以移到书库的 `code/` 文件夹，按学科分组（例如 `code/optics/paraxial.py`）。章节脚本可以直接导入（`from optics.paraxial import thin_lens`）：模板把 `code/` 加到了导入路径。在 `code/tests/` 中加测试，用书中的结果检验；`uv run pytest` 会和工具的测试一起运行它们。
When a function proves useful in more than one script, move it into your library's `code/`
folder, grouped by subject (e.g. `code/optics/paraxial.py`). Chapter scripts can import it
directly (`from optics.paraxial import thin_lens`): the template puts `code/` on the import
path. Add tests in `code/tests/`, checked against results from a book; `uv run pytest` runs them
along with the tool's tests.

---

## 11. 数据存储与安全 / Your data and keeping it safe

### 11.1 文件存放在哪里 / Where things are stored

本仓库分两部分：**工具**，以及它所处理的**书库**。
There are two parts: **the tool**, and **a library** it works on.

```
myLibrary/                   工具（本仓库）/ the tool (this repository)
├── scripts/                 工具本身 / the tool itself
├── tests/                   工具的测试 / the tool's tests (tests/browser/: in Edge)
├── local.toml               这台电脑打开哪个书库，以及设置（仅本地）/ which library this computer opens, and settings (local only)
├── .cache/reader/           PDF 阅读器、词典、预览库，所有书库共用（仅本地）/ viewer, dictionary, preview library, shared (local only)
└── library/                 作者的书库，作为示例 / the author's library, as an example

<your library>/              例如 / e.g. Documents/myLibrary Library
├── library.toml             书库名称和书架标签 / its name, and your shelf labels
├── catalog.csv              每个文档一行：id、名称、标题、作者、年份…… / one row per document: id, name, title, authors, year, ...
├── retired-documents.json   已合并或移除的文档 id / ids of documents merged or removed
├── books/<name>.pdf         书（从不进 Git）/ books (never in git)
├── papers/<name>.pdf        论文 / papers
├── theses/<name>.pdf        学位论文 / theses
├── notes/<name>/            每个文档：笔记、勾选、上次阅读、生词 / per document: notes, ticks, last read, vocabulary
├── notes/topics/            主题笔记 / topic notes
├── notes/vocabulary-review.json   复习进度 / review progress
├── notes/reading-log.json   阅读记录 / reading log
├── glossaries/              术语表 *.csv 和 glossaries.toml / glossaries and glossaries.toml
├── examples/<name>/         章节脚本 / chapter scripts
├── code/                    你的可复用代码和测试 / your reusable code and its tests
├── library.html             书库页面的静态副本（仅本地）/ static copy of the library page (local only)
├── archive/                 移除的文档、原始扫描件、标注前的原件、冲突副本（仅本地）/ removed items, original scans, pre-mark originals, conflict copies (local only)
├── .myLibrary/              工具的记录：迁移备份、操作日志（仅本地）/ the tool's records: migration backups, operation journals (local only)
└── .cache/                  搜索索引、章节页、OCR 结果（仅本地）/ search index, chapter pages, OCR results (local only)
```

| 内容 What | 位置 Where |
|---|---|
| PDF（含你的标注）PDFs (with your marks) | `books/`、`papers/`、`theses/` |
| Markdown 笔记 Markdown notes | `notes/<name>/*.md`、`notes/topics/*.md` |
| 图片 Images | 笔记中的图片还不显示（M5d）；你自己放在笔记文件夹中的图片就是普通文件。Images in notes aren't shown yet (M5d); images you put into a notes folder are ordinary files. |
| 设置 Settings | 工具文件夹的 `local.toml`；安装包中是 `%APPDATA%\myLibrary\settings.toml`。`local.toml` in the tool's folder; in the package, `%APPDATA%\myLibrary\settings.toml`. |
| 恢复草稿和界面偏好 Recovery drafts and view preferences | 浏览器的本地存储（这台电脑、这个浏览器、这个端口）。The browser's local storage (this PC, this browser, this port). |

**书从不进 Git**（有版权）：`.gitignore` 排除所有 PDF。Git 不会备份它们，请在别处（外部硬盘或私人云盘）保存一份 PDF。
**The books are never in git** (they're copyrighted): `.gitignore` excludes every PDF. Git doesn't
back them up, so keep a copy of your PDFs somewhere else (an external drive or a private cloud
folder).

### 11.2 哪些操作会修改 PDF / Which actions change your PDFs

| 操作 Action | 对 PDF 的影响 What happens to the PDF | 原件 The original |
|---|---|---|
| 添加 Adding | 改名为它的名称；上传的文件复制到书库，识别为论文或学位论文时移动到对应文件夹。Renamed to its name; uploads are copied in, and moved to `papers/` or `theses/` when recognised. | — |
| 标注 Marks | 整个 PDF 带标注重写。The whole PDF is rewritten with your marks. | 第一次标注前的版本保存**一次**在 `archive/before-marks/`。The version before your first mark is kept **once** in `archive/before-marks/`. |
| OCR | 加入隐形文字层后替换。Replaced with one that has an invisible text layer. | `archive/books/` |
| `add_bookmarks.py` | 加入书签（只对没有书签的书）。Bookmarks added (only to books without any). | `archive/books/` |
| 更好的重复副本 A better repeat | 新副本替换 PDF。The new copy replaces the PDF. | `archive/` |
| 阅读、查词、笔记、搜索 Reading, lookup, notes, search | 不修改。Never changed. | — |

### 11.3 哪些操作会删除数据 / Which operations can delete data

大多数操作是**移动到 `archive/`** 而不是删除。会真正删除数据的只有：
Most operations **move things to `archive/`** rather than delete them. These are the ones that
really delete:

| 操作 Operation | 删除什么 What it deletes | 保留什么 What it keeps |
|---|---|---|
| **⚙ Settings → Clear archive**（先询问，无法撤销 asks first, can't be undone） | `archive/` 中的文档（移除和重复的 PDF、原始扫描件、**标注前的原件**）和还没写过的笔记模板。Documents in `archive/` (removed and repeated PDFs, original scans, **pre-mark originals**) and note templates still exactly as generated. | 你的笔记、README、脚本、图片、`notes-conflicts/`、`marks-conflicts/` 以及其他文件，并列出来。Your notes, READMEs, scripts, images, `notes-conflicts/`, `marks-conflicts/` and other files, listed for you. |
| **💾 Back up** | 备份文件夹中超过 30 个的旧 zip（只删它自己的 zip，按名字识别）。Zips beyond the newest 30 in the backup folder (only its own zips, by name). | 最新 30 个 zip，以及 `PDFs/` 中的所有 PDF（从不删除）。The newest 30 zips, and every PDF in `PDFs/` (never deleted there). |
| 标注、OCR 保存 Saving marks, OCR | 覆盖书库中的 PDF（见 [11.2](#112-哪些操作会修改-pdf--which-actions-change-your-pdfs)）。Overwrite the library's PDF (see [11.2](#112-哪些操作会修改-pdf--which-actions-change-your-pdfs)). | 只保留第一次标注前的原件；之后的中间版本不保留。Only the original from before the first mark; later intermediate versions aren't kept. |
| **保留我的版本** (Keep mine) | 覆盖磁盘上的笔记。Overwrites the note on disk. | 被覆盖的版本先复制到 `archive/notes-conflicts/`。The overwritten version is copied to `archive/notes-conflicts/` first. |
| 恢复草稿 Recovery drafts | 保存后或 30 天后删除。Deleted once saved, or after 30 days. | — |

> **注意 Caution**：Clear archive 会删除标注前的原件和 OCR 前的原始扫描件，而这可能是它们**唯一**的未修改副本。如果你想保留未标注的原始 PDF，清理前先把它们复制到别处。
> Clear archive deletes the pre-mark originals and the pre-OCR scans, which may be your **only**
> unmodified copies. If you want to keep unmarked originals, copy them elsewhere before
> clearing.

> **注意 Caution**：两个书库名称相近（例如 "My library" 和 "My library 2"）且使用同一个备份文件夹时，💾 Back up 可能把对方的 zip 也算进 30 个并删除。每个书库请用单独的备份文件夹。
> If two libraries with similar names (e.g. "My library" and "My library 2") share one backup
> folder, 💾 Back up can count, and prune, each other's zips. Give each library its own backup
> folder.

### 11.4 备份与恢复 / Backup and restore

**💾 Back up（备份到文件夹 / to a folder）.** 在 **⚙ Settings** 中选择一个备份文件夹（OneDrive、U 盘、另一块硬盘），然后点击 **💾 Back up**：
Choose a backup folder in **⚙ Settings** (OneDrive, a USB stick, another disk), then click
**💾 Back up**:

- 生成一个带日期的 zip（`<书库名 library name> 2026-11-06 1530.zip`），包含笔记、阅读进度、生词和复习进度、主题笔记、术语表、书目、书架、脚本和代码；保留最新 30 个。
  It makes a dated zip (`<library name> 2026-11-06 1530.zip`) with your notes, reading progress,
  vocabulary and review progress, topic notes, glossaries, catalog, shelves, scripts and code;
  the newest 30 are kept.
- zip **不包含** PDF、`archive/`（包括冲突副本）、`.cache/` 和 `library.html`。
  The zip **leaves out** PDFs, `archive/` (including conflict copies), `.cache/` and
  `library.html`.
- 勾选 **Also keep a copy of the PDFs**（安装包中默认开启）时，PDF 复制到 zip 旁边的 `PDFs/` 中，以后只复制新的或修改过的；从书库移除的 PDF 在那里保留。
  With **Also keep a copy of the PDFs** (on in the package), the PDFs are copied into `PDFs/` next
  to the zips, and later only new or changed ones; a PDF removed from the library stays there.
- 设置了备份文件夹后，myLibrary 每天启动时自动备份一次（距上次超过 20 小时，且有改动时）。
  With a folder set, myLibrary also backs up by itself when it starts, once a day (more than
  20 hours since the last zip, and only if something changed).

```powershell
uv run scripts/folder_backup.py                    # 同 💾 Back up / like 💾 Back up
uv run scripts/folder_backup.py --to "D:\Backup" --pdfs
```

**从 zip 恢复 / Restoring from a zip**（每个 zip 中的 `RESTORE.txt` 也有说明 / also explained in
each zip's `RESTORE.txt`）:

1. 点击 **Quit** 停止 myLibrary。
   Stop myLibrary with **Quit**.
2. 把 zip 解压到书库文件夹（⚙ Settings 中的 Library folder）。
   Unzip it into your library folder (⚙ Settings, Library folder).
3. 把 `PDFs/` 中的 `books`、`papers`、`theses` 复制回书库文件夹。
   Copy `books`, `papers` and `theses` from the `PDFs/` folder back into the library folder.
4. 启动 myLibrary，在书库页面点击 **⟳ Refresh**。
   Start myLibrary and click **⟳ Refresh** on the library page.

解压会覆盖书库中同名的文件：如果书库中有比备份更新的内容，先把整个书库文件夹复制一份。
Unzipping overwrites files of the same name in the library: if the library holds anything newer
than the backup, copy the whole library folder somewhere first.

**☁ Back up（备份到 GitHub / to GitHub）.** 书库在有远程仓库的 Git 仓库中时，一键提交并推送**只有书库文件夹**（笔记、阅读进度、生词、书架、主题笔记、术语表、书目；从不包括 PDF，也从不包括仓库中的其他改动）。如果有未推送的**代码**提交，它会停止，请你自己推送；连不上 GitHub 时会提示（改动仍保存在本地）。从不等待密码输入。
When the library is in a git repository with a remote, one click commits and pushes **only the
library folder** (notes, reading progress, vocabulary, shelves, topic notes, glossaries,
catalog; never PDFs, and never other changes in the repository). If there are unpushed *code*
commits, it stops and asks you to push those yourself; if GitHub can't be reached, it says so
(your changes stay saved locally). It never waits for a password.

```powershell
uv run scripts/backup.py   # 同 ☁ Back up / like ☁ Back up
```

> 限制 Limitation：☁ Back up 遇到含中文等非 ASCII 字符的文件名时会拒绝备份。
> ☁ Back up refuses to back up when a library file has a non-ASCII (e.g. Chinese) name.

### 11.5 移动或恢复书库之前 / Before moving or restoring a library

1. 在所有标签页中保存笔记（状态为 **已保存** Saved），等待标注显示 **标注已保存** (Marks saved)。恢复草稿属于浏览器和端口，不会随书库移动。
   Save your notes in every tab (status **已保存** Saved) and wait for **标注已保存** (Marks
   saved). Recovery drafts belong to the browser and port; they don't move with the library.
2. 关闭在外部编辑器中打开的笔记，然后点击 **Quit**。
   Close notes open in your outside editor, then click **Quit**.
3. 做一次完整备份：💾 Back up 加上 PDF，或者直接复制整个书库文件夹。
   Make a full backup: 💾 Back up with the PDFs, or simply copy the whole library folder.
4. 移动**整个**文件夹，包括隐藏的 `.myLibrary/`、`catalog.csv` 和 `retired-documents.json`。
   Move the **whole** folder, including the hidden `.myLibrary/`, `catalog.csv` and
   `retired-documents.json`.
5. 在 **⚙ Settings → Library folder** 中选择新位置（或编辑 `local.toml`，或用 `--library`）。在 Settings 中选择另一个文件夹会打开那里的书库（或新建一个空书库），**不会移动**当前书库的文件。
   Choose the new place in **⚙ Settings → Library folder** (or edit `local.toml`, or use
   `--library`). Choosing another folder in Settings opens the library there (or starts a new,
   empty one); it **doesn't move** the current library's files.
6. 启动后检查几本书，点击 **⟳ Refresh**。
   After starting, check a few books and click **⟳ Refresh**.

### 11.6 永久 id 与旧书库迁移 / Permanent ids and migrating an old library

myLibrary 0.2 之前（没有 id）的书库会被拒绝打开，从不悄悄升级。由你自己转换一次：
A library from before ids (myLibrary 0.2) is refused, never upgraded silently. Convert it once,
yourself:

```powershell
uv run scripts/migrate_ids.py --library "<folder>"            # 试运行：显示每一处修改 / dry run: shows every change
uv run scripts/migrate_ids.py --library "<folder>" --apply    # 执行（先退出 myLibrary）/ do it (quit myLibrary first)
uv run scripts/migrate_ids.py --library "<folder>" --check    # 确认 id 正确 / confirm the ids are in order
```

它给每个条目一个 id，把阅读记录改为按 id 存储，保留所有数值。PDF、文件名、笔记、生词和标注保持不变。原文件保存在书库的 `.myLibrary/migrations/`。如果被中断，`--resume` 完成它，`--rollback` 恢复原文件；在此之前 myLibrary 不会打开这个书库。
It gives every entry an id and moves your reading log to ids, keeping every value. PDFs, file
names, notes, words and marks stay as they are. The originals are kept in the library's
`.myLibrary/migrations/`. If it's interrupted, `--resume` finishes it and `--rollback` puts the
old files back; until then myLibrary won't open the library.

### 11.7 可以安全删除的缓存 / Caches that are safe to delete

| 内容 What | 位置 Where | 由谁重建 Rebuilt by |
|---|---|---|
| PDF 阅读器、词典、预览库 Viewer, dictionary, preview library | 工具的 `.cache/reader/` / the tool's `.cache/reader/` | 服务器启动时，或 `uv run scripts/reader.py --setup`。The server on start, or `uv run scripts/reader.py --setup`. |
| 全文索引 Full-text index | 书库的 `.cache/books.db` / the library's `.cache/books.db` | 服务器启动时。The server on start. |
| 章节起始页 Chapter start pages | 书库的 `.cache/chapter_pages.json` | 服务器，第一次使用时。The server, on first use. |
| OCR 结果 OCR results | 书库的 `.cache/ocr/` | `ocr_pdf.py` / `add_book.py`（慢：重新 OCR / slow: re-runs OCR） |

**你自己的成果**（请备份，不要删除）：书库的 `notes/`、`examples/`、`code/`、`glossaries/`、`catalog.csv`、`library.toml`，以及 PDF 中的标注。可以用 Git 在单独的仓库（私有或公开）中管理它们。
**Your own work** (back it up, never delete it): the library's `notes/`, `examples/`, `code/`,
`glossaries/`, `catalog.csv` and `library.toml`, and the marks in your PDFs. You can version
them with git in their own repository (private or public).

---

## 12. 设置 / Settings

点击书库页面顶部的 **⚙ Settings**：
Click **⚙ Settings** at the top of the library page:

| 设置 Setting | 作用 What it does |
|---|---|
| **Library folder** | 书和笔记保存的位置。**Choose…** 打开 Windows 文件夹对话框。选择另一个文件夹会打开那里的书库（或新建一个空书库），当前书库保持不动；服务器自动重启。Where your books and notes are kept. **Choose…** opens Windows' folder dialog. Another folder opens the library there (or starts a new, empty one); the current library stays where it is; the server restarts by itself. |
| **Open notes with** | 用什么程序打开笔记：`.md` 文件的默认程序（例如 Typora、Obsidian）、Notepad、VS Code，或 **My own command…**（`{file}` 代表笔记路径）。Which program opens notes: the app set for `.md` files (e.g. Typora, Obsidian), Notepad, VS Code, or **My own command…** (`{file}` stands for the note's path). |
| **Show the Python features** | 每章的 **Script** 按钮（[10.4](#104-章节脚本--chapter-scripts)）。The **Script** button per chapter. |
| **💾 Backup folder** + **Choose…** | 💾 Back up 的 zip 保存位置（必须是完整路径）。Where 💾 Back up puts its zips (an absolute path). |
| **Also keep a copy of the PDFs** | 同时把 PDF 复制到备份文件夹（[11.4](#114-备份与恢复--backup-and-restore)）。Also copy the PDFs into the backup folder. |
| **OpenAlex key (optional)** | 你自己的 OpenAlex 密钥（[8.4](#84-openalex-与密钥--openalex-and-its-key)）。Your own OpenAlex key. |
| **Archive** → **Clear archive** | 显示 `archive/` 的大小，永久删除其中的文档（[11.3](#113-哪些操作会删除数据--which-operations-can-delete-data)）。Shows how much `archive/` holds and deletes its documents for good. |

设置保存在工具文件夹的 `local.toml` 中（安装包中是 `%APPDATA%\myLibrary\settings.toml`）。例如：
Settings are saved in `local.toml` in the tool's folder (in the package:
`%APPDATA%\myLibrary\settings.toml`). For example:

```toml
library = "D:/Study/My Library"    # 相对路径相对于工具文件夹 / a relative path is relative to the tool's folder
editor = "custom"                  # vscode / notepad / system / custom
editor_command = "notepad++ {file}"
python_features = true
backup_folder = "D:/Backup/myLibrary"
backup_pdfs = true
```

设置文件无法读取时，myLibrary 会停止并说明哪一行有问题，而不是用默认值打开另一个书库。
If the settings file can't be read, myLibrary stops and says which line is wrong, rather than
opening another library with default settings.

**打开哪个书库 / Which library opens**, in this order:

1. 任何命令的 `--library <folder>` / `--library <folder>` on any command;
2. 环境变量 `MYLIBRARY_LIBRARY` / the `MYLIBRARY_LIBRARY` environment variable;
3. 设置文件中的 `library` / `library` in the settings file;
4. 都没有：首次启动创建 `Documents\myLibrary Library` 并写入设置。
   None of these: the first start creates `Documents\myLibrary Library` and saves it.

环境变量 `MYLIBRARY_SETTINGS` 可以指定另一个设置文件（文件必须存在；浏览器测试用它）。设置了 `MYLIBRARY_LIBRARY` 时，在 Settings 中更换书库不会生效（服务器重启后仍是旧书库）。
The `MYLIBRARY_SETTINGS` environment variable names another settings file instead (it must
exist; the browser tests use it). With `MYLIBRARY_LIBRARY` set, changing the library in Settings
doesn't take effect (the server restarts into the old library).

---

## 13. 命令参考 / Command reference

在工具文件夹中运行（PowerShell、终端或 VS Code 终端）。每个命令都作用于你的书库；加 `--library <folder>` 使用另一个书库（`migrate_ids.py` 必须指定它）。
Run these in the tool's folder (PowerShell, a terminal or the VS Code terminal). Every command
works on your library; add `--library <folder>` to use another one (`migrate_ids.py` requires
it).

| 命令 Command | 作用 What it does |
|---|---|
| `uv run scripts/library_server.py` | 启动书库（同快捷方式）；`--port 8766` 换端口，`--no-browser` 不打开标签页，`--no-download` 启动时从不下载阅读器或词典。Start the library (like the shortcut); `--port 8766` another port, `--no-browser` no new tab, `--no-download` never fetch the viewer or dictionary at start. |
| `uv run scripts/make_shortcut.py` | （重新）创建桌面和开始菜单快捷方式（Windows）。(Re)create the Desktop and Start menu shortcuts (Windows). |
| `uv run scripts/add_book.py --dry-run` / 无参数 no flag | 预览 / 登记新文档（[4.4](#44-从终端添加--adding-from-the-terminal)）。Preview / register new documents. |
| `uv run scripts/add_book.py <file> --author .. --year .. --title ..` | 指定信息添加一个文件。Add one file with given details. |
| `uv run scripts/add_book.py --refresh-chapters` | 重新读取章节列表（保留笔记）。Re-read chapter lists (keeps your notes). |
| `uv run scripts/add_book.py --refresh-keywords` | 补充论文和学位论文的关键词。Fill in keywords for papers and theses. |
| `uv run scripts/add_book.py --remove <name or id>` | 把文档移到 `archive/`（`--dry-run` 预览，`--yes` 不询问）。Move a document to `archive/` (`--dry-run` to preview, `--yes` not to ask). |
| `uv run scripts/add_book.py --offline` | 不查询 Open Library。Skip the Open Library lookup. |
| `uv run scripts/ocr_pdf.py <pdf>` | 为扫描件添加 OCR 文字层（`--yes` 不询问）。Add an OCR text layer to a scan (`--yes` not to ask). |
| `uv run scripts/add_bookmarks.py [pdf]` | 为没有书签的书添加书签（`--dry-run`、`--yes`）。Add bookmarks to books without any. |
| `uv run scripts/reader.py <word or phrase>` | 在终端中查词。Look up a word in the terminal. |
| `uv run scripts/reader.py --setup` | 下载 PDF 阅读器、词典和预览库。Download the PDF viewer, dictionary and preview library. |
| `uv run scripts/reader.py --setup-viewer` | 只下载 PDF 阅读器（PDF.js，固定版本，校验 checksum）。Only the PDF viewer (PDF.js, pinned, checksum-verified). |
| `uv run scripts/reader.py --setup-preview` | 只下载笔记预览库（markdown-it，固定版本，校验 checksum）。Only the notes' preview (markdown-it, pinned, checksum-verified). |
| `uv run scripts/book_search.py <term>` | 在所有书中搜索（`--status` 显示索引状态）。Search all books (`--status` for the index status). |
| `uv run scripts/subjects.py [--apply]` | 显示 / 记录学科（[3.5](#35-学科与书架--subjects-and-shelves)）。Show / record subjects. |
| `uv run scripts/shelves.py [--apply]` | 显示 / 应用书架建议。Show / apply shelf suggestions. |
| `uv run scripts/library_page.py` | 写出静态的 `library.html`。Write the static `library.html`. |
| `uv run scripts/folder_backup.py [--to FOLDER] [--pdfs]` | 备份到文件夹（同 💾 Back up）。Back up to a folder (like 💾 Back up). |
| `uv run scripts/backup.py` | 备份到 GitHub（同 ☁ Back up）。Back up to GitHub (like ☁ Back up). |
| `uv run scripts/migrate_ids.py --library <folder> [--apply \| --resume \| --rollback \| --check]` | 转换 0.2 之前的书库（[11.6](#116-永久-id-与旧书库迁移--permanent-ids-and-migrating-an-old-library)）。Convert a pre-0.2 library. |
| `uv run scripts/build_package.py` | 构建安装包 `dist/myLibrary-<version>-win64.zip`。Build the package. |
| `uv run "<library>/examples/<book>/chNN_<topic>.py"` | 运行章节脚本。Run a chapter script. |
| `uv sync` | 创建或更新 Python 环境（`--group optics` 加入光学包）。Create or update the Python environment (`--group optics` adds the optics packages). |
| `uv add <package>` | 添加一个 Python 包。Add a Python package. |

书库的 `catalog.csv` 也可以用 Excel 打开，或在终端中搜索：
Your library's `catalog.csv` also opens in Excel, or search it from the terminal:

```powershell
Select-String -Path "<library>/catalog.csv" -Pattern aberration
```

---

## 14. 常见问题 / Troubleshooting and FAQ

**更新后看不到新功能。** 服务器可能还在运行旧代码：关闭它的最小化窗口（或点击 Quit）再启动。弹窗的改动只需刷新书的标签页（F5）。
**Something new doesn't show up after an update.** The server may still be running old code:
close its minimized window (or click Quit) and start it again. Changes to the popup only need a
reload of the book tab (F5).

**双击没有反应 / 书打开时没有弹窗。** 首次启动时阅读器和词典可能还在下载（看服务器窗口），或者书是从别处以普通 PDF 打开的。请从书库页面打开。
**Double-clicking does nothing / books open without the popup.** The viewer and dictionary may
still be downloading on first start (see the server window), or the book was opened as a plain
PDF from somewhere else. Open it from the library page.

**"Port 8765 is used by another program"。** 其他程序占用了这个端口：`uv run scripts/library_server.py --port 8766`。
Something else uses that port: start with `uv run scripts/library_server.py --port 8766`.

**"Another myLibrary is running … with a different library"。** 另一个 myLibrary 正在用别的书库运行：在它的页面上点 Quit，或用另一个端口启动。
Another myLibrary is running with a different library: Quit it from its page, or start this one
on another port.

**笔记显示 需要重新载入 (Reload needed)。** myLibrary 重启过。按 F5；你的文字会作为恢复草稿提供。
**The notes say 需要重新载入 (Reload needed).** myLibrary was restarted. Press F5; your text is
offered as a recovery draft.

**标注显示 标注没保存 (Marks not saved)。** 通常是 PDF 在别的程序中打开着：关闭它，然后点 **重试** (Retry)。
**Marks say 标注没保存 (Marks not saved).** Usually the PDF is open in another program: close it
there, then click **重试** (Retry).

**预览只显示纯文本。** 预览库还没安装：`uv run scripts/reader.py --setup-preview`，然后刷新标签页。
**The preview shows only plain text.** The preview library isn't installed:
`uv run scripts/reader.py --setup-preview`, then reload the tab.

**公式或图片在预览中没有显示。** 这是预期的：数学渲染（M5b）和图片（M5d）还没有实现（[9.10](#910-计划中的笔记功能--planned-notes-features)）。
**Maths or images don't show in the preview.** Expected: maths rendering (M5b) and images (M5d)
aren't implemented yet ([9.10](#910-计划中的笔记功能--planned-notes-features)).

**Continue 或 Read 打开了错误的页面或章节。** 章节起始页只查找一次并缓存。从书库的 `.cache/chapter_pages.json` 中删除这本书的条目（或整个文件）并重启服务器；如果章节**列表**本身错了，运行 `uv run scripts/add_book.py --refresh-chapters`。
**Continue or Read opens the wrong page or chapter.** Chapter start pages are found once and
cached. Delete the book's entry from the library's `.cache/chapter_pages.json` (or the whole
file) and restart the server; if the chapter *list* itself is wrong, run
`uv run scripts/add_book.py --refresh-chapters`.

**扫描版中选中了错误的字母。** OCR 文字的正常现象：在弹窗顶部改正单词并按 Enter（[6.1](#61-查词方式--ways-to-look-something-up)）。
**The selection in a scanned book catches the wrong letters.** Expected with OCR text: edit the
word at the top of the popup and press Enter ([6.1](#61-查词方式--ways-to-look-something-up)).

**词典给出日常含义，而不是学科含义。** 把这个术语加入术语表（**＋ 加入术语表** Add to glossary），填写你在书中看到的中文术语。
**The dictionary gives the everyday meaning, not my subject's.** Add the term to your glossary
(**＋ 加入术语表**, Add to glossary) with the Chinese term you found in your books.

**在我的书中 (In my books) 说索引还在建立。** 服务器启动时在后台为新的或修改过的书建立索引；几秒后再试。
**在我的书中 (In my books) says the index is still being built.** The server indexes new or
changed books in the background when it starts; try again in a few seconds.

**学科没有出现。** OpenAlex 的免费共享额度可能用完了：稍后点 ⟳ Refresh，或在 Settings 中填入自己的 OpenAlex 密钥（[8.4](#84-openalex-与密钥--openalex-and-its-key)）。
**Subjects don't appear.** OpenAlex's shared free budget may be used up: click ⟳ Refresh later,
or add your own OpenAlex key in Settings ([8.4](#84-openalex-与密钥--openalex-and-its-key)).

**`uv sync` 删除了光学包。** 它们是可选组：`uv sync --group optics`。
**`uv sync` removed the optics packages.** They're an optional group: `uv sync --group optics`.

**会通过网络发送什么？** 见 [1.7](#17-离线使用与需要联网的功能--offline-use-and-what-needs-the-internet)。查词、书中搜索、笔记和其他一切都在你的电脑上运行。
**Is anything sent over the internet?** See
[1.7](#17-离线使用与需要联网的功能--offline-use-and-what-needs-the-internet). Word lookups, book
search, notes and everything else run on your computer.

**其他语言？** 词典是英译中（ECDICT）。术语表适用于任何学科，但释义用中文写（`zh` 列）。
**Other languages?** The dictionary is English → Chinese (ECDICT). Glossaries work for any
subject, but their meanings are written in Chinese (the `zh` column).

---

## 15. 功能状态：已实现、已验证、计划中 / Feature status: implemented, verified, planned

"自动测试"指每次推送时在 Windows CI 上运行的测试。
"Automated tests" means the tests CI runs on Windows for every push.

| 功能 Feature | 状态 Status |
|---|---|
| 阅读器：查词、标注保存与冲突、阅读进度、预览标签页 Reader: lookup, saving marks and conflicts, reading progress, preview tabs | 已实现；Python 测试和 Microsoft Edge 中的浏览器测试（CI）。Implemented; Python tests and browser tests in Microsoft Edge (CI). |
| 笔记面板：编辑、自动保存、冲突、恢复草稿、只读、布局 Notes panel: editing, autosave, conflicts, drafts, read-only, layout | 已实现；浏览器测试（CI）。Implemented; browser tests (CI). |
| 笔记预览：源码 / 预览 / 分屏（M5a）Notes preview: Source / Preview / Split (M5a) | 已实现；有 Python 和浏览器测试。安装包中已包含预览库，但还没有在安装包中做过浏览器离线测试。Implemented; Python and browser tests. The package includes the preview library, but the preview hasn't been browser-tested offline inside the package. |
| 添加、识别、重复、移除、重命名恢复、OCR、备份脚本、id 迁移 Adding, identification, repeats, removing, rename recovery, OCR, backup scripts, id migration | 已实现；Python 测试（CI）。Implemented; Python tests (CI). |
| 书库页面的 JavaScript（按钮、对话框、筛选、复习卡片）Library page JavaScript (buttons, dialogs, filters, review cards) | 已实现；**没有自动测试**，在浏览器中手动检查。Implemented; **no automated tests**, checked by hand in the browser. |
| 现成安装包 The ready-to-use package | 可以构建；**没有自动测试**，在干净的环境中手动测试启动和退出。Builds; **no automated tests**, start and quit checked by hand in a clean environment. |
| macOS / Linux | 未测试。Not tested. |
| M5b 数学公式 Maths (KaTeX) | **计划中，未实现。** Planned, not implemented. |
| M5c 格式工具栏和排版设置 Formatting toolbar and display settings | **计划中，未实现。** Planned, not implemented. |
| M5d 粘贴截图和图片 Pasted screenshots and images | **计划中，未实现。** Planned, not implemented. |
| 以后：截图识别为可编辑的公式和表格 Later: screenshots into editable equations and tables | **计划中，未实现。** Planned, not implemented. |

更多计划（引用到笔记、从笔记回到 PDF 段落、修正书目信息和章节、桌面应用）见 [ROADMAP.md](ROADMAP.md)；产品目标和原则见 [DEVELOPMENT_SPEC.md](DEVELOPMENT_SPEC.md)。
More plans (quote to note, back from a note to the passage, correcting details and chapters, a
desktop app) are in [ROADMAP.md](ROADMAP.md); the product goals and principles are in
[DEVELOPMENT_SPEC.md](DEVELOPMENT_SPEC.md).

---

## 16. 用于你自己的学科 / Use it for your own subject

1. **书架：** 不需要做什么。每个条目添加时都会放到它的学科书架上（[3.5](#35-学科与书架--subjects-and-shelves)）。可以在书库的 `library.toml` 中给书架起中文名，或用 **Shelves** 按钮添加你自己的书架。
   **Shelves:** nothing to do. Every item gets its subject's shelf when it's added
   ([3.5](#35-学科与书架--subjects-and-shelves)); give a shelf a Chinese name in your library's
   `library.toml` if you like, or add your own with the **Shelves** button.
2. **术语表：** 为你的学科建一个，例如书库中的 `glossaries/biology.csv`，第一行是 `term,zh,note,definition`（[第 7 节](#7-术语表--glossaries)）。或者直接开始阅读：第一次从弹窗加入术语时会创建 `glossaries/my-terms.csv`。示例可以复制本仓库的 `library/glossaries/optics.csv`。
   **Glossaries:** create one for your subject, e.g. `glossaries/biology.csv` in your library,
   starting with the line `term,zh,note,definition` ([section 7](#7-术语表--glossaries)). Or just
   start reading: the first term you add from the popup creates `glossaries/my-terms.csv`. For
   an example, copy `library/glossaries/optics.csv` from this repository.
3. **Python 包：** 用 `uv add <package>` 添加章节脚本需要的包。
   **Packages:** add the Python packages your chapter scripts need with `uv add <package>`.

本仓库的 `library/` 是作者的书库（光学设计），作为真实示例：看看一个用了很久的书库是什么样子。请保持原样；你的书库在单独的文件夹中，所以 `git pull` 从不会把两者混在一起。
This repository's `library/` is the author's library (optical design), included as a real
example: browse it to see what a well-used library looks like. Leave it as it is; your library
lives in its own folder, so `git pull` never mixes the two.

---

## 17. 开发与测试 / Development and testing

```powershell
uv sync                          # Python + 包 / packages (dev and science groups)
uv run pytest                    # 测试（不含浏览器测试）/ the tests (not the browser tests)
uv run ruff check .              # 代码检查 / lint
uv run ruff format --check .     # 格式检查 / format check (uv run ruff format . to fix)
```

浏览器测试在 Microsoft Edge 中运行阅读器，每个测试使用自己的临时书库、设置和服务器：
The browser tests run the reader in Microsoft Edge, each test on its own temporary library,
settings and server:

```powershell
uv sync --group browser
uv run scripts/reader.py --setup-viewer
uv run scripts/reader.py --setup-preview
uv run pytest tests/browser                   # --headed 观看 / to watch
uv run pytest tests/browser --notes-closed    # 笔记面板关闭时 / with the notes panel closed
uv run pytest tests/browser --tracing retain-on-failure   # 失败时的追踪在 test-results/ / traces in test-results/
```

- CI（`.github/workflows/tests.yml`）在 Windows 上对每次推送和拉取请求运行代码检查、格式检查、测试和浏览器测试。
  CI (`.github/workflows/tests.yml`) runs lint, format, tests and the browser tests on Windows
  for every push and pull request.
- 测试从不使用真实书库：见 `tests/conftest.py`。
  Tests never use a real library: see `tests/conftest.py`.
- 书库页面的 JavaScript 还没有测试：修改后用 `uv run scripts/library_server.py --port 8766` 在浏览器中试一试，并说明你检查了什么。
  The library page's JavaScript has no tests yet: after changing it, try it in the browser with
  `uv run scripts/library_server.py --port 8766` and say what you checked.
- 项目规则（中文必须配英文、工具保持学科中立、不提交书籍、通过 `safe_io` 写文件）见 [CONTRIBUTING.md](CONTRIBUTING.md) 和 [CLAUDE.md](CLAUDE.md)。
  Project rules (Chinese always with English, the tool stays subject-neutral, never commit books,
  write files through `safe_io`) are in [CONTRIBUTING.md](CONTRIBUTING.md) and
  [CLAUDE.md](CLAUDE.md).

---

## 18. 许可、贡献与安装包 / License, contributing and the package

**许可：[PolyForm Noncommercial 1.0.0](LICENSE)。** 简单地说（以许可证原文为准）：
**License: [PolyForm Noncommercial 1.0.0](LICENSE).** In plain words (the license text is what
counts):

- **可以**：为任何**非商业**目的阅读、使用、修改和分享 myLibrary：个人学习、业余项目、研究、教学，或学校、慈善机构和公共机构使用。
  **You may** read, use, change and share myLibrary for any **non-commercial** purpose: personal
  study, hobby projects, research, teaching, or use by schools, charities and public
  institutions.
- **不可以**：用于商业目的，例如出售它或修改后的版本，或在付费产品或服务中使用。商业用途需要作者的书面许可。
  **You may not** use it for commercial purposes: for example, selling it or a modified version,
  or using it in a paid product or service. Commercial use needs written permission from the
  author.
- 分享时请附上 [LICENSE](LICENSE) 文件（包括其中的 "Required Notice" 一行）。
  If you share it, include the [LICENSE](LICENSE) file (with its "Required Notice" line).

**现成安装包（9.9 元人民币）。** 按上面的说明自己安装，非商业用途免费。安装包省去安装步骤：解压后双击即可；包含 Python、PDF 阅读器、词典和预览库（首次启动即可离线使用），不需要命令行。它有阅读和学习的全部功能（添加、OCR、查词、术语表、书架、笔记、进度、备份），但没有 Python 章节脚本。获取方式：即将推出。
**Ready-to-use package (9.9 RMB).** Setting myLibrary up yourself, as described above, is free
for non-commercial use. The package saves you the setup: unzip it and double-click; Python, the
PDF viewer, the dictionary and the preview library are included (it works offline from the
first start), and there's no command line. It has everything for reading and studying (adding,
OCR, lookup, glossaries, shelves, notes, progress, backup) but not the Python chapter scripts.
Where to get it: coming soon.

构建（Windows）：`uv run scripts/build_package.py` 用 `package/`（启动器、双语说明、许可证）和本仓库生成 `dist/myLibrary-<version>-win64.zip`（约 170 MB）；安装包用 `package.toml` 标记自己。
Building it (Windows): `uv run scripts/build_package.py` makes
`dist/myLibrary-<version>-win64.zip` (about 170 MB) from `package/` (launcher, bilingual guide,
licenses) and this repository; the package marks itself with a `package.toml`.

**贡献。** 欢迎任何人帮忙：报告问题、提出想法、修复、添加功能，或为新学科添加术语表。Fork 本仓库，在分支上修改，然后提交拉取请求；[CONTRIBUTING.md](CONTRIBUTING.md) 说明了步骤、项目规则和贡献者条款（贡献按本项目的许可授权，另加一项允许作者把它们包含在付费安装包中的许可）。
**Contributing.** Everyone is welcome to help: report bugs, suggest ideas, fix things, add
features or glossaries for new subjects. Fork the repository, make your change on a branch, and
open a pull request; [CONTRIBUTING.md](CONTRIBUTING.md) explains the steps, the project rules
and the contributor terms (contributions are licensed like the project, plus a license that lets
the author include them in the paid package).

---

## 19. 使用的组件 / Built with

- **[PDF.js](https://mozilla.github.io/pdf.js/)**（Mozilla）：PDF 阅读器 / the PDF viewer
- **[ECDICT](https://github.com/skywind3000/ECDICT)**：离线英汉词典 / the offline English–Chinese dictionary
- **[markdown-it](https://github.com/markdown-it/markdown-it)**：笔记预览 / the notes' preview
- **numpy / scipy / sympy / matplotlib**（`science` 组 group）：章节脚本中的数值计算、符号运算和绘图 / numerics, symbolic maths and plots in chapter scripts
- **pypdf / pypdfium2 / rapidocr / onnxruntime / reportlab / cryptography**：读取 PDF、扫描件 OCR、写入文字层、打开加密的出版社 PDF / reading PDFs, OCR for scans, writing text layers, opening encrypted publisher PDFs
- **optiland / rayoptics**（可选 `optics` 组 optional group）：光学示例的镜头设计 / lens design for the optics example

所有第三方组件及其许可证：[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
All third-party components and their licenses: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
