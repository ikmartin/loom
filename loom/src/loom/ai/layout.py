"""`loom ai init` and `loom upgrade`: the `.loom/ai/` directory, the vendor files, and their refresh.

Mode files are the author's once written: `.loom-modes-version` records the shipped hash of each, so upgrade overwrites only files still equal to what it shipped and writes `<mode>.md.new` beside an edited one.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from loom.paths import AI
from loom.scan.quilt import QuiltConfig

#: The modes loom ships, in the order the index lists them, read through `modes` alone. Each file's `When it fits:` line is the index's entry for it, the one copy; a file in a quilt's `.loom/ai/modes/` whose name is not here is not a mode, so one loom no longer ships is inert.
MODES = ["quick", "question", "audit", "referee", "review", "simplify", "flow", "draft", "ingest"]
RULES = "rules.md"  # `.loom/ai/rules.md`: not a mode, and no longer filed among them
# The one list: every loom command an agent may run, by its full path in the command tree. Everything else loom offers is the author's, so a command added later is denied until it is named here -- which an enumeration of forbidden commands could never promise, and did not: twelve mutating commands were missing from it (DR-173).
AGENT_COMMANDS = frozenset(
    {
        "annotate", "build", "check", "compile", "deps", "doctor", "draft", "history", "id", "link", "lint",
        "new", "search", "serve", "source", "status", "downstream", "history show", "history verify", "write",
        # a suggested edit, and withdrawing one of its own; what waits on the person, and a change's patch, which it reads; keeping and discarding are the author's
        "suggest", "changes",
        # the bridge: where the person is looking in the viewer, and what they did since this agent last looked
        "here", "since",
        "ai annotations", "ai drafts", "ai refresh", "ai orient", "ai mode",
        # the agent opens and names the session it works in, and writes its transcript; closing, resuming and deleting a session stay the author's, because they are decisions about the work rather than part of it
        "session new", "session rename", "session list", "session say",
        # the library's readers and an agent's tools; filing a document (`library add`, `import`) and every decision are the author's
        "library", "library update", "library review", "library read", "library search", "library why",
        "library propose", "library locate", "library relate", "library check",
        # the MCP server an agent's app starts, often from a shell that already marks an agent
        "mcp",
    }
)  # fmt: skip
#: What each agent command does to the quilt, which is what an MCP tool's hints say (`loom.mcp.tools.hints`): `read` changes nothing but loom's own command log; `derive` rewrites what `.loom/build/` derives; `write` adds to a record, a session, a document of the agent's or the library, or moves the agent's own marker (`since`); `replace` puts new text in place of a page's. Every command in `AGENT_COMMANDS` is here, and nothing else.
ACTS: dict[str, str] = {
    **dict.fromkeys(
        (
            "deps", "doctor", "downstream", "here", "history", "history show", "history verify", "link", "lint", "search",
            "source", "status", "changes", "ai annotations", "ai drafts", "ai mode", "ai orient", "session list",
            "library", "library check", "library locate", "library read", "library review", "library search",
            "library why",
        ),
        "read",
    ),
    **dict.fromkeys(("build", "check", "compile", "id", "serve"), "derive"),
    **dict.fromkeys(
        (
            "annotate", "suggest", "draft", "new", "since", "ai refresh", "session new", "session rename", "session say",
            "library propose", "library relate", "library update", "mcp",
        ),
        "write",
    ),
    "write": "replace",
}  # fmt: skip
#: The options of an agent command that are the author's acts, which its MCP tool leaves out: an agent reads what waits on the person, and only the person keeps or discards it.
AUTHOR_OPTIONS: dict[str, frozenset[str]] = {
    "changes": frozenset({"--keep", "--discard", "--keep-all", "--discard-all", "--why"}),
}
#: Agent commands that are no MCP tool: the server itself, `serve`, which runs until stopped, and `library relate`, which no agent was found to use and which the rules no longer ask for; a shell still runs it.
NOT_TOOLS = frozenset({"mcp", "serve", "library relate"})
#: The one agent command that may reach the network, when the quilt's config allows it.
NETWORK = frozenset({"library update"})
#: The line loom puts in each agent's root file, one per variant: an agent attached over MCP starts from the server's tool, and one working through a shell from the command.
MCP_LINE = "This directory is a quilt managed by loom. Before doing anything, call `loom_ai_orient`, the tool of the loom MCP server, and follow it; if you have no loom tools, run `loom ai orient` in a shell instead, and `loom doctor` to tell the author why. Write anywhere but the paths the orientation names as protected."
SHELL_LINE = "This directory is a quilt managed by loom. Before doing anything, run `loom ai orient` and follow it. Write anywhere but the paths `loom ai orient` names as protected."
#: Lines an older loom wrote, each replaced where it stands so an upgraded quilt holds one line, not two.
OLD_LINES = (
    "This directory is a quilt managed by loom. Before doing anything, call `loom_ai_orient`, the tool of the loom MCP server, and follow it; if you have no loom tools, ask the author to run `loom ai init` and approve the loom server. Write only under your session's directory in `.loom/sessions/`, and in the documents `loom_ai_orient` names as yours to edit.",
    "This directory is a quilt managed by loom. Before doing anything, run `loom ai orient` and follow it. Write only under your session's directory in `.loom/sessions/`, and in the documents `loom ai orient` names as yours to edit.",
    "This directory is a quilt managed by loom. Before doing anything, call `loom_ai_orient`, the tool of the loom MCP server, and follow it; if you have no loom tools, ask the author to run `loom ai init` and approve the loom server. Write anywhere but the paths `loom_ai_orient` names as protected.",
    "This directory is a quilt managed by loom. Before doing anything, call `loom_ai_orient`, the tool of the loom MCP server, and follow it; if you have no loom tools, ask the author to run `loom doctor`, fix what it reports, approve the loom server and restart this session. Write anywhere but the paths `loom_ai_orient` names as protected.",
)
#: The two variants of the agent layer: the MCP server's tools with `loom` in a shell beside them, the default, or the shell alone, for an agent with no MCP.
MCP, SHELL = "mcp", "shell"
VERSION_FILE = ".loom-modes-version"
#: The agent apps the quilt is set up for, one key a line (`clients.apps_in`), written with the layer; a quilt without it is set up for every app.
APPS_FILE = ".loom-apps"


def _asset(*parts: str) -> str:
    return resources.files("loom").joinpath("assets", "ai", *parts).read_text(encoding="utf-8")


def command_tree() -> list[str]:
    """Every leaf command loom offers, as the path a person types: `accept`, `ai orient`, `library verify`."""
    import click

    from loom.cli import main

    out: list[str] = []

    def walk(cmd: object, prefix: str = "") -> None:
        for name, sub in sorted(getattr(cmd, "commands", {}).items()):
            path = f"{prefix} {name}".strip()
            if isinstance(sub, click.Group):
                # a group that runs on its own (`history`, `history KEY`) is a command as well as a group
                if sub.invoke_without_command:
                    out.append(path)
                walk(sub, path)
            else:
                out.append(path)

    walk(main)
    return out


def author_commands() -> list[str]:
    """Every command that is not an agent's, derived rather than listed, so a new one is the author's until it is admitted."""
    return [c for c in command_tree() if c not in AGENT_COMMANDS]


def help_commands() -> list[str]:
    """How an agent asks loom what it offers, as typed after `loom`: the top level's help and that of each group whose name alone no rule admits, `ai` and `session`.

    The orientation sends an agent to these, they write nothing, and a rule for a command never reaches them: `Bash(loom session new*)` does not match `loom session --help`.
    """
    groups = {c.rsplit(" ", 1)[0] for c in AGENT_COMMANDS if " " in c} - AGENT_COMMANDS
    return sorted(f"{group} {flag}".strip() for group in ("", *groups) for flag in ("--help", "-h"))


def modes(root: Path | None = None) -> list[str]:
    """The modes of the quilt at `root`, in the order its agents are shown them; with no quilt, the ones loom ships.

    Every listing of the modes asks here: the orientation's index, the MCP prompts and the check of a prompt's name, `loom ai mode`, which types each mode names, the manifest's `agents.modes`, and the mode files the agent layer writes. Today a quilt's modes are loom's (`MODES`) whatever its `.loom/ai/modes/` holds, so a quilt's own set is a change to this function and not to its callers.
    """
    return list(MODES)


def tracked_docs(root: Path | None = None) -> dict[str, str]:
    """Quilt-relative path -> shipped text for every file whose edits `loom upgrade` preserves, the files of the quilt's modes among them (`modes`).

    The orientation is here because it is the first thing an author tailors -- a standing rule about this quilt, a mode the agent should not reach for -- and `loom upgrade` overwrote it without a word until it was.
    """
    allowed = "\n".join(f"  - `loom {c}`" for c in sorted(AGENT_COMMANDS))
    out = {
        f"{AI}/{RULES}": _asset(RULES).replace("{allowed_commands}", allowed),
        f"{AI}/orientation.md": _asset("orientation.md"),
        f"{AI}/formatting.md": _asset("formatting.md"),
    }
    out.update({f"{AI}/modes/{m}.md": _asset("modes", f"{m}.md") for m in modes(root)})
    return out


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_versions(root: Path) -> dict[str, str]:
    p = root / AI / VERSION_FILE
    out: dict[str, str] = {}
    if p.is_file():
        for line in p.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) == 2:
                out[parts[0]] = parts[1]
    return out


def write_versions(root: Path, texts: dict[str, str]) -> None:
    """Record the shipped hash of each of `texts` (quilt-relative path -> text) under its file name, which is how `upgrade_layer` looks it up."""
    lines = [f"{Path(rel).name} {sha(t)}" for rel, t in sorted(texts.items(), key=lambda kv: Path(kv[0]).name)]
    (root / AI / VERSION_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")


def quilt_config(root: Path) -> QuiltConfig:
    """The config of the quilt at `root`, or the defaults where there is none yet: the names the permission file is written with."""
    from loom.scan.quilt import NoQuiltError, load_quilt

    try:
        return load_quilt(root).config
    except NoQuiltError:
        return QuiltConfig()


def permissions_json(config: QuiltConfig, *, shell: bool = False) -> str:
    """`.claude/settings.json` for a quilt, generated from the one table rather than written by hand.

    In a shell the file enumerates what is refused -- the complement of `AGENT_COMMANDS`, since Claude Code's deny rules beat its allow rules and an allow-only whitelist cannot be expressed (DR-71) -- and allows `AGENT_COMMANDS` themselves outright, so the person is never asked to approve an agent's own reads and annotations. Over MCP, the default, the loom server's tools are allowed as well, as `mcp__loom__*`; the shell stays open beside them because it filters a result and takes `--batch`, and so that a server that cannot start does not cost the agent all of loom. With `shell`, for an agent that has no MCP, the tools are left out. Loom's own refusal under an agent (K5) is the boundary either way. The paths are `loom.agents`'s: the agent's places allowed, and what is always protected and what `[agents] deny` names denied; every other file is left to the client, which asks or not as the person runs it.

    The file is read twice and its two path forms are for different readings (DR-343-ikmartin): as the project's settings, `/x` is the quilt root, but an untrusted folder's allow rules are dropped there; passed with `--settings`, every rule holds but `/x` is under `.claude/`. So the allows are relative to the working directory, the quilt root an agent is started in, and the denies keep `/`, which anchors `/config.toml` to the root where a relative `config.toml` would refuse every file of that name.
    """
    import json

    from loom.agents import claude_allows, claude_denies

    # `Edit` rules govern every file-editing tool; Claude Code does not match `Write` rules against paths at all
    allow = [f"Edit({d})" for d in claude_allows()]
    # the agent's own commands, allowed outright: approving each of them is friction with nothing to decide
    allow += [f"Bash(loom {c}*)" for c in [*sorted(AGENT_COMMANDS), *help_commands()]]
    if not shell:
        allow.append("mcp__loom__*")
    deny = [f"Edit({d})" for d in claude_denies(config)]
    deny += [f"Bash(loom {c}*)" for c in author_commands()]
    deny.append("Bash(rm *)")
    return json.dumps({"permissions": {"allow": allow, "deny": deny}}, indent=2) + "\n"


#: Where each agent tool reads the quilt's rules for its agents: one policy, loom's own, rendered per tool (DR-283-ikmartin).
CLAUDE_SETTINGS = ".claude/settings.json"
CODEX_RULES = ".codex/rules/loom.rules"
#: The rules loom last put in Claude Code's permission file, in `.loom/ai/`: `allow` or `deny`, a tab and the rule, a line each, so that a rule loom no longer writes is told from one of the person's.
RULES_FILE = ".loom-rules"


def _rules_wrote(root: Path) -> dict[str, set[str]]:
    """The rules loom last wrote into Claude Code's permission file, by list, as `RULES_FILE` records them; empty where it records none."""
    out: dict[str, set[str]] = {"allow": set(), "deny": set()}
    try:
        lines = (root / AI / RULES_FILE).read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        kind, _, rule = line.partition("\t")
        if kind in out and rule:
            out[kind].add(rule)
    return out


