"""Back up the library to its git remote (GitHub): the library page's ☁ Back up button.

    uv run scripts/backup.py        # the same from the terminal

**PAUSED (DEFERRED below, owner decision 2026-11-12):** while DEFERRED is True, as now, a
backup does nothing in git at all: no commit, no push, no change to the index, a branch or
any ref, and no replay or deletion of a recovery record (it only reports one). The page shows
"☁ Back up (paused)"; the 💾 folder backup is the backup of notes and images. Everything below
describes the dormant implementation, kept for a security redesign: five High findings from
the third independent review remain unresolved in it (ROADMAP L29), so it must not be switched
back on as it is.

The dormant design. Only the library folder is committed (notes, reading progress, vocabulary,
shelves, topic notes, glossaries, catalog); never PDFs, never pasted note images
(notes/<name>/assets/: they may hold copyrighted pages or personal work; the folder backup
keeps them), and never other
changes in the repository. Git never waits for a password: if GitHub can't be reached, the
button just says so.

How it publishes (fail closed: whatever it can't make sure of, it refuses and says why):
- Where: the checked-out branch (never a detached HEAD), its upstream remote and branch, and
  nothing else: an explicit `<commit>:<branch>` push with a lease on the audited upstream
  commit, no tags, no submodules; push.default, push refspecs and mirror settings can't widen
  it. A push remote other than the upstream's is refused as ambiguous.
- What: every commit that would be published (upstream..branch, and the new one) is checked
  whole: no PDF and no note image anywhere in the library in any of their trees (so neither
  one added and deleted again, nor one already tracked, slips through), and no change outside
  the library in any of them (that's code: push it yourself, knowingly).
- The commit is built in a temporary index of its own (HEAD plus the library as it is, images
  left out by a pathspec, so no .gitignore is needed or changed), created with commit-tree
  (signed when commit.gpgSign says so; an unreadable setting or a failed signature is a
  refusal, never an unsigned commit) and put on the branch by name only if the branch is
  still where it was. Repositories with commit hooks are refused: commit-tree can't run them,
  and they are never bypassed, disabled or changed.
- The user's staging area: afterwards, holding git's own index.lock, only the entries of the
  files just committed that still equal the old commit's version are brought up to the new
  one (else git would show the backup undone as staged changes, and their next commit would
  record that). Everything else in the index stays exactly as it is. A journal in the git
  folder records the step until it is done; one left by an interruption is finished first.
"""

import argparse
import json
import os
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

import libraries
import paths
import safe_io

LIBRARY = paths.LIBRARY
# DEFERRED (owner decision, 2026-11-12, after the third independent review): automatic Git
# backup is switched off until a security redesign. back_up() then makes no commit, pushes
# nothing, never touches the index, a branch or any ref, and never replays or deletes a
# recovery record; it only says so. The implementation below is kept, unused by the app, for
# that redesign (its tests run it with DEFERRED off). The 💾 folder backup is unaffected, and
# so is the user's own use of git.
DEFERRED = True
DEFERRED_MESSAGE = (
    "Automatic Git backup is temporarily unavailable pending a security redesign: nothing was "
    "committed or pushed, and git was left exactly as it was. Your own git commits and pushes "
    "work as usual; use 💾 Back up for a local backup of your notes and images."
)
# Never wait for a password or passphrase prompt that nobody can answer
GIT_ENV = {"GIT_TERMINAL_PROMPT": "0", "GIT_SSH_COMMAND": "ssh -o BatchMode=yes"}
# Pasted note images, relative to the library (git runs in it): never staged by a backup
NO_ASSETS = ":(exclude,glob,icase)notes/**/assets/**"
TEMP_INDEX = "index.mylibrary-backup-"
JOURNAL = "mylibrary-backup-pending.json"
# Git states in which a commit would finish or disturb something the user started
IN_PROGRESS = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply")
# Hooks `git commit` runs and commit-tree doesn't
COMMIT_HOOKS = ("pre-commit", "prepare-commit-msg", "commit-msg", "post-commit")
NULL = "0" * 40


class Refused(Exception):
    """Why the backup didn't go ahead (said on the page as it is)."""


