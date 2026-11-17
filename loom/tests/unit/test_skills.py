"""A thin skill per mode for each app that reads a project's skills, written with the agent layer and again by `loom upgrade`, from the quilt's modes as `modes` lists them."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loom.ai import layout
from loom.ai.layout import modes
from tests.helpers import ok


def bare(tmp_path: Path) -> Path:
    ok("init", str(tmp_path / "q"), "--yes", cwd=tmp_path)
    return tmp_path / "q"


def skills(q: Path, where: str) -> list[str]:
    return sorted(p.parent.name for p in (q / where).glob("*/SKILL.md"))


def test_ai_init_writes_a_skill_per_mode_for_claude_code_and_codex(tmp_path: Path) -> None:
    from loom.ai.orient import fits

    q = bare(tmp_path)
    ok("ai", "init", cwd=q)
    want = sorted(f"loom-{m}" for m in modes(q))
    assert skills(q, ".claude/skills") == want and skills(q, ".agents/skills") == want
    text = (q / ".claude/skills/loom-referee/SKILL.md").read_text()
    head, body = text.split("\n---\n", 1)
    assert head.splitlines()[:2] == ["---", "name: loom-referee"]
    # a YAML double-quoted scalar, which JSON's string is
    assert (
        json.loads(head.splitlines()[2].removeprefix("description: "))
        == f"Work in loom's referee mode: {fits(q, 'referee')}"
    )
    assert "`loom_ai_mode` with the name `referee`" in body and "loom ai mode referee" in body
    assert "loom_ai_orient" in body


def test_an_app_set_up_alone_gets_its_own_skills_alone(tmp_path: Path) -> None:
    from loom.render.endpoints.agents import HANDLERS

    q = bare(tmp_path)
    got = HANDLERS["agents-setup"](q, "agents-setup", {"app": "claude-code", "author": "A. Author"})
    assert ".claude/skills/loom-quick/SKILL.md" in got["written"]
    assert len(skills(q, ".claude/skills")) == len(modes(q)) and not (q / ".agents").exists()


def test_upgrade_writes_them_again_and_takes_away_one_whose_mode_is_gone(tmp_path: Path) -> None:
    q = bare(tmp_path)
    ok("ai", "init", cwd=q)
    (q / ".claude/skills/loom-quick/SKILL.md").unlink()
    gone = q / ".claude/skills/loom-brainstorm"
    gone.mkdir()
    (gone / "SKILL.md").write_text("---\nname: loom-brainstorm\n---\n")
    mine = q / ".claude/skills/my-own/SKILL.md"
    mine.parent.mkdir()
    mine.write_text("---\nname: my-own\n---\nThe person's.\n")
    ok("upgrade", cwd=q)
    assert skills(q, ".claude/skills") == sorted([*(f"loom-{m}" for m in modes(q)), "my-own"])
    assert not gone.exists() and mine.read_text() == "---\nname: my-own\n---\nThe person's.\n"


def test_the_skills_follow_the_quilts_modes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A change to the set of modes is a change to `modes` alone, and the next upgrade writes the skills to match."""
    q = bare(tmp_path)
    ok("ai", "init", cwd=q)
    monkeypatch.setattr(layout, "modes", lambda root=None: ["quick", "referee"])
    ok("upgrade", cwd=q)
    assert skills(q, ".claude/skills") == ["loom-quick", "loom-referee"]
    assert skills(q, ".agents/skills") == ["loom-quick", "loom-referee"]


def test_a_mode_whose_line_the_author_changed_is_described_as_they_wrote_it(tmp_path: Path) -> None:
    q = bare(tmp_path)
    ok("ai", "init", cwd=q)
    mode = q / ".loom/ai/modes/flow.md"
    old = next(ln for ln in mode.read_text().splitlines() if ln.startswith("When it fits:"))
    mode.write_text(mode.read_text().replace(old, "When it fits: smoothing a proof this quilt cares about."))
    ok("upgrade", cwd=q)
    assert "smoothing a proof this quilt cares about." in (q / ".claude/skills/loom-flow/SKILL.md").read_text()
