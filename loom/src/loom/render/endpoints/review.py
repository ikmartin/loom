"""Review: the author's acceptance of blocks, and the lists of what waits for the person and for an agent (`docs/specs/evidence.md` §6, §7)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loom.paths import MANIFEST
from loom.render.endpoints.base import ApiError, Handler, _scan, _str, plain


def _review_accept(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`review-accept`: the author's acceptance of the blocks named, against the manifest the page was drawn from; an edit that touches only blocks just accepted is kept as seen."""
    import json

    from loom.identity import is_agent
    from loom.review_queue import accept
    from loom.scan.quilt import reviewer_identity

    reviewer, _ = reviewer_identity(root)
    if not reviewer:
        raise ApiError("no-reviewer", "Choose your reviewer name in Settings", status=409)
    if _str(body, "reviewer") != reviewer:
        raise ApiError("reviewer-changed", "Reviewer changed; reload Review before continuing", status=409)
    if is_agent(_str(body, "author") or reviewer):
        raise ApiError("author-only", "An agent reads and annotates; only the author accepts", status=403)
    keys = body.get("keys")
    if not isinstance(keys, list) or not keys or not all(isinstance(k, str) and k for k in keys):
        raise ApiError("bad-field", "keys must be a nonempty list of block keys")
    manifest_path = root / MANIFEST
    if not manifest_path.is_file():
        raise ApiError("review-unavailable", "build the quilt before reviewing", status=409)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("reviewer", {}).get("name") != reviewer:
        raise ApiError("reviewer-changed", "Rebuild and reload Review before continuing", status=409)
    try:
        answer = accept(_scan(root), manifest, keys, reviewer)
    except KeyError as exc:
        raise ApiError("not-unresolved", f"{exc.args[0]} is not awaiting review; reload Review", status=409) from exc
    except ValueError as exc:
        raise ApiError("compile-failed", str(exc), status=409) from exc
    if answer["accepted"]:
        # what the page showed with its Accept: an edit touching only blocks just accepted has been seen
        from loom.history.acts import keep_versions
        from loom.pending import keep_accepted

        after = _scan(root)
        moved = keep_accepted(after, reviewer, answer["accepted"])
        if moved:
            keep_versions(after, moved, "keep", "Kept an edit", reviewer)
    return {
        "ok": True,
        "result": f"accepted {len(answer['accepted'])} of {len(answer['accepted']) + len(answer['refused'])}",
        **answer,
    }


def _gathered(root: Path) -> tuple[Any, dict[str, Any], Any]:
    """The scan, the published manifest ({} before a first build) and every list's rows, for one read.

    Kept while the scan is the publisher's same one and no file `review.files_read` names changed (`memo.kept`); asks to agents marked by the servers alive now on every read, which no file says.
    """
    import json

    from loom.evidence.asks import live_sessions
    from loom.evidence.memo import kept
    from loom.evidence.review import files_read, gather, working

    result = _scan(root)

    def make() -> tuple[dict[str, Any], Any]:
        path = root / MANIFEST
        manifest = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        return manifest, gather(root, result, manifest)

    manifest, gathered = kept(root, "review", result, lambda: files_read(root), make)
    return result, manifest, working(gathered, live_sessions(root))


