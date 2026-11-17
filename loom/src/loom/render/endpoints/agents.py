"""Agents and sessions: an agent's app set up in the quilt, a session made, named, closed, reopened and deleted, and the place the reader is, which an agent may ask for."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loom.render.endpoints.base import ApiError, Handler, _str, plain, said


def _resolve_session(root: Path, which: str, *, deleted: bool = False) -> Any:
    """The session `which` names, live unless `deleted`: 404 when none does, 409 naming them when several do."""
    from loom.sessions import SessionNotFound, resolve

    try:
        return resolve(root, which, deleted=deleted)
    except SessionNotFound as exc:
        if exc.matches:
            raise ApiError("ambiguous-session", str(exc), status=409) from None
        raise ApiError("no-such-session", str(exc), status=404) from None


def _session(root: Path, endpoint: str, body: dict[str, Any]) -> str:
    """Change which session is active, retitle one, or tombstone one (plan 0.13 §5).

    Through the same functions `loom session` calls, so the two surfaces cannot spell a session event differently. **Purging is not here and never will be**: it rewrites the annotation log, and the one place that should be reachable from is a terminal where the author typed the word.
    """
    from loom.identity import whoever
    from loom.sessions import active, close, create, delete, purpose, rename, resume, sessions, set_active

    who = _str(body, "author") or whoever(root, sniff=False)
    if endpoint == "session-new":
        # named by the author on the spot, and made the one writing lands in: what §16's example does from the page
        title = _str(body, "title", required=True) or ""
        made = create(root, title, who, purpose=_str(body, "purpose") or "")
        set_active(root, made.id)
        return f"{made.id}  {title}  (active)"
    which = _str(body, "session", required=True) or ""
    # resuming and deleting name a tombstone to refuse it with its reason, and deleting one again is harmless
    found = _resolve_session(root, which, deleted=endpoint in ("session-use", "session-delete"))
    if endpoint == "session-close":
        if found.state != "open":
            raise ApiError("refused", f"{found.id} is {found.state}")
        close(root, found.id, who)
        if active(root) == found.id:
            set_active(root, None)
        return f"closed {found.id}; its annotations are hidden until it is shown or resumed"
    if endpoint == "session-reopen":
        if found.state == "open":
            raise ApiError("refused", f"{found.id} is already open")
        resume(root, found.id, who)
        return f"reopened {found.id}"
    if endpoint == "session-purpose":
        purpose(root, found.id, _str(body, "purpose") or "", who)
        return f"{found.id} is for {_str(body, 'purpose') or '(nothing stated)'}"
    if endpoint == "session-rename":
        title = _str(body, "title", required=True) or ""
        rename(root, found.id, title, who)
        return f"{found.id} is now {title}"
    if endpoint == "session-delete":
        delete(root, found.id, who, _str(body, "reason") or "")
        if active(root) == found.id:
            set_active(root, None)
        return f"deleted {found.id}; its annotations stay in the log"
    if found.state == "deleted":
        raise ApiError("refused", f"{found.id} was deleted; nothing new can be written to it")
    if found.state == "closed":
        resume(root, found.id, who)
    set_active(root, found.id)
    return f"writing to {sessions(root)[found.id].title}"


#: Where the reader is, by quilt: the last place a viewer tab reported (`here`), the stamp it came at, and when by this process's clock. Held in memory only, never written: it is where a person is, not a record.
_HERE: dict[Path, tuple[str, float, dict[str, Any]]] = {}


#: The largest place a tab may report, in bytes of JSON: a selection is words, not a document.
HERE_LIMIT = 64_000


def reading_place(root: Path) -> dict[str, Any]:
    """`GET /_api/here`'s answer: the last place a tab reported, when, and how many seconds ago; `place` is None before any has."""
    import time

    kept = _HERE.get(root.resolve())
    if kept is None:
        return {"place": None, "when": None, "age": None}
    when, at, place = kept
    return {"place": place, "when": when, "age": round(time.monotonic() - at, 1)}


