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


#: A server that, letting go of what no one holds, deletes half of it and dies there: as a kill, a Ctrl-C or a power cut in the removal leaves it.
DIES_REMOVING = """
import os, shutil, sys
from pathlib import Path
def half(path, *a, **k):
    files = sorted(p for p in Path(path).rglob('*') if p.is_file())
    for p in files[: len(files) // 2]:
        p.unlink()
    os._exit(9)
shutil.rmtree = half
from loom.render.serve import HeldBundle
HeldBundle(Path(sys.argv[1]))
"""


def many(where: Path, version: str) -> Path:
    """A bundle of forty files, so that a removal cut short leaves part of a copy."""
    bundle(where, version)
    for n in range(40):
        (where / "_app" / f"chunk{n}.js").write_text(f"chunk {n}\n")
    return where


def test_a_version_removed_part_way_is_never_served_as_whole(tmp_path: Path) -> None:
    """A version is renamed aside before it is deleted, so a removal killed half way leaves nothing under the version's name: the next server of that version makes it again, whole, and the half deleted folder goes."""
    old = many(tmp_path / "old", "700")
    HeldBundle(old).close()
    dying = subprocess.run([sys.executable, "-c", DIES_REMOVING, str(many(tmp_path / "new", "701"))], check=False)
    assert dying.returncode == 9
    again = HeldBundle(old)
    assert sorted(p.relative_to(again.path) for p in again.path.rglob("*")) == sorted(
        p.relative_to(old) for p in old.rglob("*")
    )
    assert not [p for p in viewers().iterdir() if p.name.startswith(".removing-")]


@pytest.mark.parametrize("where", ["a version", "held/", "viewers itself"])
def test_a_start_removes_nothing_through_a_link(tmp_path: Path, where: str) -> None:
    """A link planted in loom's folder, at a version's place, at a version's `held/`, or as the folder itself: a start removes nothing it reaches through it, and leaves the link."""
    outside = tmp_path / "outside"
    (outside / "held").mkdir(parents=True)
    (outside / "viewer").mkdir()
    (outside / "mydata").mkdir()
    # shaped as loom keeps a version, so that a start reaching it would let it go
    (outside / "123" / "viewer").mkdir(parents=True)
    for f in (
        "held/keep.txt",
        "held/12345678",
        "held/99999",
        "viewer/index.html",
        "mydata/notes.txt",
        "123/viewer/index.html",
    ):
        (outside / f).write_text("the person's\n")
    before = sorted(p.relative_to(outside) for p in outside.rglob("*"))
    if where == "a version":
        viewers().mkdir(parents=True, exist_ok=True)
        (viewers() / "evil").symlink_to(outside, target_is_directory=True)
    elif where == "held/":
        HeldBundle(bundle(tmp_path / "old", "800")).close()
        (viewers() / "800" / "held").rmdir()
        (viewers() / "800" / "held").symlink_to(outside / "held", target_is_directory=True)
    else:
        viewers().parent.mkdir(parents=True, exist_ok=True)
        viewers().symlink_to(outside, target_is_directory=True)
    HeldBundle(bundle(tmp_path / "new", "801"))
    after = sorted(
        p.relative_to(outside) for p in outside.rglob("*") if "801" not in p.parts and ".lock" not in p.parts
    )
    assert after == before
    assert (viewers() / "evil").is_symlink() if where == "a version" else True


@pytest.mark.parametrize("name", ["²", "99999999999999999999", "0", "007", "-1", "a folder"])
def test_a_mark_that_names_no_process_holds_nothing_and_stops_no_start(tmp_path: Path, name: str) -> None:
    """A mark is a file named by a pid: one whose name is no positive decimal pid in range, or a folder in `held/`, holds nothing, so its version is let go, and no start fails on it."""
    HeldBundle(bundle(tmp_path / "old", "900")).close()
    if name == "a folder":
        # named by a live process, so that it would hold the version were a folder taken for a mark
        (viewers() / "900" / "held" / str(os.getppid())).mkdir()
    else:
        (viewers() / "900" / "held" / name).write_text("")
    HeldBundle(bundle(tmp_path / "new", "901"))
    assert "900" not in held()


