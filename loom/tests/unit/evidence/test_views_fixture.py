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
    have = mod["mine"](LOOM_DIR.parent / "docs/specs/fixture/views")
    assert made == have, "run scripts/regen views"


def test_the_step_writes_and_clears_its_own_samples_and_leaves_another_generators(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Library's samples are another generator's, in the same folder: either may run first and neither wipes the other's."""
    for var in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "LOOM_FIXED_TIME", "LOOM_PROGRESS"):
        monkeypatch.setenv(var, os.environ.get(var, ""))
    mod = runpy.run_path(str(LOOM_DIR / "scripts" / "gen_views.py"), run_name="not_main")
    out = tmp_path / "views"
    out.mkdir()
    (out / "library-works.json").write_text('{"another": "generator"}\n', encoding="utf-8")
    (out / "review-gone.json").write_text("{}\n", encoding="utf-8")
    assert mod["main"](False, out) == 0
    assert (out / "library-works.json").read_text(encoding="utf-8") == '{"another": "generator"}\n'
    assert not (out / "review-gone.json").exists() and (out / "review-list.json").is_file()
    # a check reads its own files alone, so another generator's file never makes it stale
    assert mod["main"](True, out) == 0


def test_no_step_of_the_regeneration_writes_inside_a_folder_a_later_step_writes() -> None:
    """A step may make its folder again from nothing, as the fixture's refresh does, so the views' samples are written after it and a whole `scripts/regen` leaves them."""
    steps = runpy.run_path(str(LOOM_DIR.parent / "scripts" / "regen"), run_name="not_main")["STEPS"]
    for i, early in enumerate(steps):
        for late in steps[i + 1 :]:
            inside = [(e, w) for e in early.paths for w in late.paths if e.startswith(w.rstrip("/") + "/")]
            assert not inside, (
                f"{early.name} writes {inside[0][0]}, inside {inside[0][1]}, which {late.name} writes after it"
            )
