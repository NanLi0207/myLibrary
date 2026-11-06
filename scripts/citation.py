"""Citations for a book, paper or thesis in catalog.csv: the "Cite" menu on the library page.

APA (7th ed.), IEEE, GB/T 7714-2015 (the Chinese national standard), BibTeX and RIS
(EndNote, Zotero, Mendeley). Each made from the catalog row; books, papers and theses differ.
"""

import re

from book_meta import ascii_words, surname

STOP = {"a", "an", "the", "of", "on", "in", "and", "for", "to", "with"}
PARTICLES = {"de", "van", "von", "der", "den", "del", "da", "di", "la", "le", "du", "ter"}
# The menu's formats, in order: (key, label shown)
FORMATS = [
    ("apa", "APA"),
    ("ieee", "IEEE"),
    ("gbt", "GB/T 7714 (中国国标 Chinese standard)"),
    ("bibtex", "BibTeX"),
    ("ris", "RIS (EndNote, Zotero, Mendeley)"),
]


def authors(value: str) -> list[str]:
    """'A. Smith; B. Lee' or 'Julie Bentley, Craig Olson' -> one name each.
    'Shannon, Robert' (surname first) and 'Smith W.J.' stay one name."""
    if ";" in value:
        parts = value.split(";")
    else:
        parts = value.split(",")
        if not all(" " in p.strip() for p in parts):  # "Shannon, Robert": one person
            parts = [value]
    return [" ".join(p.split()) for p in parts if p.strip()]


def split_name(name: str) -> tuple[str, str]:
    """(given names, family name): 'Jane Doe', 'Doe, Jane', 'Smith W.J.', 'Mattie De Meester'."""
    name = " ".join(name.split())
    if "," in name:
        family, given = (x.strip() for x in name.split(",", 1))
        return given, family
    parts = name.split()
    if len(parts) > 1 and all(re.fullmatch(r"(?:[A-Z]\.?-?)+", p) for p in parts[1:]):
        return " ".join(parts[1:]), parts[0]  # "Smith W.J.": family name first
    given, family = parts[:-1], parts[-1:]
    while given and given[-1].lower() in PARTICLES:  # "De Meester", "van der Waals"
        family.insert(0, given.pop())
    return " ".join(given), " ".join(family)


def initials(given: str, dot: str = ".", space: str = " ") -> str:
    """'Jane' -> 'J.'; 'Che-Ming' -> 'C.-M.'; 'W.J.' -> 'W. J.'; dot="" and space=" " -> 'J'."""
    out = []
    for part in re.findall(r"[^\s.]+", given):
        out.append("-".join(p[0].upper() + dot for p in part.split("-") if p))
    return space.join(out)


def _people(row: dict) -> list[tuple[str, str]]:
    return [split_name(a) for a in authors(row.get("authors", ""))]


def _pages(row: dict, dash: str = "–") -> str:
    return row.get("page_range", "").replace("-", dash)


def _lead(who: str, sep: str) -> str:
    """The authors and their separator, or nothing for a work without authors."""
    return f"{who}{sep}" if who else ""


def _is_paper(row: dict) -> bool:
    return row.get("type") == "paper"


def _is_thesis(row: dict) -> bool:
    return row.get("type") == "thesis"


# How each style names a thesis, by degree: (APA, IEEE)
THESIS_NAMES = {
    "PhD": ("Doctoral dissertation", "Ph.D. dissertation"),
    "Master": ("Master's thesis", "M.S. thesis"),
    "Bachelor": ("Bachelor's thesis", "B.S. thesis"),
    "Diploma": ("Diploma thesis", "Diploma thesis"),
}


def _thesis_name(row: dict, style: int) -> str:
    return THESIS_NAMES.get(row.get("degree", ""), ("Thesis", "Thesis"))[style]


# --- APA (7th edition) ----------------------------------------------------------------------------


def apa(row: dict) -> str:
    names = [f"{family}, {initials(given)}".rstrip(", ") for given, family in _people(row)]
    if len(names) > 20:
        names = names[:19] + ["…", names[-1]]
    if len(names) == 1:
        who = names[0]
    elif len(names) == 2:
        who = f"{names[0]}, & {names[1]}"
    else:
        who = ", ".join(names[:-1]) + (f", & {names[-1]}" if names else "")
    year = row.get("year") or "n.d."
    title = row.get("title", "")
    if not names:  # APA: no author, so the title comes first
        who, title = title, ""
    doi = f" https://doi.org/{row['doi']}" if row.get("doi") else ""
    where = ""
    if _is_paper(row):
        where = row.get("journal", "")
        if row.get("volume"):
            where += f", {row['volume']}" + (f"({row['issue']})" if row.get("issue") else "")
        if row.get("page_range"):
            where += f", {_pages(row)}"
    if _is_thesis(row):  # Doe, J. (2011). Title [Doctoral dissertation, University]. DOI
        where = ", ".join(filter(None, (_thesis_name(row, 0), row.get("institution", ""))))
        return f"{who} ({year})." + (f" {title}" if title else "") + f" [{where}].{doi}"
    head = f"{who} ({year})." + (f" {title}." if title else "")
    if _is_paper(row):
        return f"{head} {where}.{doi}" if where else f"{head}{doi}"
    publisher = f" {row['publisher']}." if row.get("publisher") else ""
    return f"{head}{publisher}{doi}"


# --- IEEE -----------------------------------------------------------------------------------------


