"""`loom ai init` and `loom upgrade`: the `.loom/agents/instructions/` directory, the vendor files, and their refresh.

Mode files are the author's once written: `.loom-modes-version` records the shipped hash of each, so upgrade overwrites only files still equal to what it shipped and writes `<mode>.md.new` beside an edited one.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loom import own
from loom.paths import AI
from loom.scan.quilt import QuiltConfig

if TYPE_CHECKING:
    from loom.ai.clients import Client

#: The modes loom ships, in the order the index lists them, read through `modes` alone. Each file's `When it fits:` line is the index's entry for it, the one copy; a file in a quilt's `.loom/agents/instructions/modes/` whose name is not here is not a mode, so one loom no longer ships is inert.
MODES = ["quick", "question", "audit", "referee", "review", "simplify", "flow", "draft", "formalize"]
RULES = "rules.md"  # `.loom/agents/instructions/rules.md`: not a mode, and no longer filed among them
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
        # what is asked of agents and what they ask of the person, and what is known of a result; comparing, attesting and answering an agent are the person's
        "tasks", "tasks take", "tasks done", "tasks answer", "tasks withdraw", "ask", "evidence",
        # whether formalization is on here, and asking loom to check the Lean, whose record is loom's own; turning it on or off is the person's
        "formal", "formal check",
        # the library's web: reading it, giving a stub its text, proposing a node or a correction, and having loom digest a work from its source; comparing a node with its paper is the person's
        "library node", "library search", "library uses", "library rests-on", "library stubs", "library work",
        "library fill", "library propose", "library correct", "library digest",
        # the MCP server an agent's app starts, often from a shell that already marks an agent
        "mcp",
    }
)  # fmt: skip
#: What each agent command does to the quilt, which is what an MCP tool's hints say (`loom.mcp.tools.hints`): `read` changes nothing but loom's own command log; `derive` rewrites what loom derives, in `.loom/cache/`; `write` adds to a record, a session or a document of the agent's, or moves the agent's own marker (`since`); `replace` puts new text in place of a page's. Every command in `AGENT_COMMANDS` is here, and nothing else.
ACTS: dict[str, str] = {
    **dict.fromkeys(
        (
            "deps", "doctor", "downstream", "here", "history", "history show", "history verify", "link", "lint", "search",
            "source", "status", "changes", "ai annotations", "ai drafts", "ai mode", "ai orient", "session list",
            "tasks", "evidence", "formal", "library node", "library search", "library uses", "library rests-on",
            "library stubs", "library work",
        ),
        "read",
    ),
    **dict.fromkeys(("build", "check", "compile", "id", "serve"), "derive"),
    **dict.fromkeys(
        (
            "annotate", "suggest", "draft", "new", "since", "ai refresh", "session new", "session rename", "session say",
            "mcp", "ask", "tasks take", "tasks done",
            "tasks answer", "tasks withdraw", "formal check", "library fill", "library propose", "library correct",
            "library digest",
        ),
        "write",
    ),
    "write": "replace",
}  # fmt: skip
#: The options of an agent command that are the author's acts, which its MCP tool leaves out: an agent reads what waits on the person, and only the person keeps or discards it.
AUTHOR_OPTIONS: dict[str, frozenset[str]] = {
    "changes": frozenset({"--keep", "--discard", "--keep-all", "--discard-all", "--why"}),
}
#: Agent commands that are no MCP tool: the server itself, and `serve`, which runs until stopped.
NOT_TOOLS = frozenset({"mcp", "serve"})
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
    """Every leaf command loom offers, as the path a person types: `accept`, `ai orient`, `library add`."""
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

    Every listing of the modes asks here: the orientation's index, the MCP prompts and the check of a prompt's name, `loom ai mode`, which types each mode names, the manifest's `agents.modes`, and the mode files the agent layer writes. Today a quilt's modes are loom's (`MODES`) whatever its `.loom/agents/instructions/modes/` holds, so a quilt's own set is a change to this function and not to its callers.
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


def save_mode(root: Path, name: str, text: str | None, *, was: str | None = None, actor: str | None = None) -> str:
    """Write the quilt's copy of mode `name` through the door (`writes.act`): `text`, or with None loom's own, as Settings › Modes saves and puts back.

    Parameters
    ----------
    root : Path
        The quilt.
    name : str
        One of the quilt's `modes`.
    text : str or None
        The mode's whole new text; None puts loom's back, recording it as loom's in `.loom-modes-version` so that `loom upgrade` refreshes it again, and taking away a `<name>.md.new` loom wrote beside the edit (one the person began merging into stays).
    was : str, optional
        The text the person was shown, the quilt's copy else loom's: refused (`changed`) when the file holds anything else under the lock.
    actor : str, optional
        Who asked, for the journal.

    Returns
    -------
    str
        What was done, in a sentence.

    Raises
    ------
    WriteRefused
        `no-such-mode` (404), `no-agent-layer` where the quilt has no agents' instructions yet, `not-a-file` where the copy is reached through a link or is no regular file, `changed`, or the door's own.
    """
    from loom.writes import WriteRefused, act, history_of

    if name not in modes(root):
        raise WriteRefused("no-such-mode", f"{name} is not one of this quilt's modes ({', '.join(modes(root))})", 404)
    if not (root / AI).is_dir() or blocker(root, AI, folder=True):
        raise WriteRefused(
            "no-agent-layer",
            "this quilt has no instructions for agents yet, so its modes are loom's own; set an agent's app up here first",
        )
    rel = f"{AI}/modes/{name}.md"
    if why := blocker(root, rel) or blocker(root, f"{rel}.new"):
        raise WriteRefused("not-a-file", f"{why}, so nothing was written")
    shipped = tracked_docs(root)[rel]
    want = shipped if text is None else text
    with act(root, history_of(root), "agents", actor) as w:
        now = w.text(rel)
        if was is not None and (shipped if now is None else now) != was:
            raise WriteRefused(
                "changed", f"the {name} mode changed since it was shown, so nothing was written; look at it again"
            )
        wrote = now != want
        if wrote:
            w.replace(rel, want.encode("utf-8"))
        if text is None:
            versions_rel = f"{AI}/{VERSION_FILE}"
            before = w.text(versions_rel) or ""
            recorded = dict(line.split() for line in before.splitlines() if len(line.split()) == 2)
            recorded[f"{name}.md"] = sha(shipped)
            beside = w.text(f"{rel}.new")
            if beside is not None and (beside == shipped or sha(beside) == recorded.get(f"{name}.md.new")):
                w.remove_own(f"{rel}.new")
                recorded.pop(f"{name}.md.new", None)
                wrote = True
            after = "".join(f"{k} {v}\n" for k, v in sorted(recorded.items()))
            if after != before:
                w.replace(versions_rel, after.encode("utf-8"))
                wrote = True
    if text is None:
        return (
            f"put the {name} mode back to loom's"
            if wrote
            else f"the {name} mode is loom's already; nothing was written"
        )
    return f"saved the {name} mode" if wrote else f"the {name} mode reads so already; nothing was written"


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
    own.write_text(root / AI / VERSION_FILE, "\n".join(lines) + "\n", encoding="utf-8", root=root)


def quilt_config(root: Path) -> QuiltConfig:
    """The config of the quilt at `root`, or the defaults where there is none yet: the names the permission file is written with."""
    from loom.scan.quilt import NoQuiltError, load_quilt

    try:
        return load_quilt(root).config
    except NoQuiltError:
        return QuiltConfig()


#: What an agent runs in the quilt's Lean project without being asked each time (decision 10 of plan 0.32): Lake's build, and Lean on one file in the project's environment. Never `lake update` or `lake exe`, which reach the network or run a program; fetching Mathlib is the person's switch.
LAKE_COMMANDS = ("lake build", "lake env lean")


def lean_rules() -> tuple[list[str], list[str]]:
    """Claude Code's rules for the quilt's Lean project (`formal.install.LEAN`): the agent edits its modules and runs `LAKE_COMMANDS` without asking, and never edits loom's marker module or the files that say what the project builds and fetches, which the person's switch writes and loom's check refuses changed.

    Returns
    -------
    tuple of list of str
        The `allow` rules, relative like every allow, and the `deny` rules, anchored with `/`.
    """
    from loom.formal.install import LEAN, MARKER_MODULE

    allow = [f"Edit({LEAN}/**)", *(f"Bash({c}*)" for c in LAKE_COMMANDS)]
    deny = [
        f"Edit(/{LEAN}/{f})" for f in (f"{MARKER_MODULE}.lean", "lakefile.toml", "lean-toolchain", "lake-manifest.json")
    ]
    return allow, deny


def permissions_json(config: QuiltConfig, *, shell: bool = False) -> str:
    """`.claude/settings.json` for a quilt, generated from the one table rather than written by hand.

    In a shell the file enumerates what is refused -- the complement of `AGENT_COMMANDS`, since Claude Code's deny rules beat its allow rules and an allow-only whitelist cannot be expressed (DR-71) -- and allows `AGENT_COMMANDS` themselves outright, so the person is never asked to approve an agent's own reads and annotations. Over MCP, the default, the loom server's tools are allowed as well, as `mcp__loom__*`; the shell stays open beside them because it filters a result and takes `--batch`, and so that a server that cannot start does not cost the agent all of loom. With `shell`, for an agent that has no MCP, the tools are left out. Loom's own refusal under an agent (K5) is the boundary either way. The paths are `loom.agents`'s: the agent's places allowed, and what is always protected and what `[agents] deny` names denied; then the Lean project's (`lean_rules`), whose modules and build an agent works in without asking; every other file is left to the client, which asks or not as the person runs it.

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
    lean_allow, lean_deny = lean_rules()
    allow += lean_allow
    deny = [f"Edit({d})" for d in claude_denies(config)]
    deny += lean_deny
    deny += [f"Bash(loom {c}*)" for c in author_commands()]
    deny.append("Bash(rm *)")
    return json.dumps({"permissions": {"allow": allow, "deny": deny}}, indent=2, ensure_ascii=False) + "\n"


