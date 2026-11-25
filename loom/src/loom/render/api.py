"""The write API: the HTTP form of loom's record-writing commands (specs/write-api.md, plan 0.11 Part G).

Served by the publisher, never by the viewer. Most endpoints write only Loom's private records. Explicit pull and AI incorporation apply exactly a reviewed patch to author files. Every endpoint wraps a library function shared with CLI and test surfaces.

Nothing here wakes an agent. An agent pulls: it reads open annotations with `loom status` and `loom ai annotations` and answers with `loom annotate --reply`. A person writing in the viewer and an agent answering in its own session are the same log seen from two ends.

The endpoints are in `loom.render.endpoints`, a module for each family with its own table of handlers, so that an endpoint is added in its family's module and nowhere else. This module is the way in: what the publisher and the tests call.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loom.render.endpoints import agents, changes, files, formal, library, review, sync, web
from loom.render.endpoints import annotations as annotating  # `annotations` is the name `from __future__` binds here
from loom.render.endpoints.agents import forget_place, reading_place
from loom.render.endpoints.base import ApiError, Handler, offer_scan

__all__ = [
    "CAPABILITIES",
    "MAX_BODY",
    "NO_REBUILD",
    "OWN_LOCK",
    "READS",
    "RECORD_WRITES",
    "UPGRADE",
    "WRITE_API_VERSION",
    "ApiError",
    "discovery",
    "forget_place",
    "handle",
    "offer_scan",
    "reading_place",
]

#: The families of endpoints, a module each: its `HANDLERS`, and which of them are `READS`, `NO_REBUILD` and `RECORD_WRITES`.
FAMILIES = (annotating, changes, library, agents, sync, review, files, web, formal)
#: Every endpoint's handler, from its family's table.
HANDLERS: dict[str, Handler] = {name: serve for family in FAMILIES for name, serve in family.HANDLERS.items()}
#: What this publisher serves. A viewer reads this rather than assuming the specification's table, so an endpoint that is not here answers 404 and a viewer that hides the affordance is right to. `open` is not here: `discovery` offers it only where loom can open an application.
CAPABILITIES = [name for name in HANDLERS if name != "open"]
#: The one write a publisher serves while its quilt is in an earlier layout (`ServeSession.older`): it brings the quilt forward, and every other endpoint answers `format-old` until it has.
UPGRADE = "library-upgrade"

WRITE_API_VERSION = 1

#: Endpoints that answer and change nothing the manifest shows, so the publisher does not rebuild after them.
READS = tuple(name for family in FAMILIES for name in family.READS)

#: The largest request body the publisher reads: a 256 MB PDF in base64, the largest a person drops in the viewer, which is about what a browser can encode; `loom library add` takes any size.
MAX_BODY = 344 * 1024 * 1024

#: Endpoints the publisher does not rebuild after: the reads, and the writes that publish what they change themselves.
NO_REBUILD = tuple(name for family in FAMILIES for name in family.NO_REBUILD)
#: Writes that change records alone, which the scan never reads, or keep a version, whose landmark the build reads again (`build(reuse=…)`); their publication builds from the last scan (`ServeSession.rebuild`).
RECORD_WRITES = tuple(name for family in FAMILIES for name in family.RECORD_WRITES)
#: Writes that take their own locks and hold none while they wait on the network, so the publisher runs them outside the publication's lock.
OWN_LOCK = ("here", *library.OWN_LOCK, *sync.OWN_LOCK)


def discovery() -> dict[str, Any]:
    """The answer to `GET /_api`; `open` is offered only on a machine that can open an application."""
    from loom.files import can_open

    return {"write_api": WRITE_API_VERSION, "capabilities": [*CAPABILITIES, *(["open"] if can_open() else [])]}


def handle(root: Path, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    """Perform one write and describe it, or raise `ApiError`.

    Parameters
    ----------
    root : Path
        The quilt.
    endpoint : str
        The path after `/_api/`, one of `CAPABILITIES`.
    body : dict
        The decoded JSON request.

    Returns
    -------
    dict
        `{"ok": True, "result": <what the CLI would have printed>}`.
    """
    from loom.identity import at_the_viewer

    if endpoint not in discovery()["capabilities"]:
        raise ApiError("unknown-endpoint", f"no endpoint {endpoint}", status=404)
    # a write over HTTP is the person at the viewer, whichever shell started the server
    with at_the_viewer():
        return HANDLERS[endpoint](root, endpoint, body)
