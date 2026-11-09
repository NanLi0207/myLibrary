# myLibrary 产品与技术规格 / Product and technical specification

本文件说明 myLibrary 要成为什么、必须满足哪些要求、怎样验收。**当前计划和进度**见 [ROADMAP.md](ROADMAP.md)；
**第一版规格**（原始需求说明）原样保留在 [docs/history/DEVELOPMENT_SPEC_v1.md](docs/history/DEVELOPMENT_SPEC_v1.md)，
其中仍有效的要求已并入本文件。
This file says what myLibrary is meant to become, which requirements it must meet and how they
are accepted. The **current plan and progress** are in [ROADMAP.md](ROADMAP.md); the **first
specification** (the original requirements brief) is kept unchanged in
[docs/history/DEVELOPMENT_SPEC_v1.md](docs/history/DEVELOPMENT_SPEC_v1.md), and its requirements
that still apply are carried into this file.

**标记 / Markers:** **[已有 Existing]** = 当前代码中已实现（2026-11-09，`d6c1a5d`）implemented in the current
code · **[计划 Planned]** = 尚未实现，见 ROADMAP not implemented yet, see the ROADMAP · **[建议 Proposed]** =
本文件提出，需批准 proposed here, needs approval.

---

## 1. 产品概述 / Product overview

myLibrary 是一个本地优先的学习工作空间，用于从自己的 PDF（书、论文、学位论文，任何学科）中学习：阅读、查词、做笔记、记录
进度，并可选地用代码验证所学。它是 Python 后端加浏览器界面（PDF.js 阅读器、Markdown 笔记、本地文件），只在本机
127.0.0.1 上运行。书库是一个普通文件夹，属于用户。
myLibrary is a local-first learning workspace for studying from your own PDFs (books, papers,
theses, any subject): read, look up words, take notes, track progress, and optionally verify
what you learned with code. It is a Python backend with a browser interface (the PDF.js reader,
Markdown notes, local files), running only on the computer itself (127.0.0.1). A library is an
ordinary folder that belongs to the user.

---

## 2. 产品愿景与定位 / Product vision and positioning

**myLibrary — 阅读、理解、实践、验证、掌握。**
**myLibrary — Read. Understand. Implement. Verify. Remember.**

一个将文档、笔记、知识与可执行代码连接起来的本地优先学习与研究工作空间。
A local-first learning and research workspace connecting documents, notes, knowledge and
executable code.

### 2.1 三个支柱 / Three pillars

| 支柱 Pillar | 含义 Meaning | 现状 Status |
|---|---|---|
| **学习 Learning** | 理解并记住：生词与术语、复习、阅读记录、主题。Understand and remember: vocabulary and terms, review, reading log, topics. | [已有 Existing] 术语表、英汉词典、生词复习卡片、阅读记录、主题笔记 glossaries, English–Chinese dictionary, vocabulary review cards, reading log, topic notes |
| **阅读 Reading** | 专注、可靠地读 PDF。Focused, reliable PDF reading. | [已有 Existing] PDF.js 阅读器、继续阅读、标注保存、全文搜索、预览标签页 PDF.js reader, resume, saving marks, full-text search, preview tabs |
| **笔记 Note-taking** | 在 PDF 旁边用普通 Markdown 写自己的话。Your own words in plain Markdown beside the PDF. | [已有 Existing] 笔记面板（编辑、自动保存、冲突、草稿、预览）notes panel (editing, autosave, conflicts, drafts, preview)；[计划 Planned] 公式、格式、截图、引用到笔记、回到原文 maths, formatting, screenshots, quote to note, back to the passage |

**可执行学习（可选）/ Executable learning (optional).** 一个重要的差异化能力，尤其适合工程、数学、物理、编程、数据分析
和科研；但它是可选的，从不成为必经之路，也不盖过三个支柱。An important differentiator, especially for
engineering, mathematics, physics, programming, data analysis and research; but it is optional,
never a required path, and never overshadows the three pillars (section 7).

### 2.2 学习流程 / The learning workflow

**收集 → 阅读 → 标注 → 理解 → 整理 → 实践 → 验证 → 复习 → 回溯原文**
**Collect → Read → Annotate → Understand → Organize → Implement → Verify → Review → Revisit sources**

不是每个用户都需要每一步。阅读和记笔记必须简单，可以单独使用。
Not every user needs every step. Reading and note-taking must stay simple and usable on their
own.

