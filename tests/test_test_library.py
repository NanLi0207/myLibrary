"""The public Test & Demo library: the canonical test_library/ matches its MANIFEST.json and is
never written; its working copy is made once, kept, and reset only on purpose; it is never
backed up. Writable copies live in this test's own folders only."""

import hashlib
import json
from pathlib import Path

import backup
import catalog
import folder_backup
import libraries
import pytest
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from test_libraries import own_registry, snapshot  # noqa: F401 (the fixture)

CANONICAL = libraries.TEST_CANONICAL
MANIFEST = json.loads((CANONICAL / "MANIFEST.json").read_text(encoding="utf-8"))


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_canonical_library_is_complete_and_marked():
    about = libraries.info(CANONICAL)
    assert about["test"] and about["id"] == MANIFEST["library_id"]
    assert catalog.check(CANONICAL / "catalog.csv") == []
    rows = catalog.load(CANONICAL / "catalog.csv")
    assert {d["id"] for d in MANIFEST["documents"]} == set(rows)
    kinds = [d["type"] for d in MANIFEST["documents"]]
    assert {k: kinds.count(k) for k in set(kinds)} == {"book": 9, "paper": 7, "thesis": 2}
    for row in rows.values():
        assert (CANONICAL / row["file"]).is_file() and (CANONICAL / row["notes"]).is_dir()
    total = sum(p.stat().st_size for p in CANONICAL.rglob("*") if p.is_file())
    assert total < 50_000_000
    assert not list(CANONICAL.rglob(".cache")) and not list(CANONICAL.rglob("archive"))


@pytest.mark.parametrize("doc", MANIFEST["documents"], ids=lambda d: d["file"])
def test_each_document_matches_its_manifest(doc):
    pdf = CANONICAL / doc["file"]
    assert sha256(pdf) == doc["sha256"] and pdf.stat().st_size == doc["bytes"]
    reader = PdfReader(pdf)
    expect = doc["expect"]
    assert reader.is_encrypted == bool(expect.get("encrypted"))
    if reader.is_encrypted:
        assert reader.decrypt("")  # an empty user password, as publisher PDFs
    assert len(reader.pages) == doc["pages"]
    texts = [(page.extract_text() or "").strip() for page in reader.pages]
    if expect["text"]:
        assert max(len(t) for t in texts) > 50
    else:
        assert all(t == "" for t in texts)
    for n in expect.get("image_only_pages", []):
        assert texts[n - 1] == ""
    if "first_page_contains" in expect:
        assert expect["first_page_contains"] in texts[0]
    if "outline" in expect:
        assert len(reader.outline) == expect["outline"]
    for n in expect.get("rotated_pages", []):
        assert reader.pages[n - 1].rotation == 90
    for n in expect.get("landscape_pages", []):
        box = reader.pages[n - 1].mediabox
        assert box.width > box.height
    if "pdf_version" in expect:
        assert pdf.read_bytes().startswith(f"%PDF-{expect['pdf_version']}".encode())
    if "annotations" in expect:
        annots = [a.get_object() for page in reader.pages for a in page.get("/Annots") or []]
        names = [str(a.get("/NM")) for a in annots]
        assert len(names) == expect["annotations"]
        assert all(n.startswith("mylibrary-test") for n in names)


def test_the_negative_fixtures_never_open_as_documents():
    fixtures = {f["file"]: f for f in MANIFEST["fixtures"]}
    for f in fixtures.values():
        assert sha256(CANONICAL / f["file"]) == f["sha256"]
    locked = PdfReader(CANONICAL / "fixtures/encrypted-with-password.pdf")
    assert locked.is_encrypted and not locked.decrypt("") and locked.decrypt("test")
    for name in ("fixtures/truncated.pdf", "fixtures/not-a-pdf.pdf"):
        with pytest.raises((PdfReadError, ValueError, KeyError)):
            reader = PdfReader(CANONICAL / name, strict=True)
            [page.extract_text() for page in reader.pages]
    duplicate = fixtures["fixtures/Downloaded copy (1).pdf"]
    original = next(d for d in MANIFEST["documents"] if d["id"] == duplicate["expect"]["repeat_of"])
    assert duplicate["sha256"] == original["sha256"]
    files = {r["file"] for r in catalog.load(CANONICAL / "catalog.csv").values()}
    assert not any(f.startswith("fixtures/") for f in files)


def test_only_public_material_is_in_it():
    """No private library's notes, PDFs or paths: every PDF is listed in the manifest as
    synthetic or with its licence, and nothing names a user's folder."""
    listed = {d["file"] for d in MANIFEST["documents"]} | {f["file"] for f in MANIFEST["fixtures"]}
    pdfs = {p.relative_to(CANONICAL).as_posix() for p in CANONICAL.rglob("*.pdf")}
    assert pdfs == listed
    assert all(d["licence"] for d in MANIFEST["documents"] + MANIFEST["fixtures"])
    for path in CANONICAL.rglob("*"):
        if path.suffix in (".md", ".csv", ".json", ".toml"):
            text = path.read_text(encoding="utf-8-sig")
            assert "C:\\Users" not in text and "C:/Users" not in text, path


