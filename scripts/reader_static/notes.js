// 📝 Notes beside the PDF (task 4 M3): the document's Markdown notes in a panel to the right of
// PDF.js, read-only in this version (writing in the panel comes with M4). Served with
// lookup.js by reader.viewer_html; uses lookup.js's token and requests (myLibraryReader).
//
// - The notes are found by the document's id and a note key ("file:README.md",
//   "file:ch02-….md"), never by a path: /api/notes/list, /api/notes/get, /api/notes/open.
// - Nothing here writes anything: no note, no reading position, no reading time.
// - Layout by the window's width: beside the PDF from 1100 px, over the PDF (a drawer) from
//   760 px, the whole window below that. Beside the PDF it is remembered (open or not, its
//   width as a share of the window); in narrower windows it starts closed.
// - State for tests (and nothing else) on <body>: data-ml-notes (open/closed),
//   data-ml-notes-mode (side/drawer/full), data-ml-note-key, data-ml-note-state
//   (loading/shown/empty/missing/none/error).
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
    last: `myLibrary.notes.last.${docId}`,
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
  head.append(menu, editButton, closeButton);
  const status = el("div", "ml-notes-status");
  status.id = "mlNotesStatus";
  status.setAttribute("role", "status");
  const text = el("pre", "ml-note-text");  // the note as plain text (textContent): never HTML
  text.id = "mlNoteText";
  text.tabIndex = 0;
  text.setAttribute("aria-label", "笔记内容（只读）Note (read-only)");
  panel.append(divider, head, status, text);
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

  // Alt+N anywhere in the reader (by the key's position, so any keyboard layout or IME)
  addEventListener("keydown", (event) => {
    if (event.code !== "KeyN" || !event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    event.preventDefault();
    event.stopPropagation();
    setOpen(!open, true);
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
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    event.stopPropagation();
  });

  // --- the notes ----------------------------------------------------------------------------

  let entries = [];
  let listed = false;
  let current = null;
  let asked = 0;  // the latest request: an earlier answer arriving late is ignored
  const openedAt = Number((location.hash.match(/page=(\d+)/) || [])[1]) || null;

  function setState(state, ...nodes) {
    body.dataset.mlNoteState = state;
    status.replaceChildren(...nodes);
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

  async function loadList() {
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
    menu.disabled = !entries.length;
    if (!entries.length) {
      text.textContent = "";
      editButton.disabled = true;
      setState("none", biEl("span", "ml-muted", "这份文档还没有笔记", "No notes for this document yet"));
      return;
    }
    show(firstKey(), { chosen: false });
  }

  // `chosen`: by the user (remembered for this document); `quiet`: a refresh of the same note
  async function show(key, { chosen = true, quiet = false } = {}) {
    const mine = ++asked;
    current = key;
    menu.value = key;
    body.dataset.mlNoteKey = key;
    if (chosen) store(KEYS.last, key);
    const entry = entries.find((item) => item.key === key);
    editButton.disabled = !entry?.exists;
    if (!quiet) setState("loading", biEl("span", "ml-muted", "载入中…", "Loading…"));
    let note;
    try {
      note = await post("/api/notes/get", { id: docId, key });
    } catch (error) {
      if (mine === asked) failed(error, () => show(key, { chosen: false }));
      return;
    }
    if (mine !== asked) return;  // another note was chosen meanwhile: the last choice wins
    editButton.disabled = !note.exists;
    if (text.textContent !== note.text) {
      text.textContent = note.text;
      if (!quiet) text.scrollTop = 0;
    }
    if (!note.exists) {
      setState("missing",
        biEl("div", "ml-muted", "这一章还没有笔记", "No notes for this chapter yet"),
        biEl("div", "ml-muted", "在这里书写将在之后的版本提供",
          "Writing in this panel comes in a later version"));
    } else if (!note.text.trim()) {
      setState("empty", biEl("span", "ml-muted", "这条笔记还是空的", "This note is empty"));
    } else {
      setState("shown");
    }
  }

  menu.addEventListener("change", () => show(menu.value));

  // A short message under the header (it goes after a few seconds)
  function say(node) {
    const line = el("div");
    line.append(node);
    status.append(line);
    setTimeout(() => line.remove(), 4000);
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

  // Back in the tab (perhaps after editing the note in VS Code): the note as it is now
  const refresh = () => {
    if (open && current && document.visibilityState === "visible"
      && body.dataset.mlNoteState !== "loading") show(current, { chosen: false, quiet: true });
  };
  addEventListener("focus", refresh);
  document.addEventListener("visibilitychange", refresh);

  apply(false);
  if (open) loadList();
})();
