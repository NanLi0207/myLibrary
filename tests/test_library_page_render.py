"""M7.1 S1c (FA-02): what the library page embeds is data, never markup or script.

library_page.render puts the catalog, the shelf labels, the degree labels and the server's
API data (with the library's name) into <script> elements. A name such as
"</script><script>…" used to end the element and run (the audit's reproduction). Each value
must decode to exactly the original text, and a marker's text inside a value must never be
substituted. No library is read: the page's data sources are replaced with synthetic values."""

import json
import re

import library_page
import pytest

AUDIT = "</script><script>window.__fa02=731</script>"
HOSTILE = [
    AUDIT,
    "</ScRiPt ><img src=x onerror=window.__fa02=1>",
    "<!--<script>",
    "]]></script><!--",
    "quotes \" and ' and back\\slash \\u003c",
    "Tom & Jerry <b>bold</b> &amp; &lt;",
    "光学 Optics · Ωμέγα · 書庫",
    "line\u2028separator\u2029paragraph",
    "__API__ __DATA__ __SHELF_LABELS__ __DEGREE_LABELS__",
    "  spaces  and\ttab\nnewline ",
]


def api_with(label: str) -> dict:
    return {"token": "a-token", "library": {"mode": "personal", "label": label, "key": "k",
                                            "path": "C:/x"}}  # fmt: skip


@pytest.fixture
def page_data(monkeypatch):
    """Synthetic books and shelf labels for the page ({"books": [...], "shelves": {...}})."""
    data = {"books": [], "shelves": {}}
    monkeypatch.setattr(library_page, "books", lambda pdf_base=None: data["books"])
    monkeypatch.setattr(library_page, "shelf_labels", lambda: data["shelves"])
    return data


def embedded(html: str, prefix: str) -> tuple[object, str]:
    """(the value after `prefix` decoded, the text it was embedded as)."""
    start = html.index(prefix) + len(prefix)
    value, end = json.JSONDecoder().raw_decode(html, start)
    return value, html[start:end]


def embedded_data(html: str) -> tuple[object, str]:
    opening = '<script type="application/json" id="data">'
    start = html.index(opening) + len(opening)
    text = html[start : html.index("</script>", start)]
    return json.loads(text), text


def scripts_in(html: str) -> int:
    return len(re.findall(r"<script", html, re.IGNORECASE))


def safe_in_a_script(text: str) -> bool:
    """Nothing the HTML parser acts on inside a script element: no tag start at all."""
    return "<" not in text and "\u2028" not in text and "\u2029" not in text


def test_the_audit_payload_never_ends_the_script(page_data):
    plain = library_page.render(api_with("My library"))
    html = library_page.render(api_with(AUDIT))
    assert "<script>window.__fa02" not in html
    assert scripts_in(html) == scripts_in(plain)  # (no element added)
    value, text = embedded(html, "const API = ")
    assert value["library"]["label"] == AUDIT and safe_in_a_script(text)


@pytest.mark.parametrize("hostile", HOSTILE)
def test_every_embedded_value_decodes_exactly_and_stays_data(page_data, hostile):
    page_data["books"] = [{"id": "x", "title": hostile, "shelves": [hostile], "authors": hostile}]
    page_data["shelves"] = {hostile: hostile, "Optics": "光学 Optics"}
    plain = library_page.render(api_with("My library"))
    html = library_page.render(api_with(hostile))
    assert scripts_in(html) == scripts_in(plain)
    api, api_text = embedded(html, "const API = ")
    labels, labels_text = embedded(html, "const SHELF_LABELS = ")
    books, books_text = embedded_data(html)
    assert api == api_with(hostile)
    assert labels == page_data["shelves"] and books == page_data["books"]
    for text in (api_text, labels_text, books_text):
        assert safe_in_a_script(text)


def test_a_markers_text_in_a_value_is_never_substituted(page_data):
    marker = "__API__ __DATA__ __SHELF_LABELS__ __DEGREE_LABELS__"
    page_data["books"] = [{"id": "x", "title": marker}]
    page_data["shelves"] = {"S": marker}
    html = library_page.render(api_with(marker))
    assert embedded(html, "const API = ")[0]["library"]["label"] == marker
    assert embedded(html, "const SHELF_LABELS = ")[0] == {"S": marker}
    assert embedded_data(html)[0][0]["title"] == marker
    assert html.count("a-token") == 1  # (the API data went in once, where it belongs)


def test_the_static_copy_has_no_api_and_the_degree_labels(page_data):
    html = library_page.render()
    assert "const API = null;" in html
    degrees, _ = embedded(html, "const DEGREE_LABELS = ")
    assert degrees == library_page.thesis_meta.DEGREE_LABELS


@pytest.mark.parametrize("value", [None, True, 0, 1.5, "", "plain", [1, "<"], {"a": "&"}])
def test_script_json_decodes_to_the_same_value(value):
    text = library_page.script_json(value)
    assert json.loads(text) == value and "<" not in text and "&" not in text
