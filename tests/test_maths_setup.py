"""M5b: maths in the notes' preview. KaTeX is installed from its pinned npm package only after
the package's size and SHA-256 match and then each file taken from it matches its own SHA-256;
nothing else in the package is written, and a bad download leaves the installed copy as it was.
Every file is checked again whenever the reader page is made: a missing, changed or partial
copy is never loaded (the preview then shows formulas as written). Served from /vendor/katex/
only; copied into the package only when verified. Temporary folders and an invented package;
never the network."""

import hashlib
import io
import tarfile

import build_package
import pytest
import reader

FILES = {  # an invented KaTeX: installed name -> contents
    "katex.min.js": b"(function(){globalThis.katex={renderToString:String}})();\n",
    "katex.min.css": b".katex{font:normal 1.21em KaTeX_Main}\n",
    "LICENSE": b"The MIT License (MIT)\nCopyright (c) 2013-2020 Khan Academy\n",
    "fonts/KaTeX_Main-Regular.woff2": b"wOF2 main",
    "fonts/KaTeX_Math-Italic.woff2": b"wOF2 math",
}


def member(name: str) -> str:
    return f"package/{name}" if name == "LICENSE" else f"package/dist/{name}"


def package(files=None, extra=None, leave_out="", link="") -> bytes:
    """An npm-style package (.tgz) like KaTeX's."""
    entries = {member(n): d for n, d in (files or FILES).items()}
    entries["package/package.json"] = b'{"name": "katex"}'
    entries["package/dist/fonts/KaTeX_Main-Regular.ttf"] = b"not taken"
    entries.update(extra or {})
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as tar:
        for name, data in entries.items():
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
    """The reader's cache in a temporary folder, with an older KaTeX installed, and the invented
    files' checksums as the pinned ones."""
    folder = tmp_path / "reader"
    monkeypatch.setattr(reader, "CACHE", folder)
    monkeypatch.setattr(reader, "KATEX", folder / "katex")
    monkeypatch.setattr(
        reader, "KATEX_FILES", {n: hashlib.sha256(d).hexdigest() for n, d in FILES.items()}
    )
    reader.KATEX.mkdir(parents=True)
    (reader.KATEX / "katex.min.js").write_bytes(b"// the installed copy\n")
    return folder


def pinned(monkeypatch, data: bytes, path) -> None:
    monkeypatch.setattr(reader, "KATEX_SHA256", hashlib.sha256(data).hexdigest())
    monkeypatch.setattr(reader, "KATEX_SIZE", len(data))
    path.write_bytes(data)


def install(monkeypatch, tmp_path) -> None:
    pinned(monkeypatch, package(), tmp_path / "katex.tgz")
    reader.install_katex(tmp_path / "katex.tgz")


def installed_names() -> list[str]:
    return sorted(p.relative_to(reader.KATEX).as_posix() for p in reader.KATEX.rglob("*"))


def test_the_pinned_package_is_installed(cache, monkeypatch, tmp_path):
    install(monkeypatch, tmp_path)
    for name, data in FILES.items():
        assert (reader.KATEX / name).read_bytes() == data
    assert installed_names() == sorted([*FILES, "fonts", ".myLibrary-katex.txt"])  # nothing else
    assert reader.katex_installed() == f"verified {reader.KATEX_VERSION}"
    assert sorted(p.name for p in cache.iterdir()) == ["katex"]  # nothing left beside


def test_the_real_pin_is_exact():
    assert reader.KATEX_VERSION == "0.19.1"
    assert reader.KATEX_URL == "https://registry.npmjs.org/katex/-/katex-0.19.1.tgz"
    assert reader.KATEX_SHA256 == (
        "24da5a599eb2fcede2e270b99a6ff48bca816beecc95feeb84e8cccbd1bb34fd"
    )
    assert reader.KATEX_SIZE == 1_499_956
    names = set(reader.KATEX_FILES)
    assert {"katex.min.js", "katex.min.css", "LICENSE"} <= names
    fonts = names - {"katex.min.js", "katex.min.css", "LICENSE"}
    assert len(fonts) == 20 and all(
        n.startswith("fonts/KaTeX_") and n.endswith(".woff2") for n in fonts
    )
    for digest in reader.KATEX_FILES.values():
        assert len(digest) == 64 and int(digest, 16) >= 0


