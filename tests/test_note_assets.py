"""Pasted images in notes (task 4 M5d), server side: an image is checked from its bytes, kept as
a new file in the document's notes folder's assets/ (never over anything, never outside the
folder), and shown only through a contained route. Saving it is separate from saving a note:
nothing here deletes an image. Synthetic images and temporary libraries only."""

import errno
import io
import os
import shutil
import struct
import sys
import threading
import urllib.error
import urllib.request
import zipfile
import zlib
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path

import add_book
import catalog
import folder_backup
import image_check
import library_page
import library_server
import notes_store
import pytest
import safe_io
from image_check import ImageError
from notes_store import NoteError
from PIL import Image
from test_notes_containment import link_or_skip
from testlib import put

NAME = "doe-2015-practical-lens-design"
OTHER = "roe-2019-optics-primer"
README = "# Practical Lens Design\n\n## Reading progress\n\n- [ ] [Ch 1: Basics](ch01-basics.md)\n"


def picture(kind: str = "PNG", size=(40, 20), color=(200, 30, 30), **options) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, kind, **options)
    return out.getvalue()


def png_claiming(width: int, height: int) -> bytes:
    """A real 1×1 PNG whose header says it is width × height (a decompression bomb's shape)."""
    data = bytearray(picture(size=(1, 1)))
    ihdr = struct.pack(">II", width, height) + bytes(data[24:29])
    data[16:29] = ihdr
    data[29:33] = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr) & 0xFFFFFFFF)
    return bytes(data)


def make_doc(root: Path, slug: str, title: str) -> dict:
    folder = root / "notes" / slug
    folder.mkdir(parents=True)
    (folder / "README.md").write_text(README, encoding="utf-8")
    (folder / "ch01-basics.md").write_text("# Basics\n", encoding="utf-8")
    doc = put(root / "catalog.csv", {"slug": slug, "title": title, "notes": f"notes/{slug}/"})
    return catalog.load(root / "catalog.csv")[doc]


@pytest.fixture
def lib(tmp_path):
    root = tmp_path / "lib"
    root.mkdir()
    return root, make_doc(root, NAME, "Practical Lens Design")


def assets_of(root: Path, row: dict) -> Path:
    return root / row["notes"] / "assets"


# --- checking an image -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind, expected, options",
    [("PNG", "png", {}), ("JPEG", "jpeg", {"quality": 90}), ("WEBP", "webp", {"quality": 80})],
)
def test_png_jpeg_and_webp_are_recognised_from_their_bytes(kind, expected, options):
    info = image_check.inspect(picture(kind, **options))
    assert (info.kind, info.width, info.height) == (expected, 40, 20)
    assert info.mime == f"image/{expected}"


