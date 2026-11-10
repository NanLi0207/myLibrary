"""L23: the popup's glossary lookup (reader.lookup) agrees with what may be added (B30's "same
term"). A glossary word used to be its own base form unless one of its guesses was a glossary
word too, so a term saved only as "veiling glares" was missed for "veiling glare", depending
even on other glossaries. Lookup now also reads the words as B30 does (the selection's and its
context's words counting as glossary words), and "glasses" is never taken for the plural of
"glass" (reader.OWN_TERMS). Temporary glossaries and dictionary only (the glossary tests'
fixture); deterministic, nothing timed."""

import pytest
import reader
from test_glossary_terms import ECDICT, HEADER, glossaries, rows, write  # noqa: F401

DICTIONARY = ECDICT + (
    "datum,'deɪtəm,,n. 基准,,,,,0,0,s:data,,\n"
    "data,'deɪtə,,n. 数据,,,,,0,0,0:datum/1:s,,\n"
    "focus,'fəʊkəs,,n. 焦点,,,,,0,0,s:foci,,\n"
    "glass,glɑːs,,n. 玻璃,,,,,0,0,s:glasses,,\n"
    "glasses,'glɑːsɪz,,n. 眼镜,,,,,0,0,0:glass/1:s,,\n"
)


@pytest.fixture
def folder(glossaries, monkeypatch, tmp_path):  # noqa: F811  (the imported fixture, used)
    (tmp_path / "dictionary.csv").write_text(DICTIONARY, encoding="utf-8")
    reader.build_dictionary(tmp_path / "dictionary.csv", tmp_path / "dictionary.db")
    monkeypatch.setattr(reader, "DICT_DB", tmp_path / "dictionary.db")
    reader._lemma.cache_clear()
    return glossaries


def glossary(folder, name: str, *terms: str) -> None:
    """A glossary file with these terms, written as another program would."""
    write(folder / f"{name}.csv", HEADER + "\n" + "".join(f"{t},术语,,\n" for t in terms))


def found(query: str, context: str = "") -> list[tuple[str, str]]:
    """(term, glossary) of what the popup shows for `query`, through the public lookup()."""
    return [(e["term"], e["glossary"]) for e in reader.lookup(query, context)["glossary"]]


def refused(term: str) -> bool:
    try:
        reader.add_glossary_term(term, "术语")
    except ValueError as e:
        assert "already in" in str(e)
        return True
    return False


# --- 1-3, 14: singular and plural, however the term came in, and caches ----------------------


@pytest.mark.parametrize("saved_by", ["file", "popup"])
def test_a_plural_saved_is_found_by_its_singular(folder, saved_by):
    glossary(folder, "optics", "pupil")
    if saved_by == "file":
        glossary(folder, "optics", "pupil", "veiling glares")
    else:
        reader.add_glossary_term("veiling glares", "杂光")
    assert found("veiling glares") == [("veiling glares", "optics")]
    assert found("veiling glare") == [("veiling glares", "optics")]


@pytest.mark.parametrize("saved_by", ["file", "popup"])
def test_a_singular_saved_is_found_by_its_plural(folder, saved_by):
    glossary(folder, "optics", "pupil")
    if saved_by == "file":
        glossary(folder, "optics", "pupil", "veiling glare")
    else:
        reader.add_glossary_term("veiling glare", "杂光")
    assert found("veiling glare") == [("veiling glare", "optics")]
    assert found("veiling glares") == [("veiling glare", "optics")]


def test_outside_edits_are_seen_at_once_both_ways(folder):
    """The caches follow the files: a plural written by another program is found by its
    singular at once, and once removed it isn't found any more."""
    glossary(folder, "optics", "pupil")
    assert found("veiling glare") == []  # (caches built)
    glossary(folder, "optics", "pupil", "veiling glares")
    assert found("veiling glare") == [("veiling glares", "optics")]
    glossary(folder, "optics", "pupil")
    assert found("veiling glare") == [] and found("veiling glares") == []


# --- 4, 11: other glossaries, and their order -------------------------------------------------


def test_another_glossary_doesnt_decide_what_is_found(folder):
    """It used to: with "glare" in another glossary, optics' "veiling glares" was found by
    "veiling glare"; without it, it wasn't."""
    glossary(folder, "optics", "veiling glares")
    glossary(folder, "lighting", "glare")
    with_it = found("veiling glare")
    glossary(folder, "lighting", "pupil")
    without_it = found("veiling glare")
    assert ("veiling glares", "optics") in with_it
    assert without_it == [("veiling glares", "optics")]


