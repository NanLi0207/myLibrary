"""Task 4 M6: the private store of quote anchors (references.py) and its endpoint
(/api/references/create). Temporary libraries only."""

import hashlib
import json
import os
import subprocess
import threading
import urllib.error
import urllib.request
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path

import add_book
import folder_backup
import library_server
import pytest
import references
import safe_io
from test_document_ids import _point_modules_at, registered

SLUG = "doe-2015-practical-lens-design"


@pytest.fixture
def library(tmp_path, monkeypatch):
    _point_modules_at(tmp_path, monkeypatch)
    return tmp_path


@pytest.fixture
def book(library):
    """A registered book with a README linking chapter 1's note: (id, catalog row)."""
    doc = registered(library, SLUG, "Practical Lens Design")
    readme = library / "notes" / SLUG / "README.md"
    readme.write_text(readme.read_text("utf-8") + "\n- [ ] [Ch 1: Basics](ch01-basics.md)\n",
                      encoding="utf-8")  # fmt: skip
    return doc, library_server.catalog.load(library / "catalog.csv")[doc]


def request(**changes) -> dict:
    """A text quote as the reader sends it (references.record_from checks every field)."""
    return {
        "kind": "text", "page": 0, "pages": 1, "rotation": 0, "page_size": [595.28, 841.89],
        "normalize": 1, "loaded": "", "pdfjs": "ab12", "pdfjs_version": "4.10.38",
        "nonce": uuid.uuid4().hex, "exact": "the exit pupil", "text": "the exit pupil",
        "prefix": "Single line: ", "suffix": " is the image", "start": 13, "end": 27,
        "page_len": 400, "page_hash": "0" * 64, "rects": [[0.1, 0.1, 0.5, 0.12]],
    } | changes  # fmt: skip


NOTE = {"doc": "x", "key": "file:ch01-basics.md"}


def test_a_reference_is_kept_privately_under_the_documents_id(library, book):
    doc, row = book
    made = references.create(library, row, request(fingerprint="f" * 64, evil="x"), NOTE)
    path = library / ".myLibrary" / "references" / f"{doc}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["format"] == 1 and list(data["references"]) == [made["rid"]]
    record = data["references"][made["rid"]]
    assert references.RID_RE.fullmatch(made["rid"]) and made["repeated"] is False
    assert record["doc"] == doc and record["exact"] == "the exit pupil" and record["nm"] is None
    # the fingerprint is the server's own reading of the PDF, never what the page claimed
    pdf = library / row["file"]
    assert record["fingerprint"] == hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert "evil" not in record and record["note"] == NOTE and record["created"].endswith("+00:00")
    assert references.load(library, doc) == data["references"]
    # nothing in the notes folder, nothing named by the slug
    assert not any("references" in p.parts for p in (library / "notes").rglob("*"))
    assert SLUG not in path.name


def test_page_references_have_no_quoted_text(library, book):
    doc, row = book
    body = {k: v for k, v in request(kind="page").items()
            if k not in ("exact", "text", "prefix", "suffix", "start", "end", "page_len",
                         "page_hash", "rects")}  # fmt: skip
    made = references.create(library, row, body, NOTE)
    record = references.load(library, doc)[made["rid"]]
    assert record["kind"] == "page" and "exact" not in record and "rects" not in record


