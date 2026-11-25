"""The person's library jobs (`library.jobs`): one at a time, in the order asked, each as whoever asked for it."""

from __future__ import annotations

import contextvars
import threading
from pathlib import Path

from loom.library.jobs import jobs_of

#: Stands for the viewer's mark (`identity`), which a write sets in the thread that serves it.
ASKER: contextvars.ContextVar[str] = contextvars.ContextVar("asker", default="nobody")


def test_a_job_runs_as_whoever_asked_for_it(tmp_path: Path) -> None:
    seen: list[str] = []
    token = ASKER.set("the person at the viewer")
    try:
        jobs_of(tmp_path).submit(lambda: seen.append(ASKER.get()))
    finally:
        ASKER.reset(token)
    assert jobs_of(tmp_path).idle(10) and seen == ["the person at the viewer"], (
        "the context crosses into the job's thread"
    )


def test_jobs_run_one_at_a_time_in_the_order_asked(tmp_path: Path) -> None:
    order: list[int] = []
    together = threading.Lock()

    def job(n: int) -> None:
        assert together.acquire(blocking=False), "two jobs at once"
        order.append(n)
        together.release()

    jobs = jobs_of(tmp_path)
    for n in range(5):
        jobs.submit(lambda n=n: job(n))
    assert jobs.idle(10) and order == [0, 1, 2, 3, 4]