def record_rules(root: Path, generated: str) -> None:
    """Record loom's rules in `generated`, Claude Code's permission file as loom renders it, as the ones it wrote; nothing where the quilt has no `.loom/ai/`."""
    ours = json.loads(generated)["permissions"]
    said = "".join(f"{kind}\t{rule}\n" for kind in ("allow", "deny") for rule in ours[kind])
    p = root / AI / RULES_FILE
    if p.parent.is_dir() and (not p.is_file() or p.read_text(encoding="utf-8") != said):
        p.write_text(said, encoding="utf-8")


def settings_text(root: Path, generated: str) -> str | None:
    """Claude Code's permission file as loom writes it into the quilt at `root`: `generated`, loom's rules, then whatever else the file there holds, which is the person's; None when that file is not a JSON object, which loom leaves alone.

    The person's part is every other key and every rule loom neither renders now nor wrote last time (`RULES_FILE`) and that names no loom command or tool, so a rule a later loom or a narrower `[agents] deny` no longer renders goes, and a person's own `env`, hooks and rules stay, after loom's.
    """
    try:
        there = json.loads((root / CLAUDE_SETTINGS).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return generated
    except (OSError, ValueError):
        return None
    perms = there.get("permissions", {}) if isinstance(there, dict) else None
    if not isinstance(perms, dict) or not all(isinstance(perms.get(k, []), list) for k in ("allow", "deny")):
        return None
    ours = json.loads(generated)["permissions"]
    wrote = _rules_wrote(root)

    def loom_s(kind: str, rule: object) -> bool:
        return isinstance(rule, str) and (
            rule in ours[kind] or rule in wrote[kind] or rule.startswith(("Bash(loom ", "mcp__loom__"))
        )

    rest = {k: v for k, v in perms.items() if k not in ("allow", "deny")}
    lists = {kind: ours[kind] + [r for r in perms.get(kind, []) if not loom_s(kind, r)] for kind in ("allow", "deny")}
    return json.dumps({**there, "permissions": {**lists, **rest}}, indent=2) + "\n"


def codex_rules() -> str:
    """`.codex/rules/loom.rules`: the same policy as `permissions_json`, as Codex's command-prefix rules, in either variant, since these rules govern only the shell.

    Codex matches commands, not paths, so the path rules have no counterpart here; the author's own verbs are refused by loom itself for an agent's name whatever the tool (DR-185). Codex reads a project's rules only once the project is trusted. Unverified: Codex was not installed where this was written.
    """
    import json

    head = [
        "# Written by loom from its table of what an agent may run; `loom upgrade` rewrites it, and a quilt does not change it.",
        "# Rules of your own go in another file in this directory, which loom never touches.",
    ]

    def rule(words: list[str], decision: str) -> str:
        return f"prefix_rule(pattern = [{', '.join(json.dumps(w) for w in words)}], decision = {json.dumps(decision)})"

    body = [rule(["loom", *c.split()], "allow") for c in [*sorted(AGENT_COMMANDS), *help_commands()]]
    body += [rule(["loom", *c.split()], "forbidden") for c in author_commands()]
    body.append(rule(["rm"], "forbidden"))
    return "\n".join(head + body) + "\n"


def vendor_files(
    config: QuiltConfig,
    *,
    shell: bool = False,
    apps: list[str] | tuple[str, ...] | None = None,
    root: Path | None = None,
) -> dict[str, str]:
    """Quilt-relative path -> text for the permission files loom writes in a quilt with `config`, in one variant, of `apps` (by key, default every app); the agent root files are not among them (see `ensure_root_line`), nor the untracked MCP client files (`ai.clients`).

    With `root`, Claude Code's is what loom writes into that quilt, the person's own settings there kept after loom's rules (`settings_text`), and left out where the file there is not a JSON object, which loom leaves alone.
    """
    from loom.ai.clients import PROJECT

    wanted = {c.permissions for c in PROJECT if c.permissions and (apps is None or c.key in apps)}
    made = {CLAUDE_SETTINGS: lambda: permissions_json(config, shell=shell), CODEX_RULES: codex_rules}
    out = {rel: make() for rel, make in made.items() if rel in wanted}
    if root is not None and CLAUDE_SETTINGS in out:
        merged = settings_text(root, out[CLAUDE_SETTINGS])
        if merged is None:
            del out[CLAUDE_SETTINGS]
        else:
            out[CLAUDE_SETTINGS] = merged
    return out


def permission_files(
    root: Path, config: QuiltConfig, *, shell: bool, apps: list[str] | tuple[str, ...] | None
) -> tuple[dict[str, str], list[str], list[str]]:
    """(texts, merged, theirs): what loom writes of `apps`' permission files into the quilt at `root`; those of them that keep settings of the person's beside loom's rules; and those loom leaves alone."""
    bare = vendor_files(config, shell=shell, apps=apps)
    texts = vendor_files(config, shell=shell, apps=apps, root=root)
    merged = [rel for rel, text in texts.items() if text != bare[rel]]
    return texts, merged, [rel for rel in bare if rel not in texts]


def variant(root: Path) -> str | None:
    """Which way the quilt's agents reach loom, read off its committed files: Claude Code's permission file says `MCP` when it allows the loom server's tools, else `SHELL` when it allows `loom` commands; without one, the line loom put in an app's root file says which (`MCP_LINE`, `SHELL_LINE`), and failing that a file that starts the loom server says `MCP`; None with none of them. Codex's permission file is the same in either variant, and its server file is never committed, so neither says which. Never recorded anywhere else, so it cannot disagree with what the files say."""
    from loom.ai.clients import PROJECT, names_loom

    p = root / CLAUDE_SETTINGS
    try:
        allow = json.loads(p.read_text(encoding="utf-8"))["permissions"]["allow"]
    except (OSError, ValueError, KeyError, TypeError):
        allow = None
    if allow is not None:
        if "mcp__loom__*" in allow:
            return MCP
        if any(str(r).startswith("Bash(loom ") for r in allow):
            return SHELL
    for name in ROOT_FILES:
        try:
            lines = (root / name).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        if MCP_LINE in lines:
            return MCP
        if SHELL_LINE in lines:
            return SHELL
    for c in PROJECT:
        server = root / (c.file or "")
        if c.file and server.is_file() and names_loom(c, server.read_text(encoding="utf-8", errors="replace")):
            return MCP
    return None


@dataclass
class LayerReport:
    written: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)  # edited mode files left alone
    new_beside: list[str] = field(default_factory=list)  # <mode>.md.new written
    unchanged: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)  # loom's own, unedited, of a mode the quilt no longer has
    theirs: list[str] = field(default_factory=list)  # a file of the person's at a path loom writes, left alone
    merged: list[str] = field(default_factory=list)  # the person's, loom's part written into it, theirs kept


