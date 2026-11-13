"""Formula recognition (task 4 M5e), server side.

- Without the model: the app works, recognition says it isn't installed, nothing is fetched.
- Installing: only the pinned files, each checked (size, SHA-256), swapped in whole or not at
  all; a failed, wrong or stopped download leaves what was there.
- Recognising (a stand-in engine, deterministic): candidates, "similar", failures, a busy
  model, a timeout; never a network connection.
- The real model (the last tests): run only where it is installed (uv run
  scripts/formula_ocr.py --setup), read-only, offline (sockets blocked), on formulas drawn here
  with matplotlib. These are the real OCR checks; the stand-in tests prove only the plumbing.
"""

import hashlib
import io
import json
import socket
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import formula_ocr
import image_check
import library_server
import pytest
from formula_ocr import Candidate
from PIL import Image

REAL_MODEL = formula_ocr._model_dir()  # the tool's own copy, if the developer installed it


def png(size=(60, 30), color="white") -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, "PNG")
    return out.getvalue()


@pytest.fixture
def no_network(monkeypatch):
    """Any attempt to open a connection fails the test."""
    attempts = []

    def refuse(self, *args, **kwargs):
        attempts.append(args)
        raise AssertionError("formula recognition tried to use the network")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: refuse(None, *a))
    yield attempts
    assert not attempts


# --- tidying the model's LaTeX ------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, tidy",
    [
        (r"n _ { 1 } \operatorname { s i n } \theta _ { 1 }", r"n_1\sin\theta_1"),
        (r"I _ { 0 } \operatorname { e x p } \left( - \cfrac { 2 r ^ { 2 } } { w ^ { 2 } } \right)",
         r"I_0\exp\left(-\cfrac{2r^2}{w^2}\right)"),  # \cfrac as written: valid, not restyled
        (r"N _ { A } = 6 . 0 2 2 \times 1 0 ^ { 2 3 } \mathrm { ~ m o l } ^ { - 1 }",
         r"N_A=6.022\times10^{23}\mathrm{mol}^{-1}"),
        (r"\frac { 1 } { s ^ { ' } }", r"\frac{1}{s^{'}}"),  # never s^' (invalid)
        (r"x ^ { \prime } + y _ { \alpha }", r"x^\prime+y_\alpha"),
        (r"x ^ { 2 3 }", r"x^{23}"),  # two tokens: braces kept
        (r"\text { i f ~ x > 0 }", r"\text{if x>0}"),
        (r"\operatorname { e r f } ( x )", r"\operatorname{erf}(x)"),  # not a known function
        (r"I \! \left( r \right) \! = 1", r"I\left(r\right)=1"),
        (r"\alpha x + \beta", r"\alpha x+\beta"),  # the space LaTeX needs, and no other
        (r"\hat { \mathbf { x } }", r"\hat{\mathbf{x}}"),
        ("a + b \\", "a+b"),  # a lone trailing backslash (never valid) is dropped
        (r"a \\ b \\", r"a\\b\\"),  # line breaks (\\) are kept
        (r"\begin{matrix} { A } & { B } \\ \end{matrix}", r"\begin{matrix}{A}&{B}\\\end{matrix}"),
    ],
)  # fmt: skip
def test_tidy_changes_spacing_never_the_formula(raw, tidy):
    assert formula_ocr.tidy(raw) == tidy


def test_results_differing_only_in_spacing_count_as_one():
    key = formula_ocr.same_key
    assert key(r"\Delta x~\Delta p\ge\hbar") == key(r"\Delta x\,\Delta p\geq\hbar")
    assert key(r"\frac{ab}{c}") != key(r"\frac{a}{bc}")  # braces always count
    assert key(r"\quadratic") == r"\quadratic"  # not \quad


def test_a_runaway_repetition_is_recognised():
    assert formula_ocr.repeating([1] + [7] * 16)
    assert formula_ocr.repeating([1] + [7, 8, 9] * 16)
    assert not formula_ocr.repeating([1] + [7] * 15)
    assert not formula_ocr.repeating(list(range(100)))