@pytest.mark.parametrize(
    "name", [".staged-²-0000abcd", ".staged-99999999999999999999-0000abcd", ".removing-0-0000abcd"]
)
def test_a_folder_aside_that_names_no_process_is_left_and_stops_no_start(tmp_path: Path, name: str) -> None:
    (viewers() / name / "viewer").mkdir(parents=True)
    HeldBundle(bundle(tmp_path / "bundle", "950"))
    assert (viewers() / name / "viewer").is_dir()


def test_a_copy_of_a_bundle_changed_while_it_is_copied_is_taken_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bundle being vendored, half old and half new, is not kept as the machine's copy of its version: a copy is kept only once the bundle's listing is the same after it as before."""
    import shutil

    from loom.render import serve

    source = bundle(tmp_path / "bundle", "1000", "half vendored")
    copy, copies = shutil.copytree, []

    def vendored_meanwhile(src, dst, *a, **k):  # type: ignore[no-untyped-def]
        """`copytree` calls itself for each folder within; only the bundle's own copy counts, and the first changes the bundle as it ends."""
        out = copy(src, dst, *a, **k)
        if Path(src) == source:
            copies.append(1)
            if len(copies) == 1:
                (source / "index.html").write_text("<p>vendored whole</p>\n")
        return out

    monkeypatch.setattr(shutil, "copytree", vendored_meanwhile)
    monkeypatch.setattr(serve, "_REST", 0.0)
    now = HeldBundle(source)
    assert (now.path / "index.html").read_text() == "<p>vendored whole</p>\n" and len(copies) == 2


def test_a_bundle_never_at_rest_stops_the_start_and_says_so(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import shutil

    from loom.errors import EnvError
    from loom.render import serve

    source = bundle(tmp_path / "bundle", "1100")
    copy = shutil.copytree

    def always_changing(src, dst, *a, **k):  # type: ignore[no-untyped-def]
        out = copy(src, dst, *a, **k)
        if Path(src) == source:
            (source / "index.html").write_text(f"<p>{os.urandom(4).hex()}</p>\n")
        return out

    monkeypatch.setattr(shutil, "copytree", always_changing)
    monkeypatch.setattr(serve, "_REST", 0.0)
    with pytest.raises(EnvError, match="changed each of the 5 times"):
        HeldBundle(source)
    assert held() == {}


@pytest.mark.parametrize("what", ["the viewers", "the token", "the port"])
def test_a_server_that_cannot_start_names_what_it_could_not_do(tmp_path: Path, what: str) -> None:
    """A folder of loom's that cannot be written is named, with why; only a port that cannot be bound is blamed on the port."""
    import socket

    from loom.machine import data_dir
    from tests.unit._quilts import demo

    q = demo(tmp_path)
    env = {**os.environ, "LOOM_ARRAS_BUNDLE": str(bundle(tmp_path / "bundle", "1200"))}
    port = "0"
    taken = None
    if what == "the viewers":
        viewers().mkdir(parents=True)
        viewers().chmod(0o500)
    elif what == "the token":
        # loom makes its token folder closed to others itself, so a folder of tokens made read-only is opened again; a file in its place is not
        data_dir().mkdir(parents=True, exist_ok=True)
        (data_dir() / "tokens").write_text("not a folder\n")
    else:
        taken = socket.socket()
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = str(taken.getsockname()[1])
    try:
        said = subprocess.run(
            [sys.executable, "-m", "loom", "serve", "--port", port, "--no-compile", "--quilt", str(q)],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
    finally:
        viewers().chmod(0o700) if what == "the viewers" else None
        if taken is not None:
            taken.close()
    assert said.returncode == 2, said.stdout + said.stderr
    if what == "the port":
        assert f"cannot listen on port {port}" in said.stderr
    else:
        said_it = " ".join(said.stderr.split())
        if what == "the viewers":
            assert f"cannot keep the viewer in {viewers()}" in said_it, said.stderr
        else:
            assert f"cannot keep the server's write token in {data_dir() / 'tokens'}" in said_it, said.stderr
        assert "cannot listen on port" not in said_it
