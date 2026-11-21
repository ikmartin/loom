"""Annotations: writing one, answering, resolving, editing and deleting it, taking in a PDF's own, and the quilt's annotation types."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loom.render.endpoints.base import ApiError, Handler, _scan, _str, plain, said


def _delete(root: Path, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    """Delete an annotation, answering with the events removed, or put back events a delete removed: the viewer's undo of a delete is the second."""
    from loom.cli.review import _annotator, delete_annotation
    from loom.errors import ContentError, EnvError, NotFoundError
    from loom.records.log import EVENTS, restore

    try:
        writer = _annotator(root, _str(body, "author"), sniff=False)
        if endpoint == "delete":
            said, removed = delete_annotation(root, _str(body, "annotation", required=True) or "", writer)
            return {"ok": True, "result": said, "removed": removed}
        events = body.get("events")
        if (
            not isinstance(events, list)
            or not events
            or not all(isinstance(e, dict) and e.get("event") in EVENTS and e.get("id") for e in events)
        ):
            raise ApiError("bad-field", "events must be the events a delete answered with")
        put = restore(root, events)
        return {"ok": True, "result": f"restored {', '.join(put)}"}
    except NotFoundError as exc:
        raise ApiError(f"no-such-{exc.what}", str(exc), status=404) from exc
    except (EnvError, ContentError, ValueError) as exc:
        raise ApiError("refused", str(exc)) from exc


def _review(root: Path, endpoint: str, body: dict[str, Any]) -> str:
    # Imported here rather than at module scope: the CLI package pulls in click and the whole command tree, and a server that is only ever asked for files should not pay for it at startup.
    from loom.cli.review import _annotator, _one_comment, edit_annotation
    from loom.errors import ContentError, EnvError, NotFoundError

    # Validate the request before touching the quilt: a missing field is the caller's mistake and should be named as one, not reported as whatever the first function to be handed nothing happens to complain about.
    needs = {"annotate": ("target",), "reply": ("annotation", "message")}.get(endpoint, ("annotation",))
    for field in needs:
        _str(body, field, required=True)

    # An annotation belongs to no session, so a `session` sent with one is ignored.
    try:
        # Who is at the browser, not what shell the server was started in: with `loom serve` running in an agent's terminal every annotation the author wrote in their own browser was recorded `author: "agent"` until this stopped sniffing. An agent posting here declares itself, and `is_agent` still guards the author's verbs by that name.
        writer = _annotator(root, _str(body, "author"), sniff=False)
    except NotFoundError as exc:
        raise ApiError(f"no-such-{exc.what}", str(exc), status=404) from exc
    except (EnvError, ContentError) as exc:
        raise ApiError("refused", str(exc)) from exc

    try:
        # `undo` opens a resolved annotation again by appending another event; the viewer offers it in place of the verb that fired, so a wrong click is one click back (DR-174).
        undo = bool(body.get("undo"))
        result = _scan(root)
        if endpoint == "edit":
            # the viewer sends the new text as `message`, as every other endpoint names it; the log's field is `body`
            fields = {"body": _str(body, "message")}
            # a type of "" or null takes the type off; absent leaves it as it is
            type_given = ("" if body["type"] is None else _str(body, "type")) if "type" in body else None
            return edit_annotation(
                result,
                _str(body, "annotation", required=True) or "",
                writer,
                False,
                type_given,
                _look(body),
                _geometry(body, "rects"),
                _geometry(body, "strokes"),
                # `look: null` drops the annotation's own look, so it follows its type again
                clear_look="look" in body and body["look"] is None,
                **fields,
            )
        if endpoint == "annotate":
            # an annotation on a PDF page carries the page and its rectangles or strokes (plan 0.13 item 2)
            page = body.get("page")
            if page is not None and (not isinstance(page, int) or page < 1):
                raise ApiError("bad-field", "page must be a positive integer")
            rects = _geometry(body, "rects")
            return _one_comment(
                result,
                writer,
                _str(body, "target", required=True),
                _str(body, "message"),
                _str(body, "quote"),
                _str(body, "type"),
                None,
                None,
                page=page,
                rects=rects,
                in_doc=_str(body, "in"),
                look=_look(body),
                strokes=_geometry(body, "strokes"),
                mark=_str(body, "mark"),
                purpose=_str(body, "purpose"),
            )
        annotation = _str(body, "annotation", required=True)
        if endpoint == "reply":
            return _one_comment(
                result, writer, None, _str(body, "message", required=True), None, None, annotation, None
            )
        return _one_comment(result, writer, None, _str(body, "message"), None, None, None, annotation, undo=undo)
    except NotFoundError as exc:
        raise ApiError(f"no-such-{exc.what}", str(exc), status=404) from exc
    except ContentError as exc:
        raise ApiError("refused", str(exc)) from exc
    except EnvError as exc:
        raise ApiError("bad-request", str(exc)) from exc


