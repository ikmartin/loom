"""`scripts/bench` takes its copy off loom's home list as it removes it, through the Python of the loom it times, since `loom init` and `loom serve` put the copy there and bench keeps the person's HOME."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest

from loom.app import registry

BENCH = Path(__file__).resolve().parents[4] / "scripts" / "bench"


@pytest.mark.parametrize("through", ["the loom script's own Python", "this Python, where no script is found"])
def test_bench_takes_its_copy_off_the_home_list_and_leaves_the_rest(tmp_path: Path, through: str) -> None:
    from loom.cli.quilt import write_minimal_quilt

    bench = runpy.run_path(str(BENCH), run_name="not_main")
    script = Path(sys.executable).parent / "loom"
    bench["LOOM"][:] = [str(script) if through.startswith("the loom") else str(tmp_path / "no-such-loom")]
    if through.startswith("the loom"):
        assert bench["loom_python"]() == script.read_text().split("\n", 1)[0].removeprefix("#!").split()[0]
    else:
        assert bench["loom_python"]() == sys.executable
    copy, mine = tmp_path / "loom-bench-x" / "q", tmp_path / "mine"
    for q in (copy, mine):
        write_minimal_quilt(q, "q")
        registry.remember(q)
    bench["forget"](copy)
    assert [Path(e.root) for e in registry.entries()] == [mine.resolve()]
    # a copy the list never named leaves the list unwritten
    listed = registry.folder() / "quilts.json"
    before = listed.stat().st_mtime_ns
    bench["forget"](copy)
    assert listed.stat().st_mtime_ns == before
