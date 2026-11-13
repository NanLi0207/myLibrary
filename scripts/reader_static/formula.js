// ∑ Formula recognition (task 4 M5e): a screenshot of a formula becomes editable LaTeX. This
// file is the dialog only; notes.js decides where the result goes (`insert`), so it never
// touches a note itself.
//
// - The image is recognised on this computer (/api/formula/recognize → formula_ocr.py); it is
//   never sent anywhere else and isn't stored.
// - The model is optional: without it the dialog says so and offers the one-time download,
//   which starts only when the user clicks the button (/api/formula/install {consent: true}).
// - Up to three results are shown, each typeset with the preview's own KaTeX (the same safe
//   options: preview.js formulaHtml) with its LaTeX source. They are the model's guesses: no
//   percentages (the model's scores aren't an accuracy), and when its two best scored almost
//   the same the dialog says so. The chosen one goes into an editor with a live preview; only
//   the user's Insert puts it into the note.
// - Late answers are ignored: each request has a number, and only the latest one for the
//   dialog still open is shown.
(() => {
  "use strict";
  const reader = window.myLibraryReader;
  if (!reader?.token) return;
  const { el, bi, biEl, post } = reader;
  const TYPES = ["image/png", "image/jpeg", "image/webp"];
  const MAX_BYTES = 10 * 1024 * 1024;
  const TIMEOUT = 90_000;  // ms: the first recognition also loads the model
  const POLL = 1000;  // ms between install progress checks

  let dialog = null;
  let run = null;  // the dialog now: {image, url, insert, asImage, candidates}
  let serial = 0;  // the latest request; older answers are ignored
  let pollTimer = null;

  function button(zh, en, onclick, cls = "ml-small") {
    const b = biEl("button", cls, zh, en);
    b.type = "button";
    b.addEventListener("click", onclick);
    return b;
  }

  // --- the dialog -------------------------------------------------------------------------

  function build(host) {
    dialog = el("dialog", "ml-formula");
    dialog.id = "mlFormulaDialog";
    dialog.setAttribute("aria-labelledby", "mlFormulaTitle");
    const title = biEl("h2", "ml-formula-title", "∑ 识别公式", "Recognize a formula");
    title.id = "mlFormulaTitle";
    const close = el("button", "ml-small ml-formula-close", "×");
    close.type = "button";
    close.title = "关闭 Close (Esc)";
    close.setAttribute("aria-label", close.title);
    close.addEventListener("click", () => finish());
    const head = el("div", "ml-formula-head");
    head.append(title, close);
    const picture = el("div", "ml-formula-picture");
    picture.id = "mlFormulaPicture";
    const state = el("div", "ml-formula-state");
    state.id = "mlFormulaState";
    state.setAttribute("role", "status");
    const results = el("div", "ml-formula-results");
    results.id = "mlFormulaResults";
    dialog.append(head, picture, state, results);
    host.append(dialog);
    // Esc closes the dialog (the panel's own Esc handler, outside it, never sees it)
    dialog.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        finish();
      }
    });
    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      finish();
    });
    // Ctrl+V anywhere in the dialog but the LaTeX editor: a (new) screenshot to recognise
    dialog.addEventListener("paste", (event) => {
      if (event.target.closest?.(".ml-formula-editor")) return;  // text into the editor
      const file = imageOf(event.clipboardData);
      if (!file) return;
      event.preventDefault();
      event.stopPropagation();
      take(file);
    });
    // The panel hidden by any path (Alt+N, a narrower window): the dialog goes too, so the
    // page is never left behind a dialog nobody can see
    new MutationObserver(() => {
      if (host.hidden && dialog.open) finish();
    }).observe(host, { attributes: true, attributeFilter: ["hidden"] });
  }

  const parts = () => ({
    picture: dialog.querySelector("#mlFormulaPicture"),
    state: dialog.querySelector("#mlFormulaState"),
    results: dialog.querySelector("#mlFormulaResults"),
  });

  function setState(name, ...nodes) {
    dialog.dataset.state = name;
    parts().state.replaceChildren(...nodes);
  }

  function finish() {
    serial++;  // whatever is still on its way is ignored
    clearTimeout(pollTimer);
    if (run?.url) URL.revokeObjectURL(run.url);
    run = null;
    if (dialog?.open) dialog.close();
  }

  // An image from the clipboard (or a file list): the first PNG, JPEG or WebP
  function imageOf(data) {
    if (!data) return null;
    for (const item of data.items || []) {
      if (item.kind === "file" && item.type.startsWith("image/")) return item.getAsFile();
    }
    return [...(data.files || [])].find((f) => f.type.startsWith("image/")) || null;
  }

  // --- opening, taking an image --------------------------------------------------------------

  // options: {host (the notes panel), image (a Blob or null), insert(latex, display) -> null
  // or [zh, en] why it wasn't inserted, asImage(blob) (keep the screenshot as an image)}
  function open(options) {
    if (!dialog) build(options.host);
    finish();
    run = { insert: options.insert, asImage: options.asImage, image: null, url: null };
    parts().results.replaceChildren();
    parts().picture.replaceChildren();
    dialog.showModal();
    if (options.image) take(options.image);
    else waitForImage();
  }

  function waitForImage() {
    const read = button("从剪贴板读取", "Read the clipboard", readClipboard);
    read.id = "mlFormulaReadClipboard";
    const zone = biEl("div", "ml-formula-drop", "按 Ctrl+V 粘贴公式的截图",
      "Press Ctrl+V to paste a screenshot of the formula");
    zone.tabIndex = 0;
    setState("empty", zone, read);
    zone.focus();
  }

  async function readClipboard() {
    const mine = serial;
    try {
      for (const item of await navigator.clipboard.read()) {
        if (mine !== serial || !run) return;
        const type = item.types.find((t) => TYPES.includes(t));
        if (type) {
          const blob = await item.getType(type);
          if (mine === serial && run) take(blob);
          return;
        }
      }
      if (mine !== serial || !run) return;
      setState("empty", biEl("div", "ml-error", "剪贴板里没有图片", "There's no image on the clipboard"));
    } catch {
      if (mine !== serial || !run) return;
      setState("empty", biEl("div", "ml-error", "无法读取剪贴板：请按 Ctrl+V",
        "The clipboard can't be read here: press Ctrl+V instead"));
    }
  }

  function take(blob) {
    if (!run) return;
    serial++;
    clearTimeout(pollTimer);
    parts().results.replaceChildren();
    if (!TYPES.includes(blob.type)) {
      setState("error", biEl("div", "ml-error", "只能识别 PNG、JPEG 或 WebP 图片",
        "Only PNG, JPEG and WebP images can be recognised"));
      return;
    }
    if (blob.size > MAX_BYTES) {
      setState("error", biEl("div", "ml-error", "图片大于 10 MB", "The image is larger than 10 MB"));
      return;
    }
    if (run.url) URL.revokeObjectURL(run.url);
    run.image = blob;
    run.url = URL.createObjectURL(blob);
    const img = el("img", "ml-formula-image");
    img.src = run.url;
    img.alt = "公式截图 Formula screenshot";
    parts().picture.replaceChildren(img);
    parts().results.replaceChildren();
    recognize();
  }

  // --- recognising -------------------------------------------------------------------------

  async function request(blob) {
    const abort = new AbortController();
    const timer = setTimeout(() => abort.abort(), TIMEOUT);
    try {
      const response = await fetch("/api/formula/recognize", {
        method: "POST",
        headers: { "X-Library-Token": reader.token, "Content-Type": "application/octet-stream" },
        body: blob,
        signal: abort.signal,
      });
      let data = {};
      try {
        data = await response.json();
      } catch {
        data = {};
      }
      if (response.status === 403) {
        return { error: "restarted", message: "the server was restarted: reload this page" };
      }
      if (!response.ok) {
        return { error: data.code || "failed", message: data.error || response.statusText };
      }
      return data;
    } catch (error) {
      return { error: "offline", message: error.name === "AbortError"
        ? "no answer in time" : "the server isn't reachable" };
    } finally {
      clearTimeout(timer);
    }
  }

  async function recognize() {
    if (!run?.image) return;
    const mine = ++serial;
    parts().results.replaceChildren();
    setState("recognizing", biEl("div", "ml-muted", "正在本机识别…（第一次需要载入模型）",
      "Recognising on this computer… (the first time also loads the model)"));
    const answer = await request(run.image);
    if (mine !== serial || !run) return;  // closed, or another image since
    if (answer.error === "not-installed" || answer.error === "damaged") return offerInstall(answer);
    if (answer.error) return failed(answer);
    showResults(answer);
  }

  function failed(answer) {
    const why = {
      busy: ["另一个公式正在识别，请稍后重试", "Another formula is being recognised: try again in a moment"],
      timeout: ["识别时间过长，可以只截取公式的一部分", "Recognition took too long: try a smaller part of the formula"],
      restarted: ["服务器重新启动过：请重新载入此页面", "The server was restarted: reload this page"],
      offline: ["服务器未连接", "The server isn't reachable"],
      unavailable: ["本机 OCR 运行环境不可用", "The local OCR runtime is unavailable; the model does not need downloading again"],
    }[answer.error] || ["没能识别这张图片", "This image couldn't be recognised"];
    setState("error",
      biEl("div", "ml-error", why[0], `${why[1]} (${answer.message})`),
      button("重试", "Retry", recognize),
      keepAsImage());
  }

  // The screenshot kept as an image after all (M5d's paste)
  function keepAsImage() {
    const b = button("改为插入图片", "Insert as an image instead", () => {
      const blob = run?.image;
      const keep = run?.asImage;
      finish();
      if (blob && keep) keep(blob);
    });
    b.id = "mlFormulaAsImage";
    b.disabled = !run?.image;
    return b;
  }

  // --- installing the model (only on the user's click) ----------------------------------------

  async function offerInstall(answer) {
    const mine = serial;
    let info;
    try {
      info = await post("/api/formula/status", {});
    } catch (error) {
      if (mine !== serial || !run) return;
      return failed({ error: "offline", message: error.message });
    }
    if (mine !== serial || !run) return;
    if (info.installing) return watchInstall();
    const mb = Math.round(info.download_bytes / 1e6);
    const damaged = answer?.error === "damaged";
    const install = button(damaged ? "重新下载并安装" : "下载并安装", damaged ? "Download and install again" : "Download and install", startInstall, "ml-small ml-primary");
    install.id = "mlFormulaInstall";
    setState("install",
      biEl("div", damaged ? "ml-error" : null,
        damaged ? "公式识别模型的文件已损坏或不完整" : "公式识别还没有安装",
        damaged ? "The formula model's files are damaged or incomplete" : "Formula recognition isn't installed yet"),
      biEl("p", "ml-muted",
        `需要一次性下载约 ${mb} MB 的模型（${info.engine}，${info.license} 许可证，来自 huggingface.co）。安装后完全在本机离线运行，图片不会上传，也不收费。`,
        `It needs a one-time download of about ${mb} MB: the ${info.engine} model (${info.license} licence) from huggingface.co. After that it runs entirely on this computer, offline and free; your images are never uploaded.`),
      info.error ? biEl("div", "ml-error", "上次下载失败", `The last download failed: ${info.error}`) : "",
      install, button("取消", "Cancel", () => finish()), keepAsImage());
  }

  async function startInstall() {
    const mine = serial;
    try {
      await post("/api/formula/install", { consent: true });
    } catch (error) {
      if (mine !== serial || !run) return;
      return failed({ error: "offline", message: error.message });
    }
    if (mine !== serial || !run) return;
    watchInstall();
  }

  async function watchInstall() {
    clearTimeout(pollTimer);
    const mine = serial;
    let info;
    try {
      info = await post("/api/formula/status", {});
    } catch (error) {
      if (mine !== serial || !run) return;
      return failed({ error: "offline", message: error.message });
    }
    if (mine !== serial || !run) return;
    if (info.installed && !info.installing) {
      if (run.image) return recognize();
      return waitForImage();
    }
    if (!info.installing) return offerInstall({});  // failed: its error is shown there
    const progress = el("progress", "ml-formula-progress");
    progress.max = info.total;
    progress.value = info.done;
    const mb = (n) => (n / 1e6).toFixed(0);
    setState("installing",
      biEl("div", "ml-muted", `正在下载模型：${mb(info.done)} / ${mb(info.total)} MB`,
        `Downloading the model: ${mb(info.done)} / ${mb(info.total)} MB`),
      progress,
      biEl("div", "ml-muted", "可以关闭此窗口：下载会在后台继续", "You can close this: the download goes on in the background"));
    pollTimer = setTimeout(watchInstall, POLL);
  }

  // --- the results --------------------------------------------------------------------------

  const preview = () => window.myLibraryPreview;

  function typeset(box, latex, display = true) {
    const result = preview()?.formulaHtml ? preview().formulaHtml(latex, display)
      : { error: "the preview isn't available" };
    if (result.html !== undefined) {
      box.innerHTML = result.html;  // KaTeX's output, trust: false (preview.js)
      box.classList.remove("ml-math-error");
      return true;
    }
    box.replaceChildren(biEl("span", "ml-error", "公式错误", `Formula error: ${result.error}`));
    box.classList.add("ml-math-error");
    return false;
  }

  // "$$ x $$" or "\[ x \]" typed or pasted into the editor: the delimiters are the note's
  // business (notes.js adds them), so one surrounding pair is taken off, but only if it is
  // one formula's: in "$a$ and $b$" the first "$" closes after "a", so nothing is taken off
  // (preview.js closesAtEnd: the preview's own reading)
  function clean(latex) {
    const text = String(latex).trim();
    const fits = preview()?.closesAtEnd;
    for (const [open, close] of [["$$", "$$"], ["\\[", "\\]"], ["\\(", "\\)"], ["$", "$"]]) {
      if (text.length > open.length + close.length && text.startsWith(open) && text.endsWith(close)) {
        const inner = text.slice(open.length, text.length - close.length);
        if (fits && !fits(inner, close)) return text;
        return inner.trim();
      }
    }
    return text;
  }

  function showResults(answer) {
    const candidates = answer.candidates || [];
    run.candidates = candidates;
    const notes = [biEl("div", "ml-muted", "识别结果是模型的猜测，可能有误（例如 l、1、I，0、O，v、ν）：插入前请检查并修改。",
      "These are the model's guesses and can be wrong (l, 1 and I; 0 and O; v and ν, …): check and correct before inserting.")];
    if (answer.similar) {
      notes.push(biEl("div", "ml-warning", "模型对前两个结果的评分几乎相同：请仔细比较。",
        "The model scored the first two results almost the same: compare them carefully."));
    }
    notes.push(biEl("div", "ml-muted ml-formula-engine", `本机识别，用时 ${answer.seconds} 秒`,
      `Recognised on this computer by ${answer.engine} in ${answer.seconds} s`));
    setState("results", ...notes);

    const list = el("div", "ml-formula-candidates");
    list.setAttribute("role", "radiogroup");
    list.setAttribute("aria-label", "识别结果 Results");
    const editor = el("textarea", "ml-formula-editor");
    editor.id = "mlFormulaEditor";
    editor.spellcheck = false;
    editor.rows = 3;
    editor.setAttribute("aria-label", "LaTeX（可编辑）LaTeX (editable)");
    const live = el("div", "ml-formula-live");
    live.id = "mlFormulaLive";
    const choose = (index) => {
      for (const [i, card] of [...list.children].entries()) {
        card.setAttribute("aria-checked", String(i === index));
        card.querySelector("input").checked = i === index;
      }
      editor.value = candidates[index].latex;
      update();
    };
    candidates.forEach((candidate, index) => {
      const card = el("label", "ml-formula-candidate");
      card.dataset.index = String(index);
      const radio = el("input");
      radio.type = "radio";
      radio.name = "mlFormulaCandidate";
      radio.addEventListener("change", () => choose(index));
      const label = index === 0 ? bi(`结果 1（模型首选）`, "Result 1 (the model's first choice)")
        : bi(`结果 ${index + 1}`, `Result ${index + 1} (alternative)`);
      const head = el("div", "ml-formula-candidate-head");
      head.append(radio, label);
      const shown = el("div", "ml-formula-rendered");
      typeset(shown, candidate.latex);
      const source = el("code", "ml-formula-source", candidate.latex);
      card.append(head, shown, source);
      list.append(card);
    });

    const block = el("input");
    block.type = "radio";
    block.name = "mlFormulaMode";
    block.id = "mlFormulaBlock";
    block.checked = true;
    const inline = el("input");
    inline.type = "radio";
    inline.name = "mlFormulaMode";
    inline.id = "mlFormulaInline";
    const mode = el("div", "ml-formula-mode");
    const blockLabel = el("label");
    blockLabel.append(block, bi("独立公式 $$…$$", "Displayed $$…$$"));
    const inlineLabel = el("label");
    inlineLabel.append(inline, bi("行内公式 $…$", "Inline $…$"));
    mode.append(blockLabel, inlineLabel);

    const message = el("div", "ml-formula-message");
    message.id = "mlFormulaMessage";
    message.setAttribute("role", "alert");
    const insert = button("插入到笔记", "Insert into the note", () => {
      const latex = clean(editor.value);
      if (!latex) return;
      // A modal makes the note inert: close it before insertText, otherwise the browser
      // cannot focus the note and the fallback replacement loses its Undo history.
      dialog.close();
      const problem = run?.insert(latex, block.checked);
      if (problem) {
        dialog.showModal();
        message.replaceChildren(biEl("div", "ml-error", ...problem));
        return;
      }
      finish();
    }, "ml-small ml-primary");
    insert.id = "mlFormulaInsert";
    let timer = null;
    function update() {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const latex = clean(editor.value);
        insert.disabled = !latex;
        if (!latex) {
          live.replaceChildren();
          return;
        }
        const ok = typeset(live, latex, block.checked);
        insert.replaceChildren(ok ? bi("插入到笔记", "Insert into the note")
          : bi("仍然插入", "Insert anyway (it doesn't typeset)"));
      }, 120);
    }
    editor.addEventListener("input", update);
    block.addEventListener("change", update);
    inline.addEventListener("change", update);
    editor.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        insert.click();
      }
    });
    const editorLabel = biEl("div", "ml-formula-label", "LaTeX（可直接修改）", "LaTeX (edit it here)");
    const actions = el("div", "ml-formula-actions");
    actions.append(insert, button("取消", "Cancel", () => finish()), keepAsImage(),
      button("重新识别", "Recognise again", recognize));
    parts().results.replaceChildren(list, editorLabel, editor, biEl("div", "ml-formula-label",
      "预览", "Preview"), live, mode, message, actions);
    choose(0);
    editor.focus();
  }

  window.myLibraryFormula = Object.freeze({
    open,
    isOpen: () => Boolean(dialog?.open),
    clean,
  });
})();
