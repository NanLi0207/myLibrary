"""Subjects from OpenAlex, and shelves made from them."""

import book_meta
import shelves
import subjects
from testlib import entry, id_of, put  # noqa: F401

REAL_LOOKUP = subjects.lookup  # conftest stubs it for every other test


def topic(name, field, score):
    return {"display_name": name, "score": score, "field": {"display_name": field}}


RAIL = topic("Railway Engineering and Dynamics", "Engineering", 0.97)
WEEDS = topic(
    "Weed Control and Herbicide Applications", "Agricultural and Biological Sciences", 0.9
)


def test_a_paper_by_its_doi(monkeypatch):
    asked = []

    def answer(url, **kw):
        asked.append(url)
        return {"topics": [WEEDS, RAIL | {"score": 0.05}]}

    monkeypatch.setattr(book_meta, "_get_json", answer)
    found = REAL_LOOKUP({"doi": "10.1016/j.trpro.2023.11.574", "title": "x"})
    assert asked == ["https://api.openalex.org/works/doi:10.1016/j.trpro.2023.11.574"]
    assert (found["topic"], found["field"], found["score"]) == (
        "Weed Control and Herbicide Applications",
        "Agricultural and Biological Sciences",
        0.95,
    )


def test_a_book_by_title_and_author_adding_up_its_records(monkeypatch):
    records = [
        {
            "title": "Modern Railway Track",
            "authorships": [{"author": {"display_name": "C. Esveld"}}],
            "topics": [RAIL],
        },
        {"title": "Modern railway track: second edition", "authorships": [], "topics": [RAIL]},
        # same title, another author: not this book
        {
            "title": "Modern Railway Track",
            "authorships": [{"author": {"display_name": "A. Other"}}],
            "topics": [WEEDS],
        },
        {"title": "Something else entirely", "authorships": [], "topics": [WEEDS]},
    ]
    monkeypatch.setattr(book_meta, "_get_json", lambda url, **kw: {"results": records})
    found = REAL_LOOKUP({"title": "Modern Railway Track", "authors": "Coenraad Esveld"})
    assert found["topic"] == "Railway Engineering and Dynamics" and found["score"] == 1.0
    assert REAL_LOOKUP({"title": "Unknown To Everyone", "authors": "Nobody"}) == {}


def test_fields_in_chinese_and_english():
    assert subjects.field_label("Engineering") == "工程 Engineering"
    assert subjects.field_label("Computer Science") == "计算机科学 Computer Science"
    assert subjects.field_label("Something New") == "Something New"
    assert len(subjects.FIELDS_ZH) == 26


def test_a_sure_subject_becomes_a_shelf_next_to_yours(tmp_path, monkeypatch):
    path = tmp_path / "catalog.csv"
    for slug, title, on in (
        ("a-2001-lens", "Lens Design Basics", "Optics; Lens design"),
        ("b-2002-lens", "Practical Lens Design", "Optics; Lens design"),
        ("c-2003-lens", "Modern Lens Design", "Optics; Lens design"),
    ):
        put(path, {"slug": slug, "title": title, "shelves": on})
    monkeypatch.setattr(
        subjects,
        "lookup",
        lambda row: {
            "field": "Engineering",
            "topic": "Advanced optical system design",
            "score": 0.98,
            "source": "x",
        },
    )
    put(path, {"slug": "d-2004-lens", "title": "Lens Design Fundamentals"})
    subjects.classify(id_of(path, "d-2004-lens"), tmp_path, path)
    assert shelves.auto_shelve(id_of(path, "d-2004-lens"), tmp_path, path) == [
        "Advanced optical system design",  # its subject, a new shelf
        "Optics",  # and your own shelves that fit
        "Lens design",
    ]
    row = entry(path, "d-2004-lens")
    assert (row["field"], row["topic"], row["topic_score"]) == (
        "Engineering",
        "Advanced optical system design",
        "0.98",
    )


def test_an_unsure_subject_is_recorded_but_makes_no_shelf(tmp_path, monkeypatch):
    path = tmp_path / "catalog.csv"
    put(
        path,
        {"slug": "x-2001-y", "title": "Specifying excimer beam uniformity", "shelves": "Lasers"},
    )
    monkeypatch.setattr(
        subjects,
        "lookup",
        lambda row: {
            "field": "Engineering",
            "score": 0.46,
            "topic": "Laser Material Processing Techniques",
            "source": "x",
        },
    )
    subjects.classify(id_of(path, "x-2001-y"), tmp_path, path)
    assert shelves.add_topic_shelf(id_of(path, "x-2001-y"), path) == ""
    row = entry(path, "x-2001-y")
    assert row["topic"] == "Laser Material Processing Techniques" and row["shelves"] == "Lasers"


