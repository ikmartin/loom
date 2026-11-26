"""Notes: New note at the person's click, which runs their own command or writes a Markdown note, and the command itself, which only they set (`loom.notes`)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loom.render.endpoints.base import ApiError, Handler, _str, plain


def _refused(exc: Exception) -> ApiError:
    from loom.notes import NoteRefused
    from loom.writes import WriteRefused

    if isinstance(exc, NoteRefused):
        status = {"author-only": 403, "bad-field": 400, "bad-command": 400}.get(exc.code, 409)
        return ApiError(exc.code, exc.message, status=status)
    assert isinstance(exc, WriteRefused)
    return ApiError(exc.code, exc.message, status=exc.status)


def _new_note(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`new-note`: run the person's command on `link`, the quoted words and a name for the place, or write a Markdown note and open it when none is set; refused to an agent."""
    from loom.notes import NoteRefused, request, run
    from loom.writes import WriteRefused

    link = _str(body, "link", required=True) or ""
    try:
        req = request(root, link, _str(body, "quote") or "", _str(body, "title") or "")
        done = run(root, req, actor=_str(body, "author"))
    except (NoteRefused, WriteRefused) as exc:
        raise _refused(exc) from exc
    if done.how == "wrote":
        return {"ok": True, "result": f"wrote {done.path}", "how": "wrote", "path": done.path}
    return {"ok": True, "result": "ran your new-note command", "how": "ran", "said": done.said}


def _notes_settings(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`notes-settings`: the person's new-note command for this quilt, saved first when `command` is sent ('' removes it); refused to an agent, which neither reads nor sets it here."""
    from loom.identity import agents_act
    from loom.notes import NoteRefused, command_for, commands_path, set_command

    author = _str(body, "author")
    if agents_act(author):
        raise ApiError("author-only", "An agent never reads or sets the command loom runs at your click", status=403)
    try:
        if "command" in body:
            command = body.get("command")
            if not isinstance(command, str):
                raise ApiError("bad-field", "command must be a string")
            set_command(root, command, actor=author)
        return {"ok": True, "result": "notes settings", "command": command_for(root), "kept": str(commands_path())}
    except NoteRefused as exc:
        raise _refused(exc) from exc


HANDLERS: dict[str, Handler] = {
    "new-note": plain(_new_note),
    "notes-settings": plain(_notes_settings),
}
#: Of these, the ones that answer and change nothing the manifest shows: the command is the person's and never in the manifest.
READS: tuple[str, ...] = ("notes-settings",)
#: The ones the publisher does not rebuild after: New note's file, the stub or the one the person's editor makes, reaches the manifest through the watcher, as any file the person saves does.
NO_REBUILD: tuple[str, ...] = (*READS, "new-note")
#: The ones run outside the publication's lock: the command may take seconds to answer, and the stub is written through the door, which takes its own.
OWN_LOCK: tuple[str, ...] = ("new-note", "notes-settings")
#: The ones that change records alone.
RECORD_WRITES: tuple[str, ...] = ()