def test_screenshots_are_prepared_like_the_models_training_images():
    """Transparent → on white; dark mode → dark text on light; margins trimmed."""
    transparent = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
    transparent.paste((0, 0, 0, 255), (50, 40, 150, 60))
    trimmed = formula_ocr.trim(transparent)
    assert trimmed.mode == "RGB" and trimmed.size == (100 + 16, 20 + 16)
    assert trimmed.getpixel((0, 0)) == (255, 255, 255)
    dark = Image.new("RGB", (100, 40), (30, 30, 30))
    dark.paste((240, 240, 240), (20, 10, 80, 30))
    pixels = formula_ocr.Engine.pixels(dark)
    assert pixels.shape == (1, 3, 384, 384)
    assert pixels.mean() > 0  # mostly light (the model's +1), the text dark


# --- without the model ------------------------------------------------------------------------


def test_without_the_model_recognition_says_so_and_fetches_nothing(no_network):
    assert not formula_ocr.installed()
    assert formula_ocr.status()["installed"] is False
    with pytest.raises(formula_ocr.NotInstalled):
        formula_ocr.recognize(png())
    with pytest.raises(image_check.ImageError):  # the image is checked first, as always
        formula_ocr.recognize(b"<svg/>")


# --- installing -------------------------------------------------------------------------------


FAKE = {"encoder_model.onnx": b"E" * 3000, "decoder_model.onnx": b"D" * 2000,
        "tokenizer.json": b"{}", "README.md": b"# card\n"}  # fmt: skip


@pytest.fixture
def fake_files(monkeypatch):
    files = {n: (len(d), hashlib.sha256(d).hexdigest()) for n, d in FAKE.items()}
    monkeypatch.setattr(formula_ocr, "FILES", files)
    monkeypatch.setattr(formula_ocr, "DOWNLOAD_BYTES", sum(len(d) for d in FAKE.values()))
    return files


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def opener(served: dict, asked: list):
    def open_url(url, timeout):
        assert url.startswith(formula_ocr.SOURCE) and timeout
        asked.append(url.removeprefix(formula_ocr.SOURCE))
        return Response(served[url.removeprefix(formula_ocr.SOURCE)])

    return open_url


def test_install_puts_the_checked_files_in_place(fake_files):
    asked, seen = [], []
    formula_ocr.install(progress=seen.append, opener=opener(FAKE, asked))
    assert asked == list(FAKE)  # the pinned files only, from the pinned revision
    assert formula_ocr.installed()
    formula_ocr.verify(formula_ocr.MODEL_DIR)
    for name, data in FAKE.items():
        assert (formula_ocr.MODEL_DIR / name).read_bytes() == data
    assert sum(seen) == formula_ocr.DOWNLOAD_BYTES
    assert not list(formula_ocr.MODEL_DIR.parent.glob(".install-*"))


@pytest.mark.parametrize(
    "served, why",
    [
        ({**FAKE, "decoder_model.onnx": b"X" * 2000}, "checksum"),  # same size, other bytes
        ({**FAKE, "decoder_model.onnx": b"D" * 1999}, "checksum"),  # cut short
        ({**FAKE, "decoder_model.onnx": b"D" * 5000}, "larger than expected"),
    ],
)
def test_a_wrong_download_installs_nothing_and_keeps_the_installed_copy(fake_files, served, why):
    formula_ocr.install(opener=opener(FAKE, []))  # a good copy first
    before = {p.name: p.read_bytes() for p in formula_ocr.MODEL_DIR.iterdir()}
    with pytest.raises(ValueError, match=why):
        formula_ocr.install(opener=opener(served, []))
    assert {p.name: p.read_bytes() for p in formula_ocr.MODEL_DIR.iterdir()} == before
    assert formula_ocr.installed()
    assert not list(formula_ocr.MODEL_DIR.parent.glob(".install-*"))


