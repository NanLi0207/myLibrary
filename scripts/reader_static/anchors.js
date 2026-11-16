// Text anchors (task 4 M6; M7 finds the passages again): pure functions, no page access, so
// the same rules apply when a passage is quoted and when it is looked for again.
//
// - normalize(): the page text as anchors compare it. NFKC (the ligature "ﬁ" becomes "fi",
//   compatibility forms their plain letters), soft hyphens dropped, a hyphen at a line end
//   between letters joined ("illumi-\nnation" -> "illumination"), every run of whitespace one
//   space. `map` leads each character back to the source text (the text layer's), so offsets
//   and the selection can be translated both ways. Applied one code point at a time (a base
//   letter and a separate combining accent stay two characters): the same on both sides.
// - NORMALIZE is the version of these rules, stored with every anchor: change the rules, raise it.
// - excerpt(), quoteMarkdown(), pageMarkdown(), sourceUrl(): what goes into the note. The
//   visible quote is short (about 15 words, decision 1 of 2026-11-07); the whole selection is
//   only in the library's private references file.
(() => {
  "use strict";
  const NORMALIZE = 1;
  const LETTER = /[\p{L}\p{N}]/u;
  const SPACE = /\s/u;
  const HYPHENS = new Set(["-", "\u2010"]);

  function normalize(source) {
    const out = [];
    const map = [];
    const push = (chars, origin) => {
      for (const c of chars) {
        for (let k = 0; k < c.length; k++) {
          out.push(c[k]);
          map.push(origin);
        }
      }
    };
    const last = () => out[out.length - 1];
    let i = 0;
    while (i < source.length) {
      const point = source.codePointAt(i);
      const ch = String.fromCodePoint(point);
      const next = i + ch.length;
      if (ch === "\u00AD") {  // a soft hyphen: never part of the word
        i = next;
        continue;
      }
      if (HYPHENS.has(ch) && out.length && LETTER.test(last())) {
        let j = next;
        while (j < source.length && SPACE.test(source[j])) j++;
        if (source.slice(next, j).includes("\n") && j < source.length && LETTER.test(source[j])) {
          i = j;  // a word broken at the end of a line: joined
          continue;
        }
      }
      const plain = ch.normalize("NFKC");
      if (!plain || SPACE.test(plain)) {
        if (out.length && last() !== " ") push(" ", i);
        else if (!out.length) push(" ", i);
        i = next;
        continue;
      }
      push(plain, i);
      i = next;
    }
    map.push(source.length);
    return { text: out.join(""), map };
  }

  // The normalised offset of a source offset: the first normalised character that comes from
  // it or after it
  function toNormalized(map, offset) {
    let lo = 0;
    let hi = map.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (map[mid] < offset) lo = mid + 1;
      else hi = mid;
    }
    return lo;
  }

  const collapse = (s) => String(s).replace(/\s+/gu, " ").trim();

  // Cut at a character boundary (never half a surrogate pair)
  function cut(s, max) {
    const chars = Array.from(s);
    return chars.length > max ? chars.slice(0, max).join("") : s;
  }

  // About `words` words (or `chars` characters, for text without spaces such as Chinese),
  // then "…" when anything was left out
  function excerpt(s, words = 15, chars = 100) {
    const all = collapse(s).split(" ").filter(Boolean);
    let shown = all.slice(0, words).join(" ");
    let shortened = all.length > words;
    if (Array.from(shown).length > chars) {
      shown = cut(shown, chars).trimEnd();
      shortened = true;
    }
    return shortened ? `${shown} …` : shown;
  }

  // Book text as plain Markdown that shows as it reads: what Markdown or the preview's maths
  // would take as markup is escaped (a backslash before ASCII punctuation is CommonMark's)
  function escapeMarkdown(s) {
    let t = collapse(s).replace(/[\\`*_[\]<>$|~]/g, "\\$&").replace(/&(?=#?\w+;)/g, "\\&");
    t = t.replace(/^([#+\-=]|\d+(?=[.)]))/, (m) => (/^\d/.test(m) ? `${m}\\` : `\\${m}`));
    return t;
  }

  // A link destination may not hold spaces or unbalanced parentheses
  const encode = (s) => encodeURIComponent(s).replace(/[()'!*]/g,
    (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`);

  // /read/<document id>?page=N&ref=<rid>[&q=…]: N counts from 1, as everywhere in the reader;
  // q is the start of the quote, for when the references file is gone. The port isn't the
  // reference's identity: any host with /read/<id> is the same link
  function sourceUrl(origin, docId, page, rid, quote = "") {
    const q = cut(collapse(quote), 60);
    return `${origin}/read/${encode(docId)}?page=${page}&ref=${encode(rid)}${q ? `&q=${encode(q)}` : ""}`;
  }

  function quoteMarkdown(quote, page, url) {
    return `> ${escapeMarkdown(excerpt(quote))}\n> — [p. ${page}](${url})`;
  }

  function pageMarkdown(page, url) {
    return `[p. ${page}](${url})`;
  }

  window.myLibraryAnchors = Object.freeze({
    NORMALIZE, normalize, toNormalized, excerpt, escapeMarkdown, sourceUrl, quoteMarkdown,
    pageMarkdown,
  });
})();
