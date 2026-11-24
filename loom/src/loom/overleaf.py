"""The Overleaf mirror: a folder of the quilt that holds one Overleaf project's files as Overleaf holds them, read over git and never written back.

Loom reaches Overleaf over git only (`https://git.overleaf.com/<id>`), and only to read: it clones, fetches and takes Overleaf's bytes into the folder when the person presses Update. Nothing in loom pushes.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from loom.paths import OVERLEAF_CLONE, OVERLEAF_HERE
from loom.scan.quilt import Quilt
from loom.sync import SyncError, SyncState, tree_files

#: Overleaf's git host; every address the mirror reaches is on it.
GIT_HOST = "git.overleaf.com"
#: The credential helper every mirror git call names, after clearing any the person's own git config names: the macOS Keychain's, which Apple's and Homebrew's git ship. The test suite replaces it with a file in each test's temporary folder.
HELPER = "osxkeychain"
#: How long a call that reaches Overleaf may take before it is called unreachable, in seconds; a clone of a large project is the longest.
TIMEOUT = 300.0

#: A project id as Overleaf writes it in a project's address: 24 hex digits, or digits for an old project.
_ID = r"(?P<id>[0-9a-f]{24}|[0-9]+)"
#: A project's own address in the browser, or its git address, each with anything after the id.
_PROJECT = re.compile(rf"^(?:https?://)?(?:www\.)?overleaf\.com/project/{_ID}(?:[/?#].*)?$", re.I)
_GIT = re.compile(rf"^(?:https?://)?(?:[^@/\s]+@)?{re.escape(GIT_HOST)}/{_ID}(?:\.git)?/?(?:[?#].*)?$", re.I)
#: A sharing link: read-only (`/read/<token>`) or read-and-edit (`/<digits><letters>`), each holding a token and not the id.
_SHARING = re.compile(r"^(?:https?://)?(?:www\.)?overleaf\.com/(?:read/[A-Za-z0-9]+|[0-9]+[a-z]+)(?:[/?#].*)?$", re.I)


class LinkRefused(ValueError):
    """A pasted link no git address can be made from; `code` is the write API's."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def address(link: str) -> str:
    """The git address of the Overleaf project a pasted link names.

    Parameters
    ----------
    link : str
        The project's address in the browser (`https://www.overleaf.com/project/<id>`), its git address (`https://git.overleaf.com/<id>`), or the whole line Overleaf's Git dialog shows (`git clone https://git.overleaf.com/<id>`).

    Returns
    -------
    str
        `https://git.overleaf.com/<id>`.

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
    return f"https://{GIT_HOST}/{found.group('id').lower()}"


# ---- git, as the mirror runs it -------------------------------------------------------------------------------------


class MirrorError(SyncError):
    """Overleaf could not be read, and why, in the person's words; `code` is the write API's: `no-git`, `no-token`, `token-refused`, `no-git-access`, `offline`, `bad-token`, `failed`."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


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


