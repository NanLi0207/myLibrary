// Task 4 M7: back from a note to its passage (note → PDF), in the reading view.
//
// A reference link M6 wrote (anchors.js parseReference) is followed here, within this tab when
// it names this document (or one merged into it), else in a new preview tab. The passage is
// found again (DEVELOPMENT_SPEC 9.2; the plan's §3) and outlined for a moment (never written
// into the PDF); ↩ Back returns to where you were, step by step. The note in the panel, its
// caret, unsaved text and Undo are never touched: nothing here calls notes.js or its session,
// sets the editor's text, or moves the focus. Reading progress is left alone while visiting
// (lookup.js `tracking`): every programmatic move is announced to it first.
//
// Following a link writes nothing: /api/references/get and /api/document/ids are read-only.
(() => {
  "use strict";
  const R = window.myLibraryReader;
  const A = window.myLibraryAnchors;
  const T = window.myLibraryTracking;
  if (!R || !A || !T || !R.docId) return;
  const app = () => window.PDFViewerApplication;
  const bus = () => app().eventBus;
  const viewer = () => app().pdfViewer;
  const bi = (zh, en) => `${zh} (${en})`;
  const SEARCH_PAGES = 3000, SEARCH_MS = 30000, LIMIT = 50, SHOWN_MS = 4000;

  const merged = new Set();  // ids merged into this document (/api/document/ids at load)
  const stack = [];  // Back: where you were before each jump that moved the reader
  let current = null;  // the navigation still running, if any
  let number = 0;
  let mark = null;  // the outlined passage: {page, rects, timer}

  function setState(name, value) {
    if (value == null) delete document.body.dataset[name];
    else document.body.dataset[name] = value;
  }
  function say(zh, en) {
    R.notice(zh, en);
    controls.status.textContent = bi(zh, en);
  }

  // --- the controls: ↩ Back · n, Continue reading here, the search's progress, choices -------
  const controls = (() => {
    const box = R.el("div", "ml-nav");
    box.setAttribute("role", "region");
    box.setAttribute("aria-label", "引用导航 Reference navigation");
    const backButton = R.biEl("button", "ml-small ml-nav-back", "↩ 返回", "Back");
    backButton.title = "回到跟随引用之前的位置 Back to where you were before following the reference";
    const count = R.el("span", "ml-nav-count");
    backButton.append(count);
    const here = R.biEl("button", "ml-small ml-nav-here", "在这里继续阅读", "Continue reading here");
    const stop = R.biEl("button", "ml-small ml-nav-stop", "停止查找", "Cancel search");
    const status = R.el("div", "ml-nav-status");
    status.setAttribute("aria-live", "polite");
    const choices = R.el("div", "ml-nav-choices");
    box.append(backButton, here, stop, status, choices);
    stop.onclick = () => { if (current) current.stopped = true; };
    // A click here keeps the focus where it was (the note's caret, the PDF), as M6's quote button
    box.addEventListener("mousedown", (event) => {
      if (event.target.closest("button")) event.preventDefault();
    });
    backButton.onclick = () => back();
    here.onclick = () => {
      endVisit();
      T.continueHere();
    };
    box.hidden = true;
    document.body.append(box);
    return { box, backButton, count, here, stop, status, choices };
  })();

  function render() {
    const working = Boolean(current) || controls.choices.childElementCount > 0;
    controls.box.hidden = !stack.length && !working;
    controls.backButton.hidden = !stack.length;
    controls.here.hidden = !stack.length;
    controls.stop.hidden = !current?.searching;
    controls.count.textContent = stack.length ? ` · ${stack.length}` : "";
    setState("mlBack", String(stack.length));
  }

  // --- where you are: one consistent snapshot, read at once ---------------------------------
  function snapshot() {
    const v = viewer();
    const c = v.container;
    const area = c.getBoundingClientRect();
    let index = Math.max(0, v.currentPageNumber - 1);
    // the page under the view's top-left corner (page-at-a-time scrolling: the page shown)
    for (let i = 0; v.scrollMode !== 3 && i < v.pagesCount; i++) {
      if (v.getPageView(i).div.getBoundingClientRect().bottom > area.top + 1) {
        index = i;
        break;
      }
    }
    const view = v.getPageView(index);
    const box = view.div.getBoundingClientRect();
    const [x, y] = view.viewport.convertToPdfPoint(
      area.left - box.left - view.div.clientLeft, area.top - box.top - view.div.clientTop);
    return {
      doc: R.docId, page: index + 1, point: [x, y], scaleValue: v.currentScaleValue,
      scale: v.currentScale, rotation: v.pagesRotation, scrollMode: v.scrollMode,
      spreadMode: v.spreadMode, width: c.clientWidth, height: c.clientHeight,
      top: c.scrollTop, left: c.scrollLeft,
    };
  }

  function restore(entry) {
    const v = viewer();
    const c = v.container;
    // PDF.js's scroll and spread modes and the page first: in page-at-a-time scrolling the
    // offsets below are within the page shown, so the page must be the one you were on
    if (v.scrollMode !== entry.scrollMode) v.scrollMode = entry.scrollMode;
    if (v.spreadMode !== entry.spreadMode) v.spreadMode = entry.spreadMode;
    if (v.currentPageNumber !== entry.page) v.currentPageNumber = entry.page;
    const same = v.currentScale === entry.scale && v.pagesRotation === entry.rotation
      && v.scrollMode === entry.scrollMode && v.spreadMode === entry.spreadMode
      && c.clientWidth === entry.width && c.clientHeight === entry.height;
    if (same) {  // nothing changed: exactly where you were
      c.scrollTop = entry.top;
      c.scrollLeft = entry.left;
      return;
    }
    if (v.currentScaleValue !== entry.scaleValue) v.currentScaleValue = entry.scaleValue;
    v.scrollPageIntoView({  // the same point of the page at the top-left, at that zoom
      pageNumber: entry.page, allowNegativeOffset: true,
      destArray: [null, { name: "XYZ" }, entry.point[0], entry.point[1], null],
    });
  }

  // --- programmatic moves: announced to tracking, settled before tracking may count -------
  function settle(id) {
    const v = viewer();
    const c = v.container;
    let seen = false;
    let lastPage = performance.now();
    let position = null;
    let still = 0;
    const onUpdate = () => { seen = true; };
    const onPage = () => { lastPage = performance.now(); };
    bus().on("updateviewarea", onUpdate);
    bus().on("pagechanging", onPage);
    const started = performance.now();
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      bus().off("updateviewarea", onUpdate);
      bus().off("pagechanging", onPage);
      T.settled(id);
    };
    const step = () => {
      if (done) return;
      const now = `${c.scrollTop},${c.scrollLeft}`;
      still = now === position ? still + 1 : 0;
      position = now;
      if ((still >= 2 && seen && performance.now() - lastPage >= 150)
        || performance.now() - started > 1000) {
        finish();
      } else {
        requestAnimationFrame(step);
      }
    };
    requestAnimationFrame(step);
    setTimeout(finish, 1200);  // (no animation frames in a hidden tab)
    return finish;
  }

  // One programmatic move of navigation `nav`; the first one puts `nav`'s origin on the Back
  // stack (never for a navigation that didn't move: no phantom entries)
  function move(nav, how) {
    if (!alive(nav)) return false;
    if (!nav.moved) {
      nav.moved = true;
      if (nav.entry) {
        T.visit();
        if (stack.length >= LIMIT) stack.splice(1, 1);  // the original place is kept
        stack.push(nav.entry);
      }
    }
    const id = T.programmatic();
    nav.moves.add(id);
    how();
    settle(id);
    render();
    return true;
  }

  function alive(nav) {
    return nav === current && !nav.abort.signal.aborted && app().pdfDocument === nav.pdf;
  }

  function cancel(nav) {
    if (!nav) return;
    nav.abort.abort();
    nav.moves.forEach((id) => T.settled(id));  // (cancelled: it moves nothing more)
    if (current === nav) {
      current = null;
      setState("mlRefResult", "cancelled");
    }
  }

  // Your own move in the PDF while a passage is being found cancels only the last fine scroll
  // (B19: your move wins); typing in the note or a modifier key isn't one
  for (const type of ["pointerdown", "wheel", "keydown", "touchstart"]) {
    addEventListener(type, (event) => {
      if (!current || !event.isTrusted) return;
      const target = event.target?.nodeType === Node.ELEMENT_NODE ? event.target
        : event.target?.parentElement;
      if (target?.closest?.(".ml-notes, .ml-nav, .ml-popup, .ml-bubble")) return;
      if (event.type === "keydown" && ["Shift", "Control", "Alt", "Meta"].includes(event.key)) return;
      if (target?.closest?.("#viewerContainer, #toolbarContainer, #sidebarContainer")
        || event.type === "keydown") {
        current.yours = true;
      }
    }, { capture: true, passive: true });
  }

  // --- following a link ----------------------------------------------------------------
  // `href` as written in the note. True when it was a reference link (handled here: this
  // document in place, another in a new preview tab); false for anything else (the caller
  // keeps today's behaviour). Never throws for a link: a failure is said, and the safe
  // preview link (anchors.js safeHref) is what a click opens if this file is missing.
  function follow(href) {
    const link = A.parseReference(href);
    if (link.kind !== "reference") return false;
    if (link.id !== R.docId && !merged.has(link.id)) {
      window.open(A.safeHref(link), "_blank", "noopener");
      return true;
    }
    navigate(link, { back: true });
    return true;
  }

  function navigate(link, { back }) {
    cancel(current);
    clearMark();
    clearChoices();
    if (!app()?.pdfDocument || !viewer()?.pagesCount) {
      say("阅读器还没有准备好，请稍后再点", "The reader isn't ready yet: click again in a moment");
      return;
    }
    const nav = {
      n: ++number, link, pdf: app().pdfDocument, abort: new AbortController(), moves: new Set(),
      entry: back ? snapshot() : null,  // (taken now, before anything is awaited)
      moved: false, yours: false, searching: false, stopped: false,
    };
    current = nav;
    setState("mlRefResult", "finding");
    setState("mlRefSource", null);
    if (link.page <= viewer().pagesCount && viewer().currentPageNumber !== link.page) {
      move(nav, () => viewer().scrollPageIntoView({ pageNumber: link.page }));
    }
    render();
    resolve(nav).catch((error) => {
      if (!alive(nav)) return;
      finish(nav, "error");
      say("无法打开这个引用", `The reference couldn't be opened: ${error.message}`);
    });
  }

  function finish(nav, result) {
    if (current === nav) current = null;
    setState("mlRefResult", result);
    render();
  }

  async function record(nav) {
    const response = await fetch("/api/references/get", {
      method: "POST",
      signal: nav.abort.signal,
      headers: { "Content-Type": "application/json", "X-Library-Token": R.token },
      body: JSON.stringify({ id: nav.link.id, rid: nav.link.rid }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || response.statusText);
    return data;
  }

  const hex = (buffer) => [...new Uint8Array(buffer)].map((b) => b.toString(16).padStart(2, "0")).join("");
  const sha256 = async (s) => hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)));

  // Where the quoted bytes came from (plan §3.2): `loaded` only; the server's fingerprint
  // never proves it, and an empty `loaded` means unknown
  async function sourceOf(record) {
    if (!record.loaded) return "unknown";
    let digest = null;
    try {
      digest = await R.loadedDigest();
    } catch {
      digest = null;
    }
    return digest && digest === record.loaded ? "unchanged" : "changed";
  }

  async function resolve(nav) {
    const { link } = nav;
    const answer = await record(nav);
    if (!alive(nav)) return;
    const found = answer.record;
    if (!found) return byQuery(nav, answer.status);
    const page = found.page + 1;
    if (found.kind === "page") {
      if (page > viewer().pagesCount) return pageOnly(nav, link.page, "gone");
      await toPage(nav, page);
      if (!alive(nav)) return;
      showMark(nav, page, [[0, 0, 1, 1]], "ml-ref-page");
      return finish(nav, "page-reference");
    }
    const source = await sourceOf(found);
    if (!alive(nav)) return;
    setState("mlRefSource", source);
    if (page <= viewer().pagesCount) {
      await toPage(nav, page);
      const drawn = await drawnLayer(nav, page);
      if (!alive(nav)) return;
      if (drawn) {
        const same = found.normalize === A.NORMALIZE && found.page_hash === await sha256(drawn.norm.text)
          && drawn.norm.text.slice(found.start, found.end) === found.exact;
        if (!alive(nav)) return;
        if (same && source === "unchanged") return show(nav, drawn, found.start, found.end, "exact");
        if (same && unchangedPage(found, drawn.view)) {
          say("PDF 文件已改变；这一页的文字没有变", "The PDF file changed; this page's text is unchanged");
          return show(nav, drawn, found.start, found.end, "verified-page");
        }
      }
    }
    return discover(nav, found);
  }

  // The page itself shown to be as it was quoted (changed or unknown source): the whole page
  // text (page_hash, checked by the caller), the page count, its size and rotation
  function unchangedPage(found, view) {
    const box = view.pdfPage.view;
    const size = [box[2] - box[0], box[3] - box[1]];
    const rotation = ((view.pdfPage.rotate % 360) + 360) % 360;
    return viewer().pagesCount === found.pages && rotation === found.rotation
      && Math.abs(size[0] - found.page_size[0]) < 0.01 && Math.abs(size[1] - found.page_size[1]) < 0.01;
  }

  async function toPage(nav, page) {
    if (viewer().currentPageNumber === page && pageVisible(page)) return;
    move(nav, () => viewer().scrollPageIntoView({ pageNumber: page }));
  }

  // (PDF.js's internal page list: if an upgrade removed it, the page is simply moved to)
  function pageVisible(page) {
    const v = viewer();
    const list = typeof v._getVisiblePages === "function" ? v._getVisiblePages() : null;
    return Array.isArray(list?.views) && list.views.some((p) => p.id === page);
  }

  // The page's drawn text layer (what M6 anchored): waits for it once (a limited time);
  // null when it can't be drawn or has no text
  async function drawnLayer(nav, page) {
    const view = viewer().getPageView(page - 1);
    const ready = () => {
      const layer = view?.div?.querySelector(".textLayer");
      return layer?.querySelector(".endOfContent") ? layer : null;
    };
    let layer = ready();
    if (!layer) {
      layer = await new Promise((done) => {
        const off = () => {
          clearTimeout(timer);
          bus().off("textlayerrendered", on);
        };
        const on = (event) => {
          if (event.pageNumber !== page) return;
          off();
          done(event.error ? null : ready());
        };
        const timer = setTimeout(() => {
          off();
          done(null);
        }, 10000);
        bus().on("textlayerrendered", on);
        nav.abort.signal.addEventListener("abort", () => {
          off();
          done(null);
        });
      });
    }
    if (!layer || !alive(nav)) return null;
    const source = R.layerText(layer);
    return { page, view, source, norm: A.normalize(source.text) };
  }

  // --- changed or unknown source: the whole document searched (plan §3.4) -----------------
  async function discover(nav, found) {
    const needle = found.normalize === A.NORMALIZE ? found.exact : A.normalize(found.text).text.trim();
    const context = found.normalize === A.NORMALIZE;
    const total = viewer().pagesCount;
    const first = Math.min(Math.max(found.page, 0), total - 1);
    const order = [first, ...Array.from({ length: total }, (_, i) => i).filter((i) => i !== first)];
    const started = performance.now();
    const hits = [];
    let scanned = 0;
    nav.searching = true;
    render();
    for (const index of order) {
      if (!alive(nav)) return;
      if (nav.stopped || scanned >= SEARCH_PAGES || performance.now() - started > SEARCH_MS) break;
      if (scanned % 10 === 0) say(`正在查找原文…第 ${scanned} 页，共 ${total} 页`, `Searching… p. ${scanned} of ${total}`);
      const pdfPage = await nav.pdf.getPage(index + 1);
      const content = await pdfPage.getTextContent({ includeMarkedContent: true, disableNormalization: true });
      if (!alive(nav)) return;
      if (nav.stopped) break;  // (cancelled while this page was read: its text isn't used)
      const text = A.normalize(A.textFromContent(content)).text;
      for (const c of A.candidates(text, needle, found.prefix, found.suffix)) {
        hits.push({ ...c, full: context && c.full, page: index + 1, text });
      }
      scanned += 1;
    }
    nav.searching = false;
    const complete = scanned === total;
    const full = hits.filter((h) => h.full);
    if (complete && full.length === 1) {
      const hit = full[0];
      return land(nav, hit, needle, hit.page === found.page + 1
        ? ["这一页的文字已改变", "The page's text changed"]
        : [`在第 ${hit.page} 页找到；PDF 已改变`, `Found on page ${hit.page}; the PDF changed`], "found");
    }
    if (hits.length) return offer(nav, [...full, ...hits.filter((h) => !h.full)], needle, complete);
    const why = complete ? "not-found" : "incomplete";
    return pageOnly(nav, Math.min(found.page + 1, total), why);
  }

  // A candidate shown: the reader moves to its page and the passage is checked again in the
  // drawn layer (offsets from getTextContent are the drawn text's: test_reference_nav.py)
  async function land(nav, hit, needle, [zh, en], result) {
    await toPage(nav, hit.page);
    const drawn = await drawnLayer(nav, hit.page);
    if (!alive(nav)) return;
    if (!drawn || drawn.norm.text.slice(hit.start, hit.end) !== needle) {
      return pageOnly(nav, hit.page, "not-found");
    }
    say(zh, en);
    return show(nav, drawn, hit.start, hit.end, result);
  }

  // The link's q when there is no record (plan §3.5): only at a passage's start, on the
  // link's page; never searched for across the document (no context to prove it unique)
  async function byQuery(nav, status) {
    const { link } = nav;
    const page = Math.min(link.page, viewer().pagesCount);
    const reason = { missing: "no-file", damaged: "damaged", "no-record": "no-record",
      "newer-format": "newer" }[status] || "no-record";
    if (!link.q) return pageOnly(nav, page, reason);
    await toPage(nav, page);
    const drawn = await drawnLayer(nav, page);
    if (!alive(nav)) return;
    if (!drawn) return pageOnly(nav, page, "no-text");
    const needle = A.normalize(link.q).text.trim();
    const hits = A.queryMatches(drawn.norm.text, link.q)
      .map((h) => ({ ...h, page, text: drawn.norm.text }));
    if (hits.length === 1) {
      say("没有保存的引用：按链接中的文字找到", "No stored reference: found by the link's text");
      return show(nav, drawn, hits[0].start, hits[0].end, "query");
    }
    if (hits.length > 1) return offer(nav, hits, needle, true);
    return pageOnly(nav, page, reason);
  }

  const REASONS = {
    gone: ["这一页已不存在", "That page no longer exists"],
    "not-found": ["在 PDF 中找不到这段文字", "The passage isn't in the PDF"],
    incomplete: ["搜索没有完成：只转到这一页", "The search didn't finish: only the page is shown"],
    "no-text": ["这一页没有可用的文字层", "This page has no usable text layer"],
    "no-file": ["这份文档没有引用记录", "This document has no stored references"],
    "no-record": ["引用记录不在了", "The reference record is gone"],
    damaged: ["引用文件已损坏", "The references file is damaged"],
    newer: ["引用文件来自更新的 myLibrary", "The references file is from a newer myLibrary"],
  };

  async function pageOnly(nav, page, reason) {
    await toPage(nav, page);
    if (!alive(nav)) return;
    const [zh, en] = REASONS[reason] || REASONS["not-found"];
    say(`${zh}：只转到第 ${page} 页`, `${en}; showing page ${page} only`);
    showMark(nav, page, [[0, 0, 1, 1]], "ml-ref-page");
    setState("mlRefReason", reason);
    return finish(nav, "page");
  }

  // --- explicit choice (owner decision 3): never picked for you ------------------------------
  function offer(nav, hits, needle, complete) {
    clearChoices();
    const list = controls.choices;
    const head = R.el("div", "ml-nav-head");
    head.textContent = complete
      ? bi(`找到 ${hits.length} 处，请选择`, `Found in ${hits.length} places: choose one`)
      : bi(`搜索未完成，已找到 ${hits.length} 处`, `Search incomplete: ${hits.length} found so far`);
    list.append(head);
    // "2 of 4 on p. 41": its position among the matches on that page, in the page's order
    const onPage = new Map();
    for (const hit of hits) onPage.set(hit.page, [...(onPage.get(hit.page) || []), hit.start]);
    for (const starts of onPage.values()) starts.sort((a, b) => a - b);
    for (const hit of hits) {
      const starts = onPage.get(hit.page);
      const k = starts.indexOf(hit.start) + 1;
      const button = R.el("button", "ml-small ml-nav-choice");
      const before = hit.text.slice(Math.max(0, hit.start - 30), hit.start);
      const after = hit.text.slice(hit.end, hit.end + 30);
      const where = starts.length > 1 ? `p. ${hit.page} (${k}/${starts.length})` : `p. ${hit.page}`;
      button.textContent = `${where}: …${before}${hit.text.slice(hit.start, hit.end)}${after}…`;
      button.onclick = () => {
        if (current !== nav) return;
        clearChoices();
        land(nav, hit, needle, ["已选择", "Chosen"], "chosen");
      };
      list.append(button);
    }
    const pageButton = R.biEl("button", "ml-small ml-nav-choice", `只转到第 ${nav.link.page} 页`,
      `Only go to page ${nav.link.page}`);
    pageButton.onclick = () => {
      if (current !== nav) return;
      clearChoices();
      pageOnly(nav, Math.min(nav.link.page, viewer().pagesCount), complete ? "not-found" : "incomplete");
    };
    list.append(pageButton);
    setState("mlRefResult", complete ? "choice" : "choice-incomplete");
    say(complete ? "这段文字有多处，请选择" : "搜索未完成，请选择或只转到这一页",
      complete ? "The passage occurs in several places: choose one"
        : "The search didn't finish: choose one, or only go to the page");
    render();
  }

  function clearChoices() {
    controls.choices.replaceChildren();
  }

  // --- the passage shown and outlined ------------------------------------------------------
  function rangeFor(drawn, start, end) {
    const { source, norm } = drawn;
    const from = norm.map[start];
    const last = norm.map[end - 1];
    const to = last + (source.text.codePointAt(last) > 0xffff ? 2 : 1);
    const at = (offset, isEnd) => {
      for (const [node, s] of source.nodes) {
        const length = node.data.length;
        if (isEnd ? offset > s && offset <= s + length : offset >= s && offset < s + length) {
          return [node, offset - s];
        }
      }
      return null;
    };
    const a = at(from, false);
    const b = at(to, true);
    if (!a || !b) return null;
    const range = document.createRange();
    range.setStart(...a);
    range.setEnd(...b);
    return range;
  }

  function wrapperOf(view) {
    return view.div.querySelector(".canvasWrapper") || view.div;
  }

  function show(nav, drawn, start, end, result) {
    const range = rangeFor(drawn, start, end);
    if (!range) return pageOnly(nav, drawn.page, "not-found");
    const box = wrapperOf(drawn.view).getBoundingClientRect();  // (read now, before any wait)
    const rects = [...range.getClientRects()].filter((r) => r.width >= 0.5 && r.height >= 0.5)
      .slice(0, 500).map((r) => [(r.left - box.left) / box.width, (r.top - box.top) / box.height,
        (r.right - box.left) / box.width, (r.bottom - box.top) / box.height]);
    showMark(nav, drawn.page, rects, "ml-ref-mark");
    if (!nav.yours && rects.length) {  // (your own move since the click wins: no fine scroll)
      const c = viewer().container;
      const area = c.getBoundingClientRect();
      const top = box.top + rects[0][1] * box.height;
      const wanted = area.top + c.clientHeight / 3;
      if (Math.abs(top - wanted) > c.clientHeight / 6) move(nav, () => { c.scrollTop += top - wanted; });
    }
    return finish(nav, result);
  }

  function showMark(nav, page, rects, kind) {
    clearMark();
    mark = { page, rects, kind, timer: setTimeout(clearMark, SHOWN_MS) };
    drawMark();
  }

  function drawMark() {
    document.querySelectorAll(".ml-ref-layer").forEach((layer) => layer.remove());
    if (!mark) return;
    const view = viewer().getPageView(mark.page - 1);
    if (!view?.div) return;
    const wrap = wrapperOf(view);
    const layer = R.el("div", "ml-ref-layer");
    Object.assign(layer.style, {
      left: `${wrap.offsetLeft}px`, top: `${wrap.offsetTop}px`,
      width: `${wrap.offsetWidth}px`, height: `${wrap.offsetHeight}px`,
    });
    for (const [x0, y0, x1, y1] of mark.rects) {
      const box = R.el("div", mark.kind);
      Object.assign(box.style, {
        left: `${x0 * 100}%`, top: `${y0 * 100}%`, width: `${(x1 - x0) * 100}%`, height: `${(y1 - y0) * 100}%`,
      });
      layer.append(box);
    }
    view.div.append(layer);
    setState("mlRefMark", String(mark.page));
  }

  function clearMark() {
    if (mark) clearTimeout(mark.timer);
    mark = null;
    document.querySelectorAll(".ml-ref-layer").forEach((layer) => layer.remove());
    setState("mlRefMark", null);
  }

  // --- Back, Continue reading here ---------------------------------------------------------
  function back() {
    cancel(current);  // (a pending navigation that hadn't moved left no entry)
    clearMark();
    clearChoices();
    if (stack.length && app().pdfDocument && viewer()?.pagesCount) {  // (else kept for later)
      const entry = stack.pop();
      const id = T.programmatic();
      restore(entry);
      settle(id);
      if (!stack.length) T.restored(entry.page);
    }
    setState("mlRefResult", "back");
    render();
  }

  function endVisit() {
    cancel(current);
    clearMark();
    clearChoices();
    stack.length = 0;
    render();
  }

  // --- at load: merged ids, the position revision, a reference opened from outside --------
  async function start() {
    await app().initializedPromise;
    try {
      const ids = await R.post("/api/document/ids", { id: R.docId });
      (ids.merged || []).forEach((id) => merged.add(id));
      T.setBase(ids.position_rev);
    } catch {
      /* not known: an old id opens a preview tab; the first position decision learns the rev */
    }
    bus().on("pagerendered", ({ pageNumber }) => { if (mark?.page === pageNumber) drawMark(); });
    bus().on("rotationchanging", clearMark);
    let shown = app().pdfDocument;
    bus().on("documentloaded", () => {  // another PDF in this tab: nothing of the other applies
      const loaded = app().pdfDocument;
      const first = !shown;
      if (loaded === shown) return;  // (PDF.js says so once after pagesinit, too)
      shown = loaded;
      if (first) return;  // (the tab's first PDF: nothing to end)
      const visited = stack.length > 0;
      endVisit();
      if (visited) T.restored(app().page);
    });
    const params = new URLSearchParams(location.search);
    const rid = params.get("ref");
    if (!rid) return;
    const hashPage = Number((location.hash.match(/page=(\d+)/) || [])[1]) || 1;
    const q = params.get("q") || "";
    const refdoc = params.get("refdoc") || R.docId;
    const link = A.parseReference(
      `/read/${refdoc}?page=${hashPage}&ref=${rid}${q ? `&q=${encodeURIComponent(q)}` : ""}`);
    if (link.kind !== "reference") return;
    const go = () => navigate(link, { back: false });  // (opened from outside: no Back entry)
    if (viewer()?.pagesCount) go();
    else bus().on("pagesinit", go, { once: true });
  }
  start();

  window.myLibraryNavigate = Object.freeze({ follow, back, endVisit, depth: () => stack.length });
})();
