"""Each quilt's server as the home runs it: the unchanged `loom serve --port P --quilt ROOT`, one process a quilt in a session of its own, started, found again, stopped, started again after a crash, and restarted after an update.

A server is known to be a quilt's by its port answering `/_api` with that quilt's id, never by a pid alone, which a restart of the Mac can give to another program. So a home that starts again adopts the servers still running and starts no second one.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loom.app.registry import Entry, folder, free

#: Seconds before each start again of a server that died unasked; after the last, it is shown as could not start.
RETRIES = (2.0, 10.0, 60.0)
#: Seconds a server runs before a crash counts as a first one again.
STEADY = 60.0
#: Seconds loom's code must be still before a stale server is restarted, so an install half done is not what the new server runs.
SETTLE = 30.0
#: How often a running server is asked whether loom changed under it.
ASK_EVERY = 10.0
#: Seconds a stop waits after SIGTERM before SIGKILL.
STOP_WAIT = 10.0
#: A server's log is begun again at start once it is larger than this.
LOG_CAP = 1_000_000
#: A server that refuses to start exits 2, as every loom command refusing does (`loom.errors`): no start again changes that.
REFUSED = 2


def log_path(entry: Entry) -> Path:
    """The file the quilt's server writes what it says to."""
    return folder() / "logs" / f"{entry.id}.log"


def tail(entry: Entry, lines: int = 5) -> str:
    """The last non-empty lines the quilt's server wrote, for "could not start" and Copy details."""
    try:
        said = log_path(entry).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join([line for line in said if line.strip()][-lines:])


