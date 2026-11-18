"""A thin skill per mode for each agent app that reads skills from the project: `.claude/skills/loom-<mode>/SKILL.md` for Claude Code, `.agents/skills/loom-<mode>/SKILL.md` for Codex.

A skill only points at its mode, whose text stays the one copy in `.loom/ai/modes/` and is read through `loom_ai_mode`, so a person can start a mode from the app's `/` menu whether or not the app lists MCP prompts there. A skill is loom's only where loom wrote it: `.loom/ai/.loom-skills` records each one it wrote with the hash of its text, as `.loom-modes-version` does for the modes. Loom writes a skill where none stands or over its own unedited one, from the quilt's `modes`, at every upgrade, and removes its own unedited skill of a mode the quilt no longer has. Anything else at one of its paths, a skill of the person's, one of loom's they edited, or a link, is left alone and reported, and nothing is written or removed through a link.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path

#: The name every skill loom writes starts with.
PREFIX = "loom-"
SKILL = "SKILL.md"
#: The record of the skills loom wrote, in `.loom/ai/`: a quilt-relative path and the hash of the text written, a line each.
RECORD = ".loom-skills"


@dataclass
class SkillReport:
    """What `write_skills` did, or would do, by quilt-relative path: `written`, `unchanged`, `removed`, and `theirs`, a file of the person's at one of loom's paths, left alone."""

    written: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    theirs: list[str] = field(default_factory=list)


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
    """Whether quilt-relative `rel` is at a skill's path loom uses: `<skills>/loom-<mode>/SKILL.md`."""
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


def read_record(root: Path) -> dict[str, str]:
    """Quilt-relative path -> hash of the text loom wrote there, as `RECORD` says; empty where there is none, or none that can be read (`layout.read_plain`)."""
    from loom.ai.layout import read_plain
    from loom.paths import AI

    out: dict[str, str] = {}
    for line in (read_plain(root, f"{AI}/{RECORD}") or "").splitlines():
        rel, _, digest = line.rpartition(" ")
        if rel and digest:
            out[rel] = digest
    return out


def _plain(root: Path, rel: str, *, folder: bool = False) -> bool:
    """Whether every part of `rel` under `root` that exists is a directory, and the last a regular file (a directory with `folder`), none of them a link: the only places loom writes or removes a skill."""
    p = root
    parts = rel.split("/")
    for i, part in enumerate(parts):
        p = p / part
        try:
            mode = os.lstat(p).st_mode
        except FileNotFoundError:
            return True
        except OSError:
            return False
        if not (stat.S_ISREG(mode) if i == len(parts) - 1 and not folder else stat.S_ISDIR(mode)):
            return False
    return True


def write_skills(root: Path, apps: list[str], *, write: bool = True) -> SkillReport:
    """The skills of `apps` made what the quilt's modes make them where they are loom's, and loom's own of a mode that is gone removed; with `write` false nothing is written and the report says what would be.

    A file at one of loom's paths that loom did not write, or wrote and the person has edited since, is theirs: left alone and named in `theirs`. The record (`RECORD`) is rewritten to what loom's skills now are; it is not itself reported.
    """
    from loom.ai.clients import PROJECT
    from loom.ai.layout import _write, sha
    from loom.paths import AI

    recorded = read_record(root)
    wanted = skill_files(root, apps)
    mine = {c.skills for c in PROJECT if c.skills is not None and c.key in apps}
    # what loom wrote for an app it is not writing for now stays recorded as it was
    record = {rel: h for rel, h in recorded.items() if not any(rel.startswith(f"{d}/") for d in mine)}
    rep = SkillReport()
    for rel, text in wanted.items():
        p = root / rel
        if not _plain(root, rel):
            rep.theirs.append(rel)
            continue
        current = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None
        if current == text:
            rep.unchanged.append(rel)
            record[rel] = sha(text)
            continue
        if current is not None and recorded.get(rel) != sha(current):
            rep.theirs.append(rel)
            continue
        rep.written.append(rel)
        record[rel] = sha(text)
        if write:
            _write(root, rel, text)
    for d in sorted(mine):
        if not _plain(root, d, folder=True) or not (root / d).is_dir():
            continue
        for entry in sorted(os.scandir(root / d), key=lambda e: e.name):
            rel = f"{d}/{entry.name}/{SKILL}"
            if not entry.name.startswith(PREFIX) or rel in wanted or rel not in recorded:
                continue  # a skill loom never wrote is the person's, whatever its name
            p = root / rel
            if not _plain(root, rel) or not p.is_file():
                continue
            if recorded[rel] != sha(p.read_text(encoding="utf-8", errors="replace")):
                rep.theirs.append(rel)
                continue
            rep.removed.append(rel)
            if write:
                p.unlink()
                try:
                    p.parent.rmdir()
                except OSError:
                    pass  # something of the person's beside it stays, and so does the directory
    if write and (record != recorded or (record and not (root / AI / RECORD).is_file())):
        said = "".join(f"{rel} {h}\n" for rel, h in sorted(record.items()))
        _write(root, f"{AI}/{RECORD}", said)
    return rep
