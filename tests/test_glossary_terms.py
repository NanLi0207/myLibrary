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
    reader._lemma.cache_clear()
    yield folder
    reader._lemma.cache_clear()


def write(path, text: str, bom: bool = False) -> None:
    path.write_bytes((codecs.BOM_UTF8 if bom else b"") + text.encode("utf-8"))


def rows(path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def together(monkeypatch, count: int):
    """Hold `count` requests inside the (cached) duplicate check until all are there."""
    gate = threading.Barrier(count)
    look_up = reader.glossary

    def at_the_same_time():
        found = look_up()
        gate.wait(WAIT)  # all have looked, none has written yet
        return found

    monkeypatch.setattr(reader, "glossary", at_the_same_time)


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
