// Word lookup for the PDF.js reading view (served by library_server.py, see reader.py).
// Double-click a word: popup with your subject glossaries + the dictionary meaning.
// Drag over a phrase: it's looked up the same way; a longer passage gets a 翻译 (Translate)
// button. Every Chinese label comes with its English translation (bi() below).
(() => {
  "use strict";
  const token = window.MYLIBRARY_TOKEN;
  const file = new URLSearchParams(location.search).get("file") || "";
  const slug = (file.match(/\/books\/([a-z0-9-]+)\.pdf$/) || [])[1];
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

  function closeAll() {
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
    document.body.append(box);
    const w = box.offsetWidth;
    const h = box.offsetHeight;
    let left = Math.min(Math.max(8, rect.left), innerWidth - w - 8);
    let top = rect.bottom + 6;
    if (top + h > innerHeight - 8) top = Math.max(8, rect.top - h - 6);
    box.style.left = `${left}px`;
    box.style.top = `${top}px`;
  }

  async function post(path, body) {
    const response = await fetch(path, {
      method: "POST",
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

  // "fischer-2008-optical-system-design" -> "Fischer 2008"
  function bookLabel(bookSlug) {
    const [author, year] = bookSlug.split("-");
    return `${author[0].toUpperCase()}${author.slice(1)} ${year}`;
  }

  function openPage(bookSlug, page) {
    if (bookSlug === slug && window.PDFViewerApplication) {
      PDFViewerApplication.page = page;
      closeAll();
    } else {
      window.open(`/pdfjs/web/viewer.html?file=/books/${bookSlug}.pdf#page=${page}`, "_blank");
    }
  }

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
        found = await post("/api/search", { text: term, slug });
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
        where.append(el("b", null, bookLabel(r.slug)), ` · p. ${r.page}`);
        if (r.slug === slug) where.append(biEl("span", "ml-here", "本书", "this book"));
        item.append(where, snippetNode(r.snippet));
        item.onclick = () => openPage(r.slug, r.page);
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
    let data;
    try {
      data = await post("/api/lookup", { text, context, slug });
    } catch (e) {
      popup.replaceChildren(biEl("div", "ml-error", "查询失败", "Lookup failed: " + e.message));
      return;
    }
    if (!popup) return; // closed while waiting
    const box = popup;
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
    if (slug) {
      const save = biEl("button", "ml-button", "加入生词本", "Save word");
      save.onclick = async () => {
        save.disabled = true;
        try {
          const r = await post("/api/save-word", { slug, text, context, page });
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
    place(box, rect); // re-place now that the size is known
  }

  document.addEventListener("dblclick", (event) => {
    if (event.target.closest?.(".ml-popup, .ml-bubble")) return;
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

  // Remember where you are: the page is written to notes/<slug>/README.md ("Last read: page N")
  // so the library's Continue button can bring you back. Only once you've moved away from the
  // page the book opened at: just opening a chapter to look doesn't overwrite your place.
  async function trackPosition() {
    const app = window.PDFViewerApplication;
    if (!slug || !token || !app) return;
    await app.initializedPromise;
    const openedAt = Number((location.hash.match(/page=(\d+)/) || [])[1]) || null;
    let moved = false;
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
        body: JSON.stringify({ slug, page }),
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
  }
  trackPosition();

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
})();