def run(cwd: Path | None, *args: str, input: bytes | None = None) -> bytes:
    """Run git for the mirror, as the person's own git config never decides: the credential helper cleared and set to `HELPER`, and no prompt, so a missing or refused token fails at once instead of waiting on a terminal no one sees.

    Raises MirrorError with the failure's code (`_failure`); `no-git` where git cannot be run, `offline` past `TIMEOUT`.
    """
    from loom import gitprog

    if not gitprog.usable():
        raise MirrorError("no-git", SAID["no-git"])
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "", "SSH_ASKPASS": "", "GCM_INTERACTIVE": "never"}
    command = ["git", "-c", "credential.helper=", "-c", f"credential.helper={HELPER}", "-c", "core.askPass=", *args]
    try:
        done = subprocess.run(command, cwd=cwd, env=env, input=input, capture_output=True, check=False, timeout=TIMEOUT)
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
    """This machine's part of the mirror: `me`, the addresses the person goes by on Overleaf, and `problem`, the code of what the last reach of Overleaf could not do, or None. Kept in `.loom/local/`, never in the record that travels with the quilt, so that co-authors sharing a quilt each say who they are and no address is in a file a person commits."""
    try:
        data = json.loads((root / OVERLEAF_HERE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    me = data.get("me") if isinstance(data, dict) else None
    problem = data.get("problem") if isinstance(data, dict) else None
    return {
        "me": [m for m in me if isinstance(m, str)] if isinstance(me, list) else [],
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


# ---- pairing ---------------------------------------------------------------------------------------------------------


def paired(root: Path) -> SyncState | None:
    """The quilt's mirror record, or None when the quilt mirrors no Overleaf project."""
    try:
        state = SyncState.read(root)
    except SyncError:
        return None
    return state if state.folder else None


def _clone(root: Path, git_address: str) -> Path:
    """Loom's clone of the project at `git_address`, without a checkout, in `.loom/local/overleaf/`: fetched when it is that project's already, else made again beside and put in place, so a clone cut short never stands where a whole one is read."""
    clone = root / OVERLEAF_CLONE
    if (clone / ".git").is_dir():
        try:
            same = run(clone, "remote", "get-url", "origin").decode().strip() == git_address
        except MirrorError:
            same = False
        if same:
            run(clone, "fetch", "--quiet", "--no-tags", "origin")
            return clone
    fresh = clone.with_name(clone.name + ".new")
    shutil.rmtree(fresh, ignore_errors=True)
    fresh.parent.mkdir(parents=True, exist_ok=True)
    run(None, "clone", "--quiet", "--no-checkout", "--no-tags", git_address, str(fresh))
    shutil.rmtree(clone, ignore_errors=True)
    fresh.rename(clone)
    return clone


def _tip(clone: Path) -> tuple[str, str]:
    """(branch, revision) of the project as the clone last fetched it: the branch Overleaf's HEAD names, `main` today."""
    branch = run(clone, "symbolic-ref", "--short", "HEAD").decode().strip()
    return branch, run(clone, "rev-parse", "--verify", f"refs/remotes/origin/{branch}^{{commit}}").decode().strip()


def main_files(clone: Path, rev: str) -> list[str]:
    """The project's main file candidates at `rev`: each `.tex` at its top that declares a document class and begins a document; Overleaf's own choice of main file is not in git."""
    out = []
    for name in sorted(n for n in run(clone, "ls-tree", "--name-only", "-z", rev).decode().split("\0") if n):
        if name.lower().endswith(".tex"):
            text = run(clone, "show", f"{rev}:{name}").decode("utf-8", errors="replace")
            if "\\documentclass" in text and "\\begin{document}" in text:
                out.append(name)
    return out


def authors(clone: Path, rev: str) -> list[dict[str, str]]:
    """Who the project's history names, latest first, once each by address: `{name, email}`."""
    seen: dict[str, dict[str, str]] = {}
    for line in run(clone, "log", "--format=%aN%x00%aE", rev).decode("utf-8", errors="replace").splitlines():
        name, _, email = line.partition("\0")
        if email and email.lower() not in seen:
            seen[email.lower()] = {"name": name, "email": email}
    return list(seen.values())


def _folder_refused(root: Path, folder: str) -> str:
    """Why `folder` cannot take the project, or '': it must be a new folder of the person's, inside the quilt, under no dot-named folder."""
    parts = PurePosixPath(folder).parts
    if not folder or folder.startswith("/") or "\\" in folder or ".." in parts or any(p.startswith(".") for p in parts):
        return f"{folder or 'That'} is not a folder name loom can use"
    if (root / folder).exists():
        return f"{folder} exists already; choose a new folder"
    return ""


def propose_folder(root: Path) -> str:
    """A new folder's name for the project: `paper`, else `overleaf`, else `overleaf-2` and on."""
    for name in ("paper", "overleaf", *(f"overleaf-{n}" for n in range(2, 100))):
        if not (root / name).exists():
            return name
    return "overleaf-project"


def prepare(quilt: Quilt, git_address: str) -> dict[str, Any]:
    """Reach the project and say what pairing asks of the person, writing nothing of theirs: the clone is made or fetched.

    Parameters
    ----------
    quilt : Quilt
        The quilt to pair.
    git_address : str
        The project's git address (`address`).

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
    clone = _clone(root, git_address)
    _, rev = _tip(clone)
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


def pair(
    quilt: Quilt, git_address: str, folder: str, main: str, me: list[str], actor: str | None = None
) -> dict[str, Any]:
    """Copy the project into a new folder of the quilt and record the pairing, as one act through the door.

    Parameters
    ----------
    quilt : Quilt
        The quilt to pair.
    git_address : str
        The project's git address (`address`).
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
    from loom.history.ledger import actor_for

    root = quilt.root
    folder = folder.strip().rstrip("/")
    refused = _folder_refused(root, folder)
    if refused:
        raise MirrorError("folder-exists" if (root / folder).exists() and folder else "bad-folder", refused)
    clone = _clone(root, git_address)
    branch, rev = _tip(clone)
    if main not in main_files(clone, rev):
        raise MirrorError(
            "no-main", f"{main or 'That'} is not a file at the top of the project that begins a document."
        )
    files = tree_files(clone, rev)
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
        from loom.config_edit import set_values

        set_values(quilt, changes)
        SyncState(
            directory=OVERLEAF_CLONE,
            remote="origin",
            url=git_address,
            branch=branch,
            master=local_main,
            integrated=rev,
            incoming=rev,
            published_main=main,
            documents=[local_main],
            folder=folder,
        ).write(root)
    _keep_here(root, me=sorted({m.strip() for m in me if m.strip()}), problem=None)
    return {"folder": folder, "main": local_main}


# ---- fetching and updating -------------------------------------------------------------------------------------------


def fetch(quilt: Quilt) -> SyncState:
    """Fetch what Overleaf holds into loom's clone and record it as waiting, writing nothing of the person's; what could not be done is kept as this machine's `problem` (`here`), and cleared once a fetch succeeds.

    The clone is made again where a copied quilt lacks it. Raises MirrorError `not-paired`, or what reaching Overleaf failed on.
    """
    from loom.clock import stamp
    from loom.sync import git, revision

    root = quilt.root
    state = paired(root)
    if state is None:
        raise MirrorError("not-paired", "This quilt mirrors no Overleaf project.")
    clone = root / OVERLEAF_CLONE
    try:
        if (clone / ".git").is_dir():
            run(clone, "fetch", "--quiet", "--no-tags", "origin", state.branch)
        else:
            _clone(root, state.url)
        new = revision(clone, f"refs/remotes/origin/{state.branch}")
    except MirrorError as exc:
        _keep_here(root, problem=exc.code)
        raise
    # a ref of loom's own keeps the fetched revision whatever later fetches do
    git(clone, "update-ref", f"refs/loom/incoming/{new}", new)
    _keep_here(root, problem=None)
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
        `state`: `up-to-date` when Overleaf holds nothing new, else `updated`, with `files`, how many were written, `by`, the names of the others whose changes Review lists, `own`, how many changed blocks are left out of Review because only the person's own commits touched them, and `overwritten`, the files here that held a change made here and were written over.

    Raises
    ------
    MirrorError
        `not-paired`, or what reaching Overleaf failed on.
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
        "overwritten": said["overwritten"],
    }