def forget_place(root: Path) -> None:
    """Drop the reader's place, as a server does when it stops: nobody is reading through it any more."""
    _HERE.pop(root.resolve(), None)


def _here(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """Keep the place a viewer tab reports, in place of the last one: the tab touched last wins."""
    import json
    import time

    from loom.clock import stamp

    if body.get("route") not in ("reading", "review", "elsewhere"):
        raise ApiError("bad-field", "route must be reading, review or elsewhere")
    if len(json.dumps(body)) > HERE_LIMIT:
        raise ApiError("bad-field", f"a place is at most {HERE_LIMIT:,} bytes")
    _HERE[root.resolve()] = (stamp(), time.monotonic(), body)
    return {"ok": True}


def _setup(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """Write what agent app `app` needs to work in the quilt, as `loom ai init` writes it for every app: the agent layer where there is none, over MCP, and that app's own files alone.

    The apps the quilt is set up for already keep theirs, and a quilt whose agents use the shell keeps it. The author's act, refused to a declared agent: an agent never sets up its own boundary.
    """
    from loom.ai.clients import BY_KEY, PROJECT, chosen
    from loom.ai.layout import MCP, variant
    from loom.cli.ai import install_layer
    from loom.cli.report import counted
    from loom.identity import is_agent
    from loom.paths import AI
    from loom.scan.quilt import reviewer_identity

    if is_agent(_str(body, "author") or reviewer_identity(root)[0]):
        raise ApiError(
            "author-only",
            "An agent works in the quilt as it is set up; only the author sets up an agent's app",
            status=403,
        )
    app = _str(body, "app", required=True) or ""
    keys = [c.key for c in PROJECT]
    if app not in keys:
        raise ApiError("bad-field", f"app is one of {', '.join(keys)}")
    # a quilt with no agent layer is set up for no app yet
    have = chosen(root, None) if (root / AI).is_dir() else []
    layer, clients = install_layer(root, apps=[k for k in keys if k in have or k == app])
    written = sorted(dict.fromkeys([*layer.written, *clients.written]))
    label = BY_KEY[app].label
    said = (
        f"set up {label}: wrote {counted(len(written), 'file')}" if written else f"{label} was set up; nothing written"
    )
    foreign = [*clients.foreign, *layer.theirs]
    if clients.foreign:
        said += f"; left {', '.join(clients.foreign)} alone, which holds settings of yours"
    if layer.merged:
        said += f"; kept your own settings in {', '.join(layer.merged)} beside loom's rules"
    if layer.theirs:
        said += f"; left {', '.join(layer.theirs)} alone, which loom did not write"
    if layer.removed:
        said += f"; removed {', '.join(layer.removed)}, loom's own for a mode the quilt no longer has"
    if clients.tracked:
        said += f"; did not write {', '.join(clients.tracked)}, which git tracks and which names this machine's paths"
    return {
        "ok": True,
        "result": said,
        "written": written,
        "removed": layer.removed,
        "merged": layer.merged,
        "foreign": foreign,
        "tracked": clients.tracked,
        "variant": variant(root) or MCP,
    }


HANDLERS: dict[str, Handler] = {
    "agents-setup": plain(_setup),
    "session-use": said(_session),
    "session-rename": said(_session),
    "session-delete": said(_session),
    "session-new": said(_session),
    "session-close": said(_session),
    "session-reopen": said(_session),
    "session-purpose": said(_session),
    "here": plain(_here),
}
#: Of these, the ones that answer and change nothing the manifest shows.
READS: tuple[str, ...] = ("here",)
#: The ones the publisher does not rebuild after.
NO_REBUILD: tuple[str, ...] = READS
#: The ones that change records alone, so the publication builds from the last scan.
RECORD_WRITES: tuple[str, ...] = (
    "session-new",
    "session-use",
    "session-rename",
    "session-delete",
    "session-close",
    "session-reopen",
    "session-purpose",
)
