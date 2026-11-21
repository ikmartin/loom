"""The samples of Review's and the Web's reads and writes that the viewer's sample data is (docs/specs/fixture/views/) are what loom answers now."""

from __future__ import annotations

import os
import runpy
from pathlib import Path

import pytest

LOOM_DIR = Path(__file__).resolve().parents[3]


@pytest.mark.tree
def test_the_checked_in_samples_are_what_loom_answers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A changed shape is a changed sample, so the viewer's data cannot drift from what loom sends (`scripts/regen views`)."""
    # the generator sets these for its own process; set here, they are put back after the test
    for var in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "LOOM_FIXED_TIME", "LOOM_PROGRESS"):
        monkeypatch.setenv(var, os.environ.get(var, ""))
    mod = runpy.run_path(str(LOOM_DIR / "scripts" / "gen_views.py"), run_name="not_main")
    made = {f"{name}.json": mod["render"](sample) for name, sample in mod["samples"](tmp_path).items()}
    have = {
        p.name: p.read_text(encoding="utf-8") for p in (LOOM_DIR.parent / "docs/specs/fixture/views").glob("*.json")
    }
    assert made == have, "run scripts/regen views"
