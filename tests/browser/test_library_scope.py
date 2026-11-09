"""Recovery drafts belong to one library (libraries.scope): a copy of the library (the same
document ids) or another library served later on the same port and in the same browser never
sees them, and they are still there when their own library is opened again. Temporary
libraries only."""

import shutil

from conftest import Library, Server
from helpers import drafts_in_browser, editor_text, notes_settled, open_document, wait_save_state
from test_notes_content import book_with_notes
from test_notes_failures import FAIL, chapter_one, crash, type_at_end

LIBRARY_ID = "0b6f4d8e-2c1a-4f3b-9e7d-5a6c8b9d0e1f"  # both libraries: a copy keeps its id


def with_id(library: Library) -> None:
    (library.root / "library.toml").write_text(
        f'name = "Browser test"\nid = "{LIBRARY_ID}"\n', encoding="utf-8"
    )


def test_a_draft_stays_with_its_own_library(library, server_factory, reader_page, tmp_path):
    with_id(library)
    doc = book_with_notes(library)
    server = server_factory()
    open_document(reader_page, server, doc, page_no=2)
    notes_settled(reader_page)
    reader_page.route("**/api/notes/save", lambda route: route.fulfill(**FAIL))
    type_at_end(reader_page, "private draft of library A")
    wait_save_state(reader_page, "failed")
    saved = chapter_one(library, doc).read_bytes()
    context = reader_page.context
    crash(reader_page)
    port, home = server.port, server.home
    server.stop()

    # A copy of the library (same library id, same document ids) on the same port and in the
    # same browser: the draft is not offered, and the copy's note is shown as it is
    shutil.copytree(library.root, tmp_path / "copy of library")
    copy = Library(tmp_path / "copy of library")  # (its folders and library.toml are there)
    with_id(copy)
    other = Server(copy, home, False, ports=[port] * 5)
    try:
        page = context.new_page()
        open_document(page, other, doc, page_no=2)
        notes_settled(page)
        assert wait_save_state(page, "clean") == "clean"
        assert "private draft of library A" not in editor_text(page)
        assert chapter_one(copy, doc).read_bytes() == saved  # nothing written by looking
        assert any("private draft of library A" in d for d in drafts_in_browser(page).values()), (
            "the other library's draft must stay in the browser, never discarded"
        )
        page.close()
    finally:
        other.stop()

    # Library A again, on the same port: its draft is offered, and nothing was written
    again = Server(library, home, False, ports=[port] * 5)
    try:
        page = context.new_page()
        open_document(page, again, doc, page_no=2)
        notes_settled(page)
        assert wait_save_state(page, "draft") == "draft"
        assert chapter_one(library, doc).read_bytes() == saved
        assert chapter_one(copy, doc).read_bytes() == saved
    finally:
        again.stop()
