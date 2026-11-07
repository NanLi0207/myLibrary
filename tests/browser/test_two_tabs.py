"""Known issue D5 (ROADMAP): two tabs of the same PDF overwrite each other's marks, because
each saves the PDF as it loaded it plus its own marks. Recorded here as a strict expected
failure, scoped to D5's exact symptom: the run stays green while D5 is unfixed; it turns red
if the behaviour changes (then this test and ROADMAP are updated); and any other error,
including an AssertionError in a setup step, still fails it."""

import pytest
from helpers import highlight_line, highlighted_lines, leave_tool, open_document


class SecondTabDroppedTheFirstTabsMarks(Exception):
    """D5's symptom, and only that: raised by this test alone, the one exception the expected
    failure accepts."""


@pytest.mark.xfail(
    strict=True,
    raises=SecondTabDroppedTheFirstTabsMarks,
    reason="D5: the second tab's save drops the first tab's marks",
)
def test_marks_from_two_tabs_are_both_kept(library, server, reader_page):
    doc = library.add_book("doe-2020-marks-test", "Marks test")
    first, second = reader_page, reader_page.context.new_page()
    open_document(first, server, doc)
    open_document(second, server, doc)  # both loaded the PDF without marks

    highlight_line(first, 0)
    leave_tool(first)
    first.wait_for_function("() => document.querySelector('.ml-marks')?.dataset.state === 'saved'")
    assert highlighted_lines(library.pdf(doc)) == [0]  # setup: the first tab's mark is saved
    highlight_line(second, 3)
    leave_tool(second)
    second.wait_for_function("() => document.querySelector('.ml-marks')?.dataset.state === 'saved'")

    lines = highlighted_lines(library.pdf(doc))
    if lines == [3]:  # exactly D5: the second tab's save, without the first tab's mark
        raise SecondTabDroppedTheFirstTabsMarks(f"marks saved on lines {lines}, not [0, 3]")
    assert lines == [0, 3]  # anything else is a real failure, not "expected"
