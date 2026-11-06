"""📇 Review words: the words saved while reading (notes/<slug>/vocabulary.md), as cards
reviewed with spaced repetition.

Each word is one card, even when it was saved in several books. A card you knew comes back
later and later (BOX_DAYS: 1, 3, 7, 14, 30, 60 days); one you didn't know comes back tomorrow.
Progress is the library's notes/vocabulary-review.json ({word: {box, due, right, wrong}}), so
it's backed up with the notes. The vocabulary files themselves are never changed here.
"""

import re
from datetime import date, timedelta
from pathlib import Path

import catalog
import paths
import safe_io

LIBRARY = paths.LIBRARY
# Days until the next review, by box: 0 = new (due now), then one box up per right answer
BOX_DAYS = [0, 1, 3, 7, 14, 30, 60]
ROW_RE = re.compile(r"^\|(.+)\|\s*$")


def state_path(library: Path) -> Path:
    return library / "notes" / "vocabulary-review.json"


def _load_state(library: Path) -> dict:
    """Your progress. A damaged file is never taken for "no progress" (that would be saved over
    it): its previous version is used, else safe_io.DamagedFile says what to do."""
    return safe_io.load_json(state_path(library), {})


def read_vocabulary(text: str) -> list[dict]:
    """The rows of a vocabulary.md table: [{word, phonetic, zh, page, added}]."""
    rows = []
    for line in text.splitlines():
        m = ROW_RE.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in m[1].split("|")]
        if len(cells) < 5 or cells[0] in ("Word", "") or set(cells[0]) <= set("-: "):
            continue
        word, phonetic, zh, page, added = cells[:5]
        rows.append({"word": word, "phonetic": phonetic, "zh": zh, "page": page, "added": added})
    return rows


def cards(library: Path, catalog_path: Path, today: date | None = None) -> list[dict]:
    """Every saved word: {word, phonetic, zh, seen: [{slug, title, file, page}], box, due,
    right, wrong}, sorted by when it's due (new words by when they were saved)."""
    today = today or date.today()
    rows = catalog.load(catalog_path)
    state = _load_state(library)
    found: dict[str, dict] = {}
    for vocab in sorted((library / "notes").glob("*/vocabulary.md")):
        slug = vocab.parent.name
        book = rows.get(slug, {})
        for row in read_vocabulary(safe_io.read_text(vocab)):
            key = row["word"].lower()
            card = found.setdefault(
                key,
                {
                    "word": row["word"],
                    "phonetic": row["phonetic"],
                    "zh": row["zh"],
                    "added": row["added"],
                    "seen": [],
                },  # fmt: skip
            )
            card["phonetic"] = card["phonetic"] or row["phonetic"]
            card["zh"] = card["zh"] or row["zh"]
            card["added"] = min(card["added"] or row["added"], row["added"] or card["added"])
            card["seen"].append({
                "slug": slug,
                "title": book.get("title") or slug,
                "file": book.get("file", ""),
                "page": int(row["page"]) if row["page"].isdigit() else None,
            })  # fmt: skip
    for key, card in found.items():
        mine = state.get(key, {})
        card |= {
            "box": int(mine.get("box", 0)),
            "due": mine.get("due") or today.isoformat(),
            "right": int(mine.get("right", 0)),
            "wrong": int(mine.get("wrong", 0)),
        }
    return sorted(found.values(), key=lambda c: (c["due"], c["box"] > 0, c["added"], c["word"]))


def due(all_cards: list[dict], today: date | None = None) -> list[dict]:
    today_text = (today or date.today()).isoformat()
    return [c for c in all_cards if c["due"] <= today_text]


def answer(library: Path, word: str, knew: bool, today: date | None = None) -> dict:
    """Record an answer: knew -> one box up (later), didn't -> box 1 (tomorrow). Knowing it
    on the second try the same day (the page asks a missed word again) keeps it at box 1."""
    today = today or date.today()
    key = word.strip().lower()
    if not key:
        raise ValueError("no word")

    def record(state: dict) -> dict:
        card = state.get(key, {"box": 0, "right": 0, "wrong": 0})
        missed_today = card.get("missed") == today.isoformat()
        if not knew or missed_today:
            box = 1
        else:
            box = min(int(card.get("box", 0)) + 1, len(BOX_DAYS) - 1)
        card |= {
            "box": box,
            "due": (today + timedelta(days=BOX_DAYS[box])).isoformat(),
            "right": int(card.get("right", 0)) + knew,
            "wrong": int(card.get("wrong", 0)) + (not knew),
            "last": today.isoformat(),
        }
        if not knew:
            card["missed"] = today.isoformat()
        state[key] = card
        return {"word": word, "box": box, "due": card["due"]}

    # One answer at a time; notes/vocabulary-review.json.bak keeps the previous version
    return safe_io.update_json(state_path(library), record, {}, backup=True,
                               ensure_ascii=False, indent=1, sort_keys=True)  # fmt: skip


def summary(library: Path, catalog_path: Path, today: date | None = None) -> dict:
    """For the page: the cards due now, and how many words there are in all."""
    all_cards = cards(library, catalog_path, today)
    now = due(all_cards, today)
    return {
        "due": now,
        "total": len(all_cards),
        "learned": sum(c["box"] >= 4 for c in all_cards),  # right 4 times in a row or more
        "new": sum(c["box"] == 0 for c in now),
    }
