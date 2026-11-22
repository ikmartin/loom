"""Formalization: the person's attestation of a Lean statement (`docs/specs/evidence.md` §7)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loom.render.endpoints.base import ApiError, Handler, _scan, _str, plain

#: The status each refusal of an act answers with; any other is 409.
_STATUS = {"author-only": 403, "agent-only": 403, "no-such-result": 404, "no-such-node": 404, "no-such-proposal": 404, "refused": 400}  # fmt: skip


def refusal(exc: Any) -> ApiError:
    """An act's refusal (`evidence.acts.ActRefused`) as the write API answers it."""
    return ApiError(exc.code, str(exc), status=_STATUS.get(exc.code, 409))


def webs(root: Path) -> tuple[Any, Any]:
    """The drafts' web over the publisher's scan, and that web joined with the library's."""
    from loom.evidence.web import DraftWeb, Joined, LibraryWeb

    drafts = DraftWeb(_scan(root))
    return drafts, Joined(drafts, LibraryWeb(root))


def here_of(drafts: Any, result: str) -> Any:
    """Where a result is, by what a row names it with: a draft's block by its key, which is asked first since it has the shape of a node's id, else a node by its id; `no-such-result` (404) otherwise."""
    from loom.evidence.subjects import is_node
    from loom.evidence.web import Here

    if any(n.key == result for n in drafts.blocks):
        return Here("block", result)
    if is_node(result):
        return Here("node", result)
    raise ApiError("no-such-result", f"{result} is no result of this quilt; reload", status=404)


def _formal_attest(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`formal-attest`: the person's word that the Lean statement of the observation says what the result says, on its texts now; recorded as the reviewer whatever `author` names, which the answer says."""
    from loom.evidence.acts import ActRefused, attest
    from loom.evidence.status import files_unchanged
    from loom.render.endpoints.review import _as, _person

    who = _person(root, body)
    result = _str(body, "result", required=True) or ""
    observation = _str(body, "observation", required=True) or ""
    drafts, web = webs(root)
    try:
        attest(root, web, here_of(drafts, result), observation, who, lean_now=files_unchanged(root))
    except ActRefused as exc:
        raise refusal(exc) from exc
    return {"ok": True, "result": "attested" + _as(body, who)}


HANDLERS: dict[str, Handler] = {
    "formal-attest": plain(_formal_attest),
}
#: Of these, the ones that answer and change nothing the manifest shows.
READS: tuple[str, ...] = ()
#: The ones the publisher does not rebuild after.
NO_REBUILD: tuple[str, ...] = READS
#: The ones that change records alone, so the publication builds from the last scan, which tells the viewer something changed.
RECORD_WRITES: tuple[str, ...] = ("formal-attest",)
