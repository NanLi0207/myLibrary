"""The subject of each book, paper or thesis, from a standard classification: OpenAlex's
(250 million works; 26 fields, about 4,500 topics, based on the Scopus subject areas).

A paper or thesis is looked up by its DOI; a book by its title (records whose title matches,
and whose authors do, if any are listed; several records, e.g. editions, are added up). The
result is a field ("Engineering") and a topic ("Railway Engineering and Dynamics") in the
catalog, and, when OpenAlex is sure of the topic, a shelf with that name (see shelves.py).

    uv run scripts/subjects.py            what every item's subject would be
    uv run scripts/subjects.py --apply    look up the items that have none yet, and shelve them
"""

import urllib.parse
from collections import defaultdict
from pathlib import Path

import book_meta
import catalog
import paths
import safe_io
from book_meta import _words, surname

LIBRARY = paths.LIBRARY
SURE = 0.5  # OpenAlex's score (0-1) above which a topic becomes a shelf
VOTE = 0.3  # an item OpenAlex doesn't know: the least share of similar works on one topic
# The 26 fields, with their Chinese names (shown "中文 English" on the library page)
FIELDS_ZH = {
    "Agricultural and Biological Sciences": "农业与生物科学",
    "Arts and Humanities": "艺术与人文",
    "Biochemistry, Genetics and Molecular Biology": "生物化学、遗传学与分子生物学",
    "Business, Management and Accounting": "商业、管理与会计",
    "Chemical Engineering": "化学工程",
    "Chemistry": "化学",
    "Computer Science": "计算机科学",
    "Decision Sciences": "决策科学",
    "Dentistry": "牙医学",
    "Earth and Planetary Sciences": "地球与行星科学",
    "Economics, Econometrics and Finance": "经济学、计量经济学与金融",
    "Energy": "能源",
    "Engineering": "工程",
    "Environmental Science": "环境科学",
    "Health Professions": "卫生职业",
    "Immunology and Microbiology": "免疫学与微生物学",
    "Materials Science": "材料科学",
    "Mathematics": "数学",
    "Medicine": "医学",
    "Neuroscience": "神经科学",
    "Nursing": "护理学",
    "Pharmacology, Toxicology and Pharmaceutics": "药理学、毒理学与药剂学",
    "Physics and Astronomy": "物理学与天文学",
    "Psychology": "心理学",
    "Social Sciences": "社会科学",
    "Veterinary": "兽医学",
}


def field_label(field: str) -> str:
    """'Engineering' -> '工程 Engineering'."""
    return f"{FIELDS_ZH[field]} {field}" if field in FIELDS_ZH else field


def _topics(work: dict) -> list[tuple[str, str, float]]:
    """[(topic, field, score)] of an OpenAlex work."""
    return [
        (
            t.get("display_name", ""),
            (t.get("field") or {}).get("display_name", ""),
            t.get("score") or 0,
        )
        for t in work.get("topics") or []
        if t.get("display_name")
    ]


def _same_title(a: str, b: str) -> bool:
    """The same title, apart from a subtitle or edition note on one side."""
    wa, wb = _words(book_meta.clean_title(a)), _words(book_meta.clean_title(b))
    short, long = (wa, wb) if len(wa) <= len(wb) else (wb, wa)
    return len(short) >= 2 and long[: len(short)] == short


def lookup(row: dict) -> dict:
    """{field, topic, score, source} for a catalog row ({} if OpenAlex doesn't know it).
    Raises book_meta.Unavailable when OpenAlex couldn't answer (e.g. its daily limit)."""
    found: list[tuple[str, str, float]] = []
    source = ""
    if doi := (row.get("doi") or "").strip():
        work = book_meta._get_json(
            "https://api.openalex.org/works/doi:" + urllib.parse.quote(doi, safe="/"), strict=True
        )
        if work:
            found, source = _topics(work), f"OpenAlex (DOI {doi})"
    if not found and row.get("title"):
        query = urllib.parse.quote(book_meta.clean_title(row["title"])[:150])
        results = (book_meta._get_json(
            f"https://api.openalex.org/works?per-page=15&select=title,authorships,topics&search={query}",
            strict=True,
        ) or {}).get("results") or []  # fmt: skip
        author = surname(row.get("authors", "")) if row.get("authors") else ""
        for work in results:
            names = " ".join(
                a.get("author", {}).get("display_name", "") for a in work.get("authorships") or []
            )
            same_author = not author or author == "unknown" or not names or author in _words(names)
            if _same_title(work.get("title") or "", row["title"]) and same_author:
                found += _topics(work)  # every matching record (editions, chapters) adds up
        source = "OpenAlex (title search)" if found else ""
    if not found:
        return similar_works(row)
    totals: dict[tuple[str, str], float] = defaultdict(float)
    for topic, field, score in found:
        totals[(topic, field)] += score
    (topic, field), best = max(totals.items(), key=lambda kv: kv[1])
    return {"topic": topic, "field": field, "score": round(best / sum(totals.values()), 2),
            "source": source}  # fmt: skip