#: Where each agent tool reads the quilt's rules for its agents: one policy, loom's own, rendered per tool (DR-283-ikmartin).
CLAUDE_SETTINGS = ".claude/settings.json"
CODEX_RULES = ".codex/rules/loom.rules"
#: The rules loom last put in Claude Code's permission file, in `.loom/agents/instructions/`: `allow` or `deny`, a tab and the rule, a line each, so that a rule loom no longer writes is told from one of the person's.
RULES_FILE = ".loom-rules"


def blocker(root: Path, rel: str, *, folder: bool = False) -> str:
    """Why loom may not read or write quilt-relative `rel` as a file of the quilt's own, or '' where it may: some part of the path is a link, which may lead out of the quilt, or is not a directory, or the last is not a regular file (a directory with `folder`), which a FIFO would make a read wait on for ever. An absent path is no blocker."""
    p = root
    parts = rel.split("/")
    for i, part in enumerate(parts):
        p = p / part
        try:
            mode = os.lstat(p).st_mode
        except FileNotFoundError:
            return ""
        except OSError as exc:
            return f"`{p.relative_to(root).as_posix()}` cannot be read ({exc.strerror})"
        here = p.relative_to(root).as_posix()
        if stat.S_ISLNK(mode):
            return f"`{here}` is a link, and loom reads and writes nothing through one"
        last = i == len(parts) - 1 and not folder
        if not (stat.S_ISREG(mode) if last else stat.S_ISDIR(mode)):
            return f"`{here}` is not a {'file' if last else 'directory'}"
    return ""


