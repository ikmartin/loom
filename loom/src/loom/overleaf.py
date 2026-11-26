"""The Overleaf mirror: a folder of the quilt that holds one Overleaf project's files as Overleaf holds them, read over git and never written back.

Loom reaches Overleaf over git only, at an address it builds from the project's id (`git_address`), and only to read: it fetches into a clone of its own and takes Overleaf's bytes into the folder when the person presses Update. Nothing in loom pushes. What travels with the quilt (the record, `sync.SyncState`) is checked at every read, and the clone is used only where this machine made it (`_clone`).
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, ParamSpec, TypeVar
from urllib.parse import urlsplit

from loom.paths import LOCAL, LOOM, OVERLEAF_CLONE, OVERLEAF_HERE, SOURCE_SYNC
from loom.scan.quilt import Quilt
from loom.sync import (
    PROJECT_ID,
    MirrorError,
    SyncError,
    SyncState,
    checked_folder,
    plain_folder,
    revision,
    tree_files,
)

__all__ = ["LinkRefused", "MirrorError", "SyncError"]

#: Overleaf's git host.
GIT_HOST = "git.overleaf.com"
#: Where the projects' git addresses are, with no slash at its end: `git_address` puts a project's id after it. The test suite stands a local folder or server in.
BASE = f"https://{GIT_HOST}"
#: The transports the mirror's git may use; the test suite adds the local ones its stand-ins need.
PROTOCOLS: tuple[str, ...] = ("https",)
#: The credential helper every mirror git call names, after clearing any other: the macOS Keychain's, which Apple's and Homebrew's git ship. The test suite replaces it with a file in each test's temporary folder.
HELPER = "osxkeychain"
#: How long a call that reaches Overleaf may take before it is called unreachable, in seconds; a clone of a large project is the longest.
TIMEOUT = 300.0
#: The folder of the machine's own place (`machine.data_dir`) where this machine marks each clone it made, so that a clone a quilt brought with it is never used.
MARKS = "overleaf"
#: The files of loom's clone that can name a program, an address or other objects, whose bytes as loom wrote them the mark holds (`_seal`): its configuration, its attributes, grafts, a pointer to another git folder, and the stores of objects it borrows.
SEALED = (
    "config",
    "config.worktree",
    "info/attributes",
    "info/grafts",
    "commondir",
    "objects/info/alternates",
    "objects/info/http-alternates",
)
#: Held by every step that makes, fetches into or removes loom's clone, so the fetch a server makes as it starts never races a pairing or its end.
_CLONE_LOCK = threading.RLock()

_P = ParamSpec("_P")
_R = TypeVar("_R")


def _holding_clone(fn: Callable[_P, _R]) -> Callable[_P, _R]:
    """`fn` run holding `_CLONE_LOCK`."""

    @functools.wraps(fn)
    def held(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        with _CLONE_LOCK:
            return fn(*args, **kwargs)

    return held


# ---- the link --------------------------------------------------------------------------------------------------------

_ID = r"(?P<id>[0-9a-f]{24}|[0-9]+)"
#: A project's own address in the browser, or its git address, each with anything after the id.
_PROJECT = re.compile(rf"^(?:https?://)?(?:www\.)?overleaf\.com/project/{_ID}(?:[/?#].*)?$", re.I)
_GIT = re.compile(rf"^(?:https?://)?(?:[^@/\s]+@)?{re.escape(GIT_HOST)}/{_ID}(?:\.git)?/?(?:[?#].*)?$", re.I)
#: A sharing link: read-only (`/read/<token>`) or read-and-edit (`/<digits><letters>`), each holding a token and not the id.
_SHARING = re.compile(r"^(?:https?://)?(?:www\.)?overleaf\.com/(?:read/[A-Za-z0-9]+|[0-9]+[a-z]+)(?:[/?#].*)?$", re.I)


class LinkRefused(ValueError):
    """A pasted link no project can be read from; `code` is the write API's."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def project_of(link: str) -> str:
    """The id of the Overleaf project a pasted link names.

    Parameters
    ----------
    link : str
        The project's address in the browser (`https://www.overleaf.com/project/<id>`), its git address (`https://git.overleaf.com/<id>`), or the whole line Overleaf's Git dialog shows (`git clone https://git.overleaf.com/<id>`).

    Returns
    -------
    str
        The project's id, in lower case.

    Raises
    ------
    LinkRefused
        `sharing-link` for a link that shares the project, which holds a token and not its id; `not-a-project` for anything else.
    """
    given = link.strip()
    words = given.split()
    if len(words) >= 3 and words[0] == "git" and words[1] == "clone":
        given = next((w for w in words[2:] if not w.startswith("-")), "")
    if _SHARING.match(given):
        raise LinkRefused(
            "sharing-link",
            "That is a link for sharing the project, which does not name it. Open the project in Overleaf and paste the address from your browser, or the one under Menu, Git.",
        )
    found = _PROJECT.match(given) or _GIT.match(given)
    if found is None:
        raise LinkRefused(
            "not-a-project",
            "That is not the address of an Overleaf project. Open the project in Overleaf and paste the address from your browser, or the one under Menu, Git.",
        )
    return found.group("id").lower()


