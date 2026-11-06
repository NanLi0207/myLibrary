"""Recognise a thesis (PhD, master's, bachelor's, diploma) and read its details.

A thesis says what it is on its title page, in a formula every university uses: "A thesis
submitted ... for the degree of Doctor of Philosophy", "Dissertation zur Erlangung des
Doktorgrades", "Proefschrift ter verkrijging van de graad van doctor", "Master Thesis",
"博士学位论文". find_title_page() looks for that page among the first pages.

Its details, most trusted first:
  1. a DOI on the first pages: Crossref, else DataCite (most university repositories)
  2. an arXiv number: arXiv (whose comment often says "PhD thesis")
  3. OpenAlex, which lists millions of theses from university repositories, searched with the
     title on the title page (accepted only if its whole title is on that page)
  4. the title page itself: the title (its largest text), author ("by" / "vorgelegt von" /
     "door"), year, degree, university and supervisors
The page always gives the degree and supervisors, and its printed year and spelling win when
they agree with what's online. Only metadata is read; no thesis text is stored anywhere.
"""

import math
import re
import urllib.parse
from dataclasses import dataclass
from datetime import date

import book_meta  # its lookups (crossref, arxiv, _get_json) are called through the module
from book_meta import Meta, _best_match, _words, clean_title, find_dois, looks_like_name, surname

# Formulas that only a thesis title page uses (English, German, Dutch, French, Spanish, Italian,
# Swedish, Chinese). A page counts when it is sparse (a title page, not a paper's first page)
# or has a line that just says what it is ("Master Thesis", "Dissertation").
SIGNALS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(?:ph\.?\s?d\.?|doctoral|master'?s?|bachelor'?s?|diploma|licentiate|research|"
        r"m\.?\s?sc\.?|b\.?\s?sc\.?|honou?rs)\s+(?:thesis|dissertation)\b",
        r"\b(?:thesis|dissertation)\s+(?:submitted|presented)\b",
        r"\bin\s+(?:partial\s+)?fulfil+ment\s+of\s+the\s+requirements?\b",
        r"\b(?:degree|title)\s+of\s+(?:doctor|master|bachelor|licentiate)\b",
        r"\bin\s+candidacy\s+for\s+the\s+degree\b",
        r"\b(?:doctor|master|bachelor)\s+of\s+(?:philosophy|science|engineering|arts)\b",
        r"\bzur\s+erlangung\s+(?:des|der)\b",
        r"\b(?:doktor|master|bachelor|diplom)arbeit\b",
        r"\bdoktor(?:grades?|s)\b|\bdoktor-ingenieur|\bakademischen\s+grades?\b",
        r"\bproefschrift\b|\bter\s+verkrijging\s+van\b|\bgraad\s+van\s+doctor\b",
        r"\bth[èe]se\s+(?:de\s+doctorat|pr[ée]sent[ée]e|soutenue)\b|\bdocteur\s+(?:de|en)\b",
        r"\bm[ée]moire\s+de\s+master\b|\btesis\s+doctoral\b|\btesi\s+di\s+(?:laurea|dottorato)\b",
        r"\bdoktorsavhandling\b|\blicentiatavhandling\b|\bexamensarbete\b",
        r"(?:博士|硕士|学士)(?:学位)?论文|学位论文|申请.{0,12}学位",
    )
]
# A line that only says what the document is
LABEL_LINE = re.compile(
    r"^(?:(?:a|an|the)\s+)?(?:(?:ph\.?\s?d\.?|doctoral|master'?s?|bachelor'?s?|diploma|research|"
    r"m\.?\s?sc\.?|b\.?\s?sc\.?|senior)\s+)?(?:thesis|dissertation)$|^(?:doktor|master|bachelor|"
    r"diplom)arbeit$|^proefschrift$|^th[èe]se(?:\s+de\s+doctorat)?$|^tesis(?:\s+doctoral)?$|"
    r"^(?:博士|硕士|学士)(?:学位)?论文$",
    re.IGNORECASE,
)
SPARSE_PAGE = 1500  # characters: a title page has little text, a paper's first page a lot

