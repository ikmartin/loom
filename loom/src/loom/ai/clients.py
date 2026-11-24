"""The MCP client files: the file each agent's app reads to start `loom mcp` for a quilt, generated per machine and never committed.

Each holds one server, `loom`, started as `<loom> mcp --as "<App> Agent" --quilt <root>` with both paths absolute: apps differ on the working directory and the environment they give a server, and the file names this machine's loom anyway. An app that starts the server in the project directory (`Client.walks_up`) is given no `--quilt`, since `loom mcp` finds the quilt by walking up from there, so a quilt moved on disk keeps its agent. The project files are gitignored (`loom.gitignore.CLIENT_LINES`), and `loom doctor` fails when git tracks one. A file that holds anything else is the person's: loom leaves it alone and says what to add.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Client:
    """One agent app that can start loom's server.

    Parameters
    ----------
    key : str
        Its name for `loom ai init --client`.
    label : str
        The app's own name; the server serves `<label> Agent`.
    file : str or None
        The quilt-relative file loom writes for it; None for an app configured outside the quilt.
    form : str
        The file's format: `json` (`mcpServers`), `codex` (TOML, `mcp_servers`) or `zed` (JSON, `context_servers`).
    where : str, default ''
        Where an app configured outside the quilt keeps the file, said with its entry.
    extra : tuple of (str, object), default ()
        Fields loom's entry carries beside the command: the transport, and the approval the shell allows grant.
    walks_up : bool, default False
        The app starts the server in the project directory, so the entry names no `--quilt`; shown for Claude Code by the client tier, and assumed for no other app.
    root_file : str or None, default None
        The file at the quilt's root the app reads first, where loom puts its one line (`layout.ensure_root_line`).
    permissions : str or None, default None
        The permission file loom writes whole for the app, in either variant (`layout.vendor_files`).
    skills : str or None, default None
        Where the app reads a project's skills, which loom writes one per mode (`ai.skills`).
    listed : bool, default True
        Named in `loom ai init --client`'s help; an app configured outside the quilt, which no pilot uses, is not, and still takes the option.
    """

    key: str
    label: str
    file: str | None
    form: str
    where: str = ""
    extra: tuple[tuple[str, Any], ...] = ()
    walks_up: bool = False
    root_file: str | None = None
    permissions: str | None = None
    skills: str | None = None
    listed: bool = True

    @property
    def agent(self) -> str:
        return f"{self.label} Agent"


CLIENTS = (
    Client(
        "claude-code",
        "Claude Code",
        ".mcp.json",
        "json",
        extra=(("type", "stdio"),),
        walks_up=True,
        root_file="CLAUDE.md",
        permissions=".claude/settings.json",
        skills=".claude/skills",
    ),
    Client(
        "codex",
        "Codex",
        ".codex/config.toml",
        "codex",
        extra=(("default_tools_approval_mode", "approve"),),
        root_file="AGENTS.md",
        permissions=".codex/rules/loom.rules",
        skills=".agents/skills",
    ),
    Client(
        "gemini-cli", "Gemini CLI", ".gemini/settings.json", "json", extra=(("trust", True),), root_file="GEMINI.md"
    ),
    Client("cursor", "Cursor", ".cursor/mcp.json", "json", root_file="AGENTS.md"),
    Client(
        "claude-desktop",
        "Claude Desktop",
        None,
        "json",
        where="~/Library/Application Support/Claude/claude_desktop_config.json on macOS, %APPDATA%\\Claude\\claude_desktop_config.json on Windows",
        listed=False,
    ),
    Client("lm-studio", "LM Studio", None, "json", where="~/.lmstudio/mcp.json", listed=False),
    Client("zed", "Zed", None, "zed", where="~/.config/zed/settings.json", listed=False),
    Client(
        "jetbrains",
        "JetBrains",
        None,
        "json",
        where="Settings > Tools > AI Assistant > Model Context Protocol",
        listed=False,
    ),
)
#: The apps that read a file in the quilt, which `loom ai init` writes, and the ones the viewer sets up.
PROJECT = tuple(c for c in CLIENTS if c.file)
PROJECT_FILES = tuple(c.file for c in PROJECT if c.file)
BY_KEY = {c.key: c for c in CLIENTS}


def for_an_app(rel: str) -> bool:
    """Whether the quilt-relative `rel` is a file loom keeps for an agent app: an app's MCP or settings file, its permission file, or a file under its skills (each `Client`'s `file`, `permissions` and `skills`).

    Apps hold their own shells out of such files, some of them, so recovery never writes one (`writes._judge`): a journal line could otherwise hand an agent a write its app refuses it.
    """
    return any(
        rel in (c.file, c.permissions) or (c.skills is not None and rel.startswith(f"{c.skills}/")) for c in CLIENTS
    )


def apps_in(root: Path) -> list[str] | None:
    """The apps the quilt is set up for, by key in `PROJECT`'s order, as its agent layer records them (`layout.APPS_FILE`); None where it records none, or none that can be read (`layout.read_plain`), which is a quilt set up for every app.

    Recorded rather than read off the files, since a server's file is never committed and Cursor has no other file of its own.
    """
    from loom.ai.layout import APPS_FILE, read_plain
    from loom.paths import AI

    text = read_plain(root, f"{AI}/{APPS_FILE}")
    if text is None:
        return None
    keys = set(text.split())
    return [c.key for c in PROJECT if c.key in keys]


def chosen(root: Path, apps: list[str] | tuple[str, ...] | None) -> list[str]:
    """`apps`, in `PROJECT`'s order; with None, the apps the quilt is set up for (`apps_in`), every app where it records none."""
    if apps is None:
        apps = apps_in(root)
    if apps is None:
        return [c.key for c in PROJECT]
    return [c.key for c in PROJECT if c.key in apps]


