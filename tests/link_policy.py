"""The mandatory link-test rule for the S3 settings tests (the project's convention, as in
test_topic_notes.link_or_skip): making a symbolic link may need Developer Mode or a privilege.
Locally, only that recognised limitation skips a test (Windows: ERROR_PRIVILEGE_NOT_HELD);
any other failure to make the link (a missing folder, a bad argument, anything unexpected) is
raised as it is. In CI, MYLIBRARY_REQUIRE_LINK_TESTS=1 says the link tests must run, so any
failure to make the link fails the test. Only making the link is covered: anything the test
checks after it fails as usual."""

import os

import pytest

PRIVILEGE_NOT_HELD = 1314  # (Windows: symbolic links need Developer Mode or the privilege)


def require_links() -> bool:
    return os.environ.get("MYLIBRARY_REQUIRE_LINK_TESTS") == "1"


def _privilege_missing(error: OSError) -> bool:
    return os.name == "nt" and getattr(error, "winerror", None) == PRIVILEGE_NOT_HELD


def symlink_or_skip(target, link) -> None:
    """os.symlink(target, link); skipped only where symbolic links need a privilege this
    account lacks, and never when MYLIBRARY_REQUIRE_LINK_TESTS=1 (then: failed)."""
    try:
        if not os.path.isdir(os.path.dirname(os.path.abspath(link))):
            # (checked first, so a missing folder is never reported as a missing privilege)
            raise FileNotFoundError(2, "the link's folder doesn't exist", str(link))
        os.symlink(target, link)
    except OSError as e:
        if require_links():
            pytest.fail(
                f"MYLIBRARY_REQUIRE_LINK_TESTS=1, but the symbolic link couldn't be made ({e}): "
                "this link test must run",
                pytrace=False,
            )
        if _privilege_missing(e):
            pytest.skip(f"this system doesn't allow creating a symbolic link here ({e})")
        raise
