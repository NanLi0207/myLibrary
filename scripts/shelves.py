"""Suggest shelves for a new book, paper or thesis, the way you have shelved the others.

Only your own shelves (library.toml's [shelves] and any shelf already used in catalog.csv) are
ever suggested; a new one is never made up. A shelf is suggested when:
  1. its name is in the item's details: "lens design" in the title, "laser" in the keywords
     (any form: "lasers", "opto-mechanical" for Optomechanics);
  2. or the item is much like what's already on it (a shelf with at least two items): it shares
     the words typical of that shelf (more common there than in the rest of the library);
  3. or, for the shelf of a subject glossary (its label, e.g. "光学 Optics"), the item uses
     several of that glossary's specialist terms ("focal length", "diffraction"; not everyday
     words such as "field" or "window").
Then shelves that always come together come together: if everything on Lens design (at least
three items) is also on Optics, a new Lens design book goes on Optics too.
Only the item's details are used (title, keywords, subjects, journal); no book text is read.
"""

import csv
import math
import re
import tomllib
from collections import Counter
from pathlib import Path

import catalog
import paths

LIBRARY = paths.LIBRARY
FIELDS = ("title", "keywords", "subjects", "journal")  # what an item is about
STOP = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "of",
    "to",
    "in",
    "for",
    "on",
    "with",
    "by",
    "at",
    "from",
    "as",
    "its",
    "their",
    "into",
    "using",
    "via",
    "based",
    "new",
    "study",
    "analysis",
    "approach",
    "review",
    "introduction",
    "volume",
    "vol",
    "part",
    "edition",
    "ed",
    "proceedings",
    "proc",
    "journal",
    "international",
    "conference",
    "society",
    "spie",
    "research",
    "results",
    "engineering",
    "science",
    "applied",
    "applications",
    "application",
    "method",
    "methods",
    "system",
    "systems",
    "design",
    "development",
    "evaluation",
    "comprehensive",
    "state",
    "art",
}  # fmt: skip  ("design" is common to everything; "Lens design" still matches by its name)
SIMILAR = 0.25  # how typical of a shelf (0-1) an item's words must be
GLOSSARY_TERMS = 2  # distinct glossary terms needed for a glossary's shelf
LESS_SURE = 0.3  # a less sure subject still beats no shelf at all
CLOSEST = 0.08  # the least similarity for the last resort (closest_shelf)
ALWAYS_TOGETHER = 0.9  # share of a shelf's items also on another one, for "always together"


def stem(word: str) -> str:
    """'lasers' -> 'laser', 'optical'/'optics' -> 'optic', 'optomechanics' -> 'optomechan',
    'materials' -> 'material'; 'lensing' stays 'lensing' (not the same as 'lens')."""
    for suffix in ("ically", "ical", "ics", "ies", "es", "al", "s"):  # not "ing": lensing != lens
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return word


def tokens(text: str) -> list[str]:
    """Stemmed words, without stop words; hyphenated words also joined ("opto-mechanical"
    gives "opto", "mechan" and "optomechan")."""
    text = text.lower()
    joined = [w.replace("-", "") for w in re.findall(r"[a-z]+(?:-[a-z]+)+", text)]
    words = re.findall(r"[a-z][a-z0-9]+", text) + joined
    return [stem(w) for w in words if w not in STOP and len(w) > 2]


def about(row: dict) -> str:
    return " ".join(str(row.get(k) or "") for k in FIELDS)


def shelf_names(library: Path | None = None, catalog_path: Path | None = None) -> list[str]:
    """Your shelves: library.toml's, then any others used in the catalog."""
    library = library or LIBRARY
    names = []
    config = library / "library.toml"
    if config.exists():
        with open(config, "rb") as f:
            names = [str(k) for k in (tomllib.load(f).get("shelves") or {})]
    for row in catalog.load(catalog_path or library / "catalog.csv").values():
        for shelf in catalog.split_list(row.get("shelves") or ""):
            if shelf.lower() not in (n.lower() for n in names):
                names.append(shelf)
    return names


