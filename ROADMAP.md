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
- **2026-11-10 的新条目 / New items of 2026-11-10**（市场研究之后 after the market review；用户在 2026-11-10 把它们作为
  **规划方向**批准，**不是开始实现的授权**；开始任何工作都需要用户另行同意 approved by the user on 2026-11-10 as
  **planning directions, not authorisation to implement**; starting any of them needs the user's
  separate go-ahead）：G1 文档结构评估 document-structure assessment（第 4 节 section 4）；X1 macOS 可行性 macOS
  feasibility（第 9 节 section 9）；U1–U3 用户验证 user validation（第 2 节，计划在
  [DEVELOPMENT_SPEC.md 第 16 节](DEVELOPMENT_SPEC.md#16-用户验证计划--user-validation-plan) the plan in DEVELOPMENT_SPEC
  section 16）。已有编号都没有改变。No existing id changed.

| 优先级 Priority | 内容 Content | 已有条目 Existing items | 新条目 New |
|---|---|---|---|
| P0 | 可靠的阅读与笔记 Reliable reading and note-taking | 任务 4：M5b–M8 Task 4: M5b–M8 | — |
| P1 | 可信的来源引用 Trustworthy source references | 任务 5（基于 M6/M7 的锚点）Task 5 (on M6/M7's anchors) | — |
| P0/P1 支撑 support | v0.3 收尾：存储、恢复、可安装性 v0.3 completion: storage, recovery, installability | 任务 6、7、8 Tasks 6, 7, 8 | G1（评估 assessment） |
| P2 | 统一检索与跨文档知识 Unified retrieval and cross-document knowledge | v0.4-4、v0.4-5、v0.4-6 | — |
| P3 | 可执行学习（可选）Executable learning (optional) | 已有章节脚本 existing chapter scripts | E1–E4 |
| P4 | 主动学习与复习 Active learning and review（取决于验证 depends on validation） | v0.4-3（生词 vocabulary） | R1–R3 |
| P5 | 可选的高级功能 Optional advanced features（取决于验证 depends on validation） | v0.5-1–8；v0.4-1、2、7、8 | — |
| 并行 In parallel | 用户验证（不写代码）User validation (no code) | — | U1–U3 |
| 以后 Later | macOS 可行性；桌面应用 macOS feasibility; desktop app | 历史记录第 8 节 History section 8 | X1 |

**顺序 / Order.** v0.3 的顺序（用户 2026-11-06 定）不变：任务 4 → 5 → 6，然后 7 和 8。v0.4 在 v0.3 完成后开始，
v0.5 在 v0.4 之后。P3、P4 的新条目不会排到 v0.3 之前，除非用户另行决定。
The v0.3 order (set by the user, 2026-11-06) stays: task 4 → 5 → 6, then 7 and 8. v0.4 starts
when v0.3 is done, v0.5 after v0.4. The new P3 and P4 items don't jump ahead of v0.3 unless the
user decides so.

**2026-11-10 的市场研究没有改变顺序 / The market review of 2026-11-10 doesn't change the order.**
它建议的产品价值顺序（可靠的阅读和笔记 → 可信的来源引用 → 统一检索 → 可选的可执行学习）与上面的 P0–P3 一致，所以只更新了名称和说明；
**没有提出顺序变化**。M5b 仍然是下一个待批准的里程碑。复习、AI、高级可视化和广泛的集成（P4、P5）在用户验证（U1–U3）给出证据之前不提前。
Its recommended order of product value (reliable reading and notes → trustworthy source
references → unified retrieval → optional executable learning) matches P0–P3 above, so only
names and descriptions were updated; **no sequencing change is proposed**. M5b stays the next
milestone awaiting approval. Review, AI, advanced visualisation and broad integrations (P4, P5)
don't move forward until user validation (U1–U3) gives evidence.

---

## 1. 现状（2026-11-10）/ Where things stand (2026-11-10)

本节是带日期的快照，其他各节不写当前的提交号。截至 2026-11-10：最近推送的提交是 `1c16f25`（保护冻结的示例书库、分开个人数据），
它的 GitHub Actions 运行 42650820367 的测试和浏览器两个任务都通过（据用户 2026-11-10 的报告）。之前的 `d6c1a5d` 在运行 42634276040
中通过。2026-11-10 的市场研究文档更新只是本地提交，尚未推送。
This section is a dated snapshot; no other section records the current commit. As of
2026-11-10: the last pushed commit is `1c16f25` (protecting the frozen showcase libraries,
separating personal data), and its GitHub Actions run 42650820367 passed both the test and the
browser jobs (as reported by the user on 2026-11-10). The earlier `d6c1a5d` passed in run
42634276040. The documentation update after the market review of 2026-11-10 is a local commit,
not yet pushed.

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
| M5a Markdown 预览 M5a Markdown preview | 👀 已提交，CI 自 `d6c1a5d` 全绿。**未完成：**只用含 M5b 的工作区构建的安装包检查过离线预览（2026-11-11，可用），只含已提交 M5a 的构建从未检查；用户的人工验收没有记录。Committed; CI green since `d6c1a5d`. **Open:** the offline preview was checked only in a package built from the working tree with M5b (2026-11-11: it works), never in a build of the committed M5a alone; the user's manual acceptance isn't recorded. | `b9323dc`, `001b10f` |
| M5b LaTeX 数学公式 M5b LaTeX maths | ✅ 2026-11-11 提交、推送，CI 通过：`330362d`，运行 43007792666（第一次运行 43002486914 中浏览器测试失败：一个测试的误报，已在 `330362d` 修正，以及 L25）。Committed, pushed and CI-verified 2026-11-11: `330362d`, run 43007792666 (the first run, 43002486914, failed in the browser job: a false positive in one test, fixed in `330362d`, and L25). | `54c761e`, `330362d` |
| M5c 格式工具栏与显示偏好 M5c Formatting toolbar and display preferences | ✅ 2026-11-11 提交、推送，CI 通过：`9088646`，运行 43027506402（第一次运行 43022257625 中浏览器测试超过 15 分钟的限制，之后分到几个运行器上；那次的两个失败见 L25、B32）。Committed, pushed and CI-verified 2026-11-11: `9088646`, run 43027506402 (in the first run, 43022257625, the browser tests ran past their 15-minute limit; they were then split across runners; that run's two failures: L25, B32). | `ab9c666`, `9088646` |
| B32 章节勾选的可靠保存 B32 reliable chapter-tick saving | ✅ 2026-11-11 提交、推送，CI 通过：运行 43051704210。原来那次 CI 失败的原因仍未确定（第 11 节）。Committed, pushed and CI-verified 2026-11-11: run 43051704210. The cause of the original CI failure is still unknown (section 11). | `3dc9d2b`, `eee608c` |
| RS1 阅读状态与按进度排序 RS1 Reading status and progress sorting | ✅ 2026-11-11 批准（在 M5d 之前），已提交、推送，CI 通过：`e4c6d11`，运行 43061713059。Approved 2026-11-11 (before M5d); committed, pushed and CI-verified: `e4c6d11`, run 43061713059. | 提交 commit "Add reading status management and progress sorting" |
| M5d 粘贴截图和图片 M5d Pasted screenshots and images | ✅ 2026-11-13 提交、推送，CI 通过（运行 43403052717：Python 测试和 Ruff、浏览器分片 1、分片 2、笔记面板关闭的浏览器测试全部通过；第一次运行即成功，没有重跑）。支持粘贴 PNG/JPEG/WebP 图片，安全地保存为笔记资源，本地备份包含图片。Committed, pushed and CI-verified 2026-11-13 (run 43403052717: Python tests and Ruff, browser shard 1, browser shard 2 and the notes-panel-closed browser tests passed; overall success on the first attempt, no reruns). Pasted PNG/JPEG/WebP images, stored safely as note assets; local backups include them. | `4e4abce` |
| M5e 截图识别为公式 M5e Local formula OCR | ✅ 2026-11-13 提交、推送，CI 通过（同一提交和运行）。可选的 Pix2Text MFR 1.5 模型，下载前须用户同意，安装后在本机离线识别；可编辑 LaTeX，KaTeX 预览。Committed, pushed and CI-verified 2026-11-13 (the same commit and run). The optional Pix2Text MFR 1.5 model, downloaded only with the user's consent; recognition runs locally and offline once installed; editable LaTeX with KaTeX preview. | `4e4abce` |
| 第 4b 节：多个书库、测试/示例书库、可迁移书库 Section 4b: several libraries, Test & Demo library, portable libraries | ✅ 含 L15 修复 with the L15 fix | `2b0ff96`, `4094dc4` |
| 页面重新载入时连接被拒（监听队列 5 → 64）Connections refused on reload (listen backlog 5 → 64) | ✅ | `d6c1a5d` |
| 文档重组；冻结的示例书库和测试书库受保护（第 10 节）Documentation restructured; frozen showcase and test libraries protected (section 10) | ✅ CI 运行 run 42650820367 | `48b55f1`, `1c16f25` |
| 平台准备：`scripts/platform_services.py`（打开编辑器、文件夹对话框、用户数据文件夹），见 X1 Platform groundwork: `scripts/platform_services.py` (opening editors, the folder dialog, the user-data folder), see X1 | ✅ CI 运行 run 42811025108；macOS 部分只用模拟测试 macOS branches tested with mocks only | `b592a85` |
| B28 安全修复：Windows 编辑器经 `cmd.exe` 的命令注入（第 11 节）B28 security fix: editor command injection through `cmd.exe` on Windows (section 11) | ✅ 回归测试；隔离的真实 VS Code 验证 regression tests; isolated real VS Code check | 提交 commit "Fix Windows editor command injection in special-character paths" |
| L21 修复：相同的 ISBN 不再证明是同一个 PDF（第 11 节）L21 fix: a shared ISBN no longer proves the same PDF (section 11) | ✅ L21 回归测试和数据安全测试通过；完整测试中有 B30 的间歇失败 L21 regression and data-safety tests pass; the full suite hit B30's intermittent failure | 提交 commit "Prevent ISBN-based replacement and merging of different PDFs" |
| B29 修复：相同的 DOI 不再证明是同一个 PDF（第 11 节）B29 fix: a shared DOI no longer proves the same PDF (section 11) | ✅ B29/L21 回归测试、相关测试、一次完整测试和书库浏览器测试通过 B29/L21 regression tests, related tests, one full run and the library browser tests pass | 提交 commit "Prevent DOI-based replacement and merging of different PDFs" |
| B30 修复：并发和先后加入同一个术语（第 11 节）B30 fix: the same glossary term added twice, at once or one after the other (section 11) | ✅ 术语表测试、并发重复运行、一次完整测试通过 glossary tests, repeated concurrent runs, one full run pass | 提交 commit "Fix glossary duplicate detection with stable term normalization" |
| L23 修复：查词与加入用同一种"同一个术语"（第 11 节）L23 fix: lookup and adding share one "same term" (section 11) | ✅ L23 测试、相关测试、查词浏览器测试、一次完整测试通过 L23, related, lookup browser tests and one full run pass | 提交 commit "Fix glossary lookup consistency with term normalization" |
| 双语用户手册 Bilingual user manual | ✅ 现为 now [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | `121c67b` |

测试数量会随代码变化，这里不记录；以 CI 和本地运行的实际结果为准。**L20**（一次未识别的测试失败）仍未解决，见第 11 节。
Test counts change with the code and aren't recorded here; CI and actual local runs are what
count. **L20** (one unidentified test failure) stays unresolved, see section 11.

---

## 2. 当前里程碑 / The current milestone

**2026-11-18 状态 / Status:** M6（引用到笔记 Quote to note）和 M7（回到原文 Back to the passage）都已完成：已提交、推送并通过 CI。M6：`37a2604`，运行 43884196100。M7：`4a69511`（功能）、`89c5167`（浏览器时钟测试等待位置 API 的回答）、`f18faa0`（浏览器 CI 分成三个分片，记录 L25 再次出现），运行 44282194019 第 1 次尝试五个作业全部通过（Python 测试和 Ruff、浏览器分片 1–3、笔记面板关闭）。当前工作是 M7.1 稳定化（见下），在 M8 之前完成。
M6 and M7 are complete: committed, pushed and CI-verified. M6: `37a2604`, run 43884196100. M7: `4a69511` (the feature), `89c5167` (the browser clock test waits for the position API's answer) and `f18faa0` (browser CI in three shards; L25's recurrence recorded); run 44282194019, attempt 1, all five jobs passed (Python tests and Ruff, browser shards 1–3, notes panel closed). The current work is the M7.1 stabilization below, completed before M8.

**M7.1 稳定化 / M7.1 stabilization (approved 2026-11-18).** 来自 M7 之后的独立代码审计（Codex，六个已复现的问题 FA-01–FA-06）和历史问题登记。From the independent post-M7 code audit (Codex: six reproduced defects FA-01 to FA-06) and the historical issue register. S0–S7 are the pre-M8 target, in this order; each batch has its own fail-before/pass-after regressions, independent review and separate commit, push and CI approvals. Deferring a batch or an item needs a written justification and the owner's explicit approval, recorded here. The detailed implementation plan (revision 2, approved) and the audit evidence are kept locally, not in git.

| 批次 Batch | 内容 Contents | 状态 Status |
|---|---|---|
| S0 | M7 收尾文档；D18 静态守卫测试（不修复 D18）M7 closeout docs; D18 static guard test (does not fix D18) | ✅ `68dd75b`，CI 运行 run 44286926155 |
| S1a | FA-03：合并重复项时与笔记保存的竞争（已确认的保存可能丢失）Merge vs a concurrent note save (an acknowledged save can be lost) | ✅ `6912bbd`，CI 运行 run 44505418465（第 1 次尝试，五个作业全部通过 attempt 1, all five jobs passed） |
| S1b | FA-01：清空归档时根目录的链接/联接（可能删除书库以外的文件）A linked/junctioned archive root (deletion outside the library) | ✅ `0a078ad`，CI 运行 run 44521803189：第 1 次尝试两个浏览器分片各有一个测试失败（与 S1b 无关的超时，原因未确认，见 B39、B40），经所有者批准只重跑失败的作业一次，第 2 次尝试全部通过 attempt 1: two browser shards each failed one test (timeouts unrelated to S1b, causes unconfirmed, see B39, B40); with the owner's approval the failed jobs were rerun once; attempt 2 passed |
| S1c | FA-02：书库页面中书库名称的脚本注入 Library name injected as script into the library page | ✅ `17e8d77`，经其后代提交 `3b901d6`（B39）通过 CI：运行 run 44722195750 第 1 次尝试，五个作业全部通过。`17e8d77` 自己的运行 run 44703480992 第 1 次尝试仍记为失败（浏览器分片 1 的一个测试，B39 的设置步骤，与 S1c 无关；其余四个作业通过，链接测试已运行；原作业没有重跑）。verified through its descendant commit `3b901d6` (B39): run 44722195750, attempt 1, all five jobs passed. `17e8d77`'s own run 44703480992, attempt 1, stays recorded as failed (one test in browser shard 1, B39's setup step, unrelated to S1c; the other four jobs passed, link tests ran; the original job not rerun). |
| — | **S1 完成 S1 complete**（S1a、S1b、S1c 都已提交、推送并通过 CI committed, pushed and CI-verified）；B39 已提前处理并通过 CI B39 brought forward and CI-verified: `3b901d6`，运行 run 44722195750 第 1 次尝试 attempt 1 | ✅ |
| S2 | FA-04 + FA-05：备份按内容比较 PDF；检测删除 Backup compares PDF contents; detects deletions。Codex 审查（要求修改，所有者接受，2026-11-20）后同批加入 After Codex's review (request changes, accepted by the owner, 2026-11-20), also in this batch：B41（长路径 long paths）、同一备份文件夹一次只做一个备份 one backup at a time per backup folder、保留旧 zip 的规则 retention、说明文件的 CRC the instructions' CRC、名为 RESTORE.txt 的书库文件 a library's own RESTORE.txt | ✅ 实现完成，经 Codex 四轮独立审查，最终结论“批准，有非阻塞问题”（剩余一项记为 B42，排入 S6），所有者接受；已提交并推送 `e28bf18`，CI 运行 run 45155217482 第 1 次尝试，五个作业全部通过（Python 1,145 个通过、8 个跳过，都是可选的公式识别模型；要求运行的 Windows 符号链接和联接测试都已运行并通过）implementation complete; four rounds of Codex's independent review, final verdict APPROVE WITH NON-BLOCKING FINDINGS (the one remaining finding recorded as B42, for S6); accepted by the owner; committed and pushed as `e28bf18`, CI run 45155217482, attempt 1, all five jobs passed (Python: 1,145 passed, 8 skipped, all the optional formula-OCR model; the required Windows symlink and junction tests ran and passed)（第 11 节 FA-04/FA-05 section 11） |
| — | **S2 完成 S2 complete**：已提交、推送并通过 CI committed, pushed and CI-verified：`e28bf18`，运行 run 45155217482 第 1 次尝试 attempt 1 | ✅ |
| S3 | FA-06：设置的跨进程事务，页面只发送改动的字段 Cross-process settings transaction; the page sends only changed fields | ✅ **本地完成：Codex 最终独立验证“可以提交，有非阻塞意见”，所有者接受并批准一次本地提交（2026-11-24）；未推送，未通过 CI。Completed locally: Codex's final independent verification READY WITH NON-BLOCKING FINDINGS, accepted by the owner, who approved one local commit (2026-11-24); not pushed, not CI-verified.** 历史 History：规划和调查已批准（2026-11-23）planning and investigation approved (2026-11-23)。范围 Scope：FA-06、B43、B44（所有者把 B44 加入 S3 the owner added B44）。Codex 第一次计划审查：要求修改计划，所有者接受全部四项 Codex's first plan review: plan revision required, all four accepted：(1) 线程锁和操作系统锁共用一个 5 秒的获取期限，嵌套调用的行为写明 one 5 s acquisition deadline for the thread and OS locks, nesting defined；(2) 锁标记文件的安全创建和统一的锁身份（真实路径，文件名不同则锁不同；拒绝链接和冻结位置）safe lock-marker creation and one lock identity (real path; different file names, different locks; links and frozen locations refused)；(3) 只替换值的确切范围，发布前解析并按类型核对，不相关的字节保持不变 exact value-span edits, parsed and type-checked before publishing, unrelated bytes unchanged；(4) 先验证再转换（`"false"` 不再存成 `True`），页面只发送改动的字段 validation before coercion (`"false"` no longer stored as `True`), the page sends only changed fields。Codex 第二次计划审查：要求修改计划，所有者接受全部五项，并决定 D3（接受 B44 写入争用的剩余风险，但旧文件必须完好、可重试的错误、不重启、锁和临时文件都清理）和 D4（存储的设置类型不对时不自动修复，拒绝更新并说明）Codex's second plan review: plan revision required, all five accepted; owner decisions D3 (B44 writer contention accepted as a residual risk only with the old file intact, a retryable error, no restart, locks and temp files cleaned up) and D4 (an invalid stored setting type is never repaired: the update is refused with an explanation)。修订：确定性验收与压力特征测试分开；启动和运行时同一读取策略；唯一的规范设置目标，保留锁标记命名空间；独立的值边界验证；保存进行中不能关闭对话框 Revisions: deterministic acceptance separated from stress characterization; one read policy for startup and runtime; one canonical settings destination, reserved lock-marker namespace; independent value-boundary validation; the dialog can't be dismissed while a save is pending。Codex 第三次计划审查：要求修改计划（三项），所有者接受并选择最小修正 Codex's third plan review: plan revision required (three findings), accepted with the owner's minimum corrections：D5 — Windows 上区分大小写的文件夹中的设置不受支持，安全地拒绝 settings in a case-sensitive Windows folder are unsupported and refused safely；明确指定的 `MYLIBRARY_SETTINGS` 文件消失时始终报错，绝不当作空设置 a missing explicit `MYLIBRARY_SETTINGS` file is always an error, never empty settings；压力测试用持久化的哨兵值并分别统计每次写入的结果 the stress test uses a persisted sentinel and classifies every write outcome。Codex 对第 4 版的差异审查：要求修改两项，所有者接受 Codex's differential review of revision 4: two corrections required, accepted：区分大小写的查询失败一律拒绝 any failed case-sensitivity query refuses；只有经过验证的、重试用完的替换阻塞才算 D3，其他写入失败报告为一般的保存失败 only a verified, retry-exhausted replacement block counts as D3, other write failures are reported as a generic save failure。计划第 5 版经 Codex 批准（有非阻塞意见），所有者批准实现和本地测试（2026-11-23）plan revision 5 approved by Codex (non-blocking findings), implementation and local testing approved by the owner (2026-11-23)。**已实现并本地验证（2026-11-24），等待 Codex 独立审查；尚未提交、推送或通过 CI。Implemented and verified locally (2026-11-24), awaiting Codex's independent audit; not committed, pushed or CI-verified.** 实现中的决定 Implementation decisions：纯 TOML 编辑放在新模块 `scripts/settings_toml.py`；Windows 查询放在 `platform_services`；替换被阻止后对“正在使用”最多查看 5 次（约 0.1 秒），只有真正看到共享冲突才算 D3。The pure TOML editing is in a new module `scripts/settings_toml.py`; the Windows queries are in `platform_services`; after a blocked replacement the in-use probe looks up to 5 times (about 0.1 s), and only a sharing violation actually seen counts as D3. **Codex 第一次实现审查：要求修改（三项，所有者全部接受，2026-11-24）Codex's first implementation audit: REQUEST CHANGES (three findings, all accepted by the owner, 2026-11-24)：** (1, High) 通过 `\\?\` 选择 `settings.toml.` 时保存写进了旁边的 `settings.toml`：现在拒绝 Windows 会改变含义的路径名，并核对跟随后的位置是同一个文件 selecting `settings.toml.` through `\\?\` saved into the neighbouring `settings.toml`: names Windows changes are now refused and the followed location is checked to be the same file；(2, Medium) 只读且被打开的文件曾被报告为可重试的 D3：现在只读优先，D3 还要求读回确认未变，所有失败都按读回结果报告文件状态 a read-only file also held open was reported as a retryable D3 block: read-only now wins, D3 also needs the file read back unchanged, and every failure reports the state read back；(3, Medium) 用 `MYLIBRARY_SETTINGS` 指定区分大小写文件夹中的文件时启动没有停止：现在启动时检查 D5 a file chosen with `MYLIBRARY_SETTINGS` in a case-sensitive folder didn't stop the start: D5 is now checked at the start。**第 1 轮修正已实现并本地验证，等待 Codex 第二次审查；尚未接受、提交、推送或通过 CI。Round 1 corrections implemented and verified locally, awaiting Codex's second audit; not accepted, committed, pushed or CI-verified.** **Codex 第二次实现审查：批准，有非阻塞意见（2026-11-24），所有者接受实现，要求先改两项低严重度问题 Codex's second implementation audit: APPROVE WITH NON-BLOCKING FINDINGS (2026-11-24); the owner accepts the implementation and asked for two low-severity corrections first：** (1, Low) 两个设置符号链接测试在 `MYLIBRARY_REQUIRE_LINK_TESTS=1` 下仍会跳过：现在用 `tests/link_policy.symlink_or_skip`，CI 中创建不了链接即失败，本地无权限时仍跳过，另有模拟创建失败的策略测试 two settings symlink tests still skipped under `MYLIBRARY_REQUIRE_LINK_TESTS=1`: they now use `tests/link_policy.symlink_or_skip` (fails in CI when the link can't be made, still skips locally without the privilege), with a policy test on a simulated failure；(2, Low) 启动时用 `os.path.isdir` 检查 `.myLibrary-local`，查看失败会被当作没有：现在用 `lstat`，只有“找不到”算没有，拒绝访问、其他错误、链接或文件都让启动停止，什么都不创建 the start check used `os.path.isdir` on `.myLibrary-local`, taking a failed look for absence: it now uses `lstat`; only "not found" is absence, and access denied, any other error, a link or a file stop the start, creating nothing。第 2 轮本地检查 Round 2 local checks（2026-11-24，Windows 11，Python 3.14，基于 `e28bf18` 的工作区 working tree on `e28bf18`）：`uv run pytest -q -rs` 1325 个通过、24 个跳过（全部是本机不能创建符号链接 all for lacking the local symlink privilege；其中 3 个是 S3 的：悬空的设置文件链接、设置文件是符号链接、`.myLibrary-local` 是符号链接 3 are S3's: the dangling settings link, the symlinked settings file, a symlinked `.myLibrary-local`，必须在 CI 上真正运行通过 they must really run and pass on CI）；Edge 浏览器分片 browser shards 104、103、103 个通过 passed；`--notes-closed` 22 个通过；`test_reference_nav.py --notes-closed` 48 个通过；分片检查、`ruff check .`、`ruff format --check .`、`git diff --check` 通过 pass。证据 Evidence：`.cache/m7.1-evidence/s3/round2/`。**Codex 最后的针对性审查：需要针对性修正（两项，所有者接受，2026-11-24）Codex's final targeted review: TARGETED CORRECTION REQUIRED (two findings, accepted by the owner, 2026-11-24)：** (Medium) 第 2 轮的启动错误和用户手册建议删除无法查看的 `.myLibrary-local`，但它还可能有书库登记、日志和 Test & Demo 副本：现在消息和手册都不建议删除这个文件夹，分别说明无法查看（检查驱动器和权限）、不是文件夹（先查看并保留内容）、链接或联接点（只去掉链接本身，保留它指向的文件夹），myLibrary 什么都不改；启动仍然停止 round 2's start error and user guide advised removing an unreadable `.myLibrary-local`, which can also hold the library registry, logs and Test & Demo copies: the messages and the guide no longer suggest deleting it and cover each case apart (can't be looked at: check the drive and permissions; not a folder: inspect it and keep its contents; a link or junction: remove only the link itself, keeping the folder it points to); myLibrary changes nothing, and the start still stops；(Low) T-S5 在不能创建符号链接时悄悄返回，整个测试仍报告通过：拆成硬链接和符号链接两个测试，后者用 `symlink_or_skip` T-S5 returned silently when no symbolic link could be made, so the whole test reported a pass: split into a hard-link test and a symbolic-link test using `symlink_or_skip`。第 3 轮只做了针对性检查（没有重跑完整套件；上面第 2 轮的完整结果是修正之前的）Round 3 ran focused checks only (the full suites were not rerun; the round 2 totals above predate this correction)：相关测试 22 个中 18 个通过、4 个符号链接测试明确跳过；`MYLIBRARY_REQUIRE_LINK_TESTS=1` 时同样这 4 个失败 focused tests 18 passed and 4 symlink tests explicitly skipped, the same 4 fail with `MYLIBRARY_REQUIRE_LINK_TESTS=1`；`ruff check .`、`ruff format --check .`、`git diff --check` 通过 pass。证据 Evidence：`.cache/m7.1-evidence/s3/round3/`。**所有者接受这两项修正，并要求再改一处保存时的消息（2026-11-24）The owner accepted both corrections and asked for one more save-time message correction (2026-11-24)：** 保存时 `.myLibrary-local` 是普通文件也会说“Remove the link”：现在保存和启动用同样的三种说明（无法查看、不是文件夹、链接或联接点），无法查看时报告 `SettingsUnreadable` 而不是原始的 `PermissionError`，都不建议删除，什么都不改 a save that found `.myLibrary-local` a plain file said "Remove the link": the save now gives the startup's three explanations (can't be looked at, not a folder, a link or junction), reports `SettingsUnreadable` rather than a raw `PermissionError` when it can't look, never advises deletion and changes nothing。第 4 轮针对性检查 Round 4 focused checks：受影响的五个测试文件 the five affected test files 187 个通过、5 个符号链接测试跳过 187 passed, 5 symlink tests skipped；`ruff check .`、`ruff format --check .`、`git diff --check` 通过 pass；完整套件没有重跑 full suites not rerun。证据 Evidence：`.cache/m7.1-evidence/s3/round4/`。**所有者接受这些修正，并要求最后修正锁标记的消息（2026-11-24）The owner accepted these corrections and asked for a last marker-message correction (2026-11-24)：** 锁标记路径上的东西不对时消息说“Remove it (it holds nothing)”，即使那里是一个文件夹：现在分别说明是链接或联接点（只去掉链接本身，保留它指向的东西）、文件夹、不是普通文件的项目、或硬链接，查看失败报告 `SettingsUnreadable`；都不说它是空的，不建议删除，什么都不改；检查本身不变 the marker message said "Remove it (it holds nothing)" even for a folder at the marker's name: it now says whether it found a link or junction (remove only the link itself, keeping what it points to), a folder, an item that isn't a plain file, or a hard link, and a failed look is `SettingsUnreadable`; none calls the item empty or advises deleting it, nothing is changed, and the checks themselves are as before。第 5 轮针对性检查 Round 5 focused checks：相关测试 27 个通过、5 个符号链接测试跳过，`MYLIBRARY_REQUIRE_LINK_TESTS=1` 时这 5 个失败 focused tests 27 passed, 5 symlink tests skipped, the same 5 fail with `MYLIBRARY_REQUIRE_LINK_TESTS=1`；受影响的五个测试文件 the five affected test files 190 个通过、5 个跳过 190 passed, 5 skipped；`ruff check .`、`ruff format --check .`、`git diff --check` 通过 pass；完整套件没有重跑 full suites not rerun。证据 Evidence：`.cache/m7.1-evidence/s3/round5/`。**Codex 最终独立验证：可以提交，有非阻塞意见（READY WITH NON-BLOCKING FINDINGS），所有者接受，修正两项低严重度问题后批准一次本地提交（2026-11-24）Codex's final independent verification: READY WITH NON-BLOCKING FINDINGS, accepted by the owner, one local commit approved after two Low corrections (2026-11-24)：** (Low) 第一次保存先创建了 `.myLibrary-local`，然后查看锁标记失败，消息却说“nothing was changed”：查看失败的保存消息现在只说“the settings file was not changed” a first save created `.myLibrary-local`, then failed to look at the marker, yet said "nothing was changed": a save that can't look now says only "the settings file was not changed"；(Low) `symlink_or_skip` 把任何 `OSError` 都当作没有权限而跳过：现在本地只有 Windows 的 ERROR_PRIVILEGE_NOT_HELD（1314）才跳过，缺少文件夹和其他错误照常报错，`MYLIBRARY_REQUIRE_LINK_TESTS=1` 时任何失败都让测试失败；另有测试确认五个 S3 符号链接回归都用这个规则 `symlink_or_skip` skipped on any `OSError`: locally only Windows' ERROR_PRIVILEGE_NOT_HELD (1314) skips now, a missing folder and other errors are raised, and with `MYLIBRARY_REQUIRE_LINK_TESTS=1` any failure fails the test; a test confirms all five S3 symlink regressions use this rule。最终针对性检查 Final focused checks（2026-11-24，Windows 11，Python 3.14）：相关测试 40 个中 35 个通过、5 个符号链接测试因本机缺少权限（1314）跳过，`MYLIBRARY_REQUIRE_LINK_TESTS=1` 时这 5 个失败 focused tests 35 passed and 5 symlink tests skipped for the missing local privilege (1314), the same 5 fail with `MYLIBRARY_REQUIRE_LINK_TESTS=1`；受影响的六个测试文件 the six affected test files 234 个通过、5 个跳过 234 passed, 5 skipped；`ruff check .`、`ruff format --check .`、`git diff --check` 通过 pass。最近一次完整运行是第 2 轮（早于第 3–5 轮和最终修正，这些修正只改了消息、测试和测试辅助）The latest full runs are round 2's (before rounds 3–5 and the final corrections, which changed only messages, tests and the test helper)：Python 1,325 个通过、24 个跳过 passed, 24 skipped；浏览器分片 browser shards 104、103、103；`--notes-closed` 22；`test_reference_nav.py --notes-closed` 48；T-R6 压力特征测试是第 1 轮的 the T-R6 stress characterization is round 1's。保留的限制 Retained limitations：D3（读取者打开文件时保存可能被阻止，报告为可重试 readers holding the file open can block a save, reported as retryable）；D5（区分大小写或无法确认的 Windows 文件夹被拒绝 case-sensitive or unanswerable Windows folders refused）；网络共享上的锁未测试 locks on network shares untested；被结束的进程的锁由操作系统释放 a killed process's lock is released on the operating system's timing；保存中途被结束可能留下临时文件 a process killed mid-save can leave a temporary file。S3 的符号链接测试在本机没有真正运行，必须在 CI 中运行并通过 S3's symlink tests have not really run on this machine and must run and pass in CI。证据 Evidence：`.cache/m7.1-evidence/s3/final/`。 |
| S4 | B13（清空归档时保留原始 PDF keep original PDFs）+ B25/B33（README 字节不变 preserve README bytes） | 📋 |
| S5 | B22 + B23 + B24：笔记请求的超时、重试和冲突 note request timeouts, retry and conflicts。另外（S1a 的后续，M8 之前必须完成）：同一份文档自己的草稿在恢复、丢弃和清理时，要防止其他浏览器标签页同时写入造成的丢失；按草稿的确切快照识别（与 S1a 跨文档交接的 `drafts.settle` 相同的保护）；确定性的多标签页回归测试，并有修复前失败、修复后通过的证据。Also (S1a follow-up, mandatory before M8): a document's own drafts restored, discarded and cleaned up safely against concurrent writes from other browser tabs; protection by the draft's exact snapshot identity (as `drafts.settle` does for S1a's cross-document handoff); deterministic multi-tab regression tests with fail-before/pass-after evidence. | 📋 |
| S6 | B21, B4, B14(b), B16(b), B16(c), B42：小的正确性修复 small correctness fixes | 📋 |
| S7 | B36, B37 + B27, B38, B40（M8 之前必须调查 mandatory investigation before M8；B39 已提前处理 B39 brought forward）, L25：测试稳定性，先取证 test stability, evidence first; 另外一项观察 and, separately from L25, one observation: M7 CI 运行 44110143759 中一个 `/api/position` keepalive 请求：在断言之前没有观察到回答；服务器是否收到以及请求最终的结果都没有得到证明；是延迟还是丢失尚未确定。这项观察与 L25 分开。测试已改为等待回答（`89c5167`）。In M7 CI run 44110143759, an `/api/position` keepalive request: no response was observed before the assertion. Server receipt and the request's eventual outcome remain unproven; delay versus loss is unresolved. This observation is separate from L25. The test now waits for the answer (`89c5167`). | 📋 |

S8（之后，按需 later, as needed）：D18（任何正式的重命名调用之前必须修复 must be fixed before any production rename caller: UI, CLI, API, endpoint, job）、ECDICT 固定版本 pin、B12 + L22（安装包分发之前 before package distribution）。P2 项目推迟 P2 items deferred. L29（☁ Git 备份暂停 paused）和 L30（安装包许可 package licences）的闸门不变 gates unchanged.

**2026-11-13 状态 / Status:** M5d 和 M5e 已完成开发，已提交、推送并通过 CI（`4e4abce`，运行 43403052717：Python 测试和 Ruff、浏览器分片 1、分片 2、笔记面板关闭的浏览器测试全部通过；第一次运行即成功，没有重跑）。
M5d and M5e are complete: committed, pushed and CI-verified (`4e4abce`, https://github.com/NanLi0207/myLibrary/actions/runs/43403052717;
run 43403052717: Python tests and Ruff, browser shard 1, browser shard 2 and the notes-panel-closed browser tests passed; overall success on the first attempt, no reruns). Implementation and verification details: [M5 verification
record](docs/M5_VERIFICATION.md). M5a acceptance, L24–L27 and B33 remain open; L29 (automatic
Git backup, paused pending a security redesign) and L30 (licence questions) remain open.
The documentation commit after it, `ee23329`, is **not CI-verified**: its run 43414437518
failed in both browser shards (a test race, B34, and an L25 network failure), not rerun.

**安装包状态（与开发状态分开）/ Package status (separate from development):** Windows 便携版
`myLibrary-0.2.5-win64.zip`（SHA-256 `e617e00667e6a0b5b98d549cc2ee9316a37f3f8789c96dc313b46125e781bc76`）
已通过 25/25 项自动化安装包验收检查。**公开测试版尚未发布**，此安装包**未获准公开分发**。
The Windows portable package `myLibrary-0.2.5-win64.zip` (SHA-256
`e617e00667e6a0b5b98d549cc2ee9316a37f3f8789c96dc313b46125e781bc76`) passed 25 of 25 automated
packaged acceptance checks (docs/M5_VERIFICATION.md). Distinct stages:
- 开发完成 Development complete: ✅ (`4e4abce`)
- CI 通过 CI-verified: ✅ (run 43403052717)
- 安装包自动化验收 Packaged automated acceptance: ✅ 25/25
- 公开测试版发布 Public Beta release: ❌ **not yet**; the package is **not approved for public
  redistribution**.
- **B35（2026-11-13）改动了应用代码**：上面的安装包早于此修正，不再是发布候选；需要重新构建、新的 SHA-256 并重新做安装包验收（需另行批准）。**B35 (2026-11-13) changed application code:** the package above predates the fix and is no longer the release candidate; a rebuild, a new SHA-256 and renewed packaged acceptance are needed (separate approval).

Remaining before a public Beta: 用真实截图和真实 PDF 中有代表性的公式做人工验收 manual
acceptance with real screenshots and representative formulas from actual PDFs; 在干净的 Windows
账户上启动和快捷方式 a clean Windows account's launch and shortcuts; 整机离线验证 whole-machine
offline verification; GEOS 的 LGPL 再分发和应用许可兼容性的决定 the GEOS LGPL redistribution and
application-licence compatibility decision (L30).

**任务 4 / Task 4, M5（预览、公式、格式、粘贴图片 / preview, maths, formatting, pasted images）。**
M5a 已提交；M5b 已提交、推送并通过 CI（`330362d`）；M5c 已提交、推送并通过 CI（`9088646`）；RS1（阅读状态，第 3 节）已提交、推送并通过 CI（`e4c6d11`，运行 43061713059）；M5d/M5e 已提交、推送并通过 CI（`4e4abce`，运行 43403052717）。
M5a is committed; M5b is committed, pushed and CI-verified (`330362d`); M5c is committed, pushed and
CI-verified (`9088646`); RS1 (reading status, section 3) is committed, pushed and CI-verified
(`e4c6d11`, run 43061713059); M5d/M5e are committed, pushed and CI-verified (`4e4abce`,
run 43403052717).

开发会话只做已有工作的收尾（例如 M5a 的安装包验证、上面列出的发布前验收）和经同意的第 11 节错误修复；下一个里程碑须经用户批准，
不开始 P2–P5 或新条目 E/R/G/X/U。
Sessions cover finishing earlier approved work (e.g. M5a's package check and the pre-release
acceptance above) and fixes from section 11 with agreement; the next milestone starts only with
the user's approval; nothing from P2–P5, none of the new E/R/G/X/U items.

**仍未完成 / Still open:** M5a 在只含已提交代码的安装包中的离线预览检查和用户的人工验收（第 1 节）。
M5a's offline-preview check in a package built from committed code and the user's manual
acceptance (section 1).

**L21**（数据完整性 data integrity）：2026-11-10 复现并修复（第 11 节"已修复"）。Reproduced and fixed 2026-11-10
(section 11, "Fixed"). **新发现 / Found on the way:** B29（DOI 的同类问题 the DOI analogue）、B30（术语表并发测试间歇失败，
原因已找到 an intermittent glossary concurrency failure, cause since found）。

**接下来的顺序（用户 2026-11-10 定）/ Next, in this order (the user's decision, 2026-11-10):**
1. B29 ✅（已修复 fixed）：DOI 造成的错误重复判断（添加和刷新）；方针：只有相同的 DOI 不能授权破坏性的重复处理，没有证明文件相同时保留各自的文档。B29: false
   duplicates by DOI (Add and Refresh); policy: a matching DOI alone never authorises destructive duplicate handling, and
   separate documents are kept unless the files are shown to be the same.
2. B30 ✅（已修复 fixed）：并发加入术语的间歇失败，单独调查根本原因（初步调查找不到原因时咨询一次 Fable 专家）。B30: the intermittent concurrent
   glossary insertion, its root cause investigated on its own (one Fable consultation if a first targeted look can't find it).
3. 完整回归验证和 CI。Full regression verification and CI.
4. 以上都审核后才继续 M5b。M5b resumes only after the above is reviewed.

### 用户验证 / User validation (U1–U3) 📋 方向已批准 direction approved 2026-11-10，未开始 not started

与开发并行，不写代码，不改变里程碑顺序。U1 访谈可以早做；U2 在 PDF → 笔记 → 原文工作流（M6、M7）之后；U3 需要稳定的 Windows
测试版。完整计划、样本量和提议的成功标准见
[DEVELOPMENT_SPEC.md 第 16 节](DEVELOPMENT_SPEC.md#16-用户验证计划--user-validation-plan)。In parallel with development,
with no code and no change to the milestone order. U1 interviews may happen early; U2 follows
the PDF → note → source workflow (M6, M7); U3 needs a stable Windows beta. The full plan, sample
sizes and proposed success criteria are in DEVELOPMENT_SPEC section 16.

| 条目 Item | 内容 Content | 最早 Earliest |
|---|---|---|
| U1 | 8–12 次定性访谈（技术教材学习者和工程师）Qualitative interviews (textbook learners and engineers) | 现在 now |
| U2 | 5–8 次 PDF → 笔记 → 原文的观察，加数据恢复检查 Observed PDF → note → source sessions, with data-recovery checks | M7 之后 after M7 |
| U3 | 10–20 人、2–4 周的 Windows 试用 A Windows beta, 10–20 people, 2–4 weeks | M8 的安装包测试之后 after M8's package test |

没有应用内分析、云端遥测或强制账户。No in-app analytics, cloud telemetry or mandatory accounts.

---

## 3. P0 — 可靠的阅读与笔记 / Reliable reading and note-taking

**目标 / Goal.** 一个可靠的 PDF → 笔记 → PDF 工作流：在 PDF 旁边写笔记、预览、公式、格式、截图；把 PDF 中的一段
引用到笔记；再从笔记回到原文那一段。可靠比功能多更重要。
A reliable PDF → note → PDF workflow: notes beside the PDF with preview, maths, formatting and
screenshots; a passage quoted from the PDF into a note; from the note back to that passage.
Reliability matters more than more features.

**P0 包括 / P0 includes** 可靠的存储和恢复、好用的界面和可安装性：任务 4 的里程碑，加上第 4 节中支撑它们的任务 7（备份与恢复）和任务 8
（剩余修复、安装包测试）。**M6 和 M7 是最重要的产品里程碑 ★**：它们实现核心任务 J2（选区 → 笔记）和 J3（笔记 → 原文段落），见
[DEVELOPMENT_SPEC.md 第 2.4 节](DEVELOPMENT_SPEC.md#24-核心任务--core-jobs-to-be-done)。本节的顺序和依赖不变，下一个是 M5b（待批准）。
Reliable storage and recovery, a usable interface and installability: task 4's milestones,
plus tasks 7 (backup and recovery) and 8 (remaining fixes, the package test) in section 4 that
support them. **M6 and M7 are the key product milestones ★**: they deliver the core jobs J2
(selection → note) and J3 (note → the passage), see DEVELOPMENT_SPEC section 2.4. This
section's order and dependencies are unchanged; next is M5b (awaiting approval).

**共同约束 / Shared constraints** (history, task 4 and section 5, approved 2026-11-07/08)：
`.md` 文件是唯一的权威；所有视图都用 M4 的 `NoteSession`（自动保存、冲突、草稿、离开提醒）；PDF.js 的阅读、标注、
搜索和阅读进度不受影响；依赖使用精确版本和提交在仓库中的 SHA-256，本地提供，不用 CDN，没有构建步骤。
The `.md` file is the only authority; every view uses M4's `NoteSession` (autosave, conflicts,
drafts, the leave warning); PDF.js reading, marks, search and reading progress are unaffected;
dependencies are exact versions with committed SHA-256 values, served locally, no CDN, no build
step.

### M5b — LaTeX 数学公式 / LaTeX maths ✅ (`54c761e`, `330362d`; CI run 43007792666)

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
- **实现 Implementation (2026-11-11):**
  - KaTeX 0.19.1 from the npm registry (`katex-0.19.1.tgz`, 1,499,956 bytes, SHA-256
    `24da5a59…34fd`; npm's SHA-512 and SHA-1 matched; every file used was byte-identical to the
    GitHub release's `katex.tar.gz`). `reader.py`: `KATEX_*`, `install_katex`, `katex_installed`
    (each of the 23 files, `katex.min.js`, `katex.min.css`, `LICENSE` and 20 WOFF2 fonts,
    checked against its committed SHA-256 whenever the reader page is made; not loaded
    otherwise), `setup_maths`, `--setup-maths`, `/vendor/katex/`; `missing()` lists "maths".
  - `preview.js`: markdown-it rules of its own (inline `ml_math`, block `ml_math_block`), no
    regular expression over the text; `trust: false`, `maxSize` 20, `maxExpand` 500, at most
    10,000 characters and 100 nested `{…}` per formula; errors (and stack overflows) caught per
    formula; a formula's result cached per text. `notes.css`: display and error styles.
  - `build_package.py`: `copy_reading_view` copies KaTeX (refuses to build if it isn't
    verified) and its licence; CI's browser job installs and caches it.
- **验证 Verification (2026-11-11; CI: run 43007792666 on `330362d`):** `tests/test_maths_setup.py` (19);
  `tests/browser/test_notes_maths.py` (13, Edge: the four delimiters and common constructs,
  amounts, escapes, code, unclosed delimiters, invalid formulas, hostile input, huge and nested
  formulas, light and dark, views, typing and saving, conflicts and leaving, three kinds of
  missing or broken KaTeX); a package built into a scratch folder, unzipped in a clean
  environment (no uv, its own profile, no network for the server, outside requests blocked in
  Edge): maths typeset with KaTeX's fonts from the package, the PDF opened, nothing written into
  the package folder. Limits: L24 (section 11).

### M5c — 格式工具栏与显示偏好 / Formatting toolbar and display preferences ✅ (`ab9c666`, `9088646`; CI run 43027506402)

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
- **实现 Implementation (2026-11-11):**
  - `reader_static/format.js` (new; `reader.viewer_html` loads it before `notes.js`): every
    action as text in, one replacement out (`apply(value, start, end, action)`), no page access.
    Toggles: inline marks (`**`, `*`, `~~`, `` ` ``, `$`: by the run of markers around or inside
    the selection; several lines: each line), line prefixes (H0–H6, `- `, `1. `, `- [ ] `, `> `:
    every line touched; the selection moves with its text), blocks (```` ``` ```` and `$$`:
    the selection or the lines inside one), link and image (the whole link, or the target the
    button selected). The table is inserted, never toggled.
  - `notes.js`: the toolbar (a heading menu and 14 buttons, shown with the source: hidden in
    Preview), each action one `insertText` (one Undo; the `input` event hands it to the
    `NoteSession`), Ctrl+B / Ctrl+I on the note's textarea only (stopped there), nothing while
    the note can't be typed in (read-only, loading, a draft, a conflict decision on its way) or
    during IME composition; during an unresolved conflict it stays available, like typing (the
    user's decision, 2026-11-11: the changes are part of "mine" until Keep mine / Use disk); Aa: display preferences in `localStorage`
    (`myLibrary.notes.display`, each value checked against the choices) as CSS variables whose
    defaults are the earlier look. `notes.css`: the toolbar, the settings, the variables.
- **验证 Verification (2026-11-11; CI: run 43027506402 on `9088646`):** `tests/browser/test_notes_format.py` (16, Edge:
  every action and its toggle, every button and heading level, the selection, Undo and Redo
  one action at a time, Ctrl+B / Ctrl+I only in the note and PDF.js's keys unchanged, IME
  composition, read-only, autosave, a conflict, the views, a narrow panel, display preferences
  (applied, remembered, reset, invalid stored values, the note never touched));
  `tests/test_preview_setup.py` (format.js served and loaded before notes.js). Limits: L26.

### RS1 — 阅读状态与按进度排序 / Reading status and progress sorting ✅ 已提交、推送，CI 通过 committed, pushed and CI-verified (`e4c6d11`, run 43061713059; approved 2026-11-11)

独立的里程碑，用户决定排在 M5d 之前。（编号 RS1：R1–R3 已经是第 7 节的复习提议。）An independent milestone, put
before M5d by the user. (The id RS1: R1–R3 are already the review proposals of section 7.)

- **目标 Objective:** 读完的文档不再一直排在"按进度排序"的最前面；阅读状态独立于进度百分比，由用户选择。Finished
  documents no longer stay at the top of Sort: progress; a reading status independent of the
  percentage, chosen by the user.
- **数据 Data:** 文档笔记 README 中可选的一行 `Reading status: to read` / `reading` / `finished (YYYY-MM-DD)`
  （标记读完的日期，服务器的日期）。没有这一行 = 自动：勾过章节或读过页面为"在读 Reading"，否则"想读 To Read"，从不自动
  "读完 Finished"（到 100% 也不会）。显式的状态优先。无法理解的行或多于一行：显示出来，myLibrary 从不改写或删除，由用户在
  README 中改正。不移动任何文件，不迁移，不改 UUID、PDF 路径、笔记、勾选和 "Last read"。One optional line in the
  document's notes README; no line = automatic (Reading once a chapter is ticked or a page read,
  else To Read; never Finished, not even at 100%); an explicit status wins. A line it doesn't
  understand, or more than one: shown, never written over or removed by myLibrary, corrected by
  the user in the README. No files moved, no migration; ids, PDF paths, notes, ticks and "Last
  read" untouched.
- **实现 Implementation (2026-11-11):**
  - `library_page.py`: `reading_status`, `status_line`, `with_status` (the line set, replaced or
    removed in the file's own line endings and byte-order mark; removing undoes adding),
    `status_of`; `books()` carries `reading_status`. The page: a status menu on cards and list
    lines ("Automatic (Reading)" shows what it's derived as), a status filter (remembered),
    Sort: progress as Reading (furthest first) → To Read (newest added first) → Finished (most
    recently finished first), then title, then id; "Mark as finished?" at 100%, only on a click;
    the static copy shows the status and filters, without the menu.
  - `library_server.py`: `set_status` and `POST /api/status` (the README as bytes under its lock;
    B32's version record with its own "status" entry, so a status and a tick never conflict;
    409 with the README's status, chapters and version; an invalid line refused with 400);
    tick answers carry the status from the same read.
  - `add_book.merge_into`: the kept copy's valid status wins; without one, the other's valid one
    (its date kept); an invalid line never touched, never two lines.
  - Saving like B32's ticks: saving, failed with Retry, a conflict with Apply mine / OK, the
    leave warning, one request per document at a time, older answers never shown over newer.
- **与 v0.4-4 的关系 Relation to v0.4-4:** v0.4-4（书库搜索页）计划按阅读状态筛选；它会用 RS1 的状态，不再另建。
  v0.4-4 (the library search page) plans a reading-status filter; it will use RS1's status.
- **验证 Verification (local only, 2026-11-11; CI pending):** `tests/test_reading_status.py` (30: the line, invalid
  and duplicated lines, setting, replacing and removing with CRLF/LF and a BOM, no-ops, 100%
  without finishing, conflicts, a restart, a backup and its restore, the static page, HTTP);
  `tests/test_library_jobs.py` (4 merge cases); `tests/browser/test_status.py` (11, Edge: every
  choice, the suggestion, finished staying finished, the three sort groups, the filter
  remembered, a failed save with Retry and the leave warning, rapid choices, two tabs with OK and
  with Apply mine, a line it doesn't understand, the static page). Limits: L27.

### M5d — 粘贴截图和图片 / Pasted screenshots and images ✅ 已提交、推送，CI 通过 committed, pushed and CI-verified (`4e4abce`, run 43403052717)

- **状态 Status (2026-11-13):** 已完成。Complete: committed and pushed in `4e4abce`; CI https://github.com/NanLi0207/myLibrary/actions/runs/43403052717
  (run 43403052717: Python tests and Ruff, browser shard 1, browser shard 2 and the notes-panel-closed browser tests passed; overall success on the first attempt, no reruns). Pasted PNG/JPEG/WebP images are checked from their bytes and
  stored safely as note assets (`notes/<name>/assets/`, atomic, never over another file,
  shown through a contained route); the 💾 local backup includes them. Package status and the
  remaining release acceptance: section 2. Limits: L28.

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

### M5e — 截图识别为公式 / Recognize screenshots as formulas ✅ 已提交、推送，CI 通过 committed, pushed and CI-verified (`4e4abce`, run 43403052717)

- **状态 Status (2026-11-13):** 已完成。Complete: committed and pushed in `4e4abce`; CI https://github.com/NanLi0207/myLibrary/actions/runs/43403052717
  (run 43403052717: Python tests and Ruff, browser shard 1, browser shard 2 and the notes-panel-closed browser tests passed; overall success on the first attempt, no reruns). The optional Pix2Text MFR 1.5 model is downloaded only with the
  user's consent; recognition then runs locally and offline; the LaTeX is editable, with a
  KaTeX preview, and goes into the note only when confirmed. Package status and the remaining
  release acceptance: section 2. Limits: L28; licence questions: L30.

- **范围 Scope (2026-11-12):** optional, free local Pix2Text MFR 1.5 ONNX recognition;
  editable LaTeX and live local KaTeX; explicit insertion through the normal note session.
  本机识别、编辑和预览，确认后经正常笔记会话插入；不上传图片。Local processing; no image upload to a cloud.
- **本里程碑的硬性要求 This milestone's requirements (owner, 2026-11-12):** 公式识别必须完全免费、
  在本机运行；没有云端推理或付费 OCR 接口；不需要账号、订阅、API 密钥或任何持续费用；安装后离线可用。
  Formula OCR must stay completely free and run locally: no cloud inference or paid OCR APIs; no
  required account, subscription, API key or recurring fee; once installed it works offline. (The
  shared network and cost policy, docs/AI_DEVELOPMENT.md section 5, lets a milestone's own limits
  take precedence; these are M5e's.)
- **安装 Installation:** one explicit download of pinned, SHA-256-checked weights (about
  120 MB); offline thereafter. Existing scan-OCR runtime dependencies are reused, loaded
  lazily; no PyTorch, Transformers or Pix2Text Python package added. Missing runtime is an
  actionable error; reading and note editing stay available.
- **候选 Candidates:** up to three distinct completed sequences from beam search over real
  decoder logits, deduplicated; one if only one exists. Scores are model log-probabilities,
  never measured confidence or accuracy. Results need the user's review.
- **验证 Verification:** real model tests with sockets blocked, deterministic mocked API
  integration, and Edge UI tests are recorded separately in
  [docs/M5_VERIFICATION.md](docs/M5_VERIFICATION.md). CI-verified with the commit (run
  43403052717); the package's automated acceptance is recorded there too; public release and
  manual acceptance are still open (section 2). Licenses and redistribution conditions: [docs/FORMULA_OCR_LICENSES.md](docs/FORMULA_OCR_LICENSES.md).
  本地结果只以验证记录中"冻结的最终工作区"那一轮为准；审查前的那一轮浏览器测试作废（运行期间文件仍在改动）。
  Local results: only the run on the frozen final tree in the verification record counts. The
  earlier browser runs (before the independent review) are superseded: files changed while they
  ran. 六个合成公式的期望结果均在候选中（示例，不是准确率）。Six synthetic equations had the
  expected result among candidates (examples, not an accuracy measure).
- **边界 Limits:** printed, tightly cropped single formulas; confusing glyphs, handwriting,
  low-resolution or complex multi-line input can be wrong; CPU timeout and token limits.
  No table recognition, M6 or M7 work.

### M6 — 引用到笔记（PDF → 笔记）/ Quote to note (PDF → note) ✅ 已提交、推送，CI 通过 committed, pushed and CI-verified (`37a2604`, run 43884196100) ★ J2

- **状态 Status（2026-11-16）：** ✅ 已完成：Codex 独立审查（两轮，五个阻塞问题全部修复并复审通过）、用户人工验收、本地提交 `37a26040f282e6c7fbc58f5af3b54d3e837b3d2a`、推送，CI 运行 43884196100 第 1 次尝试四个作业全部通过（Python 测试和 Ruff、浏览器分片 1、分片 2、笔记面板关闭；CI 中符号链接测试全部运行，没有跳过）。Done: Codex independent review (two rounds; all five blocking findings fixed and re-reviewed), the owner's manual acceptance, commit `37a26040f282e6c7fbc58f5af3b54d3e837b3d2a`, pushed; https://github.com/NanLi0207/myLibrary/actions/runs/43884196100 attempt 1: all four jobs passed (Python tests and Ruff, browser shard 1, shard 2, notes panel closed; the symlink tests ran in CI, none skipped). B36、B37（间歇的测试失败）仍未解决，推迟到 M8。B36 and B37 (intermittent test failures) stay open, deferred to M8. 接受的限制见 L31（含 (9)）。Accepted limits: L31, including (9). 选区气泡和查词弹窗中的 引用到笔记 (Quote to note)、Alt+Q、笔记工具栏的 ¶↗ 引用此页 (Reference this page)；`scripts/references.py`（私有存储）、`/api/references/create`、`reader_static/anchors.js`（规范化与 Markdown）。锚点模型见 DEVELOPMENT_SPEC 9.2（已按 Fable 设计审查补充 `page_hash`、`page_size`、`rotation`、`loaded`、`nonce`）。G1 兼容性：锚点只指向来源 PDF 的 UUID 和页索引，不需要锚点迁移（9.2）。限制见 L31。The selection bubble's and lookup popup's Quote to note, Alt+Q, the notes toolbar's ¶↗ Reference this page; `scripts/references.py` (private store), `/api/references/create`, `reader_static/anchors.js` (normalising, Markdown). The anchor model is DEVELOPMENT_SPEC 9.2 (with `page_hash`, `page_size`, `rotation`, `loaded` and `nonce` added after the Fable design review). G1: an anchor names only the source PDF's UUID and a page index, so no anchor migration is needed (9.2). Limits: L31.

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

### M7 — 回到原文（笔记 → PDF）/ Back to the passage (note → PDF) ✅ 已提交、推送，CI 通过 committed, pushed and CI-verified (`4a69511`, `89c5167`, `f18faa0`; run 44282194019) ★ J3

- **状态 Status（2026-11-18）：** ✅ 已完成：按批准的计划（修订 5）实现，Codex 独立审查通过，用户人工验收通过；提交 `4a69511`，CI 修正 `89c5167`（测试）和 `f18faa0`（三个分片），推送，运行 44282194019 第 1 次尝试五个作业全部通过。Done: implemented to the approved plan (revision 5), approved by Codex's independent review and the owner's manual acceptance; commit `4a69511`, CI follow-ups `89c5167` (test) and `f18faa0` (three shards), pushed; run 44282194019, attempt 1, all five jobs passed. `reader_static/navigate.js`（跟随、↩ 返回 Back、查找原文、临时框、明确选择 follow, Back, finding, outline, explicit choice）；`anchors.js` `parseReference`/`safeHref`/`textFromContent`/`candidates`/`queryMatches`；`lookup.js` 阅读进度 reading progress（不可变的位置决定、经验证的阅读移动、按 PDF.js 的规则选页 immutable decisions, verified reading moves, PDF.js's page choice）；`notes.js`/`preview.js` 链接 links；只读的 read-only `/api/references/get`、`/api/document/ids`（`references.peek`、`catalog.peek_retired`、`safe_io.peek_json`）；`/read/` 带引用时为预览 with a reference opens a preview；有序的 ordered `/api/position`（`library_server.ordered_position`）。规则见 DEVELOPMENT_SPEC 9.2；限制见 L32。Rules: DEVELOPMENT_SPEC 9.2; limits: L32. **Codex 实现审查的三个阻塞问题已修复并经复审通过** The three blocking findings of Codex's implementation review were fixed and re-reviewed: 逐页模式下的 ↩ 返回先恢复页面和模式 Back in page-at-a-time mode restores the page and PDF.js's modes first (`navigate.js` `restore`); 在这里继续阅读/开始阅读之后立即计入阅读统计 Continue reading here / Start reading count reading statistics at once (`lookup.js` `continueHere`); 带引用的 `/read/` 只读地解析 id（损坏的墓碑文件读其 `.bak`，不留副本）a `/read/` with a reference resolves its id read-only (a damaged tombstone file is read from its `.bak`, no copy left; `catalog.peek_retired`). **复审后：阅读时间按单调时钟计算实际符合条件的经过时间**（`lookup.js` `account`）：访问和预览期间的时间不计，之前合法的时间保留，不重复计算。After the re-review: reading time is the eligible elapsed time on the monotonic clock (`lookup.js` `account`): time while visiting or previewing is never counted, earlier legitimate time is kept, nothing twice. 每次结算按区间开始时的状态（之前的可见性、活动），隐藏前读的时间保留，隐藏期间不计；不活动的区间在 120 秒处截断，回来后不补算。Each settlement judges the interval by its own state (the visibility before a change, the activity before new activity): time read before hiding is kept, hidden time never counts; an inactive interval is cut at 120 s and never counted afterwards.

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

## 4. P1 — 可信的来源引用 / Trustworthy source references

稳定的锚点、无歧义的段落定位、文档 UUID，以及 PDF 丢失或改变时的平稳恢复（核心任务 J3）。M6 已批准的隐私、版权和引用存储设计
（短的可见引用，完整锚点只在 `.myLibrary/references/`）保持不变。Stable anchors, unambiguous passage resolution,
document UUIDs and graceful recovery from missing or changed PDFs (core job J3). M6's approved
privacy, copyright and reference-storage design (a short visible quote, the full anchor only in
`.myLibrary/references/`) stays as it is.

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

### G1 — 文档结构 / Document structure 📋 方向已批准 direction approved 2026-11-10，未开始 not started

- **目标 Objective:** 一次面向未来的兼容性评估：由一个或多个 PDF 组成的逻辑上的书。评估怎样支持：一个 PDF 是整本书；一个 PDF 只有一章；一个 PDF 有几章；同一本书的多个 PDF；缺章、不同的页码、按顺序的部分覆盖。
  A forward-looking compatibility assessment of logical books made of one or more PDFs.
  Assess how to support: one PDF holding a whole book; one PDF holding one chapter; one PDF
  holding several chapters; several PDFs of one logical book; chapter gaps, differing page
  numbering and ordered partial coverage.
- **现在的交付物只有评估 / The deliverable now is the assessment only:**
  [DEVELOPMENT_SPEC.md 第 9.4 节](DEVELOPMENT_SPEC.md#94-文档结构评估--document-structure-an-assessment-建议-proposed-g1)
  （现状、缺口、与 UUID、章节笔记、目录和锚点共存的原则）。**不做推测性的数据模型，不写代码。**（the current state, the gaps,
  principles for coexisting with UUIDs, chapter notes, the catalog and anchors). **No speculative
  data model, no code.**
- **依赖与顺序 Dependencies and order:** **设计评估要在 M6/M7 确定来源锚点的假设之前完成**（用户 2026-11-10 的决定），以便锚点
  格式不排除由多个 PDF 组成的书；它不改变现在的文档 UUID 模型。任务 6 的 `chapters.json` 设计也要考虑它（不排除成员章号）。具体的数据
  模型和实现需要 U1 对 H7 的证据、单独的设计评审和批准。不改变任务 4–8 的顺序，M5b 仍是下一个。**The design assessment
  is done before M6/M7 commit to their source-anchor assumptions** (the user's decision,
  2026-11-10), so that the anchor format doesn't rule out books made of several PDFs; it doesn't
  change the document UUID model now. Task 6's `chapters.json` design takes it into account too
  (not ruling out members' chapter numbers). A concrete data model and implementation need U1's
  evidence on H7, their own design review and approval. It doesn't change the order of tasks
  4–8; M5b is still next.
- **数据 Data:** 原则：每个 PDF 的 UUID 仍然是被锚定的身份；分组（如果有）是可选的、由用户确认的附加记录；已有的引用和笔记从不改写或移动。
  Principles: each PDF's UUID stays the anchored identity; a grouping, if any, is an optional,
  user-confirmed extra record; existing references and notes are never rewritten or moved.
- **相关问题 Related:** L21（第 11 节 section 11）.

---

## 5. P2 — 统一检索与跨文档知识 / Unified retrieval and cross-document knowledge (v0.4) 📋

**在 v0.3 完成后开始。Starts when v0.3 is done.** 在 PDF、Markdown 笔记和标注中统一搜索；主题笔记和有来源支持的跨文档关系（核心任务
J4）。思维导图最多是以后的一个可选视图，从不是组织知识的前提，也从不强迫用户使用。Unified search across PDFs,
Markdown notes and annotations; topic notes and source-backed relations across documents (core
job J4). A mind map is at most a later optional view, never a prerequisite for organising
knowledge and never forced on users.

| 条目 Item | 内容 Content | 验收 Acceptance |
|---|---|---|
| v0.4-5 连接来源的主题 Topics that link sources | `notes/topics/<term>.json`：确认过的链接（文档 id、页、引用、锚点）、同义词、相关的笔记和标注；主题页；从选区和标注面板添加；只由用户确认。Confirmed links (document id, page, quote, anchor), synonyms, linked notes and annotations; a topic page; added from the selection bar and annotation panel; user confirmation only. | 一个主题汇集多个文档的来源，每一个都能回到原文。A topic gathers sources from several documents, each back to its passage. |
| v0.4-6 笔记和标注的组织 Notes and annotations organised | 全书库的标注视图；标注和主题共用的标签；相关笔记。A library-wide annotations view; tags shared by annotations and topics; related notes. | 按标签筛选标注和主题。Filter annotations and topics by tag. |
| v0.4-4 书库搜索页 Library search page | （阅读状态本身见 RS1。The reading status itself: RS1.）片段和高亮；按书名、作者、年份、类型、书架、阅读状态筛选；**笔记和标注也被索引**（统一搜索）；印刷页码；索引作为后台任务，有进度、可取消。Snippets and highlighting; filters (title, author, year, type, shelf, reading status); **notes and annotations indexed** (unified search); printed page labels; indexing as a background job with progress and cancel. | 一次搜索同时找到书页、笔记和标注。One search finds book pages, notes and annotations. |

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

**批准前的检验 / Check before approval** (2026-11-10): 来源 → 代码 → 结果的链接是否真的解决一个重要问题，先用现有的章节脚本和手工
链接检验（[DEVELOPMENT_SPEC.md 第 16.4 节](DEVELOPMENT_SPEC.md#164-来源--代码--结果是否值得做--is-source--code--result-worth-building)）。
与外部 IDE 集成，不内置 IDE。Whether source → code → result links really solve an important problem is
first tested with the existing chapter scripts and hand-made links (DEVELOPMENT_SPEC section
16.4). Integration with external IDEs, never an embedded IDE.

---

## 7. P4 — 主动学习与复习 / Active learning and review 📋

**在来源链接和知识组织可靠之后。After source links and knowledge organisation are reliable.** 不做完整的
Anki 替代品。是否值得做取决于用户验证（U1–U3）。Not a full Anki replacement. Whether it's worth doing
depends on user validation (U1–U3).

| 条目 Item | 内容 Content |
|---|---|
| v0.4-3 带语境的生词 Vocabulary with context（已有条目 existing） | 句子、释义、页码和来源链接（旧行原样读取）；可编辑；完形卡片；Anki TSV 导出；全书库的生词列表。Sentence, definition, page and source link (old rows read unchanged); editable; cloze cards; Anki TSV export; a library-wide list. |
| R1 笔记中的问答 Questions in notes（新 new） | 笔记中约定的问答格式（例如 `Q:` / `A:`），复习时带回到原文的链接。An agreed question/answer format in notes (e.g. `Q:` / `A:`), reviewed with a link back to the source. |
| R2 简单复习 Simple review（新 new） | 复用"复习生词"的 Leitner 盒子（`vocab_review.py`），进度单独保存。Reuses Review words' Leitner boxes (`vocab_review.py`), progress kept separately. |
| R3 Anki 兼容导出 Anki-compatible export（新 new） | 问答和生词导出为 Anki 可以导入的文本，带来源链接。Questions and vocabulary exported as text Anki can import, with source links. |

---

## 8. P5 — 可选的高级功能 / Optional advanced features (v0.4, v0.5) ⏸

全部可选、默认关闭；阅读、笔记、生词从不依赖它们。AI、高级可视化和广泛的集成取决于用户验证（U1–U3）。All optional
and off by default; reading, notes and vocabulary never depend on them. AI, advanced
visualisation and broad integrations depend on user validation (U1–U3).

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

### X1 — macOS 可行性与验证 / macOS feasibility and validation 📋 方向已批准 direction approved 2026-11-10 ⏸ 在 v0.3 稳定之后 after v0.3 stabilises

不授权任何移植或跨平台实现。No porting or cross-platform implementation is authorised.

- **目标 Objective:** 在核心工作流可靠之后，用有边界的工作弄清楚 myLibrary 在 macOS 上缺什么。**不承诺 macOS 支持，现在不开始移植。**
  Once the core workflow is reliable, find out with bounded work what myLibrary lacks on macOS.
  **No promise of macOS support, and no porting now.**
- **交付物 Deliverables:** 在 macOS CI 运行器上运行 `uv run pytest` 并记录失败；检查已知的平台相关代码：`libraries.py` 的书库锁
  （Windows 用 `msvcrt`，其他系统用 `fcntl`，后者从未测试）、`platform_services`（下面的准备工作）、只适用于 Windows 的
  `make_shortcut.py` 和安装包、只用 Edge 的浏览器测试；有 Mac 时做一次手工冒烟测试；一份书面报告，发现的问题写进第 11 节。Run
  `uv run pytest` on a macOS CI runner and record the failures; review the known platform-specific
  code: `libraries.py`'s library lock (`msvcrt` on Windows, `fcntl` elsewhere, the latter never
  tested), `platform_services` (the groundwork below), the Windows-only `make_shortcut.py` and
  package, the Edge-only browser tests; a manual smoke test when a Mac is available; a written
  report, with the issues found added to section 11.
- **已做的准备（2026-11-10，`b592a85`）/ Groundwork done (2026-11-10, `b592a85`):** X1 本身**没有完成**。
  `scripts/platform_services.py` 集中了与操作系统有关的三件事，Windows 的行为与以前相同：X1 itself is **not done**.
  `scripts/platform_services.py` gathers three OS-dependent things, with Windows behaving as before:
  - 用设置中的编辑器打开文件：macOS 用 `open`，`.py` 和 "Notepad" 用 `open -t`（默认文本编辑器，从不运行）；macOS 上的自定义命令拆成参数，
    路径是一个参数，不经过 shell。Opening a file with the chosen editor: `open` on macOS, `open -t`
    (the default text editor, never run) for a `.py` and for "Notepad"; a custom command on macOS
    split into arguments, the path one argument, no shell.
  - 文件夹对话框：macOS 用 `osascript` 的 "choose folder"（提示作为参数传入）；结果是 chosen / cancelled / unsupported / error，
    `/api/pick-folder` 对后两种返回错误。书库页面的三个"选择…"按钮（📚 书库对话框和 ⚙ 设置）都用同一个 `askFolder`：取消时不提示，
    不可用或失败时用已有的提示说明；字段保持原样，不保存、不添加、不切换书库（浏览器测试 `test_folder_picker.py`）。The folder
    dialog: `osascript` "choose folder" on macOS (the prompt passed as an argument); results chosen
    / cancelled / unsupported / error, and `/api/pick-folder` answers the last two with an error.
    The library page's three "Choose…" buttons (📚 Libraries dialog and ⚙ Settings) share one
    `askFolder`: silent on a cancel, the existing toast when unavailable or failing; the field
    keeps its value and nothing is saved, added or switched (browser test
    `test_folder_picker.py`).
  - 用户数据文件夹 `user_data_dir()`：Windows `%APPDATA%/myLibrary`（不变）；将来的 macOS 安装包
    `~/Library/Application Support/myLibrary`。现有的设置都不迁移。The user-data folder: Windows
    `%APPDATA%/myLibrary` (unchanged); a future macOS package `~/Library/Application
    Support/myLibrary`. No existing settings are moved.
  - **只用模拟测试 / Tested with mocks only** (`tests/test_platform_services.py`): 所有 macOS 分支（`open`、`open -t`、
    `osascript`、取消码 -128、Application Support）从没有在 Mac 上运行过。Every macOS branch (`open`, `open -t`,
    `osascript`, the -128 cancel code, Application Support) has never run on a Mac.
  - **仍只适用于 Windows / Still Windows-only:** `make_shortcut.py`、`build_package.py` 和 `package/launch.py`
    （它自己计算 `%APPDATA%/myLibrary`，与 `user_data_dir()` 目前一致，L22）、Edge 浏览器测试、`libraries.start_server` 的分离进程标志。
    `make_shortcut.py`, `build_package.py` and `package/launch.py` (it computes
    `%APPDATA%/myLibrary` itself, which agrees with `user_data_dir()` today, L22), the Edge
    browser tests, `libraries.start_server`'s detached-process flags.
- **不做 Not:** 移植、macOS 安装包、签名或公证、文档中的支持声明。Porting, a macOS package, signing or
  notarisation, any claim of support in the docs.
- **验收 Acceptance:** 报告完成，用户根据它决定是否开始移植。The report is done, and the user decides from it
  whether porting starts.
- **顺序 Order:** v0.3 完成之后；如果 U1 显示首要用户中很多人用 macOS（H8），可以由用户决定提前。After v0.3; the user
  may move it earlier if U1 shows that many primary users are on macOS (H8).

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

**M5d/M5e 新限制（2026-11-12）/ New limits:** L28 and L29 apply to M5d/M5e (committed in `4e4abce`).

| ID | 问题 Issue | 计划在 Planned in |
|---|---|---|
| L28 | M5d/M5e（`notes_store.py`、`formula_ocr.py`）：图片的原子创建需要硬链接支持（如 NTFS）；主题笔记不支持图片上传；撤销、失败或丢失响应后，已保存图片保留，不自动清理。公式可能识别错误；最多三个候选，不是校准置信度；30 秒限制在 ONNX 调用之间检查，不能中断单次原生调用或载入。安装包/CI 未验证。Atomic image creation requires hard-link support (e.g. NTFS); no image uploads to topic notes; retained images are not garbage-collected after Undo, failures or lost responses. Recognition may be wrong; at most three hypotheses, not calibrated confidence; the cooperative 30 s timeout cannot interrupt loading or a native ONNX call. Package/CI unverified. Full record: [M5_VERIFICATION.md](docs/M5_VERIFICATION.md). 另外（2026-11-12 审查后）：关闭 ∑ 对话框不会停止已在服务器上进行的识别：它继续运行（最多约 30 秒，单次原生调用或载入可能更久），期间新的识别请求最多等待 20 秒，然后提示"忙"；真正取消需要改动原生运行时，暂不做。☁ 自动 Git 备份暂停（L29）；笔记和图片的完整备份是 💾 文件夹备份。模型安装被中断后，下次安装、状态查询或识别时会把旁边完整的副本（按固定 SHA-256 校验）放回，无需重新下载。模型位置：开发版在工具的 `.cache/formula-ocr/`，安装包在 `%APPDATA%\myLibrary\formula-ocr\`（工具缓存，不在书库中，更新或重装安装包不会删除）。Also (after the 2026-11-12 review): closing the ∑ dialog doesn't stop a recognition already running on the server: it goes on (up to about 30 s; a single native call or the model load can take longer), and a new request meanwhile waits up to 20 s and then says "busy"; true cancellation would need native-runtime changes and isn't done. ☁ Automatic Git backup is paused (L29); the complete backup of notes and images is the 💾 folder backup. After a cut-off model install, the next install, status check or recognition puts a whole copy left beside the model (checked against the pinned SHA-256) back in place, with no new download. Model location: `.cache/formula-ocr/` in the tool's folder in development; `%APPDATA%\myLibrary\formula-ocr\` in the package (a tool cache, not in the library; package updates and reinstalls leave it). | — |
| **L29** | **☁ 自动 Git 备份暂停（2026-11-12，用户决定）**：第三次独立审查（Codex）在自动 Git 备份中仍发现五个高严重度问题（发布、暂存区和恢复事务），逐条列在本表下方的“L29 暂缓的安全问题”中。本版本中 `backup.DEFERRED` 使 ☁ Back up 不提交、不推送、不改动暂存区、分支或任何引用，也不重放或删除遗留的恢复记录（只报告）；按钮仍显示为"☁ Back up (paused)"并说明原因；💾 文件夹备份照常（含笔记图片），没有选备份文件夹时也会显示；用户自己的 Git 操作不受影响。这些问题**没有修复**，留给单独的安全重新设计；现有实现和测试保留（`tests/test_backup.py` 以 DEFERRED 关闭运行）。**Automatic Git backup deferred (2026-11-12, owner decision):** the third independent review (Codex) still found five High-severity publication, index and recovery-transaction issues in it, listed one by one below the table ("L29 — deferred security findings"). In this release `backup.DEFERRED` makes ☁ Back up commit nothing, push nothing, leave the index, branches and every ref alone, and never replay or delete a leftover recovery record (it is only reported); the button stays visible as "☁ Back up (paused)" and says why; the 💾 folder backup works as before (note images included) and is shown even with no backup folder chosen; the user's own git use is unaffected. The issues are **not fixed**: they await a separate security redesign; the implementation and its tests are kept (`tests/test_backup.py` runs it with DEFERRED off). | 安全重新设计 Security redesign (to be planned) |
| **L30** | **安装包发行前的许可问题（2026-11-13）**：已补齐 FlatBuffers 许可证、markdown-it 浏览器版内含库的许可证、Python 内置软件的声明和完整的第三方清单（THIRD_PARTY_NOTICES.md）；安装包已不含 OpenCV 未使用的 FFmpeg 插件（LGPL）和 ReportLab 没有许可文本的 Type 1 字体及测试字体（用户决定，2026-11-13；扫描 OCR 文字层在 Arial 和 Helvetica 下都已验证）。仍未解决：（1）GEOS 3.14.1（LGPL-2.1，Shapely 必需）：对应源代码和构建材料已准备为 GitHub Release 资产但**尚未发布**；对应关系基于公开的构建脚本、delvewheel 记录、wheel 和 GEOS 发布的哈希，未重新构建核对，构建日志未查看；在发布这些资产并接受这些证据之前，**安装包不得公开分发**；myLibrary 自身许可是否满足 LGPL-2.1 第 6 节需要**法律审查**；（2）公式模型训练数据的权利未经审计。**Licence questions before distributing the package (2026-11-13):** the FlatBuffers licence, the licences of the libraries inlined in markdown-it's browser build, the notices for software incorporated in Python and a complete inventory (THIRD_PARTY_NOTICES.md) are in place; the package no longer contains OpenCV's unused FFmpeg plugin (LGPL) or ReportLab's unlicensed Type 1 fonts and test font (owner decision, 2026-11-13; the scan-OCR text layer verified with Arial and with the Helvetica fallback). Unresolved: (1) GEOS 3.14.1 (LGPL-2.1, needed by Shapely): its corresponding source and build materials are prepared as GitHub Release assets but **not published**; the correspondence rests on the published build scripts, the delvewheel record, the wheel's and GEOS's release hashes, not on a rebuild, and the build logs weren't inspected; until those assets are published and that evidence is accepted, **the package must not be distributed publicly**; whether myLibrary's own terms meet LGPL-2.1 section 6 needs **legal review**; (2) the formula model's training-data rights are unaudited. Details: THIRD_PARTY_NOTICES.md sections 5–6, package/licenses/GEOS-LGPL-NOTICE.txt, docs/M5_VERIFICATION.md. | 发行前 Before a package release |
| **L31** | **M6 引用到笔记的限制（2026-11-13）**：(1) 引用插入失败、被提供为“插入引用”但未插入，或之后从笔记中删除时，私有的引用记录留下（无害，不显示）；(2) 引用文件损坏而 `.bak` 可读时，按 `safe_io` 的规则从 `.bak` 继续（损坏的副本保留，服务器日志说明），`.bak` 之后记录的引用会丢失，笔记中的链接仍带 `page` 和 `q`；(3) 跨页的选区被拒绝；(4) 规范化逐个码点做 NFKC，行末的连字符在两个字母之间总是相连（“well-\nknown” 变成 “wellknown”），引用和查找时规则相同；(5) 选区内的公式按 PDF.js 提取的文字记录；(6) 暂停的 ☁ Git 备份（L29）重新设计时必须排除 `.myLibrary/`（书库自己的仓库不一定忽略它）；(7) 💾 备份读取 `.myLibrary/` 时不加锁（与其他用户数据相同）；(8) 引用存储的检查与写入之间，能写书库的进程仍可能换入一个目录联接（毫秒级）；写入后的检查只在联接届时仍在时发现它，不能撤销已经写到外面的内容，也发现不了换入后又换回的情况（`references._checked`；Codex 在现有威胁模型下接受）。(9) 点击引用链接使阅读器重新载入后（M6 的链接总是载入 `/read/<id>`），笔记的撤销/重做历史丢失（已保存的文字和恢复草稿保留）；M6 接受（2026-11-16），同一文档内导航时保留编辑会话留给 M7。**M6 quote limits (2026-11-13):** (1) a reference whose quote wasn't inserted (a failure, an "Insert the quote" offer not taken) or was later deleted from the note stays as a private record (harmless, never shown); (2) a damaged references file with a readable `.bak` continues from the `.bak` (`safe_io`'s rule: the damaged copy is kept and the server's log says so), so references recorded after that `.bak` are lost; their links in notes still carry `page` and `q`; (3) a selection across pages is refused; (4) normalising applies NFKC one code point at a time, and a line-end hyphen between letters is always joined ("well-\nknown" becomes "wellknown"), the same when quoting and when finding; (5) formulas in a selection are recorded as PDF.js extracts them; (6) the paused ☁ Git backup (L29) must exclude `.myLibrary/` when it is redesigned (a library's own repository may not ignore it); (7) 💾 Back up reads `.myLibrary/` without its locks (as for other user data); (8) between the references store's check and its write, a process that can write to the library could still swap in a junction (milliseconds); the check after the write detects such a redirect only if it is still present when checked: it can't undo a write that already escaped, nor guarantee to detect a swap that was put back in time (`references._checked`; accepted by Codex under the current threat model). (9) after following a reference link that reloads the reader (M6's links always load `/read/<id>`), the note's Undo/Redo history is gone (the saved text and recovery drafts are kept); accepted for M6 (2026-11-16), keeping the editing session during same-document navigation is for M7. **M7 (feature commit `4a69511`; CI-verified at `f18faa0`, run 44282194019):** a reference to the same document now moves the reader in place, so the note's Undo/Redo is kept (`tests/browser/test_reference_nav.py`); a link opened in another tab (another document, VS Code) still starts a new page. | M7/M8; L29 |
| **L32** | **M7 回到原文的限制（2026-11-17）/ M7 limits:** (1) 找原文依赖 PDF.js 的文字提取；PDF.js 升级后改为在文档中查找而不是精确定位。Finding depends on PDF.js's text extraction; after a PDF.js upgrade it searches the document instead of landing exactly. (2) 选页和查找用了 PDF.js 的内部函数 `pdfViewer._getVisiblePages`（与已有的 `_scrollMatches` 一样，升级时要重新检查；测试会发现）。Page choice uses PDF.js's internal `pdfViewer._getVisiblePages` (like the existing `_scrollMatches`: recheck on upgrade; tests fail if it changes). 若它缺失或形式改变，不记录位置（而不是猜测），引用导航照常。If it is missing or changes form, no position is decided (never guessed) and following references still works (`test_reference_nav.py`). (3) 文档查找最多 3000 页、30 秒；之后只给出已找到的地方或页面。The document search stops at 3000 pages or 30 s; then only what was found, or the page. (4) ↩ 返回的记录只在这个标签页中，重新载入后消失；从外部打开的预览没有返回记录。The Back stack lives only in this tab and is lost on reload; a preview opened from outside has no Back entry. (5) 扫描页没有文字层时只能到页面。A scanned page without a text layer resolves to the page only. (6) 标签页还不知道合并的 id 时，旧 id 的链接在新的预览标签页中打开。A merged id clicked before the tab knows its merged ids opens a preview tab. (7) 窗口大小或不是你做的缩放与阅读移动同时发生时，这次不记录位置（下一次记录）。A reading move during an unexplained layout change (a resize, a zoom you didn't make) decides no position; the next one does. (8) 两个标签页读同一文档时，一个标签页可能丢掉一次位置决定（另一个刚写过）；下一次翻页会写入。Two tabs on one document: a tab can lose one decided position when the other just wrote; its next page turn is written. (9) 位置的顺序只在服务器内存中；重启后旧页面因令牌改变而被拒绝。Position ordering lives in the server's memory; after a restart old pages are refused by their token. (10) 中键点击用浏览器自己的行为（打开安全的预览链接）。A middle-click uses the browser's own behaviour (the safe preview link). (11) 快照不等待缩放完成：PDF.js 4.10 同步设置缩放（计划 §4.1 的等待因此不需要）。The snapshot doesn't wait for a zoom to finish: PDF.js 4.10 applies the scale synchronously (so plan §4.1's wait isn't needed). | M8 |
| B36 (S, test) | 间歇失败（2026-11-16，完整的分片 2/2 中 1 次，单独 5 次全部通过；未修复）：`test_notes_editing.py` `test_editing_in_preview_mode_records_no_reading`：笔记里打的字不在文件里。可能的原因（与失败相符，未证实）：带 `&find=` 打开时，`lookup.js` `showFound` 在 `pagesinit` 后约 100 ms 调用 PDF.js 的 `findBar.open()`，它把焦点移到查找框；测试若已先点进笔记，字就打进了查找框（笔记不变、“已保存”、离开不提醒）。这也是一个小的使用问题：查找栏会抢走正在笔记里打字的焦点。Intermittent (2026-11-16: 1 failure in a full shard 2/2 run, 5 of 5 passes alone; not fixed): the words typed into the note aren't in the file. Likely cause (matches the failure, not proven): opened with `&find=`, `lookup.js` `showFound` calls PDF.js's `findBar.open()` about 100 ms after `pagesinit`, which moves the focus to the find field; a test that already clicked into the note types into the find field (the note unchanged, "clean", no warning on leaving). It is also a small usability issue: the find bar takes the focus from someone typing in the note. | M7.1 S7 |
| B37 (S, test) | 间歇失败（2026-11-16，完整的笔记面板关闭组中 1 次，单独 5 次全部通过；未修复）：`test_saving.py` `test_while_a_save_is_on_its_way_closing_warns_and_later_changes_follow` 在测试自己用 pypdf 读 PDF 时得到 `PermissionError`（`helpers.highlighted_lines`，在 `poll` 中）。原因（来自 traceback）：服务器保存标注时原子地替换 PDF，Windows 上替换进行的瞬间打开文件会被拒绝；`poll` 不把这种暂时的读取错误当作“还没好”。应用的保存没有问题；修正在测试一侧。Intermittent (2026-11-16: 1 failure in a full notes-closed run, 5 of 5 passes alone; not fixed): the test's own pypdf read of the PDF raised `PermissionError` (`helpers.highlighted_lines`, inside `poll`). Cause (from the traceback): the server replaces the PDF atomically when saving marks, and on Windows opening the file at that instant is refused; `poll` doesn't treat that transient read error as "not yet". The app's save is not at fault; the fix belongs in the test. | M7.1 S7 |
| B38 (S, test) | 间歇失败（2026-11-17，M7 最终完整运行中 1 次；单独 6 次中 1 次；未修复，M7 没有改动这条路径。2026-11-19 M7.1 S1b 的一次完整运行中又出现 1 次，这次在同一测试第一步：错误的令牌，服务器在读取请求体之前以 403 回答；同一机制，S1b 没有改动这条路径 / again once in a full run during M7.1 S1b on 2026-11-19, this time at the same test's first step: a wrong token, answered 403 before the body is read; the same mechanism, a path S1b doesn't touch；2026-11-23 M7.1 S2 第四轮的一次定向运行中又出现 1 次（发送超大请求体那一步，`ConnectionAbortedError [WinError 10053]` 而不是 413；同一树上随后的完整运行通过；S2 没有改动这条路径 / again once in a targeted run during M7.1 S2 round 4 on 2026-11-23, at the oversized-body step, `ConnectionAbortedError [WinError 10053]` instead of 413; the full run on the same tree afterwards passed; S2 doesn't touch this path; evidence `.cache/m7.1-evidence/s2/round4/backup-tests.log`）：`tests/test_references.py` `test_the_endpoint_needs_the_key_and_a_small_body` 发送超大的请求体时，客户端偶尔得到 `ConnectionAbortedError [WinError 10053]` 而不是 413。可能的原因：服务器（`library_server.py` `do_POST`）在读取请求体之前就以 413 回答并关闭连接；Windows 在关闭还有未读数据的套接字时重置连接，客户端还在发送时就失败。修正应在测试一侧（接受连接被重置）或服务器先读完/丢弃有限的请求体。Intermittent (2026-11-17: once in M7's final full run, once in 6 runs alone; not fixed; M7 doesn't touch this path): sending an oversized body, the client sometimes gets `ConnectionAbortedError [WinError 10053]` instead of 413. Likely cause: the server (`library_server.py` `do_POST`) answers 413 and closes before reading the body; Windows resets a socket closed with unread data, so the client fails while still sending. The fix belongs in the test (accept a reset) or the server (drain a bounded body first). | M7.1 S7 |
| B39 (S, test + C, product) | 已确认两个原因并修复，Codex 独立审查通过（无阻塞问题）；已提交、推送并通过 CI：`3b901d6`，运行 44722195750 第 1 次尝试，五个作业全部通过。出现两次：CI 运行 44521803189 第 1 次尝试（S1b，浏览器分片 1，Edge 156.0.4314.58，`test_a_draft_already_in_the_chosen_note_is_dealt_with`）和 CI 运行 44703480992 第 1 次尝试（S1c，浏览器分片 1，Edge 157.0.4341.60，`test_discarding_a_stale_row_keeps_a_newer_draft`）：都在 `tests/browser/test_notes_retired.py` 共用的准备步骤 `merged_while_editing` 中点击 `#mlRetry` 时超时。**原因 1（测试同步）：** 第二次运行的 Playwright 跟踪（CI 工件）给出顺序：保存第一次被中止后 2.0 秒，面板自己的第一次自动重试开始；当时测试线程正阻塞在 `server.post("/api/refresh")` 中（CI 上约 5.7 秒），同步的路由处理器无法运行，请求一直挂起；`unroute` 把它放给已经合并完的服务器，得到真实的 410（随后出现“Route is already handled!”），重试按钮随之消失，点击一直等不到。本地把刷新放慢 3 秒即可原样复现。**原因 2（产品缺陷）：** 410（以及服务器重启后的 403）之后，面板仍每 5 秒检查磁盘；被合并文档的 id 在读取时被跟随到保留的文档，所以几秒后这个标签页把保留文档的章节笔记当作冲突显示，410 的说明和按钮（打开保留的文档、另存为文件）消失。没有数据丢失（写入仍被拒绝，文字留在编辑器和草稿里），但会误导，也是测试失败的第二个来源。**修复：** `note_session.js` 的 `reloadNeeded`：需要重新载入后不再检查磁盘，已在路上的检查的回答也不再应用；`merged_while_editing` 从页面内发起刷新（Playwright 等待时继续处理路由）、在放行之前先监听回答、继续被扣住的请求、用 `unroute_all(behavior="ignoreErrors")` 放行、只在按钮存在时在页面内一步点击重试，并断言服务器真的回答了 410（自动或手动重试都可以）；没有加长超时、没有睡眠。**验证：** 新测试：按 CI 的顺序（自动重试被扣到合并之后）；410 之后 30 秒内没有任何磁盘检查（Playwright 时钟），在保留的文档中照常检查；一个在 410 之前开始、之后才得到回答的检查不改变状态。修复前：旧的 `note_session.js` 上两个产品测试失败（仍在检查；状态变成 conflict），旧的准备步骤按 CI 的顺序失败（点击 `#mlRetry` 超时，与 CI 相同）；修复后全部通过，`test_notes_retired.py` 13 个测试连续 10 次通过。证据：`.cache/m7.1-evidence/b39/`（CI 工件：跟踪、服务器日志、控制台、截图；本地复现；修复前后的运行；本地，不在 git 中）。Both causes confirmed and fixed; approved by Codex's independent review (no blocking findings); **committed, pushed and CI-verified: `3b901d6`, run 44722195750, attempt 1, all five jobs passed.** Seen twice: CI run 44521803189 attempt 1 (S1b, browser shard 1, Edge 156.0.4314.58, `test_a_draft_already_in_the_chosen_note_is_dealt_with`) and CI run 44703480992 attempt 1 (S1c, browser shard 1, Edge 157.0.4341.60, `test_discarding_a_stale_row_keeps_a_newer_draft`): both timed out clicking `#mlRetry` in the shared setup `merged_while_editing` of `tests/browser/test_notes_retired.py`. **Cause 1 (test synchronisation):** the second run's Playwright trace (a CI artifact) gives the order: 2.0 s after the first save was aborted, the panel's own first automatic retry started; the test thread was then blocked in `server.post("/api/refresh")` (about 5.7 s on CI), so the synchronous route handler couldn't run and the request stayed pending; `unroute` released it to the server, already merged, which answered the real 410 (then "Route is already handled!"); the Retry button went with it and the click waited in vain. A 3 s slower Refresh reproduces it locally as it was. **Cause 2 (product defect):** after a 410 (and after the 403 of a restarted server) the panel still checked the disk every 5 s; a merged document's id is followed to the kept document for reading, so a few seconds later the tab showed the kept document's chapter note as a conflict, and the 410 message and its actions (Open the document that stays, Save as a file) were gone. No data was lost (writes still refused, the text in the editor and its draft), but it misled, and was a second source of test failures. **Fix:** `note_session.js` `reloadNeeded`: once a reload is needed the disk is never checked again, and the answer of a check already on its way no longer applies; `merged_while_editing` asks for the Refresh from within the page (Playwright goes on handling routes while it waits), listens for answers before releasing anything, continues held requests, releases routes with `unroute_all(behavior="ignoreErrors")`, presses Retry in the page in one step only if the button is there, and asserts that the server really answered 410 (by the automatic or the manual retry); no longer timeouts, no sleeps. **Verification:** new tests: the CI order (the automatic retry held until after the merge); no disk check in 30 s after the 410 (Playwright's clock), and the usual checks in the document that stays; a check started before the 410 and answered after it changes nothing. Before the fix: on the old `note_session.js` both product tests fail (still checking; the state becomes conflict), and the old setup fails in the CI order (clicking `#mlRetry` times out, as in CI); after it all pass, and `test_notes_retired.py`'s 13 tests passed 10 runs in a row. Evidence: `.cache/m7.1-evidence/b39/` (the CI artifact: trace, server log, console, screenshot; the local reproduction; runs before and after the fix; local, not in git). | ✅ `3b901d6`，CI 运行 run 44722195750 第 1 次尝试 attempt 1 |
| B40 (S, test) | 间歇失败（2026-11-19，CI 运行 44521803189 第 1 次尝试，浏览器分片 3，Edge 157.0.4341.60；同一提交的第 2 次尝试和本地运行都通过；原因未知）：`tests/browser/test_quotes.py` `test_the_same_words_twice_on_a_page_anchor_the_one_selected`（同一页上相同的文字出现两次）在 Alt+Q 之后等待引用状态时超时（15 秒）。注意：两个失败的分片运行在不同版本的 Edge 上。证据：`.cache/m7.1-evidence/s1b/ci-44521803189/shard3-failed.log`（本地，不在 git 中）。M8 之前必须调查（S7）。Intermittent (2026-11-19, CI run 44521803189 attempt 1, browser shard 3, Edge 157.0.4341.60; attempt 2 of the same commit and local runs passed; cause unknown): `test_the_same_words_twice_on_a_page_anchor_the_one_selected` (the same words twice on a page) timed out (15 s) waiting for the quote state after Alt+Q. Note: the two failed shards ran on different Edge versions. Evidence: `.cache/m7.1-evidence/s1b/ci-44521803189/shard3-failed.log` (local, not in git). Mandatory investigation before M8 (S7). | 📋 S7 |
| B41 (C, product) | **已在 M7.1 S2 中修复（第二轮；第三轮改为所有读写都用扩展长度形式），经 Codex 第四次审查批准，随 S2 提交并推送（`e28bf18`），CI 运行 45155217482 第 1 次尝试五个作业全部通过。详见第 11 节 FA-04/FA-05 条目。Fixed in M7.1 S2 (round 2; in round 3 every read and write goes through the extended-length form), approved by Codex's fourth review, committed and pushed with S2 (`e28bf18`), CI run 45155217482, attempt 1, all five jobs passed. Details: section 11, the FA-04/FA-05 entry.** 💾 备份曾漏掉路径超过 260 个字符的文件（2026-11-20，M7.1 S2 中发现，所有者排入 S2）：`folder_backup.your_files` 曾用普通的 `rglob` 和 `is_file` 列出文件；在没有开启长路径的 Windows 上，完整路径超过 260 个字符的笔记被当作不存在，**不进 zip，也没有任何提示**（复现：352 个字符的笔记路径）。💾 Back up used to leave out files whose path is longer than 260 characters (2026-11-20, found during M7.1 S2, scheduled into S2 by the owner): `folder_backup.your_files` listed files with plain `rglob` and `is_file`; on Windows without long paths enabled, a note whose full path exceeded 260 characters counted as absent and was **left out of the zip without any message** (reproduced with a 352-character note path). | ✅ `e28bf18`，CI 运行 run 45155217482 第 1 次尝试 attempt 1 |
| B42 (C, product, Low) | 自动备份在检查书库和备份文件夹自身的路径之前先调用 `libraries.is_test_library()`（`folder_backup.auto_backup`）（2026-11-23，Codex 对 M7.1 S2 的第四次审查，非阻塞）。已确认的情形（合成数据）：`lib` 的 `test_library = true`，另一个不同的文件夹 `lib.` 为 false；Windows 的普通路径形式把 `lib.` 当作 `lib`，于是 `auto_backup(lib.)` 读到旁边书库的标记，**静默跳过**，而不是报告不安全的路径。没有备份被覆盖、改动或删除（`back_up` 和自动备份的其余步骤都先检查路径）。修复：在 `auto_backup` 中先检查路径（`_check_own_path`），再判断测试书库；保留对真正的测试书库的跳过；需要修复前失败的测试。S2 中没有修复（所有者决定）。Automatic backup calls `libraries.is_test_library()` before checking the library's and the backup folder's own paths (`folder_backup.auto_backup`) (2026-11-23, Codex's fourth review of M7.1 S2, non-blocking). Confirmed (synthetic data): `lib` has `test_library = true`, a distinct folder `lib.` has false; the ordinary Windows path form takes `lib.` for `lib`, so `auto_backup(lib.)` reads the neighbouring library's flag and **skips silently** instead of reporting the unsafe path. No backup is overwritten, modified or pruned (`back_up` and the rest of the automatic backup check the paths first). Fix: check the paths (`_check_own_path`) in `auto_backup` before deciding the test library; keep skipping the real Test & Demo library; with a fail-before test. Not fixed in S2 (owner decision). | 📋 M7.1 S6 |
| FA-06 (C, product, Medium) | ⚙ 并发的设置保存会丢失另一个已确认的改动（Codex M7 后审计，2026-11-18）：`paths.save_settings` 不加锁地读取、合并（`_saved() \| updates`）、整文件写入；同时运行的多个书库服务器共用同一个设置文件，所以只用进程内的锁不够；页面（`library_page.py` `saveSettings`）还把打开对话框时的全部 7 个字段都发回去，过时的对话框会覆盖其他标签页或进程的改动。2026-11-23 在当前代码上用临时文件复现：两个线程分别保存 `backup_pdfs` 和 `editor`，都报告成功，只留下一个。Concurrent settings saves lose another acknowledged change (Codex post-M7 audit, 2026-11-18): `paths.save_settings` reads, merges (`_saved() \| updates`) and rewrites the whole file without a lock; several library servers share one settings file, so an in-process lock alone isn't enough; the page (`library_page.py` `saveSettings`) also sends back all 7 fields as they were when the dialog opened, so a stale dialog overwrites changes made in another tab or process. Reproduced on the current code with temporary files (2026-11-23): two threads saving `backup_pdfs` and `editor` both reported success; only one was kept. **已确认 Confirmed.** Codex 审查计划时另外复现（2026-11-23）Also reproduced by Codex during the plan review: `change_settings({"backup_pdfs": "false"})` 成功并存成布尔值 `True`（服务器先转换类型再验证）succeeds and stores Boolean `True` (the server coerces before validating); S3 改为先验证 S3 validates first. | ✅ M7.1 S3：已实现并本地验证，所有者批准本地提交；未推送，未通过 CI implemented and verified locally, local commit approved by the owner; not pushed, not CI-verified (2026-11-24) |
| B43 (C, product) | ⚙ 保存设置会损坏设置文件中不认识的非字符串值，并删除注释（2026-11-23，S3 调查中发现）：`paths._toml_value` 把布尔值以外的一切都用 `str()` 写成字符串，所以手工加入的 `zoom = 3`、`ratio = 1.5`、数组、日期和 `[window]` 表在下一次保存后变成 `'3'`、`'1.5'`、`"['a', 'b']"`、`'2026-11-23'`、`"{'width': 900}"`；每次保存（包括什么都没改的保存）都重新生成整个文件，用户的注释丢失。临时文件中复现。Saving settings corrupts unknown non-string values in the settings file and drops comments (2026-11-23, found during the S3 investigation): `paths._toml_value` writes everything but booleans through `str()`, so a hand-added `zoom = 3`, `ratio = 1.5`, an array, a date and a `[window]` table become `'3'`, `'1.5'`, `"['a', 'b']"`, `'2026-11-23'` and `"{'width': 900}"` on the next save; every save (an empty one too) regenerates the whole file and the user's comments are lost. Reproduced with temporary files. **已确认，所有者排入 S3 Confirmed, scheduled into S3 by the owner (2026-11-23).** | ✅ M7.1 S3：已实现并本地验证，所有者批准本地提交；未推送，未通过 CI implemented and verified locally, local commit approved by the owner; not pushed, not CI-verified (2026-11-24) |
| B44 (S, product, Low) | ⚙ 读取设置时不等待正在进行的替换（2026-11-23，S3 调查中从代码发现；已复现）：`paths._saved` 用普通的 `open()` 读取，而不是 `safe_io.read_bytes`（Windows 上替换文件的瞬间，另一个读取者可能得到“拒绝访问”，`safe_io` 为此重试）；设置在导入 `paths` 时（选择书库）和备份、OpenAlex、编辑器打开时都会读取，所以另一个进程保存设置的同时，这些读取可能偶尔失败。Reading settings doesn't wait out a replacement in progress (2026-11-23, found in the source during the S3 investigation; reproduced): `paths._saved` reads with a plain `open()`, not `safe_io.read_bytes` (on Windows a reader can get "access denied" at the moment a file is swapped in, which `safe_io` retries); settings are read when `paths` is imported (choosing the library) and by the backup, OpenAlex and editor opening, so these reads can occasionally fail while another process saves the settings. **已确认 Confirmed (2026-11-23)：** Codex 在 1,500 次真实的原子替换期间的 10,000 次并发读取中观察到 22 次 `PermissionError`；本地复现（临时文件，另一个进程写入）得到 7 次。Codex observed 22 `PermissionError`s in 10,000 concurrent reads during 1,500 real atomic replacements; a local reproduction (temporary files, a writer in another process) gave 7. 另外，`_saved` 先用 `Path.exists()` 检查，而它遇到任何 `OSError` 都返回 False，理论上会把读取失败当成“没有设置文件”。Also, `_saved` checks `Path.exists()` first, which returns False on any `OSError`, so a failed read could in principle be taken for "no settings file". 相关的观察（不是数据丢失）Related observation (no data loss)：读取者不停读取时，写入者的替换重试可能用完，保存显示错误，旧文件完好 with readers reading continuously, the writer's replacement retry can run out: the save shows an error, the old file stays intact. 所有者把 B44 排入 S3 Scheduled into S3 by the owner. **写入争用：已接受的限制（所有者决定 D3，2026-11-23）Writer contention: accepted limitation (owner decision D3, 2026-11-23)：** 在 Windows 上，持续的读取者或别的程序打开着设置文件时，保存可能失败；条件是旧文件逐字节不变、错误说明保存被阻止且可以重试、不重启也不切换书库、所有锁释放、临时文件清理、争用结束后重试能成功（S3 的确定性测试证明这些）。On Windows a save may fail while readers keep reading or another program holds the settings file open, provided that the old file stays byte-for-byte intact, the error says saving was blocked and can be retried, nothing restarts or switches library, all locks are released, the temporary file is removed and a retry succeeds once the contention ends (proven by S3's deterministic tests). | ✅ M7.1 S3：已实现并本地验证，所有者批准本地提交；未推送，未通过 CI implemented and verified locally, local commit approved by the owner; not pushed, not CI-verified (2026-11-24) |
| **L20** | **未解决 UNRESOLVED.** 2026-11-09 一次完整运行中有一个未识别的失败，之后没能复现。现在每次运行都写 `test-results/pytest-junit.xml`；下次失败时运行 `uv run pytest -rfE --tb=long` 并保留该文件。One unidentified failure in one full run (2026-11-09), not reproduced since. Every run now writes `test-results/pytest-junit.xml`; on the next failure run `uv run pytest -rfE --tb=long` and keep that file. | — |
| D18 (C, latent) | 重命名失败时可能丢失恢复日志（`add_book.rename_document`）。A failed rename can lose its recovery journal. **守卫（M7.1 S0）：** `tests/test_rename_guard.py` 在任何生产代码调用 `rename_document` 时失败；它**不修复** D18，只防止在 D18 修复之前出现新的调用者（UI、CLI、API、服务器接口、后台任务）。**Guard (M7.1 S0):** `tests/test_rename_guard.py`, a conservative static safeguard over the Python files under `scripts/` and `package/` only: it fails on any use of the name `rename_document` there other than its definition. It does **not** fix D18; it only keeps new callers (UI, CLI, API, server endpoint, background job) out until D18 is repaired and reviewed. False positives: any name, attribute or string spelled `rename_document`, even unrelated. Not seen: a computed name (`getattr(m, 'rename_' + 'document')`, `importlib`, `eval`/`exec`), code outside those folders, and callers in other languages. | Task 8; S8 before any rename caller |
| B2 (C) | ☁ 备份不支持非 ASCII 文件名。☁ Back up fails with non-ASCII file names. 暂缓的实现中已用 `git -z` 处理并有测试，但 Git 备份暂停期间不算修复（L29）。Handled with `git -z` and tested in the deferred implementation, but not fixed while Git backup is paused (L29). | L29 |
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
| B14 (C) | 若干小修复。Small fixes. 其中“`render()` 在插入书目数据之后才替换占位符”已由 M7.1 S1c（FA-02）修复（一次替换所有占位符）；其余未变。Of these, "`render()` replaces placeholders after inserting book data" is fixed by M7.1 S1c (FA-02: all markers replaced in one pass); the rest are unchanged. | Task 8 |
| B15 (S) | 阅读记录可能多算。The reading log may over-count. | v0.4-8 |
| B16 (S) | 尚未确认（见历史记录）。Not yet confirmed (see the history). | — |
| B17 (S) | pdfium 提取文字时可能发生本地崩溃。A native fault in pdfium during text extraction. | — |
| B21–B24 (C, audit) | OCR 中残留的按 slug 的键；没有完整超时的请求；服务器重启后 Ctrl+S 重试；相同文本之间的冲突。Slug-keyed leftovers in OCR; requests without a full timeout; Ctrl+S retries after a restart; a conflict between identical texts. | Task 8 |
| B27 (C, test only) | 浏览器测试夹具用普通 `read_text` 读取阅读记录。The browser fixture reads the reading log with a plain `read_text`. | Task 8 |
| L1 | 只有书、论文、学位论文三种类型。Only book, paper and thesis types. | Task 6 |
| L9 | 中文文档：第N章、中文章节名、中文在线目录。Chinese documents: 第N章 contents, Chinese chapter titles, a Chinese online catalogue. | v0.5-6 |
| L11 | 测试缺口：部分路由；书库页面的 JavaScript 中只有书库对话框和"选择…"文件夹按钮有浏览器测试。Test gaps: some routes; of the library page's JavaScript only the library dialog and the "Choose…" folder buttons have browser tests. | Task 8 |
| L12 | 强制关闭浏览器会丢失未保存的标注。Force-closing the browser loses unsaved marks. | — |
| L13 | 阅读时间最多可能少算一分钟。Reading time can lose up to a minute. | — |
| L14 | 笔记也可以在外部编辑器中打开（写 README 时由编辑器提示冲突）。Notes also open in an outside editor (the editor reports a newer README). | — |
| L16 | 浏览器中的状态不随书库迁移（草稿按书库隔离）。Browser state doesn't travel with a library (drafts are scoped per library). | — |
| L17 | 测试/示例书库只能在启动器中重置。The Test & Demo library resets only from the launcher. | — |
| L18 | 测试语料上的章节检测限制。Chapter detection limits on the test corpus. | Task 6 |
| L19 | 没有作者和年份的文档，名字中有两个连字符。A document without author or year gets a slug with two hyphens. | — |
| L22 | 安装包的启动器 `package/launch.py` 自己计算 `%APPDATA%/myLibrary`（日志），而不是用 `platform_services.user_data_dir()`；两者目前一致，但改其中一个时要同时改另一个。The package launcher computes `%APPDATA%/myLibrary` (its log) itself rather than through `platform_services.user_data_dir()`; they agree today, but changing one means changing the other. | 第 9 节 section 9 |
| L25 (S) | CI 的 Windows 运行器上偶尔出现 `net::ERR_NO_BUFFER_SPACE`（Windows WSAENOBUFS：无法为连接分配套接字），页面的某个请求失败，测试超时：2026-11-08 运行 42527186504（`test_search_results_stay_on_screen`，在 KaTeX 之前）和 2026-11-11 运行 43002486914（`test_readable_in_light_and_dark[dark]`，PDF.js 的 `viewer.mjs`）。没有发现泄漏（本地运行中已建立和 CLOSE_WAIT 的连接数不增长）；服务器用 HTTP/1.0，每个请求一个连接，留下 TIME_WAIT；KaTeX 使每次阅读页面多 2 个请求（显示公式时最多再加约 4 个字体）。第三次：2026-11-11 运行 43022257625（`test_without_any_move_the_match_is_centred`，`/reader/lookup.js`）。三次都在测试集的后半段（63%、74%、84%）。本地测量（2026-11-11）：动态端口 49152–65535（16384 个），TIME_WAIT 120 秒；16 个测试约 72 秒留下约 770 个 TIME_WAIT（约 48 个/测试），稳定时约 1300 个，远少于端口数，所以没有证明是端口耗尽；已建立和 CLOSE_WAIT 的连接、python/msedge 进程数都不增长。原因未确定，没有改动；浏览器测试分成几个运行器后每个运行器的负载减半（是否有帮助尚待观察）。Occasional `net::ERR_NO_BUFFER_SPACE` on CI's Windows runner (Windows WSAENOBUFS: no socket could be allocated for a connection): one of the page's requests fails and the test times out (fourth occurrence below, M7): run 42527186504 on 2026-11-08 (`test_search_results_stay_on_screen`, before KaTeX) and run 43002486914 on 2026-11-11 (`test_readable_in_light_and_dark[dark]`, PDF.js's `viewer.mjs`). No leak found (established and CLOSE_WAIT connections don't grow in local runs); the server speaks HTTP/1.0, one connection per request, leaving TIME_WAIT sockets; KaTeX adds 2 requests per reader page (up to about 4 more fonts when formulas show). A third: run 43022257625 on 2026-11-11 (`test_without_any_move_the_match_is_centred`, `/reader/lookup.js`). All three came in the second half of the suite (63%, 74%, 84%). Measured locally (2026-11-11): dynamic ports 49152–65535 (16,384), TIME_WAIT 120 s; 16 tests in about 72 s left about 770 TIME_WAIT sockets (about 48 per test), about 1,300 at steady state, far below the port count, so port exhaustion isn't shown; established and CLOSE_WAIT connections and python/msedge processes don't grow. Cause unresolved; nothing changed; splitting the browser tests across runners halves each runner's load (whether that helps is to be seen). 第四次：2026-11-12 运行 43206917253 第 1 次尝试（提交 `69c684a`，只改文档），浏览器分片 1（作业 131144297375）：`test_notes_maths.py::test_typed_maths_is_saved_as_typed` 的功能断言通过，但页面启动时 PDF.js 本地化文件 `/pdfjs/web/locale/en-US/viewer.ftl` 的请求以 `net::ERR_NO_BUFFER_SPACE` 失败，留下三个未捕获的 `TypeError: Failed to fetch`（fetchData → createBundle → generateBundles），测试在清理阶段失败；笔记的读取和保存都返回 200。经用户批准只重试这一个作业，第 2 次尝试（作业 131161806282）通过，整个运行成功。重试通过不说明原因；根本原因仍未知。A fourth: run 43206917253, attempt 1, on 2026-11-12 (commit `69c684a`, documentation only), browser shard 1 (job 131144297375): `test_notes_maths.py::test_typed_maths_is_saved_as_typed` passed its functional assertions, but during viewer startup the request for PDF.js's localisation file `/pdfjs/web/locale/en-US/viewer.ftl` failed with `net::ERR_NO_BUFFER_SPACE`, leaving three uncaught `TypeError: Failed to fetch` (fetchData → createBundle → generateBundles), so the test failed at teardown; the note's load and save both returned 200. With the user's approval only that job was retried: attempt 2 (job 131161806282) passed and the run succeeded. A passing retry explains nothing: the root cause remains unknown. 第五次：2026-11-13 运行 43414437518 第 1 次尝试（提交 `ee23329`，只改文档），浏览器分片 2：`test_notes_switching.py::test_a_failed_load_never_leaves_another_notes_text_editable` 在公共准备步骤（`open_chapter_one` → `notes_settled`，15 秒）超时，浏览器控制台有 `net::ERR_NO_BUFFER_SPACE`；根本原因仍未知，没有重跑。A fifth: run 43414437518, attempt 1, on 2026-11-13 (commit `ee23329`, documentation only), browser shard 2: `test_notes_switching.py::test_a_failed_load_never_leaves_another_notes_text_editable` timed out in its shared setup (`open_chapter_one` → `notes_settled`, 15 s) with `net::ERR_NO_BUFFER_SPACE` in the browser console; the root cause remains unknown; not rerun. **第四次（M7，2026-11-18）：** 运行 44277271746，浏览器分片 1，`test_notes_preview.py::test_keys_in_the_preview_stay_in_the_notes`：页面控制台显示 `net::ERR_NO_BUFFER_SPACE`，`note_session.js` 没有载入（`window.myLibraryNoteSession` 未定义），笔记没有打开，测试 15 秒后超时（JUnit、控制台、服务器日志、跟踪在本地 `.cache/m7-evidence/ci-44277271746-artifact/`，不进 git）。同一分片之后因 15 分钟的步骤限制在 91% 处停止（另一个问题：M7 加了测试，已改为三个分片、每个 20 分钟）。没有加重试、没有跳过、没有改应用代码；深入调查留给 S7。 **Fourth (M7, 2026-11-18):** run 44277271746, browser shard 1, `test_notes_preview.py::test_keys_in_the_preview_stay_in_the_notes`: the page console shows `net::ERR_NO_BUFFER_SPACE`, `note_session.js` didn't load (`window.myLibraryNoteSession` undefined), the note never opened and the test timed out after 15 s (JUnit, console, server log and trace kept locally in `.cache/m7-evidence/ci-44277271746-artifact/`, not in git). The same shard then stopped at 91% at its 15-minute step limit (a separate problem: M7 added tests; now three shards of 20 minutes each). No retries, no skips, no application change; deeper investigation is left to S7. | — |
| B32 | **已改进 IMPROVED**：`3dc9d2b`（保存状态、重试、离开提醒、中断后恢复）和 `eee608c`（版本检查），已推送，CI 通过（运行 43051704210）。`3dc9d2b` (save states, Retry, the leave warning, recovery after an interruption) and `eee608c` (the version check), pushed and CI-verified (run 43051704210), 2026-11-11。**原来的失败**：CI 运行 43022257625 中，`test_small_writes_sent_just_before_closing_arrive` 的章节勾选没有到达服务器；本地 5 次带记录的重复全部成功；CI 中的原因**仍未确定**（与 L25 的关系未证实）；没有证实是应用的数据丢失缺陷。**The original failure:** the chapter tick in `test_small_writes_sent_just_before_closing_arrive` didn't reach the server in CI run 43022257625; 5 logged local repetitions all succeeded; the cause in CI is **still unknown** (any link to L25 unproven); not shown to be an application data-loss defect. **保存 Saving** (`library_page.py`: `setTick`/`sendTick`/`replayTicks`/`applyMine`/`keepTheirs`)：服务器确认前标为"正在保存"；失败时保留、标红、可重试；离开页面先询问；同一章一次一个请求。A tick is "saving" until the server confirms it; kept, marked and retryable when it fails; leaving asks first; one request per chapter at a time. **版本检查 Version check** (`library_server.tick_with_version`, `check_base`, `TICK_START`)：服务器在内存中记录每个文档的勾选版本和每章最后一次写入的版本（在 README 的锁内修改，从服务器进程启动时的毫秒数开始）；页面随页面数据、刷新和每个回答得到版本（总是和对应的章节状态一起取得，从不比它们新），每次点击带上 `base`；该章在 `base` 之后被写过、而请求的状态又不同时拒绝（409，附当前章节和版本）；已经是请求的状态时成功且不写入（丢失回答后的重试安全）；不同章节不冲突。冲突时页面保留并显示用户的点击，持续提示，提供 **Apply mine**（用最新版本再发送，必须由用户点击）和 **OK**（保留 README 的状态）；从不自动重试。The server keeps, in memory, each document's tick version and each chapter's last-write version (changed under the README's lock, starting at the server process's start time in ms); the page gets versions with its data, refreshes and every answer (always together with the chapter states they belong to, never newer), and every click carries `base`; a click whose chapter was written after `base` and differs is refused (409, with the current chapters and version); already in the requested state succeeds without writing (retries after a lost answer are safe); different chapters don't conflict. On a conflict the page keeps showing the user's click, with a notice offering **Apply mine** (sent again on the newest version, only on the user's click) and **OK** (keeps the README's state); never retried by itself. **恢复 Recovery**：每个勾选在发送前存入浏览器（每个标签页、每章一条，键 `myLibrary.tick.<书库>.<文档>.<章>.<点击 id>`），确认后删除；页面关闭或崩溃后，每章最新的一条带点击时间 `since`（毫秒，有限、大于 0、不晚于服务器时间 + 1 秒，否则 400）再发送，README 在点击之后改过就成为冲突（同样由用户决定）；无法发送的（超过 30 天、损坏、文档或章节已不在）删除并说明数量。Each tick is stored in the browser before it is sent (one entry per tab and chapter, key `myLibrary.tick.<library>.<document>.<chapter>.<click id>`), removed once confirmed; after a closed or crashed page, each chapter's newest entry is sent again with the click's time `since` (ms; finite, above 0, no later than the server's time + 1 s, else 400), and a README changed after the click makes it a conflict (the user decides as above); entries that can't be sent (over 30 days, damaged, document or chapter gone) are removed and their number said. **限制 Limits**：VS Code 等外部编辑器绕过服务器的锁和版本：过时的标签页仍可能覆盖它们的修改，服务器读写之间极短时间内的外部写入也可能被覆盖；版本只在内存中，服务器重启后重新开始（旧页面的令牌也失效，需要重新载入）；中断后的恢复依靠浏览器记录的点击时间，时钟被往回调过或伪造的请求可以绕过；没有 `base` 的旧式内部调用（不是页面）是无条件的，没有这种保护；并发的修改可能需要用户明确选择；恢复只在同一个浏览器、同一书库，保留 30 天。External editors such as VS Code bypass the server's lock and versions: a stale tab can still overwrite their changes, and an external write in the instant between the server's read and write can be lost; versions live in memory and start again when the server restarts (that run's pages also need a reload: new token); recovery after an interruption relies on the browser's click time, which a clock set back or a crafted request can get past; internal calls without `base` (not the page) are unconditional, without this protection; concurrent changes may need the user's explicit choice; recovery only in the same browser and library, kept 30 days. | — |
| L26 | 格式工具栏的限制（`format.js`、`notes.js`）：表格只插入、不能取消；选中一个网址后点链接，网址成为目标，再点一次不会还原；段距只影响预览（源码没有段落）；宽度在源码中只限制文本框本身；工具栏和 Ctrl+B / Ctrl+I 只用 `insertText`，浏览器不支持时改为直接替换（仍然保存，但没有撤销）。Limits of the formatting toolbar: a table is only inserted, never toggled off; a selected web address becomes the link's target, and a second click doesn't undo that; paragraph spacing affects only the preview (the source has no paragraphs); the width only narrows the source box itself; actions go through `insertText`, with a plain replacement where a browser lacks it (still saved, but no Undo). | — |
| B33 (C) | 勾选章节（`library_server.tick_snapshot` 经 `safe_io.update_text`）和合并（`add_book.merge_into`）用通行的换行读写 README：在 Windows 上，换行为 LF 的 README 第一次被勾选时整个文件变成 CRLF（内容不变）。RS1 写阅读状态时按字节处理，不受影响。2026-11-11 在 RS1 中发现，尚未修复。Ticking a chapter (`tick_snapshot` through `safe_io.update_text`) and merging (`merge_into`) read and write the README with newline translation: on Windows, an LF README becomes CRLF throughout on its first tick (the text itself unchanged). RS1's status writes work on bytes and aren't affected. Found during RS1, 2026-11-11; not fixed. | Task 8 |
| L27 | RS1 的限制：状态的修改不存进浏览器，浏览器在保存完成前被关闭或崩溃时，这次修改会丢失（下次打开时显示原来的状态）；版本只在内存中、外部编辑器绕过锁和版本（同 B32）；无法理解的状态行要在 README 中手动改正；"Mark as finished?" 只在进度 100% 时出现；论文的 "Mark as read" 仍然只改进度。RS1's limits: a status change isn't stored in the browser meanwhile, so one made just before the browser is closed or crashes can be lost (the old status shows next time); versions are in memory only and external editors bypass the lock and versions (as for B32); a status line it doesn't understand has to be corrected in the README by hand; "Mark as finished?" appears only at 100%; a paper's "Mark as read" still changes only its progress. | — |
| L24 | 预览中公式的规则限制（`preview.js` 的 `mathInline`/`mathBlock`）：公式中不能有反引号（反引号结束查找，代码优先）；`[a $x](u)$` 这类链接与公式交错时公式优先；表格单元格中公式里的 `\|`（未转义的竖线）会把单元格分开（用 `\vert`）；没闭合的 `\(` 按 Markdown 显示为 `(`；`$a$$b$` 显示为错误；每次修改都重新渲染整条笔记（已渲染的公式有缓存；10,000 个公式约 1 秒）。Limits of the maths rules in the preview: no backtick inside a formula (a backtick ends the search: code comes first); a link interleaved with a formula, like `[a $x](u)$`, goes to the formula; an unescaped `\|` in a formula inside a table cell splits the cell (use `\vert`); an unclosed `\(` shows as `(`, as Markdown escapes it; `$a$$b$` shows as an error; every change redraws the whole note (typeset formulas are cached; 10,000 formulas take about a second). | — |

**L29 暂缓的安全问题 / L29 — deferred security findings** (Codex, third independent review,
2026-11-12; recorded as written, owner's request 2026-11-13). **Unresolved** in the dormant
implementation in `scripts/backup.py`; not to be fixed in the packaging pass, and automatic Git
backup stays switched off (`backup.DEFERRED`) until a redesign addresses all five. Line numbers
are the review's, in the file as it was then; function names are given because lines drift.
They don't block M5d/M5e image paste and OCR, since Git backup is off.

1. **High — Branch movement remains possible during index reconciliation**
   (`_bring_up_to_date`; review: `backup.py:280`, publication at line 316). The branch is
   checked after acquiring `index.lock`, but that lock does not protect Git refs. Failing
   interleaving: reconciliation checks that the branch points to backup commit B; another
   process advances the branch to C with a ref operation that does not need `index.lock`;
   reconciliation publishes an index containing B's note version against HEAD C, which can
   stage an older note version unintentionally. The comment that "nothing can change" is
   incorrect. Correction: coordinate branch identity/ref protection with index publication,
   or refuse automatic reconciliation when that guarantee can't be given; another check alone
   leaves a race.
2. **High — Recovery can overwrite intentional staging after successful index publication**
   (`_bring_up_to_date`, `_finish_pending`, journal removal in `_back_up`; review:
   `backup.py:302`, `:344`, line 439). Failing interleaving: a backup changes a note from A to
   B and publishes the reconciled index; the process crashes before deleting its journal; the
   user intentionally stages A to revert the note; recovery sees the old blob A and replaces
   it with B. The journal can't tell an unreconciled entry from a deliberately restaged old
   version. Correction: make recovery publication-aware and bind it to verified index state;
   an ambiguous replay must preserve staging and require intervention.
3. **High — Concurrent backups can overwrite or delete each other's recovery record**
   (`_finish_pending`, journal write and deletion in `_back_up`; review: `backup.py:330`, write
   at line 428, deletion at line 431). There is one shared journal and no operation-wide
   backup lock. Two backups can both begin from A: one overwrites the other's journal; the
   winner advances the branch while the loser fails its ref compare-and-swap and deletes the
   shared journal; the winner can then meet an index-lock failure or crash with no
   recoverable record. Correction: serialise backup and recovery across processes; journal
   deletion must verify transaction ownership.
4. **High — Incomplete indexes can be published** (`_bring_up_to_date`; review:
   `backup.py:285`, `:311`). A missing real index is treated as an empty one: if
   reconciliation includes a newly added file, it can publish an index holding only those
   additions, without the unrelated tracked entries. And `os.write()`'s returned byte count is
   ignored: a short write can be followed by `fsync()` and the real index replaced by
   truncated data. Correction: fail closed on a missing or unreadable index; write the whole
   buffer and validate the resulting index before publishing it.
5. **High — The effective push endpoint is not pinned** (`_destination`, `_still`, the push in
   `_back_up`; review: `backup.py:140`, checks at line 167, push at line 447). The snapshot
   captures a remote's name, not its effective push URL or configuration, and `_still()`
   checks refs but not remote configuration. A changed `remote.<name>.pushurl` can redirect
   the later push; the explicit object id, refspec and lease don't prevent publication to a
   different endpoint that holds the expected base. Multiple push URLs aren't rejected as
   ambiguous. Correction: resolve and validate the effective destination, reject ambiguous
   ones, and push to the approved destination and configuration rather than resolving
   mutable settings again.

**已修复（历史记录中仍列为未解决）/ Fixed (still listed as open in the history)**

**M5d/M5e 工作区修复（2026-11-12，已在 `4e4abce` 提交）/ Working-tree fixes (committed in `4e4abce`):** the install
handler's `stop` local shadowed Quit's function (HTTP 500); modal formula insertion lost Undo;
stale install/clipboard replies could affect a reopened dialog; model-load errors escaped
structured handling; served images were only signature-checked; Git backup could stage
personal assets (Git backup is now deferred altogether: L29). Fixed with the regressions and evidence in
[M5_VERIFICATION.md](docs/M5_VERIFICATION.md). 修复记录与验证见该文件。
**独立审查后的修正（2026-11-12，三轮，已在 `4e4abce` 提交）/ Corrections after the independent reviews
(three rounds, committed in `4e4abce`):** merges copy images first and reuse identical copies, notes and
scripts too; Refresh reports a merge that stopped, archiving nothing. Served images are always
validated in full; the ETag is a digest of the validated bytes. Formulas are written with
delimiters that read back whole, the LaTeX unchanged; `\cfrac` is no longer rewritten to
`\frac`. Model installs hold an operating-system lock (a second one is refused and never
deletes a running one's folder) and recover from a cut-off install: a whole copy (pinned
SHA-256) left beside the model is put back, offline, before anything is deleted; the last
whole copy is never deleted. **☁ Git backup is not fixed:** two rounds of redesign (a
temporary index, whole-history audit, bound destination and lease, hook and signing refusals,
a locked index compare-and-swap with a journal) still left five High findings in the third
review, so automatic Git backup is **deferred** for this release (L29). That implementation
is kept, unused, with its tests, for the redesign.
- **B34** 测试中的同步竞态（2026-11-13，已提交、推送并通过 CI：`ad5a158`，运行 43423565578 第 1 次尝试，四个作业全部通过）：CI 运行 43414437518 第 1 次尝试（提交 `ee23329`），浏览器分片 1，`test_notes_assets_formula.py::test_upload_finishing_after_note_switch_keeps_image_without_wrong_insertion` 失败于 `assert pending`。原因在测试本身：Playwright 同步 API 中路由回调只在测试处于 Playwright 调用时运行，而测试切换章节后立即检查，回调（`route.fetch()` 后才记录）可能还没完成；服务器其实已保存图片。修正：先用有界的 `page.wait_for_timeout` 等待捕获到请求和真实服务器响应（15 秒，超时给出说明），再切换章节；把响应扣到切换之后，然后验证图片没有插入错误的笔记、只在用户选择后插入、图片一直在磁盘上。应用代码未改。本地：该测试连续 30 次通过，整个文件 24 个通过（笔记面板打开和关闭各一次），分片划分检查通过。A test synchronisation race (2026-11-13, committed, pushed and CI-verified: `ad5a158`, run 43423565578, attempt 1, all four jobs passed): CI run 43414437518, attempt 1 (commit `ee23329`), browser shard 1, `test_notes_assets_formula.py::test_upload_finishing_after_note_switch_keeps_image_without_wrong_insertion` failed at `assert pending`. The cause was the test: in Playwright's synchronous API a route callback runs only while the test is inside a Playwright call, and the test asserted right after switching chapters, before the callback (which records the request only after `route.fetch()`) had finished; the server had in fact saved the image. Fix: wait, bounded, with `page.wait_for_timeout` until the request and the real server response are captured (15 s, with an informative failure), before switching chapters; the reply is still held until after the switch, then the test checks the image isn't put into the wrong note, is inserted only on the user's choice, and stays on disk. No application change. Locally: that test passed 30 times in a row; the whole file passed (24) with the notes panel open and closed; the shard partition check passed.
- **B35** 设置中更换书库后偶尔 “Couldn't refresh: forbidden”（2026-11-13，本地修复并验证，**等待独立复审，尚未提交、推送，CI 未验证**）。两个原因：(1) 书库页面（`library_page.py` `saveSettings`）在任何 HTTP 200 后就重新加载，而旧服务器在 `restart_later` 等待运行中的任务结束时仍然应答，页面于是带着即将失效的旧令牌重新加载，新服务器之后以 403 拒绝每次写入；(2) `restart_later` 的线程是守护线程，`server.shutdown()` 让 `main()` 的 `serve_forever` 返回后，解释器结束时可能在启动新服务器之前就杀掉它，于是根本没有新服务器（真实进程复现：约 3–12 次重启中失败 1 次）。修正：每个服务器进程有一个非机密的实例标识 `INSTANCE`（不授予任何权限；写入仍需令牌，Host 检查不变）；保存设置的应答给出新书库的 `expect`（`libraries.scope`：书库 id 加服务器规范化的真实文件夹路径，复制的书库不匹配），`/api/whoami` 给出 `scope`；页面只在应答成功、实例标识有效且不同、`scope` 等于 `expect` 时才重新加载（`isReplacement`）；等待有一个单调的总期限（`waitForRestart`，150 秒，不重置），每次请求连同读取应答内容都由 `AbortController` 在 5 秒或剩余时间内取消，超时后报告原因（无应答、被拒绝、另一个服务器或书库）；重启线程不再是守护线程。403 的提示改为 “Request refused (403). This page may be outdated. Reload myLibrary and check whether your previous changes were saved.”，与网络错误分开；不自动重发、不换令牌重试、不显示令牌。Codex 复审（2026-11-13）的四个问题已在本轮修正。An occasional "Couldn't refresh: forbidden" after changing the library in Settings (2026-11-13, fixed and verified locally, **pending independent review; not committed, pushed or CI-verified**). Two causes: (1) the library page (`library_page.py` `saveSettings`) reloaded on any HTTP 200, but the old server goes on answering while `restart_later` lets running jobs finish, so the page could reload with the old token, about to die, and the new server then refused every write with 403; (2) `restart_later` ran on a daemon thread: once `server.shutdown()` let `main()`'s `serve_forever` return, the ending interpreter could kill it before it started the new server (real-process repro: about 1 restart in 3–12 never came back). Fix: each server process has a non-secret instance id, `INSTANCE` (it grants nothing; writes still need the token; the Host check is unchanged); the answer to the settings save gives the new library's `expect` (`libraries.scope`: the library id plus its real folder as the server normalises it, so a copied library doesn't match) and `/api/whoami` gives `scope`; the page reloads only on a successful answer with a valid instance id other than its own and a `scope` equal to `expect` (`isReplacement`); the wait has one monotonic overall deadline (`waitForRestart`, 150 s, never reset), every request, its body included, is aborted by an `AbortController` after 5 s or the time left, and on expiry the page says why (no answer, refused, another server or library); the restart thread is no longer a daemon. A 403 now says "Request refused (403). This page may be outdated. Reload myLibrary and check whether your previous changes were saved.", apart from network failures; nothing is replayed or retried with another token, and no token is shown. The four findings of Codex's review (2026-11-13) are corrected in this round. Tests: `tests/test_library_server.py` (the old server answers as itself while it waits; the Host refusal still applies; the save names the intended library's scope, the same folder spelled otherwise matches and a copy doesn't; in a real process the new server is started even as the main thread ends, which fails on the old code), `tests/browser/test_settings_restart.py` (the page doesn't accept the old server and accepts the intended one; writes from the reloaded page work; an old tab is refused with the new message and no token; an unsaved note stays in the editor and its recovery draft and goes into neither library; 📚 Switch library leaves the original server and tab working; `isReplacement` refuses a missing, empty, malformed or old instance, another library and a missing or malformed scope; with a 4 s test deadline, a whoami that is never answered, one whose body stalls, and another library's server are each reported in time without a reload). Mutation checks: without the abort the two stall cases fail; without the scope check the identity tests fail. Locally (2026-11-13): the B35 browser file 7/7; its key restart tests 5 rounds of 5/5; related browser files 20 passed; server and library Python tests 75 passed; 20 of 20 real-process restarts came back; the full Python suite 833 passed, 11 skipped (symlink privilege); Ruff and `git diff --check` clean. The full browser shards and the notes-closed set were not run locally. Application code changed, so the verified package (`e617e006…`) is no longer the release candidate (see section 2).
- **B3** 💾 备份按名称前缀匹配会互相删除 zip：在 `2b0ff96` 中修复（精确名称，按书库区分的名称）。Zips pruned by
  name prefix: fixed in `2b0ff96` (exact names, library-scoped names).
- **B26** `safe_io` 文档字符串中的无效转义：在 `0692189` 中修复。An invalid escape in a `safe_io` docstring:
  fixed in `0692189`.
- **L15** 同时两次启动为一个书库启动两个服务器：在 `2b0ff96` 中修复（书库锁）。Two launches at once starting two
  servers for one library: fixed in `2b0ff96` (the library lock).
- **B31** `$a^2 + b^2 = c^2$` 在用户自己的预览中没有显示为公式：2026-11-11 用户在自己实际使用的 myLibrary 中手动验证，
  公式正常显示；不需要修改代码，原因没有单独确定。`$a^2 + b^2 = c^2$` not shown as a formula in the user's own
  preview: on 2026-11-11 the user verified by hand in their real myLibrary that formulas render; no code change was
  needed, and no separate cause was established.

**已修复的数据完整性问题 / Fixed data-integrity issue**
- **L23**（C，2026-11-10）查词找不到以另一种形式保存的术语 / Lookup missing a term saved in another form.
  在提交 "Fix glossary lookup consistency with term normalization"（2026-11-10）中修复。Fixed in the commit "Fix glossary lookup consistency with term normalization" (2026-11-10).
  - **已确认 / Confirmed:** 与 B30 同一原因：术语表的词是它自己的基本形式，除非它的某个猜测也是术语表的词。通过公开的 `reader.lookup` 确定地复现：只存了"veiling glares"（文件或弹窗）时查"veiling glare"找不到；**另一个术语表有没有"glare"决定能否找到**；普通复数也一样（只存"lenses"时查"lens"找不到）；B30 拒绝加入的形式，弹窗却找不到，还提示可以加入（`in_glossary` 与加入不一致）。Same cause as B30: a glossary word was its own base form unless one of its guesses was a glossary word too. Reproduced deterministically through the public `reader.lookup`: with only "veiling glares" saved (file or popup), "veiling glare" missed it; **whether another glossary held "glare" decided whether it was found**; ordinary plurals too (only "lenses" saved: "lens" missed); a form B30 refuses to add wasn't found, and the popup offered to add it (`in_glossary` disagreeing with adding).
  - **修复 / Fix** (`scripts/reader.py`): `glossary_matches` 用两种读法：术语表现在的样子（保留以前的每个匹配），以及 B30 的"同一个术语"（选区和上下文的词算作术语表的词）；后者只重算那些基本形式会因这些词而改变的已存术语，通过与术语表缓存一起建立、随文件失效的反向索引（`_glossary_index`、`_terms_for`），不每次重建。上下文中更长的术语（"entrance pupils"对"entrance pupil"）同样匹配，仍然最长的在前、不重复。`lookup` 的`in_glossary` 用与加入完全相同的规则。长度相同时拼写与所问相同的条目在前（书的学科排序仍然优先）。CSV 文件不变；加入时的检查（B30）不变。`glossary_matches` reads the words two ways: as the glossaries have them now (every former match kept), and as B30's "same term" does (the selection's and context's words counting as glossary words); the latter re-keys only stored terms whose base forms those words change, through a reverse index built with the glossary cache and invalidated with the files (`_glossary_index`, `_terms_for`), never rebuilt per query. Longer terms in the context ("entrance pupils" for "entrance pupil") match the same way, still longest first and each once. `lookup`'s `in_glossary` uses exactly the adding rule. Of equally long entries, the one spelled as asked comes first (the book's subject still ranks before that). CSV files unchanged; the adding check (B30) unchanged.
  - **有意的例外 / Deliberate exception:** `reader.OWN_TERMS = {"glasses"}`："glasses"（眼镜）从不被当作"glass"（玻璃）的复数，在查词和加入时都一样，所以两者可以各自保存、各自查到，与先后无关。只有有真实的两个不同术语时才加词。B30 中"glare"/"glares"、"lens"/"lenses"等仍然是同一个术语，"data"/"datum"仍然是两个。"glasses" (spectacles) is never taken for the plural of "glass" (the material), in lookup and when adding alike, so each can be saved and found on its own, whatever the order. A word is added only with a real case of two different terms. glare/glares, lens/lenses stay one term (B30), data/datum two.
  - **验证 / Verification:** `tests/test_glossary_lookup.py` 32 个测试（两个方向的单复数、弹窗和外部编辑、与其他术语表无关、精确拼写优先、glass/glasses 和 data/datum 各自独立、glare/glares 和普通及不规则复数、上下文两个方向、多个术语表和学科排序、`in_glossary` 与加入一致、缓存失效）；其中 15 个在没有修复的 `8a41f78` 上失败；B30 的并发测试重复 10 次 0 次失败；相关测试 160 个通过；查词相关的浏览器测试 19 个通过；完整测试一次：581 个通过、9 个跳过。32 tests (singular and plural both ways, popup and outside edits, independence from other glossaries, exact spellings first, glass/glasses and data/datum apart, glare/glares and ordinary and irregular plurals, context both ways, several glossaries and subject order, `in_glossary` agreeing with adding, cache invalidation); 15 of them fail on the unfixed `8a41f78`; B30's concurrent tests 0 of 10 repeated runs failed; 160 related tests pass; the lookup browser tests 19 pass; the full suite once: 581 passed, 9 skipped.
  - **限制 / Limitations:** `OWN_TERMS` 只有"glasses"，其他看起来像复数的独立术语要以后有实例时再加；只存"datum"时查"data"仍按词典显示 datum 的条目（如前），但不再说它已在术语表中，加入"data"也允许；`in_glossary` 只要有任何一个术语表有这个术语就为真，而加入只检查目标术语表（以前的约定）；以前因"第一行优先"被隐藏的同键行（例如 glass 和 glasses 都存过）现在会显示出来。`OWN_TERMS` holds only "glasses"; other plural-looking terms of their own are added when a real case appears; with only "datum" saved, "data" still shows datum's entry through the dictionary (as before), but no longer says it's in the glossary, and adding "data" is allowed; `in_glossary` is true when any glossary has the term, while adding checks only the target glossary (the earlier contract); rows that "the first row wins" used to hide (e.g. glass and glasses both saved) now show.

**已修复的数据完整性问题 / Fixed data-integrity issue**
- **B30**（C，2026-11-10）同一个术语被加入两次 / The same glossary term added twice.
  在提交 "Fix glossary duplicate detection with stable term normalization"（2026-11-10）中修复。Fixed in the commit "Fix glossary duplicate detection with stable term normalization" (2026-11-10).
  - **原因（有证据）/ Cause (with evidence):** 不是缺少锁：`reader._add_glossary_row` 在文件锁内重新读取并检查，锁和缓存都正常（记录线程进出锁、比较的键和术语表词汇的探测显示了这一点）。重复检查用 `tokens()`，而 `lemma()` 优先采用术语表已经使用的词形：只有"veiling glares"时，"glares"就是它自己的基本形式，键 (veiling, glares) 与"veiling glare"的 (veiling, glare) 不同，于是两者都被写入。结果取决于哪一个先写入：12 次并发运行中，复数先写入的 2 次全都重复，单数先写入的 10 次全都正确；**不需要并发**，先加复数再加单数也会重复（应用中的真实错误，不只是测试问题）。它在 `610c858` 上同样出现（30 次中 7 次）。没有证据表明它是 L20。Not a missing lock: `reader._add_glossary_row` re-reads and checks under the file's lock, and the lock and the caches behaved correctly (a probe logging each thread entering and leaving the lock, the keys compared and the glossary vocabulary showed it). The duplicate check uses `tokens()`, and `lemma()` prefers a word form a glossary already uses: with only "veiling glares" stored, "glares" is its own base form, the key (veiling, glares) differs from "veiling glare"'s (veiling, glare), and both were written. The outcome depended on which was written first: of 12 concurrent runs, the 2 with the plural first all duplicated, the 10 with the singular first were all right; **no concurrency needed**: the plural, then the singular, one after the other, duplicated too (a real application bug, not only a test issue). Also at `610c858` (7 of 30 runs). No evidence links it to L20.
  - **修复 / Fix** (`scripts/reader.py`: `lemma`, `tokens`, `_add_glossary_row`): 锁内的重复检查按术语表加入这个术语**之后**的状态判断：把新术语的词算作术语表的词（`lemma`/`tokens` 新的可选参数 `also`，默认行为不变），于是不论哪个先存，两者都得到共同的基本形式。另外删除了 `add_glossary_term` 中锁外的提前检查：它用缓存的术语表、不含新术语的词，是另一种"同一个术语"，会错误拒绝锁内检查会加入的术语（词典把"data"的基本形式给成"datum"，术语表中有"datum"时"data"被拒绝）；现在只由锁内的检查决定一次。查词、缓存、锁、原子写入、BOM 和换行都没有改。Also removed: the early check outside the lock in `add_glossary_term`: on the cached glossary and without the new term's words it was another "same term", and refused terms the check under the lock adds (the dictionary gives "data" the base form "datum", so with "datum" in the glossary "data" was refused); now the check under the lock decides, once. The duplicate check under the lock judges by the glossary as it will be **once the term is in it**: the new term's words count as glossary words (a new optional `also` for `lemma`/`tokens`, the default unchanged), so both get their shared base form whichever was stored first. Lookup, caches, the lock, atomic writes, BOM and line endings unchanged.
  - **验证 / Verification:** `tests/test_glossary_terms.py` 新增 5 个测试（两种先后顺序、强制复数先写入的并发顺序、真正不同的术语仍然都保留、datum/data 只由一种定义决定）；其中两个在没有修复的 `0624ec9` 上确定地失败，datum/data 测试在只恢复提前检查时失败；并发测试的同步点移到 `glossary_files`（删除提前检查后原来的同步点不再被调用）；并发测试重复 20 次 0 次失败；原来的间歇测试修复后单独运行 30 次 0 次失败（修复前 11 次和 7 次）；查词、术语表、读取器、safe_io 等测试 128 个通过；完整测试一次：549 个通过、9 个跳过。5 new tests (both orders, the concurrent order with the plural forced first, really different terms still both kept, datum/data decided by one definition); two of them fail deterministically on the unfixed `0624ec9`, and the datum/data test fails with only the early check restored; the concurrent tests' meeting point moved to `glossary_files` (the old one was no longer called once the early check was gone); the concurrent tests 0 of 20 repeated runs failed; the original intermittent test 0 of 30 isolated runs failed with the fix (11 and 7 before); lookup, glossary, reader and safe_io tests 128 passed; the full suite once: 549 passed, 9 skipped.
  - **限制 / Limitations:** 已经写入的重复行不会被清理（查找时第一行优先，如前）；查词中的同类不一致见 L23（之后已修复）；只在同一个术语表文件内查重复（设计如此）。Duplicate rows already written aren't cleaned up (lookup uses the first row, as before); the same inconsistency in lookup is L23 (fixed since); duplicates are checked within one glossary file (by design).

**已修复的数据完整性问题 / Fixed data-integrity issues**
- **FA-04 + FA-05**（C，数据完整性 data integrity，Codex M7 后审计 post-M7 audit，2026-11-18，M7.1 S2）💾 备份把改过的 PDF 当作“已经在那里”；自动备份看不到删除 / 💾 Back up took a changed PDF for "already there"; the automatic backup didn't see deletions.
  第一轮已实现并本地验证；Codex 审查结论为要求修改（六项），所有者接受（2026-11-20）；第二轮修正已实现；Codex 第二次审查仍要求修改（三项），所有者接受（2026-11-20）；第三轮修正已实现；Codex 第三次审查仍要求修改（两项），所有者接受（2026-11-23）；第四轮修正已实现并本地验证；Codex 第四次审查结论为“批准，有非阻塞问题”，所有者接受并批准一次本地提交（2026-11-23）；剩余的非阻塞问题记为 B42（S6）；经所有者分别批准后提交并推送为 `e28bf18`，CI 运行 45155217482 第 1 次尝试五个作业全部通过（见下面的“CI 记录”）。First round implemented and locally verified; Codex's review requested changes (six findings), accepted by the owner (2026-11-20); the second round's corrections were implemented; Codex's second review again requested changes (three findings), accepted by the owner (2026-11-20); the third round's corrections were implemented; Codex's third review again requested changes (two findings), accepted by the owner (2026-11-23); the fourth round's corrections are implemented and locally verified; Codex's fourth review: APPROVE WITH NON-BLOCKING FINDINGS, accepted by the owner, who approved one local commit (2026-11-23); the remaining non-blocking finding is B42 (S6); with the owner's separate approvals, committed and pushed as `e28bf18`; CI run 45155217482, attempt 1, all five jobs passed (see "CI record" below).
  - **已确认 / Confirmed:** FA-04：`folder_backup._copy_pdfs` 在大小相同、备份副本的时间不早于原件减 2 秒时跳过 PDF；保存标注后大小不变的 PDF（或时间被保留的）从不被备份。FA-05：`back_up(only_if_changed=True)`（`auto_backup` 用它）只比较仍存在的文件的修改时间与上一个 zip 的时间，所以只删除或重命名文件、或在旧时间下改动内容时，回答“没有改变”。修复前的新测试证实了两者，另外还有：时间相同时（Windows 时钟约 15 ms 的精度）刚改的笔记也被跳过；损坏、截断、名称重复的上一个 zip 被信任；zip 写入中途失败留下 `.zip.part` 并以未处理的异常结束；制作 zip 时一个文件被删除导致整个备份失败；PDF 副本路径超过 260 个字符时备份失败。FA-04: `folder_backup._copy_pdfs` skipped a PDF when the size matched and the backup copy's time was no older than the original's minus 2 s, so a PDF whose marks were saved without changing its size (or with its time kept) was never backed up. FA-05: `back_up(only_if_changed=True)` (used by `auto_backup`) compared only the modification times of files still there with the last zip's time, so deleting or renaming a file, or changing content under an old time, answered "nothing changed". The new tests confirmed both before the fix, and also: a note changed within the same clock tick (about 15 ms on Windows) was skipped; a damaged, truncated or duplicate-name last zip was trusted; a zip write failing halfway left a `.zip.part` and ended in an unhandled error; a file deleted while the zip was made failed the whole backup; a PDF copy past 260 characters failed the backup.
  - **修复 / Fix**（只改 `scripts/folder_backup.py`；没有新依赖、没有清单文件、没有迁移、备份格式不变 only `scripts/folder_backup.py`; no new dependency, no manifest, no migration, the backup format unchanged）：
    - PDF：只有备份副本现在逐字节与原件相同时才跳过（`_same_file`：大小不同即为改变；大小相同则按 1 MiB 的块读到第一个不同处，内存有界）；大小、时间、文件 id 或以前的摘要都不作为相同的证据。改变的 PDF 由系统复制（`shutil.copyfile`）到这次尝试自己的临时名称，写到磁盘（fsync），与原件再比较一次，相同才原子地替换旧副本；复制期间原件改变（保存标注）则重复，最多 `TRIES` 次。失败的 PDF 保留旧副本，其余 PDF 照常；有失败时备份不报告成功（`BackupIncomplete`，一种 ValueError：页面显示说明，`auto_backup` 记为失败）。备份的 PDF 仍然从不删除，原件只读取。PDFs: skipped only when the backup copy holds the same bytes now (`_same_file`: a different size is a change; an equal size is read in 1 MiB chunks up to the first difference, bounded memory); size, times, file ids or an earlier digest never count as proof. A changed PDF is copied by the system (`shutil.copyfile`) to this attempt's own temporary name, flushed to the disk (fsync), compared with the original again, and only then atomically replaces the old copy; a PDF that changes while it is copied (marks being saved) is copied again, at most `TRIES` times. A failed PDF keeps its old copy and the other PDFs go on; with a failure the backup is not reported as done (`BackupIncomplete`, a ValueError: the page shows the message and `auto_backup` reports a failure). Backed-up PDFs are still never deleted; the originals are only read.
    - zip：`only_if_changed` 时把上一个 zip 的成员清单和内容（不解压到磁盘，读到末尾即检查 CRC）与现在要备份的文件逐字节比较（`_zip_differs`），删除、重命名、新加的文件和旧时间下的改动都算改变；不同于上述的 zip（读不完、名称重复、没有 `RESTORE.txt`）从不算作“相同”：做一个新的 zip，消息说明上一个为什么不被信任，那个 zip 原样保留。新 zip 先写到唯一的临时名称、fsync、读回检查（名称完全一致，`testzip`），才获得真名；之后才删除超过 `KEEP` 的旧 zip；写入失败时不发布、不删除任何旧 zip、不留临时文件；制作期间文件被删除则重新列出，最多 `TRIES` 次。手动备份照旧每次都做 zip；每天一次的条件（20 小时）不变。The zip: with `only_if_changed`, the last zip's member list and contents (read without extracting; reading to the end checks the CRC) are compared byte for byte with the files to back up now (`_zip_differs`); a deleted, renamed or added file and a change under an old time all count. A zip unlike that (unreadable to the end, a name twice, no `RESTORE.txt`) never counts as "the same": a new zip is made, the message says why the last one wasn't trusted, and that zip is left as it is. A new zip is written to a unique temporary name, fsynced and read back (exactly the expected names, `testzip`) before it gets its real name; only then are zips beyond `KEEP` deleted; a failed write publishes nothing, deletes no old zip and leaves no temporary file; a file deleted meanwhile means listing again, at most `TRIES` times. A manual backup still always makes a zip; the once-a-day rule (20 hours) is unchanged.
    - 备份文件夹在受保护的书库（展示书库或测试书库）中时拒绝，什么也不写。A backup folder inside a frozen library (the showcase or test library) is refused before anything is written.
  - **验证 / Verification:** `tests/test_folder_backup.py` 新增 31 个测试（共 37 个）：大小相同的改动在四种时间下（原件新 1 秒、时间相同、原件更旧、备份副本在将来）都被复制；相同内容在任何时间下都不再复制；新的和大小改变的 PDF；zip 被跳过时改变的 PDF 仍被复制，`pdfs=False` 不碰 PDF；复制中途失败和无法替换时旧副本逐字节保留、没有临时文件、报告失败、其他 PDF 照常；复制期间原件改变则重复、一直改变则报告；按块比较到最后一个字节；超过 260 个字符的 PDF 副本路径；受保护的备份文件夹；在旧时间下删除笔记、删除图片、删除引用文件、保持时间的重命名、旧时间的新文件、大小和时间都不变的改动，各产生新 zip，内容逐字节相同，旧 zip 保留；没有改变（时间变新）时跳过，缓存、归档、`library.html` 和 PDF 的改变不产生 zip；`auto_backup` 在每天的条件满足时看到删除，当天内仍等待（设置时间，不睡眠）；截断、不是 zip、CRC 错误、名称重复、没有 `RESTORE.txt` 的上一个 zip；S2 之前格式的 zip 仍可作为比较基准；zip 写入失败时不发布、不删除旧 zip；读回检查失败时不发布；制作期间文件被删除时重新列出；中断留下的临时文件不被当作备份；恢复到一个新的空文件夹后，所有文件和 PDF 与书库逐字节相同，较早的 zip 保留较早的状态。31 new tests in `tests/test_folder_backup.py` (37 in all): a same-size change is copied under four time relations (the original 1 s newer, equal times, the original older, the copy in the future); the same content is never copied again whatever the times; new and resized PDFs; a changed PDF is copied while the zip is skipped, and `pdfs=False` leaves PDFs alone; a copy cut off halfway and one that can't be put in place keep the old copy byte for byte, leave no temporary file, report a failure, and the other PDFs go on; a PDF changing during the copy is copied again, and one that never settles is reported; comparison in chunks to the last byte; a PDF copy path past 260 characters; a frozen backup folder; deleting a note, an image or the references file, a rename keeping the time, a new file with an old time and a change keeping size and time, all under old times, each make a new zip with byte-identical contents and keep the old one; an unchanged library (newer times) skips, and changes in caches, the archive, `library.html` and PDFs make no zip; `auto_backup` sees a deletion once the daily rule allows and still waits within the day (times set, no sleeps); a truncated, non-zip, bad-CRC, duplicate-name or `RESTORE.txt`-less last zip; a zip made before S2 is still a baseline; a failed zip write publishes nothing and deletes no old zip; a failed read-back publishes nothing; a file deleted while the zip is made is listed again; a temporary file left by an interruption is never taken for a backup; restored into a new empty folder, every file and PDF is byte for byte the library's, and the earlier zip keeps the earlier state.
    修复前（`3b901d6` 的 `folder_backup.py`，新测试文件）：37 个中 29 个失败、8 个通过（6 个原有测试和 2 个守护原有行为的新测试）。29 个中 23 个因原缺陷失败（例如同大小改变的 PDF 仍是旧内容，删除后“nothing changed”，损坏的 zip 被信任，制作期间删除文件时 `FileNotFoundError`）；6 个先因新名称不存在而失败，加上兼容垫片后仍全部失败（没有报告失败、长路径 `FileNotFoundError`、受保护的文件夹不被拒绝；按块比较的测试检查新的实现，没有对应的旧行为）。修复后全部通过。Before the fix (`3b901d6`'s `folder_backup.py`, the new test file): 29 of 37 failed, 8 passed (the 6 existing tests and 2 new ones guarding existing behaviour). 23 of the 29 failed on the defects themselves (e.g. a same-size changed PDF kept its old content, "nothing changed" after a deletion, a damaged zip trusted, `FileNotFoundError` when a file was deleted while zipping); 6 failed first on new names, and with a compatibility shim all 6 still failed (no failure reported, `FileNotFoundError` on the long path, a frozen folder not refused; the chunked-comparison test checks the new implementation and has no old counterpart). After the fix all pass.
    **2 GB 合成数据测量 / 2 GB synthetic measurement**（一次性，不在 CI 中 one-off, not in CI；20 个 100 MiB 的随机内容 PDF，2,097,152,180 字节 20 random-content 100 MiB PDFs, 2,097,152,180 bytes；书库和备份文件夹在同一块 NVMe SSD 上 library and backup folder on the same NVMe SSD；约 31 GB 内存，数据刚写入，**操作系统缓存是热的** 31 GB RAM, data just written, **warm OS cache**）：首次备份（全部复制）4.8 秒（旧代码 0.8 秒；增加的是 fsync 和复制后的比较）；没有改变（全部比较）1.7–1.9 秒（旧代码 0.04 秒，但旧代码不读内容）；一个 PDF 中间改了一个字节、大小和时间不变 1.9 秒，复制 1 个，备份副本与原件相同（旧代码 0.01 秒，没有复制，**副本仍是旧内容**）；一个 PDF 大小改变 1.8 秒。内存：Python 分配峰值 4.3 MiB（旧代码 0.18 MiB），进程工作集峰值约 31 MiB（导入后约 27 MiB）；与 PDF 大小无关。first backup (copy all) 4.8 s (old code 0.8 s; the difference is the fsync and the comparison after the copy); unchanged (compare all) 1.7–1.9 s (old code 0.04 s, but it reads no content); one byte changed mid-PDF with size and times kept 1.9 s, 1 copied, the copy equals the original (old code 0.01 s, nothing copied, **the copy still stale**); one PDF resized 1.8 s. Memory: Python allocation peak 4.3 MiB (old code 0.18 MiB), process peak working set about 31 MiB (about 27 MiB after imports), independent of PDF size. **含义 / Implication:** 每次有 PDF 副本的备份都读两遍全部 PDF 字节（书库一遍，备份文件夹一遍）；冷缓存或慢的介质上由读取速度决定，例如 U 盘每秒约 100 MB 时，2 GB 的备份一侧约需 20 秒以上，30 GB 的书库需数分钟（估计，未测量）。按计划修订 2，正确性不为速度让步；如果所有者认为太慢，可以决定 PDF 部分多久运行一次，每次运行仍比较内容。Each backup with PDF copies reads all PDF bytes twice (the library once, the backup folder once); with a cold cache or slow media read speed dominates: at about 100 MB/s (a USB stick), the backup side of 2 GB alone takes 20 s or more and a 30 GB library minutes (an estimate, not measured). As plan revision 2 requires, correctness is not traded for speed; if the owner finds it too slow, they may decide how often the PDF part runs, each run still comparing content.
    **第一轮的最终本地检查 / The first round's final local checks**（2026-11-20，Windows 11，Python 3.14.10，基于 `3b901d6` 的工作区 working tree on `3b901d6`）：`uv run pytest -q -rs` 1070 个通过、21 个跳过（全部是本机没有权限创建符号链接的测试；CI 要求运行它们 all symlink tests lacking the local privilege; CI requires them）；Edge 157.0.4341.60 浏览器分片 browser shards 1/3、2/3、3/3 各 101 个通过 101 passed each；`--notes-closed` 组 22 个通过 22 passed；`test_reference_nav.py --notes-closed` 48 个通过 48 passed；`ruff check .`、`ruff format --check .`、`git diff --check` 通过 pass。这些检查在 `docs/USER_GUIDE.md` 和本节的文字改动之前运行；之后只改了文档，`git diff --check` 重新运行通过。The checks ran before the wording changes to `docs/USER_GUIDE.md` and this section; only docs changed afterwards, and `git diff --check` was rerun and passes. 没有 CI（未推送）no CI (not pushed)。
    证据 Evidence：`.cache/m7.1-evidence/s2/`（修复前的运行和垫片运行、`3b901d6` 的模块、测量脚本和 JSON、最终检查的日志；本地，不在 git 中 local, not in git）。
  - **Codex 审查与第二轮修正 / Codex's review and the second round's corrections**（审查结论：要求修改；所有者接受全部六项并排入 S2，2026-11-20 review verdict: request changes; all six accepted and scheduled into S2 by the owner, 2026-11-20；只改 `scripts/folder_backup.py`，备份格式不变 only `scripts/folder_backup.py`, the backup format unchanged）：
    1. **B41 长路径 / Long paths:** `your_files` 不再用 `rglob`/`is_file`，而是逐个文件夹经由长路径形式（`safe_io._os_path`）列出；PDF 的列出、比较、复制，zip 的写入、读回、命名、列出旧 zip、删除旧 zip 和 `library.toml` 的读取都经由它；书库文件夹本身超过限制也可以。与以前相同：进入联接，不进入文件夹符号链接，包括指向文件的符号链接；指回上层文件夹的联接不再走第二遍（以前会一直走下去）。列不出的文件夹、悬空的链接或联接、无法读取的文件使整个备份失败（不发布 zip、不删除旧 zip、消息说出是哪个），不再被当作空的。`your_files` lists folder by folder through the long-path form (`safe_io._os_path`) instead of `rglob`/`is_file`; so do listing, comparing and copying PDFs, writing, reading back, naming, listing and deleting zips, and reading `library.toml`; a library folder that is itself past the limit works. As before: junctions are entered, folder symlinks aren't, symlinked files are included; a junction back up to a folder it is inside isn't walked again (before, the walk went on and on). A folder that can't be listed, a dangling link or junction, or a file that can't be read fails the whole backup (no zip published, no old zip deleted, the message names it) instead of counting as empty.
    2. **一次一个备份 / One backup at a time:** 同一个备份文件夹中，判断改变、命名、发布、删除旧 zip 和复制 PDF 都在 `_one_backup_at_a_time` 之内：备份文件夹中 `.myLibrary-backup.lock` 上的操作系统锁（与服务器锁 `libraries.hold_library` 相同的做法；进程结束时由系统释放），所以线程、进程和同一文件夹的其他写法（联接、映射的驱动器）都遇到同一个锁。手动备份最多等 `LOCK_WAIT`（60 秒），然后说明另一个备份正在进行（`BackupBusy`）；启动时的自动备份不等待，直接说明。每天一次的判断也在锁内。新 zip 用不覆盖的重命名获得名字（Windows 的 `os.rename`，其他系统 `os.link`）：名字已被占用就用下一个（`-2`、`-3`），已完成的 zip 从不被替换。Deciding what changed, naming, publishing, deleting old zips and copying PDFs all happen inside `_one_backup_at_a_time` for one backup folder: an operating-system lock on `.myLibrary-backup.lock` in that folder (the same way as the server's lock, `libraries.hold_library`; the system lets go of it when a process ends), so threads, processes and other spellings of the folder (a junction, a mapped drive) all meet the same lock. A manual backup waits up to `LOCK_WAIT` (60 s), then says another backup is running (`BackupBusy`); the automatic backup at start doesn't wait and says so. The once-a-day decision is made under the lock too. A new zip gets its name by a rename that never replaces (`os.rename` on Windows, `os.link` elsewhere): a name already taken means the next one (`-2`, `-3`), and a finished zip is never replaced.
    3. **保留 / Retention:** 按名称中的日期（本工具写的）排序，不再按可被复制、同步服务或错误时钟改变的文件时间；刚做的 zip 从不被删除（保留它和其余最新的 `KEEP` − 1 个）；任何一个 zip 的名称日期或文件时间在将来（超过 `FUTURE` 60 秒），或名称中的日期不是真的日期时，这次什么也不删除，消息说明。文件时间在将来的 zip 不再阻止每天的自动备份。Ordered by the dates in the names (written by this tool), not by file times that copying, a sync service or a wrong clock can change; the zip just made is never deleted (it and the newest `KEEP` − 1 others stay); when any zip's name date or file time is in the future (beyond `FUTURE`, 60 s) or its name has no real date, nothing is deleted this time and the message says so. A zip with a file time in the future no longer holds back the daily automatic backup.
    4. **说明文件的 CRC / The instructions' CRC:** 比较上一个 zip 时，说明文件也读到末尾（检查 CRC）；它的文字可以不同（旧版本写的）。损坏的说明文件使上一个 zip 不被信任（新 zip，旧的保留）。When the last zip is compared, the instructions are read to their end too (CRC checked); their words may differ (written by an older version). Damaged instructions make the last zip untrusted (a new zip; the old one kept).
    5. **名为 RESTORE.txt 的书库文件 / A library's own RESTORE.txt:** 书库顶层有名为 `RESTORE.txt` 的文件或文件夹（任何大小写，Windows 不区分）时，说明文件改名为 `RESTORE (myLibrary backup).txt`（`INSTRUCTIONS`），用户的文件保持原名和原内容，解压时谁也不覆盖谁；两个名字都被占用时，在写入或删除任何东西之前拒绝备份并说明。用户的文件从不被排除。A top-level file or folder named `RESTORE.txt` in the library (any case: Windows doesn't tell them apart) makes the instructions `RESTORE (myLibrary backup).txt` (`INSTRUCTIONS`); the user's file keeps its name and bytes, and unzipping puts neither over the other; with both names taken the backup is refused, with an explanation, before anything is written or deleted. The user's files are never left out.
    6. **文档 / Docs:** B39 条目中过时的“已本地提交，推送和 CI 待批准”已改正；B41 排入 S2。B39's stale "committed locally, push and CI awaiting approval" corrected; B41 scheduled into S2.
    **第二轮验证 / Second-round verification:** `tests/test_folder_backup.py` 再增加 18 个测试（共 55 个，第一轮的全部保留）：超过 260 个字符的笔记（备份、在旧时间下的改动、恢复）；书库文件夹本身很深（笔记、目录、PDF，跳过、删除、逐字节恢复）；列不出的文件夹（模拟，手动和 `only_if_changed`）和真实的 Windows 权限（`icacls` 拒绝列出）；读不了的 PDF 文件夹（其他 PDF 照常）和悬空的联接；联接照旧进入、回路不再走；运行中的手动备份期间自动备份什么也不做；重叠的两个手动备份轮流进行，各有自己的 zip，第一个逐字节不变；发布前出现同名文件时不覆盖；联接写法的同一文件夹遇到同一个锁；另一个真实进程持有锁；保留在将来的文件时间和名称日期下不删除、刚做的 zip 保留、恢复正常后照常保留；将来的文件时间不阻止每天的备份；损坏的说明文件；`RESTORE.txt`、`restore.TXT` 和名为 `Restore.txt` 的文件夹；两个名字都被占用时拒绝。并发的 5 个测试连续 15 次运行全部通过。18 more tests in `tests/test_folder_backup.py` (55 in all; every first-round test kept): a note past 260 characters (backup, a change under an old time, restore); a deep library folder (notes, catalog, PDFs; skipping, a deletion, byte-for-byte restore); an unlistable folder (simulated, manual and `only_if_changed`) and a real Windows permission (`icacls` denies listing); an unreadable PDF folder (the other PDFs still go) and a dangling junction; junctions entered as before, a loop no longer walked; the automatic backup does nothing while a manual one runs; two overlapping manual backups take turns, each with its own zip, the first byte for byte unchanged; no replacing a same-name file that appears before publication; the folder through a junction meets the same lock; another real process holding the lock; retention with future file times and name dates deletes nothing and keeps the new zip, then keeps as usual again; a future file time doesn't stop the daily backup; damaged instructions; `RESTORE.txt`, `restore.TXT` and a folder `Restore.txt`; refusal with both names taken. The 5 concurrency tests passed 15 runs in a row.
    **修复前 / Before the fix:** 新测试文件在第一轮的模块上 55 个中 19 个失败（其中一部分先因新名称不存在而失败）。因此另写了只用公开接口（`back_up`、`auto_backup`、`zips`）的独立复现，在两个版本上运行（临时书库和设置）：第一轮的模块上七个情形全部出现缺陷——长路径的笔记不在 zip 中；列不出的文件夹被当作空的而报告成功；重叠的两个备份报告同一个名字、只剩一个 zip（第二个完成的 zip 被覆盖）；文件时间在将来时刚做的 zip 被删除；说明文件 CRC 错误的 zip 被当作“没有改变”；`RESTORE.txt` 和 `restore.TXT` 解压后说明文件丢失（zip 中名字重复）。当前模块上七个全部没有缺陷。The new test file on the first round's module: 19 of 55 failed (some first on new names). So a separate reproduction using only the public API (`back_up`, `auto_backup`, `zips`) ran on both versions (temporary library and settings): on the first round's module all seven scenarios showed the defect—the long-path note missing from the zip; an unlistable folder taken for empty and success reported; two overlapping backups reporting the same name with one zip left (the second's finished zip replaced); the zip just made deleted under future file times; a zip with a bad instructions CRC taken as "nothing changed"; with `RESTORE.txt` and `restore.TXT`, the instructions lost on unzipping (the name twice in the zip). On the current module none of the seven does.
    **第二轮的最终本地检查 / The second round's final local checks**（2026-11-20，Windows 11，Python 3.14.10，基于 `3b901d6` 的工作区 working tree on `3b901d6`）：`uv run pytest -q -rs` 1088 个通过、21 个跳过（全部是本机没有权限创建符号链接的测试 all symlink tests lacking the local privilege）；Edge 157.0.4341.60 浏览器分片 browser shards 1/3、2/3、3/3 各 101 个通过 101 passed each；`--notes-closed` 组 22 个通过 22 passed；`test_reference_nav.py --notes-closed` 48 个通过 48 passed；`ruff check .`、`ruff format --check .`、`git diff --check` 通过 pass。没有 CI（未推送）no CI (not pushed)。**2 GB 测量重复 / 2 GB measurement repeated**（同样条件 same conditions）：首次备份 first backup 6.1 秒 s，没有改变 unchanged 1.8–2.0 秒 s，同大小同时间的一个改动 one same-size, same-time change 2.2 秒 s（副本正确 copy correct），大小改变 resized 2.6 秒 s；Python 分配峰值 Python allocation peak 4.3 MiB，工作集峰值 working-set peak 约 about 31 MiB。第二轮没有改动 PDF 的比较和复制，只改了列出文件；首次备份比第一轮的 4.8 秒慢，是同一代码路径的运行间差异（热缓存，主要是 fsync），不是新的开销。Round 2 didn't change PDF comparison or copying, only the listing; the first backup's 6.1 s against round 1's 4.8 s is run-to-run variation on the same code path (warm cache, mostly fsync), not a new cost. 证据 Evidence：`.cache/m7.1-evidence/s2/round2/`（第一轮的模块和测试、新测试在第一轮模块上的运行、独立复现脚本和两个版本的结果、并发测试的重复运行、测量、最终检查的日志 the first round's module and tests, the new tests on it, the standalone reproduction and both versions' results, the concurrency repeats, the measurement, the final-gate logs）。
  - **Codex 第二次审查与第三轮修正 / Codex's second review and the third round's corrections**（结论：要求修改，三项，所有者接受，2026-11-20 verdict: request changes, three findings, accepted by the owner, 2026-11-20；只改 `scripts/folder_backup.py` 和测试 only `scripts/folder_backup.py` and the tests）：
    1. **Windows 名称 / Windows names:** 在 Windows 上，备份的每一次读写都用扩展长度形式（`\\?\`，`folder_backup._os`，只做字面的 `normpath`），所以名字总是按原样使用：以前在短路径中，`note.md.` 被 Windows 去掉结尾的点后读成了另一个文件 `note.md`。要备份的文件和文件夹（zip 中的和 PDF）的名字先检查（`_name_problem`、`_check_names`），在读取、写入或删除任何东西之前拒绝：以点或空格结尾、Windows 的设备名（CON、NUL、COM1…，带扩展名也算）、Windows 不允许的字符、形如 8.3 短名（如 `NOTES~1.MD`，解压后可能是另一个文件的第二个名字）、同一文件夹中只差大小写的两个名字。错误（`AmbiguousName`，一种 `BackupIncomplete`）给出相对路径、原因和改名的方法；用户的文件从不被改名或改动。这样的 PDF 不被读取、不被复制，并作为失败报告，其他 PDF 照常。On Windows every read and write of the backup goes through the extended-length form (`\\?\`, `folder_backup._os`, a lexical `normpath` only), so a name is always used exactly as written: before, in a short path, `note.md.` was read as another file, `note.md`, Windows having dropped the trailing dot. The names of the files and folders to back up (in the zip and the PDFs) are checked first (`_name_problem`, `_check_names`) and refused before anything is read, written or deleted: a trailing dot or space, a Windows device name (CON, NUL, COM1, …, with an extension too), a character Windows doesn't allow, the shape of an 8.3 short name (like `NOTES~1.MD`: once unzipped it could be a second name of another file), and two names in one folder that differ only in case. The error (`AmbiguousName`, a kind of `BackupIncomplete`) gives the relative path, the reason and how to rename; the user's files are never renamed or changed. Such a PDF is never read or copied and is reported as a failure; the other PDFs go on.
    2. **说明文件的另一个名字 / The instructions' other name:** 第二轮的 `RESTORE (myLibrary backup).txt` 在解压时得到 8.3 短名 `RESTOR~1.TXT`；书库中名为 `RESTOR~1.TXT` 的文件随后被写进它，文件丢失（已复现）。现在的候选名 `RESTORE1.TXT`、`RESTORE2.TXT` 本身是 8.3 名字，Windows 不给它们第二个名字（已验证）；仍按大小写不敏感检查与书库顶层名字的冲突，都被占用时拒绝。形如短名的用户文件（如 `RESTOR~1.TXT`）按第 1 项拒绝。现有备份不受影响（默认名仍是 `RESTORE.txt`；第二轮的名字从未提交）。Round 2's `RESTORE (myLibrary backup).txt` got the 8.3 short name `RESTOR~1.TXT` when unzipped; a library file named `RESTOR~1.TXT` was then written into it and lost (reproduced). The candidates are now `RESTORE1.TXT` and `RESTORE2.TXT`, plain 8.3 names Windows gives no second name (verified); collisions with the library's top-level names are still checked regardless of case, and with all taken the backup is refused. A user file shaped like a short name (like `RESTOR~1.TXT`) is refused by item 1. Existing backups are unaffected (the default name is still `RESTORE.txt`; round 2's name was never committed).
    3. **权限测试 / The permission test:** 测试用 `getpass.getuser()`（读取 `USERNAME` 等环境变量）指定被拒绝的账户，可能是另一个账户：拒绝没有作用于这个进程，测试报告产品失败（已复现：`USERNAME=Administrator` 时 "DID NOT RAISE OSError"）。现在用这个进程令牌中的用户 SID（`OpenProcessToken`/`GetTokenInformation`），先确认列出文件夹真的被拒绝；做不到时（没有 icacls、拒绝不起作用）以“前提条件”跳过，而不是失败；对备份失败的断言没有放宽（还检查消息中的文件夹名、旧 zip 逐字节保留、两种模式）。The test named the denied account with `getpass.getuser()` (which reads `USERNAME` and the like), possibly another account: the denial didn't apply to this process and the test reported a product failure (reproduced: "DID NOT RAISE OSError" with `USERNAME=Administrator`). It now uses the user SID in this process's token (`OpenProcessToken`/`GetTokenInformation`) and first checks that listing the folder really is refused; when that can't be set up (no icacls, a denial with no effect) it skips as a prerequisite instead of failing; the assertions on the failed backup are not weakened (they now also check the folder's name in the message, the old zip byte for byte, and both modes).
    **第三轮验证 / Third-round verification:** `tests/test_folder_backup.py` 共 91 个测试（全部保留之前的 FA-04、FA-05、B41 和第二轮的测试；新增：短路径和深路径中以点或空格结尾的文件和文件夹（8 个），设备名和短名形状（5 个），名称规则（19 个），只差大小写，名为 `NUL.pdf` 的 PDF，说明文件的 8.3 名没有短名（真实解压，检查 `GetShortPathNameW`），`RESTOR~1.TXT` 被拒绝）。每次拒绝都检查：手动两种模式和自动备份都拒绝并说出名字，没有新 zip，旧 zip（`KEEP` 1）逐字节保留，没有临时文件。修复前：新测试文件在第二轮模块上 91 个中 40 个失败（一部分先因新名称）；只用公开接口的独立复现在第二轮模块上七个情形全部出现缺陷（短路径中两种名字的 zip 成员是另一个文件的内容；深路径中两种名字被发布；`CON.md` 被发布；`RESTOR~1.TXT` 解压后丢失；应被拒绝的备份删除了之前唯一的 zip），当前模块上全部没有。权限测试在 `USERNAME=Administrator` 下：第二轮的测试失败，第三轮的通过。91 tests in `tests/test_folder_backup.py` (every earlier FA-04, FA-05, B41 and round-2 test kept; new: trailing dots and spaces on files and folders in short and deep paths (8), device names and short-name shapes (5), the name rules (19), case-only twins, a PDF named `NUL.pdf`, the instructions' 8.3 name having no short name (a real unzip, checked with `GetShortPathNameW`), `RESTOR~1.TXT` refused). Each refusal checks: both manual modes and the automatic backup refuse and name it, no new zip, the old zip (`KEEP` 1) byte for byte, no temporary file. Before the fix: the new test file on the round-2 module failed 40 of 91 (some first on new names); the public-API reproduction showed the defect in all seven scenarios on the round-2 module (in a short path, both names' zip members held another file's content; in a deep path both names were published; `CON.md` published; `RESTOR~1.TXT` lost on unzipping; a backup that should have been refused deleted the only earlier zip), and in none on the current one. The permission test under `USERNAME=Administrator`: round 2's fails, round 3's passes.
    **第三轮的最终本地检查 / The third round's final local checks**（2026-11-20，Windows 11，Python 3.14.10，基于 `3b901d6` 的工作区 working tree on `3b901d6`；文档在检查之前已定稿 docs final before the checks）：`uv run pytest -q -rs` 1124 个通过、21 个跳过（全部是本机没有权限创建符号链接的测试 all symlink tests lacking the local privilege）；Edge 157.0.4341.60 浏览器分片 browser shards 1/3、2/3、3/3 各 101 个通过 101 passed each；`--notes-closed` 组 22 个通过 22 passed；`test_reference_nav.py --notes-closed` 48 个通过 48 passed；`ruff check .`、`ruff format --check .`、`git diff --check` 通过 pass。没有 CI（未推送）no CI (not pushed)。2 GB 测量 measurement：首次备份 first backup 4.5 秒 s，没有改变 unchanged 1.7–1.8 秒 s，同大小同时间的一个改动 one same-size, same-time change 1.9 秒 s（副本正确 copy correct），工作集峰值 working-set peak 约 about 31 MiB：扩展长度路径没有可测的开销 no measurable cost from extended-length paths。证据 Evidence：`.cache/m7.1-evidence/s2/round3/`（第二轮的模块和测试、新测试在其上的运行、独立复现及两个版本的结果、权限测试在不同 `USERNAME` 下的对比、测量、最终检查的日志 round 2's module and tests, the new tests on it, the standalone reproduction and both versions' results, the permission tests under different `USERNAME`s, the measurement, the final-gate logs）。
  - **Codex 第三次审查与第四轮修正 / Codex's third review and the fourth round's corrections**（结论：要求修改，两项，所有者接受，2026-11-23 verdict: request changes, two findings, accepted by the owner, 2026-11-23；只改 `scripts/folder_backup.py` 和测试 only `scripts/folder_backup.py` and the tests）：
    1. **书库自身路径的身份（高）/ The library's own path as its identity (High):** 两个不同的文件夹 `lib` 和 `lib.`（不同的 id、不同的 PDF、相同的显示名称）得到同一个备份身份：`libraries.info` 经由普通形式读取 `library.toml`，Windows 把 `lib.` 当作 `lib`，于是读到 `lib` 的 id；`libraries.scope` 的 `realpath` 同样把它变成 `lib`。备份 `lib.`（`KEEP` 1）删除了 `lib` 的 zip 并替换了它的 PDF 副本（已复现，三种方式都如此）。现在在计算身份、解析路径或创建任何东西之前，先检查书库文件夹和备份文件夹自身路径中的每个名字（`_check_own_path`，在 `_check_destination` 的最前面）：以点或空格结尾、设备名、不允许的字符都拒绝（`AmbiguousName`，说明哪个文件夹、怎样改名、在设置中重新选择）。不自动改名、不改 id；联接、链接和 8.3 短名照常可用（它们到达同一个文件夹）；长路径照常。锁、包含检查、备份名称和 PDF 文件夹都由同一个已检查的路径决定。Two distinct folders `lib` and `lib.` (different ids, different PDFs, the same display name) got one backup identity: `libraries.info` read `library.toml` through the ordinary form, where Windows takes `lib.` for `lib`, so it read `lib`'s id; `libraries.scope`'s `realpath` made it `lib` too. Backing up `lib.` (`KEEP` 1) deleted `lib`'s zip and replaced its PDF copy (reproduced, in all three ways). Now every name in the library folder's and the backup folder's own paths is checked (`_check_own_path`, first in `_check_destination`) before the identity is computed, any path is resolved or anything is created: a trailing dot or space, a device name or a character Windows doesn't allow is refused (`AmbiguousName`, naming the folder and saying how to rename it and choose it again in Settings). Nothing is renamed and no id changes; junctions, links and 8.3 short names work as before (they reach the same folder); long paths too. The lock, the containment check, the backups' names and the PDF folder all follow from the same checked path.
    2. **发布之前检查 PDF（中）/ The PDFs checked before publication (Medium):** `books/NUL.pdf` 在新 zip 发布、保留规则删除旧 zip 之后才被发现（已复现）。现在操作的顺序是（`_back_up`）：先检查两个路径、拿锁；在锁内先完整地列出并检查要备份的一切（有 PDF 副本时包括全部 PDF，`_library_pdfs`/`_take_inventory`，文件在列出时消失则最多重列 `TRIES` 次）；然后判断改变；写入、读回并以不覆盖的方式发布 zip；复制 PDF；**只有全部成功后**才删除旧 zip。不能保留的 PDF 名字或列不出的 PDF 文件夹在备份文件夹中任何东西改变之前拒绝整个备份（不再在 zip 之后才报告，也不会少列）。之后的复制失败（磁盘已满等）仍让新 zip 留下，但消息说明保存了什么、复制了几个、哪些没有备份、没有删除旧 zip。不备份 PDF 时（`backup_pdfs` 关闭），PDF 的名字不影响 zip。`books/NUL.pdf` was found only after the new zip was published and retention had deleted the old one (reproduced). The order is now (`_back_up`): both paths checked and the lock taken; then, under the lock, everything to back up listed and checked in full (all the PDFs too when they're copied: `_library_pdfs`/`_take_inventory`; a file gone while listed means listing again, at most `TRIES` times); then what changed; then the zip written, read back and published without replacing anything; then the PDFs copied; and **only when all of that succeeded** are old zips deleted. A PDF name that can't be kept or a PDF folder that can't be listed refuses the whole backup before anything in the backup folder changes (no longer reported after the zip, and never a shorter list). A copy failing afterwards (a full disk) still lets the new zip stand, but the message says what was saved, how many were copied, which weren't, and that no old zip was deleted. Without PDF copies (`backup_pdfs` off), PDF names don't affect the zip.
    **第四轮验证 / Fourth-round verification:** `tests/test_folder_backup.py` 共 99 个测试（之前的全部保留，其中两个改为新的顺序：读不了的 PDF 文件夹和 `NUL.pdf` 现在在写入任何东西之前拒绝整个备份）；新增：`lib.`、`lib ` 和 `parent./lib` 与 `lib` 并存（不同 id、PDF，相同名称，`KEEP` 1，两种手动方式和自动备份，备份文件夹中的一切逐字节不变）；以点结尾的备份文件夹；指向书库的联接照常；`NUL.pdf` 加一个改动的笔记（两种手动方式和自动备份，一切逐字节不变，原因正确）；发布之后的复制失败（消息准确，不删除旧 zip，之后成功时照常保留）；列出时消失的文件重列。99 tests in `tests/test_folder_backup.py` (every earlier one kept; two now expect the new order: an unreadable PDF folder and `NUL.pdf` refuse the whole backup before anything is written); new: `lib.`, `lib ` and `parent./lib` beside `lib` (different ids and PDFs, the same name, `KEEP` 1, both manual ways and the automatic backup, everything in the backup folder byte for byte unchanged); a backup folder ending in a dot; a junction to the library still works; `NUL.pdf` with a changed note (both manual ways and the automatic backup, everything byte for byte, the right reason); a copy failing after publication (an accurate message, no old zip deleted, retention as usual once it succeeds); a file gone while listed is listed again.
    **修复前 / Before the fix:** 只用公开接口的复现（`.cache/m7.1-evidence/s2/round4/reproduce_round4.py`，每种方式各自从新的状态开始）：在第三轮的模块上，六次运行全部出现缺陷——`lib.` 的三种备份方式都删除了 `lib` 的 zip 并改变了它的 PDF 副本；`NUL.pdf` 的三种方式都删除了之前唯一的 zip；当前模块上六次都拒绝，备份文件夹逐字节不变。新测试文件在第三轮模块上 99 个中 8 个失败，都是行为上的失败。The public-API reproduction (`.cache/m7.1-evidence/s2/round4/reproduce_round4.py`, each way from a fresh state): on the round-3 module all six runs showed the defect—all three ways of backing up `lib.` deleted `lib`'s zip and changed its PDF copy; all three ways with `NUL.pdf` deleted the only earlier zip; on the current module all six refuse and the backup folder is byte for byte unchanged. The new test file on the round-3 module: 8 of 99 fail, all on behaviour.
    **第四轮的最终本地检查 / The fourth round's final local checks**（2026-11-23，Windows 11，Python 3.14.10，基于 `3b901d6` 的工作区 working tree on `3b901d6`；代码和文档在检查之前已定稿 code and docs final before the checks）：备份相关的测试 backup-related tests（`test_folder_backup.py`、`test_libraries.py`、`test_note_assets.py`、`test_references.py`、`test_reading_status.py`、`test_test_library.py`）358 个通过、6 个跳过（符号链接 symlinks）、1 个失败 failed：`test_references.py` `test_the_endpoint_needs_the_key_and_a_small_body`，即已知的间歇失败 B38（见第 11 节；S2 没有改动这条路径，没有为了通过而重跑 the known intermittent B38, see section 11; S2 doesn't touch that path; not rerun to get a pass）；`test_folder_backup.py` 本身 99 个全部通过 itself all 99 passed；`uv run pytest -q -rs` 1132 个通过、21 个跳过（全部是本机没有权限创建符号链接的测试 all symlink tests lacking the local privilege）；Edge 157.0.4341.60 浏览器分片 browser shards 1/3、2/3、3/3 各 101 个通过 101 passed each；`--notes-closed` 组 22 个通过 22 passed；`test_reference_nav.py --notes-closed` 48 个通过 48 passed；`ruff check .`、`ruff format --check .`、`git diff --check` 通过 pass。没有 CI（未推送）no CI (not pushed)。2 GB 测量 measurement：首次备份 first backup 4.5 秒 s，没有改变 unchanged 1.9–2.1 秒 s，同大小同时间的一个改动 one same-size, same-time change 2.1 秒 s（副本正确 copy correct），工作集峰值 working-set peak 约 about 31 MiB：先列出 PDF 没有可测的开销 no measurable cost from listing the PDFs first。证据 Evidence：`.cache/m7.1-evidence/s2/round4/`（第三轮的模块和测试、新测试在其上的运行、独立复现及两个版本的结果、测量、最终检查的日志 round 3's module and tests, the new tests on it, the standalone reproduction and both versions' results, the measurement, the final-gate logs）。
  - **CI 记录 / CI record:** 提交 commit `e28bf18aa9cd5bafeb121514b5bf6e48bf75f78b`（`main` 与 `origin/main` 相同 equal to `origin/main`），GitHub Actions 运行 run 45155217482，第 1 次尝试 attempt 1，结论 conclusion success，五个作业全部通过 all five jobs passed：test（Python 测试和 Ruff：1,145 个通过、8 个跳过，8 个都是 `tests/test_formula_ocr.py` 因可选的公式识别模型没有安装而跳过 1,145 passed, 8 skipped, all eight in `tests/test_formula_ocr.py` because the optional formula-OCR model isn't installed；`MYLIBRARY_REQUIRE_LINK_TESTS=1`：要求运行的 Windows 符号链接和联接测试都已运行并通过，没有一个跳过 the required Windows symlink and junction tests ran and passed, none skipped）、浏览器分片 browser shards 1/3、2/3、3/3、笔记面板关闭 notes panel closed。没有重跑 no reruns。
  - **限制 / Limitations:** 备份不是书库在某一时刻的一致快照（L31(7) 不变，所有者接受：制作 zip 时改动的笔记可能是改动前或改动后的内容）。被强行中断（断电、结束进程）时可能留下以点开头的 `.part` 临时文件；它们不是备份、不会被当作备份，也不被自动清理；锁标记文件 `.myLibrary-backup.lock` 留在备份文件夹中。PDF 被保存而同时比较“相同”时，结果对应比较时的内容。不在同一台计算机上的两个进程经由网络共享备份到同一文件夹时，锁依赖网络文件系统对字节范围锁的支持（未测试）；不支持硬链接的非 Windows 驱动器（FAT）上，不覆盖的命名靠持有锁时的检查。悬空的链接或联接、列不出的文件夹使备份失败，直到用户修好或移走它们。名称规则在所有系统上都检查（备份可能在 Windows 上恢复）；被拒绝的名字在用户改名之前一直阻止备份；以点或空格结尾的名字在资源管理器中通常无法改名，需要在终端中用 `\\?\` 路径改名；少数合法的名字（如 `draft~2.md`）因形如短名而被拒绝。书库文件夹和备份文件夹自身路径中的名字按第四轮检查（不检查短名形状）；其中有问题的名字使备份失败，直到用户改名并在设置中重新选择。只有备份检查书库自身的路径：应用的其他部分仍经由普通形式打开像 `lib.` 这样的文件夹（不在 S2 范围内）。Unicode 的等价形式（NFC/NFD）不检查。冷缓存或 U 盘上的时间没有测量。The backup is not a consistent snapshot of the library at one instant (L31(7) unchanged, accepted by the owner: a note changed while zipping may be in its old or new state). A hard interruption (power loss, a killed process) can leave dot-named `.part` temporary files; they're never backups, never taken for one, and aren't cleaned up automatically; the lock's marker file `.myLibrary-backup.lock` stays in the backup folder. A PDF saved while being compared as "the same" is judged by its content at the comparison. Two processes on different computers backing up to one folder over a network share rely on the network file system's byte-range locks (untested); on a non-Windows drive without hard links (FAT), never-replacing names rely on a check made while holding the lock. A dangling link or junction, or a folder that can't be listed, fails the backup until the user fixes or moves it. The name rules are checked on every system (a backup may be restored on Windows); a refused name blocks backups until the user renames it; a name ending in a dot or space usually can't be renamed in File Explorer and needs a terminal with the `\\?\` path; a few legitimate names (like `draft~2.md`) are refused for having the shape of a short name. Names in the library folder's and the backup folder's own paths are checked as in round 4 (short-name shapes excepted); a problem there fails the backup until the user renames the folder and chooses it again in Settings. Only the backup checks the library's own path: the rest of the app still opens a folder like `lib.` through the ordinary form (outside S2). Unicode equivalents (NFC/NFD) aren't checked. Times on a cold cache or a USB stick were not measured.

**已修复的安全问题 / Fixed security issue**
- **FA-02**（C，安全 security，Codex M7 后审计 post-M7 audit，2026-11-18，M7.1 S1c）书库页面把书库名称作为脚本运行 / The library page ran a library's name as script.
  已修复，Codex 独立审查通过（无阻塞问题）；提交 `17e8d77`，已推送；它自己的 CI 运行 44703480992 第 1 次尝试失败（浏览器分片 1，B39，与 S1c 无关，没有重跑），经其后代提交 `3b901d6` 的运行 44722195750 第 1 次尝试通过 CI（五个作业）。Fixed and approved by Codex's independent review (no blocking findings); commit `17e8d77`, pushed; its own CI run 44703480992 attempt 1 failed (browser shard 1, B39, unrelated to S1c; not rerun); CI-verified through its descendant commit `3b901d6`, run 44722195750, attempt 1 (all five jobs).
  - **已确认 / Confirmed:** `library_page.render` 把服务器的 API 数据（含书库名称：`library.toml` 的 name 或登记的标签，`libraries.current`）原样 `json.dumps` 后放进 `<script>`；名称中的 `</script><script>…` 结束了脚本元素并作为脚本运行。其他嵌入的值只替换了 `</`（`<!--<script>` 仍可能使页面的脚本失效），而且四个占位符依次替换：已插入的书名或标签中的占位符文字会被再次替换（B14 的一项）。复现（临时数据）：名称中的脚本插入页面，在 Edge 中运行。"
  "`library_page.render` embedded the server's API data (with the library's name: `library.toml`'s name or a registered label, `libraries.current`) as plain `json.dumps` inside a `<script>`; a name containing `</script><script>…` ended the script element and ran as script. The other embedded values only had `</` replaced (`<!--<script>` could still break the page's script), and the four markers were replaced one after another, so a marker's text in an already-inserted title or label was substituted again (one of B14's items). Reproduced (synthetic data): the name's script was inserted into the page and ran in Edge.
  - **修复 / Fix:** 页面嵌入的四个值（书目数据、API 数据、书架标签、学位标签）都经由 `library_page.script_json`：JSON 中的 `<`、`>`、`&`、U+2028、U+2029 写成 `\u003c` 等转义（JSON 在字符串之外不会有这些字符，所以值不变，页面解码后与原文完全相同）；四个占位符用一次替换完成（`MARKERS`），插入的值不会再被替换。不限制、不改写书库名称；页面上显示名称和标签的地方原本就用 `esc()` 或 `textContent`。另一个服务器生成的页面（PDF.js 查看器）只嵌入服务器令牌和十六进制的范围键，不含用户的文字。"
  "All four values the page embeds (the catalog data, the API data, the shelf labels, the degree labels) go through `library_page.script_json`: `<`, `>`, `&`, U+2028 and U+2029 in the JSON are written as `\u003c` and the like (JSON never has them outside a string, so no value changes: the page decodes exactly the original text); the four markers are replaced in one pass (`MARKERS`), so an inserted value is never substituted again. Library names are neither restricted nor rewritten; where the page shows names and labels it already used `esc()` or `textContent`. The only other server-generated page (PDF.js's viewer) embeds just the server's token and a hexadecimal scope key, no user text.
  - **验证 / Verification:** `tests/test_library_page_render.py`（21 个：审计的载荷不结束脚本、不增加元素；十种敌意文字（大小写混合的结束标签、`<!--<script>`、引号和反斜杠、`&`、中文和希腊文、U+2028/U+2029、占位符文字、空白）在 API 数据、书目数据和书架标签中解码后完全相同，嵌入的文字中没有 `<`；占位符文字不被替换；静态副本 `API = null`；`script_json` 往返）。`tests/browser/test_library_rendering.py`（3 个，真实服务器、临时书库、只允许访问测试服务器：`library.toml` 名称、书架标签和书名中的载荷不运行，页面照常绘制卡片，名称和标签完全相同，页面令牌的请求仍成功、没有令牌的仍是 403，没有页面错误；登记的标签中的载荷不运行，书库列表把它显示为文字；普通的中文、希腊文和引号名称照常可用）。"
  "修复前：独立复现中脚本元素被插入；渲染测试 17 个失败（4 个只检查普通值的两边都通过）；浏览器中名称的脚本运行（`window.__fa02` 为 731，登记标签的 `onerror` 为 2），普通名称的测试两边都通过。修复后全部通过。"
  "`tests/test_library_page_render.py` (21 tests: the audit's payload neither ends the script nor adds an element; ten hostile texts (mixed-case closing tags, `<!--<script>`, quotes and backslashes, `&`, Chinese and Greek, U+2028/U+2029, marker text, whitespace) decode exactly in the API data, the catalog data and the shelf labels, with no `<` in what is embedded; marker text is never substituted; the static copy has `API = null`; `script_json` round trips). `tests/browser/test_library_rendering.py` (3 tests on a real server with a temporary library, only the test server reachable: the payload in `library.toml`'s name, a shelf label and a title doesn't run, the page draws its cards as usual, the name and labels are exact, a request with the page's token still succeeds and one without is still 403, no page errors; a registered label's payload doesn't run and the library list shows it as text; an ordinary Chinese, Greek and quoted name works as before). Before the fix: the standalone reproduction inserted the script element; 17 renderer tests failed (the 4 that check only plain values passed on both); in the browser the name's script ran (`window.__fa02` was 731, the registered label's `onerror` 2), and the ordinary-name test passed on both. After it, all pass.
  - **限制 / Limitations:** 没有增加内容安全策略（CSP），也没有改变页面其他部分的结构；B14 的其余各项不变。"
  "No content security policy was added and nothing else in the page's structure changed; B14's other items are unchanged.

**已修复的数据完整性问题 / Fixed data-integrity issue**
- **FA-01**（C，数据安全 data safety，Codex M7 后审计 post-M7 audit，2026-11-18，M7.1 S1b）“清空归档”在 archive/ 本身是联接或链接时会删除书库以外的文件 / "Clear archive" deleted files outside the library when archive/ itself was a junction or link.
  已修复，Codex 独立审查通过（无阻塞问题；所有者接受 L31(8) 的限制）；提交 `0a078ad`，已推送；CI 运行 44521803189：第 1 次尝试两个浏览器分片失败（各一个与 S1b 无关的超时：B39、B40），经所有者批准只重跑失败的作业一次，第 2 次尝试五个作业全部通过（Python 作业中必须运行的链接测试已运行，没有被跳过）。重跑只说明这两个失败是间歇的，不说明原因。Fixed and approved by Codex's independent review (no blocking findings; the owner accepts the L31(8) limitation); commit `0a078ad`, pushed; CI run 44521803189: attempt 1 failed two browser shards (one timeout each, unrelated to S1b: B39, B40); with the owner's approval only the failed jobs were rerun, once; attempt 2: all five jobs passed (the mandatory link tests ran in the Python job, none skipped). The rerun shows only that these two failures are intermittent, not why.
  - **已确认 / Confirmed:** `library_jobs._archive_walk` 从 archive/ 开始遍历，只检查其中的项目是不是链接；`_archive_plan` 用跟随链接的 `is_dir` 接受了被重定向的根目录，`clear_archive` 随后删除计划中的文件。复现（临时文件夹）：archive/ 是指向书库外文件夹的联接时，那里的 PDF 被删除。"
  "`library_jobs._archive_walk` started at archive/ and checked only what was inside it for links; `_archive_plan` accepted a redirected root through `is_dir` (which follows links), and `clear_archive` then deleted the planned files. Reproduced (temporary folders): with archive/ a junction to a folder outside the library, a PDF there was deleted.
  - **修复 / Fix:** `library_jobs._checked_archive` 在读取或删除任何内容之前检查 archive/ 本身：必须是书库真实文件夹中名为 archive 的普通文件夹（书库文件夹本身可以经由链接或联接到达）；链接、联接、其他指向别处的重解析点（名称代理标签）、不是文件夹、真实位置不对、无法解析（循环、悬空）都被拒绝（`UnsafeArchive`，中英文说明），什么也不删除；不存在时为空，不创建。删除时还拒绝受保护的书库（`safe_io._refuse_frozen`）。archive/ 里面的链接和联接照旧不跟随、保留，现在也包括其他指向别处的重解析点。删除之前，所有计划中的文件再检查一次（仍是普通文件，经由普通文件夹到达，真实位置就是计划的位置），有一个不符就整体拒绝；每个文件和空文件夹在删除前再检查一次。服务器 `/api/archive` 回答 409 和说明；设置对话框显示说明并禁用“清空归档”，其余设置照常可用（`library_page.py`）。没有命令行入口（只有服务器路由调用它）。B13（保留原始 PDF）不在本次范围（S4）。"
  "`library_jobs._checked_archive` checks archive/ itself before anything in it is read or deleted: it must be the plain folder named archive in the library's real folder (the library folder itself may be reached through a link or junction); a link, junction, other redirecting reparse point (a name-surrogate tag), something not a folder, a real location elsewhere, or one that can't be resolved (a loop, a dangling link) is refused (`UnsafeArchive`, with a bilingual explanation) and nothing is deleted; an absent archive is empty and is not created. Clearing also refuses a frozen library (`safe_io._refuse_frozen`). Links and junctions inside archive/ are still never followed and are kept, now also other redirecting reparse points. Before anything is deleted, every planned file is checked again (still a plain file, reached through plain folders, its real location the planned one); one that isn't refuses the whole clearing; each file and empty folder is checked once more right before it is removed. The server's `/api/archive` answers 409 with the explanation; the Settings dialog shows it and disables Clear archive, and the rest of Settings stays usable (`library_page.py`). There is no command-line entry point (only the server route calls it). B13 (keeping original PDFs) is out of scope (S4).
  - **验证 / Verification:** `tests/test_archive_boundary.py`（16 个，本地无权限创建符号链接时跳过 3 个，CI 要求运行）：普通清空；不存在的 archive/；archive/ 是联接或符号链接（书库外的文件夹，以及指回书库里的文件夹）；悬空链接；名为 archive 的文件；设在书库外的 archive；受保护的书库（直接和经由联接）；嵌套的联接、符号链接和悬空链接；经由联接到达的书库正常清空；计划之后 archive/ 或计划中的文件夹被换成联接；经由 HTTP 的设置请求得到 409。书库外的哨兵文件逐字节不变。"
  "修复前：独立复现脚本中书库外的 PDF 被删除，新测试中 9 个失败（4 个守护原有行为的测试两边都通过）；修复后：复现脚本中什么都没变，全部通过。设置对话框在浏览器中手动检查（临时书库，Edge）：被拒绝时显示中英文说明并禁用按钮，普通的 archive 正常清空，没有页面错误。"
  "`tests/test_archive_boundary.py` (16 tests; 3 symlink cases skipped locally without the privilege, required in CI): ordinary clearing; an absent archive/; archive/ a junction or symlink (to a folder outside the library, and back into it); a dangling link; a file named archive; an archive set outside the library; a frozen library (directly and through a junction); nested junctions, symlinks and dangling links; a library reached through a junction cleared normally; archive/ or a planned folder replaced by a junction after planning; the Settings request over HTTP answered 409. Sentinel files outside the library stay byte-identical. Before the fix, a standalone reproduction deleted the PDF outside the library and 9 of the new tests failed (the 4 that guard existing behaviour passed on both); after it, the reproduction changes nothing and all pass. The Settings dialog was checked by hand in the browser (a temporary library, Edge): refused, it shows the bilingual explanation and disables the button; a plain archive is cleared as before; no page errors.
  - **限制 / Limitations:** 这些检查针对磁盘上已有的状态和合作的操作；另一个程序在两次检查之间换入再换回文件夹（毫秒级）仍不能防止（与 L31(8) 相同的威胁模型）。删除中途的普通 I/O 失败不会恢复已删除的文件。设置对话框的 JavaScript 没有自动化测试（手动检查）。"
  "The checks cover what is already on disk and cooperating operations; another program swapping a folder in and back between two checks (milliseconds) is still not prevented (the same threat model as L31(8)). An ordinary I/O failure partway through clearing doesn't restore files already deleted. The Settings dialog's JavaScript has no automated test (checked by hand).

**已修复的数据完整性问题 / Fixed data-integrity issue**
- **FA-03**（C，数据完整性 data integrity，Codex M7 后审计 post-M7 audit，2026-11-18，M7.1 S1a）合并重复项时，并发的笔记保存在被确认后被覆盖 / Merging a repeated document overwrote a note save that had already been acknowledged.
  已修复（含 Codex S1a 四轮审查的十个问题），Codex 复审通过；提交 `6912bbd`，已推送，CI 运行 44505418465 第 1 次尝试五个作业全部通过（Python 测试和 Ruff 中链接测试必须运行，未被跳过）。Fixed, including the ten findings of Codex's four S1a reviews, and approved by Codex's re-review; commit `6912bbd`, pushed; CI run 44505418465, attempt 1, all five jobs passed (the Python and Ruff job requires the link tests: they ran, none skipped).
  - **已确认 / Confirmed:** `add_book.merge_into` 判断保留副本的章节笔记“仍是模板”，然后不加锁地写入；笔记面板的保存（`notes_store.save`）不与它共用锁。Codex 的审查又确认了：被合并掉的文档的笔记在合并读取之后或归档期间仍能被保存；README 的写入者在不同的路径写法下不共用锁；README 链接的笔记名和副本名没有检查是否留在笔记文件夹内；没有链接时会把以前的 `-from-` 副本当作章节笔记。复审又确认：退出标记只在锁内检查，已通过检查、尚未发布的写入（已有笔记、新笔记、图片）不被等待；墓碑写入失败时标记不被清除，回滚不完整时文档却被重新打开；服务器把被合并文档的 id 跟随到保留的文档，所以旧标签页的保存、覆盖和图片会写进保留的文档。`merge_into` decided the kept copy's chapter note was still a template, then wrote it without a lock the notes panel's save (`notes_store.save`) shared. Codex's review confirmed: the merged-away document's notes could still be saved after the merge read them or while they moved to archive/; README writers didn't share a lock across spellings of the path; README-linked note names and copy names weren't checked to stay in the notes folder; without a README link, an earlier `-from-` copy could be taken for the chapter's note. The re-review confirmed: the leaving mark was checked only under the lock, so a write past its checks but not yet published (an existing note, a new note, an image) wasn't waited for; a failed tombstone write left the mark set, while an incomplete rollback reopened the document; and the server followed a merged document's id to the kept one, so a stale tab's save, overwrite or image went into the kept document. 第三轮确认：410 之后，被合并文档的恢复草稿仍以原文档的 id 保存，在保留的文档里找不到，也无法有意识地恢复。The third review confirmed: after a 410, the merged document's recovery draft stays under the original document's id, so the document that stays neither finds it nor lets the user restore it deliberately. 第四轮确认：草稿的清理按存储键删除，不核对内容：另一个标签页在同一个键下写入的更新的草稿会被较早的恢复删掉（确认、相同内容、过时的行、丢弃都如此）；清理按修订号而不是按实际保存的内容：恢复的文字在保存之前被替换，原草稿仍被删掉。The fourth review confirmed: draft cleanup deleted by storage key without checking content, so a newer draft another tab wrote under the same key was deleted by an older recovery (on confirmation, the identical-content shortcut, a stale row and discard alike); and cleanup followed revision order, not the content actually saved: a restored text replaced before it was saved still deleted the original.
  - **修复 / Fix:**
    - **一把锁 / One lock per file:** `safe_io.lock_for` 按真实路径取锁（链接和联接都跟随），同一个 README 或笔记的所有合作写入者（勾选、阅读位置、状态、面板、合并）都用同一把锁（`notes_store.note_lock` 就是它）。`safe_io.lock_for` keys on the real path (links and junctions followed), so every cooperating writer of the same README or note (ticks, reading position, status, the panel, merges) shares one lock (`notes_store.note_lock` is it).
    - **写入准入 / Write admission:** 文档自己笔记的每次写入（笔记保存、粘贴的图片）从第一次检查到发布都在 `notes_store.admitted` 之内。合并读取之前、删除移动之前，`begin_retiring` 先关闭准入，再等待已准入的写入全部完成（不持有任何笔记锁；登记处的锁不在等待笔记锁时持有；`DRAIN_SECONDS` 只是防止程序错误的上限：超时则重新打开、什么都不移动）。之后的写入被拒绝（`Retiring`）。Every write into a document's own notes (a note save, a pasted image) runs inside `notes_store.admitted` from its first check to its publication. Before a merge reads the notes and before a removal moves anything, `begin_retiring` closes admission, then waits until every admitted write has finished (holding no note lock; the registry's lock is never held while a note lock is awaited; `DRAIN_SECONDS` only bounds a bug: on timeout admission reopens and nothing moves). Later writes are refused (`Retiring`).
    - **失败处理 / Failures:** 墓碑写入（`catalog.retire`）在清理范围内：失败时什么都没改，重新打开准入。移动或删除目录行失败时回滚；只有确认每个原件都回到原处、归档的副本不在了、墓碑已撤回，才重新打开；否则文档保持关闭并打印警告。合并本身失败（它只复制，不改被合并的文档）或删除在移动之前失败时也重新打开。The tombstone write (`catalog.retire`) is inside the clean-up: if it fails nothing changed and admission reopens. If a move or the catalog removal fails, it is rolled back; admission reopens only once every original is verified back, its archived copy gone and the tombstone taken back; otherwise the document stays closed and a warning is printed. A failing merge (it only copies, never changes the merged document) or a removal failing before anything moves reopens it too.
    - **请求中的文档 / The document named:** `/api/notes/save` 和 `/api/notes/asset` 只写入请求所指的那份文档：被合并掉的 id 回答 410（附上保留它的文档 `into`），不跟随到保留的文档（`library_server.merged_away`）；检查之后才离开的文档同样 410；`Retiring` 也是 410。笔记面板把 410 当作不能再保存：不重试，文字留在编辑器和恢复草稿里，提示“已合并或已移除”，并提供“打开保留的文档”和“另存为文件”（`note_session.js`、`notes.js`）。“保留副本”（keep-copy）不变。`/api/notes/save` and `/api/notes/asset` write only into the very document the request names: a merged id gets 410 (naming the document that kept it, `into`), never followed to the kept document (`library_server.merged_away`); a document that left after the check gets 410 too, as does `Retiring`. The notes panel treats 410 as "can't be saved here any more": not retried, the text stays in the editor and a recovery draft, it says the document was merged or removed, and offers "Open the document that stays" and "Save as a file" (`note_session.js`, `notes.js`). Keep-copy is unchanged.
    - **草稿的交接 / Draft handoff:** 草稿始终保存在它被输入时的文档和笔记之下（从不改名、移动或因恢复而删除）。保留的文档打开笔记面板时，只读的 `/api/document/status` 告诉页面哪些草稿属于已合并到这里的文档，面板列出它们（`#mlElsewhere`）：只有用户点击“恢复”并选择目标笔记（默认同名笔记）才会恢复（`NoteSession.adoptDraft`）；目标笔记有自己未保存的文字、冲突、失败或草稿时拒绝。恢复绑定在列出时草稿的确切存储字符串上：点击时重新读取，若已被另一个标签页改写则什么也不恢复并重新列出。版本相同时立即保存这一快照；不同就是常规的冲突（“保留我的版本”先把笔记存进 archive/notes-conflicts/）。只有服务器确认保存的文字与恢复的快照完全相同，才把原草稿记为“已处理”；先被修改或替换、选择磁盘版本、保存失败或重新载入，原草稿都继续提供。“已处理”从不是删除：只写一个绑定该确切字符串的标记（`drafts.settle`，一次写入，没有先检查再删除）；之后在同一个键下写入的更新草稿与标记不符，所以照样提供。相同内容的捷径和丢弃（包括过时的行）也只写这样的标记。已移除且没有保留文档的草稿可以另存为文件（浏览器下载，不经服务器）；丢弃需要确认。A draft always stays under the document and note it was typed in (never renamed, moved, or deleted by a recovery). When the document that stays opens its notes panel, the read-only `/api/document/status` tells the page which drafts belong to documents merged into it, and the panel lists them (`#mlElsewhere`): one is restored only when the user clicks Restore and chooses the destination note (the note of the same name is proposed) (`NoteSession.adoptDraft`); a destination with unsaved text, a conflict, a failure or a draft of its own is refused. A restore is bound to the draft's exact stored string as listed: it is read again on the click, and if another tab rewrote it nothing is restored and the list is refreshed. The same version saves that snapshot at once; another is the usual conflict ("Keep mine" first keeps the note in archive/notes-conflicts/). Only when the server confirms a save of exactly the restored snapshot is the original marked as dealt with; edited or replaced first, the disk version chosen, a failed save or a reload all leave it offered. Dealt with is never a deletion: one write records a marker bound to that exact string (`drafts.settle`; no check followed by a delete), so a newer draft written under the same key since doesn't match it and is still offered. The identical-content shortcut and discard (a stale row too) only write such a marker. A removed document's draft with nowhere to go can be saved as a file (a browser download; nothing sent to the server); discarding asks first.
    - **只在文件夹内写 / Containment** 与 **选择章节笔记 / Chapter note:** 与上一轮相同（`NAME_RE`、文件夹内、非链接、独占创建副本；README 链接，否则唯一的原有笔记，不猜）。As in the previous round (`NAME_RE`, in the folder, not a link, copies created exclusively; the README's link, else a single original note, never a guess).
  - **验证 / Verification:** 后端：`tests/test_merge_note_saves.py` 共 72 个测试（本地无权限创建符号链接时跳过 3 个，CI 要求运行）：已准入的写入在发布那一刻暂停（已有笔记、新笔记、图片；合并和单独删除；三种布局）；墓碑写入失败、合并失败、删除在移动之前失败、完全回滚后重新打开；PDF 移不回或墓碑撤不回时保持关闭；经由真实 HTTP 路由，被合并的 id 的保存、覆盖、新笔记、图片都得到 410（附 `into`），保留文档逐字节不变；`/api/document/status` 的结果且不写入。前端：`tests/browser/test_notes_retired.py`（10 个；其中 4 个，真实服务器：输入被合并文档的笔记、用服务器自己的“刷新”真实合并并退出、真实的 410、打开保留的文档、发现草稿并有意识地恢复到用户选择的笔记、保留文档已有的内容不变；冲突后取消、保存失败、重新载入后原草稿仍在；410 栏和已移除文档的另存为文件；另外 6 个针对清理：两个标签页，保存的确认被延迟时另一个标签页写入更新的草稿，它保留；恢复的文字在保存前被替换，原草稿保留；快照原样保存后原草稿被处理；相同内容（直接的，以及在读取期间被另一个标签页改写的）；过时的行恢复和丢弃都不影响更新的草稿）和 `test_notes_failures.py` 的 410 测试。失败在先的证据：在上一版 S1a 上，第二轮的新测试中 34 个失败（其中 3 个只因异常类型不同）；在第二轮代码上，第三轮的 4 个浏览器测试和状态测试都失败；在第三轮代码上，本轮 6 个清理测试中 5 个失败（更新的草稿或原草稿丢失），直接的相同内容测试两边都通过（它守护成功的清理）。重复运行：第二轮代码的后端测试连续 10 次通过（当时 62 个通过）；第三轮的 4 个浏览器测试连续 5 次通过；本轮 10 个浏览器测试连续 5 次通过。最终一次（本轮代码）：Python 全部 1005 通过、18 跳过；浏览器三个分片 99、99、99 通过（共 297，分区检查通过）；关闭笔记面板 22 和 48 通过；Ruff 和 `git diff --check` 干净。Backend: `tests/test_merge_note_saves.py`, 72 tests (3 symlink cases skipped locally without the privilege; CI requires them): an admitted write paused at the moment it publishes (an existing note, a new note, an image; under a merge and a removal on its own; three layouts); reopening after a failed tombstone write, a failed merge, a removal failing before anything moves, and a complete rollback; staying closed when the PDF can't move back or the tombstone can't be taken back; over the real HTTP routes, a merged id's save, overwrite, new note and image all get 410 (with `into`), the kept document byte-identical; `/api/document/status`'s answers, writing nothing. Frontend: `tests/browser/test_notes_retired.py` (10 tests; 4 on a real server: typing in the merged copy's note, a real merge and retirement by the server's own Refresh, the real 410, opening the document that stays, finding the draft and restoring it deliberately into the note the user chooses, the kept document's existing content unchanged; the original draft still there after a cancelled conflict, a failed save and a reload; Save as a file from the 410 bar and for a removed document; and 6 on cleanup: two tabs, a newer draft written by the other tab while the save's confirmation is held, which survives; a restored text replaced before it is saved, the original kept; the unchanged snapshot saved, the original dealt with; identical content (plainly, and rewritten by the other tab while the note is read); a stale row's restore and discard leaving the newer draft alone) and the 410 test in `test_notes_failures.py`. Fail-before evidence: on the previous S1a version, 34 of the second round's new tests fail (3 only on the exception type); on the second round's code, the third round's 4 browser tests and the status test fail; on the third round's code, 5 of this round's 6 cleanup tests fail (a newer or the original draft lost), and the plain identical-content test passes on both (it guards the successful cleanup). Repeated runs: the second round's backend tests passed 10 times in a row (62 passing then); the third round's 4 browser tests passed 5 times in a row; this round's 10 browser tests passed 5 times in a row. Final run (this round's code): Python 1005 passed, 18 skipped; browser shards 99, 99 and 99 passed (297, partition check passed); notes panel closed 22 and 48 passed; Ruff and `git diff --check` clean.
  - **限制 / Limitations:** 锁和准入只在一个进程内（与其他锁一样）：命令行的 `add_book.py --remove` 在另一个进程里运行时，服务器看不到它；回滚不完整而保持关闭的文档，在服务器重新启动后会重新打开（需按警告手动修正）；外部编辑器不取这把锁（L14）；草稿只在这台电脑的这个浏览器里（localStorage，30 天后过期，与其他草稿一样）；被合并的文档在服务器重启前离开、而面板在另一个书库副本中打开时不会提供；已移除文档的草稿只在其他文档的面板里提供（它自己的页面已无法打开）；已处理的草稿和它的标记留在浏览器里，直到 30 天的过期（不删除才能不误删更新的草稿）；恢复后在保存之前改动了文字，原草稿会一直提供，需要用户自己丢弃；同一份文档自己的草稿（M4 的恢复和丢弃，另一个标签页的草稿）仍按存储键删除，不在本次范围内；README 的字节保留（行尾、BOM）仍是 S4（B25/B33）。Locks and admission are per process, like the others: `add_book.py --remove` run as a separate process isn't seen by the server; a document kept closed after an incomplete rollback opens again when the server restarts (put it right by hand, as the warning says); external editors don't take the lock (L14); drafts live only in this browser on this PC (localStorage, expiring after 30 days like any draft) and are offered only in the same library; a removed document's draft is offered only in other documents' panels (its own page can't be opened any more); a dealt-with draft and its marker stay in the browser until the 30-day expiry (not deleting is what keeps a newer draft safe); a restored text changed before it is saved leaves the original offered until the user discards it; a document's own drafts (M4's restore and discard of another tab's draft) are still removed by storage key, outside this change; README byte preservation (line endings, BOM) remains S4 (B25/B33).

**已修复的数据完整性问题 / Fixed data-integrity issue**
- **B29**（C，数据完整性 data integrity，2026-11-10）相同的 DOI 被当作同一个 PDF 的证明 / A shared DOI taken as proof of the same PDF.
  在提交 "Prevent DOI-based replacement and merging of different PDFs"（2026-11-10）中修复。Fixed in the commit "Prevent DOI-based replacement and merging of different PDFs" (2026-11-10).
  - **已确认 / Confirmed:** DOI 标识作品，不是某个 PDF；文章、补充材料、接受稿都可能印有文章的 DOI。用真实的添加任务复现：一个 20 页的补充材料（Crossref 按 DOI 给出文章的标题，标题检查通过）取代了 8 页文章的 PDF；刷新也会合并共享 DOI 的两个条目。A DOI names a work, not a PDF; an article, its supplementary material and its accepted manuscript can all print the article's DOI. Reproduced through the real add job: a 20-page supplement (Crossref giving it the article's title by the DOI, so the title check passed) replaced the 8-page article's PDF; Refresh would also merge two entries sharing a DOI.
  - **修复 / Fix** (`scripts/add_book.py`: `repeat_of`, `PROVEN`, `catalog_repeats`, `shared_doi`, `sharing_note`, `name_note`, `handle_repeat`/`find_repeat` 说明 docstrings; `scripts/library_jobs.py`: `_register`): 只有逐字节相同的文件才是重复；相同的 DOI（和 L21 的 ISBN）从不导致替换、归档、合并或退出文档身份，不论从页面、命令行、登记还是刷新进来。只共享 DOI 的 PDF 成为自己的文档，消息说明与哪个文档共享 DOI。缺失 PDF 的条目不再因 DOI 被重新连接。按 DOI 查找元数据、引用和搜索不变。`handle_repeat` 中替换的分支保留给以后用户确认的替换（任务 6），现在没有任何证据能到达它。Only a byte-identical file is a repeat; a shared DOI (and, from L21, ISBN) never causes a replacement, archiving, merge or retired identity, from the page, the command line, registration or Refresh. A PDF that only shares a DOI becomes a document of its own, and the message names the document it shares it with. An entry whose PDF is missing is no longer re-attached by DOI. DOI metadata lookup, citations and search are unchanged. `handle_repeat`'s replacement branch stays for a replacement the user confirms (task 6, later); no evidence reaches it now.
  - **有意的取舍 / Intentional trade-off:** 以前同一 DOI 的更好副本（例如有文字层的版本）会自动取代 PDF；现在没有任何自动替换，两者都保留，由用户决定（以后的任务 6）。PDF 缺失的条目**不能自动重新连接**，即使加入逐字节相同的文件也不行：没有可比较的文件，也没有保存这个文件的指纹（`.cache/` 中的哈希属于这台电脑，按路径和日期），所以它成为另一个文档，原条目继续等待（测试证实）。刷新只合并逐字节相同的文件。A better copy with the same DOI (e.g. a searchable version) used to replace the PDF automatically; now nothing is replaced automatically: both are kept for the user to decide (task 6, later). An entry whose PDF is missing **cannot be re-attached automatically**, not even by the byte-identical file: there is no file to compare with and no stored fingerprint of it (the hashes in `.cache/` are this computer's, by path and date), so the new file becomes another document and the entry keeps waiting (tested). Refresh merges only byte-identical files.
  - **验证 / Verification:** `tests/test_partial_pdf_repeats.py` 中 9 个 B29 测试（以前的严格 xfail 改为通过的回归测试：文章 + 补充材料、先补充材料后文章、页数相同的不同 PDF、有标注的文章、缺失的 PDF（包括逐字节相同的文件也不会重新连接）、逐字节相同的文件、两次刷新、DOI 元数据和引用），16 个 L21 测试仍通过；以前以 DOI 为证据的 13 个测试改为以相同文件为证据或断言分开保留（合并、记录和标注保护的机制照旧测试）；相关测试 241 个通过。Nine B29 tests (the former strict xfail now a passing regression test: article + supplement, supplement first, different PDFs of the same length, an annotated article, a missing PDF (not re-attached even by the byte-identical file), a byte-identical file, Refresh twice, DOI details and citations); the 16 L21 tests still pass; 13 tests that used a DOI as proof now use an identical file or assert that the documents are kept apart (the merge, records and marks machinery still tested); 241 related tests pass.
  - **限制 / Limitations:** 已经受影响的书库不会被修复；共享 DOI 的真正重复现在是两个文档，需要用户删除一个；🔎 在线查找按 DOI 把作品显示为"在书库中"（只是显示）。Libraries already affected aren't repaired; a true repeat sharing a DOI is now two documents for the user to remove one of; 🔎 Find online shows a work as "in your library" by DOI (display only).

**已修复的数据完整性问题 / Fixed data-integrity issue**
- **L21**（C，数据完整性 data integrity，2026-11-10）相同的 ISBN 被当作同一个 PDF 的证明 / A shared ISBN taken as proof of the same PDF.
  在提交 "Prevent ISBN-based replacement and merging of different PDFs"（2026-11-10）中修复。Fixed in the commit "Prevent ISBN-based replacement and merging of different PDFs" (2026-11-10).
  - **已确认 / Confirmed:** ISBN 标识出版物，不是 PDF 的内容范围。用书库页面真实的添加任务复现（临时书库、合成 PDF，只替换网络入口）：无标注的扫描书被单章或几章的 PDF 取代（页数 40 → 12 / 25）；章节 PDF 被悄悄移入 `archive/`；刷新把章节和整本书合并，保留章节、移走整本书；先章节后整本书时整本书取代章节。被取代的原件留在 `archive/` 中，但"清空归档"会删除归档中的 PDF。An ISBN names the publication, not what a PDF covers. Reproduced through the library page's real add job (temporary library, synthetic PDFs, only the network's door replaced): an unmarked scanned book replaced by a one- or several-chapter PDF (pages 40 → 12 / 25); chapter PDFs silently moved to `archive/`; Refresh merging a chapter with the book, keeping the chapter and moving the book away; the book replacing a chapter added first. Replaced originals stayed in `archive/`, but Clear archive deletes archived PDFs.
  - **修复 / Fix** (`scripts/add_book.py`, `scripts/library_jobs.py`): 相同的 ISBN 不再是重复的证明（`repeat_of`、`PROVEN`、`catalog_repeats`），只有相同的 DOI 或逐字节相同的文件才是；所以添加（页面和命令行）、`handle_repeat`、刷新都不会因 ISBN 而替换、归档或合并。只共享 ISBN 的新 PDF 成为自己的文档（自己的 UUID、笔记和进度），消息说明它与哪本书共享 ISBN、可能是其他章节、部分或版本（`add_book.shared_isbn`、`name_note`）。缺失 PDF 的记录不再因 ISBN 被重新连接。A shared ISBN is no longer proof of a repeat (`repeat_of`, `PROVEN`, `catalog_repeats`); only the same DOI or a byte-identical file is. So adding (page and command line), `handle_repeat` and Refresh never replace, archive or merge because of an ISBN. A new PDF that only shares an ISBN becomes a document of its own (its own UUID, notes and progress), and the message names the book it shares the ISBN with, as possibly other chapters, another part or edition (`add_book.shared_isbn`, `name_note`). An entry whose PDF is missing is no longer re-attached by ISBN.
  - **有意的兼容性取舍 / Intentional trade-off:** 以前同一 ISBN 的更好的完整副本（例如有文字层的版本代替扫描件）会自动取代 PDF；现在它作为第二个文档保留，由用户决定（以后的任务 6 中经用户确认的重复管理）；更好的副本有相同的 DOI 时照旧取代。在另一台电脑或恢复后重新加入缺失的 PDF也不再按 ISBN 自动连接（DOI 或相同的文件照旧）。A better complete copy with the same ISBN (e.g. a searchable version of a scan) used to replace the PDF automatically; it is now kept as a second document for the user to decide (user-confirmed duplicate management, task 6, later); a better copy with the same DOI still replaces it. Re-adding a missing PDF on another computer or after a restore no longer re-attaches by ISBN (by DOI or an identical file as before). **自 B29 起 / Since B29:** 相同的 DOI 也不再替换或重新连接 PDF；只有逐字节相同的文件才是重复（见 B29）。上面"DOI 或相同的文件照旧"中的"相同的文件"不准确：PDF 缺失时没有文件可比较，任何文件都不会自动重新连接。A shared DOI no longer replaces or re-attaches a PDF either; only a byte-identical file is a repeat (see B29). The "or an identical file as before" above was inaccurate: with the PDF missing there is nothing to compare, so no file re-attaches automatically.
  - **验证 / Verification:** `tests/test_partial_pdf_repeats.py`（16 个通过：上面的每种情况，加上相同页数的两个不同章节、缺几章的近乎完整的 PDF、两个不同的 30 页 PDF、有标注的书、页数未知的缺失 PDF、两次刷新、两个部分 PDF、命令行、逐字节相同的文件；每次都检查书的 PDF、目录行、笔记、章节映射、归档和墓碑不变）；更新了 4 个以前断言 ISBN 行为的测试（替换和标注保护改用 DOI 继续测试）；完整测试：533 个通过、9 个跳过，1 个失败（B30，在 `610c858` 上同样出现，与 L21 无关），所以完整测试**没有**全部通过；书库相关的浏览器测试通过。`tests/test_partial_pdf_repeats.py` (16 passing: every case above, plus two different chapters of equal length, a nearly complete PDF missing chapters, two different 30-page PDFs, a marked book, a missing PDF with an unknown page count, Refresh twice, two partial PDFs, the command line, a byte-identical file; each checking that the book's PDF, catalog row, notes, chapter mapping, archive and tombstones are unchanged); 4 older tests that asserted the ISBN behaviour updated (the replacement and marks protection still tested, by DOI); the full suite: 533 passed, 9 skipped, 1 failed (B30, also seen at `610c858`, unrelated to L21), so the full suite did **not** pass; the library browser tests pass.
  - **限制 / Limitations:** 已经受影响的书库不会被修复；同一 ISBN 的真正重复现在是两个文档，需要用户删除一个；🔎 在线查找按 ISBN 把书显示为"在书库中"（只是显示）。B29（DOI）未改。Libraries already affected aren't repaired; true repeats with one ISBN are now two documents for the user to remove one of; 🔎 Find online still shows a book as "in your library" by ISBN (display only). B29 (DOI) unchanged.

**已修复的安全问题 / Fixed security issue**
- **B28**（C，安全 security，2026-11-10）Windows 上经 `cmd.exe` 的命令注入 / Command injection through `cmd.exe` on Windows.
  在提交 "Fix Windows editor command injection in special-character paths"（2026-11-10）中修复。Fixed in the commit
  "Fix Windows editor command injection in special-character paths" (2026-11-10).
  - **已确认的漏洞 / Confirmed vulnerability:** Windows 运行批处理文件（`.bat`/`.cmd`）时经过 `cmd.exe`，它会解释参数中的
    `& | < > ^ % ! ( ) "`。用临时合成文件夹和模拟启动器复现：VS Code 的 `code.CMD` 收到没有空格的书库路径 `lib&ver` 时**执行了** `ver`，
    编辑器只收到 `…\lib`；`^` 被删除；`%OS%` 被展开，即使有引号。自定义编辑器是批处理文件时同样：`{file}` 不加引号时执行了注入的程序，
    `%` 总被展开。Windows runs a batch file through `cmd.exe`, which acts on `& | < > ^ % ! ( ) "` in
    its arguments. Reproduced with temporary synthetic folders and mock launchers: VS Code's
    `code.CMD` given the space-free library path `lib&ver` **ran** `ver` while the editor got only
    `…\lib`; `^` was removed; `%OS%` expanded, even inside quotes. A custom editor that is a batch
    file behaved the same: with `{file}` unquoted an injected program ran; `%` always expanded.
  - **修复 / Mitigations** (`scripts/platform_services.py`, `library_server.open_in_editor`):
    1. VS Code（`vscode_command`）：参数中有这些字符时，照 `code.CMD` 的做法但不经过 `cmd.exe`：`Code.exe` 运行 VS Code 的 `cli.js`
       （路径从 `code.CMD` 中读出），`ELECTRON_RUN_AS_NODE=1`，参数原样传入。从不把书库路径作为 `Code.exe` 的第一个参数（继承的
       `ELECTRON_RUN_AS_NODE=1` 会让它把文件夹当作 Node.js 程序运行）。找不到时用系统编辑器。VS Code (`vscode_command`): with such
       characters, what `code.CMD` does without `cmd.exe`: `Code.exe` runs VS Code's `cli.js` (its
       path read from `code.CMD`) with `ELECTRON_RUN_AS_NODE=1`, the arguments as they are. A
       library path is never `Code.exe`'s first argument (an inherited `ELECTRON_RUN_AS_NODE=1`
       would make it run the folder as a Node.js program). If they can't be found, the system editor.
    2. 自定义编辑器（`cmd_exe_risk`）：路径中有这些字符时，先像 `CreateProcess` 那样找出要运行的程序（引号中的第一部分，或不加引号时
       从短到长的每一段；去掉末尾的点和空格；没有扩展名时加 `.exe`；同样的搜索文件夹），只有原生的 `.exe`/`.com`（不是 `cmd.exe`，
       也没有被 `PATHEXT` 找到的同名批处理文件）才运行；批处理文件、`cmd.exe`、找不到的程序都不运行。Custom editors
       (`cmd_exe_risk`): with such characters in the path, the program is first found as
       `CreateProcess` finds it (the quoted first part, or unquoted each stretch shortest first;
       trailing dots and spaces dropped; `.exe` added without an extension; the same search
       folders); only a native `.exe`/`.com` runs (not `cmd.exe`, and no same-named batch file
       found through `PATHEXT`); a batch file, `cmd.exe` or a program that can't be found never runs.
    3. 不运行时：`.md` 用系统默认程序打开，`.py` 用记事本（从不用默认程序，那可能运行它）；服务器日志说明原因，不写路径。普通路径和原生程序
       照旧。When it doesn't run: a `.md` opens with its default app, a `.py` in Notepad (never its
       default app, which can run it); the server's log says why, without paths. Ordinary paths
       and native programs as before.
  - **验证 / Verification:** 回归测试 `tests/test_platform_services.py`（显式的 `.cmd`/`.bat`、经 PATH 和 PATHEXT 找到的、`{file}` 和自动附加、
    有无引号、`%`、末尾的点、含空格的程序路径、`cmd /c`、找不到的程序、安全的 `.exe`、`.md`/`.py` 的回退、真实进程中的注入和阻止、笔记不变、
    日志中没有路径）；真实 VS Code 在完全隔离的实例中验证（`R&D`、`书库&笔记`、`lib%OS%x` 正确打开，重用窗口，绊线未触发；用户的 VS Code
    数据没有使用）。Regression tests in `tests/test_platform_services.py` (explicit `.cmd`/`.bat`,
    found through PATH and PATHEXT, `{file}` and appended, quoted and unquoted, `%`, a trailing
    dot, a program path with spaces, `cmd /c`, a program not found, safe `.exe`s, the `.md`/`.py`
    fallbacks, a real-process injection and its prevention, the note unchanged, no paths in the
    log); the real VS Code verified in a fully isolated instance (`R&D`, `书库&笔记`, `lib%OS%x`
    open correctly, windows reused, no tripwire fired; the user's VS Code data not used).
  - **剩余限制 / Remaining limitations:** 用户自己配置的、会再把参数交给解释器的程序不在检查范围内：把参数转给 `cmd.exe` 的 `.exe`、
    改名的 `cmd.exe` 副本、`powershell -Command …`（PowerShell 有自己的语法）、`.md` 默认程序本身是批处理文件。macOS 和 Linux 没有这个机制。
    Programs the user configures that hand their arguments to an interpreter again aren't
    checked: an `.exe` that passes them to `cmd.exe`, a renamed copy of `cmd.exe`,
    `powershell -Command …` (PowerShell has its own syntax), a default `.md` app that is itself a
    batch file. macOS and Linux have no such mechanism.

---

## 12. 不计划 / Not planned

DjVu 或 EPUB；笔记本（notebook）；影子图书馆来源；书或书中文字进入 git；云托管、账户或订阅；强制使用 AI；替换 Python
后端或基于浏览器的界面（Electron、React、Qt 或原生界面只在有具体理由并经用户批准时）；内置 IDE；自动运行从文档中提取的
代码；复制 BookxNote、MarginNote 或 Zotero 的完整功能；取代 Zotero 的文献管理生态；应用内分析、云端遥测或强制账户；在 X1 之前承诺
macOS 支持。
DjVu or EPUB; notebooks; shadow-library sources; books or book text in git; cloud hosting,
accounts or subscriptions; mandatory AI; replacing the Python backend or the browser-based
interface (Electron, React, Qt or a native UI only with a specific reason and the user's
approval); a built-in IDE; running code extracted from documents automatically; copying the
full feature set of BookxNote, MarginNote or Zotero; replacing Zotero's reference-management
ecosystem; in-app analytics, cloud telemetry or mandatory accounts; promising macOS support
before X1.