def test_quitting_stops_a_download_and_installs_nothing(fake_files):
    with pytest.raises(formula_ocr.Cancelled):
        formula_ocr.install(stop=lambda: True, opener=opener(FAKE, []))
    assert not formula_ocr.installed() and not formula_ocr.MODEL_DIR.exists()
    assert not list(formula_ocr.MODEL_DIR.parent.glob(".install-*"))


def test_a_second_install_never_touches_one_running_however_old_it_looks(fake_files):
    import os
    import threading
    import time

    root = formula_ocr.MODEL_DIR.parent
    downloading, release = threading.Event(), threading.Event()
    plain = opener(FAKE, [])

    def held(url, timeout):  # the first install, stopped mid-download (no sleeps: events)
        downloading.set()
        assert release.wait(30)
        return plain(url, timeout)

    first_error = []

    def first():
        try:
            formula_ocr.install(opener=held)
        except Exception as e:  # (reported below)
            first_error.append(e)

    thread = threading.Thread(target=first)
    thread.start()
    try:
        assert downloading.wait(30)
        (running,) = root.glob(".install-*")
        old = time.time() - 7 * 24 * 3600  # its folder looks a week old: still in use
        os.utime(running, (old, old))
        with pytest.raises(formula_ocr.InstallBusy, match="another download"):
            formula_ocr.install(opener=opener(FAKE, []))
        assert running.is_dir()  # left alone
    finally:
        release.set()
        thread.join(60)
    assert not first_error and formula_ocr.installed()
    formula_ocr.verify(formula_ocr.MODEL_DIR)


def crash_between_the_renames(new_whole: bool = True):
    """The files exactly as a process killed between "installed copy → .old-*" and
    ".install-* → installed" leaves them (no chance to roll back): no installed model."""
    import shutil

    root = formula_ocr.MODEL_DIR.parent
    formula_ocr.install(opener=opener(FAKE, []))  # a good installed copy first
    formula_ocr.MODEL_DIR.replace(root / ".old-crash")
    shutil.copytree(root / ".old-crash", root / ".install-crash")  # the checked download
    if not new_whole:
        (root / ".install-crash" / "decoder_model.onnx").write_bytes(b"cut")
    assert not formula_ocr.installed()
    return root


def test_a_crash_between_the_renames_is_recovered_without_a_download(fake_files, no_network):
    root = crash_between_the_renames()
    assert formula_ocr.status()["installed"]  # put back, offline: nothing fetched
    formula_ocr.verify(formula_ocr.MODEL_DIR)
    assert not formula_ocr._leftovers(root)  # the spare copy cleared once one is in place


def test_only_a_whole_copy_is_put_back(fake_files):
    root = crash_between_the_renames(new_whole=False)
    assert formula_ocr.recover_interrupted()
    formula_ocr.verify(formula_ocr.MODEL_DIR)  # the old, whole copy; never the cut one
    assert not formula_ocr._leftovers(root)


def test_a_failed_install_after_a_crash_still_leaves_a_working_model(fake_files):
    crash_between_the_renames()

    def offline(url, timeout):
        raise OSError("no network")

    with pytest.raises(OSError, match="no network"):
        formula_ocr.install(opener=offline)  # recovery first, under the lock
    formula_ocr.verify(formula_ocr.MODEL_DIR)


def test_a_failed_swap_that_cant_be_undone_keeps_the_old_copy(fake_files, monkeypatch):
    from pathlib import Path

    root = formula_ocr.MODEL_DIR.parent
    formula_ocr.install(opener=opener(FAKE, []))
    real, calls = Path.replace, []

    def replace(self, target):
        calls.append(self.name)
        if len(calls) >= 2:  # the swap in, and then putting the old copy back: both fail
            raise OSError("access denied")
        return real(self, target)

    monkeypatch.setattr(Path, "replace", replace)
    with pytest.raises(OSError, match="access denied"):
        formula_ocr.install(opener=opener(FAKE, []))
    monkeypatch.setattr(Path, "replace", real)
    assert not formula_ocr.MODEL_DIR.exists()
    spares = formula_ocr._leftovers(root)
    assert any(s.name.startswith(".old-") for s in spares)  # never deleted
    assert all(formula_ocr._whole(s) for s in spares)
    assert formula_ocr.recover_interrupted()  # and put back next time
    formula_ocr.verify(formula_ocr.MODEL_DIR)


