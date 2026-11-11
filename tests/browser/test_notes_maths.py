"""Maths in the notes' preview (task 4 M5b): $…$ and \\(…\\) inline, $$…$$ and \\[…\\] displayed,
typeset by KaTeX (pinned, checksum verified, served locally). Dollar amounts, escapes and code
stay text; an invalid formula shows its source and the reason and affects nothing else; hostile
formulas never run or load anything; without KaTeX the formulas are shown as written and the
preview says why. The preview only reads the session's text: the .md file and the editor keep
the source exactly. Temporary libraries only; KaTeX from the tool's cache
(reader.py --setup-maths)."""

import time
from urllib.parse import urlsplit

import pytest
import reader
from helpers import EDITOR, editor_text, leave, type_at_end, wait_save_state
from playwright.sync_api import expect
from test_notes_preview import PREVIEW, choose_view, note_path, open_rich, saves


@pytest.fixture(autouse=True)
def katex_installed():
    if not reader.katex_installed():
        pytest.fail(
            "KaTeX isn't installed (or isn't the checksum-verified one), so maths can't be "
            "tested. Install it first: uv run scripts/reader.py --setup-maths"
        )


MATHS = r"""# Maths

Inline dollars $a^2 + b^2 = c^2$ and parentheses \(\alpha + \beta = \gamma\).

Fraction $\frac{1}{2}$, root $\sqrt[3]{x}$, indices $x_i^{n+1}$.

$$
\int_0^\infty e^{-x^2}\,dx = \frac{\sqrt{\pi}}{2}
$$

\[
\sum_{k=1}^{n} k = \frac{n(n+1)}{2}
\]

$$
\begin{pmatrix} a & b \\ c & d \end{pmatrix}
$$

> $$
> \begin{aligned}
> f(x) &= (x+1)^2 \\
>      &= x^2 + 2x + 1
> \end{aligned}
> $$

Displayed in a paragraph: $$E = mc^2$$ and \[F = ma\] too.
"""
INLINE = [r"a^2 + b^2 = c^2", r"\alpha + \beta = \gamma", r"\frac{1}{2}", r"\sqrt[3]{x}",
          r"x_i^{n+1}"]  # fmt: skip
DISPLAYED = [
    r"\int_0^\infty e^{-x^2}\,dx = \frac{\sqrt{\pi}}{2}",
    r"\sum_{k=1}^{n} k = \frac{n(n+1)}{2}",
    r"\begin{pmatrix} a & b \\ c & d \end{pmatrix}",
    r"\begin{aligned} f(x) &= (x+1)^2 \\ &= x^2 + 2x + 1 \end{aligned}",
    r"E = mc^2",
    r"F = ma",
]


def sources(page, selector: str) -> list[str]:
    """The LaTeX each typeset formula was made from (KaTeX's MathML annotation), spaces evened."""
    return page.evaluate(
        "s => [...document.querySelectorAll(s)].map(a => a.textContent.split(/\\s+/)"
        ".filter(Boolean).join(' '))",
        f"{PREVIEW} {selector} annotation[encoding='application/x-tex']",
    )


def texts(page, selector: str) -> list[str]:
    """The text of each element, every formula in it shown as ⟨m⟩ (KaTeX's hidden MathML
    repeats a formula's source in textContent)."""
    return page.evaluate(
        """s => [...document.querySelectorAll(s)].map(e => {
          const copy = e.cloneNode(true);
          copy.querySelectorAll('.ml-math').forEach(m => m.replaceWith('⟨m⟩'));
          return copy.textContent;
        })""",
        f"{PREVIEW} {selector}",
    )


def katex_asset(url: str) -> bool:
    """A request for one of KaTeX's own files (its script, stylesheet and fonts), by path."""
    return urlsplit(url).path.startswith("/vendor/katex/")


def test_katex_asset_filter_is_specific():
    assert katex_asset("http://127.0.0.1:5/vendor/katex/katex.min.js")
    assert katex_asset("http://127.0.0.1:5/vendor/katex/fonts/KaTeX_Main-Regular.woff2")
    for other in ("http://127.0.0.1:5/books/a.pdf", "http://127.0.0.1:5/vendor/markdown-it/x.js",
                  "http://127.0.0.1:5/pdfjs/web/viewer.html?file=/vendor/katex/x",
                  "http://127.0.0.1:5/reader/vendor/katex/x.js"):  # fmt: skip
        assert not katex_asset(other), other


