"""Lean tier on a project that requires Mathlib: what turning formalization on leaves lets the first fenced check pass, and the check records the replay's verdict before Lean's print, which shows Mathlib's notation.

Gated by `LOOM_LEAN_MATHLIB`, a Lake project whose `.lake/packages` holds Mathlib at the release loom pins with its build, and by Mathlib's cache on this machine (`MATHLIB_CACHE_DIR`, else `~/.cache/mathlib`), both read before a test's HOME is replaced. The packages are cloned into the test's quilt and Mathlib's build unpacked from the cache again, as `lake update` leaves it; nothing is fetched.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from loom import fence, paths
from loom.evidence.log import replay
from loom.formal import check, install, switch
from tests.unit._quilts import showcase

SOURCE = Path(os.environ["LOOM_LEAN_MATHLIB"]) if os.environ.get("LOOM_LEAN_MATHLIB") else None
CACHE = Path(
    os.environ.get("MATHLIB_CACHE_DIR") or Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "mathlib"
)


def _why_not() -> str | None:
    """Why this machine cannot run the tier's Mathlib test, or None."""
    if fence.lean_state() is not None:
        return "the fence is not up here"
    if SOURCE is None:
        return "LOOM_LEAN_MATHLIB names no Lake project with Mathlib's build"
    try:
        manifest = json.loads((SOURCE / "lake-manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return f"{SOURCE} has no lake-manifest.json"
    pinned = next((p.get("inputRev") for p in manifest.get("packages", []) if p.get("name") == "mathlib"), None)
    if pinned != install.MATHLIB or not (SOURCE / paths.LAKE_PACKAGES / "mathlib" / paths.LAKE_BUILD).is_dir():
        return f"{SOURCE} holds no build of Mathlib {install.MATHLIB}"
    if not CACHE.is_dir() or next(CACHE.glob("*.ltar"), None) is None:
        return f"no Mathlib cache at {CACHE}"
    return None


pytestmark = [pytest.mark.lean, pytest.mark.skipif(_why_not() is not None, reason=str(_why_not()))]

GAUSS = """import Loom
import Mathlib.Algebra.BigOperators.Intervals
import Mathlib.Tactic.Ring

open Finset

namespace Formal

@[loom "sh-0007"]
theorem gauss (n : ℕ) : 2 * ∑ i ∈ range (n + 1), i = n * (n + 1) := by
  induction n with
  | zero => simp
  | succ n ih => rw [sum_range_succ, mul_add, ih]; ring

end Formal
"""


def test_the_first_check_after_turning_on_passes_and_records_the_verdict_before_the_print(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Turning formalization on with Mathlib unpacked from its cache, as `lake update` unpacks it, builds nothing of the project, and the first fenced check finds Mathlib's build whole; the record of the replay's verdict comes first, its print missing, and then the record with Lean's print, in Mathlib's notation."""
    assert SOURCE is not None
    q = showcase(tmp_path)
    switch.turn_on(q)
    install.make_project(q)
    proj = install.project(q)
    (proj / "lake-manifest.json").write_bytes((SOURCE / "lake-manifest.json").read_bytes())
    (proj / paths.LAKE).mkdir()
    subprocess.run(["cp", "-cR", str(SOURCE / paths.LAKE_PACKAGES), str(proj / paths.LAKE_PACKAGES)], check=True)
    (proj / "Formal").mkdir()
    (proj / "Formal" / "Gauss.lean").write_text(GAUSS, encoding="utf-8")
    monkeypatch.setenv("MATHLIB_CACHE_DIR", str(CACHE))
    # the toolchain is installed, so elan never runs; `lake update` stands as what it leaves, Mathlib's build unpacked from the cache with no network
    monkeypatch.setattr(install, "find_elan", lambda: "/nowhere/elan")
    real = install._run

    def run(argv: list[str], cwd: Path, what: str, toolchain: str | None = None) -> Any:
        if argv[1:] == ["update"]:
            argv = [argv[0], "exe", "cache", "unpack!"]
        return real(argv, cwd, what, toolchain)

    monkeypatch.setattr(install, "_run", run)
    install.install(q)
    assert not (proj / paths.LAKE_BUILD).exists(), "turning formalization on built the project"
    done = check.check(q)
    assert done.written == ["sh-0007"] and done.errors == [] and done.unprinted == []
    verdict, printed = replay(q).about("label", "sh-0007", of="lean")
    assert verdict.get("replay")["exit"] == 0 and verdict.get("print") == "missing"
    assert [d["shown"] for d in verdict.get("declarations")] == [None]
    assert printed.get("print") is None and printed.get("replay") == verdict.get("replay")
    [row] = printed.get("declarations")
    assert row["shown"] == "theorem Formal.gauss (n : ℕ) : 2 * ∑ i ∈ Finset.range (n + 1), i = n * (n + 1)"