def test_folders_left_by_a_cut_off_install_are_cleared_by_the_next(fake_files):
    root = formula_ocr.MODEL_DIR.parent
    root.mkdir(parents=True)
    for name in (".install-cutoff", ".old-cutoff"):  # recent ones too: nobody holds the lock
        (root / name).mkdir()
        (root / name / "encoder_model.onnx").write_bytes(b"partial")
    formula_ocr.install(opener=opener(FAKE, []))
    assert formula_ocr.installed()
    assert not list(root.glob(".install-*")) and not list(root.glob(".old-*"))


def test_a_damaged_copy_is_found_when_loaded(fake_files):
    formula_ocr.install(opener=opener(FAKE, []))
    (formula_ocr.MODEL_DIR / "tokenizer.json").write_bytes(b"[]")  # same size, changed
    assert formula_ocr.installed()  # (the quick check: sizes)
    with pytest.raises(formula_ocr.ModelDamaged):
        formula_ocr.verify(formula_ocr.MODEL_DIR)


def test_install_in_the_background_reports_progress_and_errors(fake_files, monkeypatch):
    asked = []
    monkeypatch.setattr(formula_ocr.urllib.request, "urlopen", opener(FAKE, asked))
    formula_ocr.start_install()
    deadline = time.monotonic() + 10
    while formula_ocr.status()["installing"] and time.monotonic() < deadline:
        time.sleep(0.02)
    state = formula_ocr.status()
    assert state["installed"] and not state["error"] and state["done"] == state["total"]

    def offline(url, timeout):
        raise urllib.error.URLError("no network")

    monkeypatch.setattr(formula_ocr.urllib.request, "urlopen", offline)
    formula_ocr.start_install()
    while formula_ocr.status()["installing"] and time.monotonic() < deadline:
        time.sleep(0.02)
    state = formula_ocr.status()
    assert "no network" in state["error"] and state["installed"]  # the copy there stays


# --- recognising (a stand-in engine) ----------------------------------------------------------


class StandIn:
    """The engine's place in tests: what it was given, what it answers."""

    answer: list = []
    loaded = 0

    def __init__(self, folder):
        StandIn.loaded += 1

    def recognize(self, image, deadline, n_best=formula_ocr.N_BEST):
        result = StandIn.answer
        if isinstance(result, Exception):
            raise result
        if callable(result):
            return result(image, deadline)
        return result


@pytest.fixture
def stand_in(monkeypatch):
    monkeypatch.setattr(formula_ocr, "Engine", StandIn)
    monkeypatch.setattr(formula_ocr, "installed", lambda: True)
    formula_ocr._forget_engine()
    StandIn.loaded = 0
    yield StandIn
    formula_ocr._forget_engine()


def test_candidates_come_back_in_order_with_similar_scores_flagged(stand_in, no_network):
    stand_in.answer = [Candidate(r"\frac{1}{f}", -0.010), Candidate(r"\frac{1}{t}", -0.015)]
    found = formula_ocr.recognize(png())
    assert [c["latex"] for c in found["candidates"]] == [r"\frac{1}{f}", r"\frac{1}{t}"]
    assert found["similar"] is True and found["engine"] == formula_ocr.ENGINE_NAME
    stand_in.answer = [Candidate("a", -0.01), Candidate("b", -0.5)]
    assert formula_ocr.recognize(png())["similar"] is False
    stand_in.answer = [Candidate("a", -0.01)]
    assert formula_ocr.recognize(png())["similar"] is False  # one result: shown as it is
    assert stand_in.loaded == 1  # loaded once, then kept