def read_plain(root: Path, rel: str) -> str | None:
    """The text of quilt-relative `rel` where it is a regular file reached through no link (`blocker`), read so that nothing can make it wait; None where it is absent, blocked or not UTF-8."""
    if blocker(root, rel):
        return None
    try:
        fd = os.open(
            root / rel, os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        )
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        with os.fdopen(os.dup(fd), "rb") as fh:
            return fh.read().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    finally:
        os.close(fd)


def refuse_layer(root: Path) -> None:
    """Refuse (`WriteRefused`) to write the agent layer where `.loom/agents/instructions/` is there and not a directory of the quilt's own (`blocker`): what is written there through a link lands outside the quilt."""
    from loom.writes import WriteRefused

    why = blocker(root, AI, folder=True)
    if why:
        raise WriteRefused(
            "not-writable", f"loom writes nothing into {AI}/, since {why}; make it a directory of the quilt's own"
        )


def _rules_wrote(root: Path) -> dict[str, set[str]] | None:
    """The rules loom last wrote into Claude Code's permission file, by list, as `RULES_FILE` records them; None where there is no record, or none that can be read (`read_plain`)."""
    text = read_plain(root, f"{AI}/{RULES_FILE}")
    if text is None:
        return None
    out: dict[str, set[str]] = {"allow": set(), "deny": set()}
    for line in text.splitlines():
        kind, _, rule = line.partition("\t")
        if kind in out and rule:
            out[kind].add(rule)
    return out


def record_rules(root: Path, generated: str, *, before: list[str] | None = None) -> None:
    """Record loom's rules in `generated`, Claude Code's permission file as loom renders it, as the ones it wrote, once that file is written; nothing where the quilt has no `.loom/agents/instructions/`.

    With `before`, called ahead of writing that file: the record keeps every rule it held, and each of `before` (`Settings.dropped`, loom's rules in the file as it stands), beside what `generated` renders, so a write that fails at any point leaves a record naming every rule of loom's in the file.
    """
    ours = json.loads(generated)["permissions"]
    rules = {kind: list(ours[kind]) for kind in ("allow", "deny")}
    if before is not None:
        held = _rules_wrote(root) or {"allow": set(), "deny": set()}
        for d in before:
            kind, _, rule = d.partition(" ")
            held[kind].add(rule)
        for kind in rules:
            rules[kind] += sorted(held[kind] - set(rules[kind]))
    said = "".join(f"{kind}\t{rule}\n" for kind in ("allow", "deny") for rule in rules[kind])
    if (root / AI).is_dir() and read_plain(root, f"{AI}/{RULES_FILE}") != said:
        _write(root, f"{AI}/{RULES_FILE}", said)