def test_many_quotes_at_once_lose_nothing_and_never_share_an_id(library, book):
    doc, row = book
    start = threading.Barrier(8)
    made, errors = [], []

    def quote_ten():
        start.wait()
        for _ in range(10):
            try:
                made.append(references.create(library, row, request(), NOTE)["rid"])
            except Exception as e:  # (reported below)
                errors.append(e)

    threads = [threading.Thread(target=quote_ten) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    assert not errors
    stored = references.load(library, doc)
    assert len(made) == len(set(made)) == len(stored) == 80
    assert set(made) == set(stored)


def test_a_repeated_request_finds_its_reference_instead_of_making_another(library, book):
    doc, row = book
    once = request()
    first = references.create(library, row, once, NOTE)
    again = references.create(library, row, dict(once), NOTE)  # the answer was lost: Retry
    assert again == {"rid": first["rid"], "repeated": True}
    assert len(references.load(library, doc)) == 1


BAD = [
    {"kind": "highlight"}, {"page": 1}, {"page": True}, {"page": 0.0}, {"pages": 0},
    {"pages": 10**6}, {"rotation": 45}, {"rotation": 360}, {"page_size": [0, 10]},
    {"page_size": [float("nan"), 10]}, {"page_size": [1]}, {"normalize": 0},
    {"rects": [[0.1, 0.1, float("inf"), 0.2]]}, {"rects": [[0.1, 0.1, 1.5, 0.2]]},
    {"rects": [[0.5, 0.1, 0.4, 0.2]]}, {"rects": [[0.1, 0.1, 0.2]]}, {"rects": "0,0,1,1"},
    {"rects": [[0, 0, 1, 1]] * 501}, {"rects": [[True, 0, 1, 1]]}, {"exact": ""},
    {"exact": "   "}, {"exact": 5}, {"exact": "x" * 20_001}, {"start": 27, "end": 27},
    {"end": 401}, {"start": -1}, {"page_len": 0}, {"page_hash": "xyz"},
    {"nonce": "../../x"}, {"nonce": ""}, {"loaded": "abc"}, {"pdfjs": "<script>"},
    {"pdfjs_version": "x" * 40}, {"prefix": "p" * 65}, {"suffix": ["a"]},
]  # fmt: skip


@pytest.mark.parametrize("change", BAD, ids=lambda c: next(iter(c)))
def test_malformed_requests_store_nothing(library, book, change):
    doc, row = book
    with pytest.raises(references.BadReference):
        references.create(library, row, request(**change), NOTE)
    assert not (library / ".myLibrary" / "references").exists()


def test_not_a_request_at_all(library, book):
    _, row = book
    for body in (None, [], "text", 5):
        with pytest.raises(references.BadReference):
            references.create(library, row, body, NOTE)


def test_any_unicode_is_kept_as_selected(library, book):
    doc, row = book
    text = "θ λ Δφ ≈ 2π·n — 中文 (Chinese) 😀 ﬁeld \ud800"  # (a lone surrogate too)
    made = references.create(library, row, request(exact=text, text=text), NOTE)
    assert references.load(library, doc)[made["rid"]]["exact"] == text


@pytest.mark.parametrize("bad", ["../x", "..\\x", "", "A" * 36, str(uuid.uuid4()).upper(),
                                 "x/../" + str(uuid.uuid4()), None, 5])  # fmt: skip
def test_only_a_document_id_names_a_references_file(library, bad):
    with pytest.raises(references.BadReference):
        references.path_for(library, bad)


def test_a_damaged_file_is_never_replaced(library, book, capsys):
    doc, row = book
    first = references.create(library, row, request(), NOTE)["rid"]
    second = references.create(library, row, request(), NOTE)["rid"]  # (.bak now holds `first`)
    path = references.path_for(library, doc)
    damaged = b'{"format": 1, "references": {"r'
    path.write_bytes(damaged)
    # Its previous version reads: used (a copy of the damaged one is kept), and said so; the
    # reference made after that version is lost with the damage, the others stay
    third = references.create(library, row, request(), NOTE)["rid"]
    kept = list(path.parent.glob(f"{path.name}.damaged-*"))
    assert len(kept) == 1 and kept[0].read_bytes() == damaged
    assert "using its previous version" in capsys.readouterr().out
    assert set(references.load(library, doc)) == {first, third} and second not in {first, third}
    # Neither it nor its previous version reads: nothing is written, nothing replaced
    path.write_bytes(damaged)
    path.with_name(path.name + ".bak").write_bytes(b"not json")
    with pytest.raises(safe_io.DamagedFile):
        references.create(library, row, request(), NOTE)
    assert path.read_bytes() == damaged


def test_a_newer_format_is_left_alone(library, book):
    doc, row = book
    path = references.path_for(library, doc)
    path.parent.mkdir(parents=True)
    newer = json.dumps({"format": 2, "references": {"rabc": {"what": "new"}}}).encode()
    path.write_bytes(newer)
    with pytest.raises(references.BadReference, match="newer"):
        references.create(library, row, request(), NOTE)
    assert path.read_bytes() == newer
    with pytest.raises(references.BadReference):
        references.load(library, doc)


def test_references_follow_the_document_through_a_rename(library, book):
    doc, row = book
    made = references.create(library, row, request(), NOTE)["rid"]
    path = references.path_for(library, doc)
    renamed = add_book.rename_document(doc, "doe-2015-practical-optics")
    assert renamed["id"] == doc and renamed["file"] != row["file"]
    assert references.path_for(library, doc) == path and made in references.load(library, doc)
    again = references.create(library, renamed, request(), NOTE)["rid"]
    record = references.load(library, doc)[again]
    assert record["fingerprint"] == references.load(library, doc)[made]["fingerprint"]  # same PDF


def test_each_library_keeps_its_own_references(tmp_path):
    one, two = tmp_path / "one", tmp_path / "two"
    for root in (one, two):
        (root / "books").mkdir(parents=True)
    doc = str(uuid.uuid4())
    row = {"id": doc, "file": "books/a.pdf"}
    (one / "books" / "a.pdf").write_bytes(b"%PDF-1.4 one")
    references.create(one, row, request(), NOTE)
    assert len(references.load(one, doc)) == 1 and references.load(two, doc) == {}
    assert not (two / ".myLibrary").exists()


def test_the_fingerprint_follows_the_file(library, book):
    doc, row = book
    pdf = library / row["file"]
    first = references.fingerprint(pdf)
    safe_io.write_bytes(pdf, pdf.read_bytes() + b"\n% marks saved\n")
    assert references.fingerprint(pdf) == hashlib.sha256(pdf.read_bytes()).hexdigest() != first


def test_references_are_in_the_folder_backup_and_ignored_by_git(library, book):
    doc, row = book
    references.create(library, row, request(), NOTE)
    references.create(library, row, request(), NOTE)
    files = {p.relative_to(library).as_posix() for p in folder_backup.your_files(library)}
    assert f".myLibrary/references/{doc}.json" in files
    assert f".myLibrary/references/{doc}.json.bak" in files
    # a library inside this repository (like the showcase): .myLibrary/ is never tracked
    repo = Path(__file__).resolve().parents[1]
    checked = subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", f"library/.myLibrary/references/{doc}.json"],
        cwd=repo, capture_output=True,
    )  # fmt: skip
    assert checked.returncode == 0


