"""What a build makes of a text TeX did not make: TeX's own refusal, warned of once, where it was made; a failure of the machine's, which the snippet cache does not remember, noted `uses.PASSING`, so that nothing made with it outlives the build."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.render.fragments import FragmentRenderer, RenderPlan
from loom.render.uses import PASSING, noting
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan

#: (error, made before) -> (passing, warned)
FAILURES = {
    "no TeX run here": (("TeX is not run here", False), (True, False)),
    "no TeX4ht": (("make4ht is not installed", False), (True, False)),
    "a run that stopped saying nothing": (("TeX4ht made no page: it said nothing", False), (True, False)),
    "a run out of time": (("make4ht timed out after 600s", False), (True, True)),
    "TeX's refusal": (("Undefined control sequence.", False), (False, True)),
    "TeX's refusal, remembered": (("Undefined control sequence.", True), (False, False)),
}


@pytest.mark.parametrize("failure", sorted(FAILURES))
def test_a_failure_is_passing_only_when_it_is_the_machines(tmp_path: Path, failure: str) -> None:
    (tmp_path / "drafting").mkdir()
    (tmp_path / "config.toml").write_text('[quilt]\nmain = "drafting/main.tex"\nprefix = "ab"\n')
    (tmp_path / "drafting" / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\nWords.\n\\end{document}\n"
    )
    plan = RenderPlan(scan(load_quilt(tmp_path)), {}, tmp_path / "blocks", tmp_path / "svg")
    (error, cached), (passing, warned) = FAILURES[failure]
    with noting() as noted:
        FragmentRenderer(plan)._refused("drafting/main.tex", "Words.", error, cached)
    assert (PASSING in noted, bool(plan.diagnostics)) == (passing, warned)