def test_formulas_in_all_four_delimiters_are_typeset(library, server_factory, reader_page):
    failed, outside, served = [], [], {}
    # Only KaTeX's own files count here: other requests may be cancelled as a matter of course
    # (PDF.js ends its first whole-file request of a book once it has what it needs)
    reader_page.on(
        "requestfailed",
        lambda r: katex_asset(r.url) and failed.append(f"{r.url} ({r.failure})"),
    )
    reader_page.on(
        "response", lambda r: r.status >= 400 and katex_asset(r.url) and failed.append(r.url)
    )
    reader_page.on(
        "response",
        lambda r: katex_asset(r.url) and served.setdefault(urlsplit(r.url).path, r.status),
    )
    reader_page.on(
        "request",
        lambda r: (
            r.url.startswith(("http://", "https://"))
            and not r.url.startswith("http://127.0.0.1")
            and outside.append(r.url)
        ),
    )
    open_rich(library, server_factory, reader_page, chapter_one=MATHS)
    choose_view(reader_page, "preview")
    preview = reader_page.locator(PREVIEW)
    expect(preview.locator("h1")).to_have_text("Maths")
    expect(preview.locator(".ml-math")).to_have_count(len(INLINE) + len(DISPLAYED))
    expect(preview.locator(".ml-math-error, .ml-math-source")).to_have_count(0)
    assert sources(reader_page, ".ml-math-inline") == INLINE
    assert sources(reader_page, ".ml-math-display") == DISPLAYED
    expect(preview.locator(".ml-math-display .katex-display")).to_have_count(len(DISPLAYED))
    expect(preview.locator(".ml-math-inline .katex-display")).to_have_count(0)
    expect(preview.locator("blockquote .ml-math-display")).to_have_count(1)  # (no "> " in it)
    expect(preview.locator(".katex .mfrac")).not_to_have_count(0)  # fractions drawn as such
    expect(preview.locator(".katex .sqrt")).not_to_have_count(0)
    expect(preview.locator(".katex .msupsub")).not_to_have_count(0)
    expect(preview.locator(".katex .mtable")).to_have_count(2)  # the matrix, the aligned lines
    expect(preview.locator(".ml-maths-unavailable")).to_have_count(0)
    reader_page.wait_for_function(  # KaTeX's own fonts, from this server
        "() => document.fonts.status === 'loaded'"
        " && document.fonts.check('16px KaTeX_Main') && document.fonts.check('16px KaTeX_Math')"
    )
    used = reader_page.evaluate(
        "() => [...document.fonts].filter(f => f.family.startsWith('KaTeX_')"
        " && f.status === 'loaded').map(f => f.family)"
    )
    assert {"KaTeX_Main", "KaTeX_Math"} <= set(used)
    assert any(family.startswith("KaTeX_Size") for family in used)  # large operators, brackets
    assert failed == [] and outside == []  # nothing missing, nothing from the network
    assert served["/vendor/katex/katex.min.js"] == 200
    assert served["/vendor/katex/katex.min.css"] == 200
    fonts = {path: status for path, status in served.items() if path.endswith(".woff2")}
    assert fonts and set(fonts.values()) == {200}, served  # every KaTeX file asked for: found


PLAIN = r"""# Not maths

Prices: $5 and $10, or $20,000 in total.

Escaped: \$x\$ and \\(y\\) and \\[z\\].

Code: `$x$` and `\(y\)`.

```text
$$E = mc^2$$ and \(x\)
```

    $$indented code$$

Unclosed: $x and \(y and $$z

Mixed: costs $3, formula $x^2$.
"""


def test_amounts_escapes_code_and_unclosed_delimiters_stay_text(
    library, server_factory, reader_page
):
    open_rich(library, server_factory, reader_page, chapter_one=PLAIN)
    choose_view(reader_page, "preview")
    preview = reader_page.locator(PREVIEW)
    expect(preview.locator(".ml-math")).to_have_count(1)  # only $x^2$
    assert texts(reader_page, "> p") == [
        "Prices: $5 and $10, or $20,000 in total.",
        r"Escaped: $x$ and \(y\) and \[z\].",
        r"Code: $x$ and \(y\).",
        "Unclosed: $x and (y and $$z",  # (\( is Markdown's escaped "(")
        "Mixed: costs $3, formula ⟨m⟩.",
    ]
    expect(preview.locator(":scope > p code")).to_have_text(["$x$", r"\(y\)"])
    expect(preview.locator("pre code")).to_have_text(
        [r"$$E = mc^2$$ and \(x\)" + "\n", "$$indented code$$\n"]
    )
    assert sources(reader_page, ".ml-math") == ["x^2"]