@pytest.mark.parametrize(
    "bad",
    ["another package", "a missing font", "a changed file", "a file as a link", "unsafe names"],
)
def test_a_wrong_package_leaves_the_installed_copy(cache, monkeypatch, tmp_path, bad):
    path = tmp_path / "katex.tgz"
    if bad == "another package":
        pinned(monkeypatch, package(), path)
        path.write_bytes(package(extra={"package/README.md": b"changed"}))  # checksum differs
    elif bad == "a missing font":
        pinned(monkeypatch, package(leave_out=member("fonts/KaTeX_Math-Italic.woff2")), path)
    elif bad == "a changed file":  # the package's own checksum pinned, but a file isn't KaTeX's
        pinned(monkeypatch, package(files={**FILES, "katex.min.js": b"alert(1)"}), path)
    elif bad == "a file as a link":
        pinned(monkeypatch, package(link=member("katex.min.css")), path)
    else:  # names that would escape the folder, if the package were extracted as a whole
        pinned(monkeypatch, package(extra={"../../evil.js": b"evil", "/abs.js": b"evil"}), path)
    if bad == "unsafe names":
        reader.install_katex(path)  # only the named files are read: nothing else lands
        assert not (tmp_path / "evil.js").exists() and not (cache.parent / "evil.js").exists()
        assert installed_names() == sorted([*FILES, "fonts", ".myLibrary-katex.txt"])
        return
    with pytest.raises((ValueError, KeyError)):
        reader.install_katex(path)
    assert (reader.KATEX / "katex.min.js").read_bytes() == b"// the installed copy\n"
    assert sorted(p.name for p in cache.iterdir()) == ["katex"]  # no half-made copy
    assert reader.katex_installed() == ""  # (the installed copy here isn't the verified one)


@pytest.mark.parametrize(
    "damage",
    ["a changed script", "a changed font", "a missing font", "a missing stylesheet",
     "no marker", "another version's marker", "an unreadable marker"],
)  # fmt: skip
def test_a_damaged_copy_is_never_loaded(cache, monkeypatch, tmp_path, damage):
    install(monkeypatch, tmp_path)
    assert reader.katex_installed()
    katex = reader.KATEX
    if damage == "a changed script":
        (katex / "katex.min.js").write_bytes(FILES["katex.min.js"] + b"\n")
    elif damage == "a changed font":
        (katex / "fonts/KaTeX_Math-Italic.woff2").write_bytes(b"wOF2 matH")
    elif damage == "a missing font":
        (katex / "fonts/KaTeX_Main-Regular.woff2").unlink()
    elif damage == "a missing stylesheet":
        (katex / "katex.min.css").unlink()
    elif damage == "no marker":
        (katex / reader.KATEX_MARKER).unlink()
    elif damage == "another version's marker":
        (katex / reader.KATEX_MARKER).write_text(f"0.16.0\n{reader.KATEX_SHA256}\n")
    else:
        (katex / reader.KATEX_MARKER).write_bytes(b"\xff\xfe\x00broken")
    assert reader.katex_installed() == ""
    assert "maths" in reader.missing()
    viewer = tmp_path / "pdfjs" / "web"
    viewer.mkdir(parents=True)
    (viewer / "viewer.html").write_text("<html><head></head><body></body></html>")
    monkeypatch.setattr(reader, "PDFJS", tmp_path / "pdfjs")
    page = reader.viewer_html("token").decode()
    assert "/vendor/katex/" not in page  # the preview shows the formulas as written
    assert "/reader/preview.js" in page and "/reader/notes.js" in page  # the notes as always


def test_setup_downloads_only_when_missing_or_damaged(cache, monkeypatch, tmp_path):
    data = package()
    pinned(monkeypatch, data, tmp_path / "unused.tgz")
    fetched = []

    def download(url, dest):
        fetched.append(url)
        dest.write_bytes(data)

    monkeypatch.setattr(reader, "_download", download)
    reader.setup_maths()
    assert fetched == [reader.KATEX_URL] and reader.katex_installed()
    reader.setup_maths()  # already there: nothing fetched
    assert len(fetched) == 1
    (reader.KATEX / "fonts/KaTeX_Main-Regular.woff2").write_bytes(b"damaged")
    reader.setup_maths()  # damaged: fetched again and replaced
    assert len(fetched) == 2 and reader.katex_installed()
    assert not list(cache.glob("*.tgz"))  # the download isn't kept
    assert sorted(p.name for p in cache.iterdir()) == ["katex"]


