"""D16: 加入术语表 (Add to glossary) adds a row to the user's glossary CSV under that file's lock:
the duplicate check reads the file as it is now (not a cached glossary), and the whole file is
written atomically (safe_io), keeping its BOM and line endings and never joining two rows. A
failed write changes nothing. Temporary glossaries; concurrent requests are released together
with a barrier."""

import codecs
import csv
import threading

import pytest
import reader

ECDICT = (
    "word,phonetic,definition,translation,pos,collins,oxford,tag,bnc,frq,exchange,detail,audio\n"
    "pupil,'pju:pl,,n. 瞳孔,,,,,0,0,s:pupils,,\n"
    "glare,gleə,,n. 眩光,,,,,0,0,s:glares,,\n"
)
HEADER = "term,zh,note,definition"
WAIT = 30


@pytest.fixture
def glossaries(tmp_path, monkeypatch):
    """A one-word-each dictionary and an optics glossary in a temporary folder."""
    (tmp_path / "ecdict.csv").write_text(ECDICT, encoding="utf-8")
    db = tmp_path / "ecdict.db"
    reader.build_dictionary(tmp_path / "ecdict.csv", db)
    folder = tmp_path / "glossaries"
    folder.mkdir()
    monkeypatch.setattr(reader, "LIBRARY", tmp_path)
    monkeypatch.setattr(reader, "DICT_DB", db)
    monkeypatch.setattr(reader, "GLOSSARIES", folder)
    monkeypatch.setattr(reader, "GLOSSARY_CONFIG", folder / "glossaries.toml")
    monkeypatch.setattr(reader, "_glossary_cache", None)
    monkeypatch.setattr(reader, "_glossary_words_cache", None)
    monkeypatch.setattr(reader, "_glossary_index_cache", None)
    reader._lemma.cache_clear()
    yield folder
    reader._lemma.cache_clear()


def write(path, text: str, bom: bool = False) -> None:
    path.write_bytes((codecs.BOM_UTF8 if bom else b"") + text.encode("utf-8"))