#: `_write`'s `expect` for a text not made from the file it replaces.
_UNREAD: Any = object()


def _write(root: Path, rel: str, text: str, expect: str | None = _UNREAD) -> None:
    """Write one file of the agent layer whole or not at all, or refuse in a sentence where it cannot be written.

    `expect` is the text a person's file was read as when `text` was made from it, None for a file that was absent (`writes.put`'s `expect`), so a save made since is refused (`changed`) rather than overwritten. A person's file goes through the door (`loom.writes.put`), loom's own record in `.loom/` beside it: each written beside and moved into place, keeping the file's mode, so a write cut short (a full disk, a size limit) leaves the person's file as it was; a file without write permission is refused, as writing it in place would be.
    """
    import errno
    import secrets

    from loom.paths import LOOM
    from loom.writes import ANY, WriteRefused, put

    p = root / rel
    tmp = p.with_name(f".{p.name}.{secrets.token_hex(6)}.tmp")
    try:
        if not (rel == LOOM or rel.startswith(f"{LOOM}/")):
            if p.exists() and not os.access(p, os.W_OK):
                raise PermissionError(errno.EACCES, os.strerror(errno.EACCES), str(p))
            # a person's file: through the door, which writes it beside and moves it into place, keeping its mode
            seen = ANY if expect is _UNREAD else (None if expect is None else expect.encode("utf-8"))
            put(root, None, rel, text.encode("utf-8"), kind="agents", expect=seen)
            return
        # loom's own record of the layer, in `.loom/`, written beside and moved into place without reading what is there
        own.mkdir(p.parent, root=root)
        with own.open(tmp, "xb", root=root) as fh:
            fh.write(text.encode("utf-8"))
        own.replace(tmp, p, root=root)
    except OSError as exc:
        raise WriteRefused(
            "not-writable",
            f"loom could not write {rel} ({exc.strerror}); nothing after it was written, so run this again once it can be",
        ) from exc
    finally:
        with contextlib.suppress(OSError):
            own.unlink(tmp, root=root, missing_ok=True)


@dataclass
class Settings:
    """What loom makes of Claude Code's permission file in one quilt.

    `text` is what loom writes, None where it leaves the file alone, and `why` says for what; `dropped` is each rule of loom's own it takes out, `allow RULE` or `deny RULE`, since it no longer renders it; `read` is the file's text `text` was merged into, None where there was none, which the write expects to find (`writes.put`'s `expect`).
    """

    text: str | None
    why: str = ""
    dropped: list[str] = field(default_factory=list)
    read: str | None = None


def settings_for(root: Path, generated: str) -> Settings:
    """Claude Code's permission file as loom writes it into the quilt at `root`: `generated`, loom's rules, merged into whatever the file there holds, which is the person's.

    A rule is loom's where loom renders it now or `RULES_FILE` records loom writing it; with no record, an `allow` naming a loom command or tool is taken for an older loom's too. Every other rule is the person's, allow or deny, and kept after loom's, with every other key in its place and its text as written, a byte-order mark included. A file that is a link, not a regular file, empty, not UTF-8 or not a JSON object whose `permissions` holds `allow` and `deny` lists is left alone, and `why` says which.
    """
    why = blocker(root, CLAUDE_SETTINGS)
    if why:
        return Settings(None, why)
    p = root / CLAUDE_SETTINGS
    if not p.exists():
        return Settings(generated)
    text = read_plain(root, CLAUDE_SETTINGS)
    if text is None:
        return Settings(None, f"`{CLAUDE_SETTINGS}` cannot be read as UTF-8")
    bom = "\ufeff" if text.startswith("\ufeff") else ""
    body = text[len(bom) :]
    if not body.strip():
        return Settings(None, f"`{CLAUDE_SETTINGS}` is empty")
    try:
        there = json.loads(body)
    except ValueError:
        return Settings(None, f"`{CLAUDE_SETTINGS}` is not JSON")
    perms = there.get("permissions", {}) if isinstance(there, dict) else None
    if not isinstance(perms, dict) or not all(isinstance(perms.get(k, []), list) for k in ("allow", "deny")):
        return Settings(
            None, f"`{CLAUDE_SETTINGS}` is not a JSON object whose `permissions` holds `allow` and `deny` lists"
        )
    ours = json.loads(generated)["permissions"]
    wrote = _rules_wrote(root)

    def loom_s(kind: str, rule: object) -> bool:
        if not isinstance(rule, str):
            return False
        if rule in ours[kind]:
            return True
        if wrote is not None:
            return rule in wrote[kind]
        return kind == "allow" and rule.startswith(("Bash(loom ", "mcp__loom__"))

    lists = {kind: ours[kind] + [r for r in perms.get(kind, []) if not loom_s(kind, r)] for kind in ("allow", "deny")}
    dropped = [
        f"{kind} {r}"
        for kind in ("allow", "deny")
        for r in perms.get(kind, [])
        if loom_s(kind, r) and r not in ours[kind]
    ]
    merged = {k: lists.get(k, v) for k, v in perms.items()}
    for kind in ("allow", "deny"):
        merged.setdefault(kind, lists[kind])
    out = dict(there)
    out["permissions"] = merged
    return Settings(bom + json.dumps(out, indent=2, ensure_ascii=False) + "\n", dropped=dropped, read=text)


