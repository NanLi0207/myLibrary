"""📈 Reading log: time and pages per day and book (reading_log.py)."""

from datetime import date, timedelta

import reading_log
from testlib import entry, id_of, put  # noqa: F401

DAY = date(2026, 11, 6)  # a Friday


def test_reports_add_up_per_day_and_book(tmp_path):
    reading_log.record(tmp_path, "a-book", 60, [41, 42], DAY)
    reading_log.record(tmp_path, "a-book", 45, [42, 43], DAY)
    result = reading_log.record(tmp_path, "b-book", 9999, [1], DAY)  # capped
    log = reading_log.load(tmp_path)
    assert log["2026-11-06"]["a-book"] == {"s": 105, "p": [41, 42, 43]}
    assert result == {"day": "2026-11-06", "seconds": reading_log.MAX_STEP, "pages": 1}


def test_streak_counts_reading_days_up_to_today_or_yesterday(tmp_path):
    for back in (1, 2, 3, 5):  # yesterday, the two days before, and an older day
        reading_log.record(tmp_path, "a-book", 120, [], DAY - timedelta(days=back))
        reading_log.record(tmp_path, "a-book", 120, [], DAY - timedelta(days=back))
        reading_log.record(tmp_path, "a-book", 120, [], DAY - timedelta(days=back))
    totals = reading_log._day_totals(reading_log.load(tmp_path))
    assert reading_log.streak(totals, DAY) == 3  # today may still come
    reading_log.record(tmp_path, "a-book", 60, [], DAY)  # a minute: not a reading day yet
    totals = reading_log._day_totals(reading_log.load(tmp_path))
    assert reading_log.streak(totals, DAY) == 3
    assert reading_log.streak(totals, DAY + timedelta(days=2)) == 0  # a day missed


def test_summary_for_the_page(tmp_path):
    path = tmp_path / "catalog.csv"
    doc = put(path, {"slug": "a-book", "title": "Modern Lens Design"})
    reading_log.record(tmp_path, doc, 120, [5, 6], DAY)
    reading_log.record(tmp_path, doc, 120, [7], DAY - timedelta(days=4))  # Monday
    reading_log.record(tmp_path, doc, 120, [8], DAY - timedelta(days=40))  # long ago
    s = reading_log.summary(tmp_path, path, DAY)
    assert (s["today_seconds"], s["week_seconds"], s["week_pages"]) == (120, 240, 3)
    assert s["total_seconds"] == 360
    assert (
        s["days"][0]["date"] == (DAY - timedelta(days=4, weeks=reading_log.WEEKS - 1)).isoformat()
    )
    assert s["days"][-1]["date"] == DAY.isoformat()
    assert s["books"] == [{"id": doc, "title": "Modern Lens Design", "removed": False,
                           "seconds": 240, "pages": 3, "days": 2}]  # fmt: skip
