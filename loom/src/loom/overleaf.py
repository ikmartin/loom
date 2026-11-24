"""The Overleaf mirror: a folder of the quilt that holds one Overleaf project's files as Overleaf holds them, read over git and never written back.

Loom reaches Overleaf over git only (`https://git.overleaf.com/<id>`), and only to read: it clones, fetches and takes Overleaf's bytes into the folder when the person presses Update. Nothing in loom pushes.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from loom.sync import SyncError

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
