"""Changes and history: keeping and discarding what waits on the person, recording and restoring versions, and comparing two of them."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loom.render.endpoints.base import ApiError, Handler, _scan, _str, plain


def _author(root: Path, body: dict[str, Any]) -> tuple[str, tuple[str, str]]:
    """The reviewer name and the writer of a change act; `author-only` (403) for a declared agent."""
    from loom.cli.review import _annotator
    from loom.errors import ContentError, EnvError
    from loom.identity import is_agent

    who = reviewer_identity_of(root)
    if is_agent(_str(body, "author") or who):
        raise ApiError(
            "author-only", "An agent suggests and annotates; only the author keeps or discards a change", status=403
        )
    try:
        return who, _annotator(root, _str(body, "author"), sniff=False)
    except (EnvError, ContentError) as exc:
        raise ApiError("refused", str(exc)) from exc


def _change(root: Path, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    """`change-keep` and `change-discard`: the person keeps or discards changes waiting on them (`pending.py`), by id, or every one with `all`, of one document with `document`; the author's acts, refused to a declared agent. `change-discard` takes `why`, and with `undo` opens again the discarded suggested edits it names."""
    from loom.looks import keep_all, read_look
    from loom.pending import PendingRefused, discard, keep, pending
    from loom.writes import WriteRefused

    who, writer = _author(root, body)
    # a scan of the files as they are now: what waits is cut from them, and the publisher's may predate an edit
    from loom.cli._quilt import open_scan

    result = open_scan(str(root))
    given = body.get("changes")
    if body.get("all") is True:
        document = _str(body, "document")
        if endpoint == "change-keep" and result.quilt.config.track_edits and who and read_look(root, who) is None:
            keep_all(result.quilt, who)
            return {"ok": True, "result": "took your first look", "done": [], "refused": []}
        ids = [c.id for c in pending(result, who) if document is None or document in c.documents]
    elif isinstance(given, list) and given and all(isinstance(i, str) for i in given):
        ids = list(given)
    else:
        raise ApiError("missing-field", "changes is the list of the changes' ids, or send all: true")
    if endpoint == "change-discard" and body.get("undo") is True:
        return _reopen(root, ids, writer)
    versions: list[str] = []
    try:
        if endpoint == "change-keep":
            done, refused = keep(result, who, ids, writer, versions)
        else:
            done, refused = discard(result, who, ids, writer, _str(body, "why"), versions)
    except (PendingRefused, WriteRefused) as exc:
        raise ApiError(exc.code, exc.message, status=exc.status) from exc
    verb = "kept" if endpoint == "change-keep" else "discarded"
    parts = [f"{verb} {len(done)} change{'s' if len(done) != 1 else ''}"]
    if refused:
        parts.append(f"{len(refused)} could not be")
    said = "; ".join([*parts, *versions])
    return {"ok": True, "result": said, "done": done, "refused": refused}