def _geometry(body: dict[str, Any], name: str) -> list[list[float]] | None:
    """`rects` or `strokes` as a write gives them, each a list of numbers; refused when it is not."""
    from loom.records.marks import MarkRefused, clean_rects, clean_strokes

    try:
        return (clean_rects if name == "rects" else clean_strokes)(body.get(name))
    except MarkRefused as exc:
        raise ApiError(exc.code, exc.message, status=exc.status) from exc


def _take(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`annotations-take`: a PDF's own annotations written as annotations on it, what is here already left alone (`marks.take_in`)."""
    from loom.cli.review import _annotator
    from loom.errors import ContentError, EnvError
    from loom.records.marks import MarkRefused, take_in

    items = body.get("items")
    if not isinstance(items, list):
        raise ApiError("missing-field", "items is the list of annotations to take in")
    try:
        writer = _annotator(root, _str(body, "author"), sniff=False)
        took = take_in(_scan(root), _str(body, "target", required=True) or "", items, writer)
    except MarkRefused as exc:
        raise ApiError(exc.code, exc.message, status=exc.status) from exc
    except (EnvError, ContentError) as exc:
        raise ApiError("refused", str(exc)) from exc
    return {"ok": True, "result": f"took in {took['taken']}", **took}


def _look(body: dict[str, Any]) -> dict[str, Any]:
    """The look a write sets, as `look: {color, style, weight, opacity}` with any field left out; refused when it is not a table."""
    look = body.get("look")
    if look is None:
        return {}
    if not isinstance(look, dict):
        raise ApiError("bad-field", "look must be an object of color, style, weight and opacity")
    return {k: look[k] for k in ("color", "style", "weight", "opacity") if k in look}


def _types_save(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`types-save` writes `.loom/records/annotation-types.toml` whole from Settings › Annotations, the plain look with the types when `plain` is sent, or with `defaults` the defaults; the author's act, refused to a declared agent, which edits the file itself."""
    from loom.identity import is_agent
    from loom.records.types import TypesRefused, save_types
    from loom.scan.quilt import reviewer_identity

    if is_agent(_str(body, "author") or reviewer_identity(root)[0]):
        raise ApiError(
            "author-only", "An agent edits the annotation types in their file; only the author saves them here", 403
        )
    given = body.get("types")
    if body.get("defaults") is True:
        given = None
    elif not isinstance(given, list):
        raise ApiError("missing-field", "types is the list of the quilt's annotation types, or send defaults: true")
    plain = body.get("plain")
    if plain is not None and not isinstance(plain, dict):
        raise ApiError("bad-field", "plain is a look: color, style, weight and opacity")
    try:
        saved = save_types(root, given, plain)
    except TypesRefused as exc:
        raise ApiError("bad-field", str(exc)) from exc
    said = "restored the default annotation types" if given is None else f"saved {len(saved.types)} annotation types"
    return {"ok": True, "result": said, "types": [t.to_dict() for t in saved.types], "plain": saved.plain.to_dict()}


HANDLERS: dict[str, Handler] = {
    "annotate": said(_review),
    "reply": said(_review),
    "resolve": said(_review),
    "edit": said(_review),
    "delete": _delete,
    "restore": _delete,
    "annotations-take": plain(_take),
    "types-save": plain(_types_save),
}
#: Of these, the ones that answer and change nothing the manifest shows.
READS: tuple[str, ...] = ()
#: The ones the publisher does not rebuild after.
NO_REBUILD: tuple[str, ...] = READS
#: The ones that change records alone, so the publication builds from the last scan.
RECORD_WRITES: tuple[str, ...] = (
    "annotate",
    "reply",
    "resolve",
    "edit",
    "delete",
    "restore",
    "annotations-take",
    "types-save",
)