# The degree, most specific first (a German PhD candidate may be "M.Sc. Max Mustermann", and a
# master's thesis may name "Prof. Dr. X" as supervisor, so neither title counts)
DEGREES = [
    ("PhD", r"\bph\.?\s?d\b|\bdoctor\s+of\b|\bdegree\s+of\s+doctor\b|\bdoctoral\b|\bdoktor|"
            r"\bproefschrift\b|\bgraad\s+van\s+doctor\b|\bdoctorat\b|\bdocteur\b|"
            r"\btesis\s+doctoral\b|\bdottorato\b|\bdoktorsavhandling\b|博士"),
    ("Master", r"\bmaster'?s?\s+(?:thesis|dissertation)\b|\bmasterarbeit\b|"
               r"\bdegree\s+of\s+master\b|\bmaster\s+of\s+(?:science|engineering|arts)\b|"
               r"\bm\.?\s?sc\.?\s+thesis\b|\bm[ée]moire\s+de\s+master\b|\blaurea\s+magistrale\b|"
               r"\bexamensarbete\b|硕士"),
    ("Bachelor", r"\bbachelor'?s?\s+(?:thesis|dissertation)\b|\bbachelorarbeit\b|"
                 r"\bdegree\s+of\s+bachelor\b|\bbachelor\s+of\b|\bb\.?\s?sc\.?\s+thesis\b|学士"),
    ("Diploma", r"\bdiplomarbeit\b|\bdiploma\s+thesis\b"),
    ("PhD", r"\bdissertation\b"),  # alone: a doctoral thesis in most countries
]  # fmt: skip
DEGREE_RES = [(name, re.compile(p, re.IGNORECASE)) for name, p in DEGREES]
# How the library page and citations name each degree
DEGREE_LABELS = {
    "PhD": "PhD thesis",
    "Master": "Master's thesis",
    "Bachelor": "Bachelor's thesis",
    "Diploma": "Diploma thesis",
}

UNIVERSITY_WORDS = (
    r"University|Universität|Universitaet|Universiteit|Université|Universidad|Università|"
    r"Universitat|Universitet|Universidade|Uniwersytet|Hochschule|Polytechnic|Politecnico|"
    r"Technion|ETH|EPFL|KTH|Institute|Institut|College|École|Ecole|Academy|Akademie"
)
_CAP = r"[A-ZÀ-ÝĀ-Ž][\w.'’&-]*"
INSTITUTION_RE = re.compile(
    rf"((?:{_CAP}\s+){{0,4}}(?:{UNIVERSITY_WORDS})\b"
    rf"(?:\s+(?:of|for|für|de|der|di|du|des|van|zu|in)\s+(?:the\s+)?{_CAP}(?:\s+{_CAP}){{0,3}}"
    rf"|(?:\s+{_CAP}){{0,3}})?)"
)
CHINESE_INSTITUTION_RE = re.compile(r"[一-鿿]{2,15}(?:大学|学院|研究院|研究所)")
# Words before a university's name that aren't part of it ("Ph.D. Thesis University of Twente")
NOT_INSTITUTION = re.compile(
    r"^(?:(?:the|a|an|ph\.?d\.?|thesis|dissertation|master'?s?|doctoral|submitted|presented|"
    r"senate|faculty|graduate|school|department|dept\.?|bachelor'?s?|research)\s+)+",
    re.IGNORECASE,
)

