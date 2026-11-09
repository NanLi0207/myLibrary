# myLibrary

**myLibrary — 阅读、理解、实践、验证、掌握。**
**myLibrary — Read. Understand. Implement. Verify. Remember.**

一个将文档、笔记、知识与可执行代码连接起来的本地优先学习与研究工作空间。
A local-first learning and research workspace connecting documents, notes, knowledge and
executable code.

> **完整的使用说明 / The complete manual:** [docs/USER_GUIDE.md](docs/USER_GUIDE.md)（安装、每个功能、设置、命令、
> 常见问题 / installation, every feature, settings, commands, troubleshooting）。

---

## myLibrary 是什么 / What myLibrary is

用你自己的 PDF（书、论文、学位论文，任何学科）学习：在浏览器中的阅读器里读，查专业术语和生词，在 PDF 旁边用 Markdown 写笔记，
记录进度并复习。一切都在你自己的电脑上，在你自己的文件夹里。三个支柱是**学习、阅读和笔记**；对技术学科，还可以用代码复现书中
的例题（**可执行学习**，可选）。
Study from your own PDFs (books, papers, theses, any subject): read in a browser-based reader,
look up technical terms and words, write Markdown notes beside the PDF, track progress and
review. Everything stays on your own computer, in your own folder. The three pillars are
**learning, reading and note-taking**; for technical subjects you can also reproduce the
book's examples in code (**executable learning**, optional).

**不包含任何书籍**：请使用你自己的 PDF。**No books are included**: bring your own PDFs.

## 主要优点 / Main benefits

| | |
|---|---|
| **本地优先 Local-first** | 文档和笔记在你的控制之下；核心功能离线可用；不需要账户或订阅。Your documents and notes stay under your control; core features work offline; no account or subscription. |
| **开放笔记 Open notes** | 普通的 Markdown 文件，可以用 VS Code 或任何编辑器编辑。Ordinary Markdown files you can edit in VS Code or any editor. |
| **阅读与笔记结合 Integrated reading** | PDF 阅读、查词、搜索、笔记和进度在一个专注的工作流里。PDF reading, lookup, search, notes and progress in one focused workflow. |
| **可执行学习 Executable learning** | 可选：把教材中的例题与代码和数值验证连接起来。Optional: connect textbook examples with code and numerical verification. |
| **可迁移书库 Portable libraries** | 每个文档有永久身份；整个书库文件夹可以复制到另一台电脑。Every document has a permanent identity; a whole library folder copies to another computer. |
| **可追溯知识 Traceable knowledge** | 页面级链接已有；笔记与原文段落之间的精确链接正在开发（计划中）。Page-level links today; precise links between notes and passages are in development (planned). |

## 主要功能 / Key features

**已有 / Available now** (tested on Windows; CI runs on Windows):
- **阅读器 Reader:** PDF.js，记住读到哪里；PDF 中的高亮和标注保存回 PDF（带冲突检查）。PDF.js, remembering
  where you stopped; highlights and marks saved back into the PDF (with conflict checks).
- **查词 Lookup:** 学科术语表优先，然后离线英汉词典；加入生词本或术语表。Subject glossaries first, then an
  offline English–Chinese dictionary; save to your vocabulary or a glossary.
- **笔记 Notes:** 每章一个 Markdown 文件；在 PDF 旁的面板中编辑，自动保存、冲突保护、恢复草稿、预览。One Markdown file
  per chapter; edited in a panel beside the PDF with autosave, conflict protection, recovery
  drafts and preview.
- **搜索 Search:** 一次搜索所有书的全文；主题笔记汇集同一概念在不同书中的页面。Full-text search across all
  books; topic notes gather the pages where different books discuss one idea.
- **整理 Organising:** 自动识别书、论文、学位论文（ISBN、DOI、arXiv）；按学科的书架；重复检测；OCR 扫描件。Books,
  papers and theses identified automatically (ISBN, DOI, arXiv); subject shelves; repeat
  detection; OCR for scans.
- **学习 Learning:** 章节勾选、阅读记录、生词复习卡片。Chapter ticks, a reading log, vocabulary review cards.
- **可执行学习（可选）Executable learning (optional):** 每章一个 Python 脚本（从模板创建，在你的编辑器中打开）；书库中
  可复用的 `code/`；numpy、scipy、sympy、matplotlib。A Python script per chapter (from a template,
  opened in your editor); reusable `code/` in the library; numpy, scipy, sympy, matplotlib.
- **多个书库 Several libraries:** 多个私人书库、可切换；可以复制到另一台电脑；一个公开的测试/示例书库。Several
  personal libraries, switchable; copy one to another computer; a public Test & Demo library.
- **备份 Backup:** 💾 带日期的 zip 备份到你选的文件夹（OneDrive、U 盘）。💾 dated zip backups to a folder you
  choose (OneDrive, a USB stick).

**计划中 / Planned** ([ROADMAP.md](ROADMAP.md)): 公式、格式工具栏、粘贴截图；引用到笔记、从笔记回到原文段落；结构化标注；
跨文档主题；更多可执行学习的连接。Maths, a formatting toolbar, pasted screenshots; quote to note and back
from a note to the passage; structured annotations; cross-document topics; more links for
executable learning.

