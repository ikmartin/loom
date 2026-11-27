"""The home's list of quilts (`loom.app.registry`): each quilt keeps one port for good, no port passes to another quilt, a copy is another quilt, a list that cannot be read is kept and gives nothing, a port another program holds on any address is passed over, `loom serve` takes the port its quilt keeps, and every quilt `loom serve` serves or `loom init` makes joins the list, which an unreadable or locked list never stops.

Every test runs under the suite's own HOME and XDG folders (`conftest.isolated_env`), so the list is a temporary one.
"""

from __future__ import annotations

import shutil
import socket
from pathlib import Path

import pytest

from loom.app import registry


def quilt(where: Path) -> Path:
    """A minimal quilt at `where`."""
    from loom.cli.quilt import write_minimal_quilt

    write_minimal_quilt(where, "q")
    return where


def test_a_quilt_keeps_its_port_across_loads(tmp_path: Path) -> None:
    q = quilt(tmp_path / "q")
    first = registry.remember(q)
    assert first.port >= registry.FIRST_PORT
    assert registry.remember(q) == first
    assert registry.port_of(q) == first.port and registry.find(first.id) == first


def test_a_forgotten_quilts_port_is_never_given_to_another(tmp_path: Path) -> None:
    """A viewer keeps its layout per port and quilt name, so a port that passed to another quilt would hand it the first one's."""
    a = registry.remember(quilt(tmp_path / "a"))
    registry.forget(a.id)
    assert registry.entries() == []
    b = registry.remember(quilt(tmp_path / "b"))
    assert b.port != a.port
    again = registry.remember(tmp_path / "a")
    assert again.port not in (a.port, b.port)


def test_a_copied_folder_is_another_quilt_with_another_port(tmp_path: Path) -> None:
    here = quilt(tmp_path / "here")
    mine = registry.remember(here)
    shutil.copytree(here, tmp_path / "copy")
    theirs = registry.remember(tmp_path / "copy")
    assert theirs.id != mine.id and theirs.port != mine.port


def test_a_quilt_already_served_keeps_the_port_it_is_served_on(tmp_path: Path) -> None:
    """The author's quilts are served on 8791 and 8792 today, and their tabs keep their layouts there."""
    from loom.render.serve import write_serve_json

    q = quilt(tmp_path / "q")
    write_serve_json(q, 8791)  # this process stands in for the server, and it is alive
    assert registry.remember(q).port == 8791


def test_a_port_something_else_holds_is_passed_over(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))
        held.listen()
        taken = held.getsockname()[1]
        monkeypatch.setattr(registry, "FIRST_PORT", taken)
        assert registry.remember(quilt(tmp_path / "q")).port != taken


@pytest.mark.parametrize(
    ("family", "host"), [(socket.AF_INET, "0.0.0.0"), (socket.AF_INET6, "::1")], ids=["every address", "IPv6 loopback"]
)
def test_a_port_another_program_holds_on_every_address_or_the_ipv6_loopback_is_not_free(
    family: socket.AddressFamily, host: str
) -> None:
    """A quilt's server binds 127.0.0.1, which the system allows beside such a listener: two programs would answer on one port."""
    with socket.socket(family, socket.SOCK_STREAM) as held:
        held.bind((host, 0))
        held.listen()
        assert not registry.free(held.getsockname()[1])


def test_a_list_that_cannot_be_read_is_kept_and_no_port_is_given(tmp_path: Path) -> None:
    """Begun again from nothing, it would give the first port again, to a quilt whose viewer then reads another quilt's layout."""
    first = registry.remember(quilt(tmp_path / "q"))
    listed = registry.folder() / "quilts.json"
    torn = listed.read_text()[:20]
    listed.write_text(torn)
    for change in (
        lambda: registry.remember(quilt(tmp_path / "other")),
        lambda: registry.readdress(first.id),
        lambda: registry.set_open(first.id, True),
        lambda: registry.forget(first.id),
        registry.entries,
    ):
        with pytest.raises(registry.Unreadable):
            change()
    assert listed.read_text() == torn
    assert registry.port_of(tmp_path / "q") is None  # loom serve still starts


def test_another_port_is_given_on_asking_and_the_old_one_is_kept_from_others(tmp_path: Path) -> None:
    q = registry.remember(quilt(tmp_path / "q"))
    moved = registry.readdress(q.id)
    assert moved.port != q.port and registry.port_of(tmp_path / "q") == moved.port
    other = registry.remember(quilt(tmp_path / "other"))
    assert other.port not in (q.port, moved.port)