@pytest.mark.parametrize(
    "data, why",
    [
        (b"", "no image"),
        (b"not an image at all", "only PNG, JPEG and WebP"),
        (b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', "only PNG"),
        (b"<!doctype html><script>alert(1)</script>", "only PNG"),
        (b"GIF89a" + b"\0" * 40, "only PNG"),
        (b"BM" + b"\0" * 60, "only PNG"),  # BMP
        (b"\x89PNG\r\n\x1a\n" + b"\0" * 40, "readable PNG"),  # a signature and nothing else
        (b"RIFF\0\0\0\0WEBPVP8 " + b"\0" * 20, "WEBP"),
    ],
)
def test_anything_else_is_refused(data, why):
    with pytest.raises(ImageError, match=why):
        image_check.inspect(data)


def test_a_truncated_image_is_refused():
    whole = picture(size=(300, 200), color=(10, 120, 240))
    with pytest.raises(ImageError, match="damaged or incomplete|readable"):
        image_check.inspect(whole[: len(whole) // 2])
    jpeg = picture("JPEG", size=(300, 200))
    with pytest.raises(ImageError):
        image_check.inspect(jpeg[: len(jpeg) // 3])


def test_png_missing_its_end_chunk_or_with_a_wrong_crc_is_refused():
    whole = picture()
    with pytest.raises(ImageError):
        image_check.inspect(whole[:-12])  # pixels decode, but IEND is missing
    wrong_crc = bytearray(whole)
    wrong_crc[-13] ^= 1  # corrupt the final IDAT CRC, leaving compressed pixels intact
    with pytest.raises(ImageError):
        image_check.inspect(bytes(wrong_crc))


def test_the_type_comes_from_the_bytes_whatever_the_name_or_browser_says(lib):
    """A JPEG sent as "image/png" (or named .png) is still saved as the JPEG it is."""
    root, row = lib
    saved = notes_store.save_asset(root, row, picture("JPEG"))
    assert saved["name"].endswith(".jpg")


def test_size_limits_are_checked_before_decoding(monkeypatch):
    with pytest.raises(ImageError, match="larger than 10 MB"):
        image_check.inspect(b"\x89PNG\r\n\x1a\n" + b"\0" * image_check.MAX_BYTES)
    with pytest.raises(ImageError, match="too large"):
        image_check.inspect(png_claiming(20_000, 20_000))  # 400 megapixels, in 70 bytes
    with pytest.raises(ImageError, match="too large"):
        image_check.inspect(png_claiming(image_check.MAX_SIDE + 1, 10))
    bomb = png_claiming(9_000, 9_000)  # 81 megapixels (made before counting: saving loads)
    decoded = []
    real_load = Image.Image.load
    monkeypatch.setattr(Image.Image, "load", lambda self: decoded.append(1) or real_load(self))
    with pytest.raises(ImageError):
        image_check.inspect(bomb)  # refused unread
    assert not decoded


def test_animated_images_are_refused():
    frames = [Image.new("RGB", (10, 10), c) for c in ("red", "blue")]
    for kind in ("PNG", "WEBP"):
        out = io.BytesIO()
        frames[0].save(out, kind, save_all=True, append_images=frames[1:], duration=100)
        with pytest.raises(ImageError, match="animated"):
            image_check.inspect(out.getvalue())


# --- keeping an image ------------------------------------------------------------------------


def test_an_image_is_kept_as_a_new_file_exactly_as_it_came(lib):
    root, row = lib
    data = picture()
    saved = notes_store.save_asset(root, row, data, now=datetime(2026, 11, 12, 14, 30, 5))
    assert saved["path"] == f"assets/{saved['name']}"
    assert saved["name"].startswith("img-20261112-143005-") and saved["name"].endswith(".png")
    assert (saved["width"], saved["height"], saved["bytes"]) == (40, 20, len(data))
    assert (assets_of(root, row) / saved["name"]).read_bytes() == data
    # nothing else appeared: no temporary file, no change to the notes
    assert sorted(p.name for p in assets_of(root, row).iterdir()) == [saved["name"]]
    assert (root / row["notes"] / "ch01-basics.md").read_text(encoding="utf-8") == "# Basics\n"


def test_names_never_collide_and_nothing_is_ever_overwritten(lib, monkeypatch):
    root, row = lib
    first = notes_store.save_asset(root, row, picture(), now=datetime(2026, 1, 1))
    names = iter([first["name"].split("-")[-1].split(".")[0], "abcdef"])  # the same, then new
    monkeypatch.setattr(notes_store.secrets, "token_hex", lambda n: next(names))
    second = notes_store.save_asset(root, row, picture(color=(0, 0, 255)), now=datetime(2026, 1, 1))
    assert second["name"] != first["name"] and second["name"].endswith("abcdef.png")
    assert (assets_of(root, row) / first["name"]).read_bytes() == picture()  # untouched
    # every name taken: refused, nothing replaced
    monkeypatch.setattr(notes_store.secrets, "token_hex", lambda n: "abcdef")
    with pytest.raises(NoteError, match="no free name"):
        notes_store.save_asset(root, row, picture(color=(0, 255, 0)), now=datetime(2026, 1, 1))
    assert (assets_of(root, row) / second["name"]).read_bytes() == picture(color=(0, 0, 255))


def test_many_images_saved_at_once_all_survive(lib):
    root, row = lib
    results, errors = [], []

    def save(i):
        try:
            results.append(notes_store.save_asset(root, row, picture(color=(i, 0, 0))))
        except Exception as e:  # pragma: no cover - reported below
            errors.append(e)

    threads = [threading.Thread(target=save, args=(i,)) for i in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len({r["name"] for r in results}) == 12
    for r in results:  # each one whole, as it was sent
        assert (assets_of(root, row) / r["name"]).stat().st_size == r["bytes"]
    assert len(list(assets_of(root, row).iterdir())) == 12


def test_a_write_cut_off_leaves_no_image_and_no_temporary_file(lib, monkeypatch):
    root, row = lib

    def broken_link(src, dst):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(safe_io.os, "link", broken_link)
    with pytest.raises(OSError):
        notes_store.save_asset(root, row, picture())
    assert not any(assets_of(root, row).iterdir())  # (the folder may exist: it holds nothing)


def test_a_filesystem_without_atomic_creation_is_refused_not_partly_written(lib, monkeypatch):
    root, row = lib

    def unsupported(*args):
        raise OSError(errno.ENOTSUP, "hard links unsupported")

    monkeypatch.setattr(safe_io.os, "link", unsupported)
    with pytest.raises(OSError, match="atomic image storage"):
        notes_store.save_asset(root, row, picture())
    assert not list(assets_of(root, row).iterdir())


def test_a_read_only_folder_fails_cleanly(lib, monkeypatch):
    root, row = lib

    def refused(*args, **kwargs):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(safe_io, "create_bytes", refused)
    with pytest.raises(PermissionError):
        notes_store.save_asset(root, row, picture())
    assert not assets_of(root, row).exists()


def test_no_notes_folder_or_an_assets_file_is_refused(lib):
    root, row = lib
    (root / row["notes"] / "assets").write_text("a file, not a folder", encoding="utf-8")
    with pytest.raises(NoteError, match="is a file"):
        notes_store.save_asset(root, row, picture())
    assert (root / row["notes"] / "assets").read_text(encoding="utf-8") == "a file, not a folder"
    shutil.rmtree(root / row["notes"])
    with pytest.raises(NoteError, match="no notes folder"):
        notes_store.save_asset(root, row, picture())
    assert not (root / row["notes"]).exists()  # never made anew


def test_a_catalog_notes_value_outside_notes_is_refused(lib):
    root, row = lib
    for bad in ("../outside", "C:/Windows", "notes/../../x", "books"):
        with pytest.raises(NoteError):
            notes_store.save_asset(root, {**row, "notes": bad}, picture())


@pytest.mark.skipif(sys.platform != "win32", reason="directory junctions are a Windows feature")
def test_an_assets_junction_pointing_elsewhere_is_never_written_through(lib, tmp_path):
    import _winapi

    root, row = lib
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    _winapi.CreateJunction(str(outside), str(root / row["notes"] / "assets"))
    with pytest.raises(NoteError, match="link pointing elsewhere"):
        notes_store.save_asset(root, row, picture())
    assert not any(outside.iterdir())
    (outside / "img.png").write_bytes(picture())
    with pytest.raises(NoteError):
        notes_store.asset_file(root, row, "img.png")  # never shown through it either


@pytest.mark.skipif(sys.platform != "win32", reason="directory junctions are a Windows feature")
def test_notes_kept_elsewhere_through_a_junction_take_images(lib, tmp_path):
    """A junction on the notes folder itself is the user's own arrangement (OneDrive)."""
    import _winapi

    root, row = lib
    onedrive = tmp_path / "OneDrive"
    onedrive.mkdir()
    here = root / row["notes"]
    shutil.move(here, onedrive / here.name)
    _winapi.CreateJunction(str(onedrive / here.name), str(here))
    saved = notes_store.save_asset(root, row, picture())
    assert (onedrive / here.name / "assets" / saved["name"]).read_bytes() == picture()
    assert notes_store.asset_file(root, row, saved["name"]).read_bytes() == picture()


def test_a_folder_swapped_for_a_link_while_saving_loses_only_the_new_file(lib, monkeypatch):
    """The check after writing: if the new file isn't in the notes folder after all, that file
    (and only it, still the same file) is removed again."""
    root, row = lib
    calls = []
    real_inside = notes_store._inside

    def inside(path, folder):
        calls.append(path)
        return real_inside(path, folder) if len(calls) <= 1 else False  # changed after writing

    monkeypatch.setattr(notes_store, "_inside", inside)
    with pytest.raises(NoteError, match="changed into a link"):
        notes_store.save_asset(root, row, picture())
    assert not any(assets_of(root, row).iterdir())


def test_the_post_check_never_removes_a_file_that_changed(lib, monkeypatch):
    root, row = lib
    path = assets_of(root, row) / "img-x.png"
    path.parent.mkdir()
    path.write_bytes(b"someone else's file, bigger than the image would be" * 10)
    monkeypatch.setattr(notes_store, "_inside", lambda p, f: False)
    with pytest.raises(NoteError):
        notes_store._check_created(path, path.parent, root / row["notes"], size=5)
    assert path.exists()


def test_a_frozen_library_is_never_written(lib):
    root, row = lib
    safe_io.freeze(root)
    try:
        with pytest.raises(safe_io.FrozenLocation):
            notes_store.save_asset(root, row, picture())
    finally:
        safe_io._frozen.pop()
    assert not assets_of(root, row).exists()


def test_long_paths_work(tmp_path):
    root = tmp_path / ("deep-" * 30) / "library"
    os.makedirs(safe_io._os_path(root))
    slug = "a-" * 40 + "book"
    folder = root / "notes" / slug
    os.makedirs(safe_io._os_path(folder))
    row = {"id": "x", "slug": slug, "notes": f"notes/{slug}/"}
    saved = notes_store.save_asset(root, row, picture())
    assert len(str(root / row["notes"] / saved["path"])) > 260
    assert safe_io.read_bytes(notes_store.asset_file(root, row, saved["name"])) == picture()


# --- naming and finding an image to show ------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["img-20261112-143005-a1b2c3.png", "Beam profile.PNG", "光束 截面.jpeg", "fig 1 (a).webp",
     "x.jpg", "a .png"],
)  # fmt: skip
def test_names_people_give_images_are_accepted(name):
    assert notes_store.asset_name_ok(name)


@pytest.mark.parametrize(
    "name",
    ["../x.png", "..\\x.png", "a/b.png", "a\\b.png", "C:x.png", ".hidden.png", " x.png",
     "x.svg", "x.png.html", "x.gif", "x", "con.png", "NUL.jpg", "com1.webp", "x\x00.png",
     "x\n.png", "a*b.png", "a?b.png", 'a"b.png', "a<b>.png", "a|b.png", "x" * 200 + ".png",
     "", None, 3],
)  # fmt: skip
def test_names_that_could_escape_or_mislead_are_refused(lib, name):
    root, row = lib
    assert not notes_store.asset_name_ok(name)
    with pytest.raises(NoteError):
        notes_store.asset_file(root, row, name)


def test_a_linked_image_pointing_out_of_assets_is_never_shown(lib, tmp_path):
    root, row = lib
    secret = tmp_path / "secret.png"
    secret.write_bytes(picture())
    (assets_of(root, row)).mkdir()
    link_or_skip(lambda: os.symlink(secret, assets_of(root, row) / "link.png"), "symlink")
    with pytest.raises(NoteError):
        notes_store.asset_file(root, row, "link.png")


# --- over HTTP --------------------------------------------------------------------------------


@pytest.fixture
def served(lib, monkeypatch):
    root, row = lib
    other = make_doc(root, OTHER, "Optics Primer")
    for module in (library_server, library_page):
        monkeypatch.setattr(module, "LIBRARY", root)
        monkeypatch.setattr(module, "CATALOG", root / "catalog.csv")
    server = ThreadingHTTPServer(("127.0.0.1", 0), library_server.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"

    def call(path, data=b"", headers=None, method="POST", token=library_server.TOKEN):
        sent = {"X-Library-Token": token} if token else {}
        request = urllib.request.Request(
            base + path, data=data if method == "POST" else None, method=method,
            headers={**sent, **(headers or {})},
        )  # fmt: skip
        try:
            with urllib.request.urlopen(request, timeout=10) as answer:
                return answer.status, dict(answer.headers), answer.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def upload(data, doc=row, key="file:ch01-basics.md", **kw):
        headers = {"X-Document-Id": doc["id"], "X-Note-Key": key}
        return call("/api/notes/asset", data, headers, **kw)

    yield root, row, other, call, upload
    server.shutdown()
    server.server_close()


def test_upload_then_show_an_image(served):
    import json

    root, row, _, call, upload = served
    status, _, answer = upload(picture())
    assert status == 200
    saved = json.loads(answer)
    assert saved["path"].startswith("assets/img-")
    status, headers, data = call(f"/notes-assets/{row['id']}/{saved['name']}", method="GET")
    assert status == 200 and data == picture()
    assert headers["Content-Type"] == "image/png"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Content-Security-Policy"] == "default-src 'none'; sandbox"
    assert headers["Cross-Origin-Resource-Policy"] == "same-origin"
    assert "no-cache" in headers["Cache-Control"]
    # the preview's redraws: an unchanged image is answered "not modified", without its bytes
    status, _, data = call(f"/notes-assets/{row['id']}/{saved['name']}", method="GET",
                           headers={"If-None-Match": headers["ETag"]})  # fmt: skip
    assert status == 304 and data == b""


def test_not_modified_is_only_said_of_an_image_checked_again(served, monkeypatch):
    import hashlib
    import json

    root, row, other, call, upload = served
    saved = json.loads(upload(picture())[2])
    url = f"/notes-assets/{row['id']}/{saved['name']}"
    _, headers, data = call(url, method="GET")
    etag = headers["ETag"]
    assert etag == f'"{hashlib.sha256(data).hexdigest()[:32]}"'  # it names the bytes themselves
    checked = []
    real = image_check.inspect

    def counting(data):
        checked.append(len(data))
        return real(data)

    monkeypatch.setattr(image_check, "inspect", counting)
    status, answer, body = call(url, method="GET", headers={"If-None-Match": etag})
    assert status == 304 and body == b"" and answer["ETag"] == etag
    assert checked == [len(data)]  # decoded and checked again before saying so
    assert answer["X-Content-Type-Options"] == "nosniff"  # the same headers as a 200
    assert answer["Content-Security-Policy"] == "default-src 'none'; sandbox"
    # the folder and name checks still come first: another document, a bad name
    assert call(f"/notes-assets/{other['id']}/{saved['name']}", method="GET",
                headers={"If-None-Match": etag})[0] == 404  # fmt: skip
    assert call(f"/notes-assets/{row['id']}/..%2Fch01-basics.md", method="GET",
                headers={"If-None-Match": etag})[0] == 404  # fmt: skip
    path = assets_of(root, row) / saved["name"]
    # a different image of the same size under the same name: sent again with its own tag
    replacement = next(
        data
        for data in (picture(color=(c, 30, 30)) for c in range(256))
        if len(data) == len(picture()) and data != picture()
    )
    replaced = path.with_name("replacement.tmp")
    replaced.write_bytes(replacement)
    os.replace(replaced, path)
    status, headers, data = call(url, method="GET", headers={"If-None-Match": etag})
    assert status == 200 and data == replacement and headers["ETag"] != etag


def test_invalid_bytes_with_the_same_size_time_and_file_are_never_not_modified(served):
    import json

    root, row, _, call, upload = served
    saved = json.loads(upload(picture())[2])
    url = f"/notes-assets/{row['id']}/{saved['name']}"
    etag = call(url, method="GET")[1]["ETag"]
    path = assets_of(root, row) / saved["name"]
    before = os.stat(path)
    # Overwritten in place (the same file id), the same size, and its time put back exactly
    with open(path, "r+b") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + b"\0" * (before.st_size - 8))
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    after = os.stat(path)
    assert (after.st_size, after.st_mtime_ns, after.st_ino) == (
        before.st_size, before.st_mtime_ns, before.st_ino)  # fmt: skip
    status, headers, data = call(url, method="GET", headers={"If-None-Match": etag})
    assert status == 415 and data != b"" and "ETag" not in headers


def test_uploads_are_refused_unless_everything_is_right(served):
    root, row, other, call, upload = served
    assert upload(picture(), token=None)[0] == 403
    assert upload(picture(), token="wrong")[0] == 403
    assert upload(picture(), doc={"id": "0" * 8 + "-0000-4000-8000-" + "0" * 12})[0] == 404
    assert upload(picture(), key="topic:coma")[0] == 400  # topic notes: no assets folder
    assert upload(picture(), key="file:../../catalog.md")[0] == 400
    assert upload(picture(), key="file:nonexistent.md")[0] == 400
    status, _, answer = upload(b"<svg onload=alert(1)></svg>")
    assert status == 400 and b"PNG, JPEG and WebP" in answer
    assert not assets_of(root, row).exists()  # nothing was written for any of these
    big = b"\x89PNG\r\n\x1a\n" + b"\0" * (image_check.MAX_BYTES + 1)
    try:
        status = upload(big)[0]
    except ConnectionError, urllib.error.URLError:
        status = 413  # (the server answered before the whole body was sent)
    assert status == 413


def test_showing_is_contained(served, tmp_path):
    root, row, other, call, upload = served
    import json

    saved = json.loads(upload(picture())[2])
    mine = f"/notes-assets/{row['id']}/{saved['name']}"
    # another document's id never shows this document's image
    assert call(f"/notes-assets/{other['id']}/{saved['name']}", method="GET")[0] == 404
    for path in [
        f"/notes-assets/{row['id']}/..%2F..%2Fcatalog.csv",
        f"/notes-assets/{row['id']}/..%5C..%5Ccatalog.csv",
        f"/notes-assets/{row['id']}/%2e%2e%2fREADME.md",
        f"/notes-assets/{row['id']}/README.md",
        f"/notes-assets/{row['id']}/%252e%252e%252fx.png",  # encoded twice: one decoding only
        f"/notes-assets/{row['id']}/%FF%FE.png",  # not UTF-8
        f"/notes-assets/{row['id']}/C%3A%5CWindows%5Cwin.ini",
        "/notes-assets/not-an-id/x.png",
    ]:
        assert call(path, method="GET")[0] in (403, 404), path
    # only this server's own pages (a browser says where a request comes from)
    for site in ("cross-site", "same-site"):
        assert call(mine, method="GET", headers={"Sec-Fetch-Site": site})[0] == 403
    for site in ("same-origin", "none"):
        assert call(mine, method="GET", headers={"Sec-Fetch-Site": site})[0] == 200
    # and only for this computer (DNS rebinding)
    assert call(mine, method="GET", headers={"Host": "evil.example"})[0] == 403


def test_the_type_served_is_read_from_the_file(served):
    root, row, _, call, _ = served
    assets = assets_of(root, row)
    assets.mkdir()
    (assets / "evil.png").write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg"></svg>')
    (assets / "page.jpg").write_bytes(b"<!doctype html><script>alert(1)</script>")
    (assets / "real.png").write_bytes(picture("JPEG"))  # a JPEG named .png: served as a JPEG
    assert call(f"/notes-assets/{row['id']}/evil.png", method="GET")[0] == 415
    assert call(f"/notes-assets/{row['id']}/page.jpg", method="GET")[0] == 415
    status, headers, _ = call(f"/notes-assets/{row['id']}/real.png", method="GET")
    assert status == 200 and headers["Content-Type"] == "image/jpeg"


def test_unusual_names_put_there_by_hand_are_shown(served):
    from urllib.parse import quote

    root, row, _, call, _ = served
    assets = assets_of(root, row)
    assets.mkdir()
    for name in ("Beam profile (fig 2).png", "光束 截面.webp", "100% done.jpg"):
        kind = {"png": "PNG", "webp": "WEBP", "jpg": "JPEG"}[name.rsplit(".", 1)[1]]
        (assets / name).write_bytes(picture(kind))
        status, _, data = call(f"/notes-assets/{row['id']}/{quote(name)}", method="GET")
        assert status == 200 and data == picture(kind), name


def test_serving_rejects_a_signature_without_a_decodable_image(served):
    root, row, _, call, _ = served
    assets = assets_of(root, row)
    assets.mkdir()
    (assets / "broken.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"not a PNG")
    assert call(f"/notes-assets/{row['id']}/broken.png", method="GET")[0] == 415


def test_a_merged_documents_id_shows_the_kept_documents_images(served):
    import json

    root, row, other, call, upload = served
    saved = json.loads(upload(picture(), doc=other)[2])
    catalog.retire(root / "catalog.csv", other["id"], "merged", other, into=row["id"])
    catalog.remove(root / "catalog.csv", other["id"])
    notes_store.copy_assets(root / other["notes"], root / row["notes"], OTHER)
    status, _, data = call(f"/notes-assets/{other['id']}/{saved['name']}", method="GET")
    assert status == 200 and data == picture()


# --- merging, removing, backing up, moving -----------------------------------------------------


def test_merging_brings_the_images_and_their_links_follow_a_rename(lib):
    root, row = lib
    other = make_doc(root, OTHER, "Optics Primer")
    mine, theirs = assets_of(root, row), assets_of(root, other)
    theirs.mkdir()
    mine.mkdir()
    (theirs / "same.png").write_bytes(picture())
    (mine / "same.png").write_bytes(picture())  # identical: not copied twice
    (theirs / "fig 1.png").write_bytes(picture(color=(0, 0, 255)))
    (mine / "fig 1.png").write_bytes(picture(color=(0, 255, 0)))  # a different image
    (theirs / "only.webp").write_bytes(picture("WEBP"))
    copied, renamed = notes_store.copy_assets(root / other["notes"], root / row["notes"], OTHER)
    assert copied == 2
    assert renamed == {"fig 1.png": f"fig 1-from-{OTHER}.png"}
    assert (mine / "fig 1.png").read_bytes() == picture(color=(0, 255, 0))  # never replaced
    assert (mine / renamed["fig 1.png"]).read_bytes() == picture(color=(0, 0, 255))
    assert (mine / "only.webp").read_bytes() == picture("WEBP")
    text = "![a](assets/fig%201.png) ![b](<./assets/fig 1.png>) ![c](assets/same.png)"
    assert notes_store.relink(text, renamed) == (
        f"![a](assets/fig%201-from-{OTHER}.png) ![b](<./assets/fig 1-from-{OTHER}.png>) "
        "![c](assets/same.png)"
    )


def test_images_count_as_the_users_own_work(lib):
    root, row = lib
    folder = root / row["notes"]
    assert not add_book.has_own_work(folder)
    saved = notes_store.save_asset(root, row, picture())
    assert add_book.has_own_work(folder)  # even if the link to it was undone
    (folder / "assets" / saved["name"]).unlink()
    assert not add_book.has_own_work(folder)


def test_merging_a_long_colliding_image_name_keeps_a_servable_name(lib):
    root, row = lib
    other = make_doc(root, OTHER, "Other")
    source, target = assets_of(root, other), assets_of(root, row)
    source.mkdir()
    target.mkdir()
    name = "f" * 140 + ".png"
    assert notes_store.asset_name_ok(name)
    safe_io.write_bytes(source / name, picture())
    safe_io.write_bytes(target / name, picture(color="blue"))
    count, renamed = notes_store.copy_assets(root / other["notes"], root / row["notes"], "a" * 100)
    assert count == 1 and notes_store.asset_name_ok(renamed[name])
    assert safe_io.read_bytes(notes_store.asset_file(root, row, renamed[name])) == picture()
    assert safe_io.read_bytes(target / name) == picture(color="blue")


def test_merge_into_copies_images_with_the_notes(lib, monkeypatch):
    root, row = lib
    other = make_doc(root, OTHER, "Optics Primer")
    monkeypatch.setattr(add_book, "LIBRARY", root)
    monkeypatch.setattr(add_book, "CATALOG", root / "catalog.csv")
    monkeypatch.setattr(add_book, "NOTES", root / "notes")
    monkeypatch.setattr(add_book, "EXAMPLES", root / "examples")
    saved = notes_store.save_asset(root, other, picture(color=(1, 2, 3)))
    note = root / other["notes"] / "ch01-basics.md"
    note.write_text(f"# Basics\n\nMy figure:\n\n![image]({saved['path']})\n", encoding="utf-8")
    moved = add_book.merge_into(other["id"], row["id"])
    assert "1 image" in moved
    kept = root / row["notes"]
    assert (kept / saved["path"]).read_bytes() == picture(color=(1, 2, 3))
    assert f"![image]({saved['path']})" in (kept / "ch01-basics.md").read_text(encoding="utf-8")
    assert (root / other["notes"] / saved["path"]).exists()  # the merged copy keeps its own


def files_in(folder: Path) -> dict[str, bytes]:
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*")
            if p.is_file()}  # fmt: skip


def test_copying_images_again_copies_nothing_twice(lib):
    root, row = lib
    other = make_doc(root, OTHER, "Optics Primer")
    mine, theirs = assets_of(root, row), assets_of(root, other)
    theirs.mkdir()
    mine.mkdir()
    (theirs / "fig.png").write_bytes(picture(color=(0, 0, 255)))
    (mine / "fig.png").write_bytes(picture(color=(0, 255, 0)))  # a different image, same name
    (theirs / "new.png").write_bytes(picture(color=(9, 9, 9)))
    first = notes_store.copy_assets(root / other["notes"], root / row["notes"], OTHER)
    after_first = files_in(mine)
    again = notes_store.copy_assets(root / other["notes"], root / row["notes"], OTHER)
    assert first == (2, {"fig.png": f"fig-from-{OTHER}.png"})
    assert again == (0, first[1])  # the same names, nothing copied
    assert files_in(mine) == after_first
    assert (mine / "fig.png").read_bytes() == picture(color=(0, 255, 0))  # never replaced


def test_a_name_taken_by_another_image_is_passed_over(lib):
    root, row = lib
    other = make_doc(root, OTHER, "Optics Primer")
    mine, theirs = assets_of(root, row), assets_of(root, other)
    theirs.mkdir()
    mine.mkdir()
    (theirs / "fig.png").write_bytes(picture())
    (mine / "fig.png").write_bytes(picture(color=(0, 255, 0)))
    (mine / f"fig-from-{OTHER}.png").write_bytes(picture(color=(1, 1, 1)))  # also taken
    copied, renamed = notes_store.copy_assets(root / other["notes"], root / row["notes"], OTHER)
    assert (copied, renamed) == (1, {"fig.png": f"fig-from-{OTHER}-2.png"})
    assert (mine / "fig.png").read_bytes() == picture(color=(0, 255, 0))
    assert (mine / f"fig-from-{OTHER}.png").read_bytes() == picture(color=(1, 1, 1))


def test_a_link_to_the_same_bytes_elsewhere_is_never_taken_for_a_copy(lib, tmp_path):
    root, row = lib
    other = make_doc(root, OTHER, "Optics Primer")
    mine, theirs = assets_of(root, row), assets_of(root, other)
    theirs.mkdir()
    mine.mkdir()
    (theirs / "fig.png").write_bytes(picture())
    outside = tmp_path / "outside.png"
    outside.write_bytes(picture())  # the same bytes, but out of the folder: never "the same"
    link_or_skip(lambda: os.symlink(outside, mine / "fig.png"), "symbolic link")
    copied, renamed = notes_store.copy_assets(root / other["notes"], root / row["notes"], OTHER)
    assert (copied, renamed) == (1, {"fig.png": f"fig-from-{OTHER}.png"})
    assert (mine / "fig.png").is_symlink() and outside.read_bytes() == picture()


def test_a_copy_cut_off_halfway_completes_on_the_next_try(lib, monkeypatch):
    root, row = lib
    other = make_doc(root, OTHER, "Optics Primer")
    theirs = assets_of(root, other)
    theirs.mkdir()
    for n in range(3):
        (theirs / f"img-{n}.png").write_bytes(picture(color=(n, n, n)))
    real, made = safe_io.create_bytes, []

    def full_disk_after_one(path, data, **kw):
        if made:
            raise OSError(28, "No space left on device")
        real(path, data, **kw)
        made.append(path)

    monkeypatch.setattr(safe_io, "create_bytes", full_disk_after_one)
    with pytest.raises(OSError):
        notes_store.copy_assets(root / other["notes"], root / row["notes"], OTHER)
    monkeypatch.setattr(safe_io, "create_bytes", real)
    copied, renamed = notes_store.copy_assets(root / other["notes"], root / row["notes"], OTHER)
    assert (copied, renamed) == (2, {})
    assert files_in(assets_of(root, row)) == files_in(theirs)


@pytest.fixture
def merging(lib, monkeypatch):
    root, row = lib
    for name, value in (("LIBRARY", root), ("CATALOG", root / "catalog.csv"),
                        ("NOTES", root / "notes"), ("EXAMPLES", root / "examples")):  # fmt: skip
        monkeypatch.setattr(add_book, name, value)
    other = make_doc(root, OTHER, "Optics Primer")
    saved = notes_store.save_asset(root, other, picture(color=(1, 2, 3)))
    (assets_of(root, row)).mkdir()
    (assets_of(root, row) / saved["name"]).write_bytes(picture(color=(7, 7, 7)))  # name taken
    note = root / other["notes"] / "ch01-basics.md"
    note.write_text(f"# Basics\n\nMine:\n\n![image]({saved['path']})\n", encoding="utf-8")
    (root / row["notes"] / "ch01-basics.md").write_text("# Basics\n\nKept's own.\n", "utf-8")
    return root, row, other, saved


def test_merge_into_run_again_after_being_cut_off_duplicates_nothing(merging, monkeypatch):
    root, row, other, saved = merging
    real = add_book.notes_store.relink

    def cut_off(*args):
        raise OSError(5, "the drive was unplugged")

    monkeypatch.setattr(add_book.notes_store, "relink", cut_off)  # after the images, before notes
    with pytest.raises(OSError):
        add_book.merge_into(other["id"], row["id"])
    monkeypatch.setattr(add_book.notes_store, "relink", real)
    add_book.merge_into(other["id"], row["id"])
    kept = files_in(root / row["notes"])
    add_book.merge_into(other["id"], row["id"])  # and once more: nothing changes
    assert files_in(root / row["notes"]) == kept
    new_name = f"{Path(saved['name']).stem}-from-{OTHER}.png"
    assert sorted(n for n in kept if n.startswith("assets/")) == sorted(
        [f"assets/{saved['name']}", f"assets/{new_name}"]
    )
    assert kept[f"assets/{new_name}"] == picture(color=(1, 2, 3))
    copies = sorted(n for n in kept if n.startswith("ch01-basics"))
    assert copies == sorted(["ch01-basics.md", f"ch01-basics-from-{OTHER}.md"])
    assert f"assets/{new_name}" in kept[f"ch01-basics-from-{OTHER}.md"].decode("utf-8")
    assert kept["ch01-basics.md"] == (root / row["notes"] / "ch01-basics.md").read_bytes()
    assert b"Kept's own." in kept["ch01-basics.md"]


def test_without_hard_links_a_merge_stops_before_changing_the_kept_document(merging, monkeypatch):
    root, row, other, saved = merging
    before_catalog = (root / "catalog.csv").read_bytes()
    before_notes = files_in(root / row["notes"])

    def unsupported(*args):
        raise OSError(errno.ENOTSUP, "hard links unsupported")

    monkeypatch.setattr(safe_io.os, "link", unsupported)
    with pytest.raises(OSError, match="atomic image storage"):
        add_book.merge_into(other["id"], row["id"])
    assert (root / "catalog.csv").read_bytes() == before_catalog
    assert files_in(root / row["notes"]) == before_notes
    assert (root / other["notes"] / saved["path"]).read_bytes() == picture(color=(1, 2, 3))


def test_refresh_reports_a_merge_that_stopped_and_archives_nothing(merging, monkeypatch):
    import library_jobs

    root, row, other, saved = merging
    pair = {"keep": row["id"], "drop": other["id"], "other": other["id"], "reason": "same file",
            "why": "the same"}  # fmt: skip
    monkeypatch.setattr(add_book, "catalog_repeats", lambda: [pair])
    removed = []
    monkeypatch.setattr(add_book, "remove_book", lambda *a, **kw: removed.append(a))

    def unsupported(*args):
        raise OSError(errno.ENOTSUP, "hard links unsupported")

    monkeypatch.setattr(safe_io.os, "link", unsupported)
    jobs = library_jobs._check_catalog_repeats()
    assert len(jobs) == 1 and jobs[0]["status"] == "error"
    assert "merging them stopped" in jobs[0]["message"]
    assert str(root) not in jobs[0]["message"]  # the reason, never a full path
    assert not removed and other["id"] in catalog.load(root / "catalog.csv")


def test_the_folder_backup_holds_the_images_and_restores_them(lib, tmp_path_factory):
    root, row = lib
    saved = notes_store.save_asset(root, row, picture())
    note = root / row["notes"] / "ch01-basics.md"
    note.write_text(f"![image]({saved['path']})\n", encoding="utf-8")
    dest = tmp_path_factory.mktemp("backups")
    result = folder_backup.back_up(dest, pdfs=False, library=root)
    restored_root = tmp_path_factory.mktemp("restored") / "目录 with spaces"
    with zipfile.ZipFile(dest / result["file"]) as z:
        z.extractall(restored_root)
    found = list(restored_root.rglob(saved["name"]))
    assert len(found) == 1 and found[0].read_bytes() == picture()
    # the note's relative link still names it, wherever the library now is
    restored_note = next(restored_root.rglob("ch01-basics.md"))
    assert (restored_note.parent / saved["path"]).read_bytes() == picture()


def test_a_moved_library_still_shows_its_images(lib, tmp_path):
    root, row = lib
    saved = notes_store.save_asset(root, row, picture())
    moved = tmp_path / "移动后 moved library"
    shutil.copytree(root, moved)
    assert notes_store.asset_file(moved, row, saved["name"]).read_bytes() == picture()