## 典型的学习流程 / Typical learning workflows

```
收集 Collect → 阅读 Read → 标注 Annotate → 理解 Understand → 整理 Organize
     → 实践 Implement → 验证 Verify → 复习 Review → 回溯原文 Revisit sources
```

1. **读书和记笔记 / Read and take notes:** 在书库页面点 **Read**（或 **Continue**）→ 在阅读器中读，双击查词 → 在旁边的
   面板中用自己的话写这一章的笔记。Click **Read** (or **Continue**) on the library page → read,
   double-click to look up → write the chapter's note in your own words in the panel beside it.
2. **比较不同的书 / Compare books:** 搜索一个概念 → 打开各本书的相关页 → 在主题笔记中记下你的理解。Search for an idea
   → open the relevant pages in each book → write your understanding in a topic note.
3. **用代码验证（可选）/ Verify with code (optional):** 读到一个公式 → 点该章的 **Script** → 在 VS Code 中实现并运行 →
   与书中的结果对比 → 把结论写进笔记。Reach an equation → click the chapter's **Script** → implement
   and run it in VS Code → compare with the book → write the conclusion into the note.

## 为什么选择 myLibrary / Why myLibrary?

myLibrary 的不同之处不在于别的软件做不到某件事，而在于把这些放进了一个简单的本地工作流：用户自己管理的 PDF 书库文件夹、普通的
Markdown 笔记、稳定的文档身份、可配置的外部编辑器、与章节关联的代码和科学计算，以及（计划中的）精确来源链接和跨文档的知识组织。
它特别照顾阅读英文学术资料的中文读者。
What sets myLibrary apart isn't that other software can't do these things; it's that they come
together in one simple local workflow: user-managed PDF library folders, plain Markdown notes,
stable document identities, configurable external editors, chapter-associated code and
scientific computation, and (planned) precise source links and cross-document knowledge. It
takes particular care of Chinese readers of English academic material.

### 与其他工具的简短比较 / A short comparison

| | myLibrary | BookxNote Pro | MarginNote 5 | Zotero 10 |
|---|---|---|---|---|
| 侧重 Focus | 阅读、笔记、学习；可选的代码验证 reading, notes, learning; optional code verification | 摘录和大纲 excerpts and outlines | 卡片、思维导图、复习 cards, mind maps, review | 文献管理和引用 literature management and citation |
| 笔记 Notes | 普通 Markdown 文件 plain Markdown files | 应用数据（第三方说明为 JSON）app data (JSON per third-party sources) | 应用数据库 app database | 数据库中的富文本，可导出 Markdown rich text in a database, Markdown export |
| 回到原文 Back to the source | 页面级；段落级计划中 page level; passage level planned | 回链协议 backlink protocol | 卡片链接回原文 cards link back | 标注链接、Show on Page annotation links, Show on Page |
| 代码 Code | 内置章节脚本工作流 built-in chapter-script workflow | 外部工具 external tools | 外部工具 external tools | 外部工具、插件 external tools, plugins |
| 平台 Platforms | Windows（已测试 tested） | Windows, Linux | Apple 平台 Apple platforms | 桌面和移动端 desktop and mobile |

每款产品都有自己的长处（例如 Zotero 的引用管理、MarginNote 的复习和思维导图）。详细的、注明来源和核实日期的比较见
[docs/COMPETITIVE_ANALYSIS.md](docs/COMPETITIVE_ANALYSIS.md)。
Each product has its own strengths (e.g. Zotero's citation management, MarginNote's review and
mind maps). A detailed comparison with sources and verification dates is in
[docs/COMPETITIVE_ANALYSIS.md](docs/COMPETITIVE_ANALYSIS.md).

## 当前状态 / Current status

