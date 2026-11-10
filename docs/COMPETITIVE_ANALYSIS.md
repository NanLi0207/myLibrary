# 竞品分析 / Competitive analysis

myLibrary 与 BookxNote Pro、MarginNote 5（及其前身 MarginNote 4）、Zotero 10、Zotero + Obsidian 组合工作流、
Readwise Reader 和 ReadPaper 的工作流比较。目的是找到值得借鉴的做法和真正的工作流差异，而不是证明哪个产品更好。
A workflow comparison of myLibrary with BookxNote Pro, MarginNote 5 (and MarginNote 4, which it
grew from), Zotero 10, the combined Zotero + Obsidian workflow, Readwise Reader and ReadPaper.
The aim is to find practices worth learning from and the genuine workflow differences, not to
prove that any product is better.

**这是桌面研究，不是用户调查 / This is desk research, not a user survey.** 本文只依据公开资料和工作流分析，没有
有代表性的用户样本。文中关于用户需要什么的说法都是**推断或假设**，不是已证明的市场需求；它们列在第 9 节，由
[DEVELOPMENT_SPEC.md 第 16 节](../DEVELOPMENT_SPEC.md#16-用户验证计划--user-validation-plan)的用户验证计划检验。本文不写
市场规模、用户数量或未核实的价格。
This document rests on public sources and workflow analysis only, with no representative
sample of users. Anything it says about what users want is an **inference or a hypothesis**,
not proven market demand; those are listed in section 9 and tested by the user validation plan
in DEVELOPMENT_SPEC section 16. No market sizes, user numbers or unverified prices appear here.

**证据标记 / Evidence labels** (sections 4–9; sections 1–3 name third-party sources inline):
**[F]** 已核实的产品事实（官方资料，注明日期）verified product fact (official source, dated) ·
**[S]** 二手资料（第三方介绍、用户论坛）secondary source (third-party write-up, user forum) ·
**[I]** 本文根据工作流分析做出的推断 our inference from workflow analysis ·
**[H]** 需要用户研究检验的假设 hypothesis that needs user research.

**方法与限制 / Method and limits.**
- 关于其他产品的说法都来自下面列出的公开资料，**没有实际上手测试**：第 1–3 节**检查于 2026-11-09**，第 4–6 节**检查于
  2026-11-10**。资料通过自动摘要阅读；引用原话之前请重读原页面。Every claim about another product comes from
  the public sources cited, **without hands-on testing**: sections 1–3 **checked 2026-11-09**,
  sections 4–6 **checked 2026-11-10**. The sources were read through automated summaries;
  re-read a page before quoting it word for word.
- 优先使用官方资料；第三方资料会注明。**BookxNote 官网（bookxnote.com）在检查时无法连接**，所以该部分只来自第三方资料，
  属于**部分核实**。Official sources first; third-party ones are labelled. **BookxNote's official site
  (bookxnote.com) refused connections when checked**, so that section rests on third-party
  sources and is **partly verified**.
- **"未在资料中找到"不等于"没有这个功能"。** "Not found in the sources checked" never means "doesn't have it".
- 区分三种情况：**原生**功能、**第三方**插件或集成、借助**外部工具**可以完成的工作流。任何应用都可以和外部编程工具一起
  使用；本文比较的是原生的、集成的工作流。Three cases are kept apart: **native** features,
  **third-party** plugins or integrations, and workflows possible with **external tools**. Any of
  these applications can be used alongside external programming tools; this document compares
  native, integrated workflows.
- 商标属于各自的所有者；本文不表示任何认可或合作关系。Trademarks belong to their owners; nothing here implies
  endorsement or affiliation.
- myLibrary 的计划中功能都标为"计划中"，并对应 [ROADMAP.md](../ROADMAP.md) 中的条目。Planned myLibrary features are
  marked "planned", with their item in [ROADMAP.md](../ROADMAP.md).

---

## 1. BookxNote Pro（部分核实 / partly verified）

**版本与平台 / Version and platforms.** winget 软件包索引中为 3.0.0.2023，发布者 BookxSoftware，许可"专有"；Windows
（32/64 位）和 Linux。价格未核实。Version 3.0.0.2023 in the winget package index, publisher
BookxSoftware, licence "Proprietary"; Windows (32/64-bit) and Linux. Price unverified.
[wingetgui](https://wingetgui.com/apps/BookxSoftware-BookxNotePro),
[winget.ragerworks](https://winget.ragerworks.com/package/BookxSoftware.BookxNotePro) (third-party).

**典型工作流 / Typical workflow** (third-party description): 打开 PDF 或 EPUB（自动导入目录）→ 阅读 → 高亮和摘录 →
摘录自动整理成结构化的笔记大纲，内置思维导图 → 导出（图片、Anki 卡片、HTML、XMind、OPML）。Open a PDF or EPUB (its table
of contents imported) → read → highlight and excerpt → excerpts organised into a structured note
outline, with a built-in mind map → export (images, Anki cards, HTML, XMind, OPML).
[ragerworks](https://winget.ragerworks.com/package/BookxSoftware.BookxNotePro).

- **回到原文 / Back to the source:** "外部回链协议"（选项 → 基本设置 → 注册外部回链协议），点击链接在 BookxNote 中打开
  笔记位置；链接中有笔记本、书和 uuid 等 id。An external backlink protocol (Options → Basic settings →
  Register external backlink protocol) opens BookxNote at the note; links carry notebook, book
  and uuid ids. [sspai, 2025-02-24](https://sspai.com/post/96688),
  [PKMer script](https://pkmer.cn/Pkmer-Docs/10-obsidian/obsidian社区插件/excalidraw/自定义excalidraw脚本-实现excalidraw与bookxnote的联动) (third-party).
- **存储 / Storage:** 笔记是 `notebooks` 文件夹中的 JSON 文件（第三方 Obsidian 插件的说明）。标注是否写入 PDF：未核实。
  Notes are JSON files in a `notebooks` folder (per a third-party Obsidian plugin); whether
  annotations are written into the PDF: unverified.
  [bookxnote-sync](https://community.obsidian.md/plugins/bookxnote-sync).
- **集成 / Integrations:** Obsidian 同步、Quicker、Excalidraw 脚本都是第三方的；未找到官方插件系统。Obsidian sync,
  Quicker and Excalidraw scripts are third-party; no official plugin system found.
- **未核实 / Unverified:** 价格、账户要求、云同步、备份、应用内复习、笔记中的 Markdown。Price, account
  requirement, cloud sync, backup, in-app review, Markdown in notes.

**启示 / Lesson [I].** 把 PDF 选区变成有用的笔记内容要**极其容易**：一步完成，自动带上来源。对应 M6（引用到笔记，计划中）。
Make turning a PDF selection into useful note content **extremely easy**: one step, with the
source attached. Corresponds to M6 (quote to note, planned).

---

## 2. MarginNote 5（源自 MarginNote 4 / grown from MarginNote 4）

**版本与平台 / Version and platforms.** 官方"新功能"页面把版本标为 **MarginNote 5 · 5.0.0，2026 年 10 月**，之前是
MN 4.4（2026-05）、4.3（约 2026-03）、4.2（2025-10）、4.0（2024-05）；App Store 中的应用（名为 "MarginNote 4: AI
Notes·MindMap"）显示 5.0.1。MarginNote 5 是现有 MN4 应用的免费更新，保留学习集、笔记和购买记录。平台：iOS/iPadOS 17+、
macOS 14+（另有 DMG）、visionOS 1+。专有软件；免费下载，Pro 一次性购买，Max 订阅或终身，AI 额度另购。
The official What's New page labels it **MarginNote 5 · 5.0.0, October 2026**, after MN 4.4
(2026-05), 4.3 (~2026-03), 4.2 (2025-10) and 4.0 (2024-05); the App Store app (titled
"MarginNote 4: AI Notes·MindMap") shows 5.0.1. MarginNote 5 is a free update of the existing MN4
app that keeps study sets, notes and purchases. Platforms: iOS/iPadOS 17+, macOS 14+ (also a
DMG), visionOS 1+. Proprietary; free download, Pro one-time, Max subscription or lifetime, AI
credits extra.
[What's new](https://www.marginnote.com/en/whats-new/index.html),
[pricing](https://www.marginnote.com/pricing),
[App Store](https://apps.apple.com/us/app/marginnote-4-ai-notes-mindmap/id1531657269).

**MarginNote 4 的工作流 / The MarginNote 4 workflow** it evolved from: 导入文档 → 建立学习集 → 把文字和图片摘录为
**链接回原文的卡片** → 把来自不同文档的卡片排进同一张思维导图 → 复习。Import documents → create a study
set → excerpt text and images into **cards that link back to the source** → arrange cards from
different documents in one mind map → review.
[marginnote.com](https://www.marginnote.com/), [App Store](https://apps.apple.com/us/app/marginnote-4-ai-notes-mindmap/id1531657269).

**MarginNote 5 的变化 / What MarginNote 5 adds** (official pages):
- **模板系统 / Templates:** 从已有模板开始，调整支持的模式、工具和菜单以适应某项任务，并在其他学习集中重用；"标准"模板有
  摘录、手写、整理、回忆四种模式，每种模式只显示该步骤的工具；模板库中的模板可以连同所需的插件一起安装，并可导出分享。
  Start from a template, adjust its modes, tools and menus for a task, and reuse it in other
  study sets; the "Standard" template has Excerpt, Handwrite, Organize and Recall modes, each
  showing only that step's tools; the Template Gallery installs templates with the plug-ins they
  need, and templates can be exported and shared.
  [templates](https://www.marginnote.com/en/features/templates/index.html),
  [What's new](https://www.marginnote.com/en/whats-new/index.html).
- **界面 / Interface:** 场景界面成为默认，可切回传统（MN4）界面；主页"学习集优先"，复习卡组单独一页，一键"今日复习"；
  文档统称为"书库"。The scenario interface is the default, with a switch back to the
  traditional (MN4) layout; a study-sets-first home, review decks on their own page, Today's
  Review in one tap; documents are called "the Library". [What's new](https://www.marginnote.com/en/whats-new/index.html).
- **AI:** 把聊天回答保存为卡片，或把其大纲变为思维导图分支（在设备上转换，可撤销）。Save a chat answer as a card, or
  turn its outline into mind-map branches (converted on device, with undo).
- **复习 / Review:** App Store 的说明提到 FSRS 间隔重复和回忆模式；官方新功能页面没有提到 FSRS。The App Store text
  mentions FSRS spaced repetition and a Recall mode; the What's New page doesn't mention FSRS.
- **备份与恢复（原生）/ Backup and restore (native):** 设置 → 备份与恢复；自 MN 4.3 起有自动备份（本地、WebDAV、百度网盘、
  Google Drive；手动到每周），格式 `.marginbackupall`；"完全导出"有三种粒度；在新设备上导入该文件即可恢复。iCloud 是同步，
  不是备份；应用 iCloud 更改之前会保存历史版本。Settings → Backup & Restore; Auto Backup since MN 4.3
  (Local, WebDAV, Baidu NetDisk, Google Drive; manual to weekly), format `.marginbackupall`;
  Full Export in three granularities; restore by importing that file on a new device. iCloud is
  sync, not backup; a history version is saved before iCloud changes are applied.
  [sync & backup](https://www.marginnote.com/en/features/sync-backup/index.html),
  [What's new](https://www.marginnote.com/en/whats-new/index.html).
- **Markdown:** MN 4.2 的 AI 可把手写和公式转为 Markdown；更早的版本说明提到 Markdown 文本框。笔记是否以 Markdown 文件
  保存：未找到。MN 4.2's AI turns handwriting and formulas into Markdown; older release notes
  mention Markdown text boxes. Whether notes are stored as Markdown files: not found.
- **导出 / Export:** 思维导图可导出为 PDF（App Store）。Anki 和 Markdown 导出在官方页面上未确认（只见于 Setapp 和用户
  论坛）。Mind maps export to PDF (App Store). Anki and Markdown export are not confirmed on
  official pages (only on Setapp and in user forums).
  [Setapp](https://setapp.com/apps/MarginNote),
  [forum: Anki](https://forum.marginnote.com/t/ipados-flash-cards-export-to-anki-link-function/10196),
  [forum: Markdown](https://forum.marginnote.com/t/still-no-export-to-markdown/9316).
- **PDF 标注 / PDF annotations:** 用户报告导出的 PDF 中标注被压平或渲染（2021–2022 年用户帖子，非官方）；内部存储和标注
  id：未找到官方说明。Users report exported PDFs carry flattened or rendered marks (user posts
  2021–2022, not staff); internal storage and annotation ids: no official statement found.
  [forum](https://forum.marginnote.com/t/export-as-pdf-with-my-annotations/5316).
- **未核实 / Unverified:** 离线使用和账户要求的完整说明。A full statement on offline use and account
  requirements.

**启示 / Lesson [I].** 让用户按**自己的知识结构**重新组织来自多个文档的信息，每一条都能回到原文；MarginNote 5 的模板也说明，
**只显示当前步骤需要的工具**能降低复杂度。但不强迫每个用户使用思维导图或卡片：myLibrary 以主题笔记和标签为基础
（v0.4-5、v0.4-6，计划中），思维导图最多是以后的可选视图。Let users reorganise information from several
documents into **their own knowledge structure**, each item back to its source; MarginNote 5's
templates also show that **showing only the tools a step needs** reduces complexity. But no user
should be forced into mind maps or cards: myLibrary builds on topic notes and tags (v0.4-5,
v0.4-6, planned), a mind map at most a later optional view.

---

## 3. Zotero 10.0.8

**版本与平台 / Version and platforms.** **10.0.8，2026-11-06**；macOS、Windows、Linux 桌面版，以及 iOS 和 Android；
AGPLv3 开源；应用免费，数据同步免费不限量；文件存储 300 MB 免费，更多付费。10.0.8, released 2026-11-06;
desktop on macOS, Windows and Linux, plus iOS and Android; AGPLv3 open source; the app is free,
data sync free and unlimited; 300 MB of file storage free, more paid.
[changelog](https://www.zotero.org/support/changelog), [download](https://www.zotero.org/download/),
[licence](https://raw.githubusercontent.com/zotero/zotero/main/COPYING),
[sync](https://www.zotero.org/support/sync), [storage](https://www.zotero.org/storage).

**本地优先 / Local-first.** 数据默认存在本地数据目录（Windows：`C:\Users\<用户名>\Zotero`），核心是 `zotero.sqlite`，附件在
`storage/<8 位键>/`；可以在设置中选择自定义数据目录（Zotero 不会自己搬数据，需要关闭 Zotero 后手动复制）；只有同步需要
账户，个人文库的文件同步可用 WebDAV。Data is stored locally by default (Windows:
`C:\Users\<user>\Zotero`), centred on `zotero.sqlite`, attachments in `storage/<8-character
key>/`; a custom data directory can be chosen in the settings (Zotero doesn't move the data
itself: close it and copy the folder); an account is needed only for sync, and WebDAV can sync
files of a personal library.
[zotero_data](https://www.zotero.org/support/zotero_data), [sync](https://www.zotero.org/support/sync).

**多个文库 / Several libraries.** 除个人的"我的文库"外，原生支持群组文库，它们彼此完全独立，也可以"用作在同一个 Zotero
配置中保持多个独立文库的方法"。Besides the personal My Library, group libraries are native and wholly
separate, and can be used "as a way to keep separate libraries within one Zotero profile".
[groups](https://www.zotero.org/support/groups).

**典型工作流 / Typical workflow:** 管理文献 → 阅读 PDF → 标注 → 把标注加入笔记 → 从笔记回到原文 → 在文字处理软件中引用。
Manage literature → read the PDF → annotate → add annotations to notes → go back from a note to
the source → cite in a word processor.

- **标注存储 / Annotation storage:** 存在 Zotero 数据库中而不是 PDF 中，"以便快速、无冲突地同步"。早期 Zotero 6 的
  "Store Annotations in File…" 因冲突和丢数据风险已移除；现在通过 File → Export PDF…、阅读器的 Save As… 或导出时的
  "Include Annotations" 把标注写进 PDF 副本。PDF 中已有的（其他程序做的）标注只读显示，File → Import Annotations…
  可以把它们变为可编辑并从 PDF 中移除。Stored in the Zotero database, not the PDF, "to enable fast,
  conflict-free syncing". Early Zotero 6's "Store Annotations in File…" was removed because of
  conflict and data-loss risk; annotations go into a PDF copy through File → Export PDF…, the
  reader's Save As… or "Include Annotations" on export. Annotations already in a PDF from
  elsewhere show read-only; File → Import Annotations… makes them editable and removes them
  from the PDF.
  [annotations in database](https://www.zotero.org/support/kb/annotations_in_database),
  [PDF reader](https://www.zotero.org/support/pdf_reader).
- **PDF 被修改时 / When the PDF changes:** 在外部工具中增删、重排或旋转页面，可能使标注"落在错误的页或位置"。整个文件被
  替换的情况未见说明。Adding, deleting, reordering or rotating pages in an outside tool can put
  annotations "on the wrong page or in the wrong position"; replacing a file outright isn't
  addressed. (Same pages.)
- **笔记 → 原文 / Note → source:** 由标注生成的笔记带有回到 PDF 页的链接，"Show on Page" 在阅读器中打开该处。工作人员
  （2021）给出的链接格式 `zotero://open-pdf/library/items/<itemKey>?page=N`；`&annotation=<key>` 只见于用户帖子，未找到
  官方文档。Notes built from annotations link back to the PDF page; "Show on Page" opens the
  reader there. A staff member (2021) gave the format
  `zotero://open-pdf/library/items/<itemKey>?page=N`; `&annotation=<key>` appears only in a user
  post, no official docs found. [forum](https://forums.zotero.org/discussion/comment/517931/).
- **Markdown:** 笔记可导出为 Markdown，可带回到条目和单个标注的 `zotero://` 链接（工作人员，2021-12-16）；编辑器是富文本，
  Markdown 输入未见说明。Notes export to Markdown, optionally with `zotero://` links to items and
  single annotations (staff, 2021-12-16); the editor is rich text, Markdown input not stated.
  [forum](https://forums.zotero.org/discussion/comment/395984), [notes](https://www.zotero.org/support/notes).
- **引用与插件 / Citation and plugins:** 自带 Word、LibreOffice、Google Docs 插件；有插件生态（例如 Better BibTeX 是第三方
  扩展）。Bundled Word, LibreOffice and Google Docs plugins; a plugin ecosystem (e.g. Better
  BibTeX is a third-party extension).
  [word processor integration](https://www.zotero.org/support/word_processor_integration),
  [Better BibTeX](https://retorque.re/zotero-better-bibtex/).
- **未在检查的官方页面中找到 / Not found in the official pages checked:** 思维导图、闪卡、间隔重复。Mind maps,
  flashcards, spaced repetition.
- **未核实 / Unverified:** 原生导出格式的完整列表（检查的页面返回 404）。The full list of native export
  formats (the page checked returned 404).

**启示 / Lesson [I].** 来源引用必须**精确、稳定、可恢复、可验证**。Zotero 说明了两点：标注身份不应只依赖 PDF 文件本身；PDF
被修改时锚点可能失效，必须能察觉并明确处理。myLibrary 把标注保存在 PDF 中（PDF.js），每个文档有永久 UUID；计划中的锚点
模型加入 PDF 指纹和分级回退（任务 5，[DEVELOPMENT_SPEC.md 第 9 节](../DEVELOPMENT_SPEC.md#9-来源锚点与数据模型--source-anchors-and-data-models)）。
Source references must be **precise, stable, recoverable and verifiable**. Zotero shows two
things: annotation identity shouldn't depend on the PDF file alone, and anchors can break when a
PDF changes, which must be detected and handled visibly. myLibrary keeps marks inside the PDF
(PDF.js) and gives every document a permanent UUID; the planned anchor model adds a PDF
fingerprint and graded fallback (task 5, DEVELOPMENT_SPEC section 9).

---

## 4. Zotero + Obsidian 组合工作流 / The Zotero + Obsidian workflow

这不是一个产品，而是很多研究者自己搭的组合：Zotero 管文献和 PDF 标注，Obsidian 管 Markdown 笔记，中间用社区插件连接。
Zotero 一方的事实见第 3 节。Not one product but a combination many researchers assemble
themselves: Zotero for literature and PDF annotations, Obsidian for Markdown notes, a community
plugin in between. Zotero's side is in section 3.

**Obsidian（官方资料，2026-11-10）/ Obsidian (official sources, 2026-11-10).**
- [F] 笔记是"仓库"（vault，本地文件系统中的一个文件夹）里的 Markdown 纯文本文件；仓库的设置在 `.obsidian` 文件夹中；可以用
  Obsidian Sync、Dropbox、iCloud、OneDrive、Git 等同步。Notes are "Markdown-formatted plain text files in a
  vault", and "a vault is a folder on your local file system"; vault settings live in a
  `.obsidian` folder; sync through Obsidian Sync, Dropbox, iCloud, OneDrive, Git and others.
  [data storage](https://obsidian.md/help/data-storage).
- [F] "Free without limits"，不需要注册，数据存在本地设备上；Sync 和 Publish 是付费附加服务；商业许可是可选的（"You are not
  required to pay for a commercial license"）。"Free without limits", no sign-up, data stored
  locally; Sync and Publish are paid add-ons; the commercial licence is optional.
  [pricing](https://obsidian.md/pricing).
- [F] 下载页（版本 1.15.0）：Windows、macOS、Linux（AppImage、Snap、Deb；Flatpak 由社区维护）、Android、iOS。The download
  page (version 1.15.0): Windows, macOS, Linux (AppImage, Snap, Deb; Flatpak community-maintained),
  Android, iOS. [download](https://obsidian.md/download).
- [F] 支持的文件类型包括 PDF，PDF 可以直接嵌入笔记。Supported file types include PDF, and PDFs "can be
  embedded directly into your notes". [file formats](https://obsidian.md/help/file-formats).

**连接插件 / The bridge plugin** — Zotero Integration（社区插件，对 Zotero 和 Obsidian 都是第三方 🔌 community plugin,
third-party to both apps）：
- [F] "Insert and import citations, bibliographies, notes, and PDF annotations from Zotero into
  Obsidian. Requires the Better BibTeX for Zotero plugin." 导入的标注类型：高亮、下划线、删除线、注释、矩形（矩形变为
  图片）；模板字段包括标注文字、颜色、页码、评论、日期。Imported annotation types: highlights,
  underlines, strikethroughs, notes, rectangles (rectangles become images); template fields
  include the annotated text, colour, page, comment and date.
  [README](https://github.com/community-archive/obsidian-zotero-integration),
  [PDF annotations](https://github.com/community-archive/obsidian-zotero-integration/blob/main/docs/PDF%20Annotations.md),
  [templating](https://github.com/community-archive/obsidian-zotero-integration/blob/main/docs/Templating.md).
- [F] 原来的地址 `github.com/mgmeyers/obsidian-zotero-integration` 现在转到 `community-archive` 组织；README 说文档"currently
  incomplete"。维护状态未核实。The original address now redirects to a `community-archive`
  organisation; the README says the documentation is "currently incomplete". Maintenance status
  not verified.
- ❓ 导入的标注是否带回到 Zotero 中 PDF 该页的链接：所读的模板和导出设置文档中未提到。Whether an imported
  annotation carries a link back to the page in Zotero: not stated in the templating and export
  docs read. (Zotero's own Markdown export can include `zotero://` links, section 3.)

**典型工作流 / Typical workflow** [S/I]: 在 Zotero 中收集和标注 → 用插件把标注导入 Obsidian 的文献笔记 → 在 Obsidian 中写作和
链接 → 需要原文时回到 Zotero。Collect and annotate in Zotero → import the annotations into a
literature note in Obsidian through the plugin → write and link in Obsidian → go back to Zotero
for the source.

**摩擦 / Friction** [I]: 两个应用、两个数据存储，靠两个第三方插件（Better BibTeX 和桥接插件）连接；导入的标注是一份副本，
之后在 Zotero 中的修改是否同步回来未核实；能否回到原文取决于模板设置。Two apps and two data stores, joined
by two third-party plugins (Better BibTeX and the bridge); imported annotations are a copy, and
whether later changes in Zotero flow back wasn't checked; getting back to the source depends on
the template.

**启示 / Lesson [I].** Obsidian 说明了**开放的 Markdown 文件夹**的价值：笔记属于用户，任何工具都能读写，生态可以围绕它
生长。myLibrary 的笔记已经是普通 `.md` 文件；应该保持它们在其他 Markdown 工具中可读、来源链接是普通链接，并且与用户已有的
工具**并存**，而不是取代它们。这个组合也说明了 myLibrary 能减少的摩擦：阅读、标注、笔记和回到原文在同一个本地工作流中，
不需要插件链。Obsidian shows the value of an **open Markdown folder**: the notes belong to the
user, any tool can read and write them, and an ecosystem can grow around them. myLibrary's notes
are already plain `.md` files; they should stay readable in other Markdown tools, with source
links as ordinary links, and **coexist** with the tools users already have rather than replace
them. The combination also shows the friction myLibrary can reduce: reading, marking, notes and
the way back to the source in one local workflow, with no plugin chain.

---

## 5. Readwise Reader

**版本与平台 / Version and platforms** [F]（官方资料 official sources, 2026-11-10）: iOS 和 Android 应用；网页应用和
Chrome、Firefox、Safari 扩展；Mac 和 Windows 桌面应用；电子墨水模式；Linux 未列出。iOS and Android apps; a web app
and Chrome, Firefox and Safari extensions; Mac and Windows desktop apps; an e-ink mode; Linux not
listed. [readwise.io/read](https://readwise.io/read). 版本号未记录 version number not recorded.

**账户与价格 / Account and price** [F]: 需要创建账户；30 天免费试用，不需要信用卡；之后需要订阅（检查时 Full Readwise 按年付
每月 9.99 美元，只用 Reader 按年付每月 7.99 美元）。An account is required; a free 30-day trial without a
credit card; a subscription afterwards (when checked: Full Readwise USD 9.99/month billed
annually, Reader only USD 7.99/month billed annually).
[readwise.io/read](https://readwise.io/read), [pricing](https://readwise.io/pricing).

- **存储与离线 / Storage and offline** [F]: "Reader also works offline"；"Everything syncs continuously across
  your devices"；文档"stay in your account"。具体的云端存储方式未说明。The exact storage arrangement isn't
  stated. [readwise.io/read](https://readwise.io/read), [pricing](https://readwise.io/pricing).
- **PDF** [F]: 支持 PDF 和 EPUB；可以高亮图片、表格和富文本；PDF 的"快照"工具把选中的区域作为图片存进笔记本；网页版可下载带标注的
  PDF（Shift+D）；其他 PDF 应用中做的高亮不会被导入（"on our roadmap"）。PDFs and EPUBs; highlights on
  images, tables and rich text; a snapshot tool saves a selected PDF area as an image in the
  Notebook; the web app downloads an annotated PDF (Shift+D); highlights made in other PDF apps
  are not imported ("on our roadmap").
  [PDF FAQ](https://docs.readwise.io/reader/docs/faqs/pdfs).
- **导出 / Export** [F]: 每个文档的笔记和高亮可下载为 Markdown（模板可编辑）；文档列表 CSV、订阅 OPML、上传文件的 ZIP；高亮通过
  Readwise 导出到 Obsidian 和 Notion（Highlights Lite 方案不含导出）；"带标注打印"只在网页版。A document's notes
  and highlights download as Markdown (editable template); a CSV of documents, OPML of feeds, a
  ZIP of uploaded files; highlights export to Obsidian and Notion through Readwise (not in
  Highlights Lite); "print with annotations" is web-only.
  [exporting](https://docs.readwise.io/reader/docs/faqs/exporting), [pricing](https://readwise.io/pricing).
- ❓ 从导出的笔记回到 PDF 中原处的链接：未检查。A link from exported notes back to the place in the
  PDF: not checked.

**典型工作流 / Typical workflow** [I]: 把文章、PDF、电子书收进一个收件箱 → 阅读时一个动作高亮 → 高亮和笔记自动进入笔记本并同步 →
以后回顾，或导出到笔记软件。Save articles, PDFs and books into one inbox → highlight in one gesture
while reading → highlights and notes land in the Notebook and sync → revisit later, or export to
a notes app.

**启示 / Lesson [I].** **低摩擦的捕捉和回顾**：一个动作完成高亮，高亮立刻成为可以回顾、可以导出的内容。对 myLibrary：引用到笔记
必须一步完成（M6），回到原文必须一点即达（M7）；回顾（R1–R3）是以后的事，并取决于用户验证。不同之处在于数据模型：Reader
基于账户和订阅、跨设备同步；myLibrary 是本地文件夹，没有账户，也没有同步或移动端。**Low-friction capture and
revisiting**: one gesture makes a highlight, and the highlight is at once something to revisit
and export. For myLibrary: quote to note must be one step (M6) and the way back one click (M7);
revisiting (R1–R3) comes later and depends on user validation. The data model differs: Reader
is account- and subscription-based with sync across devices; myLibrary is a local folder, with
no account, and no sync or mobile apps.

---

## 6. ReadPaper

**带日期的通知，不是产品功能 / Dated notices, not product features.** 下面的通知描述的是 2026 年秋季的一次过渡，
不是 ReadPaper 长期的功能；日期过后应重新检查。The notices below describe a transition in autumn 2026, not
lasting ReadPaper functionality; re-check them once the dates have passed.
- [S] **最初的计划：10 月 31 日关停 / The original plan: shutdown on 31 October.** 一份题为"ReadPaper 旧版站点关停通知"
  （ReadPaper 旧版站点关停通知 / ReadPaper legacy site shutdown notice）、署名 ReadPaper 团队的通知说旧版站点计划在 10 月 31 日关停。用户
  2026-11-10 在一个**第三方网站**上看到这份通知（[scigreat.com 上的副本 copy on scigreat.com](https://www.scigreat.com/?golink=aHR0cHM6Ly9yZWFkcGFwZXIuY29tLw%3D%3D&nonce=fb47db48a3)）；
  同一天的自动检查从这个链接只得到"非法请求，正在返回首页..."（非法请求，正在返回首页），readpaper.com 上也已不再显示这份通知。所以它只是
  第三方转载的、无法复查的资料，不是 ReadPaper 自己的页面；年份没有说明。A notice titled "ReadPaper 旧版站点关停通知"
  (ReadPaper legacy site shutdown notice), signed by the ReadPaper team, describes a planned
  shutdown of the legacy site on 31 October. The user saw it on 2026-11-10 on a **third-party
  site**; an automated check the same day got only "illegal request, returning to the home page"
  from that link, and readpaper.com no longer shows the notice. So it is a third-party copy that
  couldn't be re-checked, not a ReadPaper page; no year is stated.
- [F] **之后：临时重启导出，11 月 15 日最终截止 / Later: export temporarily reopened, final cutoff on 15 November**
  （readpaper.com 首页和 /about 页面的"关站提醒"（site-closure reminder），检查于 2026-11-10，页面未写年份 no year on the
  page）："为了给还未迁移的同学留出从容的准备时间，我们临时重启数据导出接口。"（为了给还未迁移的用户留出准备时间，临时重启数据导出接口）；
  "ReadPaper将于11月15日正式切换为Agent新版，到期后旧版将关闭全部数据导出功能，无法再备份资料。"（11 月 15 日正式切换为 Agent 新版，
  之后旧版关闭全部数据导出功能，无法再备份资料）；"请尽快导出、迁移你的文献与笔记。"（请尽快导出、迁移文献与笔记）。可导出的内容和格式没有
  说明。"To give users who haven't migrated yet time to prepare, we have temporarily restarted the
  data-export interface"; ReadPaper switches to the new Agent version on 15 November, after
  which the old version closes all data export and backups can no longer be made; users are
  asked to export and migrate their literature and notes soon. What can be exported, and in
  which formats, isn't stated. [readpaper.com/about](https://readpaper.com/about),
  [readpaper.com](https://readpaper.com).
- 这些日期是检查当天的通知内容，**不保证仍然有效**；之后可能再次改变。These dates are what the notices said on
  the day they were checked and **are not guaranteed to stay current**; they may change again.
- [F] downloads.readpaper.com 是 "ReadPaper Desktop" 的下载页："当前为 Alpha 测试版，使用前请备份重要文档"（当前为 Alpha
  测试版，使用前请备份重要文档）；Mac（Apple Silicon、Intel）和 Windows（x64、ARM64）安装程序；版本记录在检查时没有载入。
  A download page for "ReadPaper Desktop": currently an Alpha test version, "back up important
  documents before use"; installers for Mac (Apple Silicon, Intel) and Windows (x64, ARM64); the
  changelog didn't load when checked. [downloads.readpaper.com](https://downloads.readpaper.com).
- ❓ App Store 页面（中国区和英国区）在检查时返回 404，开发者、版本和日期未核实。The App Store pages (China and
  UK) returned 404 when checked; developer, version and date unverified.

**二手资料（未在官方页面核实）/ Secondary sources (not verified on official pages)** [S]: 第三方介绍和较早的应用
商店、浏览器扩展页面描述了：全文对照翻译和划词翻译；AI 解读论文；高亮、笔记、手写和截图；文件夹和标签；iPad、Windows、Mac 和
网页之间的云同步；Word 插件和 BibTeX 引用。各来源给出的免费额度互相矛盾，这里不采用。Third-party write-ups and older
app-store and browser-extension pages describe: side-by-side full-text and selection
translation; AI explanation of papers; highlights, notes, handwriting and screenshots; folders
and tags; cloud sync between iPad, Windows, Mac and the web; a Word plugin and BibTeX citation.
The free quotas they give contradict each other and aren't used here.
[ai-bot.cn](https://ai-bot.cn/readpaper/),
[Chrome Web Store](https://chrome.google.com/webstore/detail/readpaper-importer/nchidjaafkcjdgdbbdpkpokodiehhcdg).

**启示 / Lesson [I].** ReadPaper 说明**面向中文读者的学术阅读**是一个真实的产品方向：翻译、术语和阅读辅助放在阅读器中，而不是
另一个工具里。myLibrary 的英汉查词和学科术语表服务于同样的读者。2026 年秋季的官方通知同时说明了**可移植性和数据所有权**为什么重要：当笔记和
标注存在一项服务中时，能否导出、何时导出由提供方决定。myLibrary 的回答是普通文件：PDF 中的标注、`.md` 笔记、CSV 目录、💾 备份，
不依赖任何导出功能。ReadPaper shows that **academic reading for Chinese-speaking readers** is a
real product direction: translation, terms and reading aids inside the reader rather than in
another tool. myLibrary's English–Chinese lookup and subject glossaries serve the same readers.
The official notice of autumn 2026 also shows why **portability and data ownership** matter: when notes and
annotations live in a service, whether and when they can be exported is the provider's
decision. myLibrary's answer is ordinary files: marks in the PDF, `.md` notes, a CSV catalog and
💾 backups, with no export feature to depend on.

---

## 7. 对比 / Comparison

✅ 原生，已核实 native, verified · 📋 myLibrary 计划中 planned · 🔌 第三方插件或集成 third-party · 🧰 借助外部工具的工作流
via external tools · ❓ 未核实 unverified. 其他产品只代表上面引用的资料（2026-11-09）；myLibrary 以 2026-11-09 核对时的
代码为准（`d6c1a5d`），之后的变化见 [ROADMAP.md](../ROADMAP.md)。Other products: only what the cited sources
say (2026-11-09); myLibrary: the code as checked on 2026-11-09 (`d6c1a5d`), later changes in the
ROADMAP.

| 方面 Aspect | myLibrary | BookxNote Pro（部分核实 partly verified） | MarginNote 5 | Zotero 10.0.8 |
|---|---|---|---|---|
| PDF 阅读 PDF reading | ✅ PDF.js（浏览器中 in the browser） | ✅ PDF, EPUB | ✅ | ✅ |
| 标注 Annotation | ✅ 保存在 PDF 中 saved into the PDF | ✅（存储方式 ❓ storage ❓） | ✅（内部格式 ❓ internal format ❓） | ✅ 保存在数据库中，可导出到 PDF in the database, exportable into a PDF |
| 笔记格式 Note format | ✅ 普通 `.md` 文件 plain `.md` files | JSON（第三方说明 third-party description） | 应用数据库；AI 可生成 Markdown app database; AI can produce Markdown ❓ | 数据库中的富文本，可导出 Markdown rich text in the database, Markdown export |
| 标注 → 笔记 Annotation to note | 📋 M6 | ✅ 摘录 → 大纲 excerpt → outline | ✅ 摘录 → 卡片 excerpt → card | ✅ 标注加入笔记 annotations into notes |
| 回到原文 Back to the source | ✅ 页面级 page level（`/read/<id>?page=N`）；📋 段落级 passage level (M7) | ✅ 回链协议 backlink protocol | ✅ 卡片链接回原文 cards link back | ✅ Show on Page, `zotero://open-pdf` |
| 跨文档组织 Cross-document organisation | ✅ 主题笔记 topic notes；📋 连接来源的主题、标签 topics linking sources, tags (v0.4) | ✅ 大纲、思维导图（每本书）outline, mind map (per book) ❓ | ✅ 学习集、卡片、思维导图 study sets, cards, mind maps | ✅ 集合、标签、相关条目 collections, tags, related items |
| 复习 Review | ✅ 生词卡片（Leitner）vocabulary cards；📋 笔记问答 note Q&A (R1–R3) | 导出到 Anki export to Anki（第三方说明 third-party description） | ✅ 复习卡组 review decks（FSRS：App Store） | 未找到 not found（🔌 插件可能 plugins may） |
| 本地优先 Local-first | ✅ 书库文件夹中的普通文件 plain files in a library folder | ✅ 本地文件（第三方说明 third-party description） | ✅ 本地数据，iCloud 同步可选 local data, optional iCloud sync | ✅ 本地数据目录，同步可选 local data directory, optional sync |
| 备份与迁移 Backup and moving | ✅ 💾 zip 备份；整个文件夹可复制到别的电脑 zip backups; copy the whole folder to another computer | ❓ | ✅ 自动备份（本地、WebDAV、网盘）、完全导出、在新设备恢复 Auto Backup (local, WebDAV, cloud drives), Full Export, restore on a new device | ✅ 数据目录可手动复制；同步 data directory copied by hand; sync |
| 多个库 Several libraries | ✅ 多个**独立的书库文件夹**，各自完整、可单独复制，各由自己的服务器打开 several **independent library folders**, each complete, copied on its own, opened by its own server | ❓ | ✅ 一个应用中的多个学习集 several study sets in one app | ✅ 同一数据目录中的"我的文库"和各自独立的群组文库（为协作和同步设计）My Library and separate group libraries in one data directory (built for collaboration and sync) |
| 文档身份 Document identity | ✅ 每个文档永久 UUID，与文件名无关 a permanent UUID per document, independent of the file name | ✅ uuid（回链 in backlinks） | ❓ | ✅ 条目键 item keys |
| 外部编辑器 External editor | ✅ 原生设置：VS Code、记事本、系统、自定义 native setting: VS Code, Notepad, system, custom | 🔌 Obsidian 同步 Obsidian sync | ❓ | 🔌 插件 plugins；🧰 导出 export |
| 代码与计算 Code and computation | ✅ 章节 Python 脚本、书库的 `code/`、科学计算依赖组 chapter Python scripts, the library's `code/`, a scientific dependency group；📋 E1–E4 | 🧰 | 🧰；🔌 模板插件 template plug-ins ❓ | 🧰；🔌 插件 plugins |
| 离线 Offline | ✅ 核心功能 core features | ❓ | ❓ | ✅ 本地数据 local data |
| 引用管理 Citation | 基础：BibTeX 导出 basic: BibTeX export | ❓ | ❓ | ✅ 成熟，文字处理插件 mature, word-processor plugins |
| 平台 Platforms | Windows（已测试 tested）；macOS/Linux 未测试 untested | Windows, Linux | Apple 平台 Apple platforms | 三种桌面系统和移动端 three desktop systems and mobile |
| 许可 Licence | PolyForm 非商业；付费的现成安装包 PolyForm Noncommercial; a paid ready-to-use package | 专有 proprietary | 专有 proprietary | AGPLv3 |

**第 4–6 节的工作流 / The workflows of sections 4–6** (检查于 checked 2026-11-10；同样的标记 same markers):

| 方面 Aspect | myLibrary | Zotero + Obsidian | Readwise Reader | ReadPaper |
|---|---|---|---|---|
| 数据在哪里 Where the data lives | ✅ 一个本地书库文件夹 one local library folder | ✅ Zotero 数据目录 + Obsidian 仓库文件夹，都在本地 Zotero data directory + Obsidian vault folder, both local | ✅ 用户账户，跨设备同步 the user's account, synced across devices | 云同步 cloud sync（[S]）；❓ |
| 笔记格式 Note format | ✅ 普通 `.md` plain `.md` | ✅ 普通 `.md`（Obsidian）plain `.md` (Obsidian) | 应用内；可下载 Markdown in-app; Markdown download | ❓ |
| PDF 标注 PDF marks | ✅ 保存在 PDF 中 saved into the PDF | ✅ Zotero 数据库 Zotero database | ✅ 高亮；网页版可下载带标注的 PDF highlights; annotated PDF download (web) | 高亮、笔记 highlights, notes（[S]） |
| 标注 → 笔记 Mark to note | 📋 M6 | 🔌 桥接插件导入 imported by the bridge plugin | ✅ 自动进入笔记本 straight into the Notebook | ❓ |
| 回到原文 Back to the source | ✅ 页面级 page level；📋 段落级 passage level (M7) | 🔌 取决于模板 depends on the template ❓ | ❓ 未检查 not checked | ❓ |
| 账户 Account | ✅ 不需要 none | ✅ 本地使用不需要（只有同步需要）none for local use (sync only) | 需要，试用后订阅 required, subscription after the trial | ❓ |
| 离线 Offline | ✅ 核心功能 core features | ✅ 本地数据 local data | ✅ "works offline" | ❓ |
| 可移植 Portability | ✅ 普通文件；💾 zip 备份 plain files; zip backups | ✅ 普通文件夹 plain folders | ✅ Markdown、CSV、OPML、ZIP 导出 exports | 通知：11 月 15 日后旧版关闭数据导出 notice: the old version's data export closes after 15 November ([F]，2026-11-10，带日期的通知 dated notice) |
| 中文阅读辅助 Chinese reading aids | ✅ 英汉查词、术语表 English–Chinese lookup, glossaries | 🔌 ❓ | ❓ | 翻译 translation（[S]） |
| 平台 Platforms | Windows（已测试 tested） | 桌面三种系统和移动端 three desktop systems and mobile | 网页、Windows、Mac、iOS、Android web, Windows, Mac, iOS, Android | Windows、Mac 桌面版（Alpha）Windows, Mac desktop (Alpha)；其他 others [S] |
| 代码与计算 Code and computation | ✅ 章节脚本、`code/` chapter scripts, `code/`；📋 E1–E4 | 🧰 | 🧰 | 🧰 |

---

## 8. myLibrary 的定位 / Where myLibrary stands

**三个支柱：学习、阅读、笔记。可执行学习是可选的差异化能力。**
**Three pillars: learning, reading, note-taking. Executable learning is an optional
differentiator.**

**目标定位 / Target positioning** ([DEVELOPMENT_SPEC.md 第 2 节](../DEVELOPMENT_SPEC.md#2-产品愿景与定位--product-vision-and-positioning))：
一个本地优先的知识与实践工作空间，用于从技术文档中深入学习。首要承诺是低摩擦、可追溯的阅读和笔记；独特的高级工作流是
PDF/来源 → Markdown 笔记 → 代码或实验 → 结果 → 原文（可选）。A local-first knowledge and practice workspace for
deep learning from technical documents. The primary promise is low-friction, traceable reading
and note-taking; the distinctive advanced workflow is PDF/source → Markdown note → code or
experiment → result → original source (optional).

**差异不在于别的软件做不到，而在于 myLibrary 把这些放在一个简单的本地工作流里：**
**The difference isn't that other software can't do these things; it's that myLibrary puts them
together in one simple, local workflow:**

1. 本地的、用户可以直接访问的 PDF 书库（普通文件夹）。Local PDF libraries the user can access directly (an
   ordinary folder).
2. 普通的 Markdown 笔记文件。Plain Markdown note files.
3. 稳定的文档身份（永久 UUID）和可迁移的书库。Stable document identities (permanent UUIDs) and portable
   libraries.
4. 可配置的外部编辑器。Configurable external editors.
5. 与章节关联的代码示例，以及可复用的科学计算代码（`code/`）。Chapter-associated code examples and reusable
   scientific code (`code/`).
6. **计划中：**与来源关联的知识和可复现的学习工作流（M6/M7、任务 5、E1–E4）。**Planned:** source-linked
   knowledge and a reproducible learning workflow (M6/M7, task 5, E1–E4).

**可执行学习——不止于阅读，更通过实践掌握知识。/ Executable Learning — go beyond reading, learn by
implementing.** 读一章，打开该章的脚本，实现公式，运行并与书中结果对比，把结论写进笔记，再回到原文。这对工程、数学、物理、
编程、数据分析和科研尤其有用；对不需要它的学科，它保持隐藏（设置中可关闭）。Read a chapter, open its script,
implement the equations, run them and compare with the book, write the conclusions into the
note, return to the source. Especially useful in engineering, mathematics, physics, programming,
data analysis and research; for subjects that don't need it, it stays out of the way (switchable
in Settings).

**需要学习的 / To learn from** [I]:

| 产品 Product | 借鉴什么 Lesson | myLibrary 中对应的工作 Where it lands |
|---|---|---|
| BookxNote Pro | 高效的 PDF 摘录和笔记整理 efficient PDF extraction and note organisation | M6 引用到笔记 quote to note |
| MarginNote 5 | 面向任务的学习、知识重组、按步骤精简工具 task-oriented study, restructuring knowledge, step-focused tools | v0.4-5/6（不强制思维导图 no mind map forced） |
| Zotero | 可靠的文献管理、标注和引用 reliable literature management, annotation and citation | 任务 5 Task 5；只做基础引用 basic citation only |
| Obsidian | 开放的 Markdown 知识管理和互操作 open Markdown knowledge management, interoperability | 普通 `.md` 笔记、普通链接，与用户已有的工具并存 plain `.md` notes, ordinary links, coexisting with users' tools |
| Readwise Reader | 低摩擦的捕捉、高亮和回顾 low-friction capture, highlighting, revisiting | M6/M7 一步完成 one step；R1–R3 以后 later |
| ReadPaper | 中文学术阅读工作流；注意可移植性和数据所有权 Chinese academic-reading workflows; mind portability and data ownership | 英汉查词、术语表 English–Chinese lookup, glossaries；普通文件 plain files (DS-4) |

**不去照搬 / Not copied for the sake of a feature list:** MarginNote 的模板系统、Zotero 完整的引用管理系统（myLibrary 不打算
取代 Zotero 的生态）、思维导图优先的工作流、Obsidian 的插件生态、Readwise 的账户和同步服务、全文翻译。只借鉴能让 myLibrary 自己的
工作流更可靠、更简单的做法。MarginNote's template system, Zotero's complete citation-management system
(myLibrary doesn't aim to replace Zotero's ecosystem), a mind-map-first workflow, Obsidian's
plugin ecosystem, Readwise's account-and-sync service, full-text translation. Only practices that
make myLibrary's own workflow more reliable and simpler are adopted.

**两种"多个库"并不相同 / Two kinds of "several libraries".** myLibrary 的每个书库是一个独立的普通文件夹（PDF、笔记、
目录、阅读记录都在里面），可以整个复制或移动；Zotero 的群组文库与"我的文库"在同一个 Zotero 数据目录中，主要为共享和同步
设计。两者解决的问题不同，没有优劣之分。Each myLibrary library is an independent ordinary folder (PDFs,
notes, catalog, reading log inside), copied or moved as a whole; Zotero's group libraries sit
with My Library in one Zotero data directory, designed mainly for sharing and sync. They solve
different problems; neither is "better".

**myLibrary 较弱的地方 / Where myLibrary is weaker:** 引用管理远不如 Zotero；没有移动端、同步或网页捕捉；只在 Windows 上测试过；
没有全文翻译；没有思维导图和完整的间隔重复；引用到笔记和段落级回到原文还在计划中。Citation management is far
behind Zotero; no mobile apps, sync or web capture; tested only on Windows; no full-text
translation; no mind maps or full spaced repetition; quote to note and passage-level navigation
are still planned.

**不因竞品改变开发顺序 / Competitors don't reorder the plan.** 先完成已批准的 Markdown 笔记、引用到笔记、回到原文
（任务 4），再做更大的知识管理功能（[ROADMAP.md](../ROADMAP.md)）。First finish the approved Markdown notes,
quote to note and back to the passage (task 4), then larger knowledge-management features.

---

## 9. 需要用户研究检验的假设 / Hypotheses for user research

以下都是 **[H] 假设**，来自上面的工作流分析，**没有用户数据支持**。它们由
[DEVELOPMENT_SPEC.md 第 16 节](../DEVELOPMENT_SPEC.md#16-用户验证计划--user-validation-plan)的验证计划（U1–U3）检验；
结果出来之前，不能把它们当作需求的证据。All of these are **[H] hypotheses** from the workflow analysis
above, **with no user data behind them**. The validation plan (U1–U3) in DEVELOPMENT_SPEC
section 16 tests them; until then they are no evidence of demand.

| # | 假设 Hypothesis | 检验 Tested in |
|---|---|---|
| H1 | 技术教材学习者最大的摩擦是在 PDF 阅读器和笔记之间来回（复制段落、丢失页码）。For technical-textbook learners the biggest friction is moving between the PDF reader and the notes (copying passages, losing the page). | U1, U2 |
| H2 | 一步带链接的引用和一点即达的回到原文会被经常使用。A one-step quote with a link, and a one-click way back, would be used often. | U2, U3 |
| H3 | 本地、普通文件的所有权对这些用户足够重要，愿意因此接受较少的功能（没有同步、没有移动端）。Local ownership in plain files matters enough to these users to accept fewer features (no sync, no mobile). | U1, U3 |
| H4 | 已经组合使用 Zotero、Obsidian、VS Code、Jupyter 的用户想减少切换，而不是换掉这些工具。Users who already combine Zotero, Obsidian, VS Code and Jupyter want fewer switches, not replacements. | U1 |
| H5 | 来源 → 代码 → 结果的链接对一部分用户（主要是工程师和计算型学习者）解决一个经常出现的问题，对多数用户不是。Source → code → result links solve a frequent problem for some users (mainly engineers and computational learners), not for most. | U1, U2, U3 |
| H6 | 中文读者在阅读英文技术书时更需要术语和查词，而不是全文翻译。Chinese-speaking readers of English technical books need terms and word lookup more than full-text translation. | U1 |
| H7 | 一章一个 PDF、几章一个 PDF、一本书分成多个 PDF 的情况在目标用户中常见。One PDF per chapter, several chapters per PDF, or one book in several PDFs is common among target users. | U1 |
| H8 | 首要目标用户中有相当一部分使用 macOS。A significant share of the primary audience uses macOS. | U1 |
