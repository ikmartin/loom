"""The install and the check as the server runs them for the viewer: one at a time for a quilt, in a thread of their own, with what each last said kept in memory for `formal-state`."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Job:
    """What the server is doing for formalization in one quilt, or did last: `install` or `check`, `running`, `done` or `failed`, the step it is on or what it found."""

    kind: str
    state: str = "running"
    said: str = ""
    started: float = field(default_factory=time.time)
    found: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "state": self.state, "said": self.said, "found": self.found}


_JOBS: dict[Path, Job] = {}
_LOCK = threading.Lock()


def current(root: Path) -> Job | None:
    """The quilt's job now, or the last one it ran in this server's life."""
    with _LOCK:
        return _JOBS.get(root.resolve())


def start(root: Path, kind: str, work: Callable[[Callable[[str], None]], dict[str, Any]]) -> Job | None:
    """Run `work` in a thread for the quilt at `root`, which it tells each step through the callable it is given; None, starting nothing, while another runs there.

    `work` answers what it found, kept on the job when it is done; an exception it raises is kept as what the job said, and the job failed. Review's and the Web's reads see the records it writes by the log itself (`evidence.memo`), so nothing is rebuilt after it.
    """
    key = root.resolve()
    with _LOCK:
        running = _JOBS.get(key)
        if running is not None and running.state == "running":
            return None
        job = _JOBS[key] = Job(kind)

    def tell(step: str) -> None:
        job.said = step

    def run() -> None:
        try:
            job.found = work(tell)
            job.state = "done"
        except Exception as exc:  # noqa: BLE001 -- what failed is shown to the person, and the server goes on
            job.said, job.state = str(exc), "failed"

    threading.Thread(target=run, name=f"loom-formal-{kind}", daemon=True).start()
    return job
