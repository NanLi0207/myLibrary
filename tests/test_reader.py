import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import library_page
import library_server
import pytest
import reader
from testlib import id_of, put

ECDICT_SAMPLE = """\
word,phonetic,definition,translation,pos,collins,oxford,tag,bnc,frq,exchange,detail,audio
aberration,æbə'reɪʃən,,n. 偏差\\n[化] 像差,,,,,0,0,s:aberrations,,
aberrations,,,n. 偏差( aberration的复数形式 ),,,,,0,0,0:aberration/1:s,,
pupil,'pju:pl,,"n. 学生, 瞳孔",,,,,0,0,s:pupils,,
entrance,'entrəns,,n. 入口,,,,,0,0,,,
stop,stɒp,,n. 停止,,,,,0,0,s:stops,,
"""

GLOSSARY = """term,zh,note,definition
aberration,像差,,
pupil,光瞳,不是“学生”,孔径光阑的像。
entrance pupil,入瞳,,
"""


@pytest.fixture
def dictionary(tmp_path, monkeypatch):
    """A five-word ECDICT and a three-term optics glossary in a temporary folder."""
    csv_path = tmp_path / "ecdict.csv"
    csv_path.write_text(ECDICT_SAMPLE, encoding="utf-8")
    db = tmp_path / ".cache" / "reader" / "ecdict.db"
    db.parent.mkdir(parents=True)
    assert reader.build_dictionary(csv_path, db) == 5
    glossary = tmp_path / "glossaries" / "optics.csv"
    glossary.parent.mkdir()
    glossary.write_text(GLOSSARY, encoding="utf-8")
    monkeypatch.setattr(reader, "LIBRARY", tmp_path)
    monkeypatch.setattr(reader, "DICT_DB", db)
    monkeypatch.setattr(reader, "GLOSSARIES", glossary.parent)
    monkeypatch.setattr(reader, "GLOSSARY_CONFIG", glossary.parent / "glossaries.toml")
    monkeypatch.setattr(reader, "_glossary_cache", None)
    monkeypatch.setattr(reader, "_glossary_words_cache", None)
    monkeypatch.setattr(reader, "_glossary_index_cache", None)
    reader._lemma.cache_clear()
    yield tmp_path
    reader._lemma.cache_clear()


def test_plural_shows_base_word_with_optics_meaning_first(dictionary):
    info = reader.lookup("aberrations,")
    assert [g["zh"] for g in info["glossary"]] == ["像差"]
    entry = info["entries"][0]
    assert entry["word"] == "aberration" and entry["from"] == "aberrations"
    assert "像差" in entry["translation"] and "\n" in entry["translation"]


def test_longer_glossary_term_found_in_context(dictionary):
    info = reader.lookup("pupils", "light enters the entrance pupils here")
    assert [g["term"] for g in info["glossary"]] == ["entrance pupil", "pupil"]
    # Without that context only the word itself matches
    alone = reader.lookup("pupil")["glossary"]
    assert [g["term"] for g in alone] == ["pupil"]
    assert alone[0]["definition"] == "孔径光阑的像。" and alone[0]["note"] == "不是“学生”"


def test_unknown_word(dictionary):
    info = reader.lookup("zzzz")
    assert info["glossary"] == [] and info["entries"] == []


def test_save_word_once(dictionary):
    doc = put(dictionary / "catalog.csv", {"slug": "a-book", "title": "A Book"})
    first = reader.save_word(doc, "A Book", "pupils", "the entrance pupil", 12)
    again = reader.save_word(doc, "A Book", "pupil", "", 40)
    assert first["saved"] is True and again["saved"] is False
    vocab = (dictionary / "notes" / "a-book" / "vocabulary.md").read_text(encoding="utf-8")
    assert vocab.startswith("# Vocabulary: A Book")
    # The word's own optics meaning (光瞳), not that of the phrase around it (入瞳)
    assert "| pupil | 'pju:pl | 光瞳 | 12 |" in vocab
    assert vocab.count("| pupil |") == 1


def test_save_phrase_uses_glossary_term(dictionary):
    doc = put(dictionary / "catalog.csv", {"slug": "a-book", "title": "A Book"})
    reader.save_word(doc, "A Book", "Entrance  Pupil", "", None)
    vocab = (dictionary / "notes" / "a-book" / "vocabulary.md").read_text(encoding="utf-8")
    assert "| entrance pupil |  | 入瞳 |  |" in vocab