def git_address(project: str) -> str:
    """The git address of the project `project` names, built from `BASE` and the id alone; MirrorError `bad-record` for anything but an id."""
    if not isinstance(project, str) or not PROJECT_ID.fullmatch(project):
        raise MirrorError("bad-record", "That is not the id of an Overleaf project.")
    return f"{BASE}/{project}"


def address(link: str) -> str:
    """The git address of the project a pasted link names (`project_of`, `git_address`)."""
    return git_address(project_of(link))


# ---- git, as the mirror runs it -------------------------------------------------------------------------------------

#: What the person reads when the record names a project whose history does not hold what loom last took in.
BAD_PROJECT = "This quilt's record names an Overleaf project that does not hold what loom last took in from it; end the pairing and pair it again."

#: What each failure says to the person, by code.
SAID = {
    "no-git": "Loom needs git to reach Overleaf, and this Mac has none.",
    "no-token": "Overleaf asks for a git token. Make one in Overleaf under Account Settings, Git integration, and paste it here.",
    "token-refused": "Overleaf did not accept the token. Tokens last a year; make a new one in Overleaf under Account Settings, Git integration, and paste it here.",
    "no-git-access": "Overleaf would not give loom this project. Git access needs the project's owner to have a premium plan, and the link must be the project's own.",
    "offline": "Could not reach Overleaf. Check the connection and try again.",
    "bad-token": "That is not a git token: a token is one line of letters and digits.",
}


def _failure(stderr: str) -> MirrorError:
    """The failure git's own words name: no token, a refused one, no access to the project, or Overleaf unreachable; anything else as git said it."""
    lines = [ln.strip() for ln in stderr.splitlines() if ln.strip()]
    said = next((ln for ln in reversed(lines) if ln.startswith(("fatal:", "error:"))), lines[-1] if lines else "")
    low = said.lower()
    if "terminal prompts disabled" in low or "could not read username" in low or "could not read password" in low:
        code = "no-token"
    elif "authentication failed" in low or "returned error: 401" in low:
        code = "token-refused"
    elif "not found" in low or "returned error: 403" in low or "returned error: 404" in low:
        code = "no-git-access"
    elif "unable to access" in low or "could not resolve host" in low:
        code = "offline"
    else:
        return MirrorError("failed", f"Overleaf could not be read: {said.removeprefix('fatal: ') or 'git failed'}")
    return MirrorError(code, SAID[code])