def _git(*args: str, env: dict | None = None, input: str | None = None):
    return subprocess.run(
        ["git", "-C", str(LIBRARY), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        env=os.environ | GIT_ENV | (env or {}),
        input=input,
    )


def git(*args: str, check: bool = True, env: dict | None = None, input: str | None = None,
        strip: bool = True) -> str:  # fmt: skip
    done = _git(*args, env=env, input=input)
    if check and done.returncode != 0:
        lines = (done.stderr or done.stdout).strip().splitlines()
        raise RuntimeError(lines[-1] if lines else "git failed")
    return done.stdout.strip() if strip else done.stdout


def names(*args: str, env: dict | None = None) -> list[str]:
    """File names from a git listing, exactly as they are (-z: never quoted, so a Chinese
    name is still seen to end in .pdf)."""
    command, *rest = args  # (-z straight after the command: never after a "--")
    return [n for n in git(command, "-z", *rest, env=env, strip=False).split("\0") if n]


def config(key: str) -> str | None:
    """A git setting's value; None when it isn't set; Refused when git can't read it."""
    done = _git("config", "--get", key)
    if done.returncode == 1:
        return None
    if done.returncode != 0:
        raise Refused(f"git's setting {key} can't be read ({done.stderr.strip()[:200]})")
    return done.stdout.strip()


def available() -> bool:
    """Is the library inside a git repository whose branch has a remote to push to? Never
    for the Test & Demo library (its working copy sits in the tool's folder, but is no part of
    the repository)."""
    if libraries.is_test_library(LIBRARY):
        return False
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


def note_asset(path: str) -> bool:
    """A pasted note image: a file in an assets/ folder under the library's notes/ (`path`
    relative to the library; as NO_ASSETS, whatever the case)."""
    parts = path.replace("\\", "/").lower().split("/")
    return parts[0] == "notes" and "assets" in parts[1:-1]


def _git_path(name: str) -> Path:
    return Path(git("rev-parse", "--path-format=absolute", "--git-path", name))


# --- where it goes ------------------------------------------------------------------------


def _destination() -> dict:
    """The branch (full ref), its commit, the remote and the remote branch it is published
    to, and the upstream commit last seen there. Refused when any of it is unclear."""
    branch = git("symbolic-ref", "-q", "HEAD", check=False)
    if not branch.startswith("refs/heads/"):
        raise Refused("git is on no branch (detached HEAD); check out the library's branch")
    short = branch.removeprefix("refs/heads/")
    remote, merge = config(f"branch.{short}.remote"), config(f"branch.{short}.merge")
    if not remote or remote == "." or not merge or not merge.startswith("refs/heads/"):
        raise Refused(f"the branch {short} has no upstream branch on a remote")
    for key in (f"branch.{short}.pushRemote", "remote.pushDefault"):
        if (other := config(key)) and other != remote:
            raise Refused(f"git pushes this branch to “{other}” ({key}) but its upstream is "
                          f"on “{remote}”: unclear where a backup should go")  # fmt: skip
    if (config(f"remote.{remote}.mirror") or "").lower() in ("true", "yes", "on", "1"):
        raise Refused(f"the remote “{remote}” is a mirror: a push would publish everything")
    upstream = git("rev-parse", "--symbolic-full-name", "@{upstream}")
    return {
        "branch": branch,
        "head": git("rev-parse", "--verify", f"{branch}^{{commit}}"),
        "remote": remote,
        "merge": merge,
        "upstream": upstream,
        "base": git("rev-parse", "--verify", f"{upstream}^{{commit}}"),
    }


def _still(where: dict, tip: str) -> None:
    """Still on the same branch, at `tip`, with the same upstream commit: else Refused."""
    if git("symbolic-ref", "-q", "HEAD", check=False) != where["branch"]:
        raise Refused("the checked-out branch changed while backing up; try again")
    if git("rev-parse", "--verify", where["branch"]) != tip:
        raise Refused("the branch moved while backing up (a commit was made meanwhile); "
                      "try again")  # fmt: skip
    if git("rev-parse", "--verify", f"{where['upstream']}^{{commit}}") != where["base"]:
        raise Refused("the upstream branch changed while backing up; try again")


# --- what it publishes --------------------------------------------------------------------


def _audit(commits: list[str], prefix: str) -> None:
    """Every commit to be published, whole: no PDF and no note image anywhere in the library
    in its tree, no change outside the library. Refused, naming the path and the commit."""
    for commit in commits:
        short = commit[:10]
        for name in names("ls-tree", "-r", "--full-tree", "--name-only", commit):
            if not name.startswith(prefix):
                continue
            inside = name[len(prefix) :]
            if inside.lower().endswith(".pdf"):
                raise Refused(f"a PDF is in the library in commit {short} ({inside}); a "
                              "backup never publishes a book: remove it from git's history "
                              "yourself (it stays on disk)")  # fmt: skip
            if note_asset(inside):
                raise Refused(f"a personal note image is tracked by git in commit {short} "
                              f"({inside}); remove it from git yourself (git rm --cached, "
                              "and from unpushed commits); the folder backup keeps "
                              "images")  # fmt: skip
        if prefix:
            changed = names("diff-tree", "-r", "-m", "--root", "--no-commit-id",
                            "--name-only", "--no-renames", commit)  # fmt: skip
            if outside := [f for f in changed if not f.startswith(prefix)]:
                raise Refused(f"commit {short} changes files outside the library "
                              f"({outside[0]}): that's code; push it yourself first")  # fmt: skip


def _in_progress() -> str:
    """Why a commit now would disturb what the user is doing in git, or ""."""
    for name in IN_PROGRESS:
        if _git_path(name).exists():
            return "a merge, rebase, cherry-pick or revert is in progress in git; finish it first"
    if git("ls-files", "-u"):
        return "git has unresolved conflicts; resolve them first"
    # Entries git hides from the working tree (skip-worktree, assume-unchanged): a commit from
    # a fresh index wouldn't keep them hidden
    if any(n[0] == "S" or n[0].islower() for n in names("ls-files", "-v", "--", ".")):
        return "some library files are marked skip-worktree or assume-unchanged in git"
    if (config("core.sparseCheckout") or "").lower() == "true" or list(
        _git_path("index").parent.glob("sharedindex.*")
    ):
        return "this repository uses a sparse checkout or a split index"
    return ""


def _hooks() -> str:
    """Commit hooks this repository has (commit-tree runs none of them), or ""."""
    folder = _git_path("hooks")
    found = [h for h in COMMIT_HOOKS if (folder / h).is_file()]
    configured = _git("config", "--get-regexp", r"^hook\..*\.event$")
    if configured.returncode not in (0, 1):
        raise Refused("git's hook settings can't be read")
    found += [line.split()[-1] for line in configured.stdout.splitlines()
              if line.split()[-1] in COMMIT_HOOKS]  # fmt: skip
    return ", ".join(sorted(set(found)))


def _signing() -> list[str]:
    """commit-tree's signing option from commit.gpgSign (commit-tree never reads it itself).
    Unset: none; a value git can't read as true or false: Refused."""
    done = _git("config", "--type=bool", "--get", "commit.gpgsign")
    if done.returncode == 1:
        return []
    if done.returncode != 0 or done.stdout.strip() not in ("true", "false"):
        raise Refused("git's setting commit.gpgSign can't be read as true or false; fix it "
                      "(git config commit.gpgSign true|false)")  # fmt: skip
    return ["-S"] if done.stdout.strip() == "true" else []


# --- the user's staging area --------------------------------------------------------------


def _tree(commit: str, wanted: set[str]) -> dict[str, tuple[str, str]]:
    found = {}
    for line in git("ls-tree", "-r", "-z", "--full-tree", commit, strip=False).split("\0"):
        if line:
            info, name = line.split("\t", 1)
            mode, _, sha = info.split()
            if name in wanted:
                found[name] = (mode, sha)
    return found


def _bring_up_to_date(journal: dict) -> str:
    """The journal's step: under git's index.lock, each file the backup committed whose
    index entry is still exactly the old commit's (a plain staged entry, no special state) is
    given the new commit's; one not in the index that the old commit didn't have either (a new
    file) is added. Anything else, staged by the user or another program, is left exactly as
    it is. "" when done; else why not (the journal stays, to finish later)."""
    if git("symbolic-ref", "-q", "HEAD", check=False) != journal["branch"]:
        return "the checked-out branch changed"
    index = _git_path("index")
    lock = Path(f"{index}.lock")
    try:  # git's own lock: no git command can change the index while it is held
        handle = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0))
    except FileExistsError:
        return "another program is using git's index (index.lock); try again in a moment"
    work = index.with_name(f"{TEMP_INDEX}{uuid.uuid4().hex[:12]}")
    published = False
    try:
        # Checked again now that nothing can change: the branch and where it points
        if git("symbolic-ref", "-q", "HEAD", check=False) != journal["branch"]:
            return "the checked-out branch changed"
        if git("rev-parse", "--verify", journal["branch"]) != journal["new"]:
            return "the branch moved on before git's staging area was brought up to date"
        if index.exists():
            work.write_bytes(index.read_bytes())
        paths_ = set(journal["paths"])
        old, new = _tree(journal["old"], paths_), _tree(journal["new"], paths_)
        current: dict[str, list[tuple[str, str, str, str]]] = {}
        for line in git("ls-files", "-s", "-v", "-z", "--full-name", "--", ":/",
                        env={"GIT_INDEX_FILE": str(work)}, strip=False).split("\0"):  # fmt: skip
            if line:
                info, name = line.split("\t", 1)
                tag, mode, sha, stage = info.split()
                if name in paths_:
                    current.setdefault(name, []).append((tag, mode, sha, stage))
        records = []
        for name in sorted(paths_):
            entries = current.get(name, [])
            # Exactly the old commit's version: one plain entry (tag H, stage 0), same mode
            # and blob. Anything else (staged by someone, a special state) is left alone
            untouched = name in old and entries == [("H", old[name][0], old[name][1], "0")]
            if untouched:
                mode, sha = new.get(name, ("0", NULL))
                records.append(f"{mode} {sha}\t{name}")
            elif not entries and name not in old and name in new:
                records.append(f"{new[name][0]} {new[name][1]}\t{name}")
        if records:
            git("update-index", "-z", "--index-info", env={"GIT_INDEX_FILE": str(work)},
                input="\0".join(records) + "\0")  # fmt: skip
            os.write(handle, work.read_bytes())
            os.fsync(handle)
        os.close(handle)
        handle = None
        if records:
            os.replace(lock, index)  # as git itself publishes an index
            published = True
        return ""
    except (OSError, RuntimeError) as e:
        return f"git's staging area couldn't be updated ({e})"
    finally:
        if handle is not None:
            os.close(handle)
        if not published:
            lock.unlink(missing_ok=True)
        work.unlink(missing_ok=True)
        Path(f"{work}.lock").unlink(missing_ok=True)


