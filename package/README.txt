myLibrary：用你自己的 PDF 书学习
myLibrary: study from your own PDF books
====================================================================

开始 / Getting started
--------------------------------------------------------------------
1. 把这个文件夹放在你想放的地方（例如 D:\myLibrary），然后双击 “Start myLibrary.cmd”。
   Put this folder where you want to keep it (e.g. D:\myLibrary), then double-click
   "Start myLibrary.cmd".
2. 第一次启动会在桌面和开始菜单创建 “myLibrary” 快捷方式；以后用它们启动。
   The first start creates "myLibrary" shortcuts on the Desktop and in the Start menu;
   use those from then on.
3. 书库页面会在浏览器中打开。点击 “＋ Add”（添加）选择你的 PDF（书、论文或学位论文），
   或者直接把 PDF 拖到页面上。“🔎 Find online”（在线查找）可以用 DOI、书名、作者等在网上搜索。
   The library page opens in your browser. Click "＋ Add" and choose your PDFs (books, papers
   or theses), or just drag the PDFs onto the page. "🔎 Find online" searches the internet by
   DOI, title, author and more.

不需要安装 Python，也不需要命令行；查词词典和 PDF 阅读器都已包含，可离线使用。
No Python or command line needed; the dictionary and PDF viewer are included and work offline.

阅读与查词 / Reading and looking up words
--------------------------------------------------------------------
- 点击书上的 “Start reading / Continue”（开始阅读 / 继续）打开书和这一章的笔记。
  Click "Start reading" / "Continue" on a book to open it with the chapter's notes.
- 双击一个单词，或拖选一个短语：弹出中文意思、音标和发音。
  Double-click a word, or drag over a phrase: its Chinese meaning, phonetics and sound.
- “📚 在我的书中”（In my books）：在你所有的书里找到讲解这个词的页面。
  "📚 在我的书中" (In my books): the pages of all your books that explain the term.
- “加入生词本”（Save word）把单词加入这本书的生词本。
  "加入生词本" (Save word) adds the word to the book's vocabulary list.
- 书库页上的“📇 Review words”（复习生词）把保存的生词做成卡片复习：空格键显示意思，
  认识按 2，不认识按 1。认识的词会隔 1、3、7、14、30、60 天再出现。
  "📇 Review words" on the library page turns your saved words into cards: Space shows the
  meaning, 2 = knew it, 1 = didn't. Words you know come back after 1, 3, 7, 14, 30, 60 days.
- “＋ 加入术语表”（Add to glossary）：添加你自己学科的术语和中文译名。
  "＋ 加入术语表" (Add to glossary): add your subject's terms with their Chinese names.
- 阅读位置会自动保存；下次点击 “Continue · p. N” 回到原处。
  Your place is saved automatically; "Continue · p. N" takes you back next time.

整理你的书 / Organising your books
--------------------------------------------------------------------
- 书架（Shelves）：每本书可以放在一个或多个书架上（例如 “Optics; Lasers”）。
  Shelves: put each book on one or more shelves (e.g. "Optics; Lasers").
- 读完一章后，在 “Chapters”（章节）里勾选它，记录进度。
  Tick a chapter under "Chapters" when you've finished it, to track your progress.
- 扫描版的书：点击 “OCR”（文字识别），之后就可以查词和搜索。
  Scanned books: click "OCR" so their words can be looked up and searched.

设置 / Settings（⚙ Settings）
--------------------------------------------------------------------
- 书库文件夹：你的书和笔记保存的位置（默认：文档\myLibrary Library）。
  Library folder: where your books and notes are kept (default: Documents\myLibrary Library).
- 用什么软件打开笔记：默认程序（例如 Typora、Obsidian）、记事本、VS Code 或自定义命令。
  Which program opens your notes: the default app (e.g. Typora, Obsidian), Notepad, VS Code,
  or your own command.

你的数据 / Your data
--------------------------------------------------------------------
备份 (Back up)：在“⚙ Settings”（设置）里选一个备份文件夹（如 OneDrive 或 U 盘），点“💾 Back up”。
笔记、进度和生词本存成带日期的 zip，PDF 另外复制一份；以后每天启动时自动备份一次。
Back up: choose a backup folder in "⚙ Settings" (e.g. OneDrive or a USB stick) and click
"💾 Back up". Your notes, progress and vocabulary go into a dated zip, and the PDFs are copied
next to it; after that it backs up by itself once a day when myLibrary starts.

OpenAlex 密钥 (OpenAlex key)：查学科和“🔎 Find online”要用 OpenAlex。一次加很多书时，免费的
共享额度可能用完；在 https://openalex.org/settings/api-key 免费申请一个，粘贴到“⚙ Settings”。
OpenAlex key: subjects and "🔎 Find online" use OpenAlex. Adding many books at once can use up
the free shared budget; get your own free key at https://openalex.org/settings/api-key and
paste it into "⚙ Settings".

你的书、笔记、生词本和进度都保存在书库文件夹里，都是普通文件（PDF、Markdown、CSV）。
请定期备份这个文件夹。更新 myLibrary 时，下载新版本即可，书库不受影响。
Your books, notes, vocabulary and progress are all ordinary files (PDF, Markdown, CSV) in your
library folder. Back that folder up regularly. To update myLibrary, just use the new version;
your library isn't touched.

关闭 / Stopping
--------------------------------------------------------------------
在书库页面点击 “Quit”（退出）。
Click "Quit" on the library page.

许可 / License
--------------------------------------------------------------------
个人非商业使用。详见 LICENSE 和 THIRD_PARTY_NOTICES.md。
For personal, non-commercial use. See LICENSE and THIRD_PARTY_NOTICES.md.
Source code: https://github.com/NanLi0207/myLibrary