# --- the endpoint ------------------------------------------------------------------------------


@pytest.fixture
def server(library):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


def post(base, body, token=None, raw=None):
    data = raw if raw is not None else json.dumps(body).encode()
    req = urllib.request.Request(
        base + "/api/references/create", data=data, method="POST",
        headers={"Content-Type": "application/json",
                 "X-Library-Token": library_server.TOKEN if token is None else token},
    )  # fmt: skip
    try:
        with urllib.request.urlopen(req, timeout=10) as answer:
            return answer.status, json.load(answer)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_the_endpoint_stores_a_quote_for_one_of_the_documents_notes(library, book, server):
    doc, _ = book
    status, made = post(server, request(id=doc, note_key="file:ch01-basics.md"))
    assert status == 200 and references.RID_RE.fullmatch(made["rid"])
    record = references.load(library, doc)[made["rid"]]
    assert record["note"] == {"doc": doc, "key": "file:ch01-basics.md"}


@pytest.mark.parametrize("change, code", [
    ({"note_key": "file:../../catalog.csv"}, 400), ({"note_key": "file:not-linked.md"}, 400),
    ({"note_key": None}, 400), ({"id": "../../etc"}, 404), ({"id": str(uuid.uuid4())}, 404),
    ({"page": -1}, 400), ({"rects": [[0, 0, 2, 2]]}, 400),
])  # fmt: skip
def test_the_endpoint_refuses_what_it_cant_store(library, book, server, change, code):
    doc, _ = book
    status, answer = post(server, request(id=doc, note_key="file:ch01-basics.md") | change)
    assert status == code and "error" in answer
    assert not (library / ".myLibrary" / "references").exists()


def test_the_endpoint_needs_the_key_and_a_small_body(library, book, server):
    doc, _ = book
    status, _ = post(server, request(id=doc, note_key="file:ch01-basics.md"), token="wrong")
    assert status == 403
    status, _ = post(server, None, raw=b"{" + b" " * references.MAX_BODY + b"}")
    assert status == 413
    assert not (library / ".myLibrary" / "references").exists()