def test_the_working_copy_is_made_once_and_kept(own_registry):  # noqa: F811
    before = snapshot(CANONICAL)
    working = libraries.test_library()
    assert working == libraries.TEST_WORKING and libraries.is_test_library(working)
    readme = working / "notes" / "topics" / "aperture.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\nmy test note\n", encoding="utf-8")
    assert libraries.test_library() == working
    assert readme.read_text(encoding="utf-8").endswith("my test note\n")  # not reset by itself
    assert snapshot(CANONICAL) == before


def test_reset_replaces_only_the_working_copy_and_keeps_the_last_one(own_registry, monkeypatch):  # noqa: F811
    before = snapshot(CANONICAL)
    working = libraries.test_library()
    (working / "notes" / "mine.md").write_text("changed in the test library\n", encoding="utf-8")
    monkeypatch.setattr(libraries, "find_server", lambda library, **kw: 8766)
    with pytest.raises(libraries.LibraryError, match="is open"):
        libraries.reset_test_library()
    assert (working / "notes" / "mine.md").exists()
    monkeypatch.setattr(libraries, "find_server", lambda library, **kw: None)
    libraries.reset_test_library()
    assert not (working / "notes" / "mine.md").exists()
    assert (libraries.TEST_PREVIOUS / "notes" / "mine.md").exists()
    assert snapshot(CANONICAL) == before


def test_reset_refuses_a_folder_that_isnt_the_test_library(own_registry):  # noqa: F811
    working = libraries.TEST_WORKING
    working.mkdir(parents=True)
    (working / "library.toml").write_text('name = "someone\'s real library"\n', encoding="utf-8")
    (working / "notes.md").write_text("precious\n", encoding="utf-8")
    with pytest.raises(libraries.LibraryError, match="isn't the Test & Demo library"):
        libraries.reset_test_library()
    with pytest.raises(libraries.LibraryError, match="isn't the Test & Demo library"):
        libraries.test_library()
    assert (working / "notes.md").read_text(encoding="utf-8") == "precious\n"
    assert not libraries.TEST_PREVIOUS.exists()


def test_the_test_library_is_never_backed_up(own_registry, tmp_path, monkeypatch):  # noqa: F811
    working = libraries.test_library()
    with pytest.raises(ValueError, match="Test & Demo"):
        folder_backup.back_up(tmp_path / "Backups", library=working)
    assert folder_backup.auto_backup(working) == ""
    assert not (tmp_path / "Backups").exists()
    monkeypatch.setattr(backup, "LIBRARY", working)
    assert backup.available() is False


ALLOWED_LICENCES = {"CC BY 4.0", "CC0 1.0 (public domain dedication)"}


def test_every_real_document_has_verified_provenance():
    """A real document only with a licence that allows redistribution, its source, the
    evidence, the attribution and a checksum matching the generator's (make_test_library.REAL:
    the file it was built from)."""
    real = [d for d in MANIFEST["documents"] if d["source"] == "real"]
    assert len(real) >= 2
    for d in real:
        assert d["licence"] in ALLOWED_LICENCES, d["file"]
        for field in ("source_url", "pdf_url", "licence_url", "attribution", "evidence"):
            assert d[field].strip(), (d["file"], field)
        assert d["source_url"].startswith("https://doi.org/")
    built_from = {r["sha256"] for r in generator_constant("REAL")}
    assert {d["sha256"] for d in real} == built_from  # unchanged, byte for byte
    synthetic = [d for d in MANIFEST["documents"] if d["source"] == "synthetic"]
    assert all(d["licence"].startswith("synthetic") for d in synthetic)


def generator_constant(name: str):
    """A constant (REAL, FIXED_IDS) of tests/make_test_library.py, read without running it
    (importing it would make its temporary library)."""
    import ast

    source = (Path(__file__).parent / "make_test_library.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == name:
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found")


def test_the_corpus_ids_are_fixed_in_the_generator():
    """A rebuild gives every document the id it has now (make_test_library.FIXED_IDS): ids are
    valid UUID4s (catalog.is_id), unique, and exactly the canonical library's."""
    fixed = generator_constant("FIXED_IDS")
    assert all(catalog.is_id(i) for i in fixed.values())
    assert len(set(fixed.values())) == len(fixed)
    assert set(fixed.values()) == {d["id"] for d in MANIFEST["documents"]}
    assert set(fixed.values()) == set(catalog.load(CANONICAL / "catalog.csv"))