ROOT_FILES = ("CLAUDE.md", "AGENTS.md", "GEMINI.md")


def ensure_root_line(
    root: Path, write: bool = True, *, shell: bool = False, apps: list[str] | tuple[str, ...] | None = None
) -> list[str]:
    """Put loom's one line, the variant's, into the root file of each of `apps` (by key, default every app) without taking the files over; returns what was written, or with `write` false what would be.

    These are the files an agent reads before anything else, and they are also where an author writes what is true of *their* project — so loom contributes a line and owns nothing else. The other variant's line, and any line an older loom wrote (`OLD_LINES`), is replaced where it stands; everything around it is left exactly as the author left it. Loom writing the whole file is what clobbered hand-written instructions on every upgrade (DR-151).
    """
    from loom.ai.clients import PROJECT

    line, other = (SHELL_LINE, MCP_LINE) if shell else (MCP_LINE, SHELL_LINE)
    replaced = (other, *OLD_LINES)
    read = {c.root_file for c in PROJECT if apps is None or c.key in apps}
    written: list[str] = []
    for name in (n for n in ROOT_FILES if n in read):
        p = root / name
        existing = p.read_text(encoding="utf-8") if p.is_file() else ""
        lines = existing.splitlines()
        if line in lines:
            continue
        written.append(name)
        if not write:
            continue
        if any(x in replaced for x in lines):
            kept = [line if x in replaced else x for x in lines]
            # two old lines become one: the first keeps its place
            kept = [x for i, x in enumerate(kept) if x != line or kept.index(line) == i]
            p.write_text("\n".join(kept) + "\n", encoding="utf-8")
            continue
        p.write_text(existing.rstrip("\n") + ("\n\n" if existing.strip() else "") + line + "\n", encoding="utf-8")
    return written


