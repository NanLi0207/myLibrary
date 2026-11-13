"""☁ Git backup while it is deferred (owner decision, 2026-11-12): nothing in git is changed,
nothing is published, a leftover recovery record is left alone, the page says so, and the 💾
folder backup keeps working with notes and images. Temporary repositories and invented data
only."""

import hashlib
import json
import subprocess
import threading
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer

import backup
import folder_backup
import library_server
import pytest


def run(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout  # fmt: skip


@pytest.fixture
def library_repo(tmp_path, monkeypatch):
    """An external library in a repository of its own, with a remote, mid-work: changed notes,
    a pasted image, a file the user staged, an unpushed commit of theirs."""
    remote = tmp_path / "remote.git"
    run(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    work = tmp_path / "My Library 书库"
    run(tmp_path, "clone", "-q", str(remote), str(work))
    for key, value in (("user.name", "Test"), ("user.email", "test@example.com")):
        run(work, "config", key, value)
    notes = work / "notes" / "doe-2015-optics"
    notes.mkdir(parents=True)
    (notes / "README.md").write_text("Last read: page 3\n", encoding="utf-8")
    run(work, "add", "-A")
    run(work, "commit", "-q", "-m", "start")
    run(work, "push", "-q", "-u", "origin", "main")
    (notes / "topic.md").write_text("mine, committed but not pushed\n", encoding="utf-8")
    run(work, "add", "notes/doe-2015-optics/topic.md")
    run(work, "commit", "-q", "-m", "my own commit")
    (notes / "README.md").write_text("Last read: page 9\n", encoding="utf-8")
    (notes / "assets").mkdir()
    (notes / "assets" / "img-1.png").write_bytes(b"\x89PNG personal screenshot")
    (notes / "ch01-basics.md").write_text("![image](assets/img-1.png)\n", encoding="utf-8")
    run(work, "add", "notes/doe-2015-optics/ch01-basics.md")  # staged by the user
    (notes / "ch01-basics.md").write_text("![image](assets/img-1.png)\nmore\n", encoding="utf-8")
    monkeypatch.setattr(backup, "LIBRARY", work)
    return work, remote, notes


def git_state(work, remote):
    """Everything a backup could change in git: refs (local and remote), HEAD, the index
    file's exact bytes, what is staged, the status, the remote's refs."""
    git_dir = work / ".git"
    return {
        "refs": run(work, "for-each-ref", "--format=%(refname) %(objectname)"),
        "head": run(work, "symbolic-ref", "HEAD") + run(work, "rev-parse", "HEAD"),
        "index": hashlib.sha256((git_dir / "index").read_bytes()).hexdigest(),
        "staged": run(work, "diff", "--cached", "--name-only"),
        "status": run(work, "status", "--porcelain=v1", "--untracked-files=all"),
        "remote": run(remote, "for-each-ref", "--format=%(refname) %(objectname)"),
        "git files": sorted(p.name for p in git_dir.iterdir()),
    }


def test_deferred_backup_changes_nothing_in_git(library_repo):
    work, remote, notes = library_repo
    assert backup.DEFERRED  # the app's setting for this release
    assert backup.available()  # (a library a backup would otherwise go ahead in)
    before = git_state(work, remote)
    result = backup.back_up()
    assert result == {"ok": False, "deferred": True, "message": backup.DEFERRED_MESSAGE}
    assert "temporarily unavailable" in result["message"]
    assert git_state(work, remote) == before  # no commit, no push, index byte-identical
    assert (notes / "assets" / "img-1.png").read_bytes() == b"\x89PNG personal screenshot"


def test_a_leftover_recovery_record_is_reported_never_replayed_or_deleted(library_repo):
    work, remote, notes = library_repo
    record = work / ".git" / backup.JOURNAL
    journal = {"branch": "refs/heads/main", "old": run(work, "rev-parse", "HEAD~1").strip(),
               "new": run(work, "rev-parse", "HEAD").strip(),
               "paths": ["notes/doe-2015-optics/topic.md"]}  # fmt: skip
    record.write_text(json.dumps(journal), encoding="utf-8")
    contents = record.read_bytes()
    before = git_state(work, remote)
    result = backup.back_up()
    assert not result["ok"] and result["deferred"]
    assert "recovery record" in result["message"] and str(record) in result["message"]
    assert record.read_bytes() == contents  # kept exactly
    assert git_state(work, remote) == before  # and nothing it names was applied


def test_manual_git_work_goes_on_as_usual(library_repo):
    work, remote, notes = library_repo
    backup.back_up()
    run(work, "add", "notes/doe-2015-optics/README.md")
    run(work, "commit", "-q", "-m", "by hand")
    run(work, "push", "-q")
    assert run(remote, "log", "-1", "--format=%s", "main").strip() == "by hand"


def test_the_folder_backup_still_holds_notes_and_images(library_repo, tmp_path):
    work, remote, notes = library_repo
    before = git_state(work, remote)
    dest = tmp_path / "zips"
    dest.mkdir()
    made = folder_backup.back_up(dest, pdfs=False, library=work)
    with zipfile.ZipFile(dest / made["file"]) as z:
        held = {n.replace("\\", "/"): z.read(n) for n in z.namelist()}
    image = next(d for n, d in held.items() if n.endswith("doe-2015-optics/assets/img-1.png"))
    note = next(d for n, d in held.items() if n.endswith("doe-2015-optics/ch01-basics.md"))
    assert image == b"\x89PNG personal screenshot"
    assert note.replace(b"\r\n", b"\n") == b"![image](assets/img-1.png)\nmore\n"
    assert git_state(work, remote) == before  # (and it left git alone too)


def test_the_page_says_the_git_backup_is_paused(library_repo, monkeypatch):
    work, remote, notes = library_repo
    for module in (library_server,):
        monkeypatch.setattr(module, "LIBRARY", work)
        monkeypatch.setattr(module, "CATALOG", work / "catalog.csv")
    (work / "catalog.csv").write_text("id,slug\n", encoding="utf-8")
    server = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        page = urllib.request.urlopen(base + "/", timeout=10).read().decode()
        assert '"backup": true' in page and '"backup_deferred": true' in page
        assert "☁ Back up (paused)" in page and "temporarily unavailable" in page
        # the local backup is offered meanwhile, even with no backup folder chosen yet
        assert "(!API.backup || API.backup_deferred || API.folder_backup)" in page
        before = git_state(work, remote)
        request = urllib.request.Request(base + "/api/backup", data=b"{}", method="POST",
                                         headers={"X-Library-Token": library_server.TOKEN,
                                                  "Content-Type": "application/json"})  # fmt: skip
        with urllib.request.urlopen(request, timeout=10) as answer:
            said = json.load(answer)
        assert said["ok"] is False and said["deferred"] is True
        assert "temporarily unavailable" in said["message"]
        assert git_state(work, remote) == before
    finally:
        server.shutdown()
        server.server_close()
