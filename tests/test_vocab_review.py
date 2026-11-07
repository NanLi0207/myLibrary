"""📇 Review words: saved words as cards, spaced repetition."""

from datetime import date, timedelta

import vocab_review
from testlib import entry, id_of, put  # noqa: F401

DAY = date(2026, 11, 6)
TABLE = """# Vocabulary: {title}

Words looked up while reading (added with 加入生词本 / Save word in the reading view).

| Word | Phonetic | 中文 Chinese | Page | Added |
|---|---|---|---|---|
{rows}"""


def library(tmp_path, books: dict[str, list[str]]):
    """books: {slug: ["| word | phonetic | zh | page | added |", ...]}"""
    path = tmp_path / "catalog.csv"
    for slug, rows in books.items():
        put(path, {"slug": slug, "title": slug.title(), "file": f"books/{slug}.pdf"})
        notes = tmp_path / "notes" / slug
        notes.mkdir(parents=True)
        (notes / "vocabulary.md").write_text(
            TABLE.format(title=slug, rows="\n".join(rows) + "\n"), encoding="utf-8"
        )
    return path


def test_words_from_every_book_one_card_each(tmp_path):
    path = library(tmp_path, {
        "a-book": ["| vignetting |  | 渐晕 | 16 | 2026-11-05 |",
                   "| Ordinate | 'ɒ:dineit | n. 纵线, 纵座标 | 27 | 2026-11-05 |"],
        "b-book": ["| ordinate |  |  | 3 | 2026-11-04 |"],
    })  # fmt: skip
    cards = vocab_review.cards(tmp_path, path, DAY)
    assert [c["word"] for c in cards] == ["Ordinate", "vignetting"]  # new: by when saved
    ordinate = cards[0]
    assert ordinate["zh"] == "n. 纵线, 纵座标" and ordinate["phonetic"] == "'ɒ:dineit"
    a, b = id_of(path, "a-book"), id_of(path, "b-book")
    assert [(s["id"], s["page"]) for s in ordinate["seen"]] == [(a, 27), (b, 3)]
    assert [s["title"] for s in ordinate["seen"]] == ["A-Book", "B-Book"]
    assert all(c["box"] == 0 and c["due"] == DAY.isoformat() for c in cards)


def test_knowing_a_word_brings_it_back_later_and_later(tmp_path):
    path = library(tmp_path, {"a-book": ["| modulus |  | 模数 | 33 | 2026-11-05 |"]})
    day, gaps = DAY, []
    for _ in range(4):
        result = vocab_review.answer(tmp_path, "modulus", True, day)
        next_day = date.fromisoformat(result["due"])
        gaps.append((next_day - day).days)
        assert vocab_review.due(vocab_review.cards(tmp_path, path, day), day) == []
        day = next_day
    assert gaps == [1, 3, 7, 14]
    assert vocab_review.summary(tmp_path, path, day)["learned"] == 1


def test_not_knowing_it_brings_it_back_tomorrow(tmp_path):
    path = library(tmp_path, {"a-book": ["| rigorous |  | 严格的 | 35 | 2026-11-05 |"]})
    for _ in range(3):
        vocab_review.answer(tmp_path, "rigorous", True, DAY)
    result = vocab_review.answer(tmp_path, "Rigorous", False, DAY)
    assert result["box"] == 1 and result["due"] == (DAY + timedelta(days=1)).isoformat()
    card = vocab_review.cards(tmp_path, path, DAY)[0]
    assert (card["right"], card["wrong"]) == (3, 1)
    # right on the second try the same day: still tomorrow, not three days later
    again = vocab_review.answer(tmp_path, "rigorous", True, DAY)
    assert again["box"] == 1 and again["due"] == (DAY + timedelta(days=1)).isoformat()
    tomorrow = DAY + timedelta(days=1)
    assert vocab_review.answer(tmp_path, "rigorous", True, tomorrow)["box"] == 2


def test_the_vocabulary_files_are_never_changed(tmp_path):
    path = library(tmp_path, {"a-book": ["| acronym |  | 首字母缩拼词 | 20 | 2026-11-05 |"]})
    vocab = tmp_path / "notes" / "a-book" / "vocabulary.md"
    before = vocab.read_text(encoding="utf-8")
    vocab_review.answer(tmp_path, "acronym", True, DAY)
    assert vocab.read_text(encoding="utf-8") == before
    assert vocab_review.state_path(tmp_path).exists()
    assert vocab_review.summary(tmp_path, path, DAY)["due"] == []