def ask(entry: Entry) -> dict[str, Any] | None:
    """What the server on the quilt's port says at `/_api`, when it is this quilt's server; None otherwise."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{entry.port}/_api", timeout=2) as resp:
            body = json.loads(resp.read())
    except (OSError, ValueError, urllib.error.URLError):
        return None
    return body if isinstance(body, dict) and body.get("quilt") == entry.id else None


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@dataclass
class Child:
    """A server the home started or adopted: its process (None when adopted), when it started, its starts again so far, and when the next is due."""

    proc: subprocess.Popen[bytes] | None
    started: float
    tries: int = 0
    again_at: float | None = None
    asked: float = 0.0


class Supervisor:
    """The quilts' servers the home runs.

    Parameters
    ----------
    extra : sequence of str, default ()
        Options added to every `loom serve` it starts (`--no-compile` in tests).
    """

    def __init__(self, extra: Sequence[str] = ()) -> None:
        from loom.render.serve import code_stamp

        self.extra = tuple(extra)
        self.children: dict[str, Child] = {}
        #: Quilts whose server could not start: (why, what it said last). `port-taken`, `refused` or `exited`.
        self.failed: dict[str, tuple[str, str]] = {}
        self.lock = threading.RLock()
        self.stamp = code_stamp()
        self.still_since = time.monotonic()
        self.stamp_asked = 0.0

    def state(self, entry: Entry) -> dict[str, Any]:
        """The quilt's state for the home page.

        Returns
        -------
        dict
            `state`: `missing` (its folder is gone), `failed` (with `why` and `said`), `running` (with `url`), `starting` or `stopped`.
        """
        with self.lock:
            if not Path(entry.root).is_dir():
                return {"state": "missing"}
            if entry.id in self.failed:
                why, said = self.failed[entry.id]
                return {"state": "failed", "why": why, "said": said}
            if ask(entry) is not None:
                return {"state": "running", "url": f"http://127.0.0.1:{entry.port}/"}
            child = self.children.get(entry.id)
            if child is not None and (child.again_at is not None or (child.proc and child.proc.poll() is None)):
                return {"state": "starting"}
            return {"state": "stopped"}

    def open(self, entry: Entry) -> dict[str, Any]:
        """Start the quilt's server on its port, or adopt the one already answering there; its state after (`state`)."""
        with self.lock:
            self.failed.pop(entry.id, None)
            if Path(entry.root).is_dir() and entry.id not in self.children:
                if ask(entry) is not None:
                    self.children[entry.id] = Child(None, time.monotonic())
                elif not free(entry.port):
                    self.failed[entry.id] = ("port-taken", "")
                else:
                    self._start(entry, 0)
            return self.state(entry)

    def _start(self, entry: Entry, tries: int) -> None:
        log = log_path(entry)
        log.parent.mkdir(parents=True, exist_ok=True)
        if log.exists() and log.stat().st_size > LOG_CAP:
            log.unlink()
        with open(log, "ab") as out:
            # -P: the quilt is no place to import loom from; a `loom.py` an agent wrote there would run in its place
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-P",
                    "-m",
                    "loom",
                    "serve",
                    "--port",
                    str(entry.port),
                    "--quilt",
                    entry.root,
                    *self.extra,
                ],
                cwd=folder(),
                env={**os.environ, "PYTHONSAFEPATH": "1"},
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        self.children[entry.id] = Child(proc, time.monotonic(), tries)

    def stop(self, entry: Entry) -> None:
        """Stop the quilt's server, whether the home started it or found it: SIGTERM, its own clean stop, then SIGKILL after `STOP_WAIT`."""
        with self.lock:
            child = self.children.pop(entry.id, None)
            self.failed.pop(entry.id, None)
            pid = None
            if child is not None and child.proc is not None and child.proc.poll() is None:
                pid = child.proc.pid
            elif ask(entry) is not None:
                from loom.render.serve import read_serve_json

                found = read_serve_json(Path(entry.root)).get("pid")
                pid = found if isinstance(found, int) else None
            if pid is None:
                return
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGTERM)
            end = time.monotonic() + STOP_WAIT
            while time.monotonic() < end:
                if child is not None and child.proc is not None and child.proc.poll() is not None:
                    return
                if (child is None or child.proc is None) and not _alive(pid):
                    return
                time.sleep(0.05)
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
            if child is not None and child.proc is not None:
                child.proc.wait()

    def stop_all(self, listed: Iterable[Entry]) -> None:
        """Stop every server the home runs, as it stops itself; what the person left open stays so on the list."""
        for entry in listed:
            if entry.id in self.children:
                self.stop(entry)

    def tick(self, listed: Iterable[Entry]) -> None:
        """Keep each quilt the person left open served: start one not running, start again one that died after its wait, and restart one that is stale once loom's code has been still for `SETTLE`."""
        from loom.render.serve import code_stamp

        now = time.monotonic()
        if now - self.stamp_asked >= ASK_EVERY:
            self.stamp_asked = now
            stamp = code_stamp()
            if stamp != self.stamp:
                self.stamp, self.still_since = stamp, now
        with self.lock:
            for entry in listed:
                if not entry.open or entry.id in self.failed or not Path(entry.root).is_dir():
                    continue
                child = self.children.get(entry.id)
                if child is None:
                    self.open(entry)
                    continue
                if child.proc is not None and child.proc.poll() is not None:
                    self._died(entry, child, now)
                elif now - child.asked >= ASK_EVERY:
                    child.asked = now
                    said = ask(entry)
                    if said is None:
                        if child.proc is None:
                            # an adopted server stopped by something else: started as if it had died
                            self.children.pop(entry.id)
                            self.open(entry)
                        continue
                    if now - child.started >= STEADY:
                        child.tries = 0
                    if said.get("stale") and now - self.still_since >= SETTLE:
                        self.stop(entry)
                        self._start(entry, 0)

    def _died(self, entry: Entry, child: Child, now: float) -> None:
        """A server that exited unasked: a refusal stays failed at once; a crash starts again after its wait, until `RETRIES` run out."""
        assert child.proc is not None
        if child.proc.returncode == REFUSED:
            self.children.pop(entry.id)
            self.failed[entry.id] = ("refused", tail(entry))
        elif child.again_at is None:
            if child.tries >= len(RETRIES):
                self.children.pop(entry.id)
                self.failed[entry.id] = ("exited", tail(entry))
            else:
                child.again_at = now + RETRIES[child.tries]
        elif now >= child.again_at:
            self._start(entry, child.tries + 1)