### 2.3 核心原则 / Core principles

1. **本地优先、离线优先 / Local-first, offline-first.** 阅读、导航、笔记、搜索、生词在没有网络时都能用；在线功能（元数据
   查找、主题、在线查找、以后的翻译和 AI）都是可选的。Reading, navigation, notes, search and vocabulary
   work without a network; online features (metadata lookup, subjects, Find online, later
   translation and AI) are optional.
2. **用户拥有自己的文档、笔记和代码 / The user owns documents, notes and code.**
3. **开放、可移植的格式 / Open, portable formats:** PDF、Markdown、CSV、JSON、TOML、Python。
4. **稳定的文档身份和来源引用 / Stable document identity and source references:** 永久 UUID（第 9 节）。
5. **可靠的保存、恢复和迁移 / Reliable saving, recovery and migration** (section 10).
6. **日常操作简单，高级功能可选 / Simple everyday use, advanced features optional.**
7. **可验证的知识和精确的来源 / Verifiable knowledge, precise sources.**
8. **通过外部开发工具实现可执行学习 / Executable learning through external development tools.**
9. **不强制云账户、订阅或 AI 提供商 / No mandatory cloud account, subscription or AI provider.**
10. **渐进开发，不做不必要的框架重写 / Incremental development, no needless framework rewrites:** 保持 Python
    后端、本地网页界面、PDF.js、Markdown 笔记和 UUID 身份，除非有具体理由并经批准。Keep the Python backend,
    local web interface, PDF.js, Markdown notes and UUID identity unless a specific change is
    justified and approved.
11. **学科中立 / Subject-neutral:** 工具（`scripts/`）不假设任何学科；学科知识属于书库（术语表、`code/`）。The tool
    (`scripts/`) assumes no subject; subject knowledge belongs to a library (glossaries, `code/`).
12. **已实现与计划分清 / Implemented and planned kept apart** in every document.

---

## 3. 目标用户与应用场景 / Target users and use cases

| 用户 User | 场景 Use case | 主要功能 Main features |
|---|---|---|
| 阅读英文教材的中文学习者 Chinese learners reading English textbooks | 读书、查专业术语、记生词、每章笔记 read, look up terms, keep vocabulary, notes per chapter | 术语表优先的查词、生词复习、章节笔记 glossary-first lookup, vocabulary review, chapter notes |
| 研究生和科研人员 Graduate students and researchers | 读论文、比较不同来源、引用 read papers, compare sources, cite | 论文识别（DOI、arXiv）、全文搜索、主题笔记、BibTeX；[计划] 精确来源链接 paper identification (DOI, arXiv), full-text search, topic notes, BibTeX; [planned] precise source links |
| 工程师和技术学科的学生 Engineers and students of technical subjects | 复现例题、公式和算法 reproduce worked examples, equations, algorithms | 章节脚本、`code/`（可执行学习）chapter scripts, `code/` (executable learning) |
| 有多个领域资料的人 People with material in several fields | 每个领域一个书库，或在两台电脑之间搬书库 one library per field, or libraries moved between computers | 多个书库、可迁移书库 several libraries, portable libraries |

**两种工作方式 / Two ways of working** (from the first spec): **读书**（阅读、生词、章节笔记、复习）和**论文研究**（元数据、
技术概念、标注、跨论文比较、引用）共用同一个书库、阅读器、搜索和笔记；以后可以是同一数据上的两套默认设置（v0.5-8），不是两个
应用。**Book study** (reading, vocabulary, chapter notes, review) and **paper research**
(metadata, technical concepts, annotations, comparing papers, citation) share one library,
reader, search and notes; later possibly two sets of defaults over the same data (v0.5-8),
never two applications.

---

## 4. 竞品定位 / Competitive positioning

详见 [docs/COMPETITIVE_ANALYSIS.md](docs/COMPETITIVE_ANALYSIS.md)（来源和核实日期 2026-11-09）。Details, sources
and verification dates in the competitive analysis.

- **借鉴 / Learn from:** BookxNote Pro：一步把选区变成笔记（→ M6）；MarginNote 5：跨文档重组、按步骤精简工具（→ v0.4-5/6）；
  Zotero 10：精确、稳定、可恢复的来源引用（→ 任务 5）。BookxNote Pro: one step from selection to note
  (→ M6); MarginNote 5: cross-document reorganisation, step-focused tools (→ v0.4-5/6); Zotero 10:
  precise, stable, recoverable source references (→ task 5).
