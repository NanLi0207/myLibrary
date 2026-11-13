# myLibrary 产品与技术规格 / Product and technical specification

本文件说明 myLibrary 要成为什么、必须满足哪些要求、怎样验收。**当前计划和进度**见 [ROADMAP.md](ROADMAP.md)；
**第一版规格**（原始需求说明）原样保留在 [docs/history/DEVELOPMENT_SPEC_v1.md](docs/history/DEVELOPMENT_SPEC_v1.md)，
其中仍有效的要求已并入本文件。
This file says what myLibrary is meant to become, which requirements it must meet and how they
are accepted. The **current plan and progress** are in [ROADMAP.md](ROADMAP.md); the **first
specification** (the original requirements brief) is kept unchanged in
[docs/history/DEVELOPMENT_SPEC_v1.md](docs/history/DEVELOPMENT_SPEC_v1.md), and its requirements
that still apply are carried into this file.

**标记 / Markers:** **[已有 Existing]** = 已在代码中实现（最近核对的提交和 CI 见 [ROADMAP.md 第 1 节](ROADMAP.md)）
implemented in the code (the last checked commit and CI are in ROADMAP section 1) ·
**[计划 Planned]** = 尚未实现，见 ROADMAP not implemented yet, see the ROADMAP · **[建议 Proposed]** =
本文件提出，需批准 proposed here, needs approval. G1、X1、U1–U3 于 2026-11-10 作为**规划方向**获批，但**都没有实现，也没有开始**；
开始工作需要用户另行同意。G1, X1 and U1–U3 were approved as **planning directions** on 2026-11-10, but
**none is implemented or started**; starting work needs the user's separate go-ahead.

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

一个本地优先的知识与实践工作空间，用于从技术文档中深入学习。
A local-first knowledge and practice workspace for deep learning from technical documents.

**首要承诺 / The primary promise:** 低摩擦、可追溯的阅读和笔记：读长 PDF，一步把一段变成 Markdown 笔记，再从笔记回到原文那一段。
这条最简单的路径不依赖编程、AI 或高级知识管理。Low-friction, traceable reading and note-taking: read
long PDFs, turn a passage into a Markdown note in one step, and go from the note back to that
passage. This simplest path depends on no programming, AI or advanced knowledge management.

**独特的高级工作流（可选）/ The distinctive advanced workflow (optional):**
PDF/来源 source → Markdown 笔记 note → 代码或实验 code or experiment → 结果 result → 原文 original source.

| 环节 Link | 现状 Status |
|---|---|
| PDF → 笔记 note | [计划 Planned] M6（现在：手动复制 today: copy by hand） |
| 笔记 → 原文 note → source | [已有 Existing] 页面级 page level (`/read/<id>?page=N`)；[计划 Planned] 段落级 passage level M7，稳定锚点 stable anchors task 5 |
| 来源 → 代码 source → code | [已有 Existing] 每章的脚本 a script per chapter；[建议 Proposed] 段落链接 passage links E1 |
| 代码 → 结果 → 笔记 code → result → note | [建议 Proposed] E2, E3 |

**定位和标语的决定（2026-11-10）/ Positioning and tagline decision (2026-11-10).** 标语
"阅读、理解、实践、验证、掌握 / Read. Understand. Implement. Verify. Remember." **保持不变**：它描述了完整的学习循环，是已有的品牌。
改变的是标语下面的描述句，原来是"一个将文档、笔记、知识与可执行代码连接起来的本地优先学习与研究工作空间"。改的原因：原句把可执行代码与
文档和笔记并列，好像它是核心；新句子说出首要的读者（深入学习技术文档的人）和承诺（知识与实践），而可执行学习仍然是可选的。
"技术文档"说的是市场重点，不是功能限制：工具对任何学科都可用（原则 11）。**建议：**标语中的"实践、验证"是否会让不编程的读者觉得
这个工具不适合他们，是一个待检验的问题（U1、U3）；在有证据之前不改标语。
The tagline "Read. Understand. Implement. Verify. Remember." **stays**: it describes the whole
learning loop and is the established brand. What changed is the descriptive line under it,
formerly "A local-first learning and research workspace connecting documents, notes, knowledge
and executable code". The reason: the old line set executable code beside documents and notes
as if it were core; the new one names the primary audience (people learning in depth from
technical documents) and the promise (knowledge and practice), while executable learning stays
optional. "Technical documents" states the market focus, not a limit on the tool: it stays
usable for any subject (principle 11). **Recommendation:** whether "Implement. Verify." in the
tagline makes non-programming readers think the tool isn't for them is an open question (U1,
U3); the tagline isn't changed without that evidence.

### 2.1 三个支柱 / Three pillars

