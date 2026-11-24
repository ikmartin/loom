"""`loom upgrade` on a quilt an earlier loom made: its library carried into the node store and the layout stamped, so every other command opens it again; on a quilt in this loom's layout, nothing carried."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.library.carry import BIBLIOGRAPHY
from loom.library.store import node_ids
from loom.paths import FORMAT
from tests.helpers import json_of, ok, refused
from tests.unit.library._old import older_quilt


@pytest.fixture
def older(tmp_path: Path) -> Path:
    """A quilt as an earlier loom left it, in format 1, its library written by hand (`_old`)."""
    return older_quilt(tmp_path)


def test_every_other_command_refuses_the_quilt_and_says_upgrade(older: Path) -> None:
    refused("status", cwd=older, code=2, match="loom upgrade brings it forward")


def test_upgrade_carries_the_library_and_stamps_the_layout(older: Path) -> None:
    keys = (older / BIBLIOGRAPHY).read_text(encoding="utf-8").count("\n@")
    said = json_of("upgrade", "--json", cwd=older)
    carried = said["carried"]
    assert len(carried["references"]) >= 1 and carried["problems"] == [], carried
    assert said["verdict"].startswith("brought the quilt forward to format 2"), said["verdict"]
    assert (older / FORMAT).read_text(encoding="utf-8") == "2\n"
    assert not (older / BIBLIOGRAPHY).exists()
    assert len([n for n in node_ids(older) if n.endswith("-ref")]) == len(carried["references"]) >= keys
    ok("status", cwd=older)
    again = json_of("upgrade", "--json", cwd=older)
    assert again["carried"] is None, "a quilt in this loom's layout has nothing to carry"


def test_a_dry_run_carries_nothing_and_stamps_nothing(older: Path) -> None:
    before = {p.relative_to(older).as_posix(): p.read_bytes() for p in older.rglob("*") if p.is_file()}
    said = json_of("upgrade", "--dry-run", "--json", cwd=older)
    assert said["verdict"].startswith("would bring the quilt forward to format 2")
    assert len(said["carried"]["references"]) >= 1
    after = {p.relative_to(older).as_posix(): p.read_bytes() for p in older.rglob("*") if p.is_file()}
    assert {k: v for k, v in after.items() if not k.startswith(".loom/cache/")} == {
        k: v for k, v in before.items() if not k.startswith(".loom/cache/")
    }