def similar_works(row: dict) -> dict:
    """An item OpenAlex has no record of (a report, a small publisher's book): the topic most
    of the works found for its title and keywords are about; its score is their share
    (e.g. 0.72 = 72% of them). {} if they don't agree enough (VOTE)."""
    query = " ".join([book_meta.clean_title(row.get("title", "")).split(" - ")[0],
                      row.get("keywords", "").replace(";", " ")]).strip()  # fmt: skip
    if len(_words(query)) < 2:
        return {}
    results = (book_meta._get_json(
        "https://api.openalex.org/works?per-page=10&select=topics&search="
        + urllib.parse.quote(query[:200]),
        strict=True,
    ) or {}).get("results") or []  # fmt: skip
    votes: dict[tuple[str, str], float] = defaultdict(float)
    for work in results:
        for name, field, score in _topics(work)[:1]:  # each work's main topic
            votes[(name, field)] += score
    if len(results) < 5 or not votes:
        return {}
    (topic, field), best = max(votes.items(), key=lambda kv: kv[1])
    share = round(best / sum(votes.values()), 2)
    if share < VOTE:
        return {}
    return {"topic": topic, "field": field, "score": share, "source": "OpenAlex (similar works)"}


# Items already looked up without result, so Refresh doesn't ask OpenAlex again every time
def _tried(library: Path) -> Path:
    return library / ".cache" / "subjects_tried.json"


def classify(doc_id: str, library: Path, catalog_path: Path) -> dict:
    """Look up an item's subject and record it (catalog columns field, topic). Returns it.
    Raises book_meta.Unavailable when OpenAlex couldn't answer: the item isn't marked as
    tried then, so the next Refresh asks again."""
    row = catalog.load(catalog_path).get(doc_id)
    if not row:
        return {}
    found = lookup(row)
    if found:
        subject = {
            "field": found["field"],
            "topic": found["topic"],
            "topic_score": str(found["score"]),
        }
        catalog.update(catalog_path, doc_id, subject)
    else:

        def add(known: list) -> None:
            known[:] = sorted(set(known) | {doc_id})

        # A cache: if it's ever damaged it starts again (those items are just asked again)
        safe_io.update_json(_tried(library), add, [], cache=True)
    return found


def unclassified(library: Path, catalog_path: Path) -> list[str]:
    """Items with no subject yet, not already looked up in vain."""
    known = set(safe_io.load_json(_tried(library), [], cache=True))
    return [
        s for s, r in catalog.load(catalog_path).items() if not r.get("topic") and s not in known
    ]


def _main() -> None:
    import argparse
    import sys

    import shelves

    sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    paths.add_argument(parser)
    parser.add_argument("--apply", action="store_true", help="record subjects and shelve the items")
    args = parser.parse_args()
    paths.refuse_frozen()  # never the showcase library/ or test_library/ (paths.FROZEN)
    catalog_path = LIBRARY / "catalog.csv"
    for doc_id, row in catalog.load(catalog_path).items():
        if row.get("topic"):  # already known
            found = {"field": row["field"], "topic": row["topic"], "score": row["topic_score"]}
        elif args.apply:
            found = classify(doc_id, LIBRARY, catalog_path)
        else:
            found = lookup(row)
        if args.apply:
            shelves.add_topic_shelf(doc_id, catalog_path)
        print(f"{row['title'][:44]:44} | {found.get('field', '-')[:22]:22} | "
              f"{found.get('topic', '-')[:44]:44} | {found.get('score', '')}")  # fmt: skip


if __name__ == "__main__":
    _main()