def init_layer(root: Path, *, shell: bool = False, apps: list[str] | tuple[str, ...] | None = None) -> LayerReport:
    """Write `.loom/ai/` into a quilt that has no `.loom/ai/` yet, with the permission files, root lines and skills of `apps` (by key, default every app) in one variant: what agents may run is loom's, and the same whichever tool runs them (DR-283)."""
    from loom.ai.clients import chosen
    from loom.ai.skills import RECORD as SKILLS_RECORD
    from loom.ai.skills import write_skills

    ai = root / AI
    if ai.exists():
        raise FileExistsError(str(ai))
    rep = LayerReport()
    (ai / "modes").mkdir(parents=True)
    texts = tracked_docs(root)
    for rel, text in texts.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        rep.written.append(rel)
    for name in ("README.md",):
        (ai / name).write_text(_asset(name), encoding="utf-8")
        rep.written.append(f"{AI}/{name}")
    write_versions(root, texts)
    rep.written.append(f"{AI}/{VERSION_FILE}")
    config = quilt_config(root)
    texts, rep.merged, rep.theirs = permission_files(root, config, shell=shell, apps=apps)
    for rel, text in texts.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        rep.written.append(rel)
    if CLAUDE_SETTINGS in texts:
        record_rules(root, permissions_json(config, shell=shell))
        rep.written.append(f"{AI}/{RULES_FILE}")
    rep.written.extend(ensure_root_line(root, shell=shell, apps=apps))
    skills = write_skills(root, chosen(root, apps))
    rep.written += skills.written
    rep.theirs += skills.theirs
    if (ai / SKILLS_RECORD).is_file():
        rep.written.append(f"{AI}/{SKILLS_RECORD}")
    return rep


