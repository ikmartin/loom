"""A quilt holding the spec's nine nodes, for the store's, the index's and the tags' tests: a folder with `.loom/library/nodes/` and nothing else loom needs here."""

from __future__ import annotations

import os
import time
from pathlib import Path

from loom.paths import LIBRARY_NODES
from tests.unit.library._examples import fixtures


def quilt(tmp_path: Path, *, aged: bool = False) -> Path:
    """A quilt with the nine files; `aged` dates them an hour back, so an index made now has no reason to read them twice."""
    root = tmp_path / "q"
    nodes = root / LIBRARY_NODES
    nodes.mkdir(parents=True)
    for name, data in fixtures().items():
        (nodes / name).write_bytes(data)
        if aged:
            then = time.time() - 3600
            os.utime(nodes / name, (then, then))
    return root
