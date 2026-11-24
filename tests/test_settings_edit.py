"""M7.1 S3, B43: saving a setting changes only that setting's value in the settings file.
Comments, spacing, line endings, unknown settings of every TOML type and tables stay byte for
byte; what can't be changed that way is refused with the file untouched; a wrong stored type
is never "repaired" (D4). T-E1..E14 of the S3 plan; temporary settings files only."""

import os
import random
import tomllib
from datetime import UTC, date, datetime, time, timedelta, timezone

import paths
import pytest
import settings_toml
from settings_toml import SettingsNotWritable, edit, same

NL = os.linesep  # (a new line in a file that has no line ending yet)


NL = os.linesep  # (a new line in a file that has no line ending yet)


@pytest.fixture
def settings(tmp_path, monkeypatch):
    file = tmp_path / "settings.toml"
    file.write_bytes(b"")
    monkeypatch.setattr(paths, "SETTINGS_FILE", file)
    monkeypatch.setattr(paths, "SETTINGS_SOURCE", "explicit", raising=False)
    return file


def save(file, text: str | bytes, updates: dict) -> bytes:
    """Write `text`, save `updates` through paths.save_settings, return the file's bytes."""
    file.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)
    paths.save_settings(updates)
    return file.read_bytes()


def unchanged_by(file, text: str, updates: dict, error=SettingsNotWritable, match=None):
    """The save is refused and the file keeps its bytes and its time."""
    file.write_bytes(text.encode("utf-8"))
    before = file.stat().st_mtime_ns
    with pytest.raises(error, match=match):
        paths.save_settings(updates)
    assert file.read_bytes() == text.encode("utf-8") and file.stat().st_mtime_ns == before
    assert not [p for p in file.parent.iterdir() if p.name.endswith(".tmp")]


def test_a_value_and_only_the_value_changes(settings):
    """T-E1: the plan's example, and spacing, quoted keys, comments, Unicode and escapes."""
    text = "editor = 'system'  # keep this explanation\n"
    assert save(settings, text, {"editor": "notepad"}) == (
        b"editor = 'notepad'  # keep this explanation\n"
    )
    text = (
        "# my settings, 我的设置 (my settings)\n"
        "\n"
        '  "editor"   =\t"vscode"\t# 编辑器 (editor)\n'
        "editor_command = 'code \"{file}\"' # quoted\n"
        "'backup_folder' = \"D:\\\\Backups\\\\ü\" \n"
    )
    after = save(settings, text, {"editor": "custom", "backup_folder": "E:/备份 (backup)"})
    assert after.decode("utf-8") == text.replace('"vscode"', "'custom'").replace(
        '"D:\\\\Backups\\\\ü"', "'E:/备份 (backup)'"
    )
    assert tomllib.loads(after.decode("utf-8"))["editor_command"] == 'code "{file}"'


def test_a_wrong_span_is_caught_by_the_line_check(settings, monkeypatch):
    """T-E1b: the line check doesn't trust the scanner: a span that takes the comment, the
    spaces before it, or the line ending is refused, and the file stays as it was."""
    text = "editor = 'system'  # keep this explanation\n"
    start = text.index("'system'")
    value_end = start + len("'system'")
    for end in (value_end + 2, len(text) - 1, len(text), value_end - 1):
        with pytest.raises(SettingsNotWritable):
            settings_toml._check_replacement(text, "editor", start, end, "'notepad'")
    assert settings_toml._check_replacement(text, "editor", start, value_end, "'n'") == (
        "editor = 'n'  # keep this explanation\n"
    )

    class WrongScan(settings_toml._Scan):  # (a scanner that ends the value at the line's end)
        def _scan(self):
            super()._scan()
            for entry in self.entries:
                entry["end"] = self.text.find("\n", entry["start"])

    monkeypatch.setattr(settings_toml, "_Scan", WrongScan)
    unchanged_by(settings, text, {"editor": "notepad"})


ALL_TYPES = """\
# every TOML type this version doesn't know of, kept as it is
count = 3
ratio = 1.5
small = -0.0
huge = 1e3
odd = nan
flag = false
hex = 0xFF
when = 2026-11-23
stamp = 1979-05-27 07:32:00-08:00
local = 1979-05-27T07:32:00
noon = 12:00:00
recent = ["a", 'b', 3]
nested = [
  [1, 2], # pairs
  {x = 1, y = "two"},
]
point = {x = 1, y = 2.0, "z" = true}
site."google.com" = true
editor = 'system'

[window]
width = 900
editor = "not the setting: a [window] key"

[[recent_files]]
path = 'C:\\notes\\a.md'
[[recent_files]]
path = "b.md"
"""


