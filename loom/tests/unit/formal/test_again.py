"""Loom's check run again on its own once a Lean record goes stale, with the fenced steps standing in: only where formalization is on here and the Lean has been still, once for each state of the Lean and the texts it states, and never while another job runs."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from loom import fence
from loom.evidence.log import replay
from loom.formal import again, check, install, jobs, switch
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan
from tests.unit.formal.test_check import (
    SATURATION,
    _probe,
    _status,
    _steps,
)

LATER = again.QUIET + 5


def _looker(q: Path) -> again.Again:
    return again.Again(q, lambda: scan(load_quilt(q)))


def _settled(q: Path) -> jobs.Job:
    for _ in range(200):
        job = jobs.current(q)
        if job is not None and job.state != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("the job never ended")


def _changed(q: Path, words: str) -> None:
    (install.project(q) / SATURATION).write_text(f"import Loom\n-- {words}\n", encoding="utf-8")


def test_nothing_recorded_or_nothing_stale_runs_nothing(quilt: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ran = _steps(monkeypatch, _probe())
    looker = _looker(quilt)
    assert not looker.look(time.time() + LATER) and ran == []
    check.check(quilt)
    ran.clear()
    assert not looker.look(time.time() + LATER) and ran == []


def test_a_changed_lean_file_is_checked_again_once_it_has_been_still(
    quilt: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The record stops standing when its Lean changes; loom waits for the Lean to be still, then checks, and the result's record stands again."""
    _steps(monkeypatch, _probe())
    check.check(quilt)
    _changed(quilt, "a proof shortened")
    assert _status(quilt, "sh-0007").lean == "rerun"
    looker = _looker(quilt)
    assert not looker.look(time.time())  # just changed: an agent may still be at work
    assert looker.look(time.time() + LATER)
    job = _settled(quilt)
    assert (job.kind, job.state) == ("check", "done") and "sh-0007" in job.found["written"]
    assert _status(quilt, "sh-0007").lean == "unattested"
    assert not looker.look(time.time() + 2 * LATER)


def test_a_changed_statement_is_checked_again(quilt: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A statement that changed in the paper leaves its record on a text that is gone; loom checks again and records on the new text."""
    _steps(monkeypatch, _probe())
    check.check(quilt)
    node = quilt / "drafting" / "nodes" / "sh-0007.tex"
    node.write_text(node.read_text(encoding="utf-8").replace("some integer $n \\neq 0$", "some integer $n$"), encoding="utf-8")  # fmt: skip
    looker = _looker(quilt)
    assert again.stale(quilt, scan(load_quilt(quilt)))[0] == ["sh-0007"]
    looker.look(time.time())
    assert looker.look(time.time() + LATER)
    _settled(quilt)
    assert _status(quilt, "sh-0007").lean == "unattested"


def test_a_state_already_checked_is_not_checked_again(quilt: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A record that cannot stand again, its marker gone from the Lean, is checked once and not over and over, even by a server started again; a new change is checked."""
    _steps(monkeypatch, _probe())
    check.check(quilt)
    probe = _probe()
    probe["declarations"] = [d for d in probe["declarations"] if d["name"] != "Formal.cycleLattice_saturated._loom"]
    ran = _steps(monkeypatch, probe)
    _changed(quilt, "the marker removed")
    looker = _looker(quilt)
    looker.look(time.time())
    assert looker.look(time.time() + LATER)
    _settled(quilt)
    assert again.stale(quilt, scan(load_quilt(quilt)))[0] == ["sh-0007"]
    count = len(ran)
    assert not looker.look(time.time() + 2 * LATER)
    restarted = _looker(quilt)
    restarted.look(time.time())
    assert not restarted.look(time.time() + LATER) and len(ran) == count
    _changed(quilt, "edited again")
    restarted.look(time.time())
    assert restarted.look(time.time() + LATER)
    _settled(quilt)


@pytest.mark.parametrize("why", ["off", "fence", "running"])
def test_off_here_with_no_fence_or_while_a_job_runs_nothing_starts(quilt: Path, monkeypatch: pytest.MonkeyPatch, why: str) -> None:  # fmt: skip
    """Turned off on this machine, nothing runs, which is what keeps a co-author's quilt from running Lean; with the fence down the check could not run fenced; and one job at a time."""
    ran = _steps(monkeypatch, _probe())
    check.check(quilt)
    _changed(quilt, "changed")
    ran.clear()
    if why == "off":
        switch.turn_off(quilt)
    elif why == "fence":
        monkeypatch.setattr(fence, "lean_state", lambda: "nested")
    else:
        held: list[Any] = []
        jobs.start(quilt, "install", lambda tell: held.append(time.sleep(0.5)) or {})
    looker = _looker(quilt)
    looker.look(time.time())
    assert not looker.look(time.time() + LATER) and ran == []
    assert len(replay(quilt).of_kind("lean")) == 3
    if why == "running":
        _settled(quilt)
