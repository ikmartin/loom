"""Loom in the Applications folder (`loom.app.launcher`, `loom app --install`) and `loom app --open`: the bundle written where it needs no password and passes the system's check, and opening the home page starts a home only when none runs.

Every test runs under the suite's own HOME and XDG folders; a browser is never opened.
"""

from __future__ import annotations

import os
import plistlib
import shutil
import signal
import socket
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from loom.app.registry import home_url
from tests.helpers import ok
from tests.unit.app.conftest import until

mac = pytest.mark.skipif(sys.platform != "darwin", reason="Loom.app is written on macOS only")


@pytest.fixture
def homes(bundle: Path) -> Iterator[None]:
    """Every home a test starts is stopped at the end."""
    yield
    from loom.app.registry import address

    if home_url():
        import json

        os.kill(json.loads(address().read_text())["pid"], signal.SIGTERM)
        until(lambda: not home_url(), "the home stopped")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@mac
def test_loom_app_is_written_in_the_persons_applications_folder_and_passes_the_systems_check(home: Path) -> None:
    ok("app", "--install")
    app = home / "Applications" / "Loom.app"
    info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    assert info["CFBundleExecutable"] == "Loom" and info["CFBundlePackageType"] == "APPL"
    if shutil.which("plutil"):
        subprocess.run(["plutil", "-lint", str(app / "Contents" / "Info.plist")], check=True, capture_output=True)
    script = app / "Contents" / "MacOS" / "Loom"
    assert os.access(script, os.X_OK)
    subprocess.run(["sh", "-n", str(script)], check=True)
    assert f"{sys.executable} -P -m loom app --open" in script.read_text()
    ok("app", "--install")  # an update writes it again over the last


def test_opening_the_home_page_starts_a_home_only_when_none_runs(homes: None, monkeypatch: pytest.MonkeyPatch) -> None:
    import webbrowser

    opened: list[str] = []
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url) or True)
    port = free_port()
    ok("app", "--open", "--port", str(port))
    assert opened == [f"http://127.0.0.1:{port}/"] == [home_url()]
    ok("app", "--open", "--port", str(free_port()))
    assert opened == [f"http://127.0.0.1:{port}/"] * 2  # the same home, not a second one


@mac
def test_loom_app_starts_a_home_in_the_persons_home_folder(homes: None) -> None:
    ok("app", "--install")
    script = Path.home() / "Applications" / "Loom.app" / "Contents" / "MacOS" / "Loom"
    # the browser a fresh Python's webbrowser opens is $BROWSER's command: here one that does nothing
    subprocess.run([str(script)], env={**os.environ, "BROWSER": "/usr/bin/true"}, check=True, timeout=60)
    until(lambda: bool(home_url()), "the home started")