def test_settings_of_every_type_survive_byte_for_byte(settings):
    """T-E2: unknown settings of every TOML type, tables and arrays of tables: their bytes and
    their types and values (True is not 1) stay; only editor's value changes."""
    before = tomllib.loads(ALL_TYPES)
    after_bytes = save(settings, ALL_TYPES, {"editor": "notepad", "backup_pdfs": True})
    after_text = after_bytes.decode("utf-8")
    assert after_text.replace(
        "editor = 'notepad'\nbackup_pdfs = true\n", "editor = 'system'\n"
    ) == (ALL_TYPES)
    after = tomllib.loads(after_text)
    for key in before.keys() - {"editor"}:
        assert same(after[key], before[key]), key
    assert type(after["count"]) is int and type(after["flag"]) is bool
    assert after["window"]["editor"] == "not the setting: a [window] key"


def test_comment_marks_inside_strings_are_not_comments(settings):
    """T-E3."""
    text = "editor_command = \"code '#{file}'\" # the real comment\neditor = '#custom'\n"
    after = save(settings, text, {"editor": "custom"})
    assert after.decode() == text.replace("'#custom'", "'custom'")
    assert tomllib.loads(after.decode())["editor_command"] == "code '#{file}'"


def test_what_looks_like_settings_inside_multiline_strings_is_left_alone(settings):
    """T-E4: a key line and a [table] line inside multi-line strings aren't settings."""
    text = (
        'notes = """\neditor = \'vscode\'\n[fake]\n"""\n'
        "more = '''\nbackup_pdfs = true\n'''\n"
        'tricky = """ends with quotes"" """\n'
    )
    after = save(settings, text, {"editor": "notepad", "backup_pdfs": False}).decode()
    assert after == text + "editor = 'notepad'\nbackup_pdfs = false\n"
    parsed = tomllib.loads(after)
    assert parsed["notes"] == "editor = 'vscode'\n[fake]\n" and parsed["backup_pdfs"] is False


def test_a_setting_name_inside_a_table_is_not_the_setting(settings):
    """T-E5: `editor` under [ui] belongs to [ui]: the setting is added at the top level, before
    the first table, and [ui] keeps its own."""
    text = "[ui]\neditor = 'x'\n"
    after = save(settings, text, {"editor": "system"}).decode()
    assert after == "editor = 'system'\n[ui]\neditor = 'x'\n"
    assert tomllib.loads(after)["ui"] == {"editor": "x"}


def test_line_endings_are_kept(settings):
    """T-E6: CRLF stays CRLF, LF stays LF; a mixed file: the first line's ending for a new
    line, every other line as it was."""
    crlf = "# c\r\neditor = 'vscode'\r\n"
    assert save(settings, crlf, {"editor": "system", "backup_pdfs": True}) == (
        b"# c\r\neditor = 'system'\r\nbackup_pdfs = true\r\n"
    )
    lf = "editor = 'vscode'\n"
    assert save(settings, lf, {"backup_pdfs": True}) == b"editor = 'vscode'\nbackup_pdfs = true\n"
    mixed = "a = 1\r\nb = 2\n"
    assert save(settings, mixed, {"editor": "system"}) == b"a = 1\r\nb = 2\neditor = 'system'\r\n"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # after the last top-level setting (before comments that follow it)
        ("a = 1\n# end\n", "a = 1\neditor = 'system'\n# end\n"),
        # no final newline after a setting: one before the new line, none after it
        ("a = 1", f"a = 1{NL}editor = 'system'"),  # (no line ending to copy: the system's)
        ("a = 1\r\n# no newline", "a = 1\r\neditor = 'system'\r\n# no newline"),
        # only a comment, no final newline
        ("# only a comment", f"# only a comment{NL}editor = 'system'"),
        # before the first table, when there's no top-level setting
        ("# top\n[ui]\nx = 1\n", "# top\neditor = 'system'\n[ui]\nx = 1\n"),
        # a file that begins with a table: at its very start
        ("[ui]\nx = 1", "editor = 'system'\n[ui]\nx = 1"),
        ("  [ui]\nx = 1\n", "editor = 'system'\n  [ui]\nx = 1\n"),
        # after a top-level setting that spans lines
        ("list = [\n  1,\n]\n[t]\n", "list = [\n  1,\n]\neditor = 'system'\n[t]\n"),
        # an empty file
        ("", f"editor = 'system'{NL}"),
    ],
)
def test_where_a_new_setting_goes(settings, text, expected):
    """T-E7: insertions add one line; everything else stays where and as it was."""
    assert save(settings, text, {"editor": "system"}).decode("utf-8") == expected