def test_static_files_stay_inside_their_folders(tmp_path, monkeypatch):
    (tmp_path / "pdfjs" / "web").mkdir(parents=True)
    (tmp_path / "pdfjs" / "web" / "viewer.mjs").write_text("// js", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("no", encoding="utf-8")
    monkeypatch.setattr(reader, "PDFJS", tmp_path / "pdfjs")
    body, kind = reader.static_file("/pdfjs/web/viewer.mjs")
    assert body == b"// js" and kind.startswith("text/javascript")
    assert reader.static_file("/pdfjs/../secret.txt") is None
    assert reader.static_file("/pdfjs/web/missing.js") is None
    assert reader.static_file("/reader/lookup.js") is not None  # the real popup script


def test_viewer_gets_popup_and_token(tmp_path, monkeypatch):
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "viewer.html").write_text(
        "﻿<html><head><title>v</title></head><body></body></html>", encoding="utf-8"
    )
    monkeypatch.setattr(reader, "PDFJS", tmp_path)
    html = reader.viewer_html("tok123").decode()
    assert '/reader/lookup.js"' in html and "'tok123'" in html
    assert html.index("lookup.js") < html.index("</head>")
    # the notes panel: after lookup.js, whose helpers it uses (both deferred: run in order)
    assert '/reader/notes.css"' in html
    assert html.index("lookup.js") < html.index("/reader/notes.js") < html.index("</head>")
    assert reader.static_file("/reader/notes.js") and reader.static_file("/reader/notes.css")


def test_http_lookup_and_save(dictionary, monkeypatch):
    for module in (library_server, library_page):
        monkeypatch.setattr(module, "LIBRARY", dictionary)
        monkeypatch.setattr(module, "CATALOG", dictionary / "catalog.csv")
    doc = put(
        dictionary / "catalog.csv",
        {"slug": "doe-2015-optics", "title": "Optics", "file": "books/doe-2015-optics.pdf"},
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"

    def post(path, body, token=library_server.TOKEN):
        request = urllib.request.Request(
            base + path,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "X-Library-Token": token},
            method="POST",
        )
        return json.load(urllib.request.urlopen(request, timeout=5))

    try:
        with pytest.raises(urllib.error.HTTPError) as denied:
            post("/api/lookup", {"text": "pupil"}, token="wrong")
        assert denied.value.code == 403
        assert post("/api/lookup", {"text": "pupil"})["glossary"][0]["zh"] == "光瞳"
        saved = post("/api/save-word", {"id": doc, "text": "stop", "page": 3})
        assert saved == {
            "word": "stop",
            "saved": True,
            "file": "notes/doe-2015-optics/vocabulary.md",
        }
        with pytest.raises(urllib.error.HTTPError) as unknown:
            post("/api/save-word", {"id": "../x", "text": "stop"})
        assert unknown.value.code == 404
        with pytest.raises(urllib.error.HTTPError) as by_name:  # a name is no identity any more
            post("/api/save-word", {"id": "doe-2015-optics", "text": "stop"})
        assert by_name.value.code == 404
    finally:
        server.shutdown()


def test_terms_inside_a_longer_selection(dictionary):
    info = reader.lookup("the entrance pupils of a stop")
    assert [g["term"] for g in info["glossary"]] == ["entrance pupil"]
    assert info["in_glossary"] is False
    # Words the glossary term already explains aren't listed again; stop words are skipped
    assert [w["word"] for w in info["words"]] == ["stop"]
    assert info["words"][0]["translation"] == "n. 停止"
    # A selection that is itself a term doesn't list its parts
    info = reader.lookup("entrance pupil")
    assert info["in_glossary"] is True and [g["term"] for g in info["glossary"]] == [
        "entrance pupil"
    ]
    assert info["words"] == []


def test_unknown_phrase_word_by_word(dictionary):
    info = reader.lookup("stopped aberrations zzz")
    assert info["glossary"] == [g for g in info["glossary"] if g["term"] == "aberration"]
    words = {w["word"]: w for w in info["words"]}
    assert set(words) == {"stopped", "zzz"}  # "aberrations" is explained by the glossary
    assert words["stopped"]["translation"] == "n. 停止" and words["zzz"]["translation"] == ""


