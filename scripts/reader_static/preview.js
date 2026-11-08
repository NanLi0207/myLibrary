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
// - images aren't loaded (pasted images are M5d): shown as their description, no request made;
// - heading ids are prefixed (ml-h-…), so they can never collide with PDF.js's own ids.
// Without markdown-it (not set up: reader.py --setup-preview) `available` is false and notes.js
// shows the plain text instead.
(() => {
  "use strict";
  const create = window.markdownit;
  const md = typeof create === "function"
    ? create({ html: false, linkify: false, typographer: false, breaks: false })
    : null;

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
      return `<span class="ml-image-placeholder" title="${escape(src)}">`
        + `图片 Image: ${escape(alt || src)}</span>`;
    };
  }

  window.myLibraryPreview = {
    available: Boolean(md),
    // The HTML for a note's text (markdown-it's own output, html: false); null without it
    html: (text) => (md ? md.render(String(text)) : null),
    isWeb,
    headingId: (fragment) => `ml-h-${slug(fragment)}`,
  };
})();
