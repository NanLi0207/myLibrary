"""The ready-to-use package's licences (scripts/build_package.py): every bundled Python
distribution comes with its licence text, our own licence files are there, and
THIRD_PARTY_NOTICES.md names everything the package bundles. No package is built here."""

import re
import shutil
import subprocess

import build_package
import paths
import pytest


def dist_info(site, name, *licence_files):
    info = site / f"{name}.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text("Name: x\n", encoding="utf-8")
    for f in licence_files:
        (info / f).parent.mkdir(parents=True, exist_ok=True)
        (info / f).write_text("licence\n", encoding="utf-8")


def test_a_distribution_without_any_licence_text_stops_the_build(tmp_path):
    site = tmp_path / "site-packages"
    dist_info(site, "with_licence-1.0", "licenses/LICENSE")
    dist_info(site, "with_copying-1.0", "COPYING.txt")
    # texts in a folder, named after the licence (as pypdfium2 ships them)
    dist_info(site, "in_a_folder-5.14.0", "licenses/LICENSES/Apache-2.0.txt",
              "licenses/data/windows_x64/BUILD_LICENSES/zlib.txt")  # fmt: skip
    dist_info(site, "flatbuffers-25.12.19")  # none in its wheel: we provide it
    dist_info(site, "onnxruntime-1.31.1")  # its licence and notices are in its package folder
    (site / "onnxruntime").mkdir()
    (site / "onnxruntime" / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (site / "onnxruntime" / "ThirdPartyNotices.txt").write_text("notices\n", encoding="utf-8")
    dist_info(site, "mystery-2.0")  # nothing at all
    assert build_package.unlicensed(site) == ["mystery-2.0"]
    with pytest.raises(SystemExit, match="mystery-2.0"):
        build_package.check_licenses(site)
    (site / "onnxruntime" / "ThirdPartyNotices.txt").unlink()  # one of its files missing
    assert build_package.unlicensed(site) == ["mystery-2.0", "onnxruntime-1.31.1"]


def touch(site, name):
    (site / name).parent.mkdir(parents=True, exist_ok=True)
    (site / name).write_bytes(b"x")


def test_unused_ffmpeg_and_unlicensed_fonts_are_left_out_and_nothing_else(tmp_path):
    site = tmp_path / "site-packages"
    others = ["cv2/cv2.pyd", "cv2/LICENSE-3RD-PARTY.txt", "reportlab/fonts/00readme.txt",
              "reportlab/pdfbase/_fontdata.py", "shapely.libs/geos_c-x.dll"]  # fmt: skip
    for name in build_package.EXCLUDE + build_package.KEEP + others:
        touch(site, name)
    removed = build_package.exclude(site)
    assert sorted(removed) == sorted(build_package.EXCLUDE)
    assert not any((site / n).exists() for n in build_package.EXCLUDE)
    assert all((site / n).is_file() for n in build_package.KEEP + others)


def test_the_exclusions_are_exactly_the_approved_files():
    excluded = set(build_package.EXCLUDE)
    assert "cv2/opencv_videoio_ffmpeg500_64.dll" in excluded
    assert "reportlab/fonts/hb-test.ttf" in excluded
    assert len([n for n in excluded if n.endswith((".afm", ".pfb"))]) == 2 * 17
    assert not [n for n in excluded if "DarkGarden" in n or "Vera" in n or "cv2.pyd" in n]
    assert not excluded & set(build_package.KEEP)


@pytest.mark.parametrize("problem", ["another ffmpeg", "a kept font missing"])
def test_the_build_stops_if_ffmpeg_remains_or_a_kept_file_is_gone(tmp_path, problem):
    site = tmp_path / "site-packages"
    for name in build_package.EXCLUDE + build_package.KEEP:
        touch(site, name)
    if problem == "another ffmpeg":
        touch(site, "cv2/opencv_videoio_ffmpeg510_64.dll")  # (a future wheel's name)
    else:
        (site / "reportlab/fonts/DarkGarden.sfd").unlink()
    with pytest.raises(SystemExit):
        build_package.exclude(site)


def test_the_geos_notice_names_the_shipped_binaries():
    notice = (build_package.LICENSES / "GEOS-LGPL-NOTICE.txt").read_text("utf-8")
    for fact in ("geos-bf067cd6ff74ee0ad5f3ff52c7ef08c9.dll",
                 "0948bdb5c70b82e5055b55e9419b78d68372b1d0ec877277fa6e79276f6299b9",
                 "geos_c-6dd9fd915eef8a7928285416bef1e666.dll",
                 "6e65985b30831761887de3217853a720147626b18cb41668cd2bdc43d1bcded1",
                 "48dd1d961391f314ab7fa8812c86ca2a727bee2bdca1478730eacaea007da18e",
                 "3c20919cda9a505db07b5216baa980bacdaa0702da715b43f176fb07eff7e716",
                 "Evidence limits"):  # fmt: skip
        assert fact in notice


def test_our_licence_files_are_there_and_whole():
    for name in build_package.OUR_LICENSE_FILES:
        text = (build_package.LICENSES / name).read_text(encoding="utf-8")
        assert len(text) > 500, name
    flatbuffers = (build_package.LICENSES / "FlatBuffers-LICENSE.txt").read_text("utf-8")
    assert "Apache License" in flatbuffers and "Version 2.0, January 2004" in flatbuffers
    assert "END OF TERMS AND CONDITIONS" in flatbuffers
    bundled = (build_package.LICENSES / "markdown-it-bundled-LICENSES.txt").read_text("utf-8")
    for name in ("entities 8.1.0", "linkify-it 6.1.0", "mdurl 2.1.0", "uc.micro 3.0.0",
                 "punycode.js 2.3.1"):  # fmt: skip
        assert name in bundled
    python = (build_package.LICENSES / "Python-incorporated-software.txt").read_text("utf-8")
    for part in ("OpenSSL", "expat", "libffi", "zlib", "libmpdec", "mimalloc"):
        assert part in python


def test_the_notices_name_every_bundled_python_package():
    uv = shutil.which("uv")
    if not uv:
        pytest.skip("uv isn't on PATH (it lists what the package bundles)")
    exported = subprocess.run(
        [uv, "export", "--quiet", "--no-default-groups", "--no-emit-project", "--no-hashes",
         "--frozen", "--format", "requirements-txt"],
        cwd=paths.APP, capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout  # fmt: skip
    bundled = {re.split(r"[=<>; ]", line)[0].strip().lower()
               for line in exported.splitlines() if line and line[0].isalnum()}  # fmt: skip
    notices = (paths.APP / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8").lower()
    named = {n for n in bundled if n in notices or n.replace("-", "_") in notices}
    assert bundled and not bundled - named, sorted(bundled - named)
