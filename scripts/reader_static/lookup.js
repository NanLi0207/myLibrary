// Word lookup for the PDF.js reading view (served by library_server.py, see reader.py).
// Double-click a word: popup with your subject glossaries + the dictionary meaning.
// Drag over a phrase: it's looked up the same way; a longer passage gets a 翻译 (Translate)
// button. Every Chinese label comes with its English translation (bi() below).
(() => {
  "use strict";
  const token = window.MYLIBRARY_TOKEN;
  // The document being read: its id (catalog.py), given by the server in the address
  const docId = new URLSearchParams(location.search).get("id") || "";
  // Opened from a search result to look something up (&preview=1): not reading, so nothing is
  // recorded (no "Last read", no reading time) until "Start reading" is clicked
  let preview = new URLSearchParams(location.search).get("preview") === "1";
  let popup = null;
  let bubble = null;

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  // Chinese label + its English translation (smaller, grey), for any element's content
  function bi(zh, en) {
    const span = el("span", "ml-bi");
    span.append(zh, " ", el("span", "ml-en", en));
    return span;
  }

  function biEl(tag, cls, zh, en) {
    const e = el(tag, cls);
    e.append(bi(zh, en));
    return e;
  }

  // The notes panel (notes.js) is the user's own text, not the document: no lookup there, its
  // keys and clicks aren't reading time, and the marks' Undo/Esc don't act from it
  function inNotes(node) {
    const element = node?.nodeType === Node.TEXT_NODE ? node.parentElement : node;
    return !!element?.closest?.(".ml-notes");
  }

  // The space the notes panel takes beside the PDF (0 when it's closed or over the PDF)
  function notesSpace() {
    return parseFloat(getComputedStyle(document.documentElement)
      .getPropertyValue("--ml-notes-space")) || 0;
  }

  let sizeWatch = null;

  function closeAll() {
    sizeWatch?.disconnect();
    sizeWatch = null;
    popup?.remove();
    bubble?.remove();
    popup = bubble = null;
  }

  // Text around the selection (a few text-layer spans each side), so the server can spot
  // longer glossary terms: "pupil" inside "entrance pupil"
  function contextOf(range) {
    const node = range.startContainer;
    const span = (node.nodeType === 1 ? node : node.parentElement)?.closest(".textLayer span");
    const layer = span?.closest(".textLayer");
    if (!layer) return range.toString();
    const spans = [...layer.querySelectorAll("span")].filter((s) => !s.querySelector("span"));
    const i = spans.indexOf(span);
    return spans.slice(Math.max(0, i - 3), i + 4).map((s) => s.textContent).join(" ");
  }

  function pageOf(range) {
    const node = range.startContainer;
    const page = (node.nodeType === 1 ? node : node.parentElement)?.closest(".page");
    return page ? Number(page.dataset.pageNumber) : window.PDFViewerApplication?.page ?? null;
  }

  function place(box, rect) {
    // Only added once: moving it again would reset its scroll and take the focus from its input
    if (box.parentNode !== document.body) document.body.append(box);
    const w = box.offsetWidth;
    const h = box.offsetHeight;
    const right = innerWidth - notesSpace();  // in the PDF's part of the window
    let left = Math.max(8, Math.min(rect.left, right - w - 8));  // never off the left edge
    let top = rect.bottom + 6;
    if (top + h > innerHeight - 8) top = Math.max(8, rect.top - h - 6);
    box.style.left = `${left}px`;
    box.style.top = `${top}px`;
  }

  async function post(path, body) {
    const response = await fetch(path, {
      method: "POST",
      keepalive: true,  // a click's write still arrives if the tab is closed at once
      headers: { "Content-Type": "application/json", "X-Library-Token": token },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || response.statusText);
    return data;
  }

  function speak(text) {
    if (!window.speechSynthesis) return;
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "en-US";
    u.rate = 0.9;
    speechSynthesis.speak(u);
  }

  function translateLink(text, zh = "整句翻译", en = "Translate (Bing)") {
    const a = link("", "https://www.bing.com/translator?from=en&to=zh-Hans&text=" + encodeURIComponent(text));
    a.replaceChildren(bi(zh, en));
    return a;
  }

  function link(label, url) {
    const a = el("a", "ml-link", label);
    a.href = url;
    a.target = "_blank";
    a.rel = "noopener";
    return a;
  }

  // "books/fischer-2008-optical-system-design.pdf" -> "Fischer 2008" (its file's name)
  function bookLabel(file) {
    const [author, year] = (file.split("/").pop() || "").split("-");
    return author ? `${author[0].toUpperCase()}${author.slice(1)} ${year || ""}`.trim() : file;
  }

  // A search result: the document (by its id) at that page, with the searched text highlighted,
  // in a preview tab (a look-up, not reading: it leaves "Last read" and the reading log alone;
  // also for this book, so the place you're reading at here stays where it is)
  function openPage(id, page, term) {
    closeAll();
    const find = term ? `&find=${encodeURIComponent(term)}` : "";
    window.open(`/read/${encodeURIComponent(id)}?page=${page}${find}&preview=1`, "_blank");
  }

  // Highlight a searched term on a page with PDF.js's own find (yellow, the current match
  // stronger; the find bar shows "n of N" with ▲▼ for the other matches; closing it or Esc
  // clears them). Nothing is written into the PDF: these are not annotations. The term may not
  // be found exactly as the index matched it (it also matches other word forms, e.g.
  // "vignetted" for "vignetting"): then the page stays where the result is, and a note says so
  // rather than jumping to some other page.
  let findNotice = null;
  function notice(zh, en) {
    if (!findNotice) {
      findNotice = el("div", "ml-saved ml-find");
      document.body.append(findNotice);
    }
    findNotice.replaceChildren(bi(zh, en));
    findNotice.hidden = false;
    clearTimeout(findNotice.timer);
    findNotice.timer = setTimeout(() => { findNotice.hidden = true; }, 6000);
  }

  // The arrival at a search result (/read/<id>?page=N&find=term) positions the reader once,
  // unless the user moves first: their own page turn, scroll, click or key always wins over
  // the arrival's positioning (B19). It watches for that from the moment the reader loads.
  // Its outcome is in document.body.dataset.mlArrival (this tab only, never stored):
  // "pending", then "centred" (the match brought to the middle), "left" (the user moved
  // first; nothing more is positioned), "elsewhere" (the term isn't on the result's page) or
  // "not-found".
  function startArrival() {
    const listening = new AbortController();
    const arrival = {
      ended: false,
      found: false,  // the arrival's find has reported its result
      keepPlace: false,  // the user moved before that: keep their place when it comes
      timer: null,
      end(outcome) {  // stop everything this arrival still had planned
        if (arrival.ended) return;
        arrival.ended = true;
        clearTimeout(arrival.timer);
        listening.abort();
        document.body.dataset.mlArrival = outcome;
      },
    };
    document.body.dataset.mlArrival = "pending";
    const userMoved = (event) => {
      if (!event.isTrusted) return;  // the user's own input only, never a script's events
      if (event.type === "keydown" && ["Shift", "Control", "Alt", "Meta"].includes(event.key)) return;
      const finder = window.PDFViewerApplication?.findController;
      // PDF.js scrolls once to the match its find selected, when that page's text is drawn
      // (its _scrollMatches flag: a PDF.js 4.10 internal, to recheck when PDF.js is upgraded;
      // tests: test_preview.py). Already selected: that pending scroll is withdrawn now
      if (arrival.found && finder) finder._scrollMatches = false;
      else arrival.keepPlace = true;
      arrival.end("left");
    };
    for (const type of ["pointerdown", "wheel", "keydown", "touchstart"]) {
      addEventListener(type, userMoved, { capture: true, passive: true, signal: listening.signal });
    }
    return arrival;
  }

  function showFound(term, page, arrival) {
    const app = window.PDFViewerApplication;
    if (!arrival.ended) app.page = page;  // PDF.js's find starts from the current page
    const bar = app.findBar;
    if (bar) {
      bar.open();
      bar.findField.value = term;
      bar.highlightAll.checked = true;
      bar.caseSensitive.checked = false;
      bar.entireWord.checked = false;
    }
    const viewer = app.pdfViewer?.container;
    let ours = false;  // the find being sent is the arrival's own
    const onState = ({ state }) => {
      if (state === 3) return;  // PENDING: still reading pages
      app.eventBus.off("updatefindcontrolstate", onState);
      app.eventBus.off("find", userFind);
      arrival.found = true;
      if (arrival.ended) {
        // The user moved before the result came. Right after this event PDF.js turns to the
        // match's page and asks to scroll to it; once it has, the user's place is put back
        // and the scroll withdrawn (before the screen is drawn again)
        if (arrival.keepPlace && viewer) {
          const { scrollTop, scrollLeft } = viewer;
          queueMicrotask(() => {
            if (app.findController) app.findController._scrollMatches = false;
            viewer.scrollTop = scrollTop;
            viewer.scrollLeft = scrollLeft;
          });
        }
        return;  // the highlights stay; nothing else moves
      }
      const at = app.findController?.selected?.pageIdx;
      if (state === 1 || at == null) {  // NOT_FOUND (e.g. a scan without a text layer)
        app.page = page;
        notice(`在此文档中没有找到 “${term}”（本页由搜索得出）`,
          `“${term}” wasn't found as typed; this is the page the search found`);
        arrival.end("not-found");
      } else if (at + 1 !== page) {  // only elsewhere: don't jump away from the result's page
        // PDF.js would scroll to its match once that page is drawn. It asks for that right
        // after this event, so the request is withdrawn just after (the arrows still work)
        arrival.timer = setTimeout(() => {
          if (arrival.ended) return;
          if (app.findController) app.findController._scrollMatches = false;
          app.page = page;
          arrival.end("elsewhere");
        }, 0);
        notice(`本页没有完全一致的 “${term}”，可用查找栏的箭头看其他位置`,
          `No exact “${term}” on this page; the find bar's arrows go to other matches`);
      } else {
        // PDF.js puts the match near the top; bring it to the middle once it's drawn, unless
        // the reader is on another page by then
        arrival.timer = setTimeout(() => {
          if (arrival.ended) return;
          if (app.page !== page) return arrival.end("left");
          document.querySelector(".textLayer .highlight.selected")
            ?.scrollIntoView({ block: "center" });
          arrival.end("centred");
        }, 300);
      }
    };
    // A find of the user's own (typing, Enter, ▲▼) before the result came replaces the
    // arrival's: its result is the user's, and the arrival leaves it alone
    const userFind = () => {
      if (ours) return;
      app.eventBus.off("updatefindcontrolstate", onState);
      app.eventBus.off("find", userFind);
      arrival.keepPlace = false;
      arrival.end("left");
    };
    app.eventBus.on("updatefindcontrolstate", onState);
    app.eventBus.on("find", userFind);
    ours = true;
    try {
      app.eventBus.dispatch("find", {
        source: bar || app, type: "", query: term, caseSensitive: false, entireWord: false,
        highlightAll: true, findPrevious: false, matchDiacritics: true,
      });
    } finally {
      ours = false;
    }
  }

  // Opened from a search result: the arrival starts watching at once (a move before the find
  // has even started counts too); the term is highlighted once the pages are ready
  async function findFromAddress() {
    const app = window.PDFViewerApplication;
    const term = new URLSearchParams(location.search).get("find");
    if (!app || !term) return;
    const arrival = startArrival();
    await app.initializedPromise;
    const page = Number((location.hash.match(/page=(\d+)/) || [])[1]) || 1;
    const go = () => setTimeout(() => showFound(term, page, arrival), 100);
    if (app.pdfViewer?.pagesCount) go();
    else app.eventBus.on("pagesinit", go, { once: true });
  }
  findFromAddress();

  function snippetNode(snippet) {
    const p = el("div", "ml-snippet");
    snippet.split(/(\x02[^\x03]*\x03)/).forEach((part) => {
      if (part.startsWith("\x02")) p.append(el("mark", null, part.slice(1, -1)));
      else if (part) p.append(part);
    });
    return p;
  }

  // 在我的书中 (In my books) + encyclopedia links for one term
  function learnMore(term, zh) {
    const wrap = el("div", "ml-more");
    const row = el("div", "ml-more-links");
    const books = biEl("button", "ml-small", "📚 在我的书中", "In my books");
    const results = el("div", "ml-results");
    books.onclick = async () => {
      books.disabled = true;
      results.replaceChildren(biEl("div", "ml-muted", "搜索中…", "Searching…"));
      let found;
      try {
        found = await post("/api/search", { text: term, id: docId });
      } catch (e) {
        results.replaceChildren(biEl("div", "ml-error", "搜索失败", "Search failed: " + e.message));
        books.disabled = false;
        return;
      }
      results.replaceChildren();
      if (!found.results.length) {
        results.append(found.indexing
          ? biEl("div", "ml-muted", "书的全文索引还在建立，请稍后再试",
            "The book index is still being built; try again in a moment")
          : biEl("div", "ml-muted", `书中没有找到 “${found.term}”`, "Not found in your books"));
        books.disabled = false;
        return;
      }
      results.append(biEl("div", "ml-muted",
        `“${found.term}” 出现在 ${found.books} 本书的 ${found.pages} 页中；最相关的页：`,
        `on ${found.pages} page${found.pages === 1 ? "" : "s"} in ${found.books} book${found.books === 1 ? "" : "s"}; most relevant:`));
      for (const r of found.results) {
        const item = el("button", "ml-result");
        item.title = `${r.title}，PDF 第 ${r.page} 页 / PDF page ${r.page}`;
        const where = el("div", "ml-where");
        where.append(el("b", null, bookLabel(r.file)), ` · p. ${r.page}`);
        if (r.id === docId) where.append(biEl("span", "ml-here", "本书", "this book"));
        item.append(where, snippetNode(r.snippet));
        item.onclick = () => openPage(r.id, r.page, found.term);
        results.append(item);
      }
    };
    // 主题笔记 (Topic note): your notes on this term across all your books
    const topic = biEl("button", "ml-small", "📝 主题笔记", "Topic note");
    topic.title = "打开或新建这个主题的笔记 / Open or start your notes on this topic (notes/topics/)";
    topic.onclick = async () => {
      topic.disabled = true;
      try {
        const r = await post("/api/topic", { text: term });
        topic.replaceChildren(r.opened ? bi("已打开 ✓", "Opened") : bi("已创建 ✓", "Created"));
        topic.title = r.file;
      } catch (e) {
        topic.replaceChildren(bi("失败", "Failed"));
        topic.title = e.message;
      }
    };
    row.append(books, topic);
    row.append(link("Wikipedia", "https://en.wikipedia.org/w/index.php?search=" + encodeURIComponent(term)));
    if (zh) {
      const name = zh.split(/[（(；;，,]/)[0].trim();
      const zhWiki = link("", "https://zh.wikipedia.org/w/index.php?search=" + encodeURIComponent(name));
      zhWiki.append(bi("维基百科", "Chinese Wikipedia"));
      const baike = link("", "https://baike.baidu.com/search/word?word=" + encodeURIComponent(name));
      baike.append(bi("百度百科", "Baidu Baike"));
      row.append(zhWiki, baike);
    }
    wrap.append(row, results);
    return wrap;
  }

  // 加入术语表 (Add to glossary): your own Chinese term (+ definition) for a glossaries/*.csv
  function addTermForm(term, glossaries, done) {
    const wrap = el("div", "ml-addterm");
    const open = biEl("button", "ml-small", "＋ 加入术语表", "Add to glossary");
    open.title = `把 “${term}” 和你的中文译名加入术语表 / Add “${term}” and its Chinese term to a glossary (glossaries folder)`;
    open.onclick = () => {
      const form = el("form", "ml-form");
      form.append(biEl("div", "ml-muted", `“${term}” 的中文译名（参考书中的解释后填写）：`,
        "its Chinese term (fill in after reading how your books explain it):"));
      // More than one glossary: choose which one (the default is listed first)
      const which = el("select");
      for (const g of glossaries) {
        const option = el("option", null, g.label === g.name ? g.name : `${g.label}（${g.name}）`);
        option.value = g.name;
        which.append(option);
      }
      if (glossaries.length > 1) form.append(which);
      const zh = el("input");
      zh.placeholder = "中文 Chinese term, e.g. 杂光";
      zh.required = true;
      zh.maxLength = 60;
      const def = el("textarea");
      def.placeholder = "定义（可选，用自己的话）Definition (optional, in your own words)";
      def.rows = 2;
      def.maxLength = 400;
      const save = biEl("button", "ml-button", "保存", "Save");
      save.type = "submit";
      const status = el("span", "ml-muted");
      const row = el("div", "ml-actions");
      row.append(save, status);
      form.append(zh, def, row);
      form.onsubmit = async (event) => {
        event.preventDefault();
        save.disabled = true;
        try {
          await post("/api/glossary", {
            term, zh: zh.value, definition: def.value, glossary: which.value || null,
          });
          done();
        } catch (e) {
          status.textContent = e.message;
          save.disabled = false;
        }
      };
      wrap.replaceChildren(form);
      zh.focus();
    };
    wrap.append(open);
    return wrap;
  }

  async function lookup(text, range) {
    closeAll();
    const rect = range.getBoundingClientRect();
    const context = contextOf(range);
    const page = pageOf(range);
    popup = el("div", "ml-popup");
    popup.append(biEl("div", "ml-muted", "查询中…", "Looking up…"));
    place(popup, rect);
    // Placed again whenever it grows or shrinks (search results, the add-term form, an error),
    // so it stays inside the window (B18); taller than 70vh, it scrolls
    const box = popup;
    sizeWatch = new ResizeObserver(() => { if (popup === box) place(box, rect); });
    sizeWatch.observe(box);
    let data;
    try {
      data = await post("/api/lookup", { text, context, id: docId });
    } catch (e) {
      if (popup === box) box.replaceChildren(biEl("div", "ml-error", "查询失败", "Lookup failed: " + e.message));
      return;
    }
    if (popup !== box) return; // closed (or replaced) while waiting
    box.replaceChildren();

    const head = el("div", "ml-head");
    const entry = data.entries[0];
    // Editable: if the selection caught the wrong letters (common in scanned books), fix the
    // word here and press Enter to look it up again
    const word = el("input", "ml-word");
    word.value = entry?.word || data.query;
    word.title = "可以修改，按 Enter 重新查询 / Edit and press Enter to look up again";
    word.spellcheck = false;
    word.size = Math.max(4, Math.min(28, word.value.length + 1));
    word.onkeydown = (event) => {
      if (event.key === "Enter" && word.value.trim()) lookup(word.value.trim(), range);
    };
    head.append(word);
    if (entry?.phonetic) head.append(el("span", "ml-phonetic", `/${entry.phonetic}/`));
    const say = el("button", "ml-icon", "🔊");
    say.title = "朗读 / Read aloud";
    say.onclick = () => speak(entry?.word || data.query);
    head.append(say);
    box.append(head);
    if (entry?.from) box.append(el("div", "ml-muted", `${entry.from} → ${entry.word}`));

    for (const g of data.glossary) {
      const row = el("div", "ml-gloss");
      row.append(el("span", "ml-tag", g.label), el("b", null, g.term), " ", el("span", "ml-zh", g.zh));
      if (g.definition) row.append(el("div", "ml-def", g.definition));
      if (g.note) row.append(el("div", "ml-note", g.note));
      row.append(learnMore(g.term, g.zh));
      box.append(row);
    }
    if (entry) box.append(el("div", "ml-trans", entry.translation));
    if (data.words.length) {
      // A phrase nobody knows as a whole: what each word means
      const list = el("div", "ml-words");
      list.append(entry || data.glossary.length
        ? biEl("div", "ml-muted", "其他词：", "Other words:")
        : biEl("div", "ml-muted", "整个短语没有查到，逐词意思：", "Phrase not found; word by word:"));
      for (const w of data.words) {
        const row = el("div", "ml-wordrow");
        row.append(el("b", null, w.word), " ");
        if (w.zh) row.append(el("span", "ml-tag", w.label), el("span", "ml-zh", w.zh), " ");
        if (w.translation) row.append(el("span", "ml-muted", w.translation));
        else if (!w.zh) row.append(biEl("span", "ml-muted", "（词典里没有）", "(not in the dictionary)"));
        list.append(row);
      }
      box.append(list);
    } else if (!entry && !data.glossary.length) {
      box.append(data.dictionary === false
        ? biEl("div", "ml-muted", "词典还没下载好（服务器正在准备，稍后再试）",
          "The dictionary isn't downloaded yet (the server is preparing it; try again shortly)")
        : biEl("div", "ml-muted", "词典里没有这个词", "Not in the dictionary"));
    }
    if (!data.in_glossary) {
      // The whole selection isn't a glossary term: search the books for it, and let me add it
      // "aberrations" -> its base word "aberration"; a phrase stays as selected
      const term = entry && !/\s/.test(data.query) ? entry.word : data.query;
      if (/\s/.test(term)) box.append(biEl("div", "ml-phrase", `整个短语 “${term}”：`, "whole phrase:"));
      box.append(learnMore(term, null));
      box.append(addTermForm(term, data.glossaries, () => lookup(text, range)));
    }

    const actions = el("div", "ml-actions");
    if (docId) {
      const save = biEl("button", "ml-button", "加入生词本", "Save word");
      save.onclick = async () => {
        save.disabled = true;
        try {
          const r = await post("/api/save-word", { id: docId, text, context, page });
          save.replaceChildren(r.saved ? bi("已加入 ✓", "Saved") : bi("已在生词本中", "Already saved"));
          save.title = r.file;
        } catch (e) {
          save.replaceChildren(bi("保存失败", "Save failed"));
          save.title = e.message;
        }
      };
      actions.append(save);
    }
    if (/\s/.test(text)) actions.append(translateLink(text));
    box.append(actions);
    place(box, rect); // now that the size is known (the size watch does it for later changes)
  }

  document.addEventListener("dblclick", (event) => {
    if (event.target.closest?.(".ml-popup, .ml-bubble") || inNotes(event.target)) return;
    const sel = getSelection();
    const text = sel.toString().trim();
    if (!text || !sel.rangeCount || text.length > 60) return;
    lookup(text, sel.getRangeAt(0));
  });

  // Extend a range that starts or ends in the middle of a word to the whole word
  function snapToWords(original) {
    const isWord = (c) => c !== undefined && /[\p{L}\p{N}'’-]/u.test(c);
    const range = original.cloneRange();
    const start = range.startContainer;
    if (start.nodeType === Node.TEXT_NODE) {
      const t = start.textContent;
      let i = range.startOffset;
      if (isWord(t[i])) while (i > 0 && isWord(t[i - 1])) i--;
      range.setStart(start, i);
    }
    const end = range.endContainer;
    if (end.nodeType === Node.TEXT_NODE) {
      const t = end.textContent;
      let j = range.endOffset;
      if (isWord(t[j - 1])) while (j < t.length && isWord(t[j])) j++;
      range.setEnd(end, j);
    }
    return range;
  }

  // Selected by dragging (or triple-click): up to 6 words are looked up right away, like a
  // double-click; a longer selection (a sentence) gets a 翻译 (Translate) button
  document.addEventListener("mouseup", (event) => {
    if (event.detail === 2 || event.target.closest?.(".ml-popup, .ml-bubble")) return;
    setTimeout(() => {
      const sel = getSelection();
      if (!sel.rangeCount || !sel.toString().trim()) return;
      if (!sel.anchorNode?.parentElement?.closest(".textLayer")) return;
      if (inNotes(sel.focusNode)) return;  // dragged on into the notes panel: not a lookup
      // A drag that starts or ends inside a word takes the whole word ("eiling gla" ->
      // "veiling glare"); show the snapped selection so you see what was looked up
      const range = snapToWords(sel.getRangeAt(0));
      sel.removeAllRanges();
      sel.addRange(range);
      const text = range.toString().replace(/\s+/g, " ").trim();
      if (!text) return;
      if (text.split(" ").length <= 6 && text.length <= 60) {
        lookup(text, range);
        return;
      }
      bubble?.remove();
      bubble = el("div", "ml-bubble");
      const translate = translateLink(text, "翻译", "Translate");
      translate.className = "ml-button";
      bubble.append(translate);
      const rects = range.getClientRects();
      place(bubble, rects[rects.length - 1] || range.getBoundingClientRect());
    }, 0);
  });

  // Remember where you are: the page is written to the notes README ("Last read: page N")
  // so the library's Continue button can bring you back. Only once you've moved away from the
  // page the book opened at: just opening a chapter to look doesn't overwrite your place.
  // `fromHere` (Start reading in a preview): this page counts at once.
  async function trackPosition(fromHere = false) {
    const app = window.PDFViewerApplication;
    if (!docId || !token || !app) return;
    await app.initializedPromise;
    const openedAt = Number((location.hash.match(/page=(\d+)/) || [])[1]) || null;
    let moved = fromHere;
    let saved = null;
    let timer = null;
    const save = (keepalive = false) => {
      clearTimeout(timer);
      const page = app.page;
      if (!moved || !page || page === saved) return;
      saved = page;
      fetch("/api/position", {
        method: "POST",
        keepalive,
        headers: { "Content-Type": "application/json", "X-Library-Token": token },
        body: JSON.stringify({ id: docId, page }),
      }).catch(() => { saved = null; });
    };
    app.eventBus.on("pagechanging", (event) => {
      if (!moved && event.pageNumber === openedAt) return;
      moved = true;
      clearTimeout(timer);
      timer = setTimeout(save, 2000);
    });
    addEventListener("pagehide", () => save(true));
    document.addEventListener("visibilitychange", () => { if (document.hidden) save(true); });
    if (fromHere) save();
  }
  if (!preview) trackPosition();

  // 📈 Reading log: the time you actively read (tab visible, and you moved, scrolled or turned
  // a page in the last two minutes) and the pages you looked at, sent every minute and when
  // you leave (reading_log.py adds them up per day).
  async function trackReading() {
    const app = window.PDFViewerApplication;
    if (!docId || !token || !app) return;
    await app.initializedPromise;
    const IDLE = 120000, TICK = 15000;
    let lastActive = Date.now();
    let seconds = 0;
    const pages = new Set();
    // Using the notes panel isn't reading (task 4 decision 3); turning a page always is
    const active = (event) => { if (!inNotes(event?.target)) lastActive = Date.now(); };
    for (const type of ["mousemove", "keydown", "wheel", "pointerdown", "touchstart"]) {
      addEventListener(type, active, { passive: true, capture: true });
    }
    addEventListener("scroll", active, { passive: true, capture: true });
    app.eventBus.on("pagechanging", (event) => { active(); pages.add(event.pageNumber); });
    const send = (keepalive = false) => {
      if (!seconds && !pages.size) return;
      const body = JSON.stringify({ id: docId, seconds: Math.round(seconds), pages: [...pages] });
      seconds = 0;
      pages.clear();
      fetch("/api/reading", {
        method: "POST",
        keepalive,
        headers: { "Content-Type": "application/json", "X-Library-Token": token },
        body,
      }).catch(() => {});
    };
    setInterval(() => {
      if (document.visibilityState !== "visible" || Date.now() - lastActive > IDLE) return;
      seconds += TICK / 1000;
      if (app.page) pages.add(app.page);
    }, TICK);
    setInterval(send, 60000);
    addEventListener("pagehide", () => send(true));
    document.addEventListener("visibilitychange", () => { if (document.hidden) send(true); });
  }
  if (!preview) trackReading();

  // Preview (a search result): a small bar says so; "Start reading" turns this tab into a
  // normal reading tab from the current page on (position saved, reading time counted)
  function previewBar() {
    if (!preview) return;
    const bar = el("div", "ml-preview");
    const start = biEl("button", "ml-small", "开始阅读", "Start reading");
    bar.append(biEl("span", null, "预览：不计入阅读进度", "Preview: not counted as reading"), start);
    start.onclick = () => {
      preview = false;
      bar.remove();
      const params = new URLSearchParams(location.search);
      params.delete("preview");  // a reload now reads normally too
      history.replaceState(null, "", `${location.pathname}?${params}${location.hash}`);
      trackPosition(true);
      trackReading();
    };
    document.body.append(bar);
  }
  previewBar();

  // ✎ Correcting marks. PDF.js already selects a highlight, deletes it (🗑 on its toolbar, or
  // Delete/Backspace), undoes (Ctrl+Z, and the "Undo" bar after a deletion), also for highlights
  // saved in the PDF earlier, but only while an editing tool is on, which isn't obvious. So:
  // a click on a highlight while reading selects it (turning the highlight tool on); Esc with
  // nothing selected leaves the tool; a hint says how, the first time a tool is turned on.
  // Deleting is PDF.js's own, and keepMarks saves it like any other change of marks.
  async function easyMarkEditing() {
    const app = window.PDFViewerApplication;
    if (!app) return;
    await app.initializedPromise;
    const NONE = 0, HIGHLIGHT = 9;  // pdfjs AnnotationEditorType
    const mode = () => app.pdfViewer?.annotationEditorMode ?? NONE;
    const inside = (node, x, y) => {
      const r = node.getBoundingClientRect();
      return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom;
    };
    let hinted = false;
    app.eventBus.on("annotationeditormodechanged", ({ mode: m }) => {
      if (m > 0 && !hinted) {
        hinted = true;
        notice("点击标注可选中；按 Delete 或 🗑 删除；↶ 撤销 (Ctrl+Z)，↷ 重做 (Ctrl+Y)；Esc 退出工具",
          "Click a mark to select it; Delete or 🗑 removes it; ↶ Undo (Ctrl+Z), ↷ Redo (Ctrl+Y); Esc leaves the tool");
      }
    });
    // A single click on a highlight while reading (not a double-click: that looks a word up)
    let pending = null;
    document.addEventListener("click", (event) => {
      if (mode() !== NONE || event.detail !== 1) return;
      if (String(window.getSelection() || "").trim()) return;
      const page = event.target.closest?.(".page");
      const { clientX: x, clientY: y } = event;
      if (!page || ![...page.querySelectorAll(".annotationLayer .highlightAnnotation")]
        .some((a) => inside(a, x, y))) return;
      clearTimeout(pending);
      pending = setTimeout(() => selectMarkAt(x, y), 350);
    }, true);
    document.addEventListener("dblclick", () => clearTimeout(pending), true);
    async function selectMarkAt(x, y) {
      app.eventBus.dispatch("switchannotationeditormode", { source: window, mode: HIGHLIGHT });
      for (let i = 0; i < 30; i++) {  // the page's saved highlights become editable shortly
        await new Promise((resolve) => setTimeout(resolve, 100));
        const mark = [...document.querySelectorAll(".annotationEditorLayer .highlightEditor")]
          .find((e) => inside(e, x, y));
        if (mark) {
          mark.focus();  // PDF.js selects a mark that gets the focus: its toolbar shows 🗑
          return;
        }
      }
    }
    // Esc: PDF.js unselects the selected mark; with none selected, leave the tool
    addEventListener("keydown", (event) => {
      if (event.key !== "Escape" || mode() === NONE) return;
      if (document.querySelector(".annotationEditorLayer .selectedEditor")) return;
      if (event.target.closest?.("input, textarea, [contenteditable='true']")) return;
      if (inNotes(event.target)) return;  // Esc in the notes panel is the panel's
      app.eventBus.dispatch("switchannotationeditormode", { source: window, mode: NONE });
    }, true);
  }
  easyMarkEditing();

  // ↶ Undo / ↷ Redo for marks, on the toolbar and with Ctrl+Z, Ctrl+Y and Ctrl+Shift+Z, also
  // while reading (no tool on). The history is PDF.js's own (one per open document, kept when
  // a tool is turned off; up to 128 steps); these only ask it to undo or redo ("editingaction",
  // the event PDF.js's own menus use) and show whether it can ("annotationeditorstateschanged").
  // Search highlights aren't marks, so they never enter it. In a text field (the find bar,
  // the dictionary, a form), the shortcuts are the field's own and PDF.js doesn't see them.
  async function undoRedo() {
    const app = window.PDFViewerApplication;
    if (!app) return;
    await app.initializedPromise;
    const anchor = document.getElementById("editorModeButtons");
    if (!anchor) return;
    const button = (id, zh, en, keys) => {
      const b = el("button", "toolbarButton");
      b.id = id;
      b.type = "button";
      b.disabled = true;
      b.title = `${zh} ${en} (${keys})`;
      b.setAttribute("aria-label", `${zh} ${en}`);
      b.append(el("span", null, `${zh} ${en}`));
      return b;
    };
    const undo = button("mlUndo", "撤销", "Undo", "Ctrl+Z");
    const redo = button("mlRedo", "重做", "Redo", "Ctrl+Y / Ctrl+Shift+Z");
    anchor.before(undo, redo);
    const act = (name) => app.eventBus.dispatch("editingaction", { source: window, name });
    undo.onclick = () => act("undo");
    redo.onclick = () => act("redo");
    app.eventBus.on("annotationeditorstateschanged", ({ details }) => {
      if ("hasSomethingToUndo" in details) undo.disabled = !details.hasSomethingToUndo;
      if ("hasSomethingToRedo" in details) redo.disabled = !details.hasSomethingToRedo;
    });
    app.eventBus.on("documentloaded", () => { undo.disabled = redo.disabled = true; });
    // Shortcuts: after the page's own listeners (document, bubbling) and before PDF.js's
    // (window), so PDF.js never acts twice, nor inside a text field.
    document.addEventListener("keydown", (event) => {
      if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
      const key = event.key.toLowerCase();
      const name = key === "z" ? (event.shiftKey ? "redo" : "undo")
        : key === "y" && !event.shiftKey ? "redo" : null;
      if (!name) return;
      event.stopPropagation();
      const t = event.target;
      if (t instanceof HTMLInputElement || t instanceof HTMLTextAreaElement
        || t instanceof HTMLSelectElement || t?.isContentEditable) return;  // the field's own
      if (inNotes(t)) return;  // in the notes panel: never the PDF's marks
      event.preventDefault();
      act(name);
    });
  }
  undoRedo();

  // Keep your marks: highlights, drawings, text and stamps made with PDF.js's tools are
  // written into the library's PDF (reader.save_marks) a second after you stop marking.
  // What counts is whether the marks on screen differ from the last ones the server said it
  // wrote: PDF.js's hash of its annotation storage, where "" means no changes (the PDF as
  // opened). PDF.js's own "modified" flag isn't enough: it isn't set when a mark leaves the
  // storage (a deletion, an undo), so it can't tell whether everything is saved.
  // - The status (bottom right) says 标注未保存 (Marks not saved yet) with 立即保存 (Save now),
  //   正在保存 (Saving), 标注已保存 (Marks saved) only once the server has written the file,
  //   or 标注没保存 (Marks not saved) with 重试 (Retry), which stays until a save succeeds.
  // - While marks are unsaved or a save is on its way, the browser asks before the tab is
  //   closed, reloaded or left; nothing is sent while closing (a whole PDF can't be).
  // - A save sends the marks as they are when it starts; changes made meanwhile are saved
  //   next, so the last state is the one that stays. One save at a time.
  // - Versions (D5): a save names the version of the PDF its marks were made on: the SHA-256
  //   of the bytes this tab loaded, then of what it last saved (the server's answer). The
  //   server writes only over that version. If the PDF changed elsewhere (another tab saved,
  //   OCR replaced it), nothing is written to it: the tab's PDF is kept, checked, in
  //   archive/marks-conflicts/ and the status says 标注冲突 (Marks conflict) with where. The
  //   marks stay here, unsaved: nothing more is saved by itself; 再存一份副本 (Keep another
  //   copy) keeps marks made since; 重新载入 (Reload) shows the current PDF, and only once
  //   the latest marks are in a copy (until then leaving is warned about, as for any unsaved
  //   marks).
  // - A save that got no answer may have been written: its version is sent with the next save
  //   (X-PDF-Unconfirmed), and if that's the PDF now, it was this tab's own: no conflict.
  async function keepMarks() {
    const app = window.PDFViewerApplication;
    if (!docId || !token || !app) return;
    await app.initializedPromise;
    const QUIET = 1000;  // ms without changes before saving
    const status = el("div", "ml-saved ml-marks");
    status.hidden = true;
    document.body.append(status);
    let hideTimer = null;
    let state = "";
    const show = (next, zh, en, ...actions) => {
      clearTimeout(hideTimer);
      status.hidden = false;
      if (next === state && next !== "failed" && next !== "conflict") return;  // keep its button usable
      state = next;
      status.dataset.state = next;
      status.replaceChildren(bi(zh, en));
      for (const action of actions) status.append(" ", action);
      status.classList.toggle("ml-problem", next === "failed" || next === "conflict");
      if (next === "saved") hideTimer = setTimeout(() => { status.hidden = true; state = ""; }, 2500);
    };
    const button = (zh, en, onclick) => {
      const b = biEl("button", "ml-small", zh, en);
      b.onclick = onclick;
      return b;
    };
    const hex = (buffer) => [...new Uint8Array(buffer)].map((b) => b.toString(16).padStart(2, "0")).join("");
    const sha256 = async (bytes) => hex(await crypto.subtle.digest("SHA-256", bytes));
    let savedHash = "";   // the marks the server last wrote ("": the PDF as opened)
    let lastHash = null;  // the marks at the last check
    let changedAt = 0;    // when they last changed
    let saving = false;
    let failures = 0;
    let failedAt = 0;
    let version = null;   // promise: the version this tab's marks are on (as loaded, then saved)
    let unconfirmed = []; // versions of saves that got no answer since the last confirmed one
    let conflict = null;  // after a 409: {kept: where the copy is, marks: the marks it holds}
    let leaving = false;  // Reload after a conflict, with the latest marks in a copy
    app.eventBus.on("documentloaded", () => {
      savedHash = "";
      lastHash = null;
      failures = 0;
      unconfirmed = [];
      conflict = null;
      status.hidden = true;
      state = "";
      // The exact bytes PDF.js loaded (the server sends the whole file, never cached)
      version = app.pdfDocument.getData().then(sha256);
      version.catch(() => {});  // (a save says so, if it comes to that)
    });
    const current = () => app.pdfDocument?.annotationStorage.serializable.hash ?? savedHash;
    const unsaved = () => current() !== savedHash;

    async function send(data, base, action) {
      const response = await fetch("/api/save-marks", {
        method: "POST",
        headers: {
          "Content-Type": "application/pdf", "X-Library-Token": token, "X-Document-Id": docId,
          "X-PDF-Version": base, "X-PDF-Unconfirmed": unconfirmed.join(","),
          "X-Marks-Action": action,
        },
        body: data,
      });
      const answer = await response.json().catch(() => ({}));
      return { response, answer };
    }

    function showConflict(problem = "") {
      const latest = current() === conflict.marks;  // the copy holds the marks shown now
      status.dataset.latest = latest ? "1" : "0";
      const where = el("code", "ml-path");
      where.textContent = conflict.kept;
      const copyPath = button("复制路径", "Copy path", () => navigator.clipboard?.writeText(conflict.kept));
      const actions = [where, copyPath];
      if (latest) {
        actions.push(button("重新载入", "Reload", () => {
          if (current() !== conflict.marks) return showConflict();  // marked meanwhile
          leaving = true;
          app.pdfDocument?.annotationStorage.resetModified();  // they're in the checked copy
          location.reload();
        }));
      } else {
        actions.push(bi("之后的标注还不在副本里", "Marks made since aren't in the copy yet"),
          button("再存一份副本", "Keep another copy", keepCopy));
      }
      if (problem) actions.push(biEl("span", "ml-error", "副本没保存", problem));
      show("conflict",
        "标注冲突：这份 PDF 在别处被修改了（另一个标签页或 OCR），你的标注没有写入它，已另存在资料库的",
        "Marks conflict: this PDF was changed elsewhere (another tab, or OCR), so your marks "
        + "weren't written into it; they are kept in your library's", ...actions);
    }

    async function keepCopy() {
      const doc = app.pdfDocument;
      if (!doc || saving || !conflict) return;
      saving = true;
      const marks = current();
      try {
        const data = await doc.saveDocument();
        const { response, answer } = await send(data, await version, "keep-copy");
        if (!response.ok || !answer.kept) throw new Error(answer.error || response.statusText);
        if (doc !== app.pdfDocument) return;
        conflict = { kept: answer.kept, marks };
        showConflict();
      } catch (error) {
        showConflict(error.message);
      } finally {
        saving = false;
      }
    }

    async function save() {
      const doc = app.pdfDocument;
      if (!doc || saving || conflict) return;
      const hash = current();
      if (hash === savedHash) return;
      saving = true;
      show("saving", "正在保存标注…", "Saving your marks…");
      let sent = null;
      try {
        const base = await version;
        const data = await doc.saveDocument();  // the PDF with the marks as they are now: `hash`
        sent = await sha256(data);
        const { response, answer } = await send(data, base, "save");
        if (doc !== app.pdfDocument) return;  // another PDF was opened meanwhile
        if (response.status === 409 && answer.conflict) {  // changed elsewhere: ours is kept
          sent = null;
          unconfirmed = [];
          conflict = { kept: answer.kept, marks: hash };
          failures = 0;
          showConflict();
          return;
        }
        if (!response.ok || !answer.saved || !answer.version) {
          throw new Error(answer.error || response.statusText);
        }
        sent = null;
        unconfirmed = [];
        version = Promise.resolve(answer.version);  // what the next save builds on
        savedHash = hash;
        failures = 0;
        if (current() === hash) {
          doc.annotationStorage.resetModified();  // PDF.js's own warning off too
          show("saved", "标注已保存", "Marks saved");
        }
      } catch (error) {
        if (sent) {  // sent, but no proper answer: perhaps written; the next save says so
          unconfirmed = [...unconfirmed, sent].slice(-8);
        }
        failures++;
        failedAt = Date.now();
        show("failed", "标注没保存", `Marks not saved: ${error.message}`,
          button("重试", "Retry", () => { failures = 0; save(); }));
      } finally {
        saving = false;
      }
    }

    setInterval(() => {
      if (!app.pdfDocument || saving) return;
      const hash = current();
      if (conflict) {  // nothing saved by itself: say whether the copy has the latest marks
        if ((hash === conflict.marks) !== (status.dataset.latest === "1")) {
          status.dataset.latest = hash === conflict.marks ? "1" : "0";
          showConflict();
        }
        return;
      }
      if (hash === savedHash) {  // all saved (also after undoing back to it)
        lastHash = null;
        if (app._annotationStorageModified) app.pdfDocument.annotationStorage.resetModified();
        if (state === "unsaved" || state === "failed") { status.hidden = true; state = ""; }
        return;
      }
      if (hash !== lastHash) {  // still marking: wait until it's quiet for a moment
        lastHash = hash;
        changedAt = Date.now();
        failures = Math.min(failures, 1);  // a new change tries again
      }
      if (failures) {  // stays visible; tries again after 3 s, at most 3 times, then Retry
        if (failures < 3 && Date.now() - failedAt > 3000) save();
        return;
      }
      show("unsaved", "标注未保存", "Marks not saved yet", button("立即保存", "Save now", save));
      if (Date.now() - changedAt >= QUIET) save();
    }, 250);

    addEventListener("beforeunload", (event) => {
      if (leaving && conflict && current() === conflict.marks) return;  // Reload: they're kept
      if (!saving && !unsaved() && !conflict) return;  // all saved: leave freely
      event.preventDefault();
      event.returnValue = "";  // the browser's own "Leave site? Changes may not be saved"
    });
  }
  keepMarks();

  document.addEventListener("mousedown", (event) => {
    if (!event.target.closest?.(".ml-popup, .ml-bubble")) closeAll();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeAll();
  });
  // Scrolling the page moves the text away from the popup; scrolling inside the popup is fine
  document.addEventListener("scroll", (event) => {
    if (!event.target.closest?.(".ml-popup")) closeAll();
  }, true);

  // For notes.js (the notes panel): the same token, requests and bilingual labels, not copies
  window.myLibraryReader = Object.freeze({
    token, docId, post, el, bi, biEl, isPreview: () => preview,
  });
})();
