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


def test_python_runs_every_uv_step_under_it_in_an_environment_of_its_own(
    verify: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[list[str]] = []

    def found(cmd: list[str], **_: object) -> Any:
        asked.append(cmd)
        return type("Done", (), {"returncode": 0, "stdout": "/somewhere/python3.11\n"})()

    monkeypatch.setattr(verify.subprocess, "run", found)
    steps = {s.name: s for s in verify.under_python([s for s in verify.STEPS if "fast" in s.tiers], "3.11")}
    assert asked == [["uv", "python", "find", "3.11"]]
    for name in ("ruff", "mypy", "pytest unit", "work queue"):
        assert steps[name].env["UV_PYTHON"] == "3.11"
        assert steps[name].env["UV_PYTHON_DOWNLOADS"] == "never"
        assert steps[name].env["UV_PROJECT_ENVIRONMENT"] == str(verify.ROOT / "loom" / ".venv-3.11")
    assert "UV_PYTHON" not in steps["vitest"].env
    assert "UV_PYTHON" not in steps["hard wrap"].env


def test_python_refuses_a_version_uv_cannot_find_here_rather_than_download_one(
    verify: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(verify.subprocess, "run", lambda *a, **k: type("Done", (), {"returncode": 2, "stdout": ""})())
    with pytest.raises(SystemExit, match="no Python 3.10 on this machine"):
        verify.under_python(list(verify.STEPS), "3.10")
    with pytest.raises(SystemExit, match="X.Y"):
        verify.under_python(list(verify.STEPS), "3")


def test_wide_font_reaches_the_three_suites_and_not_the_build(verify: ModuleType) -> None:
    steps = {s.name: s for s in verify.in_wide_font([s for s in verify.STEPS if "full" in s.tiers])}
    assert [n for n, s in steps.items() if s.env.get("VIEWER_WIDE_FONT")] == ["e2e", "write", "reading"]
