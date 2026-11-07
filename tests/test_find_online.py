"""🔎 Find online: DOI / arXiv / ISBN lookups, free searches, and "in your library"."""

import book_meta
import find_online
import library_jobs
import pytest
from testlib import entry, id_of, put  # noqa: F401

WORK = {
    "title": "Laser weeding of common weed species",
    "publication_year": 2024,
    "type": "article",
    "doi": "https://doi.org/10.3389/fpls.2024.1",
    "cited_by_count": 39,
    "authorships": [{"author": {"display_name": "Christian Andreasen"}, "institutions": []}],
    "primary_location": {"source": {"display_name": "Frontiers in Plant Science"}},
    "best_oa_location": {"pdf_url": "https://example.org/paper.pdf"},
    "open_access": {"oa_url": "https://doi.org/10.3389/fpls.2024.1"},
}


@pytest.fixture
def owned(tmp_path, monkeypatch):
    path = tmp_path / "catalog.csv"
    put(
        path,
        {
            "slug": "smith-1992-modern-lens-design",
            "title": "Modern Lens Design",
            "year": "1992",
            "isbn": "9780070591783",
        },
    )
    put(
        path,
        {
            "slug": "andreasen-2024-laser-weeding",
            "doi": "10.3389/fpls.2024.1",
            "title": "Laser weeding of common weed species",
            "year": "2024",
        },
    )
    monkeypatch.setattr(find_online, "CATALOG", path)


def test_free_text_searches_works_authors_and_books(owned, monkeypatch):
    asked = []

    def answer(url, **kw):
        asked.append(url)
        if "/authors?" in url:
            return {"results": [{"display_name": "Somebody Else", "id": "A1"}]}
        if "openlibrary" in url:
            return {
                "docs": [
                    {
                        "title": "Modern lens design",
                        "author_name": ["Warren J. Smith"],
                        "first_publish_year": 1992,
                        "isbn": ["0070591784", "9780070591783"],
                        "key": "/works/OL1W",
                    }
                ]
            }
        return {"results": [WORK]}

    monkeypatch.setattr(book_meta, "_get_json", answer)
    found = find_online.find("  laser   weeding ")
    assert found["query"] == "laser weeding"
    works, books = found["sections"]
    [paper] = works["results"]
    assert (paper["kind"], paper["doi"], paper["pdf"], paper["venue"]) == (
        "paper",
        "10.3389/fpls.2024.1",
        "https://example.org/paper.pdf",
        "Frontiers in Plant Science",
    )
    assert paper["in_library"] == id_of(find_online.CATALOG, "andreasen-2024-laser-weeding")  # DOI
    assert books["results"][0]["in_library"] == id_of(
        find_online.CATALOG, "smith-1992-modern-lens-design"
    )  # ISBN
    assert books["results"][0]["isbn"] == "9780070591783"
    # "laser weeding" could be a name: the author search ran, but "Somebody Else" doesn't match
    assert any("/authors?" in u for u in asked)
    assert [e["label"] for e in found["engines"]][:3] == [
        "Google Scholar",
        "Semantic Scholar",
        "百度学术 Baidu Scholar",
    ]
    assert found["engines"][0]["url"].endswith("q=laser%20weeding")


def test_an_authors_works_first(owned, monkeypatch):
    def answer(url, **kw):
        if "/authors?" in url:
            return {
                "results": [
                    {
                        "display_name": "Warren J. Smith",
                        "id": "https://x/A42",
                        "last_known_institutions": [{"display_name": "Kaiser Electro-Optics"}],
                    }
                ]
            }
        if "author.id:A42" in url:
            return {"results": [WORK | {"title": "Modern Optical Engineering", "type": "book"}]}
        return {"results": [], "docs": []}

    monkeypatch.setattr(book_meta, "_get_json", answer)
    [by_author] = find_online.find("Warren Smith")["sections"]
    assert by_author["title"] == "Works by Warren J. Smith (Kaiser Electro-Optics)"
    assert by_author["results"][0]["kind"] == "book"


def test_doi_arxiv_and_isbn_go_straight_to_the_work(owned, monkeypatch):
    crossref = {
        "message": {
            "type": "journal-article",
            "title": ["Freeform optics for imaging"],
            "author": [{"given": "Jannick", "family": "Rolland"}],
            "issued": {"date-parts": [[2021]]},
            "container-title": ["Optica"],
        }
    }

    def answer(url, **kw):
        if "crossref" in url:
            return crossref
        if "/works/doi:" in url:
            return WORK | {"title": "Freeform optics for imaging", "best_oa_location": {}}
        return None

    monkeypatch.setattr(book_meta, "_get_json", answer)
    [section] = find_online.find("https://doi.org/10.1364/OPTICA.413762")["sections"]
    [hit] = section["results"]
    assert (hit["title"], hit["authors"], hit["venue"], hit["pdf"]) == (
        "Freeform optics for imaging",
        "Jannick Rolland",
        "Optica",
        "",
    )
    assert hit["free"]  # OpenAlex's open-access link

    monkeypatch.setattr(
        book_meta, "arxiv", lambda i: book_meta.Meta(title="A thesis", author="Z", kind="thesis")
    )
    [section] = find_online.find("arXiv:2308.08698")["sections"]
    assert section["results"][0]["pdf"] == "https://arxiv.org/pdf/2308.08698"
    assert section["results"][0]["kind"] == "thesis"

    monkeypatch.setattr(
        book_meta,
        "open_library",
        lambda isbns: book_meta.Meta(title="Modern lens design", isbn="9780070591783", year="1992"),
    )
    [section] = find_online.find("978-0-07-059178-3")["sections"]
    assert section["results"][0]["in_library"] == id_of(
        find_online.CATALOG, "smith-1992-modern-lens-design"
    )


def test_people_and_topics():
    assert find_online.looks_like_person("Robert R. Shannon")
    assert find_online.looks_like_person("Shannon, Robert")
    assert not find_online.looks_like_person("lens design of the eye")
    assert not find_online.looks_like_person("10.1364/oe.27.001234")
    assert not find_online.looks_like_person("aberrations")


def test_download_refuses_web_pages(tmp_path, monkeypatch):
    with pytest.raises(ValueError):
        library_jobs.start_download("file:///etc/passwd")

    class Page:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def read(self, n):
            return b"<!doctype html><p>Sign in to download</p>"

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: Page())
    job = library_jobs._new_job("add", file="x", message="")
    library_jobs._download(job, "https://example.org/x", "x")
    assert job["status"] == "error" and "web page, not a PDF" in job["message"]
