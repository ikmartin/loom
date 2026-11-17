"""The agent apps a quilt is set up for: recorded beside its agent layer, kept through `loom upgrade` and doctor, added to one at a time by the viewer's `agents-setup`, and every one of them written by `loom ai init`."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.ai.clients import PROJECT, apps_in, chosen
from loom.ai.layout import MCP, SHELL, variant
from loom.render.endpoints.base import ApiError
from tests.helpers import ok
from tests.unit._quilts import demo

EVERY = [c.key for c in PROJECT]
CLAUDE_FILES = ("CLAUDE.md", ".claude/settings.json", ".mcp.json")
OTHERS = (
    "AGENTS.md",
    "GEMINI.md",
    ".codex/rules/loom.rules",
    ".codex/config.toml",
    ".gemini/settings.json",
    ".cursor/mcp.json",
)


def bare(tmp_path: Path) -> Path:
    """A new quilt with no agent layer, as the home page makes one."""
    ok("init", str(tmp_path / "q"), "--yes", cwd=tmp_path)
    q = tmp_path / "q"
    assert not (q / ".loom" / "ai").exists()
    return q


def setup(q: Path, app: str, author: str = "A. Author") -> dict[str, object]:
    from loom.render.endpoints.agents import HANDLERS

    return HANDLERS["agents-setup"](q, "agents-setup", {"app": app, "author": author})


def test_a_quilt_set_up_for_claude_code_alone_stays_so_through_an_upgrade_and_reads_clean(tmp_path: Path) -> None:
    from loom.doctor import check_mcp, check_permissions

    q = bare(tmp_path)
    got = setup(q, "claude-code")
    assert got["variant"] == MCP and apps_in(q) == ["claude-code"]
    assert all((q / rel).is_file() for rel in CLAUDE_FILES) and not any((q / rel).exists() for rel in OTHERS)
    ok("upgrade", cwd=q)
    assert apps_in(q) == ["claude-code"] and not any((q / rel).exists() for rel in OTHERS)
    assert check_permissions(q).status == "ok" and check_permissions(q).detail.startswith(".claude/settings.json:")
    assert [i.status for i in check_mcp(q)] == ["ok"]
    assert setup(q, "claude-code")["written"] == [], "set up already"


def test_a_second_app_is_added_beside_the_first(tmp_path: Path) -> None:
    q = bare(tmp_path)
    setup(q, "claude-code")
    got = setup(q, "codex")
    assert apps_in(q) == ["claude-code", "codex"]
    assert {"AGENTS.md", ".codex/rules/loom.rules", ".codex/config.toml"} <= set(got["written"])  # type: ignore[arg-type]
    assert not any((q / rel).exists() for rel in ("GEMINI.md", ".gemini/settings.json", ".cursor/mcp.json"))


def test_a_quilt_whose_agents_use_the_shell_keeps_it(tmp_path: Path) -> None:
    q = bare(tmp_path)
    ok("ai", "init", "--shell", cwd=q)
    assert variant(q) == SHELL
    assert setup(q, "claude-code")["variant"] == SHELL and variant(q) == SHELL
    assert not (q / ".mcp.json").exists()


def test_a_quilt_set_up_for_codex_alone_reads_its_variant_from_codex(tmp_path: Path) -> None:
    q = bare(tmp_path)
    setup(q, "codex")
    assert apps_in(q) == ["codex"] and variant(q) == MCP and not (q / ".claude").exists()


def test_an_app_it_does_not_set_up_is_refused(tmp_path: Path) -> None:
    q = bare(tmp_path)
    with pytest.raises(ApiError, match="app is one of claude-code, codex, gemini-cli, cursor"):
        setup(q, "claude-desktop")
    assert not (q / ".loom" / "ai").exists()


def test_ai_init_writes_every_app_and_a_new_quilt_reaches_loom_over_mcp(tmp_path: Path) -> None:
    """MCP is the default for a new quilt, whichever way the agent layer is written: `loom ai init`, `loom init` with an AI, or the viewer's setup."""
    q = bare(tmp_path)
    ok("ai", "init", cwd=q)
    assert apps_in(q) == EVERY and variant(q) == MCP
    made = tmp_path / "with-claude"
    ok("init", str(made), "--ai", "claude", "--yes", cwd=tmp_path)
    assert variant(made) == MCP and (made / ".mcp.json").is_file()
    (tmp_path / "d").mkdir()
    shipped = demo(tmp_path / "d")
    assert chosen(shipped, None) == EVERY, "a layer that records no apps is set up for every one"
