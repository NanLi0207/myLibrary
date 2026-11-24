"""Lossless edits of the settings file (M7.1 S3, B43): change only the settings asked for.

paths.update_settings hands this module the settings file's bytes and the settings to change;
it returns the new bytes, or None when nothing would change. It never reads or writes files.

What it guarantees (checked before anything is returned, else SettingsNotWritable):
- only the value of each changed setting is replaced, or one new `key = value` line inserted;
  every other byte stays as it was: comments, spacing, quoting, line endings, a missing final
  newline, settings this version doesn't know of any TOML type, tables;
- a setting counts only as a plain key of the top-level table (before the first [table]
  header); anything else about a changed setting (a dotted key, a table, a multi-line or
  number value, a key spelled with escapes) is refused, never guessed at;
- a stored value of the wrong type (backup_pdfs = 1) is never "repaired" (D4): refused;
- the result parses, holds exactly the new values, and every other value is the same in type
  and value (True is not 1) as before.
Each replacement is also checked against an independent whole-line grammar (_LINE_RE), so a
wrong span found by the scanner can't eat a comment, spaces or the line ending.
"""

import math
import re
import tomllib
from datetime import datetime, time

HEADER = "# myLibrary settings (see scripts/paths.py)"


class SettingsDamaged(ValueError):
    """The settings file can't be read as settings (not UTF-8, or not valid TOML)."""


class SettingsNotUTF8(SettingsDamaged):
    pass


class SettingsSyntax(SettingsDamaged):
    pass


class SettingsNotWritable(ValueError):
    """A save that can't be made without changing something else, or without guessing."""


def parse(data: bytes, name: str) -> dict:
    """The settings in `data` (the file `name`, for messages)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise SettingsNotUTF8(
            f"The settings file {name} isn't UTF-8 text (byte {e.start}). Fix it in a text editor "
            "(or delete it to start with the default settings)."
        ) from None
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise SettingsSyntax(
            f"The settings file {name} can't be read ({e}). Fix that line in a text editor "
            "(or delete the file to start with the default settings)."
        ) from None


def same(a, b) -> bool:
    """Equal and of the same type, all the way down (True != 1, 1 != 1.0, nan == nan)."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, float):
        return repr(a) == repr(b) or (math.isnan(a) and math.isnan(b))
    if isinstance(a, datetime | time):
        return a == b and a.utcoffset() == b.utcoffset()
    return a == b


# --- values the way paths has always written them ---------------------------------------------

_TOML_ESCAPES = {"\\": "\\\\", '"': '\\"', "\b": "\\b", "\t": "\\t", "\n": "\\n", "\f": "\\f",
                 "\r": "\\r"}  # fmt: skip


def value_text(value) -> str:
    """A setting's value as TOML: true/false, a literal string when possible (backslashes in
    Windows paths stay as they are), else a basic string with everything escaped that a TOML
    reader would refuse, so the file always stays readable."""
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    control = any(ord(c) < 0x20 or ord(c) == 0x7F for c in text)
    if "'" not in text and not control:
        return f"'{text}'"
    escaped = "".join(
        _TOML_ESCAPES.get(c) or (f"\\u{ord(c):04X}" if ord(c) < 0x20 or ord(c) == 0x7F else c)
        for c in text
    )
    return f'"{escaped}"'


# --- the independent line check ----------------------------------------------------------------

_BASIC = r'"(?:[^"\\\x00-\x08\x0a-\x1f\x7f]|\\(?:[btnfr"\\]|u[0-9A-Fa-f]{4}|U[0-9A-Fa-f]{8}))*"'
_LITERAL = r"'[^'\x00-\x08\x0a-\x1f\x7f]*'"
VALUE_RE = re.compile(rf"(?:{_BASIC}|{_LITERAL}|true|false)")