- **差异 / Differentiation:** 不是别人做不到，而是把这些放进一个简单的本地工作流：用户管理的本地 PDF 书库、普通 Markdown
  笔记、稳定的文档身份、可配置的外部编辑器、章节代码示例、可复用的科学计算；[计划] 精确来源链接和跨文档知识组织。Not that
  others can't, but one simple local workflow: user-managed local PDF libraries, plain Markdown
  notes, stable document identity, configurable external editors, chapter code examples, reusable
  scientific code; [planned] precise source links and cross-document knowledge.
- **不照搬 / Not copied:** MarginNote 的模板系统、Zotero 完整的引用管理、思维导图优先的工作流。MarginNote's
  template system, Zotero's complete citation management, a mind-map-first workflow.

---

## 5. 核心用户工作流 / Core user workflows

| # | 工作流 Workflow | 步骤 Steps | 现状 Status |
|---|---|---|---|
| W1 | 添加文档 Add documents | ＋ Add 或拖放 → 识别（ISBN、DOI、arXiv、标题页）→ 命名 → 登记 → 章节笔记模板 → 书架。＋ Add or drop → identify (ISBN, DOI, arXiv, title page) → name → register → chapter templates → shelves. | [已有 Existing] |
| W2 | 阅读与查词 Read and look up | 阅读/继续 → 双击或选词 → 术语表、词典 → 加入生词本 / 术语表 / 主题笔记。Read/Continue → double-click or select → glossaries, dictionary → save word / glossary term / topic note. | [已有 Existing] |
| W3 | 边读边记 Read and write | 阅读器中打开笔记面板 → 编辑 Markdown，自动保存，预览。Open the notes panel in the reader → edit Markdown, autosaved, previewed. | [已有 Existing]（公式、格式、截图 [计划] maths, formatting, screenshots [planned]） |
| W4 | PDF → 笔记 → PDF | 选中段落 → 引用到笔记 → 点击链接回到那一段。Select a passage → quote to note → click the link back to it. | [计划 Planned] M6, M7 |
| W5 | 复习 Review | 📇 复习生词（Leitner 盒子）；阅读记录。📇 Review words (Leitner boxes); reading log. | [已有 Existing]；笔记问答 note Q&A [建议 Proposed] R1–R3 |
| W6 | 可执行学习 Executable learning | 章节 → Script → 在编辑器中写和运行 → 结论写进笔记。Chapter → Script → write and run in the editor → conclusions into the note. | [已有 Existing]；与来源和结果的链接 links to sources and results [建议 Proposed] E1–E4 |
| W7 | 多个书库 Several libraries | 选择书库模式 → 私人书库 / 测试与示例；切换书库；把书库复制到另一台电脑。Choose a library mode → personal / Test & Demo; switch library; copy a library to another computer. | [已有 Existing] |
| W8 | 备份 Back up | 💾 zip 备份到任意文件夹；☁ git 备份（书库在仓库中时）。💾 zip backup to any folder; ☁ git backup (when the library is in a repository). | [已有 Existing]；从备份恢复 restore [计划 Planned] task 7 |

---

## 6. 功能需求 / Functional requirements

每条需求都有编号，便于验收和引用。Every requirement has an id for acceptance and reference.

### 6.1 书库与文档 / Library and documents
- **FR-L1** [已有] 每个文档有永久的 UUID4 身份；slug 只是文件和文件夹的名字。Every document has a permanent
  UUID4 identity; the slug is only the file and folder name.
- **FR-L2** [已有] 识别书、论文、学位论文的元数据并记录每个字段的来源。Identify metadata of books, papers and
  theses and record where each field came from.
- **FR-L3** [已有] 重复必须有证据（DOI、非论文的 ISBN、相同文件的 SHA-256）；仅凭名字或标题从不算重复。A repeat needs
  proof (DOI, ISBN for non-papers, identical file by SHA-256); a name or title alone never is.
- **FR-L4** [已有] 移除的文档进入书库的 `archive/`，留下墓碑记录。Removed documents go to the library's
  `archive/` and leave a tombstone.
- **FR-L5** [计划 task 6] 在页面上修正元数据和章节；用户的修改从不被自动步骤覆盖。Correct metadata and chapters
  on the page; the user's edits are never overwritten by automatic steps.