def upgrade_layer(
    root: Path, write: bool = True, *, shell: bool | None = None, apps: list[str] | tuple[str, ...] | None = None
) -> LayerReport:
    """Refresh the generated files of an existing `.loom/ai/`; keep edited mode files and write `.new` beside them.

    The permission files keep the variant they are in (`variant`) unless `shell` says which; with none, MCP. They, the root lines and the skills (`ai.skills`) are those of `apps`, by default the apps the quilt is set up for (`clients.chosen`), so a quilt set up for one app stays so. A skill of the person's at one of loom's paths is left alone (`theirs`), and loom's own of a mode that is gone is taken away (`removed`). With `write` false nothing is written and the report says what would be: `loom doctor`'s dry run, byte for byte what `loom upgrade` compares.
    """
    from loom.ai.clients import chosen
    from loom.ai.skills import write_skills

    if shell is None:
        shell = variant(root) == SHELL
    apps = chosen(root, apps)
    ai = root / AI
    rep = LayerReport()
    if not ai.is_dir():
        return rep
    recorded = read_versions(root)
    texts = tracked_docs(root)
    wrote_beside: dict[
        str, str
    ] = {}  # each .new as loom wrote it, so a later upgrade can tell the author's merge from it
    for rel, shipped in texts.items():
        p = root / rel
        name = Path(rel).name
        if not p.is_file():
            if write:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(shipped, encoding="utf-8")
            rep.written.append(rel)
            continue
        current = p.read_text(encoding="utf-8")
        if sha(current) == sha(shipped):
            rep.unchanged.append(rel)
            continue
        if recorded.get(name) == sha(current):
            if write:
                p.write_text(shipped, encoding="utf-8")  # untouched since it was shipped: refresh
            rep.written.append(rel)
        else:
            beside = p.with_name(name + ".new")
            there = beside.read_text(encoding="utf-8") if beside.is_file() else None
            last = recorded.get(name + ".new")
            rep.kept.append(rel)
            if there is None and last == sha(shipped):
                # merged and deleted: the author has this version, and nothing goes beside it until loom ships another
                wrote_beside[name + ".new"] = last
                continue
            # a .new as loom wrote it is brought up to date; one the author has begun merging into is theirs (K4)
            if there is None or (sha(there) == last and there != shipped):
                if write:
                    beside.write_text(shipped, encoding="utf-8")
                wrote_beside[name + ".new"] = sha(shipped)
            elif last:
                wrote_beside[name + ".new"] = last
            rep.new_beside.append(rel + ".new")
    names = {Path(rel).name for rel in texts}
    new_versions = {name: h for name, h in recorded.items() if name in names} | wrote_beside
    for rel, shipped in texts.items():
        if rel in rep.kept:
            continue  # the record keeps the hash of what was shipped last time, so a later upgrade still sees the edit
        new_versions[Path(rel).name] = sha(shipped)
    if write:
        (ai / VERSION_FILE).write_text(
            "\n".join(f"{k} {v}" for k, v in sorted(new_versions.items())) + "\n", encoding="utf-8"
        )
    for name in ("README.md",):
        p = ai / name
        text = _asset(name)
        if not p.is_file() or p.read_text(encoding="utf-8") != text:
            if write:
                p.write_text(text, encoding="utf-8")
            rep.written.append(f"{AI}/{name}")
        else:
            rep.unchanged.append(f"{AI}/{name}")
    written, unchanged = write_permissions(root, quilt_config(root), shell=shell, write=write, apps=apps, report=rep)
    rep.written += written
    rep.unchanged += unchanged
    rep.written.extend(ensure_root_line(root, write, shell=shell, apps=apps))
    skills = write_skills(root, apps, write=write)
    rep.written += skills.written
    rep.unchanged += skills.unchanged
    rep.removed += skills.removed
    rep.theirs += skills.theirs
    return rep


