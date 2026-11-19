// 📝 Notes beside the PDF (task 4 M3, M4): the document's Markdown notes in a panel to the
// right of PDF.js, edited as Markdown source (mode A). Served with lookup.js and
// note_session.js by reader.viewer_html; uses lookup.js's token and requests (myLibraryReader)
// and note_session.js's NoteSession (the text, its saving, conflicts, recovery drafts).
//
// - The notes are found by the document's id and a note key ("file:README.md",
//   "file:ch02-….md"), never by a path: /api/notes/list|get|version|save|keep-copy|open.
// - Opening or viewing a note writes nothing; only typed text is saved. Never reading
//   position or reading time.
// - Layout by the window's width: beside the PDF from 1100 px, over the PDF (a drawer) from
//   760 px, the whole window below that. Beside the PDF it is remembered (open or not, its
//   width as a share of the window); in narrower windows it starts closed.
// - Views (M5a): 源码 / 预览 / 分屏 (Source / Preview / Split), Alt+P, remembered in this
//   browser. The preview (preview.js) is drawn from the session's text only: it never edits
//   or saves, so switching views writes nothing.
// - Formatting (M5c): a toolbar over the source (format.js turns each action into one edit of
//   the Markdown, applied with insertText: one Undo reverts one action, and it reaches the
//   session like typing); Ctrl+B / Ctrl+I only while typing in the note; nothing while the
//   note can't be typed in or a word is being composed (IME). Display preferences (Aa: font,
//   size, line height, paragraph spacing, width) are this browser's, never in the note.
// - State on <body>, for tests and for the read-only and loading logic: data-ml-notes
//   (open/closed), data-ml-notes-mode (side/drawer/full), data-ml-note-key, data-ml-note-state
//   (loading/shown/empty/missing/none/error), data-ml-save-state (clean/dirty/saving/failed/
//   offline/conflict/draft), data-ml-draft (kept/failed/none), data-ml-note-view.
(() => {
  "use strict";
  const reader = window.myLibraryReader;
  const app = window.PDFViewerApplication;
  if (!reader?.docId || !reader.token || !app) return;  // a bare PDF (no id): no panel
  const { docId, post, el, bi, biEl } = reader;
  const root = document.documentElement;
  const body = document.body;

  // --- what's remembered (this browser; storage may be unavailable: then nothing is) -------

  const KEYS = {
    open: "myLibrary.notes.open",
    width: "myLibrary.notes.width",
    last: `myLibrary.notes.last.${window.MYLIBRARY_SCOPE || "none"}:${docId}`,  // per library
    readOnly: "myLibrary.notes.readonly",
    view: "myLibrary.notes.view",
    display: "myLibrary.notes.display",  // M5c: font, size, line height, spacing, width
  };
  const load = (key) => {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  };
  const store = (key, value) => {
    try {
      localStorage.setItem(key, value);
    } catch {
      // a private window or blocked storage: it just isn't remembered
    }
  };

  // --- layout -------------------------------------------------------------------------------

  const SIDE_FROM = 1100;  // window width from which the notes sit beside the PDF
  const FULL_BELOW = 760;  // below this they take the whole window
  const PDF_MIN = 480;
  const NOTES_MIN = 320;
  const SHARE = 0.38;  // the notes' default share of the window
  const DRAWER = 420;
  const STEP = 24;  // ← / → on the divider
  const modeFor = (width) => (width >= SIDE_FROM ? "side" : width >= FULL_BELOW ? "drawer" : "full");

  let mode = modeFor(innerWidth);
  const storedShare = Number(load(KEYS.width));
  let share = storedShare > 0 && storedShare < 1 ? storedShare : SHARE;
  let sideOpen = load(KEYS.open) !== "0";  // first use: open
  let open = mode === "side" && sideOpen;  // narrower windows start closed
  let space = 0;  // what the panel takes from the PDF now (px)

  const sideWidth = () => Math.round(
    Math.min(Math.max(share * innerWidth, NOTES_MIN), innerWidth - PDF_MIN));

  // PDF.js re-fits "page width", "page fit" and "automatic" zoom only on its resize event,
  // which it sends for window resizes alone; a numeric zoom stays as it is. While the divider
  // moves, at most every 150 ms, so pages aren't redrawn on every frame
  let refitTimer = null;
  let lastRefit = 0;
  function refit(now) {
    const send = () => {
      clearTimeout(refitTimer);
      refitTimer = null;
      lastRefit = performance.now();
      app.eventBus?.dispatch("resize", { source: window });
    };
    if (now) return send();
    if (!refitTimer) refitTimer = setTimeout(send, Math.max(0, 150 - (performance.now() - lastRefit)));
  }

  // --- the panel ------------------------------------------------------------------------

  const panel = el("aside", "ml-notes");
  panel.id = "mlNotes";
  panel.setAttribute("aria-label", "笔记 Notes");
  panel.hidden = true;
  const divider = el("div", "ml-notes-divider");
  divider.setAttribute("role", "separator");
  divider.setAttribute("aria-orientation", "vertical");
  divider.setAttribute("aria-label", "调整笔记宽度 Resize the notes");
  divider.title = "拖动调整宽度，双击收起 / Drag to resize (←/→), double-click to hide";
  divider.tabIndex = 0;
  const head = el("div", "ml-notes-head");
  const menu = el("select");
  menu.id = "mlNoteSelect";
  menu.title = "选择笔记 Choose a note";
  menu.setAttribute("aria-label", menu.title);
  const editButton = el("button", null, "↗");
  editButton.id = "mlNoteOpen";
  editButton.type = "button";
  editButton.title = "在编辑器中打开 Open in the editor";
  editButton.setAttribute("aria-label", editButton.title);
  editButton.disabled = true;
  const closeButton = el("button", null, "✕");
  closeButton.id = "mlNotesClose";
  closeButton.type = "button";
  closeButton.title = "收起笔记 Hide the notes (Alt+N)";
  closeButton.setAttribute("aria-label", closeButton.title);
  // Saving (task 4 M4): the state, 保存 (Save), 🔒 (read-only)
  const saveState = el("span", "ml-save-state");
  saveState.id = "mlSaveState";
  saveState.setAttribute("role", "status");
  const saveButton = biEl("button", "ml-small", "保存", "Save");
  saveButton.id = "mlNoteSave";
  saveButton.type = "button";
  saveButton.title = "保存 Save now (Ctrl+S)";
  const lockButton = el("button", null, "🔒");
  lockButton.id = "mlNoteLock";
  lockButton.type = "button";
  lockButton.title = "只读 Read-only (no typing in the note)";
  lockButton.setAttribute("aria-label", lockButton.title);
  head.append(menu, saveState, saveButton, lockButton, editButton, closeButton);
  const status = el("div", "ml-notes-status");
  status.id = "mlNotesStatus";
  status.setAttribute("role", "status");
  // A bar for what needs a decision: a conflict, a draft to restore, a failed save
  const bar = el("div", "ml-note-bar");
  bar.id = "mlNoteBar";
  bar.hidden = true;
  // M7.1 S1a: recovery drafts of documents that left the library (merged into this one, or
  // removed), each offered until the user restores, saves or discards it
  const elsewhereBox = el("div", "ml-note-bar ml-elsewhere");
  elsewhereBox.id = "mlElsewhere";
  elsewhereBox.hidden = true;
  // Compare: the other version, read-only, above yours
  const compare = el("div", "ml-compare");
  compare.hidden = true;
  const compareLabel = el("div", "ml-compare-label");
  const compareText = el("textarea", "ml-compare-text");
  compareText.id = "mlCompareText";
  compareText.readOnly = true;
  compareText.spellcheck = false;
  compare.append(compareLabel, compareText);
  // The note: its Markdown source, as plain text (a textarea's value: never HTML)
  const text = el("textarea", "ml-note-text");
  text.id = "mlNoteText";
  text.spellcheck = false;
  text.setAttribute("aria-label", "笔记 Note (Markdown)");
  // M5a: the same text rendered (read-only), instead of the source or beside it
  const VIEWS = [["source", "源码", "Source"], ["preview", "预览", "Preview"], ["split", "分屏", "Split"]];
  const viewSwitch = el("div", "ml-view-switch");
  viewSwitch.setAttribute("role", "group");
  viewSwitch.setAttribute("aria-label", "显示 View (Alt+P)");
  const viewButtons = new Map(VIEWS.map(([name, zh, en]) => {
    const b = biEl("button", "ml-small", zh, en);
    b.type = "button";
    b.dataset.view = name;
    b.title = `${zh} ${en}${name === "split" ? "" : " (Alt+P)"}`;
    viewSwitch.append(b);
    return [name, b];
  }));
  const preview = el("div", "ml-note-preview");
  preview.id = "mlNotePreview";
  preview.tabIndex = 0;  // its own scroll keys; plain keys stay in the panel (below)
  preview.setAttribute("role", "document");
  preview.setAttribute("aria-label", "笔记预览 Note preview");
  const views = el("div", "ml-note-views");
  views.append(text, preview);
  // M5c: the formatting toolbar (over the source) and the display preferences (Aa)
  const HEADINGS = [["", "标题", "Heading"], ["h1", "H1", "Heading 1"], ["h2", "H2", "Heading 2"],
    ["h3", "H3", "Heading 3"], ["h4", "H4", "Heading 4"], ["h5", "H5", "Heading 5"],
    ["h6", "H6", "Heading 6"], ["h0", "正文", "Plain text"]];
  const TOOLS = [  // action, label, Chinese, English, key
    ["bold", "B", "粗体", "Bold", "Ctrl+B"], ["italic", "I", "斜体", "Italic", "Ctrl+I"],
    ["strike", "S", "删除线", "Strikethrough"], ["bullet", "•", "项目列表", "Bulleted list"],
    ["number", "1.", "编号列表", "Numbered list"], ["task", "☑", "任务列表", "Task list"],
    ["quote", "❝", "引用", "Quote"], ["code", "`", "行内代码", "Inline code"],
    ["codeblock", "```", "代码块", "Code block"], ["link", "🔗", "链接", "Link"],
    ["image", "🖼", "图片（Markdown 语法）", "Image (Markdown syntax)"], ["table", "▦", "表格", "Table"],
    ["math", "$", "行内公式", "Inline equation"], ["mathblock", "$$", "独立公式", "Displayed equation"],
  ];
  const tools = el("div", "ml-format-bar");
  tools.id = "mlFormatBar";
  tools.setAttribute("role", "toolbar");
  tools.setAttribute("aria-label", "格式 Formatting");
  const headingMenu = el("select", "ml-format-heading");
  headingMenu.id = "mlFormatHeading";
  headingMenu.title = "标题 Heading";
  headingMenu.setAttribute("aria-label", headingMenu.title);
  for (const [value, zh, en] of HEADINGS) {
    const option = el("option", null, value ? `${zh} ${en}` : `${zh} ${en}…`);
    option.value = value;
    headingMenu.append(option);
  }
  tools.append(headingMenu);
  const toolButtons = TOOLS.map(([action, label, zh, en, key]) => {
    const b = el("button", "ml-tool", label);
    b.type = "button";
    b.dataset.action = action;
    b.title = `${zh} ${en}${key ? ` (${key})` : ""}`;
    b.setAttribute("aria-label", b.title);
    tools.append(b);
    return b;
  });
  // M5e: a formula from a screenshot (the ∑ dialog, formula.js); M5d's pasted images need no
  // button: Ctrl+V in the note
  const formulaButton = el("button", "ml-tool ml-tool-formula", "∑⌕");
  formulaButton.id = "mlFormulaButton";
  formulaButton.type = "button";
  formulaButton.title = "识别公式截图 Recognize a formula from a screenshot (Ctrl+Shift+V)";
  formulaButton.setAttribute("aria-label", formulaButton.title);
  tools.append(formulaButton);
  // M6: a page link without quoted text (for pages whose text can't be selected, e.g. scans);
  // a selection is quoted from the PDF's bubble or with Alt+Q
  const pageRefButton = el("button", "ml-tool ml-tool-page-ref", "¶↗");
  pageRefButton.id = "mlPageRefButton";
  pageRefButton.type = "button";
  pageRefButton.title = "引用此页 Reference this page (a link to the page shown, no quoted text)";
  pageRefButton.setAttribute("aria-label", pageRefButton.title);
  pageRefButton.addEventListener("click", () => reader.referencePage?.());
  tools.append(pageRefButton);
  const displayButton = el("button", "ml-small ml-display-toggle", "Aa");
  displayButton.id = "mlDisplayToggle";
  displayButton.type = "button";
  displayButton.title = "显示设置 Display settings (this browser only)";
  displayButton.setAttribute("aria-label", displayButton.title);
  displayButton.setAttribute("aria-expanded", "false");
  viewSwitch.append(displayButton);
  const display = el("div", "ml-display");
  display.id = "mlDisplay";
  display.hidden = true;
  panel.append(divider, head, viewSwitch, display, tools, status, bar, elsewhereBox, compare, views);
  body.append(panel);

  // 📝 on PDF.js's toolbar, at its right end
  const toggle = el("button", "toolbarButton");
  toggle.id = "mlNotesToggle";
  toggle.type = "button";
  toggle.title = "笔记 Notes (Alt+N)";
  toggle.setAttribute("aria-label", "笔记 Notes");
  toggle.append(el("span", null, "笔记 Notes"));
  document.getElementById("toolbarViewerRight")?.append(toggle);

  function apply(refitNow = true) {
    const width = mode === "side" ? sideWidth()
      : mode === "drawer" ? Math.min(DRAWER, innerWidth - 48) : innerWidth;
    const next = open && mode === "side" ? width : 0;
    root.style.setProperty("--ml-notes-width", `${width}px`);
    root.style.setProperty("--ml-notes-space", `${next}px`);
    panel.hidden = !open;
    panel.dataset.mode = mode;
    body.dataset.mlNotes = open ? "open" : "closed";
    body.dataset.mlNotesMode = mode;
    toggle.setAttribute("aria-pressed", String(open));
    toggle.classList.toggle("toggled", open);
    const percent = (px) => Math.round((100 * px) / innerWidth);
    divider.setAttribute("aria-valuenow", String(percent(width)));
    divider.setAttribute("aria-valuemin", String(percent(NOTES_MIN)));
    divider.setAttribute("aria-valuemax", String(percent(innerWidth - PDF_MIN)));
    if (next !== space) {
      space = next;
      refit(refitNow);
    }
  }

  const focusPdf = () => (app.pdfViewer?.container || document.getElementById("viewerContainer"))
    ?.focus({ preventScroll: true });

  // `byUser` beside the PDF is remembered; in narrower windows it never changes what's stored
  function setOpen(next, byUser) {
    if (next === open) return;
    const focusInside = panel.contains(document.activeElement);
    open = next;
    if (byUser && mode === "side") {
      sideOpen = next;
      store(KEYS.open, next ? "1" : "0");
    }
    apply();
    if (open) {
      if (!listed) loadList();
      if (mode !== "side") menu.focus();
    } else if (focusInside) {
      focusPdf();
    }
  }

  toggle.addEventListener("click", () => setOpen(!open, true));
  closeButton.addEventListener("click", () => setOpen(false, true));

  addEventListener("resize", () => {
    const next = modeFor(innerWidth);
    if (next !== mode) {
      const was = mode;
      mode = next;
      if (next === "side") open = sideOpen;  // wide again: as the user left it there
      else if (was === "side") open = false;  // narrower: starts closed; what's stored stays
      if (open && !listed) loadList();
    }
    apply();
  });

  // --- the divider --------------------------------------------------------------------------

  function setWidth(px, refitNow) {
    share = Math.min(Math.max(px, NOTES_MIN), innerWidth - PDF_MIN) / innerWidth;
    apply(refitNow);
  }
  let dragging = null;
  divider.addEventListener("pointerdown", (event) => {
    if (mode !== "side" || event.button !== 0) return;
    event.preventDefault();
    divider.setPointerCapture(event.pointerId);
    dragging = event.pointerId;
    body.classList.add("ml-dragging");
  });
  divider.addEventListener("pointermove", (event) => {
    if (dragging === event.pointerId) setWidth(innerWidth - event.clientX, false);
  });
  const endDrag = (event) => {
    if (dragging !== event.pointerId) return;
    dragging = null;
    body.classList.remove("ml-dragging");
    store(KEYS.width, String(share));
    refit(true);
  };
  for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) {
    divider.addEventListener(type, endDrag);
  }
  divider.addEventListener("dblclick", () => setOpen(false, true));
  divider.addEventListener("keydown", (event) => {
    const by = { ArrowLeft: STEP, ArrowRight: -STEP }[event.key];
    if (!by || mode !== "side") return;
    event.preventDefault();
    setWidth(sideWidth() + by, true);
    store(KEYS.width, String(share));
  });

  // --- keys ---------------------------------------------------------------------------------

  // (the ∑ dialog of M5e is modal: nothing behind it changes while it is open)
  const formulaOpen = () => Boolean(window.myLibraryFormula?.isOpen());
  // Alt+N anywhere in the reader (by the key's position, so any keyboard layout or IME)
  addEventListener("keydown", (event) => {
    if (event.code !== "KeyN" || !event.altKey || event.ctrlKey || event.metaKey || event.shiftKey
      || formulaOpen()) return;
    event.preventDefault();
    event.stopPropagation();
    setOpen(!open, true);
  }, true);
  // Alt+P while the notes are open: Source ↔ Preview (from Split: Preview)
  addEventListener("keydown", (event) => {
    if (event.code !== "KeyP" || !event.altKey || event.ctrlKey || event.metaKey || event.shiftKey
      || !open || formulaOpen()) return;
    event.preventDefault();
    event.stopPropagation();
    setView(view === "source" ? "preview" : "source");
  }, true);

  // In the panel, plain keys (Space, PageDown, arrows, Home, n, p, …) are the panel's: PDF.js
  // would otherwise turn its pages. Ctrl and Alt shortcuts go on (Ctrl+F still finds in the
  // PDF; lookup.js keeps the marks' Ctrl+Z from acting here). Esc: back to the PDF beside it,
  // or closes the panel over it
  panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      if (mode === "side") focusPdf();
      else setOpen(false, true);
      return;
    }
    // Ctrl+S in the panel saves the note (never PDF.js's "save the PDF", decision D4)
    if ((event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === "s") {
      event.preventDefault();
      event.stopPropagation();
      saveNow();
      return;
    }
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    event.stopPropagation();
  });

  // --- the notes ----------------------------------------------------------------------------

  const { NoteSession, drafts } = window.myLibraryNoteSession;
  let entries = [];
  let listed = false;
  let current = null;
  // M6: where the user last put the caret in the note ({key, pos, value}); a quote goes there
  // while the note's text is still what it was then, else at the end
  let caretAt = null;
  let asked = 0;  // the latest request: an earlier answer arriving late is ignored
  let busy = false;  // a conflict choice or a draft choice is on its way
  let comparing = false;
  const sessions = new Map();  // key -> NoteSession, for this tab: unsaved text is never dropped
  const openedAt = Number((location.hash.match(/page=(\d+)/) || [])[1]) || null;
  let readOnly = load(KEYS.readOnly) === "1";  // 🔒, remembered (decision D3: editable by default)
  drafts.expire();

  // Other tabs of this browser on the same note: told at once when one saves (the 409 check
  // is still the real protection; this only makes it visible sooner)
  let channel = null;
  try {
    channel = new BroadcastChannel("myLibrary-notes");
    channel.onmessage = ({ data }) => {
      const session = data?.docId === docId ? sessions.get(data.key) : null;
      if (session && data.version !== session.base) session.checkDisk();
    };
  } catch {
    channel = null;
  }

  const session = () => (current ? sessions.get(current) : null);
  // The session the box's text belongs to, for typing: the note chosen, and only once its own
  // text is in the box. While another note loads (or failed to), the box isn't that note's,
  // so nothing typed may reach it: never one note's text saved into another's file
  const typing = () => {
    const note = session();
    return note && note.loaded && text.dataset.key === note.key ? note : null;
  };

  // --- views: source, preview, split (M5a) ------------------------------------------------------

  const markdown = window.myLibraryPreview;
  let view = VIEWS.some(([name]) => name === load(KEYS.view)) ? load(KEYS.view) : "source";
  let previewTimer = null;

  function setView(next, remember = true) {
    const focusWasIn = text.contains(document.activeElement) ? "text"
      : preview.contains(document.activeElement) ? "preview" : "";
    view = next;
    if (remember) store(KEYS.view, next);
    views.dataset.view = next;
    body.dataset.mlNoteView = next;
    for (const [name, b] of viewButtons) b.setAttribute("aria-pressed", String(name === next));
    text.hidden = next === "preview";
    tools.hidden = next === "preview";  // (formatting edits the source: shown with it)
    preview.hidden = next === "source";
    drawPreview();
    // The focus stays in the notes (never left to PDF.js, whose keys would turn pages)
    if (focusWasIn === "text" && text.hidden) preview.focus();
    if (focusWasIn === "preview" && preview.hidden) text.focus();
  }
  for (const [name, b] of viewButtons) b.addEventListener("click", () => setView(name));

  // The note whose text is in the box, rendered (only ever read: nothing here edits or saves);
  // nothing while another note loads (D13)
  function drawPreview() {
    clearTimeout(previewTimer);
    previewTimer = null;
    if (view === "source") return;
    const note = typing();
    if (!note) {
      preview.replaceChildren();
      return;
    }
    const { scrollTop } = preview;
    if (markdown?.available) {
      // Images already shown are kept (moved into the new rendering): no flicker and no new
      // request while typing; the scroll position stays right because they keep their size
      const shown = new Map();
      for (const img of preview.querySelectorAll("img.ml-image")) {
        if (img.complete && img.naturalWidth) {
          const src = img.getAttribute("src");
          shown.set(src, [...(shown.get(src) || []), img]);
        }
      }
      // markdown-it, html: false (preview.js); images only from this document's assets/
      preview.innerHTML = markdown.html(note.text, { image: assetUrl });
      for (const img of preview.querySelectorAll("img.ml-image")) {
        const src = img.getAttribute("src");
        if (missingImages.has(src)) {
          img.replaceWith(missingImage(img));
          continue;
        }
        const kept = shown.get(src)?.shift();
        if (kept) {
          kept.alt = img.alt;
          kept.title = img.title;
          img.replaceWith(kept);
        }
      }
    } else {
      const plain = el("pre", "ml-preview-plain");
      plain.textContent = note.text;
      preview.replaceChildren(biEl("div", "ml-muted ml-preview-setup",
        "预览需要先安装：uv run scripts/reader.py --setup-preview",
        "The preview needs setting up: uv run scripts/reader.py --setup-preview"), plain);
    }
    preview.scrollTop = scrollTop;
  }
  // M5d: a note's image link → the server's contained route for this document's assets/, or
  // null (then preview.js shows a placeholder and nothing is requested). Only "assets/<name>"
  // or "./assets/<name>", with a name as notes_store.asset_name_ok takes it; the server checks
  // the name and the folder again
  const ASSET_NAME = /^[^\x00-\x1f\x7f/\\:*?"<>|.\s][^\x00-\x1f\x7f/\\:*?"<>|]{0,140}\.(png|jpe?g|webp)$/iu;
  function assetUrl(src) {
    let path = String(src).trim().replace(/^\.\//, "");
    if (!path.startsWith("assets/")) return null;
    path = path.slice("assets/".length).split(/[?#]/)[0];
    let name;
    try {
      name = decodeURIComponent(path);
    } catch {
      return null;
    }
    if (!ASSET_NAME.test(name)) return null;
    return `/notes-assets/${docId}/${encodeURIComponent(name)}`;
  }
  // An image that couldn't be shown (missing, not an image): a placeholder saying so, also
  // in later redraws (never asked for again until another note is shown)
  const missingImages = new Set();
  function missingImage(img) {
    const name = decodeURIComponent(img.getAttribute("src").split("/").pop());
    const box = biEl("span", "ml-image-placeholder ml-image-missing", `图片无法显示：${name}`,
      `Image can't be shown: ${img.alt ? `${img.alt} — ` : ""}assets/${name}`);
    box.title = `assets/${name}`;
    return box;
  }
  preview.addEventListener("error", (event) => {
    const img = event.target;
    if (!(img instanceof HTMLImageElement) || !img.classList.contains("ml-image")) return;
    missingImages.add(img.getAttribute("src"));
    img.replaceWith(missingImage(img));
  }, true);  // (an image's error doesn't bubble)

  // While typing in Split: a moment after the last key; otherwise at once
  function schedulePreview(now) {
    if (view === "source") return;
    if (now || view === "preview") return drawPreview();
    clearTimeout(previewTimer);
    previewTimer = setTimeout(drawPreview, 200);
  }
  // Split: the preview follows the source's scrolling (proportionally)
  text.addEventListener("scroll", () => {
    if (view !== "split") return;
    const share = text.scrollTop / Math.max(1, text.scrollHeight - text.clientHeight);
    preview.scrollTop = share * (preview.scrollHeight - preview.clientHeight);
  });
  // Links in the preview: http(s) open in a new tab (preview.js marks them); a #heading
  // scrolls the preview (never PDF.js's own #page=…); another note of this document opens in
  // the panel; /read/<id> opens in a new tab; anything else does nothing
  preview.addEventListener("click", (event) => {
    const link = event.target.closest?.("a[href]");
    if (!link || !preview.contains(link)) return;
    const href = link.getAttribute("href");
    // M7: a reference link (its href already this server's safe preview, preview.js) is
    // followed by navigate.js: in place for this document, else a new preview tab. Without
    // navigate.js nothing is prevented: the link itself opens that preview in a new tab.
    const anchors = window.myLibraryAnchors;
    const reference = anchors?.parseReference(href);
    if (reference?.kind === "reference" && window.myLibraryNavigate) {
      event.preventDefault();
      if (event.ctrlKey || event.metaKey || event.shiftKey) {  // a new tab asked for
        window.open(anchors.safeHref(reference), "_blank", "noopener");
        return;
      }
      try {
        window.myLibraryNavigate.follow(href);
      } catch {
        window.open(anchors.safeHref(reference), "_blank", "noopener");
      }
      return;
    }
    if (markdown?.isWeb(href)) return;
    event.preventDefault();
    if (href.startsWith("#")) {
      let fragment = href.slice(1);
      try { fragment = decodeURIComponent(fragment); } catch { /* as written */ }
      const target = document.getElementById(markdown.headingId(fragment));
      if (target && preview.contains(target)) target.scrollIntoView({ block: "start" });
      return;
    }
    if (/^\/read\/[0-9a-f-]{36}([?#]|$)/.test(href)) {
      window.open(href, "_blank", "noopener");
      return;
    }
    let name = href.split(/[?#]/)[0].replace(/^\.\//, "");
    try { name = decodeURIComponent(name); } catch { /* as written */ }
    const entry = entries.find((e) => e.key === `file:${name}`);
    if (entry) {
      show(entry.key);
    } else {
      say(biEl("span", "ml-muted", `不是这份文档的笔记：${name}`, `Not a note of this document: ${name}`));
    }
  });

  // M7: Ctrl+click on a reference link in the Markdown source follows it (navigate.js), as a
  // click does in the preview. On click (the caret is already where you clicked), with
  // nothing selected; the text is only read, never written. Anything else: as before.
  const LINK_AT = /\]\(([^)\s]+)\)|https?:\/\/[^\s)<>]+|\/read\/[^\s)<>]+/g;
  text.addEventListener("click", (event) => {
    if (!(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey) return;
    if (text.selectionStart !== text.selectionEnd) return;
    const at = text.selectionStart;
    const lineStart = text.value.lastIndexOf("\n", at - 1) + 1;
    const lineEnd = text.value.indexOf("\n", at);
    const line = text.value.slice(lineStart, lineEnd < 0 ? undefined : lineEnd);
    for (const m of line.matchAll(LINK_AT)) {
      const from = lineStart + m.index;
      if (at < from || at > from + m[0].length) continue;
      const href = m[1] || m[0];
      const reference = window.myLibraryAnchors?.parseReference(href);
      if (reference?.kind !== "reference") return;
      if (!window.myLibraryNavigate) {
        say(biEl("span", "ml-muted", "现在无法跟随引用", "The reference can't be followed right now"));
        return;
      }
      try {
        window.myLibraryNavigate.follow(href);
      } catch (error) {
        say(biEl("span", "ml-muted", "无法跟随引用", `The reference couldn't be followed: ${error.message}`));
      }
      return;
    }
  });

  // --- display preferences (M5c): this browser's, never in the note ------------------------

  const SYSTEM_FONT = 'system-ui, "Segoe UI", "Microsoft YaHei", sans-serif';
  const DISPLAY = [  // name, Chinese, English, [value, label, CSS value], the default
    ["font", "字体", "Font", [
      ["system", "系统 System", SYSTEM_FONT],
      ["serif", "衬线 Serif", 'Georgia, "Times New Roman", SimSun, serif'],
      ["mono", "等宽 Monospace", 'Consolas, "Cascadia Mono", "Microsoft YaHei", monospace'],
    ], "system"],
    ["size", "字号", "Size", ["12", "13", "14", "15", "16", "18", "20"]
      .map((n) => [n, `${n} px`, `${n}px`]), "14"],
    ["line", "行距", "Line height", ["1.3", "1.45", "1.6", "1.8", "2"].map((n) => [n, n, n]), "1.6"],
    ["para", "段距", "Paragraph spacing (preview)", ["0.4", "0.8", "1.2", "1.6"]
      .map((n) => [n, `${n} em`, `${n}em`]), "0.8"],
    ["width", "宽度", "Width", [
      ["full", "整宽 Full", "100%"], ["wide", "宽 Wide", "56em"],
      ["medium", "中 Medium", "44em"], ["narrow", "窄 Narrow", "34em"],
    ], "full"],
  ];
  const CSS_VARS = { font: "--ml-note-font", size: "--ml-note-size", line: "--ml-note-line",
    para: "--ml-note-para", width: "--ml-note-measure" };
  const defaults = () => Object.fromEntries(DISPLAY.map(([name, , , , value]) => [name, value]));
  // What's stored, each value checked against the choices (anything else: the default)
  function storedDisplay() {
    const chosen = defaults();
    let saved = null;
    try {
      saved = JSON.parse(load(KEYS.display) || "null");
    } catch {
      saved = null;
    }
    if (saved && typeof saved === "object") {
      for (const [name, , , options] of DISPLAY) {
        if (options.some(([value]) => value === saved[name])) chosen[name] = saved[name];
      }
    }
    return chosen;
  }
  let shown = storedDisplay();
  const displayMenus = new Map();
  function applyDisplay() {
    for (const [name, , , options] of DISPLAY) {
      const [, , css] = options.find(([value]) => value === shown[name]);
      panel.style.setProperty(CSS_VARS[name], css);
      const menuFor = displayMenus.get(name);
      if (menuFor) menuFor.value = shown[name];
    }
    body.dataset.mlNoteDisplay = DISPLAY.map(([name]) => `${name}=${shown[name]}`).join(" ");
  }
  for (const [name, zh, en, options] of DISPLAY) {
    const label = el("label", "ml-display-row");
    const select = el("select");
    select.dataset.pref = name;
    for (const [value, text_] of options) {
      const option = el("option", null, text_);
      option.value = value;
      select.append(option);
    }
    select.addEventListener("change", () => {
      shown = { ...shown, [name]: select.value };
      store(KEYS.display, JSON.stringify(shown));
      applyDisplay();
    });
    label.append(bi(zh, en), select);
    display.append(label);
    displayMenus.set(name, select);
  }
  const resetDisplay = button("恢复默认", "Reset", () => {
    shown = defaults();
    store(KEYS.display, JSON.stringify(shown));
    applyDisplay();
  }, "mlDisplayReset");
  display.append(resetDisplay);
  displayButton.addEventListener("click", () => {
    display.hidden = !display.hidden;
    displayButton.setAttribute("aria-expanded", String(!display.hidden));
  });
  applyDisplay();

  function sessionFor(key) {
    if (!sessions.has(key)) {
      sessions.set(key, new NoteSession({
        token: reader.token, docId, key,
        onChange: (changed) => { if (changed.key === current) render(changed); },
        onSaved: (saved) => channel?.postMessage({ docId, key: saved.key, version: saved.base }),
        onHandoff: (adopted) => {  // a restored draft's save confirmed: its original is gone
          say(biEl("span", "ml-muted", `草稿已恢复并保存到“${noteName(adopted.key)}”`,
            `The draft was restored and saved in “${noteName(adopted.key)}”`), 12000);
          scanElsewhere();
        },
      }));
    }
    return sessions.get(key);
  }

  // M6: a quote's pending line (its offer to insert, its Retry) stays when the note changes:
  // going back to the note it was asked for is how it is inserted
  const quoteLines = new Set();
  function keepLine(line, ms) {
    quoteLines.add(line);
    status.append(line);
    setTimeout(() => dropLine(line), ms);
  }
  function dropLine(line) {
    quoteLines.delete(line);
    line.remove();
  }

  function setState(state, ...nodes) {
    body.dataset.mlNoteState = state;
    status.replaceChildren(...nodes, ...quoteLines);
  }

  function failed(error, retry) {
    const again = biEl("button", "ml-small", "重试", "Retry");
    again.type = "button";
    again.addEventListener("click", retry);
    setState("error", biEl("span", "ml-error", "无法载入笔记", `Couldn't load the note: ${error.message}`), again);
  }

  const GROUPS = [
    ["document", "本书", "This document"],
    ["chapter", "章节", "Chapters"],
    ["other", "其他", "Other notes"],
  ];
  function labelOf(entry) {
    if (entry.kind === "chapter") {
      return entry.exists ? entry.title : `${entry.title}（还没有 not written yet）`;
    }
    return entry.key.slice("file:".length);  // README.md, notes.md, vocabulary.md, …
  }

  function buildMenu() {
    menu.replaceChildren();
    for (const [kind, zh, en] of GROUPS) {
      const members = entries.filter((entry) => entry.kind === kind);
      if (!members.length) continue;
      const group = el("optgroup");
      group.label = `${zh} ${en}`;
      for (const entry of members) {
        const option = el("option", null, labelOf(entry));
        option.value = entry.key;
        group.append(option);
      }
      menu.append(group);
    }
  }

  // The note to start with: the chapter of the page the reader opened at (from the chapter
  // pages the server has cached), else the last one chosen for this document, else its main
  // note. Only at the start: later page turns never switch the note
  function firstKey() {
    const page = openedAt || app.page || null;
    const before = entries.filter((entry) => entry.kind === "chapter"
      && Number.isInteger(entry.page) && page && entry.page <= page);
    if (before.length) return before.reduce((a, b) => (b.page >= a.page ? b : a)).key;
    const last = load(KEYS.last);
    if (last && entries.some((entry) => entry.key === last)) return last;
    const main = entries.find((entry) => entry.key === "file:notes.md")
      || entries.find((entry) => entry.key === "file:README.md") || entries[0];
    return main.key;
  }

  // M6: the latest list or note load (a promise), how many are under way, and how many notes
  // the user chose: a quote asked for while the panel loads waits for it (quoteTarget), and
  // never goes into a note the user chose meanwhile
  let loading = Promise.resolve();
  let underWay = 0;
  let requested = null;  // the note last asked for (show()), before it is current
  let userChoices = 0;
  function tracked(promise) {
    loading = promise;
    underWay++;
    promise.finally(() => { underWay--; }).catch(() => {});
    return promise;
  }

  function loadList() {
    return tracked(listNotes());
  }

  function show(key, { chosen = true } = {}) {
    requested = key;
    if (chosen) userChoices++;
    return tracked(showNote(key, { chosen }));
  }

  async function listNotes() {
    listed = true;
    const mine = ++asked;
    setState("loading", biEl("span", "ml-muted", "载入中…", "Loading…"));
    let list;
    try {
      list = (await post("/api/notes/list", { id: docId })).notes;
    } catch (error) {
      if (mine === asked) {
        listed = false;
        failed(error, loadList);
      }
      return;
    }
    if (mine !== asked) return;
    entries = list.filter((entry) => entry.kind !== "topic");  // topic notes: a later version
    buildMenu();
    scanElsewhere();
    menu.disabled = !entries.length;
    if (!entries.length) {
      text.value = "";
      text.readOnly = true;
      syncTools();
      editButton.disabled = saveButton.disabled = true;
      setState("none", biEl("span", "ml-muted", "这份文档还没有笔记", "No notes for this document yet"));
      return;
    }
    return show(firstKey(), { chosen: false });
  }

  // Show a note. Leaving one with unsaved text saves it first; if that save fails or meets a
  // conflict, the note stays on screen with its text (never discarded by switching)
  async function showNote(key, { chosen = true } = {}) {
    const mine = ++asked;
    const leaving = session();
    if (leaving && key !== current && leaving.unconfirmed) {
      menu.value = current;
      const state = await leaving.flush();
      if (mine !== asked) return;  // another note was chosen while saving: that choice wins
      if (state !== "clean") {
        say(biEl("span", "ml-error", "这条笔记还没保存好，请先处理",
          "This note isn't saved yet: deal with it first"));
        return;
      }
    }
    if (key !== current) caretAt = null;  // M6: a quote goes to the end until a caret is placed
    current = key;
    menu.value = key;
    comparing = false;
    missingImages.clear();  // (an image added by hand meanwhile is asked for again)
    body.dataset.mlNoteKey = key;
    if (chosen) store(KEYS.last, key);
    const note = sessionFor(key);
    if (note.loaded && note.unconfirmed) return render(note, { fresh: true });  // as left here
    // Until this note's text is in the box, the box is read-only, and empty if it held
    // another note's text (that text stays in its own session)
    text.readOnly = true;
    syncTools();
    if (text.dataset.key !== key) {
      text.value = "";
      delete text.dataset.key;
      drawPreview();  // (nothing: no note's text is in the box now)
    }
    setState("loading", biEl("span", "ml-muted", "载入中…", "Loading…"));
    let answer;
    try {
      answer = await post("/api/notes/get", { id: docId, key });
    } catch (error) {
      if (mine === asked) failed(error, () => show(key, { chosen: false }));
      return;  // the box stays read-only: nothing typed can reach a note not shown
    }
    if (mine !== asked) return;  // another note was chosen meanwhile: the last choice wins
    if (note.loaded && note.unconfirmed) return render(note, { fresh: true });
    note.load(answer);  // renders (onChange)
    render(note, { fresh: true });
  }

  menu.addEventListener("change", () => show(menu.value));

  // --- showing a session --------------------------------------------------------------------

  const STATES = {
    clean: ["已保存", "Saved"],
    dirty: ["未保存", "Unsaved"],
    saving: ["正在保存…", "Saving…"],
    failed: ["保存失败", "Save failed"],
    offline: ["服务器未连接", "Server not reachable"],
    restarted: ["需要重新载入", "Reload needed"],
    conflict: ["有冲突", "Conflict"],
    draft: ["有未保存的草稿", "Unsaved draft"],
  };

  function render(note, { fresh = false } = {}) {
    if (note.key !== current || !note.loaded) return;  // not loaded: show() renders it once it is
    if (text.dataset.key !== note.key) {  // another note than the one in the box: from its top
      fresh = true;
      text.dataset.key = note.key;
    }
    // The text: replaced only when it came from elsewhere (loaded, the disk version taken, a
    // draft restored), never while the user's own typing is what's in the box
    if (text.value !== note.text) {
      const { selectionStart, selectionEnd, scrollTop } = text;
      text.value = note.text;
      if (fresh) {
        text.scrollTop = 0;
      } else {
        text.setSelectionRange(selectionStart, selectionEnd);
        text.scrollTop = scrollTop;
      }
    }
    const state = note.state;
    body.dataset.mlSaveState = state;
    body.dataset.mlDraft = note.draftState;
    saveState.dataset.state = state;
    saveState.replaceChildren(bi(...STATES[state]));
    saveState.title = note.failure?.message || "";
    saveButton.disabled = !["dirty", "failed", "offline"].includes(state);  // not "restarted"
    editButton.disabled = !note.exists;
    lockButton.setAttribute("aria-pressed", String(readOnly));
    lockButton.textContent = readOnly ? "🔒" : "🔓";
    text.readOnly = readOnly || busy || state === "draft";
    syncTools();
    // The state line (as in M3) and its hint
    if (!note.exists && !note.text) {
      setState("missing",
        biEl("div", "ml-muted", "这一章还没有笔记", "No notes for this chapter yet"),
        biEl("div", "ml-muted", "直接输入即可开始；保存时才会创建文件",
          "Just type to start it: the file is created when it's saved"));
    } else if (!note.text.trim()) {
      setState("empty", biEl("span", "ml-muted", "这条笔记还是空的", "This note is empty"));
    } else if (["loading", "missing", "empty", "error", "none"].includes(body.dataset.mlNoteState)
      || fresh) {
      setState("shown");
    }
    if (note.notice === "updated") {
      note.notice = "";
      say(biEl("span", "ml-muted", "已从磁盘更新（在别处修改过）", "Updated from disk (changed elsewhere)"));
    }
    renderBar(note);
    schedulePreview(fresh);
  }

  function button(zh, en, onclick, id) {
    const b = biEl("button", "ml-small", zh, en);
    b.type = "button";
    if (id) b.id = id;
    b.addEventListener("click", onclick);
    return b;
  }

  function renderBar(note) {
    const parts = [];
    const state = note.state;
    if (state === "conflict") {
      parts.push(
        biEl("div", "ml-error", "这条笔记在别处被修改了（例如 VS Code 或另一个标签页）",
          "This note was changed elsewhere (VS Code, another tab). Your text is kept here and as a draft."),
        button("保留我的版本", "Keep mine", () => resolve("mine"), "mlKeepMine"),
        button("载入磁盘版本", "Use the disk version", () => resolve("disk"), "mlUseDisk"),
        button(comparing ? "隐藏对比" : "对比", comparing ? "Hide compare" : "Compare",
          () => { comparing = !comparing; renderBar(note); }, "mlCompare"),
      );
    } else if (state === "draft") {
      const when = new Date(note.recovered.draft.time || 0).toLocaleString();
      parts.push(
        biEl("div", null, `发现未保存的草稿（${when}）`, `An unsaved draft was found (${when})`),
        button("恢复", "Restore", () => chooseDraft("restore"), "mlRestoreDraft"),
        button("丢弃", "Discard", () => chooseDraft("discard"), "mlDiscardDraft"),
        button(comparing ? "隐藏对比" : "对比", comparing ? "Hide compare" : "Compare",
          () => { comparing = !comparing; renderBar(note); }, "mlCompare"),
      );
    } else if (state === "restarted" && note.failure?.gone) {
      parts.push(biEl("div", "ml-error",
        "这份文档已合并到另一份文档或已移除：没有保存。你的文字仍在编辑器和恢复草稿里",
        "This document was merged into another or removed: nothing was saved. Your text stays in the editor and in a recovery draft"));
      if (note.failure.into) {
        parts.push(biEl("div", "ml-muted", "在保留的文档里打开笔记面板，可以选择把草稿恢复到哪条笔记",
          "In the document that stays, the notes panel offers the draft: you choose the note it goes into"));
        parts.push(button("打开保留的文档", "Open the document that stays",
          () => { location.href = `/read/${encodeURIComponent(note.failure.into)}`; }, "mlOpenKept"));
      }
      parts.push(button("另存为文件", "Save as a file",
        () => saveAsFile(note.text, note.key), "mlSaveDraftFile"));
    } else if (state === "restarted") {
      parts.push(biEl("div", "ml-error",
        "服务器重新启动过：请重新载入此页面后继续保存。你的文字保留在浏览器的恢复草稿里，载入后会提供恢复",
        "The server was restarted: reload this page to go on saving. Your text is kept as a recovery draft and offered after the reload"));
    } else if (state === "failed" || state === "offline") {
      parts.push(
        biEl("div", "ml-error", state === "offline" ? "服务器未连接：文字仍在这里，会自动重试"
          : "保存失败：文字仍在这里，会自动重试",
        `${note.failure.message}: your text is kept here and retried`),
        button("重试", "Retry", () => note.retryNow(), "mlRetry"),
      );
    }
    if (note.draftState === "failed") {
      parts.push(biEl("div", "ml-error", "浏览器无法保存恢复草稿：如果浏览器崩溃，未保存的文字会丢失",
        "The browser can't keep a recovery draft: unsaved text would be lost if the browser crashed"));
    }
    bar.replaceChildren(...parts);
    bar.hidden = !parts.length;
    bar.dataset.kind = parts.length ? state : "";
    // Compare: the other side, read-only (a conflict: the disk version; a draft: the draft)
    const other = state === "conflict" ? note.conflict.text
      : state === "draft" ? note.recovered.draft.text : null;
    compare.hidden = !(comparing && other !== null);
    if (!compare.hidden) {
      compareLabel.replaceChildren(state === "conflict"
        ? bi("磁盘上的版本（只读）", "The version on disk (read-only)")
        : bi("草稿（只读）", "The draft (read-only)"));
      if (compareText.value !== other) compareText.value = other;
    }
  }

  async function resolve(choice) {
    const note = session();
    if (!note || busy) return;
    busy = true;
    render(note);
    const done = choice === "mine" ? await note.keepMine() : await note.useDisk();
    busy = false;
    comparing = false;
    render(note);
    if (done.ok) {
      say(biEl("span", "ml-muted",
        choice === "mine" ? `已保存你的版本；磁盘上的旧版本保存在 ${done.kept || "（无）"}`
          : `已载入磁盘版本；你的版本保存在 ${done.kept}`,
        choice === "mine" ? `Your version is saved; the other one is kept in ${done.kept || "(none)"}`
          : `The disk version is loaded; yours is kept in ${done.kept}`), 12000);
    } else if (done.again) {
      say(biEl("span", "ml-error", "磁盘上的版本又变了，请再看一次", "The disk version changed again: please look again"));
    } else {  // the conflict stays open: nothing was resolved, nothing was lost
      say(biEl("span", "ml-error",
        "没能完成，冲突仍未解决。没有任何内容丢失：你的文字仍在这里和恢复草稿中，磁盘上的笔记没有改动",
        "Couldn't complete it, so the conflict is still open. Nothing was lost: your text is "
        + `still here and in the recovery draft, and the note on disk is unchanged (${done.message || "no answer"})`),
      15000);
    }
  }

  async function chooseDraft(choice) {
    const note = session();
    if (!note || busy) return;
    if (choice === "discard") {
      note.discardDraft();
      return;
    }
    busy = true;
    render(note);
    const done = await note.restoreDraft();
    busy = false;
    comparing = false;
    render(note);
    if (!done.ok) say(biEl("span", "ml-error", "草稿没能恢复，它仍然保留着", `The draft wasn't restored (it's still kept): ${done.message || ""}`));
    else if (done.conflict) say(biEl("span", "ml-error", "草稿之后文件又被修改了：请选择保留哪一个", "The file changed after the draft: choose which to keep"));
  }

  // --- drafts of documents that left the library (M7.1 S1a) ----------------------------------
  // A draft is kept under the document and note it was typed in. When that document was
  // merged into this one, it is offered here: restored only into a note the user chooses
  // (adoptDraft: never over unsaved text or a draft of that note; the usual version check and
  // conflict), its original kept until a save of exactly the restored text is confirmed. A
  // removed document's drafts can be saved as a file. Nothing here is done without a click;
  // discarding asks first. Dealt-with drafts are never deleted, only marked (drafts.settle)
  let elsewhere = [];  // [{found, status}] shown now
  let scanning = 0;

  async function scanElsewhere() {
    const mine = ++scanning;
    const found = drafts.elsewhere(docId);
    let documents = {};
    if (found.length) {
      const ids = [...new Set(found.map((f) => f.docId))].slice(0, 200);
      try {
        documents = (await post("/api/document/status", { ids })).documents || {};
      } catch {
        documents = {};  // (unknown for now: offered the next time the panel loads)
      }
    }
    if (mine !== scanning) return;
    elsewhere = found.map((f) => ({ found: f, status: documents[f.docId] }))
      .filter(({ status }) => (status?.status === "merged" && status.into === docId)
        || status?.status === "removed");
    renderElsewhere();
  }

  function renderElsewhere() {
    const parts = [];
    for (const item of elsewhere) {
      const { found, status } = item;
      const title = status.title || found.docId;
      const note = String(found.key).replace(/^file:/, "");
      const when = new Date(found.draft.time || 0).toLocaleString();
      const row = el("div", "ml-elsewhere-item");
      row.dataset.storageKey = found.storageKey;
      if (status.status === "merged") {
        row.append(biEl("div", null,
          `已合并到这份文档的“${title}”中有未保存的草稿（${note}，${when}）`,
          `An unsaved draft from “${title}”, merged into this document (${note}, ${when})`));
        const choose = el("select", "ml-elsewhere-target");
        choose.setAttribute("aria-label", "恢复到 Restore into");
        for (const entry of entries) {
          const option = el("option", null, labelOf(entry));
          option.value = entry.key;
          choose.append(option);
        }
        // (the same note name if this document has one, else the note shown now)
        choose.value = entries.some((e) => e.key === found.key) ? found.key : (current || "");
        row.append(bi("恢复到：", "Restore into: "), choose,
          button("恢复", "Restore", () => adopt(item, choose.value), "mlAdoptDraft"));
      } else {
        row.append(biEl("div", null,
          `已移除的“${title}”中有未保存的草稿（${note}，${when}）：可以另存为文件`,
          `An unsaved draft from “${title}”, removed from the library (${note}, ${when}): save it as a file`));
      }
      row.append(
        button("另存为文件", "Save as a file", () => saveAsFile(found.draft.text, found.key, title),
          "mlElsewhereFile"),
        button("丢弃", "Discard", () => {
          if (!window.confirm("丢弃这份草稿？Discard this draft?")) return;
          // (this exact draft only: one written there since by another tab stays offered)
          if (!drafts.settle(found.storageKey, found.raw)) {
            say(biEl("span", "ml-error", "浏览器无法记录：草稿仍然保留着",
              "The browser couldn't record it: the draft is still kept"));
          }
          scanElsewhere();
        }, "mlElsewhereDiscard"),
      );
      parts.push(row);
    }
    elsewhereBox.replaceChildren(...parts);
    elsewhereBox.hidden = !parts.length;
  }

  async function adopt(item, key) {
    if (busy || !entries.some((e) => e.key === key)) return;
    await show(key);
    const note = session();
    if (!note || note.key !== key || !note.loaded) {
      say(biEl("span", "ml-error", "没能打开所选的笔记：草稿仍然保留着",
        "The chosen note couldn't be opened: the draft is still kept"));
      return;
    }
    busy = true;
    render(note);
    const done = await note.adoptDraft(item.found);
    busy = false;
    comparing = false;
    render(note);
    if (done.changed) {
      say(biEl("span", "ml-error", "这份草稿在列出之后又被修改了（另一个标签页）：什么也没有恢复，请再看一次",
        "This draft changed after it was listed (another tab): nothing was restored; look again"), 12000);
      scanElsewhere();
    } else if (done.same && !done.settled) {
      say(biEl("span", "ml-error", "这条笔记已经是草稿的内容，但浏览器无法记录：草稿仍然保留着",
        "This note already holds the draft's text, but the browser couldn't record it: the draft is still kept"), 12000);
    } else if (done.occupied) {
      say(biEl("span", "ml-error", "这条笔记有自己未保存的文字或草稿：请先处理它，或选择另一条笔记。草稿仍然保留着",
        "This note has unsaved text or a draft of its own: settle that first, or choose another note. The draft is still kept"), 12000);
    } else if (!done.ok) {
      say(biEl("span", "ml-error", "草稿没能恢复，它仍然保留着",
        `The draft wasn't restored (it's still kept): ${done.message || ""}`), 12000);
    } else if (done.conflict) {
      say(biEl("span", "ml-error", "这条笔记和草稿所基于的版本不同：请选择保留哪一个。确认保存之前，原草稿一直保留",
        "This note isn't the version the draft was based on: choose which to keep. The original draft is kept until that is saved"), 12000);
    }
  }

  // A text as a .md file, downloaded by the browser (nothing sent to the server)
  function saveAsFile(value, key, title = "") {
    const name = `${(title || "draft").replace(/[^\w.-]+/g, "-").slice(0, 60)}-${
      String(key).replace(/^file:/, "").replace(/[^\w.-]+/g, "-")}`.replace(/\.md$/, "");
    const link = el("a");
    link.href = URL.createObjectURL(new Blob([value], { type: "text/markdown;charset=utf-8" }));
    link.download = `${name}-draft.md`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 60000);
  }

  function saveNow() {
    const note = session();
    if (!note) return;
    if (note.failure) note.retryNow();
    else note.flush();
  }
  saveButton.addEventListener("click", saveNow);

  lockButton.addEventListener("click", () => {
    readOnly = !readOnly;
    store(KEYS.readOnly, readOnly ? "1" : "0");
    if (session()) render(session());
  });

  // A short message under the header (it goes after a few seconds)
  function say(node, ms = 4000) {
    const line = el("div");
    line.append(node);
    status.append(line);
    setTimeout(() => line.remove(), ms);
  }
  editButton.addEventListener("click", async () => {
    if (!current) return;
    try {
      const answer = await post("/api/notes/open", { id: docId, key: current });
      say(answer.opened
        ? biEl("span", "ml-muted", "已在编辑器中打开", "Opened in the editor")
        : biEl("span", "ml-error", "编辑器无法启动", answer.message));
    } catch (error) {
      say(biEl("span", "ml-error", "无法打开", error.message));
    }
  });

  // --- typing ---------------------------------------------------------------------------

  text.addEventListener("input", () => typing()?.edit(text.value));
  // Chinese input: nothing is saved while a word is being composed. The composition ends on
  // the session it started in, even if the note changed meanwhile (else that one never
  // autosaves again); its text is taken only if the box still holds that note
  let composingIn = null;
  text.addEventListener("compositionstart", () => {
    composingIn = typing();
    composingIn?.setComposing(true);
  });
  text.addEventListener("compositionend", () => {
    const note = composingIn;
    composingIn = null;
    if (note && note === typing()) note.edit(text.value);
    note?.setComposing(false);
  });

  // Markdown helpers (decision D7), through insertText so the browser's own Undo still undoes
  // them: Tab / Shift+Tab indent or outdent the line(s); Enter continues a list or a quote,
  // and ends it on an empty item. Never during IME composition
  const insert = (value) => document.execCommand("insertText", false, value);
  const lineStartAt = (value, at) => value.lastIndexOf("\n", at - 1) + 1;

  function indent(outdent) {
    const { value, selectionStart: start, selectionEnd: end } = text;
    if (!outdent && start === end) return insert("  ");
    const from = lineStartAt(value, start);
    const last = end > start && value[end - 1] === "\n" ? end - 1 : end;
    let to = value.indexOf("\n", last);
    if (to === -1) to = value.length;
    const block = value.slice(from, to);
    const changed = block.split("\n")
      .map((line) => (outdent ? line.replace(/^( {1,2}|\t)/, "") : `  ${line}`)).join("\n");
    if (changed === block) return true;
    text.setSelectionRange(from, to);
    insert(changed);
    text.setSelectionRange(from, from + changed.length);
    return true;
  }

  function continueBlock() {
    const { value, selectionStart: start, selectionEnd: end } = text;
    if (start !== end) return false;
    const from = lineStartAt(value, start);
    const line = value.slice(from, start);
    const rest = value.slice(start, value.indexOf("\n", start) === -1 ? value.length : value.indexOf("\n", start));
    const item = line.match(/^(\s*)(?:([-*+])|(\d+)([.)]))(\s+)(\[[ xX]\]\s+)?/);
    const quote = line.match(/^(\s*(?:>\s?)+)/);
    const marker = item ? item[0] : quote ? quote[1] : null;
    if (!marker) return false;
    if (line === marker && !rest.trim()) {  // an empty item or quote line: the list ends here
      text.setSelectionRange(from, start);
      insert("");
      return true;
    }
    if (item) {
      const next = item[2] || `${Number(item[3]) + 1}${item[4]}`;
      insert(`\n${item[1]}${next}${item[5]}${item[6] ? "[ ] " : ""}`);
    } else {
      insert(`\n${quote[1]}`);
    }
    return true;
  }

  // --- formatting (M5c) ---------------------------------------------------------------------

  const formatting = window.myLibraryFormat;
  let composing = false;  // an IME word being composed: formatting waits for it
  // (added after the session's own composition listeners, so the toolbar is set last)
  text.addEventListener("compositionstart", () => {
    composing = true;
    syncTools();
  });
  text.addEventListener("compositionend", () => {
    composing = false;
    syncTools();
  });
  const canFormat = () => Boolean(formatting) && !text.readOnly && !composing && Boolean(typing());

  // One action: one replacement of the source through insertText (so one Undo reverts it, and
  // the input event hands it to the session), then the selection format.js gives
  function format(action) {
    if (!canFormat()) return false;
    const edit = formatting.apply(text.value, text.selectionStart, text.selectionEnd, action);
    text.focus({ preventScroll: true });
    if (!edit) return true;
    if (text.value.slice(edit.from, edit.to) !== edit.text) {
      text.setSelectionRange(edit.from, edit.to);
      if (!document.execCommand("insertText", false, edit.text)) {
        // (no insertText: the text still changes and is saved, without the browser's Undo)
        text.setRangeText(edit.text, edit.from, edit.to, "end");
        text.dispatchEvent(new Event("input"));
      }
    }
    text.setSelectionRange(edit.selStart, edit.selEnd);
    return true;
  }

  function syncTools() {
    const off = !canFormat();
    headingMenu.disabled = off;
    for (const b of toolButtons) b.disabled = off;
    formulaButton.disabled = off || !window.myLibraryFormula;
    tools.dataset.state = off ? "off" : "on";
  }

  // --- pasted images (M5d) and formulas (M5e) ------------------------------------------------
  //
  // Saving an image and saving the note are separate: the image is written at once (its own
  // request, a new file in the document's assets/), then its link is typed into the note like
  // any other edit (one insertText: one Undo; the session saves it). An image is never deleted
  // here: not when the note's save fails or meets a conflict, not when its link is undone.
  // Anything that finishes later is put in only where it was asked for: the same note, still
  // in the box, its text unchanged since; otherwise the image is kept and the user is offered
  // to insert its link where they are now.

  const MAX_IMAGE = 10 * 1024 * 1024;
  const IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp"];
  const MAX_IMAGES = 10;  // in one paste
  let formulaNext = 0;  // Ctrl+Shift+V was pressed just now: the next image is a formula

  // Where an insertion was asked for: the note, its text then, the selection then
  const target = () => ({
    note: typing(), key: text.dataset.key, value: text.value,
    start: text.selectionStart, end: text.selectionEnd,
  });
  // The box still shows that note, unchanged, and it can be typed in
  const sameTarget = (at) => at.note && typing() === at.note && text.dataset.key === at.key
    && !text.readOnly && !composing;

  // One edit of the source, as the toolbar's: insertText (one Undo, the input event reaches
  // the session), or without it a plain change that is still saved
  function replaceRange(from, to, value) {
    text.focus({ preventScroll: true });
    text.setSelectionRange(from, to);
    if (!document.execCommand("insertText", false, value)) {
      text.setRangeText(value, from, to, "end");
      text.dispatchEvent(new Event("input"));
    }
  }

  function imagesOf(data) {
    const found = [];
    for (const item of data?.items || []) {
      if (item.kind === "file" && item.type.startsWith("image/")) {
        const file = item.getAsFile();
        if (file) found.push(file);
      }
    }
    if (!found.length) found.push(...[...(data?.files || [])].filter((f) => f.type.startsWith("image/")));
    return found;
  }

  async function uploadImage(file, key) {
    const abort = new AbortController();
    const timer = setTimeout(() => abort.abort(), 60_000);
    try {
      const response = await fetch("/api/notes/asset", {
        method: "POST",
        headers: {
          "X-Library-Token": reader.token, "X-Document-Id": docId,
          "X-Note-Key": encodeURIComponent(key), "Content-Type": "application/octet-stream",
        },
        body: file,
        signal: abort.signal,
      });
      const data = await response.json();
      if (response.status === 403) throw new Error("the server was restarted: reload this page");
      if (!response.ok) throw new Error(data.error || response.statusText);
      if (typeof data.path !== "string" || !assetUrl(data.path)) {
        throw new Error("the server returned an invalid image path");
      }
      return data;
    } catch (error) {
      if (error.name === "AbortError") throw new Error("no answer from the server in time");
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }

  const imageLink = (saved) => `![image](${saved.path})`;

  // Saved images whose links couldn't go where they were asked for: kept, and offered here
  function offerLinks(links) {
    body.dataset.mlPaste = "kept";
    const markdown = links.join("\n");
    const insertHere = button("插入到当前位置", "Insert here", () => {
      const at = target();
      if (!sameTarget(at) || !at.key?.startsWith("file:")) {
        say(biEl("span", "ml-error", "现在不能编辑这条笔记", "This note can't be edited right now"));
        return;
      }
      replaceRange(at.start, at.end, markdown);
      line.remove();
    });
    insertHere.classList.add("mlInsertKept");
    const line = el("div", "ml-paste-kept");
    line.append(biEl("span", "ml-muted", `图片已保存，但没有插入（笔记在此期间变了）：${markdown}`,
      `The image is saved but its link wasn't inserted (the note changed meanwhile): ${markdown}`),
    insertHere);
    status.append(line);
    setTimeout(() => line.remove(), 120_000);
  }

  // Ctrl+V of one or more images: each saved, then their links inserted at once
  async function pasteImages(files, at = target()) {
    if (!sameTarget(at)) {
      body.dataset.mlPaste = "refused";
      say(biEl("span", "ml-error", "这条笔记现在不能编辑（只读或正在载入）",
        "This note can't be edited right now (read-only or loading): nothing was pasted"));
      return;
    }
    if (!at.key?.startsWith("file:")) {
      body.dataset.mlPaste = "refused";
      say(biEl("span", "ml-error", "图片只能粘贴到这份文档自己的笔记中", "Images can be pasted only into this document's own notes"));
      return;
    }
    const wrong = files.find((f) => !IMAGE_TYPES.includes(f.type) || f.size > MAX_IMAGE);
    if (wrong || files.length > MAX_IMAGES) {
      body.dataset.mlPaste = "refused";
      say(biEl("span", "ml-error", "只能粘贴 PNG、JPEG 或 WebP 图片，每张不超过 10 MB，一次最多 10 张",
        "Only PNG, JPEG and WebP images of at most 10 MB, up to 10 at a time, can be pasted"), 8000);
      return;
    }
    body.dataset.mlPaste = "saving";
    const saving = biEl("span", "ml-muted", "正在保存图片…", "Saving the image…");
    say(saving, 60_000);
    const links = [];
    let failure = null;
    for (const file of files) {
      try {
        links.push(imageLink(await uploadImage(file, at.key)));
      } catch (error) {
        failure = error;
        break;  // (the ones saved before are still inserted)
      }
    }
    saving.parentElement?.remove();
    if (failure) {
      say(biEl("span", "ml-error", "图片没有保存", `The image wasn't saved: ${failure.message}`), 10_000);
    }
    if (!links.length) {
      body.dataset.mlPaste = "failed";
      return;
    }
    if (sameTarget(at) && text.value === at.value) {
      replaceRange(at.start, at.end, links.join("\n"));
      body.dataset.mlPaste = failure ? "failed" : "inserted";
    } else {
      offerLinks(links);
    }
  }

  // --- quotes from the PDF (task 4 M6) --------------------------------------------------------
  //
  // lookup.js captures the selection (or the page, 引用此页) and calls quote() below. The
  // anchor is stored first (/api/references/create: references.py, private); only then is the
  // short quote with its link typed into the note, as one insertText (one Undo; the session
  // saves it like any edit, with its conflicts, drafts and retries). Nothing goes into the note
  // when the anchor wasn't stored, and nothing into another note than the one it was asked for
  // (taken with the click or key, before the PDF side's work: takeTarget). A note left before
  // the anchor is stored gets nothing (said so); one that changed or was left while it was
  // stored gets an offer to insert it, in that same note only.

  const anchors = window.myLibraryAnchors;
  // Recorded at the user's own clicks, keys and edits: the box's selection itself can't be read
  // later (moving the page's selection into the PDF resets it, with no event)
  const noteCaret = () => {
    caretAt = { key: text.dataset.key || null, pos: text.selectionEnd, value: text.value };
  };
  for (const type of ["click", "keyup", "input"]) text.addEventListener(type, noteCaret);
  const caretFor = (at) => (caretAt && caretAt.key === at.key && caretAt.value === at.value
    ? Math.min(caretAt.pos, at.value.length) : at.value.length);
  let quoting = false;

  async function createReference(capture, key) {
    const abort = new AbortController();
    const timer = setTimeout(() => abort.abort(), 30_000);
    try {
      const response = await fetch("/api/references/create", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Library-Token": reader.token },
        body: JSON.stringify({ ...capture, id: docId, note_key: key }),
        signal: abort.signal,
      });
      const data = await response.json().catch(() => ({}));
      if (response.status === 403) {
        throw new Error("request refused (403): this page may be outdated; reload it");
      }
      if (!response.ok) throw new Error(data.error || response.statusText);
      if (typeof data.rid !== "string" || !/^r[0-9a-f]{16}$/.test(data.rid)) {
        throw new Error("the server returned an invalid reference");
      }
      return data;
    } catch (error) {
      if (error.name === "AbortError") throw new Error("no answer from the server in time");
      if (error instanceof TypeError) throw new Error("myLibrary isn't reachable");
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }

  // The quote as a block of its own: a blank line before and after it
  function asBlock(value, where, markdown) {
    const before = value.slice(0, where);
    const after = value.slice(where);
    const lead = !before || before.endsWith("\n\n") ? "" : before.endsWith("\n") ? "\n" : "\n\n";
    const tail = !after ? "\n" : after.startsWith("\n\n") ? "" : after.startsWith("\n") ? "\n" : "\n\n";
    return lead + markdown + tail;
  }

  // A quote stored for a note that changed or was left while it was stored: offered for that
  // same note only (its record names it; never another note), once the user is back in it
  function offerQuote(markdown, key) {
    body.dataset.mlQuote = "kept";
    const name = noteName(key);
    const insertHere = button("插入引用", "Insert the quote", () => {
      const at = target();
      if (at.key !== key || current !== key) {
        say(biEl("span", "ml-error", `先回到“${name}”再插入`, `Go back to ${name} to insert it`));
        return;
      }
      if (!sameTarget(at) || unsafe(at.note)) {
        say(biEl("span", "ml-error", "现在不能编辑这条笔记", "This note can't be edited right now"));
        return;
      }
      const where = caretFor(at);
      replaceRange(where, where, asBlock(at.value, where, markdown));
      body.dataset.mlQuote = "inserted";
      dropLine(line);
    });
    insertHere.classList.add("mlInsertQuote");
    const line = el("div", "ml-paste-kept ml-quote-kept");
    line.append(biEl("span", "ml-muted", `引用已记录，但没有插入（“${name}”在此期间变了或被离开）`,
      `The quote is recorded but wasn't inserted (${name} changed or was left meanwhile)`), insertHere);
    keepLine(line, 120_000);
  }

  function noteName(key) {
    const entry = entries.find((e) => e.key === key);
    return entry ? labelOf(entry) : String(key).replace(/^file:/, "");
  }
  // A quote never goes into a note with a conflict or a recovery draft to settle first, nor
  // while the page must be reloaded (the server restarted)
  const unsafe = (note) => ["conflict", "draft", "restarted"].includes(note?.state);
  const NOT_EDITABLE = ["先打开一条可以编辑的笔记，再引用（只读、正在载入、有冲突或草稿时不能引用）",
    "Open a note you can edit, then quote again (not while it is read-only or loading, or has a conflict or a draft to settle)"];
  const LEFT = ["引用期间换了笔记：什么也没有插入，请重新引用",
    "Another note was chosen while quoting: nothing was inserted; quote again"];
  const BUSY = ["上一个引用还没完成", "The previous quote isn't finished yet"];

  function refuse([zh, en]) {
    body.dataset.mlQuote = "refused";
    say(biEl("span", "ml-error", zh, en), 8000);
  }

  // Where a quote goes, taken the moment it is asked for, before anything is awaited (Codex
  // M6 review): the note in the box and its caret then; or, while the panel is still loading
  // (never opened yet, or a note on its way), the note it is loading, waited for later; null
  // when no note can take it
  function takeTarget() {
    const at = target();
    if (sameTarget(at) && !unsafe(at.note)) return { ...at, where: caretFor(at) };
    if (!listed || underWay) {
      return { pending: true, key: underWay ? requested : null, choices: userChoices };
    }
    return null;
  }

  // After awaiting: the target still valid ({problem} if not). A pending one once its note is
  // in the box, and only if the user chose no other note meanwhile. A taken one only if that
  // same note (its own session) is in the box again; typed in meanwhile: at the caret now
  async function settleTarget(taken) {
    if (taken.pending) {
      for (let seen = null; seen !== loading;) {  // (a load may start the next one: all of them)
        seen = loading;
        try {
          await seen;
        } catch {
          // the panel says why
        }
      }
      if (userChoices !== taken.choices || (taken.key && current !== taken.key)) {
        return { problem: LEFT };
      }
      const at = target();
      if (!sameTarget(at) || unsafe(at.note)) return { problem: NOT_EDITABLE };
      return { ...at, where: caretFor(at) };
    }
    if (current !== taken.key || !sameTarget(taken)) return { problem: LEFT };
    if (unsafe(taken.note)) return { problem: NOT_EDITABLE };
    if (text.value === taken.value) return taken;
    const at = target();
    return { ...at, where: caretFor(at) };
  }

  // lookup.js calls this in the same task as the user's click or key (toNotes there), with a
  // promise of the anchor (null: it couldn't be made, already said)
  function quote(pending) {
    const taken = takeTarget();
    if (quoting) {
      Promise.resolve(pending).catch(() => {});
      say(biEl("span", "ml-muted", ...BUSY));
      return;
    }
    quoting = true;  // (the panel shows nothing until the anchor is made)
    quoteWhenReady(taken, pending).finally(() => { quoting = false; });
  }

  async function quoteWhenReady(taken, pending) {
    const capture = await Promise.resolve(pending).catch(() => null);
    if (!capture) return;  // (said by lookup.js; the notes are left alone)
    if (!open) setOpen(true, true);  // (only now: a quote that can't be made opens nothing)
    if (!taken) return refuse(NOT_EDITABLE);
    const at = await settleTarget(taken);
    if (at.problem) return refuse(at.problem);
    await deliver(capture, at);
  }

  // The anchor stored first, then the quote typed into the note it was asked for, as one
  // insertText (one Undo; saved like any edit). Nothing goes into the note when the anchor
  // wasn't stored
  async function deliver(capture, at) {
    body.dataset.mlQuote = "saving";
    let made;
    try {
      made = await createReference(capture, at.key);
    } catch (error) {
      body.dataset.mlQuote = "failed";
      // Trying again sends the same request (its nonce): a reference stored before an answer
      // was lost is found, not made twice; and only into the same note
      const again = button("重试", "Retry", () => {
        if (quoting) {
          say(biEl("span", "ml-muted", ...BUSY));
          return;
        }
        dropLine(line);
        quoting = true;
        (async () => {
          const now = await settleTarget(at);
          if (now.problem) return refuse(now.problem);
          await deliver(capture, now);
        })().finally(() => { quoting = false; });
      });
      again.classList.add("mlQuoteRetry");
      const line = el("div", "ml-error ml-quote-failed");
      line.append(biEl("span", null, "引用没有记录，笔记中没有插入任何内容",
        `The quote wasn't recorded, nothing was inserted: ${error.message}`), " ", again);
      keepLine(line, 60_000);
      return;
    }
    const page = capture.page + 1;  // links count pages from 1
    const visible = capture.kind === "text" ? anchors.excerpt(capture.exact) : "";
    const url = anchors.sourceUrl(location.origin, docId, page, made.rid, visible.replace(/ …$/, ""));
    const markdown = capture.kind === "text"
      ? anchors.quoteMarkdown(capture.exact, page, url) : anchors.pageMarkdown(page, url);
    if (current === at.key && sameTarget(at) && !unsafe(at.note) && text.value === at.value) {
      replaceRange(at.where, at.where, asBlock(at.value, at.where, markdown));
      body.dataset.mlQuote = "inserted";
    } else {
      offerQuote(markdown, at.key);
    }
  }

  window.myLibraryNotes = Object.freeze({ quote });

  text.addEventListener("keydown", (event) => {
    if (event.code === "KeyV" && (event.ctrlKey || event.metaKey) && event.shiftKey && !event.altKey) {
      formulaNext = Date.now();
    }
  });

  // Ctrl+V: text as before; an image (and no text) is saved and linked. Ctrl+Shift+V with an
  // image: the ∑ dialog. Nothing during IME composition or while the note can't be typed in
  text.addEventListener("paste", (event) => {
    const asFormula = Date.now() - formulaNext < 1000;
    formulaNext = 0;
    const files = imagesOf(event.clipboardData);
    if (!files.length || composing) return;  // text: the browser's own paste
    if (!asFormula && event.clipboardData.getData("text/plain").trim()) return;  // text wins
    event.preventDefault();
    event.stopPropagation();  // (never PDF.js's paste)
    if (asFormula) openFormula(files[0]);
    else pasteImages(files);
  });

  // The delimiters a confirmed formula is written with, so that the preview reads it back
  // whole (preview.js closesAtEnd, its own rules): $…$ / $$…$$ as usual; \(…\) / \[…\] when
  // the LaTeX itself would end those early (a "$" of its own, as in \text{$x$}, or a digit
  // right after an inline one). The LaTeX is kept exactly as confirmed. Only if no pair reads
  // back whole are its unpaired dollar signs escaped (\$, a dollar sign to KaTeX)
  function delimited(body, pairs, next) {
    const fits = window.myLibraryPreview?.closesAtEnd;
    for (const [open, close] of pairs) {
      if (!fits || fits(body, close, next)) return `${open}${body}${close}`;
    }
    const [open, close] = pairs[0];
    // (a backslash and the character after it are a pair, as LaTeX and the preview read them)
    return `${open}${body.replace(/\\[\s\S]|\$/g, (m) => (m === "$" ? "\\$" : m))}${close}`;
  }

  // $$…$$ on lines of its own (a blank line around it, so it is a block), or $…$ in the line
  function formulaMarkdown(latex, display, before, after) {
    // (right after an unpaired backslash, a delimiter would be read as an escaped character)
    const space = /(^|[^\\])(\\\\)*\\$/.test(before) ? " " : "";
    if (!display) {
      const body = latex.replace(/\s*\n\s*/g, " ");
      // "$" right after another "$" would make "$$": then only \(…\)
      const pairs = before.endsWith("$") ? [["\\(", "\\)"]] : [["$", "$"], ["\\(", "\\)"]];
      return space + delimited(body, pairs, after.slice(0, 1));
    }
    const lines = latex.replace(/\n\s*\n/g, "\n");
    const lead = !before || before.endsWith("\n\n") ? "" : before.endsWith("\n") ? "\n" : "\n\n";
    const tail = after.startsWith("\n\n") ? "" : after.startsWith("\n") ? "\n" : after ? "\n\n" : "\n";
    const block = delimited(`\n${lines}\n`, [["$$", "$$"], ["\\[", "\\]"]], "");
    return `${lead}${block}${tail}`;
  }

  function openFormula(image = null) {
    const formula = window.myLibraryFormula;
    const at = target();
    if (!formula) return;
    if (!sameTarget(at)) {
      say(biEl("span", "ml-error", "这条笔记现在不能编辑（只读或正在载入）",
        "This note can't be edited right now (read-only or loading)"));
      return;
    }
    formula.open({
      host: panel,
      image,
      // The confirmed LaTeX, into the note it was asked for, or a reason why not
      insert(latex, display) {
        if (!sameTarget(at)) {
          return ["这条笔记已不在编辑器中或不能编辑：没有插入", "The note it was for is no longer open or can't be edited: nothing was inserted"];
        }
        if (text.value === at.value) text.setSelectionRange(at.start, at.end);
        const { selectionStart: from, selectionEnd: to, value } = text;
        replaceRange(from, to, formulaMarkdown(latex, display, value.slice(0, from), value.slice(to)));
        body.dataset.mlFormula = "inserted";
        return null;
      },
      asImage(blob) {
        pasteImages([blob], at);
      },
    });
  }
  formulaButton.addEventListener("click", () => openFormula());
  // The buttons never take the focus from the note (its selection stays where it was)
  tools.addEventListener("mousedown", (event) => {
    if (event.target.closest("button")) event.preventDefault();
  });
  for (const b of toolButtons) b.addEventListener("click", () => format(b.dataset.action));
  headingMenu.addEventListener("change", () => {
    const action = headingMenu.value;
    headingMenu.value = "";
    if (action) format(action);
  });

  // Ctrl+B / Ctrl+I: only here, while typing in the note (by the key's position, so any
  // layout or IME); stopped here, so PDF.js and the browser never see them
  text.addEventListener("keydown", (event) => {
    const shortcut = { KeyB: "bold", KeyI: "italic" }[event.code];
    if (!shortcut || !(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey) return;
    event.preventDefault();
    event.stopPropagation();
    if (!event.isComposing && event.keyCode !== 229) format(shortcut);
  });

  text.addEventListener("keydown", (event) => {
    if (text.readOnly || event.isComposing || event.keyCode === 229) return;
    if (event.key === "Tab" && !event.ctrlKey && !event.altKey && !event.metaKey) {
      event.preventDefault();
      indent(event.shiftKey);
    } else if (event.key === "Enter" && !event.shiftKey && !event.ctrlKey && !event.altKey
      && !event.metaKey && continueBlock()) {
      event.preventDefault();
    }
  });

  // --- leaving, and changes made elsewhere ------------------------------------------------

  // The browser asks before the tab is closed, reloaded or left while any note has text the
  // server hasn't confirmed; the recovery draft keeps it too (decision D1)
  addEventListener("beforeunload", (event) => {
    if (![...sessions.values()].some((note) => note.unconfirmed)) return;
    event.preventDefault();
    event.returnValue = "";
  });
  addEventListener("pagehide", () => sessions.forEach((note) => note.leaving()));
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") sessions.forEach((note) => note.queueDraft(true));
  });

  // The note on screen is checked for changes made elsewhere when the tab comes back, and
  // every 5 s while the panel shows it (decision D6)
  const check = () => {
    if (open && document.visibilityState === "visible") session()?.checkDisk();
  };
  addEventListener("focus", check);
  document.addEventListener("visibilitychange", check);
  setInterval(check, 5000);

  apply(false);
  setView(view, false);
  syncTools();
  if (open) loadList();
})();
