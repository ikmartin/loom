"""Formalization: what asking an agent to formalize results comes to, the asking, and the person's attestation of a Lean statement (`docs/specs/evidence.md` §7)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loom.render.endpoints.base import ApiError, Handler, _scan, _str, plain
from loom.render.endpoints.review import _as, _person

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

    who = _person(root, body)
    result = _str(body, "result", required=True) or ""
    observation = _str(body, "observation", required=True) or ""
    drafts, web = webs(root)
    try:
        attest(root, web, here_of(drafts, result), observation, who, lean_now=files_unchanged(root))
    except ActRefused as exc:
        raise refusal(exc) from exc
    return {"ok": True, "result": "attested" + _as(body, who)}


class _Planner:
    """One read's way to a plan: the drafts' results as the Web reads them, the library's by its files, each as an `Item`, what each uses, and each as a list's row."""

    def __init__(self, root: Path) -> None:
        import json

        from loom.evidence.web import Joined, LibraryWeb
        from loom.evidence.webview import drafts
        from loom.paths import MANIFEST

        try:
            manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            manifest = {}
        self.manifest: dict[str, Any] = manifest
        self.drafts = drafts(_scan(root), manifest, root)
        self.library = LibraryWeb(root)
        self.web = Joined(self.drafts.web, self.library)
        self._nodes: dict[str, Any] = {}

    def _node(self, key: str) -> Any:
        from loom.evidence.status import status
        from loom.evidence.web import Here

        if key not in self._nodes:
            self._nodes[key] = status(self.drafts.evidence, self.web, Here("node", key), lean_now=self.drafts.lean_now)
        return self._nodes[key]

    def item(self, key: str) -> Any:
        from loom.evidence.plan import STATED, Item

        node = self.drafts.node(key)
        if node is not None:
            taxon = str(self.manifest.get("nodes", {}).get(key, {}).get("taxon") or node.taxon or "").lower()
            return Item(key, True, bool(node.labels), taxon in STATED, self.drafts.standing(key))
        held = self.library.file(key)
        return Item(key, False, True, held is not None and held[1].taxon in STATED, self._node(key))

    def uses(self, key: str) -> tuple[list[str], list[str]]:
        if self.drafts.node(key) is not None:
            statement, proofs = self.drafts.uses(key)
            return statement, [p for p, _ in proofs]
        held = self.library.file(key)
        # a library result is assumed, never proved: what its proofs use is not followed
        return ([u for u in held[1].uses if self.library.file(u) is not None] if held else []), []

    def key_of(self, key: str) -> tuple[str, str] | None:
        """A result's lasting name as records name it: a node's id, or a draft's label; None for a draft's result with none."""
        from loom.evidence.web import Here

        if self.drafts.is_library(key):
            return ("node", key)
        found = self.drafts.web.subject(Here("block", key))
        return found.key if found is not None else None

    def elaborated(self, found: Any) -> bool:
        """Whether a result's current Lean record is on its text now, still stands and elaborated: accepted, and the kernel's replay passed."""
        from loom.evidence.plan import elaborated

        return elaborated(self.drafts.evidence, found, self.drafts.lean_now)

    def before(self, target: str, found: Any) -> list[Any]:
        """What stands before `target` reads formalized, from the gate's own needs of the Lean the request will make (`plan.asked`, `status.needs`, `plan.needed`), the target's own Lean first."""
        from loom.evidence.plan import asked, needed, target_need
        from loom.evidence.status import needs
        from loom.evidence.web import Here

        here = Here("block", target)
        nodes, assumed, rests = asked(found, target, self.drafts.is_library, self.key_of)
        nodes += [n for kind, n in self.web.closure(here) if kind == "node" and n not in nodes]
        subject = self.web.subject(here)
        seen = frozenset({subject.name}) if subject is not None else frozenset()
        leaves = needs(self.drafts.evidence, self.web, nodes, assumed, self.drafts.lean_now, seen, list(self.web.cited(here)), here, rests)  # fmt: skip

        def own(key: tuple[str, str]) -> tuple[str, Any, bool] | None:
            if key[0] == "node":
                return (key[1], self._node(key[1]), self.elaborated(self._node(key[1]))) if self.drafts.is_library(key[1]) else None  # fmt: skip
            there = self.drafts.web.holder(key, here)
            if there is None or self.drafts.node(there.name) is None:
                return None
            standing = self.drafts.standing(there.name)
            return there.name, standing, self.elaborated(standing)

        mine = target_need(target, self.drafts.standing(target), self.elaborated(self.drafts.standing(target)))
        return ([mine] if mine is not None else []) + needed(leaves, own)

    def row(self, key: str) -> dict[str, Any]:
        from loom.evidence.webview import node_row

        if self.drafts.node(key) is not None:
            return self.drafts.row(key)
        held = self.library.file(key)
        return node_row(key, self._node(key), held[1] if held else None)

    def target(self, key: str) -> dict[str, Any]:
        row = self.row(key)
        fragment = self.manifest.get("nodes", {}).get(key, {}).get("fragment")
        return {"key": key, "name": row["name"], "title": row["title"], "doc": row["source"]["doc"], "statement": {"fragment": fragment}}  # fmt: skip


def _results(body: dict[str, Any], name: str, *, required: bool) -> list[str]:
    value = body.get(name)
    if value is None and not required:
        return []
    if not isinstance(value, list) or (required and not value) or not all(isinstance(k, str) and k for k in value):
        raise ApiError("bad-field", f"{name} is a {'nonempty ' if required else ''}list of results' keys")
    return list(dict.fromkeys(value))


def _planned(root: Path, body: dict[str, Any]) -> tuple[_Planner, list[str], list[str]]:
    """The planner for one read, the targets and the results chosen assumed for now; a target that is no result of the person's documents is `no-such-result` (404)."""
    planner = _Planner(root)
    targets = _results(body, "targets", required=True)
    assume = _results(body, "assume", required=False)
    for key in targets:
        if planner.drafts.node(key) is None:
            raise ApiError("no-such-result", f"{key} is no result of your documents; reload", status=404)
    return planner, targets, assume