def settings_left(root: Path, config: QuiltConfig | None = None) -> str:
    """Why loom leaves Claude Code's permission file in the quilt at `root` alone, so that none of its rules is in force there, or '' where it writes it."""
    return settings_for(root, permissions_json(config or quilt_config(root))).why


def codex_rules() -> str:
    """`.codex/rules/loom.rules`: the same policy as `permissions_json`, as Codex's command-prefix rules, in either variant, since these rules govern only the shell.

    Codex matches commands, not paths, so the path rules have no counterpart here, and Lake's build is allowed as a command (`LAKE_COMMANDS`); the author's own verbs are refused by loom itself for an agent's name whatever the tool (DR-185). Codex reads a project's rules only once the project is trusted. Unverified: Codex was not installed where this was written.
    """
    import json

    head = [
        "# Written by loom from its table of what an agent may run; `loom upgrade` rewrites it, and a quilt does not change it.",
        "# Rules of your own go in another file in this directory, which loom never touches.",
    ]

    def rule(words: list[str], decision: str) -> str:
        return f"prefix_rule(pattern = [{', '.join(json.dumps(w) for w in words)}], decision = {json.dumps(decision)})"

    body = [rule(["loom", *c.split()], "allow") for c in [*sorted(AGENT_COMMANDS), *help_commands()]]
    body += [rule(c.split(), "allow") for c in LAKE_COMMANDS]
    body += [rule(["loom", *c.split()], "forbidden") for c in author_commands()]
    body.append(rule(["rm"], "forbidden"))
    return "\n".join(head + body) + "\n"


def _claude_settings(config: QuiltConfig, shell: bool) -> str:
    return permissions_json(config, shell=shell)


def _codex_rules(config: QuiltConfig, shell: bool) -> str:
    return codex_rules()


def _claude_holds(root: Path, config: QuiltConfig) -> bool:
    """Whether Claude Code's settings in the quilt at `root` refuse an edit in every place `config`'s list names, as they stand now: a file loom writes into (`settings_left`), whose `deny` holds each of loom's `Edit` rules for the list."""
    from loom.agents import claude_denies

    if settings_left(root, config):
        return False
    try:
        data = json.loads((read_plain(root, CLAUDE_SETTINGS) or "").removeprefix("\ufeff"))
        deny = set(data["permissions"]["deny"])
    except (ValueError, KeyError, TypeError):
        return False
    return {f"Edit({d})" for d in claude_denies(config)} <= deny


#: Each permission file loom writes, by quilt-relative path: what writes it, and, for one that carries the `[agents] deny` list so that the app reading it refuses an agent's own edit there, what says whether the file on disk holds the list now; None for one that cannot. Claude Code's settings render the list as `Edit` denies; Codex's rules are command prefixes, which govern only the shell.
PERMISSION_WRITERS: dict[str, tuple[Callable[[QuiltConfig, bool], str], Callable[[Path, QuiltConfig], bool] | None]] = {
    CLAUDE_SETTINGS: (_claude_settings, _claude_holds),
    CODEX_RULES: (_codex_rules, None),
}


def holds_deny(client: Client) -> bool:
    """Whether the permission file loom writes for `client`'s app can carry the `[agents] deny` list (`PERMISSION_WRITERS`); an app with none is only told the list."""
    return (
        client.permissions is not None
        and PERMISSION_WRITERS.get(client.permissions, (_codex_rules, None))[1] is not None
    )


def holds_deny_now(root: Path, config: QuiltConfig, client: Client) -> bool:
    """Whether `client`'s app is refused an edit in the places `config`'s list names by its permission file as it stands in the quilt at `root`: one loom writes that carries the list and holds it now, so a list changed by hand since the file was written, or a file loom leaves alone, holds the app to nothing."""
    if not holds_deny(client) or client.permissions is None:
        return False
    check = PERMISSION_WRITERS[client.permissions][1]
    return check is not None and check(root, config)


