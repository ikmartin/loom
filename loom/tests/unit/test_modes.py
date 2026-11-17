"""The modes are listed by one function, `loom.ai.layout.modes`, so that a quilt's own set of modes changes it and none of its callers."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import loom
from loom.ai import layout
from tests.helpers import refused
from tests.unit._quilts import demo


def test_nothing_but_the_one_function_reads_the_shipped_list() -> None:
    src = Path(loom.__file__).parent
    readers = sorted(
        p.relative_to(src).as_posix()
        for p in src.rglob("*.py")
        if re.search(r"\bMODES\b", p.read_text(encoding="utf-8"))
    )
    assert readers == ["ai/layout.py"]


def test_every_listing_follows_the_one_function(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With the function answering two modes, the index, the prompts, the mode files the layer writes, the modes each type is named by, and `loom ai mode` all say two."""
    from loom.ai.orient import mode_index, modes_using
    from loom.mcp.prompts import prompts

    q = demo(tmp_path)
    monkeypatch.setattr(layout, "modes", lambda root=None: ["quick", "referee"])
    assert [p.name for p in prompts(q)] == ["quick", "referee"]
    assert re.findall(r"^- \*\*(\w+)\*\*", mode_index(q), re.M) == ["quick", "referee"]
    assert sorted(rel for rel in layout.tracked_docs(q) if "/modes/" in rel) == [
        ".loom/ai/modes/quick.md",
        ".loom/ai/modes/referee.md",
    ]
    assert {m for named in modes_using(q).values() for m in named} <= {"quick", "referee"}
    refused("ai", "mode", "audit", cwd=q, code=2, match="the modes are quick, referee")