def ieee(row: dict) -> str:
    names = [f"{initials(given)} {family}".strip() for given, family in _people(row)]
    if len(names) > 6:
        who = f"{names[0]} et al."
    elif len(names) <= 2:
        who = " and ".join(names)
    else:
        who = ", ".join(names[:-1]) + f", and {names[-1]}"
    title, year = row.get("title", ""), row.get("year", "")
    if _is_thesis(row):  # J. Doe, "Title," Ph.D. dissertation, University, 2011.
        parts = [_thesis_name(row, 1), row.get("institution", ""), year]
        return f'{_lead(who, ", ")}"{title}," ' + ", ".join(p for p in parts if p) + "."
    if not _is_paper(row):
        publisher = f" {row['publisher']}," if row.get("publisher") else ""
        return f"{_lead(who, ', ')}{title}.{publisher} {year}."
    parts = [row.get("journal", "")]
    if row.get("volume"):
        parts.append(f"vol. {row['volume']}")
    if row.get("issue"):
        parts.append(f"no. {row['issue']}")
    pages = row.get("page_range", "")
    if pages:  # a range is pages; a single number is an article number (e.g. MDPI)
        parts.append(f"pp. {_pages(row)}" if "-" in pages else f"Art. no. {pages}")
    parts.append(year)
    # IEEE puts the comma inside the quotes: …, "Title," Journal, vol. 6, …
    text = f'{_lead(who, ", ")}"{title}," ' + ", ".join(p for p in parts if p)
    return text + (f", doi: {row['doi']}." if row.get("doi") else ".")


# --- GB/T 7714-2015 -------------------------------------------------------------------------------


def gbt(row: dict) -> str:
    """The Chinese national standard: 'DOE J, ZHANG W. Title[J]. Journal, 2019, 27(8): 1-9.'"""
    people = _people(row)
    names = [f"{family.upper()} {initials(given, dot='')}".strip() for given, family in people[:3]]
    who = ", ".join(names) + (", et al" if len(people) > 3 else "")
    title, year = row.get("title", ""), row.get("year", "")
    if _is_thesis(row):  # [D]: 学位论文 (thesis)
        school = f"{row['institution']}, " if row.get("institution") else ""
        return f"{_lead(who, '. ')}{title}[D]. {school}{year}."
    if not _is_paper(row):
        publisher = f"{row['publisher']}, " if row.get("publisher") else ""
        return f"{_lead(who, '. ')}{title}[M]. {publisher}{year}."
    where = f"{row.get('journal', '')}, {year}"
    if row.get("volume"):
        where += f", {row['volume']}" + (f"({row['issue']})" if row.get("issue") else "")
    if row.get("page_range"):
        where += f": {_pages(row, '-')}"
    doi = f" DOI:{row['doi']}." if row.get("doi") else ""
    return f"{_lead(who, '. ')}{title}[J]. {where}.{doi}"


# --- BibTeX (LaTeX) -------------------------------------------------------------------------------


def _escape(text: str) -> str:
    return re.sub(r"([&%$#_])", r"\\\1", " ".join(text.split()))


def bibtex(row: dict) -> str:
    title, year = row.get("title", ""), row.get("year", "")
    first_word = next((w for w in ascii_words(title) if w not in STOP), "untitled")
    key = f"{surname(row.get('authors', ''))}{year}{first_word}"
    is_paper, is_thesis = _is_paper(row), _is_thesis(row)
    degree = row.get("degree", "")
    fields = {
        "author": " and ".join(_escape(a) for a in authors(row.get("authors", ""))),
        "title": "{" + _escape(title) + "}",  # keep its capitals
        "journal": _escape(row.get("journal", "")) if is_paper else "",
        "school": _escape(row.get("institution", "")) if is_thesis else "",
        # @mastersthesis also serves bachelor's and diploma theses, with their own type
        "type": _thesis_name(row, 0) if is_thesis and degree in ("Bachelor", "Diploma") else "",
        "year": year,
        "volume": row.get("volume", ""),
        "number": row.get("issue", ""),
        "pages": row.get("page_range", "").replace("-", "--"),
        "publisher": "" if is_paper else _escape(row.get("publisher", "")),
        "isbn": "" if is_paper else row.get("isbn", ""),
        "doi": row.get("doi", ""),
    }
    kind = "article" if is_paper and fields["journal"] else ("misc" if is_paper else "book")
    if is_thesis:
        kind = "phdthesis" if degree == "PhD" else ("mastersthesis" if degree else "phdthesis")
    lines = [f"  {name} = {{{value}}}," for name, value in fields.items() if value]
    return f"@{kind}{{{key},\n" + "\n".join(lines) + "\n}"


# --- RIS (EndNote, Zotero, Mendeley import) -------------------------------------------------------


def ris(row: dict) -> str:
    is_paper, is_thesis = _is_paper(row), _is_thesis(row)
    lines = [f"TY  - {'JOUR' if is_paper else 'THES' if is_thesis else 'BOOK'}"]
    lines += [f"AU  - {family}, {given}".rstrip(", ") for given, family in _people(row)]
    first, _, last = row.get("page_range", "").partition("-")
    for tag, value in (
        ("TI", row.get("title")),
        ("JO", row.get("journal") if is_paper else ""),
        ("PY", row.get("year")),
        ("VL", row.get("volume")),
        ("IS", row.get("issue")),
        ("SP", first),
        ("EP", last),
        ("PB", row.get("institution") if is_thesis else "" if is_paper else row.get("publisher")),
        ("M3", _thesis_name(row, 0) if is_thesis else ""),
        ("SN", "" if is_paper else row.get("isbn")),
        ("DO", row.get("doi")),
    ):
        if value:
            lines.append(f"{tag}  - {value}")
    return "\n".join(lines + ["ER  - "])


def all_formats(row: dict) -> list[dict]:
    """[{key, label, text}] in menu order."""
    makers = {"apa": apa, "ieee": ieee, "gbt": gbt, "bibtex": bibtex, "ris": ris}
    return [{"key": k, "label": label, "text": makers[k](row)} for k, label in FORMATS]