def _glossaries(library: Path, names: list[str]) -> dict[str, list[str]]:
    """{shelf name: glossary terms} for glossaries whose label or name is a shelf's."""
    folder = library / "glossaries"
    if not folder.is_dir():
        return {}
    config = {}
    if (folder / "glossaries.toml").exists():
        with open(folder / "glossaries.toml", "rb") as f:
            config = tomllib.load(f)
    labels = {}
    if (library / "library.toml").exists():
        with open(library / "library.toml", "rb") as f:
            configured = tomllib.load(f).get("shelves") or {}
        labels = {str(v).lower(): str(k) for k, v in configured.items()}
    shelves = {n.lower(): n for n in names}
    found = {}
    for path in folder.glob("*.csv"):
        settings = config.get(path.stem) if isinstance(config.get(path.stem), dict) else {}
        label = str(settings.get("label") or "").lower()
        # The shelf with that label ("光学 Optics"), or named like the glossary ("optics")
        english = label.split()[-1] if label else ""
        shelf = labels.get(label) or shelves.get(path.stem.lower()) or shelves.get(english)
        if shelf:
            with open(path, encoding="utf-8-sig", newline="") as f:
                terms = [(r.get("term") or "").strip().lower() for r in csv.DictReader(f)]
            # Specialist terms only: several words, or one long word ("diffraction")
            found[shelf] = [t for t in terms if " " in t or len(t) >= 8]
    return found


def _share(word: str, group: list[set]) -> float:
    """The share of items in `group` that use `word`."""
    return sum(word in words for words in group) / len(group) if group else 0.0


def similarity(row: dict, rows: list[dict], names: list[str]) -> dict[str, tuple[float, int]]:
    """{shelf: (score, shared typical words)}: how much `row` is like what's on each shelf
    (shelves with at least two items). A word counts as much as it's more common on that shelf
    than in the rest of the library, rare words most ("optic", on everything here, says
    nothing)."""
    mine = set(tokens(about(row)))
    shelved = [
        (set(tokens(about(r))), set(catalog.split_list(r.get("shelves") or ""))) for r in rows
    ]
    if not mine or not shelved:
        return {}
    seen = Counter(t for words, _ in shelved for t in words)
    idf = {t: math.log((len(shelved) + 1) / (seen[t] + 1)) + 1 for t in mine}
    scores = {}
    for shelf in names:
        members = [words for words, on in shelved if shelf in on]
        others = [words for words, on in shelved if shelf not in on]
        if len(members) < 2:  # one item is too little to learn a shelf from
            continue
        typical = {t: max(0.0, _share(t, members) - _share(t, others)) for t in mine}
        score = sum(idf[t] * typical[t] for t in mine) / sum(idf.values())
        scores[shelf] = (score, sum(v > 0 for v in typical.values()))
    return scores


def closest_shelf(row: dict, rows: list[dict], names: list[str]) -> str:
    """Last resort for an item on no shelf: the shelf it's most like, if it shares at least two
    typical words with it and clearly leads (twice the next one's score); else ""."""
    ranked = sorted(similarity(row, rows, names).items(), key=lambda kv: -kv[1][0])
    if not ranked:
        return ""
    best, (score, shared) = ranked[0]
    runner_up = ranked[1][1][0] if len(ranked) > 1 else 0.0
    return best if score >= CLOSEST and shared >= 2 and score >= 2 * runner_up else ""


def suggest(
    row: dict, rows: list[dict], library: Path | None = None, catalog_path: Path | None = None
) -> list[str]:
    """Shelves for `row` (a catalog row, or the same keys), from your other items `rows`."""
    library = library or LIBRARY
    names = shelf_names(library, catalog_path)
    text = about(row)
    mine = set(tokens(text))
    if not mine:
        return []
    shelved = [set(catalog.split_list(r.get("shelves") or "")) for r in rows]
    scores = similarity(row, rows, names)

    chosen = []
    for shelf in names:
        name_words = set(tokens(shelf))
        if name_words and name_words <= mine:  # 1. its name is in the details
            chosen.append(shelf)
            continue
        # 2. like what's on it, on more than one word (a short title such as "The art and
        # science of optical design" is too little to go on)
        score, shared = scores.get(shelf, (0.0, 0))
        if score >= SIMILAR and shared >= 2:
            chosen.append(shelf)
    # 3. a glossary's shelf, from its terms
    lowered = " " + " ".join(re.findall(r"[a-z0-9]+", text.lower())) + " "
    for shelf, terms in _glossaries(library, names).items():
        used = {t for t in terms if f" {t} " in lowered or f" {t}s " in lowered}
        if len(used) >= GLOSSARY_TERMS and shelf not in chosen:
            chosen.append(shelf)
    # Shelves that always come together
    for shelf in list(chosen):
        on = [s for s in shelved if shelf in s]
        if len(on) < 3:
            continue
        for other in names:
            if other not in chosen and sum(other in s for s in on) / len(on) >= ALWAYS_TOGETHER:
                chosen.append(other)
    return [n for n in names if n in chosen]  # in your order