| 支柱 Pillar | 含义 Meaning | 现状 Status |
|---|---|---|
| **学习 Learning** | 理解并记住：生词与术语、复习、阅读记录、主题。Understand and remember: vocabulary and terms, review, reading log, topics. | [已有 Existing] 术语表、英汉词典、生词复习卡片、阅读记录、主题笔记 glossaries, English–Chinese dictionary, vocabulary review cards, reading log, topic notes |
| **阅读 Reading** | 专注、可靠地读 PDF。Focused, reliable PDF reading. | [已有 Existing] PDF.js 阅读器、继续阅读、标注保存、全文搜索、预览标签页 PDF.js reader, resume, saving marks, full-text search, preview tabs |
| **笔记 Note-taking** | 在 PDF 旁边用普通 Markdown 写自己的话。Your own words in plain Markdown beside the PDF. | [已有 Existing] 笔记面板（编辑、自动保存、冲突、草稿、预览）notes panel (editing, autosave, conflicts, drafts, preview)；[已有 Existing] 预览中的公式（M5b）maths in the preview；[已有 Existing] 格式工具栏和显示设置（M5c）formatting toolbar and display settings；[已有 Existing] 截图和公式识别（M5d/M5e，`4e4abce`）screenshots and formula recognition；[计划 Planned] 引用到笔记、回到原文 quote to note, back to the passage |

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

### 2.4 核心任务 / Core jobs to be done

2026-11-10 的市场研究（公开资料的桌面研究，见 [docs/COMPETITIVE_ANALYSIS.md](docs/COMPETITIVE_ANALYSIS.md)）找出的高优先级工作流。
它们的重要性是**假设**，由第 16 节检验。用户现在把 Zotero、Obsidian、VS Code、Jupyter 等工具组合起来使用；myLibrary 的机会是**减少
这些学习工作流之间的摩擦**，而不是复制这些应用的每个功能。
The high-priority workflows found by the market review of 2026-11-10 (desk research of public
sources, see the competitive analysis). Their importance is a **hypothesis**, tested in section
16. Users today combine tools such as Zotero, Obsidian, VS Code and Jupyter; myLibrary's
opportunity is to **reduce the friction between these learning workflows**, not to duplicate
every feature of those applications.

| # | 任务 Job | 现状 Status | 路线图 Roadmap |
|---|---|---|---|
| J1 | 不受打扰地读长 PDF Read long PDFs without unnecessary distractions | [已有 Existing] PDF.js 阅读器、继续阅读、可关闭的笔记面板 the reader, resume, a closable notes panel | M8（小屏幕、提示 small screens, chips）, v0.4-7（大 PDF large PDFs） |
| J2 | 很快把 PDF 选区变成 Markdown 笔记 Turn a PDF selection into a Markdown note quickly | [计划 Planned] | **M6** |
| J3 | 从笔记回到原文的确切段落 Return from a note to the exact original passage | [已有 Existing] 页面级 page level；[计划 Planned] 段落级 passage level | **M7**, task 5 |
| J4 | 在多个 PDF、笔记和标注中找到知识 Find knowledge across PDFs, notes and annotations | [已有 Existing] PDF 全文搜索、主题笔记 full-text search of PDFs, topic notes；[计划 Planned] 笔记和标注的统一搜索 unified search of notes and annotations | v0.4-4, v0.4-5, v0.4-6, task 5 |
| J5 | 数据本地拥有、开放、可移植 Keep data locally owned, open and portable | [已有 Existing] 普通文件、UUID、可迁移书库、💾 备份 plain files, UUIDs, portable libraries, backups；[计划 Planned] 从备份恢复 restore | task 7 |
| J6 | 可选：把来源与外部代码、计算、实验、图和结果联系起来 Optionally associate sources with external code, calculations, experiments, plots and results | [已有 Existing] 章节脚本、`code/` chapter scripts, `code/`；[建议 Proposed] 链接和结果 links and results | E1–E4 |

**J1–J3 和 J5 是最简单的路径，从不依赖编程、AI 或高级知识管理**（FR-E3）。**J1–J3 and J5 are the simplest path and
never depend on programming, AI or advanced knowledge management.**

---

## 3. 目标用户与应用场景 / Target users and use cases

myLibrary 仍然是学科中立的本地优先应用；**初期的目标市场**集中在下面四类用户，按优先级排列。这是 2026-11-10 根据桌面研究做出的
**产品重点决定，不是测量过的市场**：每个用户群的需要都是第 16 节要检验的假设。重点只决定先做什么和用什么例子，**从不导致在工具中写死
工程或光学的假设**（原则 11）。
myLibrary stays a subject-neutral, local-first application; its **initial target market**
focuses on the four groups below, in priority order. This is a **product-focus decision made on
2026-11-10 from desk research, not a measured market**: each group's needs are hypotheses for
section 16 to test. The focus decides only what comes first and which examples are used; it
**never leads to engineering or optics assumptions hard-coded into the tool** (principle 11).