# "by" and its translations: the author's name follows on the same line or the next one
AUTHOR_LABEL = re.compile(
    r"^(?:by|von|vorgelegt\s+von|eingereicht\s+von|door|par|presented\s+by|submitted\s+by|"
    r"written\s+by|author|candidate|autor(?:in)?|verfasser(?:in)?|作者(?:姓名)?|研究生(?:姓名)?|"
    r"申请人)\s*[:：]?\s*(.*)$",
    re.IGNORECASE,
)
SUPERVISOR_LABEL = re.compile(
    r"^(?:(?:academic|thesis|principal|main|first|research)\s+)?(?:supervisors?|advisors?|"
    r"advisers?)|^dissertation\s+(?:director|advisor|supervisor)|^(?:assistent-|co-?)?promotor(?:en)?|"
    r"^(?:erst|haupt)?gutachter(?:in)?|^(?:haupt)?referent(?:in)?|^betreuer(?:in)?|"
    r"^directeur(?:\s+de\s+th[èe]se)?|^relatore|^director\s+of\s+(?:thesis|research)|"
    r"^导师|^指导教师",
    re.IGNORECASE,
)
# Titles and degrees in front of a name: "M.Sc. Max Mustermann", "Dipl.-Phys. ..."
NAME_PREFIX = re.compile(
    r"^(?:(?:dipl\.?-?\w*\.?|m\.?\s?sc\.?|b\.?\s?sc\.?|m\.?\s?eng\.?|ir\.|drs\.|mr\.|ms\.|mrs\.)\s*)+",
    re.IGNORECASE,
)
# Lines that are never the title: dates, places with a year, arXiv stamps, page numbers
NOISE_LINE = re.compile(
    r"arxiv:|^\W*$|^[ivxlc\d]+$|copyright|©|all rights reserved|@|https?://|"
    r"\b(?:19|20)\d{2}\b|^(?:january|february|march|april|may|june|july|august|september|"
    r"october|november|december)\b",
    re.IGNORECASE,
)
LABEL_WORDS = re.compile(
    rf"\b(?:{UNIVERSITY_WORDS}|thesis|dissertation|degree|doctor|faculty|school|department|"
    r"fachbereich|fakultät|submitted|presented|requirements?|fulfil+ment|candidacy|"
    r"philosophy|supervisor|advisor|promotor|gutachter|betreuer|erlangung|vorgelegt|"
    r"proefschrift|verkrijging|graad|abstract|contents|acknowledg\w*|preface|dedicated)\b|"
    r"大学|学院|论文|学位|导师",
    re.IGNORECASE,
)


@dataclass
class TitlePage:
    index: int  # 0-based page number
    text: str
    score: int


def _lines(text: str) -> list[str]:
    return [" ".join(line.split()) for line in text.splitlines() if line.strip()]


def thesis_score(text: str) -> int:
    """How strongly a page says "thesis title page" (0: not at all)."""
    label = any(LABEL_LINE.match(line) for line in _lines(text))
    signals = sum(bool(s.search(text)) for s in SIGNALS)
    if not label and (not signals or len(text) > SPARSE_PAGE):
        return 0
    return signals + 2 * label


def find_title_page(texts: list[str], pages: int = 8) -> TitlePage | None:
    """The title page of a thesis among the first pages, or None if it isn't a thesis."""
    best = None
    for index, text in enumerate(texts[:pages]):
        if (score := thesis_score(text)) and (not best or score > best.score):
            best = TitlePage(index, text, score)
    return best


def degree(text: str) -> str:
    """'PhD', 'Master', 'Bachelor', 'Diploma', or '' if the text doesn't say."""
    return next((name for name, pattern in DEGREE_RES if pattern.search(text)), "")


def degree_label(value: str) -> str:
    """'PhD' -> 'PhD thesis'; '' -> 'Thesis'."""
    return DEGREE_LABELS.get(value, "Thesis")


def institution(text: str) -> str:
    """The university on a title page, e.g. 'Universität Dortmund', '清华大学'."""
    found = []
    for line in _lines(text):
        for m in INSTITUTION_RE.finditer(line):
            name = NOT_INSTITUTION.sub("", m[1]).strip(" ,.;:-–—")
            if (
                re.search(UNIVERSITY_WORDS, name)
                and len(name.split()) >= 2
                or name
                in (
                    "ETH",
                    "EPFL",
                    "KTH",
                    "Technion",
                )
            ):
                found.append(name)
        found += CHINESE_INSTITUTION_RE.findall(line)
    # A university rather than an institute or college, when the page names both
    universities = [f for f in found if re.search(r"Univ|Hochschule|Polytech|大学", f)]
    return (universities or found or [""])[0]


def _clean_name(text: str) -> str:
    text = re.sub(r"\(.*?\)", "", text)  # "(Universiteit Twente)"
    text = re.split(r"\s+(?:aus|from|geb\.|geboren|born|née)\b|,\s*(?:born|geb)", text)[0]
    text = NAME_PREFIX.sub("", text.strip())
    text = re.sub(r"\s+\.", ".", text)  # "Prof. Dr . K. Niemax"
    return " ".join(text.split()).strip(" ,;:")


