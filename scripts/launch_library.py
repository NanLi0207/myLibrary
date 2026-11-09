"""Choose a library and open it: the development launcher (Start myLibrary Dev.cmd runs it).

    uv run scripts/launch_library.py            # choose: Personal Libraries or Test & Demo
    uv run scripts/launch_library.py --test     # straight to the Test & Demo library
    uv run scripts/launch_library.py --personal "Optics Research"   # a personal library by label

Two levels, as on the library page (📚 切换书库 Switch library):
  1. 选择书库模式 (Choose a Library Mode): 私人书库 (Personal Libraries) or 测试/示例书库
     (Test & Demo Library)
  2. 私人书库 (Personal Libraries): open, create, add an existing one, rename, remove from the
     list, locate a moved one; or back to the modes.

Everything it does is libraries.py's (the page uses the same functions): each library gets its
own server (a running one is reused), and the browser opens it. `library_server.py` and
`library_server.py --library <folder>` still work as before.
"""

import argparse
import sys
import webbrowser
from pathlib import Path

import libraries

LibraryError = libraries.LibraryError


def _ask(prompt: str, read=input) -> str:
    try:
        return read(prompt).strip()
    except EOFError:
        return "q"


def _report(report: dict, say=print) -> None:
    for line in report["errors"]:
        say(f"  ✗ {line}")
    for line in report["warnings"]:
        say(f"  ⚠ {line}")
    if report["ok"]:
        docs = ", ".join(f"{n} {kind}" for kind, n in report["documents"].items())
        say(f"  ✓ {report['name'] or Path(report['path']).name}" + (f" ({docs})" if docs else ""))


def personal_menu(read=input, say=print) -> str | None:
    """Level 2. Returns the address of the library opened, "back", or None (quit)."""
    while True:
        entries = libraries.personal()
        say("\n私人书库 (Personal Libraries)")
        if not entries:
            say("  还没有 (none yet)")
        for n, e in enumerate(entries, 1):
            marks = (" [默认 default]" if e["default"] else "") + (
                "" if e["available"] else f" [找不到 not found: {e['problem']}]"
            )
            say(f"  {n}. {e['label']}{marks}\n      {e['path']}")
        say(
            "  <number> 打开 (open) · n 新建 (create) · a 添加已有 (add existing) · "
            "r 重命名 (rename) · u 移出列表 (remove from list) · l 重新定位 (locate moved) · "
            "b 返回书库模式 (back to modes) · q 退出 (quit)"
        )
        choice = _ask("> ", read).lower()
        try:
            if choice == "q":
                return None
            if choice == "b":
                return "back"
            if choice.isdigit() and 1 <= int(choice) <= len(entries):
                entry = entries[int(choice) - 1]
                say(f"正在打开 (Opening) {entry['label']}…")
                return libraries.open_personal(entry["key"])
            if choice in ("a", "n"):
                folder = _ask("文件夹 (Folder): ", read).strip('"')
                label = _ask("名称 (Label, Enter = folder name): ", read)
                if choice == "n":
                    made = libraries.create(folder, label)
                    say(f"已新建 (Created): {made['label']}")
                    continue
                report = libraries.check(folder)
                _report(report, say)
                if not report["ok"]:
                    continue
                if (
                    _ask("添加？文件夹不会被改动 (Add it? The folder isn't changed) [y/N] ", read)
                    != "y"
                ):
                    continue
                added = libraries.register(folder, label)
                say(f"已添加 (Added): {added['label']}")
                if added["same_id"]:
                    say(
                        "  与这些书库标识相同，是副本或移动后的书库，不会合并 (same library id: a "
                        f"copy or a moved library, never merged): {', '.join(added['same_id'])}"
                    )
            elif choice in ("r", "u", "l"):
                which = _ask("哪一个 (Which number)? ", read)
                if not (which.isdigit() and 1 <= int(which) <= len(entries)):
                    continue
                entry = entries[int(which) - 1]
                if choice == "r":
                    libraries.rename(entry["key"], _ask("新名称 (New label): ", read))
                elif choice == "u":
                    prompt = f"把“{entry['label']}”移出列表？文件夹保持不变 "
                    prompt += "(Remove from the list? The folder stays) [y/N] "
                    if _ask(prompt, read) == "y":
                        libraries.unregister(entry["key"])
                else:
                    folder = _ask("新的文件夹 (Its new folder): ", read).strip('"')
                    libraries.relocate(entry["key"], folder)
        except (LibraryError, OSError) as e:
            say(f"  ✗ {e}")


def test_menu(read=input, say=print) -> str | None:
    """Test & Demo: open it, or reset its working copy."""
    say("\n测试/示例书库 (Test & Demo Library)")
    say(f"  {libraries.TEST_WORKING}")
    say("  o 打开 (open) · reset 重置为初始内容 (reset to the original)")
    say("  b 返回 (back) · q 退出 (quit)")
    choice = _ask("> ", read).lower()
    try:
        if choice == "reset":
            prompt = (
                "这会丢弃测试书库里的所有改动 (This discards every change in the Test & Demo "
                "library). Type RESET: "
            )
            if _ask(prompt, read) == "RESET":
                libraries.reset_test_library()
                say(f"已重置 (Reset); the previous copy is in {libraries.TEST_PREVIOUS}")
            return "back"
        if choice == "o":
            say("正在打开 (Opening) 测试/示例书库 (Test & Demo library)…")
            return libraries.open_test()
        return None if choice == "q" else "back"
    except (LibraryError, OSError) as e:
        say(f"  ✗ {e}")
        return "back"


def choose(read=input, say=print) -> str | None:
    """Level 1, then level 2: the address of the library chosen, or None."""
    while True:
        say("\n选择书库模式 (Choose a Library Mode)")
        say("  1. 私人书库 (Personal Libraries)")
        say("  2. 测试/示例书库 (Test & Demo Library)")
        say("  q. 退出 (Quit)")
        choice = _ask("> ", read).lower()
        if choice == "q":
            return None
        result = (
            personal_menu(read, say)
            if choice == "1"
            else test_menu(read, say)
            if choice == "2"
            else "back"
        )
        if result != "back":
            return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--test", action="store_true", help="open the Test & Demo library")
    group.add_argument("--personal", metavar="LABEL", help="open a personal library by label")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Chinese in a cmd window
    try:
        if args.test:
            url = libraries.open_test()
        elif args.personal:
            found = [e for e in libraries.personal() if e["label"] == args.personal]
            if len(found) != 1:
                sys.exit(
                    f"{len(found)} personal libraries are labelled “{args.personal}”: "
                    "choose one from the menu instead"
                )
            url = libraries.open_personal(found[0]["key"])
        else:
            url = choose()
    except LibraryError as e:
        sys.exit(f"✗ {e}")
    if not url:
        return
    print(f"myLibrary: {url}")
    if not args.no_browser:
        webbrowser.open(url)


if __name__ == "__main__":
    main()
