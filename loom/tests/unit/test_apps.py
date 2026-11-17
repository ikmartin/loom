"""The agent apps a quilt is set up for: recorded beside its agent layer, kept through `loom upgrade` and doctor, added to one at a time by the viewer's `agents-setup`, and every one of them written by `loom ai init`."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.ai.clients import PROJECT, apps_in, chosen
from loom.ai.layout import MCP, MCP_LINE, SHELL, variant
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


def test_a_quilt_set_up_for_codex_alone_stays_on_mcp_in_a_fresh_clone(tmp_path: Path) -> None:
    """Codex's server file is never committed and its rules are the same in either variant, so the root file's line is what says MCP: an upgrade keeps it, and setting Codex up again writes the server file."""
    q = bare(tmp_path)
    setup(q, "codex")
    (q / ".codex/config.toml").unlink()
    assert variant(q) == MCP
    assert ".codex/config.toml" in setup(q, "codex")["written"]  # type: ignore[operator]
    (q / ".codex/config.toml").unlink()
    ok("upgrade", cwd=q)
    assert MCP_LINE in (q / "AGENTS.md").read_text().splitlines() and (q / ".codex/config.toml").is_file()


def test_codex_set_up_beside_a_server_file_of_the_persons_is_over_mcp(tmp_path: Path) -> None:
    q = bare(tmp_path)
    (q / ".codex").mkdir()
    (q / ".codex/config.toml").write_text('model = "gpt-5"\n')
    got = setup(q, "codex")
    assert got["variant"] == MCP and ".codex/config.toml" in got["foreign"]  # type: ignore[operator]
    assert MCP_LINE in (q / "AGENTS.md").read_text().splitlines()
    assert (q / ".codex/config.toml").read_text() == 'model = "gpt-5"\n'


def test_setting_up_claude_code_keeps_the_persons_own_settings_beside_loom_s_rules(tmp_path: Path) -> None:
    """A project often has a `.claude/settings.json` of its own before it is a quilt: its `env`, hooks and rules stay, after loom's rules, and the answer says so."""
    import json

    q = bare(tmp_path)
    settings = q / ".claude/settings.json"
    settings.parent.mkdir()
    theirs = {
        "permissions": {"allow": ["Bash(make *)"], "defaultMode": "acceptEdits"},
        "env": {"MY_VAR": "1"},
        "hooks": {"Stop": []},
    }
    settings.write_text(json.dumps(theirs, indent=1))
    got = setup(q, "claude-code")
    assert got["merged"] == [".claude/settings.json"] and got["variant"] == MCP
    assert "kept your own settings in .claude/settings.json" in str(got["result"])
    now = json.loads(settings.read_text())
    assert now["env"] == {"MY_VAR": "1"} and now["hooks"] == {"Stop": []}
    assert now["permissions"]["defaultMode"] == "acceptEdits"
    assert now["permissions"]["allow"][-1] == "Bash(make *)" and "mcp__loom__*" in now["permissions"]["allow"]
    assert any(r.startswith("Bash(loom ") for r in now["permissions"]["deny"])
    ok("upgrade", cwd=q)
    assert json.loads(settings.read_text()) == now, "an upgrade keeps them too"


def test_a_rule_loom_no_longer_writes_goes_and_the_persons_stay(tmp_path: Path) -> None:
    """Loom records the rules it wrote, so when `[agents] deny` narrows, its old rule is told from one of the person's."""
    import json

    from loom.ai.layout import permissions_stale, quilt_config, write_permissions

    q = bare(tmp_path)
    setup(q, "claude-code")
    settings = q / ".claude/settings.json"
    data = json.loads(settings.read_text())
    data["permissions"]["deny"].append("Edit(/private/**)")
    settings.write_text(json.dumps(data, indent=2) + "\n")
    config = q / "config.toml"
    config.write_text(config.read_text().replace("\ndeny = []\n", '\ndeny = ["paper/"]\n', 1))
    assert permissions_stale(q, quilt_config(q))
    write_permissions(q, quilt_config(q), shell=False)
    deny = json.loads(settings.read_text())["permissions"]["deny"]
    assert "Edit(/**/paper/**)" in deny and deny[-1] == "Edit(/private/**)"
    config.write_text(config.read_text().replace('deny = ["paper/"]', "deny = []"))
    write_permissions(q, quilt_config(q), shell=False)
    deny = json.loads(settings.read_text())["permissions"]["deny"]
    assert "Edit(/**/paper/**)" not in deny and deny[-1] == "Edit(/private/**)"
    assert not permissions_stale(q, quilt_config(q))


def test_a_settings_file_that_is_no_json_object_is_left_alone_and_said(tmp_path: Path) -> None:
    q = bare(tmp_path)
    settings = q / ".claude/settings.json"
    settings.parent.mkdir()
    settings.write_text("{ not json")
    got = setup(q, "claude-code")
    assert ".claude/settings.json" in got["foreign"] and ".claude/settings.json" not in got["written"]  # type: ignore[operator]
    assert settings.read_text() == "{ not json"
