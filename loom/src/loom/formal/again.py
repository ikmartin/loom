"""Loom's check run again on its own when a `lean` record goes stale: decision 10 of plan 0.32 has loom check the Lean again when the statement or a definition changes, and decision 16 lets it, since the person turned on, on this machine, a feature whose words say it does (`loom formal on`, Settings › Lean).

While `loom serve` runs, `Again` looks every `INTERVAL` seconds. It starts the check as `formal-check` does when formalization is on for the quilt here, the project and the fence are there, nothing runs for the quilt (`jobs`), some result a record once stated has, on a text it has now, no record that still stands (`stale`), and the Lean, the project's own build and those texts have been still for `QUIET` seconds, so an agent building or a person typing a statement is not raced. Each such state is checked once (`switch.checked`): a record that can never stand again, its marker gone, is not checked over and over, and a server started again over the same Lean runs nothing.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

#: Seconds between looks.
INTERVAL = 5.0
#: Seconds the Lean and the texts it states must be still before loom checks on its own.
QUIET = 60.0


def stale(root: Path, scanned: Any) -> tuple[list[str], list[str]]:
    """The results some `lean` record once stated that have, on a text they have now, no record still standing (`status.files_unchanged`), by name; and every text now of the results records state, as `kind:name@hash`, which `state` digests. A result with no text now, gone from the quilt, is neither."""
    from loom.evidence import log
    from loom.evidence.status import files_unchanged
    from loom.formal.check import resolver

    records: dict[tuple[str, str], list[Any]] = {}
    for r in log.replay(root).of_kind("lean"):
        if r.on is not None:
            records.setdefault(r.on.key, []).append(r)
    if not records:
        return [], []
    standing = files_unchanged(root)
    resolve = resolver(root, scanned)
    due: list[str] = []
    texts: list[str] = []
    for (kind, name), recs in sorted(records.items()):
        now = {s.hash for s in resolve(name) if s.key == (kind, name)}
        texts += sorted(f"{kind}:{name}@{h}" for h in now)
        if any(not any(r.on.hash == h and standing(r) for r in recs) for h in now):
            due.append(name)
    return due, texts


def _project_files(proj: Path) -> list[Path]:
    """The project's modules and the files saying what it builds, as the check reads them."""
    from loom.formal.check import CONFIG, modules

    return [proj / p for p in modules(proj).values()] + [proj / p for p in CONFIG]


def newest(proj: Path) -> float:
    """When the project's sources or its own build last changed: the newest modification time among its modules, its configuration and every file of `.lake/build`, which an agent's `lake build` writes; 0 for none."""
    from loom.paths import LAKE_BUILD

    times = [0.0]
    for p in _project_files(proj):
        try:
            times.append(p.stat().st_mtime)
        except OSError:
            continue
    for here, _dirs, names in os.walk(proj / LAKE_BUILD):
        for name in names:
            try:
                times.append((Path(here) / name).stat().st_mtime)
            except OSError:
                continue
    return max(times)


def state(proj: Path, texts: list[str]) -> str:
    """One digest of what a check would read: the hash of each of the project's modules and configuration files, and the texts now of the results records state."""
    files = {}
    for p in _project_files(proj):
        try:
            files[p.relative_to(proj).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        except OSError:
            files[p.relative_to(proj).as_posix()] = None
    return "sha256:" + hashlib.sha256(json.dumps([files, texts], sort_keys=True).encode("utf-8")).hexdigest()


class Again:
    """`loom serve`'s look at whether the quilt's Lean records went stale, on a thread of its own, starting loom's check when one did (the module's rules); `scan` gives the scan of the server's last publication, None before the first, and nothing is looked at until there is one."""

    def __init__(self, root: Path, scan: Callable[[], Any], interval: float = INTERVAL, quiet: float = QUIET) -> None:
        self.root = root
        self.scan = scan
        self.interval = interval
        self.quiet = quiet
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        #: The state last seen and since when, so a state is checked only once it has held for `quiet` seconds.
        self._seen: tuple[str, float] = ("", 0.0)
        #: What `stale` and `state` last answered, by what they read: the scan, the log's and the project's files as they stood.
        self._read: tuple[Any, tuple[list[str], str]] | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="loom-formal-again", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval * 3)

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.look()
            except Exception as exc:  # noqa: BLE001 -- a look that fails is said, and the next may do better
                print(f"loom serve: looking whether the Lean went stale failed: {exc}", file=sys.stderr)

    def look(self, now: float | None = None) -> bool:
        """Look once, and start the check where the module's rules say; whether it started one."""
        from loom import fence
        from loom.formal import install, jobs, switch

        root = self.root
        if not switch.is_on(root):
            return False
        proj = install.project(root)
        if not (proj / "lakefile.toml").is_file() or fence.lean_state() is not None:
            return False
        running = jobs.current(root)
        if running is not None and running.state == "running":
            return False
        scanned = self.scan()
        if scanned is None:
            return False
        due, held = self._stale(proj, scanned)
        if not due:
            return False
        at = time.time() if now is None else now
        if held != self._seen[0]:
            self._seen = (held, at)
        if at - max(self._seen[1], newest(proj)) < self.quiet or held == switch.checked(root):
            return False
        switch.remember_checked(root, held)
        return jobs.start_check(root) is not None

    def _stale(self, proj: Path, scanned: Any) -> tuple[list[str], str]:
        """`stale`'s results and the `state` of their texts, read again only once the scan, the evidence log or one of the project's files has changed since the last look."""
        from loom.evidence.log import log_path

        def stat(p: Path) -> tuple[int, int] | None:
            try:
                st = p.stat()
            except OSError:
                return None
            return (st.st_mtime_ns, st.st_size)

        read = (id(scanned), stat(log_path(self.root)), tuple(stat(p) for p in _project_files(proj)))
        if self._read is None or self._read[0] != read:
            due, texts = stale(self.root, scanned)
            self._read = (read, (due, state(proj, texts) if due else ""))
        return self._read[1]