- **FR-L6** [已有] 多个独立书库，每个书库是一个完整的文件夹，可以整个复制或移动（[docs/LIBRARIES.md](docs/LIBRARIES.md)）。
  Several independent libraries, each a complete folder that can be copied or moved whole.

### 6.2 阅读 / Reading
- **FR-R1** [已有] PDF.js 阅读器在章节或上次阅读的页面打开；`/read/<id>` 是持久链接。The PDF.js reader opens at
  the chapter or the last page read; `/read/<id>` is the lasting link.
- **FR-R2** [已有] 查词顺序：与文档学科匹配的术语表，然后离线英汉词典（ECDICT）。Lookup order: glossaries
  matching the document's subject, then the offline English–Chinese dictionary (ECDICT).
- **FR-R3** [已有] PDF.js 编辑工具的标注保存进 PDF，带版本检查，原件保留一份。Marks made with PDF.js's editor
  tools are saved into the PDF, version-checked, the original kept once.
- **FR-R4** [已有] 全书库全文搜索（SQLite FTS5，可重建的缓存）。Full-text search of all books (SQLite FTS5, a
  rebuildable cache).
- **FR-R5** [计划 task 5] 标注列表、筛选、跳转、注释和标签。An annotation list with filters, jumps, comments
  and tags.

### 6.3 笔记 / Notes
- **FR-N1** [已有] 每章一个 Markdown 文件，论文一个 `notes.md`；`.md` 文件是唯一的权威。One Markdown file per
  chapter, one `notes.md` per paper; the `.md` file is the only authority.
- **FR-N2** [已有] 笔记面板：自动保存、冲突检测（从不覆盖更新的文件）、恢复草稿（按书库隔离）、只读、源码/预览/分屏。
  Notes panel: autosave, conflict detection (never over a newer file), recovery drafts (scoped
  per library), read-only, Source/Preview/Split.
- **FR-N3** [已有] 笔记也可以在外部编辑器中打开（VS Code、记事本、系统默认、自定义命令）。Notes also open in an
  outside editor (VS Code, Notepad, system default, a custom command).
- **FR-N4** [计划 M5b–M5d] 公式、格式工具栏、粘贴截图。Maths, formatting toolbar, pasted screenshots.
- **FR-N5** [计划 M6/M7] 引用到笔记；从笔记回到原文段落。Quote to note; from a note back to the passage.
- **FR-N6** [已有] 工具自己从不把书中的文字写进笔记（模板只有标题）。The tool never writes book text into notes on
  its own (templates hold headings only).

### 6.4 学习与复习 / Learning and review
- **FR-S1** [已有] 生词本（`vocabulary.md`）和 📇 复习生词（Leitner 盒子，从不修改生词文件）。Vocabulary
  (`vocabulary.md`) and 📇 Review words (Leitner boxes; the vocabulary files are never edited).
- **FR-S2** [已有] 阅读记录（主动阅读时间和看过的页）。Reading log (active time and pages seen).
- **FR-S3** [已有] 主题笔记（只写书和页码，从不写书中文字）。Topic notes (book and page only, never book text).
- **FR-S4** [计划 v0.4] 连接来源的主题、标签、统一搜索。Topics linking sources, tags, unified search.
- **FR-S5** [建议 R1–R3] 笔记问答、简单复习、Anki 兼容导出。Note Q&A, simple review, Anki-compatible export.

---

## 7. 可执行学习 / Executable learning

**可执行学习——不止于阅读，更通过实践掌握知识。**
**Executable Learning — go beyond reading, learn by implementing.**

可选能力：书库是本地、用户可访问的文件，用户可以写程序复现书和论文中的例题、公式、算法、仿真和实验。
An optional capability: because a library is local, user-accessible files, users can write
programs that reproduce the examples, equations, algorithms, simulations and experiments of
their books and papers.

**示例 / Example.** 读高斯光束传播一章 → 理解公式 → 在 VS Code 中打开该章的 Python 脚本 → 实现模型 → 计算并画图 → 与书中
结果比较 → 把观察写进 Markdown 笔记 → 回到相应的章节或段落。Read the Gaussian-beam chapter → understand the
equations → open the chapter's Python script in VS Code → implement the model → compute and
plot → compare with the book → write the observations in the Markdown note → return to the
chapter or passage.

### 7.1 已有 / Existing