def _is_name(text: str) -> bool:
    """'Zeyu Kuang', 'M.F. Schneider', '张三' yes; 'Va n j a M a r g e t i·c', 'Yale University'
    no."""
    if re.fullmatch(r"[一-鿿]{2,4}", text):
        return True
    tokens = text.split()
    singles = [t for t in tokens if len(t) == 1]
    return (
        1 <= len(tokens) <= 6
        and len(singles) * 2 < len(tokens)  # not letter-spaced
        and looks_like_name(text)
        and not LABEL_WORDS.search(text)
        and not re.search(r"\d|[,:;]", text)
    )


def _labelled(lines: list[str], label: re.Pattern) -> list[str]:
    """The text after each label: on the same line ("by Jane Doe") or the next one."""
    found = []
    for i, line in enumerate(lines):
        if m := label.match(line):
            rest = (m[1] if m.groups() else line[m.end() :]).strip(" :：")
            if not rest and i + 1 < len(lines):
                rest = lines[i + 1]
            found.append(_clean_name(rest))
    return found


def supervisors(text: str) -> str:
    """'Prof. Vincenzo Savona; ...' from "Supervisor:", "Promotor:", "Erstgutachter:" lines."""
    names = []
    for name in _labelled(_lines(text), SUPERVISOR_LABEL):
        name = re.sub(r"^[\s:：]+", "", name)
        if name and len(name) <= 80 and looks_like_name(name) and name not in names:
            names.append(name)
    return "; ".join(names[:3])


def page_lines(page) -> list[tuple[float, str, float]]:
    """(font size, text, height on the page) for each line of a PDF page, top to bottom; []
    if it can't be read."""
    fragments: list[tuple[float, float, str]] = []

    def visit(text, cm, tm, font, size):
        if text.strip() and size:
            scale = math.hypot(tm[2], tm[3]) * math.hypot(cm[2], cm[3])
            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
            fragments.append((y, size * scale, text))

    try:
        page.extract_text(visitor_text=visit)
    except Exception:
        return []
    lines: list[list] = []  # [y, size, text]
    for y, size, text in fragments:
        same = next((line for line in lines if abs(line[0] - y) <= 2), None)
        if same:
            same[1] = max(same[1], size)
            same[2] += text
        else:
            lines.append([y, size, text])
    lines.sort(key=lambda line: -line[0])
    return [(round(s, 1), " ".join(t.split()), y) for y, s, t in lines if t.strip()]


def _title_case(text: str) -> str:
    """'LASER CLADDING WITH POWDER' -> 'Laser Cladding with Powder' (other titles unchanged)."""
    if not text.isupper():
        return text
    small = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to",
             "with", "from", "into", "via"}  # fmt: skip
    words = text.lower().split()
    return " ".join(w if i and w in small else w[:1].upper() + w[1:] for i, w in enumerate(words))


def _is_title_line(line: str, author: str) -> bool:
    return (
        not LABEL_LINE.match(line)
        and not LABEL_WORDS.search(line)
        and not NOISE_LINE.search(line)
        and not AUTHOR_LABEL.match(line)
        and not SUPERVISOR_LABEL.match(line)
        and not (author and _words(line) == _words(author))
        and len(_words(line)) >= 1
    )


def title_on_page(text: str, sized: list, author: str = "") -> str:
    """The title: the largest text on the title page that isn't a label, the author, a date or
    the university. Without font sizes (e.g. an OCR'd page), the first lines at the top."""
    if sized:
        candidates = [(s, t, y) for s, t, y in sized if _is_title_line(t, author)]
        if candidates:
            biggest = max(s for s, _, _ in candidates)
            start = next(i for i, line in enumerate(sized) if line in candidates
                         and line[0] >= biggest - 0.5)  # fmt: skip
            size, first, y = sized[start]
            parts, last_y = [first], y
            for s, t, line_y in sized[start + 1 :]:
                if abs(s - size) > 0.5 or not _is_title_line(t, author):
                    break
                # A wide gap before a line of the same size: a subtitle
                gap = abs(last_y - line_y)
                parts.append((": " if gap > 2.2 * size else " ") + t)
                last_y = line_y
            title = re.sub(r"\s+:", ":", "".join(parts))
            if len(_words(title)) >= 2:
                return _title_case(title)
    lines = _lines(text)
    top = []
    for line in lines:
        if _is_title_line(line, author):
            top.append(line)
        elif top:
            break
    return _title_case(" ".join(top))