def test_unknown_items_are_looked_up_once(tmp_path):
    path = tmp_path / "catalog.csv"
    put(path, {"slug": "x-2001-y", "title": "Internal report"})
    assert subjects.unclassified(tmp_path, path) == [id_of(path, "x-2001-y")]
    subjects.classify(
        id_of(path, "x-2001-y"), tmp_path, path
    )  # OpenAlex doesn't know it (stub: {})
    assert subjects.unclassified(tmp_path, path) == []


def test_a_less_sure_subject_only_when_nothing_else_fits(tmp_path, monkeypatch):
    path = tmp_path / "catalog.csv"
    put(path, {"slug": "x-2001-y", "title": "Specifying excimer beam uniformity"})
    monkeypatch.setattr(
        subjects,
        "lookup",
        lambda row: {
            "field": "Engineering",
            "score": 0.46,
            "source": "x",
            "topic": "Laser Material Processing Techniques",
        },
    )
    subjects.classify(id_of(path, "x-2001-y"), tmp_path, path)
    assert shelves.auto_shelve(id_of(path, "x-2001-y"), tmp_path, path) == [
        "Laser Material Processing Techniques"
    ]


def test_unknown_items_go_by_what_similar_works_are_about(monkeypatch):
    lens = topic("Advanced optical system design", "Engineering", 0.9)
    works = [{"topics": [lens]}] * 7 + [{"topics": [RAIL]}] * 3
    answers = {"title": [], "vote": works}

    def answer(url, **kw):  # the title search finds no record of it; the vote finds works
        return {"results": answers["vote" if "select=topics&" in url else "title"]}

    monkeypatch.setattr(book_meta, "_get_json", answer)
    found = REAL_LOOKUP({"title": "Introduction to Lens Design With Practical ZEMAX examples"})
    assert (found["topic"], found["score"], found["source"]) == (
        "Advanced optical system design",
        0.68,  # 7 x 0.9 against 3 x 0.97, weighted by how sure each is
        "OpenAlex (similar works)",
    )
    answers["vote"] = [{"topics": [topic(f"Topic {n}", "Engineering", 0.9)]} for n in range(10)]
    assert REAL_LOOKUP({"title": "Something nobody agrees on"}) == {}  # no majority: nothing


def test_last_resort_the_clearly_closest_shelf():
    rows = [
        {
            "title": "Weed control on railway tracks",
            "keywords": "vegetation management",
            "shelves": "Weeds",
        },
        {
            "title": "Herbicide-free vegetation control",
            "keywords": "vegetation; railway",
            "shelves": "Weeds",
        },
        {"title": "Wheel rail adhesion", "shelves": "Rail"},
        {"title": "Rail friction", "shelves": "Rail"},
    ]
    names = ["Weeds", "Rail"]
    report = {"title": "UIC Guideline for Integrated Vegetation Management - Part A"}
    assert shelves.closest_shelf(report, rows, names) == "Weeds"
    assert shelves.closest_shelf({"title": "Pro Git"}, rows, names) == ""  # nothing close


def test_an_item_is_not_marked_tried_when_openalex_cant_answer(tmp_path, monkeypatch):
    path = tmp_path / "catalog.csv"
    put(path, {"slug": "x-2001-y", "title": "Modern Lens Design"})

    def daily_limit(row):
        raise book_meta.Unavailable("api.openalex.org: HTTP 429")

    monkeypatch.setattr(subjects, "lookup", daily_limit)
    try:
        subjects.classify(id_of(path, "x-2001-y"), tmp_path, path)
    except book_meta.Unavailable:
        pass
    assert subjects.unclassified(tmp_path, path) == [
        id_of(path, "x-2001-y")
    ]  # asked again next time


def test_strict_requests_tell_no_record_from_no_answer(monkeypatch):
    import io
    import urllib.error

    import pytest

    def fail(code, retry_after="0"):
        def urlopen(request, timeout):
            raise urllib.error.HTTPError(
                request.full_url, code, "", {"Retry-After": retry_after}, io.BytesIO()
            )

        return urlopen

    monkeypatch.setattr(book_meta.time, "sleep", lambda s: None)
    monkeypatch.setattr(book_meta.urllib.request, "urlopen", fail(404))
    assert book_meta._get_json("https://api.openalex.org/works/doi:x", strict=True) is None
    monkeypatch.setattr(book_meta.urllib.request, "urlopen", fail(429, "35149"))
    with pytest.raises(book_meta.Unavailable):
        book_meta._get_json("https://api.openalex.org/works?search=x", strict=True)
    assert book_meta._get_json("https://api.openalex.org/works?search=x") is None