| 能力 Capability | 实现 Implementation |
|---|---|
| 章节脚本 Chapter scripts | 书库页面的 **Script**：从模板创建 `examples/<book>/chNN_<topic>.py` 并在编辑器中打开；之后 Read/Continue 也打开它（`library_server.script_for`）。The library page's **Script** creates `examples/<book>/chNN_<topic>.py` from a template and opens it in the editor; later Read/Continue open it too. |
| 可复用代码 Reusable code | 书库的 `code/`，按学科分组（如 `code/optics/`），在脚本的导入路径上；`code/tests/` 由 `uv run pytest` 运行。The library's `code/`, by subject (e.g. `code/optics/`), on the scripts' import path; `code/tests/` run by `uv run pytest`. |
| 科学计算依赖 Scientific dependencies | `science` 组：numpy、scipy、sympy、matplotlib（`uv sync` 默认安装）；可选的 `optics` 组（optiland、rayoptics）。The `science` group (installed by default) and the optional `optics` group. |
| 外部编辑器 External editor | 设置中选择（VS Code、记事本、系统默认、自定义 `{file}` 命令）；`.py` 从不用系统默认程序打开。Chosen in Settings; a `.py` is never opened with its default app (that could run it). |
| 开关 Switch | ⚙ 设置 → 显示 Python 功能（源码安装默认开，安装包中关）。Settings → Show the Python features (on from source, off in the package). |

### 7.2 要求 / Requirements
- **FR-E1** [已有] 运行代码永远是用户在自己的编辑器或终端中的明确操作；myLibrary 从不运行脚本。Running code is
  always the user's explicit action in their own editor or terminal; myLibrary never runs a
  script.
- **FR-E2** [已有] 从不自动运行从文档中提取的代码。Code extracted from documents is never run automatically.
- **FR-E3** [已有] 没有 Python 功能时，阅读、笔记和学习完全不受影响。Without the Python features, reading,
  notes and learning are entirely unaffected.
- **FR-E4** [建议 E1–E4] 来源 ↔ 代码链接、结果与笔记、可复现记录、其他语言模板（ROADMAP 第 6 节）。Source ↔ code
  links, results in notes, a reproducibility record, other-language templates (ROADMAP section 6).
- **不做 / Not:** 内置 IDE 或代码执行环境。A built-in IDE or execution environment.

---

## 8. 技术架构 / Technical architecture

### 8.1 现有架构 / Existing architecture