def author_on_page(text: str, title: str | None = None) -> str:
    """After "by" (or its translations); else, once the title is known, a line on its own
    that looks like a name (and isn't part of the title)."""
    lines = _lines(text)
    for name in _labelled(lines, AUTHOR_LABEL):
        if _is_name(name):
            return name
    if title is None:
        return ""
    after_label = {lines[i + 1] for i, line in enumerate(lines[:-1])
                   if SUPERVISOR_LABEL.match(line) or AUTHOR_LABEL.match(line)}  # fmt: skip
    title_words = set(_words(title))
    for line in lines:
        name = _clean_name(line)
        if (
            line not in after_label
            and not SUPERVISOR_LABEL.match(line)
            and not re.match(r"(?:prof|dr)\b", line, re.IGNORECASE)
            and not (title_words and set(_words(name)) <= title_words)
            and _is_name(name)
            and 2 <= len(name.split()) <= 4
        ):
            return name
    return ""


def printed_year(text: str) -> str:
    """The latest year on the title page (the defence or submission, not a birth date)."""
    this_year = date.today().year
    years = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", text) if int(y) <= this_year + 1]
    return str(max(years)) if years else ""


def read_title_page(page: TitlePage, sized: list, front: str) -> Meta:
    """What the title page (and the pages near it, `front`) say about the thesis."""
    meta = Meta(kind="thesis")
    author = author_on_page(page.text)
    title = title_on_page(page.text, sized, author)
    author = author or author_on_page(page.text, title)
    # The title page's title in title case, part by part ("LASER CLADDING: effect of ...")
    title = ": ".join(_title_case(part) for part in title.split(": "))
    meta.fill(
        f"title page (p. {page.index + 1})",
        title=title,
        author=author,
        year=printed_year(page.text),
        degree=degree(page.text) or degree(front),
        institution=institution(page.text) or institution(front),
        supervisors=supervisors(page.text) or supervisors(front),
    )
    return meta


# --- Online -------------------------------------------------------------------------------------


def doi_csl(doi: str) -> Meta:
    """A DOI's details from whichever registry holds it (DataCite for most university
    repositories, which Crossref doesn't know), via doi.org in the CSL format."""
    data = book_meta._get_json(
        f"https://doi.org/{urllib.parse.quote(doi, safe='/')}",
        headers={"Accept": "application/vnd.citationstyles.csl+json"},
    )
    meta = Meta(kind="thesis")
    if not data or not data.get("title"):
        return meta
    names = [
        " ".join(filter(None, (a.get("given"), a.get("family")))) or a.get("literal", "")
        for a in data.get("author") or []
    ]
    year = ((data.get("issued") or {}).get("date-parts") or [[None]])[0][0]
    contributors = [c.get("literal", "") for c in data.get("contributor") or []]
    meta.fill(
        f"DataCite (DOI {doi})",
        title=clean_title(str(data.get("title", ""))),
        author=book_meta.join_names(names),
        year=str(year or ""),
        institution=next((c for c in contributors if re.search(UNIVERSITY_WORDS, c)), "")
        or str(data.get("publisher") or ""),
        degree=degree(str(data.get("genre") or "")),
        doi=doi,
        url=f"https://doi.org/{doi}",
    )
    return meta


def doi_lookup(doi: str) -> Meta:
    """A DOI's details: Crossref, else DataCite (most university repositories)."""
    found = book_meta.crossref(doi)
    return found if found.title else doi_csl(doi)