BROKEN = r"""# Errors

Before $\frac{1}{$ and after $x^2$ and \(\undefinedcommand\) then $y$.

$$
\begin{matrix} a & b
$$

## Still here

$$\left( x$$

The end.
"""


def test_an_invalid_formula_affects_only_itself(library, server_factory, reader_page):
    open_rich(library, server_factory, reader_page, chapter_one=BROKEN)
    choose_view(reader_page, "preview")
    preview = reader_page.locator(PREVIEW)
    errors = preview.locator(".ml-math-error")
    expect(errors).to_have_count(4)
    expect(errors.locator("code")).to_have_text([
        r"$\frac{1}{$", r"\(\undefinedcommand\)", "$$\n\\begin{matrix} a & b\n$$",
        r"$$\left( x$$",
    ])  # fmt: skip
    for n in range(4):
        assert "Formula error" in errors.nth(n).get_attribute("title")
    expect(errors.nth(2).locator(".ml-math-reason")).to_contain_text("公式错误 Formula error")
    expect(errors.nth(0).locator(".ml-math-reason")).to_have_count(0)  # inline: in its title
    assert sources(reader_page, ".ml-math") == ["x^2", "y"]  # the others are typeset
    expect(preview.locator("h2")).to_have_text("Still here")
    expect(preview.locator(":scope > p").last).to_have_text("The end.")


HOSTILE = r"""# Hostile

$\href{javascript:window.__pwned=1}{click}$ and $\url{javascript:window.__pwned=2}$

$\htmlClass{x" onclick="window.__pwned=3}{a}$ $\htmlId{mlNotePreview}{b}$
$\htmlStyle{background:url(https://example.com/s.png)}{c}$ $\htmlData{onclick=window.__pwned=4}{d}$

$\includegraphics[height=1em]{https://example.com/i.png}$

$<img src=x onerror="window.__pwned=5">$ and \(</span><script>window.__pwned=6</script>\)

$$
</div><iframe src="https://example.com/f"></iframe>
$$

$\text{<b onmouseover=window.__pwned=7>bold</b>}$ $\color{red" onclick="x}{z}$

After all that, **the note** goes on.
"""


def test_hostile_formulas_never_run_or_load_anything(library, server_factory, reader_page):
    requested = []
    reader_page.on("request", lambda r: requested.append(r.url))
    open_rich(library, server_factory, reader_page, chapter_one=HOSTILE)
    choose_view(reader_page, "preview")
    preview = reader_page.locator(PREVIEW)
    expect(preview.locator("strong")).to_have_text("the note")
    for selector in ("script", "img", "iframe", "a", "b", "[onerror]", "[onclick]",
                     "[onmouseover]", "[data-onclick]", ".x", "[style*='url(']",
                     "[href]", "[src]"):  # fmt: skip
        expect(preview.locator(selector)).to_have_count(0)
    assert reader_page.evaluate("() => document.querySelectorAll('#mlNotePreview').length") == 1
    expect(preview.locator(".ml-math")).to_have_count(12)  # each one still a formula, typeset
    reader_page.evaluate(  # a click and the mouse over every part of every formula: nothing runs
        """() => document.querySelectorAll('#mlNotePreview .ml-math, #mlNotePreview .ml-math *')
          .forEach(e => ['mouseover', 'mouseenter', 'click'].forEach(
            type => e.dispatchEvent(new MouseEvent(type, { bubbles: true }))))"""
    )
    assert reader_page.evaluate("() => window.__pwned") is None
    assert not [u for u in requested if "example.com" in u or u.endswith("/x")]