def vendor_files(
    config: QuiltConfig,
    *,
    shell: bool = False,
    apps: list[str] | tuple[str, ...] | None = None,
    root: Path | None = None,
) -> dict[str, str]:
    """Quilt-relative path -> text for the permission files loom writes in a quilt with `config`, in one variant, of `apps` (by key, default every app); the agent root files are not among them (see `ensure_root_line`), nor the untracked MCP client files (`ai.clients`).

    With `root`, Claude Code's is what loom writes into that quilt, merged with the person's own settings there (`settings_for`), and left out where loom leaves that file alone.
    """
    from loom.ai.clients import PROJECT

    wanted = {c.permissions for c in PROJECT if c.permissions and (apps is None or c.key in apps)}
    out = {rel: write(config, shell) for rel, (write, _) in PERMISSION_WRITERS.items() if rel in wanted}
    if root is not None and CLAUDE_SETTINGS in out:
        merged = settings_for(root, out[CLAUDE_SETTINGS]).text
        if merged is None:
            del out[CLAUDE_SETTINGS]
        else:
            out[CLAUDE_SETTINGS] = merged
    return out


@dataclass
class Permissions:
    """What loom writes of the permission files into one quilt: `texts` by quilt-relative path; `merged`, those that keep settings of the person's beside loom's rules; `theirs`, those loom leaves alone; `dropped`, loom's own rules it takes out, `FILE: allow RULE` or `FILE: deny RULE`."""

    texts: dict[str, str]
    merged: list[str] = field(default_factory=list)
    theirs: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    #: the person's text a merged file was made from, which its write expects to find
    read: dict[str, str | None] = field(default_factory=dict)
    #: Claude Code's `Settings.dropped`, as `record_rules` takes it.
    rules_out: list[str] = field(default_factory=list)


def permission_files(
    root: Path, config: QuiltConfig, *, shell: bool, apps: list[str] | tuple[str, ...] | None
) -> Permissions:
    """What loom writes of `apps`' permission files into the quilt at `root`, in one variant (`Permissions`)."""
    bare = vendor_files(config, shell=shell, apps=apps)
    out = Permissions(
        texts={rel: text for rel, text in bare.items() if rel == CLAUDE_SETTINGS or not blocker(root, rel)}
    )
    out.theirs = [rel for rel in bare if rel not in out.texts]
    if CLAUDE_SETTINGS in bare:
        got = settings_for(root, bare[CLAUDE_SETTINGS])
        if got.text is None:
            del out.texts[CLAUDE_SETTINGS]
            out.theirs.append(CLAUDE_SETTINGS)
        else:
            out.texts[CLAUDE_SETTINGS] = got.text
            out.read[CLAUDE_SETTINGS] = got.read
            if got.text != bare[CLAUDE_SETTINGS]:
                out.merged.append(CLAUDE_SETTINGS)
            out.dropped = [f"{CLAUDE_SETTINGS}: {d}" for d in got.dropped]
            out.rules_out = got.dropped
    return out


def variant(root: Path) -> str | None:
    """Which way the quilt's agents reach loom, read off its committed files: Claude Code's permission file says `MCP` when it allows the loom server's tools, else `SHELL` when it allows `loom` commands; without one, the line loom put in an app's root file says which (`MCP_LINE`, `SHELL_LINE`), and failing that a file that starts the loom server says `MCP`; None with none of them. Codex's permission file is the same in either variant, and its server file is never committed, so neither says which. Never recorded anywhere else, so it cannot disagree with what the files say. Each file is read only where it is a regular file reached through no link (`read_plain`), so nothing in a copied quilt can make this wait."""
    from loom.ai.clients import PROJECT, names_loom

    try:
        allow = json.loads((read_plain(root, CLAUDE_SETTINGS) or "").removeprefix("\ufeff"))["permissions"]["allow"]
    except (ValueError, KeyError, TypeError):
        allow = None
    if allow is not None:
        if "mcp__loom__*" in allow:
            return MCP
        if any(str(r).startswith("Bash(loom ") for r in allow):
            return SHELL
    for name in ROOT_FILES:
        lines = (read_plain(root, name) or "").splitlines()
        if MCP_LINE in lines:
            return MCP
        if SHELL_LINE in lines:
            return SHELL
    for c in PROJECT:
        text = read_plain(root, c.file) if c.file else None
        if text is not None and names_loom(c, text):
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
    dropped: list[str] = field(
        default_factory=list
    )  # loom's own rules taken out of a permission file: `FILE: allow RULE`


ROOT_FILES = ("CLAUDE.md", "AGENTS.md", "GEMINI.md")


