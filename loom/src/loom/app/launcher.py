"""Loom in the Applications folder: `~/Applications/Loom.app`, which opens loom's home page and starts it first when it is not running.

The bundle holds a shell script, not a program, and loom writes it on the person's machine, so the system never quarantines it and it needs no signature. It names the Python loom was installed with, which an update keeps where it is.
"""

from __future__ import annotations

import plistlib
import shlex
import sys
from pathlib import Path

from loom.version import __version__


def app_path() -> Path:
    """Where Loom.app is written: the person's own Applications folder, which needs no password."""
    return Path.home() / "Applications" / "Loom.app"


def write_launcher() -> Path:
    """Write Loom.app, over one an earlier install wrote, and return its path.

    Returns
    -------
    Path
        The bundle, whose `Contents/MacOS/Loom` runs `loom app --open` with this loom's Python.
    """
    app = app_path()
    macos = app / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    info = {
        "CFBundleName": "Loom",
        "CFBundleDisplayName": "Loom",
        "CFBundleIdentifier": "local.loom.home",
        "CFBundleExecutable": "Loom",
        "CFBundlePackageType": "APPL",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleShortVersionString": __version__,
        "CFBundleVersion": __version__,
    }
    (app / "Contents" / "Info.plist").write_bytes(plistlib.dumps(info))
    script = macos / "Loom"
    script.write_text(
        "#!/bin/sh\n"
        "# Open loom's home page, starting it first when it is not running.\n"
        f"exec {shlex.quote(sys.executable)} -P -m loom app --open >/dev/null 2>&1\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return app
