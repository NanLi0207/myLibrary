"""Back up the library to its git remote (GitHub): the library page's ☁ Back up button.

    uv run scripts/backup.py        # the same from the terminal

Only the library folder is committed (notes, reading progress, vocabulary, shelves, topic
notes, glossaries, catalog); never PDFs, and never other changes in the repository, staged or
not. It refuses to push when there are unpushed commits that change anything outside the
library (that's code: push it yourself, knowingly). Git never waits for a password: if GitHub
can't be reached, the button just says so.
"""

import argparse
import os
import subprocess
from datetime import datetime
from pathlib import Path

import paths

LIBRARY = paths.LIBRARY
# Never wait for a password or passphrase prompt that nobody can answer
GIT_ENV = {"GIT_TERMINAL_PROMPT": "0", "GIT_SSH_COMMAND": "ssh -o BatchMode=yes"}


def git(*args: str, check: bool = True) -> str:
    done = subprocess.run(
        ["git", "-C", str(LIBRARY), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        env=os.environ | GIT_ENV,
    )
    if check and done.returncode != 0:
        lines = (done.stderr or done.stdout).strip().splitlines()
        raise RuntimeError(lines[-1] if lines else "git failed")
    return done.stdout.strip()


def available() -> bool:
    """Is the library inside a git repository whose branch has a remote to push to?"""
    try:
        git("rev-parse", "--show-toplevel")
        return bool(git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"))
    except RuntimeError, OSError, subprocess.SubprocessError:
        return False


def _summary(files: list[str], prefix: str) -> str:
    """'3 files: shannon-1997-art-science-optical-design, topics' from the changed paths."""
    parts = []
    for f in files:
        rest = f.removeprefix(prefix).split("/")
        name = rest[1] if rest[0] == "notes" and len(rest) > 2 else rest[0]
        if name not in parts:
            parts.append(name)
    shown = ", ".join(parts[:4]) + (", …" if len(parts) > 4 else "")
    return f"{len(files)} file{'s' if len(files) != 1 else ''}: {shown}"


def back_up() -> dict:
    """Commit the library's changes and push. Returns {"ok": bool, "message": str}."""
    if not available():
        return {"ok": False, "message": "Back up needs the library in a git repository with a "
                "remote (e.g. GitHub)"}  # fmt: skip
    root = Path(git("rev-parse", "--show-toplevel"))
    prefix = LIBRARY.resolve().relative_to(root.resolve()).as_posix()
    prefix = "" if prefix == "." else prefix + "/"
    library = "."  # git runs inside the library folder: "." is exactly the library

    # Unpushed commits that touch anything outside the library: code, not ours to publish
    outside = [
        f
        for f in git("diff", "--name-only", "@{upstream}...HEAD").splitlines()
        if f and not f.startswith(prefix)
    ]
    if prefix and outside:
        return {"ok": False, "message": f"Not backed up: {len(outside)} changed file(s) outside "
                "the library are waiting to be pushed (code). Push those first."}  # fmt: skip

    git("add", "-A", "--", library)
    staged = git("diff", "--cached", "--name-only", "--", library).splitlines()
    pdfs = [f for f in staged if f.lower().endswith(".pdf")]
    if pdfs:  # .gitignore should make this impossible; never publish a book
        git("reset", "-q", "--", *pdfs)
        return {
            "ok": False,
            "message": f"Not backed up: a PDF was about to be included ({pdfs[0]})",
        }
    committed = ""
    if staged:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        # "--only" with paths: commits just the library, whatever else is staged
        git("commit", "-q", "--only", "-m", f"Back up library {stamp} ({_summary(staged, prefix)})",
            "--", library)  # fmt: skip
        committed = _summary(staged, prefix)
    if int(git("rev-list", "--count", "@{upstream}..HEAD") or 0) == 0:
        return {"ok": True, "message": "Already backed up: nothing changed since the last time"}
    try:
        git("push", "-q")
    except RuntimeError as e:
        saved = f"Saved locally ({committed}) but" if committed else "Changes are saved locally but"
        return {"ok": False, "message": f"{saved} not pushed to GitHub: {e}"}
    return {"ok": True, "message": f"Backed up to GitHub ({committed or 'earlier changes'})"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    paths.add_argument(parser)
    parser.parse_args()
    print(back_up()["message"])


if __name__ == "__main__":
    main()