| 部分 Part | 实现 Implementation |
|---|---|
| 服务器 Server | `library_server.py`：标准库 `ThreadingHTTPServer`，只监听 127.0.0.1，检查 Host 头，POST 需每次运行的令牌，只提供目录中登记的 PDF；监听队列 64；每个书库一个服务器进程，由书库锁保证唯一（`libraries.hold_library`）。Standard-library server on 127.0.0.1 only, Host header checked, a per-run token on every POST, only catalogued PDFs served; listen backlog 64; one server process per library, unique through the library lock. |
| 书库页面 Library page | `library_page.py`：一个 HTML/CSS/JS 模板；静态副本 `library.html`。One HTML/CSS/JS template; a static copy. |
| 阅读器 Reader | PDF.js 4.10.38（固定版本、校验，安装到工具的 `.cache/reader/`）加 `reader_static/`：`lookup.js`、`notes.js`、`note_session.js`、`preview.js`；markdown-it 15.0.3 用于预览。PDF.js (pinned, checked, in the tool's `.cache/reader/`) plus `reader_static/`; markdown-it for the preview. |
| 数据 Data | 书库文件夹中的普通文件：`catalog.csv`（每文档一行，`id` 列为 UUID）、`notes/`、`glossaries/`、`examples/`、`code/`、`library.toml`；可重建的 `.cache/`；工具记录 `.myLibrary/`。Plain files in the library folder; a rebuildable `.cache/`; the tool's records in `.myLibrary/`. |
| 写入 Writing | 全部经过 `safe_io`：原子写入、按文件加锁、损坏文件不被覆盖（`.bak`、`DamagedFile`）、退出时等待关键操作。Everything through `safe_io`: atomic writes, per-file locks, damaged files never replaced (`.bak`, `DamagedFile`), Quit waits for critical operations. |
| 后台任务 Jobs | `library_jobs.py`：每个任务一个线程，在安全点检查停止。One thread per job, stopping at safe points. |
| 工具与书库 Tool and library | 工具（`scripts/`、`tests/`、文档）与书库（个人数据）分开；`paths.py` 决定使用哪个书库；机器本地记录在 `.myLibrary-local/`。The tool and a library (personal data) are kept apart; `paths.py` chooses the library; machine-local records in `.myLibrary-local/`. |
| 测试 Tests | pytest（每次运行都有自己的临时书库和设置，隔离保护拒绝写真实数据）、Edge 浏览器测试、Windows CI。pytest (each run with its own temporary library and settings; an isolation guard refuses writes to real data), browser tests in Edge, Windows CI. |

### 8.2 建议的架构变化 / Proposed architecture changes
- 引用存储 `.myLibrary/references/<id>.json`（M6，设计已批准）。The references store (M6, design approved).
- 标注旁注 `annotations.json` 和 `scripts/annotations.py`（任务 5）。The annotations sidecar and module (task 5).
- 提供者接口 `scripts/assist.py`，默认关闭（v0.4-1）。A provider interface, off by default (v0.4-1).
- 桌面包装（pywebview 或类似），包装现有界面而不重写（ROADMAP 第 9 节）。A desktop wrapper (pywebview or
  similar) around the existing interface, not a rewrite.

**约束 / Constraints:** 不使用 Electron、React、Qt 或其他框架（除非有具体理由并经批准）；前端资源本地、固定版本、校验，运行时
不用 CDN，没有构建步骤；通过 `paths.APP` 找工具文件；用户数据只在书库或设置文件中，从不写入安装文件夹。No Electron,
React, Qt or other framework without a specific reason and approval; frontend assets local,
pinned, checksum-verified, no CDN at runtime, no build step; tool files found through
`paths.APP`; user data only in a library or the settings file, never in the installation
folder.

---

## 9. 来源锚点与数据模型 / Source anchors and data models

### 9.1 现有 / Existing
- **文档 / Document:** `catalog.csv` 的一行，`id` = UUID4；`file` 和 `notes` 是书库内的相对路径。A `catalog.csv`
  row, `id` = UUID4; `file` and `notes` are paths relative to the library.
- **退出的文档 / Retired documents:** `retired-documents.json` 中的墓碑（合并：`resolve()` 跟随；移除：保留标题）。
  Tombstones (merged: followed by `resolve()`; removed: the title kept).
- **书库身份 / Library identity:** `library.toml` 中可选的 `id`（新书库才有）；浏览器草稿和备份名按书库区分。An
  optional `id` in `library.toml` (new libraries); browser drafts and backup names scoped per
  library.
- **页面链接 / Page links:** `/read/<id>?page=N`，与主机和端口无关。Independent of host and port.
- **标注 / Marks:** PDF.js 写入 PDF 的标准标注，带 `/NM` 名称。Standard annotations PDF.js writes into the
  PDF, with `/NM` names.

### 9.2 建议的锚点模型 / Proposed anchor model (M6, M7, task 5)

| 字段 Field | 用途 Purpose |
|---|---|
| `doc` | 文档 UUID Document UUID |
| `rid` | 引用 id（在文档内唯一）Reference id (unique within the document) |
| `page` | 页索引（从 0 开始）Page index (zero-based) |
| `text` | 选中的文字（只在 `.myLibrary/references/` 中）Selected text (only in `.myLibrary/references/`) |
| `prefix`, `suffix` | 前后文，用于消除歧义 Context for disambiguation |
| `rects` | 规范化矩形（0–1，相对页面）Normalised rectangles (0–1, relative to the page) |
| `fingerprint` | 引用时 PDF 的 SHA-256 The PDF's SHA-256 when quoted |
| `nm` | （可选）对应的 PDF 标注的 `/NM` (Optional) the `/NM` of the matching PDF mark |

**定位顺序 / Resolution order:** 精确位置 → 唯一的文字/位置匹配 → 页面 → 来源缺失提示和恢复选项；**有歧义时从不悄悄选择**。
Exact location → a unique text/position match → the page → a missing-source warning with a
recovery option; **an ambiguous match is never chosen silently.**

**已批准的决定（2026-11-07，历史记录第 5 节）/ Approved decisions:** 笔记中可见的引用很短（约 15 个词 + 链接）；完整
锚点只在 `.myLibrary/references/`（不进 git，进 💾 备份，从不进公开的 `notes/`）；链接写成
`http://127.0.0.1:<port>/read/<id>?…`，端口不是身份。The visible quote in a note is short (about 15
words + the link); the full anchor only in `.myLibrary/references/` (not in git, in 💾 backup,
never in the public `notes/`); links are `http://127.0.0.1:<port>/read/<id>?…`, the port is not
identity.

**与 PDF 中的标注共存 / Coexisting with marks in the PDF:** 标注留在 PDF 中；旁注只按 `/NM` 指向它们，从不改写或删除；PDF
被替换时，指纹不同即被察觉，按定位顺序处理，从不丢弃用户的注释。Marks stay in the PDF; the sidecar only points at
them by `/NM` and never rewrites or deletes them; when a PDF is replaced, a different fingerprint
shows it, the resolution order applies, and the user's comments are never dropped.

---

## 10. 数据安全与可迁移性 / Data safety and portability

- **DS-1** 笔记、生词、主题笔记、阅读记录、复习进度、PDF 中的标注、`catalog.csv`、`library.toml` 是用户的工作：从不删除；
  移入书库的 `archive/`（`add_book.move_to_archive`）。Notes, vocabulary, topic notes, reading log,
  review progress, marks in PDFs, `catalog.csv` and `library.toml` are the user's work: never
  deleted; moved to the library's `archive/`.
- **DS-2** 所有写入经过 `safe_io`（原子、加锁、损坏不覆盖）。All writes through `safe_io` (atomic, locked,
  damage never overwritten).
- **DS-3** 迁移是明确、有日志、有备份、可回滚的，事先征得同意；旧格式的目录被拒绝，从不悄悄升级（`migrate_ids.py`）。
  Migrations are explicit, journaled, backed up and reversible, agreed first; an old-format
  catalog is refused, never upgraded silently.
- **DS-4** 可迁移：书库中的一切以相对路径引用；复制或移动整个文件夹后，文档 id、笔记、标注、阅读记录、生词、术语表、书架都保留；
  机器相关的设置（编辑器、备份文件夹、书库列表）不在书库中。Portable: everything refers to the library by
  relative path; after copying or moving the whole folder, ids, notes, marks, log, vocabulary,
  glossaries and shelves remain; machine-specific settings (editor, backup folder, the library
  list) live outside it.
- **DS-5** 添加已有书库只读取它；不迁移、不修复、不清理。Adding an existing library only reads it; no
  migration, repair or cleanup.
- **DS-6** 版权：书从不进 git；工具从不把书中文字写进公开的笔记；公开的测试/示例书库只含合成或已核实许可的文档。Copyright:
  books never go into git; the tool never writes book text into public notes; the public Test &
  Demo library holds only synthetic or licence-verified documents.

---

## 11. 用户体验原则 / User experience principles

1. **每个中文都配英文 / Chinese always with English** (UI, docs, messages).
2. **一步完成常见操作 / Common actions in one step:** 例如引用到笔记（计划）。e.g. quote to note (planned).
3. **从不悄悄丢失或覆盖 / Never lose or overwrite silently:** 冲突、草稿、离开提醒都明确显示。Conflicts, drafts
   and the leave warning are always visible.
4. **高级功能不打扰 / Advanced features stay out of the way:** Python 功能可关闭；AI 默认关闭。Python features
   can be switched off; AI is off by default.
5. **页面能完成一切 / The page does everything:** 安装包需要的每个功能都能在书库页面上完成，不需要终端。Every feature
   the package needs works from the library page, without a terminal.
6. **诚实的状态 / Honest status:** 只能找到页面、PDF 已改变、离线等情况都说清楚。Only-the-page, a changed PDF,
   offline: always said plainly.

---

## 12. 非功能性需求 / Nonfunctional requirements

| 编号 ID | 要求 Requirement | 怎样检查 How checked |
|---|---|---|
| NF-1 | 只监听 127.0.0.1；端口可配置；端口从不是身份。127.0.0.1 only; configurable port; the port is never identity. | 服务器测试 server tests |
| NF-2 | 断网时阅读、笔记、搜索、生词可用。Reading, notes, search, vocabulary work offline. | `--no-download` 的测试服务器 test servers with `--no-download` |
| NF-3 | 并发写入不丢失（线程和两个服务器之间）。No lost writes under concurrency (threads; two servers). | 并发测试、书库锁测试 concurrency and library-lock tests |
| NF-4 | 退出不会切断写入。Quit never cuts off a write. | `safe_io.critical` 的测试 tests |
| NF-5 | 一次页面载入的突发连接不被拒绝。A page load's burst of connections is never refused. | `test_a_burst_of_connections_is_never_refused` |
| NF-6 | 依赖固定版本；下载的资源校验 SHA-256。Pinned dependencies; downloaded assets SHA-256-checked. | 安装测试 setup tests |
| NF-7 | 支持 Windows 长路径、空格和中文路径。Long Windows paths, spaces and Chinese in paths. | `test_long_paths.py`, portability tests |
| NF-8 | 大 PDF（500 MB 以上）的性能（计划，v0.4-7）：先测量再改进；本文件不写未测量的数字。Large-PDF (500 MB+) performance (planned, v0.4-7): measured before improving; no unmeasured numbers here. | 计划 planned |

平台：在 Windows 上开发和测试；macOS 和 Linux 未测试。Platform: developed and tested on Windows; macOS and
Linux untested.

---

## 13. 测试与验收标准 / Testing and acceptance criteria

- 每个行为改变都有确定性的回归测试；测试只使用临时书库（`tests/conftest.py`、`tests/isolation_guard.py`），从不触碰真实
  书库。Every behaviour change has deterministic regression tests; tests use temporary libraries
  only and never touch a real one.
- 阅读器的改变有 Edge 浏览器测试（`tests/browser/`，每个测试自己的书库、设置和服务器）。Reader changes have
  browser tests in Edge (each test with its own library, settings and server).
- 必须一直保留的测试类别：数据保护、并发与冲突、文件系统包含、符号链接与目录联接、原子写入、恢复与备份、PDF 完整性、测试隔离。
  Test categories always kept: data protection, concurrency and conflicts, filesystem
  containment, symlinks and junctions, atomic writes, recovery and backup, PDF integrity, test
  isolation.
- 完成前：`uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`；需要时浏览器测试；CI 在 Windows 上运行同样的
  检查。Before done: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`; browser
  tests where relevant; CI runs the same on Windows.
- 每次 pytest 运行都写 `test-results/pytest-junit.xml`；间歇性失败要用证据调查，重跑通过不是解释（L20）。Every pytest
  run writes `test-results/pytest-junit.xml`; intermittent failures are investigated with
  evidence, a passing rerun isn't an explanation (L20).
- 公开的测试/示例书库 `test_library/` 是标准测试语料：固定 id、可复现构建、每个 PDF 的校验和与期望在 `MANIFEST.json` 中。
  The public `test_library/` is the standard corpus: fixed ids, reproducible build, every PDF's
  checksum and expectations in `MANIFEST.json`.
- 每个里程碑的具体验收标准在 [ROADMAP.md](ROADMAP.md) 中。Each milestone's specific acceptance criteria are
  in the ROADMAP.

---

## 14. 长期产品方向 / Future product direction

按顺序（ROADMAP 第 0.2 节）：完成笔记工作流（P0）→ 稳定的来源锚点（P1）→ 跨文档知识（P2）→ 可执行学习的扩展（P3）→
主动学习（P4）→ 可选的高级功能和 AI（P5）→ 桌面应用。AI 始终可选、注重隐私、生成内容与原文清楚区分、只引用实际检索到的来源。
In order (ROADMAP section 0.2): finish the notes workflow (P0) → stable source anchors (P1) →
cross-document knowledge (P2) → more executable learning (P3) → active learning (P4) → optional
advanced features and AI (P5) → a desktop app. AI stays optional, privacy-conscious, with
generated text clearly apart from the source and citing only what was actually retrieved.

---

## 15. 不开发的功能 / Non-goals

DjVu 或 EPUB；笔记本（notebook）；影子图书馆来源；书或书中文字进入 git；云托管、账户或订阅；强制 AI；替换 Python 后端或
浏览器界面（除非有具体理由并经批准）；内置 IDE；自动运行从文档中提取的代码；为了功能列表照搬其他产品（MarginNote 的模板系统、
Zotero 完整的引用管理、思维导图优先的工作流）；完整的 Anki 替代品。
DjVu or EPUB; notebooks; shadow-library sources; books or book text in git; cloud hosting,
accounts or subscriptions; mandatory AI; replacing the Python backend or browser interface
(unless justified and approved); a built-in IDE; running code extracted from documents
automatically; copying other products for a feature list (MarginNote's template system,
Zotero's complete citation management, a mind-map-first workflow); a full Anki replacement.