@pytest.mark.parametrize(
    ("text", "updates"),
    [
        ("editor.x = 1\n", {"editor": "system"}),
        ("[editor]\nx = 1\n", {"editor": "system"}),
        ("[[editor]]\nx = 1\n", {"editor": "system"}),
        ('editor = """multi\nline"""\n', {"editor": "system"}),
        ("editor = '''raw'''\n", {"editor": "system"}),
        ("editor = 3\n", {"editor": "system"}),
        ('"edit\\u006fr" = "vscode"\n', {"editor": "system"}),
        ("backup_pdfs = 1\n", {"backup_pdfs": False}),  # D4: never repaired
        ("backup_pdfs = 'true'\n", {"backup_pdfs": True}),
        ("editor = true\n", {"editor": "system"}),
        ("editor = ['a']\n", {"editor": "system"}),
        ("editor = {x = 1}\n", {"editor": "system"}),
    ],
)
def test_what_cant_be_changed_losslessly_is_refused(settings, text, updates):
    """T-E8: a changed setting in a shape this version doesn't edit, or of the wrong type
    (D4): refused, the file's bytes and time unchanged, no temporary file left."""
    unchanged_by(settings, text, updates)


def test_a_save_that_changes_nothing_writes_nothing(settings, tmp_path, monkeypatch):
    """T-E9: the same values, or nothing to save: no write at all (bytes and time), and no
    file created where none was."""
    text = "# keep\neditor = 'notepad'\nbackup_pdfs = true\n"
    settings.write_text(text, encoding="utf-8")
    before = settings.stat().st_mtime_ns
    paths.save_settings({"editor": "notepad", "backup_pdfs": True})
    paths.save_settings({})
    assert settings.read_text(encoding="utf-8") == text and settings.stat().st_mtime_ns == before
    usual = tmp_path / "local.toml"
    monkeypatch.setattr(paths, "SETTINGS_FILE", usual)
    monkeypatch.setattr(paths, "SETTINGS_SOURCE", "default", raising=False)
    paths.save_settings({})
    assert not usual.exists()


def test_a_stored_value_of_the_wrong_type_is_refused_not_repaired(settings):
    """T-E10 (D4): backup_pdfs = 1 or "true" isn't turned into true: changing backup_pdfs is
    refused with a message to correct it by hand; changing another setting works and leaves
    the wrong value exactly as it was."""
    for stored in ("1", "'true'", '"true"'):
        text = f"backup_pdfs = {stored}  # by hand\neditor = 'vscode'\n"
        unchanged_by(settings, text, {"backup_pdfs": True}, match="correct it by hand")
        after = save(settings, text, {"editor": "notepad"}).decode()
        assert after == text.replace("'vscode'", "'notepad'")


def test_the_final_check_refuses_an_edit_that_changes_anything_else(settings, monkeypatch):
    """T-E11: the parse-and-compare check is independent of how the edit was made: an edit
    that also changes another value, or lands inside a multi-line string, is refused."""
    real = settings_toml._edit_one

    def changes_another(text, key, value, name, newline):
        return real(text, key, value, name, newline).replace("count = 3", "count = 4")

    monkeypatch.setattr(settings_toml, "_edit_one", changes_another)
    unchanged_by(settings, "count = 3\neditor = 'vscode'\n", {"editor": "system"})

    def into_a_string(text, key, value, name, newline):
        at = text.index('"""') + 4
        return text[:at] + f"{key} = 'x'\n" + text[at:]

    monkeypatch.setattr(settings_toml, "_edit_one", into_a_string)
    unchanged_by(settings, 'notes = """\nline\n"""\n', {"editor": "system"})


def test_a_new_settings_file_is_written_as_before(tmp_path, monkeypatch):
    """T-E12: no file yet (the usual one, a first start): the header and the settings."""
    usual = tmp_path / "local.toml"
    monkeypatch.setattr(paths, "SETTINGS_FILE", usual)
    monkeypatch.setattr(paths, "SETTINGS_SOURCE", "default", raising=False)
    paths.save_settings({"library": "D:/My Library", "python_features": False})
    text = usual.read_bytes().decode()
    nl = "\r\n" if "\r\n" in text else "\n"
    assert text == nl.join(
        [settings_toml.HEADER, "library = 'D:/My Library'", "python_features = false", ""]
    )