def test_a_failed_download_leaves_the_reader_working(cache, monkeypatch):
    def offline(url, dest):
        raise OSError("no network")

    monkeypatch.setattr(reader, "_download", offline)
    with pytest.raises(OSError):
        reader.setup_maths()
    assert reader.katex_installed() == "" and "maths" in reader.missing()
    assert (reader.KATEX / "katex.min.js").read_bytes() == b"// the installed copy\n"
    assert not list(cache.glob("*.tgz"))


def test_it_is_served_from_its_own_folder_only(cache, monkeypatch, tmp_path):
    install(monkeypatch, tmp_path)
    (cache / "secret.txt").write_text("not served")
    body, kind = reader.static_file("/vendor/katex/katex.min.js")
    assert body == FILES["katex.min.js"] and kind.startswith("text/javascript")
    body, kind = reader.static_file("/vendor/katex/katex.min.css")
    assert body == FILES["katex.min.css"] and kind.startswith("text/css")
    body, kind = reader.static_file("/vendor/katex/fonts/KaTeX_Main-Regular.woff2")
    assert body == FILES["fonts/KaTeX_Main-Regular.woff2"] and kind == "font/woff2"
    for path in ("/vendor/katex/../secret.txt", "/vendor/katex/..\\secret.txt",
                 "/vendor/katex/fonts/../../secret.txt", "/vendor/katex/",
                 "/vendor/katex/fonts/KaTeX_Main-Regular.ttf"):  # fmt: skip
        assert reader.static_file(path) is None, path


def test_the_reader_page_loads_it_only_when_verified(cache, monkeypatch, tmp_path):
    viewer = tmp_path / "pdfjs" / "web"
    viewer.mkdir(parents=True)
    (viewer / "viewer.html").write_text("<html><head></head><body></body></html>")
    monkeypatch.setattr(reader, "PDFJS", tmp_path / "pdfjs")
    page = reader.viewer_html("token").decode()
    assert "/vendor/katex/" not in page  # the installed copy here isn't the verified one
    install(monkeypatch, tmp_path)
    page = reader.viewer_html("token").decode()
    assert page.count("/vendor/katex/") == 2  # its stylesheet and script, nothing else
    assert '<link rel="stylesheet" href="/vendor/katex/katex.min.css">' in page
    assert page.index("/vendor/katex/katex.min.css") < page.index("/reader/notes.css")
    order = [page.index(s) for s in ("/reader/note_session.js", "/vendor/katex/katex.min.js",
                                     "/reader/preview.js", "/reader/notes.js")]  # fmt: skip
    assert order == sorted(order)  # KaTeX is there before preview.js reads it


def test_the_package_gets_the_verified_copy_only(cache, monkeypatch, tmp_path):
    for name, folder in (("PDFJS", "pdfjs"), ("MARKDOWN_IT", "markdown-it")):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "x.js").write_text("x")
        monkeypatch.setattr(reader, name, tmp_path / folder)
    (tmp_path / "ecdict.db").write_bytes(b"db")
    monkeypatch.setattr(reader, "DICT_DB", tmp_path / "ecdict.db")
    with pytest.raises(SystemExit, match="--setup-maths"):  # not verified: no package
        build_package.copy_reading_view(tmp_path / "unverified")
    assert not (tmp_path / "unverified" / ".cache" / "reader" / "katex").exists()
    install(monkeypatch, tmp_path)
    root = tmp_path / "package"
    build_package.copy_reading_view(root)
    copied = root / ".cache" / "reader" / "katex"
    for name, data in FILES.items():
        assert (copied / name).read_bytes() == data
    monkeypatch.setattr(reader, "KATEX", copied)  # as the package's own reader sees it
    assert reader.katex_installed() == f"verified {reader.KATEX_VERSION}"
