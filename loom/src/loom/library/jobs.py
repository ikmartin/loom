"""The person's library jobs: work a write starts that outlasts its answer, a digest whose source must first be compiled (`library-digest`), run one at a time in the publisher's process.

A job is the act of whoever asked for it: it runs in a copy of the context the write was asked in, so a job the person starts from the viewer runs as theirs (`identity`, the viewer's mark), in its own thread. Nothing of a job is kept: what it does is the files it writes and the records of its acts, and the library's generation moves when they land.
"""

from __future__ import annotations

import contextvars
import itertools
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

#: The jobs of each quilt this process serves, by its root.
_ALL: dict[Path, Jobs] = {}
_GUARD = threading.Lock()
_NUMBERS = itertools.count(1)


@dataclass
class Jobs:
    """One quilt's queue: jobs run in the order asked, one at a time, each in the context it was asked in."""

    root: Path
    _due: list[tuple[str, contextvars.Context, Callable[[], object]]] = field(default_factory=list)
    _cond: threading.Condition = field(default_factory=threading.Condition)
    _thread: threading.Thread | None = None
    _busy: str | None = None

    def submit(self, run: Callable[[], object]) -> str:
        """Queue `run`, to be run in a copy of the caller's context; its job's id."""
        job = f"job-{next(_NUMBERS)}"
        with self._cond:
            self._due.append((job, contextvars.copy_context(), run))
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._work, name="loom-library-jobs", daemon=True)
                self._thread.start()
            self._cond.notify_all()
        return job

    def idle(self, timeout: float) -> bool:
        """Wait until no job is due or running, at most `timeout` seconds; whether it got there."""
        with self._cond:
            return self._cond.wait_for(lambda: not self._due and self._busy is None, timeout)

    def _work(self) -> None:
        while True:
            with self._cond:
                if not self._due:
                    self._thread = None
                    return
                job, context, run = self._due.pop(0)
                self._busy = job
            try:
                context.run(run)
            except Exception as exc:  # noqa: BLE001 -- one job's failure is its own; what it wrote says how far it got
                import click

                click.echo(f"loom: a library job ended early: {type(exc).__name__}: {exc}"[:300], err=True)
            finally:
                with self._cond:
                    self._busy = None
                    self._cond.notify_all()


def jobs_of(root: Path) -> Jobs:
    """The queue of the quilt at `root`, made the first time it is asked for."""
    key = root.resolve()
    with _GUARD:
        if key not in _ALL:
            _ALL[key] = Jobs(key)
        return _ALL[key]
