// The notes' preview (task 4 M5a): a note's Markdown source shown rendered, read-only. It only
// reads text it is given and returns HTML for it; it never changes, saves or stores anything.
// notes.js decides what to show and handles the clicks.
//
// Safety, by construction rather than by cleaning HTML afterwards:
// - markdown-it with html: false: HTML written in a note is escaped and shown as text, so
//   nothing in a note can add an element, an attribute or a script;
// - links: only http(s), #heading, a relative name (another note) and /read/<id> become links
//   (validateLink, which markdown-it applies after decoding entities and normalising); any
//   other scheme (javascript:, data:, file:, vbscript:, …) stays plain text;
// - images: only the document's own pasted images (M5d) are loaded: notes.js passes a
//   function (options.image) that turns "assets/<name>" into the server's contained route,
//   /notes-assets/<id>/<name>; any other image (a web address, data:, a path elsewhere) stays
//   a placeholder with its description, and no request is made for it;
// - heading ids are prefixed (ml-h-…), so they can never collide with PDF.js's own ids.
// Without markdown-it (not set up: reader.py --setup-preview) `available` is false and notes.js
// shows the plain text instead.
//
// Maths (M5b): $…$ and \(…\) inline, $$…$$ and \[…\] displayed, typeset by KaTeX. They are
// markdown-it rules of their own (an inline one, and a block one for a formula on lines of its
// own), never a search-and-replace over the text, so code spans, code blocks and \-escapes stay
// as Markdown has them:
// - a backslash escapes the next character (\$ is a dollar sign; \\( is "\(", not maths), and
//   inside a formula it is LaTeX's own (\$ and \} never end one);
// - $ opens a formula only before a non-space; as in TeX, the next unescaped $ ends it, and
//   only if it follows a non-space and isn't before a digit or another $; else the first $ was
//   a dollar sign: "$5 and $10" and "costs $3, formula $x^2$" keep their amounts as text;
// - a backtick ends the search for the closing delimiter (code spans come first), and a
//   displayed block ends at a blank line: an unclosed delimiter stays plain text;
// - KaTeX with trust: false (no links, classes, styles or data attributes from a formula),
//   maxSize and maxExpand limits, formulas of at most MAX_FORMULA characters and MAX_DEPTH
//   nested groups (anything else that overflows KaTeX's own recursion is caught); an error shows
//   that formula's source and the reason, and touches nothing else.
// KaTeX is loaded only when every file of it passed its check (reader.katex_installed); without
// it a formula is shown as written, and the preview says why.
(() => {
  "use strict";
  const create = window.markdownit;
  const md = typeof create === "function"
    ? create({ html: false, linkify: false, typographer: false, breaks: false })
    : null;
  const katex = () => (typeof window.katex?.renderToString === "function" ? window.katex : null);

  const SCHEME = /^[a-z][a-z0-9+.-]*:/i;
  const isWeb = (url) => /^https?:\/\//i.test(url);
  function allowed(url) {
    const u = String(url).trim();
    if (SCHEME.test(u)) return isWeb(u);  // http(s) only
    if (u.startsWith("//") || u.includes("\\")) return false;  // another host, odd paths
    return true;  // #heading, another note (relative), /read/<id>
  }

  // A heading's id: its text, lower-case, words joined by "-" (as GitHub and VS Code make them,
  // so [see below](#my-heading) works), prefixed; repeated headings get -1, -2, …
  function slug(text) {
    return text.trim().toLowerCase()
      .replace(/[^\p{L}\p{N}\s-]/gu, "")
      .replace(/\s+/g, "-");
  }

  if (md) {
    md.validateLink = allowed;
    const escape = md.utils.escapeHtml;

    md.core.ruler.push("ml_heading_ids", (state) => {
      const seen = new Map();
      state.tokens.forEach((token, i) => {
        if (token.type !== "heading_open") return;
        const base = slug(state.tokens[i + 1]?.content || "") || "section";
        const count = seen.get(base) || 0;
        seen.set(base, count + 1);
        token.attrSet("id", `ml-h-${count ? `${base}-${count}` : base}`);
      });
    });

    const linkOpen = md.renderer.rules.link_open
      || ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options));
    md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
      const href = tokens[idx].attrGet("href") || "";
      if (isWeb(href)) {  // opened in a new tab, telling it nothing about this page
        tokens[idx].attrSet("target", "_blank");
        tokens[idx].attrSet("rel", "noopener noreferrer");
      }
      return linkOpen(tokens, idx, options, env, self);
    };

    md.renderer.rules.image = (tokens, idx, options, env, self) => {
      const token = tokens[idx];
      const alt = self.renderInlineAsText(token.children || [], options, env);
      const src = token.attrGet("src") || "";
      const url = typeof env.mlImage === "function" ? env.mlImage(src) : null;
      if (url) {  // (a same-origin path made by notes.js from a checked name; escaped anyway)
        return `<img class="ml-image" src="${escape(url)}" alt="${escape(alt)}"`
          + ` title="${escape(alt || src)}" decoding="async">`;
      }
      return `<span class="ml-image-placeholder" title="${escape(src)}">`
        + `图片 Image: ${escape(alt || src)}</span>`;
    };

    md.inline.ruler.before("escape", "ml_math", mathInline);
    md.block.ruler.before("fence", "ml_math_block", mathBlock,
      { alt: ["paragraph", "reference", "blockquote", "list"] });
    md.renderer.rules.ml_math = (tokens, idx, options, env) => mathHtml(tokens[idx], env, "span");
    md.renderer.rules.ml_math_block = (tokens, idx, options, env) =>
      `${mathHtml(tokens[idx], env, "div")}\n`;
  }

  // --- maths (M5b) -----------------------------------------------------------------------------

  const MAX_FORMULA = 10_000;  // characters in one formula
  const MAX_DEPTH = 100;  // groups {…} inside each other
  const MAX_BLOCK_LINES = 200;  // lines a displayed formula may take
  const KATEX_OPTIONS = {
    throwOnError: true,  // (caught below: the error is shown with the formula's source)
    trust: false,  // no \href, \url, \includegraphics, \htmlClass, \htmlId, \htmlStyle, \htmlData
    strict: "ignore",
    maxSize: 20,  // em: the largest size a formula may ask for (\rule, \kern, …)
    maxExpand: 500,  // macro expansions per formula (\def loops end here)
  };
  const BACKSLASH = 0x5c;
  const DOLLAR = 0x24;
  const BACKTICK = 0x60;
  const isSpace = (code) => code === 0x20 || code === 0x09 || code === 0x0a || code === 0x0d;
  const isDigit = (code) => code >= 0x30 && code <= 0x39;

  // Where a formula whose content starts at `from` ends: [index of its closing delimiter, -1]
  // or [-1, where the search stopped]. A backslash and the character after it are a pair (a
  // LaTeX command or escape, never a delimiter); a backtick stops the search.
  function findClose(src, from, end, close) {
    for (let i = from; i < end; i++) {
      const code = src.charCodeAt(i);
      if (code === BACKTICK) return [-1, i];
      if (code === BACKSLASH) {
        if (close[0] === "\\" && src.charCodeAt(i + 1) === close.charCodeAt(1)
            && i + 2 <= end) return [i, -1];
        i++;
        continue;
      }
      if (code !== DOLLAR || close[0] !== "$") continue;
      if (close === "$$") {
        if (src.charCodeAt(i + 1) === DOLLAR && i + 2 <= end) return [i, -1];
        continue;
      }
      // $…$: as in TeX, the next unescaped $ ends it; if that $ can't close (a space before
      // it, a digit after it, or "$$"), the opening one was a dollar sign: "$3, or $x$"
      const closes = !isSpace(src.charCodeAt(i - 1)) && src.charCodeAt(i + 1) !== DOLLAR
        && !isDigit(src.charCodeAt(i + 1));
      return closes ? [i, -1] : [-1, i];
    }
    return [-1, end];
  }

  // Inline: $…$, $$…$$, \(…\), \[…\] (the last two displayed) within a paragraph
  function mathInline(state, silent) {
    const { src, pos, posMax } = state;
    const code = src.charCodeAt(pos);
    let open;
    let close;
    let run = 0;
    if (code === BACKSLASH) {
      const next = src.charCodeAt(pos + 1);
      if (next === 0x28) [open, close] = ["\\(", "\\)"];
      else if (next === 0x5b) [open, close] = ["\\[", "\\]"];
      else return false;  // (an escape: markdown-it's own rule)
    } else if (code === DOLLAR) {
      while (pos + run < posMax && src.charCodeAt(pos + run) === DOLLAR) run++;
      if (run === 1 && pos + 1 < posMax && !isSpace(src.charCodeAt(pos + 1))) {
        [open, close] = ["$", "$"];
      } else if (run === 2) {
        [open, close] = ["$$", "$$"];
      }
    } else {
      return false;
    }
    const from = pos + (open ? open.length : 0);
    // A search that found no closing delimiter up to `stop` needn't be repeated for the
    // delimiters before `stop` (else a line of many "$" would take quadratic time)
    const misses = (state.mlMathMisses ||= new Map());
    const key = `${close}:${posMax}`;
    let at = -1;
    if (open && from < (misses.get(key) ?? -1)) {
      at = -1;
    } else if (open) {
      const [found, stop] = findClose(src, from, posMax, close);
      at = found;
      if (found < 0) misses.set(key, stop);
    }
    if (at < 0 || !src.slice(from, at).trim()) {
      if (code === BACKSLASH) return false;
      if (!silent) state.pending += "$".repeat(run);  // plain dollar signs
      state.pos += run;
      return true;
    }
    if (!silent) {
      const token = state.push("ml_math", "", 0);
      token.content = src.slice(from, at);
      token.markup = open;
      token.info = close;
      token.meta = { display: open !== "$" && open !== "\\(" };
    }
    state.pos = at + close.length;
    return true;
  }

  // A displayed formula on lines of its own: $$ or \[ at the start of a line, its closing
  // delimiter at the end of the same or a later line, with no blank line between
  function mathBlock(state, startLine, endLine, silent) {
    if (state.sCount[startLine] - state.blkIndent >= 4) return false;  // (indented code)
    const { src } = state;
    const start = state.bMarks[startLine] + state.tShift[startLine];
    let open;
    let close;
    if (src.startsWith("$$", start) && src.charCodeAt(start + 2) !== DOLLAR) {
      [open, close] = ["$$", "$$"];
    } else if (src.startsWith("\\[", start)) {
      [open, close] = ["\\[", "\\]"];
    } else {
      return false;
    }
    // Each line's own text (inside a quote or a list, without its "> " or indentation)
    const lines = [];
    let line = startLine;
    for (let lineFrom = start + open.length; ; ) {
      const lineEnd = state.eMarks[line];
      const [found, stop] = findClose(src, lineFrom, lineEnd, close);
      if (found >= 0) {
        if (src.slice(found + close.length, lineEnd).trim()) return false;  // text after it
        lines.push(src.slice(lineFrom, found));
        break;
      }
      if (stop < lineEnd) return false;  // a backtick
      lines.push(src.slice(lineFrom, lineEnd));
      line++;
      if (line >= endLine || line - startLine > MAX_BLOCK_LINES || state.isEmpty(line)
          || state.sCount[line] < state.blkIndent) return false;
      lineFrom = state.bMarks[line] + state.tShift[line];
    }
    const content = lines.join("\n");
    if (!content.trim()) return false;
    if (silent) return true;
    const token = state.push("ml_math_block", "", 0);
    token.block = true;
    token.content = content;
    token.markup = open;
    token.info = close;
    token.meta = { display: true };
    token.map = [startLine, line + 1];
    state.line = line + 1;
    return true;
  }

  // How deeply a formula's groups {…} are nested (\{ and \} are braces, not groups)
  function depth(source) {
    let level = 0;
    let deepest = 0;
    for (let i = 0; i < source.length; i++) {
      const code = source.charCodeAt(i);
      if (code === BACKSLASH) i++;
      else if (code === 0x7b) deepest = Math.max(deepest, ++level);
      else if (code === 0x7d) level--;
    }
    return deepest;
  }

  // A formula typeset once per text and kind (the preview is redrawn while typing)
  const typeset = new Map();
  function typesetFormula(engine, source, display) {
    const key = `${display ? "D" : "I"}${source}`;
    let result = typeset.get(key);
    if (result) return result;
    if (source.length > MAX_FORMULA) {
      result = { error: `公式太长 Too long: ${source.length} characters (at most ${MAX_FORMULA})` };
    } else if (depth(source) > MAX_DEPTH) {
      result = { error: `嵌套太深 Nested too deeply: more than ${MAX_DEPTH} levels of {…}` };
    } else {
      try {
        result = { html: engine.renderToString(source, { ...KATEX_OPTIONS, displayMode: display }) };
      } catch (error) {  // KaTeX's ParseError, or anything else (a stack overflow): this formula only
        result = { error: String(error?.message || error).slice(0, 300) };
      }
    }
    if (typeset.size >= 2_000) typeset.clear();
    typeset.set(key, result);
    return result;
  }

  function mathHtml(token, env, tag) {
    const escape = md.utils.escapeHtml;
    const { display } = token.meta;
    const written = escape(token.markup + token.content + token.info);
    const kind = `ml-math ${display ? "ml-math-display" : "ml-math-inline"}`;
    env.mlMaths = (env.mlMaths || 0) + 1;
    const engine = katex();
    if (!engine) return `<${tag} class="${kind} ml-math-source"><code>${written}</code></${tag}>`;
    const result = typesetFormula(engine, token.content, display);
    if (result.html !== undefined) return `<${tag} class="${kind}">${result.html}</${tag}>`;
    const reason = escape(`公式错误 Formula error: ${result.error}`);
    const shown = display ? `<span class="ml-math-reason">${reason}</span>` : "";
    return `<${tag} class="${kind} ml-math-error" title="${reason}"><code>${written}</code>`
      + `${shown}</${tag}>`;
  }

  const NO_MATHS = '<div class="ml-muted ml-maths-unavailable" role="note">'
    + "公式无法显示：KaTeX 没有安装或没有通过校验（uv run scripts/reader.py --setup-maths），"
    + "公式按原文显示。 <span class=\"ml-en\">Maths can't be shown: KaTeX isn't installed or"
    + " didn't pass its check (uv run scripts/reader.py --setup-maths); formulas are shown as"
    + " written.</span></div>\n";

  // The HTML for a note's text (markdown-it's own output, html: false); null without it.
  // options.image(src): the URL to load a note's image from, or null (a placeholder)
  function render(text, options = {}) {
    if (!md) return null;
    const env = { mlImage: options.image };
    const html = md.render(String(text), env);
    return env.mlMaths && !katex() ? NO_MATHS + html : html;
  }

  // One formula on its own (M5e's dialog): the same KaTeX, options and limits as the
  // preview's. {html} or {error}; without KaTeX {error} saying so
  function formulaHtml(source, display = true) {
    const engine = katex();
    if (!engine) return { error: "KaTeX isn't installed (uv run scripts/reader.py --setup-maths)" };
    return typesetFormula(engine, String(source), display);
  }

  // M5e: whether `body` followed by the closing delimiter `close` ($, $$, \) or \]) is read
  // here as one formula ending exactly there, `next` being the note's character after it (a
  // digit after "$" means it was a dollar sign). The ∑ dialog asks before writing a formula
  // into a note, so the note says what the user confirmed, read back the same way
  function closesAtEnd(body, close, next = "") {
    const text = String(body);
    const src = text + close + next;
    const [found] = findClose(src, 0, text.length + close.length, close);
    return found === text.length;
  }

  window.myLibraryPreview = {
    available: Boolean(md),
    maths: () => Boolean(katex()),
    html: render,
    formulaHtml,
    closesAtEnd,
    isWeb,
    headingId: (fragment) => `ml-h-${slug(fragment)}`,
  };
})();