def rows(path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def together(monkeypatch, count: int):
    """Hold `count` requests once they have chosen their glossary, before any of them reaches
    the file's lock, until all are there: all in flight at once. (glossary_files is the first
    thing a request asks; each thread waits only on its first call, since the duplicate check
    under the lock asks again, and waiting there would hold the lock.)"""
    gate = threading.Barrier(count)
    files = reader.glossary_files
    waited = threading.local()

    def at_the_same_time():
        found = files()
        if not getattr(waited, "done", False):
            waited.done = True
            gate.wait(WAIT)  # all have chosen their glossary, none has written yet
        return found

    monkeypatch.setattr(reader, "glossary_files", at_the_same_time)


def run_all(*works):
    outcomes = [{} for _ in works]

    def run(work, outcome):
        try:
            outcome["result"] = work()
        except BaseException as e:
            outcome["error"] = e

    threads = [threading.Thread(target=run, args=pair, daemon=True)
               for pair in zip(works, outcomes, strict=True)]  # fmt: skip
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(WAIT)
    return outcomes


def test_the_same_term_twice_at_once_is_added_once(glossaries, monkeypatch):
    optics = glossaries / "optics.csv"
    write(optics, f"{HEADER}\npupil,光瞳,,\n")
    together(monkeypatch, 2)
    outcomes = run_all(lambda: reader.add_glossary_term("veiling glare", "杂光"),
                       lambda: reader.add_glossary_term("veiling glares", "杂光"))  # fmt: skip
    errors = [o["error"] for o in outcomes if "error" in o]
    assert len(errors) == 1 and isinstance(errors[0], ValueError), outcomes
    assert "already in" in str(errors[0])
    terms = [r["term"] for r in rows(optics)]
    assert terms.count("veiling glare") + terms.count("veiling glares") == 1, terms


@pytest.mark.parametrize(
    "first, second",
    [("veiling glare", "veiling glares"), ("veiling glares", "veiling glare")],
    ids=["singular-first", "plural-first"],
)
def test_the_same_term_is_refused_whichever_form_came_first(glossaries, first, second):
    """B30: lemma prefers a form a glossary uses, so with only "veiling glares" stored, "glares"
    was its own base form and "veiling glare" was added beside it, one request after the
    other, no concurrency needed. The check now counts the new term's words as glossary words
    (the glossary as it will be): the same term either way round."""
    optics = glossaries / "optics.csv"
    write(optics, f"{HEADER}\npupil,光瞳,,\n")
    reader.add_glossary_term(first, "杂光")
    before = optics.read_bytes()
    with pytest.raises(ValueError, match="already in the optics glossary"):
        reader.add_glossary_term(second, "杂光")
    assert optics.read_bytes() == before  # nothing written
    assert [r["term"] for r in rows(optics)] == ["pupil", first]


def test_the_plural_written_first_still_stops_the_singular(glossaries, monkeypatch):
    """B30's failing interleaving, forced: both requests pass the (cached) look-up, then the
    plural is written first and only then does the singular reach the file's lock. It used to
    be added too (both reported success, two rows); now it gets the duplicate error."""
    optics = glossaries / "optics.csv"
    write(optics, f"{HEADER}\npupil,光瞳,,\n")
    together(monkeypatch, 2)
    plural_written = threading.Event()
    add_row = reader._add_glossary_row

    def in_this_order(path, term, row, label):
        if term == "veiling glare":
            assert plural_written.wait(WAIT), "the plural was never written"
        try:
            return add_row(path, term, row, label)
        finally:
            if term == "veiling glares":
                plural_written.set()

    monkeypatch.setattr(reader, "_add_glossary_row", in_this_order)
    singular, plural = run_all(
        lambda: reader.add_glossary_term("veiling glare", "杂光"),
        lambda: reader.add_glossary_term("veiling glares", "杂光"),
    )
    assert "result" in plural and isinstance(singular.get("error"), ValueError), (singular, plural)
    assert "already in" in str(singular["error"])
    assert [r["term"] for r in rows(optics)] == ["pupil", "veiling glares"]


def test_different_words_with_a_shared_stem_are_still_different_terms(glossaries):
    """Counting the new term's words as glossary words changes nothing for terms that really
    differ: "veiling glare" and "veiling flare", "pupil" and "pupil function"."""
    optics = glossaries / "optics.csv"
    write(optics, f"{HEADER}\npupil,光瞳,,\n")
    for term in ("veiling glare", "veiling flare", "pupil function", "exit pupil"):
        reader.add_glossary_term(term, "术语")
    assert [r["term"] for r in rows(optics)] == [
        "pupil", "veiling glare", "veiling flare", "pupil function", "exit pupil"
    ]  # fmt: skip


def test_one_definition_of_the_same_term_decides(glossaries, monkeypatch, tmp_path):
    """The dictionary gives "data" the base form "datum" (ECDICT's 0: exchange; no plural ending
    to strip, not an irregular plural we list). With "datum" (a reference surface) in the
    glossary, an early check without the new term's words took "data" for "datum" and refused
    it, though the check that decides (under the lock, with the glossary as it will be) sees
    two terms, as lookup will once both are in. One definition decides now: "data" is added;
    "datum" again, and "data" again, are still refused."""
    (tmp_path / "with-datum.csv").write_text(
        ECDICT + "datum,'deɪtəm,,n. 基准,,,,,0,0,s:data,,\n"
        "data,'deɪtə,,n. 数据,,,,,0,0,0:datum/1:s,,\n",
        encoding="utf-8",
    )
    db = tmp_path / "with-datum.db"
    reader.build_dictionary(tmp_path / "with-datum.csv", db)
    monkeypatch.setattr(reader, "DICT_DB", db)
    reader._lemma.cache_clear()
    optics = glossaries / "optics.csv"
    write(optics, f"{HEADER}\ndatum,基准,,\n")
    assert reader.lemma("data") == "datum"  # (the dictionary's base form, as things are)
    reader.add_glossary_term("data", "数据")
    assert [r["term"] for r in rows(optics)] == ["datum", "data"]
    for again in ("datum", "data"):
        with pytest.raises(ValueError, match="already in the optics glossary"):
            reader.add_glossary_term(again, "基准")
    assert [r["term"] for r in rows(optics)] == ["datum", "data"]
    # ... and lookup, once both are in, keeps them apart too: two entries
    keys = reader.glossary()
    assert keys[("datum",)][0]["zh"] == "基准" and keys[("data",)][0]["zh"] == "数据"


def test_two_different_terms_at_once_are_both_kept(glossaries, monkeypatch):
    optics = glossaries / "optics.csv"
    write(optics, f"{HEADER}\npupil,光瞳,,\n")
    together(monkeypatch, 2)
    outcomes = run_all(lambda: reader.add_glossary_term("veiling glare", "杂光"),
                       lambda: reader.add_glossary_term("vignetting", "渐晕"))  # fmt: skip
    assert all("result" in o for o in outcomes), outcomes
    assert sorted(r["term"] for r in rows(optics)) == ["pupil", "veiling glare", "vignetting"]


def test_a_failed_write_changes_nothing(glossaries, monkeypatch):
    optics = glossaries / "optics.csv"
    write(optics, f"{HEADER}\npupil,光瞳,,\n")
    before = optics.read_bytes()
    assert "glare" not in str(reader.glossary())  # (the cache, as it was)

    def disk_full(path, data, **kw):
        raise OSError(28, "No space left on device")

    with monkeypatch.context() as failing:
        failing.setattr(reader.safe_io, "write_bytes", disk_full)
        with pytest.raises(OSError):
            reader.add_glossary_term("veiling glare", "杂光")
    assert optics.read_bytes() == before
    assert ("veiling", "glare") not in reader.glossary()  # nothing taken as added
    reader.add_glossary_term("veiling glare", "杂光")  # and adding it later works
    assert ("veiling", "glare") in reader.glossary()


@pytest.mark.parametrize("eol", ["\r\n", "\n"])
@pytest.mark.parametrize("bom", [True, False])
def test_the_files_bom_and_line_endings_are_kept(glossaries, eol, bom):
    optics = glossaries / "optics.csv"
    write(optics, f"{HEADER}{eol}pupil,光瞳,,{eol}", bom=bom)
    reader.add_glossary_term("veiling glare", "杂光", "像面上均匀的杂光背景", "flare")
    data = optics.read_bytes()
    assert data.startswith(codecs.BOM_UTF8) == bom
    text = data.decode("utf-8-sig")
    assert text.endswith(f"veiling glare,杂光,flare,像面上均匀的杂光背景{eol}")
    if eol == "\r\n":
        assert "\n" not in text.replace("\r\n", "")  # (no bare LF added)
    else:
        assert "\r" not in text
    assert [r["term"] for r in rows(optics)] == ["pupil", "veiling glare"]


def test_a_file_without_a_final_newline_gets_its_row_on_a_line_of_its_own(glossaries):
    optics = glossaries / "optics.csv"
    write(optics, f"{HEADER}\r\npupil,光瞳,,")  # (as some editors leave it)
    reader.add_glossary_term("vignetting", "渐晕")
    expected = f"{HEADER}\r\npupil,光瞳,,\r\nvignetting,渐晕,,\r\n"
    assert optics.read_bytes().decode("utf-8") == expected
    assert [(r["term"], r["zh"]) for r in rows(optics)] == [
        ("pupil", "光瞳"),
        ("vignetting", "渐晕"),
    ]


def test_a_new_glossary_is_made_with_its_header(glossaries):
    reader.add_glossary_term("vignetting", "渐晕")
    path = glossaries / f"{reader.NEW_GLOSSARY}.csv"
    assert [r["term"] for r in rows(path)] == ["vignetting"]


def test_the_glossary_readers_see_the_new_term(glossaries):
    write(glossaries / "optics.csv", f"{HEADER}\npupil,光瞳,,\n")
    reader.glossary()  # (cached before the addition)
    reader.add_glossary_term("veiling glare", "杂光")
    assert [e["zh"] for e in reader.glossary()[("veiling", "glare")]] == ["杂光"]
    found = reader.lookup("glare", "the veiling glare here")["glossary"]
    assert found[0]["zh"] == "杂光"


def test_a_glossary_past_the_windows_path_limit(tmp_path, glossaries, monkeypatch):
    deep = tmp_path
    while len(str(deep)) < 250:
        deep = deep / ("long-folder-name-" + "x" * 20)
    monkeypatch.setattr(reader, "GLOSSARIES", deep / "glossaries")
    reader.add_glossary_term("vignetting", "渐晕")
    path = deep / "glossaries" / f"{reader.NEW_GLOSSARY}.csv"
    assert len(str(path)) > 260
    text = reader.safe_io.read_bytes(path).decode("utf-8")
    assert text.splitlines()[-1] == "vignetting,渐晕,,"
    with pytest.raises(ValueError, match="already in"):
        reader.add_glossary_term("vignetting", "渐晕")
    assert reader.safe_io.read_bytes(path).decode("utf-8") == text