| 优先级 Priority | 用户 Users | 他们做什么 What they do | 最相关的任务 Most relevant jobs | 主要功能 Main features |
|---|---|---|---|---|
| **A. 首要 Primary** | 深入学习技术教材的人：说中文的理工科研究生；自学工程、数学、物理、计算机等技术学科的人 Deep technical-textbook learners: Chinese-speaking STEM graduate students; self-directed learners of engineering, mathematics, physics, computing and other technical subjects | 系统地逐章学习教材、习题、公式和章节笔记 work systematically through textbooks, exercises, equations and chapter notes | J1, J2, J3, J5；部分人 some: J6 | 阅读器、术语表优先的英汉查词、章节笔记、生词复习、阅读记录；[已有] 公式（M5b）；[计划] 引用到笔记、回到原文 the reader, glossary-first English–Chinese lookup, chapter notes, vocabulary review, reading log; [existing] maths (M5b); [planned] quote to note, back to the passage |
| **B. 其次 Secondary** | 执业工程师和技术专业人员 Practising engineers and technical professionals | 反复查阅技术书、论文、手册和参考资料；把理论与计算、仿真和实际实现联系起来 consult technical books, papers, manuals and references again and again; connect theory with calculations, simulations and implementations | J3, J4, J6 | 全文搜索、主题笔记、章节脚本、`code/`；[计划] 统一搜索、E1–E4 full-text search, topic notes, chapter scripts, `code/`; [planned] unified search, E1–E4 |
| **C. 以后 Later** | 学术文献研究者 Academic literature researchers | 管理论文、比较结论、在文档之间追溯证据 manage papers, compare findings, trace evidence across documents | J3, J4 | 论文识别（DOI、arXiv）、BibTeX；[计划] 连接来源的主题、标注面板 paper identification, BibTeX; [planned] topics linking sources, the annotation panel。**不试图取代 Zotero 完整的文献管理生态。Not an attempt to replace Zotero's reference-management ecosystem.** |
| **D. 以后扩展 Later expansion** | 一般的深度读者 General deep readers | 想要有结构的阅读和笔记，不需要编程功能 want structured reading and notes without programming features | J1, J2, J3, J5 | 同 A，Python 功能关闭（安装包中默认关闭）as A, with the Python features off (off by default in the package) |

**仍然支持的场景 / Use cases still supported:** 有多个领域资料的人可以每个领域一个书库，或在两台电脑之间搬书库（多个书库、可迁移书库，
[docs/LIBRARIES.md](docs/LIBRARIES.md)）。People with material in several fields keep one library per field, or
move libraries between computers (several libraries, portable libraries).

**两种工作方式 / Two ways of working** (from the first spec): **读书**（阅读、生词、章节笔记、复习）和**论文研究**（元数据、
技术概念、标注、跨论文比较、引用）共用同一个书库、阅读器、搜索和笔记；以后可以是同一数据上的两套默认设置（v0.5-8），不是两个
应用。**Book study** (reading, vocabulary, chapter notes, review) and **paper research**
(metadata, technical concepts, annotations, comparing papers, citation) share one library,
reader, search and notes; later possibly two sets of defaults over the same data (v0.5-8),
never two applications.

---

## 4. 竞品定位 / Competitive positioning

详见 [docs/COMPETITIVE_ANALYSIS.md](docs/COMPETITIVE_ANALYSIS.md)（来源和核实日期 2026-11-09、2026-11-10；已核实的事实、二手资料、
推断和假设分开标记）。Details, sources and verification dates (2026-11-09, 2026-11-10) in the
competitive analysis, with verified facts, secondary sources, inferences and hypotheses labelled
apart.

- **借鉴 / Learn from:** BookxNote Pro：高效的 PDF 摘录和笔记整理（→ M6）；MarginNote 5：面向任务的学习和知识重组（→ v0.4-5/6）；
  Zotero 10：可靠的文献管理、标注和引用，精确、稳定、可恢复的来源引用（→ 任务 5）；Obsidian（常与 Zotero 组合使用）：开放的 Markdown
  知识管理和互操作（→ 普通 `.md` 笔记和普通链接）；Readwise Reader：低摩擦的捕捉、高亮和回顾（→ M6/M7，以后 R1–R3）；ReadPaper：
  中文学术阅读工作流，并提醒可移植性和数据所有权的重要（→ 查词和术语表，DS-4）。BookxNote Pro: efficient PDF
  extraction and note organisation (→ M6); MarginNote 5: task-oriented study and restructuring
  knowledge (→ v0.4-5/6); Zotero 10: reliable literature management, annotation and citation,
  precise, stable, recoverable source references (→ task 5); Obsidian (often combined with
  Zotero): open Markdown knowledge management and interoperability (→ plain `.md` notes and
  ordinary links); Readwise Reader: low-friction capture, highlighting and revisiting (→ M6/M7,
  later R1–R3); ReadPaper: Chinese academic-reading workflows, and a reminder of why portability
  and data ownership matter (→ lookup and glossaries, DS-4).
