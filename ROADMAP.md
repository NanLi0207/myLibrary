# myLibrary 路线图 / Roadmap

本文件是当前的开发计划：现在做什么、接下来做什么、每一步怎样才算完成。产品目标和要求见
[DEVELOPMENT_SPEC.md](DEVELOPMENT_SPEC.md)；已完成工作的设计、决定、错误报告和验证记录原样保留在
[docs/history/ROADMAP_HISTORY.md](docs/history/ROADMAP_HISTORY.md)（下文简称"历史记录"）。
This file is the active development plan: what is being done now, what comes next, and when
each step counts as done. Product goals and requirements are in
[DEVELOPMENT_SPEC.md](DEVELOPMENT_SPEC.md). The designs, decisions, bug reports and verification
records of past work are kept unchanged in
[docs/history/ROADMAP_HISTORY.md](docs/history/ROADMAP_HISTORY.md) (below: "the history").

**更新规则 / Keeping it current.** 代码改动时在同一次提交里更新本文件：完成的条目写上提交号，发现的错误和限制写进
第 11 节（写函数或文件名，不写行号），修好的移到"已修复"。计划改变时改这里，不留过时内容。
Update this file in the same change as the code: give finished items their commit, add bugs
and limitations to section 11 (name the function or file, not a line number), move fixed ones
to "fixed". When a plan changes, change it here; never leave it stale.

---

## 0. 怎样读这份路线图 / How to read this roadmap

### 0.1 状态 / Status

| 状态 Status | 含义 Meaning |
|---|---|
| ✅ 已完成并提交 Done and committed | 实现、测试、提交（并推送）；写明提交号。Implemented, tested, committed (and pushed); commit given. |
| 🧪 已实现并测试，未提交 Implemented, tested, not committed | 本地完成，等待用户审核后提交。Done locally, waiting for the user's review before a commit. |
| 👀 已实现，待审核 Implemented, awaiting review | 已提交，但用户的人工验收或某项验证（如安装包）还没完成。Committed, but the user's manual acceptance or a named check (e.g. the package) is still open. |
| 🔨 进行中 In progress | 已批准，正在做。Approved and being worked on. |
| 📋 计划中 Planned | 已写入计划；开始前要按下文规则得到批准。In the plan; needs approval as below before work starts. |
| ⏸ 暂缓 / 受阻 Deferred or blocked | 等待某个前提或决定；写明原因。Waiting for a prerequisite or decision; the reason is given. |

**里程碑完成的标准 / Definition of Done (every milestone).** 只有同时满足以下几点才算完成：
A milestone is done only when all of these hold:
1. 交付物全部实现，没有降低已有行为。All deliverables implemented; no existing behaviour degraded.
2. 新行为有确定性的回归测试；涉及阅读器的改动有浏览器测试。Deterministic regression tests for new behaviour;
   browser tests for reader changes.
3. `uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .` 通过；需要时浏览器测试通过；Windows CI 通过。
   `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` pass; browser tests
   where relevant; Windows CI green.
4. 没有动过真实书库 `library/`；破坏性情形只在临时文件夹中测试。The real `library/` untouched;
   destructive cases tested only in temporary folders.
5. 本文件、用户指南和（必要时）CLAUDE.md 已更新；未验证的部分明确写出。This file, the user guide and (if
   needed) CLAUDE.md updated; anything not verified is said so.
6. 用户批准后才提交。Committed only after the user's approval.

### 0.2 编号 / Numbering

- **已有编号保持不变 / Existing ids stay.** v0.3 的任务 1–8、任务 4 的里程碑 M1–M8（含 M5a–M5d）、v0.4 和
  v0.5 的条目（下文写作 v0.4-N、v0.5-N）、第 4b 节（多个书库）、错误编号 D/B/L 都沿用历史记录中的编号。
  v0.3 tasks 1–8, task 4's milestones M1–M8 (with M5a–M5d), the v0.4 and v0.5 items (written
  v0.4-N, v0.5-N below), section 4b (several libraries) and the bug ids D/B/L keep the numbers
  they have in the history.
- **优先级 P0–P5 是分组，不是新编号 / Priorities P0–P5 group, they don't renumber.** 它们按产品优先级排列已有
  条目（第 3–8 节）。They order the existing items by product priority (sections 3–8).
- **新条目 / New items.** 只有已有条目没有覆盖的工作才有新编号：E1–E4（可执行学习）、R1–R3（复习）。它们是
  2026-11-09 提出的**建议**，开始前需要用户批准。Only work no existing item covers gets a new id:
  E1–E4 (executable learning), R1–R3 (review). They are **proposals** from 2026-11-09 and need
  the user's approval before work starts.