def test_the_books_subject_still_comes_first(folder, monkeypatch):
    """Several glossaries with the term: the one of the book's subject first, as before."""
    glossary(folder, "biology", "pupil")
    glossary(folder, "optics", "pupils")
    import shelves

    about = set(shelves.tokens("optics"))
    monkeypatch.setattr(reader, "book_subject_words", lambda doc_id: about)
    result = reader.lookup("pupil", doc_id="any")["glossary"]
    assert [e["glossary"] for e in result] == ["optics", "biology"]
    monkeypatch.setattr(reader, "book_subject_words", lambda doc_id: set())
    result = reader.lookup("pupil", doc_id="any")["glossary"]
    assert [e["glossary"] for e in result] == ["biology", "optics"]  # exact spelling first


# --- 5: exact spellings ---------------------------------------------------------------------


def test_the_exact_spelling_always_finds_the_term_and_comes_first(folder):
    glossary(folder, "a-optics", "veiling glares", "entrance pupil", "datum")
    glossary(folder, "b-lighting", "veiling glare")
    for term in ("entrance pupil", "datum"):
        assert found(term) == [(term, "a-optics")]
    assert found("veiling glares") == [
        ("veiling glares", "a-optics"),
        ("veiling glare", "b-lighting"),
    ]
    assert found("veiling glare") == [
        ("veiling glare", "b-lighting"),
        ("veiling glares", "a-optics"),
    ]


# --- 6-9: which forms are one term, which are two ---------------------------------------------


@pytest.mark.parametrize(
    "first, second",
    [("glass", "glasses"), ("glasses", "glass"), ("data", "datum"), ("datum", "data")],
)
def test_distinct_technical_terms_are_both_kept_and_found(folder, first, second):
    """Glass (the material) and glasses (spectacles); data and a datum (a reference surface):
    each can be added beside the other, in either order, and each finds itself."""
    glossary(folder, "optics", "pupil")
    assert not refused(first) and not refused(second)
    assert [r["term"] for r in rows(folder / "optics.csv")] == ["pupil", first, second]
    assert found(first) == [(first, "optics")] and found(second) == [(second, "optics")]


@pytest.mark.parametrize("term", ["glass", "glasses"])
def test_glass_and_glasses_dont_find_each_other(folder, term):
    glossary(folder, "optics", term)
    other = "glasses" if term == "glass" else "glass"
    assert found(other) == [] and found(term) == [(term, "optics")]


@pytest.mark.parametrize(
    "saved, asked",
    [("veiling glare", "veiling glares"), ("veiling glares", "veiling glare"),
     ("lens", "lenses"), ("lenses", "lens"), ("focus", "foci"), ("foci", "focus")],
)  # fmt: skip
def test_one_term_in_two_forms_is_refused_and_found(folder, saved, asked):
    """Ordinary plurals (glare, lens) and irregular ones (focus, foci): one term, whichever
    form is saved; the other form is refused when added, and finds the saved one."""
    glossary(folder, "optics", "pupil", saved)
    assert found(asked) == [(saved, "optics")]
    assert refused(asked)


# --- 10: terms around the selection ---------------------------------------------------------


@pytest.mark.parametrize(
    "saved, selection, context",
    [("entrance pupils", "pupil", "here the entrance pupil is small"),
     ("entrance pupil", "pupils", "both entrance pupils are small")],
)  # fmt: skip
def test_a_longer_term_around_the_selection_is_found_in_either_form(
    folder, saved, selection, context
):
    glossary(folder, "optics", saved, "lens")
    assert found(selection, context) == [(saved, "optics")]


def test_context_matching_stays_with_the_words_around_the_selection(folder):
    """No broader matches: a term is found for the selection only where the context holds it
    around the selection, longest first, each once."""
    glossary(folder, "optics", "entrance pupils", "exit pupil", "pupil")
    got = found("pupil", "here the entrance pupil is small")
    assert got == [("entrance pupils", "optics"), ("pupil", "optics")]  # not "exit pupil"


# --- 12: the popup's "in the glossary" agrees with adding ------------------------------------


@pytest.mark.parametrize(
    "saved, asked",
    [("veiling glares", "veiling glare"), ("veiling glare", "veiling glares"),
     ("glass", "glasses"), ("glasses", "glass"), ("datum", "data"), ("data", "datum"),
     ("lenses", "lens"), ("focus", "foci"), ("entrance pupil", "pupil")],
)  # fmt: skip
def test_in_glossary_says_what_adding_would_do(folder, saved, asked):
    """The popup offers 加入术语表 (Add to glossary) unless in_glossary: exactly when adding
    would be refused."""
    glossary(folder, "optics", saved)
    in_glossary = reader.lookup(asked)["in_glossary"]
    assert in_glossary == refused(asked), (saved, asked, in_glossary)
