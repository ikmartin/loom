"""The viewer a server holds (`render/serve.HeldBundle`): the machine's one copy of each version, in loom's own place (`machine.viewers`), shared by every server of it, marked held by each, and let go at a start once no live process holds it; so a server killed outright leaves nothing the next start does not remove.

Every test runs under the suite's own HOME and XDG folders (`conftest.isolated_env`), so the machine's place here is a temporary one.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from loom.machine import viewers
from loom.render.serve import HeldBundle

#: A server holding the bundle at argv[1]: it prints the copy it serves, then waits to be stopped.
HOLD = "import sys, time; from pathlib import Path; from loom.render.serve import HeldBundle; print(HeldBundle(Path(sys.argv[1])).path, flush=True); time.sleep(300)"


def bundle(where: Path, version: str | None, page: str = "the viewer") -> Path:
    """A built viewer at `where`: a page, and `_app/version.json` naming `version` (none for None)."""
    (where / "_app").mkdir(parents=True, exist_ok=True)
    (where / "index.html").write_text(f"<p>{page}</p>\n")
    version_file = where / "_app" / "version.json"
    if version is None:
        version_file.unlink(missing_ok=True)
    else:
        version_file.write_text(json.dumps({"version": version}))
    return where


@pytest.fixture
def servers() -> Iterator[list[subprocess.Popen[str]]]:
    """Other servers, each its own process, stopped outright at the end if a test has not."""
    running: list[subprocess.Popen[str]] = []
    yield running
    for proc in running:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def another_server(servers: list[subprocess.Popen[str]], source: Path) -> tuple[subprocess.Popen[str], Path]:
    """A server in another process holding `source`, and the copy it serves."""
    proc = subprocess.Popen([sys.executable, "-c", HOLD, str(source)], stdout=subprocess.PIPE, text=True)
    servers.append(proc)
    assert proc.stdout is not None
    return proc, Path(proc.stdout.readline().strip())


def killed(proc: subprocess.Popen[str]) -> None:
    """Stopped as the viewer's test harness stops a server: SIGKILL, so nothing of its own runs."""
    os.kill(proc.pid, signal.SIGKILL)
    proc.wait()


def held() -> dict[str, list[str]]:
    """Each version folder in the machine's place, with the pids that hold it; the lock file left out."""
    return {
        entry.name: sorted(m.name for m in (entry / "held").glob("*")) if (entry / "held").is_dir() else []
        for entry in sorted(viewers().iterdir())
        if entry.name != ".lock"
    }


def test_a_server_killed_outright_leaves_nothing_the_next_start_does_not_remove(
    tmp_path: Path, servers: list[subprocess.Popen[str]]
) -> None:
    """Its mark, its version no other server holds, and a copy it was half way through making are gone once another server starts; nothing of it is in the temporary folder."""
    before = {p.name for p in Path(tempfile.gettempdir()).glob("loom-viewer-*")}
    proc, copy = another_server(servers, bundle(tmp_path / "old", "100"))
    assert copy == viewers() / "100" / "viewer" and (copy / "index.html").is_file()
    killed(proc)
    # a copy half made by a process gone: one that has run and exited
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    (viewers() / f".staged-{dead.pid}-0000abcd" / "viewer").mkdir(parents=True)
    assert held() == {f".staged-{dead.pid}-0000abcd": [], "100": [str(proc.pid)]}
    now = HeldBundle(bundle(tmp_path / "new", "200"))
    assert held() == {"200": [str(os.getpid())]}
    assert now.path == viewers() / "200" / "viewer"
    assert {p.name for p in Path(tempfile.gettempdir()).glob("loom-viewer-*")} == before


def test_two_servers_of_one_version_share_one_copy(tmp_path: Path, servers: list[subprocess.Popen[str]]) -> None:
    source = bundle(tmp_path / "bundle", "300")
    proc, theirs = another_server(servers, source)
    mine = HeldBundle(source)
    assert mine.path == theirs == viewers() / "300" / "viewer"
    assert held() == {"300": sorted([str(proc.pid), str(os.getpid())])}


def test_a_server_keeps_serving_its_own_version_after_the_bundle_is_vendored_again(tmp_path: Path) -> None:
    """The copy is the version the server started with; the vendored bundle moving on makes it stale, and the next server holds the new version beside it."""
    source = bundle(tmp_path / "bundle", "400", "the old viewer")
    first = HeldBundle(source)
    assert not first.stale()
    bundle(source, "401", "the new viewer")
    assert first.stale() and first.version == "400"
    assert (first.path / "index.html").read_text() == "<p>the old viewer</p>\n"
    second = HeldBundle(source)
    assert second.version == "401" and (second.path / "index.html").read_text() == "<p>the new viewer</p>\n"
    assert set(held()) == {"400", "401"}


def test_a_version_no_live_process_holds_is_gone_after_the_next_start(tmp_path: Path) -> None:
    first = HeldBundle(bundle(tmp_path / "old", "500"))
    first.close()
    assert held() == {"500": []}
    HeldBundle(bundle(tmp_path / "new", "501"))
    assert held() == {"501": [str(os.getpid())]}


def test_a_held_version_is_not_removed(tmp_path: Path, servers: list[subprocess.Popen[str]]) -> None:
    """A version another live server holds stays through any number of starts, and goes at the first start after that server is gone."""
    proc, theirs = another_server(servers, bundle(tmp_path / "old", "600"))
    HeldBundle(bundle(tmp_path / "new", "601"))
    HeldBundle(bundle(tmp_path / "new", "601"))
    assert (theirs / "index.html").is_file() and held()["600"] == [str(proc.pid)]
    killed(proc)
    HeldBundle(bundle(tmp_path / "new", "601"))
    assert "600" not in held()


def test_a_viewer_that_names_no_version_is_its_servers_alone(
    tmp_path: Path, servers: list[subprocess.Popen[str]]
) -> None:
    """A bundle with no `_app/version.json` cannot be shared by version: each server holds a copy of its own, let go once its process is gone."""
    source = bundle(tmp_path / "bundle", None)
    proc, theirs = another_server(servers, source)
    mine = HeldBundle(source)
    assert theirs == viewers() / f"unversioned-{proc.pid}" / "viewer"
    assert mine.path == viewers() / f"unversioned-{os.getpid()}" / "viewer" and mine.version == ""
    killed(proc)
    HeldBundle(source)
    assert held() == {f"unversioned-{os.getpid()}": [str(os.getpid())]}
