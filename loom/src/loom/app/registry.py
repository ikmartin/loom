"""The quilts this machine's home lists, each with the port it keeps: `app/quilts.json` in loom's folder for the machine (`machine.data_dir`).

One file, read and written whole under its lock. A quilt is known by where it lies (`machine.quilt_id`), so a copied folder is another quilt with a port of its own. A port once given is never given to another quilt: a viewer keeps its preferences per port and its layout per port and quilt name, so a port that passed to another quilt would hand it the first one's. So a list that is there but cannot be read is never started again from nothing: it is kept as it is, and nothing is given or changed until it can be read (`Unreadable`).
"""

from __future__ import annotations

import json
import os
import socket
import urllib.request
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass
from pathlib import Path

from loom import own
from loom.errors import EnvError
from loom.machine import data_dir, quilt_id

#: The home page's own port (`loom app`), beside the 8791 that `loom serve` takes by default.
HOME_PORT = 8790
#: Where the ports given to quilts start; the next is always one no quilt was given before.
FIRST_PORT = 8800
#: Seconds `loom serve` and `loom init` wait for the list's lock before going on without it (`join`).
JOIN_WAIT = 2.0


class Unreadable(EnvError):
    """The list of quilts is there and cannot be read: it is kept as it is, and no port is given out and nothing on it changes until it can be read."""

    def __init__(self) -> None:
        super().__init__(
            "loom could not read its list of quilts, so it shows none and gives no quilt an address until it can; "
            "the list is kept as it was"
        )


@dataclass
class Entry:
    """One quilt on the list: its id, where it lies, the port it keeps, and whether the person left it open."""

    id: str
    root: str
    port: int
    open: bool = False


def folder() -> Path:
    """The home's folder in loom's folder for the machine: the list, the home's address, each quilt's server log, the drops waiting."""
    return data_dir() / "app"


def _path() -> Path:
    return folder() / "quilts.json"


def address() -> Path:
    """Where the running home records its port, pid and address."""
    return folder() / "home.json"


def home_url() -> str:
    """The home page's address while a home runs on this machine, else '': the address `home.json` records, once the home there answers `/_api` with the pid it records, so an address a home killed outright left behind is not trusted on its pid alone."""
    try:
        data = json.loads(address().read_text(encoding="utf-8"))
        pid, url = data["pid"], data["url"]
    except (OSError, ValueError, KeyError, TypeError):
        return ""
    if not isinstance(pid, int) or not isinstance(url, str) or not url.startswith("http://127.0.0.1:"):
        return ""
    try:
        with urllib.request.urlopen(f"{url}_api", timeout=2) as resp:
            said = json.loads(resp.read())
    except (OSError, ValueError):
        return ""
    return url if isinstance(said, dict) and said.get("home") is True and said.get("pid") == pid else ""


def _read() -> tuple[dict[str, Entry], set[int]]:
    """The list and every port ever given; both empty when there is no list yet, and `Unreadable` when there is one that cannot be read."""
    try:
        text = _path().read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, set()
    except (OSError, ValueError) as exc:
        raise Unreadable from exc
    try:
        data = json.loads(text)
        entries = {e["id"]: Entry(**e) for e in data["quilts"]}
        given = {int(p) for p in data["given"]}
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise Unreadable from exc
    return entries, given | {e.port for e in entries.values()}


def _write(entries: dict[str, Entry], given: set[int]) -> None:
    """Write the list whole, through a temporary file flushed to the disk and renamed into place."""
    p = _path()
    own.mkdir(p.parent, root=data_dir())
    tmp = p.with_name(f".{p.name}.{os.getpid()}")
    with own.open(tmp, "w", encoding="utf-8", root=data_dir()) as out:
        out.write(
            json.dumps({"quilts": [asdict(e) for e in entries.values()], "given": sorted(given)}, indent=1) + "\n"
        )
        out.flush()
        os.fsync(out.fileno())
    own.replace(tmp, p, root=data_dir())


def _locked(wait: float | None = None) -> AbstractContextManager[None]:
    from loom.locks import locked

    return locked(folder() / ".lock", wait=wait, root=data_dir())


def free(port: int) -> bool:
    """Whether a quilt's server would have `port` to itself: it can be bound at 127.0.0.1 as the server binds it, past the closed connections a stopped server leaves waiting, and nothing answers there or on the IPv6 loopback, as a program listening on every address does beside such a bind."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
    for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        try:
            with socket.socket(family, socket.SOCK_STREAM) as probe:
                probe.settimeout(0.5)
                if probe.connect_ex((host, port)) == 0:
                    return False
        except OSError:
            pass  # no IPv6 here
    return True


def _next_port(given: set[int]) -> int:
    port = FIRST_PORT
    while port in given or not free(port):
        port += 1
    return port


def entries() -> list[Entry]:
    """Every quilt on the list, in the order they were added; `Unreadable` when the list cannot be read."""
    return list(_read()[0].values())


def find(key: str) -> Entry | None:
    """The entry with id `key`, or None."""
    return _read()[0].get(key)


def port_of(root: Path) -> int | None:
    """The port the quilt at `root` keeps, or None when it is not on the list or the list cannot be read."""
    try:
        found = find(quilt_id(root))
    except Unreadable:
        return None
    return found.port if found else None


def remember(root: Path, wait: float | None = None) -> Entry:
    """Put the quilt at `root` on the list, or find it there.

    Parameters
    ----------
    root : Path
        The quilt's root.
    wait : float, optional
        Seconds to wait for the list's lock before refusing with EnvError; default the lock's own.

    Returns
    -------
    Entry
        Its entry: one already there unchanged; a new one keeping the port its running server listens on, else the first port from `FIRST_PORT` no quilt was ever given and nothing holds now.
    """
    from loom.render.serve import open_url, read_serve_json

    key = quilt_id(root)
    with _locked(wait):
        listed, given = _read()
        if key in listed:
            return listed[key]
        running = read_serve_json(root).get("port") if open_url(root) else None
        port = running if isinstance(running, int) and running not in given else _next_port(given)
        entry = Entry(key, str(root.resolve()), port)
        listed[key] = entry
        _write(listed, given | {port})
        return entry


def join(root: Path) -> Entry | None:
    """Put the quilt at `root` on the list, as `loom serve` does once it listens and `loom init` once its quilt is made, never failing either.

    Parameters
    ----------
    root : Path
        The quilt's root.

    Returns
    -------
    Entry or None
        Its entry, as `remember` gives it; None when the list cannot be read, stays locked past `JOIN_WAIT` or cannot be written, which leaves it as it was.

    See Also
    --------
    remember : The same, refusing instead.
    """
    try:
        return remember(root, wait=JOIN_WAIT)
    except (EnvError, OSError):
        return None


def readdress(key: str) -> Entry:
    """Give the quilt `key` a port no quilt was ever given, for a quilt whose own port another program holds; its viewer's layout and preferences start afresh there."""
    with _locked():
        listed, given = _read()
        entry = listed[key]
        entry.port = _next_port(given)
        _write(listed, given | {entry.port})
        return entry


def set_open(key: str, value: bool) -> None:
    """Record whether the person left the quilt `key` open, which the home's next start follows."""
    with _locked():
        listed, given = _read()
        if key in listed:
            listed[key].open = value
            _write(listed, given)


def forget(key: str) -> None:
    """Take the quilt `key` off the list; its folder is untouched and its port is never given again."""
    with _locked():
        listed, given = _read()
        listed.pop(key, None)
        _write(listed, given)