def run(clone: Path | None, *args: str, input: bytes | None = None) -> bytes:
    """Run git for the mirror: in loom's clone `clone` (`--git-dir`), or in none.

    Nothing the person's or a repository's configuration says chooses a program, a helper or an address: the person's and the system's git config are not read, no `GIT_` variable of the environment reaches git, hooks are off, the credential helper is cleared and set to `HELPER`, git never prompts, and only `PROTOCOLS` may carry a fetch. Raises MirrorError with the failure's code (`_failure`); `no-git` where git cannot be run, `offline` past `TIMEOUT`.
    """
    from loom import gitprog

    if not gitprog.usable():
        raise MirrorError("no-git", SAID["no-git"])
    neutral = tempfile.gettempdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CEILING_DIRECTORIES=os.path.dirname(neutral),
        GIT_TERMINAL_PROMPT="0",
        GIT_ASKPASS="",
        SSH_ASKPASS="",
        GCM_INTERACTIVE="never",
    )
    settings = [
        f"core.hooksPath={os.devnull}",
        "core.fsmonitor=false",
        "gc.auto=0",
        "maintenance.auto=false",
        "core.askPass=",
        "credential.helper=",
        f"credential.helper={HELPER}",
        "protocol.allow=never",
        *(f"protocol.{p}.allow=always" for p in PROTOCOLS),
    ]
    command = ["git", *(a for s in settings for a in ("-c", s))]
    if clone is not None:
        if not _sealed(clone):
            raise MirrorError(
                "no-clone", "Loom's copy of the project changed since loom made it; update again to make it anew."
            )
        command.append(f"--git-dir={clone}")
    try:
        done = subprocess.run(
            [*command, *args], cwd=neutral, env=env, input=input, capture_output=True, check=False, timeout=TIMEOUT
        )
    except subprocess.TimeoutExpired as exc:
        raise MirrorError("offline", SAID["offline"]) from exc
    except FileNotFoundError as exc:
        raise MirrorError("no-git", SAID["no-git"]) from exc
    if done.returncode:
        raise _failure(done.stderr.decode("utf-8", errors="replace"))
    return done.stdout


def store_token(git_address: str, token: str) -> None:
    """Give `HELPER` the person's token for the host of `git_address`, as git itself would after a successful sign-in: on standard input to `git credential approve`, never on a command line, and kept nowhere by loom.

    Overleaf's git takes the user name `git` and the token as its password, and one token serves all the person's projects, so it is stored by host. Raises MirrorError `bad-token` for one that is not a single line of printable characters, which the helper's protocol would otherwise read as more than a password.
    """
    token = token.strip()
    if not token or not token.isprintable() or any(c.isspace() for c in token):
        raise MirrorError("bad-token", SAID["bad-token"])
    parts = urlsplit(git_address)
    host = parts.netloc.rsplit("@", 1)[-1]
    run(
        None,
        "credential",
        "approve",
        input=f"protocol={parts.scheme}\nhost={host}\nusername=git\npassword={token}\n\n".encode(),
    )


# ---- this machine's part ---------------------------------------------------------------------------------------------