def _journal_path() -> Path:
    return _git_path(JOURNAL)


def _pending_note() -> str:
    """While DEFERRED: a recovery record left by an earlier backup, if any, is only reported
    (read-only: never replayed, changed or deleted)."""
    try:
        if libraries.is_test_library(LIBRARY) or _git("rev-parse", "--git-dir").returncode:
            return ""
        path = _journal_path()
    except OSError, RuntimeError, subprocess.SubprocessError:
        return ""
    if not path.exists():
        return ""
    return (f" An earlier backup left a recovery record ({path}); it is kept as it is and "
            "will be handled by the redesigned backup. Check “git status” before your next "
            "commit: files listed as staged that you didn't stage can be unstaged one by one "
            "(git restore --staged -- <file>).")  # fmt: skip


def _finish_pending() -> None:
    """A backup cut off after its commit and before git's staging area was brought up to
    date: finished now, or Refused (saying what to do) when it can't be."""
    path = _journal_path()
    if not path.exists():
        return
    try:
        journal = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refused(f"the record of an earlier backup ({path.name}) can't be read: {e}") from None
    if why := _bring_up_to_date(journal):
        branch = journal["branch"].removeprefix("refs/heads/")
        raise Refused(
            f"an earlier backup committed {journal['new'][:10]} on {branch}, but git's staging "
            f"area wasn't brought up to date ({why}). Check out {branch} and back up again. If "
            "the branch has moved on since, check “git status”: files listed as staged that "
            "you didn't stage can be unstaged one by one (git restore --staged -- <file>); "
            f"then delete {path} by hand."
        )
    path.unlink(missing_ok=True)


