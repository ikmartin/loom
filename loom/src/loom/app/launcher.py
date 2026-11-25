"""loom's app in the Applications folder: `~/Applications/Loom.app`, which opens loom's home page and starts it first when it is not running.

The bundle holds a shell script, not a program, and loom writes it on the person's machine, so the system never quarantines it and it needs no signature. It names the Python loom was installed with, which an update keeps where it is. Loom writes over a bundle only when it is its own, told by `IDENTIFIER` inside it: where another app is called `NAME`, in the person's Applications folder or the system's, loom touches nothing of it and its app is `OTHER_NAME`.
"""

from __future__ import annotations

import plistlib
import shlex
import sys
from pathlib import Path

from loom.errors import EnvError
from loom.version import __version__

#: The app's name in the Applications folder.
NAME = "Loom"
#: Its name where another app is called `NAME`.
OTHER_NAME = "Loom Quilts"
#: The identifier inside loom's own bundle, by which loom knows a bundle is its own to write over.
IDENTIFIER = "local.loom.home"
#: The system's Applications folder, whose apps the person's own sit beside in Launchpad and Spotlight.
SYSTEM = Path("/Applications")


def _ours(app: Path) -> bool:
    """Whether the bundle at `app` is loom's own, by the identifier in its `Info.plist`."""
    try:
        info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    except (OSError, ValueError, plistlib.InvalidFileException):
        return False
    return isinstance(info, dict) and info.get("CFBundleIdentifier") == IDENTIFIER


def app_path() -> Path:
    """Where loom's app is written: `NAME` in the person's own Applications folder, which needs no password, or `OTHER_NAME` where another app has that name there or in the system's; EnvError when other apps have both."""
    for name in (NAME, OTHER_NAME):
        mine = Path.home() / "Applications" / f"{name}.app"
        if all(not p.exists() or _ours(p) for p in (mine, SYSTEM / f"{name}.app")):
            return mine
    raise EnvError(f"other apps are called {NAME} and {OTHER_NAME}, so loom wrote no app of its own")


def write_launcher() -> Path:
    """Write loom's app, over one an earlier install wrote, and return its path.

    Returns
    -------
    Path
        The bundle (`app_path`), whose `Contents/MacOS/Loom` runs `loom app --open` with this loom's Python.
    """
    app = app_path()
    macos = app / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    name = app.name.removesuffix(".app")
    info = {
        "CFBundleName": name,
        "CFBundleDisplayName": name,
        "CFBundleIdentifier": IDENTIFIER,
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
