"""The D18 gate (M7.1 S0): `add_book.rename_document` must not be reachable from production code
until D18 (ROADMAP section 11: a failed rename can lose its recovery journal) is repaired and
independently reviewed. This test only keeps new callers out. It does **not** fix D18.

A conservative static safeguard, deliberately simple (not an analyser):
- It covers only the Python files under scripts/ and package/.
- False positives: any name, attribute, import or string spelled exactly `rename_document`
  there fails it, even an unrelated local variable or another object's attribute. That is
  intended: rename it, or fix D18 first.
- Not seen: a computed name (`getattr(m, "rename_" + "document")`, `importlib`, `eval`/`exec`),
  code outside those two folders, and callers written in other languages. Reviews still check
  for new rename callers.

Production code is every Python file under scripts/ and package/. Its only allowed mention of
the name is the function's own definition (`def rename_document`). Its existing recovery
(`recover_operations` → `_undo_rename`) and the tests that exercise renaming directly are left
as they are. Any other use is reported with its file and line: a call, an attribute such as
`add_book.rename_document`, an import, an alias or a string such as `getattr(…, "rename_document")`.
Once D18 is fixed, remove this guard in the same reviewed change that adds the first caller."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCTION = ("scripts", "package")
NAME = "rename_document"


def uses(source: str) -> list[tuple[int, str]]:
    """Every use of NAME in one module's source, except its definition: (line, kind)."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name) and node.id == NAME:
            found.append((node.lineno, "name"))
        elif isinstance(node, ast.Attribute) and node.attr == NAME:
            found.append((node.lineno, "attribute"))
        elif isinstance(node, ast.alias) and NAME in (node.name, node.asname):
            found.append((node.lineno, "import"))
        elif isinstance(node, ast.Constant) and node.value == NAME:
            found.append((node.lineno, "string"))
    return found


def callers(root: Path) -> list[str]:
    """Every use of NAME in the production code under `root`, as 'file:line kind'."""
    found = []
    for folder in PRODUCTION:
        for path in sorted((root / folder).rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for line, kind in uses(text):
                found.append(f"{path.relative_to(root).as_posix()}:{line} {kind}")
    return found


def test_no_production_code_calls_rename_document_until_d18_is_fixed():
    found = callers(ROOT)
    assert not found, (
        "D18 is not fixed: rename_document must have no production caller (UI, CLI, API, "
        "server endpoint, background job) until D18 is repaired and reviewed "
        "(ROADMAP section 11). This static guard may also flag an unrelated use of the same "
        "name: rename that instead. Found: " + ", ".join(found)
    )


def test_the_function_still_exists_where_the_guard_expects_it():
    """The guard is only meaningful if it looks at the real function: renamed or moved, the
    guard must be updated rather than pass vacuously."""
    tree = ast.parse((ROOT / "scripts" / "add_book.py").read_text(encoding="utf-8"))
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert NAME in names


def test_the_guard_finds_each_kind_of_caller(tmp_path):
    """Negative control: synthetic production modules that reach the function are reported."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "package").mkdir()
    (tmp_path / "scripts" / "add_book.py").write_text(
        f"def {NAME}(doc_id, slug):\n    '''{NAME} renames'''  # (a docstring is no use)\n",
        encoding="utf-8",
    )
    cases = {
        "cli.py": f"import add_book\nadd_book.{NAME}('id', 'slug')\n",
        "server.py": f"from add_book import {NAME}\n",
        "alias.py": f"from add_book import {NAME} as rename\n",
        "job.py": f"import add_book\nrun = getattr(add_book, '{NAME}')\n",
        "local.py": f"def go({NAME}):\n    return {NAME}('x', 'y')\n",
    }
    for name, source in cases.items():
        (tmp_path / "scripts" / name).write_text(source, encoding="utf-8")
    (tmp_path / "package" / "launch.py").write_text(f"add_book.{NAME}('a', 'b')\n", "utf-8")
    found = callers(tmp_path)
    reported = {entry.split(":")[0] for entry in found}
    assert reported == {f"scripts/{n}" for n in cases} | {"package/launch.py"}, found
    assert not any(entry.startswith("scripts/add_book.py") for entry in found)
