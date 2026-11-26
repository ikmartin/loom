"""`loom doctor`'s line for Lean: off it says only whether the quilt carries a project; on, what the check needs that is missing, as a warning with what fixes it, and once all is there when loom last checked and what came of it, with how many results' Lean changed since."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from loom import fence
from loom.doctor import OK, WARN, check_lean
from loom.formal import check, install, switch
from tests.unit._quilts import showcase
from tests.unit.formal.test_check import SATURATION, _probe, _steps, quilt  # noqa: F401 -- `quilt` is a fixture


def test_off_it_says_whether_the_quilt_carries_a_project(tmp_path: Path) -> None:
    q = showcase(tmp_path)
    item = check_lean(q)
    assert (item.status, item.detail, item.shown) == (OK, "formalization is off here", False)
    install.make_project(q)
    item = check_lean(q)
    assert item.status == OK and item.shown and "a Lean project in lean/, of which loom runs nothing" in item.detail


def test_on_it_warns_of_what_the_check_needs_and_says_what_fixes_it(quilt: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    item = check_lean(quilt)
    assert item.status == OK and item.detail.endswith("not checked yet on this machine")
    assert item.detail.startswith(f"on: the project in lean/, {install.TOOLCHAIN}")
    monkeypatch.setattr(fence, "lean_state", lambda: "nested")
    item = check_lean(quilt)
    assert (item.status, item.detail) == (WARN, "on, but loom cannot check Lean here: the fence is not up (nested)")
    shutil.rmtree(install.toolchain_folder(install.TOOLCHAIN))
    item = check_lean(quilt)
    assert (item.status, item.remedy) == (WARN, "loom formal on installs it") and install.TOOLCHAIN in item.detail
    (install.project(quilt) / "lakefile.toml").unlink()
    assert (check_lean(quilt).status, check_lean(quilt).remedy) == (WARN, "loom formal on makes it")


def test_on_it_says_when_loom_last_checked_and_how_many_results_lean_changed_since(quilt: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    _steps(monkeypatch, _probe())
    check.check(quilt)
    item = check_lean(quilt)
    assert item.status == OK and "; last checked " in item.detail and "(3 recorded, 0 as before)" in item.detail
    assert item.extra["stale"] == 0
    (install.project(quilt) / SATURATION).write_text("import Loom\n-- changed\n", encoding="utf-8")
    item = check_lean(quilt)
    assert item.detail.endswith("; 3 of 3 results' Lean changed since, which loom checks again while it serves")
    # a refused check is a warning, with what it said
    monkeypatch.setattr(install, "marker_is_loom_s", lambda root: False)
    with pytest.raises(check.Refused):
        check.check(quilt)
    item = check_lean(quilt)
    assert item.status == WARN and "was refused: lean/Loom.lean is not loom's marker module" in item.detail
    switch.turn_off(quilt)
    assert check_lean(quilt).status == OK