def test_add_glossary_term(dictionary):
    added = reader.add_glossary_term("  Veiling glare ", "杂光", "像面上均匀的杂光背景, 降低对比度")
    assert added["term"] == "Veiling glare"
    info = reader.lookup("veiling glare")
    assert info["in_glossary"] is True
    assert info["glossary"][0]["definition"] == "像面上均匀的杂光背景, 降低对比度"  # comma kept
    with pytest.raises(ValueError, match="already"):
        reader.add_glossary_term("veiling glares", "x")  # same term, plural
    with pytest.raises(ValueError, match="中文"):
        reader.add_glossary_term("flare", "  ")
    with pytest.raises(ValueError, match="English"):
        reader.add_glossary_term("杂光", "杂光")
    lines = (dictionary / "glossaries" / "optics.csv").read_text(encoding="utf-8").splitlines()
    assert lines[-1] == 'Veiling glare,杂光,,"像面上均匀的杂光背景, 降低对比度"'


def test_several_glossaries_with_labels(dictionary):
    folder = dictionary / "glossaries"
    (folder / "biology.csv").write_text(
        "term,zh,note,definition\npupil,瞳孔,,虹膜中央的开口。\ncell,细胞,,\n", encoding="utf-8"
    )
    (folder / "glossaries.toml").write_text(
        'default = "biology"\n[optics]\nlabel = "光学"\n[biology]\nlabel = "生物"\n',
        encoding="utf-8",
    )
    assert [g["name"] for g in reader.glossary_files()] == ["biology", "optics"]  # default first
    # The same term in two subjects: both meanings, each with its own label
    info = reader.lookup("pupil")
    assert [(g["label"], g["zh"]) for g in info["glossary"]] == [("生物", "瞳孔"), ("光学", "光瞳")]
    assert info["glossaries"] == [
        {"name": "biology", "label": "生物"},
        {"name": "optics", "label": "光学"},
    ]
    # New terms go to the default glossary, or to the one chosen
    assert reader.add_glossary_term("nucleus", "细胞核")["glossary"] == "biology"
    added = reader.add_glossary_term("cell", "（光学）单元", glossary_name="optics")
    assert added["label"] == "光学"  # "cell" is only in biology so far: fine to add to optics
    with pytest.raises(ValueError, match="already in the 生物 glossary"):
        reader.add_glossary_term("cells", "x", glossary_name="biology")
    with pytest.raises(ValueError, match="no glossary"):
        reader.add_glossary_term("tissue", "组织", glossary_name="chemistry")
    # Switched off in the config: not used any more
    (folder / "glossaries.toml").write_text("[optics]\nenabled = false\n", encoding="utf-8")
    assert [g["label"] for g in reader.lookup("pupil")["glossary"]] == ["biology"]


def test_first_term_creates_a_glossary(dictionary):
    (dictionary / "glossaries" / "optics.csv").unlink()
    assert reader.glossary_files() == []
    added = reader.add_glossary_term("stop", "光阑")
    assert added["glossary"] == "my-terms"
    text = (dictionary / "glossaries" / "my-terms.csv").read_text(encoding="utf-8")
    assert text == "term,zh,note,definition\nstop,光阑,,\n"
    assert reader.lookup("stops")["glossary"][0]["zh"] == "光阑"


def test_irregular_plurals(dictionary):
    assert [reader.lemma(w) for w in ("matrices", "phenomena", "axes", "criteria")] == [
        "matrix",
        "phenomenon",
        "axis",
        "criterion",
    ]


def test_glossaries_of_the_books_shelves_come_first(dictionary):
    (dictionary / "glossaries" / "biology.csv").write_text(
        "term,zh,note,definition\npupil,瞳孔,,\n", encoding="utf-8"
    )
    for slug, shelves in (("eye-book", "Biology; Medicine"), ("lens-book", "Optics")):
        put(dictionary / "catalog.csv", {"slug": slug, "shelves": shelves})
    # Shelves named after a subject: "Advanced optical system design" is about optics
    put(dictionary / "catalog.csv", {"slug": "design-book", "field": "Engineering",
                   "shelves": "Advanced optical system design",
                   "topic": "Advanced optical system design"})  # fmt: skip

    def order(name):
        doc = id_of(dictionary / "catalog.csv", name) if name else None
        return [g["glossary"] for g in reader.lookup("pupil", "", doc)["glossary"]]

    assert order(None) == ["biology", "optics"]  # no book: alphabetical
    assert order("eye-book") == ["biology", "optics"]
    assert order("lens-book") == ["optics", "biology"]
    assert order("design-book") == ["optics", "biology"]
    # A longer, more specific term still comes before a shelf match
    info = reader.lookup(
        "pupil", "the entrance pupil", id_of(dictionary / "catalog.csv", "eye-book")
    )
    assert [g["term"] for g in info["glossary"]] == ["entrance pupil", "pupil", "pupil"]