def _formal_plan(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`formal-plan`: what asking an agent to formalize the targets comes to, and what stops it or stands before it reads formalized."""
    from loom.evidence.plan import plan

    planner, targets, assume = _planned(root, body)
    found = plan(targets, assume, planner.item, planner.uses, planner.before)
    row = planner.row
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for need in found.before:
        groups.setdefault((need.why, need.when), []).append({"cite": need.key} if need.why == "cite" else row(need.key))
    return {
        "ok": True,
        "targets": [planner.target(k) for k in found.targets],
        "state": [row(k) for k in found.state],
        "prove": [{**row(k), "assume": chosen} for k, chosen in found.prove],
        "assume": [{**row(k), "why": why} for k, why in found.assume],
        "formalized": [row(k) for k in found.formalized],
        "stops": [row(k) for k in found.stops],
        "before": [{"why": why, "when": when, "results": results} for (why, when), results in groups.items()],
    }


def _formal_ask(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`formal-ask`: one task for an agent for each target, its plan in it; refused `needs-label` while a target, or a result to state or prove, has no label, which loom never writes."""
    from loom.evidence.asks import AskRefused, ask
    from loom.evidence.asks import refusal as ask_refusal
    from loom.evidence.plan import plan
    from loom.evidence.web import Here

    who = _person(root, body)
    planner, targets, assume = _planned(root, body)
    plans = {t: plan([t], assume, planner.item, planner.uses) for t in targets}
    stops = list(dict.fromkeys(k for p in plans.values() for k in p.stops))
    if stops:
        names = ", ".join(planner.row(k)["name"] or k for k in stops)
        raise ApiError("needs-label", f"{names} needs a label first; add it in your source", status=409)

    def subject(key: str) -> dict[str, Any]:
        found = planner.web.subject(Here("block" if planner.drafts.node(key) is not None else "node", key))
        if found is None:
            raise ApiError("needs-label", f"{key} needs a label first; add it in your source", status=409)
        return found.to_dict()

    # every target's ask is made and checked before any is written, so a refusal leaves none written
    asks: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for key, p in plans.items():
        target = subject(key)
        fields = {
            "origin": planner.drafts.homes(key),
            "target": target,
            "state": [subject(k) for k in p.state],
            "prove": [subject(k) for k, chosen in p.prove if not chosen],
            "assume": [subject(k) for k, chosen in p.prove if chosen] + [subject(k) for k, _why in p.assume],
        }
        problem = ask_refusal(who, "formalize", "agent", {"label": target["label"]}, **fields)
        if problem:
            raise ApiError("refused", problem, status=400)
        asks.append(({"label": target["label"]}, fields))
    tasks = []
    for on, fields in asks:
        try:
            tasks.append(ask(root, who, "formalize", "agent", on, **fields).id)
        except AskRefused as exc:
            raise ApiError("refused", str(exc), status=400) from exc
    return {"ok": True, "tasks": tasks, "result": f"asked for {len(tasks)}" + _as(body, who)}


HANDLERS: dict[str, Handler] = {
    "formal-plan": plain(_formal_plan),
    "formal-ask": plain(_formal_ask),
    "formal-attest": plain(_formal_attest),
}
#: Of these, the ones that answer and change nothing the manifest shows.
READS: tuple[str, ...] = ("formal-plan",)
#: The ones the publisher does not rebuild after.
NO_REBUILD: tuple[str, ...] = READS
#: The ones that change records alone, so the publication builds from the last scan, which tells the viewer something changed.
RECORD_WRITES: tuple[str, ...] = ("formal-ask", "formal-attest")