def here(root: Path) -> dict[str, Any]:
    """This machine's part of the mirror, kept in `.loom/local/`, never in the record that travels with the quilt, so that co-authors sharing a quilt each say who they are and no address is in a file a person commits: `me`, the addresses the person goes by on Overleaf; `asked`, those of the history's authors they were shown when they said; `ask`, whether to ask again; and `problem`, the code of what the last reach of Overleaf could not do, or None."""
    try:
        data = json.loads((root / OVERLEAF_HERE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data = data if isinstance(data, dict) else {}

    def addresses(key: str) -> list[str]:
        held = data.get(key)
        return [m for m in held if isinstance(m, str)] if isinstance(held, list) else []

    problem = data.get("problem")
    return {
        "me": addresses("me"),
        "asked": addresses("asked"),
        "ask": data.get("ask") is True,
        "problem": problem if isinstance(problem, str) else None,
    }


def _keep_here(root: Path, **changes: Any) -> None:
    """Write `changes` into this machine's part (`here`), whole or not at all."""
    data = {**here(root), **changes}
    path = root / OVERLEAF_HERE
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _ask_again(root: Path, clone: Path, rev: str) -> None:
    """Ask again who the person is when the machine knows them by no address and the history names someone they were not shown: a quilt that came without its `.loom/local/`, or "none yet" before their first change."""
    held = here(root)
    named = {a["email"].lower() for a in authors(clone, rev)}
    _keep_here(root, ask=not held["me"] and bool(named - {a.lower() for a in held["asked"]}))


# ---- loom's clone ----------------------------------------------------------------------------------------------------


def _mark_of(clone: Path) -> Path:
    """Where this machine marks the clone at `clone`, outside the quilt: keyed by where the clone really lies."""
    from loom.machine import data_dir

    key = hashlib.sha256(os.path.realpath(clone).encode("utf-8")).hexdigest()[:24]
    return data_dir() / MARKS / f"{key}.json"


def _seal(clone: Path) -> str:
    """A digest of each of `SEALED` in the clone at `clone`, its bytes or that it is not there; a file that cannot be read as a file seals as such."""
    held = []
    for name in SEALED:
        path = clone / name
        try:
            data: str | None = hashlib.sha256(path.read_bytes()).hexdigest()
        except FileNotFoundError:
            data = None
        except OSError:
            data = "unreadable"
        held.append([name, data, path.is_symlink()])
    return hashlib.sha256(json.dumps(held).encode()).hexdigest()


def _identity(clone: Path, project: str) -> dict[str, Any] | None:
    """What a mark of the clone at `clone` for `project` holds: where it lies, the project, the folder's identity on the file system, so a folder copied or put in its place is not it, and the seal of what in it can name a program or an address (`_seal`), so a key written into it since is seen; None where no folder is there."""
    try:
        it = os.stat(clone, follow_symlinks=False)
    except OSError:
        return None
    if not stat.S_ISDIR(it.st_mode):
        return None
    return {
        "clone": os.path.realpath(clone),
        "project": project,
        "dev": it.st_dev,
        "ino": it.st_ino,
        "seal": _seal(clone),
    }


def _sealed(clone: Path) -> bool:
    """Whether the clone at `clone` is one this machine made, holding what it held then in each of `SEALED`: checked before every git call in it (`run`)."""
    try:
        held = json.loads(_mark_of(clone).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(held, dict) and held == _identity(clone, str(held.get("project")))


def _marked(clone: Path, project: str) -> bool:
    """Whether this machine made the clone at `clone` for `project`."""
    try:
        held = json.loads(_mark_of(clone).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    mine = _identity(clone, project)
    return mine is not None and held == mine


def _remove(path: Path) -> None:
    """Take `path` away, a folder whole, never following a link to anything outside it."""
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _clone(root: Path, project: str) -> Path:
    """Loom's clone of `project`, without a work tree, in `.loom/local/overleaf/`, fetched from the address loom builds (`git_address`), with Overleaf's tip at `refs/loom/tip`.

    Used only where this machine made it for this quilt and this project and nothing that can name a program or an address in it has changed since (`_marked`, `_seal`): any other folder found there, a clone a quilt brought with it or one whose configuration was written to since among them, is removed and made again, never repaired in place, so nothing in it (a hook, a setting, an address) is ever read. Refused (`bad-record`) where `.loom/local/` does not lie in the quilt's own `.loom/`.
    """
    local = Path(os.path.realpath(root / LOCAL))
    if local.parent != Path(os.path.realpath(root / LOOM)):
        raise MirrorError(
            "bad-record",
            "This quilt's .loom/local/ lies outside the quilt, so loom makes no copy of the project there.",
        )
    clone = root / OVERLEAF_CLONE
    if not _marked(clone, project):
        fresh = clone.with_name(clone.name + ".new")
        _remove(fresh)
        _remove(clone)
        _mark_of(clone).unlink(missing_ok=True)
        fresh.parent.mkdir(parents=True, exist_ok=True)
        run(None, "init", "--quiet", "--bare", "--template=", "--", str(fresh))
        fresh.rename(clone)
        mark = _mark_of(clone)
        mark.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        mark.write_text(json.dumps(_identity(clone, project), sort_keys=True) + "\n", encoding="utf-8")
    run(
        clone,
        "fetch",
        "--quiet",
        "--no-tags",
        "--no-write-fetch-head",
        "--",
        git_address(project),
        "+HEAD:refs/loom/tip",
    )
    return clone


def _tip(clone: Path) -> str:
    """The project's tip as the clone last fetched it."""
    return revision(clone, "refs/loom/tip")


def main_files(clone: Path, rev: str) -> list[str]:
    """The project's main file candidates at `rev`: each `.tex` at its top that declares a document class and begins a document; Overleaf's own choice of main file is not in git."""
    from loom.sync import MAIN_FILE

    out = []
    listed = run(clone, "ls-tree", "--name-only", "-z", "--end-of-options", rev).decode("utf-8", errors="replace")
    for name in sorted(n for n in listed.split("\0") if n):
        if MAIN_FILE.fullmatch(name):
            text = run(clone, "show", f"{rev}:{name}").decode("utf-8", errors="replace")
            if "\\documentclass" in text and "\\begin{document}" in text:
                out.append(name)
    return out


def authors(clone: Path, rev: str) -> list[dict[str, str]]:
    """Who the project's history names, latest first, once each by address: `{name, email}`."""
    seen: dict[str, dict[str, str]] = {}
    said = run(clone, "log", "--format=%aN%x00%aE", "--end-of-options", rev).decode("utf-8", errors="replace")
    for line in said.splitlines():
        name, _, email = line.partition("\0")
        if email and email.lower() not in seen:
            seen[email.lower()] = {"name": name, "email": email}
    return list(seen.values())


# ---- pairing ---------------------------------------------------------------------------------------------------------


def paired(root: Path) -> SyncState | None:
    """The quilt's mirror record, checked (`SyncState.read`), or None when the quilt mirrors no project; MirrorError `bad-record` for a record loom cannot use."""
    try:
        return SyncState.read(root)
    except MirrorError as exc:
        if exc.code == "not-paired":
            return None
        raise


def mirrored(root: Path, rel: str) -> bool:
    """Whether the real file `rel` reaches lies in the folder a mirror keeps its project in, which only an update writes.

    Judged as recovery judges a place (`writes._place`, `writes._loom_named`): the path's links resolved to the real file, and each folder it lies in compared with the mirrored folder by the file system's identity, never by spelling, so a link into the folder, or the folder named in another case where case is ignored, is the folder. A path the file system cannot resolve is taken as in it, since it cannot be shown to lie outside; a record loom cannot use, or whose folder is not one the mirror may write (`checked_folder`), the quilt itself among them, mirrors nothing.
    """
    from loom.scan.quilt import NoQuiltError, load_quilt
    from loom.writes import _real

    try:
        state = SyncState.read(root)
        folder = checked_folder(root, load_quilt(root).history_dir, state.folder)
        own = os.stat(root / folder)
    except (SyncError, NoQuiltError, OSError, ValueError):
        return False
    top, real = _real(root), _real(root / rel)
    if top is None or real is None:
        # a path the file system cannot resolve, as while a folder on it is being renamed, is not trusted to lie outside
        return True
    for place in (real, *real.parents):
        try:
            it = os.stat(place)
        except OSError:
            continue
        if (it.st_dev, it.st_ino) == (own.st_dev, own.st_ino):
            return True
        if place == top:
            break
    return False


def propose_folder(root: Path) -> str:
    """A new folder's name for the project: `paper`, else `overleaf`, else `overleaf-2` and on."""
    for name in ("paper", "overleaf", *(f"overleaf-{n}" for n in range(2, 100))):
        if not (root / name).exists():
            return name
    return "overleaf-project"


@_holding_clone
def prepare(quilt: Quilt, project: str) -> dict[str, Any]:
    """Reach the project and say what pairing asks of the person, writing nothing of theirs: the clone is made or fetched.

    Parameters
    ----------
    quilt : Quilt
        The quilt to pair.
    project : str
        The project's id (`project_of`).

    Returns
    -------
    dict
        `folder`, a proposed name for a new folder; `mains`, the main file candidates, and `main`, the one loom would take ('' when the person must choose); `authors`, who the history names (`authors`); `me`, the addresses this machine already knows the person by.

    Raises
    ------
    MirrorError
        `paired` when the quilt mirrors a project already, `no-main` when no file of the project begins a document, or what reaching Overleaf failed on (`run`).
    """
    root = quilt.root
    if paired(root) is not None:
        raise MirrorError("paired", "This quilt mirrors an Overleaf project already.")
    clone = _clone(root, project)
    rev = _tip(clone)
    mains = main_files(clone, rev)
    if not mains:
        raise MirrorError(
            "no-main", "No file at the top of the project begins a document, so loom cannot tell which is the paper."
        )
    main = mains[0] if len(mains) == 1 else ("main.tex" if "main.tex" in mains else "")
    return {
        "folder": propose_folder(root),
        "mains": mains,
        "main": main,
        "authors": authors(clone, rev),
        "me": here(root)["me"],
    }


@_holding_clone
def pair(quilt: Quilt, project: str, folder: str, main: str, me: list[str], actor: str | None = None) -> dict[str, Any]:
    """Copy the project into a new folder of the quilt and record the pairing, as one act through the door.

    Parameters
    ----------
    quilt : Quilt
        The quilt to pair.
    project : str
        The project's id (`project_of`).
    folder : str
        The new folder, quilt-relative; it becomes the project's root, so each path maps one to one.
    main : str
        The project's main file, one of `main_files`.
    me : list of str
        The addresses the person goes by in the project's history; [] when they have made no change there yet. Kept on this machine (`here`).
    actor : str, optional
        Who the act is recorded as; default the quilt's author.

    Returns
    -------
    dict
        `folder` and `main`, the main document's quilt path.

    Raises
    ------
    MirrorError
        `paired`, `folder-exists` or `bad-folder`, `no-main` for a main file that does not begin a document, or what reaching Overleaf failed on.
    """
    from loom import writes
    from loom.config_edit import set_values
    from loom.history.ledger import actor_for

    root = quilt.root
    folder = folder.strip().rstrip("/")
    if not plain_folder(folder):
        raise MirrorError("bad-folder", f"{folder or 'That'} is not a folder name loom can use")
    if (root / folder).exists() or (root / folder).is_symlink():
        raise MirrorError("folder-exists", f"{folder} exists already; choose a new folder")
    try:
        checked_folder(root, quilt.history_dir, folder)
    except MirrorError as exc:
        raise MirrorError("bad-folder", f"{folder} is not a folder name loom can use") from exc
    if paired(root) is not None:
        raise MirrorError("paired", "This quilt mirrors an Overleaf project already.")
    clone = _clone(root, project)
    rev = _tip(clone)
    if main not in main_files(clone, rev):
        raise MirrorError(
            "no-main", f"{main or 'That'} is not a file at the top of the project that begins a document."
        )
    files = tree_files(clone, rev)
    shown = [a["email"] for a in authors(clone, rev)]
    local_main = f"{folder}/{main}"
    with (
        writes.act(root, quilt.history_dir, "pull", actor if actor is not None else actor_for(root)) as w,
        writes.staging(w),
    ):
        # decided again under the lock: another request may have paired, or made the folder, since
        if paired(root) is not None:
            raise MirrorError("paired", "This quilt mirrors an Overleaf project already.")
        if (root / folder).exists():
            raise MirrorError("folder-exists", f"{folder} exists already; choose a new folder")
        for rel, data in files.items():
            w.replace(f"{folder}/{rel}", data)
        changes: dict[str, Any] = {"agents.deny": [*quilt.config.agents_deny, f"{folder}/"]}
        if not quilt.config.main or not (root / quilt.config.main).is_file():
            changes["quilt.main"] = local_main
        set_values(quilt, changes)
        SyncState(project=project, folder=folder, main=main, integrated=rev, incoming=rev).write(root)
    _keep_here(root, me=sorted({m.strip() for m in me if m.strip()}), asked=shown, ask=False, problem=None)
    return {"folder": folder, "main": local_main}


@_holding_clone
def who(quilt: Quilt) -> list[dict[str, str]]:
    """Who the paired project's history names, as the clone last fetched it, to ask the person again which is them; MirrorError `not-paired`, or what reaching Overleaf failed on where this machine has no clone yet."""
    state = SyncState.read(quilt.root)
    clone = quilt.root / OVERLEAF_CLONE
    if not _marked(clone, state.project):
        clone = _clone(quilt.root, state.project)
    return authors(clone, _tip(clone))


def set_me(quilt: Quilt, me: list[str]) -> None:
    """Keep the addresses the person goes by on Overleaf, answering the question `who` asks; [] is "none yet", asked again once the history names someone new."""
    shown = [a["email"] for a in who(quilt)]
    _keep_here(quilt.root, me=sorted({m.strip() for m in me if m.strip()}), asked=shown, ask=False)


# ---- fetching and updating -------------------------------------------------------------------------------------------


@_holding_clone
def fetch(quilt: Quilt) -> SyncState:
    """Fetch what Overleaf holds into loom's clone and record it as waiting, writing nothing of the person's; what could not be done is kept as this machine's `problem` (`here`), and cleared once a fetch succeeds. Says to ask again who the person is where the machine does not know.

    The clone is made again where this machine did not make it (`_clone`). The record is written under the door's lock, read again there, so a fetch beside an update never undoes it. Raises MirrorError `not-paired`, `bad-record`, or what reaching Overleaf failed on.
    """
    from loom.clock import stamp
    from loom.locks import locked
    from loom.paths import WRITES_LOCK
    from loom.sync import git

    root = quilt.root
    state = SyncState.read(root)
    try:
        clone = _clone(root, state.project)
        new = _tip(clone)
        try:
            revision(clone, state.integrated)
        except MirrorError as exc:
            # a project whose history does not hold what was last taken in from it is not this quilt's
            raise MirrorError("bad-record", BAD_PROJECT) from exc
    except MirrorError as exc:
        _keep_here(root, problem=exc.code)
        raise
    # a ref of loom's own keeps each fetched revision whatever later fetches do
    git(clone, "update-ref", f"refs/loom/seen/{new}", new)
    _keep_here(root, problem=None)
    _ask_again(root, clone, new)
    # the record read again and written under the door's lock, so an update that took text in since the first read is never put back
    with locked(root / WRITES_LOCK):
        state = SyncState.read(root)
        if new != state.incoming:
            state.incoming, state.observed = new, stamp()
            state.write(root)
    return state


def update(quilt: Quilt, actor: str | None = None) -> dict[str, Any]:
    """Fetch, and take what Overleaf holds into the mirrored folder as one act through the door (`sync.incorporate`).

    Parameters
    ----------
    quilt : Quilt
        The mirroring quilt.
    actor : str, optional
        Who the act is recorded as; default the quilt's author.

    Returns
    -------
    dict
        `state`: `up-to-date` when Overleaf holds nothing new, else `updated`, with `files`, how many were written; `by`, the names of the others whose changes Review lists; `own`, how many changed blocks and places are left out of Review because only the person's own commits touched them; `places`, each change outside a block, `{file, place, by}`, `place` one of `sync.PLACES`; `here`, the blocks whose change was one made here and written over; and `overwritten`, the files here that held a change made here and were written over, each kept as a version (`sync.incorporate`).

    Raises
    ------
    MirrorError
        `not-paired`, `bad-record`, `taken-in`, or what reaching Overleaf failed on.
    """
    from loom import sync

    state = fetch(quilt)
    if state.incoming == state.integrated:
        return {"state": "up-to-date"}
    said = sync.incorporate(quilt, state, here(quilt.root)["me"], actor)
    return {
        "state": "updated",
        "files": len(said["paths"]),
        "by": said["by"],
        "own": said["own"],
        "places": said["places"],
        "here": said["here"],
        "overwritten": said["overwritten"],
    }


@_holding_clone
def unpair(quilt: Quilt) -> None:
    """End the pairing: the record, loom's clone, its mark and this machine's part go; the folder stays, its files now the person's to edit like any other, and denied to agents until the person says otherwise in Settings."""
    root = quilt.root
    if not (root / SOURCE_SYNC).is_file():
        raise MirrorError("not-paired", "This quilt mirrors no Overleaf project.")
    (root / SOURCE_SYNC).unlink()
    clone = root / OVERLEAF_CLONE
    _mark_of(clone).unlink(missing_ok=True)
    _remove(clone)
    (root / OVERLEAF_HERE).unlink(missing_ok=True)


def published(root: Path) -> dict[str, Any]:
    """The manifest's `overleaf`: whether the quilt mirrors a project and how it stands, in fields the viewer draws in its own words; no revision, token or anyone's address.

    Returns
    -------
    dict
        `{"paired": false}`, or `paired`, `folder`, `main` (the main document's quilt path), `link` (the project's page in Overleaf, a link only), `waiting` (Overleaf holds text not yet taken in, as the last fetch saw), `last` (the last update: `when`, `files`, `by`, `own`, `places`, `here`; null before one), `ask_me` (ask the person again which of the history's authors is them) and `problem` (what the last reach of Overleaf could not do, by its code, `bad-record` for a record loom cannot use; null when it went well).
    """
    try:
        state = paired(root)
    except MirrorError:
        return {
            "paired": True,
            "folder": "",
            "main": "",
            "link": "",
            "waiting": False,
            "last": None,
            "ask_me": False,
            "problem": "bad-record",
        }
    if state is None:
        return {"paired": False}
    last = state.last_pull
    held = here(root)
    return {
        "paired": True,
        "folder": state.folder,
        "main": state.master,
        "link": f"https://www.overleaf.com/project/{state.project}",
        "waiting": bool(state.incoming) and state.incoming != state.integrated,
        "last": {k: last.get(k) for k in ("when", "files", "by", "own", "places", "here")}
        if last.get("when")
        else None,
        "ask_me": held["ask"],
        "problem": held["problem"],
    }