def test_a_file_written_by_the_previous_version_is_updated_losslessly(settings):
    """T-E13: e28bf18 wrote a header, literal strings and CRLF; it is updated in place."""
    old = (
        "# myLibrary settings (see scripts/paths.py)\r\n"
        "library = 'C:/Users/me/Documents/myLibrary Library'\r\n"
        "editor = 'vscode'\r\n"
        "editor_command = 'code \"{file}\"'\r\n"
        "python_features = true\r\n"
        "backup_folder = 'D:\\Backups'\r\n"
        "backup_pdfs = false\r\n"
        "openalex_key = ''\r\n"
    )
    after = save(settings, old, {"backup_pdfs": True, "openalex_key": "abc12345"})
    assert after.decode() == old.replace("backup_pdfs = false", "backup_pdfs = true").replace(
        "openalex_key = ''", "openalex_key = 'abc12345'"
    )
    assert tomllib.loads(after.decode())["backup_folder"] == "D:\\Backups"


FRAGMENTS = [
    "# a comment\n", "\n", "count = 3\n", "ratio = 2.5 # half\n", 'name = "x # y"\n',
    "flag = true\n", "when = 2026-11-23\n", "list = [1, 2]\n", "multi = [\n  'a',\n]\n",
    'text = """\neditor = 1\n"""\n', "editor = 'vscode'\n", "editor = 'vscode'  # c\n",
    "backup_pdfs = false\n", "backup_pdfs = 1\n", "\"editor_command\" = 'code {file}'\n",
    "editor.sub = 1\n", "inline = {a = 1}\n",
]  # fmt: skip
TABLES = ["", "[ui]\nwidth = 900\n", "[ui]\neditor = 'x'\n[[r]]\np = 1\n"]
VALUES = {
    "editor": ["system", "notepad"], "backup_pdfs": [True, False],
    "editor_command": ["code {file}", "it's \"quoted\"", ""], "library": ["D:/L", "C:\\x y"],
}  # fmt: skip


def test_generated_files_are_either_refused_untouched_or_edited_exactly(settings):
    """T-E14: many generated files and updates: every save is either refused with the file
    untouched, or gives a file that holds the new values, every other value the same, and
    every other line of the old file still there in order."""
    rng = random.Random(20261123)
    saved = refused = 0
    for _ in range(300):
        lines = rng.sample(FRAGMENTS, rng.randint(0, 6))
        text = "".join(lines) + rng.choice(TABLES)
        if rng.random() < 0.3:
            text = text.replace("\n", "\r\n")
        if rng.random() < 0.2:
            text = text.rstrip("\r\n")
        try:
            before = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            continue  # (a combination that isn't TOML: duplicate keys)
        keys = rng.sample(sorted(VALUES), rng.randint(1, 3))
        updates = {k: rng.choice(VALUES[k]) for k in keys}
        settings.write_bytes(text.encode())
        try:
            paths.save_settings(updates)
        except SettingsNotWritable:
            refused += 1
            assert settings.read_bytes() == text.encode()
            continue
        saved += 1
        after_text = settings.read_bytes().decode()
        after = tomllib.loads(after_text)
        for key, value in updates.items():
            assert same(after[key], value)
        for key in before.keys() - updates.keys():
            assert same(after[key], before[key])
        old_lines = [ln for ln in text.splitlines(keepends=True) if not _sets(ln, updates)]
        remaining = iter(after_text.splitlines(keepends=True))
        for line in old_lines:  # (every untouched old line, in order, byte for byte)
            assert any(line == candidate for candidate in remaining) or (
                line == text.splitlines(keepends=True)[-1] and not line.endswith("\n")
            ), line
    assert saved > 50 and refused > 10  # (both kinds really happened)


def _sets(line: str, updates: dict) -> bool:
    stripped = line.lstrip().lstrip("\"'")
    return any(stripped.startswith(k) for k in updates)


def test_same_tells_types_apart():
    """The comparison the checks rely on: True is not 1, 1 is not 1.0, nan is nan."""
    assert (
        same(1, 1) and not same(True, 1) and not same(1, 1.0) and same(float("nan"), float("nan"))
    )
    assert not same(0.0, -0.0) and same([1, {"a": True}], [1, {"a": True}])
    assert not same({"a": 1}, {"a": True}) and not same([1], [1, 2])
    tz = timezone(timedelta(hours=-8))
    assert not same(datetime(1979, 5, 27, 7, tzinfo=tz), datetime(1979, 5, 27, 15, tzinfo=UTC))
    assert same(date(2026, 11, 23), date(2026, 11, 23)) and not same(time(12), time(12, 0, 1))


def test_edit_is_pure_and_returns_none_for_no_change():
    types = paths.SETTINGS_TYPES
    assert (
        edit(b"editor = 'a'\n", {"editor": "a"}, types=types, name="s", default_newline="\n")
        is None
    )
    assert edit(None, {}, types=types, name="s", default_newline="\n") is None
    assert edit(b"", {}, types=types, name="s", default_newline="\n") is None
