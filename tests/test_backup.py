import subprocess

import backup
import pytest


def run(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
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
