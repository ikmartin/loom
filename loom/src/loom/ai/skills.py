"""A thin skill per mode for each agent app that reads skills from the project: `.claude/skills/loom-<mode>/SKILL.md` for Claude Code, `.agents/skills/loom-<mode>/SKILL.md` for Codex.

A skill only points at its mode, whose text stays the one copy in `.loom/ai/modes/` and is read through `loom_ai_mode`, so a person can start a mode from the app's `/` menu whether or not the app lists MCP prompts there. Loom writes the skills whole, from the quilt's `modes`, and again at every upgrade, and removes a `loom-` skill whose mode the quilt no longer has; a skill by any other name is the person's and never touched.
"""

from __future__ import annotations

import json
from pathlib import Path

#: The name every skill loom writes starts with, which is how loom knows its own.
PREFIX = "loom-"
SKILL = "SKILL.md"


def skill_text(root: Path, name: str) -> str:
    """The skill for mode `name`: a description from the quilt's own `When it fits:` line, and a body that sends the agent to the mode."""
    from loom.ai.orient import fits

    said = fits(root, name)
    description = f"Work in loom's {name} mode" + (f": {said}" if said else ".")
    return (
        "---\n"
        f"name: {PREFIX}{name}\n"
        f"description: {json.dumps(description, ensure_ascii=False)}\n"
        "---\n\n"
        f"Work in loom's {name} mode on what the person named when they asked for it, or on what the conversation names; if it names nothing yet, ask them what to work on.\n\n"
        "1. If you have not called `loom_ai_orient` in this conversation, call it first (in a shell, `loom ai orient`), and follow it.\n"
        f"2. Call `loom_ai_mode` with the name `{name}` (in a shell, `loom ai mode {name}`) and work as it says.\n\n"
        f"The mode is the quilt's own copy, `.loom/ai/modes/{name}.md`; this skill only points at it, and loom writes it again from the mode.\n"
    )


def is_skill(rel: str) -> bool:
    """Whether quilt-relative `rel` is a skill loom writes: `<skills>/loom-<mode>/SKILL.md`."""
    parts = rel.split("/")
    return len(parts) >= 3 and parts[-1] == SKILL and parts[-2].startswith(PREFIX)


def skill_files(root: Path, apps: list[str]) -> dict[str, str]:
    """Quilt-relative path -> text of every skill loom writes for `apps`, one per mode of the quilt (`modes`)."""
    from loom.ai.clients import PROJECT
    from loom.ai.layout import modes

    out: dict[str, str] = {}
    for c in PROJECT:
        if c.skills is None or c.key not in apps:
            continue
        for name in modes(root):
            out[f"{c.skills}/{PREFIX}{name}/{SKILL}"] = skill_text(root, name)
    return out


def write_skills(root: Path, apps: list[str], *, write: bool = True) -> tuple[list[str], list[str]]:
    """(written, unchanged): the skills of `apps` made what the quilt's modes make them, and a `loom-` skill of theirs whose mode is gone removed (among `written`); with `write` false nothing is written and the lists say what would be."""
    from loom.ai.clients import PROJECT

    wanted = skill_files(root, apps)
    written: list[str] = []
    unchanged: list[str] = []
    for rel, text in wanted.items():
        p = root / rel
        if p.is_file() and p.read_text(encoding="utf-8") == text:
            unchanged.append(rel)
            continue
        written.append(rel)
        if write:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
    for c in PROJECT:
        if c.skills is None or c.key not in apps:
            continue
        for p in sorted((root / c.skills).glob(f"{PREFIX}*/{SKILL}")):
            rel = p.relative_to(root).as_posix()
            if rel in wanted:
                continue
            written.append(rel)
            if write:
                p.unlink()
                try:
                    p.parent.rmdir()
                except OSError:
                    pass  # something of the person's beside it stays, and so does the directory
    return written, unchanged