def _undo(root: Path, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    """`change-undo`: the person undoes the Keep of the suggested edits it names, each in one step (`pending.unkeep`); the author's act, refused to a declared agent, and refused whole (`other-quilt`) unless it names this quilt."""
    from loom.cli._quilt import open_scan
    from loom.pending import PendingRefused, unkeep
    from loom.writes import WriteRefused

    who, writer = _author(root, body)
    given = body.get("changes")
    if not (isinstance(given, list) and given and all(isinstance(i, str) for i in given)):
        raise ApiError("missing-field", "changes is the list of the kept suggested edits' ids")
    # a tab may have followed the port to another quilt: an undo is done only in the quilt it names
    from loom.machine import quilt_id

    named = body.get("quilt")
    if named != quilt_id(root):
        why = "another quilt" if named is not None else "a quilt the undo does not name"
        raise ApiError("other-quilt", f"that Keep was made in {why}, so nothing was undone", status=409)
    versions: list[str] = []
    try:
        done, refused = unkeep(open_scan(str(root)), who, list(given), writer, versions)
    except (PendingRefused, WriteRefused) as exc:
        raise ApiError(exc.code, exc.message, status=exc.status) from exc
    parts = [f"undid the keep of {len(done)} suggested edit{'s' if len(done) != 1 else ''}"]
    if refused:
        parts.append(f"{len(refused)} could not be")
    return {"ok": True, "result": "; ".join([*parts, *versions]), "done": done, "refused": refused}


def reviewer_identity_of(root: Path) -> str:
    """The reviewer name Review resolves, whose look the changes are since; '' when there is none."""
    from loom.scan.quilt import reviewer_identity

    return reviewer_identity(root)[0] or ""


def _reopen(root: Path, ids: list[str], writer: tuple[str, str]) -> dict[str, Any]:
    """Open again the discarded suggested edits `ids`: the viewer's undo of a Discard. A kept one is refused (`records.edits.discard`); `change-undo` undoes its Keep."""
    from loom.records.edits import EditRefused, discard, find

    done: list[str] = []
    refused: list[dict[str, str]] = []
    for i in ids:
        edit = find(root, i)
        if edit is None:
            raise ApiError(
                "no-such-change",
                f"no suggested edit {i}; an in-place change discarded comes back from History",
                status=404,
            )
        try:
            discard(root, edit, writer, undo=True)
            done.append(i)
        except EditRefused as exc:
            refused.append({"id": i, "why": exc.message, "code": exc.code})
    return {"ok": True, "result": f"reopened {len(done)}", "done": done, "refused": refused}


def _history(root: Path, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    """`history-record` keeps a version of a document under the author's name for it, as `loom stamp DOC -m NAME`; `history-restore` puts a version back into its document (`document`, `version`), or the text an undo set aside back into its file (`path`, `text`), keeping what it replaces first. The author's acts, refused to a declared agent."""
    from loom.history.acts import RestoreRefused, put_back, restore
    from loom.history.ledger import actor_for, load_history
    from loom.history.steps import slug, stamp_document
    from loom.identity import is_agent
    from loom.looks import open_texts
    from loom.scan.quilt import load_quilt, reviewer_identity

    who = reviewer_identity(root)[0] or actor_for(root)
    if is_agent(_str(body, "author") or who or ""):
        raise ApiError(
            "author-only", "An agent reads and annotates; only the author records or restores a version", status=403
        )
    quilt = load_quilt(root)
    if endpoint == "history-restore" and body.get("path") is not None:
        path = _str(body, "path", required=True) or ""
        digest = _str(body, "text", required=True) or ""
        try:
            put_back(root, quilt.history_dir, path, digest, who, open_texts(quilt))
        except RestoreRefused as exc:
            raise ApiError(exc.code, exc.message, status=409) from exc
        return {"ok": True, "result": f"put {path} back as the undo found it; its text before is kept"}
    result = _scan(root)
    doc = _str(body, "document", required=True) or ""
    if result.document_role(doc) != "person":
        raise ApiError("bad-field", f"{doc} is not one of your documents")
    if endpoint == "history-record":
        name = (_str(body, "name", required=True) or "").strip()
        if not name:
            raise ApiError("bad-field", "a version needs a name", fields={"name": "Give the version a name."})
        history = load_history(quilt.history_dir)
        landmark = slug(f"{Path(doc).stem} {name}", limit=120)
        if history.landmark(landmark) is not None:
            raise ApiError(
                "name-in-use",
                f"a version named {name} is kept already",
                status=409,
                fields={"name": "That name is in use."},
            )
        try:
            stamp_document(result, history, doc, landmark, name, who)
        except ValueError as exc:
            raise ApiError("cannot-record", str(exc).split(";")[0], status=409) from exc
        return {"ok": True, "result": f"kept this version of {Path(doc).name} as “{name}”"}
    version = _str(body, "version", required=True) or ""
    try:
        done = restore(result, doc, version, who)
    except RestoreRefused as exc:
        raise ApiError(exc.code, exc.message, status=404 if exc.code == "unknown-version" else 409) from exc
    if not done["paths"]:
        return {"ok": True, "result": f"{Path(doc).name} is already as “{done['label']}” holds it"}
    return {
        "ok": True,
        "result": f"put {Path(doc).name} back as “{done['label']}” holds it; its text before is the version “{done['before']}”",
    }


def _compare(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """The differing pairs of two items, rendered with their changed words.

    Body: `left` and `right`, each a live document's path or a landmark (`DOC@STEP`, a name or a step). Writes nothing a record holds: its renderings go to `.loom/cache/site/compare/`, named by their inputs.
    """
    from loom.render.compare import CompareError, compare

    left = _str(body, "left", required=True) or ""
    right = _str(body, "right", required=True) or ""
    try:
        return {"ok": True, **compare(_scan(root), left, right)}
    except CompareError as exc:
        raise ApiError("unknown-item", str(exc), status=404) from exc


HANDLERS: dict[str, Handler] = {
    "change-keep": _change,
    "change-discard": _change,
    "change-undo": _undo,
    "history-record": _history,
    "history-restore": _history,
    "compare": plain(_compare),
}
#: Of these, the ones that answer and change nothing the manifest shows.
READS: tuple[str, ...] = ("compare",)
#: The ones the publisher does not rebuild after.
NO_REBUILD: tuple[str, ...] = READS
#: The ones that change records alone, or keep a version, so the publication builds from the last scan.
RECORD_WRITES: tuple[str, ...] = ("history-record",)