# --- the backup ---------------------------------------------------------------------------


def back_up() -> dict:
    """Commit the library's changes and push. Returns {"ok": bool, "message": str} (and
    "deferred": True while DEFERRED: then nothing in git is changed, only looked at)."""
    if DEFERRED:
        return {"ok": False, "deferred": True, "message": DEFERRED_MESSAGE + _pending_note()}
    try:
        # An earlier backup cut off before git's staging area was updated comes first, even
        # on a branch with no upstream (where the rest would be refused anyway)
        in_git = _git("rev-parse", "--git-dir").returncode == 0
        if in_git and not libraries.is_test_library(LIBRARY):
            _finish_pending()
        if not available():
            return {"ok": False, "message": "Back up needs the library in a git repository "
                    "with a remote (e.g. GitHub)"}  # fmt: skip
        return _back_up()
    except Refused as e:
        return {"ok": False, "message": f"Not backed up: {e}"}


def _back_up() -> dict:
    root = Path(git("rev-parse", "--show-toplevel"))
    prefix = LIBRARY.resolve().relative_to(root.resolve()).as_posix()
    prefix = "" if prefix == "." else prefix + "/"

    def library_asset(name: str) -> bool:  # (`name` relative to the repository)
        return name.startswith(prefix) and note_asset(name[len(prefix) :])

    where = _destination()
    if busy := _in_progress():
        raise Refused(busy)
    head, base = where["head"], where["base"]
    if git("rev-parse", "--verify", "HEAD") != head:
        raise Refused("the checked-out branch changed while backing up; try again")
    if _git("merge-base", "--is-ancestor", base, head).returncode:
        raise Refused("the branch and its upstream have diverged (or the branch is behind); "
                      "pull first")  # fmt: skip
    _audit(git("rev-list", f"{base}..{head}").split(), prefix)
    staged = names("diff", "--cached", "--name-only", "--no-renames", head)
    if images := [f for f in staged if library_asset(f)]:
        raise Refused(f"personal note images are staged in git ({images[0]}); unstage them "
                      "(git restore --staged -- <file>): the folder backup keeps them")  # fmt: skip

    # The commit, in an index of its own: HEAD plus the library as it is, images left out
    index = _git_path(f"{TEMP_INDEX}{uuid.uuid4().hex[:12]}")
    own = {"GIT_INDEX_FILE": str(index)}
    committed, summary, tip, warning = [], "", head, ""
    try:
        git("read-tree", head, env=own)
        git("add", "-A", "--", ".", NO_ASSETS, env=own)
        committed = names("diff", "--cached", "--name-only", "--no-renames", head, env=own)
        if pdfs := [f for f in committed if f.lower().endswith(".pdf")]:
            raise Refused(f"a PDF was about to be included ({pdfs[0]})")
        if strays := [f for f in committed if library_asset(f) or not f.startswith(prefix)]:
            raise Refused(f"{strays[0]} was about to be included")  # (never expected)
        if committed:
            if hooks := _hooks():
                raise Refused(f"this repository has git commit hooks ({hooks}), which the "
                              "backup can't run and never bypasses: commit the library "
                              "yourself, or use the 💾 folder backup")  # fmt: skip
            sign = _signing()
            summary = _summary(committed, prefix)
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            message = f"Back up library {stamp} ({summary})"
            tree = git("write-tree", env=own)
            try:  # a failed signature makes no commit: never an unsigned one instead
                commit = git("commit-tree", tree, "-p", head, *sign, "-m", message)
            except RuntimeError as e:
                raise Refused(f"git couldn't make the commit ({e})") from None
            _audit([commit], prefix)
            _still(where, head)  # the same branch, still at the commit it was built on
            journal = {"branch": where["branch"], "old": head, "new": commit,
                       "paths": committed}  # fmt: skip
            safe_io.write_text(_journal_path(), json.dumps(journal))  # (whole or not at all)
            moved = _git("update-ref", "-m", message, where["branch"], commit, head)
            if moved.returncode:  # the branch isn't where it was: nothing changed
                _journal_path().unlink(missing_ok=True)
                raise Refused("the branch moved while backing up (a commit was made "
                              "meanwhile); try again")  # fmt: skip
            tip = commit
            if why := _bring_up_to_date(journal):
                warning = (f" Git's staging area wasn't brought up to date ({why}); the next "
                           "backup finishes it first.")  # fmt: skip
            else:
                _journal_path().unlink(missing_ok=True)
    finally:
        index.unlink(missing_ok=True)
        Path(f"{index}.lock").unlink(missing_ok=True)

    if tip == base:
        return {"ok": True, "message": "Already backed up: nothing changed since the last time"}
    _still(where, tip)  # nothing moved between the checks and the push
    pushed = _git("push", "--porcelain", "--no-follow-tags", "--recurse-submodules=no",
                  f"--force-with-lease={where['merge']}:{base}", where["remote"],
                  f"{tip}:{where['merge']}")  # fmt: skip
    if pushed.returncode:
        lines = (pushed.stderr or pushed.stdout).strip().splitlines()
        saved = f"Saved locally ({summary}) but" if summary else "Changes are saved locally but"
        why = lines[-1] if lines else "git push failed"
        return {"ok": False, "message": f"{saved} not pushed to GitHub: {why}{warning}"}
    done = f"Backed up to GitHub ({summary or 'earlier changes'}){warning}"
    return {"ok": not warning, "message": done}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    paths.add_argument(parser)
    parser.parse_args()
    paths.refuse_frozen()  # never the showcase library/ or test_library/ (paths.FROZEN)
    print(back_up()["message"])


if __name__ == "__main__":
    main()