def _review_counts(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`review-counts`: each kind's rows, what waits for an agent, everything, and each of the person's documents with what concerns it."""
    from loom.evidence.review import counts

    result, _manifest, gathered = _gathered(root)
    documents = _persons(result)
    return {"ok": True, **counts(gathered, documents)}


def _persons(result: Any) -> list[str]:
    """The person's documents, by path: the scan's documents whose role is `person`, never an agent's copy."""
    return sorted(m for m in result.masters if result.document_role(m) == "person")


def _review_list(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`review-list`: one kind's rows, what waits for an agent, or everything in rank order; narrowed to one document with `doc`."""
    from loom.evidence.review import AGENTS, KINDS, listed

    kind = _str(body, "kind") or "all"
    if kind not in (*KINDS, AGENTS, "all"):
        raise ApiError("bad-field", f"kind is all, agents or one of {', '.join(KINDS)}")
    _result, _manifest, gathered = _gathered(root)
    return {"ok": True, "groups": listed(gathered, kind, _str(body, "doc"))}


def _review_row(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`review-row`: one row with what its body is drawn from, asked when the row opens."""
    from loom.evidence.review import body_of, find

    row_id = _str(body, "row", required=True) or ""
    _result, manifest, gathered = _gathered(root)
    found = find(gathered, row_id)
    if found is None:
        raise ApiError("no-such-row", f"{row_id} waits for nobody now; reload Review", status=404)
    return {"ok": True, "row": found.to_dict(), "body": body_of(found, manifest)}


def _person(root: Path, body: dict[str, Any]) -> Any:
    """The person a Review write acts as: the quilt's reviewer, refused for a declared agent (`author-only`), as accepting is."""
    from loom.evidence.subjects import Who
    from loom.identity import is_agent
    from loom.scan.quilt import reviewer_identity

    reviewer, _ = reviewer_identity(root)
    if not reviewer:
        raise ApiError("no-reviewer", "Choose your reviewer name in Settings", status=409)
    if is_agent(_str(body, "author") or reviewer):
        raise ApiError(
            "author-only", "An agent asks and answers with its own commands; this is the person's", status=403
        )
    return Who("person", reviewer)


def _as(body: dict[str, Any], who: Any) -> str:
    """' as NAME, the reviewer' when the body names another person as `author`, for the answer to say whose name the record carries; '' otherwise."""
    author = _str(body, "author")
    return f" as {who.name}, the reviewer" if author and author != who.name else ""


def _refused(exc: Exception, task: str) -> ApiError:
    """An ask's refusal as the write API answers it: an ask the log does not hold is 404, anything else 409."""
    message = str(exc)
    if "is no ask" in message:
        return ApiError("no-such-task", f"{task} is no ask of this quilt; reload Review", status=404)
    return ApiError("refused", message, status=409)


def _review_answer(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`review-answer`: the person answers an agent's question, with one of its choices, words of their own, or both; recorded as the reviewer whatever `author` names, which the answer says."""
    from loom.evidence.asks import AskRefused, replay, say

    who = _person(root, body)
    question = _str(body, "question", required=True) or ""
    choice = body.get("choice")
    if choice is not None and (not isinstance(choice, int) or isinstance(choice, bool)):
        raise ApiError("bad-field", "choice is the number of one of the question's choices")
    found = replay(root).asks.get(question)
    if found is not None and (found.answers or found.withdrawn is not None):
        raise ApiError("closed", "this question is answered or withdrawn already; reload Review", status=409)
    try:
        say(
            root,
            who,
            "answered",
            question,
            words=_str(body, "text") or "",
            **({"choice": choice} if choice is not None else {}),
        )
    except AskRefused as exc:
        raise _refused(exc, question) from exc
    return {"ok": True, "result": "answered" + _as(body, who)}


def _review_task(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`review-task`: the person asks an agent; `on` holds the place and what the kind needs, `docs` the person's documents it is for, by default those that read the place (`docs/specs/evidence.md` §7)."""
    from loom.evidence.asks import AskRefused, ask

    who = _person(root, body)
    kind = _str(body, "kind", required=True) or ""
    on = body.get("on")
    if not isinstance(on, dict):
        raise ApiError("bad-field", "on is an object naming the place and what the task needs")
    docs = _docs(root, body.get("docs"))
    place, fields, readers = _task(root, kind, on, _str(body, "text") or "")
    try:
        made = ask(root, who, kind, "agent", place, origin=docs or readers, **fields)
    except AskRefused as exc:
        raise ApiError("refused", str(exc), status=400) from exc
    return {"ok": True, "result": "asked" + _as(body, who), "task": made.id}


def _docs(root: Path, docs: Any) -> list[str]:
    """`review-task`'s `docs`, each one of the person's documents (`_persons`), else `bad-field`; [] when none is given.

    An agent's copy or a path that is no document is refused, as `review-counts` never lists them.
    """
    if docs is None:
        return []
    if not isinstance(docs, list) or not all(isinstance(d, str) for d in docs):
        raise ApiError("bad-field", "docs is a list of paths of your documents")
    mine = _persons(_scan(root))
    stray = [d for d in docs if d not in mine]
    if stray:
        raise ApiError("bad-field", f"{stray[0]} is not one of your documents; docs names a draft by its path")
    return list(docs)


def _task(root: Path, kind: str, on: dict[str, Any], text: str) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """(place, the ask's own fields, the documents that read the place) for a `review-task` of `kind`."""
    if kind == "read":
        nodes = on.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            raise ApiError("bad-field", "a read names its stubs in on.nodes")
        return {"node": str(nodes[0])}, {"nodes": nodes, **({"marks": on["marks"]} if on.get("marks") else {})}, []
    if kind == "digest":
        fields: dict[str, Any] = {k: on[k] for k in ("ref", "scope", "nodes", "marks") if k in on}
        return {"ref": str(on.get("ref"))}, fields, []
    if kind == "correct":
        return {"node": str(on.get("node"))}, {"text": text}, []
    if kind == "ask":
        if "ref" in on:
            place: dict[str, Any] = {"ref": str(on["ref"]), **({"page": on["page"]} if "page" in on else {})}
            readers: list[str] = []
        else:
            place, readers = _block(root, str(on.get("key") or ""))
        return place, {"text": text, **({"quote": on["quote"]} if on.get("quote") else {})}, readers
    if kind == "restate":
        target, readers = _target(root, str(on.get("result") or ""))
        return {target.kind: target.name}, {"target": target.to_dict(), "differs": text}, readers
    if kind == "which-result":
        place, readers = _block(root, str(on.get("key") or ""))
        return place, {"cites": str(on.get("ref") or "")}, readers
    raise ApiError(
        "bad-field", "kind is read, digest, ask, correct, restate or which-result; a formalization is formal-ask's"
    )


def _block(root: Path, key: str) -> tuple[dict[str, Any], list[str]]:
    """A block of a person's document as a note names it, and the documents that read it."""
    from loom.records.locate import block_hash, context_of

    result = _scan(root)
    node = result.nodes.get(key)
    if node is None or node.kind in ("master", "file"):
        raise ApiError("no-such-result", f"{key} is no block of this quilt; reload", status=404)
    block = {"key": node.key, "hash": block_hash(result, node.key), "context": context_of(result, node)}
    return {"block": block}, sorted(node.reached_by)


def _target(root: Path, result_key: str) -> tuple[Any, list[str]]:
    """A result's subject now: a draft's block by its label and text; a node waits for the node store."""
    from loom.evidence.web import DraftWeb, Here

    result = _scan(root)
    subject = DraftWeb(result).subject(Here("block", result_key))
    if subject is None:
        raise ApiError("no-such-result", f"{result_key} is no labelled result of a draft; reload", status=404)
    node = result.nodes[result_key]
    return subject, sorted(node.reached_by)


def _review_task_delete(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`review-task-delete`: the person withdraws an ask, which is deleting it from what waits; recorded as the reviewer whatever `author` names, which the answer says."""
    from loom.evidence.asks import AskRefused, replay, say

    who = _person(root, body)
    task = _str(body, "task", required=True) or ""
    found = replay(root).asks.get(task)
    if found is not None and found.withdrawn is not None:
        raise ApiError("closed", "this ask is withdrawn already; reload Review", status=409)
    try:
        say(root, who, "withdrawn", task)
    except AskRefused as exc:
        raise _refused(exc, task) from exc
    return {"ok": True, "result": "withdrawn" + _as(body, who)}


HANDLERS: dict[str, Handler] = {
    "review-accept": plain(_review_accept),
    "review-counts": plain(_review_counts),
    "review-list": plain(_review_list),
    "review-row": plain(_review_row),
    "review-answer": plain(_review_answer),
    "review-task": plain(_review_task),
    "review-task-delete": plain(_review_task_delete),
}
#: Of these, the ones that answer and change nothing the manifest shows.
READS: tuple[str, ...] = ("review-counts", "review-list", "review-row")
#: The ones the publisher does not rebuild after.
NO_REBUILD: tuple[str, ...] = READS
#: The ones that change records alone, so the publication builds from the last scan, which tells the viewer something changed.
RECORD_WRITES: tuple[str, ...] = ("review-answer", "review-task", "review-task-delete")