@dataclass
class ClientReport:
    """What `write_clients` did, by quilt-relative file: `written` (or, writing nothing, would be), `current`, `foreign` (the person's, left alone), `tracked` (loom's entry under git, left alone) and `removed`."""

    written: list[str] = field(default_factory=list)
    current: list[str] = field(default_factory=list)
    foreign: list[str] = field(default_factory=list)
    tracked: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, list[str]]:
        return {
            "written": self.written,
            "current": self.current,
            "foreign": self.foreign,
            "tracked": self.tracked,
            "removed": self.removed,
        }


def command() -> tuple[str, list[str]]:
    """The absolute command that starts this loom: its script beside the running interpreter, else that interpreter with `-P -m loom`.

    An agent's app runs it in the project, so the interpreter starts in safe-path mode: `-m` alone puts that directory first on `sys.path`, where a `loom.py` in the quilt would be the server.
    """
    exe = Path(sys.executable)
    script = exe.parent / ("loom.exe" if sys.platform == "win32" else "loom")
    if script.is_file():
        return str(script), []
    return str(exe), ["-P", "-m", "loom"]


def render(client: Client, root: Path) -> str:
    """The whole file loom writes for `client` in the quilt at `root`, which is also the entry to add to a file of the person's."""
    cmd, pre = command()
    entry: dict[str, Any] = {
        "command": cmd,
        "args": [*pre, "mcp", "--as", client.agent, *([] if client.walks_up else ["--quilt", str(root.resolve())])],
        **dict(client.extra),
    }
    if client.form == "codex":
        return "[mcp_servers.loom]\n" + "".join(f"{k} = {_toml(v)}\n" for k, v in entry.items())
    return json.dumps({_servers_key(client): {"loom": entry}}, indent=2, ensure_ascii=False) + "\n"


def _toml(value: Any) -> str:
    """`value` as TOML: JSON's string escapes are TOML's, and an array takes a line per item so no line outgrows the path in it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "[\n" + "".join(f"  {_toml(v)},\n" for v in value) + "]"
    return json.dumps(value, ensure_ascii=False)


def _servers_key(client: Client) -> str:
    return {"codex": "mcp_servers", "zed": "context_servers"}.get(client.form, "mcpServers")


def _parsed(client: Client, text: str) -> Any:
    try:
        return tomllib.loads(text) if client.form == "codex" else json.loads(text)
    except ValueError:
        return None


def names_loom(client: Client, text: str) -> bool:
    """Whether the file names a server `loom`, loom's own or not: what the tracked guard looks for."""
    data = _parsed(client, text)
    servers = data.get(_servers_key(client)) if isinstance(data, dict) else None
    return isinstance(servers, dict) and "loom" in servers


def is_loom_file(client: Client, text: str) -> bool:
    """Whether the file is loom's to rewrite: it parses, and holds one server, `loom`, started as `mcp --as`, and nothing else."""
    data = _parsed(client, text)
    key = _servers_key(client)
    if (
        not isinstance(data, dict)
        or set(data) != {key}
        or not isinstance(data[key], dict)
        or set(data[key]) != {"loom"}
    ):
        return False
    args = data[key]["loom"].get("args") if isinstance(data[key]["loom"], dict) else None
    return isinstance(args, list) and "mcp" in args and "--as" in args[args.index("mcp") :]


def tracked(root: Path, files: tuple[str, ...]) -> set[str]:
    """Which of `files` git tracks in the quilt at `root`; none when it is not under git or git is not installed."""
    from loom import gitprog

    if not gitprog.usable():
        return set()
    try:
        done = subprocess.run(["git", "ls-files", "-z", "--", *files], cwd=root, capture_output=True, check=False)
    except OSError:
        return set()
    if done.returncode != 0:
        return set()
    return {p for p in done.stdout.decode("utf-8", errors="replace").split("\0") if p}


def write_clients(
    root: Path, write: bool = True, *, shell: bool = False, apps: list[str] | tuple[str, ...] | None = None
) -> ClientReport:
    """Write the project client file loom owns of each of `apps` (`chosen`), or with `write` false say which it would; with `shell`, remove them instead.

    A file of the person's, or one git tracks with a loom server in it, is never written or removed: the first is reported `foreign`, the second `tracked`, and `loom doctor` fails on it. So is one that is a link, not a regular file or not UTF-8 (`layout.read_plain`), reported `foreign`.
    """
    from loom.ai.layout import _write, blocker, read_plain

    rep = ClientReport()
    under_git = tracked(root, PROJECT_FILES)
    keys = chosen(root, apps)
    for c in PROJECT:
        if c.key not in keys:
            continue
        assert c.file is not None
        p = root / c.file
        text = read_plain(root, c.file)
        if blocker(root, c.file) or (text is None and os.path.lexists(p)):
            rep.foreign.append(c.file)
            continue
        if text is not None and c.file in under_git and names_loom(c, text):
            rep.tracked.append(c.file)
            continue
        if text is not None and not is_loom_file(c, text):
            rep.foreign.append(c.file)
            continue
        if shell:
            if text is not None:
                rep.removed.append(c.file)
                if write:
                    from loom.writes import put

                    put(root, None, c.file, None, kind="agents", expect=text.encode("utf-8"))
            continue
        want = render(c, root)
        if text == want:
            rep.current.append(c.file)
            continue
        rep.written.append(c.file)
        if write:
            _write(root, c.file, want, expect=text)
    return rep
