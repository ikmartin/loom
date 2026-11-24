"""The home's servers (`loom.app.supervise`): each quilt served on the port it keeps, found again by a home that starts again, started again after a crash, left failed after a refusal or when its port is held, restarted when loom changed under it, and stopped with the home while staying on the list as open.

Each test runs real `loom serve` processes, with no compiles and a stand-in viewer, under the suite's own HOME and XDG folders.
"""

from __future__ import annotations

import json
import os
import signal
import socket
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from loom.app import registry, supervise
from loom.app.registry import Entry
from loom.app.supervise import Supervisor
from loom.render.serve import read_serve_json
from tests.unit.app.conftest import until


@pytest.fixture
def sups(bundle: Path, ports: None) -> Iterator[list[Supervisor]]:
    """Homes for the test, each serving with no compiles; whatever they run is stopped at the end."""
    made: list[Supervisor] = []
    yield made
    for sup in made:
        for child in sup.children.values():
            if child.proc is not None and child.proc.poll() is None:
                child.proc.kill()
                child.proc.wait()


def home(sups: list[Supervisor]) -> Supervisor:
    sup = Supervisor(("--no-compile",))
    sups.append(sup)
    return sup


def quilt(where: Path) -> Entry:
    from loom.cli.quilt import write_minimal_quilt

    write_minimal_quilt(where, "q")
    return registry.remember(where)


def running(sup: Supervisor, entry: Entry) -> Callable[[], bool]:
    return lambda: sup.state(entry)["state"] == "running"


def pid_of(entry: Entry) -> int:
    pid = read_serve_json(Path(entry.root))["pid"]
    assert isinstance(pid, int)
    return pid


def test_a_quilt_opened_is_served_on_its_port_and_a_home_started_again_finds_it(
    tmp_path: Path, sups: list[Supervisor]
) -> None:
    entry = quilt(tmp_path / "q")
    first = home(sups)
    assert first.open(entry)["state"] in ("starting", "running")
    until(running(first, entry), "the server")
    assert first.state(entry) == {"state": "running", "url": f"http://127.0.0.1:{entry.port}/"}
    pid = pid_of(entry)
    again = home(sups)
    assert again.open(entry)["state"] == "running"
    assert again.children[entry.id].proc is None and pid_of(entry) == pid


def test_a_server_killed_outright_is_started_again_on_its_port(
    tmp_path: Path, sups: list[Supervisor], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(supervise, "RETRIES", (0.0,))
    entry = quilt(tmp_path / "q")
    registry.set_open(entry.id, True)
    sup = home(sups)
    sup.tick(registry.entries())
    until(running(sup, entry), "the server")
    pid = pid_of(entry)
    os.kill(pid, signal.SIGKILL)

    def back() -> bool:
        sup.tick(registry.entries())
        return sup.state(entry)["state"] == "running" and pid_of(entry) != pid

    until(back, "the server started again")
    assert read_serve_json(Path(entry.root))["port"] == entry.port


def test_a_port_another_program_holds_is_said_and_nothing_is_started(tmp_path: Path, sups: list[Supervisor]) -> None:
    entry = quilt(tmp_path / "q")
    with socket.socket() as held:
        held.bind(("127.0.0.1", entry.port))
        held.listen()
        sup = home(sups)
        assert sup.open(entry) == {"state": "failed", "why": "port-taken", "said": ""}
        assert entry.id not in sup.children


def test_a_server_that_refuses_to_start_is_not_started_again(tmp_path: Path, sups: list[Supervisor]) -> None:
    (tmp_path / "bare").mkdir()
    entry = registry.remember(tmp_path / "bare")  # a folder that is not a quilt: loom serve refuses it
    registry.set_open(entry.id, True)
    sup = home(sups)

    def failed() -> bool:
        sup.tick(registry.entries())
        return sup.state(entry)["state"] == "failed"

    until(failed, "the refusal")
    state = sup.state(entry)
    assert state["why"] == "refused" and "not inside a quilt" in state["said"]


def test_a_server_loom_changed_under_is_restarted_on_its_port(
    tmp_path: Path, bundle: Path, sups: list[Supervisor], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A viewer vendored again makes a running server stale, as an install of loom does."""
    monkeypatch.setattr(supervise, "SETTLE", 0.0)
    monkeypatch.setattr(supervise, "ASK_EVERY", 0.0)
    entry = quilt(tmp_path / "q")
    registry.set_open(entry.id, True)
    sup = home(sups)
    sup.tick(registry.entries())
    until(running(sup, entry), "the server")
    pid = pid_of(entry)
    (bundle / "_app" / "version.json").write_text(json.dumps({"version": "2"}))
    assert (supervise.ask(entry) or {}).get("stale") is True

    def restarted() -> bool:
        sup.tick(registry.entries())
        said = supervise.ask(entry)
        return said is not None and not said.get("stale") and pid_of(entry) != pid

    until(restarted, "the server restarted")
    assert (supervise.ask(entry) or {}).get("viewer") == "2"


def test_a_home_stopping_stops_its_servers_and_what_was_left_open_comes_back(
    tmp_path: Path, sups: list[Supervisor]
) -> None:
    entry = quilt(tmp_path / "q")
    registry.set_open(entry.id, True)
    sup = home(sups)
    sup.tick(registry.entries())
    until(running(sup, entry), "the server")
    sup.stop_all(registry.entries())
    assert supervise.ask(entry) is None and read_serve_json(Path(entry.root)) == {}
    assert registry.find(entry.id).open is True  # type: ignore[union-attr]
    after = home(sups)
    after.tick(registry.entries())
    until(running(after, entry), "the server started by the next home")