- **与已有工具并存 / Coexisting with existing tools:** myLibrary 减少 Zotero、Obsidian、VS Code、Jupyter 等工具之间的摩擦，
  而不是取代它们：笔记在任何 Markdown 编辑器中可读，代码在用户自己的编辑器中写和运行，引用可以导出为 BibTeX。myLibrary reduces
  the friction between tools such as Zotero, Obsidian, VS Code and Jupyter rather than replacing
  them: notes readable in any Markdown editor, code written and run in the user's own editor,
  citations exported as BibTeX.
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
| W3 | 边读边记 Read and write | 阅读器中打开笔记面板 → 编辑 Markdown，自动保存，预览。Open the notes panel in the reader → edit Markdown, autosaved, previewed. | [已有 Existing]（公式 maths: M5b 已有 existing；格式 formatting: M5c 已有 existing；截图和公式识别 screenshots and formula recognition: M5d/M5e 已有 existing（`4e4abce`）） |
| W4 | PDF → 笔记 → PDF | 选中段落 → 引用到笔记 → 点击链接回到那一段。Select a passage → quote to note → click the link back to it. | [计划 Planned] M6, M7 |
| W5 | 复习 Review | 📇 复习生词（Leitner 盒子）；阅读记录。📇 Review words (Leitner boxes); reading log. | [已有 Existing]；笔记问答 note Q&A [建议 Proposed] R1–R3 |
| W6 | 可执行学习 Executable learning | 章节 → Script → 在编辑器中写和运行 → 结论写进笔记。Chapter → Script → write and run in the editor → conclusions into the note. | [已有 Existing]；与来源和结果的链接 links to sources and results [建议 Proposed] E1–E4 |
| W7 | 多个书库 Several libraries | 选择书库模式 → 私人书库 / 测试与示例；切换书库；把书库复制到另一台电脑。Choose a library mode → personal / Test & Demo; switch library; copy a library to another computer. | [已有 Existing] |
| W8 | 备份 Back up | 💾 zip 备份到任意文件夹；☁ git 备份（书库在仓库中时）。💾 zip backup to any folder; ☁ git backup (when the library is in a repository). | [已有 Existing]；☁ git 备份暂停 paused (ROADMAP L29)；从备份恢复 restore [计划 Planned] task 7 |

---

## 6. 功能需求 / Functional requirements

每条需求都有编号，便于验收和引用。Every requirement has an id for acceptance and reference.

### 6.1 书库与文档 / Library and documents
- **FR-L1** [已有] 每个文档有永久的 UUID4 身份；slug 只是文件和文件夹的名字。Every document has a permanent
  UUID4 identity; the slug is only the file and folder name.
- **FR-L2** [已有] 识别书、论文、学位论文的元数据并记录每个字段的来源。Identify metadata of books, papers and
  theses and record where each field came from.
- **FR-L3** [已有] 重复必须有证据：相同文件的 SHA-256，只有它；仅凭名字、标题、相同的 ISBN 或 DOI 从不算重复（它们标识出版物或作品，
  不是 PDF 的内容范围，L21、B29），只共享它们的 PDF 是各自的文档，从不被自动替换、归档或合并。A repeat needs proof: an
  identical file by SHA-256, and only that; a name, a title, a shared ISBN or DOI alone never is
  (they name a publication or a work, not what a PDF covers, L21, B29): PDFs that only share them
  are separate documents, never replaced, archived or merged automatically.
- **FR-L4** [已有] 移除的文档进入书库的 `archive/`，留下墓碑记录。Removed documents go to the library's
  `archive/` and leave a tombstone.
- **FR-L5** [计划 task 6] 在页面上修正元数据和章节；用户的修改从不被自动步骤覆盖。Correct metadata and chapters
  on the page; the user's edits are never overwritten by automatic steps.
- **FR-L6** [已有] 多个独立书库，每个书库是一个完整的文件夹，可以整个复制或移动（[docs/LIBRARIES.md](docs/LIBRARIES.md)）。
- **FR-L7** [已实现，CI 待验证 RS1] 阅读状态（想读、在读、读完）由用户选择，记在文档笔记 README 的一行中；没有这一行时自动推断（从不自动"读完"）；按进度排序先列在读、再列想读、最后列读完；状态筛选。A reading status (To Read, Reading, Finished) chosen by the user, kept as one line in the document's notes README; derived when there's none (never Finished by itself); Sort: progress lists Reading, then To Read, then Finished; a status filter.
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
- **FR-N4** [M5b/M5c 已有 existing；M5d/M5e 已有 existing（`4e4abce`，CI 通过 CI-verified；验证记录见 verification record: docs/M5_VERIFICATION.md）] 公式、格式工具栏、粘贴截图和本机公式识别。Maths, formatting toolbar, pasted screenshots and optional local formula recognition.
  M5d stores validated PNG/JPEG/WebP in the document notes' `assets/`, atomically and without
  replacement; Markdown keeps relative links. Folder backup includes images; the automatic
  Git backup is deferred (ROADMAP L29), and personal note assets are never for Git
  publication, so a Git-only restore lacks the images. M5e uses optional pinned Pix2Text MFR 1.5 weights on the CPU,
  offline after an explicit download; real decoder beam hypotheses, editable LaTeX, local
  KaTeX preview, explicit confirmation and the existing note-save session. No cloud, account,
  API key or additional mandatory Python dependency. 本地资源和普通 Markdown；模型可选，确认后才插入，无云端处理。
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
| 阅读器 Reader | PDF.js 4.10.38（固定版本、校验，安装到工具的 `.cache/reader/`）加 `reader_static/`：`lookup.js`、`notes.js`、`note_session.js`、`preview.js`；markdown-it 15.0.3 用于预览；KaTeX 0.19.1 用于预览中的公式（每个文件的 SHA-256 写在 `reader.py` 中，生成阅读页面时校验，不通过就不加载）。PDF.js (pinned, checked, in the tool's `.cache/reader/`) plus `reader_static/`; markdown-it for the preview; KaTeX for its maths (each file's SHA-256 committed in `reader.py` and checked whenever the reader page is made; not loaded unless it passes). |
| 数据 Data | 书库文件夹中的普通文件：`catalog.csv`（每文档一行，`id` 列为 UUID）、`notes/`、`glossaries/`、`examples/`、`code/`、`library.toml`；可重建的 `.cache/`；工具记录 `.myLibrary/`。Plain files in the library folder; a rebuildable `.cache/`; the tool's records in `.myLibrary/`. |
| 写入 Writing | 全部经过 `safe_io`：原子写入、按文件加锁、损坏文件不被覆盖（`.bak`、`DamagedFile`）、退出时等待关键操作。Everything through `safe_io`: atomic writes, per-file locks, damaged files never replaced (`.bak`, `DamagedFile`), Quit waits for critical operations. |
| 后台任务 Jobs | `library_jobs.py`：每个任务一个线程，在安全点检查停止。One thread per job, stopping at safe points. |
| 工具与书库 Tool and library | 工具（`scripts/`、`tests/`、文档）与书库（个人数据）分开；`paths.py` 决定使用哪个书库；机器本地记录在 `.myLibrary-local/`。The tool and a library (personal data) are kept apart; `paths.py` chooses the library; machine-local records in `.myLibrary-local/`. |
| 平台服务 Platform services | `platform_services.py`：用设置中的编辑器打开文件（`.py` 从不用默认程序打开）、系统的文件夹对话框（结果：chosen / cancelled / unsupported / error）、安装包的用户数据文件夹（Windows `%APPDATA%/myLibrary`；将来的 macOS 安装包 `~/Library/Application Support/myLibrary`）。Windows 的行为不变；程序只接收参数列表，不经过 shell；macOS 分支只用模拟测试。Opening a file with the chosen editor (a `.py` never with its default app), the system folder dialog (results chosen / cancelled / unsupported / error), the package's user-data folder (Windows `%APPDATA%/myLibrary`; a future macOS package `~/Library/Application Support/myLibrary`). Windows behaviour unchanged; programs get argument lists, never a shell; the macOS branches are tested with mocks only. |
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