当前开发：v0.3 任务 4（笔记面板）；Markdown 预览（M5a）已提交（安装包中的验证和人工验收尚未完成），下一步是数学公式（M5b，待批准）。完整的功能状态表见
[用户指南第 15 节](docs/USER_GUIDE.md#15-功能状态已实现已验证计划中--feature-status-implemented-verified-planned)，
进度见 [ROADMAP.md](ROADMAP.md)。只在 Windows 上测试过；macOS 和 Linux 未测试。版本 0.2.5（尚未发布新版本）。
Current development: v0.3 task 4 (the notes panel); the Markdown preview (M5a) is committed
(its check inside the package and the manual acceptance are still open), next is maths (M5b,
awaiting approval). The full feature-status table is in the user guide, section 15;
progress in the ROADMAP. Tested on Windows only; macOS and Linux untested. Version 0.2.5 (no new
release yet).

## 快速开始 / Quick start

需要 / Needs: [uv](https://docs.astral.sh/uv/)、[Git](https://git-scm.com/)、现代浏览器 a modern browser（作者用
Microsoft Edge）；可选 optional: [VS Code](https://code.visualstudio.com/)。

```powershell
git clone https://github.com/NanLi0207/myLibrary.git "$HOME\myLibrary"
cd "$HOME\myLibrary"
uv sync                                # 安装 Python 和包 / install Python and the packages
uv run scripts/make_shortcut.py        # Windows：桌面和开始菜单快捷方式 / Desktop + Start menu shortcut
uv run scripts/library_server.py       # 打开书库页面 / opens the library page (http://127.0.0.1:8765)
```

在源码目录中，**Start myLibrary Dev.cmd** 先让你选择书库模式（私人书库或测试/示例书库）。工具文件夹只放工具；你的书和笔记放在
单独的书库文件夹里，`git pull` 更新工具时从不碰它们。详见[用户指南第 1 节](docs/USER_GUIDE.md#1-安装与首次启动--installation-and-first-launch)。
In a source checkout, **Start myLibrary Dev.cmd** first lets you choose a library mode (personal
or Test & Demo). The tool folder holds only the tool; your books and notes live in a separate
library folder that `git pull` never touches. Details in the user guide, section 1.

## 文档 / Documentation

| 文档 Document | 内容 Content |
|---|---|
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | 完整的双语使用说明 The complete bilingual manual |
| [docs/LIBRARIES.md](docs/LIBRARIES.md) | 多个书库、测试/示例书库、把书库搬到另一台电脑 Several libraries, the Test & Demo library, moving a library |
| [docs/COMPETITIVE_ANALYSIS.md](docs/COMPETITIVE_ANALYSIS.md) | 与 BookxNote Pro、MarginNote 5、Zotero 10 的比较 Comparison with BookxNote Pro, MarginNote 5, Zotero 10 |
| [DEVELOPMENT_SPEC.md](DEVELOPMENT_SPEC.md) | 产品与技术规格 Product and technical specification |
| [ROADMAP.md](ROADMAP.md) | 当前计划和进度 Active plan and progress |
| [docs/history/](docs/history/) | 以前的路线图和规格（完整保留）Earlier roadmap and specification (kept in full) |
| [test_library/README.md](test_library/README.md) | 公开测试语料、来源和许可 The public test corpus, its sources and licences |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 如何贡献 How to contribute |
| [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) | 第三方组件及其许可 Third-party components and their licences |

## 路线图 / Roadmap

按顺序：完成笔记工作流（公式、格式、截图、引用到笔记、回到原文）→ 稳定的来源锚点和结构化标注 → 跨文档知识组织 → 更多可执行
学习 → 复习 → 可选的高级功能和 AI → 桌面应用。见 [ROADMAP.md](ROADMAP.md)。
In order: finish the notes workflow (maths, formatting, screenshots, quote to note, back to the
passage) → stable source anchors and structured annotations → cross-document knowledge → more
executable learning → review → optional advanced features and AI → a desktop app. See
[ROADMAP.md](ROADMAP.md).

## 贡献 / Contributing

欢迎报告问题、提出想法、修复和添加功能，或为新学科添加术语表。见 [CONTRIBUTING.md](CONTRIBUTING.md)（包括贡献者条款）。
Bug reports, ideas, fixes, features and glossaries for new subjects are welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md) (including the contributor terms).

## 许可与发行 / License and distribution

**源代码：[PolyForm Noncommercial 1.0.0](LICENSE)**（这不是开源意义上的宽松许可）。简单地说（以许可证原文为准）：可以为任何
**非商业**目的阅读、使用、修改和分享（个人学习、研究、教学、学校、慈善和公共机构）；**商业用途**（例如出售或在付费产品或服务中
使用）需要作者的书面许可。分享时请附上 [LICENSE](LICENSE)（包括 "Required Notice" 一行）。
**Source code: [PolyForm Noncommercial 1.0.0](LICENSE)** (not a permissive open-source
licence). In plain words (the licence text is what counts): you may read, use, change and share
it for any **non-commercial** purpose (personal study, research, teaching, schools, charities,
public institutions); **commercial use** (e.g. selling it or using it in a paid product or
service) needs the author's written permission. Include the [LICENSE](LICENSE) file (with its
"Required Notice" line) when sharing.

**现成安装包（9.9 元人民币，即将推出）/ Ready-to-use package (9.9 RMB, coming soon).** 自己按上面的步骤安装，非商业用途
免费。安装包只是省去安装：解压后双击即可，包含 Python、PDF 阅读器、词典和预览库，不需要命令行；它不包含 Python 章节脚本功能。
Setting myLibrary up yourself, as above, is free for non-commercial use. The package only saves
the setup: unzip and double-click; Python, the PDF viewer, the dictionary and the preview
library are included, no command line; it doesn't include the Python chapter-script features.

第三方组件及其许可：[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。公开测试语料中的两篇真实论文使用各自的许可（CC BY 4.0、
CC0），见 [test_library/README.md](test_library/README.md)。
Third-party components and their licences: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The
two real papers in the public test corpus have their own licences (CC BY 4.0, CC0), see
[test_library/README.md](test_library/README.md).

> 作者用它学习光学设计；作者自己的书库放在本仓库的 `library/` 中作为真实示例（不含书本身）。The author uses it to
> learn optical design; their library is in `library/` as a worked example (the books themselves
> are not included).
