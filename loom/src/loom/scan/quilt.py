"""Quilt discovery, quilt config, user config, and author-name resolution.

find_quilt walks up from a directory to the nearest config.toml with a [quilt] table. resolve_author applies the order flag, user config, git, refusal; the refusal message is part of the contract and tests check it verbatim.
"""

from __future__ import annotations

import json
import os
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loom.paths import CACHE, HISTORY, LOCAL, LOOM, OVERLEAF_CLONE, SCRATCH, SOURCE_SYNC

NO_AUTHOR_MESSAGE = (
    'no author name: add name = "Your Name" under [author] in ~/.config/loom/config.toml, or pass --as NAME'
)


CONFIG_KEYS: dict[str, set[str]] = {
    # `history` is the record's directory, documented and never written by init
    "quilt": {"name", "main", "home", "history", "prefix", "engine", "research_state"},
    # `online`: whether loom may use the network for cited works; `contact`: the address the lookup services are given
    "library": {"online", "contact"},
    "lint": {"disable"},
    # `deny`: where an agent may not write, gitignore-style, beside what is always protected (`loom.agents`)
    "agents": {"deny"},
    "author": {"name"},
    # `[basis]` names environments, so any key is valid there and each value is checked instead
    "basis": set(),
}


class NoQuiltError(Exception):
    """Raised when no config.toml with a [quilt] table is found walking up from the start directory."""


class LayoutError(NoQuiltError):
    """Raised for a quilt whose `.loom/` is not in this loom's layout (`loom.layout`); str(exc) says what was found and what this loom reads."""


class SettingError(NoQuiltError):
    """Raised for a quilt one of whose path settings lies where loom removes files (`removed_in`); str(exc) names the setting, where it points and why."""


class NoAuthorError(Exception):
    """Raised when no author name can be resolved; str(exc) is NO_AUTHOR_MESSAGE."""


# the `[quilt]` keys a person may set for every quilt in their user config; the quilt's own value wins
USER_QUILT_KEYS = ("name", "history")


@dataclass
class QuiltConfig:
    name: str = ""
    main: str = ""
    home: str = ""  # the file the viewer opens on when it remembers no place; unset, the root README.md
    history: str = HISTORY
    research_state: str = "research-state.md"  # the quilt's research state, a page an agent keeps and the person edits
    prefix: str = "q"
    engine: str = "pdflatex"
    online: bool = False  # [library] online: whether loom may look identifiers up and fetch documents
    online_asked: bool = False  # `[library] online` is set at all; unset, the viewer asks before the first paper
    contact: str = ""  # [library] contact: the address the lookup services are given
    author: str = ""  # [author] name: who this quilt's records name
    author_declared: bool = False  # the quilt states an `[author]` table, even with an empty name
    lint_disable: list[str] = field(default_factory=list)
    agents_deny: list[str] = field(default_factory=list)  # [agents] deny: the patterns loom accepted, in order
    basis: dict[str, str] = field(default_factory=dict)  # [basis]: environment name -> basis, over the built-in names
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any], user: dict[str, Any] | None = None) -> QuiltConfig:
        """The config of a quilt from its `config.toml` table, with the user config's `[quilt]` values (USER_QUILT_KEYS only) as defaults under it."""
        cfg = cls()

        def table(name: str) -> dict[str, Any]:
            """A named table, or empty when the file gives that name a scalar (which is warned about below)."""
            value = data.get(name, {})
            return value if isinstance(value, dict) else {}

        for table_name, keys in data.items():
            if not isinstance(keys, dict):
                cfg.warnings.append(f"config.toml: [{table_name}] is not a table; ignored")
                continue
            known = CONFIG_KEYS.get(table_name)
            if table_name == "review" and "track_edits" in keys:
                cfg.warnings.append(
                    "config.toml: [review] track_edits is gone: every quilt keeps your look now, so your own edits in an editor wait in Your Changes too; delete the [review] table"
                )
                continue
            if known is None:
                cfg.warnings.append(f"config.toml: unknown table [{table_name}]; ignored")
                continue
            for key in keys:
                if key not in known and table_name != "basis":
                    cfg.warnings.append(f"config.toml: unknown key {table_name}.{key}; ignored")
        q = dict(table("quilt"))
        uq = (user or {}).get("quilt", {})
        if isinstance(uq, dict):
            for key in USER_QUILT_KEYS:
                if key in uq and key not in q:
                    q[key] = uq[key]
        cfg.name = str(q.get("name", cfg.name)).strip()
        cfg.history = str(q.get("history", cfg.history)).strip("/") or cfg.history
        cfg.research_state = str(q.get("research_state", cfg.research_state)).strip("/") or cfg.research_state
        cfg.main = str(q.get("main", ""))
        cfg.home = str(q.get("home", "")).strip().strip("/")
        cfg.prefix = str(q.get("prefix", cfg.prefix))
        cfg.engine = str(q.get("engine", cfg.engine))
        cfg.online = bool(table("library").get("online", False))
        cfg.online_asked = "online" in table("library")
        cfg.contact = str(table("library").get("contact", ""))
        cfg.lint_disable = [str(x) for x in table("lint").get("disable", [])]
        cfg.agents_deny = _agents_deny(table("agents").get("deny", []), cfg.warnings)
        from loom.scan.nodes import NAMED_BASES

        for env_name, basis in table("basis").items():
            if basis in NAMED_BASES:
                cfg.basis[str(env_name).lower().replace(" ", "-")] = basis
            else:
                cfg.warnings.append(
                    f"config.toml: basis.{env_name} = {basis!r} is not one of {', '.join(NAMED_BASES)}; ignored"
                )
        cfg.author_declared = isinstance(data.get("author"), dict)
        cfg.author = str(table("author").get("name", "")).strip()
        return cfg


