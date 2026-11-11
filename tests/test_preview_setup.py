"""M5a: the notes' preview library (markdown-it) is installed from its pinned npm package only
after its size and SHA-256 match; only the two named files are read from it (nothing else in
the package is ever written), and a bad download leaves the working copy as it was. It is
served from /vendor/markdown-it/ only, and the reader page loads it only when it is the
verified one. Temporary folders and an invented package; never the network."""

import hashlib
import io
import tarfile

import pytest
import reader

MINIFIED = b"(function(){globalThis.markdownit=function(){return {render:String}}})();\n"
LICENSE = b"Copyright (c) 2014 Vitaly Puzrin, Alex Kocharin.\n"


def package(extra: dict | None = None, leave_out: str = "", link: str = "") -> bytes:
    """An npm-style package (.tgz) with markdown-it's browser build and licence."""
    files = {
        "package/dist/browser/markdown-it.umd.min.js": MINIFIED,
        "package/LICENSE": LICENSE,
        "package/package.json": b'{"name": "markdown-it"}',
        **(extra or {}),
    }
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as tar:
        for name, data in files.items():
            if name == leave_out:
                continue
            info = tarfile.TarInfo(name)
            if name == link:
                info.type, info.linkname = tarfile.SYMTYPE, "../../outside.js"
                tar.addfile(info)
                continue
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return out.getvalue()


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """The reader's cache in a temporary folder, with a working (older) preview installed."""
    folder = tmp_path / "reader"
    monkeypatch.setattr(reader, "CACHE", folder)
    monkeypatch.setattr(reader, "MARKDOWN_IT", folder / "markdown-it")
    reader.MARKDOWN_IT.mkdir(parents=True)
    (reader.MARKDOWN_IT / "markdown-it.min.js").write_bytes(b"// the working copy\n")
    return folder


def pinned(monkeypatch, data: bytes, path) -> None:
    monkeypatch.setattr(reader, "MARKDOWN_IT_SHA256", hashlib.sha256(data).hexdigest())
    monkeypatch.setattr(reader, "MARKDOWN_IT_SIZE", len(data))
    path.write_bytes(data)


def test_the_pinned_package_is_installed(cache, monkeypatch, tmp_path):
    data = package()
    pinned(monkeypatch, data, tmp_path / "markdown-it.tgz")
    reader.install_markdown_it(tmp_path / "markdown-it.tgz")
    assert (reader.MARKDOWN_IT / "markdown-it.min.js").read_bytes() == MINIFIED
    assert (reader.MARKDOWN_IT / "LICENSE").read_bytes() == LICENSE
    assert sorted(p.name for p in reader.MARKDOWN_IT.iterdir()) == [
        ".myLibrary-markdown-it.txt", "LICENSE", "markdown-it.min.js"]  # fmt: skip
    assert reader.markdown_it_installed() == f"verified {reader.MARKDOWN_IT_VERSION}"
    assert sorted(p.name for p in cache.iterdir()) == ["markdown-it"]  # nothing left beside


def test_the_real_pin_is_exact():
    assert reader.MARKDOWN_IT_VERSION == "15.0.3"
    assert reader.MARKDOWN_IT_URL.endswith("/markdown-it/-/markdown-it-15.0.3.tgz")
    assert reader.MARKDOWN_IT_URL.startswith("https://registry.npmjs.org/")
    assert len(reader.MARKDOWN_IT_SHA256) == 64 and reader.MARKDOWN_IT_SIZE == 587_613


@pytest.mark.parametrize(
    "bad",
    ["another file", "a missing build", "the build as a link", "a link in the package"],
)
def test_a_wrong_package_leaves_the_working_copy(cache, monkeypatch, tmp_path, bad):
    path = tmp_path / "markdown-it.tgz"
    build = "package/dist/browser/markdown-it.umd.min.js"
    if bad == "another file":
        pinned(monkeypatch, package(), path)
        path.write_bytes(package(extra={"package/README.md": b"changed"}))  # checksum differs
    elif bad == "a missing build":
        pinned(monkeypatch, package(leave_out=build), path)
    elif bad == "the build as a link":
        pinned(monkeypatch, package(link=build), path)
    else:  # names that would escape the folder, if the package were extracted as a whole
        pinned(monkeypatch, package(extra={"../../evil.js": b"evil", "/abs.js": b"evil"}), path)
    if bad == "a link in the package":
        reader.install_markdown_it(path)  # only the named files are read: nothing else lands
        assert not (tmp_path / "evil.js").exists() and not (cache.parent / "evil.js").exists()
        return
    with pytest.raises((ValueError, KeyError)):
        reader.install_markdown_it(path)
    assert (reader.MARKDOWN_IT / "markdown-it.min.js").read_bytes() == b"// the working copy\n"
    assert sorted(p.name for p in cache.iterdir()) == ["markdown-it"]  # no half-made copy
    assert reader.markdown_it_installed() == ""  # (the working copy isn't the verified one)


def test_setup_downloads_only_when_missing(cache, monkeypatch, tmp_path):
    data = package()
    pinned(monkeypatch, data, tmp_path / "unused.tgz")
    fetched = []

    def download(url, dest):
        fetched.append(url)
        dest.write_bytes(data)

    monkeypatch.setattr(reader, "_download", download)
    reader.setup_preview()
    assert fetched == [reader.MARKDOWN_IT_URL] and reader.markdown_it_installed()
    reader.setup_preview()  # already there: nothing fetched
    assert len(fetched) == 1
    assert not list(cache.glob("*.tgz"))  # the download isn't kept


def test_missing_lists_the_preview(cache, monkeypatch):
    assert "notes preview" in reader.missing()


def test_it_is_served_from_its_own_folder_only(cache, monkeypatch, tmp_path):
    pinned(monkeypatch, package(), tmp_path / "markdown-it.tgz")
    reader.install_markdown_it(tmp_path / "markdown-it.tgz")
    (cache / "secret.txt").write_text("not served")
    body, kind = reader.static_file("/vendor/markdown-it/markdown-it.min.js")
    assert body == MINIFIED and kind.startswith("text/javascript")
    for path in ("/vendor/markdown-it/../secret.txt", "/vendor/markdown-it/..\\secret.txt",
                 "/vendor/markdown-it/", "/vendor/secret.txt"):  # fmt: skip
        assert reader.static_file(path) is None, path


def test_the_reader_page_loads_it_only_when_verified(cache, monkeypatch, tmp_path):
    viewer = tmp_path / "pdfjs" / "web"
    viewer.mkdir(parents=True)
    (viewer / "viewer.html").write_text("<html><head></head><body></body></html>")
    monkeypatch.setattr(reader, "PDFJS", tmp_path / "pdfjs")
    page = reader.viewer_html("token").decode()
    assert "/vendor/markdown-it/" not in page  # the working copy here isn't the verified one
    assert page.index("/reader/preview.js") < page.index("/reader/notes.js")
    pinned(monkeypatch, package(), tmp_path / "markdown-it.tgz")
    reader.install_markdown_it(tmp_path / "markdown-it.tgz")
    page = reader.viewer_html("token").decode()
    order = [page.index(s) for s in ("/reader/note_session.js", "/vendor/markdown-it/",
                                     "/reader/preview.js", "/reader/format.js",
                                     "/reader/notes.js")]  # fmt: skip
    assert order == sorted(order)  # (format.js, M5c: notes.js uses it)
    body, kind = reader.static_file("/reader/format.js")
    assert b"myLibraryFormat" in body and kind.startswith("text/javascript")