def _line_re(key: str) -> re.Pattern:
    k = re.escape(key)
    return re.compile(
        rf"(?P<lead>[ \t]*)(?P<key>{k}|\"{k}\"|'{k}')(?P<ws0>[ \t]*)=(?P<ws1>[ \t]*)"
        rf"(?P<value>{VALUE_RE.pattern})(?P<trail>[ \t]*)(?P<comment>#[^\r\n]*)?"
        r"(?P<eol>\r\n|\n|)"
    )


def _physical_line(text: str, at: int) -> tuple[int, int]:
    """(start, end) of the physical line holding `at`, its line ending included."""
    start = text.rfind("\n", 0, at) + 1
    newline = text.find("\n", at)
    return start, (len(text) if newline < 0 else newline + 1)


def _check_replacement(text: str, key: str, start: int, end: int, new: str) -> str:
    """The text with [start, end) replaced by `new`, after proving that [start, end) is exactly
    the value of a `key = value` line, and that only it changes."""
    if not VALUE_RE.fullmatch(new):
        raise SettingsNotWritable(f"{key}: {new!r} isn't a single TOML value")
    line_start, line_end = _physical_line(text, start)
    line = text[line_start:line_end]
    pattern = _line_re(key)
    old = pattern.fullmatch(line)
    if not old or old.start("value") + line_start != start or old.end("value") + line_start != end:
        raise SettingsNotWritable(f"{key}: the value to replace isn't exactly one value")
    new_line = line[: old.start("value")] + new + line[old.end("value") :]
    again = pattern.fullmatch(new_line)
    parts = ("lead", "key", "ws0", "ws1", "trail", "comment", "eol")
    if not again or any(again.group(p) != old.group(p) for p in parts):
        raise SettingsNotWritable(f"{key}: the rest of its line wouldn't stay as it is")
    return text[:start] + new + text[end:]


# --- following the file's structure -------------------------------------------------------------


class _Unfollowable(Exception):
    """The scanner met something it doesn't follow (valid TOML it can't handle): refuse."""


_BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_TIME_AFTER_SPACE = re.compile(r" \d{2}:\d{2}")