def test_a_merged_documents_old_id_is_refused(library, book, server, monkeypatch):
    doc, _ = book
    other = str(uuid.uuid4())
    monkeypatch.setattr(library_server, "live_id", lambda value: doc if value == other else None)
    status, answer = post(server, request(id=other, note_key="file:ch01-basics.md"))
    assert status == 409 and "merged" in answer["error"]
    assert not (library / ".myLibrary" / "references").exists()


def test_a_damaged_references_file_answers_an_error_and_stays(library, book, server):
    doc, _ = book
    path = references.path_for(library, doc)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"{ damaged")
    path.with_name(path.name + ".bak").write_bytes(b"also damaged")
    status, answer = post(server, request(id=doc, note_key="file:ch01-basics.md"))
    assert status == 500 and "error" in answer and str(library) not in answer["error"]
    assert path.read_bytes() == b"{ damaged"


def test_a_source_link_opens_the_page(library, book, server):
    doc, _ = book
    _, made = post(server, request(id=doc, note_key="file:ch01-basics.md"))
    url = f"{server}/read/{doc}?page=1&ref={made['rid']}&q=the%20exit%20pupil"

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    with pytest.raises(urllib.error.HTTPError) as moved:
        urllib.request.build_opener(NoRedirect).open(url, timeout=10)
    assert moved.value.code == 302 and "#page=1" in moved.value.headers["Location"]


# --- containment: links and junctions (Codex M6 review) -----------------------------------------
#
# Junctions need no special right on Windows, so those cases always run here; symlinks do
# (symlink_or_skip: skipped on a PC without the right, a failure in CI where it's required).


def junction(target: Path, link: Path) -> None:
    import _winapi  # (Windows only, as the whole tool)

    _winapi.CreateJunction(str(target), str(link))


def outside_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*"))


def test_a_junction_in_place_of_the_references_folder_is_refused(library, book, tmp_path_factory):
    doc, row = book
    outside = tmp_path_factory.mktemp("outside")
    (library / ".myLibrary").mkdir()
    junction(outside, library / ".myLibrary" / "references")
    with pytest.raises(references.UnsafeStore, match="link or junction"):
        references.create(library, row, request(), NOTE)
    with pytest.raises(references.UnsafeStore):
        references.load(library, doc)
    assert outside_files(outside) == []  # nothing written through it
    assert (library / ".myLibrary" / "references").is_junction()  # and nothing changed here


def test_a_junction_in_place_of_dot_mylibrary_gets_no_folder_made_through_it(
    library, book, tmp_path_factory
):
    _, row = book
    outside = tmp_path_factory.mktemp("outside")
    junction(outside, library / ".myLibrary")  # references/ doesn't exist yet
    with pytest.raises(references.UnsafeStore):
        references.create(library, row, request(), NOTE)
    assert outside_files(outside) == []  # not even an empty references/ folder


def test_a_junction_named_like_the_references_file_is_refused(library, book, tmp_path_factory):
    doc, row = book
    outside = tmp_path_factory.mktemp("outside")
    path = references.path_for(library, doc)
    path.parent.mkdir(parents=True)
    junction(outside, path)
    with pytest.raises(references.UnsafeStore, match="not a file"):
        references.create(library, row, request(), NOTE)
    assert outside_files(outside) == []


@pytest.mark.parametrize("which", ["file", "bak"])
def test_a_symlinked_references_file_or_previous_version_is_neither_read_nor_written(
    library, book, tmp_path_factory, which
):
    from test_notes_store import symlink_or_skip

    doc, row = book
    references.create(library, row, request(), NOTE)
    references.create(library, row, request(), NOTE)  # (now there is a .bak too)
    path = references.path_for(library, doc)
    link = path if which == "file" else path.with_name(path.name + ".bak")
    secret = tmp_path_factory.mktemp("outside") / "secret.json"
    original = json.dumps({"format": 1, "references": {"rsecret": {"private": "x"}}}).encode()
    secret.write_bytes(original)
    kept = link.read_bytes()
    link.unlink()
    symlink_or_skip(secret, link)
    with pytest.raises(references.UnsafeStore, match="link or junction"):
        references.create(library, row, request(), NOTE)
    with pytest.raises(references.UnsafeStore):
        references.load(library, doc)  # its content is never returned
    assert secret.read_bytes() == original and link.is_symlink()  # neither changed
    link.unlink()
    link.write_bytes(kept)  # a plain file again: works as before
    references.create(library, row, request(), NOTE)


