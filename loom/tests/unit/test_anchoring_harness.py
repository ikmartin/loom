"""The anchoring harness runs on today's loom: it files annotations and suggested edits on a paper, applies a co-author's edits, and says of every record whether it is on the right block, a wrong one, detached or lost.

The harness (`tests/tools/anchoring/`, from the v0.1 study) is how the records' following of the text is measured on real papers, and it calls loom's own writers and scan, so it breaks when they move. This runs it small, on the synthetic quilt's source and on a paper that is no quilt, and asserts that it ran and judged every record. It asserts nothing about how many land right: today some land on the wrong block, which is the fault the harness exists to measure.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools" / "anchoring"
OUTCOMES = {"right", "wrong", "detached", "lost"}

PAPER = r"""\documentclass{article}
\usepackage{amsthm}
\newtheorem{theorem}{Theorem}
\newtheorem{lemma}{Lemma}
\begin{document}
\section{Widgets}
A widget is a finite set with an involution, and every statement below is about one fixed widget.

\begin{lemma}\label{lem:orbits}
Every orbit of the involution on a finite widget has one or two points and no more than that.
\end{lemma}
\begin{proof}
The involution applied twice is the identity, so an orbit holds a point and its image only.
\end{proof}

\begin{theorem}
The number of fixed points of a finite widget has the same parity as the number of its points.
\end{theorem}
\begin{proof}
Count the points orbit by orbit and use the lemma above for the size of each orbit in turn.
\end{proof}
\end{document}
"""


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """The harness's runner, loaded from the tools directory as its own scripts load each other."""
    monkeypatch.syspath_prepend(str(TOOLS))
    monkeypatch.delitem(sys.modules, "harness", raising=False)
    spec = importlib.util.spec_from_file_location("anchoring_run", TOOLS / "run.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def judged(results: Path, scenarios: list[str]) -> int:
    """How many records the harness filed, having checked that every one was given an outcome in every scenario."""
    data = json.loads(results.read_text(encoding="utf-8"))
    assert data["targets"] and data["records"], "the harness found nothing to file a record on"
    assert sorted(data["rows"]) == sorted(scenarios)
    for name, rows in data["rows"].items():
        assert [r for r in rows if "error" in r] == [], (name, rows)
        assert {r["outcome"] for r in rows} <= OUTCOMES, name
        assert len(rows) == len(data["records"]), name
    return len(data["records"])


def test_the_harness_judges_every_record_it_files_on_a_committed_quilt(run: ModuleType, tmp_path: Path) -> None:
    scenarios = ["insert-above", "light-edit"]
    written = run.run(tmp_path / "out", [str(run.SOURCES / "synthetic")], scenarios)
    assert judged(written["synthetic"], scenarios) >= 8


def test_a_paper_that_is_no_quilt_is_run_as_the_smallest_quilt_there_is(run: ModuleType, tmp_path: Path) -> None:
    paper = tmp_path / "widgets"
    paper.mkdir()
    (paper / "widgets.tex").write_text(PAPER, encoding="utf-8")
    scenarios = ["insert-above", "rename-file"]
    written = run.run(tmp_path / "out", [str(paper)], scenarios)
    assert (tmp_path / "out" / "quilts" / "widgets" / "config.toml").is_file() and not (paper / "config.toml").exists()
    assert judged(written["widgets"], scenarios) >= 4
