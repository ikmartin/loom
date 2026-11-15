"""Whether the git program can be run: on a Mac with no developer tools `/usr/bin/git` is Apple's stub, and running it opens a dialog offering to install them.

Every place loom runs git asks `usable` first and treats a stub as git being absent.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from functools import lru_cache


def apple_stub(path: str) -> bool:
    """Whether `path` is macOS's `/usr/bin/git` while no developer tools are installed, which `xcode-select -p` says without opening anything."""
    if sys.platform != "darwin" or os.path.realpath(path) != "/usr/bin/git":
        return False
    try:
        return subprocess.run(["/usr/bin/xcode-select", "-p"], capture_output=True, timeout=10).returncode != 0
    except (OSError, subprocess.SubprocessError):
        return False


@lru_cache(maxsize=8)
def _usable(path: str | None) -> bool:
    return path is not None and not apple_stub(path)


def usable() -> bool:
    """Whether a real git is on the path: found, and not Apple's stub."""
    return _usable(shutil.which("git"))