| 优先级 Priority | 内容 Content | 已有条目 Existing items | 新条目 New |
|---|---|---|---|
| P0 | 完成阅读与笔记工作流 Finish the reading and notes workflow | 任务 4：M5b–M8 Task 4: M5b–M8 | — |
| P1 | 稳定的来源锚点与结构化标注 Stable source anchors, structured annotations | 任务 5（基于 M6/M7 的锚点）Task 5 (on M6/M7's anchors) | — |
| P0/P1 支撑 support | v0.3 收尾：数据可靠性 v0.3 completion: data reliability | 任务 6、7、8 Tasks 6, 7, 8 | — |
| P2 | 跨文档知识组织 Cross-document knowledge | v0.4-4、v0.4-5、v0.4-6 | — |
| P3 | 可执行学习（可选）Executable learning (optional) | 已有章节脚本 existing chapter scripts | E1–E4 |
| P4 | 主动学习与复习 Active learning and review | v0.4-3（生词 vocabulary） | R1–R3 |
| P5 | 可选的高级功能 Optional advanced features | v0.5-1–8；v0.4-1、2、7、8 | — |
| 以后 Later | 桌面应用 Desktop app | 历史记录第 8 节 History section 8 | — |

**顺序 / Order.** v0.3 的顺序（用户 2026-11-06 定）不变：任务 4 → 5 → 6，然后 7 和 8。v0.4 在 v0.3 完成后开始，
v0.5 在 v0.4 之后。P3、P4 的新条目不会排到 v0.3 之前，除非用户另行决定。
The v0.3 order (set by the user, 2026-11-06) stays: task 4 → 5 → 6, then 7 and 8. v0.4 starts
when v0.3 is done, v0.5 after v0.4. The new P3 and P4 items don't jump ahead of v0.3 unless the
user decides so.

---

## 1. 现状（2026-11-09）/ Where things stand (2026-11-09)

`main` 在 `d6c1a5d`，与 GitHub 同步；CI（Windows：测试和 Edge 浏览器测试）在该提交上全部通过（运行
42634276040）。本地只有用户自己的两个书库文件有未提交的改动（`library/notes/reading-log.json` 和一条章节笔记），
它们不属于任何开发提交。
`main` is at `d6c1a5d`, in step with GitHub; CI (Windows: tests and browser tests in Edge) is
green on it (run 42634276040). Locally, only two of the user's own library files have
uncommitted changes (`library/notes/reading-log.json` and one chapter note); they belong to no
development commit.

| 工作 Work | 状态 Status | 提交 Commits |
|---|---|---|
| v0.3 任务 1：安全写入与后台任务 Task 1: safe writing, background jobs | ✅ | `419a46f` |
| 任务 2：名称冲突与 PDF 误替换 Task 2: name collisions, accidental PDF replacement | ✅ | `ad47aff` |
| 任务 3：永久 UUID 身份 Task 3: permanent UUID identity | ✅ 真实书库已迁移并验证 real library migrated and verified | `5b82b6d`, `17dd9c4` |
| 任务 4 M1 笔记存储与 API Task 4 M1 notes store and API | ✅ | `9acaf52` |
| M2 CI 中的浏览器测试 M2 browser tests in CI | ✅ | `6b19d78`, `3730d23`, `7ff8325` |
| M3 分屏、笔记只读 M3 split screen, notes read-only | ✅ | `73fbc72` |
| M4 在面板中编辑和保存 M4 editing and saving in the panel | ✅ 用户人工验收已通过 user acceptance passed | `268a7cd` |
| 审计后的数据安全修复 Data-safety fixes after the audit (D5, D13–D17, D19, D20, B26) | ✅ | `ac206d4`, `8f029a7`, `edb4dbe`, `8154293`, `0bb1ad7`, `d7b9fc5`, `aa4bf1c`, `a32f3fc`, `0692189` |
| M5a Markdown 预览 M5a Markdown preview | 👀 已提交，CI 自 `d6c1a5d` 全绿。**未完成：**安装包中的离线预览从未验证；用户的人工验收没有记录。Committed; CI green since `d6c1a5d`. **Open:** the preview inside a built package is unverified; the user's manual acceptance isn't recorded. | `b9323dc`, `001b10f` |
| 第 4b 节：多个书库、测试/示例书库、可迁移书库 Section 4b: several libraries, Test & Demo library, portable libraries | ✅ 含 L15 修复 with the L15 fix | `2b0ff96`, `4094dc4` |
| 页面重新载入时连接被拒（监听队列 5 → 64）Connections refused on reload (listen backlog 5 → 64) | ✅ | `d6c1a5d` |
| 双语用户手册 Bilingual user manual | ✅ 现为 now [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | `121c67b` |

测试数量会随代码变化，这里不记录；以 CI 和本地运行的实际结果为准。**L20**（一次未识别的测试失败）仍未解决，见第 11 节。
Test counts change with the code and aren't recorded here; CI and actual local runs are what
count. **L20** (one unidentified test failure) stays unresolved, see section 11.

---

## 2. 当前里程碑 / The current milestone

**任务 4 / Task 4, M5（预览、公式、格式、粘贴图片 / preview, maths, formatting, pasted images）。**
M5a 已提交；**下一步是 M5b，开始前需要用户批准**（2026-11-08 的决定：M5b–M5d 各自单独批准）。
M5a is committed; **next is M5b, which needs the user's approval before work starts** (decision
of 2026-11-08: M5b–M5d are each approved separately).

在用户批准之前，开发会话只做：已批准工作的收尾（例如 M5a 的安装包验证）、经同意的第 11 节错误修复；不开始新的里程碑，
也不开始 P2–P5 或新条目 E/R。
Until the user approves it, a development session only does: finishing approved work (e.g.
M5a's package check) and fixes from section 11 with agreement; no new milestone, nothing from
P2–P5, none of the new E/R items.

---

## 3. P0 — 完成阅读与笔记工作流 / Finish the reading and notes workflow

**目标 / Goal.** 一个可靠的 PDF → 笔记 → PDF 工作流：在 PDF 旁边写笔记、预览、公式、格式、截图；把 PDF 中的一段
引用到笔记；再从笔记回到原文那一段。可靠比功能多更重要。
A reliable PDF → note → PDF workflow: notes beside the PDF with preview, maths, formatting and
screenshots; a passage quoted from the PDF into a note; from the note back to that passage.
Reliability matters more than more features.

**共同约束 / Shared constraints** (history, task 4 and section 5, approved 2026-11-07/08)：
`.md` 文件是唯一的权威；所有视图都用 M4 的 `NoteSession`（自动保存、冲突、草稿、离开提醒）；PDF.js 的阅读、标注、
搜索和阅读进度不受影响；依赖使用精确版本和提交在仓库中的 SHA-256，本地提供，不用 CDN，没有构建步骤。
The `.md` file is the only authority; every view uses M4's `NoteSession` (autosave, conflicts,
drafts, the leave warning); PDF.js reading, marks, search and reading progress are unaffected;
dependencies are exact versions with committed SHA-256 values, served locally, no CDN, no build
step.

### M5b — LaTeX 数学公式 / LaTeX maths 📋 需批准 needs approval

- **目标 Objective:** 在预览中显示公式。Show equations in the preview.
- **依赖 Dependencies:** M5a.
- **交付物 Deliverables:** 固定版本并校验的 KaTeX；`$…$`、`$$…$$`、`\(…\)`、`\[…\]`；不误伤金额和代码；无效的
  LaTeX 显示为错误而不崩溃；`trust: false`，大小和展开限制。Pinned, verified KaTeX; `$…$`, `$$…$$`,
  `\(…\)`, `\[…\]`; rules that leave dollar amounts and code alone; invalid LaTeX shown as an
  error, never a crash; `trust: false`, size and expansion limits.
- **模块 Modules:** `reader.py` (setup, checks, serving), `reader_static/preview.js`,
  `build_package.py`, `THIRD_PARTY_NOTICES.md`.
- **数据 Data:** 无变化（`.md` 不变）。None (the `.md` is unchanged).
- **风险 Risks:** 巨大或恶意的公式拖慢页面；字体文件体积。Huge or hostile formulas slowing the page; font
  file size.
- **测试 Tests:** Python（安装、校验、缺失时回退）；Edge（渲染、错误、安全、深色模式）。Python (setup, checks,
  fallback); Edge (rendering, errors, safety, dark mode).
- **验收 Acceptance:** 测试集中的公式全部正确渲染；无效公式只影响它自己；没有 KaTeX 时预览显示原文并说明原因。
  All formulas in the test set render; an invalid one affects only itself; without KaTeX the
  preview shows the source and says why.

### M5c — 格式工具栏与显示偏好 / Formatting toolbar and display preferences 📋 需批准 needs approval

- **目标 Objective:** 不写 Markdown 也能排版，仍然只编辑 Markdown 源码。Formatting without typing Markdown,
  still editing only the Markdown source.
- **依赖 Dependencies:** M5a（公式按钮需要 M5b the equation button needs M5b）.
- **交付物 Deliverables:** 标题 H1–H6、粗体、斜体、删除线、列表、任务列表、引用、代码、链接、图片、表格、公式；尽量可以
  取消；保留选区、光标、浏览器撤销（`insertText`）、输入法组合、自动保存与冲突；Ctrl+B / Ctrl+I 只在笔记中生效；显示
  偏好（字体、字号、行距、段距、宽度）按浏览器保存，与 Markdown 分开。**不使用所见即所得编辑器或富文本框架。**
  Headings H1–H6, bold, italic, strikethrough, lists, task lists, quote, code, link, image,
  table, equation; toggling off where practical; keeping the selection, caret, browser undo
  (`insertText`), IME composition, autosave and conflicts; Ctrl+B / Ctrl+I only inside the
  note; display preferences (font, size, line height, paragraph spacing, width) per browser,
  apart from the Markdown. **No WYSIWYG editor or rich-text framework.**
- **模块 Modules:** `reader_static/notes.js`, `notes.css`.
- **数据 Data:** 显示偏好在浏览器存储中，不在书库中。Display preferences in browser storage, not the library.
- **风险 Risks:** 与 PDF.js 快捷键冲突；输入法。Clashes with PDF.js shortcuts; IME.
- **测试 Tests:** Edge：每个按钮、撤销、输入法、冲突时的行为。Edge: every button, undo, IME, behaviour during
  a conflict.
- **验收 Acceptance:** 每个按钮生成正确的 Markdown；一次撤销还原一次操作；PDF.js 的快捷键不受影响。Every button
  produces the right Markdown; one undo reverts one action; PDF.js shortcuts unaffected.

### M5d — 粘贴截图和图片 / Pasted screenshots and images 📋 需批准 needs approval

- **目标 Objective:** Ctrl+V 粘贴截图，图片成为笔记旁的本地文件。Ctrl+V a screenshot; the image becomes a
  local file beside the note.
- **依赖 Dependencies:** M5a.
- **交付物 Deliverables:** 受管理的本地资源（路径受限、不冲突的名字、原子写入、大小限制、按内容检查类型）；插入相对
  Markdown 链接；预览通过受限路径显示本地图片，不上传；保存冲突时从不删除图片。A managed local asset (contained
  path, collision-safe name, atomic write, size limit, type checked from the bytes); a relative
  Markdown image link inserted; the preview shows local images through a contained route,
  nothing uploaded; an asset is never deleted because a save met a conflict.
- **模块 Modules:** `notes_store.py`, `library_server.py` (a new contained route), `notes.js`,
  `preview.js`.
- **数据 Data:** 笔记文件夹中的图片文件（例如 `notes/<slug>/assets/`，批准时确定）；进入 💾 备份。Image files
  in the notes folder (e.g. `notes/<slug>/assets/`, decided at approval); included in 💾 backup.
- **风险 Risks:** 路径逃逸；大文件；公开仓库中的书页截图（版权）。Path escape; large files; screenshots of
  book pages in a public repository (copyright).
- **测试 Tests:** Python（路径、名字、原子写入、类型、大小）；Edge（粘贴、显示、冲突）。Python (paths, names,
  atomic writes, types, sizes); Edge (paste, display, conflict).
- **验收 Acceptance:** 粘贴的截图立刻显示并已在磁盘上；任何链接或 `..` 都不能写到笔记文件夹之外。A pasted
  screenshot shows at once and is on disk; no link or `..` can write outside the notes folder.

### M6 — 引用到笔记（PDF → 笔记）/ Quote to note (PDF → note) 📋

- **目标 Objective:** 选中 PDF 中的一段，一步插入带来源链接的引用。Select a passage and insert a quotation
  with its source link in one step.
- **依赖 Dependencies:** M4；设计见历史记录第 5 节（已批准）。M4; design in the history, section 5 (approved).
- **交付物 Deliverables:** 选区气泡中的"引用到笔记"和 Alt+Q；插入光标处或末尾；锚点私下记录在
  `.myLibrary/references/<id>.json`（`safe_io.update_json`）；没有文字层的页面用"引用此页"。"Quote to note" in
  the selection bubble and Alt+Q; inserted at the cursor or the end; the anchor recorded
  privately in `.myLibrary/references/<id>.json` (`safe_io.update_json`); "Reference this page"
  on pages without a text layer.
- **模块 Modules:** `lookup.js`, `notes.js`, `library_server.py`, a new references store.
- **数据 Data:** 第 4 节的锚点模型。**已批准的决定：**可见的引用默认很短（约 15 个词 + "…" + 链接）；完整选区、
  前后文、位置和指纹只存在 `.myLibrary/references/`（不进 git，进 💾 备份，从不进公开的 `notes/`）；链接写成
  `http://127.0.0.1:<port>/read/<id>?…`，端口不是身份。The anchor model in section 4. **Approved
  decisions:** the visible quote is short by default (about 15 words + "…" + the link); the full
  selection, context, positions and fingerprint live only in `.myLibrary/references/` (not in
  git, in 💾 backup, never in the public `notes/`); links are
  `http://127.0.0.1:<port>/read/<id>?…`, and the port is not identity.
- **风险 Risks:** 版权与公开仓库（见上面的决定）。Copyright and the public repository (decisions above).
- **测试 Tests:** 浏览器：单行、跨行、连字符、连字、希腊字母、同一页重复的文字、无文字层的页面；Python：引用文件的
  并发写入和损坏（`.bak`）。Browser: one line, across lines, hyphenation, ligatures, Greek, the
  same words twice on a page, a page without text; Python: concurrent writes and damage (`.bak`)
  of the references file.
- **验收 Acceptance:** 测试集中每种选区都插入正确的文字和能用的链接；工具自己从不把书中的长段文字写进笔记。Every
  selection in the test set inserts the right text and a working link; the tool never writes
  long book text into notes on its own.

### M7 — 回到原文（笔记 → PDF）/ Back to the passage (note → PDF) 📋

- **目标 Objective:** 点击笔记中的来源链接，回到 PDF 中那一段并临时标出。Click a source link in a note and
  land on that passage, outlined for a moment.
- **依赖 Dependencies:** M6.
- **交付物 Deliverables:** 预览中点击或编辑器中 Ctrl+点击；同一文档在当前阅读器中移动，其他文档在新标签页的预览模式中
  打开；临时黄色框，从不写入 PDF；`/read/<id>?page=N&ref=<rid>` 从外部（VS Code、书库页面）也能用；只能找到页面或
  PDF 已改变时给出提示。Click in Preview or Ctrl+click in the editor; within the open reader for
  the same document, a new tab in Preview Mode for another; a temporary yellow outline, never
  written into the PDF; `/read/<id>?page=N&ref=<rid>` from outside (VS Code, the library page);
  a notice when only the page could be found or the PDF changed.
- **模块 Modules:** `lookup.js`, `preview.js`, `library_server.py` (`/read`).
- **数据 Data:** 读取 M6 的锚点。Reads M6's anchors.
- **风险 Risks:** PDF.js 升级改变文字提取（退回到页面，而不是坏掉）。PDF.js upgrades change text extraction
  (it falls back to the page rather than breaking).
- **测试 Tests:** 浏览器：同一页两处相同的文字（找到正确的一处）、跨 span、缺少引用文件、标注保存之后、已删除的文档。
  Browser: the same words twice (the right one), across spans, a missing references file, after
  marks were saved, a deleted document.
- **验收 Acceptance:** 测试集中每个链接都落到正确位置，或者清楚说明只能到页面以及原因；从不悄悄选择有歧义的匹配。
  Every link in the test set lands on the right passage, or says plainly that only the page could
  be found and why; never picks an ambiguous match silently.

### M8 — 收尾 / Polish and finish 📋

- **交付物 Deliverables:** 阅读进入下一章时提示该章的笔记（输入时从不自动切换）；笔记列表中的主题笔记；小屏幕；帮助、
  用户指南和 CLAUDE.md 更新；在干净环境中构建并测试安装包（含 M5a 的离线预览）。A chip offering the next
  chapter's note when reading moves on (never switching by itself while typing); topic notes in
  the note list; small screens; help, user guide and CLAUDE.md updated; the package built and
  tested unzipped in a clean environment (including M5a's offline preview).
- **验收 Acceptance:** 安装包测试按 CLAUDE.md 的步骤通过；任务 4 的全部浏览器测试在 CI 中通过。The package test
  passes as CLAUDE.md describes; all of task 4's browser tests pass in CI.

不在任务 4 中 / Not in task 4: AI 解释或翻译（v0.4/v0.5）、全书库笔记搜索（v0.4）、同时打开多条笔记。AI explain or
translate (v0.4/v0.5); notes search across the library (v0.4); more than one note open at once.

---

## 4. P1 — 稳定的来源锚点与结构化标注 / Stable source anchors and structured annotations

### 任务 5 / Task 5 📋 在任务 4 之后 after task 4

- **目标 Objective:** 来源引用精确、稳定、可恢复、可验证：标注和笔记互相找得到；PDF 改变或丢失时有明确的结果。
  Source references that are precise, stable, recoverable and verifiable: marks and notes find
  each other, with a clear outcome when a PDF changes or goes missing.
- **依赖 Dependencies:** M6/M7（锚点格式）。**先确认 PDF.js 在多次保存后 `/NM` 保持不变**，并把结果记在这里。
  M6/M7 (the anchor format). **First confirm that PDF.js keeps `/NM` stable across saves**, and
  record the result here.
- **已完成 Done:** 不会互相覆盖的标注保存（D5，`ac206d4`）。Marks that can't overwrite each other (D5,
  `ac206d4`).
- **交付物 Deliverables:**
  - 保存标注：失败时退避重试；保存后更新 `book_search` 的标记，而不是重建索引。Saving marks: retry with
    backoff; update `book_search`'s stamp after a save instead of re-indexing.
  - `scripts/annotations.py`：读取每个标注的 `/NM`、类型、页、矩形、颜色、高亮文字和内容，写入 `annotations.json`
    （注释和标签只在旁注文件中）。Reads each mark's `/NM`, type, page, rectangle, colour,
    highlighted text and contents into `annotations.json` (comments and tags only in the
    sidecar).
  - 标注面板：列表、筛选、跳转、"到笔记"、注释和标签；跨文档搜索。Annotation panel: list, filter, jump,
    "To note", comments and tags; search across documents.
  - 导出到 `notes/<slug>/annotations.md`（自动生成，从不和用户的笔记混在一起）。Export to
    `notes/<slug>/annotations.md` (generated, never mixed into the user's notes).
  - 用 M6 的引用文件把 PDF 标注和笔记双向链接。Link a PDF mark and a note both ways through M6's
    references file.
- **锚点模型 Anchor model**（在历史记录第 5 节的基础上提出；细节见
  [DEVELOPMENT_SPEC.md 第 9 节](DEVELOPMENT_SPEC.md#9-来源锚点与数据模型--source-anchors-and-data-models)）：
  文档 UUID、引用 id、页索引、选中文字、前后文、规范化矩形、PDF 指纹（SHA-256）。(Proposed on the basis of
  section 5 of the history; details in DEVELOPMENT_SPEC section 9): document UUID, reference id,
  page index, selected text, prefix and suffix, normalised rectangles, PDF fingerprint
  (SHA-256).
- **定位顺序 Resolution order:** 1. 精确位置 exact location → 2. 恢复的文字或位置匹配（仅当唯一时）recovered
  text or position match (only when unique) → 3. 页面 page → 4. 来源缺失提示和恢复选项 missing-source warning
  with a recovery option. **有歧义时从不悄悄选择。An ambiguous match is never chosen silently.**
- **与 PDF 内的标注共存 Coexisting with marks in the PDF:** 标注仍保存在 PDF 中（PDF.js，`/NM` 名称）；旁注文件只保存
  注释、标签和链接，按 `/NM` 指向标注，从不改写 PDF 中的标注。PDF 被替换或修改时，指纹会显示出来，然后按上面的顺序处理。
  Marks stay inside the PDF (PDF.js, `/NM` names); the sidecar holds only comments, tags and
  links, pointing at marks by `/NM`, and never rewrites the PDF's marks. When a PDF is replaced
  or changed, the fingerprint shows it and the order above applies.
- **模块 Modules:** `reader.py` (`save_marks`), `book_search.py`, a new `annotations.py`,
  `lookup.js`, `notes.js`.
- **风险 Risks:** `/NM` 不稳定（那时只能按页面和文字找）；PDF 的不同版本（跨版本的模糊锚定推迟）。`/NM` not
  stable (then only page and text); different editions of a PDF (fuzzy anchoring across editions
  deferred).
- **测试 Tests:** 用 PDF.js 实际保存的样本、加密 PDF、过期的保存、重新读取后旁注仍在、锚点回退到页面；测试/示例书库已有
  带 `/NM` 的标注样本。A real PDF.js-saved fixture, an encrypted PDF, a stale save, sidecar comments
  surviving re-reads, anchor fallback to the page; the Test & Demo library already has marks with
  `/NM`.
- **验收 Acceptance:** 每个标注在列表中出现一次并能跳转；PDF 被替换后，无法精确定位的标注被明确标出，从不丢失。Every
  mark appears once in the list and jumps to its place; after the PDF is replaced, marks that
  can't be placed exactly are flagged, never lost.

### v0.3 收尾：数据可靠性 / v0.3 completion: data reliability (Tasks 6, 7, 8) 📋

| 任务 Task | 交付物 Deliverables | 验收 Acceptance |
|---|---|---|
| 6 元数据、章节、重复 Metadata, chapters, duplicates | "编辑详情"对话框（写目录和 README，标为 `you`，自动步骤从不覆盖）；新类型 report；`chapters.json` 章节编辑（优先于检测；笔记文件从不改名或删除）；"可能重复"列表（保留两者 / 替换文件 / 合并；双方都有用户的工作时从不自动）。"Edit details" (catalog and README, marked `you`, never overwritten by automatic steps); type "report"; a `chapters.json` chapter editor (wins over detection; note files never renamed or deleted); a "possible duplicates" list (keep both / replace file / merge; never automatic when both hold work). | 编辑在刷新后保留；清空的字段保持为空；合并可以撤销。Edits survive Refresh; a cleared field stays cleared; a merge can be undone. |
| 7 备份与恢复 Backup and recovery | `backup.py` 使用 `core.quotepath=false`（B2）；清空归档默认保留 `before-marks/` 和 OCR 原件（B13）；"从备份恢复"到新文件夹，从不覆盖当前书库。（"zip 名称精确匹配"已在第 4b 节完成。）`backup.py` with `core.quotepath=false` (B2); Clear archive keeps `before-marks/` and OCR originals by default (B13); "Restore from backup" into a new folder, never over the current library. ("Exact zip name match" is already done, in 4b.) | 备份后恢复到干净的文件夹，书库能打开，笔记、记录和复习状态都在；git 备份支持非 ASCII 文件名。Backed up and restored into a clean folder, the library opens with notes, log and review state; git backup handles non-ASCII names. |
| 8 剩余修复与发布检查 Remaining fixes, release check | 第 11 节中的错误（B4、B5、B7–B12、B14、`ocr_pdf.replace_pdf` 的顺序）；L11 中未测试的路由；安装包的干净环境测试，然后一次添加五个 PDF 再退出；整理示例书库（需用户同意）。Section 11's bugs (B4, B5, B7–B12, B14, the `ocr_pdf.replace_pdf` order); L11's untested routes; the package clean-environment test, then five PDFs added at once and Quit; tidying the example library (with the user's agreement). | **v0.3 完成**：本节和第 3 节的所有条目完成，全部测试和安装包测试通过。**v0.3 is done** when every item here and in section 3 is done and every test, the package test included, passes. |

---

## 5. P2 — 跨文档知识组织 / Cross-document knowledge (v0.4) 📋

**在 v0.3 完成后开始。Starts when v0.3 is done.** 思维导图最多是以后的一个可选视图，从不是组织知识的前提。
A mind map is at most a later optional view, never a prerequisite for organising knowledge.

| 条目 Item | 内容 Content | 验收 Acceptance |
|---|---|---|
| v0.4-5 连接来源的主题 Topics that link sources | `notes/topics/<term>.json`：确认过的链接（文档 id、页、引用、锚点）、同义词、相关的笔记和标注；主题页；从选区和标注面板添加；只由用户确认。Confirmed links (document id, page, quote, anchor), synonyms, linked notes and annotations; a topic page; added from the selection bar and annotation panel; user confirmation only. | 一个主题汇集多个文档的来源，每一个都能回到原文。A topic gathers sources from several documents, each back to its passage. |
| v0.4-6 笔记和标注的组织 Notes and annotations organised | 全书库的标注视图；标注和主题共用的标签；相关笔记。A library-wide annotations view; tags shared by annotations and topics; related notes. | 按标签筛选标注和主题。Filter annotations and topics by tag. |
| v0.4-4 书库搜索页 Library search page | 片段和高亮；按书名、作者、年份、类型、书架、阅读状态筛选；**笔记和标注也被索引**（统一搜索）；印刷页码；索引作为后台任务，有进度、可取消。Snippets and highlighting; filters (title, author, year, type, shelf, reading status); **notes and annotations indexed** (unified search); printed page labels; indexing as a background job with progress and cancel. | 一次搜索同时找到书页、笔记和标注。One search finds book pages, notes and annotations. |

---

## 6. P3 — 可执行学习（可选）/ Executable learning (optional) 📋 新条目需批准 new items need approval

可执行学习是可选的能力，主要面向技术学科；学习、阅读和笔记这三个支柱从不依赖它（见 DEVELOPMENT_SPEC 第 2、7 节）。
Executable learning is an optional capability, mainly for technical subjects; the three pillars
(learning, reading, note-taking) never depend on it (DEVELOPMENT_SPEC sections 2 and 7).

**已有 / Existing** ([user guide, Chapter scripts](docs/USER_GUIDE.md#104-章节脚本--chapter-scripts))：
章节脚本（书库页面的 Script 按钮从模板创建 `examples/<book>/chNN_<topic>.py` 并在编辑器中打开）；书库的 `code/`
（按学科的可复用代码，在脚本的导入路径上；`code/tests/` 由 pytest 运行）；`science` 依赖组（numpy、scipy、sympy、
matplotlib）和可选的 `optics` 组；可配置的编辑器（VS Code、记事本、系统默认、自定义）；`.py` 从不用系统默认程序打开；
安装包中默认关闭 Python 功能。
Chapter scripts (the library page's Script button creates `examples/<book>/chNN_<topic>.py`
from a template and opens it in the editor); the library's `code/` (reusable code by subject, on
the scripts' import path; `code/tests/` run by pytest); the `science` dependency group (numpy,
scipy, sympy, matplotlib) and the optional `optics` group; the configurable editor (VS Code,
Notepad, system, custom); a `.py` is never opened with its default app; Python features are off
in the package.

**原则 / Principles.** 使用用户自己的外部工具，不内置 IDE；运行代码永远是用户的明确操作；从不自动运行从文档中提取的代码。
The user's own external tools, no built-in IDE; running code is always an explicit user action;
code extracted from documents is never run automatically.

| 新条目 New | 内容 Content | 依赖 Depends on |
|---|---|---|
| E1 来源 ↔ 代码链接 Source ↔ code links | 脚本头部写入文档 id、章节和（M6 之后的）段落链接；笔记可以链接到脚本（在编辑器中打开，不运行）。The script header carries the document id, chapter and (after M6) passage links; notes can link to a script (opens it in the editor, never runs it). | M6/M7 |
| E2 结果与笔记 Results in notes | 脚本保存的图和数据放在约定位置（例如 `examples/<book>/results/`），笔记可以显示它们（复用 M5d 的受限图片路由）。Plots and data a script saves go to an agreed place (e.g. `examples/<book>/results/`), and notes can show them (reusing M5d's contained image route). | M5d |
| E3 可复现的记录 Reproducibility record | 模板记录运行命令和依赖（`uv run`，`pyproject.toml` 的组）；可选的 `examples/<book>/README.md` 索引。The template records the run command and dependencies (`uv run`, the `pyproject.toml` group); an optional `examples/<book>/README.md` index. | — |
| E4 其他语言 Other languages | 可选模板：Julia、R、MATLAB/Octave（只创建文件并在编辑器中打开）。Optional templates: Julia, R, MATLAB/Octave (create the file and open it in the editor only). | E3 |

**验收（每项）/ Acceptance (each):** 在测试/示例书库中走通"读一章 → 打开脚本 → 运行 → 结果写进笔记 → 回到原文"；
用户没有选择运行时，任何路径都不会执行代码。The Test & Demo library walks through "read a chapter
→ open the script → run it → result in the note → back to the passage"; no path runs code
unless the user chooses to.

---

## 7. P4 — 主动学习与复习 / Active learning and review 📋

**在来源链接和知识组织可靠之后。After source links and knowledge organisation are reliable.** 不做完整的
Anki 替代品。Not a full Anki replacement.

| 条目 Item | 内容 Content |
|---|---|
| v0.4-3 带语境的生词 Vocabulary with context（已有条目 existing） | 句子、释义、页码和来源链接（旧行原样读取）；可编辑；完形卡片；Anki TSV 导出；全书库的生词列表。Sentence, definition, page and source link (old rows read unchanged); editable; cloze cards; Anki TSV export; a library-wide list. |
| R1 笔记中的问答 Questions in notes（新 new） | 笔记中约定的问答格式（例如 `Q:` / `A:`），复习时带回到原文的链接。An agreed question/answer format in notes (e.g. `Q:` / `A:`), reviewed with a link back to the source. |
| R2 简单复习 Simple review（新 new） | 复用"复习生词"的 Leitner 盒子（`vocab_review.py`），进度单独保存。Reuses Review words' Leitner boxes (`vocab_review.py`), progress kept separately. |
| R3 Anki 兼容导出 Anki-compatible export（新 new） | 问答和生词导出为 Anki 可以导入的文本，带来源链接。Questions and vocabulary exported as text Anki can import, with source links. |

---

## 8. P5 — 可选的高级功能 / Optional advanced features (v0.4, v0.5) ⏸

全部可选、默认关闭；阅读、笔记、生词从不依赖它们。All optional and off by default; reading, notes and
vocabulary never depend on them.

- v0.4-1 语境查词和提供者接口（`assist.py`：显示将发送的内容，从不发送整本书）；v0.4-2 选区工具栏中的翻译和解释。
  Context-aware lookup and a provider interface (`assist.py`: shows exactly what is sent, never
  the whole document); Translate and Explain in the selection toolbar.
- v0.4-7 大 PDF（HTTP Range，用 500 MB 以上的 PDF 前后测量）；v0.4-8 阅读记录的准确性（B15）。Large PDFs
  (HTTP Range, measured with a 500 MB+ PDF before and after); reading-log accuracy (B15).
- v0.5-1–4 AI：本地模型或用户自己的密钥；基于所选段落的解释，**生成的内容与原文清楚区分**，只引用实际检索到的来源；
  主题链接的建议须由用户确认。AI: local models or the user's own keys; explanations grounded in the
  selected passage, **generated text clearly labelled apart from the source**, citing only what
  was actually retrieved; suggested topic links confirmed by the user.
- v0.5-5 导入 BibTeX、RIS、Zotero；v0.5-6 中文文档（第N章目录、中文章节名、OCR 文字层的 CJK 字体，L9）；v0.5-7
  下载安全（ECDICT 固定版本和校验）；v0.5-8 两种工作区（读书 / 论文研究）作为同一份数据上的不同默认设置。Imports
  (BibTeX, RIS, Zotero); Chinese documents (L9); download safety (ECDICT pinned and checked); two
  workspaces (book study / paper research) as different defaults over the same data.
- 以后再考虑 / Later to consider: 更好的 OCR 和技术文档处理、公式提取、可选的知识可视化（例如思维导图视图）。
  Better OCR and technical-document processing, formula extraction, optional knowledge
  visualisation (e.g. a mind-map view).

---

## 9. 桌面应用与安装包 / Desktop application and package ⏸ 在任务 4–6 之后 after tasks 4–6

目标：在 Windows 上安装，从桌面图标启动，在自己的窗口中使用，不需要 Python、Git 或终端；现有界面被包装而不是重写。细节
见历史记录第 8 节（待比较：PyInstaller 或类似工具、pywebview 加 WebView2、Windows 安装程序）。在那之前不做 EXE、
安装程序、窗口包装或许可证代码；新代码遵循 CLAUDE.md 中"便于打包"的规则。现有的现成 zip 安装包
（`build_package.py`，9.9 元人民币）保持不变。
Goal: install on Windows, start from a desktop icon, use it in its own window with no Python,
Git or terminal; the existing interface is wrapped, not rewritten. Details in the history,
section 8 (to compare: PyInstaller or similar, pywebview with WebView2, a Windows installer).
Until then no EXE, installer, window wrapper or licence code; new code follows CLAUDE.md's
packaging-friendly rules. The existing ready-to-use zip package (`build_package.py`, 9.9 RMB)
stays as it is.

---

## 10. 示例书库 / The example library (`library/`)

**冻结的公开示例 / A frozen public showcase** (2026-11-09): 用户自己的书库已复制到仓库之外（每台电脑
`local.toml` 中的默认书库，不在 git 中）。
`library/` 保持 git 中的样子，应用从不打开或写入它：`paths.FROZEN`、`paths.ensure_library`、`safe_io.FrozenLocation`、
各写入脚本的 `paths.refuse_frozen()`；测试 `tests/test_showcase.py`。The user's own library was copied
outside the repository (on this computer, the default in `local.toml`); `library/` stays as it
is in git and the app never opens or writes it. 下面的整理事项若要做，应在用户自己的书库中做；`library/` 的任何改变都
需要用户单独决定。The tidying items below, if done, belong in the user's own library; any change to
`library/` is a separate decision of the user's.

这是用户的数据：只在用户同意后用工具修正。11 个条目的 `type` 为空；`bentley`、`chacon` 的作者用逗号分隔；
`archut-2022`、`jendrny-2024` 有 DOI，却用了 PDF 创建日期作为年份；`esveld`、`bentley`、`geary` 的详情来自文件名；
`yoder` 和两份 UIC 文件没有主题，每次刷新都会再次查询。在单独评审的迁移之前，它的 git 跟踪状态保持不变。
These are the user's data: corrected with the tool and only with the user's agreement. 11
items have an empty `type`; `bentley` and `chacon` list authors with commas; `archut-2022` and
`jendrny-2024` take their year from the PDF's creation date despite having a DOI; `esveld`,
`bentley` and `geary` have details from the filename; `yoder` and both UIC items have no topic
and are asked again on every Refresh. Its git tracking stays as it is until a separately
reviewed migration.

---

## 11. 已知问题与限制 / Known bugs and limitations

C = 已确认 confirmed，S = 怀疑 suspected。完整描述见历史记录第 3 节；本表是当前状态。Full descriptions are
in the history, section 3; this table is the current state.

**未解决 / Open**

| ID | 问题 Issue | 计划在 Planned in |
|---|---|---|
| **L20** | **未解决 UNRESOLVED.** 2026-11-09 一次完整运行中有一个未识别的失败，之后没能复现。现在每次运行都写 `test-results/pytest-junit.xml`；下次失败时运行 `uv run pytest -rfE --tb=long` 并保留该文件。One unidentified failure in one full run (2026-11-09), not reproduced since. Every run now writes `test-results/pytest-junit.xml`; on the next failure run `uv run pytest -rfE --tb=long` and keep that file. | — |
| D18 (C, latent) | 重命名失败时可能丢失恢复日志（`add_book.rename_document`）。A failed rename can lose its recovery journal. | Task 8 |
| B2 (C) | ☁ 备份不支持非 ASCII 文件名。☁ Back up fails with non-ASCII file names. | Task 7 |
| B4 (C) | 设置了 `MYLIBRARY_LIBRARY` 时更换书库可能悄悄不生效。A library change can silently not take effect when `MYLIBRARY_LIBRARY` is set. | Task 8 |
| B5 (C) | 保存的释义可能与弹窗不同。The saved meaning can differ from the popup. | Task 8 |
| B6 (C) | 连字符断词影响查词和搜索。Hyphenation breaks lookup and search. | v0.4-1 |
| B7 (C) | `vocabulary.md` 的解析不稳健。`vocabulary.md` parsing is fragile. | Task 8, v0.4-3 |
| B8 (C) | 搜索的页数在更新前仍计入已移除的书。Search page counts include removed books until the next update. | Task 8 |
| B9 (C) | BibTeX 转义缺少 `{ } \ ~ ^`。BibTeX escaping misses `{ } \ ~ ^`. | Task 8 |
| B10 (C) | 损坏的 `pdfjs.zip` 会被重复使用。A corrupt `pdfjs.zip` is reused. | Task 8 |
| B11 (C) | 离线或被限流时很慢（忽略 429 `Retry-After`）。Slow when offline or rate-limited. | Task 8 |
| B12 (C) | 安装包中的错误看不到。Package errors go unseen. | Task 8 |
| B13 (C) | 清空归档会删除唯一的无标注原件。Clear archive deletes the only unmarked originals. | Task 7 |
| B14 (C) | 若干小修复。Small fixes. | Task 8 |
| B15 (S) | 阅读记录可能多算。The reading log may over-count. | v0.4-8 |
| B16 (S) | 尚未确认（见历史记录）。Not yet confirmed (see the history). | — |
| B17 (S) | pdfium 提取文字时可能发生本地崩溃。A native fault in pdfium during text extraction. | — |
| B21–B24 (C, audit) | OCR 中残留的按 slug 的键；没有完整超时的请求；服务器重启后 Ctrl+S 重试；相同文本之间的冲突。Slug-keyed leftovers in OCR; requests without a full timeout; Ctrl+S retries after a restart; a conflict between identical texts. | Task 8 |
| B27 (C, test only) | 浏览器测试夹具用普通 `read_text` 读取阅读记录。The browser fixture reads the reading log with a plain `read_text`. | Task 8 |
| L1 | 只有书、论文、学位论文三种类型。Only book, paper and thesis types. | Task 6 |
| L9 | 中文文档：第N章、中文章节名、中文在线目录。Chinese documents: 第N章 contents, Chinese chapter titles, a Chinese online catalogue. | v0.5-6 |
| L11 | 测试缺口：部分路由；书库页面的 JavaScript 中只有书库对话框有浏览器测试。Test gaps: some routes; of the library page's JavaScript only the library dialog has browser tests. | Task 8 |
| L12 | 强制关闭浏览器会丢失未保存的标注。Force-closing the browser loses unsaved marks. | — |
| L13 | 阅读时间最多可能少算一分钟。Reading time can lose up to a minute. | — |
| L14 | 笔记也可以在外部编辑器中打开（写 README 时由编辑器提示冲突）。Notes also open in an outside editor (the editor reports a newer README). | — |
| L16 | 浏览器中的状态不随书库迁移（草稿按书库隔离）。Browser state doesn't travel with a library (drafts are scoped per library). | — |
| L17 | 测试/示例书库只能在启动器中重置。The Test & Demo library resets only from the launcher. | — |
| L18 | 测试语料上的章节检测限制。Chapter detection limits on the test corpus. | Task 6 |
| L19 | 没有作者和年份的文档，名字中有两个连字符。A document without author or year gets a slug with two hyphens. | — |

**已修复（历史记录中仍列为未解决）/ Fixed (still listed as open in the history)**
- **B3** 💾 备份按名称前缀匹配会互相删除 zip：在 `2b0ff96` 中修复（精确名称，按书库区分的名称）。Zips pruned by
  name prefix: fixed in `2b0ff96` (exact names, library-scoped names).
- **B26** `safe_io` 文档字符串中的无效转义：在 `0692189` 中修复。An invalid escape in a `safe_io` docstring:
  fixed in `0692189`.
- **L15** 同时两次启动为一个书库启动两个服务器：在 `2b0ff96` 中修复（书库锁）。Two launches at once starting two
  servers for one library: fixed in `2b0ff96` (the library lock).

---

## 12. 不计划 / Not planned

DjVu 或 EPUB；笔记本（notebook）；影子图书馆来源；书或书中文字进入 git；云托管、账户或订阅；强制使用 AI；替换 Python
后端或基于浏览器的界面（Electron、React、Qt 或原生界面只在有具体理由并经用户批准时）；内置 IDE；自动运行从文档中提取的
代码；复制 BookxNote、MarginNote 或 Zotero 的完整功能。
DjVu or EPUB; notebooks; shadow-library sources; books or book text in git; cloud hosting,
accounts or subscriptions; mandatory AI; replacing the Python backend or the browser-based
interface (Electron, React, Qt or a native UI only with a specific reason and the user's
approval); a built-in IDE; running code extracted from documents automatically; copying the
full feature set of BookxNote, MarginNote or Zotero.