### 9.4 文档结构：评估 / Document structure: an assessment [建议 Proposed] G1

本节是评估和设计原则，**不是数据模型**；具体设计要等用户研究（假设 H7）之后，并在实现之前单独评审和批准。G1 于 2026-11-10 作为规划方向
获批：它的设计评估要在 M6/M7 确定来源锚点的假设之前完成，现在不改变文档 UUID 模型；尚未开始。This section is an assessment and
a set of design principles, **not a data model**; a concrete design waits for user research
(hypothesis H7) and gets its own review and approval before any implementation. G1 was approved
as a planning direction on 2026-11-10: its design assessment comes before M6/M7 commit to their
source-anchor assumptions, without changing the document UUID model now; it hasn't started.

**现在 / Today** [已有 Existing]: 目录中的一行 = 一个 PDF 文件 = 一个 UUID。章节从这个 PDF 中检测（书签，否则印刷的目录页，扫描件用 OCR）；
每个检测到的章节一个笔记模板 `notes/<slug>/chNN-*.md`；阅读记录、PDF 中的标注和（计划中的）锚点都指向文档 id 和这个文件中的页索引。
One catalog row = one PDF file = one UUID. Chapters are detected from that PDF (bookmarks, else
the printed contents pages, OCR for scans); one note template per detected chapter; the reading
log, marks in the PDF and the (planned) anchors all point at the document id and a page index in
that file.

| 情况 Case | 现在 Today | 缺少什么 What's missing |
|---|---|---|
| 一个 PDF 是整本书 One PDF, a whole book | 支持（设计时的情况）Supported (the case it was designed for) | — |
| 一个 PDF 只有一章 One PDF, one chapter | 作为独立的文档登记；章节检测（`book_toc`）在书签标题带章号时用它，否则从 1 开始编号，所以章节 PDF 的书签可能被当作"章节"（未用真实文件测试）；带有整本书 ISBN 的章节 PDF 是自己的文档（L21 修复后）Registered as a document of its own; chapter detection (`book_toc`) uses a chapter number in a bookmark title when there is one and otherwise counts from 1, so a chapter PDF's section bookmarks may become its "chapters" (not tested with a real file); a chapter PDF carrying the book's ISBN is a document of its own (since the L21 fix) | 章号；与书的关系 The chapter number; the relation to the book |
| 一个 PDF 有几章 One PDF, several chapters | 同上 As above | 章节范围 The chapter range |
| 同一本书的多个 PDF Several PDFs of one logical book | 各自是独立的文档，彼此没有关系；进度、章节勾选和搜索结果按文件 Each its own document, unrelated; progress, chapter ticks and search results per file | 分组和顺序 A grouping and an order |
| 缺章、不同的页码、按顺序的部分覆盖 Chapter gaps, differing page numbering, ordered partial coverage | 链接用页索引；印刷页码不显示在笔记中 Links use the page index; printed page numbers aren't shown in notes | 印刷页码标签；哪些章节缺少 Printed page labels; which chapters are missing |

**与现有模型共存的原则 / Principles for coexisting with the existing model:**
1. **每个 PDF 文件的 UUID 仍然是被阅读和被锚定的身份。** 标注、锚点（文档 + 页索引 + 指纹）、阅读记录、搜索索引继续指向文件所属的文档；
   分组从不取代它们，所以已有的引用从不需要改写（没有锚点迁移）。**Each PDF file's UUID stays the identity of
   what is read and anchored.** Marks, anchors (document + page index + fingerprint), the reading
   log and the search index keep pointing at the file's document; a grouping never replaces
   them, so no existing reference is ever rewritten (no anchor migration).