def test_the_open_flag_is_kept(tmp_path: Path) -> None:
    q = registry.remember(quilt(tmp_path / "q"))
    registry.set_open(q.id, True)
    assert registry.find(q.id).open is True  # type: ignore[union-attr]
    registry.set_open(q.id, False)
    assert registry.find(q.id).open is False  # type: ignore[union-attr]


def test_loom_serve_listens_on_the_port_its_quilt_keeps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With no `--port`, the port the home keeps for the quilt; a quilt the home does not know takes 8791."""
    from loom.cli import serve_cmd
    from loom.render.serve import CannotBind
    from tests.helpers import refused
    from tests.unit.render._serve import fake_bundle

    asked: list[int] = []

    class Refusing:
        def __init__(self, quilt: object, bundle: object, port: int, **_: object) -> None:
            asked.append(port)

        def listen(self) -> None:
            raise CannotBind(asked[-1], "held for the test")

    monkeypatch.setattr(serve_cmd, "ServeSession", Refusing)
    bundle = fake_bundle(tmp_path)
    monkeypatch.setattr(serve_cmd, "locate_bundle", lambda: bundle)
    q = quilt(tmp_path / "q")
    refused("serve", "--quilt", str(q), code=2, match="cannot listen")
    kept = registry.remember(q).port
    refused("serve", "--quilt", str(q), code=2, match=f"port {kept}")
    refused("serve", "--quilt", str(q), "--port", "9123", code=2, match="port 9123")
    assert asked == [8791, kept, 9123]


class Listening:
    """A stand-in for the server: it records itself as listening on its port, as `ServeSession.listen` does, and stops at once."""

    def __init__(self, quilt: object, bundle: object, port: int, **_: object) -> None:
        self.root = quilt.root  # type: ignore[attr-defined]
        self.port, self.url, self.older = port, f"http://127.0.0.1:{port}/", None

    def listen(self) -> None:
        from loom.render.serve import write_serve_json

        write_serve_json(self.root, self.port)  # this process stands in for the server, and it is alive

    def start(self) -> None:
        raise KeyboardInterrupt

    def stop(self) -> None:
        from loom.paths import SERVE_JSON

        (self.root / SERVE_JSON).unlink()


@pytest.fixture
def serving(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`loom serve` with `Listening` for its server, its stand-in viewer and no SIGTERM handler left behind."""
    import signal

    from loom.cli import serve_cmd
    from tests.unit.render._serve import fake_bundle

    monkeypatch.setattr(serve_cmd, "ServeSession", Listening)
    bundle = fake_bundle(tmp_path)
    monkeypatch.setattr(serve_cmd, "locate_bundle", lambda: bundle)
    monkeypatch.setattr(signal, "signal", lambda *_: None)


@pytest.mark.usefixtures("serving")
def test_a_quilt_served_or_made_joins_the_list(tmp_path: Path) -> None:
    """Served, it keeps the port it is served on; made with `loom init`, a port of its own from `FIRST_PORT`."""
    from tests.helpers import ok

    served = quilt(tmp_path / "served")
    ok("serve", "--quilt", str(served), "--port", "9124")
    made = tmp_path / "made"
    ok("init", str(made), "--prefix", "q", "--ai", "none", "--yes")
    first, second = registry.entries()
    assert (Path(first.root), first.port) == (served.resolve(), 9124)
    assert Path(second.root) == made.resolve() and second.port >= registry.FIRST_PORT
    # served again, on another port, it keeps its own
    ok("serve", "--quilt", str(served), "--port", "9125")
    assert registry.port_of(served) == 9124 and len(registry.entries()) == 2


@pytest.mark.usefixtures("serving")
def test_an_unreadable_or_locked_list_stops_neither_serve_nor_init(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The list is left as it was, and the command goes on as if there were none."""
    import threading

    from tests.helpers import ok

    registry.remember(quilt(tmp_path / "first"))
    listed = registry.folder() / "quilts.json"
    torn = listed.read_text()[:20]
    listed.write_text(torn)
    ok("serve", "--quilt", str(quilt(tmp_path / "a")), "--port", "9126")
    ok("init", str(tmp_path / "b"), "--prefix", "q", "--ai", "none", "--yes")
    assert listed.read_text() == torn
    listed.unlink()
    monkeypatch.setattr(registry, "JOIN_WAIT", 0.2)
    held, done = threading.Event(), threading.Event()

    def hold() -> None:
        with registry._locked():
            held.set()
            done.wait(30)

    holder = threading.Thread(target=hold)
    holder.start()
    try:
        held.wait(30)
        ok("serve", "--quilt", str(quilt(tmp_path / "c")), "--port", "9127")
        ok("init", str(tmp_path / "d"), "--prefix", "q", "--ai", "none", "--yes")
    finally:
        done.set()
        holder.join()
    assert not listed.exists()