class _Scan:
    """Where things are, for the top-level table: each `key = value` line before the first
    table header, the first header, and every key path that names a table or a dotted key."""

    def __init__(self, text: str):
        self.text = text
        self.n = len(text)
        self.entries: list[dict] = []  # root key/value lines (before the first header)
        self.first_header: int | None = None  # start of the first header's physical line
        self.first_segments: set[str] = set()  # first segment of every dotted key and header
        self._scan()

    # characters
    def _ws(self, i: int) -> int:
        while i < self.n and self.text[i] in " \t":
            i += 1
        return i

    def _eol(self, i: int) -> int:
        """After optional spaces and a comment, the index after the line ending (or the end)."""
        i = self._ws(i)
        if i < self.n and self.text[i] == "#":
            while i < self.n and self.text[i] not in "\r\n":
                i += 1
        if i < self.n and self.text[i] == "\r":
            i += 1
        if i < self.n and self.text[i] == "\n":
            return i + 1
        if i >= self.n:
            return i
        raise _Unfollowable(f"unexpected {self.text[i]!r} at {i}")

    def _blank(self, i: int) -> int:
        """Spaces, newlines and comments (inside arrays)."""
        while i < self.n:
            c = self.text[i]
            if c in " \t\r\n":
                i += 1
            elif c == "#":
                while i < self.n and self.text[i] not in "\r\n":
                    i += 1
            else:
                break
        return i

    # keys
    def _key_segment(self, i: int) -> tuple[str, bool, int]:
        """(segment, spelled with an escape, index after it)."""
        c = self.text[i] if i < self.n else ""
        if c == '"':
            j, escaped = i + 1, False
            while j < self.n and self.text[j] != '"':
                if self.text[j] == "\\":
                    escaped = True
                    j += 1
                j += 1
            return self.text[i + 1 : j], escaped, j + 1
        if c == "'":
            j = self.text.find("'", i + 1)
            if j < 0:
                raise _Unfollowable("unclosed key")
            return self.text[i + 1 : j], False, j + 1
        m = _BARE_KEY.match(self.text, i)
        if not m:
            raise _Unfollowable(f"no key at {i}")
        return m.group(), False, m.end()

    def _key(self, i: int) -> tuple[list[tuple[str, bool]], int]:
        segments = []
        while True:
            seg, escaped, i = self._key_segment(self._ws(i))
            segments.append((seg, escaped))
            j = self._ws(i)
            if j < self.n and self.text[j] == ".":
                i = j + 1
                continue
            return segments, j

    # values
    def _string_end(self, i: int) -> int:
        t = self.text
        if t.startswith('"""', i) or t.startswith("'''", i):
            quote, basic, j = t[i], t[i] == '"', i + 3
            while j < self.n:
                if basic and t[j] == "\\":
                    j += 2
                    continue
                if t.startswith(quote * 3, j):
                    run = 3
                    while run < 5 and j + run < self.n and t[j + run] == quote:
                        run += 1
                    return j + run
                j += 1
            raise _Unfollowable("unclosed multi-line string")
        quote, j = t[i], i + 1
        while j < self.n and t[j] != quote:
            if t[j] in "\r\n":
                raise _Unfollowable("newline in a string")
            if quote == '"' and t[j] == "\\":
                j += 1
            j += 1
        if j >= self.n:
            raise _Unfollowable("unclosed string")
        return j + 1

    def _value_end(self, i: int) -> int:
        t = self.text
        c = t[i] if i < self.n else ""
        if c in "\"'":
            return self._string_end(i)
        if c == "[":
            j = self._blank(i + 1)
            while j < self.n and t[j] != "]":
                j = self._blank(self._value_end(j))
                if j < self.n and t[j] == ",":
                    j = self._blank(j + 1)
            if j >= self.n:
                raise _Unfollowable("unclosed array")
            return j + 1
        if c == "{":
            j = self._ws(i + 1)
            while j < self.n and t[j] != "}":
                _, j = self._key(j)
                if j >= self.n or t[j] != "=":
                    raise _Unfollowable("no = in an inline table")
                j = self._ws(self._value_end(self._ws(j + 1)))
                if j < self.n and t[j] == ",":
                    j = self._ws(j + 1)
            if j >= self.n:
                raise _Unfollowable("unclosed inline table")
            return j + 1
        j = i
        while j < self.n and t[j] not in " \t\r\n,]}#":
            j += 1
        if j == i:
            raise _Unfollowable(f"no value at {i}")
        if _DATE.fullmatch(t, i, i + 10) and j == i + 10 and _TIME_AFTER_SPACE.match(t, j):
            j += 1  # a date and a time separated by a space: one value
            while j < self.n and t[j] not in " \t\r\n,]}#":
                j += 1
        return j

    def _scan(self) -> None:
        i = 0
        while i < self.n:
            line_start = i
            j = self._ws(i)
            if j >= self.n:
                break
            c = self.text[j]
            if c in "\r\n#":
                i = self._eol(j)
                continue
            if c == "[":
                if self.first_header is None:
                    self.first_header = line_start
                k = j + (2 if self.text.startswith("[[", j) else 1)
                segments, k = self._key(k)
                self.first_segments.add(segments[0][0])
                if not self.text.startswith("]", k):
                    raise _Unfollowable("unclosed table header")
                k += 2 if self.text.startswith("]]", k) else 1
                i = self._eol(k)
                continue
            segments, k = self._key(j)
            if k >= self.n or self.text[k] != "=":
                raise _Unfollowable(f"no = after a key at {j}")
            value_start = self._ws(k + 1)
            value_end = self._value_end(value_start)
            i = self._eol(value_end)
            if self.first_header is None:
                if len(segments) > 1:  # (a dotted key inside a [table] is that table's)
                    self.first_segments.add(segments[0][0])
                self.entries.append(
                    {"segments": segments, "start": value_start, "end": value_end, "after": i}
                )


# --- the edit ----------------------------------------------------------------------------------


def _newline(text: str, default: str) -> str:
    at = text.find("\n")
    if at < 0:
        return default
    return "\r\n" if at > 0 and text[at - 1] == "\r" else "\n"


