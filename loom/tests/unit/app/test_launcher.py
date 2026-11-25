"""loom's app in the Applications folder (`loom.app.launcher`, `loom app --install`) and `loom app --open`: the bundle written where it needs no password and passes the system's check, another app called Loom never touched, opening the home page starts a home only when none runs, one home a machine, and an address a dead home left is not trusted.

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

from loom.app import launcher
from loom.app.registry import address, home_url
from tests.helpers import ok
from tests.unit.app.conftest import until

mac = pytest.mark.skipif(sys.platform != "darwin", reason="Loom.app is written on macOS only")


@pytest.fixture(autouse=True)
def system_apps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The system's Applications folder, empty: this machine's own is never read."""
    p = tmp_path / "system-apps"
    p.mkdir()
    monkeypatch.setattr(launcher, "SYSTEM", p)
    return p


@pytest.fixture
def homes(bundle: Path) -> Iterator[None]:
    """Every home a test starts is stopped at the end."""
    yield
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


def other_app(folder: Path) -> Path:
    """Another program's bundle called Loom in `folder`."""
    app = folder / "Loom.app"
    (app / "Contents" / "MacOS").mkdir(parents=True)
    (app / "Contents" / "Info.plist").write_bytes(
        plistlib.dumps({"CFBundleIdentifier": "com.example.recorder", "CFBundleExecutable": "Loom"})
    )
    (app / "Contents" / "MacOS" / "Loom").write_bytes(b"\xcf\xfa\xed\xfe a program")
    return app


@mac
@pytest.mark.parametrize("where", ["the person's", "the system's"])
def test_another_app_called_loom_is_never_touched_and_looms_takes_another_name(
    home: Path, system_apps: Path, where: str
) -> None:
    other = other_app(home / "Applications" if where == "the person's" else system_apps)
    before = {p: p.read_bytes() for p in other.rglob("*") if p.is_file()}
    said = ok("app", "--install").output
    assert {p: p.read_bytes() for p in other.rglob("*") if p.is_file()} == before
    mine = home / "Applications" / f"{launcher.OTHER_NAME}.app"
    assert plistlib.loads((mine / "Contents" / "Info.plist").read_bytes())["CFBundleIdentifier"] == launcher.IDENTIFIER
    assert f"loom's is {launcher.OTHER_NAME}" in said
    assert ok("app", "--install").output == said  # an update writes its own again, beside the other


@mac
@pytest.mark.parametrize("to", ["nothing", "a bundle of loom's elsewhere"])
def test_a_link_called_loom_is_not_looms_own_and_is_left_as_it_is(home: Path, to: str) -> None:
    there = home / "elsewhere" / "Loom.app"
    if to != "nothing":
        (there / "Contents").mkdir(parents=True)
        (there / "Contents" / "Info.plist").write_bytes(plistlib.dumps({"CFBundleIdentifier": launcher.IDENTIFIER}))
    link = home / "Applications" / "Loom.app"
    link.parent.mkdir()
    link.symlink_to(there)
    said = ok("app", "--install").output
    assert link.is_symlink() and os.readlink(link) == str(there)
    assert not (there / "Contents" / "MacOS").exists()
    assert (home / "Applications" / f"{launcher.OTHER_NAME}.app" / "Contents" / "MacOS" / "Loom").is_file()
    assert f"loom's is {launcher.OTHER_NAME}" in said


def test_a_second_home_finds_the_first_and_leaves_it_to_run(homes: None, tmp_path: Path) -> None:
    """Two started at once, as a double click on the app does."""
    procs = [
        subprocess.Popen(
            [sys.executable, "-P", "-m", "loom", "app", "--port", str(free_port())],
            stdout=open(tmp_path / f"home-{n}.log", "wb"),  # noqa: SIM115 -- the process keeps it
            stderr=subprocess.STDOUT,
        )
        for n in range(2)
    ]
    try:
        until(lambda: any(p.poll() is not None for p in procs), "one of the two to leave")
        left = next(n for n, p in enumerate(procs) if p.poll() is not None)
        assert procs[left].returncode == 0 and procs[1 - left].poll() is None
        assert home_url() and home_url() in (tmp_path / f"home-{left}.log").read_text()
    finally:
        for p in procs:
            p.terminate()
            p.wait()


def test_an_address_a_home_killed_outright_left_is_not_trusted(homes: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Its pid may be any program's by now: here this test's own."""
    import json
    import webbrowser

    dead = free_port()
    address().parent.mkdir(parents=True, exist_ok=True)
    address().write_text(json.dumps({"port": dead, "pid": os.getpid(), "url": f"http://127.0.0.1:{dead}/"}))
    assert home_url() == ""
    opened: list[str] = []
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url) or True)
    port = free_port()
    ok("app", "--open", "--port", str(port))
    assert opened == [f"http://127.0.0.1:{port}/"]
