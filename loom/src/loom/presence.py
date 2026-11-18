"""Who is connected: a record per `loom mcp` process at `.loom/local/live/<pid>.json`, held under a lock while its process runs, and the list of those alive.

The record's shape is `docs/specs/write-api.md` §1's. The lock is the proof of life: a reader that can take it knows no process holds the record, whatever its pid names now, so a server killed outright, a record copied with a quilt and a reused pid all read as gone, and the reader deletes the record. Nothing here is committed or read by a build; nothing here may stop an agent's server, so a record that cannot be written is left unwritten.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import stat
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loom.paths import LIVE

#: The record's format number, which a reader checks before it lists one.
FORMAT = 1
#: How often `loom serve` looks at the records, in seconds.
INTERVAL = 1.0
#: The environment an agent's app gives its server: the conversation's id, and how the app was started.
CONVERSATION = "CLAUDE_CODE_SESSION_ID"
ENTRYPOINT = "CLAUDE_CODE_ENTRYPOINT"
#: A record's file name, the only one a reader opens: the server's pid in ASCII digits, as the server writes it.
NAME = re.compile(r"[1-9][0-9]*\.json")
#: The most of a record a reader reads; a server's own is well under a kilobyte.
MOST = 65536
#: Every open of a record: never through a link, and never waiting on a file that is not one (a FIFO).
_SAFE = os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)


def record_path(root: Path, pid: int) -> Path:
    return root / LIVE / f"{pid}.json"


def _place(root: Path, *, make: bool = False) -> Path | None:
    """`.loom/local/live/` when it is a directory and not a link, made with `make` where there is none; None otherwise, so nothing is read or written through a link a copied quilt carries."""
    where = root / LIVE
    try:
        if make and not os.path.lexists(where):
            where.mkdir(parents=True, exist_ok=True)
        return where if stat.S_ISDIR(os.lstat(where).st_mode) else None
    except OSError:
        return None


class Presence:
    """This process's own record: written at its first request, written again in place at each call and binding, removed when the process ends.

    The file is opened once and locked for the process's life; its descriptor is not inherited, so a command the server runs never keeps it alive. `end` does no more than unlink and close, so a signal handler may call it.
    """

    def __init__(self, root: Path, name: str) -> None:
        from loom.version import __version__

        self.root = root
        self.path = record_path(root, os.getpid())
        self.fd: int | None = None
        self.ended = False
        self.data: dict[str, Any] = {
            "format": FORMAT,
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "as": name,
            "client": None,
            "protocol": None,
            "conversation": os.environ.get(CONVERSATION) or None,
            "entrypoint": os.environ.get(ENTRYPOINT) or None,
            "session": None,
            "loom": __version__,
            "started": None,
            "last": None,
        }

    @property
    def begun(self) -> bool:
        return self.data["started"] is not None

    def begin(self, client: dict[str, Any] | None, protocol: str | None) -> None:
        """Write the record at the first request; later ones change nothing here."""
        from loom.clock import stamp

        if self.begun or self.ended:
            return
        self.data["client"] = client
        self.data["protocol"] = protocol
        self.data["started"] = stamp()
        self._write()

    def called(self, kind: str, name: str) -> None:
        """A tool call, a prompt or a resource read: the latest call and its time."""
        from loom.clock import stamp

        self.data["last"] = {"kind": kind, "name": name, "when": stamp()}
        if self.begun:
            self._write()

    def bound(self, session: str) -> None:
        """The loom session this server writes into."""
        if self.data["session"] == session:
            return
        self.data["session"] = session
        if self.begun:
            self._write()

    def end(self) -> None:
        """Remove the record and let the lock go; safe to call twice and from a signal handler."""
        self.ended = True
        fd, self.fd = self.fd, None
        if fd is None:
            return
        with contextlib.suppress(OSError):
            os.unlink(self.path)
        with contextlib.suppress(OSError):
            os.close(fd)

    def _write(self) -> None:
        """Write the record over itself, opening and locking it first where this process holds none, or where a reader took it away."""
        if self.ended:
            return
        try:
            if self.fd is not None and not _still_there(self.fd, self.path):
                os.close(self.fd)
                self.fd = None
            if self.fd is None:
                if _place(self.root, make=True) is None:
                    return
                self.fd = _held(self.path)
            text = json.dumps(self.data, ensure_ascii=False).encode("utf-8")
            os.pwrite(self.fd, text, 0)
            os.ftruncate(self.fd, len(text))
        except OSError:
            pass  # an agent's server works without its record; the viewer just says nothing of it


def _held(path: Path) -> int:
    """The record's file, opened and locked for this process: a reader holds its shared lock for an instant, so the wait is no longer. Whatever else stands at this process's own name (a link, a FIFO, a directory a copied quilt carried) is removed first, or the record is not written."""
    from loom.locks import hold

    while True:
        with contextlib.suppress(FileNotFoundError):
            if not stat.S_ISREG(os.lstat(path).st_mode):
                os.unlink(path)
        fd = os.open(path, os.O_RDWR | os.O_CREAT | _SAFE, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise OSError(f"{path} is not a file")
            hold(fd)
        except OSError:
            os.close(fd)
            raise
        # a reader that found the file unheld before the lock was taken deletes it: open the one at the path again
        if _still_there(fd, path):
            return fd
        os.close(fd)


def _still_there(fd: int, path: Path) -> bool:
    """Whether `path` is still the file `fd` holds: a reader that found it unheld in the instant before it was locked may have deleted it."""
    try:
        held, there = os.fstat(fd), os.lstat(path)
    except OSError:
        return False
    return (held.st_dev, held.st_ino) == (there.st_dev, there.st_ino)


def live(root: Path) -> list[dict[str, Any]]:
    """The records of the `loom mcp` processes alive now, the oldest first; a record no process holds is deleted.

    Parameters
    ----------
    root : Path
        The quilt.

    Returns
    -------
    list of dict
        Each record as its server wrote it (`docs/specs/write-api.md` §1). Only a regular file named for a pid in ASCII digits (`NAME`) is opened, in a `.loom/local/live/` that is no link; anything else there is left alone. One that does not parse, whose `pid` is not its file's name, or whose lock cannot be tried is left where it is and not listed, and no entry stops the look at the rest.
    """
    where = _place(root)
    if where is None:
        return []
    try:
        names = sorted(os.listdir(where))
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for name in names:
        if not NAME.fullmatch(name):
            continue
        try:
            record = _alive(where / name, int(name.removesuffix(".json")))
        except Exception:  # noqa: BLE001 -- one entry a quilt carried must not hide the others
            continue
        if record is not None:
            out.append(record)
    return sorted(out, key=lambda r: (str(r.get("started") or ""), int(r["pid"])))


def _alive(path: Path, pid: int) -> dict[str, Any] | None:
    """The record at `path` when a process holds it; deleted, and None, when none does; None, and left alone, when it is not a regular file."""
    from loom.locks import held

    try:
        if not stat.S_ISREG(os.lstat(path).st_mode):
            return None
        fd = os.open(path, os.O_RDONLY | _SAFE)
    except OSError:
        return None
    try:
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                return None
            alive = held(fd)
        except OSError:
            return None
        if alive:
            return _parsed(fd, pid)
        if alive is None:
            return None  # a filesystem without locks: nothing proves the process is loom's
        # nobody holds it: the process is gone, or the record came from elsewhere
        if _still_there(fd, path):
            with contextlib.suppress(OSError):
                os.unlink(path)
        return None
    finally:
        os.close(fd)


def _parsed(fd: int, pid: int) -> dict[str, Any] | None:
    """The record a live process holds, read whole; its writer rewrites it in place, so a read caught between its write and its truncation is read again."""
    for _ in range(5):
        size = os.fstat(fd).st_size
        if size > MOST:
            return None
        raw = os.pread(fd, max(size, 1), 0)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            time.sleep(0.002)
            continue
        if isinstance(data, dict) and data.get("format") == FORMAT and data.get("pid") == pid:
            return data
        return None
    return None


def prune(root: Path) -> None:
    """Delete every record no process holds, as a starting server does."""
    live(root)


class Watch:
    """`loom serve`'s look at the records, once every `interval` seconds on a thread of its own, calling `told` with the list as JSON each time it changes.

    The first look is taken when it is made, so `state` has a list before the thread starts.
    """

    def __init__(self, root: Path, told: Callable[[bytes], None], interval: float = INTERVAL) -> None:
        self.root = root
        self.told = told
        self.interval = interval
        try:
            self.state = _state(root)
        except Exception:  # noqa: BLE001 -- a bad look says nobody is connected, and the next one may do better
            self.state = b"[]"
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self.told(self.state)
        self._thread = threading.Thread(target=self._loop, name="loom-presence", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval * 3)

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                now = _state(self.root)
            except Exception:  # noqa: BLE001 -- a bad look must not end the thread
                continue
            if now != self.state:
                self.state = now
                self.told(now)


def _state(root: Path) -> bytes:
    return json.dumps(live(root), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