def ensure_root_line(
    root: Path,
    write: bool = True,
    *,
    shell: bool = False,
    apps: list[str] | tuple[str, ...] | None = None,
    report: LayerReport | None = None,
) -> list[str]:
    """Put loom's one line, the variant's, into the root file of each of `apps` (by key, default every app) without taking the files over; returns what was written, or with `write` false what would be.

    These are the files an agent reads before anything else, and they are also where an author writes what is true of *their* project — so loom contributes a line and owns nothing else. The other variant's line, and any line an older loom wrote (`OLD_LINES`), is replaced where it stands; everything around it is left exactly as the author left it. Loom writing the whole file is what clobbered hand-written instructions on every upgrade (DR-151). A root file that is a link, not a regular file or not UTF-8 is left alone and, with `report`, named in its `theirs`.
    """
    from loom.ai.clients import PROJECT

    line, other = (SHELL_LINE, MCP_LINE) if shell else (MCP_LINE, SHELL_LINE)
    replaced = (other, *OLD_LINES)
    read = {c.root_file for c in PROJECT if apps is None or c.key in apps}
    written: list[str] = []
    for name in (n for n in ROOT_FILES if n in read):
        p = root / name
        there = read_plain(root, name)
        if there is None and os.path.lexists(p):
            if report is not None:
                report.theirs.append(name)
            continue
        existing = there or ""
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
            _write(root, name, "\n".join(kept) + "\n", expect=there)
            continue
        _write(root, name, existing.rstrip("\n") + ("\n\n" if existing.strip() else "") + line + "\n", expect=there)
    return written


def init_layer(root: Path, *, shell: bool = False, apps: list[str] | tuple[str, ...] | None = None) -> LayerReport:
    """Write `.loom/agents/instructions/` into a quilt that has no `.loom/agents/instructions/` yet, with the permission files, root lines and skills of `apps` (by key, default every app) in one variant: what agents may run is loom's, and the same whichever tool runs them (DR-283)."""
    from loom.ai.clients import chosen
    from loom.ai.skills import RECORD as SKILLS_RECORD
    from loom.ai.skills import write_skills

    ai = root / AI
    if ai.exists():
        raise FileExistsError(str(ai))
    rep = LayerReport()
    own.mkdir(ai / "modes", root=root, exist_ok=False)
    texts = tracked_docs(root)
    for rel, text in texts.items():
        _write(root, rel, text)
        rep.written.append(rel)
    for name in ("README.md",):
        own.write_text(ai / name, _asset(name), encoding="utf-8", root=root)
        rep.written.append(f"{AI}/{name}")
    write_versions(root, texts)
    rep.written.append(f"{AI}/{VERSION_FILE}")
    config = quilt_config(root)
    made = permission_files(root, config, shell=shell, apps=apps)
    rep.merged, rep.theirs, rep.dropped = made.merged, made.theirs, made.dropped
    generated = permissions_json(config, shell=shell)
    for rel, text in made.texts.items():
        if rel == CLAUDE_SETTINGS:
            record_rules(root, generated, before=made.rules_out)
        _write(root, rel, text, **({"expect": made.read[rel]} if rel in made.read else {}))
        rep.written.append(rel)
    if CLAUDE_SETTINGS in made.texts:
        # before the file and after it, so a write that fails at any point leaves the record naming every rule of loom's there
        record_rules(root, generated)
        rep.written.append(f"{AI}/{RULES_FILE}")
    rep.written.extend(ensure_root_line(root, shell=shell, apps=apps, report=rep))
    skills = write_skills(root, chosen(root, apps))
    rep.written += skills.written
    rep.theirs += skills.theirs
    if (ai / SKILLS_RECORD).is_file():
        rep.written.append(f"{AI}/{SKILLS_RECORD}")
    return rep


def upgrade_layer(
    root: Path, write: bool = True, *, shell: bool | None = None, apps: list[str] | tuple[str, ...] | None = None
) -> LayerReport:
    """Refresh the generated files of an existing `.loom/agents/instructions/`; keep edited mode files and write `.new` beside them. Nothing where `.loom/agents/instructions/` is absent or not a directory of the quilt's own (`blocker`).

    The permission files keep the variant they are in (`variant`) unless `shell` says which; with none, MCP. They, the root lines and the skills (`ai.skills`) are those of `apps`, by default the apps the quilt is set up for (`clients.chosen`), so a quilt set up for one app stays so. A skill of the person's at one of loom's paths, or a mode file they edited of a mode that is gone, is left alone (`theirs`), and loom's own skill and mode file of a mode that is gone are taken away (`removed`). With `write` false nothing is written and the report says what would be: `loom doctor`'s dry run, byte for byte what `loom upgrade` compares.
    """
    from loom.ai.clients import chosen
    from loom.ai.skills import write_skills

    if shell is None:
        shell = variant(root) == SHELL
    apps = chosen(root, apps)
    ai = root / AI
    rep = LayerReport()
    if not ai.is_dir() or blocker(root, AI, folder=True):
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
                _write(root, rel, shipped)
            rep.written.append(rel)
            continue
        current = p.read_text(encoding="utf-8")
        if sha(current) == sha(shipped):
            rep.unchanged.append(rel)
            continue
        if recorded.get(name) == sha(current):
            if write:
                _write(root, rel, shipped)  # untouched since it was shipped: refresh
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
                    _write(root, f"{rel}.new", shipped)
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
    _gone_modes(root, texts, recorded, rep, write=write)
    if write:
        own.write_text(
            ai / VERSION_FILE, "\n".join(f"{k} {v}" for k, v in sorted(new_versions.items())) + "\n", root=root
        )
    for name in ("README.md",):
        p = ai / name
        text = _asset(name)
        if not p.is_file() or p.read_text(encoding="utf-8") != text:
            if write:
                _write(root, f"{AI}/{name}", text)
            rep.written.append(f"{AI}/{name}")
        else:
            rep.unchanged.append(f"{AI}/{name}")
    written, unchanged = write_permissions(root, quilt_config(root), shell=shell, write=write, apps=apps, report=rep)
    rep.written += written
    rep.unchanged += unchanged
    rep.written.extend(ensure_root_line(root, write, shell=shell, apps=apps, report=rep))
    skills = write_skills(root, apps, write=write)
    rep.written += skills.written
    rep.unchanged += skills.unchanged
    rep.removed += skills.removed
    rep.theirs += skills.theirs
    return rep