def test_huge_and_deeply_nested_formulas_never_freeze_the_preview(
    library, server_factory, reader_page
):
    deep = "$" + "{" * 4_000 + "x" + "}" * 4_000 + "$"  # (else KaTeX's own recursion runs out)
    loop = r"$\def\a{\a\a}\a$"  # endless expansion: maxExpand ends it
    long = "$" + "x+" * 6_000 + "x$"  # more than 10,000 characters
    nested = "$$" + r"\frac{" * 60 + "x" + "}{y}" * 60 + "$$"
    many = " ".join(f"$x_{{{n}}}$" for n in range(800))
    note = f"# Large\n\n{deep}\n\n{loop}\n\n{long}\n\n{nested}\n\n{many}\n\n## After\n"
    open_rich(library, server_factory, reader_page, chapter_one=note)
    started = time.monotonic()
    choose_view(reader_page, "preview")
    preview = reader_page.locator(PREVIEW)
    expect(preview.locator("h2")).to_have_text("After")
    assert time.monotonic() - started < 15  # (a generous bound: it takes well under a second)
    errors = preview.locator(".ml-math-error")
    expect(errors).to_have_count(3)
    assert "Nested too deeply" in errors.nth(0).get_attribute("title")
    assert "Too many expansions" in errors.nth(1).get_attribute("title")
    assert "Too long" in errors.nth(2).get_attribute("title")
    expect(preview.locator(".ml-math:not(.ml-math-error)")).to_have_count(801)
    choose_view(reader_page, "split")  # still answering: typing shows at once in the preview
    type_at_end(reader_page, "\nNew $z^3$ here\n")
    expect(preview.locator(":scope > p")).to_have_count(5)  # (the nested one is a block)
    assert texts(reader_page, "> p")[-1] == "New ⟨m⟩ here"
    assert sources(reader_page, ".ml-math")[-1] == "z^3"


def colours(page, selector: str) -> dict:
    """The contrast of an element's text against the preview's background, and whether the
    element's text colour is the preview's own."""
    return page.evaluate(
        """s => {
          const p = document.getElementById('mlNotePreview');
          const e = p.querySelector(s);
          const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
          const lum = ([r, g, b]) => {
            const f = (v) => {
              v /= 255;
              return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
            };
            return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
          };
          const text = getComputedStyle(e).color;
          const [a, b] = [lum(rgb(text)), lum(rgb(getComputedStyle(p).backgroundColor))]
            .sort((x, y) => y - x);
          return { contrast: (a + 0.05) / (b + 0.05), same: text === getComputedStyle(p).color };
        }""",
        selector,
    )


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_formulas_and_errors_readable_in_light_and_dark(
    library, server_factory, reader_page, scheme
):
    reader_page.emulate_media(color_scheme=scheme)
    note = "# Colours\n\nA formula $\\frac{a}{b}$, an error $\\frac{$.\n\n$$\\sum_k k^2$$\n"
    open_rich(library, server_factory, reader_page, chapter_one=note)
    choose_view(reader_page, "preview")
    expect(reader_page.locator(f"{PREVIEW} .ml-math-error")).to_have_count(1)
    for selector in (".ml-math-inline .katex", ".ml-math-display .katex", ".ml-math-error code"):
        found = colours(reader_page, selector)
        assert found["same"], selector  # the text's own colour, light or dark
        assert found["contrast"] >= 4.5, (selector, found)


def test_views_never_change_the_source(library, server_factory, reader_page):
    doc, _ = open_rich(library, server_factory, reader_page, chapter_one=MATHS)
    before = note_path(library, doc).read_bytes()
    sent = saves(reader_page)
    for name in ("preview", "split", "source", "preview", "split", "source"):
        choose_view(reader_page, name)
        assert editor_text(reader_page) == MATHS  # the editor keeps the source exactly
    reader_page.wait_for_timeout(2_000)  # longer than the autosave delay: nothing comes
    assert sent == [] and note_path(library, doc).read_bytes() == before == MATHS.encode()
    assert reader_page.evaluate("() => document.body.dataset.mlSaveState") == "clean"


def test_typed_maths_is_saved_as_typed(library, server_factory, reader_page):
    doc, _ = open_rich(library, server_factory, reader_page, chapter_one="# Typed\n")
    choose_view(reader_page, "split")
    typed = "\nEnergy $E = \\frac{1}{2} m v^2$ and\n\n$$\n\\int_a^b f\\,dx\n$$\n"
    type_at_end(reader_page, typed)
    preview = reader_page.locator(PREVIEW)
    expect(preview.locator(".ml-math .katex")).to_have_count(2)
    assert sources(reader_page, ".ml-math") == [r"E = \frac{1}{2} m v^2", r"\int_a^b f\,dx"]
    reader_page.keyboard.press("Control+s")
    wait_save_state(reader_page, "clean")
    assert note_path(library, doc).read_text("utf-8") == "# Typed\n" + typed  # byte for byte
    assert editor_text(reader_page) == "# Typed\n" + typed