def test_failures_are_reported_never_raised_raw(stand_in):
    stand_in.answer = []
    with pytest.raises(formula_ocr.FormulaError, match="no formula"):
        formula_ocr.recognize(png())
    stand_in.answer = RuntimeError("onnxruntime: bad allocation")
    with pytest.raises(formula_ocr.FormulaError, match="model failed") as failed:
        formula_ocr.recognize(png())
    assert failed.value.code == "failed"
    stand_in.answer = formula_ocr.TimedOut("too long")
    with pytest.raises(formula_ocr.TimedOut):
        formula_ocr.recognize(png())


def test_one_recognition_at_a_time(stand_in, monkeypatch):
    started, release = threading.Event(), threading.Event()

    def slow(image, deadline):
        started.set()
        release.wait(5)
        return [Candidate("x", -0.1)]

    stand_in.answer = slow
    monkeypatch.setattr(formula_ocr, "BUSY_WAIT", 0.1)
    first = threading.Thread(target=formula_ocr.recognize, args=(png(),))
    first.start()
    started.wait(5)
    with pytest.raises(formula_ocr.Busy):
        formula_ocr.recognize(png())
    release.set()
    first.join(5)
    assert formula_ocr.recognize(png())["candidates"]  # free again


def test_the_deadline_is_passed_to_the_engine(stand_in, monkeypatch):
    seen = []
    stand_in.answer = lambda image, deadline: (
        seen.append(deadline - time.monotonic()) or [Candidate("x", 0.0)]
    )
    formula_ocr.recognize(png(), timeout=7)
    assert 6 < seen[0] <= 7


# --- over HTTP --------------------------------------------------------------------------------


