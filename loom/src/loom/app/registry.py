"""The quilts this machine's home lists, each with the port it keeps: `app/quilts.json` in loom's folder for the machine (`machine.data_dir`).

One file, read and written whole under its lock. A quilt is known by where it lies (`machine.quilt_id`), so a copied folder is another quilt with a port of its own. A port once given is never given to another quilt: a viewer keeps its preferences per port and its layout per port and quilt name, so a port that passed to another quilt would hand it the first one's.
"""

from __future__ import annotations

import json
import os
import socket
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass
from pathlib import Path

from loom.machine import data_dir, quilt_id

#: The home page's own port (`loom app`), beside the 8791 that `loom serve` takes by default.
HOME_PORT = 8790
#: Where the ports given to quilts start; the next is always one no quilt was given before.
FIRST_PORT = 8800


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
    return folder() / "serve.json"


def home_url() -> str:
    """The home page's address while a home runs on this machine, else ''."""
    try:
        data = json.loads(address().read_text(encoding="utf-8"))
        pid, url = data["pid"], data["url"]
        os.kill(pid, 0)
    except (OSError, ValueError, KeyError, TypeError):
        return ""
    return url if isinstance(url, str) else ""


def _read() -> tuple[dict[str, Entry], set[int]]:
    """The list and every port ever given; both empty when there is no list or it cannot be read."""
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
        entries = {e["id"]: Entry(**e) for e in data.get("quilts", [])}
        given = {int(p) for p in data.get("given", [])}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return {}, set()
    return entries, given | {e.port for e in entries.values()}


def _write(entries: dict[str, Entry], given: set[int]) -> None:
    """Write the list whole, through a temporary file renamed into place."""
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.{os.getpid()}")
    tmp.write_text(
        json.dumps({"quilts": [asdict(e) for e in entries.values()], "given": sorted(given)}, indent=1) + "\n",
        encoding="utf-8",
    )
    tmp.replace(p)


def _locked() -> AbstractContextManager[None]:
    from loom.locks import locked

    return locked(folder() / ".lock")


def free(port: int) -> bool:
    """Whether nothing listens on `port` at 127.0.0.1, by binding it for a moment as a server binds it: past the closed connections a stopped server leaves waiting."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _next_port(given: set[int]) -> int:
    port = FIRST_PORT
    while port in given or not free(port):
        port += 1
    return port


def entries() -> list[Entry]:
    """Every quilt on the list, in the order they were added."""
    return list(_read()[0].values())


def find(key: str) -> Entry | None:
    """The entry with id `key`, or None."""
    return _read()[0].get(key)


def port_of(root: Path) -> int | None:
    """The port the quilt at `root` keeps, or None when it is not on the list."""
    found = find(quilt_id(root))
    return found.port if found else None


def remember(root: Path) -> Entry:
    """Put the quilt at `root` on the list, or find it there.

    Parameters
    ----------
    root : Path
        The quilt's root.

    Returns
    -------
    Entry
        Its entry: one already there unchanged; a new one keeping the port its running server listens on, else the first port from `FIRST_PORT` no quilt was ever given and nothing holds now.
    """
    from loom.render.serve import open_url, read_serve_json

    key = quilt_id(root)
    with _locked():
        listed, given = _read()
        if key in listed:
            return listed[key]
        running = read_serve_json(root).get("port") if open_url(root) else None
        port = running if isinstance(running, int) and running not in given else _next_port(given)
        entry = Entry(key, str(root.resolve()), port)
        listed[key] = entry
        _write(listed, given | {port})
        return entry


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
