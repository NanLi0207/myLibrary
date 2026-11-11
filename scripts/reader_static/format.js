// Markdown formatting for the notes (task 4 M5c): what the toolbar and Ctrl+B / Ctrl+I do to
// the note's Markdown source. Only text in, text out: apply(value, start, end, action) returns
// one replacement { from, to, text } and the selection to set afterwards { selStart, selEnd }
// (positions in the new value), or null when there's nothing to do. notes.js makes it one
// insertText, so the browser's own Undo reverts one action, and the change reaches the note's
// session like typing (autosave, drafts, conflicts). Nothing here touches the page.
//
// Every action is a toggle where practical: applied again to its own result, it is undone.
// - inline (bold, italic, strike, code, inline maths): around the selection, or its lines;
// - line prefixes (heading 0–6, bullets, numbers, tasks, quote): every line the selection
//   touches;
// - blocks (fenced code, displayed maths): around those lines;
// - link and image: around the selection; a selected link or image is turned back into text;
// - table: a small empty table, on lines of its own.
(() => {
  "use strict";

  const result = (from, to, text, selStart, selEnd = selStart) => ({ from, to, text, selStart, selEnd });

  // The whole lines a selection touches: [from, to) (a selection ending just after a line
  // break doesn't take the next line)
  function lineRange(value, start, end) {
    const from = value.lastIndexOf("\n", start - 1) + 1;
    const last = end > start && value[end - 1] === "\n" ? end - 1 : end;
    let to = value.indexOf("\n", last);
    if (to === -1) to = value.length;
    return [from, to];
  }

  // --- inline: **bold**, *italic*, ~~strike~~, `code`, $maths$ -------------------------------

  const INLINE = {
    bold: { ch: "*", size: 2, has: (n) => n >= 2 },
    italic: { ch: "*", size: 1, has: (n) => n % 2 === 1 },  // * or *** (bold and italic)
    strike: { ch: "~", size: 2, has: (n) => n >= 2 },
    code: { ch: "`", size: 1, has: (n) => n >= 1 },
    math: { ch: "$", size: 1, has: (n) => n === 1 },
  };

  const run = (s, at, step, ch) => {
    let n = 0;
    while (s[at + step * n] === ch) n++;
    return n;
  };

  // A span (no line break) wrapped or unwrapped: its new text, and where its content now is
  function toggleSpan(span, kind, outside) {
    const { ch, size, has } = INLINE[kind];
    // Markers inside the selection: "**bold**" selected
    const lead = run(span, 0, 1, ch);
    const trail = run(span, span.length - 1, -1, ch);
    const inner = Math.min(lead, trail);
    if (span.length > 2 * size && lead < span.length && has(inner)) {
      const cut = kind === "code" ? inner : size;
      let content = span.slice(cut, span.length - cut);
      if (kind === "code" && cut > 1 && content.startsWith(" ") && content.endsWith(" ")) {
        content = content.slice(1, -1);
      }
      return { text: content, from: 0, to: content.length, removed: true };
    }
    if (outside && has(outside.count)) return { unwrapOutside: kind === "code" ? outside.count : size };
    let marker = ch.repeat(size);
    let pad = "";
    if (kind === "code" && span.includes("`")) {  // a backtick inside: a longer fence
      let longest = 0;
      for (const m of span.match(/`+/g)) longest = Math.max(longest, m.length);
      marker = "`".repeat(longest + 1);
      pad = " ";
    }
    const text = marker + pad + span + pad + marker;
    return { text, from: marker.length + pad.length, to: marker.length + pad.length + span.length };
  }

  function inline(value, start, end, kind) {
    const { ch } = INLINE[kind];
    let s = start;
    let e = end;
    if (value.slice(s, e).includes("\n")) return inlineLines(value, start, end, kind);
    while (s < e && /\s/.test(value[s])) s++;  // "word " selected: the word only
    while (e > s && /\s/.test(value[e - 1])) e--;
    // `` x`y ``: a code span with a backtick inside has its content padded with a space
    if (kind === "code" && value[s - 1] === " " && value[e] === " ") {
      const fence = Math.min(run(value, s - 2, -1, ch), run(value, e + 1, 1, ch));
      if (fence >= 2) return result(s - 1 - fence, e + 1 + fence, value.slice(s, e), s - 1 - fence, e - 1 - fence);
    }
    const before = run(value, s - 1, -1, ch);
    const after = run(value, e, 1, ch);
    const changed = toggleSpan(value.slice(s, e), kind, { count: Math.min(before, after) });
    if (changed.unwrapOutside) {  // the markers are just outside the selection: removed
      const cut = changed.unwrapOutside;
      return result(s - cut, e + cut, value.slice(s, e), s - cut, e - cut);
    }
    return result(s, e, changed.text, s + changed.from, s + changed.to);
  }

  // Several lines: each non-blank line's text (its list or quote marker left alone) wrapped,
  // or, when every one already is, unwrapped
  function inlineLines(value, start, end, kind) {
    const PREFIX = /^(\s*(?:>\s?)*(?:[-*+]\s+(?:\[[ xX]\]\s+)?|\d+[.)]\s+|#{1,6}\s+)?)(.*?)(\s*)$/;
    const lines = value.slice(start, end).split("\n");
    const parts = lines.map((line) => line.match(PREFIX));
    const filled = parts.filter((p) => p[2]);
    if (!filled.length) return null;
    const removing = filled.every((p) => toggleSpan(p[2], kind).removed);
    const text = parts.map((p) => {
      if (!p[2]) return p[0];
      const changed = toggleSpan(p[2], kind);
      return p[1] + (Boolean(changed.removed) === removing ? changed.text : p[2]) + p[3];
    }).join("\n");
    return result(start, end, text, start, start + text.length);
  }

  // --- line prefixes: headings, lists, tasks, quotes -----------------------------------------

  const BULLET = /^(\s*)[-*+]\s+(?!\[[ xX]\]\s)/;
  const NUMBER = /^(\s*)\d+[.)]\s+/;
  const TASK = /^(\s*)[-*+]\s+\[[ xX]\]\s+/;
  const ANY_ITEM = /^(\s*)(?:[-*+]\s+(?:\[[ xX]\]\s+)?|\d+[.)]\s+)/;
  const HEADING = /^\s{0,3}(#{1,6})(?:\s+|$)/;
  const QUOTE = /^(\s*)> ?/;

  // Each line: [the part of it replaced (its old prefix), the new prefix]; the rest stays
  function linePrefixes(lines, action, level) {
    const filled = lines.filter((line) => line.trim());
    if (!filled.length && action !== "quote") return null;
    const all = (re, test = (m) => m) => filled.length > 0 && filled.every((line) => {
      const m = line.match(re);
      return Boolean(m && test(m));
    });
    // Already so on every line: the action takes it off again
    const off = action === "heading" ? level === 0 || all(HEADING, (h) => h[1].length === level)
      : action === "quote" ? all(QUOTE)
        : all({ bullet: BULLET, number: NUMBER, task: TASK }[action]);
    let number = 0;
    return lines.map((line) => {
      const blank = !line.trim();
      if (action === "heading") {
        const m = line.match(HEADING);
        const old = m ? m[0] : (line.match(/^\s*/)[0]);
        if (blank) return [0, ""];
        return [old.length, off ? "" : `${"#".repeat(level)} `];
      }
      if (action === "quote") {
        if (off) return [(line.match(QUOTE) || [""])[0].length, ""];
        if (blank) return lines.length > 1 ? [line.length, ">"] : [0, "> "];
        return [0, "> "];
      }
      if (blank) return [0, ""];
      const item = line.match(ANY_ITEM);
      const indent = line.match(/^\s*/)[0];
      const old = item ? item[0] : indent;
      if (off) return [old.length, indent];  // back to plain lines
      number += 1;
      const marker = action === "bullet" ? "- " : action === "task" ? "- [ ] " : `${number}. `;
      return [old.length, indent + marker];
    });
  }

  function prefixes(value, start, end, action, level) {
    const [from, to] = lineRange(value, start, end);
    const lines = value.slice(from, to).split("\n");
    const plan = linePrefixes(lines, action, level);
    if (!plan) return null;
    const newLines = lines.map((line, i) => plan[i][1] + line.slice(plan[i][0]));
    const text = newLines.join("\n");
    // The selection moves with the text it was on (a prefix added before it shifts it)
    const map = (pos) => {
      let oldAt = from;
      let newAt = from;
      for (let i = 0; i < lines.length; i++) {
        if (pos <= oldAt + lines[i].length) {
          const inLine = pos - oldAt;
          const [cut, prefix] = plan[i];
          // A selection from a line's start keeps the new marker in it; a caret goes after it
          if (inLine === 0 && start !== end) return newAt;
          if (inLine <= cut) return newAt + prefix.length;
          return newAt + inLine - cut + prefix.length;
        }
        oldAt += lines[i].length + 1;
        newAt += newLines[i].length + 1;
      }
      return from + text.length;
    };
    const selStart = map(start);
    const selEnd = start === end ? selStart : map(end);
    return result(from, to, text, selStart, selEnd);
  }

  // --- blocks: ```code``` and $$maths$$ ------------------------------------------------------

  function block(value, start, end, fence) {
    const [from, to] = lineRange(value, start, end);
    const lines = value.slice(from, to).split("\n");
    const first = lines[0].trim();
    const last = lines[lines.length - 1].trim();
    const opens = fence === "```" ? first.startsWith("```") : first === "$$";
    if (lines.length >= 2 && opens && last === fence) {  // the selection is such a block: unwrap
      const text = lines.slice(1, -1).join("\n");
      return result(from, to, text, from, from + text.length);
    }
    // The lines inside such a block (its fences just above and below them): unwrapped too
    if (from > 0 && to < value.length) {
      const above = value.lastIndexOf("\n", from - 2) + 1;
      let below = value.indexOf("\n", to + 1);
      if (below === -1) below = value.length;
      const opening = value.slice(above, from - 1).trim();
      const closing = value.slice(to + 1, below).trim();
      if ((fence === "```" ? opening.startsWith("```") : opening === "$$") && closing === fence) {
        const text = value.slice(from, to);
        return result(above, below, text, start - (from - above), end - (from - above));
      }
    }
    const content = lines.join("\n");
    const text = `${fence}\n${content}\n${fence}`;
    const inner = from + fence.length + 1;
    if (!content.trim()) return result(from, to, text, inner);  // an empty block: caret inside
    return result(from, to, text, inner, inner + content.length);
  }

  // --- links and images ------------------------------------------------------------------------

  function link(value, start, end, image) {
    const selected = value.slice(start, end);
    const bang = image ? "!" : "";
    const existing = selected.match(image ? /^!\[([^\]\n]*)\]\(([^)\n]*)\)$/ : /^\[([^\]\n]*)\]\(([^)\n]*)\)$/);
    if (existing) return result(start, end, existing[1], start, start + existing[1].length);
    if (selected.includes("\n")) return null;
    // The target of a link (or image) selected, as the button leaves it: back to its text
    if (value.slice(start - 2, start) === "](" && value[end] === ")") {
      const open = value.lastIndexOf("[", start - 2);
      const label = value.slice(open + 1, start - 2);
      const isImage = value[open - 1] === "!";
      if (open >= 0 && isImage === image && !/[\]\n]/.test(label)) {
        const from = isImage ? open - 1 : open;
        return result(from, end + 1, label, from, from + label.length);
      }
    }
    if (/^https?:\/\/\S+$/.test(selected)) {  // a web address selected: it becomes the target
      const text = `${bang}[](${selected})`;
      return result(start, end, text, start + bang.length + 1);
    }
    const target = image ? "image.png" : "https://";
    const text = `${bang}[${selected}](${target})`;
    const at = start + bang.length + selected.length + 3;
    return result(start, end, text, at, at + target.length);  // the target, ready to type over
  }

  // --- a table -----------------------------------------------------------------------------------

  function table(value, start, end) {
    const selected = value.slice(start, end);
    if (selected.includes("\n")) return null;
    const lineStart = value.lastIndexOf("\n", start - 1) + 1;
    let lineEnd = value.indexOf("\n", end);
    if (lineEnd === -1) lineEnd = value.length;
    const before = value.slice(lineStart, start);
    const after = value.slice(end, lineEnd);
    // On lines of its own, after a blank line (a table can't start inside a paragraph)
    const previous = value.slice(0, lineStart).replace(/\n$/, "");
    const previousLine = previous.slice(previous.lastIndexOf("\n") + 1);
    let next = value.indexOf("\n", lineEnd + 1);
    if (next === -1) next = value.length;
    const nextLine = lineEnd < value.length ? value.slice(lineEnd + 1, next) : "";
    const lead = before.trim() ? "\n\n" : lineStart > 0 && previousLine.trim() ? "\n" : "";
    const tail = after.trim() ? "\n\n" : nextLine.trim() ? "\n" : "";
    const cell = selected.trim() || " ";
    const body = `| ${cell} |   |\n| --- | --- |\n|   |   |`;
    const text = `${lead}${body}${tail}`;
    const at = start + lead.length + 2;
    return result(start, end, text, at, at + (selected.trim() ? cell.length : 0));
  }

  // --- the actions ---------------------------------------------------------------------------

  const ACTIONS = {
    bold: (v, s, e) => inline(v, s, e, "bold"),
    italic: (v, s, e) => inline(v, s, e, "italic"),
    strike: (v, s, e) => inline(v, s, e, "strike"),
    code: (v, s, e) => inline(v, s, e, "code"),
    math: (v, s, e) => inline(v, s, e, "math"),
    bullet: (v, s, e) => prefixes(v, s, e, "bullet"),
    number: (v, s, e) => prefixes(v, s, e, "number"),
    task: (v, s, e) => prefixes(v, s, e, "task"),
    quote: (v, s, e) => prefixes(v, s, e, "quote"),
    codeblock: (v, s, e) => block(v, s, e, "```"),
    mathblock: (v, s, e) => block(v, s, e, "$$"),
    link: (v, s, e) => link(v, s, e, false),
    image: (v, s, e) => link(v, s, e, true),
    table,
  };
  for (let level = 0; level <= 6; level++) {
    ACTIONS[`h${level}`] = (v, s, e) => prefixes(v, s, e, "heading", level);
  }

  function apply(value, start, end, action) {
    const act = ACTIONS[action];
    if (!act) throw new Error(`unknown formatting action: ${action}`);
    const s = Math.max(0, Math.min(start, end, value.length));
    const e = Math.min(value.length, Math.max(start, end));
    return act(String(value), s, e);
  }

  window.myLibraryFormat = { apply, actions: Object.keys(ACTIONS) };
})();