def write_permissions(
    root: Path,
    config: QuiltConfig,
    *,
    shell: bool,
    write: bool = True,
    apps: list[str] | tuple[str, ...] | None = None,
    report: LayerReport | None = None,
) -> tuple[list[str], list[str]]:
    """(written, unchanged): the permission files of `apps` (by default the apps the quilt is set up for, `clients.chosen`) rewritten to what `config` and this loom make them, in one variant, the person's own settings in Claude Code's kept after loom's rules (`settings_text`).

    A missing one of those apps is written like a stale one; `upgrade_layer` and the viewer's Update Claude Code both come here. `report`, where given, gains the files that keep settings of the person's (`merged`) and those left alone (`theirs`).
    """
    from loom.ai.clients import chosen

    written: list[str] = []
    unchanged: list[str] = []
    texts, merged, theirs = permission_files(root, config, shell=shell, apps=chosen(root, apps))
    if report is not None:
        report.merged += merged
        report.theirs += theirs
    if write and CLAUDE_SETTINGS in texts:
        record_rules(root, permissions_json(config, shell=shell))
    for rel, text in texts.items():
        p = root / rel
        if p.is_file() and p.read_text(encoding="utf-8") == text:
            unchanged.append(rel)
            continue
        if write:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        written.append(rel)
    return written, unchanged


def permissions_stale(root: Path, config: QuiltConfig) -> bool:
    """Whether Claude Code's permission file is there and not what `config` and this loom make it, in the variant it is in, the person's own settings in it kept (`settings_text`)."""
    path = root / CLAUDE_SETTINGS
    if not path.is_file():
        return False
    want = vendor_files(config, shell=variant(root) == SHELL, root=root).get(CLAUDE_SETTINGS)
    return want is not None and path.read_text(encoding="utf-8") != want


def settings_deny_paths(config: QuiltConfig, *, shell: bool = False) -> list[str]:
    """The Edit/Write patterns and commands the generated settings deny for a quilt with `config`, for tests."""
    data = json.loads(permissions_json(config, shell=shell))
    return [str(r) for r in data["permissions"]["deny"]]