def test_a_conflict_and_leaving_work_the_same_with_maths(library, server_factory, reader_page):
    doc, _ = open_rich(library, server_factory, reader_page, chapter_one=MATHS)
    choose_view(reader_page, "split")
    note_path(library, doc).write_bytes(b"# Changed elsewhere\n\n$y = 1$\n")
    type_at_end(reader_page, "mine $\\beta$")
    reader_page.keyboard.press("Control+s")
    wait_save_state(reader_page, "conflict")
    choose_view(reader_page, "preview")
    expect(reader_page.locator("#mlNoteBar")).to_be_visible()  # the decision is still offered
    expect(reader_page.locator(f"{PREVIEW} .ml-math").last).to_contain_text("β")  # the text kept
    assert leave(reader_page, "close", stay=True)  # unsaved: still warned
    assert note_path(library, doc).read_bytes() == b"# Changed elsewhere\n\n$y = 1$\n"
    reader_page.locator("#mlNoteBar").get_by_role("button", name="Keep mine").click()
    wait_save_state(reader_page, "clean")
    assert note_path(library, doc).read_text("utf-8") == MATHS + "mine $\\beta$"


KATEX_FAILURES = {
    "not loaded": None,  # missing (the server checks the files; here the browser can't get them)
    "a damaged script": "truncated",  # its own SyntaxError: KaTeX isn't defined
    "a failing renderer": (
        "window.katex = { renderToString() { throw new Error('renderer failed'); } };"
    ),
}


@pytest.mark.parametrize("failure", list(KATEX_FAILURES))
def test_without_katex_the_formulas_show_as_written(library, server_factory, page, failure):
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(f"{e.name}: {e.message}"))
    page.set_default_timeout(15_000)
    body = KATEX_FAILURES[failure]
    if body is None:
        page.route("**/vendor/katex/**", lambda route: route.abort())
    else:
        if body == "truncated":
            body = (reader.KATEX / "katex.min.js").read_text(encoding="utf-8")[:2_000]
        script = body
        page.route(
            "**/vendor/katex/katex.min.js",
            lambda route: route.fulfill(body=script, content_type="text/javascript"),
        )
    doc, _ = open_rich(library, server_factory, page, chapter_one=MATHS)
    choose_view(page, "preview")
    preview = page.locator(PREVIEW)
    expect(preview.locator("h1")).to_have_text("Maths")  # the rest of the note as always
    expect(preview.locator(".ml-math")).to_have_count(len(INLINE) + len(DISPLAYED))
    expect(preview.locator(".katex")).to_have_count(0)
    if failure == "a failing renderer":  # KaTeX is there, but fails: each formula says so
        expect(preview.locator(".ml-math-error")).to_have_count(len(INLINE) + len(DISPLAYED))
        assert "renderer failed" in preview.locator(".ml-math-error").first.get_attribute("title")
        expect(preview.locator(".ml-maths-unavailable")).to_have_count(0)
    else:  # no KaTeX: shown as written, and why
        expect(preview.locator(".ml-maths-unavailable")).to_contain_text("--setup-maths")
        expect(preview.locator(".ml-maths-unavailable")).to_contain_text("Maths can't be shown")
        expect(preview.locator(".ml-math-source code").first).to_have_text("$a^2 + b^2 = c^2$")
        expect(preview.locator(".ml-math-source code").nth(1)).to_have_text(
            r"\(\alpha + \beta = \gamma\)"
        )
    choose_view(page, "source")  # editing and saving as always
    assert editor_text(page) == MATHS
    type_at_end(page, "still saved $x$")
    page.keyboard.press("Control+s")
    wait_save_state(page, "clean")
    assert note_path(library, doc).read_text("utf-8") == MATHS + "still saved $x$"
    expect(page.locator(EDITOR)).to_be_visible()
    if failure == "a damaged script":  # only KaTeX's own, as it loads; nothing from the notes
        assert len(errors) == 1 and errors[0].startswith("SyntaxError"), errors
    else:
        assert errors == []
