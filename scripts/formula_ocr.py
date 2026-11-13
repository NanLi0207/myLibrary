"""Formula recognition (task 4 M5e): a screenshot of a formula becomes editable LaTeX, on this
computer only.

Optional, and free: the model is downloaded only when the user asks for it (the notes panel's
∑ dialog, or `uv run scripts/formula_ocr.py --setup`), once; after that recognition needs no
network at all. Nothing is ever sent anywhere: the image goes from the page to this local
server and into the model, and is not kept.

The engine (an adapter: `Engine`, the only class that knows the model):
  Pix2Text MFR 1.5 by breezedeus (https://huggingface.co/breezedeus/pix2text-mfr-1.5, MIT
  licence; a TrOCR-style encoder–decoder exported to ONNX), run with onnxruntime on the CPU.
  onnxruntime, numpy and Pillow are already core dependencies (RapidOCR uses them), so the
  model files are all that is added. The files are pinned to one revision and each is checked
  against its SHA-256 when installed and again when first loaded.

Recognition: the image is checked (image_check), its margins trimmed, then decoded with a beam
search that keeps up to N_BEST different results. They are only the model's guesses: the
page shows them all for the user to check, correct and confirm. Their scores are the model's
own (mean log-probability per token), not a measured accuracy, and are never shown as one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import threading
import time
import urllib.request
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import image_check
import paths
import platform_services
import safe_io

ENGINE_NAME = "Pix2Text MFR 1.5"
MODEL_PAGE = "https://huggingface.co/breezedeus/pix2text-mfr-1.5"
MODEL_LICENSE = "MIT"
REVISION = "1cef9f0bdcd6a4c63df7de1311fb0894593340cc"  # the model repository's commit
SOURCE = f"{MODEL_PAGE}/resolve/{REVISION}/"
FILES = {  # name -> (size in bytes, SHA-256)
    "encoder_model.onnx": (
        87_510_770, "080a3f660f08bc9ebcacdd96e34be6b6400f8c7e62d7cd0dd8251badc37f610b"),
    "decoder_model.onnx": (
        32_026_253, "917deb98e91a0453c5f234f58a0f32f9fb037de8527c7eb4ed394daf9e692f2a"),
    "tokenizer.json": (
        113_168, "4ffbeb2143e6a38324bb6111b7a8109530d38a076a8439aa5777535f0a32758a"),
    "README.md": (  # the model card: its licence and origin, kept with the model
        9_441, "7ae7136c49c64378ff09a86b750ef9c2007ad8e91e148be391e3480bfd9dce97"),
}  # fmt: skip
DOWNLOAD_BYTES = sum(size for size, _ in FILES.values())
MARKER = ".myLibrary-formula-model.txt"
LOCK = ".install.lock"  # beside the model's folder: held by the one install running


def _model_dir() -> Path:
    """The tool's own cache in development; in the package, this computer's user-data folder
    (an update or reinstall of the package never touches it, and nothing is written into the
    application's folder)."""
    base = platform_services.user_data_dir() if paths.IS_PACKAGE else paths.APP / ".cache"
    return base / "formula-ocr" / "pix2text-mfr-1.5"


MODEL_DIR = _model_dir()

N_BEST = 3  # different results shown at most
BEAMS = 3  # the beam search's width (each step costs about BEAMS times a greedy one)
MAX_TOKENS = 400  # a long multi-line formula is about 300
TIMEOUT = 30.0  # seconds for one recognition
BUSY_WAIT = 20.0  # seconds a request waits for another recognition to finish
SIMILAR = 0.01  # top two results closer than this (mean log-probability): "similar"
THREADS = 4  # CPU threads for the model (the server keeps the rest)


class FormulaError(Exception):
    """Recognition couldn't be done; `code` tells the page which (its message says why)."""

    code = "failed"


class NotInstalled(FormulaError):
    code = "not-installed"


class RuntimeUnavailable(FormulaError):
    code = "unavailable"


class ModelDamaged(FormulaError):
    code = "damaged"


class Busy(FormulaError):
    code = "busy"


class TimedOut(FormulaError):
    code = "timeout"


class InstallBusy(FormulaError):
    """Another install of the model is running (the page's or `--setup`'s)."""

    code = "busy"


class Cancelled(Exception):
    """The install was stopped (myLibrary is quitting): nothing was installed."""


# --- the model's files ------------------------------------------------------------------


def _marker_ok(folder: Path) -> bool:
    try:
        return (folder / MARKER).read_text(encoding="utf-8").split()[:1] == [REVISION]
    except OSError, UnicodeDecodeError:
        return False


def installed() -> bool:
    """Quick check (no hashing): the pinned model is in place, each file of the right size."""
    if not _marker_ok(MODEL_DIR):
        return False
    try:
        return all((MODEL_DIR / n).stat().st_size == size for n, (size, _) in FILES.items())
    except OSError:
        return False


def verify(folder: Path) -> None:
    """Every file there and unchanged (SHA-256), else ModelDamaged."""
    if not _marker_ok(folder):
        raise ModelDamaged("the formula model's files aren't the expected version")
    for name, (size, digest) in FILES.items():
        sha = hashlib.sha256()
        try:
            with open(folder / name, "rb") as f:
                while chunk := f.read(1 << 20):
                    sha.update(chunk)
        except OSError:
            raise ModelDamaged(f"the formula model's {name} is missing") from None
        if sha.hexdigest() != digest or (folder / name).stat().st_size != size:
            raise ModelDamaged(f"the formula model's {name} is damaged")


_install_lock = threading.Lock()
_install_state = {"state": "idle", "done": 0, "total": DOWNLOAD_BYTES, "error": ""}


def _fetch(url: str, dest: Path, size: int, digest: str, progress, stop, opener) -> None:
    """One file, checked while it arrives: never more than its size, then its SHA-256."""
    sha = hashlib.sha256()
    got = 0
    with opener(url, timeout=60) as response, open(dest, "xb") as out:
        while chunk := response.read(1 << 20):
            if stop():
                raise Cancelled()
            got += len(chunk)
            if got > size:
                raise ValueError(f"{dest.name}: the download is larger than expected")
            sha.update(chunk)
            out.write(chunk)
            progress(len(chunk))
    if got != size or sha.hexdigest() != digest:
        raise ValueError(f"{dest.name}: the download isn't the expected file (checksum)")


@contextmanager
def _owning_install(root: Path):
    """While held, this process is the only one installing the model into `root` (the
    page's download and `--setup` in a terminal may both try). An operating-system lock on
    `root/.install.lock`: released by the system when the process ends, however it ends, so
    a cut-off install never keeps it. InstallBusy at once if another install holds it."""
    handle = open(root / LOCK, "a+b")  # (held for the whole install)
    try:
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise InstallBusy("another download of the formula model is running (from this "
                              "page or the terminal); wait for it to finish") from None  # fmt: skip
        yield
    finally:
        handle.close()  # (releases the lock)


def install(progress=lambda n: None, stop=lambda: False, opener=None) -> None:
    """Download the pinned model (DOWNLOAD_BYTES) and put it in place. Each file is checked
    against its size and SHA-256; the new folder is swapped in only once all of them are
    right, so a failed or stopped download leaves the installed copy (if any) as it was. One
    install at a time (_owning_install); InstallBusy while another runs."""
    opener = opener or urllib.request.urlopen
    root = MODEL_DIR.parent
    root.mkdir(parents=True, exist_ok=True)
    with _owning_install(root):
        # Holding the lock, no other install is running: anything left beside the model was
        # left by one that was cut off; a whole copy there is put back first, never deleted
        _recover(root)
        _install_into(root, progress, stop, opener)
    _forget_engine()


def _install_into(root: Path, progress, stop, opener) -> None:
    """The download into a new folder, checked, then swapped in. The installed copy (if any)
    is moved aside first and deleted only once the checked new one is in place; if the swap
    fails and the installed copy can't be put back either, it stays whole in .old-*, where
    _recover finds it. A cut-off process (no chance to clean up) leaves the same: the next
    install, status() or recognition puts a whole copy back."""
    new = root / f".install-{uuid.uuid4().hex[:8]}"
    new.mkdir()
    try:
        for name, (size, digest) in FILES.items():
            _fetch(SOURCE + name, new / name, size, digest, progress, stop, opener)
        safe_io.write_text(new / MARKER, f"{REVISION}\n{ENGINE_NAME}\n", encoding="utf-8")
        verify(new)
    except BaseException:
        shutil.rmtree(new, ignore_errors=True)  # an incomplete download: nothing of value
        raise
    old = None
    if MODEL_DIR.exists():
        old = root / f".old-{uuid.uuid4().hex[:8]}"
        MODEL_DIR.replace(old)
    try:
        new.replace(MODEL_DIR)
    except BaseException:
        if old is not None and not MODEL_DIR.exists():
            try:
                old.replace(MODEL_DIR)  # the installed copy back in place
            except OSError:
                pass  # (it stays whole in .old-*: _recover puts it back)
        raise  # (the checked download stays too, in .install-*: also a whole copy)
    if old is not None:
        shutil.rmtree(old, ignore_errors=True)  # replaced by a checked copy


def _whole(folder: Path) -> bool:
    """The pinned model, every file there and unchanged (SHA-256)."""
    try:
        verify(folder)
        return True
    except ModelDamaged:
        return False


def _leftovers(root: Path) -> list[Path]:
    return sorted([*root.glob(".install-*"), *root.glob(".old-*")])


def _recover(root: Path) -> None:
    """Holding the install lock, after an install that was cut off: if the installed model
    isn't whole, a whole copy left beside it (.old-*: the copy being replaced; .install-*: a
    checked download not yet in place) takes its place. Leftovers are deleted only when the
    installed model is whole (they are then spare) or when they aren't whole themselves:
    the last whole copy is never deleted."""
    if not _whole(MODEL_DIR):
        for spare in _leftovers(root):
            if not _whole(spare):
                continue
            aside = None
            if MODEL_DIR.exists():  # damaged or incomplete: moved aside, deleted below
                aside = root / f".old-{uuid.uuid4().hex[:8]}-damaged"
                MODEL_DIR.replace(aside)
            try:
                spare.replace(MODEL_DIR)
            except OSError:
                if aside is not None and not MODEL_DIR.exists():
                    aside.replace(MODEL_DIR)  # as it was
                raise
            break
    whole = _whole(MODEL_DIR)
    for spare in _leftovers(root):
        if whole or not _whole(spare):
            shutil.rmtree(spare, ignore_errors=True)


def recover_interrupted() -> bool:
    """Put back a whole copy left by an install that was cut off (the model then works
    offline again with no new download). False when there is nothing to do, or while an
    install is running (it does this itself)."""
    root = MODEL_DIR.parent
    if not root.is_dir() or not _leftovers(root):
        return False
    try:
        with _owning_install(root):
            _recover(root)
    except InstallBusy:
        return False
    _forget_engine()
    return installed()


def start_install(stop=lambda: False) -> dict:
    """Install in the background (the page polls status()); one at a time."""
    with _install_lock:
        if _install_state["state"] == "downloading":
            return status()
        _install_state.update(state="downloading", done=0, total=DOWNLOAD_BYTES, error="")

    def advance(n: int) -> None:
        _install_state["done"] += n

    def run() -> None:
        try:
            install(advance, stop)
            _install_state.update(state="idle", error="")
        except Cancelled:
            _install_state.update(state="failed", error="stopped: myLibrary was quitting")
        except Exception as e:  # network, disk, checksum: said on the page, nothing installed
            _install_state.update(state="failed", error=str(e)[:300])

    threading.Thread(target=run, name="formula-model-install", daemon=True).start()
    return status()


def status() -> dict:
    """What the page shows: installed or not, a download in progress, its last error. A
    whole copy left by a cut-off install is put back first (recover_interrupted)."""
    state = dict(_install_state)
    present = installed() or recover_interrupted()
    return {
        "installed": present,
        "installing": state["state"] == "downloading",
        "done": state["done"],
        "total": state["total"],
        "error": state["error"] if state["state"] == "failed" else "",
        "engine": ENGINE_NAME,
        "license": MODEL_LICENSE,
        "source": MODEL_PAGE,
        "download_bytes": DOWNLOAD_BYTES,
    }


# --- the engine (the adapter: the only code that knows this model) --------------------------


def _bytes_to_unicode() -> dict[int, str]:
    """The byte-level BPE's table (as GPT-2's): each byte is one printable character."""
    keep = [*range(ord("!"), ord("~") + 1), *range(ord("¡"), ord("¬") + 1),
            *range(ord("®"), ord("ÿ") + 1)]  # fmt: skip
    table = {b: chr(b) for b in keep}
    extra = 0
    for b in range(256):
        if b not in table:
            table[b] = chr(256 + extra)
            extra += 1
    return table


BYTE_OF = {c: b for b, c in _bytes_to_unicode().items()}


@dataclass(frozen=True)
class Candidate:
    latex: str
    score: float  # the model's mean log-probability per token (not an accuracy)


class Engine:
    """Pix2Text MFR 1.5: a DeiT encoder (384 × 384 pixels) and a TrOCR decoder (byte-level
    BPE, 1,868 tokens; no cache of past steps in this export, so each step reads the whole
    sequence so far). Another model would be another class with this one method."""

    START, END = 1, 2

    def __init__(self, folder: Path):
        import onnxruntime as ort  # (only when recognising: the server starts without it)

        verify(folder)
        options = ort.SessionOptions()
        options.intra_op_num_threads = THREADS
        options.inter_op_num_threads = 1
        cpu = ["CPUExecutionProvider"]
        self.encoder = ort.InferenceSession(str(folder / "encoder_model.onnx"), options,
                                            providers=cpu)  # fmt: skip
        self.decoder = ort.InferenceSession(str(folder / "decoder_model.onnx"), options,
                                            providers=cpu)  # fmt: skip
        tokenizer = json.loads((folder / "tokenizer.json").read_text(encoding="utf-8"))
        self.tokens = {i: t for t, i in tokenizer["model"]["vocab"].items()}
        self.special = {t["id"] for t in tokenizer["added_tokens"]}

    @staticmethod
    def pixels(image):
        """The model's input: on white (transparency flattened), dark text on a light
        background (a dark-mode screenshot is inverted), 384 × 384, scaled to [-1, 1]."""
        import numpy as np
        from PIL import Image

        image = trim(image)
        rgb = np.asarray(image, dtype=np.float32) / 255.0
        if rgb.mean() < 0.5:
            image = Image.fromarray((255 - np.asarray(image)).astype(np.uint8))
        image = image.resize((384, 384), Image.Resampling.BICUBIC)
        values = (np.asarray(image, dtype=np.float32) / 255.0 - 0.5) / 0.5
        return values.transpose(2, 0, 1)[None]

    def text(self, ids: list[int]) -> str:
        chars = "".join(self.tokens.get(i, "") for i in ids if i not in self.special)
        return bytes(BYTE_OF[c] for c in chars if c in BYTE_OF).decode("utf-8", "replace")

    def recognize(self, image, deadline: float, n_best: int = N_BEST) -> list[Candidate]:
        import numpy as np

        encoded = self.encoder.run(None, {"pixel_values": self.pixels(image)})[0]
        alive: list[tuple[list[int], float]] = [([self.START], 0.0)]
        done: list[tuple[float, list[int]]] = []  # (mean log-probability, tokens)
        for _ in range(MAX_TOKENS):
            if time.monotonic() > deadline:
                raise TimedOut("recognition took too long; try a smaller part of the formula")
            ids = np.array([seq for seq, _ in alive], dtype=np.int64)
            context = np.repeat(encoded, len(alive), axis=0)
            inputs = {"input_ids": ids, "encoder_hidden_states": context}
            logits = self.decoder.run(None, inputs)[0][:, -1, :].astype(np.float64)
            logits -= logits.max(axis=-1, keepdims=True)
            logp = logits - np.log(np.exp(logits).sum(axis=-1, keepdims=True))
            options = []
            for row, (seq, score) in enumerate(alive):
                for token in np.argsort(logp[row])[::-1][: BEAMS * 2]:
                    options.append((score + float(logp[row, token]), seq, int(token)))
            options.sort(key=lambda o: -o[0])
            alive = []
            for score, seq, token in options:
                if token == self.END:
                    if len(seq) > 1:
                        done.append((score / len(seq), seq[1:]))
                elif not repeating(seq + [token]):  # a runaway repetition: dropped
                    alive.append((seq + [token], score))
                if len(alive) == BEAMS:
                    break
            done.sort(key=lambda d: -d[0])
            if not alive:
                break
            # Enough results, and even the best unfinished one already scores below them
            if len(done) >= BEAMS and alive[0][1] / len(alive[0][0]) < done[BEAMS - 1][0]:
                break
        found: list[Candidate] = []
        seen: set[str] = set()
        for score, seq in done:
            latex = tidy(self.text(seq))
            key = same_key(latex)
            if latex and key not in seen:
                seen.add(key)
                found.append(Candidate(latex, round(score, 4)))
            if len(found) == n_best:
                break
        return found


SPACING = re.compile(r"\\[,;:! ]|~|\\q?quad(?![A-Za-z])|\s")


def same_key(latex: str) -> str:
    r"""What two results must share to count as one: they differ only in spacing (\, ~ \quad),
    \ge / \geq, \le / \leq. Never braces or anything else that can change a formula."""
    key = SPACING.sub("", latex)
    return re.sub(r"\\(ge|le)(?![A-Za-z])", r"\\\1q", key)


def repeating(seq: list[int], times: int = 16) -> bool:
    """The sequence ends in one short pattern (1–4 tokens) repeated `times` times: the model
    is stuck (e.g. "\\! \\! \\! ..."), never a real formula."""
    for size in range(1, 5):
        tail = seq[-size * times :]
        if len(tail) == size * times and tail == tail[:size] * times:
            return True
    return False


def trim(image, pad: int = 8):
    """The image on white with its plain margins cut to `pad` pixels: the model was trained on
    tightly cropped formulas."""
    from PIL import Image, ImageChops

    if image.mode in ("RGBA", "LA", "PA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        image = Image.alpha_composite(Image.new("RGBA", rgba.size, "white"), rgba)
    image = image.convert("RGB")
    corner = image.getpixel((0, 0))
    difference = ImageChops.difference(image, Image.new("RGB", image.size, corner))
    box = difference.convert("L").point(lambda v: 255 if v > 24 else 0).getbbox()
    if not box:
        return image
    left, top, right, bottom = box
    cropped = image.crop((left, top, right, bottom))
    framed = Image.new("RGB", (cropped.width + 2 * pad, cropped.height + 2 * pad), corner)
    framed.paste(cropped, (pad, pad))
    return framed


# --- tidying the model's LaTeX ------------------------------------------------------------

# The model writes one token per word: "I _ { 0 } \operatorname { e x p } ( - \cfrac ...".
# tidy() only removes what never changes the formula: spaces, \! (negative thin spaces), the
# braces around a lone sub- or superscript, a font command's letters written apart. Known
# functions written as \operatorname{sin} become \sin (the same typesetting). Other commands
# stay as the model wrote them, \cfrac included (a fraction set in display style: valid, and
# it isn't this tool's to restyle; the user can change it before inserting).
FUNCTIONS = frozenset(
    "sin cos tan cot sec csc arcsin arccos arctan sinh cosh tanh coth exp log ln lg lim "
    "liminf limsup max min sup inf det dim ker deg gcd hom arg Pr".split()
)
WORD_COMMANDS = frozenset(
    r"\operatorname \operatorname* \mathrm \mathbf \mathit \mathsf \mathtt \mathcal "
    r"\mathbb \mathfrak \boldsymbol \text \textrm \textbf \textit \textsf \texttt \mbox".split()
)
TEXT_COMMANDS = frozenset(r"\text \textrm \textbf \textit \textsf \texttt \mbox".split())
GREEK = (
    "alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa lambda mu nu "
    "xi pi varpi rho varrho sigma varsigma tau upsilon phi varphi chi psi omega Gamma Delta "
    "Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega"
).split()
LONE_SCRIPTS = frozenset(
    [f"\\{g}" for g in GREEK]
    + r"\prime \infty \ast \star \circ \dagger \ddagger \top \perp \pm \mp \cdot \bullet".split()
)
CONTROL_WORD_END = re.compile(r"\\[A-Za-z]+\*?$")


def _plain(token: str) -> bool:
    """One character that can be part of a word (not a brace or a backslash)."""
    return len(token) == 1 and token not in "{}\\"


def _closing(tokens: list[str], opening: int) -> int:
    depth = 0
    for i in range(opening, len(tokens)):
        depth += {"{": 1, "}": -1}.get(tokens[i], 0)
        if depth == 0:
            return i
    return -1


def tidy(raw: str) -> str:
    """The model's LaTeX, written as a person would: the same formula, fewer spaces."""
    tokens = raw.split()
    out: list[str] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == "\\!":
            i += 1
            continue
        if token in WORD_COMMANDS and i + 1 < len(tokens) and tokens[i + 1] == "{":
            end = _closing(tokens, i + 1)
            inner = tokens[i + 2 : end] if end > 0 else []
            if inner and all(_plain(t) or t == "~" for t in inner):
                word = "".join(" " if t == "~" else t for t in inner).strip()
                if token not in TEXT_COMMANDS:
                    word = word.replace(" ", "")
                if token in (r"\operatorname", r"\mathrm") and word in FUNCTIONS:
                    out.append("\\" + word)
                elif word:
                    out.append(f"{token}{{{word}}}")
                i = end + 1
                continue
        out.append(token)
        i += 1
    while out and out[-1] == "\\":  # a lone backslash at the end is never valid LaTeX
        out.pop()
    # x _ { 0 } -> x_0: braces around one letter or digit (or a Greek letter, \prime, ...);
    # never other characters: s^{'} is valid, s^' is not
    joined: list[str] = []
    i = 0
    while i < len(out):
        if (out[i] in ("_", "^") and i + 3 < len(out) and out[i + 1] == "{"
                and out[i + 3] == "}" and (out[i + 2].isalnum() and len(out[i + 2]) == 1
                                           or out[i + 2] in LONE_SCRIPTS)):  # fmt: skip
            joined += [out[i], out[i + 2]]
            i += 4
            continue
        joined.append(out[i])
        i += 1
    text = ""
    for token in joined:  # a space only where LaTeX needs one: \sin x, not \sinx
        if text and CONTROL_WORD_END.search(text) and token[:1].isalpha():
            text += " "
        text += token
    return text


# --- recognising ------------------------------------------------------------------------

_engine: Engine | None = None
_run_lock = threading.Lock()  # one recognition (and one model load) at a time


def _forget_engine() -> None:
    global _engine
    with _run_lock:
        _engine = None


def recognize(data: bytes, *, timeout: float = TIMEOUT) -> dict:
    """{candidates: [{latex, score}], similar, engine, seconds} for a screenshot of a formula.
    `similar`: the top two scored almost the same (the page says so). ImageError for an image
    it can't take; FormulaError otherwise. Nothing is stored and nothing goes online."""
    global _engine
    _, image = image_check.decode(data)
    if not installed() and not recover_interrupted():  # (offline again after a cut-off install)
        image.close()
        raise NotInstalled("formula recognition isn't installed yet")
    if not _run_lock.acquire(timeout=BUSY_WAIT):
        image.close()
        raise Busy("another formula is being recognised; try again in a moment")
    try:
        started = time.monotonic()
        try:
            if _engine is None:
                _engine = Engine(MODEL_DIR)
            found = _engine.recognize(image, started + timeout)
        except ImportError:
            raise RuntimeUnavailable(
                "the local OCR runtime is unavailable; repair the application's dependencies "
                "(source installation: uv sync); the model does not need reinstalling"
            ) from None
        except FormulaError:
            raise
        except Exception as e:  # the runtime itself failed: said on the page
            raise FormulaError(f"the formula model failed: {str(e)[:200]}") from None
        seconds = round(time.monotonic() - started, 2)
    finally:
        _run_lock.release()
        image.close()
    if not found:
        raise FormulaError("no formula was recognised in this image")
    similar = len(found) > 1 and found[0].score - found[1].score < SIMILAR
    return {
        "candidates": [{"latex": c.latex, "score": c.score} for c in found],
        "similar": similar,
        "engine": ENGINE_NAME,
        "seconds": seconds,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    size = f"about {DOWNLOAD_BYTES // 1_000_000} MB, once"
    parser.add_argument("--setup", action="store_true", help=f"download the model ({size})")
    parser.add_argument("--status", action="store_true", help="is the model installed?")
    parser.add_argument("image", nargs="*", help="recognise these images (PNG, JPEG, WebP)")
    args = parser.parse_args()
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    if args.setup:
        if installed():
            verify(MODEL_DIR)
            print(f"  {ENGINE_NAME} is already installed (checksums verified)")
        else:
            print(f"  downloading {ENGINE_NAME} ({DOWNLOAD_BYTES / 1e6:.0f} MB, {MODEL_LICENSE}) "
                  f"from {MODEL_PAGE} ...")  # fmt: skip
            try:
                install()
            except InstallBusy as e:
                print(f"  {e}")
                return
            print(f"  installed in {MODEL_DIR} (checksums verified); it now works offline")
    if args.status or not (args.setup or args.image):
        print(f"  {ENGINE_NAME}: {'installed' if installed() else 'not installed'} ({MODEL_DIR})")
    for name in args.image:
        try:
            found = recognize(Path(name).read_bytes())
        except (image_check.ImageError, FormulaError) as e:
            print(f"{name}: {e}")
            continue
        print(f"{name} ({found['seconds']} s{', similar scores' if found['similar'] else ''}):")
        for c in found["candidates"]:
            print(f"  {c['latex']}    [{c['score']}]")


if __name__ == "__main__":
    main()
