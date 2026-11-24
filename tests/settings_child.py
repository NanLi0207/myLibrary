"""A separate process saving settings, for the cross-process tests of the settings transaction
(tests/test_settings_transaction.py). Run with MYLIBRARY_SETTINGS and MYLIBRARY_LIBRARY set to
temporary places. It speaks one line at a time on stdout:

  contended:<thread|os>   a lock was found taken; this process waits for it (the handshake)
  held                    both locks held (hold / lock), waiting for "release" on stdin
  done <json>             the save returned (all settings)
  error <Class> <msg>     the save raised

usage: settings_child.py save|hold <key> <json value> [lock wait]
       settings_child.py lock [lock wait]      (only take the locks, until "release")
"""

import json
import sys

import paths


def _say(line: str) -> None:
    print(line, flush=True)


def _wait_for_release() -> None:
    _say("held")
    if sys.stdin.readline().strip() != "release":
        raise SystemExit("expected release")


def main() -> None:
    action = sys.argv[1]
    paths._on_lock_contended = lambda kind: _say(f"contended:{kind}")
    wait_at = 4 if action != "lock" else 2
    if len(sys.argv) > wait_at:
        paths.SETTINGS_LOCK_WAIT = float(sys.argv[wait_at])
    try:
        if action == "lock":
            with paths._settings_locks():
                _wait_for_release()
            _say("done {}")
            return
        key, value = sys.argv[2], json.loads(sys.argv[3])
        if action == "hold":
            paths._on_before_publish = _wait_for_release
        result = paths.save_settings({key: value})
        _say("done " + json.dumps(result))
    except Exception as e:
        _say(f"error {type(e).__name__} {str(e).splitlines()[0] if str(e) else ''}")


if __name__ == "__main__":
    main()
