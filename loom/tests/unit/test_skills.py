"""A thin skill per mode for each app that reads a project's skills, written with the agent layer and again by `loom upgrade`, from the quilt's modes as `modes` lists them."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from loom.ai import layout
from loom.ai.layout import modes, upgrade_layer
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


def test_upgrade_writes_its_own_again_and_leaves_every_skill_it_did_not_write(tmp_path: Path) -> None:
    """A skill is loom's only where loom wrote it: a `loom-` name is not enough, and one of loom's the person edited is theirs."""
    q = bare(tmp_path)
    ok("ai", "init", cwd=q)
    (q / ".claude/skills/loom-quick/SKILL.md").unlink()
    notes = q / ".claude/skills/loom-notes/SKILL.md"
    notes.parent.mkdir()
    notes.write_text("---\nname: loom-notes\n---\nThe person's.\n")
    edited = q / ".claude/skills/loom-review/SKILL.md"
    edited.write_text(edited.read_text() + "\nAnd always check the bibliography.\n")
    mine = q / ".claude/skills/my-own/SKILL.md"
    mine.parent.mkdir()
    mine.write_text("---\nname: my-own\n---\nThe person's.\n")
    rep = upgrade_layer(q)
    assert ".claude/skills/loom-quick/SKILL.md" in rep.written
    assert rep.theirs == [".claude/skills/loom-review/SKILL.md"] and rep.removed == []
    assert notes.read_text() == "---\nname: loom-notes\n---\nThe person's.\n"
    assert edited.read_text().endswith("And always check the bibliography.\n")
    assert mine.read_text() == "---\nname: my-own\n---\nThe person's.\n"


def test_nothing_is_written_or_removed_through_a_link(tmp_path: Path) -> None:
    """A link at a skill's path, or in place of the skills folder, may lead out of the quilt: loom neither follows it to write nor to delete."""
    q = bare(tmp_path)
    ok("ai", "init", cwd=q)
    outside = tmp_path / "outside"
    (outside / "loom-mine").mkdir(parents=True)
    (outside / "loom-mine/SKILL.md").write_text("theirs, outside the quilt\n")
    (outside / "loom-quick").mkdir()
    (outside / "loom-quick/SKILL.md").write_text("theirs too\n")
    (q / ".claude/skills/loom-mine").symlink_to(outside / "loom-mine", target_is_directory=True)
    quick = q / ".claude/skills/loom-quick"
    shutil.rmtree(quick)
    quick.symlink_to(outside / "loom-quick", target_is_directory=True)
    shutil.rmtree(q / ".agents/skills")
    (q / ".agents/skills").symlink_to(outside, target_is_directory=True)
    theirs = upgrade_layer(q).theirs
    assert ".claude/skills/loom-quick/SKILL.md" in theirs and ".agents/skills/loom-quick/SKILL.md" in theirs
    assert (outside / "loom-mine/SKILL.md").read_text() == "theirs, outside the quilt\n"
    assert (outside / "loom-quick/SKILL.md").read_text() == "theirs too\n"
    assert sorted(p.name for p in outside.iterdir()) == ["loom-mine", "loom-quick"]


def test_setting_up_an_app_leaves_a_skill_of_the_persons_at_one_of_its_paths(tmp_path: Path) -> None:
    from loom.render.endpoints.agents import HANDLERS

    q = bare(tmp_path)
    theirs = q / ".claude/skills/loom-review/SKILL.md"
    theirs.parent.mkdir(parents=True)
    theirs.write_text("---\nname: loom-review\ndescription: my own review checklist\n---\nMy checklist.\n")
    got = HANDLERS["agents-setup"](q, "agents-setup", {"app": "claude-code", "author": "A. Author"})
    assert ".claude/skills/loom-review/SKILL.md" in got["foreign"]
    assert (
        ".claude/skills/loom-review/SKILL.md" not in got["written"]
        and ".claude/skills/loom-quick/SKILL.md" in got["written"]
    )
    assert theirs.read_text().endswith("My checklist.\n")
    assert "loom-review/SKILL.md alone" in got["result"]


def test_loom_removes_its_own_skill_of_a_mode_that_is_gone_and_keeps_an_edited_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    q = bare(tmp_path)
    ok("ai", "init", cwd=q)
    edited = q / ".claude/skills/loom-flow/SKILL.md"
    edited.write_text(edited.read_text() + "\nMine now.\n")
    monkeypatch.setattr(layout, "modes", lambda root=None: [m for m in layout.MODES if m not in ("flow", "draft")])
    rep = upgrade_layer(q)
    assert sorted(rep.removed) == [
        ".agents/skills/loom-draft/SKILL.md",
        ".agents/skills/loom-flow/SKILL.md",
        ".claude/skills/loom-draft/SKILL.md",
    ]
    assert rep.theirs == [".claude/skills/loom-flow/SKILL.md"] and edited.read_text().endswith("Mine now.\n")
    assert not (q / ".claude/skills/loom-draft").exists()


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