def _gone_modes(root: Path, texts: dict[str, str], recorded: dict[str, str], rep: LayerReport, *, write: bool) -> None:
    """Take away loom's own file of each mode the quilt no longer has (`removed`), as `upgrade_layer` does.

    Loom's own is a file whose text has the hash `.loom-modes-version` records for its name; one the person edited, or one loom never recorded, is left, the edited one named in `theirs`. Nothing is read or removed through a link (`read_plain`).
    """
    folder = f"{AI}/modes"
    if blocker(root, folder, folder=True) or not (root / folder).is_dir():
        return
    for p in sorted((root / folder).glob("*.md")):
        rel = f"{folder}/{p.name}"
        text = read_plain(root, rel)
        if rel in texts or p.name not in recorded or text is None:
            continue
        if sha(text) != recorded[p.name]:
            rep.theirs.append(rel)
            continue
        if write:
            own.unlink(p, root=root)
        rep.removed.append(rel)


def write_permissions(
    root: Path,
    config: QuiltConfig,
    *,
    shell: bool,
    write: bool = True,
    apps: list[str] | tuple[str, ...] | None = None,
    report: LayerReport | None = None,
) -> tuple[list[str], list[str]]:
    """(written, unchanged): the permission files of `apps` (by default the apps the quilt is set up for, `clients.chosen`) rewritten to what `config` and this loom make them, in one variant, the person's own settings in Claude Code's kept (`settings_for`); a file that cannot be written is refused (`WriteRefused`), the record of loom's rules naming every one in the file whatever failed (`record_rules`), and so is every write where `.loom/agents/instructions/` is not the quilt's own (`refuse_layer`).

    A missing one of those apps is written like a stale one; `upgrade_layer` and the viewer's Update Claude Code both come here. `report`, where given, gains the files that keep settings of the person's (`merged`), those left alone (`theirs`) and loom's own rules taken out (`dropped`).
    """
    from loom.ai.clients import chosen

    if write:
        refuse_layer(root)
    written: list[str] = []
    unchanged: list[str] = []
    made = permission_files(root, config, shell=shell, apps=chosen(root, apps))
    if report is not None:
        report.merged += made.merged
        report.theirs += made.theirs
        report.dropped += made.dropped
    generated = permissions_json(config, shell=shell)
    for rel, text in made.texts.items():
        if read_plain(root, rel) == text:
            unchanged.append(rel)
            continue
        if write:
            if rel == CLAUDE_SETTINGS:
                record_rules(root, generated, before=made.rules_out)
            _write(root, rel, text, **({"expect": made.read[rel]} if rel in made.read else {}))
        written.append(rel)
    if write and CLAUDE_SETTINGS in made.texts:
        # before the file and after it, so a write that fails at any point leaves the record naming every rule of loom's there
        record_rules(root, generated)
    return written, unchanged


def permissions_stale(root: Path, config: QuiltConfig) -> bool:
    """Whether Claude Code's permission file is there and not what `config` and this loom make it, in the variant it is in, the person's own settings in it kept (`settings_for`); a file loom leaves alone is not stale, and `settings_left` says why."""
    there = read_plain(root, CLAUDE_SETTINGS)
    if there is None:
        return False
    want = vendor_files(config, shell=variant(root) == SHELL, root=root).get(CLAUDE_SETTINGS)
    return want is not None and there != want


def settings_deny_paths(config: QuiltConfig, *, shell: bool = False) -> list[str]:
    """The Edit/Write patterns and commands the generated settings deny for a quilt with `config`, for tests."""
    data = json.loads(permissions_json(config, shell=shell))
    return [str(r) for r in data["permissions"]["deny"]]