@pytest.fixture
def http(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"

    def call(path, data, json_body=False, token=library_server.TOKEN):
        body = json.dumps(data).encode() if json_body else data
        request = urllib.request.Request(base + path, data=body, method="POST",
                                         headers={"X-Library-Token": token})  # fmt: skip
        try:
            with urllib.request.urlopen(request, timeout=20) as answer:
                return answer.status, json.loads(answer.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    yield call
    server.shutdown()
    server.server_close()


def test_the_endpoints(http, stand_in, monkeypatch):
    assert http("/api/formula/recognize", png(), token="wrong")[0] == 403
    status, answer = http("/api/formula/recognize", b"not an image")
    assert status == 400 and "PNG" in answer["error"]
    stand_in.answer = [Candidate(r"E=h\nu", -0.01)]
    status, answer = http("/api/formula/recognize", png())
    assert status == 200 and answer["candidates"][0]["latex"] == r"E=h\nu"
    stand_in.answer = formula_ocr.TimedOut("too long")
    assert http("/api/formula/recognize", png()) == (504, {"error": "too long", "code": "timeout"})
    monkeypatch.setattr(formula_ocr, "installed", lambda: False)
    status, answer = http("/api/formula/recognize", png())
    assert status == 503 and answer["code"] == "not-installed"
    status, answer = http("/api/formula/status", {}, json_body=True)
    assert status == 200 and answer["installed"] is False and answer["license"] == "MIT"
    # the download only on an explicit choice
    started = []
    monkeypatch.setattr(formula_ocr, "start_install", lambda stop: started.append(1) or {})
    assert http("/api/formula/install", {}, json_body=True)[0] == 400
    assert http("/api/formula/install", {"consent": "yes"}, json_body=True)[0] == 400
    assert not started
    assert http("/api/formula/install", {"consent": True}, json_body=True)[0] == 200
    assert started == [1]


# --- the real model (only where it is installed) -------------------------------------------------

needs_model = pytest.mark.skipif(
    not (REAL_MODEL / formula_ocr.MARKER).exists(),
    reason="the formula model isn't installed (uv run scripts/formula_ocr.py --setup)",
)

# (formula, how matplotlib draws it; the meaning the result must have, spacing aside)
REAL = [
    (r"\int_0^1 x^2\,dx=\frac{1}{3}", r"\int_0^1 x^2\,dx=\frac{1}{3}"),
    (r"\frac{1}{f}=\frac{1}{s}+\frac{1}{s'}", r"\frac{1}{f}=\frac{1}{s}+\frac{1}{s'}"),
    (r"I(r)=I_0\exp\left(-\frac{2r^2}{w^2}\right)", r"I(r)=I_0\exp\left(-\frac{2r^2}{w^2}\right)"),
    (r"n_1\sin\theta_1=n_2\sin\theta_2", r"n_1\sin\theta_1=n_2\sin\theta_2"),
    (r"z_R=\frac{\pi w_0^2}{\lambda}", r"z_R=\frac{\pi w_0^2}{\lambda}"),
    (r"E=h\nu", r"E=h\nu"),
]


def norm(latex: str) -> str:
    """Spacing, \\left/\\right, \\cfrac for \\frac (display style) and braces around one token
    never change a formula's meaning."""
    import re

    latex = re.sub(r"\\(left|right|big|Big)(?![a-zA-Z])|\\[,;!]|~|\s", "", latex)
    latex = re.sub(r"\\cfrac(?![a-zA-Z])", r"\\frac", latex)
    latex = latex.replace("^{\\prime}", "'").replace("^\\prime", "'").replace("^{'}", "'")
    for _ in range(4):
        latex = re.sub(r"\{(\\?[a-zA-Z0-9])\}", r"\1", latex)
    return latex


def drawn(latex: str, fontset: str = "cm") -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["mathtext.fontset"] = fontset
    figure = plt.figure(figsize=(0.01, 0.01))
    figure.text(0, 0, f"${latex}$", fontsize=16)
    out = io.BytesIO()
    figure.savefig(out, format="png", dpi=150, bbox_inches="tight", pad_inches=0.08,
                   facecolor="white")  # fmt: skip
    plt.close(figure)
    return out.getvalue()


@pytest.fixture
def real_model(monkeypatch):
    monkeypatch.setattr(formula_ocr, "MODEL_DIR", REAL_MODEL)
    formula_ocr._forget_engine()
    yield
    formula_ocr._forget_engine()


@needs_model
def test_real_model_is_the_pinned_one(real_model):
    formula_ocr.verify(REAL_MODEL)


def test_runtime_missing_is_actionable_and_does_not_reinstall(stand_in, monkeypatch):
    def missing(folder):
        raise ImportError("onnxruntime missing")

    monkeypatch.setattr(formula_ocr, "Engine", missing)
    with pytest.raises(formula_ocr.RuntimeUnavailable, match="does not need reinstalling"):
        formula_ocr.recognize(png())


def test_model_load_failure_is_reported_cleanly(stand_in, monkeypatch):
    def broken(folder):
        raise RuntimeError("cannot load ONNX")

    monkeypatch.setattr(formula_ocr, "Engine", broken)
    with pytest.raises(formula_ocr.FormulaError, match="cannot load ONNX"):
        formula_ocr.recognize(png())


@needs_model
@pytest.mark.parametrize("latex, meaning", REAL)
def test_real_model_reads_printed_formulas_offline(real_model, no_network, latex, meaning):
    found = formula_ocr.recognize(drawn(latex))
    results = [c["latex"] for c in found["candidates"]]
    assert 1 <= len(results) <= formula_ocr.N_BEST
    assert norm(meaning) in [norm(r) for r in results], results
    assert found["seconds"] < formula_ocr.TIMEOUT


@needs_model
def test_real_model_reads_a_dark_mode_and_a_transparent_screenshot(real_model, no_network):
    image = Image.open(io.BytesIO(drawn(r"E=h\nu"))).convert("RGB")
    dark = Image.eval(image, lambda v: 255 - v)
    transparent = image.convert("L").point(lambda v: 255 - v)
    clear = Image.new("RGBA", image.size, (0, 0, 0, 0))
    clear.putalpha(transparent)
    for shown in (dark, clear):
        out = io.BytesIO()
        shown.save(out, "PNG")
        results = [c["latex"] for c in formula_ocr.recognize(out.getvalue())["candidates"]]
        assert norm(r"E=h\nu") in [norm(r) for r in results], results