2. **如果得到验证，最小的增加是一个可选的、由用户确认的分组记录**：一个逻辑上的书，有自己的 UUID，按顺序列出成员文档的 id 和每个成员覆盖的
   章节（允许并显示缺章）。它是用户数据，经过 `safe_io` 写入；成员仍是普通文档；删除分组从不删除成员。**If validated, the smallest
   addition is an optional, user-confirmed grouping record**: a logical book with its own UUID,
   listing its member documents' ids in order with the chapters each covers (gaps allowed and
   shown). It is user data, written through `safe_io`; members stay ordinary documents; removing
   a group never removes a member.
3. **章节笔记留在各成员文档的文件夹中**，按书的视图按顺序列出它们。把笔记移到分组的文件夹是 DS-3 意义上的迁移，需要单独同意。**Chapter
   notes stay in each member document's folder**; a book-level view lists them in order. Moving
   notes into a group folder would be a migration in the sense of DS-3 and needs separate
   agreement.
4. **章号和章节标题**：任务 6 的 `chapters.json`（用户的章节编辑）是记录成员章号的自然位置；任务 6 的设计不应排除这一点。**Chapter
   numbers and titles:** task 6's `chapters.json` (the user's chapter editor) is the natural
   place for a member's chapter numbers; task 6's design shouldn't rule that out.
5. **页码只用于显示**：显示印刷页码（PDF 有 `/PageLabels` 时用它，否则用用户设置的偏移）；链接和锚点仍用页索引。**Page numbers
   for display only:** show printed page labels (the PDF's `/PageLabels` where present, else an
   offset the user sets); links and anchors keep the page index.
6. **重复的证据**：相同的 ISBN 不再让章节 PDF 成为整本书的重复（L21，2026-11-10 修复，FR-L3）：只共享 ISBN 的 PDF 是各自的文档。
   **Evidence for repeats:** the same ISBN no longer makes a chapter PDF a repeat of its book
   (L21, fixed 2026-11-10, FR-L3): PDFs that only share an ISBN are documents of their own.

**未决定 / Not decided:** 分组是目录中的一行还是单独的文件；搜索和阅读记录怎样按书汇总；阅读器中怎样在成员之间移动。Whether a
group is a catalog row or a separate file; how search and the reading log add up per book; how
the reader moves between members.

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
- **DS-7** [已有 Existing] 冻结的文件夹：仓库中的公开示例 `library/` 和标准测试书库 `test_library/` 从不被应用打开或
  写入（`paths.FROZEN`；`ensure_library`、`safe_io`、各写入脚本都拒绝）。Frozen folders: the public showcase
  `library/` and the canonical `test_library/` in the repository are never opened or written by
  the app (`paths.FROZEN`; refused by `ensure_library`, `safe_io` and every writing script).

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

平台：在 Windows 上开发和测试；macOS 和 Linux 未测试，也不承诺支持。与操作系统有关的操作集中在 `platform_services.py`
（macOS 分支已写好但只用模拟测试）。核心工作流可靠之后有一个有边界的 macOS 可行性评估
（ROADMAP 的 X1，2026-11-10 作为规划方向获批，未开始，不授权移植）。Platform: developed and tested on Windows; macOS and Linux are untested and
not promised. Operating-system-dependent operations are gathered in `platform_services.py`
(macOS branches written but tested with mocks only). A bounded macOS feasibility assessment follows once the core workflow is reliable
(ROADMAP X1, approved as a planning direction on 2026-11-10, not started, no porting
authorised).

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

按产品价值的顺序（ROADMAP 第 0.2 节）：可靠的阅读和笔记，包括存储、恢复、好用的界面和可安装性（P0）→ 可信的来源引用（P1）→
统一检索和跨文档知识（P2）→ 可选的可执行学习（P3）→ 主动学习（P4）→ 可选的高级功能和 AI（P5）→ 桌面应用；文档结构（G1）和 macOS
可行性（X1）是有边界的规划方向（2026-11-10 获批，未开始）。P4、P5 以及间隔重复、AI、高级可视化和广泛的集成都取决于用户验证（第 16 节）。AI 始终可选、注重隐私、
生成内容与原文清楚区分、只引用实际检索到的来源。
In order of product value (ROADMAP section 0.2): reliable reading and note-taking, with storage,
recovery, a usable interface and installability (P0) → trustworthy source references (P1) →
unified retrieval and cross-document knowledge (P2) → optional executable learning (P3) →
active learning (P4) → optional advanced features and AI (P5) → a desktop app; document
structure (G1) and macOS feasibility (X1) are bounded planning directions (approved
2026-11-10, not started). P4, P5 and spaced repetition,
AI, advanced visualisation and broad integrations depend on user validation (section 16). AI
stays optional, privacy-conscious, with generated text clearly apart from the source and citing
only what was actually retrieved.

---

## 15. 不开发的功能 / Non-goals

