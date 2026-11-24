"""The unasked job as `loom serve` runs it: after each build, the works the library's stubs name, each tried once."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from loom.render.serve import ServeSession
from tests.unit.library.test_unasked import given_source, quilt, tried


def test_the_server_tries_each_work_its_stubs_name_once_and_a_rebuild_tries_none_again(
    serve: Callable[..., ServeSession], tmp_path: Path
) -> None:
    root, refs = quilt(tmp_path)
    smith, jones, arden = refs["Smi24"], refs["Jon19"], refs["Arx24"]
    given_source(root, smith, tmp_path)
    s = serve(root, unasked=True)
    assert s.unasked is not None and s.unasked.idle(60)
    outcomes = {ref: [(a["outcome"], a["why"]) for a in tried(root, ref)] for ref in (smith, jones, arden)}
    assert outcomes == {
        smith: [("surveyed", "no-pdf")],
        jones: [("waiting", "no-document")],
        arden: [],
    }, "the arXiv work waits for the network, which this quilt has not allowed"
    s.rebuild()
    assert s.unasked.idle(60)
    assert {ref: len(tried(root, ref)) for ref in (smith, jones, arden)} == {smith: 1, jones: 1, arden: 0}
