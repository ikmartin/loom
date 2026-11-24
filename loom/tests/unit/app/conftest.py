"""What the home's tests share: a stand-in viewer every server they start serves, ports of their own, and an end to every server they started."""

from __future__ import annotations

import json
import os
import signal
import socket
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from loom.app import registry, supervise
from loom.render.serve import read_serve_json
from tests.helpers import PATIENCE


def until(done: Callable[[], bool], what: str) -> None:
    """Wait for `done`, at most `PATIENCE`."""
    end = time.monotonic() + PATIENCE
    while time.monotonic() < end:
        if done():
            return
        time.sleep(0.1)
    raise AssertionError(f"waited {PATIENCE} s for {what}")


@pytest.fixture
def bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A stand-in viewer, version 1, which every server the test starts serves."""
    b = tmp_path / "bundle"
    (b / "_app").mkdir(parents=True)
    (b / "index.html").write_text("<p>viewer</p>")
    (b / "_app" / "version.json").write_text(json.dumps({"version": "1"}))
    monkeypatch.setenv("LOOM_ARRAS_BUNDLE", str(b))
    return b


@pytest.fixture
def ports(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Quilts' ports from a free one of the system's, away from every other test's; any quilt's server still answering at the end is stopped outright."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        monkeypatch.setattr(registry, "FIRST_PORT", s.getsockname()[1])
    yield
    for entry in registry.entries():
        pid = read_serve_json(Path(entry.root)).get("pid")
        if isinstance(pid, int) and supervise.ask(entry) is not None:
            os.kill(pid, signal.SIGKILL)
