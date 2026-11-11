"""Build the ready-to-use Windows package: dist/myLibrary-<version>/ and its .zip.

    uv run scripts/build_package.py

The package needs no Python, uv, git or command line on the buyer's computer:
  runtime/python/          a portable Python (copied from the one uv installed)
  runtime/site-packages/   only what the library needs (pyproject "dependencies", from uv.lock)
  scripts/                 the tool
  .cache/reader/           the PDF viewer, the dictionary, the notes' preview (markdown-it) and
                           its maths (KaTeX, with its fonts), so it works offline at once
  launch.py, Start myLibrary.cmd, README.txt, LICENSE, notices and third-party licenses
  package.toml             marks it as the package: settings go to %APPDATA%/myLibrary, and the
                           Python features (chapter scripts) are off
"""

import shutil
import subprocess
import sys
import tomllib
from datetime import date
from pathlib import Path

import paths
import reader

APP = paths.APP
DIST = APP / "dist"

# Not needed to run the library; leaving them out saves ~100 MB
SKIP_IN_PYTHON = {"test", "tests", "idlelib", "tkinter", "turtledemo", "tcl", "include", "libs",
                  "Scripts", "site-packages", "__pycache__", "ensurepip", "venv"}  # fmt: skip
SKIP_SCRIPTS = {"build_package.py", "make_shortcut.py"}  # build-time / development only
# Model-conversion tools in onnxruntime: OCR only *runs* models. They also hold the package's
# deepest file paths, which can break unzipping into a deep folder (Windows' 260-character limit)
PRUNE = ["onnxruntime/tools", "onnxruntime/transformers", "onnxruntime/quantization"]
LONGEST_OK = 130  # characters, from the package's own folder down


def run(command: list[str]) -> None:
    print("  $", " ".join(command))
    subprocess.run(command, check=True)


def copy_python(target: Path) -> Path:
    """The interpreter uv installed (python-build-standalone: relocatable), trimmed."""
    base = Path(sys.base_prefix)
    if not (base / "pythonw.exe").exists():
        sys.exit(f"No pythonw.exe in {base}: build the package on Windows, with uv's Python")
    print(f"  Python {sys.version.split()[0]} from {base}")
    shutil.copytree(base, target, ignore=lambda d, names: [n for n in names if n in SKIP_IN_PYTHON])
    return target / "python.exe"


def install_packages(python: Path, target: Path) -> None:
    """The library's own dependencies at the versions in uv.lock (no dev/science/optics)."""
    requirements = DIST / "requirements.txt"
    run(["uv", "export", "--quiet", "--no-default-groups", "--no-emit-project", "--no-hashes",
         "--format", "requirements-txt", "--output-file", str(requirements)])  # fmt: skip
    run(["uv", "pip", "install", "--quiet", "--python", str(python), "--target", str(target),
         "-r", str(requirements)])  # fmt: skip
    requirements.unlink()
    for folder in PRUNE:
        shutil.rmtree(target / folder, ignore_errors=True)


def check_path_lengths(root: Path) -> None:
    """Windows can't unzip paths over 260 characters: keep the package's own paths short."""
    longest = max((p for p in root.rglob("*") if p.is_file()), key=lambda p: len(str(p)))
    length = len(longest.relative_to(root.parent).as_posix())
    print(f"  longest path in the package: {length} characters")
    if length > LONGEST_OK:
        sys.exit(f"  ! too long: {longest.relative_to(root.parent)}")


def copy_reading_view(root: Path) -> None:
    """The reader's offline parts into the package, as reader.setup() installed them. KaTeX is
    copied only when every file of it passes its check: a damaged copy would leave the package
    without maths (its reader page wouldn't load it), so the build stops instead."""
    if not reader.katex_installed():
        sys.exit("  ! KaTeX isn't the verified one: uv run scripts/reader.py --setup-maths")
    cache = root / ".cache" / "reader"
    shutil.copytree(reader.PDFJS, cache / "pdfjs")
    shutil.copytree(reader.MARKDOWN_IT, cache / "markdown-it")
    shutil.copytree(reader.KATEX, cache / "katex")
    shutil.copy2(reader.DICT_DB, cache / "ecdict.db")


def main() -> None:
    version = tomllib.loads((APP / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = version["version"]
    name = f"myLibrary-{version}"
    root = DIST / name
    print(f"Building {paths.display(root)}")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    print("1/5 PDF viewer, dictionary, notes preview and maths")
    reader.setup()
    copy_reading_view(root)

    print("2/5 Python")
    python = copy_python(root / "runtime" / "python")

    print("3/5 packages")
    install_packages(python, root / "runtime" / "site-packages")

    print("4/5 the tool")
    shutil.copytree(
        APP / "scripts",
        root / "scripts",
        ignore=lambda d, names: [n for n in names if n in SKIP_SCRIPTS or n == "__pycache__"],
    )
    for f in ("launch.py", "Start myLibrary.cmd", "README.txt"):
        shutil.copy2(APP / "package" / f, root / f)
    shutil.copy2(APP / "LICENSE", root / "LICENSE")
    shutil.copy2(APP / "THIRD_PARTY_NOTICES.md", root / "THIRD_PARTY_NOTICES.md")
    licenses = root / "third_party_licenses"
    licenses.mkdir()
    shutil.copy2(APP / "package" / "licenses" / "ECDICT-LICENSE.txt", licenses)
    shutil.copy2(reader.PDFJS / "LICENSE", licenses / "PDF.js-LICENSE.txt")
    shutil.copy2(reader.MARKDOWN_IT / "LICENSE", licenses / "markdown-it-LICENSE.txt")
    shutil.copy2(reader.KATEX / "LICENSE", licenses / "KaTeX-LICENSE.txt")
    shutil.copy2(root / "runtime" / "python" / "LICENSE.txt", licenses / "Python-LICENSE.txt")
    (root / "package.toml").write_text(
        f'# The ready-to-use package of myLibrary (see scripts/paths.py)\nversion = "{version}"\n'
        f'built = "{date.today().isoformat()}"\n',
        encoding="utf-8",
    )

    check_path_lengths(root)
    print("5/5 zip")
    archive = shutil.make_archive(str(DIST / f"{name}-win64"), "zip", DIST, name)
    size = Path(archive).stat().st_size / 1e6
    print(f"Done: {paths.display(Path(archive))} ({size:.0f} MB)")


if __name__ == "__main__":
    main()
