"""The agent apps a quilt is set up for: recorded beside its agent layer, kept through `loom upgrade` and doctor, added to one at a time by the viewer's `agents-setup`, and every one of them written by `loom ai init`."""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any

import pytest

from loom.ai.clients import PROJECT, apps_in, chosen
from loom.ai.layout import MCP, MCP_LINE, SHELL, variant
from loom.render.endpoints.base import ApiError
from tests.helpers import exits, ok
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


def test_doctor_reads_a_settings_file_that_keeps_the_persons_own_as_current(tmp_path: Path) -> None:
    import json

    from loom.doctor import check_permissions

    q = bare(tmp_path)
    settings = q / ".claude/settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"env": {"MY_VAR": "1"}}))
    setup(q, "claude-code")
    assert check_permissions(q).status == "ok"


def _settings(q: Path) -> dict[str, Any]:
    return json.loads((q / ".claude/settings.json").read_text(encoding="utf-8").removeprefix("﻿"))  # type: ignore[no-any-return]


def _deny(q: Path, entries: str) -> None:
    config = q / "config.toml"
    text = config.read_text()
    config.write_text(re.sub(r"(?m)^deny = \[.*\]$", f"deny = {entries}", text, count=1))


def test_a_persons_rules_are_kept_whatever_they_name_where_loom_records_its_own(tmp_path: Path) -> None:
    """With the record, a rule is loom's only where loom renders it or wrote it: a person's deny of a loom tool narrows what an agent may do, and stays."""
    q = bare(tmp_path)
    setup(q, "claude-code")
    data = _settings(q)
    theirs = ["mcp__loom__loom_write", "Bash(loom annotate --delete*)", "Read(./secrets/**)"]
    data["permissions"]["deny"] += theirs
    data["permissions"]["allow"].append("mcp__loom__loom_session_say")
    (q / ".claude/settings.json").write_text(json.dumps(data, indent=2) + "\n")
    ok("upgrade", cwd=q)
    after = _settings(q)["permissions"]
    assert after["deny"][-3:] == theirs and after["allow"][-1] == "mcp__loom__loom_session_say"


def test_without_the_record_only_an_allow_naming_loom_is_taken_for_an_older_looms(tmp_path: Path) -> None:
    q = bare(tmp_path)
    setup(q, "claude-code")
    (q / ".loom/ai/.loom-rules").unlink()
    data = _settings(q)
    data["permissions"]["allow"].append("Bash(loom accept*)")
    data["permissions"]["deny"].append("mcp__loom__loom_write")
    (q / ".claude/settings.json").write_text(json.dumps(data, indent=2) + "\n")
    ok("upgrade", cwd=q)
    after = _settings(q)["permissions"]
    assert "Bash(loom accept*)" not in after["allow"] and after["deny"][-1] == "mcp__loom__loom_write"
    assert (q / ".loom/ai/.loom-rules").is_file()


def test_the_merge_keeps_the_persons_text_as_written(tmp_path: Path) -> None:
    """Non-ASCII stays as typed, keys stay where the person put them, and a byte-order mark stays at the head."""
    q = bare(tmp_path)
    settings = q / ".claude/settings.json"
    settings.parent.mkdir()
    theirs = {
        "$schema": "https://json.schemastore.org/claude-code-settings.json",
        "permissions": {"defaultMode": "acceptEdits", "deny": ["Read(./secrets/**)"], "allow": ["Bash(make *)"]},
        "env": {"AUTHOR": "Zoë Ñ"},
    }
    settings.write_text("﻿" + json.dumps(theirs, indent=2, ensure_ascii=False), encoding="utf-8")
    assert setup(q, "claude-code")["merged"] == [".claude/settings.json"]
    text = settings.read_text(encoding="utf-8")
    assert text.startswith("﻿{") and '"AUTHOR": "Zoë Ñ"' in text
    now = _settings(q)
    assert list(now) == ["$schema", "permissions", "env"]
    assert list(now["permissions"]) == ["defaultMode", "deny", "allow"]
    assert "mcp__loom__*" in now["permissions"]["allow"] and now["permissions"]["deny"][-1] == "Read(./secrets/**)"


def test_the_record_is_written_after_the_settings_and_a_failed_write_is_refused(tmp_path: Path) -> None:
    """A settings file loom cannot write leaves the record saying what is there, so loom's old rule is still told from the person's once it can."""
    q = bare(tmp_path)
    setup(q, "claude-code")
    _deny(q, '["private/**"]')
    ok("upgrade", cwd=q)
    assert any("private" in r for r in _settings(q)["permissions"]["deny"])
    _deny(q, "[]")
    settings = q / ".claude/settings.json"
    settings.chmod(0o444)
    try:
        refused = exits(1, "upgrade", cwd=q)
        assert "loom could not write .claude/settings.json" in refused.output and "Traceback" not in refused.output
        assert "private" in (q / ".loom/ai/.loom-rules").read_text()
    finally:
        settings.chmod(0o644)
    ok("upgrade", cwd=q)
    assert not any("private" in r for r in _settings(q)["permissions"]["deny"])


def test_variant_and_upgrade_never_wait_on_a_root_file_that_is_a_fifo(tmp_path: Path) -> None:
    """A FIFO named `CLAUDE.md` in a copied quilt: the variant is read without it, and the root line is not written into it."""
    from loom.ai.layout import upgrade_layer

    q = bare(tmp_path)
    setup(q, "codex")
    fifo = q / "CLAUDE.md"
    os.mkfifo(fifo)
    try:
        got: list[object] = []
        look = threading.Thread(
            target=lambda: got.append((variant(q), upgrade_layer(q, apps=["claude-code", "codex"]).theirs)), daemon=True
        )
        look.start()
        look.join(10)
        assert got, "variant() or the upgrade waited on the FIFO"
        assert got[0] == (MCP, ["CLAUDE.md"])
    finally:
        try:
            os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
        except OSError:
            pass
