"""A paper brought into the quilt from the viewer: dropped, a file at a time, or chosen in the system's file dialog; a `.tex`, its folder or a source archive comes in through the import's one act, a PDF into the library (`app.create.bring`). The empty quilt's page is where the person does it."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loom.render.endpoints.base import ApiError, Handler, _str, plain


def _paper_import(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`paper-import`: bring what waits in `drop` into the quilt, the paper `main` names where several could be (`app.create.bring_drop`)."""
    from loom.app.create import bring_drop

    drop = _str(body, "drop", required=True) or ""
    return {"ok": True, **bring_drop(root, drop, _str(body, "main"))}


def _paper_choose(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`paper-choose`: the system's file dialog, on the person's click, then what they chose brought into the quilt (`app.create.bring_chosen`); `{cancelled: true}` when they cancel."""
    from loom.app.create import bring_chosen
    from loom.app.server import choose_file

    chosen = choose_file("Choose your paper, its source archive, or a PDF to read")
    if chosen is None:
        return {"ok": True, "cancelled": True}
    return {"ok": True, **bring_chosen(root, chosen)}


def _paper_receive(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`paper-receive` takes a file's bytes as they stream, which the publisher reads before any JSON (`render.serve`); a JSON body is not a file."""
    raise ApiError("not-a-stream", "a dropped file is sent as its bytes, application/octet-stream")


def receive_stream(drop: str | None, path: str, stream: Any, length: int) -> dict[str, Any]:
    """The publisher's way into `paper-receive`: keep the streamed bytes in a drop outside the quilt (`app.create.receive`), or raise ApiError once what the sender still sends is read, so it reads the refusal."""
    from loom.app.create import receive
    from loom.library.intake import _drain

    read = 0

    class Counted:
        def read(self, size: int = -1, /) -> bytes:
            nonlocal read
            chunk: bytes = stream.read(size)
            read += len(chunk)
            return chunk

    try:
        return {"ok": True, **receive(drop, path, Counted(), length)}
    except ApiError:
        _drain(stream, length - read)
        raise


HANDLERS: dict[str, Handler] = {
    "paper-receive": plain(_paper_receive),
    "paper-import": plain(_paper_import),
    "paper-choose": plain(_paper_choose),
}
#: Of these, the ones that answer and change nothing the manifest shows.
READS: tuple[str, ...] = ()
#: The ones the publisher does not rebuild after: a file received, which waits outside the quilt.
NO_REBUILD: tuple[str, ...] = ("paper-receive",)
#: The ones that change records alone.
RECORD_WRITES: tuple[str, ...] = ()
#: The ones run outside the publication's lock: the dialog waits on the person and an import compiles for minutes, while the import's act and the library's intake take their own locks.
OWN_LOCK: tuple[str, ...] = ("paper-import", "paper-choose")
