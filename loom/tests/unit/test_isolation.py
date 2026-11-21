"""The isolation every test runs in holds whatever the test does with its own `monkeypatch`, and whatever shell runs the suite."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from loom.identity import AGENT_MARKERS


def test_a_test_s_undo_takes_back_only_its_own_patches(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`monkeypatch.undo()` once reverted the isolation too, so the rest of a test ran in the shell's own HOME and with an agent's markers; the isolation is a patch of its own now."""
    monkeypatch.setenv("LOOM_TEST_PROBE", "1")
    monkeypatch.undo()
    assert "LOOM_TEST_PROBE" not in os.environ
    assert os.environ["HOME"] == str(home)
    assert not [m for m in AGENT_MARKERS if m in os.environ]


def test_no_test_starts_in_an_agent_s_shell() -> None:
    """A suite run by an agent and one run by CI give the same results: a test that means an agent's shell sets a marker itself."""
    assert not [m for m in AGENT_MARKERS if m in os.environ]
