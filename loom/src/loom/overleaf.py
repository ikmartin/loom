"""The Overleaf mirror: a folder of the quilt that holds one Overleaf project's files as Overleaf holds them, read over git and never written back.

Loom reaches Overleaf over git only (`https://git.overleaf.com/<id>`), and only to read: it clones, fetches and takes Overleaf's bytes into the folder when the person presses Update. Nothing in loom pushes.
"""

from __future__ import annotations

import re

#: Overleaf's git host; every address the mirror reaches is on it.
GIT_HOST = "git.overleaf.com"

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
