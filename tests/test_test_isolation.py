"""The tests' own safety net (tests/conftest.py, background_jobs_end_with_the_test): a job a test
starts in the background (library_jobs) must end inside that test, while its redirections to a
temporary library still hold. Each case runs a small test session in a subprocess with a copy
of the real conftest.py, so removing or breaking the fixture fails these tests."""

from pathlib import Path

pytest_plugins = ["pytester"]

CONFTEST = Path(__file__).with_name("conftest.py")
SCRIPTS = Path(__file__).parent.parent / "scripts"

# A job that outlives its test's body: what page does it see when it gets to "write"?
OUTLIVES_ITS_TEST = """
import threading, time
import library_jobs, library_page

seen = {}
done = threading.Event()

def test_a_starts_a_slow_job():
    seen["test"] = library_page.PAGE  # this test's redirected page (conftest)
    def job():
        time.sleep(0.3)  # still working when the test's body has returned
        seen["job"] = library_page.PAGE  # where it would write the page now
        done.set()
    library_jobs._in_background(job)

def test_b_the_job_used_test_a_s_library():
    assert done.wait(10), "the job never ended"
    assert seen["job"] == seen["test"], f"the job wrote to {seen['job']}, not {seen['test']}"
"""

# A job that doesn't end in time (it only stops when asked): the run must stop there
NEVER_ENDS = """
import library_jobs

ran = []

def test_a_starts_a_job_that_waits_to_be_stopped():
    library_jobs._in_background(lambda: library_jobs._stopping.wait(30))

def test_b_must_not_run_beside_it():
    ran.append("b")
"""


def session(pytester, tests: str, conftest: str | None = None):
    pytester.makeconftest(conftest or CONFTEST.read_text(encoding="utf-8"))
    pytester.makeini(f"[pytest]\npythonpath = {SCRIPTS.as_posix()}\n")
    pytester.makepyfile(test_inner=tests)
    return pytester.runpytest_subprocess("-p", "no:cacheprovider", "-v")


def test_a_background_job_ends_inside_its_test(pytester):
    result = session(pytester, OUTLIVES_ITS_TEST)
    result.assert_outcomes(passed=2)


def test_a_job_that_doesnt_end_stops_the_whole_run(pytester):
    text = CONFTEST.read_text(encoding="utf-8")
    assert "JOB_WAIT = 30" in text
    result = session(pytester, NEVER_ENDS, text.replace("JOB_WAIT = 30", "JOB_WAIT = 0.5"))
    assert result.ret == 3, result.stdout.str()
    result.stdout.fnmatch_lines(["*didn't finish within 0.5 s of its test*"])
    assert "test_b_must_not_run_beside_it" not in result.stdout.str()