# --- the PDF viewer (PDF.js): pinned, checksum-verified install --------------------------------


def _fake_release(path, names=None):
    """A small zip shaped like the PDF.js release; returns its bytes."""
    import zipfile

    names = names or ["web/viewer.html", "web/viewer.mjs", "build/pdf.mjs", "build/pdf.worker.mjs"]
    with zipfile.ZipFile(path, "w") as z:
        for name in names:
            z.writestr(name, f"new {name}")
    return path.read_bytes()


@pytest.fixture
def viewer_home(tmp_path, monkeypatch):
    """The reader's cache in a temporary folder, with a working (old) viewer installed."""
    monkeypatch.setattr(reader, "CACHE", tmp_path / "reader")
    monkeypatch.setattr(reader, "PDFJS", tmp_path / "reader" / "pdfjs")
    (reader.PDFJS / "web").mkdir(parents=True)
    (reader.PDFJS / "web" / "viewer.html").write_text("old viewer", encoding="utf-8")
    return tmp_path


def _pin(monkeypatch, data):
    import hashlib

    monkeypatch.setattr(reader, "PDFJS_SHA256", hashlib.sha256(data).hexdigest())
    monkeypatch.setattr(reader, "PDFJS_SIZE", len(data))


def test_the_viewer_is_installed_only_from_the_expected_archive(viewer_home, monkeypatch):
    good = viewer_home / "good.zip"
    data = _fake_release(good)
    assert reader.viewer_installed() == "unverified"  # installed before checksums
    with pytest.raises(ValueError, match="isn't the expected file"):  # the real pin: no match
        reader.install_viewer(good)
    assert (reader.PDFJS / "web" / "viewer.html").read_text(encoding="utf-8") == "old viewer"

    _pin(monkeypatch, data)
    reader.install_viewer(good)
    assert (reader.PDFJS / "web" / "viewer.html").read_text(encoding="utf-8").startswith("new")
    assert reader.viewer_installed() == f"verified {reader.PDFJS_VERSION}"
    assert sorted(p.name for p in reader.CACHE.iterdir()) == ["pdfjs"]  # nothing left over


@pytest.mark.parametrize(
    "names",
    [
        [
            "../evil.txt",
            "web/viewer.html",
            "web/viewer.mjs",
            "build/pdf.mjs",
            "build/pdf.worker.mjs",
        ],
        ["web/viewer.html", "web/viewer.mjs", "build/pdf.worker.mjs"],  # no build/pdf.mjs
        [
            "C:/evil.txt",
            "web/viewer.html",
            "web/viewer.mjs",
            "build/pdf.mjs",
            "build/pdf.worker.mjs",
        ],
    ],
)
def test_an_unexpected_archive_leaves_the_working_viewer(viewer_home, monkeypatch, names):
    bad = viewer_home / "bad.zip"
    _pin(monkeypatch, _fake_release(bad, names))  # even with a matching checksum
    with pytest.raises(ValueError):
        reader.install_viewer(bad)
    assert (reader.PDFJS / "web" / "viewer.html").read_text(encoding="utf-8") == "old viewer"
    assert not (viewer_home / "evil.txt").exists() and not (reader.CACHE / "evil.txt").exists()
    assert sorted(p.name for p in reader.CACHE.iterdir()) == ["pdfjs"]


def test_setup_viewer_downloads_checks_and_installs(viewer_home, monkeypatch):
    release = viewer_home / "release.zip"
    _pin(monkeypatch, _fake_release(release))
    monkeypatch.setattr(reader, "PDFJS_URL", release.as_uri())
    reader.setup_viewer()  # an (unverified) viewer is there: nothing downloaded
    assert (reader.PDFJS / "web" / "viewer.html").read_text(encoding="utf-8") == "old viewer"
    import shutil

    shutil.rmtree(reader.PDFJS)
    reader.setup_viewer()
    assert reader.viewer_installed() == f"verified {reader.PDFJS_VERSION}"
    assert sorted(p.name for p in reader.CACHE.iterdir()) == ["pdfjs"]  # the zip removed