def _agents_deny(value: Any, warnings: list[str]) -> list[str]:
    """`[agents] deny`'s entries loom can enforce; each refused one is a warning, and stays protected only if another entry covers it."""
    from loom.agents import compile_pattern

    if not isinstance(value, list):
        warnings.append("config.toml: agents.deny is not a list of patterns; ignored")
        return []
    out: list[str] = []
    for entry in value:
        got = compile_pattern(entry) if isinstance(entry, str) else f"{entry!r} is not a string"
        if isinstance(got, str):
            warnings.append(f"config.toml: agents.deny entry {got}; ignored")
        else:
            out.append(entry)
    return out


@dataclass
class Quilt:
    root: Path
    config: QuiltConfig

    @property
    def history_dir(self) -> Path:
        return self.root / self.config.history

    @property
    def name(self) -> str:
        """The project's name: `[quilt] name`, else the root directory's."""
        return self.config.name or self.root.name


def is_quilt_root(path: Path) -> bool:
    cfg = path / "config.toml"
    if not cfg.is_file():
        return False
    try:
        data = tomllib.loads(cfg.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return False
    return isinstance(data.get("quilt"), dict)


def find_quilt(start: Path | None = None) -> Quilt:
    """Locate the quilt containing `start` (default: LOOM_QUILT or the current directory)."""
    if start is None:
        env = os.environ.get("LOOM_QUILT")
        start = Path(env).expanduser() if env else Path.cwd()
    start = start.resolve()
    for candidate in [start, *start.parents]:
        if is_quilt_root(candidate):
            return load_quilt(candidate)
    # A `config.toml` that is there and will not parse is a different problem from one that is absent, and saying
    # "no config.toml" about a file the author is looking at sends them hunting for the wrong thing. Found by the
    # reading study, 2026-09-21, after a stray second `[author]` table made a quilt vanish.
    for candidate in [start, *start.parents]:
        cfg = candidate / "config.toml"
        if not cfg.is_file():
            continue
        try:
            tomllib.loads(cfg.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise NoQuiltError(f"{cfg} is not valid TOML, so this is not a readable quilt: {exc}") from exc
        except OSError:
            continue
    raise NoQuiltError(f"not inside a quilt: no config.toml with a [quilt] table above {start}")


def load_quilt(root: Path) -> Quilt:
    """The quilt at `root`, its `.loom/` stamped with this loom's layout when it has none yet.

    Raises
    ------
    LayoutError
        When `.loom/` holds no layout number or one this loom does not read.
    """
    from loom import layout

    data = tomllib.loads((root / "config.toml").read_text(encoding="utf-8"))
    if not (root / LOOM).exists():
        try:
            layout.stamp(root)
        except OSError:
            pass  # a quilt loom cannot write into is read as it is
    why = layout.refusal(root)
    if why is not None:
        raise LayoutError(why)
    config = QuiltConfig.from_dict(data, load_user_config())
    why = removed_in(root, config)
    if why is not None:
        raise SettingError(why)
    return Quilt(root=root, config=config)


#: The folders of `.loom/` loom removes files from and git ignores: no setting of the quilt may point into one.
REMOVED_IN = (CACHE, LOCAL, SCRATCH)


def removed_in(root: Path, config: QuiltConfig) -> str | None:
    """Why a path setting of the quilt at `root` cannot stand, or None: one that lies in a folder of `REMOVED_IN`, by its path or through a link.

    The settings: `[quilt] history`, `research_state`, `main` and `home`, and the sync directory `loom sync init` records. Each names where the person's or loom's kept files go, and the sweep would remove them there.
    """
    named = [
        ("[quilt] history", config.history),
        ("[quilt] research_state", config.research_state),
        ("[quilt] main", config.main),
        ("[quilt] home", config.home),
    ]
    try:
        synced = json.loads((root / SOURCE_SYNC).read_text(encoding="utf-8")).get("directory")
    except (OSError, ValueError, AttributeError):
        synced = None
    # the Overleaf mirror's clone is loom's own, made in `.loom/local/` because it is this machine's (`loom.overleaf`)
    if isinstance(synced, str) and synced and synced != OVERLEAF_CLONE:
        named.append(("the sync directory", synced))
    real_root = Path(os.path.realpath(root))
    for setting, value in named:
        if not value:
            continue
        lexical = Path(os.path.normpath(value))
        real = Path(os.path.realpath(root / value))
        for folder in REMOVED_IN:
            if lexical.is_relative_to(folder) or real.is_relative_to(real_root / folder):
                return f"{setting} is {value}, inside {folder}/, where loom removes files; set it outside {REMOVED_IN[0]}/, {REMOVED_IN[1]}/ and {REMOVED_IN[2]}/"
    return None


def user_config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else Path.home() / ".config") / "loom" / "config.toml"


def load_user_config() -> dict[str, Any]:
    path = user_config_path()
    if not path.is_file():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return {}


def git_user_name(cwd: Path | None = None) -> str | None:
    """`git config user.name` in `cwd`, asked of git again only when a file it was read from, or one it would be read from, has changed.

    A build asks once per annotation when no loom author name is set, so the answer is kept per directory and git environment beside the files it came from: every file git names as an origin, every `include.path` and `includeIf.*.path` in them, the global configuration and `<cwd>/.git`. Not noticed: a repository made above `cwd`, or an `includeIf` whose condition changes while no file does.
    """
    here = (cwd or Path.cwd()).absolute()
    env = tuple(os.environ.get(k) for k in _GIT_ENV)
    known = _GIT_NAMES.get((here, env))
    if known is not None and _stamps(known[0]) == known[1]:
        return known[2]
    name, files = _git_user_name(here)
    _GIT_NAMES[(here, env)] = (files, _stamps(files), name)
    return name


#: What else decides which files `git config` reads; part of `_GIT_NAMES`'s key.
_GIT_ENV = (
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
    "GIT_CONFIG_NOSYSTEM",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_COUNT",
    "GIT_DIR",
    "HOME",
    "XDG_CONFIG_HOME",
)
_GIT_NAMES: dict[
    tuple[Path, tuple[str | None, ...]], tuple[tuple[Path, ...], tuple[tuple[int, int] | None, ...], str | None]
] = {}


def _stamps(files: tuple[Path, ...]) -> tuple[tuple[int, int] | None, ...]:
    out: list[tuple[int, int] | None] = []
    for f in files:
        try:
            st = f.stat()
        except OSError:
            out.append(None)
        else:
            out.append((st.st_mtime_ns, st.st_size))
    return tuple(out)


def _git_user_name(here: Path) -> tuple[str | None, tuple[Path, ...]]:
    """The name git gives in `here`, the last `user.name` it reads, and the files to watch for a change to it.

    One `git config --list --show-origin`; a relative origin is the repository's own file, named from the top of its working tree, and an include's path is relative to the file that names it.
    """
    home = Path.home()
    top = next((p for p in (here, *here.parents) if (p / ".git").exists()), here)
    watch = {here / ".git"}
    if os.environ.get("GIT_CONFIG_GLOBAL"):
        watch.add(top / Path(os.environ["GIT_CONFIG_GLOBAL"]).expanduser())
    else:
        watch |= {home / ".gitconfig", Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config") / "git" / "config"}
    if os.environ.get("GIT_CONFIG_SYSTEM"):
        watch.add(top / Path(os.environ["GIT_CONFIG_SYSTEM"]).expanduser())
    from loom import gitprog

    if not gitprog.usable():
        # Apple's stub opens an installer dialog: no name, kept like any other answer
        return None, tuple(sorted(watch))
    try:
        proc = subprocess.run(
            ["git", "config", "--list", "--show-origin", "-z"], capture_output=True, cwd=here, timeout=10, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None, tuple(sorted(watch))
    name = None
    said = proc.stdout.decode("utf-8", errors="replace").split("\0")
    for origin, entry in zip(said[::2], said[1::2], strict=False):
        key, _, value = entry.partition("\n")
        source = top / origin[len("file:") :] if origin.startswith("file:") else None
        if source is not None:
            watch.add(source)
        if key == "user.name":
            name = value.strip() or None
        elif key.startswith(("include.", "includeif.")) and key.endswith(".path") and value:
            path = Path(value).expanduser()
            watch.add(path if path.is_absolute() or source is None else source.parent / path)
    return name, tuple(sorted(watch))


#: `resolve_author`'s source for a name git gives: Review and `loom status` say so, since a look and an acceptance are kept under the name.
FROM_GIT = "git config user.name"


def resolve_author(explicit: str | None, cwd: Path | None = None) -> tuple[str, str]:
    """The person's name and where it comes from: `--as`, then the user config's `[author] name`, then git's `user.name`.

    The one resolver of a person's name; a quilt's own `[author]` never names its reader. Each source is read once per process and again only when its files change (`_user_author`, `git_user_name`), so a process asks git nothing per call and sees a name saved in Settings at once. Raises NoAuthorError when no source gives one.
    """
    if explicit and explicit.strip():
        return explicit.strip(), "--as"
    name = _user_author()
    if name:
        return name, str(user_config_path())
    git_name = git_user_name(cwd)
    if git_name:
        return git_name, FROM_GIT
    raise NoAuthorError(NO_AUTHOR_MESSAGE)


#: The user config's author name by the config's path and stamp, so it is read once until the file changes.
_USER_AUTHOR: dict[Path, tuple[tuple[tuple[int, int] | None, ...], str]] = {}


def _user_author() -> str:
    """`[author] name` from the user config, '' when unset; read again only when the file's stamp changes."""
    path = user_config_path()
    stamp = _stamps((path,))
    kept = _USER_AUTHOR.get(path)
    if kept is not None and kept[0] == stamp:
        return kept[1]
    author = load_user_config().get("author", {})
    name = author.get("name") if isinstance(author, dict) else None
    out = name.strip() if isinstance(name, str) else ""
    _USER_AUTHOR[path] = (stamp, out)
    return out


def reviewer_identity(cwd: Path) -> tuple[str, str]:
    """The reviewer's name and its source as `resolve_author` gives them, `('', '')` when there is none: reading goes on without a name, and acceptance refuses."""
    try:
        return resolve_author(None, cwd)
    except NoAuthorError:
        return "", ""


def save_author(name: str) -> None:
    """Atomically edit only the local author name, preserving the rest of the config."""
    import re
    import tempfile

    name = name.strip()
    if not name or any(ord(c) < 32 for c in name):
        raise ValueError("choose a nonempty author name without control characters")
    path = user_config_path()
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    before = tomllib.loads(original)
    expected = {**before, "author": {**before.get("author", {}), "name": name}}
    line = "name = " + json.dumps(name, ensure_ascii=False) + "\n"
    table = re.search(r"(?m)^\s*\[author\][^\n]*\n?", original)
    if table:
        following = original[table.end() :]
        end = re.search(r"(?m)^\s*\[", following)
        boundary = table.end() + (end.start() if end else len(following))
        body = original[table.end() : boundary]
        field = re.search(r"(?m)^\s*name\s*=.*(?:\n|$)", body)
        body = body[: field.start()] + line + body[field.end() :] if field else line + body
        updated = original[: table.end()].rstrip("\n") + "\n" + body + original[boundary:]
    else:
        updated = original.rstrip() + "\n\n[author]\n" + line
    try:
        unchanged = tomllib.loads(updated) == expected
    except tomllib.TOMLDecodeError:
        unchanged = False
    if not unchanged:
        raise ValueError(f"cannot safely edit this author table; set author.name in {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as temp:
        temp.write(updated)
        temporary = Path(temp.name)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
