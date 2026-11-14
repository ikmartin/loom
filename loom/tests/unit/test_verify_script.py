"""`scripts/verify` gives each step that runs tests its share of the run's budget of workers."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

VERIFY = Path(__file__).resolve().parents[3] / "scripts" / "verify"


@pytest.fixture(scope="module")
def verify() -> ModuleType:
    """The script as a module, loaded without leaving a `__pycache__` beside it."""
    loader = importlib.machinery.SourceFileLoader("loom_verify_script", str(VERIFY))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    # a dataclass looks its own module up by name while it is being defined
    sys.modules[loader.name] = module
    writes, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = writes
    return module


def shared(verify: ModuleType, tier: str, workers: int) -> dict[str, Any]:
    return {s.name: s for s in verify.share_workers([s for s in verify.STEPS if tier in s.tiers], workers)}


def test_a_budget_caps_pytest_and_vitest_in_the_everyday_lane(verify: ModuleType) -> None:
    steps = shared(verify, "fast", 3)
    assert steps["pytest unit"].env["PYTEST_XDIST_AUTO_NUM_WORKERS"] == "3"
    assert "--maxWorkers=3" in steps["vitest"].cmd
    assert all(s.env["VERIFY_WORKERS"] == "3" for s in steps.values())


def test_pytest_and_the_browser_suites_divide_a_budget_when_they_run_together(verify: ModuleType) -> None:
    steps = shared(verify, "full", 4)
    for name in ("pytest unit", "pytest tree", "pytest tex"):
        assert steps[name].env["PYTEST_XDIST_AUTO_NUM_WORKERS"] == "2", name
    for name in ("e2e", "write", "reading"):
        cmd = steps[name].cmd
        assert cmd[cmd.index("--workers") + 1] == "1", name
    # the figure script keeps its one worker
    assert "--workers" not in steps["shots"].cmd