def _edit_one(text: str, key: str, value, name: str, default_newline: str) -> str:
    try:
        scan = _Scan(text)
    except _Unfollowable as e:
        raise SettingsNotWritable(
            f"Couldn't follow the structure of the settings file {name} ({e}), so {key} "
            "wasn't saved. Check the file in a text editor."
        ) from None
    if key in scan.first_segments:
        raise SettingsNotWritable(
            f"{key} in the settings file {name} is written as a table or a dotted key; change "
            "it there by hand (a plain `key = value` line near the top)."
        )
    found = [e for e in scan.entries if [s for s, _ in e["segments"]] == [key]]
    new = value_text(value)
    if found:
        entry = found[0]
        if len(found) > 1 or any(escaped for _, escaped in entry["segments"]):
            raise SettingsNotWritable(f"{key} in the settings file {name}: change it by hand.")
        old_value = text[entry["start"] : entry["end"]]
        if not VALUE_RE.fullmatch(old_value):
            raise SettingsNotWritable(
                f"{key} in the settings file {name} is written in a form this version doesn't "
                "change (e.g. a multi-line string); change it there by hand."
            )
        return _check_replacement(text, key, entry["start"], entry["end"], new)
    # a new line: after the last top-level setting, else before the first table, else at the end
    nl = _newline(text, default_newline)
    line = f"{key} = {new}"
    if scan.entries:
        at = scan.entries[-1]["after"]
        if at == len(text) and not text.endswith("\n"):
            segment = nl + line  # (no final newline before: none after either)
        else:
            segment = line + nl
    elif scan.first_header is not None:
        at, segment = scan.first_header, line + nl
    else:
        at = len(text)
        segment = line + nl if (not text or text.endswith("\n")) else nl + line
    result = text[:at] + segment + text[at:]
    if result[:at] != text[:at] or result[at + len(segment) :] != text[at:]:
        raise SettingsNotWritable(f"{key}: the insertion would change other text")  # (can't)
    return result


def edit(
    old: bytes | None, updates: dict, *, types: dict, name: str, default_newline: str
) -> bytes | None:
    """The settings file's new bytes with `updates` applied, or None if nothing changes.
    `types`: each setting's one accepted type (bool or str). `old` None: no file yet."""
    if not updates:
        return None
    if old is None:
        lines = [HEADER] + [f"{k} = {value_text(v)}" for k, v in updates.items()]
        text = default_newline.join(lines) + default_newline
        if not all(same(tomllib.loads(text).get(k), v) for k, v in updates.items()):
            raise SettingsNotWritable("the new settings file wouldn't read back as written")
        return text.encode("utf-8")
    before = parse(old, name)
    for key in updates:
        if key in before and type(before[key]) is not types[key]:
            kind = "true or false" if types[key] is bool else "text in quotes"
            raise SettingsNotWritable(
                f"{key} in the settings file {name} is {before[key]!r}, which isn't "
                f"{kind}; correct it by hand in a text editor, then save again."
            )
    if all(k in before and same(before[k], v) for k, v in updates.items()):
        return None
    text = old.decode("utf-8")
    for key, value in updates.items():
        if key in before and same(before[key], value):
            continue
        text = _edit_one(text, key, value, name, default_newline)
    _verify(before, text, updates, name)
    return text.encode("utf-8")


def _verify(before: dict, text: str, updates: dict, name: str) -> None:
    try:
        after = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise SettingsNotWritable(f"saving would make {name} unreadable ({e})") from None
    for key, value in updates.items():
        if not same(after.get(key), value):
            raise SettingsNotWritable(f"saving {key} in {name} wouldn't read back as written")
    if after.keys() != before.keys() | updates.keys():
        raise SettingsNotWritable(f"saving would add or remove other settings in {name}")
    for key in before.keys() - updates.keys():
        if not same(after[key], before[key]):
            raise SettingsNotWritable(f"saving would change {key} in {name}")