DjVu 或 EPUB；笔记本（notebook）；影子图书馆来源；书或书中文字进入 git；云托管、账户或订阅；强制 AI；替换 Python 后端或
浏览器界面（除非有具体理由并经批准）；内置 IDE；自动运行从文档中提取的代码；为了功能列表照搬其他产品（MarginNote 的模板系统、
Zotero 完整的引用管理、思维导图优先的工作流）；完整的 Anki 替代品；取代 Zotero 的文献管理生态；应用内分析、云端遥测或强制账户。
DjVu or EPUB; notebooks; shadow-library sources; books or book text in git; cloud hosting,
accounts or subscriptions; mandatory AI; replacing the Python backend or browser interface
(unless justified and approved); a built-in IDE; running code extracted from documents
automatically; copying other products for a feature list (MarginNote's template system,
Zotero's complete citation management, a mind-map-first workflow); a full Anki replacement;
replacing Zotero's reference-management ecosystem; in-app analytics, cloud telemetry or
mandatory accounts.

---

## 16. 用户验证计划 / User validation plan

**这是计划，不是已完成的研究。** 下面的样本量和成功标准是**提议的决策规则**，不是市场统计；在任何一轮实际完成之前，第 3 节的用户群和
第 2.4 节的任务都只是假设（[COMPETITIVE_ANALYSIS.md 第 9 节](docs/COMPETITIVE_ANALYSIS.md#9-需要用户研究检验的假设--hypotheses-for-user-research)
的 H1–H8，**未经验证的市场假设**）。ROADMAP 中的编号是 U1–U3（2026-11-10 作为规划活动获批，尚未开始；开始需要用户另行同意）。
**This is a plan, not completed research.** The sample sizes and success criteria below are
**proposed decision rules**, not market statistics; until a round has actually been done, the
groups in section 3 and the jobs in section 2.4 remain hypotheses (H1–H8 in the competitive
analysis, section 9, **unverified market hypotheses**). Their ROADMAP ids are U1–U3 (approved as
planned activities on 2026-11-10, not started; starting needs the user's separate go-ahead).

**共同规则 / Shared rules.** 没有应用内分析、云端遥测或强制账户：证据来自访谈、观察和参与者自己选择分享的东西（例如一个笔记文件夹或日志
文件，由他们自己查看后发送）。录音和记录事先征得同意，分析后匿名化。参与者用自己的 PDF，书和书中文字从不被收集；需要共同材料时用公开的
测试/示例书库。No in-app analytics, cloud telemetry or mandatory accounts: evidence comes from
interviews, observation and what participants choose to share (e.g. a notes folder or a log
file they look at before sending). Recordings and notes only with consent, anonymised for
analysis. Participants use their own PDFs and no book or book text is collected; shared material
uses the public Test & Demo library.

### 16.1 U1 — 定性访谈 / Qualitative interviews（现在就可以，不需要代码 possible now, no code）
- **对象 Who:** 8–12 人：6–8 位技术教材学习者（A），3–5 位执业工程师（B）；尽量包括已经组合使用 Zotero、Obsidian、VS Code 或 Jupyter
  的人，以及用 macOS 的人。8–12 people: 6–8 technical-textbook learners (A), 3–5 practising
  engineers (B); including where possible people who already combine Zotero, Obsidian, VS Code
  or Jupyter, and macOS users.
- **问什么 What:** 最近一次认真学一章的经过（工具、切换、在哪里丢了上下文）；怎样回到原文；笔记存在哪里、是否丢过；是否用代码检查书中的
  结果，以及代码怎样找回它对应的段落；PDF 是整本、按章还是分成几份（H7）；平台（H8）。问过去的具体行为，而不是"你想要什么功能"。The
  last time they studied a chapter seriously (tools, switches, where context got lost); how they
  get back to the source; where notes live and whether they ever lost any; whether they check a
  book's results in code, and how the code finds its passage again; whether PDFs come whole, per
  chapter or split (H7); platform (H8). Ask about specific past behaviour, not "which features
  would you like".
- **输出 Output:** 每个假设 H1–H8 的证据摘要（支持、反对、不清楚），引用具体的访谈而不是百分比。An evidence summary per
  hypothesis H1–H8 (supports, contradicts, unclear), citing specific interviews rather than
  percentages.

### 16.2 U2 — 观察真实的 PDF → 笔记 → 原文工作流 / Observing real PDF → note → source workflows（在 M7 之后 after M7）
- **对象 Who:** 5–8 位参与者（多数来自 A），每人一次 45–60 分钟的观察，用他们自己的一章。5–8 participants (mostly A),
  one 45–60 minute observed session each, on a chapter of their own.
- **任务 Tasks:** 读几页；把三段引用到笔记；写自己的笔记；第二天（或会话结束时）从笔记回到这三段；对使用代码的人：从脚本回到它对应的段落。
  Read a few pages; quote three passages into a note; write their own note; next day (or at the
  end) go back to those three passages from the note; for those who use code: from the script
  back to its passage.
- **数据恢复检查 Data-recovery checks:** 在测试/示例书库或参与者的副本上（从不在他们唯一的书库上）：写到一半强制关闭浏览器、两个标签页编辑同一笔记、
  断网、替换 PDF，然后记录能否看到草稿、冲突提示和"只能找到页面"的说明。On the Test & Demo library or a copy of
  the participant's library (never their only one): force-close the browser mid-edit, edit one
  note in two tabs, go offline, replace the PDF; record whether the draft, the conflict notice
  and the "only the page could be found" message are seen and understood.
- **提议的成功标准 Proposed success criteria:** 至少 80% 的引用不需要帮助就完成；至少 80% 的回到原文落到正确段落，或清楚说明只能到页面；
  恢复检查中**没有任何笔记文字丢失**（任何丢失都是阻塞问题，不论比例）；每个参与者遇到的主要摩擦被记录并归入路线图条目。At least
  80% of quotes completed without help; at least 80% of returns land on the right passage or say
  plainly that only the page could be found; **no note text lost** in the recovery checks (any
  loss is a blocker, whatever the rate); each participant's main friction recorded and mapped to
  a roadmap item.

### 16.3 U3 — 小规模 Windows 试用 / A small Windows beta（在 M8 的安装包测试之后 after M8's package test）
- **对象 Who:** 10–20 位 Windows 参与者（A 和 B），2–4 周，用现成安装包或源码安装。10–20 Windows participants (A
  and B) for 2–4 weeks, with the ready-to-use package or a source install.
- **怎样收集 How collected:** 开始和结束时的短访谈；每周一次几道题的问卷（是否这周用过、卡在哪里、有没有丢东西）；参与者自愿分享的笔记文件夹
  结构或日志。没有遥测。A short interview at the start and the end; a few-question weekly
  check-in (used it this week? stuck where? lost anything?); a notes-folder layout or log the
  participant chooses to share. No telemetry.
- **提议的成功标准 Proposed success criteria:** 安装和第一次添加 PDF 不需要帮助就完成的人至少 80%；第二周以后仍每周使用的人至少一半；
  没有确认的数据丢失；参与者能说出一件 myLibrary 比他们原来的组合更省事的事（或者明确说没有，这也是证据）。At least 80% install
  and add a first PDF without help; at least half still use it weekly after week two; no
  confirmed data loss; participants can name one thing myLibrary makes easier than their old
  combination (or say plainly that nothing does, which is evidence too).

### 16.4 来源 → 代码 → 结果是否值得做 / Is source → code → result worth building?
在批准 E1–E4 之前回答。现在已经可以不写新代码地试：参与者在章节脚本的注释中手工粘贴 `/read/<id>?page=N` 链接，把结果图手工放进笔记。
Answered before E1–E4 are approved. It can be tried now without new code: participants paste
`/read/<id>?page=N` links into a chapter script's comments by hand and put result plots into
the note by hand.
- **看什么 Look for:** 多少参与者本来就用代码检查书中的内容（U1）；他们多久需要从代码或结果回到原文；手工链接在试用中是否真的被用到（U2、U3）。
  How many participants already check book content in code (U1); how often they need to get
  from code or a result back to the source; whether the hand-made links are actually used in the
  trial (U2, U3).
- **提议的决策规则 Proposed decision rule:** 只有当使用代码的参与者中至少一半说这是经常出现的问题、并且在试用中实际用了手工链接时，才建议开始
  E1；否则 E1–E4 保持为建议，章节脚本保持现状。E1 is recommended only if at least half of the
  code-using participants call it a frequent problem and actually used the hand-made links in
  the trial; otherwise E1–E4 stay proposals and chapter scripts stay as they are.

### 16.5 改变优先级的证据标准 / Evidence for changing priorities
- 改变顺序是**用户的决定**；验证结果只是提议的依据，写进 ROADMAP 时附上证据摘要。A change of order is **the user's
  decision**; validation results are only grounds for a proposal, recorded in the ROADMAP with the
  evidence summary.
- **数据丢失或无法恢复**的报告总是优先于新功能，不论有几个人遇到。Reports of **data loss or unrecoverable
  state** always come before new features, however few people hit them.
- 一个假设只有在**多数相关参与者**（例如 U1 中 A 组的多数）的具体行为支持时，才用来提前某项工作；只来自一两个人的要求记录下来，但不改变顺序。
  A hypothesis moves work forward only when the concrete behaviour of **most relevant
  participants** (e.g. most of group A in U1) supports it; a request from one or two people is
  recorded but doesn't reorder the plan.
- 如果 H7（多 PDF 的书）得到支持，G1 的数据模型和实现可以提议与任务 6 一起做（G1 的设计评估本来就在 M6/M7 之前）；如果 H8（macOS）
  得到支持，X1 可以提议排在 v0.3 完成之后的第一个位置。If H7 (multi-PDF books) is supported, G1's data model
  and implementation can be proposed together with task 6 (G1's design assessment comes before
  M6/M7 anyway); if H8 (macOS) is supported, X1 can be proposed for the first slot after v0.3.
- 如果 U1 已经做过，而 J2/J3 的摩擦（H1、H2）**没有**得到支持，在开始 M6 之前和用户一起重新审视 P0 的范围，而不是悄悄继续。没有做
  U1 时，已批准的顺序照常进行。If U1 has run and the J2/J3 friction (H1, H2) is **not** supported,
  P0's scope is reviewed with the user before M6 starts, rather than carrying on silently.
  Without U1, the approved order goes ahead as it is.
