"""A quilt's library as an earlier loom left it, in layout format 1, written by hand: what the carry-over (`library.carry`), `loom upgrade` and `library-upgrade` read. No generated quilt is in format 1, so every test of the carry builds its own."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from loom.library.carry import BIBLIOGRAPHY, STORAGE
from loom.paths import FORMAT, LIBRARY

#: A work stating an arXiv number, with its PDF in the old store under that number, and a book stating nothing.
SMI24 = """@article{Smi24,
  author = {Smith, Jane},
  title  = {Widgets},
  year   = {2024},
  eprint = {2401.01234v1},
  archiveprefix = {arXiv},
  loom-source = {smith-widgets.pdf},
}"""
HAR77 = """@book{Har77,
  author    = {Hartshorne, Robin},
  title     = {Algebraic Geometry},
  publisher = {Springer},
  year      = {1977},
}"""
PDF_A = b"%PDF-1.4\n% the arXiv preprint\n"


def old_library(root: Path, bib: str, stored: Mapping[str, bytes] | None = None) -> Path:
    """Make `root`'s library format 1's: the format stamped 1, `bib` as `.loom/library/bibliography.bib` under the head the earlier loom wrote, and each of `stored`, a path under the old store to its bytes; returns `root`."""
    (root / FORMAT).parent.mkdir(parents=True, exist_ok=True)
    (root / FORMAT).write_text("1\n", encoding="utf-8")
    (root / LIBRARY).mkdir(parents=True, exist_ok=True)
    head = "% The quilt's bibliography, gathered by `loom library update` from the landmarks.\n\n"
    (root / BIBLIOGRAPHY).write_text(head + bib + "\n", encoding="utf-8")
    for rel, data in (stored or {}).items():
        path = root / STORAGE / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return root


#: What an earlier loom's agents were told and allowed of its library, every command of it gone: a mode of its own, its skill, a line of the rules, and a permission.
OLD_MODE = "ingest"
OLD_COMMAND = "loom library read"
OLD_RULE = f"Bash({OLD_COMMAND}*)"


def old_agents(root: Path) -> Path:
    """Make `root`'s agents' layer, which `loom ai init` wrote, an earlier loom's: the `OLD_MODE` mode file and its Claude Code skill, each recorded as loom's own, `rules.md` naming `OLD_COMMAND` as loom's own, and `OLD_RULE` allowed in `.claude/settings.json` and recorded as loom's rule; returns `root`."""
    import hashlib
    import json

    from loom.ai.layout import RULES_FILE, VERSION_FILE
    from loom.ai.skills import RECORD
    from loom.paths import AI

    def sha(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def record(rel: str, line: str) -> None:
        with (root / AI / rel).open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    mode = f"# The {OLD_MODE} mode\n\nRun `loom library update`, then `{OLD_COMMAND} KEY` for each work.\n"
    (root / AI / "modes" / f"{OLD_MODE}.md").write_text(mode, encoding="utf-8")
    record(VERSION_FILE, f"{OLD_MODE}.md {sha(mode)}")
    skill_rel = f".claude/skills/loom-{OLD_MODE}/SKILL.md"
    skill = f"---\nname: loom-{OLD_MODE}\n---\n\nWork in loom's {OLD_MODE} mode.\n"
    (root / skill_rel).parent.mkdir(parents=True, exist_ok=True)
    (root / skill_rel).write_text(skill, encoding="utf-8")
    record(RECORD, f"{skill_rel} {sha(skill)}")
    rules = f"# What an agent may run\n\n- `{OLD_COMMAND}`\n"
    (root / AI / "rules.md").write_text(rules, encoding="utf-8")
    versions = (root / AI / VERSION_FILE).read_text(encoding="utf-8").splitlines()
    kept = [line for line in versions if not line.startswith("rules.md ")]
    (root / AI / VERSION_FILE).write_text("\n".join([*kept, f"rules.md {sha(rules)}"]) + "\n", encoding="utf-8")
    settings = root / ".claude" / "settings.json"
    data = json.loads(settings.read_text(encoding="utf-8"))
    data["permissions"]["allow"].append(OLD_RULE)
    settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    record(RULES_FILE, f"allow\t{OLD_RULE}")
    return root


def older_quilt(tmp_path: Path, *, agents: bool = False) -> Path:
    """A quilt `loom init` made, its library then written as format 1's: `SMI24` with its PDF stored, and `HAR77`; with `agents`, `loom ai init` first and the layer it wrote made an earlier loom's (`old_agents`)."""
    from tests.helpers import ok

    q = tmp_path / "q"
    ok("init", str(q), cwd=tmp_path)
    if agents:
        ok("ai", "init", cwd=q)
        old_agents(q)
    return old_library(q, f"{SMI24}\n\n{HAR77}", {"arxiv/2401.01234v1/paper.pdf": PDF_A})