def _source_institution(work: dict) -> str:
    """OpenAlex: the author's institution, else the repository's university in brackets,
    'Eldorado (Technische Universität Dortmund)' -> 'Technische Universität Dortmund'."""
    for authorship in work.get("authorships") or []:
        for inst in authorship.get("institutions") or []:
            if inst.get("display_name"):
                return inst["display_name"]
    source = ((work.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
    m = re.search(r"\(([^()]+)\)\s*$", source)
    return m[1] if m and re.search(UNIVERSITY_WORDS, m[1]) else ""


def openalex_thesis(queries: list[str], page_text: str) -> Meta:
    """OpenAlex's theses (from university repositories), searched with the title; a result
    counts only if its whole title is on the title page."""
    queries = [q for q in dict.fromkeys(queries) if len(_words(q)) >= 2][:4]
    work = book_meta.openalex_match(queries, page_text, filter_="type:dissertation")
    meta = Meta(kind="thesis")
    if not work:
        return meta
    doi = book_meta.openalex_doi(work)
    names = book_meta.openalex_names(work)
    meta.fill(
        "OpenAlex",
        title=clean_title(work.get("title") or ""),
        author=names[0] if names else "",  # a thesis has one author
        year=str(work.get("publication_year") or ""),
        institution=_source_institution(work),
        doi=doi,
        url=f"https://doi.org/{doi}" if doi else work.get("id", ""),
    )
    return meta


def _same_person(a: str, b: str) -> bool:
    return bool(a and b) and surname(a) == surname(b)


def identify_thesis(
    stem: str, texts: list[str], sized_of, online: bool = True, arxiv_id: str = ""
) -> Meta:
    """A thesis's details from its first pages (`texts`; `sized_of(i)` gives page i's lines
    with font sizes) and, when online, its DOI, arXiv number or OpenAlex."""
    page = find_title_page(texts) or TitlePage(
        next((i for i, t in enumerate(texts) if t.strip()), 0), next(iter(texts), ""), 0
    )
    front = "\n".join(texts[:8])
    local = read_title_page(page, sized_of(page.index) if texts else [], front)
    found = Meta()
    if online:
        # The thesis's own DOI is on its first pages; later pages cite other works
        for doi in find_dois(stem + " " + "\n".join(texts[:3]))[:2]:
            found = doi_lookup(doi)
            # Its own DOI only if the title it gives is the one on these pages
            if found.title and _best_match(front, [(found.title, found.year, True)]):
                break
            found = Meta()
        if not found.title and arxiv_id:
            found = book_meta.arxiv(arxiv_id)
        if not found.title:
            queries = [local.title] + [t for t in _lines(page.text) if _is_title_line(t, "")]
            found = openalex_thesis(queries, page.text)

    meta = Meta(kind="thesis")
    # The page's spelling of the title when it's the same title ("Femtosecond Laser Ablation"
    # rather than OpenAlex's "femtosecond laser ablation"), else the online one (it has the
    # subtitle the page layout may hide)
    page_words, online_words = _words(local.title), _words(found.title)
    if local.title and page_words[: len(online_words)] == online_words:  # same, or + subtitle
        meta.fill(local.sources["title"], title=local.title)
    meta.fill(found.sources.get("title", ""), title=found.title)
    # One author; the page's full name when the online one has only initials ("Marcel Fredrik
    # Schneider" for "M.F. Schneider"), else the online one (it has the accents: "Margetić")
    online_author = found.author.split(";")[0]
    initials_only = re.match(r"(?:[A-Z]\.\s*-?)+\s*\S+$", online_author)
    if _same_person(local.author, online_author) and initials_only:
        meta.fill(local.sources["author"], author=local.author)
    meta.fill(found.sources.get("author", ""), author=online_author)
    meta.fill(local.sources.get("author", ""), author=local.author)
    # The year printed on the title page, unless it's later than the online one (then it's
    # when the PDF was made, e.g. LaTeX's \today on an arXiv copy)
    if local.year and (not found.year or local.year <= found.year):
        meta.fill(local.sources["year"], year=local.year)
    meta.fill(found.sources.get("year", ""), year=found.year)
    for key in ("degree", "institution", "supervisors"):
        meta.fill(local.sources.get(key, ""), **{key: getattr(local, key)})
        meta.fill(found.sources.get(key, ""), **{key: getattr(found, key)})
    for key in ("doi", "url", "isbn", "subjects"):
        meta.fill(found.sources.get(key, ""), **{key: getattr(found, key)})
    return meta
