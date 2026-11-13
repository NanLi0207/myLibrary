"""The automatic Git backup's implementation, kept for its security redesign. The app has it
switched off (backup.DEFERRED; see test_backup_deferred.py); these tests run the dormant code
with it on, in temporary repositories only, so its behaviour and the cases found unsafe stay
documented. Passing here does not make it safe to switch back on: the third independent review
(2026-11-12) left High findings open (ROADMAP L29)."""

import subprocess
import zipfile

import backup
import pytest


@pytest.fixture(autouse=True)
def dormant_implementation(monkeypatch):
    monkeypatch.setattr(backup, "DEFERRED", False)


def run(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A repository with a library/ folder, cloned from a local "GitHub" (a bare repository)."""
    remote = tmp_path / "remote.git"
    run(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    work = tmp_path / "work"
    run(tmp_path, "clone", "-q", str(remote), str(work))
    for key, value in (("user.name", "Test"), ("user.email", "test@example.com")):
        run(work, "config", key, value)
    (work / ".gitignore").write_text("*.pdf\n", encoding="utf-8")
    (work / "scripts").mkdir()
    (work / "scripts" / "tool.py").write_text("print('tool')\n", encoding="utf-8")
    notes = work / "library" / "notes" / "doe-2015-optics"
    notes.mkdir(parents=True)
    (notes / "README.md").write_text("Last read: page 3\n", encoding="utf-8")
    run(work, "add", "-A")
    run(work, "commit", "-q", "-m", "start")
    run(work, "push", "-q", "-u", "origin", "main")
    monkeypatch.setattr(backup, "LIBRARY", work / "library")
    return work, remote


def remote_files(remote):
    return run(remote, "ls-tree", "-r", "--name-only", "main").split()


def test_backs_up_only_the_library(repo):
    work, remote = repo
    assert backup.available()
    assert backup.back_up()["message"].startswith("Already backed up")

    # Reading progress, a new vocabulary list, a book PDF, and unrelated code changes
    notes = work / "library" / "notes" / "doe-2015-optics"
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    (notes / "vocabulary.md").write_text("| pupil |\n", encoding="utf-8")
    (work / "library" / "books").mkdir()
    (work / "library" / "books" / "doe-2015-optics.pdf").write_bytes(b"%PDF-1.4")
    (work / "scripts" / "tool.py").write_text("print('changed')\n", encoding="utf-8")
    (work / "scripts" / "staged.py").write_text("x = 1\n", encoding="utf-8")
    run(work, "add", "scripts/staged.py")  # something staged by hand: must stay out

    result = backup.back_up()
    assert result["ok"] and result["message"].startswith("Backed up to GitHub (2 files")
    on_github = remote_files(remote)
    assert "library/notes/doe-2015-optics/vocabulary.md" in on_github
    assert not any(f.endswith(".pdf") for f in on_github)  # never a book
    assert "scripts/staged.py" not in on_github
    # the code changes are still there, untouched (one staged, one not)
    status = run(work, "status", "--short")
    assert "A  scripts/staged.py" in status and " M scripts/tool.py" in status


def test_unpushed_committed_images_are_not_pushed_by_backup(repo):
    work, remote = repo
    assets = work / "library/notes/doe-2015-optics/assets"
    assets.mkdir()
    (assets / "private.png").write_bytes(b"personal screenshot")
    run(work, "add", "library/notes")
    run(work, "commit", "-qm", "private images, not for publication")
    result = backup.back_up()
    assert not result["ok"] and "personal note image is tracked" in result["message"]
    assert "library/notes/doe-2015-optics/assets/private.png" not in result["message"]
    assert "notes/doe-2015-optics/assets/private.png" in result["message"]
    assert not any("assets/" in f for f in remote_files(remote))


# --- pasted note images (M5d): an external library that is a repository of its own -------------
# No .gitignore at all: the images must stay out by the backup's own rule, not by ignore files


@pytest.fixture
def library_repo(tmp_path, monkeypatch):
    remote = tmp_path / "remote.git"
    run(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    work = tmp_path / "My Library 书库"
    run(tmp_path, "clone", "-q", str(remote), str(work))
    for key, value in (("user.name", "Test"), ("user.email", "test@example.com")):
        run(work, "config", key, value)
    notes = work / "notes" / "doe-2015-optics"
    notes.mkdir(parents=True)
    (notes / "README.md").write_text("Last read: page 3\n", encoding="utf-8")
    (work / "catalog.csv").write_text("id,slug\n", encoding="utf-8")
    run(work, "add", "-A")
    run(work, "commit", "-q", "-m", "start")
    run(work, "push", "-q", "-u", "origin", "main")
    monkeypatch.setattr(backup, "LIBRARY", work)
    return work, remote, notes


def staging(work):
    """The index exactly: every entry's mode, blob and stage, and what differs from HEAD."""
    return run(work, "ls-files", "-s"), run(work, "diff", "--cached", "--name-only")


def test_notes_are_backed_up_and_their_images_never(library_repo, tmp_path):
    import folder_backup

    work, remote, notes = library_repo
    (notes / "assets").mkdir()
    (notes / "assets" / "img-1.png").write_bytes(b"personal screenshot")
    (notes / "assets" / "Fig 2 光.PNG").write_bytes(b"copyrighted page")
    (notes / "ch01-basics.md").write_text("![image](assets/img-1.png)\n", encoding="utf-8")
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")

    result = backup.back_up()
    assert result["ok"] and result["message"].startswith("Backed up to GitHub (2 files"), result
    on_github = remote_files(remote)
    assert "notes/doe-2015-optics/ch01-basics.md" in on_github
    assert not any("assets" in f for f in on_github)
    assert not any("assets" in f for f in run(work, "ls-files").split("\n"))
    # nothing left staged, the images still there and untracked, the notes clean
    assert staging(work)[1] == ""
    status = run(work, "status", "--short", "--untracked-files=all")
    assert "README.md" not in status and "ch01-basics.md" not in status
    assert status.count("assets/") == 2 and status.startswith("??")
    assert (notes / "assets" / "img-1.png").read_bytes() == b"personal screenshot"
    # the next backup has nothing to do (the images are no change to it)
    assert backup.back_up()["message"].startswith("Already backed up")
    # the folder backup still holds the images
    dest = tmp_path / "zips"
    dest.mkdir()
    made = folder_backup.back_up(dest, pdfs=False, library=work)
    with zipfile.ZipFile(dest / made["file"]) as z:
        assert any(n.endswith("assets/img-1.png") for n in z.namelist())


def test_staged_images_are_refused_and_the_staging_area_kept(library_repo):
    work, remote, notes = library_repo
    (notes / "assets").mkdir()
    (notes / "assets" / "img-1.png").write_bytes(b"personal screenshot")
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    run(work, "add", "notes/doe-2015-optics/assets/img-1.png")  # staged by hand
    before = staging(work)
    result = backup.back_up()
    assert not result["ok"] and "staged" in result["message"]
    assert staging(work) == before  # not a thing unstaged, reset or added
    assert not any("assets" in f for f in remote_files(remote))
    assert run(work, "log", "-1", "--format=%s").strip() == "start"


def test_what_the_user_staged_stays_staged_exactly(library_repo):
    work, remote, notes = library_repo
    readme = notes / "README.md"
    readme.write_text("Last read: page 5\n", encoding="utf-8")
    run(work, "add", "notes/doe-2015-optics/README.md")  # a version staged by hand...
    staged_blob = run(work, "ls-files", "-s", "notes/doe-2015-optics/README.md").split()[1]
    readme.write_text("Last read: page 7\n", encoding="utf-8")  # ...then edited again
    (work / "draft.md").write_text("mine\n", encoding="utf-8")
    run(work, "add", "draft.md")
    (notes / "vocabulary.md").write_text("| pupil |\n", encoding="utf-8")

    result = backup.back_up()
    assert result["ok"], result
    # the backup holds the files as they are on disk
    assert run(remote, "show", "main:notes/doe-2015-optics/README.md") == "Last read: page 7\n"
    # the user's staged entries are exactly as they were; the file they never staged is clean
    assert run(work, "ls-files", "-s", "notes/doe-2015-optics/README.md").split()[1] == staged_blob
    assert run(work, "ls-files", "-s", "draft.md")
    status = run(work, "status", "--short")
    assert "vocabulary.md" not in status


def test_a_refused_backup_leaves_nothing_newly_staged(library_repo):
    work, remote, notes = library_repo
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    books = work / "books"
    books.mkdir()
    (books / "李-2020-光学.pdf").write_bytes(b"%PDF-1.4")  # no ignore rule; a quoted name in git
    run(work, "add", "catalog.csv")  # (nothing to stage: the index as the user left it)
    before = staging(work)
    result = backup.back_up()
    assert not result["ok"] and "PDF" in result["message"], result
    assert staging(work) == before
    assert remote_files(remote) == ["catalog.csv", "notes/doe-2015-optics/README.md"]
    assert (work / ".git").is_dir() and not list((work / ".git").glob("index.my*"))


def before_git(monkeypatch, command: str, action, times: int = 1):
    """Run `action` just before the backup's next `times` git `command`s (a deterministic
    point in its sequence: no sleeps)."""
    real, left = backup._git, [times]

    def wrapped(*args, **kw):
        if args and args[0] == command and left[0]:
            left[0] -= 1
            action()
        return real(*args, **kw)

    monkeypatch.setattr(backup, "_git", wrapped)


def head(work, ref="HEAD"):
    return run(work, "rev-parse", ref).strip()


def test_a_failure_while_committing_leaves_the_staging_area_as_it_was(library_repo, monkeypatch):
    work, remote, notes = library_repo
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    before = staging(work)
    real = backup._git

    def failing(*args, **kw):
        if args[0] == "commit-tree":
            raise RuntimeError("disk full")
        return real(*args, **kw)

    monkeypatch.setattr(backup, "_git", failing)
    result = backup.back_up()
    assert not result["ok"] and "disk full" in result["message"]
    assert staging(work) == before
    assert run(work, "log", "-1", "--format=%s").strip() == "start"
    assert (work / ".git").is_dir() and not list((work / ".git").glob("index.my*"))
    assert not (work / ".git" / backup.JOURNAL).exists()


def test_a_commit_made_meanwhile_is_never_undone(library_repo, monkeypatch):
    work, remote, notes = library_repo
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")

    def commit_theirs():  # the user commits just before the backup puts its commit in place
        (work / "other.txt").write_text("theirs\n", encoding="utf-8")
        run(work, "add", "other.txt")
        run(work, "commit", "-q", "-m", "theirs")

    before_git(monkeypatch, "update-ref", commit_theirs)
    result = backup.back_up()
    assert not result["ok"] and "try again" in result["message"]
    assert run(work, "log", "-1", "--format=%s").strip() == "theirs"
    assert (work / "other.txt").exists() and "other.txt" in run(work, "ls-files")
    assert not (work / ".git" / backup.JOURNAL).exists()
    assert remote_files(remote) == ["catalog.csv", "notes/doe-2015-optics/README.md"]


def test_a_merge_in_progress_is_left_alone(library_repo):
    work, remote, notes = library_repo
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    git_dir = work / ".git"
    (git_dir / "MERGE_HEAD").write_text(run(work, "rev-parse", "HEAD"), encoding="utf-8")
    result = backup.back_up()
    assert not result["ok"] and "in progress" in result["message"]
    assert run(work, "log", "-1", "--format=%s").strip() == "start"


def test_note_asset_paths():
    assert backup.note_asset("notes/doe/assets/img-1.png")
    assert backup.note_asset("NOTES/doe/Assets/x.PNG")
    assert backup.note_asset("notes/doe/assets/sub/x.png")
    assert not backup.note_asset("notes/doe/assets.md")
    assert not backup.note_asset("code/assets/x.png")
    assert not backup.note_asset("notes/doe/ch01-basics.md")


# --- what would be published: every outgoing commit, whole -----------------------------------


def commit_files(work, message, **files):
    """Commit files (relative path -> bytes, or None to delete) by hand, as a user would."""
    for name, data in files.items():
        path = work / name
        if data is None:
            run(work, "rm", "-q", "--", name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            run(work, "add", "--", name)
    run(work, "commit", "-q", "-m", message)
    return head(work)


@pytest.mark.parametrize(
    "unsafe",
    [
        "notes/doe-2015-optics/assets/private.png",  # an image added, then deleted
        "books/doe-2015-optics.pdf",  # a book added, then deleted
        "notes/doe-2015-optics/assets/图 1 'q' #% ü.PNG",  # unusual and Unicode names
        "books/李 2020 光学 (2nd).PDF",
    ],
)
def test_unsafe_files_in_outgoing_history_block_the_push(library_repo, unsafe):
    work, remote, notes = library_repo
    published, remote_head = remote_files(remote), head(remote, "main")
    added = commit_files(work, "add it", **{unsafe: b"private"})
    commit_files(work, "and delete it again", **{unsafe: None})
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    local = head(work)
    result = backup.back_up()
    assert not result["ok"]
    assert unsafe in result["message"] and added[:10] in result["message"]  # path and commit
    assert remote_files(remote) == published and head(remote, "main") == remote_head
    assert head(work) == local  # no commit made, none removed
    assert run(work, "log", "--format=%s").split("\n")[:2] == ["and delete it again", "add it"]
    assert (notes / "README.md").read_text(encoding="utf-8") == "Last read: page 9\n"


def test_an_image_already_published_is_never_carried_into_a_backup(library_repo):
    work, remote, notes = library_repo
    commit_files(work, "an image, published by hand",
                 **{"notes/doe-2015-optics/assets/old.png": b"private"})  # fmt: skip
    run(work, "push", "-q")
    published, local = remote_files(remote), head(work)
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    result = backup.back_up()
    assert not result["ok"] and "notes/doe-2015-optics/assets/old.png" in result["message"]
    assert "git rm --cached" in result["message"]  # what to do about it, by hand
    assert remote_files(remote) == published and head(work) == local
    assert (work / "notes/doe-2015-optics/assets/old.png").read_bytes() == b"private"


def test_an_image_inherited_from_an_unpushed_commit_blocks_the_backup(library_repo):
    work, remote, notes = library_repo
    published = remote_files(remote)
    commit_files(work, "an image", **{"notes/doe-2015-optics/assets/x.png": b"private"})
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    result = backup.back_up()
    assert not result["ok"] and "assets/x.png" in result["message"]
    assert remote_files(remote) == published


def test_clean_history_with_unusual_note_names_is_published(library_repo):
    work, remote, notes = library_repo
    commit_files(work, "notes by hand", **{"notes/doe-2015-optics/ch 01 — 光 'x'.md": b"mine\n"})
    (notes / "ch02 'two' #% ü.md").write_text("more\n", encoding="utf-8")
    result = backup.back_up()
    assert result["ok"], result
    published = run(remote, "ls-tree", "-r", "--name-only", "-z", "main").split("\0")
    assert "notes/doe-2015-optics/ch 01 — 光 'x'.md" in published
    assert "notes/doe-2015-optics/ch02 'two' #% ü.md" in published
    assert head(remote, "main") == head(work)


# --- where it goes: the branch, the commit and the remote branch, exactly ----------------------


def test_switching_branch_at_the_same_commit_stops_the_backup(library_repo, monkeypatch):
    work, remote, notes = library_repo
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    start = head(work)

    def switch():  # another branch at the very same commit (git switch, without the files)
        run(work, "branch", "other")
        run(work, "symbolic-ref", "HEAD", "refs/heads/other")

    before_git(monkeypatch, "write-tree", switch)
    result = backup.back_up()
    assert not result["ok"] and "branch changed" in result["message"]
    assert head(work, "main") == start and head(work, "other") == start
    assert head(remote, "main") == start
    assert not (work / ".git" / backup.JOURNAL).exists()


def test_a_remote_commit_meanwhile_is_never_overwritten(library_repo, tmp_path):
    work, remote, notes = library_repo
    other = tmp_path / "elsewhere"
    run(tmp_path, "clone", "-q", str(remote), str(other))
    for key, value in (("user.name", "Other"), ("user.email", "o@example.com")):
        run(other, "config", key, value)
    theirs = commit_files(other, "from another computer", **{"topics.md": b"theirs\n"})
    run(other, "push", "-q")  # this computer hasn't fetched it
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    result = backup.back_up()
    assert not result["ok"] and result["message"].startswith("Saved locally")
    assert head(remote, "main") == theirs  # theirs is still there, not replaced
    assert "Back up library" in run(work, "log", "-1", "--format=%s")  # ours kept locally


def test_the_branch_moving_before_the_push_stops_it(library_repo, monkeypatch):
    work, remote, notes = library_repo
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    start = head(remote, "main")
    moved = []

    def move_branch():  # e.g. a commit made by another program (no index needed for it)
        tree = run(work, "rev-parse", "main^{tree}").strip()
        commit = run(work, "commit-tree", tree, "-p", "main", "-m", "meanwhile").strip()
        run(work, "update-ref", "refs/heads/main", commit)
        moved.append(commit)

    real = backup._bring_up_to_date

    def then_move(journal):
        done = real(journal)
        move_branch()
        return done

    monkeypatch.setattr(backup, "_bring_up_to_date", then_move)
    result = backup.back_up()
    assert not result["ok"] and "moved" in result["message"]
    assert head(remote, "main") == start  # nothing pushed
    assert head(work, "main") == moved[0]  # and nothing local undone


def test_push_settings_never_widen_what_is_published(library_repo):
    work, remote, notes = library_repo
    run(work, "config", "push.default", "matching")
    run(work, "config", "push.followTags", "true")
    run(work, "config", "--add", "remote.origin.push", "refs/heads/*:refs/heads/*")
    run(work, "config", "--add", "remote.origin.push", "+refs/tags/*:refs/tags/*")
    run(work, "branch", "extra")
    run(work, "checkout", "-q", "extra")
    commit_files(work, "private branch", **{"diary.md": b"not for github\n"})
    run(work, "checkout", "-q", "main")
    run(work, "tag", "-a", "-m", "a tag", "v1")
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    result = backup.back_up()
    assert result["ok"], result
    assert run(remote, "branch", "--format=%(refname)").split() == ["refs/heads/main"]
    assert run(remote, "tag") == ""
    assert head(remote, "main") == head(work, "main")


@pytest.mark.parametrize(
    "setting, value, why",
    [
        ("branch.main.pushRemote", "backup", "unclear where"),
        ("remote.pushDefault", "backup", "unclear where"),
        ("remote.origin.mirror", "true", "mirror"),
    ],
)
def test_unclear_destinations_are_refused(library_repo, setting, value, why):
    work, remote, notes = library_repo
    run(work, "remote", "add", "backup", str(remote))
    run(work, "config", setting, value)
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    start = head(work)
    result = backup.back_up()
    assert not result["ok"] and why in result["message"]
    assert head(work) == start and head(remote, "main") == start


def test_a_detached_head_is_refused(library_repo):
    work, remote, notes = library_repo
    run(work, "checkout", "-q", "--detach")
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    start = head(work)
    result = backup.back_up()  # (a detached HEAD has no upstream: not even offered)
    assert not result["ok"]
    assert head(work) == start and head(remote, "main") == start
    assert run(work, "rev-parse", "--abbrev-ref", "HEAD").strip() == "HEAD"  # still detached
    # and if git did name an upstream, the destination check itself refuses it
    run(work, "config", "branch.HEAD.remote", "origin")
    with pytest.raises(backup.Refused, match="detached"):
        backup._destination()


# --- the user's staging area: only the backed-up files that still have the old version ------


def entries(work, *paths):
    """The index entries exactly: tag (special states), mode, blob, stage, path."""
    return run(work, "ls-files", "-s", "-v", "--", *paths)


def test_staging_done_just_before_is_kept_and_the_rest_brought_up_to_date(
    library_repo, monkeypatch
):
    work, remote, notes = library_repo
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    (notes / "vocabulary.md").write_text("| pupil |\n", encoding="utf-8")
    real = backup._bring_up_to_date

    def stage_then_update(journal):  # another program stages a version of README meanwhile
        made = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=work,
                              input=b"page 5\n", capture_output=True, check=True)  # fmt: skip
        blob = made.stdout.decode().strip()
        run(work, "update-index", "--cacheinfo", f"100644,{blob},notes/doe-2015-optics/README.md")
        return real(journal)

    monkeypatch.setattr(backup, "_bring_up_to_date", stage_then_update)
    assert backup.back_up()["ok"]
    readme = entries(work, "notes/doe-2015-optics/README.md").split()
    assert run(work, "cat-file", "-p", readme[2]) == "page 5\n"  # theirs, untouched
    status = run(work, "status", "--short")
    assert "vocabulary.md" not in status  # brought up to date (it was never staged)


def test_nobody_can_stage_while_the_index_is_being_updated(library_repo, monkeypatch):
    work, remote, notes = library_repo
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    (work / "draft.md").write_text("mine\n", encoding="utf-8")
    tried = []

    def try_to_stage():  # inside the update: git's index.lock is held
        done = subprocess.run(["git", "add", "draft.md"], cwd=work, capture_output=True,
                              text=True, encoding="utf-8")  # fmt: skip
        tried.append(done)

    before_git(monkeypatch, "update-index", try_to_stage)
    assert backup.back_up()["ok"]
    # the other program was kept out (it says so and can try again), not overwritten later
    assert tried and tried[0].returncode != 0 and "index.lock" in tried[0].stderr
    assert (work / "draft.md").read_text(encoding="utf-8") == "mine\n"
    assert run(work, "status", "--short") == ""  # (draft.md is in the library: backed up)


def test_unrelated_entries_and_their_special_states_are_kept_exactly(repo):
    work, remote = repo
    run(work, "update-index", "--assume-unchanged", "scripts/tool.py")  # outside the library
    (work / "scripts" / "staged.py").write_text("x = 1\n", encoding="utf-8")
    run(work, "add", "scripts/staged.py")
    before = entries(work, "scripts")
    (work / "library/notes/doe-2015-optics/README.md").write_text("page 9\n", encoding="utf-8")
    assert backup.back_up()["ok"]
    assert entries(work, "scripts") == before
    assert entries(work, "scripts/tool.py").startswith("h ")  # assume-unchanged kept


def test_a_held_index_lock_leaves_the_index_alone_and_the_next_backup_finishes(
    library_repo, monkeypatch
):
    work, remote, notes = library_repo
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    old_index = entries(work)
    lock = work / ".git" / "index.lock"
    real = backup._bring_up_to_date

    def locked(journal):  # an editor's git view is busy with the index
        lock.write_bytes(b"")
        try:
            return real(journal)
        finally:
            assert lock.read_bytes() == b""  # theirs: never written or removed by the backup

    monkeypatch.setattr(backup, "_bring_up_to_date", locked)
    result = backup.back_up()
    assert not result["ok"] and "index.lock" in result["message"]
    assert entries(work) == old_index  # not touched
    assert head(remote, "main") == head(work)  # the commit itself is backed up
    assert (work / ".git" / backup.JOURNAL).exists()
    lock.unlink()
    monkeypatch.setattr(backup, "_bring_up_to_date", real)
    assert backup.back_up()["message"].startswith("Already backed up")
    assert not (work / ".git" / backup.JOURNAL).exists()
    assert "README.md" not in run(work, "status", "--short")


def test_an_interruption_after_the_commit_is_finished_by_the_next_backup(library_repo, monkeypatch):
    work, remote, notes = library_repo
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    start = head(remote, "main")

    def cut_off(journal):
        raise KeyboardInterrupt  # the program stops between the commit and the index

    monkeypatch.setattr(backup, "_bring_up_to_date", cut_off)
    with pytest.raises(KeyboardInterrupt):
        backup.back_up()
    assert (work / ".git" / backup.JOURNAL).exists()
    assert head(remote, "main") == start  # not pushed yet
    monkeypatch.undo()
    monkeypatch.setattr(backup, "LIBRARY", work)
    monkeypatch.setattr(backup, "DEFERRED", False)  # (undo() reset it too)
    result = backup.back_up()
    assert result["ok"] and head(remote, "main") == head(work), result
    assert not (work / ".git" / backup.JOURNAL).exists()
    assert "README.md" not in run(work, "status", "--short")


def test_a_branch_switch_before_the_index_update_is_refused_until_switched_back(
    library_repo, monkeypatch
):
    work, remote, notes = library_repo
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    run(work, "branch", "other")
    real = backup._bring_up_to_date

    def switch_first(journal):
        run(work, "symbolic-ref", "HEAD", "refs/heads/other")
        return real(journal)

    monkeypatch.setattr(backup, "_bring_up_to_date", switch_first)
    old_index = entries(work)
    result = backup.back_up()
    assert not result["ok"] and "branch changed" in result["message"]
    assert entries(work) == old_index  # the other branch's index: never touched
    monkeypatch.setattr(backup, "_bring_up_to_date", real)
    result = backup.back_up()  # still on the other branch: refused, saying what to do
    assert not result["ok"] and "Check out main" in result["message"]
    run(work, "symbolic-ref", "HEAD", "refs/heads/main")
    assert backup.back_up()["ok"]
    assert not (work / ".git" / backup.JOURNAL).exists()


# --- hooks and signing ------------------------------------------------------------------------


@pytest.mark.parametrize("where", ["hooks folder", "hooksPath", "config"])
def test_repositories_with_commit_hooks_are_refused(library_repo, tmp_path, where):
    work, remote, notes = library_repo
    if where == "hooks folder":
        hook = work / ".git" / "hooks" / "pre-commit"
    elif where == "hooksPath":
        hook = tmp_path / "team-hooks" / "commit-msg"
        run(work, "config", "core.hooksPath", str(tmp_path / "team-hooks"))
    else:
        hook = None
        run(work, "config", "hook.lint.command", "echo lint")
        run(work, "config", "hook.lint.event", "pre-commit")
    if hook:
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    start = head(work)
    result = backup.back_up()
    assert not result["ok"] and "commit hooks" in result["message"]
    assert "folder backup" in result["message"]
    assert head(work) == start and head(remote, "main") == start
    if hook:
        assert hook.read_text(encoding="utf-8") == "#!/bin/sh\nexit 0\n"  # never changed


def test_sample_hooks_are_not_active_hooks(library_repo):
    work, remote, notes = library_repo
    assert list((work / ".git" / "hooks").glob("*.sample"))  # (as git init leaves them)
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    assert backup.back_up()["ok"]


def test_unset_signing_makes_an_unsigned_commit(library_repo):
    work, remote, notes = library_repo
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    assert backup.back_up()["ok"]
    assert "gpgsig" not in run(work, "cat-file", "commit", "HEAD")


@pytest.mark.parametrize(
    "settings, why",
    [
        ({"commit.gpgsign": "maybe"}, "commit.gpgSign"),  # not a boolean
        ({"commit.gpgsign": "true", "gpg.program": "no-such-gpg-program"}, "couldn't make"),
    ],
)
def test_unclear_or_failing_signing_makes_no_commit(library_repo, settings, why):
    work, remote, notes = library_repo
    for key, value in settings.items():
        run(work, "config", key, value)
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    start = head(work)
    result = backup.back_up()
    assert not result["ok"] and why in result["message"], result
    assert head(work) == start and head(remote, "main") == start  # never an unsigned one


def test_signing_is_honoured(library_repo, tmp_path):
    import shutil

    work, remote, notes = library_repo
    keygen = shutil.which("ssh-keygen")
    if not keygen:
        pytest.skip("ssh-keygen isn't available to make a signing key")
    key = tmp_path / "signing-key"
    subprocess.run([keygen, "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    run(work, "config", "gpg.format", "ssh")
    run(work, "config", "user.signingkey", str(key))
    run(work, "config", "commit.gpgsign", "true")
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    result = backup.back_up()
    assert result["ok"], result
    assert "gpgsig" in run(work, "cat-file", "commit", "HEAD")


def test_refuses_to_push_unpushed_code(repo):
    work, remote = repo
    (work / "scripts" / "tool.py").write_text("print('new code')\n", encoding="utf-8")
    run(work, "commit", "-q", "-am", "code, not pushed yet")
    (work / "library" / "notes" / "doe-2015-optics" / "README.md").write_text("page 12\n")

    result = backup.back_up()
    assert not result["ok"] and "outside the library" in result["message"]
    assert "code, not pushed" not in run(remote, "log", "--oneline", "main")


def test_push_failure_keeps_the_commit(repo, tmp_path):
    work, remote = repo
    run(work, "remote", "set-url", "origin", str(tmp_path / "gone.git"))  # GitHub unreachable
    (work / "library" / "notes" / "doe-2015-optics" / "README.md").write_text("page 20\n")
    result = backup.back_up()
    assert not result["ok"] and result["message"].startswith("Saved locally (1 file")
    assert "Back up library" in run(work, "log", "-1", "--format=%s")


def test_not_available_outside_git(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "LIBRARY", tmp_path)
    assert not backup.available()
    assert not backup.back_up()["ok"]