def _sure_topic(row: dict, sure: float | None = None) -> str:
    """The item's subject topic, if OpenAlex is sure enough of it (default: subjects.SURE) to
    make it a shelf."""
    import subjects

    try:
        score = float(row.get("topic_score") or 0)
    except ValueError:
        score = 0.0
    needed = subjects.SURE if sure is None else sure
    return row.get("topic", "") if row.get("topic") and score >= needed else ""


def add_topic_shelf(doc_id: str, catalog_path: Path) -> str:
    """Put an item on its subject's shelf too (keeping its other shelves). Returns the shelf."""
    row = catalog.load(catalog_path).get(doc_id) or {}
    topic = _sure_topic(row)
    on = catalog.split_list(row.get("shelves") or "")
    if not topic or topic in on:
        return ""
    catalog.set_field(catalog_path, doc_id, "shelves", "; ".join(on + [topic]))
    return topic


def auto_shelve(doc_id: str, library: Path, catalog_path: Path) -> list[str]:
    """Put a newly added item on shelves, if it's on none yet: its subject's shelf (when
    OpenAlex is sure of it, a new shelf if need be), and your own shelves that fit it. Without
    a known subject, the shelves whose items it's most like (subject shelves included)."""
    rows = catalog.load(catalog_path)
    row = rows.get(doc_id)
    if not row or catalog.split_list(row.get("shelves") or ""):
        return []
    others = [r for s, r in rows.items() if s != doc_id]
    topic = _sure_topic(row)
    found = suggest(row, others, library, catalog_path)
    if topic:  # its own subject, and of the rest only your own shelves (not other subjects)
        subjects_used = {r.get("topic") for r in others if r.get("topic")}
        found = [topic] + [s for s in found if s not in subjects_used and s != topic]
    if not found and (fallback := _sure_topic(row, LESS_SURE)):
        found = [fallback]  # nothing else fits: its subject, though OpenAlex is less sure
    if not found and (closest := closest_shelf(row, others, shelf_names(library, catalog_path))):
        found = [closest]  # last resort: the shelf it's clearly most like
    if found:
        catalog.set_field(catalog_path, doc_id, "shelves", "; ".join(found))
    return found


def _main() -> None:
    """uv run scripts/shelves.py           what it would suggest for each item, next to yours
    uv run scripts/shelves.py --apply   put the items that are on no shelf on the suggested ones
    """
    import argparse
    import sys

    sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=_main.__doc__)
    paths.add_argument(parser)
    parser.add_argument("--apply", action="store_true", help="shelve the items on no shelf")
    args = parser.parse_args()
    catalog_path = LIBRARY / "catalog.csv"
    rows = catalog.load(catalog_path)
    print(f"{'YOUR SHELVES':30} | {'SUGGESTED':30} | TITLE")
    for doc_id, row in rows.items():
        others = [r for s, r in rows.items() if s != doc_id]
        found = "; ".join(suggest(row, others)) or "-"
        print(f"{row.get('shelves') or '-':30.30} | {found:30.30} | {row['title'][:60]}")
    if args.apply:
        done = [s for s in rows if auto_shelve(s, LIBRARY, catalog_path)]
        print(f"\nPut {len(done)} item(s) on shelves; change any with Shelves on the library page.")


if __name__ == "__main__":
    _main()
