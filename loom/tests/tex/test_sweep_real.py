"""TeX tier: what the sweep keeps is everything the build as it stands was made from, so a build of every fragment from the swept cache alone, with no TeX, publishes the same site."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from loom.lifetimes import FRESH, sweep
from loom.paths import BUILD_INDEX, SITE
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan
from tests.helpers import edit, run
from tests.unit._quilts import showcase


def _site(q: Path) -> dict[str, bytes]:
    out = {}
    for p in sorted((q / SITE).rglob("*")):
        if p.is_file():
            data = p.read_bytes()
            if p.name == "manifest.json":
                manifest = json.loads(data)
                manifest.pop("generated", None)
                data = json.dumps(manifest, sort_keys=True).encode()
            out[p.relative_to(q / SITE).as_posix()] = data
    return out


@pytest.mark.tex
def test_a_cache_swept_after_an_edit_still_makes_every_fragment_without_tex(tmp_path: Path) -> None:
    """Pages compiled, a node edited after its page was made (so its document's page is stale for it), built and swept: every fragment is made again from the cache alone and comes out the same."""
    q = showcase(tmp_path)
    for doc in scan(load_quilt(q)).masters:
        run("compile", doc, "--html", cwd=q)
    run("build", cwd=q)
    edit(q / "drafting/nodes/sh-0006.tex", "\\label{sh-0006}\n", "\\label{sh-0006}\nMoreover $x^2 \\geq 0$ here. ")
    run("build", cwd=q)
    swept = sweep(q, scan(load_quilt(q)), now=time.time() + FRESH + 60)
    assert swept.files > 0 and not swept.failed
    before = _site(q)
    (q / BUILD_INDEX).unlink()
    run("build", "--no-compile", cwd=q)
    assert _site(q) == before