def test_a_file_where_a_folder_belongs_is_refused(library, book):
    doc, row = book
    (library / ".myLibrary").write_bytes(b"not a folder")
    with pytest.raises(references.UnsafeStore, match="not a folder"):
        references.create(library, row, request(), NOTE)
    assert (library / ".myLibrary").read_bytes() == b"not a folder"


def test_a_library_reached_through_a_junction_keeps_its_references_inside(
    library, book, tmp_path_factory
):
    doc, row = book
    linked = tmp_path_factory.mktemp("elsewhere") / "library-link"
    junction(library, linked)  # the library folder itself kept elsewhere: the user's own choice
    made = references.create(linked, row, request(), NOTE)["rid"]
    assert made in references.load(linked, doc)
    assert (library / ".myLibrary" / "references" / f"{doc}.json").is_file()


def test_a_junction_swapped_in_while_saving_is_reported(library, book, tmp_path_factory,
                                                        monkeypatch):  # fmt: skip
    doc, row = book
    references.create(library, row, request(), NOTE)
    folder = library / ".myLibrary" / "references"
    moved = tmp_path_factory.mktemp("outside") / "moved"
    real_update = safe_io.update_json

    def then_swapped(*args, **kwargs):
        result = real_update(*args, **kwargs)
        folder.rename(moved)  # another process, between the write and the check after it
        junction(moved, folder)
        return result

    monkeypatch.setattr(safe_io, "update_json", then_swapped)
    with pytest.raises(references.UnsafeStore, match="changed while saving"):
        references.create(library, row, request(), NOTE)
    assert folder.is_junction()  # reported, never deleted or undone
    assert (moved / f"{doc}.json").is_file()


def test_the_endpoint_refuses_a_junctioned_store_with_an_error(library, book, server,
                                                                tmp_path_factory):  # fmt: skip
    doc, _ = book
    outside = tmp_path_factory.mktemp("outside")
    (library / ".myLibrary").mkdir()
    junction(outside, library / ".myLibrary" / "references")
    status, answer = post(server, request(id=doc, note_key="file:ch01-basics.md"))
    assert status == 500 and "link or junction" in answer["error"]
    assert str(library) not in answer["error"] and outside_files(outside) == []


# --- a frozen library (paths.FROZEN) is never changed, not even by a folder (Codex M6 review) --


def tree(folder: Path) -> dict:
    """Every file and folder under `folder` with its bytes (the whole tree, to compare)."""
    return {
        p.relative_to(folder).as_posix(): None if p.is_dir() else p.read_bytes()
        for p in sorted(folder.rglob("*"))
    }


@pytest.mark.parametrize("reached", ["directly", "junction", "symlink"])
@pytest.mark.parametrize("store", ["none yet", "existing"])
def test_a_frozen_library_gets_no_folder_and_no_reference(
    library, book, tmp_path_factory, monkeypatch, reached, store
):
    doc, row = book
    if store == "existing":
        references.create(library, row, request(), NOTE)
    monkeypatch.setattr(safe_io, "_frozen", list(safe_io._frozen))
    safe_io.freeze(library)
    root = library
    if reached != "directly":  # a link to the frozen library is refused just the same
        root = tmp_path_factory.mktemp("elsewhere") / "library-link"
        if reached == "junction":
            junction(library, root)
        else:
            from test_notes_store import link_or_skip

            link_or_skip(lambda: os.symlink(library, root, target_is_directory=True), "symlink")
    before = tree(library)
    with pytest.raises(safe_io.FrozenLocation):
        references.create(root, row, request(), NOTE)
    assert tree(library) == before  # not even an empty .myLibrary/ or references/ folder
    assert (library / ".myLibrary").exists() == (store == "existing")
    assert len(references.load(root, doc)) == (store == "existing")  # reading is still allowed
    assert tree(library) == before
