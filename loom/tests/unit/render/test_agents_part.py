"""The manifest's `agents`: the apps the viewer can set up and whether each is, the line an agent is told first, and the quilt's modes as `modes` lists them."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loom.ai.layout import MCP_LINE, modes
from tests.helpers import ok, run
from tests.unit._quilts import demo


def built(q: Path) -> dict[str, Any]:
    run("build", cwd=q)
    return json.loads((q / ".loom/cache/site/manifest.json").read_text())["agents"]  # type: ignore[no-any-return]


def test_a_quilt_with_no_agent_layer_is_set_up_for_no_app(tmp_path: Path) -> None:
    ok("init", str(tmp_path / "q"), "--yes", cwd=tmp_path)
    got = built(tmp_path / "q")
    assert [(a["key"], a["set_up"]) for a in got["apps"]] == [
        ("claude-code", False),
        ("codex", False),
        ("gemini-cli", False),
        ("cursor", False),
    ]
    assert got["line"] == "" and [m["name"] for m in got["modes"]] == modes()


def test_a_quilt_set_up_for_claude_code_says_so_and_what_its_agent_is_told(tmp_path: Path) -> None:
    from loom.render.endpoints.agents import HANDLERS

    ok("init", str(tmp_path / "q"), "--yes", cwd=tmp_path)
    q = tmp_path / "q"
    HANDLERS["agents-setup"](q, "agents-setup", {"app": "claude-code", "author": "A. Author"})
    got = built(q)
    assert [a["key"] for a in got["apps"] if a["set_up"]] == ["claude-code"]
    assert got["line"] == MCP_LINE
    assert not any(m["edited"] for m in got["modes"])


def test_a_mode_the_author_edited_is_marked_and_its_line_is_the_quilts(tmp_path: Path) -> None:
    q = demo(tmp_path)
    ok("upgrade", cwd=q)
    mode = q / ".loom/agents/instructions/modes/referee.md"
    text = mode.read_text()
    fits = next(ln for ln in text.splitlines() if ln.startswith("When it fits:"))
    mode.write_text(text.replace(fits, "When it fits: refereeing, as this quilt does it."))
    got = {m["name"]: m for m in built(q)["modes"]}
    assert got["referee"]["edited"] is True and got["referee"]["fits"] == "refereeing, as this quilt does it."
    assert got["referee"]["path"] == ".loom/agents/instructions/modes/referee.md" and got["quick"]["edited"] is False


def test_each_mode_carries_its_text_as_a_person_edits_it_and_whether_a_newer_one_waits(tmp_path: Path) -> None:
    q = demo(tmp_path)
    ok("upgrade", cwd=q)
    mode = q / ".loom/agents/instructions/modes/referee.md"
    mode.write_text(mode.read_text() + "\nThis quilt's own last line.\n")
    ok("upgrade", cwd=q)
    got = {m["name"]: m for m in built(q)["modes"]}
    assert got["referee"]["text"] == mode.read_text() and "{type:" in got["referee"]["text"]
    assert got["referee"]["newer"] is True and got["quick"]["newer"] is False


def test_a_quilt_with_no_agent_layer_shows_loom_s_own_text_of_each_mode(tmp_path: Path) -> None:
    from loom.ai.layout import tracked_docs

    ok("init", str(tmp_path / "q"), "--yes", cwd=tmp_path)
    shipped = tracked_docs()
    got = built(tmp_path / "q")["modes"]
    assert all(m["text"] == shipped[m["path"]] for m in got)
    assert not any(m["newer"] or m["edited"] for m in got)
